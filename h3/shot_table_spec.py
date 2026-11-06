"""Shared constants and helpers of the H3 V4 master specification (research/OWNER_MASTER_PROMPT_V4_2026-11-07.txt).

Every module (pack_validator, writer, router/compiler, fallback policy, Gate D audio, Step 9 QC) imports its numbers from here
so they cannot disagree. Pure Python, no I/O."""
from __future__ import annotations

FPS = 24
LATTICE_N_MIN, LATTICE_N_MAX = 6, 20            # pixel_frames = 5 + 17n, latent_slots = 5n + 2  (107..345 frames = 4.46..14.38 s)
MAX_SHOT_SEC = 15.0
MAX_CHARS_PER_SHOT = 3                           # significant characters per shot (Step 5.5 check 3)
STUDIO_REEL_RANGE = (60.0, 75.0)                 # studio preset, seconds per reel
DURATION_BUCKETS = {"15-30": (15.0, 30.0), "30-60": (30.0, 60.0), "60-90": (60.0, 90.0), "90-180": (90.0, 180.0), "custom": None}
MAX_REPAIR_RETRIES = 1                           # per writer stage
PROMPT_CHAR_LIMIT = 7000                         # hard limit of an H3 prompt

HOOKS = ("visual-joke", "reversal", "suspense", "tender", "chase", "reveal", "callback", "expression-beat")
STRONG_HOOKS = ("visual-joke", "reversal", "reveal", "suspense", "tender")   # allowed for the opening and the closing shot
DENSITY_HOOKS = ("reveal", "reversal", "callback")                           # at least 1 of every 3 consecutive shots

STORY_GATE_CHECKS = ("active_protagonist", "crisis_from_flaw", "no_coincidence_resolution", "ending_reuses_emotional_anchor",
                     "non_flat_antagonistic_pressure", "dialogue_shows_relationship_change")

COLUMNS = ("shot_id_and_duration", "continuity_handoff", "reference_anchors", "hook_type", "per_second_directives", "audio_and_dialogue_track")
REFERENCE_ANCHOR_KEYS = ("fixed_landmarks", "character_positions", "exited_character_status", "lighting_baseline")
LIGHTING_KEYS = ("key", "fill", "rim", "shot_modifiers")
PER_SECOND_KEYS = ("action_pose_expression", "camera", "spatial_position", "audio_cue", "handoff_to_next_second")
AUDIO_TRACK_KEYS = ("narration", "dialogue", "sfx_cues", "performance_notes")
EXIT_RELEASE_SHOTS = 2                           # a character is released only after 2 consecutive off-stage shots

MODES = ("T2VA", "I2VA", "FL2VA", "L2VA", "Ref2VA")
REF2VA_LIMITS = {"image_refs": 9, "video_refs": 3, "audio_refs": 0}
REF2VA_SECTIONS = ("subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music")
VIDEO_SHIFT = {"keyframe": 6.0, "ref2va": 12.0}
AUDIO_SHIFT = 3.0                                # Route C sing8

SPEECH_LANGS = ("hi", "mr", "en")                # voiced by ElevenLabs outside H3 (H3 itself supports 11 other languages)
H3_NATIVE_LANGS = ("ar", "zh", "en", "fr", "de", "it", "ja", "ko", "pt", "ru", "es")

FALLBACK_RUNGS = 4
HUMAN_CHOICES = ("switch_models", "relax_requirements", "skip_with_placeholder_missing_clip", "supply_reference_video")

LOUDNESS = {"target_lufs": -14.0, "tolerance": 0.5, "loudnorm_tp": -1.8, "tp_ceiling_dbtp": -1.5, "lra": 11}
# owner 2026-11-07: bottom margin 896 px = 35% of 2560 (Meta Reels ad guidance, covers YouTube Shorts UI); top 360 = 14%; sides 160 (11%) kept
CAPTION = {"play_res": (1440, 2560), "margin_l": 160, "margin_r": 160, "margin_v": 896, "top_blocked_y": 360, "alignment": 2,
           "max_words": 6, "font": "NotoSansDevanagari-Bold.ttf"}
VO_FIT_MARGIN_SEC = 0.10
TAIL_SILENCE_MAX_SEC = 0.45
HOOK_NARRATION = {"window_sec": 15.0, "min_coverage": 0.90, "min_words": 38, "max_dead_air_sec": 0.45}


def lattice(n: int) -> dict:
    """The H3 frame lattice for n in 6..20."""
    if not isinstance(n, int) or isinstance(n, bool) or not LATTICE_N_MIN <= n <= LATTICE_N_MAX:
        raise ValueError(f"lattice n must be an int in {LATTICE_N_MIN}..{LATTICE_N_MAX}, got {n!r}")
    pf = 5 + 17 * n
    return {"n": n, "pixel_frames": pf, "latent_slots": 5 * n + 2, "seconds": round(pf / FPS, 3)}


def snap_seconds(seconds: float) -> dict:
    """The lattice entry whose duration is nearest to `seconds` (ties go to the shorter one), clamped to n in 6..20."""
    best = min(range(LATTICE_N_MIN, LATTICE_N_MAX + 1), key=lambda n: (abs(lattice(n)["seconds"] - float(seconds)), n))
    return lattice(best)
