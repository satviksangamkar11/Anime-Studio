"""Tests for director/image_gates.py (spec J11). Tiny synthetic arrays; every expectation worked out by hand.

Hand arithmetic used below:
- A 16x16 image with block=8 has four 8x8 tiles: top-left, top-right, bottom-left, bottom-right.
- A flat tile that is identical in A and B gives SSIM exactly 1.
- A flat tile of 0 in A and 1.0 in B (0..1 scale, uint8 255) gives luminance term C1/(1+C1) = 0.0001/1.0001
  (about 0.0001) and structure term 1, so tile SSIM is about 0.0001.
- mean_l1 is on the 0..1 scale: |a-b|/255 averaged over the compared values (max_l1 = 3/255 fits that).
"""
import time

import numpy as np
import pytest

from image_gates import (
    GateError,
    to_float01,
    dilate,
    block_ssim,
    background_lock,
    cast_parity,
    limb_parity,
    posture_state,
    posture_matches,
    feasible_motion,
)


def flat(value, h=16, w=16):
    return np.full((h, w, 3), value, dtype=np.uint8)


def gradient(h=16, w=16):
    return (np.arange(h * w * 3) % 256).astype(np.uint8).reshape(h, w, 3)


def no_mask(h=16, w=16):
    return np.zeros((h, w), dtype=bool)


# ---------- to_float01 ----------

def test_to_float01_uint8_scales_to_unit_range():
    out = to_float01(np.array([[[0, 255, 51]]], dtype=np.uint8))
    assert np.issubdtype(out.dtype, np.floating)
    assert out[0, 0, 0] == pytest.approx(0.0)
    assert out[0, 0, 1] == pytest.approx(1.0)
    assert out[0, 0, 2] == pytest.approx(0.2)


def test_float_image_refused():
    # E8: floats are refused, so a float 0..1 image can never be divided by 255 a second time.
    with pytest.raises(GateError, match="convert to uint8 0..255 first"):
        to_float01(np.full((2, 2, 3), 0.5))
    with pytest.raises(GateError, match="convert to uint8 0..255 first"):
        to_float01(np.full((2, 2, 3), 127.5))


def test_to_float01_wrong_shape_raises():
    with pytest.raises(GateError):
        to_float01(np.zeros((4, 4)))


def test_to_float01_object_dtype_raises():
    with pytest.raises(GateError):
        to_float01(np.empty((2, 2, 3), dtype=object))


# ---------- dilate ----------

def make_small_mask():
    m = np.zeros((9, 9), dtype=bool)
    m[4, 4] = True
    return m


def test_dilate_zero_returns_equal_copy():
    m = make_small_mask()
    out = dilate(m, 0)
    assert np.array_equal(out, m)
    out[0, 0] = True
    assert not m[0, 0]  # the input must not change


def test_dilate_three_gives_7x7_square():
    # centre (4,4), px 3 -> rows 1..7 and cols 1..7 -> 7*7 = 49 True pixels
    out = dilate(make_small_mask(), 3)
    assert out.sum() == 49
    assert out[1:8, 1:8].all()
    assert not out[0, :].any()
    assert not out[8, :].any()
    assert not out[:, 0].any()
    assert not out[:, 8].any()


# ---------- block_ssim ----------

def test_block_ssim_identical_is_one():
    x = gradient()
    valid = np.ones((16, 16), dtype=bool)
    assert block_ssim(x, x.copy(), valid) == pytest.approx(1.0)


def test_block_ssim_all_invalid_raises_no_comparable_area():
    x = gradient()
    valid = np.zeros((16, 16), dtype=bool)
    with pytest.raises(GateError, match="no comparable area"):
        block_ssim(x, x.copy(), valid)


def test_block_ssim_tile_with_one_invalid_pixel_is_skipped():
    # b differs in the whole top-left tile, but one pixel of that tile is invalid, so that tile is not
    # entirely inside valid and is skipped. The other three tiles are identical -> SSIM 1.0.
    a = flat(0)
    b = a.copy()
    b[0:8, 0:8, :] = 255
    valid = np.ones((16, 16), dtype=bool)
    valid[0, 0] = False
    assert block_ssim(a, b, valid) == pytest.approx(1.0)


