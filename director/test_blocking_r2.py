import os
import re
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


def _seated_to_standing():
    member = _member("SHIVA", (0.5, 0.8), (0.5, 0.8), pose="seated")
    member["end"]["pose"] = "standing"
    return member


def _sheet():
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
        "arc_sec": 2.0,
        "writer_seconds": 5.0,
        "cut_to_next": "cut",
        "source_refs": ["ch2:p10"],
        "cast": [_seated_to_standing()],
    }


def _codes(problems):
    found = set()
    for p in problems:
        found.update(re.findall(r"BLK-S\d+", p))
    return found


def _has_s_problem(problems):
    return bool(problems) and any("BLK-S" in p for p in problems)


def _turned_facing_sheet(deg, sec):
    # facing right -> left, so the turn record is the only thing that explains the change
    member = _member("SHIVA", (0.5, 0.8), (0.5, 0.8), pose="standing", facing="right")
    member["end"]["facing"] = "left"
    member["turn"] = {"deg": deg, "sec": sec}
    sheet = _sheet()
    sheet["cast"] = [member]
    return sheet


def test_valid_sheet_still_has_no_problems():
    assert blocking.validate(_sheet()) == []


def test_pace_code_unique(tmp_path):
    # defect 1: bad pace must use BLK-S19, not the shot_id/file-name mismatch code BLK-S17
    bad_pace = _sheet()
    bad_pace["cast"][0]["pace"] = "run"
    pace_codes = _codes(blocking.validate(bad_pace))

    path = tmp_path / "SHOT-002.json"
    path.write_text(json.dumps(_sheet()), encoding="utf-8")  # sheet says SHOT-001, file says SHOT-002
    with pytest.raises(blocking.BlockingError) as info:
        blocking.load_sheet(str(path))
    mismatch_codes = _codes(info.value.args[0])

    assert pace_codes
    assert mismatch_codes
    assert pace_codes.isdisjoint(mismatch_codes)
    assert "BLK-S19" in pace_codes


def test_nan_arc_sec_reported():
    sheet = _sheet()
    sheet["arc_sec"] = float("nan")
    assert _has_s_problem(blocking.validate(sheet))


def test_inf_writer_seconds_reported():
    sheet = _sheet()
    sheet["writer_seconds"] = float("inf")
    assert _has_s_problem(blocking.validate(sheet))


def test_pose_missing_facing_reported():
    sheet = _sheet()
    del sheet["cast"][0]["start"]["facing"]
    assert _has_s_problem(blocking.validate(sheet))


def test_pose_missing_pose_reported():
    sheet = _sheet()
    del sheet["cast"][0]["start"]["pose"]
    assert _has_s_problem(blocking.validate(sheet))


def test_pose_missing_mouth_moves_reported():
    sheet = _sheet()
    del sheet["cast"][0]["start"]["mouth_moves"]
    assert _has_s_problem(blocking.validate(sheet))


def test_camera_without_move_key_reported():
    sheet = _sheet()
    del sheet["camera"]["move"]
    assert _has_s_problem(blocking.validate(sheet))


def test_duplicate_cast_ids_reported():
    sheet = _sheet()
    sheet["cast"] = [_member("SHIVA", (0.3, 0.8), (0.3, 0.8)), _member("SHIVA", (0.7, 0.8), (0.7, 0.8))]
    assert _has_s_problem(blocking.validate(sheet))


def test_entry_char_not_in_cast_reported():
    sheet = _sheet()
    sheet["entries"] = [{"char": "GHOST", "side": "left"}]
    assert _has_s_problem(blocking.validate(sheet))


def test_entry_without_char_reported():
    sheet = _sheet()
    sheet["entries"] = [{"side": "left"}]
    assert _has_s_problem(blocking.validate(sheet))


def test_exit_char_not_in_cast_reported():
    sheet = _sheet()
    sheet["exits"] = [{"char": "GHOST", "side": "right"}]
    assert _has_s_problem(blocking.validate(sheet))


def test_speaks_string_reported():
    sheet = _sheet()
    sheet["cast"][0]["speaks"] = "yes"
    assert _has_s_problem(blocking.validate(sheet))


def test_arms_float_reported():
    sheet = _sheet()
    sheet["cast"][0]["arms"] = 2.5
    assert _has_s_problem(blocking.validate(sheet))


def test_arms_bool_reported():
    sheet = _sheet()
    sheet["cast"][0]["arms"] = True
    assert _has_s_problem(blocking.validate(sheet))


def test_arms_below_two_reported():
    sheet = _sheet()
    sheet["cast"][0]["arms"] = 1
    assert _has_s_problem(blocking.validate(sheet))


def test_prop_visible_only_in_A_disappears():
    # A is the start image: a prop visible only in A is gone by the end image
    sheet = _sheet()
    sheet["cast"] = [_member("SHIVA", (0.5, 0.8), (0.5, 0.8))]
    sheet["props"] = [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["A"]}]
    assert "throne: disappears" in blocking.change_list(sheet)
    assert "throne: appears" not in blocking.change_list(sheet)


def test_prop_visible_only_in_B_appears():
    # B is the end image: a prop visible only in B is new at the end
    sheet = _sheet()
    sheet["cast"] = [_member("SHIVA", (0.5, 0.8), (0.5, 0.8))]
    sheet["props"] = [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["B"]}]
    assert "throne: appears" in blocking.change_list(sheet)
    assert "throne: disappears" not in blocking.change_list(sheet)


def test_change_list_turn_keeps_mouth_line():
    sheet = _turned_facing_sheet(90, 1.0)
    sheet["cast"][0]["start"]["mouth_moves"] = False
    sheet["cast"][0]["end"]["mouth_moves"] = True
    changes = blocking.change_list(sheet)
    assert "SHIVA: turn 90 degrees right" in changes
    assert "SHIVA: mouth open" in changes


def test_change_list_turn_without_mouth_change():
    sheet = _turned_facing_sheet(90, 1.0)
    assert blocking.change_list(sheet) == [
        "SHIVA: turn 90 degrees right",
        "keep everything else exactly the same",
    ]
