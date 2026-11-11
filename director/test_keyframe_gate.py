"""Tests for director/keyframe_gate.py (card X-10). Synthetic 128x128 frames, every expectation worked out by hand.

Hand arithmetic used below (masks come from plate_composite.diff_mask: threshold 24, dilate 6, 3x3 squares):
- Plate = gradient background. A has a 10x10 white square at rows 40-49, cols 20-29.
- A diff mask is that square; dilated by 6 it is a 22x22 box: rows 34-55, cols 14-35 (484 px).
- B with the square at cols 22-31 gives a box at rows 34-55, cols 16-37.
- A-box minus B-box = cols 14-15 x 22 rows = 44 px. Hole fraction 44/16384 (<= 0.02, so composite).
- B with the square at cols 40-49 gives a box at cols 34-55. A-box minus B-box = cols 14-33 = 440 px.
  Hole fraction 440/16384 = 0.02686 (> 0.02, so keep B).
- Displacement = centroid shift of the two boxes: 2.0 px and 20.0 px.
- Area fraction is the comparable background from image_gates.background_lock (outside both dilated masks).
"""

import json

import numpy as np
import pytest

import image_gates
import keyframe_gate as kg

H = 128
W = 128
SQUARE = 10
A_TOP = 40
A_LEFT = 20


def _plate():
    row = (np.arange(W) * 2).astype(np.uint8)
    g = np.tile(row, (H, 1))
    return np.stack([g, g, g], axis=2)


def _with_square(bg, left):
    img = bg.copy()
    img[A_TOP:A_TOP + SQUARE, left:left + SQUARE] = 255
    return img


def _moved(bg):
    return np.clip(bg.astype(np.int16) + 6, 0, 255).astype(np.uint8)


def _sheet(required=1, entry_exit=False):
    return {"expect": {"required_cast_count": required, "entry_exit_allowed": entry_exit,
                       "arms": {"sage": 2}, "posture": {"sage": ("standing", "standing")}}}


def _side(cast=1, arms=2, posture="standing", extra=None, marks=False):
    return {"cast_count": cast, "chars": {"sage": {"arms": arms, "posture": posture}},
            "extra_figures": extra or [], "marks_or_letters": marks}


def _review(a=None, b=None, full=True, reviewer="reviewer-1"):
    return {"shot_id": "S1", "full_size": full, "reviewer": reviewer,
            "A": a or _side(), "B": b or _side()}


def _lock(tmp_path, seconds=1.0):
    return {"flow_root": str(tmp_path), "seconds": seconds, "input_sha256": "lock-hash"}


def _record(tmp_path):
    return json.loads((kg.keyframe_dir(tmp_path) / "S1.json").read_text())


def _run(tmp_path, b_img=None, b_left=22, review=None, sheet=None, lock=None):
    plate = _plate()
    a = _with_square(plate, A_LEFT)
    b = b_img if b_img is not None else _with_square(plate, b_left)
    return kg.gate(plate, a, b, sheet or _sheet(), review or _review(), lock or _lock(tmp_path))


def test_shift_2px_composites(tmp_path):
    result = _run(tmp_path, b_left=22)
    rec = _record(tmp_path)
    checks = rec["checks"]
    assert result is True
    assert checks["plan_use"] == "composite"
    assert checks["b_final_is_composite"] is True
    assert checks["hole_fraction"] == pytest.approx(44 / 16384)
    assert checks["displacement"] == pytest.approx(2.0)
    assert checks["area_ok"] is True
    plate = _plate()
    ma = kg.diff_mask(plate, _with_square(plate, A_LEFT))
    mb = kg.diff_mask(plate, _with_square(plate, 22))
    expected = image_gates.background_lock(_with_square(plate, A_LEFT), _with_square(plate, 22), ma, mb)
    assert checks["area_fraction"] == pytest.approx(expected["area_fraction"])
    assert checks["area_fraction"] >= kg.MIN_AREA


def test_shift_20px_keeps_b(tmp_path):
    result = _run(tmp_path, b_left=40)
    rec = _record(tmp_path)
    checks = rec["checks"]
    assert result is True
    assert checks["plan_use"] == "keep_b"
    assert checks["b_final_is_composite"] is False
    assert checks["hole_fraction"] == pytest.approx(440 / 16384)
    assert checks["displacement"] == pytest.approx(20.0)
    assert rec["sha256"]["B_final"] == rec["sha256"]["B"]


def test_background_moved_fails(tmp_path):
    plate = _plate()
    a = _with_square(plate, A_LEFT)
    b = _with_square(np.roll(plate, 3, axis=1), 22)
    result = kg.gate(plate, a, b, _sheet(), _review(), _lock(tmp_path))
    assert result is False
    assert _record(tmp_path)["checks"]["background_lock"] is False


def test_missing_sage_fails(tmp_path):
    result = _run(tmp_path, sheet=_sheet(required=2), review=_review(a=_side(cast=1), b=_side(cast=1)))
    assert result is False
    assert _record(tmp_path)["checks"]["cast_parity"] is False


def test_seated_vs_standing_fails(tmp_path):
    result = _run(tmp_path, review=_review(b=_side(posture="seated")))
    assert result is False
    assert _record(tmp_path)["checks"]["posture_matches"] is False


