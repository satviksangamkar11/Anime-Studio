"""Tests for plate_composite."""

import os
import numpy as np
import pytest

import plate_composite


def _make_img(h, w, color):
    return np.full((h, w, 3), color, dtype=np.uint8)


def test_composite_full_true_equals_b():
    a = _make_img(10, 10, (10, 20, 30))
    b = _make_img(10, 10, (200, 210, 220))
    mask = np.ones((10, 10), dtype=bool)
    out = plate_composite.composite(a, b, mask)
    assert np.array_equal(out, b)
    assert np.array_equal(a, _make_img(10, 10, (10, 20, 30)))


def test_composite_full_false_equals_a():
    a = _make_img(10, 10, (10, 20, 30))
    b = _make_img(10, 10, (200, 210, 220))
    mask = np.zeros((10, 10), dtype=bool)
    out = plate_composite.composite(a, b, mask)
    assert np.array_equal(out, a)


def test_composite_feather_edge_strictly_between():
    a = _make_img(5, 5, (0, 0, 0))
    b = _make_img(5, 5, (255, 255, 255))
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True
    out = plate_composite.composite(a, b, mask, feather_px=1)
    assert out.dtype == np.uint8
    center = out[2, 2].astype(np.int16)
    assert np.all(center > 0)
    assert np.all(center < 255)


# observer 10 (codex LOW): diff_mask must return a bool mask, not a numeric one
def test_diff_mask_returns_bool():
    a = _make_img(20, 20, (100, 100, 100))
    b = a.copy()
    b[5:10, 5:10] = (200, 200, 200)
    mask = plate_composite.diff_mask(a, b, threshold=24, dilate_px=0, min_area=1)
    assert mask.dtype == bool
    assert mask.shape == (20, 20)


def test_diff_mask_finds_square_changed():
    a = _make_img(20, 20, (100, 100, 100))
    b = a.copy()
    b[5:10, 5:10] = (200, 200, 200)
    mask = plate_composite.diff_mask(a, b, threshold=24, dilate_px=0, min_area=1)
    assert mask[5:10, 5:10].all()


def test_diff_mask_ignores_tiny_speckle():
    a = _make_img(20, 20, (100, 100, 100))
    b = a.copy()
    b[3, 3] = (200, 200, 200)
    mask = plate_composite.diff_mask(a, b, threshold=24, dilate_px=0, min_area=50)
    assert not mask.any()


def test_diff_mask_ignores_below_threshold():
    a = _make_img(20, 20, (100, 100, 100))
    b = a.copy()
    b[5:10, 5:10] = (110, 110, 110)
    mask = plate_composite.diff_mask(a, b, threshold=24, dilate_px=0, min_area=1)
    assert not mask.any()


def test_diff_mask_shape_mismatch():
    a = _make_img(10, 10, (0, 0, 0))
    b = _make_img(10, 11, (0, 0, 0))
    try:
        plate_composite.diff_mask(a, b)
    except plate_composite.CompositeError:
        return
    raise AssertionError("expected CompositeError")


def test_composite_shape_mismatch():
    a = _make_img(10, 10, (0, 0, 0))
    b = _make_img(10, 11, (0, 0, 0))
    mask = np.zeros((10, 10), dtype=bool)
    try:
        plate_composite.composite(a, b, mask)
    except plate_composite.CompositeError:
        return
    raise AssertionError("expected CompositeError")


def test_hole_fraction_moved_away_positive():
    mask_a = np.zeros((10, 10), dtype=bool)
    mask_a[2:5, 2:5] = True
    mask_b = np.zeros((10, 10), dtype=bool)
    mask_b[7:9, 7:9] = True
    hf = plate_composite.hole_fraction(mask_a, mask_b)
    assert hf > 0.0


def test_hole_fraction_grew_is_zero():
    mask_a = np.zeros((10, 10), dtype=bool)
    mask_a[2:5, 2:5] = True
    mask_b = np.zeros((10, 10), dtype=bool)
    mask_b[2:6, 2:6] = True
    hf = plate_composite.hole_fraction(mask_a, mask_b)
    assert hf == 0.0


