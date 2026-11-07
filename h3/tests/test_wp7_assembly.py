"""WP7 assembly tests: delivery flags, G3 colour seams, loudness pass-through. Clips are made in tmp_path."""
import os
import shutil
import subprocess

import pytest

from core.style_pack import load_core
from h3.assemble_reel import (attach_colour_seams, build_ffmpeg_assembly_plan, colour_seams, loudness_plan,
                              write_assembly_script, write_loudness_json)
from h3.render_controller import _write_assembly
from h3.tests.synth import build_story

FFMPEG = shutil.which("ffmpeg") is not None
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg not on PATH")


def _clip(path, colour, frames=24):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=64x64:r=24",
                    "-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return str(path)


def _shot(sid, trim_in=0, trim_out=24, act=None):
    shot = {"shot_id": sid, "episode_id": "EP_T",
            "timing_and_lattice": {"fps": 24, "trim_in_frame": trim_in, "trim_out_frame": trim_out,
                                   "editorial_frames": trim_out - trim_in}}
    if act is not None:
        shot["metadata"] = {"look": {"act": act}}
    return shot


# ---- 1. delivery flags ----

def _cmd_and_filter(tmp_path, story):
    shots = story["episodes"][0]["shots"]
    plan = build_ffmpeg_assembly_plan(shots, "out.mp4")
    clips = [str(tmp_path / f"c{i}.mp4") for i in range(len(shots))]
    paths = write_assembly_script(plan, clips, str(tmp_path / "asm"))
    with open(paths["cmd"], encoding="utf-8") as f:
        cmd = f.read()
    return plan, cmd


def test_delivery_flags_present_in_assemble_cmd(tmp_path):
    story = build_story(str(tmp_path / "story"))
    _, cmd = _cmd_and_filter(tmp_path, story)
    d = load_core()["delivery"]
    flags = (f"-c:v {d['codec']} -crf {d['crf']} -pix_fmt {d['pix_fmt']} -colorspace {d['colorspace']} "
             f"-color_primaries {d['color_primaries']} -color_trc {d['color_trc']} -color_range {d['color_range']} "
             f"-c:a {d['audio']['codec']} -b:a {d['audio']['bitrate']} -movflags +faststart")
    assert flags in cmd
    assert '-map "[vout]" -map "[aout]"' in cmd and f"-r {load_core()['fps']}" in cmd
    assert cmd.index('-map "[aout]"') < cmd.index(flags) < cmd.index('"out.mp4"')


def test_filter_ends_with_bt709_scale_node(tmp_path):
    story = build_story(str(tmp_path / "story"))
    plan = build_ffmpeg_assembly_plan(story["episodes"][0]["shots"], "out.mp4")
    assert plan["filter_complex"].endswith(
        "concat=n=3:v=1:a=1[vcat][aout];[vcat]scale=out_color_matrix=bt709:out_range=tv[vout]")


def test_plan_carries_no_seams_and_note_without_clips(tmp_path):
    story = build_story(str(tmp_path / "story"))
    plan = build_ffmpeg_assembly_plan(story["episodes"][0]["shots"], "out.mp4")
    assert plan["colour_seams"] == []
    assert plan["colour_seams_note"] == "no clips yet: G3 not run"


# ---- 2. G3 colour seams ----

def test_colour_seams_missing_clip_is_fail_entry(tmp_path):
    shots = [_shot("A"), _shot("B")]
    entries = colour_seams([str(tmp_path / "missing_a.mp4"), str(tmp_path / "missing_b.mp4")], shots)
    assert entries and all(e["rule"] == "G3" and e["level"] == "FAIL" for e in entries)
    assert any("missing_a.mp4" in e["message"] for e in entries)


def test_colour_seams_unreadable_clip_is_fail_entry(tmp_path):
    bad = tmp_path / "junk.mp4"
    bad.write_bytes(b"not a video at all")
    entries = colour_seams([str(bad), str(bad)], [_shot("A"), _shot("B")])
    assert entries and all(e["rule"] == "G3" and e["level"] == "FAIL" for e in entries)


@needs_ffmpeg
def test_colour_seams_short_clip_is_fail_entry(tmp_path):
    short = _clip(tmp_path / "short.mp4", "red", frames=12)
    ok = _clip(tmp_path / "ok.mp4", "red", frames=24)
    entries = colour_seams([short, ok], [_shot("A", 0, 30), _shot("B", 0, 24)])
    assert len(entries) == 1 and entries[0]["rule"] == "G3" and "short.mp4" in entries[0]["message"]


@needs_ffmpeg
def test_colour_seams_different_colour_is_one_g3_fail(tmp_path):
    a, b = _clip(tmp_path / "a.mp4", "red"), _clip(tmp_path / "b.mp4", "blue")
    entries = colour_seams([a, b], [_shot("A"), _shot("B")])
    assert len(entries) == 1
    e = entries[0]
    assert e["rule"] == "G3" and e["level"] == "FAIL" and e["shot"] == "A"
    assert "between A and B" in e["message"] and "dE" in e["message"]