# ---------- background_lock ----------

def test_identical_images_pass():
    img = gradient()
    res = background_lock(img, img.copy(), no_mask(), no_mask(), dilate_px=0)
    assert res["ssim"] == pytest.approx(1.0)
    assert res["mean_l1"] == pytest.approx(0.0)
    assert res["area_fraction"] == pytest.approx(1.0)
    assert res["pass"] is True


def test_changed_background_fails():
    # top-left 8x8 tile changes 0 -> 255 (1.0 scale) outside any mask.
    # tile SSIM about 0.0001 for that tile, 1.0 for the other three -> mean about (3 + 0.0001) / 4 = 0.75.
    # L1: 64 pixels x 3 channels each differ by 1.0; 192 / 768 = 0.25.
    a = flat(0)
    b = flat(0)
    b[0:8, 0:8, :] = 255
    res = background_lock(a, b, no_mask(), no_mask(), dilate_px=0)
    assert res["ssim"] == pytest.approx(0.75, abs=1e-3)
    assert res["mean_l1"] == pytest.approx(0.25, abs=1e-6)
    assert res["pass"] is False
    assert res["area_fraction"] == pytest.approx(1.0)


def test_change_inside_dilated_mask_is_ignored():
    # mask pixel (1,1) with dilate_px 1 excludes rows 0..2 and cols 0..2 (3x3 = 9 pixels).
    # The change b[0:3, 0:3] lies exactly inside that excluded square. The top-left tile is then not
    # entirely valid and is skipped; the other three tiles are identical -> SSIM 1.0, L1 0, pass.
    a = flat(0)
    b = flat(0)
    b[0:3, 0:3, :] = 255
    mask = no_mask()
    mask[1, 1] = True
    res = background_lock(a, b, mask, mask, dilate_px=1)
    assert res["ssim"] == pytest.approx(1.0)
    assert res["mean_l1"] == pytest.approx(0.0)
    assert res["pass"] is True
    assert 0.0 < res["area_fraction"] <= 1.0


def test_shape_mismatch_raises():
    a = flat(0, 16, 16)
    b = np.zeros((16, 12, 3), dtype=np.uint8)
    with pytest.raises(GateError):
        background_lock(a, b, no_mask(16, 16), no_mask(16, 12), dilate_px=0)


def test_small_area_fails():
    # 64x64 frame, only the top-left 8x8 tile is comparable: area 64/4096 = 0.015625 < 0.25 -> pass False.
    # The images are identical, so SSIM 1.0 and L1 0 do not cause the failure; the area does.
    a = gradient(64, 64)
    mask = np.ones((64, 64), dtype=bool)
    mask[0:8, 0:8] = False
    res = background_lock(a, a.copy(), mask, np.zeros((64, 64), dtype=bool), dilate_px=0)
    assert res["area_fraction"] == pytest.approx(64 / 4096)
    assert res["pass"] is False
    assert any("comparable area" in r for r in res["reasons"])


def test_all_masked_image_raises_no_comparable_area():
    a = flat(0)
    mask = np.ones((16, 16), dtype=bool)
    with pytest.raises(GateError, match="no comparable area"):
        background_lock(a, a.copy(), mask, mask, dilate_px=0)


def test_float_inputs_refused_by_background_lock():
    # E8 follow-up: the old test compared uint8 and float results. Floats are refused now, so it checks that.
    a_f = gradient().astype(np.float64)
    b_f = a_f.copy()
    b_f[0:8, 0:8, :] = 200.0
    with pytest.raises(GateError, match="convert to uint8 0..255 first"):
        background_lock(a_f, b_f, no_mask(), no_mask(), dilate_px=0)


