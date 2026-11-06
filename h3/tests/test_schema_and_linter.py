import os

import pytest

from h3.compile_h3_sing8 import compile_fl2va_prompt
from h3.schema_and_linter import (lattice_n_to_frames_and_slots, lint_profile, lint_story,
                                  load_default_profile, read_png_dimensions_on_disk, resolve_keyframes,
                                  sanitize_single_line, write_minimal_valid_png)
from h3.tests.synth import A_END, A_START, B_END, B_START, _timing, codes


def _shots(story):
    return story["episodes"][0]["shots"]


def _pic(story, name):
    return os.path.join(story["episodes"][0]["asset_root"], name)


def _codes(story, **kw):
    r = lint_story(story, **kw)
    return codes(r["errors"])


def test_lattice_helper_and_sanitize():
    assert lattice_n_to_frames_and_slots(10) == (175, 52)
    assert sanitize_single_line("  a \n b\t c ") == "a b c"


def test_positive_fixture_lints_clean(story):
    assert lint_story(story) == {"errors": [], "warnings": []}


def test_reuse_missing_own_picture_is_resolved_and_REUSED(story):
    os.remove(_pic(story, B_START))
    _shots(story)[1]["fl2va_keyframes"]["reuse_upstream_b_id"] = "SYN_A"
    kf = resolve_keyframes(_shots(story)[1], _shots(story)[0], story["episodes"][0]["asset_root"])
    assert kf == {"picture_1": A_END, "picture_2": B_END, "reused": True}
    r = lint_story(story)
    assert r["errors"] == []
    assert any("KF-W1" in w for w in r["warnings"])


def test_reuse_own_picture_present_wins(story):
    _shots(story)[1]["fl2va_keyframes"]["reuse_upstream_b_id"] = "SYN_A"
    kf = resolve_keyframes(_shots(story)[1], _shots(story)[0], story["episodes"][0]["asset_root"])
    assert kf["picture_1"] == B_START and kf["reused"] is False
    assert lint_story(story) == {"errors": [], "warnings": []}


def test_reuse_id_not_previous_shot_KF05(story):
    _shots(story)[1]["fl2va_keyframes"]["reuse_upstream_b_id"] = "SYN_Z"
    assert "KF-05" in _codes(story)


def test_top_level_extra_key_allowed_only_metadata(story):
    _shots(story)[0]["metadata"] = {"note": "ok"}
    assert lint_story(story)["errors"] == []
    _shots(story)[0]["junk"] = 1
    assert "SC-01" in _codes(story)


def test_missing_top_level_key_SC01(story):
    del _shots(story)[0]["sound_plan"]
    assert "SC-01" in _codes(story)


@pytest.mark.parametrize("mutate", [
    lambda st: _shots(st)[0]["timing_and_lattice"].pop("fps"),
    lambda st: _shots(st)[0]["camera"].__setitem__("extra", 1),
    lambda st: _shots(st)[0]["motion_7_stage"]["stage_frame_spans"].pop("7_settled_end_state"),
    lambda st: _shots(st)[1]["dialogue_and_lip_lock"]["utterances"][0].pop("text"),
])
def test_block_key_set_mismatch_SC02(story, mutate):
    mutate(story)
    assert "SC-02" in _codes(story)


def test_missing_png_KF02(story):
    os.remove(_pic(story, A_END))
    assert "KF-02" in _codes(story)


def test_wrong_png_size_KF03(story):
    write_minimal_valid_png(_pic(story, A_END), 864, 1000)
    assert "KF-03" in _codes(story)


def test_not_a_png_KF03(story):
    with open(_pic(story, A_END), "wb") as f:
        f.write(b"not a png at all, just text padding here")
    assert "KF-03" in _codes(story)


def test_png_dimensions_read_from_ihdr(story):
    assert read_png_dimensions_on_disk(_pic(story, A_START)) == [864, 1536]


def test_pixel_frames_not_17n_plus_5_PF02(story):
    _shots(story)[0]["timing_and_lattice"]["pixel_frames"] = 176
    assert "PF-02" in _codes(story)


@pytest.mark.parametrize("n", [5, 21])
def test_lattice_n_out_of_range_PF01(story, n):
    pf, slots = lattice_n_to_frames_and_slots(n)
    _shots(story)[0]["timing_and_lattice"].update(lattice_n=n, pixel_frames=pf, latent_slots=slots)
    assert "PF-01" in _codes(story)


def test_stage_span_gap_MO02(story):
    _shots(story)[0]["motion_7_stage"]["stage_frame_spans"]["2_anticipation"] = [26, 49]
    assert "MO-02" in _codes(story)


def test_cadence_overlap_CD01(story):
    _shots(story)[0]["anime_timing_cadence"]["burst_window_frames"] = [79, 124]
    assert "CD-01" in _codes(story)


def test_seam_handle_out_of_range_CN04(story):
    _shots(story)[1]["timing_and_lattice"] = _timing(40, 145, 40, 30, 145)
    assert "CN-04" in _codes(story)


def test_dynamic_trim_out_outside_stage6_MO03(story):
    _shots(story)[0]["timing_and_lattice"] = _timing(0, 150, 0, 25, 0)  # tail 25 is legal, trim_out 150 is past stage 6
    assert "MO-03" in _codes(story)


def test_chained_path_mismatch_CN09(story):
    _shots(story)[2]["fl2va_keyframes"]["picture_1_path"] = A_START
    assert "CN-09" in _codes(story)


