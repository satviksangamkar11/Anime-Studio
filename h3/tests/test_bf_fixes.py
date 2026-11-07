"""Backlog-fix regressions (research/TRIAGE_R4_BF_2026-11-07.md): one test per fixed item in h3."""
import copy

import h3.render_controller as rc
import h3.schema_and_linter as sl
from h3.gate_d_audio import _lang_track, same_timing_problems
from h3.tests.synth import build_story, codes
from h3.tests.test_voice_engine import voice_story
from h3.voice_manifest import build_manifest, voice_ids_for


def _shot(sid, ed, by_lang=None, **extra):
    trk = {"narration_by_lang": by_lang} if by_lang is not None else {}
    return {"id": sid, "editorial_duration_sec": ed, "audio_and_dialogue_track": trk, **extra}


# Item 1: a language with no time_range is not compared, so no false TIME-01
def test_language_without_time_range_is_not_a_false_time01():
    shot = _shot("S1", 2.0, {"en": {"text": "Hi.", "language": "en", "time_range": [0.0, 1.0]},
                             "hi": {"text": "नमस्ते", "language": "hi"}})
    assert same_timing_problems([shot]) == []


def test_different_time_ranges_are_still_time01():
    shot = _shot("S1", 2.0, {"en": {"text": "Hi.", "time_range": [0.0, 1.0]},
                             "hi": {"text": "नमस्ते", "time_range": [0.5, 1.5]}})
    assert [e["code"] for e in same_timing_problems([shot])] == ["TIME-01"]


# Item 2: a bool editorial_frames is not counted as 1 frame in the running total
def test_bool_editorial_frames_does_not_enter_the_running_total(tmp_path, monkeypatch):
    story = build_story(tmp_path)
    story["episodes"][0]["shots"][0]["timing_and_lattice"]["editorial_frames"] = True
    seen = []
    real = sl._check_window
    monkeypatch.setattr(sl, "_check_window", lambda log, shot, running, fps: (seen.append(running), real(log, shot, running, fps)))
    sl.lint_story(story)
    assert seen[1] == 0   # shot B starts after shot A, whose bool length counts as 0 (was 1)


# Item 3: a non-object track is an error entry, never a crash or a silent skip
def test_non_object_track_is_reported_by_the_manifest(tmp_path):
    shots = [{"id": "S1", "editorial_duration_sec": 2.0, "audio_and_dialogue_track": ["not", "an", "object"]}]
    m = build_manifest(str(tmp_path), shots, ["en"])
    assert m["entries"] == []
    assert [e["code"] for e in m["fit"]["errors"]] == ["VO_BAD_TRACK"]
    assert m["fit"]["ok"] is False


def test_voice_ids_for_non_object_track_has_no_speakers():
    shot = {"id": "S1", "audio_and_dialogue_track": "text"}
    assert voice_ids_for(shot, "en", {}) == {"narrator": None, "speakers": {}}


# Item 4: non-object voice_anchor, compiled and narration_by_lang are errors, not tracebacks
def test_non_object_voice_anchor_is_va01_not_a_crash(tmp_path):
    story = voice_story(str(tmp_path))
    story["registry"]["characters"]["char_alpha"]["voice_anchor"] = "a string anchor"
    errs = sl.lint_story(story)["errors"]
    assert "VA-01" in codes(errs)


def test_non_object_compiled_map_is_an_error_entry(tmp_path):
    story = build_story(tmp_path)
    out = sl.lint_story(story, compiled=["not", "a", "map"])
    assert any("compiled must be an object" in e for e in out["errors"])


def test_non_object_narration_by_lang_is_treated_as_missing():
    trk = {"narration_by_lang": "text"}
    assert _lang_track(trk, "en") == (None, [])


def test_non_object_narration_by_lang_is_time01_in_timing_check():
    shot = _shot("S1", 2.0, "text")
    assert [e["code"] for e in same_timing_problems([shot])] == ["TIME-01"]


def test_voice_anchor_rows_in_a_copy_of_the_story_are_unchanged(tmp_path):
    # guard: the valid story still lints clean with the voice guards in place
    story = voice_story(str(tmp_path))
    assert "VA-01" not in codes(sl.lint_story(copy.deepcopy(story))["errors"])


# Item 5: _qc_result turns an AttributeError into a blocking reason
def test_qc_result_attribute_error_blocks_instead_of_raising(monkeypatch):
    def broken(shots, measurers=None):
        raise AttributeError("'str' object has no attribute 'get'")
    monkeypatch.setattr(rc, "final_qc", broken)
    res = rc._qc_result([{"episode": {"episode_id": "E1", "shots": []}}], {})
    assert res["ok"] is False
    assert "Step 9 QC not run: AttributeError" in res["reasons"][0]
