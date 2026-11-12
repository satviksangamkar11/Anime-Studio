"""Tests for h3/v4_to_h3.py: mapping per column, the 7-stage sound-cue rule, lattice math, mouth fields,
the problems list, a lint-clean round trip, and no mutation of the input. Offline: PNG files are written to a tmp folder."""
import copy
import json
import os

import pytest

from h3 import v4_to_h3
from h3.schema_and_linter import STAGES, lint_story, write_minimal_valid_png
from h3.v4_to_h3 import convert_pack, main

SHOT_A, SHOT_B = "SHOT-001", "SHOT-002"
MOTION = "medium, slow push in"

ACTIONS = ["Raj lifts his eyes from the scroll", "Raj turns toward the door", "Raj stands, the lamp flame bends",
           "Raj steps one pace", "Raj stops, hand at the door latch", "Raj looks back at the lamp",
           "Raj opens the door a crack", "Raj pulls the shutter closed"]
CUES = ["a page rustles", "wooden hinge creaks", "cloth sleeve swish", "a soft step on stone", "latch click",
        "lamp hiss", "door creak and night insects", "shutter thud"]


def _directives(pf_sec=7.29):
    """Eight brackets: seven full seconds and a short last one that reaches the editorial end (7.29 s)."""
    out = []
    for t in range(7):
        out.append({"t0": float(t), "t1": float(t + 1), "action_pose_expression": ACTIONS[t], "camera": MOTION,
                    "spatial_position": "center-left, mid depth", "audio_cue": CUES[t],
                    "handoff_to_next_second": "eyes stay on the door"})
    out.append({"t0": 7.0, "t1": pf_sec, "action_pose_expression": ACTIONS[7], "camera": MOTION,
                "spatial_position": "center-right, mid depth", "audio_cue": CUES[7],
                "handoff_to_next_second": "light spills out"})
    return out


def _row(sid, ep, *, incoming, outgoing, h3_extra=None, in_tag="lunging_low", out_tag="lunging_low"):
    mouth = {str(s): "closed" for s in range(8)}          # 175 frames = 7.29 s -> seconds 0..7
    mouth["3"] = "open_non_verbal_breath"
    h3 = {"story_beat": f"{sid} beat", "emotional_objective": "quiet resolve", "location_id": "ENV-HALL",
          "shot_scale": "medium", "screen_direction_vector": "left_to_right", "camera_axis_side": "left",
          "horizon_line_y_ratio": 0.4, "incoming_seam_type": incoming, "outgoing_seam_type": outgoing,
          "cut_in_biomechanical_state_tag": in_tag, "cut_out_biomechanical_state_tag": out_tag,
          "cut_in_pose_vector": {"torso_pitch_deg": 8.5, "knee_flex_deg": 15.5, "com_y_ratio": 0.505},
          "cut_out_pose_vector": {"torso_pitch_deg": 8.5, "knee_flex_deg": 15.5, "com_y_ratio": 0.505},
          "props_present": ["brass lamp"], "hold_window_frames": [0, 79], "burst_window_frames": [80, 124],
          "impact_or_settle_frames": [125, 175], "cadence_clause": "Hold the pose quietly, then a quick burst, then settle."}
    h3.update(h3_extra or {})
    return {
        "id": sid, "episode": ep, "route": "Ref2VA",
        "lattice_n": 10, "pixel_frames": 175, "latent_slots": 52, "editorial_duration_sec": 7.29,
        "continuity_handoff": {"incoming": f"{sid} opens with the lamp lit.", "outgoing": f"{sid} hands the turn on.",
                               "loop_seam": None},
        "reference_anchors": {"fixed_landmarks": ["carved teak door on the left wall", "brass lamp on the low table"],
                              "character_positions": [{"id": "CHAR-RAJ", "screen": "center-left", "depth": "mid"}],
                              "exited_character_status": [],
                              "lighting_baseline": {"key": "warm lamp light from the right", "fill": "soft cool light",
                                                    "rim": "thin edge light", "shot_modifiers": "none"}},
        "hook_type": "reveal", "is_opening_0_2s_hook": sid == SHOT_A, "is_closing_hook": sid == SHOT_B,
        "deliberate_flip_marker": None,
        "per_second_directives": _directives(),
        "audio_and_dialogue_track": {
            "narration": {"text": "The lamp is lit.", "language": "en", "time_range": [0.5, 5.0]},
            "dialogue": [],
            "sfx_cues": [{"time_range": "1.2-1.6s", "sfx_key": "lamp_pop", "description": "a small pop as the flame bends"},
                         {"time_range": "3.0-3.4s", "sfx_key": "hinge", "description": "a wooden hinge creaks as the door moves"},
                         {"time_range": "5.1-5.6s", "sfx_key": "latch", "description": "a metal latch clicks shut"}],
            "performance_notes": {"text": "Narrator voice only.", "narrator_mouth_closed": True, "mouth_state": mouth}},
        "h3_fields": h3,
    }


