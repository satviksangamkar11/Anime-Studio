import copy
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import blocking  # noqa: E402
import blocking_lint  # noqa: E402


def _pose(x, y, scale, facing, pose, mouth):
    return {"x": x, "y": y, "scale": scale, "facing": facing, "pose": pose, "mouth_moves": mouth}


# The full Opus example sheet (research/OPUS_CALIBRATION_REVIEW_2026-11-12.md section 6.3).
OPUS_EXAMPLE = {
    "schema": "blocking/1.1", "shot_id": "SHOT-012", "plate_id": "PLATE-yamuna-bank-morning",
    "location_id": "LOC-yamuna-bank", "kind": "acting", "emotion": "resolve", "composition": "thirds_left",
    "route": "SE",
    "camera": {"mode": "fixed", "framing": "medium", "move": None, "angle": "eye_level", "lens": "normal",
               "motivation": None, "shake": None},
    "light": {"key_dir": "left", "palette_id": "PAL-morning"},
    "props": [{"id": "P1", "class": "flute", "x": 0.30, "y": 0.62, "visible": ["A", "B"]}],
    "entries": [], "exits": [],
    "sound_cues": [{"t": 1.6, "text": "cloth rustle", "kind": "hit"}, {"t": 0.0, "text": "river wind", "kind": "bed"}],
    "beats": [{"t": 0.0, "label": "STILL", "action": "Krishna kneels, eyes on the river", "physics": "reeds sway",
               "primary": False},
              {"t": 1.6, "label": "RISE", "action": "Krishna stands up in one smooth push",
               "physics": "dhoti hem swings and settles", "primary": True},
              {"t": 4.0, "label": "HOLD", "action": "Krishna lifts the flute to chest height",
               "physics": "wind lifts the peacock feather", "primary": False}],
    "arc_sec": 2.4, "writer_seconds": 5.9, "cut_to_next": "cut", "chain_from": None, "voice_rest": None,
    "hook_type": None, "source_refs": ["L41"],
    "cast": [{"id": "CHAR-KRISHNA", "name": "Krishna", "speaks": False, "arms": 2, "pace": "slow", "hold": False,
              "expression": "resolve", "source_refs": ["L41"],
              "start": {"x": 0.30, "y": 0.70, "scale": 0.50, "facing": "right", "pose": "kneeling",
                        "mouth_moves": False},
              "end": {"x": 0.30, "y": 0.66, "scale": 0.72, "facing": "right", "pose": "standing",
                      "mouth_moves": False}}],
}


def _ex():
    return copy.deepcopy(OPUS_EXAMPLE)


def _shot(shot_id, seconds, cut="cut", hook=None, chain_from=None):
    """Minimal valid blocking/1.1 sheet with no cast: used for the reel-level lint rules."""
    return {
        "schema": "blocking/1.1", "shot_id": shot_id, "plate_id": "PLATE-x", "location_id": "LOC-x",
        "kind": "acting", "camera": {"mode": "fixed", "framing": "wide", "move": None},
        "light": {"key_dir": "top", "palette_id": "PAL-x"}, "props": [], "entries": [], "exits": [],
        "sound_cues": [], "arc_sec": 0.0, "writer_seconds": seconds, "cut_to_next": cut,
        "source_refs": ["L1"], "cast": [], "hook_type": hook, "chain_from": chain_from,
    }


def _codes(problems):
    found = set()
    for p in problems:
        found.update("L%s" % c for c in re.findall(r"\bL(\d\d)\b", p))
    return found


def _lint_one(sheet):
    return blocking_lint.lint([sheet])


def _with_hook(sheet, hook="kinetic"):
    sheet["hook_type"] = hook
    return sheet


# ---- loading and validation -------------------------------------------------------------------

def test_full_opus_example_validates():
    assert blocking.validate(_ex()) == []


def test_full_opus_example_lints_clean_once_hook_is_set():
    assert _lint_one(_with_hook(_ex())) == []


def test_blocking_1_0_sheets_still_load(tmp_path):
    sheet = {
        "schema": "blocking/1", "shot_id": "SHOT-001", "plate_id": "PLATE-throne", "location_id": "LOC-throne",
        "kind": "acting", "camera": {"mode": "move", "framing": "medium", "move": "dolly_in_free_text"},
        "light": {"key_dir": "left", "palette_id": "PAL-x"}, "props": [], "entries": [], "exits": [],
        "sound_cues": [], "arc_sec": 0.0, "writer_seconds": 4.0, "cut_to_next": "cut", "source_refs": ["L1"],
        "cast": [],
    }
    assert blocking.validate(sheet) == []
    path = tmp_path / "SHOT-001.json"
    path.write_text(json.dumps(sheet), encoding="utf-8")
    assert blocking.load_sheet(str(path))["shot_id"] == "SHOT-001"
    # 1.0 has no new rules: a free-text move and a move with no motivation lint clean
    assert _lint_one(sheet) == []


