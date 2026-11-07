"""A26: tools/calibrate_sat_ceiling.py computes and writes gates.sat_avg_ceiling; the release test fails while it is null."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import calibrate_sat_ceiling as cal  # noqa: E402
from core.frame_metrics import per_frame_stats  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def png(path, rgb):
    Image.new("RGB", (64, 64), rgb).save(path)
    return str(path)


def test_percentile_nearest_rank():
    assert cal.percentile([1, 2, 3, 4, 5], 100) == 5
    assert cal.percentile([1, 2, 3, 4, 5], 50) == 3
    assert cal.percentile([7], 1) == 7


@needs_ffmpeg
def test_calibrate_matches_the_measured_frames(tmp_path):
    red, grey = png(tmp_path / "red.png", (220, 30, 30)), png(tmp_path / "grey.png", (120, 120, 120))
    res = cal.calibrate([red, grey], 100)
    expected = max(per_frame_stats(red)[0]["SATAVG"], per_frame_stats(grey)[0]["SATAVG"])
    assert res["ceiling"] == round(expected, 2) and res["frames"] == 2 and res["files"] == 2
    assert res["ceiling"] > cal.calibrate([grey], 100)["ceiling"]


def test_calibrate_refuses_bad_input(tmp_path):
    with pytest.raises(ValueError):
        cal.calibrate([], 99)
    with pytest.raises(ValueError):
        cal.calibrate([str(tmp_path / "missing.png")], 99)
    with pytest.raises(ValueError):
        cal.calibrate([str(tmp_path / "x")], 0)


def test_write_ceiling_replaces_only_the_value(tmp_path):
    core = tmp_path / "core.json"
    shutil.copy(ROOT / "core" / "core.json", core)
    before = json.loads(core.read_text(encoding="utf-8"))
    cal.write_ceiling(core, 123.45)
    after = json.loads(core.read_text(encoding="utf-8"))
    assert after["gates"]["sat_avg_ceiling"] == 123.45
    after["gates"]["sat_avg_ceiling"] = before["gates"]["sat_avg_ceiling"]
    assert after == before
    cal.write_ceiling(core, 99)   # a second write replaces a number too
    assert json.loads(core.read_text(encoding="utf-8"))["gates"]["sat_avg_ceiling"] == 99.0


def test_write_ceiling_refuses_a_file_without_the_key(tmp_path):
    bad = tmp_path / "core.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        cal.write_ceiling(bad, 1)


@needs_ffmpeg
def test_cli_prints_without_writing_and_writes_with_flag(tmp_path):
    ref = png(tmp_path / "ref.png", (200, 60, 60))
    core = tmp_path / "core.json"
    shutil.copy(ROOT / "core" / "core.json", core)
    run = lambda *extra: subprocess.run([sys.executable, str(ROOT / "tools" / "calibrate_sat_ceiling.py"), ref, "--core", str(core), *extra],
                                        capture_output=True, text=True)
    p = run()
    assert p.returncode == 0 and "not written" in p.stdout
    assert json.loads(core.read_text(encoding="utf-8"))["gates"]["sat_avg_ceiling"] is None   # printing does not write
    p = run("--write")
    assert p.returncode == 0 and isinstance(json.loads(core.read_text(encoding="utf-8"))["gates"]["sat_avg_ceiling"], float)
    assert subprocess.run([sys.executable, str(ROOT / "tools" / "calibrate_sat_ceiling.py")], capture_output=True).returncode == 2


@pytest.mark.skipif(not os.environ.get("ANIME_RELEASE"), reason="release gate: set ANIME_RELEASE=1 once the reference frames are approved")
def test_release_requires_a_calibrated_sat_avg_ceiling():
    value = json.loads((ROOT / "core" / "core.json").read_text(encoding="utf-8"))["gates"]["sat_avg_ceiling"]
    assert isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0, \
        "gates.sat_avg_ceiling is still null: run tools/calibrate_sat_ceiling.py on the approved reference frames with --write"