def build_pack(root):
    """A 2-shot V4 pack: shot 1 (INTER in, static out), shot 2 (CHAINED in from shot 1, INTER out). Written to root."""
    os.makedirs(os.path.join(root, "keyframes"), exist_ok=True)
    write_minimal_valid_png(os.path.join(root, "keyframes", f"{SHOT_A}-A.png"), 864, 1536)
    write_minimal_valid_png(os.path.join(root, "keyframes", f"{SHOT_A}-B.png"), 864, 1536)
    write_minimal_valid_png(os.path.join(root, "keyframes", f"{SHOT_B}-B.png"), 864, 1536)
    shots = [_row(SHOT_A, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD"),
             _row(SHOT_B, 1, incoming="CHAINED_POSE_HOLD", outgoing="INTER_REEL_HANDSHAKE")]
    bible = {"style_lock": {"prefix": "2D hand-drawn cel-shaded anime, Indian classical Puranic proportions, organic line weight."},
             "forbidden_looks": ["3D CG", "Pixar look"],
             "characters": {"CHAR-RAJ": {"name": "Raj", "role": "protagonist"}},
             "environments": {"ENV-HALL": {"name": "Teak hall", "continuity_landmarks": ["carved teak door"],
                                           "lighting_baseline": {"key": "warm lamp light from the right"}}},
             "props": {"PROP-LAMP": {"name": "Brass lamp"}}}
    stage = {"output_languages": ["en", "hi", "mr"], "output_language": "en",
             "voice_engine": {"en": "elevenlabs", "hi": "elevenlabs", "mr": "elevenlabs"}}
    with open(os.path.join(root, "shots.json"), "w", encoding="utf-8") as f:
        json.dump(shots, f)
    with open(os.path.join(root, "bible.json"), "w", encoding="utf-8") as f:
        json.dump(bible, f)
    with open(os.path.join(root, "stage_1_story.json"), "w", encoding="utf-8") as f:
        json.dump(stage, f)
    return shots, bible, stage


@pytest.fixture
def pack(tmp_path):
    root = str(tmp_path / "pack")
    os.makedirs(root)
    build_pack(root)
    return root


def _shot(story, sid):
    return next(s for ep in story["episodes"] for s in ep["shots"] if s["shot_id"] == sid)


def _problems_for(res, sid):
    return [p for p in res["problems"] if p.startswith(sid + ":")]


# ---- round trip: a V4 pack that the H3 linter accepts ----

def test_round_trip_lints_clean(pack):
    res = convert_pack(pack)
    assert res["problems"] == []
    assert lint_story(res["story"])["errors"] == []


def test_output_languages_and_voice_engine_are_metadata_only(pack):
    story = convert_pack(pack)["story"]
    assert story["output_languages"] == ["en", "hi", "mr"] and story["output_language"] == "en"
    assert story["voice_engine"] == {"en": "elevenlabs", "hi": "elevenlabs", "mr": "elevenlabs"}
    assert story["registry"]["voice_engine"] == story["voice_engine"]   # Q-R4-4: the registry copy is what the linter and Gate D read
    from h3.schema_and_linter import voice_mode
    assert voice_mode(story["registry"]) is False        # all elevenlabs: H3 speech stays off


def test_languages_argument_overrides_stage_file(pack):
    story = convert_pack(pack, languages=["hi"])["story"]
    assert story["output_languages"] == ["hi"] and story["output_language"] == "hi"


def test_bad_languages_are_a_problem(pack):
    res = convert_pack(pack, languages=["fr"])
    assert any("output_languages" in p for p in res["problems"])


# ---- column 1: lattice and timing ----

def test_lattice_timing_from_column_one(pack):
    t = _shot(convert_pack(pack)["story"], SHOT_A)["timing_and_lattice"]
    assert (t["lattice_n"], t["pixel_frames"], t["latent_slots"]) == (10, 175, 52)
    assert t["editorial_frames"] == 175 and t["editorial_duration_sec"] == 7.29
    assert t["trim_in_frame"] == 0 and t["trim_out_frame"] == 175
    assert t["tail_handle_frames"] == 0 and t["head_handle_frames"] == 0


def test_master_reel_window_accumulates_across_shots(pack):
    story = convert_pack(pack)["story"]
    a = _shot(story, SHOT_A)["timing_and_lattice"]
    b = _shot(story, SHOT_B)["timing_and_lattice"]
    assert a["master_reel_frame_window"] == [0, 175]
    assert b["master_reel_frame_window"] == [175, 350]
    assert story["episodes"][0]["episode_plan"]["target_editorial_frames"] == 350


def test_wrong_pixel_frames_are_reported_and_lattice_wins(pack):
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    shots[0]["pixel_frames"] = 176
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert any("pixel_frames/latent_slots do not match lattice_n 10" in p for p in res["problems"])
    assert _shot(res["story"], SHOT_A)["timing_and_lattice"]["pixel_frames"] == 175


def test_bad_lattice_n_skips_the_shot_with_a_problem(pack):
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    shots[1]["lattice_n"] = 25
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert any(p.startswith(f"{SHOT_B}: lattice_n 25") for p in res["problems"])
    assert [s["shot_id"] for s in res["story"]["episodes"][0]["shots"]] == [SHOT_A]


# ---- column 2 and 3 ----

def test_continuity_text_becomes_seam_notes(pack):
    c = _shot(convert_pack(pack)["story"], SHOT_B)["continuity_and_seam_lock"]
    assert c["incoming_seam_note"] == "SHOT-002 opens with the lamp lit."
    assert c["outgoing_seam_note"] == "SHOT-002 hands the turn on."
    assert c["incoming_seam_type"] == "CHAINED_POSE_HOLD"


def test_chained_incoming_takes_picture_one_from_previous_picture_two(pack):
    story = convert_pack(pack)["story"]
    prev_b = _shot(story, SHOT_A)["fl2va_keyframes"]["picture_2_path"]
    assert _shot(story, SHOT_B)["fl2va_keyframes"]["picture_1_path"] == prev_b


def test_reference_anchors_land_in_registry_not_in_the_shot(pack):
    story = convert_pack(pack)["story"]
    row = story["registry"]["v4_rows"][SHOT_A]
    assert row["reference_anchors"]["fixed_landmarks"][0] == "carved teak door on the left wall"
    assert story["registry"]["environments"]["ENV-HALL"]["continuity_landmarks"] == ["carved teak door"]


def test_hook_fields_are_kept_under_registry(pack):
    row = convert_pack(pack)["story"]["registry"]["v4_rows"][SHOT_B]
    assert row["is_closing_hook"] is True and row["hook_type"] == "reveal"


def test_missing_boundary_frames_are_a_problem(pack):
    os.remove(os.path.join(pack, "keyframes", f"{SHOT_A}-A.png"))
    res = convert_pack(pack)
    assert any(p.startswith(f"{SHOT_A}: boundary frames missing") for p in res["problems"])


# ---- column 5: the 7 stages and the sound-cue rule ----

def test_seven_stages_are_contiguous_and_end_at_pixel_frames(pack):
    spans = _shot(convert_pack(pack)["story"], SHOT_A)["motion_7_stage"]["stage_frame_spans"]
    assert list(spans) == list(STAGES)
    expect = 0
    for k in STAGES:
        a, b = spans[k]
        assert a == expect and b >= a
        expect = b + 1
    assert spans[STAGES[-1]][1] == 175


def test_every_stage_has_an_action_and_no_duplicate(pack):
    # M-01b: was "every stage keeps a sound cue". Cues now live in overall_soundscape, not in the stages.
    m = _shot(convert_pack(pack)["story"], SHOT_A)["motion_7_stage"]
    for k in STAGES:
        assert m[k].strip(), k
    assert len({m[k] for k in STAGES}) == len(STAGES)


def test_stage_cues_are_in_soundscape_in_time_order(pack):
    # M-01b: was "stage sentence uses the cues of the seconds it covers" (cues glued into each stage).
    m = _shot(convert_pack(pack)["story"], SHOT_A)["motion_7_stage"]
    snd = _shot(convert_pack(pack)["story"], SHOT_A)["sound_plan"]["overall_soundscape"]
    assert not any("a page rustles" in m[k] for k in STAGES)
    assert snd.index("a page rustles") < snd.index("wooden hinge creaks") < snd.index("cloth sleeve swish")
    assert "door creak" in snd and "shutter thud" in snd


def test_stage_without_a_sound_word_is_not_a_problem(pack):
    # M-01b: was "stage without a sound word is a problem" (SX-01 stage check removed, SX_MIN_STAGE_CUES = 0).
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    shots[0]["per_second_directives"][0]["audio_cue"] = "the lamp glows"
    shots[0]["per_second_directives"][0]["action_pose_expression"] = "Raj smiles"
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert not any("has no sound word" in p for p in res["problems"])


def test_camera_motion_is_one_official_motion(pack):
    cam = _shot(convert_pack(pack)["story"], SHOT_A)["camera"]
    assert cam["motion_type"] == "Push In"
    assert cam["compiled_clause"] == "The camera pushes in."
    assert cam["amplitude"] == "medium_omitted" and cam["speed"] == "normal_omitted"


def test_camera_change_inside_a_shot_is_a_problem(pack):
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    shots[0]["per_second_directives"][3]["camera"] = "medium, pan left"
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert any("camera differs across seconds" in p for p in res["problems"])


def test_sound_plan_from_sfx_cues(pack):
    # M-01b: was startswith("A small pop...") and count(".") == 3 (no "First" label, 3 sentences).
    snd = _shot(convert_pack(pack)["story"], SHOT_A)["sound_plan"]
    assert snd["non_diegetic_music"] == "N/A"
    assert snd["overall_soundscape"].startswith("First a page rustles; then wooden hinge creaks; then a small pop")
    assert 1 <= snd["overall_soundscape"].count(".") <= 4


# ---- mouth fields and the speech rule ----

def test_mouth_fields_follow_performance_notes(pack):
    d = _shot(convert_pack(pack)["story"], SHOT_A)["dialogue_and_lip_lock"]
    assert d["has_dialogue"] is False and d["utterances"] == []
    assert d["narrator_mouth_closed"] is True
    assert d["mouth_state"]["3"] == "open_non_verbal_breath"
    assert len(d["mouth_state"]) == 8                # seconds 0..7 for 175 frames
    assert "non-verbal breaths" not in d["mouth_state_rule"]   # M-01b: was "...breaths at second 3" (breath exception deleted)


def test_narration_and_dialogue_never_reach_the_prompt(pack):
    story = convert_pack(pack)["story"]
    assert _shot(story, SHOT_A)["dialogue_and_lip_lock"]["utterances"] == []
    assert "The lamp is lit." not in json.dumps(_shot(story, SHOT_A))


def test_missing_mouth_state_is_a_problem(pack):
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    del shots[0]["audio_and_dialogue_track"]["performance_notes"]["mouth_state"]["7"]
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert any("no mouth_state for second 7" in p for p in res["problems"])


# ---- problems for missing data ----

def test_missing_h3_field_is_reported_not_invented(pack):
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    del shots[0]["h3_fields"]["cut_in_pose_vector"]
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert f"{SHOT_A}: h3_fields.cut_in_pose_vector missing (H3-only field, not in the V4 columns)" in res["problems"]
    assert "cut_in_pose_vector" not in _shot(res["story"], SHOT_A)["continuity_and_seam_lock"] or \
        _shot(res["story"], SHOT_A)["continuity_and_seam_lock"]["cut_in_pose_vector"] is None
    # FINDING: lint_story does not flag a None pose vector on the first shot (no check reads cut_in_pose_vector
    # without a previous shot). The converter problem list is the only report here; see HANDOFF V4H3 open questions.


def test_dynamic_seam_on_a_full_length_shot_is_a_problem(pack):
    # Changed 2026-11-07 (H3A): handles are now derived from the editorial length, not set to 0. A full-length shot
    # (editorial == pixel_frames) has no head handle to give, so a DYNAMIC incoming seam is reported with the numbers.
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    shots[0]["h3_fields"]["incoming_seam_type"] = "DYNAMIC_MATCH_ON_ACTION"
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert any(p.startswith(f"{SHOT_A}: incoming DYNAMIC head handle 0 outside 8..35") for p in res["problems"])


def test_unknown_location_is_a_problem(pack):
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    shots[1]["h3_fields"]["location_id"] = "ENV-NOPE"
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert any("ENV-NOPE" in p for p in res["problems"])


def test_row_without_episode_is_skipped_with_a_problem(pack):
    shots = json.load(open(os.path.join(pack, "shots.json"), encoding="utf-8"))
    del shots[1]["episode"]
    json.dump(shots, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = convert_pack(pack)
    assert any(p.startswith("row 2: no episode number") for p in res["problems"])


# ---- input is not changed ----

def test_input_dicts_are_not_mutated(pack):
    shots, bible, stage = build_pack(pack)           # rewrites the same files; fresh copies to compare
    before = (copy.deepcopy(shots), copy.deepcopy(bible), copy.deepcopy(stage))
    convert_pack({"shots": shots, "bible": bible, "stage": stage, "asset_root": pack})
    assert (shots, bible, stage) == before


# ---- CLI ----

def test_cli_exit_zero_on_clean_pack(pack, capsys):
    assert main([pack]) == 0
    assert "lint clean" in capsys.readouterr().out


def test_cli_writes_story_and_exit_one_with_problems(pack, tmp_path, capsys):
    out = tmp_path / "story_h3.json"
    os.remove(os.path.join(pack, "keyframes", f"{SHOT_B}-B.png"))
    assert main([pack, "--out", str(out)]) == 1
    assert out.is_file() and "PROBLEM" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))["output_languages"] == ["en", "hi", "mr"]


def test_cli_exit_two_without_a_pack(tmp_path):
    assert main([str(tmp_path)]) == 2


def test_cli_exit_two_for_bad_lang(pack):
    assert main([pack, "--lang", "fr"]) == 2