def test_missing_approval_fails(tmp_path):
    result = _run(tmp_path, review=_review(reviewer=""))
    assert result is False
    assert _record(tmp_path)["checks"]["review_valid"] is False


def test_not_full_size_refused(tmp_path):
    result = _run(tmp_path, review=_review(full=False))
    assert result is False
    rec = _record(tmp_path)
    assert rec["checks"]["review_valid"] is False
    assert rec["pass"] is False


def test_extra_figure_fails(tmp_path):
    result = _run(tmp_path, review=_review(a=_side(extra=[{"x": 1}])))
    assert result is False
    assert _record(tmp_path)["checks"]["no_extra_figures_or_marks"] is False


def test_limb_mismatch_fails(tmp_path):
    result = _run(tmp_path, review=_review(b=_side(arms=1)))
    assert result is False
    assert _record(tmp_path)["checks"]["limb_parity"] is False


def test_motion_too_fast_fails(tmp_path):
    result = _run(tmp_path, lock=_lock(tmp_path, seconds=0.005))
    assert result is False
    assert _record(tmp_path)["checks"]["feasible_motion"] is False


def test_record_hashes_change_with_B(tmp_path):
    _run(tmp_path, b_left=22)
    first = _record(tmp_path)["sha256"]
    _run(tmp_path, b_left=24)
    second = _record(tmp_path)["sha256"]
    assert first["B"] != second["B"]
    assert first["plate"] == second["plate"]
    assert first["A"] == second["A"]
    assert first["B_final"] != second["B_final"]


@pytest.mark.parametrize("flag", ["yes", 1, "true"])
def test_full_size_must_be_boolean_true(tmp_path, flag):
    result = _run(tmp_path, review=_review(full=flag))
    assert result is False
    assert _record(tmp_path)["checks"]["review_valid"] is False


@pytest.mark.parametrize("count", ["1", True, 1.0])
def test_cast_count_must_be_int(tmp_path, count):
    result = _run(tmp_path, review=_review(a=_side(cast=count), b=_side(cast=count)))
    assert result is False
    assert _record(tmp_path)["pass"] is False


def test_string_required_count_refused(tmp_path):
    result = _run(tmp_path, sheet=_sheet(required="1"), review=_review(a=_side(cast="1"), b=_side(cast="1")))
    assert result is False
    assert _record(tmp_path)["pass"] is False


def test_area_check_uses_background_fraction(tmp_path):
    plate = _plate()
    big = plate.copy()
    big[36:86, 36:86] = 255
    result = kg.gate(plate, big, _with_square(plate, 22), _sheet(), _review(), _lock(tmp_path))
    assert result is False
    checks = _record(tmp_path)["checks"]
    assert 0 < checks["area_fraction"] < kg.MIN_AREA
    assert checks["area_ok"] is False


def test_no_comparable_area_writes_failing_record(tmp_path):
    plate = _plate()
    full = np.full_like(plate, 255)
    result = kg.gate(plate, full, _with_square(plate, 22), _sheet(), _review(), _lock(tmp_path))
    assert result is False
    rec = _record(tmp_path)
    assert rec["pass"] is False
    assert rec["checks"]["area_ok"] is False


def test_seconds_none_writes_failing_record(tmp_path):
    result = _run(tmp_path, lock=_lock(tmp_path, seconds=None))
    assert result is False
    rec = _record(tmp_path)
    assert rec["pass"] is False
    assert rec["checks"]["feasible_motion"] is False


def test_posture_expect_is_start_for_A_and_end_for_B():
    """Gap 3: image_expect gives (start, end). A must match start, B must match end, None is not constrained."""
    expect = {"X": ("standing", "seated")}
    assert kg.posture_matches({"X": {"posture": "standing"}}, {"X": {"posture": "seated"}}, expect) is True
    assert kg.posture_matches({"X": {"posture": "seated"}}, {"X": {"posture": "seated"}}, expect) is False
    assert kg.posture_matches({"X": {"posture": "standing"}}, {"X": {"posture": "standing"}}, expect) is False
    assert kg.posture_matches({"X": {"posture": "standing"}}, {"X": {"posture": "standing"}},
                              {"X": (None, None)}) is True
    assert kg.posture_matches({"X": {"posture": "unknown"}}, {"X": {"posture": "seated"}},
                              {"X": (None, "seated")}) is True


def test_posture_expect_as_one_string_is_refused():
    """Gap 3: the old one-string-per-character shape is no longer accepted."""
    with pytest.raises(ValueError):
        kg.posture_matches({"X": {"posture": "standing"}}, {"X": {"posture": "standing"}}, {"X": "standing"})


def test_keyframe_dir_is_one_constant_for_writer_and_approval():
    """Gap 4: the gate writes keyframe_dir(flow_root); approval_sheet reads from the same name and helper."""
    import approval_sheet
    assert kg.keyframe_dir("/x/flow") == kg.Path("/x/flow") / kg.KEYFRAME_DIR_NAME
    assert approval_sheet.KEYFRAME_DIR_NAME == kg.KEYFRAME_DIR_NAME
