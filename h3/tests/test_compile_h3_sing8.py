import copy
import json
import os

import pytest

from h3.compile_h3_sing8 import compile_comfyui_workflow, compile_episode, compile_fl2va_prompt
from h3.schema_and_linter import MOUTH_LOCK_PHRASE, PROMPT_RE, PromptRefused, lint_story, lint_workflow, resolve_keyframes
from h3.tests.synth import A_START, A_END, SPEECH_UTTERANCE, codes


def _ctx(story):
    shots = story["episodes"][0]["shots"]
    root = story["episodes"][0]["asset_root"]
    return shots, story["registry"], root


def _wf(story, i=0, second_pass=False):
    shots, reg, root = _ctx(story)
    prev = shots[i - 1] if i else None
    text = compile_fl2va_prompt(shots[i], reg)["compiled_prompt"]
    return compile_comfyui_workflow(shots[i], reg, text, second_pass, resolve_keyframes(shots[i], prev, root))


def test_prompt_layout_header_and_single_shot_tag(story):
    shots, reg, _ = _ctx(story)
    out = compile_fl2va_prompt(shots[0], reg)
    m = PROMPT_RE.match(out["compiled_prompt"])
    assert m, "compiled prompt must match the 4-part layout"
    assert m.group("sec") == "7.29"
    assert m.group("imd").startswith("[Shot 1] Hand-drawn anime cel animation")
    assert out["char_counts"]["total"] == len(out["compiled_prompt"])


def test_speech_is_refused_at_source_not_emitted(story):
    # Pure-Foley (2026-11-07): the old <d> dialogue block is gone; an utterance is refused with SL-04.
    shots, reg, _ = _ctx(story)
    shots[1]["dialogue_and_lip_lock"]["utterances"] = [copy.deepcopy(SPEECH_UTTERANCE)]
    with pytest.raises(PromptRefused) as e:
        compile_fl2va_prompt(shots[1], reg)
    assert e.value.code == "SL-04"


def test_speech_pattern_in_stage_text_is_refused(story):
    shots, reg, _ = _ctx(story)
    shots[0]["motion_7_stage"]["3_initiation"] += " The figure says (S1) it is time."
    with pytest.raises(PromptRefused) as e:
        compile_fl2va_prompt(shots[0], reg)
    assert e.value.code == "SL-01"


def test_mouth_lock_phrase_is_in_description_of_every_shot(story):
    shots, reg, _ = _ctx(story)
    for shot in shots:
        text = compile_fl2va_prompt(shot, reg)["compiled_prompt"]
        imd = PROMPT_RE.match(text).group("imd")
        assert MOUTH_LOCK_PHRASE in imd


def test_flow_chips_and_storyboard_tags_are_stripped_before_emission(story):
    shots, reg, _ = _ctx(story)
    shots[0]["motion_7_stage"]["2_anticipation"] += " @CHAR-01 stands in [char:hero] [scene:step] ROOM-> at 0.0-1.0s."
    out = compile_fl2va_prompt(shots[0], reg)
    assert "@CHAR" not in out["compiled_prompt"] and "[char:" not in out["compiled_prompt"]
    assert "->" not in out["compiled_prompt"] and "0.0-1.0s" not in out["compiled_prompt"]
    assert "@CHAR-01" in out["stripped_tags"] and "[char:hero]" in out["stripped_tags"]
    assert lint_story(story) == {"errors": [], "warnings": []}


def test_compile_episode_writes_prompt_and_workflow_that_lint_clean(story, tmp_path):
    out = str(tmp_path / "out")
    written = compile_episode(story, "SYN_EP1", out)
    assert len(written) == 6
    shots, reg, _ = _ctx(story)
    for shot in shots:
        d = os.path.join(out, shot["shot_id"])
        with open(os.path.join(d, "prompt.txt"), encoding="utf-8", newline="") as f:
            text = f.read()
        assert text == compile_fl2va_prompt(shot, reg)["compiled_prompt"]
        with open(os.path.join(d, "workflow.json"), encoding="utf-8") as f:
            wf = json.load(f)
        assert wf["_unverified_node_classes"] is True
        assert lint_workflow(wf, shot, reg["execution_profile"]) == {"errors": [], "warnings": []}


def test_compile_episode_shot_subset(story, tmp_path):
    written = compile_episode(story, "SYN_EP1", str(tmp_path), shot_ids=["SYN_B"])
    assert len(written) == 2 and all("SYN_B" in p for p in written)


def test_compile_episode_refuses_a_story_with_lint_errors(story, tmp_path):
    story["episodes"][0]["shots"][0]["timing_and_lattice"]["pixel_frames"] = 176
    with pytest.raises(ValueError, match="PF-02"):
        compile_episode(story, "SYN_EP1", str(tmp_path))


def test_second_pass_adds_nodes_and_still_lints(story):
    story["registry"]["execution_profile"]["upscale_resolution"] = [1440, 2560]
    wf = _wf(story, 0, second_pass=True)
    assert {"10", "11", "12", "13"} <= set(wf["nodes"])
    assert lint_workflow(wf, story["episodes"][0]["shots"][0], story["registry"]["execution_profile"])["errors"] == []


def test_second_pass_needs_upscale_resolution(story):
    with pytest.raises(ValueError, match="upscale_resolution"):
        _wf(story, 0, second_pass=True)


@pytest.mark.parametrize("mutate, code", [
    (lambda wf: wf["nodes"]["2"]["inputs"].__setitem__("strength_model", 0.8), "WF-02"),
    (lambda wf: wf["nodes"]["7"]["inputs"].__setitem__("steps", 4), "WF-05"),
    (lambda wf: wf["nodes"]["5"]["inputs"].__setitem__("width", 768), "WF-06"),
    (lambda wf: wf["nodes"]["6"]["inputs"].__setitem__("cfg", 1.5), "WF-04"),
    (lambda wf: wf["nodes"]["6"]["inputs"].__setitem__("has_negative_branch", True), "WF-04"),
    # SYN_A is a boundary-frame (FL2VA-routed) shot: its keyframe shift is 6.0, so 12.0 (the Ref2VA value) is wrong.
    (lambda wf: wf["nodes"]["3"]["inputs"].__setitem__("video_shift", 12.0), "WF-03"),
    (lambda wf: wf["nodes"].pop("9"), "WF-01"),
    (lambda wf: wf.pop("_unverified_node_classes"), "WF-08"),
])
def test_workflow_rule_violations(story, mutate, code):
    wf = _wf(story, 0)
    mutate(wf)
    res = lint_workflow(wf, story["episodes"][0]["shots"][0], story["registry"]["execution_profile"])
    assert code in codes(res["errors"])


def test_keyframes_feed_first_and_last_frame(story):
    wf = _wf(story, 0)
    assert wf["nodes"]["5"]["inputs"]["first_frame"] == A_START
    assert wf["nodes"]["5"]["inputs"]["last_frame"] == A_END
