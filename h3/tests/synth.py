"""Synthetic 3-shot story (made-up content, n=10, 175 frames) that passes every rule. Used by all h3 tests."""
import copy
import os
import re

from h3.schema_and_linter import STAGES, load_default_profile, write_minimal_valid_png

A_START, A_END = "syn_a_start.png", "syn_a_end.png"
B_START, B_END = "syn_b_start.png", "syn_b_end.png"
C_END = "syn_c_end.png"
PNGS = (A_START, A_END, B_START, B_END, C_END)
SHOT_IDS = ("SYN_A", "SYN_B", "SYN_C")
MSG_RE = re.compile(r"^(SYN_[ABC]|<shot \d+>): ([A-Z]{2,3}-[A-Z0-9]+) ")  # 3-letter codes such as LEN-01

STAGE_TEXT = {
    "1_starting_state": "The figure stands still on the rain-washed step, weight even on both feet, cloak hanging straight down with a faint rustle.",
    "2_anticipation": "A small breath lifts the shoulders, the head tilts a fraction, and the grip on the umbrella tightens.",
    "3_initiation": "The body shifts its weight forward onto the front foot while the eyes lock on the far end of the lane with a soft step.",
    "4_drive": "The torso leans into the motion, the arm swings wide with a whoosh, and the cloak begins to trail behind the figure.",
    "5_contact_approach": "The foot strikes the wet stone, sending a thin spray outward as the figure closes the last gap.",
    "6_impact_result": "The stance snaps into a low lunge, the umbrella drops away, and water scatters in a clean ring.",
    "7_settled_end_state": "The figure rises slowly into a steady upright pose, breathing calm with a quiet hum, eyes fixed on the lit doorway.",
}
SPANS = {"1_starting_state": [0, 24], "2_anticipation": [25, 49], "3_initiation": [50, 74],
         "4_drive": [75, 99], "5_contact_approach": [100, 124], "6_impact_result": [125, 149],
         "7_settled_end_state": [150, 175]}
CADENCE = {"hold_window_frames": [0, 79], "burst_window_frames": [80, 124],
           "impact_or_settle_frames": [125, 175],
           "cadence_clause": "Hold the pose quietly, then a quick burst of ink strokes, then settle on the final beat."}
STYLE = {"mandatory_prefix": "Hand-drawn anime cel animation, flat colour, clean ink lines, one continuous take",
         "banned_style_tokens": ["photorealistic", "3d render"]}
CHARACTERS = {"char_alpha": {"short_disambiguator": "the tall figure in a grey cloak"},
              "char_beta": {"short_disambiguator": "the young figure in a red scarf"}}


def _sec(frames):
    return round(frames / 24, 2)


def _timing(ti, to, head, tail, start, n=10, pf=175):
    ed = to - ti
    return {"lattice_n": n, "pixel_frames": pf, "latent_slots": 5 * n + 2,
            "generation_duration_sec": _sec(pf), "exact_generation_duration_sec": _sec(pf),
            "prompt_alignment_sec_str": f"{pf / 24:.2f}", "fps": 24, "trim_in_frame": ti,
            "trim_out_frame": to, "head_handle_frames": head, "tail_handle_frames": tail,
            "trim_in_sec": _sec(ti), "trim_out_sec": _sec(to), "head_handle_sec": _sec(head),
            "tail_handle_sec": _sec(tail), "editorial_frames": ed, "editorial_duration_sec": _sec(ed),
            "master_reel_frame_window": [start, start + ed], "master_reel_window_sec": [_sec(start), _sec(start + ed)]}


def _pose(torso, knee, com):
    return {"torso_pitch_deg": torso, "knee_flex_deg": knee, "com_y_ratio": com}


def _motion():
    return {**STAGE_TEXT, "stage_frame_spans": copy.deepcopy(SPANS)}


def _shot(sid, seq, timing, cont, kf, camera, dialogue):
    import math
    dialogue = {**dialogue, "narrator_mouth_closed": True,
                "mouth_state": {str(i): "closed" for i in range(math.ceil(timing["pixel_frames"] / 24))}}
    return {"shot_id": sid, "episode_id": "SYN_EP1", "sequence_order": seq,
            "story_beat": f"Synthetic beat {seq}.", "emotional_objective": "Quiet resolve.",
            "mute_animatic_verification": False, "timing_and_lattice": timing,
            "continuity_and_seam_lock": cont, "fl2va_keyframes": kf, "motion_7_stage": _motion(),
            "anime_timing_cadence": copy.deepcopy(CADENCE), "camera": camera,
            "dialogue_and_lip_lock": dialogue,
            "sound_plan": {"overall_soundscape": "Rain on wet stone, a distant bell ringing, soft wind through the leaves.",
                           "non_diegetic_music": "N/A"}}


