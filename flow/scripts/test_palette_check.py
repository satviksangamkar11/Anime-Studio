"""G1 palette gate (WP5): palette_check.py, tools/measure_plate.py and the filer hook.
All images are made with Pillow in tmp_path; packs are written to tmp_path. No network, no model calls."""
import json
import os
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import palette_check as pc  # noqa: E402
from core.style_pack import srgb_to_lab, delta_e_2000  # noqa: E402

FILER = HERE / "file_flow_download.py"
MEASURE = ROOT / "tools" / "measure_plate.py"
EDIT = "34ba531b-b5c7-43fa-82a5-7b7746b57016"
SKY, GROUND, WATER = (120, 170, 230), (110, 80, 50), (40, 90, 120)
PALE_WATER = (175, 205, 215)
PLATE_SIZE = (96, 160)
WATER_BOX = [0, 0.7, 1, 1]
PACK, ENV = "test_pack", "ENV-X"


def bands(size, water=WATER):
    """Sky / ground / water bands: sky 0-40%, ground 40-70%, water 70-100% of the height."""
    w, h = size
    im = Image.new("RGB", size, SKY)
    d = ImageDraw.Draw(im)
    d.rectangle([0, int(h * 0.4), w - 1, int(h * 0.7) - 1], fill=GROUND)
    d.rectangle([0, int(h * 0.7), w - 1, h - 1], fill=water)
    return im


def noisy(im, seed=1):
    rnd = random.Random(seed)
    out = im.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            px[x, y] = tuple(max(0, min(255, c + rnd.randint(-3, 3))) for c in px[x, y])
    return out


def run_measure(png, env_id, styles, *extra):
    args = [sys.executable, str(MEASURE), str(png), env_id, "--pack", PACK, "--styles-dir", str(styles), *extra]
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")


