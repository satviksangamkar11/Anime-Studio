"""clip_tools.py gates (G2, G6, G7) on ffmpeg clips built in tmp_path. Packs and stories are written to tmp_path."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_tools  # noqa: E402

FFMPEG = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")

PACK = {
    "pack_id": "pack_test", "version": "t", "status": "draft",
    "colour_script": {"phases": [{"id": "PH-1", "role": "play", "luma_mean": [0, 1], "sat_mean": [0, 1],
                                  "lut": "luts/pack_test/a.cube"}]},
    "acts": {
        "BUILD": {"role": "build", "phase": "PH-1", "lut": "luts/pack_test/build.cube",
                  "luma_mean": [0.0, 1.0], "sat_mean": [0.0, 1.0]},
        "BRIGHT": {"role": "peak", "phase": "PH-1", "lut": "luts/pack_test/bright.cube",
                   "luma_mean": [0.6, 0.9], "sat_mean": [0.0, 1.0]},
    },
    "palettes": {},
    "frame_law": {"min_dL_focal_vs_bg": 10, "max_neon_hues_per_shot": 2, "pure_white_area_cap_frac": 0.5},
    "impact": {"allowed_types": ["flash"], "type_max_frames": {"flash": 3}},
}


def make_clip(path, src):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-c:v", "libx264",
                    "-crf", "0", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def look(**extra):
    base = {"palette_id": "p", "act": "BUILD", "phase": "PH-1", "focal": "CHAR-A",
            "focal_value": "lightest", "hook": {"type": "H-01", "caption": "x"},
            "impact_frames": [], "vfx": [], "accent_use": False, "hold_purpose": None}
    base.update(extra)
    return base


@pytest.fixture
def env(tmp_path):
    styles = tmp_path / "styles"
    styles.mkdir()
    (styles / "pack_test.json").write_text(json.dumps(PACK), encoding="utf-8")
    story = tmp_path / "story.json"
    story.write_text(json.dumps({"slug": "t", "style_pack": "pack_test", "platform": "shorts_9x16",
                                 "language": "en", "episode_target_s": [30, 60]}), encoding="utf-8")
    return {"styles": styles, "story": story, "dir": tmp_path}


def shot_file(env, shot, name="shot.json"):
    p = env["dir"] / name
    p.write_text(json.dumps(shot), encoding="utf-8")
    return p


def run(env, clip, shot, out=None):
    return clip_tools.gates(clip, shot, env["story"], out_dir=out or env["dir"], styles_dir=env["styles"])


def rules(report, level=None):
    return [e["rule"] for e in report["entries"] if level is None or e["level"] == level]


STEADY = "color=c=0x336699:s=96x160:r=24:d=5"
JUMP = "color=c=black:s=96x160:r=24:d=2,geq=lum='if(gte(N,24),117,40)':cb=128:cr=128"


@FFMPEG
def test_steady_colour_has_no_fail(env):
    clip = make_clip(env["dir"] / "steady.mp4", STEADY)
    report = run(env, clip, {"id": "S01", "look": look()})
    assert report["fail"] is False and rules(report, "FAIL") == []


@FFMPEG
def test_slow_ramp_over_five_seconds_gives_drift_warn(env):
    clip = make_clip(env["dir"] / "ramp.mp4",
                     "color=c=black:s=96x160:r=24:d=5,geq=lum='255*T/5':cb=128:cr=128")
    report = run(env, clip, {"id": "S01", "look": look()})
    assert report["fail"] is False
    assert any(e["rule"] == "G2" and "drift" in e["message"] for e in report["entries"])


@FFMPEG
def test_undeclared_luma_jump_is_fail(env):
    clip = make_clip(env["dir"] / "jump.mp4", JUMP)
    report = run(env, clip, {"id": "S01", "look": look()})
    assert report["fail"] is True
    fails = [e for e in report["entries"] if e["level"] == "FAIL"]
    assert len(fails) == 1 and fails[0]["rule"] == "G2" and "frame 24" in fails[0]["message"]


@FFMPEG
def test_declared_impact_of_the_jump_passes(env):
    clip = make_clip(env["dir"] / "jump_decl.mp4", JUMP)
    shot = {"id": "S01", "look": look(impact_frames=[{"at_s": 1.0, "type": "flash", "frames": 1}])}
    assert run(env, clip, shot)["fail"] is False


@FFMPEG
def test_declared_impact_uses_trim_in_frame(env):
    clip = make_clip(env["dir"] / "jump_trim.mp4", JUMP)
    shot = {"id": "S01", "timing_and_lattice": {"trim_in_frame": 12},
            "look": look(impact_frames=[{"at_s": 0.5, "type": "flash", "frames": 1}])}
    assert run(env, clip, shot)["fail"] is False


@FFMPEG
def test_luma_step_report_is_capped_at_five_plus_summary(env):
    clip = make_clip(env["dir"] / "alt.mp4",
                     "color=c=black:s=96x160:r=24:d=2,geq=lum='if(mod(N,2),117,40)':cb=128:cr=128")
    report = run(env, clip, {"id": "S01", "look": look()})
    fails = [e for e in report["entries"] if e["level"] == "FAIL"]
    assert len(fails) == 6 and "more" in fails[-1]["message"]


@FFMPEG
def test_mean_luma_outside_act_range_warns(env):
    clip = make_clip(env["dir"] / "dark.mp4", "color=c=black:s=96x160:r=24:d=1")
    report = run(env, clip, {"id": "S01", "look": look(act="BRIGHT")})
    assert any(e["rule"] == "G2" and e["level"] == "WARN" and "luma" in e["message"] for e in report["entries"])


@FFMPEG
def test_mostly_white_clip_gives_g6_warn(env):
    clip = make_clip(env["dir"] / "white.mp4", "color=c=white:s=96x160:r=24:d=1")
    report = run(env, clip, {"id": "S01", "look": look()})
    assert any(e["rule"] == "G6" and e["level"] == "WARN" for e in report["entries"])


@FFMPEG
def test_g7_focal_box_must_be_the_extreme_in_focal_value_direction(env):
    clip = make_clip(env["dir"] / "split.mp4",
                     "color=c=black:s=96x160:r=24:d=1,geq=lum='if(lt(X,48),200,40)':cb=128:cr=128")
    dark_right = {"id": "S01", "look": look(focal_box=[0.5, 0, 1, 1], focal_value="lightest")}
    bright_left = {"id": "S01", "look": look(focal_box=[0, 0, 0.5, 1], focal_value="lightest")}
    dark_right_darkest = {"id": "S01", "look": look(focal_box=[0.5, 0, 1, 1], focal_value="darkest")}
    no_box = {"id": "S01", "look": look()}
    wrong = run(env, clip, dark_right)
    assert any(e["rule"] == "G7" and "lightest" in e["message"] for e in wrong["entries"])
    assert "G7" not in rules(run(env, clip, bright_left))
    assert "G7" not in rules(run(env, clip, dark_right_darkest))
    assert "G7" not in rules(run(env, clip, no_box))


@FFMPEG
def test_malformed_shot_json_is_a_p0_fail_entry(env):
    bad = env["dir"] / "bad_shot.json"
    bad.write_text("{not json", encoding="utf-8")
    report = clip_tools.gates(env["dir"] / "none.mp4", bad, env["story"], out_dir=env["dir"],
                              styles_dir=env["styles"])
    assert report["fail"] is True and report["entries"][0]["rule"] == "P0"


@FFMPEG
def test_missing_clip_is_a_g2_fail_entry(env):
    report = run(env, env["dir"] / "missing.mp4", {"id": "S01", "look": look()})
    assert report["fail"] is True and rules(report, "FAIL") == ["G2"]


@FFMPEG
def test_missing_look_block_warns_and_still_checks_luma(env):
    clip = make_clip(env["dir"] / "nolook.mp4", JUMP)
    report = run(env, clip, {"id": "S01"})
    assert any("no look block" in e["message"] for e in report["entries"])
    assert report["fail"] is True


@FFMPEG
def test_cli_writes_report_and_exit_code(env):
    clip = make_clip(env["dir"] / "cli_jump.mp4", JUMP)
    shot = shot_file(env, {"id": "S01", "look": look()})
    out = env["dir"] / "reports"
    argv = ["gates", str(clip), "--shot", str(shot), "--story", str(env["story"]),
            "--styles-dir", str(env["styles"]), "--out", str(out)]
    assert clip_tools.main(argv) == 1
    data = json.loads((out / "cli_jump_gates.json").read_text(encoding="utf-8"))
    assert data["fail"] is True

    steady = make_clip(env["dir"] / "cli_steady.mp4", STEADY)
    ok_shot = shot_file(env, {"id": "S01", "look": look()}, name="ok_shot.json")
    assert clip_tools.main(["gates", str(steady), "--shot", str(ok_shot), "--story", str(env["story"]),
                            "--styles-dir", str(env["styles"]), "--out", str(out)]) == 0
