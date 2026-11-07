"""Round-4 regressions (triage R4-DIR): an empty model answer is retried; a non-string narration language does not crash."""
import json

import pytest

import retry_policy
import write_pack
from pack_validator import _check_voice


def test_empty_answer_from_nvidia_is_classified_as_empty(monkeypatch):
    calls = []

    def empty_answer(prompt, model):
        calls.append(1)
        return write_pack.envelope("", "stop", "nvidia", model)

    monkeypatch.setattr(write_pack, "call_nvidia", empty_answer)
    with pytest.raises(retry_policy.ModelGaveUp) as gave_up:
        write_pack.call_path("p", "nvidia", "m", "medium", False, policy=retry_policy.Policy(max_attempts=3),
                             sleep=lambda s: None)
    assert gave_up.value.kind == retry_policy.EMPTY      # a switch kind: the next model is tried, not the same one again
    assert len(calls) == 1


def test_envelope_check_classifies_empty_and_cut_off_answers():
    assert write_pack.envelope_check(write_pack.envelope("", "stop", "nvidia", "m")) == retry_policy.EMPTY
    assert write_pack.envelope_check(write_pack.envelope("", "length", "nvidia", "m")) == retry_policy.EMPTY_CUT_OFF
    assert write_pack.envelope_check(write_pack.envelope("text", "stop", "nvidia", "m")) is None


def test_list_narration_language_is_not_a_crash():
    rows = [{"id": "S1", "audio_and_dialogue_track": {"narration": {"language": ["en"], "text": "x"}}}]
    errs, warns = [], []
    _check_voice(rows, {}, {"en": "h3"}, ["en"], errs, warns)   # must not raise TypeError (unhashable list)


def test_episodes_block_that_is_not_a_list_is_a_stage_failure():
    text = "```json episodes\nnull\n```"
    with pytest.raises(ValueError, match="must be a JSON list"):
        write_pack.episodes_from(text)


def test_multilingual_narration_needs_a_narrator_voice_for_each_elevenlabs_language():
    rows = [{"id": "S1", "audio_and_dialogue_track": {"narration_by_lang": {
        "en": {"text": "Hello.", "language": "en", "time_range": [0.0, 1.0]},
        "hi": {"text": "नमस्ते।", "language": "hi", "time_range": [0.0, 1.0]}}}}]
    bible = {"voice_map": {"NARRATOR": {"en": "voice-en"}}}
    errs, warns = [], []
    _check_voice(rows, bible, {"en": "elevenlabs", "hi": "elevenlabs"}, ["en", "hi"], errs, warns)
    assert [e["code"] for e in errs] == ["VM-01"]
    assert "hi" in errs[0]["where"]


def test_staged_pack_is_validated_from_story_plan_not_from_model_envelopes(tmp_path):
    from test_pack_validator import story, valid_shots, write_pack
    from pack_validator import validate_pack
    pack = write_pack(tmp_path / "staged", valid_shots(), story_data=None)
    (pack / "story_plan.json").write_text(json.dumps(story(), ensure_ascii=False), encoding="utf-8")
    (pack / "stage_1_raw.json").write_text(write_pack_envelope("no story block here"), encoding="utf-8")
    (pack / "stage_1_validation.json").write_text("{\"errors\": []}", encoding="utf-8")
    rep = validate_pack(pack)
    assert not [e for e in rep["errors"] if str(e.get("code", "")).startswith("STORY-")], rep["errors"]


def write_pack_envelope(text):
    import write_pack as wp
    return wp.envelope(text, "stop", "nvidia", "m")


def test_bool_episode_number_is_not_an_episode():
    text = '```json story\n{"episodes": [{"episode": true}, {"episode": 2}]}\n```'
    try:
        eps = write_pack.episodes_from(text)
    except ValueError:
        return
    assert not any(isinstance(e, bool) for e in eps) and eps == [2]


def test_row_level_narration_by_lang_needs_a_narrator_voice():
    rows = [{"id": "S1", "narration_by_lang": {"hi": {"text": "नमस्ते।", "language": "hi", "time_range": [0.0, 1.0]}}}]
    errs, warns = [], []
    _check_voice(rows, {"voice_map": {"NARRATOR": {"en": "voice-en"}}}, {"hi": "elevenlabs"}, ["hi"], errs, warns)
    assert [e["code"] for e in errs] == ["VM-01"]


def test_story_block_that_is_not_an_object_does_not_crash_episodes_from():
    text = "```json story\n[1, 2, 3]\n```"
    try:
        write_pack.episodes_from(text)
    except ValueError:
        pass   # a clean stage failure is fine; an AttributeError is not


def test_stage5_wrong_types_become_empty_not_a_crash():
    shots = [{"id": "SHOT-01", "source_id": "SHOT-01", "audio_and_dialogue_track": {"dialogue": [{"speaker": "A"}]}}]
    items = [{"shot_id": "SHOT-01", "cards": 5, "dialogue_texts": 5}]
    out = write_pack.apply_captions(shots, items, ["en"])
    assert out[0]["captions"] == []
    items2 = [{"shot_id": "SHOT-01", "captions_by_lang": [1, 2], "narration_text_by_lang": [1], "dialogue_texts_by_lang": {"en": 5}}]
    write_pack.apply_captions([dict(shots[0])], items2, ["en", "hi"])
