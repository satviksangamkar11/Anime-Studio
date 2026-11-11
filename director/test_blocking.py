import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blocking  # noqa: E402
import shot_router  # noqa: E402


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


def test_valid_sheet_has_no_problems():
    assert blocking.validate(_sheet()) == []


def test_missing_plate_id_reported():
    sheet = _sheet()
    del sheet["plate_id"]
    problems = blocking.validate(sheet)
    assert problems
    assert any(p.startswith("SHOT-001: BLK-S") for p in problems)


def test_bad_pose_value_reported():
    sheet = _sheet()
    sheet["cast"][0]["start"]["pose"] = "dancing"
    problems = blocking.validate(sheet)
    assert problems
    assert any(p.startswith("SHOT-001: BLK-S") for p in problems)


def test_file_name_id_mismatch_raises(tmp_path):
    path = tmp_path / "SHOT-002.json"
    path.write_text(json.dumps(_sheet()), encoding="utf-8")  # sheet says SHOT-001
    assert issubclass(blocking.BlockingError, ValueError)
    with pytest.raises(blocking.BlockingError):
        blocking.load_sheet(str(path))


def test_load_sheet_roundtrip(tmp_path):
    path = tmp_path / "SHOT-001.json"
    path.write_text(json.dumps(_sheet()), encoding="utf-8")
    assert blocking.load_sheet(str(path)) == _sheet()


def test_load_reel_missing_file_raises(tmp_path):
    with pytest.raises((blocking.BlockingError, OSError)):
        blocking.load_reel(str(tmp_path), ["SHOT-001"])


def test_distance_hand_checked():
    member = {"start": _pose(0.20, 0.80, 0.50), "end": _pose(0.60, 0.80, 0.50)}
    # 0.4 * 9/16 = 0.225 frame heights, no scale change
    assert blocking.distance(member) == pytest.approx(0.225)


def test_distance_includes_scale_change():
    member = {"start": _pose(0.5, 0.8, 0.5), "end": _pose(0.5, 0.8, 0.6)}
    assert blocking.distance(member) == pytest.approx(0.1)


def test_is_moving_pose_only():
    member = _member("SHIVA", (0.5, 0.8), (0.5, 0.8), pose="seated")
    member["end"]["pose"] = "standing"
    assert blocking.distance(member) == pytest.approx(0.0)
    assert blocking.is_moving(member) is True


def test_is_moving_false_when_nothing_changes():
    member = _member("SHIVA", (0.5, 0.8), (0.5, 0.8))
    assert blocking.is_moving(member) is False


def test_validate_never_raises_on_garbage():
    for garbage in (None, [], "x", {}):
        result = blocking.validate(garbage)
        assert isinstance(result, list)
        assert result  # garbage is never a valid sheet


def test_router_features_kfi_case():
    sheet = _sheet()
    features = blocking.router_features(sheet, 168)
    assert features["duration_sec"] == pytest.approx(7.0)
    assert features["needs_end_pose"] is True
    assert features["cast_count"] == 1
    assert features["arc_sec"] == pytest.approx(2.0)
    route = shot_router.route_shot(features)
    assert route["route"] == "KFI"


def test_router_features_soft_se_case():
    sheet = _sheet()
    sheet["arc_sec"] = 1.0
    features = blocking.router_features(sheet, 168)
    route = shot_router.route_shot(features)
    assert route["route"] == "SOFT_SE"


def test_prompt_args_offscreen_entry_not_on_screen():
    sheet = _sheet()
    sheet["cast"] = [
        _member("A", (0.3, 0.8), (0.3, 0.8), speaks=True),
        _member("GHOST", (-0.3, 0.8), (-0.2, 0.8)),  # off-frame at start and end
    ]
    args = blocking.prompt_args(sheet)
    assert args["cast"] == ["A", "GHOST"]
    assert args["on_screen"] == ["A"]
    assert args["speaking"] == ["A"]
    assert args["sound_cues"] == ["soft wind"]
    assert set(args["visible"]) == {"A", "GHOST", "throne"}


def test_image_expect_counts():
    sheet = _sheet()
    sheet["cast"] = [
        _member("A", (0.3, 0.8), (0.3, 0.8)),
        _member("B", (0.7, 0.8), (0.7, 0.8)),
        _member("C", (-0.2, 0.8), (0.2, 0.8)),  # entering: off-frame at start
    ]
    sheet["entries"] = [{"char": "C", "side": "left"}]
    expect = blocking.image_expect(sheet, 24)
    assert expect["required_cast_count"] == 2
    assert expect["entry_exit_allowed"] is True
    assert expect["seconds"] == pytest.approx(1.0)


def test_known_classes():
    sheet = _sheet()
    sheet["props"].append({"id": "P2", "class": "snake", "x": 0.4, "y": 0.9, "visible": ["A"]})
    assert blocking.known_classes(sheet) == {"person", "throne", "snake"}


def test_change_list_exact():
    sheet = _sheet()
    sheet["cast"] = [_member("SHIVA", (0.5, 0.8), (0.5, 0.8), pose="seated")]
    sheet["cast"][0]["end"]["pose"] = "standing"
    assert blocking.change_list(sheet) == ["SHIVA: seated -> standing", "keep everything else exactly the same"]


def test_known_classes_follow_the_cast():
    """Gap 8: 'person' is allowed only while the sheet has a cast member; prop classes always come from props."""
    sheet = _sheet()
    sheet["cast"] = [_member("A", (0.3, 0.8), (0.3, 0.8)), _member("B", (0.7, 0.8), (0.7, 0.8))]
    assert "person" in blocking.known_classes(sheet)
    sheet["cast"] = [m for m in sheet["cast"] if m["id"] != "A"]
    assert "person" in blocking.known_classes(sheet), "one cast member left: person stays allowed"
    sheet["cast"] = []
    assert blocking.known_classes(sheet) == {"throne"}, "no cast member: person is removed from the allowed set"
    assert blocking.known_classes({"props": [{"class": "dog"}]}) == {"dog"}
