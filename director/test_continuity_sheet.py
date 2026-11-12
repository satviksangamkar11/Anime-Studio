import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuity_sheet as c  # noqa: E402


def _m(mid, x, facing, speaks=False, end_x=None, end_facing=None, pose="standing"):
    end_x = x if end_x is None else end_x
    end_facing = facing if end_facing is None else end_facing
    return {"id": mid, "speaks": speaks,
            "start": {"x": x, "y": 0.6, "scale": 0.5, "pose": pose, "facing": facing, "mouth_moves": False},
            "end": {"x": end_x, "y": 0.6, "scale": 0.5, "pose": pose, "facing": end_facing, "mouth_moves": False}}


SHEET_1 = {"shot_id": "SHOT-001", "cut_to_next": "match",
           "cast": [_m("KRISHNA", 0.2, "right", end_x=0.3), _m("YASHODA", 0.7, "left", speaks=True)],
           "props": [{"id": "PROP-POT", "class": "pot", "x": 0.5, "y": 0.8, "visible": ["A"]},
                     {"id": "PROP-FLUTE", "class": "flute", "x": 0.1, "y": 0.5, "visible": ["A", "B"]}]}

SHEET_2_FLIP = {"shot_id": "SHOT-002", "cut_to_next": "cut",
                "cast": [_m("KRISHNA", 0.3, "left")], "props": []}


def test_direction_is_start_facing():
    assert c.direction(SHEET_1) == {"KRISHNA": "right", "YASHODA": "left"}


def test_eyeline_pair_facing_each_other():
    assert c.eyeline_pairs(SHEET_1) == [["KRISHNA", "YASHODA"]]


def test_no_eyeline_pair_when_both_face_same_way():
    s = {"shot_id": "SHOT-003", "cut_to_next": "cut",
         "cast": [_m("A", 0.2, "right"), _m("B", 0.7, "right")], "props": []}
    assert c.eyeline_pairs(s) == []


def test_no_eyeline_pair_when_facing_away_from_each_other():
    s = {"shot_id": "SHOT-004", "cut_to_next": "cut",
         "cast": [_m("A", 0.2, "left"), _m("B", 0.7, "left")], "props": []}
    assert c.eyeline_pairs(s) == []


def test_prop_states():
    assert c.prop_states(SHEET_1) == {"PROP-POT": "A only", "PROP-FLUTE": "A+B"}


def test_end_state_of_each_cast_member():
    assert c.end_state(SHEET_1)["KRISHNA"] == {"x": 0.3, "y": 0.6, "pose": "standing", "facing": "right"}


def test_direction_flip_across_match_cut_is_reported():
    s1 = dict(SHEET_1, cut_to_next="match")
    s2 = {"shot_id": "SHOT-002", "cut_to_next": "cut",
          "cast": [_m("KRISHNA", 0.3, "left")], "props": []}
    assert c.direction_flips([s1, s2]) == [("SHOT-001", "SHOT-002", "KRISHNA")]


def test_direction_change_on_a_plain_cut_is_not_a_flip():
    s1 = dict(SHEET_1, cut_to_next="cut")
    s2 = {"shot_id": "SHOT-002", "cut_to_next": "cut", "cast": [_m("KRISHNA", 0.3, "left")], "props": []}
    assert c.direction_flips([s1, s2]) == []


def test_rows_per_shot_and_empty_input():
    rows = c.continuity_rows([SHEET_1, SHEET_2_FLIP])
    assert [r["shot_id"] for r in rows] == ["SHOT-001", "SHOT-002"]
    assert rows[0]["eyeline_pairs"] == [["KRISHNA", "YASHODA"]] and rows[0]["prop_states"]["PROP-POT"] == "A only"
    assert c.continuity_rows([]) == []


def test_svg_written_with_shots_props_and_flip(tmp_path):
    out = tmp_path / "continuity.svg"
    s1 = dict(SHEET_1, cut_to_next="match")
    c.write_continuity_svg([s1, SHEET_2_FLIP], out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<svg") and "SHOT-001" in text and "PROP-POT" in text
    assert "FLIP" in text or "flip" in text.lower()


def test_svg_escapes_markup(tmp_path):
    s = {"shot_id": "SHOT-009", "cut_to_next": "cut",
         "cast": [_m("A<B>", 0.2, "right")], "props": []}
    out = tmp_path / "c.svg"
    c.write_continuity_svg([s], out)
    assert "A&lt;B&gt;" in out.read_text(encoding="utf-8")


def test_non_dict_start_or_end_does_not_crash():
    # M-31: a truthy non-dict start/end (bad input) is treated as empty, not an AttributeError
    sheet = {"shot_id": "SHOT-009", "cut_to_next": "cut",
             "cast": [{"id": "KRISHNA", "start": "left", "end": ["x"]}], "props": []}
    c.direction(sheet)
    c.eyeline_pairs(sheet)
    c.end_state(sheet)
