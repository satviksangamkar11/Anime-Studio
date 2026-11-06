"""5-mode router, Ref2VA limits and 6-section compile, strip_tags, and the ComfyUI shift parameters (offline)."""
import pytest

from h3.compile_h3_sing8 import compile_comfyui_workflow, compile_fl2va_prompt
from h3.router import REF2VA, ref2va_limit_problems, ref2va_limits_ok, route_shot, video_shift_for, workflow_mode
from h3.schema_and_linter import REF2VA_RE, lint_profile, lint_story, lint_workflow, load_default_profile, \
    resolve_keyframes, strip_tags
from h3.shot_table_spec import AUDIO_SHIFT, VIDEO_SHIFT
from h3.tests.synth import A_END, A_START, B_START, codes, ref2va_story

SECTIONS = ["subject_definitions", "summary", "retention_analysis", "detailed_description",
            "overall_soundscape", "non_diegetic_music"]


def _ref_shot(images=1, videos=0, audio=None):
    k = {"mode": "REF2VA", "dimensions_verified": [864, 1536], "reference_images": [f"r{i}.png" for i in range(images)],
         "reference_videos": [f"v{i}.mp4" for i in range(videos)]}
    if audio is not None:
        k["reference_audio"] = audio
    return {"fl2va_keyframes": k}


# ---------- router table ----------

@pytest.mark.parametrize("kf, expected", [
    ({}, "T2VA"),
    ({"picture_1_path": "a.png"}, "I2VA"),
    ({"picture_2_path": "b.png"}, "L2VA"),
    ({"picture_1_path": "a.png", "picture_2_path": "b.png"}, "FL2VA"),
    ({"reference_images": ["r.png"]}, REF2VA),
    ({"picture_1_path": "a.png", "reference_images": ["r.png"]}, REF2VA),
    ({"picture_1_path": "a.png", "picture_2_path": "b.png", "reference_images": ["r.png"]}, "FL2VA"),
])
def test_route_table(kf, expected):
    assert route_shot({"fl2va_keyframes": {"mode": "FL2VA", **kf}}) == expected


def test_synth_boundary_shots_route_fl2va_and_ref_story_routes_shot_a(tmp_path):
    story = ref2va_story(str(tmp_path))
    assert [route_shot(s) for s in story["episodes"][0]["shots"]] == [REF2VA, "FL2VA", "FL2VA"]


# ---------- Ref2VA limits ----------

@pytest.mark.parametrize("images, videos, code", [(9, 3, None), (10, 0, "RF-01"), (1, 4, "RF-02")])
def test_ref2va_limits(images, videos, code):
    shot = _ref_shot(images, videos)
    got = {c for c, _ in ref2va_limit_problems(shot)}
    assert got == (set() if code is None else {code})
    assert ref2va_limits_ok(shot) is (code is None)


def test_ref2va_refuses_any_audio_ref():
    shot = _ref_shot(1, audio=["voice.wav"])
    assert {c for c, _ in ref2va_limit_problems(shot)} == {"AU-01"}


def test_audio_tag_in_ref2va_text_is_refused_by_lint(tmp_path):
    story = ref2va_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["motion_7_stage"]["4_drive"] += " A voice from <Audio 1> leads the turn."
    assert "AU-01" in codes(lint_story(story)["errors"])


# ---------- Ref2VA 6-section compile ----------

def test_ref2va_prompt_has_six_official_sections_in_order(tmp_path):
    story = ref2va_story(str(tmp_path))
    shot, reg = story["episodes"][0]["shots"][0], story["registry"]
    text = compile_fl2va_prompt(shot, reg)["compiled_prompt"]
    assert [line.split(":", 1)[0] for line in text.split("\n")] == SECTIONS
    m = REF2VA_RE.match(text)
    assert m, "Ref2VA prompt must match the 6-section layout"
    assert text.endswith("non_diegetic_music: N/A")
    assert "<Subject 1>" in m.group("subj") and "<Picture 1>" in m.group("subj")
    assert "<Picture 1>, <Picture 2>, <Picture 3>" in m.group("ret")
    assert "<Audio" not in text and "<Video" not in text  # no video refs in this shot


def test_ref2va_story_lints_clean(tmp_path):
    assert lint_story(ref2va_story(str(tmp_path))) == {"errors": [], "warnings": []}