def _cont(inc, inc_note, out, out_note, tag_in, pose_in, tag_out, pose_out, scale="medium"):
    return {"location_id": "loc_step", "shot_scale": scale, "subjects_present": ["char_alpha"],
            "props_present": ["umbrella"], "screen_direction_vector": "left_to_right",
            "camera_axis_side": "left", "horizon_line_y_ratio": 0.4,
            "incoming_seam_type": inc, "incoming_seam_note": inc_note,
            "cut_in_biomechanical_state_tag": tag_in, "cut_in_pose_vector": pose_in,
            "outgoing_seam_type": out, "outgoing_seam_note": out_note,
            "cut_out_biomechanical_state_tag": tag_out, "cut_out_pose_vector": pose_out}


def _kf(p1, p2, **extra):
    return {"mode": "REF2VA", "picture_1_path": p1, "picture_2_path": p2,
            "dimensions_verified": [864, 1536], **extra}


NO_DIALOGUE = {"has_dialogue": False, "utterances": [], "mouth_state_rule": "Mouths stay closed for the whole shot."}
# Pure-Foley: no speech in any shot. This utterance is only injected by tests that prove the speech refusal.
SPEECH_UTTERANCE = {"speaker_id": "spk_01", "character_id": "char_alpha", "is_offscreen_voiceover": True,
                    "voiceover_action_cue": "the figure's jaw tightens", "language": "en",
                    "text": "Hold the line until the bell.", "start_sec": 0.5, "end_sec": 3.0,
                    "lip_lock_clause": "lips stay closed while the off-screen voice speaks"}


def build_story(root):
    """Writes the PNGs under root/pics and returns a story dict. Shots A (inter-reel in, dynamic out),
    B (dynamic in, dynamic out, both-dynamic cut bounds), C (chained in from B, inter-reel out)."""
    pics = os.path.join(root, "pics")
    os.makedirs(pics, exist_ok=True)
    for name in PNGS:
        write_minimal_valid_png(os.path.join(pics, name), 864, 1536)
    a = _shot("SYN_A", 1, _timing(0, 145, 0, 30, 0),
              _cont("INTER_REEL_HANDSHAKE", "Handshake from the reel opening.", "DYNAMIC_MATCH_ON_ACTION",
                    "Action cut on the lean.", "still_on_step", _pose(2.0, 10.0, 0.50),
                    "leaning_forward", _pose(12.0, 22.0, 0.55)),
              _kf(A_START, A_END),
              {"motion_type": "Static Shot", "amplitude": "medium_omitted", "speed": "normal_omitted",
               "compiled_clause": "The camera holds a static shot."}, copy.deepcopy(NO_DIALOGUE))
    b_dialogue = {"has_dialogue": False, "utterances": [],
                  "mouth_state_rule": "Mouths stay closed while the off-screen figure keeps silent."}
    b = _shot("SYN_B", 2, _timing(12, 145, 12, 30, 145),
              _cont("DYNAMIC_MATCH_ON_ACTION", "Dynamic match from the lean.", "DYNAMIC_MATCH_ON_ACTION",
                    "Dynamic cut on the lunge.", "leaning_forward", _pose(12.5, 21.0, 0.56),
                    "lunging_low", _pose(8.0, 15.0, 0.50)),
              _kf(B_START, B_END),
              {"motion_type": "Push In", "amplitude": "with small amplitude", "speed": "at slow speed",
               "compiled_clause": "The camera pushes in with small amplitude at slow speed."}, b_dialogue)
    c_dialogue = {"has_dialogue": False, "utterances": [],
                  "mouth_state_rule": "The figure's mouth stays closed while the figure turns toward the light."}
    c = _shot("SYN_C", 3, _timing(0, 175, 0, 0, 278),
              _cont("CHAINED_POSE_HOLD", "Chained from the lunge.", "INTER_REEL_HANDSHAKE",
                    "Handshake into the next reel.", "lunging_low", _pose(8.5, 15.5, 0.505),
                    "settled_upright", _pose(3.0, 11.0, 0.52), scale="wide"),
              _kf(B_END, C_END),
              {"motion_type": "Tracking Shot", "amplitude": "with large amplitude", "speed": "at fast speed",
               "compiled_clause": "The camera tracks the figure with large amplitude at fast speed."}, c_dialogue)
    return {"registry": {"execution_profile": load_default_profile("sing8_864x1536"),
                         "style_lock": copy.deepcopy(STYLE), "characters": copy.deepcopy(CHARACTERS)},
            "episodes": [{"episode_id": "SYN_EP1", "asset_root": pics, "shots": [a, b, c],
                          "episode_plan": {"target_editorial_frames": 453}}]}


def ref2va_story(root):
    """build_story with shot A re-routed to Ref2VA: three reference cards and no boundary frames."""
    story = build_story(root)
    story["episodes"][0]["shots"][0]["fl2va_keyframes"] = {
        "mode": "REF2VA", "dimensions_verified": [864, 1536], "reference_images": [A_START, A_END, B_START]}
    return story


def codes(messages):
    """Set of rule codes; asserts every message starts with a shot id as required."""
    out = set()
    for m in messages:
        hit = MSG_RE.match(m)
        assert hit, f"message does not start with shot id and code: {m!r}"
        out.add(hit.group(2))
    return out
