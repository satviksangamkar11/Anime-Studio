from layout_validator import check_layout
from test_shot_schema import RICH


def shot(**kw):
    return {**RICH, **kw}


A = shot(id="SHOT-06", end_state="Krishna on the branch, facing river", cut_in="establishing", cut_out="match on action")
B = shot(id="SHOT-07")   # RICH: start_state, cut_in "match on action from SHOT-06", end_state set


def test_a_clean_chain_has_no_problems():
    assert check_layout([A, B]) == []


def test_state_hand_off_needs_both_sides():
    assert check_layout([shot(id="A", end_state="", cut_in="x", cut_out="y"), B]) == ["A: missing end_state (hand-off to SHOT-07)"]
    assert check_layout([A, shot(id="SHOT-07", start_state="")]) == ["SHOT-07: missing start_state (hand-off from SHOT-06)"]


def test_cut_in_and_cut_out_must_be_present():
    problems = check_layout([shot(id="SHOT-06", cut_in="", cut_out=None), B])
    assert "SHOT-06: missing cut_in" in problems and "SHOT-06: missing cut_out" in problems


def test_a_facing_flip_in_one_scene_is_a_180_warning():
    flipped = shot(id="SHOT-07", cast=[dict(RICH["cast"][0], facing="left")])
    problems = check_layout([A, flipped])
    assert len(problems) == 1 and "180-degree" in problems[0] and "facing flips right -> left" in problems[0]


def test_a_flip_is_allowed_with_a_reverse_or_crossing_cut():
    flipped = shot(id="SHOT-07", cast=[dict(RICH["cast"][0], facing="left")])
    assert check_layout([A, dict(flipped, cut_in="reverse angle on Krishna")]) == []
    assert check_layout([A, dict(flipped, cut_in="crossing the line for the river view")]) == []


def test_a_flip_across_two_scenes_is_not_checked():
    flipped = shot(id="SHOT-07", scene="other", cast=[dict(RICH["cast"][0], facing="left")])
    assert check_layout([A, flipped]) == []


def test_opposite_screen_sides_must_face_opposite_ways():
    left = {"id": "CHAR-A", "screen": "left", "facing": "right"}
    same = {"id": "CHAR-B", "screen": "right", "facing": "right"}
    opposite = dict(same, facing="left")
    assert any("eyeline" in p for p in check_layout([shot(id="S", cast=[left, same])]))
    assert check_layout([shot(id="S", cast=[left, opposite])]) == []