def test_inputs_not_mutated():
    a = gradient()
    b = gradient()
    b[0:8, 0:8, :] = 0
    mask = no_mask()
    mask[5, 5] = True
    a0, b0, m0 = a.copy(), b.copy(), mask.copy()
    background_lock(a, b, mask, mask, dilate_px=2)
    assert np.array_equal(a, a0)
    assert np.array_equal(b, b0)
    assert np.array_equal(mask, m0)
    x = a
    x0 = x.copy()
    block_ssim(x, x, np.ones((16, 16), dtype=bool))
    assert np.array_equal(x, x0)


# ---------- cast_parity ----------

def test_cast_parity_equal_counts_no_problem():
    assert cast_parity(3, 3, 3) == []


def test_cast_parity_differ_only():
    # 4 vs 3, both at least the required 3 -> only the differ message
    assert cast_parity(4, 3, 3) == ["cast count differs between A and B (4 vs 3)"]


def test_cast_parity_differ_and_fewer_both_listed_in_order():
    # 2 vs 3: differ message first, then A is below 3. B is 3, not below.
    assert cast_parity(2, 3, 3) == [
        "cast count differs between A and B (2 vs 3)",
        "A shows fewer people than the script requires (2 < 3)",
    ]


def test_cast_parity_fewer_than_required_both_sides():
    # equal counts 2 and 2 with required 3: no differ message, A and B both below
    assert cast_parity(2, 2, 3) == [
        "A shows fewer people than the script requires (2 < 3)",
        "B shows fewer people than the script requires (2 < 3)",
    ]


def test_cast_parity_entry_exit_allowed_skips_differ():
    # 2 vs 3 allowed to differ: no differ message; A below 3 gives the A message; B is 3, fine
    assert cast_parity(2, 3, 3, entry_exit_allowed=True) == [
        "A shows fewer people than the script requires (2 < 3)",
    ]


def test_cast_parity_entry_exit_allowed_equal_ok():
    assert cast_parity(3, 3, 3, entry_exit_allowed=True) == []


def test_cast_parity_negative_counts_raise():
    with pytest.raises(GateError):
        cast_parity(-1, 3, 3)
    with pytest.raises(GateError):
        cast_parity(3, -1, 3)


# ---------- limb_parity ----------

def test_limb_parity_4_vs_2():
    assert limb_parity(4, 2) == ["arm count differs between A and B (4 vs 2)"]


def test_limb_parity_equal_is_empty():
    assert limb_parity(2, 2) == []


# ---------- posture_state ----------

def test_posture_state_thresholds():
    assert posture_state(1.2) == "standing"
    assert posture_state(1.11) == "standing"
    assert posture_state(1.1) == "unknown"   # exactly 1.1 is not > 1.1
    assert posture_state(0.9) == "unknown"   # between the thresholds
    assert posture_state(0.65) == "unknown"  # exactly 0.65 is not < 0.65
    assert posture_state(0.64) == "seated"
    assert posture_state(0.0) == "seated"


# ---------- posture_matches ----------

def test_posture_matches_all_agree_no_problem():
    assert posture_matches("standing", "standing", "standing", "standing") == []


def test_posture_matches_no_requirement_no_problem():
    assert posture_matches("standing", "seated", None, None) == []


def test_posture_matches_mismatch_messages_in_order():
    # A standing vs script start seated; B seated vs script end standing: both mismatch, A first
    assert posture_matches("standing", "seated", "seated", "standing") == [
        "A is standing but the script says seated",
        "B is seated but the script says standing",
    ]


def test_posture_matches_unknown_is_a_problem_when_script_known():
    assert posture_matches("unknown", "seated", "seated", "seated") == ["A posture unclear"]


def test_posture_matches_unknown_never_matches_known_script():
    assert posture_matches("unknown", "unknown", "standing", "seated") == [
        "A posture unclear",
        "B posture unclear",
    ]


def test_posture_matches_unknown_with_no_requirement_is_fine():
    assert posture_matches("unknown", "unknown", None, None) == []


# ---------- feasible_motion ----------