def write_pack(styles: Path, data=None):
    styles.mkdir(parents=True, exist_ok=True)
    data = data if data is not None else {"pack_id": PACK, "status": "draft"}
    (styles / f"{PACK}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return styles / f"{PACK}.json"


def measured_env(plate):
    m = pc.measure(plate, regions=[{"name": "water", "box": WATER_BOX}])
    lab = {"L": m["L"], "a": m["a"], "b": m["b"]}
    return {"id": ENV, "measured": dict(lab, luma=m["luma"]), "regions": [
        {"name": "water", "box": WATER_BOX, "measured": dict(m["regions"]["water"])}], "accepted_siblings": []}


def fails(entries):
    return [e for e in entries if e["level"] == "FAIL"]


def warns(entries):
    return [e for e in entries if e["level"] == "WARN"]


# ---- measure ----
def test_measure_solid_colour_is_its_lab():
    img = Image.new("RGB", (40, 60), (200, 30, 60))
    m = pc.measure(img)
    expect = srgb_to_lab((200, 30, 60))
    assert abs(m["L"] - expect[0]) <= 0.5
    assert abs(m["a"] - expect[1]) <= 0.5
    assert abs(m["b"] - expect[2]) <= 0.5


def test_measure_luma_white_and_black():
    assert abs(pc.measure(Image.new("RGB", (8, 8), (255, 255, 255)))["luma"] - 1.0) < 0.01
    assert pc.measure(Image.new("RGB", (8, 8), (0, 0, 0)))["luma"] < 0.01


def test_measure_regions_measured_separately():
    img = Image.new("RGB", (40, 60), (255, 0, 0))
    img.paste((0, 0, 255), (20, 0, 40, 60))
    m = pc.measure(img, regions=[{"name": "left", "box": [0, 0, 0.5, 1]},
                                 {"name": "right", "box": [0.5, 0, 1, 1]}])
    red, blue = srgb_to_lab((255, 0, 0)), srgb_to_lab((0, 0, 255))
    assert delta_e_2000(m["regions"]["left"].values(), red) < 0.5
    assert delta_e_2000(m["regions"]["right"].values(), blue) < 0.5


# ---- check_keyframe ----
def test_matching_keyframe_passes(tmp_path):
    plate = bands(PLATE_SIZE)
    env = measured_env(plate)
    key = noisy(plate)
    assert fails(pc.check_keyframe(key, env, aspect="9:16")) == []


def test_pale_water_keyframe_fails_on_water(tmp_path):
    env = measured_env(bands(PLATE_SIZE))
    pale = bands(PLATE_SIZE, water=PALE_WATER)
    bad = fails(pc.check_keyframe(pale, env, aspect="9:16"))
    assert bad, "pale water must FAIL"
    assert any("water" in e["message"] for e in bad)
    assert all(e["rule"] == "G1" for e in bad)


def test_wrong_orientation_fails_and_portrait_passes():
    plate = bands(PLATE_SIZE)
    env = measured_env(plate)
    landscape = plate.transpose(Image.Transpose.ROTATE_90)
    bad = fails(pc.check_keyframe(landscape, env, aspect="9:16"))
    assert any("wrong orientation" in e["message"] for e in bad)
    assert fails(pc.check_keyframe(plate, env, aspect="9:16")) == []
    land_env = measured_env(landscape)
    assert fails(pc.check_keyframe(landscape, land_env, aspect="16:9")) == []
    assert any("wrong orientation" in e["message"] for e in fails(pc.check_keyframe(plate, land_env, aspect="16:9")))


def test_no_measured_lab_is_one_warn_only():
    plate = bands(PLATE_SIZE)
    entries = pc.check_keyframe(plate, {"id": ENV, "measured": {}}, aspect="9:16")
    assert fails(entries) == []
    assert len(entries) == 1 and entries[0]["level"] == "WARN"
    assert "G1 skipped" in entries[0]["message"]
    assert pc.check_keyframe(plate, None)[0]["level"] == "WARN"


def test_unmeasured_sibling_warns_and_bad_sibling_fails():
    plate = bands(PLATE_SIZE)
    env = measured_env(plate)
    env["accepted_siblings"] = ["P2"]
    w = pc.check_keyframe(plate, env, aspect="9:16")
    assert fails(w) == [] and any("P2" in e["message"] for e in warns(w))
    env["sibling_measured"] = {"P2": {"L": 95, "a": 0, "b": 0}}
    f = fails(pc.check_keyframe(plate, env, aspect="9:16"))
    assert any("P2" in e["message"] for e in f)


def test_junk_input_gives_fail_entry_not_traceback(tmp_path):
    plate = bands(PLATE_SIZE)
    assert fails(pc.check_keyframe(plate, "nope"))[0]["rule"] == "G1"
    assert fails(pc.check_keyframe(plate, {"id": ENV, "measured": {"L": "hi", "a": 0, "b": 0}}))
    assert fails(pc.check_keyframe(str(tmp_path / "missing.png"), measured_env(plate)))[0]["rule"] == "G1"


# ---- check_download ----
def test_check_download_missing_pack_or_env_is_warn(tmp_path):
    styles = tmp_path / "styles"
    write_pack(styles)
    r = pc.check_download(bands(PLATE_SIZE), "no_such_pack", ENV, styles_dir=styles)
    assert r["fail"] is False and r["entries"][0]["level"] == "WARN"
    r = pc.check_download(bands(PLATE_SIZE), PACK, "NO-ENV", styles_dir=styles)
    assert r["fail"] is False and "G1 skipped" in r["entries"][0]["message"]


# ---- tools/measure_plate.py ----
def test_measure_plate_writes_env_and_second_run_is_byte_identical(tmp_path):
    styles = tmp_path / "styles"
    path = write_pack(styles)
    plate = tmp_path / "plate.png"
    bands(PLATE_SIZE).save(plate)
    args = (plate, ENV, styles, "--region", "water:0,0.7,1,1")
    assert run_measure(*args).returncode == 0
    first = path.read_bytes()
    pack = json.loads(first)
    env = pack["environments"][0]
    assert set(env["measured"]) == {"L", "a", "b", "luma"}
    assert env["regions"][0]["name"] == "water" and set(env["regions"][0]["measured"]) == {"L", "a", "b"}
    assert b"\r\n" not in first
    assert run_measure(*args).returncode == 0
    assert path.read_bytes() == first


def test_measure_plate_sibling_added_once(tmp_path):
    styles = tmp_path / "styles"
    path = write_pack(styles)
    plate = tmp_path / "plate.png"
    bands(PLATE_SIZE).save(plate)
    assert run_measure(plate, ENV, styles).returncode == 0
    for _ in range(2):
        assert run_measure(plate, ENV, styles, "--sibling", "PLATE-2").returncode == 0
    env = json.loads(path.read_text(encoding="utf-8"))["environments"][0]
    assert env["accepted_siblings"] == ["PLATE-2"]
    assert set(env["sibling_measured"]["PLATE-2"]) == {"L", "a", "b"}


def test_measure_plate_refuses_missing_png_or_pack(tmp_path):
    styles = tmp_path / "styles"
    write_pack(styles)
    assert run_measure(tmp_path / "nope.png", ENV, styles).returncode == 2
    plate = tmp_path / "plate.png"
    bands(PLATE_SIZE).save(plate)
    r = subprocess.run([sys.executable, str(MEASURE), str(plate), ENV, "--pack", "absent_pack",
                        "--styles-dir", str(styles)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2


# ---- filer hook (G1) ----
def setup_pack(tmp_path):
    styles = tmp_path / "styles"
    write_pack(styles)
    plate = tmp_path / "plate.png"
    bands(PLATE_SIZE).save(plate)
    assert run_measure(plate, ENV, styles, "--region", "water:0,0.7,1,1").returncode == 0
    return styles


def run_filer(src, root, styles, pack=PACK, env_id=ENV):
    env = dict(os.environ, FLOW_OUT_ROOT=str(root), FLOW_ADHYAY="1", FLOW_MAX_AGE_S="300",
               PYTHONIOENCODING="utf-8", FLOW_ASPECT="9:16", FLOW_APPROVED_DHASH="", FLOW_LINEAGE="",
               FLOW_DECIDED_BY="", FLOW_STYLE_PACK=pack, FLOW_ENV_ID=env_id,
               FLOW_STYLES_DIR=str(styles) if styles else "")
    args = [sys.executable, str(FILER), str(src), "KRISHNA_TURNAROUND", "v01", f"edit/{EDIT}",
            "", "references", "", "", ""]
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env=env)


def test_filer_refuses_pale_water_and_files_nothing(tmp_path):
    styles = setup_pack(tmp_path)
    src = tmp_path / "download.jpg"
    bands((1536, 2752), water=PALE_WATER).save(src, "JPEG", quality=95)
    root = tmp_path / "anime_kaliya"
    r = run_filer(src, root, styles)
    assert r.returncode == 2, r.stderr
    assert "REFUSED: palette gate G1" in r.stderr
    refs = root / "adhyay_01"          # the filer's sub-folder argument is empty here, so files sit in the chapter folder
    palette = refs / "KRISHNA_TURNAROUND__candidate_v01.png.palette.json"
    assert palette.is_file()
    entries = json.loads(palette.read_text(encoding="utf-8"))
    assert any(e["level"] == "FAIL" and e["rule"] == "G1" for e in entries)
    assert not list(refs.glob("*__candidate_v01.png")) and not list(refs.glob("*__2K_source.jpg"))
    assert not (root / "adhyay_01" / "flow_log.jsonl").exists()


def test_filer_files_matching_picture(tmp_path):
    styles = setup_pack(tmp_path)
    src = tmp_path / "download.jpg"
    bands((1536, 2752)).save(src, "JPEG", quality=95)
    root = tmp_path / "anime_kaliya"
    r = run_filer(src, root, styles)
    assert r.returncode == 0, r.stderr
    assert (root / "adhyay_01" / "KRISHNA_TURNAROUND__candidate_v01.png").is_file()


def test_filer_one_palette_var_refused(tmp_path):
    styles = setup_pack(tmp_path)
    src = tmp_path / "download.jpg"
    bands((1536, 2752)).save(src, "JPEG", quality=95)
    r = run_filer(src, tmp_path / "anime_kaliya", styles, env_id="")
    assert r.returncode == 2
    assert "FLOW_STYLE_PACK and FLOW_ENV_ID must be set together" in r.stderr
