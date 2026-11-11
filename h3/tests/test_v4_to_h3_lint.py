"""Gap (haiku-gap2): h3/v4_to_h3.convert_pack ran blocking.validate only, never director/blocking_lint, so a sheet with
a pose change in 0.25 s (lint code L02) reached the H3 story. convert_pack now lints every sheet in use with the shot
seconds of its row (or the lock) and turns each lint problem into a problem for that shot.

Hand-checked numbers: pose change in 0.25 s is under 0.5 s, so the lint code is L02 (blocking_lint: seconds < 0.5 -> L02,
0.5 <= seconds < 1.0 -> L03). A pose change in 5.0 s is over POSE_CHANGE_MIN_SEC (1.0 s) and gives no pose code.
Offline: no model call, no network.
"""
import copy

from h3 import v4_to_h3 as v4
from h3.tests.test_v4_to_h3 import _row

BIBLE = {"style_lock": {"prefix": "2D hand-drawn cel-shaded anime, organic line weight."},
         "forbidden_looks": ["3D CG"], "characters": {}, "environments": {}, "props": {}}
SID = "SHOT-001"


def _pose(x, pose="standing", facing="right"):
    return {"x": x, "y": 0.8, "scale": 0.5, "facing": facing, "pose": pose, "mouth_moves": False}


def _member(cid, name, x, end_pose="standing", end_facing="right"):
    return {"id": cid, "name": name, "speaks": False, "arms": 2, "source_refs": ["ch2:p10"],
            "start": _pose(x), "end": _pose(x, end_pose, end_facing)}


def _sheet(cast):
    """The same shape as the sheets of director/test_e2e_blocking_lock.py (known to pass blocking.validate)."""
    return {"schema": "blocking/1", "shot_id": SID, "plate_id": "PLATE-hall", "location_id": "ENV-HALL",
            "kind": "acting", "camera": {"mode": "fixed", "framing": "medium", "move": None},
            "light": {"key_dir": "left", "palette_id": "PAL-warm"},
            "props": [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["A", "B"]}],
            "entries": [], "exits": [], "sound_cues": [{"t": 1.0, "text": "soft wind"}],
            "arc_sec": 2.0, "writer_seconds": 5.0, "cut_to_next": "cut", "source_refs": ["ch2:p10"], "cast": cast}


def _convert(sheet, seconds, tmp_path):
    row = _row(SID, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD")
    row["editorial_duration_sec"] = seconds
    return v4.convert_pack({"shots": [row], "bible": copy.deepcopy(BIBLE), "stage": {},
                            "asset_root": str(tmp_path)},
                           languages=["en"], blocking={SID: sheet})["problems"]


def _lint_problems(problems):
    return [p for p in problems if p.startswith(SID + ": L")]


def test_fast_pose_change_is_blocked(tmp_path):
    """Raj goes standing -> seated in 0.25 s: lint L02 must reach the problems of SHOT-001."""
    sheet = _sheet([_member("CHAR-RAJ", "Raj", 0.3, end_pose="seated")])
    problems = _convert(sheet, 0.25, tmp_path)
    assert SID + ": L02 pose change too fast" in problems, problems


def test_clean_sheet_passes_lint(tmp_path):
    """No pose change at all: no lint code for SHOT-001."""
    sheet = _sheet([_member("CHAR-RAJ", "Raj", 0.3)])
    assert _lint_problems(_convert(sheet, 5.0, tmp_path)) == []


def test_pose_change_in_five_seconds_is_not_blocked(tmp_path):
    """The same pose change as the blocked case, but in 5.0 s: no pose code (the rule is about speed, not the change)."""
    sheet = _sheet([_member("CHAR-RAJ", "Raj", 0.3, end_pose="seated")])
    assert [p for p in _lint_problems(_convert(sheet, 5.0, tmp_path)) if "L02" in p or "L03" in p] == []


def test_no_sheet_means_no_lint(tmp_path, monkeypatch):
    """A pack that carries no sheet never loads blocking_lint: results stay as they were."""
    def boom():
        raise AssertionError("blocking_lint must not run without a sheet")
    monkeypatch.setattr(v4, "_lint_module", boom)
    row = _row(SID, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD")
    res = v4.convert_pack({"shots": [row], "bible": copy.deepcopy(BIBLE), "stage": {}, "asset_root": str(tmp_path)},
                          languages=["en"])
    assert _lint_problems(res["problems"]) == []
    res = v4.convert_pack({"shots": [row], "bible": copy.deepcopy(BIBLE), "stage": {}, "asset_root": str(tmp_path)},
                          languages=["en"], blocking={})
    assert _lint_problems(res["problems"]) == []


def test_l01_validation_code_reaches_problems(tmp_path):
    """A bad pose value is a blocking.validate fault; through lint it comes out as SHOT-001: L01 with the rule text."""
    bad = _member("CHAR-RAJ", "Raj", 0.3)
    bad["start"]["pose"] = "dancing"
    problems = _convert(_sheet([bad]), 5.0, tmp_path)
    assert any(p.startswith(SID + ": L01 ") and "bad pose value" in p for p in problems), problems


def test_l10_facing_change_without_turn_reaches_problems(tmp_path):
    """Facing flips right -> left with no turn record: SHOT-001: L10 (lint code), not only a validate line."""
    turned = _member("CHAR-RAJ", "Raj", 0.3)
    turned["end"]["facing"] = "left"
    problems = _convert(_sheet([turned]), 5.0, tmp_path)
    assert SID + ": L10 facing changes without a turn record for CHAR-RAJ" in problems, problems
