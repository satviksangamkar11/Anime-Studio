"""Round-2 review fixes (Super VL, 2026-11-07): clean refusals instead of KeyError, one AU-01, PR-00 on workflow failure,
PO-05 for a missing style_lock, SC-02 (not SC-03) for a bad diegetic_text_events."""
import copy

import pytest

from h3.compile_h3_sing8 import compile_episode, compile_fl2va_prompt
from h3.router import workflow_mode
from h3.schema_and_linter import lint_shot, lint_story
from h3.tests.synth import SPEECH_UTTERANCE, codes


def _voice_story(story):
    story["registry"]["voice_engine"] = {"en": "h3"}  # English H3 speech on: _speech_sentences runs
    shot = story["episodes"][0]["shots"][0]
    shot["dialogue_and_lip_lock"]["utterances"] = [copy.deepcopy(SPEECH_UTTERANCE)]
    return shot


def test_speech_with_unknown_character_is_refused_cleanly(story):
    shot = _voice_story(story)
    shot["dialogue_and_lip_lock"]["utterances"][0]["character_id"] = "char_missing"
    with pytest.raises(ValueError, match="char_missing"):
        compile_fl2va_prompt(shot, story["registry"])


def test_speech_with_character_lacking_voice_anchor_is_refused_cleanly(story):
    shot = _voice_story(story)  # the synth characters carry no voice_anchor
    with pytest.raises(ValueError, match="voice_anchor"):
        compile_fl2va_prompt(shot, story["registry"])


def test_missing_style_lock_is_refused_by_compile(story):
    del story["registry"]["style_lock"]
    with pytest.raises(ValueError, match="style_lock"):
        compile_fl2va_prompt(story["episodes"][0]["shots"][0], story["registry"])


def test_lint_flags_missing_style_lock_as_po05(story):
    del story["registry"]["style_lock"]
    assert "PO-05" in codes(lint_story(story)["errors"])
    with pytest.raises(ValueError, match="PO-05"):
        compile_episode(story, "SYN_EP1", story["episodes"][0]["asset_root"])


def test_workflow_compile_failure_with_precompiled_prompt_is_recorded(story):
    shots, reg = story["episodes"][0]["shots"], story["registry"]
    prof = reg["execution_profile"]
    route_key = f"{workflow_mode('FL2VA')}_{prof['checkpoint_architecture_namespace']}"
    assert route_key in prof["mode_to_lora_map"]
    del prof["mode_to_lora_map"][route_key]  # compile_comfyui_workflow now fails with KeyError for SYN_A
    text = compile_fl2va_prompt(shots[0], reg)["compiled_prompt"]
    res = lint_story(story, compiled={"SYN_A": text})
    assert "PR-00" in codes(res["errors"])


def test_pure_foley_audio_reference_logs_au01_once(story):
    shot = copy.deepcopy(story["episodes"][0]["shots"][0])
    shot["fl2va_keyframes"]["reference_audio"] = ["char_alpha"]
    au = [m for m in lint_shot(shot, story["registry"]["execution_profile"], story["registry"],
                               story["episodes"][0]["asset_root"])["errors"] if " AU-01 " in m]
    assert len(au) == 1


def test_shot_without_shot_id_is_refused_cleanly(story):
    shot = copy.deepcopy(story["episodes"][0]["shots"][0])
    del shot["shot_id"]
    with pytest.raises(ValueError, match="shot_id"):
        compile_fl2va_prompt(shot, story["registry"])


def test_non_numeric_diegetic_text_events_is_sc02_not_sc03(story):
    shot = copy.deepcopy(story["episodes"][0]["shots"][0])
    shot["metadata"] = {"diegetic_text_events": "many"}
    found = codes(lint_shot(shot, story["registry"]["execution_profile"], story["registry"],
                            story["episodes"][0]["asset_root"])["errors"])
    assert "SC-02" in found and "SC-03" not in found