def test_ref2va_label_without_reference_is_RF03(tmp_path):
    story = ref2va_story(str(tmp_path))
    shot, reg = story["episodes"][0]["shots"][0], story["registry"]
    tampered = compile_fl2va_prompt(shot, reg)["compiled_prompt"].replace("<Picture 1>", "<Picture 7>", 1)
    assert "RF-03" in codes(lint_story(story, compiled={"SYN_A": tampered})["errors"])


def test_ref2va_workflow_uses_ref_lora_and_12_shift(tmp_path):
    story = ref2va_story(str(tmp_path))
    shot, reg, root = story["episodes"][0]["shots"][0], story["registry"], story["episodes"][0]["asset_root"]
    prof = reg["execution_profile"]
    text = compile_fl2va_prompt(shot, reg)["compiled_prompt"]
    wf = compile_comfyui_workflow(shot, reg, text, False, resolve_keyframes(shot, None, root))
    assert wf["nodes"]["3"]["inputs"]["video_shift"] == 12.0
    assert wf["nodes"]["2"]["inputs"]["lora_name"] == prof["mode_to_lora_map"]["REF2VA_SINGULARITY_REF_FUSION"]
    assert wf["nodes"]["5"]["inputs"]["reference_images"] == [A_START, A_END, B_START]
    assert lint_workflow(wf, shot, prof) == {"errors": [], "warnings": []}


# ---------- strip_tags ----------

@pytest.mark.parametrize("raw, gone", [
    ("@CHAR-01 walks", "@CHAR-01"), ("@SHEET-hero sheet", "@SHEET-hero"), ("ENV-lane is wet", "ENV-lane"),
    ("@STYLE-ink lines", "@STYLE-ink"), ("[char:hero] nods", "[char:hero]"), ("[scene:lane] opens", "[scene:lane]"),
    ("[shot:3] cut", "[shot:3]"), ("[dur:5s] hold", "[dur:5s]"), ("[hook:reveal] start", "[hook:reveal]"),
    ("┌──┐ panel", "┌"), ("the door -> opens", "->"), ("a cut at 0.0-1.0s", "0.0-1.0s"),
])
def test_strip_tags_removes_each_kind(raw, gone):
    clean, removed = strip_tags(raw)
    assert gone not in clean
    assert any(gone in r for r in removed)


def test_strip_tags_keeps_shot_tag_header_and_plain_text():
    text = "[Shot 1] Hand-drawn, aligns with the 7.29-second mark and the 0.00-second mark."
    assert strip_tags(text) == (text, [])


# ---------- shift parameters ----------

def test_shipped_profiles_carry_the_contract_shifts():
    for name in ("sing8_864x1536", "sing8_768x1344"):
        prof = load_default_profile(name)
        assert prof["model_sampling_av"]["video_shift"] == VIDEO_SHIFT
        assert prof["model_sampling_av"]["audio_shift"] == AUDIO_SHIFT
        assert lint_profile(prof)["errors"] == []


def test_video_shift_for_routes():
    prof = load_default_profile("sing8_864x1536")
    assert video_shift_for(prof, "FL2VA") == 6.0
    assert video_shift_for(prof, REF2VA) == 12.0
    assert workflow_mode(REF2VA) == "REF2VA" and workflow_mode("FL2VA") == "FL2VA"


def test_shifts_are_configurable_and_wired_into_the_workflow(tmp_path):
    story = ref2va_story(str(tmp_path))
    prof = story["registry"]["execution_profile"]
    prof["model_sampling_av"]["video_shift"] = {"keyframe": 5.5, "ref2va": 10.5}
    prof["model_sampling_av"]["audio_shift"] = 2.5
    shot, reg = story["episodes"][0]["shots"][1], story["registry"]
    wf = compile_comfyui_workflow(shot, reg, compile_fl2va_prompt(shot, reg)["compiled_prompt"])
    assert wf["nodes"]["3"]["inputs"] == {"model": ["2", 0], "video_shift": 5.5, "audio_shift": 2.5}
    ref_shot = story["episodes"][0]["shots"][0]
    wf_ref = compile_comfyui_workflow(ref_shot, reg, compile_fl2va_prompt(ref_shot, reg)["compiled_prompt"])
    assert wf_ref["nodes"]["3"]["inputs"]["video_shift"] == 10.5
    assert lint_workflow(wf, shot, prof) == {"errors": [], "warnings": []}


def test_missing_shift_parameter_is_PO04():
    prof = load_default_profile("sing8_864x1536")
    del prof["model_sampling_av"]["video_shift"]
    assert any(e.startswith("PO-04") for e in lint_profile(prof)["errors"])