def test_composite_is_safe_boundary():
    total = 100
    mask_a = np.zeros((10, 10), dtype=bool)
    mask_a.flat[:total] = True
    mask_b = np.zeros((10, 10), dtype=bool)
    # exactly 2 holes out of 100 -> fraction 0.02 -> safe
    mask_b.flat[:98] = True
    res = plate_composite.composite_is_safe(mask_a, mask_b, max_hole_fraction=0.02)
    assert res["safe"] is True
    assert res["hole_fraction"] == 0.02

    mask_b2 = np.zeros((10, 10), dtype=bool)
    mask_b2.flat[:97] = True
    res2 = plate_composite.composite_is_safe(mask_a, mask_b2, max_hole_fraction=0.02)
    assert res2["safe"] is False
    assert res2["reason"] == "character uncovers background that A does not show; use B unchanged or re-edit"


def test_plan_keep_b_when_hole_large():
    a = _make_img(10, 10, (0, 0, 0))
    b = _make_img(10, 10, (1, 1, 1))
    mask_a = np.ones((10, 10), dtype=bool)
    mask_b = np.zeros((10, 10), dtype=bool)
    res = plate_composite.plan(a, b, mask_a, mask_b)
    assert res["use"] == "keep_b"
    assert res["hole_fraction"] == 1.0


# observer 10 (codex LOW): plan must return exactly the documented keys and mask_area of char mask B
def test_plan_result_shape_and_mask_area():
    a = _make_img(10, 10, (0, 0, 0))
    b = _make_img(10, 10, (1, 1, 1))
    mask_a = np.zeros((10, 10), dtype=bool)
    mask_b = np.zeros((10, 10), dtype=bool)
    mask_b[1:4, 1:5] = True
    res = plate_composite.plan(a, b, mask_a, mask_b)
    assert set(res.keys()) == {"use", "hole_fraction", "mask_area"}
    assert res["mask_area"] == 12.0
    assert res["use"] == "composite"


def test_plan_composite_when_safe():
    a = _make_img(10, 10, (0, 0, 0))
    b = _make_img(10, 10, (1, 1, 1))
    mask_a = np.zeros((10, 10), dtype=bool)
    mask_b = np.zeros((10, 10), dtype=bool)
    res = plate_composite.plan(a, b, mask_a, mask_b)
    assert res["use"] == "composite"
    assert res["hole_fraction"] == 0.0


def test_save_load_round_trip_and_no_temp_left(tmp_path):
    img = _make_img(4, 4, (1, 2, 3))
    path = os.path.join(tmp_path, "out.png")
    before = set(os.listdir(tmp_path))
    plate_composite.save_rgb(path, img)
    after = set(os.listdir(tmp_path))
    assert after - before == {os.path.basename(path)}
    loaded = plate_composite.load_rgb(path)
    assert np.array_equal(loaded, img)


def test_save_rgb_refuses_bad_array(tmp_path):
    path = os.path.join(tmp_path, "bad.png")
    # observer 10 (ultra MED): the wrong-dtype check was unreachable after the early return; both checks now run
    try:
        plate_composite.save_rgb(path, np.zeros((4, 4), dtype=np.uint8))
    except plate_composite.CompositeError:
        pass
    else:
        raise AssertionError("expected CompositeError for wrong shape")

    try:
        plate_composite.save_rgb(path, np.zeros((4, 4, 3), dtype=np.float32))
    except plate_composite.CompositeError:
        pass
    else:
        raise AssertionError("expected CompositeError for wrong dtype")
    assert not os.path.exists(path)


def test_load_rgb_missing_file(tmp_path):
    path = os.path.join(tmp_path, "missing.png")
    try:
        plate_composite.load_rgb(path)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_inputs_not_mutated():
    a = _make_img(6, 6, (50, 60, 70))
    b = _make_img(6, 6, (150, 160, 170))
    a_copy = a.copy()
    b_copy = b.copy()
    mask = np.zeros((6, 6), dtype=bool)
    mask[2:4, 2:4] = True
    plate_composite.composite(a, b, mask, feather_px=1)
    assert np.array_equal(a, a_copy)
    assert np.array_equal(b, b_copy)


def test_save_rgb_refuses_wrong_shape_alone(tmp_path):
    # observer 7 (TEST_FINDINGS ultra/codex): the wrong-shape case on its own, no early return shadowing it
    path = os.path.join(tmp_path, "bad_shape.png")
    try:
        plate_composite.save_rgb(path, np.zeros((4, 4), dtype=np.uint8))
    except plate_composite.CompositeError:
        assert not os.path.exists(path)
        return
    raise AssertionError("expected CompositeError for wrong shape")


