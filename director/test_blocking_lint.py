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


def test_clean_sheet_passes():
    assert blocking_lint.lint([_sheet()]) == []


def test_l01_validate_problem_passed_through():
    sheet = _sheet()
    del sheet["plate_id"]
    problems = blocking_lint.lint([sheet])
    assert _has(problems, "L01")
    assert all(p.startswith("SHOT-001: ") for p in problems)


def test_speed_ok_5s():
    # 0.4 * 9/16 = 0.225 frame heights over 5 s = 0.045 per s, under 0.25
    sheet = _sheet(writer_seconds=5.0, cast=[_member("SHIVA", (0.20, 0.8), (0.60, 0.8))])
    assert blocking_lint.lint([sheet]) == []


# changed 2026-11-11 (owner approved): walking limit is now 0.5 FH/s
def test_speed_fail_6_frames_old():
    # 0.225 over 6 frames = 0.25 s = speed 0.9 per s, over 0.5
    sheet = _sheet(writer_seconds=5.0, cast=[_member("SHIVA", (0.20, 0.8), (0.60, 0.8))])
    lock = {"shots": [{"id": "SHOT-001", "start_frame": 0, "edit_frames": 6}]}
    assert _has(blocking_lint.lint([sheet], lock=lock), "L03")


def test_pose_change_18_frames_fails():
    # 18 frames = 0.75 s, under POSE_CHANGE_MIN_SEC 1.0
    sheet = _sheet(writer_seconds=0.75)
    problems = blocking_lint.lint([sheet])
    assert _has(problems, "L02") or _has(problems, "L03")


def test_pose_change_24_frames_passes():
    # 24 frames = 1.0 s, exactly the minimum
    sheet = _sheet(writer_seconds=1.0)
    assert blocking_lint.lint([sheet]) == []


def test_crossing():
    a = _member("A", (0.3, 0.8), (0.7, 0.8))
    b = _member("B", (0.6, 0.8), (0.4, 0.8))
    sheet = _sheet(cast=[a, b])
    assert _has(blocking_lint.lint([sheet]), "L04")


def test_continuity_0_03_ok_0_10_fails():
    def pair(second_start_x):
        s1 = _sheet("SHOT-001", cut_to_next="match",
                    cast=[_member("SHIVA", (0.5, 0.8), (0.5, 0.8))])
        s2 = _sheet("SHOT-002", cast=[_member("SHIVA", (second_start_x, 0.8), (second_start_x, 0.8))])
        return [s1, s2]

    assert blocking_lint.lint(pair(0.53)) == []
    assert _has(blocking_lint.lint(pair(0.60)), "L05")


def test_continuity_cut_allows_jump():
    s1 = _sheet("SHOT-001", cut_to_next="cut", cast=[_member("SHIVA", (0.5, 0.8), (0.5, 0.8))])
    s2 = _sheet("SHOT-002", cast=[_member("SHIVA", (0.60, 0.8), (0.60, 0.8))])
    assert blocking_lint.lint([s1, s2]) == []


def test_four_movers_fail():
    cast = [
        _member(f"M{i}", (0.1 + 0.1 * i, 0.5 + 0.1 * i), (0.5 + 0.1 * i, 0.5 + 0.1 * i))
        for i in range(4)
    ]
    sheet = _sheet(cast=cast)
    assert _has(blocking_lint.lint([sheet]), "L06")


def test_speaker_without_mouth_fails():
    sheet = _sheet(cast=[_member("SHIVA", (0.5, 0.8), (0.5, 0.8), speaks=True)])
    assert _has(blocking_lint.lint([sheet]), "L07")


def test_speaker_with_mouth_passes():
    sheet = _sheet(cast=[_member("SHIVA", (0.5, 0.8), (0.5, 0.8), speaks=True, start_mouth=True)])
    assert blocking_lint.lint([sheet]) == []


def test_serpents_hiss_fails():
    sheet = _sheet(sound_cues=[{"t": 1.0, "text": "serpents hiss"}])
    assert _has(blocking_lint.lint([sheet]), "L08")


def test_snake_visible_prop_passes():
    sheet = _sheet(
        props=[{"id": "P2", "class": "snake", "x": 0.4, "y": 0.9, "visible": ["A", "B"]}],
        sound_cues=[{"t": 1.0, "text": "snakes hiss"}],
    )
    assert blocking_lint.lint([sheet]) == []


def test_entry_must_start_offscreen():
    sheet = _sheet(entries=[{"char": "SHIVA", "side": "left"}])  # SHIVA starts at x 0.5, on screen
    assert _has(blocking_lint.lint([sheet]), "L09")


def test_entry_starting_offscreen_passes():
    sheet = _sheet(
        entries=[{"char": "SHIVA", "side": "left"}],
        cast=[_member("SHIVA", (-0.2, 0.8), (0.3, 0.8))],
    )
    assert blocking_lint.lint([sheet]) == []


# changed 2026-11-11 (owner approved): walking limit is now 0.5 FH/s
def test_lock_seconds_override_writer_seconds():
    cast = [_member("SHIVA", (0.20, 0.8), (0.60, 0.8))]  # 0.225 frame heights
    writer_only = _sheet(writer_seconds=5.0, cast=cast)
    assert blocking_lint.lint([writer_only]) == []
    lock = {"shots": [{"id": "SHOT-001", "start_frame": 0, "edit_frames": 6}]}  # 0.25 s
    assert _has(blocking_lint.lint([writer_only], lock=lock), "L03")
