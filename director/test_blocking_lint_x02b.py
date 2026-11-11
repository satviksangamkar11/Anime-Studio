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
        "cast": [_member("SHIVA", (0.5, 0.8), (0.5, 0.8))],
    }
    sheet.update(over)
    return sheet


def _has(problems, code):
    return any(code in p for p in problems)


def _turn_sheet(deg, sec, writer_seconds=5.0):
    # facing right -> left, so only a turn record can explain the change
    member = _member("SHIVA", (0.5, 0.8), (0.5, 0.8), end_pose="standing", facing="right")
    member["end"]["facing"] = "left"
    member["turn"] = {"deg": deg, "sec": sec}
    return _sheet(writer_seconds=writer_seconds, cast=[member])


def test_speed_walk_half_ok():
    # 0.225 frame heights over 0.6 s = 0.375 per s, under the walk limit 0.5
    sheet = _sheet(writer_seconds=0.6, cast=[_member("SHIVA", (0.20, 0.8), (0.60, 0.8))])
    assert blocking_lint.lint([sheet]) == []


def test_speed_slow_pace_fails_same_move():
    # same move as above, but pace "slow" caps speed at 0.25 per s
    member = _member("SHIVA", (0.20, 0.8), (0.60, 0.8))
    member["pace"] = "slow"
    sheet = _sheet(writer_seconds=0.6, cast=[member])
    assert _has(blocking_lint.lint([sheet]), "L03")


def test_speed_fail_6_frames():
    # 0.225 frame heights over 6 frames = 0.25 s = 0.9 per s, over 0.5
    sheet = _sheet(writer_seconds=5.0, cast=[_member("SHIVA", (0.20, 0.8), (0.60, 0.8))])
    lock = {"shots": [{"id": "SHOT-001", "start_frame": 0, "edit_frames": 6}]}
    assert _has(blocking_lint.lint([sheet], lock=lock), "L03")


def test_facing_change_without_turn_l10():
    member = _member("SHIVA", (0.5, 0.8), (0.5, 0.8))
    member["end"]["facing"] = "left"
    assert _has(blocking_lint.lint([_sheet(cast=[member])]), "L10")


def test_turn_90_in_0_75s_l10():
    # 90 degrees needs at least 1.0 s
    assert _has(blocking_lint.lint([_turn_sheet(90, 0.75)]), "L10")


def test_turn_90_in_1_0s_ok():
    assert blocking_lint.lint([_turn_sheet(90, 1.0)]) == []


def test_turn_180_in_1_5s_l10():
    # 180 degrees needs at least 2.0 s
    assert _has(blocking_lint.lint([_turn_sheet(-180, 1.5)]), "L10")


def test_turn_180_in_2_0s_ok():
    assert blocking_lint.lint([_turn_sheet(-180, 2.0)]) == []


def test_turn_longer_than_shot_l10():
    # turn of 3.0 s inside a 2.0 s shot
    assert _has(blocking_lint.lint([_turn_sheet(90, 3.0, writer_seconds=2.0)]), "L10")


def test_no_facing_change_no_turn_ok():
    assert blocking_lint.lint([_sheet()]) == []
