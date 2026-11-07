"""Round-5 regressions (triage R5, h3): six defects, one test each."""
import copy

import h3.gate_d_audio as gd
import h3.render_controller as rc
from h3.schema_and_linter import lint_story
from h3.tests.test_gate_d_audio import _codes, _run, _story, _vo_root
from h3.tests.synth import build_story
from h3.voice_manifest import voice_ids_for


def test_r5_music_presence_string_levels_do_not_raise_type_error():
    voice = ["y"] + [-20.0] * 9              # a string voice level is not a speech window
    bgm = ["x"] + [-38.0] * 9                # a string BGM level is not a usable level
    rep = gd.check_music_presence(voice, bgm)
    assert rep["ok"], rep["errors"]


def test_r5_voice_ids_use_dialogue_by_lang_for_the_language():
    shot = {"audio_and_dialogue_track": {"dialogue": [], "dialogue_by_lang": {
        "hi": [{"speaker": "A", "text": "x"}, {"speaker": "B", "text": "y"}]}}}
    voice_map = {"A": {"hi": "voice_a"}, "B": {"hi": "voice_b"}}
    assert voice_ids_for(shot, "hi", voice_map)["speakers"] == {"A": "voice_a", "B": "voice_b"}


def test_r5_zero_editorial_shot_is_not_fit_checked(tmp_path):
    shots = _story()
    shots[1]["editorial_duration_sec"] = 0                 # VO wav exists for it, but there is no length to fit
    out = _run(tmp_path, ["hi"], shots=shots)
    assert "VO_OVERFLOW_ERROR" not in _codes(out["reports"]["hi"])


def test_r5_bool_pixel_frames_do_not_count_as_frames(story, tmp_path):
    st = copy.deepcopy(story)
    groups = rc.select_scope(st, "all")
    base = rc.prepare(st, groups, str(tmp_path / "a"), write=False)["totals"]["frames"]
    shot = st["episodes"][0]["shots"][0]
    orig = shot["timing_and_lattice"]["pixel_frames"]
    shot["timing_and_lattice"]["pixel_frames"] = True
    groups = rc.select_scope(st, "all")
    res = rc.prepare(st, groups, str(tmp_path / "b"), write=False)
    rows = {r["shot_id"]: r for e in res["episodes"] for r in e["rows"]}
    assert rows[shot["shot_id"]]["seconds"] is None
    assert res["totals"]["frames"] == base - orig


def test_r5_list_shot_id_is_linted_not_a_type_error(tmp_path):
    story = build_story(tmp_path)
    story["episodes"][0]["shots"][0]["shot_id"] = [1, 2]
    out = lint_story(story)                                # must not raise TypeError
    assert out["errors"], "a non-string shot_id must be reported"


def test_r5_foley_only_reel_has_no_no_vo_files_error(tmp_path):
    shots = _story()
    for s in shots:
        s["audio_and_dialogue_track"]["narration_by_lang"] = {}   # no speech in any shot, in any language
        s["audio_and_dialogue_track"]["dialogue_by_lang"] = {}
    out = _run(tmp_path, ["hi"], vo_dir=_vo_root(tmp_path, langs=()), shots=shots)
    assert "NO_VO_FILES" not in _codes(out["reports"]["hi"])