def test_save_rgb_refuses_float32_alone(tmp_path):
    # observer 7 (TEST_FINDINGS codex): the float32 case on its own, with the correct (H, W, 3) shape
    path = os.path.join(tmp_path, "bad_dtype.png")
    try:
        plate_composite.save_rgb(path, np.zeros((4, 4, 3), dtype=np.float32))
    except plate_composite.CompositeError:
        assert not os.path.exists(path)
        return
    raise AssertionError("expected CompositeError for float32")


def test_diff_mask_joins_u_shaped_component():
    # observer 7 (TEST_FINDINGS codex): both arms are labelled apart in the first scan and joined by the
    # bottom bar. One component of 36 px >= min_area 30 must survive whole (16 px per arm alone would not).
    a = _make_img(12, 12, (100, 100, 100))
    b = a.copy()
    b[2:10, 2:4] = (200, 200, 200)
    b[2:10, 6:8] = (200, 200, 200)
    b[8:10, 4:6] = (200, 200, 200)
    expected = np.zeros((12, 12), dtype=bool)
    expected[2:10, 2:4] = True
    expected[2:10, 6:8] = True
    expected[8:10, 4:6] = True
    mask = plate_composite.diff_mask(a, b, threshold=24, dilate_px=0, min_area=30)
    assert np.array_equal(mask, expected)
    assert mask.sum() == 36


# ---------- review findings, round 10 (observer 9: codex r0/r1 claims checked against the module) ----------

def test_composite_refuses_float_images():
    # observer 9 (codex r0): composite must refuse non-uint8 images with CompositeError (no silent truncation).
    a = np.zeros((4, 4, 3), dtype=np.float32)
    mask = np.zeros((4, 4), dtype=bool)
    with pytest.raises(plate_composite.CompositeError):
        plate_composite.composite(a, a.copy(), mask)


def test_composite_and_diff_mask_refuse_malformed_shape():
    # observer 9 (codex r1): 2-D images (no channel axis) must raise CompositeError, not a NumPy error.
    a = np.zeros((4, 4), dtype=np.uint8)
    mask = np.zeros((4, 4), dtype=bool)
    with pytest.raises(plate_composite.CompositeError):
        plate_composite.composite(a, a.copy(), mask)
    with pytest.raises(plate_composite.CompositeError):
        plate_composite.diff_mask(a, a.copy())


# ---------- review findings, third run, point 4 (2026-11-10, Haiku test pass) ----------
# Both the feather test and the .jpg test pass now: _box_blur pads with edge values,
# and save_rgb refuses non-.png names.

def test_composite_feather_full_true_and_full_false_on_8x8():
    a = _make_img(8, 8, (10, 20, 30))
    b = _make_img(8, 8, (200, 210, 220))
    # Arithmetic: full-True mask -> feathered weight is 1.0 everywhere, so out = A*0 + B*1 = B.
    # Zero padding breaks this at the border: the corner 5x5 window (px=2) holds only 3x3 = 9
    # in-bounds cells, so weight = 9/25 = 0.36 and R = 10*0.64 + 200*0.36 = 78.4 -> 78, not 200.
    out_true = plate_composite.composite(a, b, np.ones((8, 8), dtype=bool), feather_px=2)
    assert np.array_equal(out_true, b)
    # Arithmetic: full-False mask -> weight is 0.0 everywhere, so out = A*1 + B*0 = A exactly.
    out_false = plate_composite.composite(a, b, np.zeros((8, 8), dtype=bool), feather_px=2)
    assert np.array_equal(out_false, a)


def test_diff_mask_threshold_is_strict_at_24_and_25():
    a = _make_img(20, 20, (100, 100, 100))
    b = a.copy()
    # Arithmetic: |100 - 124| = 24; 24 > 24 is False, so this block is NOT in the mask.
    b[2:5, 2:5] = (124, 124, 124)
    # Arithmetic: |100 - 125| = 25; 25 > 24 is True, so this 3x3 block (9 px) IS in the mask.
    b[10:13, 10:13] = (125, 125, 125)
    mask = plate_composite.diff_mask(a, b, threshold=24, dilate_px=0, min_area=1)
    assert not mask[2:5, 2:5].any()
    assert mask[10:13, 10:13].all()
    assert mask.sum() == 9


