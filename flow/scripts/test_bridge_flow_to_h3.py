import os
import subprocess
import sys
from fractions import Fraction

import pytest
from PIL import Image, ImageStat

import bridge_flow_to_h3 as b

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_flow_to_h3.py")


def flow_like(path, w, h, red, blue):
    """Rows < red are pure red, rows >= h-blue are pure blue, a green gradient fills the rest."""
    im = Image.new("RGB", (w, h))
    kept = h - red - blue
    for y in range(h):
        if y < red:
            c = (255, 0, 0)
        elif y >= h - blue:
            c = (0, 0, 255)
        else:
            c = (0, round(255 * (y + 0.5 - red) / kept), 0)
        im.paste(c, (0, y, w, y + 1))
    im.save(path)
    return str(path)


def cli(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


def test_864x1536_centre_window_exact_no_stretch(tmp_path):
    src = flow_like(tmp_path / "src.png", 1536, 2752, red=11, blue=11)
    dst = tmp_path / "out.png"
    r = b.bridge(src, str(dst), size=(864, 1536))

    top = Fraction(32, 3)  # window 1536 x 2730.667, centred -> 10.667 px off top and bottom
    assert r["box"] == pytest.approx((0.0, float(top), 1536.0, float(2752 - top)), abs=1e-9)
    assert r["crop_px_removed"] == pytest.approx(21.333, abs=1e-3)
    assert r["aspect_error_pct"] < 1e-9
    assert r["src_size"] == (1536, 2752) and r["size"] == (864, 1536)

    with Image.open(dst) as im:
        assert im.size == (864, 1536)
        out = im.convert("RGB")
    # the red and blue marked rows were cut away (a stretch or off-centre crop would show them)
    assert ImageStat.Stat(out.crop((0, 0, 864, 1))).mean[0] < 128
    assert ImageStat.Stat(out.crop((0, 1535, 864, 1536))).mean[2] < 128
    # interior gradient matches the window mapping exactly (no stretch, no shift)
    scale = float(2752 - 2 * top) / 1536
    for y in range(100, 1436, 37):
        c = float(top) + (y + 0.5) * scale
        expected = 255 * (c - 11) / (2752 - 22)
        assert abs(out.getpixel((432, y))[1] - expected) <= 2


def test_768x1344_window_centred(tmp_path):
    src = flow_like(tmp_path / "src.png", 1536, 2752, red=32, blue=32)
    dst = tmp_path / "out.png"
    r = b.bridge(src, str(dst), size=(768, 1344))

    assert r["box"] == (0.0, 32.0, 1536.0, 2720.0)  # 1536 x 2688, 32 px off each end
    assert r["crop_px_removed"] == 64.0
    with Image.open(dst) as im:
        assert im.size == (768, 1344)
        out = im.convert("RGB")
    assert ImageStat.Stat(out.crop((0, 0, 768, 1))).mean[0] < 128
    assert ImageStat.Stat(out.crop((0, 1343, 768, 1344))).mean[2] < 128


def test_landscape_source_refused_for_portrait_target(tmp_path):
    src = tmp_path / "land.png"
    Image.new("RGB", (2752, 1536), (10, 20, 30)).save(src)
    dst = tmp_path / "out.png"
    with pytest.raises(ValueError, match="aspect"):
        b.bridge(str(src), str(dst), size=(864, 1536))
    assert not dst.exists()


@pytest.mark.parametrize("size", [(850, 1536), (864, 1500)])
def test_non_multiple_of_32_refused(tmp_path, size):
    src = flow_like(tmp_path / "src.png", 1536, 2752, red=11, blue=11)
    with pytest.raises(ValueError, match="divisible by 32"):
        b.bridge(src, str(tmp_path / "out.png"), size=size)


def test_aspect_tolerance_is_a_parameter(tmp_path):
    src = flow_like(tmp_path / "src.png", 1536, 2752, red=11, blue=11)  # 0.78% off 864x1536
    b.bridge(src, str(tmp_path / "ok.png"), size=(864, 1536))  # default 3% passes
    with pytest.raises(ValueError, match="aspect"):
        b.bridge(src, str(tmp_path / "no.png"), size=(864, 1536), tol_pct=0.5)


def test_cli_single_file_then_skip(tmp_path):
    src = flow_like(tmp_path / "src.png", 1536, 2752, red=11, blue=11)
    dst = tmp_path / "sub" / "out.png"
    p = cli("--src", src, "--out", str(dst), "--size", "864x1536")
    assert p.returncode == 0 and p.stdout.startswith("OK"), p.stdout + p.stderr
    with Image.open(dst) as im:
        assert im.size == (864, 1536)
    p2 = cli("--src", src, "--out", str(dst), "--size", "864x1536")
    assert p2.returncode == 0 and p2.stdout.startswith("SKIP"), p2.stdout + p2.stderr


def test_cli_final_dir_refuses_bad_skips_repeats_and_ignores_others(tmp_path):
    final = tmp_path / "final"
    final.mkdir()
    flow_like(final / "LEAP-03A__candidate_v01__final.png", 1536, 2752, red=11, blue=11)
    Image.new("RGB", (2752, 1536), (0, 0, 0)).save(final / "LEAP-04A__candidate_v01__final.png")
    Image.new("RGB", (64, 64)).save(final / "LEAP-03A__candidate_v01__clean.png")
    out = tmp_path / "out"

    p = cli("--final-dir", str(final), "--out-dir", str(out), "--size", "864x1536")
    assert p.returncode == 1
    assert "OK       LEAP-03A" in p.stdout
    assert "REFUSED  LEAP-04A" in p.stdout
    assert "clean" not in p.stdout
    assert (out / "LEAP-03A_864x1536.png").exists()
    assert not (out / "LEAP-04A_864x1536.png").exists()

    p2 = cli("--final-dir", str(final), "--out-dir", str(out), "--size", "864x1536")
    assert p2.returncode == 1
    assert "SKIP     LEAP-03A" in p2.stdout


def test_json_mode_lists_each_source_and_prints_nothing_else(tmp_path):
    """G9: --json prints one JSON list (OK, REFUSED) with the box and the reason; exit 1 because one was refused."""
    import json
    final = tmp_path / "final"
    final.mkdir()
    flow_like(final / "LEAP-03A__candidate_v01__final.png", 1536, 2752, red=11, blue=11)
    Image.new("RGB", (2752, 1536), (0, 0, 0)).save(final / "LEAP-04A__candidate_v01__final.png")
    out = tmp_path / "out"
    p = cli("--final-dir", str(final), "--out-dir", str(out), "--size", "864x1536", "--json")
    assert p.returncode == 1, p.stdout + p.stderr
    recs = json.loads(p.stdout)
    by = {r["label"]: r for r in recs}
    assert by["LEAP-03A"]["status"] == "OK" and len(by["LEAP-03A"]["box"]) == 4 and by["LEAP-03A"]["removed_px"] > 0
    assert by["LEAP-04A"]["status"] == "REFUSED" and "aspect" in by["LEAP-04A"]["reason"]
    assert (out / "LEAP-03A_864x1536.png").exists()


def test_json_dry_run_has_dry_status_and_writes_nothing(tmp_path):
    import json
    final = tmp_path / "final"
    final.mkdir()
    flow_like(final / "LEAP-03A__candidate_v01__final.png", 1536, 2752, red=11, blue=11)
    out = tmp_path / "out"
    p = cli("--final-dir", str(final), "--out-dir", str(out), "--dry-run", "--json")
    assert p.returncode == 0 and json.loads(p.stdout)[0]["status"] == "DRY"
    assert not out.exists()


def test_pattern_flag_selects_other_files_and_empty_json_is_a_list(tmp_path):
    import json
    final = tmp_path / "final"
    final.mkdir()
    flow_like(final / "ENV_X__candidate_v01__final.png", 1536, 2752, red=11, blue=11)
    out = tmp_path / "out"
    p = cli("--final-dir", str(final), "--out-dir", str(out), "--pattern", "ENV_*__final.png", "--json")
    assert p.returncode == 0 and [r["label"] for r in json.loads(p.stdout)] == ["ENV_X"]
    none = cli("--final-dir", str(final), "--out-dir", str(out), "--pattern", "NOPE*.png", "--json")
    assert none.returncode == 1 and none.stdout.strip() == "[]"


def test_dry_run_writes_nothing(tmp_path):
    final = tmp_path / "final"
    final.mkdir()
    flow_like(final / "LEAP-03A__candidate_v01__final.png", 1536, 2752, red=11, blue=11)
    out = tmp_path / "out"  # does not exist yet
    p = cli("--final-dir", str(final), "--out-dir", str(out), "--dry-run")
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.startswith("DRY-RUN  LEAP-03A 1536x2752")
    assert not out.exists()
