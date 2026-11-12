"""M-02 start-only (S) route, h3 side. The FL2VA golden hash was captured before M-02 and must not change.
Start-only prompts and workflows are compiled only when asked (start_only=True) or when the story shot has no picture_2."""
import copy
import hashlib
import json

import pytest

from h3 import shot_mode
from h3.compile_h3_sing8 import compile_comfyui_workflow, compile_fl2va_prompt
from h3.schema_and_linter import PROMPT_I2VA_RE, PROMPT_RE, lint_story, resolve_keyframes
from h3.tests.synth import codes

FL2VA_GOLDEN = "3b99fa5f7e803cb63d9ae772720b33fdd957e05ddce970dd93eaa78ac709a222"


def _golden_hash(story):
    ep = story["episodes"][0]
    shots, reg = ep["shots"], story["registry"]
    out = []
    for i, sh in enumerate(shots):
        prev = shots[i - 1] if i else None
        prompt = compile_fl2va_prompt(sh, reg)["compiled_prompt"]
        wf = compile_comfyui_workflow(sh, reg, prompt, False, resolve_keyframes(sh, prev, ep["asset_root"]))
        out.append([sh["shot_id"], prompt, json.dumps(wf, sort_keys=True)])
    return hashlib.sha256(json.dumps(out).encode()).hexdigest()


def test_fl2va_golden_unchanged(story):
    assert _golden_hash(story) == FL2VA_GOLDEN


def test_s_prompt_names_picture_1_only(story):
    sh = story["episodes"][0]["shots"][0]
    text = compile_fl2va_prompt(sh, story["registry"], start_only=True)["compiled_prompt"]
    assert "Picture 2" not in text
    assert "in Picture 1." in text
    assert PROMPT_I2VA_RE.match(text), "start-only prompt must match the start-only layout"
    assert not PROMPT_RE.match(text), "start-only prompt must not match the 4-part FL2VA layout"
    assert "\n\n" not in text
    assert "lips" in text  # the mouth sentence stays


def test_s_workflow_has_no_end_anchor(story):
    sh = story["episodes"][0]["shots"][0]
    reg = story["registry"]
    text = compile_fl2va_prompt(sh, reg, start_only=True)["compiled_prompt"]
    wf = compile_comfyui_workflow(sh, reg, text, start_only=True)
    node5 = wf["nodes"]["5"]["inputs"]
    assert node5["last_frame"] is None
    assert node5["first_frame"] == sh["fl2va_keyframes"]["picture_1_path"]
    prof = reg["execution_profile"]
    assert "I2VA_SINGULARITY_REF_FUSION" in prof["mode_to_lora_map"]
    assert wf["nodes"]["2"]["inputs"]["lora_name"] == prof["mode_to_lora_map"]["I2VA_SINGULARITY_REF_FUSION"]


def test_s_flag_off_refuses_s_row():   # M-32: "off" now means SHOT_MODE_S_ALLOW=0 (default is on)
    shot = {"id": "s1", "start": "a.png", "image_prompt_type": "S", "pixel_frames": 175}
    with pytest.raises(shot_mode.ShotModeError, match="SHOT_MODE_S_ALLOW"):
        shot_mode.frame_row(shot, env={"SHOT_MODE_S_ALLOW": "0"})


def test_s_row_drops_end_keys():
    shot = {"id": "s1", "start": "a.png", "end": "b.png", "image_prompt_type": "S", "pixel_frames": 175,
            "end_frame_position": 170}
    row = shot_mode.frame_row(shot, env={"SHOT_MODE_S_ALLOW": "1"})
    assert row["image_prompt_type"] == "S"
    assert "end" not in row and "end_frame_position" not in row


def test_linter_accepts_start_only_shot(story):
    st = copy.deepcopy(story)
    sh = st["episodes"][0]["shots"][0]
    sh["fl2va_keyframes"].pop("picture_2_path", None)   # route I2VA: start picture only
    found = codes(lint_story(st)["errors"])
    assert "PR-01" not in found
    assert "KF-06" not in found


S_HEADER = ("For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) "
            "is fully referenced.")


def test_s_header_is_official_i2va_line(story):
    sh = story["episodes"][0]["shots"][0]
    text = compile_fl2va_prompt(sh, story["registry"], start_only=True)["compiled_prompt"]
    assert text.split("\n")[0] == S_HEADER
    assert "How the reference pictures align" not in text


def test_s_prompt_has_no_picture_2(story):
    sh = story["episodes"][0]["shots"][0]
    text = compile_fl2va_prompt(sh, story["registry"], start_only=True)["compiled_prompt"]
    assert "Picture 2" not in text and "\n\n" not in text
    two = compile_fl2va_prompt(sh, story["registry"])["compiled_prompt"]
    assert "Picture 2" in two and two.startswith("How the reference pictures align")