def test_diff_mask_min_area_keeps_4px_blob_at_4_and_drops_at_5():
    a = _make_img(20, 20, (100, 100, 100))
    b = a.copy()
    # Arithmetic: 2x2 block = 4 px, one 4-connected component; |100 - 200| = 100 > 24.
    b[5:7, 5:7] = (200, 200, 200)
    # min_area 4: component size 4 >= 4 is True, kept.
    kept = plate_composite.diff_mask(a, b, threshold=24, dilate_px=0, min_area=4)
    assert kept.sum() == 4
    assert kept[5:7, 5:7].all()
    # min_area 5: component size 4 >= 5 is False, removed.
    dropped = plate_composite.diff_mask(a, b, threshold=24, dilate_px=0, min_area=5)
    assert not dropped.any()


def test_save_rgb_refuses_jpg_name(tmp_path):
    # save_rgb writes PNG only: a .jpg name must raise CompositeError and leave no file.
    path = os.path.join(tmp_path, "bad.jpg")
    img = _make_img(4, 4, (1, 2, 3))
    with pytest.raises(plate_composite.CompositeError):
        plate_composite.save_rgb(path, img)
    assert not os.path.exists(path)


def test_composite_half_mask_feather_edge_row():
    # Half-mask edge, feather_px=1, 6x6. mask row = [1,1,1,0,0,0]; the box blur pads with EDGE values
    # (np.pad mode="edge"), and all rows are identical so only the column average matters.
    # Each cell = (sum of mask over x-1..x+1, edge-clamped) / 3, then R = 0*(1-m) + 200*m:
    #   x=0: cols -1,0,1 -> 1,1,1 -> m=1.0      -> R=200
    #   x=1: cols 0,1,2  -> 1,1,1 -> m=1.0      -> R=200
    #   x=2: cols 1,2,3  -> 1,1,0 -> m=2/3      -> R=133.33 -> 133 (uint8 truncation)
    #   x=3: cols 2,3,4  -> 1,0,0 -> m=1/3      -> R=66.67  -> 66
    #   x=4: cols 3,4,5  -> 0,0,0 -> m=0.0      -> R=0
    #   x=5: cols 4,5,6  -> 0,0,0 (6 clamps to 5) -> R=0
    a = _make_img(6, 6, (0, 0, 0))
    b = _make_img(6, 6, (200, 200, 200))
    mask = np.zeros((6, 6), dtype=bool)
    mask[:, :3] = True
    result = plate_composite.composite(a, b, mask, feather_px=1)
    row = result[0, :, 0]
    assert row[0] == 200
    assert row[5] == 0
    assert 0 < row[2] < 200
    assert 0 < row[3] < 200


def _dilate_reference(mask, px):
    # the old per-pixel loop, copied here as the reference for _dilate_square
    h, w = mask.shape
    padded = np.zeros((h + 2 * px, w + 2 * px), dtype=bool)
    padded[px:h + px, px:w + px] = mask
    out = np.zeros_like(mask, dtype=bool)
    for y in range(h):
        for x in range(w):
            if padded[y:y + 2 * px + 1, x:x + 2 * px + 1].any():
                out[y, x] = True
    return out


def _box_blur_reference(mask, px):
    # the old per-pixel loop, copied here as the reference for _box_blur
    h, w = mask.shape
    padded = np.pad(mask, px, mode="edge")
    out = np.zeros_like(mask, dtype=np.float64)
    area = (2 * px + 1) ** 2
    for y in range(h):
        for x in range(w):
            out[y, x] = padded[y:y + 2 * px + 1, x:x + 2 * px + 1].sum() / area
    return out


def test_dilate_matches_reference():
    rng = np.random.default_rng(15)
    for i in range(20):
        mask = rng.random((32, 32)) < 0.05
        px = 1 + i % 4
        assert np.array_equal(plate_composite._dilate_square(mask, px), _dilate_reference(mask, px))


def test_blur_matches_reference():
    rng = np.random.default_rng(15)
    mask = (rng.random((32, 32)) < 0.5).astype(np.float64)
    diff = np.abs(plate_composite._box_blur(mask, 2) - _box_blur_reference(mask, 2)).max()
    assert diff < 1e-9


def test_full_frame_speed():
    import time

    rng = np.random.default_rng(15)
    mask = rng.random((768, 1344)) < 0.1
    start = time.perf_counter()
    plate_composite._dilate_square(mask, 6)
    plate_composite._box_blur(mask.astype(np.float64), 4)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0
