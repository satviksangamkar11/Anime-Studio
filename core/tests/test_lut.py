"""Tests for core/lut.py (WP8 cube maths and shot-match LUT). Pure functions, no files outside tmp_path."""
import math

import pytest

from core.lut import (
    act_reference_lab,
    apply_cube,
    combine,
    grade_fn,
    identity_fn,
    lab_to_srgb,
    parse_cube,
    shot_match_fn,
    shot_match_offset,
    write_cube,
    write_shot_lut,
)
from core.style_pack import delta_e_2000, srgb_to_lab

HEX20 = [
    "#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#00FFFF", "#FF00FF",
    "#808080", "#BF4040", "#1A2B3C", "#DEADBE", "#123456", "#ABCDEF", "#FE9A20", "#4A90E2",
    "#7FFF00", "#800000", "#2F4F4F", "#F0E68C",
]


def _srgb_dec(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _srgb_enc(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def test_lab_round_trip_20_colours():
    assert len(HEX20) == 20
    for hx in HEX20:
        rgb = [int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        back = lab_to_srgb(srgb_to_lab(hx))
        assert max(abs(a - b) for a, b in zip(back, rgb)) < 0.002, hx


def test_identity_fn_is_identity():
    assert identity_fn(0.1, 0.2, 0.3) == (0.1, 0.2, 0.3)


def test_identity_cube_grid_and_layout(tmp_path):
    p = tmp_path / "id.cube"
    write_cube(p, identity_fn, size=5, title="ident")
    raw = p.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    lines = raw.decode("utf-8").split("\n")[:-1]
    assert lines[0] == 'TITLE "ident"'
    assert lines[1] == "LUT_3D_SIZE 5"
    assert lines[2] == "DOMAIN_MIN 0.0 0.0 0.0"
    assert lines[3] == "DOMAIN_MAX 1.0 1.0 1.0"
    rows = lines[4:]
    assert len(rows) == 125
    assert rows[0] == "0.000000 0.000000 0.000000"
    assert rows[1] == "0.250000 0.000000 0.000000"   # red changes fastest
    assert rows[5] == "0.000000 0.250000 0.000000"   # then green
    assert rows[25] == "0.000000 0.000000 0.250000"  # then blue
    for idx, row in enumerate(rows):
        r, g, b = idx % 5, (idx // 5) % 5, idx // 25
        assert row == f"{r / 4:.6f} {g / 4:.6f} {b / 4:.6f}"


def test_cube_bytes_deterministic(tmp_path):
    fn = grade_fn({"exposure": 0.5, "temp": -4})
    a = tmp_path / "a.cube"
    b = tmp_path / "b.cube"
    write_cube(a, fn, size=9, title="DRAFT — owner to approve")
    write_cube(b, fn, size=9, title="DRAFT — owner to approve")
    assert a.read_bytes() == b.read_bytes()
    assert "—".encode("utf-8") in a.read_bytes()


def test_parse_round_trip(tmp_path):
    fn = grade_fn({"exposure": 1, "contrast": 10})
    p = tmp_path / "g.cube"
    write_cube(p, fn, size=5, title="rt")
    cube = parse_cube(p)
    assert cube["title"] == "rt"
    assert cube["size"] == 5
    assert len(cube["table"]) == 125
    for idx in (1, 5, 25, 124):
        r, g, b = idx % 5, (idx // 5) % 5, idx // 25
        expect = fn(r / 4, g / 4, b / 4)
        assert all(abs(x - y) <= 1e-6 for x, y in zip(cube["table"][idx], expect))


def test_exposure_plus_one_ev_doubles_linear_mid_grey():
    r, _, _ = grade_fn({"exposure": 1})(0.5, 0.5, 0.5)
    expected = _srgb_enc(2 * _srgb_dec(0.5))
    assert r == pytest.approx(expected, abs=0.005)


def test_contrast_plus_20_moves_quarter_points_apart():
    fn = grade_fn({"contrast": 20})
    assert fn(0.75, 0.75, 0.75)[0] == pytest.approx(0.8)
    assert fn(0.25, 0.25, 0.25)[0] == pytest.approx(0.2)


def test_saturation_minus_100_is_grey():
    r, g, b = grade_fn({"saturation": -100})(0.9, 0.3, 0.1)
    assert abs(r - g) < 1e-6 and abs(g - b) < 1e-6


def test_temp_plus_10_warms():
    r, g, b = grade_fn({"temp": 10})(0.5, 0.5, 0.5)
    assert r == pytest.approx(0.525)
    assert g == pytest.approx(0.5)
    assert b == pytest.approx(0.475)


def test_shadow_lift_plus_8_raises_black_and_keeps_mid():
    fn = grade_fn({"shadow_lift": 8})
    assert fn(0, 0, 0) == pytest.approx((0.02, 0.02, 0.02), abs=1e-9)
    assert fn(0.5, 0.5, 0.5) == pytest.approx((0.5, 0.5, 0.5), abs=1e-9)


def test_negative_crush_lowers_shadows_only():
    fn = grade_fn({"shadow_crush": -8})
    assert fn(0.1, 0.1, 0.1)[0] == pytest.approx(0.1 - 0.02 * 0.36, abs=1e-9)
    assert fn(0.5, 0.5, 0.5)[0] == pytest.approx(0.5, abs=1e-9)


def test_missing_keys_and_unused_keys_are_identity():
    for grade in ({}, {"highlight": 50, "bloom_pct": 10, "vignette_pct": 20}):
        assert grade_fn(grade)(0.3, 0.6, 0.9) == pytest.approx((0.3, 0.6, 0.9), abs=1e-12)


def test_grade_output_is_clamped():
    assert max(grade_fn({"exposure": 3})(1, 1, 1)) <= 1.0
    out = grade_fn({"contrast": 100})(0.0, 0.9, 1.0)
    assert min(out) >= 0.0 and max(out) <= 1.0


def test_shot_match_offset_clamped_and_exact():
    clip = (50.0, 0.0, 0.0)
    far = shot_match_offset(clip, (80.0, 0.0, 0.0), 3)
    assert math.dist(far, (0, 0, 0)) == pytest.approx(3.0, abs=1e-9)
    assert far == pytest.approx((3.0, 0.0, 0.0), abs=1e-9)
    near = shot_match_offset(clip, (51.0, 1.0, 0.0), 3)
    assert near == pytest.approx((1.0, 1.0, 0.0), abs=1e-9)


def test_shot_match_reference_none_is_zero_and_identity():
    off = shot_match_offset((50.0, 1.0, 1.0), None, 3)
    assert off == (0.0, 0.0, 0.0)
    assert shot_match_fn(off)(0.2, 0.4, 0.6) == pytest.approx((0.2, 0.4, 0.6), abs=1e-12)


def test_shot_match_pins_black_and_white():
    fn = shot_match_fn((2.0, 1.0, 1.0))
    assert fn(0, 0, 0) == pytest.approx((0, 0, 0), abs=1e-9)
    assert fn(1, 1, 1) == pytest.approx((1, 1, 1), abs=1e-9)


def test_shot_match_mid_grey_moves_within_clamp_plus_half(tmp_path):
    clip = srgb_to_lab((128, 128, 128))
    off = shot_match_offset(clip, srgb_to_lab("#A08060"), 3.0)
    assert math.hypot(*off) == pytest.approx(3.0, abs=1e-9)
    p = tmp_path / "sm.cube"
    write_shot_lut(p, identity_fn, off, size=33)
    cube = parse_cube(p)
    out = apply_cube(cube["table"], cube["size"], (0.5, 0.5, 0.5))
    ints = tuple(round(v * 255) for v in out)
    moved = delta_e_2000(srgb_to_lab(ints), clip)
    assert 0.5 < moved <= 3.0 + 0.5
    direct = shot_match_fn(off)(0.5, 0.5, 0.5)
    assert max(abs(a - b) for a, b in zip(out, direct)) < 0.01


def test_combine_applies_in_order():
    def add_red(r, g, b):
        return (r + 0.1, g, b)

    def double_red(r, g, b):
        return (r * 2, g, b)

    assert combine(add_red, double_red)(0.1, 0.2, 0.3) == pytest.approx((0.4, 0.2, 0.3))
    assert combine(double_red, add_red)(0.1, 0.2, 0.3) == pytest.approx((0.3, 0.2, 0.3))


def test_act_reference_lab_from_phase_key():
    pack = {
        "colour_script": {"phases": [{"id": "PH-1", "key": "#808080"}, {"id": "PH-2", "key": None}]},
        "acts": {"HOOK": {"phase": "PH-1"}, "BUILD": {"phase": "PH-2"}},
    }
    assert act_reference_lab(pack, "HOOK") == pytest.approx(srgb_to_lab("#808080"))
    assert act_reference_lab(pack, "BUILD") is None
    assert act_reference_lab(pack, "NOPE") is None
