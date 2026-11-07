"""WP8 post tests. Every clip, pack, story and episode is built in tmp_path (PNG frames + sine audio, 96x160 at 24 fps).
Skipped as a whole when ffmpeg or ffprobe is not on PATH."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageStat

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import post  # noqa: E402  (also puts the repo root on sys.path)
from core.lut import identity_fn, write_cube  # noqa: E402
from h3.assemble_reel import loudness_plan, write_loudness_json  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                reason="ffmpeg not on PATH")

W, H, FPS = 96, 160, 24
GREY = (90, 120, 160)
RED = (200, 40, 40)
PACK = {
    "pack_id": "test_pack", "version": "1.0", "status": "draft",
    "colour_script": {"phases": [{"id": "PH-PLAY", "role": "play", "key": "#5A7898", "luma_mean": [0, 1],
                                  "sat_mean": [0, 1], "lut": "luts/test_pack/hook.cube"}]},
    "acts": {
        "HOOK": {"role": "hook", "phase": "PH-PLAY", "lut": "luts/test_pack/hook.cube", "luma_mean": [0, 1],
                 "sat_mean": [0, 1], "grain": True, "grade": {"exposure": 0.0, "contrast": 0.0}},
        "BUILD": {"role": "build", "phase": "PH-PLAY", "lut": "luts/test_pack/build.cube",
                  "luma_mean": [0, 1], "sat_mean": [0, 1], "grade": {"exposure": 0.2}},
    },
    "palettes": {"P1": {"characters": ["CHAR_A"], "time_lock": None,
                        "colors": {"Gold": {"hex": "#C9A227", "role": "accent", "usage_pct": 10, "neon": False}},
                        "special_laws": []}},
    "frame_law": {"min_dL_focal_vs_bg": None, "max_neon_hues_per_shot": 0, "pure_white_area_cap_frac": 0.5},
    "impact": {"allowed_types": ["white_out", "black_out", "inverted", "chroma_split", "alpha_sil"],
               "type_max_frames": {"white_out": 4, "black_out": 4, "inverted": 4, "chroma_split": 4, "alpha_sil": 4}},
    "typography": {"display": "Test Display", "sacred": "Test Sacred", "subtitle_latin": "Arial",
                   "subtitle_devanagari": "Nirmala UI", "min_px_at_1080w": 30, "font_dir": "fonts"},
    "prompt_forbidden_words": [], "guardrails": [], "sound_sync": {"enabled": False},
    "flash_colours": {"white": "#FFFFFF", "black": "#000000"},
}
STORY = {"slug": "test", "style_pack": "test_pack", "platform": "shorts_9x16", "language": "en",
         "episode_target_s": [1, 60]}


def _make_clip(path, colours):
    """One clip: one PNG per colour (24 fps) and a 440 Hz sine track of the same length."""
    frames = path.parent / (path.stem + "_frames")
    frames.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(colours):
        Image.new("RGB", (W, H), c).save(frames / f"f_{i:04d}.png")
    secs = len(colours) / FPS
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(frames / "f_%04d.png"),
                    "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={secs:.4f}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)


def _shot(sid, act="HOOK", ed=48, impacts=(), captions=None):
    return {"shot_id": sid, "episode_id": "EP1",
            "timing_and_lattice": {"fps": FPS, "trim_in_frame": 0, "trim_out_frame": ed, "editorial_frames": ed,
                                   "trim_in_sec": 0.0, "trim_out_sec": round(ed / FPS, 2),
                                   "editorial_duration_sec": round(ed / FPS, 2)},
            "metadata": {"look": {"act": act, "impact_frames": list(impacts),
                                  "hook": {"type": "H-01", "caption": "Hook line"}},
                         "captions": list(captions or [])}}


def _setup(tmp_path, clips=None, shots=None, loud=True):
    clips = clips if clips is not None else {"SHOT_A": [GREY] * 48, "SHOT_B": [GREY] * 48}
    styles = tmp_path / "styles"
    (styles / "luts" / "test_pack").mkdir(parents=True)
    (styles / "test_pack.json").write_text(json.dumps(PACK), encoding="utf-8")
    write_cube(styles / "luts" / "test_pack" / "hook.cube", identity_fn, size=2, title="identity test")
    story = tmp_path / "story.json"
    story.write_text(json.dumps(STORY), encoding="utf-8")
    build = tmp_path / "build"
    for sid, colours in clips.items():
        _make_clip(build / sid / "clip.mp4", colours)
    shots = shots if shots is not None else [_shot(sid) for sid in clips]
    (build / "episode.json").write_text(json.dumps({"episode_id": "EP1", "shots": shots}), encoding="utf-8")
    if loud:
        measured = {sid: -18.0 for sid in clips}
        write_loudness_json(build / "loudness.json", measured, loudness_plan(measured))
    return build, story, styles


def _run(build, story, styles, **kw):
    return post.run_post(build, story, styles_dir=styles, fonts_dir=build.parent / "nofonts", **kw)


def _probe_streams(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,pix_fmt,color_space,color_transfer,color_primaries,color_range",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)["streams"]


def _frame_mean(video, n, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"select=eq(n\\,{n})",
                    "-frames:v", "1", str(out)], check=True)
    with Image.open(out) as im:
        return ImageStat.Stat(im.convert("L")).mean[0]


def _rules(report, rule, level=None):
    return [e for e in report["entries"] if e["rule"] == rule and (level is None or e["level"] == level)]


def test_two_shot_episode_exports_bt709_tv_with_audio(tmp_path):
    build, story, styles = _setup(tmp_path)
    report = _run(build, story, styles)
    assert report["fail"] is False, report["entries"]
    assert report["written"] is True
    final = build / "EP1_final.mp4"
    assert final.is_file()
    assert (build / "colour_report.json").is_file()
    assert (build / "loudness.json").is_file()
    streams = _probe_streams(final)
    video = [s for s in streams if s["codec_type"] == "video"]
    assert len(video) == 1
    assert video[0]["pix_fmt"] == "yuv420p"
    assert video[0]["color_space"] == "bt709"
    assert video[0]["color_transfer"] == "bt709"
    assert video[0]["color_primaries"] == "bt709"
    assert video[0]["color_range"] == "tv"
    assert [s["codec_type"] for s in streams] == ["video", "audio"]   # H3 audio kept, no music stream added


def test_injected_four_flash_second_refuses(tmp_path, capsys):
    flash = [(255, 255, 255) if i % 2 == 0 else (0, 0, 0) for i in range(8)] + [GREY] * 40   # 8 alternating frames = 4 flashes
    build, story, styles = _setup(tmp_path, clips={"SHOT_A": flash, "SHOT_B": [GREY] * 48})
    exit_code = post.main([str(build), "--story", str(story), "--styles-dir", str(styles),
                           "--fonts-dir", str(tmp_path / "nofonts")])
    assert exit_code == 1
    assert not (build / "EP1_final.mp4").exists()
    assert not list((build / "post").glob("*.tmp.mp4"))
    report = json.loads((build / "colour_report.json").read_text(encoding="utf-8"))
    assert report["fail"] is True and report["written"] is False
    assert [e for e in report["entries"] if e["rule"] == "F1" and e["level"] == "FAIL"]


def test_dry_run_prints_graph_and_starts_nothing(tmp_path, monkeypatch):
    build, story, styles = _setup(tmp_path)

    def boom(*a, **k):
        raise AssertionError("dry run must not start a subprocess")

    monkeypatch.setattr(post.subprocess, "run", boom)
    monkeypatch.setattr(post.subprocess, "Popen", boom)
    report = post.run_post(build, story, styles_dir=styles, fonts_dir=tmp_path / "nofonts", dry_run=True)
    graph = report["graph"]
    for needle in ("lut3d", "format=gbrp16le", "scale=out_color_matrix=bt709", "sws_dither=ed"):
        assert needle in graph
    assert "auto_scale" not in graph
    assert not (build / "EP1_final.mp4").exists()
    assert not (build / "post").exists()
    assert not (build / "colour_report.json").exists()
    assert report["fail"] is False


def test_impact_filters_and_alpha_sil_warning(tmp_path, monkeypatch):
    impacts = [{"at_s": 0.5, "type": "inverted", "frames": 2},
               {"at_s": 1.0, "type": "chroma_split", "frames": 3},
               {"at_s": 1.5, "type": "alpha_sil", "frames": 2}]
    build, story, styles = _setup(tmp_path, shots=[_shot("SHOT_A", impacts=impacts), _shot("SHOT_B")])
    monkeypatch.setattr(post.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no")))
    report = post.run_post(build, story, styles_dir=styles, fonts_dir=tmp_path / "nofonts", dry_run=True)
    graph = report["graph"]
    assert "negate:enable='between(n,12,13)'" in graph          # 0.5 s = frame 12, 2 frames
    assert "rgbashift=rh=-8:bh=8:enable='between(n,24,26)'" in graph   # 1.0 s, 3 frames, +-8 px at 1080 wide
    assert "alpha" not in graph
    alpha = _rules(report, "POST", "WARN")
    assert any("alpha_sil" in e["message"] for e in alpha)
    assert not _rules(report, "POST", "FAIL")


def test_white_out_replaces_two_frames(tmp_path):
    build, story, styles = _setup(tmp_path, shots=[_shot("SHOT_A", impacts=[{"at_s": 1.0, "type": "white_out",
                                                                              "frames": 2}]),
                                                   _shot("SHOT_B")])
    report = _run(build, story, styles)
    assert report["written"] is True, report["entries"]
    final = build / "EP1_final.mp4"
    assert _frame_mean(final, 24, build / "f24.png") > 240
    assert _frame_mean(final, 25, build / "f25.png") > 240
    assert _frame_mean(final, 23, build / "f23.png") < 240


def test_g3_refuses_different_colours_and_passes_same(tmp_path):
    build, story, styles = _setup(tmp_path, clips={"SHOT_A": [GREY] * 48, "SHOT_B": [RED] * 48})
    report = _run(build, story, styles)
    assert _rules(report, "G3", "FAIL")
    assert report["written"] is False

    build2, story2, styles2 = _setup(tmp_path / "same")
    report2 = _run(build2, story2, styles2)
    assert not _rules(report2, "G3")


def test_g5_loop_seam_is_a_warning_only(tmp_path):
    fade = [tuple(int(c + (60 - c) * i / 47) for c in (200, 200, 200)) for i in range(48)]
    build, story, styles = _setup(tmp_path, clips={"SHOT_A": [GREY] * 48, "SHOT_B": fade})
    report = _run(build, story, styles)
    seam = _rules(report, "G5")
    assert seam and all(e["level"] == "WARN" for e in seam)
    assert not any(e["rule"] == "G5" and e["level"] == "FAIL" for e in report["entries"])


def test_upscale_hook_runs_once_per_clip(tmp_path):
    log = tmp_path / "upscale.log"
    script = tmp_path / "copy_up.py"
    script.write_text("import shutil, sys\nopen(sys.argv[3], 'a').write(sys.argv[1] + '\\n')\n"
                      "shutil.copyfile(sys.argv[1], sys.argv[2])\n", encoding="utf-8")
    build, story, styles = _setup(tmp_path / "ok")
    cmd = f'"{sys.executable}" "{script}" {{in}} {{out}} "{log}"'
    report = _run(build, story, styles, upscale_cmd=cmd)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2
    assert not _rules(report, "POST", "FAIL")

    failing = tmp_path / "fail_up.py"
    failing.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    build2, story2, styles2 = _setup(tmp_path / "bad")
    report2 = _run(build2, story2, styles2, upscale_cmd=f'"{sys.executable}" "{failing}" {{in}} {{out}}')
    assert _rules(report2, "POST", "FAIL")
    assert report2["written"] is False
    assert not (build2 / "EP1_final.mp4").exists()


@pytest.mark.skipif("subtitles" not in subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                                                       capture_output=True, text=True).stdout,
                    reason="ffmpeg has no subtitles filter")
def test_captions_written_and_burned(tmp_path):
    build, story, styles = _setup(tmp_path)
    report = _run(build, story, styles)
    ass = (build / "post" / "captions.ass").read_text(encoding="utf-8")
    assert "Hook line" in ass
    assert report["written"] is True


def test_no_ffmpeg_auto_scale_node(tmp_path):
    build, story, styles = _setup(tmp_path)
    report = _run(build, story, styles)
    assert report["written"] is True
    argv = ["verbose" if a == "error" else a for a in report["commands"][-1]]
    argv[-1] = "verbose_check.mp4"
    r = subprocess.run(argv, cwd=str(build / "post"), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    assert r.returncode == 0
    assert "auto_scale" not in (r.stdout + r.stderr)


def test_malformed_episode_json_is_a_post_fail(tmp_path, capsys):
    build, story, styles = _setup(tmp_path)
    (build / "episode.json").write_text("{not json", encoding="utf-8")
    code = post.main([str(build), "--story", str(story), "--styles-dir", str(styles)])
    assert code == 1
    report = json.loads((build / "colour_report.json").read_text(encoding="utf-8"))
    assert [e for e in report["entries"] if e["rule"] == "POST" and e["level"] == "FAIL"]


def test_missing_clip_is_a_post_fail(tmp_path):
    build, story, styles = _setup(tmp_path)
    (build / "SHOT_B" / "clip.mp4").unlink()
    report = _run(build, story, styles)
    assert any(e["rule"] == "POST" and e["level"] == "FAIL" and "SHOT_B" in e["message"]
               for e in report["entries"])
    assert report["written"] is False