def test_state_tag_mismatch_CN07(story):
    _shots(story)[1]["continuity_and_seam_lock"]["cut_in_biomechanical_state_tag"] = "wrong_tag"
    assert "CN-07" in _codes(story)


@pytest.mark.parametrize("key, delta", [("torso_pitch_deg", 6.0), ("knee_flex_deg", 6.0), ("com_y_ratio", 0.04)])
def test_pose_jump_CN08(story, key, delta):
    _shots(story)[2]["continuity_and_seam_lock"]["cut_in_pose_vector"][key] += delta
    assert "CN-08" in _codes(story)


def test_header_mismatch_PR01(story):
    tampered = compile_fl2va_prompt(_shots(story)[1], story["registry"])["compiled_prompt"].replace("7.29-second", "7.30-second")
    assert "PR-01" in _codes(story, compiled={"SYN_B": tampered})


def test_multiline_cadence_clause_still_passes(story):
    _shots(story)[0]["anime_timing_cadence"]["cadence_clause"] = "Hold the pose quietly,\nthen a quick burst,\n\nthen settle."
    assert lint_story(story) == {"errors": [], "warnings": []}


def test_banned_style_token_PR04(story):
    _shots(story)[0]["motion_7_stage"]["1_starting_state"] += " Photorealistic lighting."
    assert "PR-04" in _codes(story)


def test_camera_phrase_mismatch_CM02(story):
    _shots(story)[0]["camera"] = {"motion_type": "Zoom In", "amplitude": "medium_omitted",
                                  "speed": "normal_omitted", "compiled_clause": "The camera pans left."}
    assert "CM-02" in _codes(story)


def test_camera_omitted_amplitude_word_present_CM04(story):
    _shots(story)[0]["camera"]["compiled_clause"] = "The camera holds a static shot with amplitude."
    assert "CM-04" in _codes(story)


def test_camera_unofficial_motion_CM01(story):
    _shots(story)[0]["camera"]["motion_type"] = "Dolly Zoom"
    assert "CM-01" in _codes(story)


def test_utterance_unknown_character_DL02(story):
    _shots(story)[1]["dialogue_and_lip_lock"]["utterances"][0]["character_id"] = "char_missing"
    assert "DL-02" in _codes(story)


def test_dialogue_flag_mismatch_DL01(story):
    _shots(story)[0]["dialogue_and_lip_lock"]["has_dialogue"] = True
    assert "DL-01" in _codes(story)


def test_chained_needs_trim_in_zero_CN02(story):
    _shots(story)[2]["timing_and_lattice"] = _timing(5, 175, 5, 0, 278)
    assert "CN-02" in _codes(story)


def test_unknown_seam_type_CN01(story):
    _shots(story)[0]["continuity_and_seam_lock"]["incoming_seam_type"] = "BOGUS"
    assert "CN-01" in _codes(story)


def test_both_dynamic_cut_bounds_CN06(story):
    _shots(story)[1]["timing_and_lattice"] = _timing(35, 145, 35, 30, 145)  # editorial 110 < 115 and handle sum 65 > 60
    assert "CN-06" in _codes(story)


def test_episode_total_TM05(story):
    story["episodes"][0]["episode_plan"]["target_editorial_frames"] = 452
    assert "TM-05" in _codes(story)


def test_master_reel_window_TM04(story):
    _shots(story)[2]["timing_and_lattice"]["master_reel_frame_window"] = [0, 175]
    assert "TM-04" in _codes(story)


def test_description_length_PR05(story):
    story["registry"]["execution_profile"]["min_imd_body_chars"] = 99999
    assert "PR-05" in _codes(story)


def test_timestamp_PR03(story):
    _shots(story)[0]["motion_7_stage"]["1_starting_state"] += " At 00:03.500 the figure moves."
    assert "PR-03" in _codes(story)


def test_second_shot_tag_PR02(story):
    _shots(story)[1]["dialogue_and_lip_lock"]["utterances"][0]["text"] = "Hold the line [Shot 2] now."
    assert "PR-02" in _codes(story)


def test_banned_negative_words_are_warnings_only(story):
    story["registry"]["style_lock"]["banned_negative_words_regex"] = r"\bumbrella\b"
    r = lint_story(story)
    assert r["errors"] == []
    assert any("PR-W1" in w for w in r["warnings"])


def test_fl2va_on_ref2va_lora_is_warning_not_error(story):
    _shots(story)[0]["fl2va_keyframes"]["mode"] = "FL2VA"
    r = lint_story(story)
    assert r["errors"] == []
    assert any("WF-W1" in w and w.startswith("SYN_A:") for w in r["warnings"])


@pytest.mark.parametrize("name", ["sing8_864x1536", "sing8_768x1344"])
def test_profile_files_load_and_divide_by_32(name):
    p = load_default_profile(name)
    w, h = p["base_resolution"]
    assert w % 32 == 0 and h % 32 == 0
    assert lint_profile(p)["errors"] == []


def test_768_profile_aspect_mismatch_is_warning():
    r = lint_profile(load_default_profile("sing8_768x1344"))
    assert any(w.startswith("PO-W2") for w in r["warnings"])


def test_profile_base_not_divisible_by_32_PO01():
    p = load_default_profile("sing8_864x1536")
    p["base_resolution"] = [850, 1536]
    assert any(e.startswith("PO-01") for e in lint_profile(p)["errors"])


def test_strict_aspect_mismatch_is_error_PO02():
    p = load_default_profile("sing8_768x1344")
    del p["aspect_strict"]
    assert any(e.startswith("PO-02") for e in lint_profile(p)["errors"])