def test_unknown_schema_still_refused():
    sheet = _ex()
    sheet["schema"] = "blocking/2"
    assert any("BLK-S02" in p for p in blocking.validate(sheet))


def test_pace_fast_accepted_and_pace_of_returns_it():
    sheet = _ex()
    sheet["cast"][0]["pace"] = "fast"
    assert blocking.validate(sheet) == []
    assert blocking.pace_of(sheet["cast"][0]) == "fast"


def test_pace_unknown_value_refused():
    sheet = _ex()
    sheet["cast"][0]["pace"] = "turbo"
    assert any("BLK-S19" in p for p in blocking.validate(sheet))


def test_camera_move_enum_refused_on_1_1():
    sheet = _ex()
    sheet["camera"].update({"mode": "move", "move": "spin_wildly", "motivation": "audience must feel it"})
    assert any("BLK-S06" in p for p in blocking.validate(sheet))


def test_composition_enum_refused():
    sheet = _ex()
    sheet["composition"] = "diagonal"
    assert any("BLK-S20" in p for p in blocking.validate(sheet))


def test_emotion_route_hook_enums_refused():
    for field, bad in (("emotion", "meh"), ("route", "XX"), ("hook_type", "bogus")):
        sheet = _ex()
        sheet[field] = bad
        assert any("BLK-S21" in p for p in blocking.validate(sheet)), field


def test_shake_out_of_range_refused():
    sheet = _ex()
    sheet["camera"]["shake"] = {"t": 1.0, "dur": 2.0}
    assert any("BLK-S06" in p for p in blocking.validate(sheet))


def test_hold_and_expression_types_refused():
    sheet = _ex()
    sheet["cast"][0]["hold"] = "yes"
    assert any("BLK-S16" in p for p in blocking.validate(sheet))
    sheet = _ex()
    sheet["cast"][0]["expression"] = 3
    assert any("BLK-S16" in p for p in blocking.validate(sheet))


def test_beat_label_must_be_one_to_three_upper_words():
    sheet = _ex()
    sheet["beats"][0]["label"] = "still and quiet"
    assert any("BLK-S21" in p for p in blocking.validate(sheet))


def test_caption_safe_is_computed_from_speaking_faces():
    sheet = _ex()
    assert blocking.caption_safe(sheet) is True
    sheet["cast"][0]["speaks"] = True
    sheet["cast"][0]["start"]["mouth_moves"] = True
    sheet["cast"][0]["start"]["y"] = 0.70
    assert blocking.caption_safe(sheet) is False


# ---- lint L11-L17 -----------------------------------------------------------------------------

def test_l11_fixed_mode_with_a_move_flagged():
    sheet = _ex()
    sheet["camera"]["move"] = "push_in"
    assert "L11" in _codes(_lint_one(sheet))


def test_l11_move_mode_without_move_flagged():
    sheet = _ex()
    sheet["camera"]["mode"] = "move"
    assert "L11" in _codes(_lint_one(sheet))


def test_l11_move_needs_motivation_of_three_words():
    sheet = _ex()
    sheet["camera"].update({"mode": "move", "move": "push_in", "motivation": None})
    assert "L11" in _codes(_lint_one(sheet))
    sheet["camera"]["motivation"] = "too short"
    assert "L11" in _codes(_lint_one(sheet))
    sheet["camera"]["motivation"] = "audience must feel its size"
    assert "L11" not in _codes(_lint_one(sheet))


def test_l12_orbit_refused_while_a_cast_member_moves_without_hold():
    sheet = _ex()
    sheet["camera"].update({"mode": "move", "move": "orbit_left", "motivation": "divine presence fills the bank"})
    assert "L12" in _codes(_lint_one(sheet))
    sheet["cast"][0]["hold"] = True
    assert "L12" not in _codes(_lint_one(sheet))


def test_l12_orbit_allowed_when_cast_does_not_move():
    sheet = _ex()
    sheet["cast"][0]["end"] = copy.deepcopy(sheet["cast"][0]["start"])
    sheet["camera"].update({"mode": "move", "move": "orbit_right", "motivation": "divine presence fills the bank"})
    assert "L12" not in _codes(_lint_one(sheet))


def test_l13_shake_inside_shot_and_body_kind_only():
    sheet = _ex()
    sheet["kind"] = "body_action"
    sheet["camera"]["shake"] = {"t": 4.1, "dur": 1.0}
    assert "L13" not in _codes(_lint_one(sheet))
    sheet["camera"]["shake"] = {"t": 5.5, "dur": 1.0}
    assert "L13" in _codes(_lint_one(sheet))
    sheet["camera"]["shake"] = {"t": 4.1, "dur": 1.0}
    sheet["kind"] = "acting"
    assert "L13" in _codes(_lint_one(sheet))


