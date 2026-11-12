"""Tests for director/story_shape.py (card M-23, Opus calibration review 6.1 and 8). Written BEFORE the module.

Hand-computed values. Reel time: shot 1 starts at 0 s. Good reel durations 3.5, 6.6, 12.0, 4.5, 5.2 = 31.8 s.
Shot starts: 0.0, 3.5, 10.1, 22.1, 26.6. voice_rest is [t0, t1] in shot-relative seconds (G11 one clock).
Old packs (no premise, no arc_beat) must load: every new-field rule is a warning there, never an error.
"""
import pytest

import story_shape
import write_pack_glue
import test_write_pack_glue as twg

PREMISE = {"character": "Daksha", "goal": "stop the wedding", "obstacle": "her father's oath",
           "stakes": "her village", "payoff": "she speaks the vow"}
BEATS = ["hook", "setup", "escalation", "escalation", "payoff"]
GOOD_DURS = [3.5, 6.6, 12.0, 4.5, 5.2]
GOOD_STORY = {"premise": PREMISE, "reel_target_s": 32}


def shots(durs, beats=BEATS):
    rows = []
    for i, d in enumerate(durs):
        row = {"id": "SHOT-%03d" % (i + 1), "editorial_duration_sec": d}
        if beats is not None:
            row["arc_beat"] = beats[i]
        rows.append(row)
    return rows


def good_rows():
    rows = shots(GOOD_DURS)
    rows[0]["shape_hook_type"] = "scale_tableau"
    rows[2]["voice_rest"] = [2.0, 4.5]
    return rows


def has(lines, code):
    return any(line.startswith(code + " ") for line in lines)


def narrated(text="Daksha stands alone."):
    return {"narration_by_lang": {"en": text}}


# ---- a clean new-format reel -------------------------------------------------

def test_good_reel_has_no_errors_or_warnings():
    errors, warnings = story_shape.lint(good_rows(), GOOD_STORY)
    assert errors == []
    assert warnings == []


# ---- SHAPE-01 premise --------------------------------------------------------

def test_premise_missing_key_is_error():
    partial = {k: v for k, v in PREMISE.items() if k != "payoff"}
    errors, _ = story_shape.lint(good_rows(), {"premise": partial, "reel_target_s": 32})
    assert has(errors, "SHAPE-01")


def test_premise_blank_stakes_is_error():
    blank = dict(PREMISE, stakes="   ")
    errors, _ = story_shape.lint(good_rows(), {"premise": blank, "reel_target_s": 32})
    assert has(errors, "SHAPE-01")


def test_old_pack_without_premise_only_warns():
    errors, warnings = story_shape.lint(shots(GOOD_DURS, beats=None), {})
    assert errors == []
    assert has(warnings, "SHAPE-01")
    assert has(warnings, "SHAPE-03")


# ---- SHAPE-02 reel_target_s --------------------------------------------------

def test_target_outside_25_to_75_warns_only():
    for target in (20, 76):
        errors, warnings = story_shape.lint(good_rows(), dict(GOOD_STORY, reel_target_s=target))
        assert errors == []
        assert has(warnings, "SHAPE-02")


def test_target_on_the_bounds_does_not_warn():
    for target in (25, 75):
        errors, warnings = story_shape.lint(good_rows(), dict(GOOD_STORY, reel_target_s=target))
        assert errors == []
        assert not has(warnings, "SHAPE-02")


def test_target_not_a_number_is_error():
    errors, _ = story_shape.lint(good_rows(), dict(GOOD_STORY, reel_target_s="30"))
    assert has(errors, "SHAPE-02")


def test_target_absent_is_not_checked():
    errors, warnings = story_shape.lint(good_rows(), {"premise": PREMISE})
    assert errors == []
    assert not has(warnings, "SHAPE-02")


# ---- SHAPE-03 to SHAPE-06 arc ------------------------------------------------

def test_arc_out_of_order_is_error():
    rows = shots(GOOD_DURS, beats=["hook", "escalation", "setup", "escalation", "payoff"])
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-04")


def test_shot_one_not_hook_is_error():
    rows = shots(GOOD_DURS, beats=["setup", "hook", "escalation", "escalation", "payoff"])
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-05")


def test_missing_arc_beat_in_new_format_is_error():
    rows = good_rows()
    del rows[3]["arc_beat"]
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-03")


def test_payoff_under_5_seconds_is_error():
    errors, _ = story_shape.lint(shots([3.5, 6.6, 12.0, 6.0, 4.9]), GOOD_STORY)
    assert has(errors, "SHAPE-06")


# ---- SHAPE-07 short shot and centrepiece -------------------------------------

def test_long_reel_without_short_shot_is_error():
    errors, _ = story_shape.lint(shots([4.6, 6.6, 12.0, 4.7, 5.4]), GOOD_STORY)
    assert has(errors, "SHAPE-07")


def test_long_reel_without_centrepiece_is_error():
    errors, _ = story_shape.lint(shots([3.5, 6.6, 9.0, 4.5, 5.2]), GOOD_STORY)
    assert has(errors, "SHAPE-07")


def test_short_reel_needs_no_centrepiece():
    rows = shots([3.0, 4.0, 2.0, 3.0, 5.5])
    errors, _ = story_shape.lint(rows, {"premise": PREMISE})
    assert errors == []


# ---- SHAPE-08 anti-metronome -------------------------------------------------

