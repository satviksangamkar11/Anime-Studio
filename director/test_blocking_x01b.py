import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blocking  # noqa: E402


def _pose(x, y, scale, facing="right", pose="standing", mouth=False):
    return {"x": x, "y": y, "scale": scale, "facing": facing, "pose": pose, "mouth_moves": mouth}


def _member(cid, start_xy, end_xy, pose="standing", facing="right", scale=0.5, speaks=False, arms=2):
    return {
        "id": cid,
        "name": cid,
        "speaks": speaks,
        "arms": arms,
        "source_refs": ["ch2:p10"],
        "start": _pose(start_xy[0], start_xy[1], scale, facing, pose),
        "end": _pose(end_xy[0], end_xy[1], scale, facing, pose),
    }


def _sheet(**member_extra):
    member = _member("SHIVA", (0.5, 0.8), (0.5, 0.8))
    member.update(member_extra)
    return {
        "schema": "blocking/1",
        "shot_id": "SHOT-001",
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
        "cast": [member],
    }


def _turned(deg, sec):
    # facing changes right -> left, so a turn record is the only thing that explains it
    sheet = _sheet(turn={"deg": deg, "sec": sec})
    sheet["cast"][0]["end"]["facing"] = "left"
    return sheet


def _is_s_problem(problems):
    return bool(problems) and all(p.startswith("SHOT-001: BLK-S") for p in problems)


def test_pace_default_walk_ok():
    # no "pace" key at all means walk
    assert blocking.validate(_sheet()) == []


def test_pace_slow_ok():
    assert blocking.validate(_sheet(pace="slow")) == []


def test_bad_pace_reported():
    assert _is_s_problem(blocking.validate(_sheet(pace="run")))


def test_turn_valid_ok():
    assert blocking.validate(_turned(90, 1.0)) == []
    assert blocking.validate(_turned(-180, 2.0)) == []


def test_turn_zero_deg_reported():
    assert _is_s_problem(blocking.validate(_turned(0, 1.0)))


def test_turn_bool_deg_reported():
    assert _is_s_problem(blocking.validate(_turned(True, 1.0)))


def test_turn_float_deg_reported():
    assert _is_s_problem(blocking.validate(_turned(90.0, 1.0)))


def test_turn_out_of_range_reported():
    assert _is_s_problem(blocking.validate(_turned(400, 1.0)))
    assert _is_s_problem(blocking.validate(_turned(-400, 1.0)))


def test_turn_bad_sec_reported():
    for bad in (0, -1, float("nan"), True):
        assert _is_s_problem(blocking.validate(_turned(90, bad))), bad


def test_turn_not_dict_reported():
    assert _is_s_problem(blocking.validate(_sheet(turn="left")))


def test_change_list_turn_right():
    sheet = _turned(90, 1.0)
    changes = blocking.change_list(sheet)
    assert "SHIVA: turn 90 degrees right" in changes
    assert not any("turn to face" in line for line in changes)


def test_change_list_turn_left():
    sheet = _turned(-180, 2.0)
    changes = blocking.change_list(sheet)
    assert "SHIVA: turn 180 degrees left" in changes
    assert not any("turn to face" in line for line in changes)


def test_change_list_without_turn_unchanged():
    sheet = _turned(90, 1.0)
    del sheet["cast"][0]["turn"]
    assert "SHIVA: turn to face left" in blocking.change_list(sheet)