def test_l14_beats_two_to_four_with_gaps_and_one_primary():
    assert "L14" not in _codes(_lint_one(_with_hook(_ex())))
    sheet = _with_hook(_ex())
    sheet["beats"] = sheet["beats"][:1]
    assert "L14" in _codes(_lint_one(sheet))
    sheet = _with_hook(_ex())
    sheet["beats"][1]["t"] = 1.0
    assert "L14" in _codes(_lint_one(sheet))
    sheet = _with_hook(_ex())
    sheet["beats"][2]["primary"] = True
    assert "L14" in _codes(_lint_one(sheet))
    sheet = _with_hook(_ex())
    sheet["beats"][2]["t"] = 6.0
    assert "L14" in _codes(_lint_one(sheet))


def test_l15_speaking_face_below_caption_line_flagged():
    sheet = _with_hook(_ex())
    sheet["cast"][0].update({"speaks": True})
    sheet["cast"][0]["start"]["mouth_moves"] = True
    sheet["cast"][0]["end"]["mouth_moves"] = True
    assert "L15" in _codes(_lint_one(sheet))
    sheet["cast"][0]["start"]["y"] = 0.60
    sheet["cast"][0]["end"]["y"] = 0.60
    assert "L15" not in _codes(_lint_one(sheet))


def test_l16_first_shot_needs_a_hook_but_later_shots_do_not():
    first = _shot("SHOT-001", 4.0, hook=None)
    assert "L16" in _codes(blocking_lint.lint([first]))
    first = _shot("SHOT-001", 4.0, hook="none")
    assert "L16" in _codes(blocking_lint.lint([first]))
    first = _shot("SHOT-001", 4.0, hook="scale_tableau")
    assert "L16" not in _codes(blocking_lint.lint([first]))
    second = _shot("SHOT-002", 9.0, hook=None)
    assert "L16" not in _codes(blocking_lint.lint([first, second]))


def test_l17_chain_needs_previous_match_and_depth_at_most_two():
    a = _shot("SHOT-001", 4.0, cut="match", hook="kinetic")
    b = _shot("SHOT-002", 9.0, cut="match", chain_from="SHOT-001")
    assert "L17" not in _codes(blocking_lint.lint([a, b]))
    a_cut = _shot("SHOT-001", 4.0, cut="cut", hook="kinetic")
    assert "L17" in _codes(blocking_lint.lint([a_cut, b]))
    wrong = _shot("SHOT-002", 9.0, chain_from="SHOT-007")
    assert "L17" in _codes(blocking_lint.lint([a, wrong]))
    c = _shot("SHOT-003", 9.0, cut="match", chain_from="SHOT-002")
    d = _shot("SHOT-004", 6.0, chain_from="SHOT-003")
    assert "L17" in _codes(blocking_lint.lint([a, b, c, d]))
    assert "L17" not in _codes(blocking_lint.lint([a, b, c]))


# ---- lint L18-L19 (P-02 anti-metronome and reel mix) -----------------------------------------

def test_l18_consecutive_shots_within_half_second_flagged():
    a = _shot("SHOT-001", 5.0, hook="kinetic")
    b = _shot("SHOT-002", 5.3)
    assert "L18" in _codes(blocking_lint.lint([a, b]))
    c = _shot("SHOT-002", 6.0)
    assert "L18" not in _codes(blocking_lint.lint([a, c]))


def test_l19_reel_of_25_s_needs_short_shot_and_centrepiece():
    ok = [_shot("SHOT-001", 4.0, hook="kinetic"), _shot("SHOT-002", 8.0), _shot("SHOT-003", 13.0)]
    assert "L19" not in _codes(blocking_lint.lint(ok))
    no_short = [_shot("SHOT-001", 5.0, hook="kinetic"), _shot("SHOT-002", 8.0), _shot("SHOT-003", 12.0)]
    assert "L19" in _codes(blocking_lint.lint(no_short))
    no_centre = [_shot("SHOT-001", 4.0, hook="kinetic"), _shot("SHOT-002", 7.5), _shot("SHOT-003", 6.0),
                 _shot("SHOT-004", 9.5)]
    assert "L19" in _codes(blocking_lint.lint(no_centre))


def test_l19_short_reel_is_exempt():
    short = [_shot("SHOT-001", 5.0, hook="kinetic"), _shot("SHOT-002", 8.0), _shot("SHOT-003", 9.0)]
    assert "L19" not in _codes(blocking_lint.lint(short))


def test_1_0_reel_gets_no_new_lint_codes():
    sheets = []
    for i, seconds in enumerate((5.0, 5.3, 12.0), start=1):
        sheet = _shot("SHOT-%03d" % i, seconds)
        sheet["schema"] = "blocking/1"
        sheet.pop("hook_type")
        sheet.pop("chain_from")
        sheets.append(sheet)
    assert blocking_lint.lint(sheets) == []
