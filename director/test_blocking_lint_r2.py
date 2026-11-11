import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blocking_lint  # noqa: E402


def _pose(x, y, scale=0.5, facing="right", pose="standing", mouth=False):
    return {"x": x, "y": y, "scale": scale, "facing": facing, "pose": pose, "mouth_moves": mouth}


def _member(cid, start_xy, end_xy, pose="standing", end_pose=None, facing="right", speaks=False,
            start_mouth=False, end_mouth=False, arms=2):
    return {
        "id": cid,
        "name": cid,
        "speaks": speaks,
        "arms": arms,
        "source_refs": ["ch2:p10"],
        "start": _pose(start_xy[0], start_xy[1], 0.5, facing, pose, start_mouth),
        "end": _pose(end_xy[0], end_xy[1], 0.5, facing, end_pose or pose, end_mouth),
    }


def _sheet(shot_id="SHOT-001", **over):
    sheet = {
        "schema": "blocking/1",
        "shot_id": shot_id,
        "plate_id": "PLATE-throne",
        "location_id": "LOC-palace-hall",
        "kind": "acting",
        "camera": {"mode": "fixed", "framing": "medium", "move": None},
        "light": {"key_dir": "left", "palette_id": "PAL-warm"},
        "props": [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["A", "B"]}],
        "entries": [],
        "exits": [],
        "sound_cues": [{"t": 1.0, "text": "soft wind"}],
        "arc_sec": 0.0,
        "writer_seconds": 5.0,
        "cut_to_next": "cut",
        "source_refs": ["ch2:p10"],
        "cast": [_member("SHIVA", (0.5, 0.8), (0.5, 0.8), pose="seated", end_pose="standing")],
    }
    sheet.update(over)
    return sheet


def _has(problems, code):
    return any(code in p for p in problems)


def _static_sheet(**over):
    return _sheet(cast=[_member("SHIVA", (0.5, 0.8), (0.5, 0.8))], **over)


def test_clean_sheet_passes():
    assert blocking_lint.lint([_sheet()]) == []


def test_none_cast_name_with_sound_cue_does_not_raise():
    sheet = _sheet()
    sheet["cast"][0]["name"] = None
    problems = blocking_lint.lint([sheet])
    assert isinstance(problems, list)


def test_none_prop_class_does_not_raise():
    sheet = _sheet()
    sheet["props"][0]["class"] = None
    problems = blocking_lint.lint([sheet])
    assert isinstance(problems, list)


def test_lock_edit_frames_zero_reported():
    # 0 frames for a 0.225 frame-height move is unreachable
    sheet = _sheet(writer_seconds=5.0, cast=[_member("SHIVA", (0.20, 0.8), (0.60, 0.8))])
    lock = {"shots": [{"id": "SHOT-001", "start_frame": 0, "edit_frames": 0}]}
    problems = blocking_lint.lint([sheet], lock=lock)
    assert problems
    assert _has(problems, "L03")


def test_lint_none_returns_problem():
    problems = blocking_lint.lint(None)
    assert isinstance(problems, list)
    assert problems


def test_lint_non_dict_sheet_does_not_raise():
    problems = blocking_lint.lint(["x", None, 5])
    assert isinstance(problems, list)


def test_member_missing_start_does_not_raise():
    sheet = _sheet()
    del sheet["cast"][0]["start"]
    problems = blocking_lint.lint([sheet])
    assert isinstance(problems, list)
    assert _has(problems, "L01")


def test_member_start_none_does_not_raise():
    sheet = _sheet()
    sheet["cast"][0]["start"] = None
    problems = blocking_lint.lint([sheet])
    assert isinstance(problems, list)


def test_l09_entry_char_not_in_cast():
    sheet = _static_sheet(entries=[{"char": "GHOST", "side": "left"}])
    problems = blocking_lint.lint([sheet])
    assert any("GHOST" in p for p in problems)


def test_turn_180_in_0_5s_unchanged_facing_l10():
    sheet = _static_sheet()
    sheet["cast"][0]["turn"] = {"deg": 180, "sec": 0.5}
    assert _has(blocking_lint.lint([sheet]), "L10")


def test_turn_90_in_1_0s_unchanged_facing_ok():
    sheet = _static_sheet()
    sheet["cast"][0]["turn"] = {"deg": 90, "sec": 1.0}
    assert not _has(blocking_lint.lint([sheet]), "L10")


def test_turn_longer_than_shot_unchanged_facing_l10():
    sheet = _static_sheet(writer_seconds=2.0)
    sheet["cast"][0]["turn"] = {"deg": 90, "sec": 3.0}
    assert _has(blocking_lint.lint([sheet]), "L10")


def test_facing_change_with_invalid_turn_still_l10():
    member = _member("SHIVA", (0.5, 0.8), (0.5, 0.8), facing="right")
    member["end"]["facing"] = "left"
    member["turn"] = {"deg": 0, "sec": 1.0}
    sheet = _sheet(cast=[member])
    problems = blocking_lint.lint([sheet])
    assert _has(problems, "L01")
    assert _has(problems, "L10")
