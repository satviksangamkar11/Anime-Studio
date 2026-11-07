"""Tests for tools/make_lut.py (WP8). Files are built in tmp_path; the CLI runs in a subprocess."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from core.lut import apply_cube, parse_cube

TOOL = Path(__file__).resolve().parents[2] / "tools" / "make_lut.py"
DRAFT = "DRAFT — owner to approve"


def _pack(styles, pack_id="tpack"):
    styles.mkdir(parents=True, exist_ok=True)
    band = {"luma_mean": [0, 1], "sat_mean": [0, 1], "phase": "PH-1"}
    data = {
        "pack_id": pack_id,
        "version": "0.1",
        "status": "draft",
        "acts": {
            "HOOK": {**band, "role": "hook", "lut": f"luts/{pack_id}/HOOK.cube",
                     "grade": {"exposure": 1}},
            "PLAIN": {**band, "role": "neutral", "lut": f"luts/{pack_id}/PLAIN.cube"},
        },
    }
    (styles / f"{pack_id}.json").write_text(json.dumps(data), encoding="utf-8")
    return styles


def _run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, encoding="utf-8")


def _target(styles, act="HOOK"):
    return styles / "luts" / "tpack" / f"{act}.cube"


def test_builds_draft_cube_with_draft_title(tmp_path):
    styles = _pack(tmp_path / "styles")
    res = _run("tpack", "HOOK", "--styles-dir", str(styles), "--size", "5")
    assert res.returncode == 0, res.stderr
    target = _target(styles)
    assert target.is_file()
    assert target.read_text(encoding="utf-8").splitlines()[0] == f'TITLE "{DRAFT}"'
    assert str(target) in res.stdout


def test_second_run_is_byte_identical(tmp_path):
    styles = _pack(tmp_path / "styles")
    assert _run("tpack", "HOOK", "--styles-dir", str(styles), "--size", "5").returncode == 0
    first = _target(styles).read_bytes()
    assert _run("tpack", "HOOK", "--styles-dir", str(styles), "--size", "5").returncode == 0
    assert _target(styles).read_bytes() == first


def test_existing_non_draft_cube_refused_unless_force(tmp_path):
    styles = _pack(tmp_path / "styles")
    target = _target(styles)
    target.parent.mkdir(parents=True)
    target.write_text('TITLE "Resolve export"\nLUT_3D_SIZE 2\n', encoding="utf-8")
    before = target.read_bytes()
    res = _run("tpack", "HOOK", "--styles-dir", str(styles), "--size", "5")
    assert res.returncode == 2
    assert target.read_bytes() == before
    res = _run("tpack", "HOOK", "--styles-dir", str(styles), "--size", "5", "--force")
    assert res.returncode == 0, res.stderr
    assert target.read_text(encoding="utf-8").splitlines()[0] == f'TITLE "{DRAFT}"'


def test_act_without_grade_is_identity_with_warn(tmp_path):
    styles = _pack(tmp_path / "styles")
    res = _run("tpack", "PLAIN", "--styles-dir", str(styles), "--size", "5")
    assert res.returncode == 0, res.stderr
    assert "WARN" in res.stdout + res.stderr
    cube = parse_cube(_target(styles, "PLAIN"))
    assert cube["table"][1] == pytest.approx((0.25, 0.0, 0.0), abs=1e-6)
    assert cube["table"][5] == pytest.approx((0.0, 0.25, 0.0), abs=1e-6)


def test_unknown_act_exits_2(tmp_path):
    styles = _pack(tmp_path / "styles")
    res = _run("tpack", "NOSUCH", "--styles-dir", str(styles), "--size", "5")
    assert res.returncode == 2
    assert "NOSUCH" in res.stderr


def test_unknown_pack_exits_2(tmp_path):
    styles = _pack(tmp_path / "styles")
    res = _run("nopack", "HOOK", "--styles-dir", str(styles), "--size", "5")
    assert res.returncode == 2


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_ffmpeg_lut3d_matches_predicted_brightness(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    styles = _pack(tmp_path / "styles")
    res = _run("tpack", "HOOK", "--styles-dir", str(styles))
    assert res.returncode == 0, res.stderr
    cube_path = _target(styles)
    work = tmp_path / "work"
    work.mkdir()
    Image.new("RGB", (64, 64), (128, 128, 128)).save(work / "in.png")
    shutil.copy(cube_path, work / "hook.cube")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "in.png",
                    "-vf", "lut3d=file=hook.cube", "out.png"], cwd=work, check=True)
    px = Image.open(work / "out.png").convert("RGB").getpixel((32, 32))
    cube = parse_cube(cube_path)
    predicted = apply_cube(cube["table"], cube["size"], (128 / 255,) * 3)
    for chan in range(3):
        assert abs(px[chan] - predicted[chan] * 255) <= 6
    assert px[0] > 128 + 20