def test_consecutive_similar_lengths_is_error():
    errors, _ = story_shape.lint(shots([3.5, 6.6, 6.8, 4.5, 5.2]), GOOD_STORY)
    assert has(errors, "SHAPE-08")


def test_difference_of_exactly_half_a_second_is_error():
    errors, _ = story_shape.lint(shots([3.5, 6.6, 12.0, 4.5, 5.0]), GOOD_STORY)
    assert has(errors, "SHAPE-08")


# ---- SHAPE-09 shape_hook_type ------------------------------------------------------

def test_hook_none_refused_in_narrated_reel():
    rows = good_rows()
    rows[0]["shape_hook_type"] = "none"
    rows[0]["audio_and_dialogue_track"] = narrated()
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-09")


def test_hook_none_allowed_without_narration():
    rows = good_rows()
    rows[0]["shape_hook_type"] = "none"
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert errors == []


def test_unknown_hook_type_is_error():
    rows = good_rows()
    rows[0]["shape_hook_type"] = "boom"
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-09")


# ---- SHAPE-10 voice_rest -----------------------------------------------------

def test_voice_rest_span_under_2_seconds_is_error():
    rows = good_rows()
    rows[2]["voice_rest"] = [2.0, 3.5]
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-10")


def test_voice_rest_past_its_shot_end_is_error():
    rows = good_rows()
    rows[2]["voice_rest"] = [10.0, 13.0]
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-10")


def test_voice_rest_bad_shape_is_error():
    rows = good_rows()
    rows[2]["voice_rest"] = [12.0]
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-10")


# ---- old packs still load ----------------------------------------------------

def test_old_pack_ten_even_shots_loads_with_warnings_only():
    errors, warnings = story_shape.lint(shots([3.0] * 10, beats=None), None)
    assert errors == []
    assert has(warnings, "SHAPE-08")
    assert has(warnings, "SHAPE-07")


# ---- writer_gate wiring (write_pack_glue) -------------------------------------

def test_writer_gate_old_pack_gets_no_shape_problems(tmp_path):
    # The overall verdict is not checked here: the fixture already fails script_inspect's hook rules at HEAD
    # (pre-existing, unrelated to M-23). Only the shape wiring is checked: old packs add warnings, never problems.
    rows = [twg._good_row(1), twg._good_row(2)]
    twg._write_pack(tmp_path, rows)
    result = write_pack_glue.writer_gate(tmp_path, rows, twg.SOURCE, story={})
    assert not any(p.startswith("SHAPE-") for p in result["problems"])
    assert isinstance(result["warnings"], list)
    assert any(w.startswith("SHAPE-01") for w in result["warnings"])


def test_writer_gate_bad_premise_blocks(tmp_path):
    rows = [twg._good_row(1), twg._good_row(2)]
    twg._write_pack(tmp_path, rows)
    result = write_pack_glue.writer_gate(tmp_path, rows, twg.SOURCE, story={"premise": {"character": "Daksha"}})
    assert result["ok"] is False
    assert has(result["problems"], "SHAPE-01")


def test_voice_rest_span_over_4_seconds_is_error():
    rows = good_rows()
    rows[2]["voice_rest"] = [2.0, 6.1]
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-10")


# ---- one field name: shape_hook_type (pattern) vs hook_type (H3 word) --------

def test_h3_hook_type_word_is_not_a_shape_hook():
    rows = good_rows()
    rows[1]["hook_type"] = "reveal"
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert errors == []


def test_shape_hook_falls_back_to_the_blocking_sheet_hook_type():
    rows = good_rows()
    rows[0].pop("shape_hook_type")
    rows[0]["blocking"] = {"hook_type": "boom"}
    errors, _ = story_shape.lint(rows, GOOD_STORY)
    assert has(errors, "SHAPE-09")
    rows[0]["blocking"] = {"hook_type": "kinetic"}
    assert story_shape.lint(rows, GOOD_STORY)[0] == []


def test_blocking_hook_none_on_shot_1_of_a_narrated_reel_is_refused():
    rows = good_rows()
    rows[0].pop("shape_hook_type")
    rows[0]["blocking"] = {"hook_type": "none"}
    rows[0]["audio_and_dialogue_track"] = narrated()
    assert has(story_shape.lint(rows, GOOD_STORY)[0], "SHAPE-09")


def test_writer_gate_passes_a_v24_pack_with_h3_hook_and_shape_hook(tmp_path):
    rows = [twg._good_row(1), twg._good_row(2)]
    rows[0].update({"arc_beat": "hook", "hook_type": "reveal", "shape_hook_type": "kinetic", "voice_rest": None})
    rows[1].update({"arc_beat": "payoff", "hook_type": "callback", "voice_rest": [1.0, 3.0],
                    "editorial_duration_sec": 6.0})
    rows[1]["blocking"]["writer_seconds"] = 6.0
    twg._write_pack(tmp_path, rows)
    result = write_pack_glue.writer_gate(tmp_path, rows, twg.SOURCE, story={"premise": PREMISE, "reel_target_s": 10})
    assert not any(p.startswith("SHAPE-09") for p in result["problems"])
    assert not any("voice_rest" in p for p in result["problems"])
    rows[0]["shape_hook_type"] = "reveal"          # an H3 word in the shape field must still be caught
    bad = write_pack_glue.writer_gate(tmp_path, rows, twg.SOURCE, story={"premise": PREMISE, "reel_target_s": 10})
    assert any(p.startswith("SHAPE-09") for p in bad["problems"])
