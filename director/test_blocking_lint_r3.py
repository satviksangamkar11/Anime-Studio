"""Round-3 tests for director/blocking_lint.py: non-number pose values must give a problem, never a TypeError.
Written BEFORE the fixes (rule 54(3)): frozen after.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blocking_lint  # noqa: E402


def _pose(x, y, scale=0.5, facing="right", pose="standing", mouth=False):
    return {"x": x, "y": y, "scale": scale, "facing": facing, "pose": pose, "mouth_moves": mouth}


def _sheet(**over):
    member = {
        "id": "SHIVA", "name": "SHIVA", "speaks": False, "arms": 2, "source_refs": ["ch2:p10"],
        "start": _pose(0.5, 0.8, 0.5, "right", "seated"),
        "end": _pose(0.5, 0.8, 0.5, "right", "standing"),
    }
    sheet = {
        "schema": "blocking/1", "shot_id": "SHOT-001", "plate_id": "PLATE-throne",
        "location_id": "LOC-palace-hall", "kind": "acting",
        "camera": {"mode": "fixed", "framing": "medium", "move": None},
        "light": {"key_dir": "left", "palette_id": "PAL-warm"},
        "props": [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["A", "B"]}],
        "entries": [], "exits": [], "sound_cues": [{"t": 1.0, "text": "soft wind"}],
        "arc_sec": 0.0, "writer_seconds": 5.0, "cut_to_next": "cut", "source_refs": ["ch2:p10"],
        "cast": [member],
    }
    sheet.update(over)
    return sheet


def test_string_x_does_not_raise():
    sheet = _sheet()
    sheet["cast"][0]["start"]["x"] = "0.5"
    problems = blocking_lint.lint([sheet])
    assert isinstance(problems, list)
    assert any("L01" in p for p in problems)


def test_string_scale_does_not_raise():
    sheet = _sheet()
    sheet["cast"][0]["start"]["scale"] = "0.5"
    assert isinstance(blocking_lint.lint([sheet]), list)


def test_string_y_does_not_raise():
    sheet = _sheet()
    sheet["cast"][0]["start"]["y"] = "0.8"
    assert isinstance(blocking_lint.lint([sheet]), list)


def test_none_x_does_not_raise():
    sheet = _sheet()
    sheet["cast"][0]["start"]["x"] = None
    assert isinstance(blocking_lint.lint([sheet]), list)


def test_string_arc_sec_does_not_raise():
    sheet = _sheet(arc_sec="2.0")
    problems = blocking_lint.lint([sheet])
    assert isinstance(problems, list)
    assert any("L01" in p for p in problems)