def test_feasible_motion_boundary_inclusive():
    # 10 / 2 = 5.0 exactly equals max 5.0 -> feasible
    assert feasible_motion(10.0, 2.0, 5.0) is True
    # 10.1 / 2 = 5.05 > 5.0 -> not feasible
    assert feasible_motion(10.1, 2.0, 5.0) is False


def test_feasible_motion_zero_displacement_ok():
    assert feasible_motion(0.0, 1.0, 0.0) is True


def test_feasible_motion_bad_inputs_raise():
    with pytest.raises(GateError):
        feasible_motion(1.0, 0.0, 5.0)
    with pytest.raises(GateError):
        feasible_motion(1.0, -1.0, 5.0)
    with pytest.raises(GateError):
        feasible_motion(-1.0, 1.0, 5.0)


# ---------- review findings, fifth run (spec J11 point 3) ----------

def test_uint8_mask_with_zero_dilate_raises_gate_error():
    # Masks must be bool. A uint8 mask with dilate_px=0 used to fail with IndexError at diff[valid].
    # Hand check: no arithmetic; the mask dtype is uint8, so GateError("masks must be bool") is expected.
    a = flat(0)
    mask = np.zeros((16, 16), dtype=np.uint8)
    with pytest.raises(GateError, match="masks must be bool"):
        background_lock(a, a.copy(), mask, mask, dilate_px=0)


def test_huge_dilate_fast():
    # H7-J11: px is clamped to max(H, W) = 16. One True pixel at (8, 8) reaches every pixel in 8 steps.
    m = np.zeros((16, 16), dtype=bool)
    m[8, 8] = True
    start = time.perf_counter()
    out = dilate(m, 10 ** 6)
    elapsed = time.perf_counter() - start
    assert out.all()
    assert elapsed < 1.0


def test_bool_count_refused():
    # Hand check: True is an int in Python, but a bool count is refused by GateError.
    with pytest.raises(GateError):
        cast_parity(True, 3, 3)
    with pytest.raises(GateError):
        cast_parity(3, True, 3)
    with pytest.raises(GateError):
        cast_parity(3, 3, True)
    with pytest.raises(GateError):
        cast_parity(3.0, 3, 3)
    with pytest.raises(GateError):
        limb_parity(True, 2)
    with pytest.raises(GateError):
        limb_parity(2, 2.0)


def test_dilate_non_integer_px_raises_gate_error():
    # Hand check: px = 1.5 is not an integer, so GateError (not TypeError) is expected.
    with pytest.raises(GateError):
        dilate(make_small_mask(), 1.5)


def test_feasible_motion_nan_seconds_raises_gate_error():
    # Hand check: NaN seconds is not a finite positive number, so GateError is expected.
    with pytest.raises(GateError):
        feasible_motion(1.0, float("nan"), 5.0)


# ---------- review findings, round 10 (observer 9: codex r0/r1 claims checked against the module) ----------

def test_feasible_motion_nan_displacement_raises_gate_error():
    # observer 9 (codex r0): NaN displacement must not be reported as feasible; NaN is not finite -> GateError.
    with pytest.raises(GateError):
        feasible_motion(float("nan"), 1.0, 5.0)


def test_feasible_motion_infinite_inputs_raise_gate_error():
    # observer 9 (codex r0): infinite displacement or infinite max_per_sec -> GateError.
    with pytest.raises(GateError):
        feasible_motion(float("inf"), 1.0, 5.0)
    with pytest.raises(GateError):
        feasible_motion(1.0, 1.0, float("inf"))


def test_dilate_negative_px_raises_gate_error():
    # observer 9 (spec fifth-run finding 2): px must be >= 0. Hand check: px = -1 -> GateError.
    with pytest.raises(GateError):
        dilate(make_small_mask(), -1)


def test_to_float01_integer_dtypes_other_than_uint8_raise():
    # observer 9 (codex r1): only uint8 or float images are legal. Hand check: int16 and int32 -> GateError.
    with pytest.raises(GateError):
        to_float01(np.zeros((4, 4, 3), dtype=np.int16))
    with pytest.raises(GateError):
        to_float01(np.zeros((4, 4, 3), dtype=np.int32))
