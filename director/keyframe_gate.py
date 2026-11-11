"""Keyframe gate for card X-10.

Validates ``keyframe_review.json`` (rule 25 / problem 22: ``full_size`` must be
true) and gates the A/B keyframes into a ``<flow_root>/keyframe_gates/<SHOT>.json`` record (see keyframe_dir).

Depends on: ``director.plate_composite`` (diff_mask, plan, composite),
``director.image_gates`` (background_lock).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np

try:  # director is a package
    from director.plate_composite import composite, diff_mask, plan  # type: ignore
    from director.image_gates import GateError, background_lock  # type: ignore
except ImportError:  # pragma: no cover - fallback for flat layouts
    from plate_composite import composite, diff_mask, plan  # type: ignore
    from image_gates import GateError, background_lock  # type: ignore

MIN_AREA = 0.25
MAX_SPEED_H = 256.0
FEATHER_PX = 4
VALID_POSTURES = {"standing", "seated", "unknown"}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


KEYFRAME_DIR_NAME = "keyframe_gates"


def keyframe_dir(flow_root) -> Path:
    """The one folder for keyframe gate records: the gate writes here and approval_sheet reads here."""
    return Path(flow_root) / KEYFRAME_DIR_NAME


def _sha256_array(arr) -> str:
    a = np.ascontiguousarray(np.asarray(arr))
    return hashlib.sha256(a.tobytes()).hexdigest()


def _sha256_json(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _is_count(value) -> bool:
    return isinstance(value, (int, np.integer)) and not isinstance(value, bool) and value >= 0


def _centroid(mask):
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return 0.0, 0.0
    return float(ys.mean()), float(xs.mean())


# ---------------------------------------------------------------------------
# Review validation (rule 25 / problem 22)
# ---------------------------------------------------------------------------

def validate_review(review: Any, sheet: Any = None) -> bool:
    """Return True when ``review`` matches the keyframe_review.json shape.

    Rule 25 / problem 22: ``full_size`` must be true.
    """
    try:
        if not isinstance(review, dict):
            return False
        if review.get("full_size") is not True:
            return False
        if "shot_id" not in review or not review.get("reviewer"):
            return False
        for side in ("A", "B"):
            side_review = review.get(side)
            if not isinstance(side_review, dict):
                return False
            for key in ("cast_count", "chars", "extra_figures", "marks_or_letters"):
                if key not in side_review:
                    return False
            if not isinstance(side_review.get("chars"), dict):
                return False
            if not _is_count(side_review.get("cast_count")):
                return False
            for ch in side_review["chars"].values():
                if not isinstance(ch, dict):
                    return False
                if "arms" not in ch or "posture" not in ch:
                    return False
                if ch.get("posture") not in VALID_POSTURES:
                    return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Parity / motion helpers
# ---------------------------------------------------------------------------

def cast_parity(cast_a, cast_b, required_cast_count, entry_exit_allowed) -> bool:
    """Cast counts must agree; must match the requirement unless entry/exit allowed."""
    try:
        if not (_is_count(cast_a) and _is_count(cast_b)):
            return False
        if required_cast_count is not None and not _is_count(required_cast_count):
            return False
        if cast_a != cast_b:
            return False
        if required_cast_count is not None and not entry_exit_allowed:
            return cast_a == required_cast_count
        return True
    except Exception:
        return False


def limb_parity(chars_a, chars_b, expect_arms) -> bool:
    """Per-character arm parity between A and B and against the expectation."""
    ok = True
    expect_arms = expect_arms or {}
    for cid in set(chars_a) | set(chars_b):
        a = chars_a.get(cid, {}) or {}
        b = chars_b.get(cid, {}) or {}
        if a.get("arms") != b.get("arms"):
            ok = False
        if cid in expect_arms:
            if a.get("arms") != expect_arms[cid] or b.get("arms") != expect_arms[cid]:
                ok = False
    return bool(ok)


def posture_matches(chars_a, chars_b, expect_posture) -> bool:
    """Per-character posture check.

    expect_posture is blocking.image_expect's shape: {cid: (start, end)}. Frame A must show ``start`` and frame B
    must show ``end``; None means not constrained. A character with no expectation must simply match between A and B.
    A bare string is refused (the old one-string-per-character shape).
    """
    ok = True
    expect_posture = expect_posture or {}
    for cid in set(chars_a) | set(chars_b):
        a = chars_a.get(cid, {}) or {}
        b = chars_b.get(cid, {}) or {}
        pa, pb = a.get("posture"), b.get("posture")
        if cid in expect_posture:
            pair = expect_posture[cid]
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError("expect posture for %s must be (start, end), got %r" % (cid, pair))
            start, end = pair
            if (start is not None and pa != start) or (end is not None and pb != end):
                ok = False
        elif pa != pb:
            ok = False
    return bool(ok)


def feasible_motion(displacement, seconds, max_speed=MAX_SPEED_H) -> bool:
    """True when displacement/seconds does not exceed max_speed."""
    try:
        if seconds is None or seconds <= 0:
            return bool(displacement == 0)
        return abs(float(displacement)) <= float(max_speed) * float(seconds)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

def gate(plate, img_a, img_b, sheet, review, lock) -> bool:
    """Run the keyframe gate and write ``keyframe_gate/<SHOT>.json``.

    Returns True when every check passes.
    """
    checks: Dict[str, Any] = {}

    plate = np.asarray(plate)
    img_a = np.asarray(img_a)
    img_b = np.asarray(img_b)

    # Rule 25 / problem 22: review shape + full_size must be true.
    review_ok = validate_review(review, sheet)
    checks["review_valid"] = bool(review_ok)
    if not review_ok:
        checks["pass"] = False
        _write_record(sheet, review, lock, plate, img_a, img_b, img_b, checks)
        return False

    # Masks: the empty plate makes character masks free.
    ma = np.asarray(diff_mask(plate, img_a))
    mb = np.asarray(diff_mask(plate, img_b))

    # Background lock + area fraction (stable area must be >= MIN_AREA).
    try:
        bg_result = background_lock(img_a, img_b, ma, mb)
    except GateError as exc:  # no comparable area: fail the gate, keep the record
        bg_result = {"pass": False, "area_fraction": 0.0, "reasons": [str(exc)]}
    bg_ok = bool(bg_result["pass"])
    checks["background_lock"] = bg_ok
    checks["background_reasons"] = list(bg_result["reasons"])
    area_fraction = float(bg_result["area_fraction"])
    checks["area_fraction"] = area_fraction
    checks["area_ok"] = bool(area_fraction >= MIN_AREA)

    # Plan -> composite or keep B.
    plan_result = plan(img_a, img_b, ma, mb)
    use = _get(plan_result, "use", "keep")
    checks["plan_use"] = str(use)
    if use == "composite":
        b_final = np.asarray(composite(img_a, img_b, mb, feather_px=FEATHER_PX))
    else:
        b_final = img_b
    checks["b_final_is_composite"] = bool(use == "composite")
    checks["hole_fraction"] = float(_get(plan_result, "hole_fraction", 0.0))

    # Cast parity.
    expect = _get(sheet, "expect", {}) or {}
    required_cast_count = _get(expect, "required_cast_count", None)
    entry_exit_allowed = _get(expect, "entry_exit_allowed", False)
    cast_a = _get(review["A"], "cast_count", None)
    cast_b = _get(review["B"], "cast_count", None)
    cp = cast_parity(cast_a, cast_b, required_cast_count, entry_exit_allowed)
    checks["cast_parity"] = bool(cp)

    # Limb + posture parity per character.
    chars_a = _get(review["A"], "chars", {}) or {}
    chars_b = _get(review["B"], "chars", {}) or {}
    expect_arms = _get(expect, "arms", {}) or {}
    expect_posture = _get(expect, "posture", {}) or {}
    lp = limb_parity(chars_a, chars_b, expect_arms)
    pm = posture_matches(chars_a, chars_b, expect_posture)
    checks["limb_parity"] = bool(lp)
    checks["posture_matches"] = bool(pm)

    # Feasible motion (seconds from the lock).
    ay, ax = _centroid(ma)
    by, bx = _centroid(mb)
    displacement = float(np.hypot(by - ay, bx - ax))
    seconds = _get(lock, "seconds", 1.0)
    fm = feasible_motion(displacement, seconds, MAX_SPEED_H)
    checks["feasible_motion"] = bool(fm)
    checks["displacement"] = float(displacement)
    checks["seconds"] = seconds

    # Extra figures / marks or letters must be absent.
    ef_ok = True
    for side in ("A", "B"):
        side_review = _get(review, side, {}) or {}
        if side_review.get("extra_figures"):
            ef_ok = False
        if side_review.get("marks_or_letters"):
            ef_ok = False
    checks["no_extra_figures_or_marks"] = bool(ef_ok)

    pass_all = bool(
        review_ok
        and bg_ok
        and checks["area_ok"]
        and checks["cast_parity"]
        and checks["limb_parity"]
        and checks["posture_matches"]
        and checks["feasible_motion"]
        and checks["no_extra_figures_or_marks"]
    )
    checks["pass"] = pass_all

    _write_record(sheet, review, lock, plate, img_a, img_b, b_final, checks)
    return pass_all


def _write_record(sheet, review, lock, plate, img_a, img_b, b_final, checks) -> None:
    shot_id = _get(review, "shot_id", "unknown")
    flow_root = _get(lock, "flow_root", _get(sheet, "flow_root", Path.cwd()))
    flow_root = Path(flow_root)
    out_dir = keyframe_dir(flow_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "shot_id": str(shot_id),
        "sha256": {
            "plate": _sha256_array(plate),
            "A": _sha256_array(img_a),
            "B": _sha256_array(img_b),
            "B_final": _sha256_array(b_final),
            "sheet": _sha256_json(sheet),
            "review": _sha256_json(review),
            "lock_input": _get(lock, "input_sha256", ""),
        },
        "checks": checks,
        "pass": bool(checks.get("pass", False)),
    }
    out_path = out_dir / (Path(str(shot_id)).name + ".json")
    out_path.write_text(json.dumps(record, indent=2, default=str))