@needs_ffmpeg
def test_colour_seams_same_colour_has_no_entries(tmp_path):
    a, b = _clip(tmp_path / "a.mp4", "red"), _clip(tmp_path / "b.mp4", "red")
    assert colour_seams([a, b], [_shot("A"), _shot("B")]) == []


@needs_ffmpeg
def test_colour_seams_skipped_when_act_changes(tmp_path):
    a, b = _clip(tmp_path / "a.mp4", "red"), _clip(tmp_path / "b.mp4", "blue")
    shots = [_shot("A", act="ACT_1"), _shot("B", act="ACT_2")]
    assert colour_seams([a, b], shots) == []


@needs_ffmpeg
def test_colour_seams_same_act_still_checked(tmp_path):
    a, b = _clip(tmp_path / "a.mp4", "red"), _clip(tmp_path / "b.mp4", "blue")
    shots = [_shot("A", act="ACT_1"), _shot("B", act="ACT_1")]
    assert len(colour_seams([a, b], shots)) == 1


def test_attach_colour_seams_without_clips_sets_note(tmp_path):
    plan = {"colour_seams": [], "colour_seams_note": "no clips yet: G3 not run"}
    out = attach_colour_seams(plan, [str(tmp_path / "x.mp4"), str(tmp_path / "y.mp4")],
                              [_shot("A"), _shot("B")])
    assert out is plan
    assert plan["colour_seams"] == [] and plan["colour_seams_note"] == "no clips yet: G3 not run"


@needs_ffmpeg
def test_attach_colour_seams_with_clips_sets_entries(tmp_path):
    a, b = _clip(tmp_path / "a.mp4", "red"), _clip(tmp_path / "b.mp4", "blue")
    plan = {"colour_seams": [], "colour_seams_note": "no clips yet: G3 not run"}
    attach_colour_seams(plan, [a, b], [_shot("A"), _shot("B")])
    assert len(plan["colour_seams"]) == 1 and plan["colour_seams"][0]["rule"] == "G3"
    assert "colour_seams_note" not in plan


# ---- 3. loudness pass-through ----

def test_loudness_json_is_passed_to_filter(tmp_path):
    story = build_story(str(tmp_path / "story"))
    ep = story["episodes"][0]
    shots = ep["shots"]
    ep_dir = tmp_path / "ep"
    ep_dir.mkdir()
    measured = {s["shot_id"]: v for s, v in zip(shots, (-23.7, -20.0, -18.0))}
    write_loudness_json(str(ep_dir / "loudness.json"), measured, loudness_plan(measured))
    out = _write_assembly(ep, shots, str(ep_dir))
    with open(out["filter"], encoding="utf-8") as f:
        fc = f.read()
    assert fc.count("volume=") == 3 and fc.count("alimiter=") == 3
    for i in range(3):
        chain = fc[fc.index(f"[{i}:a]atrim="):]
        chain = chain[:chain.index(f"[a{i}]")]
        assert chain.index("volume=") < chain.index("afade=t=in")
        assert chain.index("alimiter=") < chain.index("afade=t=out")


def test_without_loudness_json_filter_is_todays_chain(tmp_path):
    story = build_story(str(tmp_path / "story"))
    ep = story["episodes"][0]
    shots = ep["shots"]
    ep_dir = tmp_path / "ep"
    ep_dir.mkdir()
    out = _write_assembly(ep, shots, str(ep_dir))
    with open(out["filter"], encoding="utf-8") as f:
        assert f.read() == build_ffmpeg_assembly_plan(shots, f"{ep['episode_id']}.mp4")["filter_complex"]
    assert "volume=" not in open(out["filter"], encoding="utf-8").read()
    assert "colour_seams" not in out


def test_corrupt_loudness_json_raises_value_error(tmp_path):
    story = build_story(str(tmp_path / "story"))
    ep = story["episodes"][0]
    ep_dir = tmp_path / "ep"
    ep_dir.mkdir()
    (ep_dir / "loudness.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="loudness.json"):
        _write_assembly(ep, ep["shots"], str(ep_dir))
    (ep_dir / "loudness.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="loudness.json"):
        _write_assembly(ep, ep["shots"], str(ep_dir))


@needs_ffmpeg
def test_controller_attaches_colour_seams_when_clips_exist(tmp_path):
    story = build_story(str(tmp_path / "story"))
    ep = story["episodes"][0]
    ep_dir = tmp_path / "ep"
    for s in ep["shots"]:
        d = ep_dir / s["shot_id"]
        d.mkdir(parents=True)
        _clip(d / "clip.mp4", "gray", frames=24)
    out = _write_assembly(ep, ep["shots"], str(ep_dir))
    assert isinstance(out["colour_seams"], int)
    assert os.path.isfile(out["cmd"])
