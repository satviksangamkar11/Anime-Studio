"""Shot schema, rule linter and PNG helpers for the h3 sing8 route. Story-agnostic.

Every error/warning string is "<shot_id>: <CODE> <message>" so tests can assert on codes.
"""
import json
import math
import os
import re
import struct
import zlib

from h3.router import REF2VA, ref2va_limit_problems, ref_inventory, route_shot, video_shift_for, workflow_mode
from h3.voice_engine import audio_ref_problems
from h3.shot_table_spec import PROMPT_CHAR_LIMIT

STAGES = ("1_starting_state", "2_anticipation", "3_initiation", "4_drive",
          "5_contact_approach", "6_impact_result", "7_settled_end_state")
CHAINED, INTER, DYN = "CHAINED_POSE_HOLD", "INTER_REEL_HANDSHAKE", "DYNAMIC_MATCH_ON_ACTION"
STATIC_SEAMS = {CHAINED, INTER}
SEAM_TYPES = STATIC_SEAMS | {DYN}
LATTICE_CUT_BOUNDS = {6: ((45, 75), (32, 62)), 7: ((64, 92), (32, 60)),
                      8: ((81, 109), (32, 60)), 10: ((115, 143), (32, 60))}
OFFICIAL_CAMERA_MOTION_PHRASES = {
    "Zoom In": ("zooms in",), "Zoom Out": ("zooms out",), "Push In": ("pushes in",),
    "Pull Out": ("pulls out", "pulls back"), "Pan Left": ("pans left",), "Pan Right": ("pans right",),
    "Truck Left": ("trucks left",), "Truck Right": ("trucks right",),
    "Tilt Up": ("tilts up",), "Tilt Down": ("tilts down",),
    "Pedestal Up": ("pedestals up", "rises slowly"), "Pedestal Down": ("pedestals down", "descends slowly"),
    "Arc Shot": ("arcs", "moves in an arc", "circles"), "Tracking Shot": ("tracks",),
    "Static Shot": ("holds a static shot", "remains static", "stays locked"),
    "Shake Slightly": ("shakes slightly", "drifts very slightly"), "Shake Strongly": ("shakes strongly",),
    "POV": ("point of view", "pov"), "Roll Clockwise": ("rolls clockwise",),
    "Roll Counterclockwise": ("rolls counterclockwise",)}
# M-03: blocking camera.move enum -> (official motion_type, sentence start). One sentence per shot (Opus section 6.2).
CAMERA_MOVE_CLAUSES = {
    None: ("Static Shot", "The camera stays locked"), "locked": ("Static Shot", "The camera stays locked"),
    "push_in": ("Push In", "The camera pushes in slowly"), "pull_back": ("Pull Out", "The camera pulls back slowly"),
    "pan_left": ("Pan Left", "The camera pans left slowly"), "pan_right": ("Pan Right", "The camera pans right slowly"),
    "tilt_up": ("Tilt Up", "The camera tilts up slowly"), "tilt_down": ("Tilt Down", "The camera tilts down slowly"),
    "track_left": ("Tracking Shot", "The camera tracks left slowly"),
    "track_right": ("Tracking Shot", "The camera tracks right slowly"),
    "orbit_left": ("Arc Shot", "The camera circles slowly left around the subjects"),
    "orbit_right": ("Arc Shot", "The camera circles slowly right around the subjects"),
    "crane_up": ("Pedestal Up", "The camera rises slowly above the scene"),
    "crane_down": ("Pedestal Down", "The camera descends slowly over the scene"),
    "handheld_drift": ("Shake Slightly", "The camera drifts very slightly, as if held by hand")}
AMPLITUDES = {"with small amplitude", "with large amplitude"}
SPEEDS = {"at slow speed", "at fast speed"}
SEC_FRAMES = {"generation_duration_sec": "pixel_frames", "exact_generation_duration_sec": "pixel_frames",
              "trim_in_sec": "trim_in_frame", "trim_out_sec": "trim_out_frame",
              "head_handle_sec": "head_handle_frames", "tail_handle_sec": "tail_handle_frames",
              "editorial_duration_sec": "editorial_frames"}
SHOT_KEYS = {"shot_id", "episode_id", "sequence_order", "story_beat", "emotional_objective",
             "mute_animatic_verification", "timing_and_lattice", "continuity_and_seam_lock",
             "fl2va_keyframes", "motion_7_stage", "anime_timing_cadence", "camera",
             "dialogue_and_lip_lock", "sound_plan"}
TIMING_KEYS = {"lattice_n", "pixel_frames", "latent_slots", "generation_duration_sec",
               "exact_generation_duration_sec", "prompt_alignment_sec_str", "fps", "trim_in_frame",
               "trim_out_frame", "head_handle_frames", "tail_handle_frames", "trim_in_sec",
               "trim_out_sec", "head_handle_sec", "tail_handle_sec", "editorial_frames",
               "editorial_duration_sec", "master_reel_frame_window", "master_reel_window_sec"}
CONT_KEYS = {"location_id", "shot_scale", "subjects_present", "props_present",
             "screen_direction_vector", "camera_axis_side", "horizon_line_y_ratio",
             "incoming_seam_type", "incoming_seam_note", "cut_in_biomechanical_state_tag",
             "cut_in_pose_vector", "outgoing_seam_type", "outgoing_seam_note",
             "cut_out_biomechanical_state_tag", "cut_out_pose_vector"}
POSE_KEYS = {"torso_pitch_deg", "knee_flex_deg", "com_y_ratio"}
CADENCE_KEYS = {"hold_window_frames", "burst_window_frames", "impact_or_settle_frames", "cadence_clause"}
CAMERA_KEYS = {"motion_type", "amplitude", "speed", "compiled_clause"}
DIALOGUE_KEYS = {"has_dialogue", "utterances", "mouth_state_rule"}
UTTERANCE_KEYS = {"speaker_id", "character_id", "is_offscreen_voiceover", "voiceover_action_cue",
                  "language", "text", "start_sec", "end_sec", "lip_lock_clause"}
SOUND_KEYS = {"overall_soundscape", "non_diegetic_music"}
BLOCKS = {  # block -> (required keys, optional keys)
    "timing_and_lattice": (TIMING_KEYS, set()),
    "continuity_and_seam_lock": (CONT_KEYS, set()),
    "fl2va_keyframes": ({"mode", "dimensions_verified"},
                        {"picture_1_path", "picture_2_path", "flow_source_a", "flow_source_b", "reuse_upstream_b_id",
                         "reference_images", "reference_videos", "reference_audio"}),  # KF-06: boundary or refs
    "motion_7_stage": (set(STAGES) | {"stage_frame_spans"}, set()),
    "anime_timing_cadence": (CADENCE_KEYS, set()),
    "camera": (CAMERA_KEYS, set()),
    "dialogue_and_lip_lock": (DIALOGUE_KEYS, {"narrator_mouth_closed", "mouth_state"}),  # pure-Foley: MO-01
    "sound_plan": (SOUND_KEYS, set()),
}
PROFILE_KEYS = {"route_id", "checkpoint_name", "mode_to_lora_map", "checkpoint_architecture_namespace",
                "runtime_lora_strength", "steps_nfe", "cfg", "sampler_name", "scheduler",
                "model_sampling_av", "fps", "aspect_ratio", "base_resolution",
                "ref_image_size_policy", "min_imd_body_chars", "max_imd_body_chars",
                "max_total_prompt_chars", "valid_lattice_n_range"}
PROMPT_RE = re.compile(
    r"""\AHow the reference pictures align with the target video — Picture 1 \(from Shot 1\) aligns with the 0\.00-second mark of the target video; Picture 2 \(from Shot 1\) aligns with the (?P<sec>\d+\.\d{2})-second mark of the target video\.\nintegrated_multimodal_description: (?P<imd>[^\n]+)\noverall_soundscape: (?P<snd>[^\n]*)\nnon_diegetic_music: (?P<music>[^\n]*)\Z""")
PROMPT_I2VA_RE = re.compile(   # start-only (M-02): one picture, no end-anchor sentence
    r"""\AFor the target video, at 0\.00 seconds into the target video, <Picture 1> \(from \[Shot 1\]\) is fully referenced\.\nintegrated_multimodal_description: (?P<imd>[^\n]+)\noverall_soundscape: (?P<snd>[^\n]*)\nnon_diegetic_music: (?P<music>[^\n]*)\Z""")
PNG_SIG = b"\x89PNG\r\n\x1a\n"

# ID safety pattern: alphanumeric start, then alphanumeric/underscore/hyphen up to 64 chars total
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# SD-02: a soundscape must name at least one sound (whole word, inflections allowed: sounds, ringing, winds)
SOUNDSCAPE_WORD_RE = re.compile(
    r"\b(?:sound|hiss|rustle|splash|wind|water|step|breath|hum|whoosh|roar|crack|thud|drip|flow|ring|voice)\w*",
    re.IGNORECASE)
SOUND_PREFIX = "Sound effects only:"  # fixed words that open every compiled overall_soundscape
BED_MAX_WORDS = 12  # registry.sound_beds phrases: same casing and punctuation, at most 12 words

# ---- Pure-Foley prompt locks (owner master prompt V4 section 1): H3 is a Foley/SFX generator, never a speaker ----
MOUTH_LOCK_PHRASE = "while his lips remain completely closed"   # MO-01 positive lock, must sit in the description
MOUTH_STATES = ("closed", "open_non_verbal_breath")
SPEAKER_ID_RE = re.compile(r"\(\s*S\d+(?:\s*,\s*S\d+)*\s*\)")                 # SL-01, compound (S1,S2) included
LANG_TAG_RE = re.compile(r"\[\s*(?:hi|mr|en|ar|zh|fr|de|it|ja|ko|pt|ru|es|hindi|marathi|english|hinglish|arabic|"
                         r"chinese|french|german|italian|japanese|korean|portuguese|russian|spanish)\s*\]", re.I)  # SL-02
DIALOGUE_WRAP_RE = re.compile(r"</?d>", re.I)                                  # SL-03
AUDIO_TAG_RE = re.compile(r"<\s*Audio\s*\d+\s*>", re.I)                        # AU-01
CHIP_RE = re.compile(r"@(?:CHAR|SHEET|ENV|STYLE)-[A-Za-z0-9_*-]*|\b(?:SHEET|ENV|STYLE)-[A-Za-z0-9_-]+")  # TG-01 Flow chips
BRACKET_TAG_RE = re.compile(r"\[\s*(?:char|scene|shot|dur|hook)\s*:[^\]\n]*\]", re.I)  # TG-01 [char:..] [scene:..] ...
PANEL_RE = re.compile(r"[─-╿]+|\+[-=]{2,}\+")                        # TG-01 panel borders
ARROW_RE = re.compile(r"[←-⇿➡➔➜]|-->|->|=>")          # TG-01 arrows
TIMING_LABEL_RE = re.compile(r"\b\d+(?:\.\d+)?\s*[-–—]\s*\d+(?:\.\d+)?\s*s\b"
                             r"|\b\d{1,2}:\d{2}(?:\.\d+)?\s*[-–—]\s*\d{1,2}:\d{2}(?:\.\d+)?")  # TG-01 timing labels
TAG_RES = (CHIP_RE, BRACKET_TAG_RE, PANEL_RE, ARROW_RE, TIMING_LABEL_RE)
QUOTE_RE = re.compile(r'"[^"\n]*"|“[^”\n]*”')                   # TX-01 on-screen text
SFX_CUE_RE = re.compile(r"\b(?:sound|hiss|rustle|splash|wind|water|step|breath|hum|whoosh|roar|crack|thud|drip|flow|"
                        r"ring|voice|pop|click|tick|knock|snap|slam|scrape|tap|clink|creak|crunch|rain|spray|swish|"
                        r"thump|buzz|chime|bell|bird|song|stream|breeze|murmur|whisper|crackle|rumble|echo|tone|chant|drone|gust|sigh|"
                        r"flutter|patter|ripple|trickle|clang|rush|swell|twang|clasp|conch|thunk)\w*", re.I)                    # SX-01 synchronized physical sound
SX_MIN_STAGE_CUES = 0        # SX-01 retired per stage (D1 = B, M-01): sound cues live in overall_soundscape, checked by SX-02
MOUTH_PERSON_RE = re.compile(r"\b(?:keeps?|keep) (?:their|his|her) lips (?:completely )?closed\b|\bspeaks? with moving lips\b",
                             re.I)                                             # MO-01 per-person mouth sentence (prompt_hygiene)
SX02_STOP = frozenset("a an the and or of as in on at to from with by into its his her their some soft low high faint sharp "
                      "short quick light deep dry heavy loud distant then".split())
SX_MAX_SENTENCES = 4         # SX-01: overall_soundscape is 1-4 English sentences
REF2VA_RE = re.compile(
    r"\Asubject_definitions: (?P<subj>[^\n]+)\nsummary: (?P<summary>[^\n]+)\nretention_analysis: (?P<ret>[^\n]+)\n"
    r"detailed_description: (?P<det>[^\n]+)\noverall_soundscape: (?P<snd>[^\n]+)\nnon_diegetic_music: N/A\Z")
MOUTH_LOCK_SENTENCE = ("Silent performance: the figure never speaks, and his mouth stays shut "
                       f"{MOUTH_LOCK_PHRASE} for the whole shot.")


class PromptRefused(ValueError):
    """The compiler refuses a shot. code is the rule code (SL-01..SL-04); str(e) is '<code> <message>'."""

    def __init__(self, code, msg):
        super().__init__(f"{code} {msg}")
        self.code, self.msg = code, msg


def clean_text(text):
    """Free text as it may be emitted: Flow chips and storyboard tags stripped, then sanitize_single_line."""
    return sanitize_single_line(strip_tags(text)[0])


def strip_tags(text):
    """Remove Flow chips, bracket storyboard tags, panel borders, arrows and timing labels.
    Returns (clean_text, removed): removed lists every stripped piece."""
    removed = []

    def cut(m):
        removed.append(m.group(0))
        return " "
    out = text
    for rx in (BRACKET_TAG_RE, CHIP_RE, TIMING_LABEL_RE, PANEL_RE, ARROW_RE):
        out = rx.sub(cut, out)
    return out, removed


def iter_strings(obj, path="shot"):
    """(path, string) for every string inside a nested shot object."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, f"{path}[{i}]")


def speech_problems(text):
    """[(code, message)] for the 3 speech patterns: SL-01 (S\\d+) ids, SL-02 [Language] tags, SL-03 <d> wrappers."""
    out = []
    if SPEAKER_ID_RE.search(text):
        out.append(("SL-01", "speaker id such as (S1) is a speech leak"))
    if LANG_TAG_RE.search(text):
        out.append(("SL-02", "[Language] dialogue tag is a speech leak"))
    if DIALOGUE_WRAP_RE.search(text):
        out.append(("SL-03", "<d>...</d> wrapper is a speech leak"))
    return out


def voice_mode(reg):
    """English H3 speech is on only when the registry sets voice_engine.en = "h3" explicitly (old stories stay pure Foley)."""
    ve = reg.get("voice_engine") if isinstance(reg, dict) else None
    return isinstance(ve, dict) and ve.get("en") == "h3"


def refuse_speech_in_source(shot, voice=False):
    """Source-level refusal before any prompt is built. Pure Foley: any utterance (SL-04). English H3 voice: utterances
    allowed in English only (VE-06); speech patterns are still refused in every free-text field."""
    utterances = (shot.get("dialogue_and_lip_lock") or {}).get("utterances")
    if utterances and not voice:
        raise PromptRefused("SL-04", "utterances present: speech is voiced by ElevenLabs outside H3, H3 prompts carry none")
    for u in utterances or []:
        if voice and isinstance(u, dict) and u.get("language") != "en":
            raise PromptRefused("VE-06", f"utterance language {u.get('language')!r}: H3 speech is English only")
    for path, value in iter_strings(shot):
        if voice and path.startswith("shot.dialogue_and_lip_lock.utterances"):
            continue  # the utterance text is the speech itself; it is emitted inside <d> by the compiler
        for code, msg in speech_problems(value):
            raise PromptRefused(code, f"{msg} (in {path})")


def voice_context(shot, reg):
    """Context for the emitted-prompt speech check: None in pure-Foley mode; else the speaker ids of the story map,
    the number of utterances, the number of <Audio N> refs and whether the shot has an on-screen speaker."""
    if not voice_mode(reg):
        return None
    utt = [u for u in (shot.get("dialogue_and_lip_lock") or {}).get("utterances") or [] if isinstance(u, dict)]
    return {"speaker_ids": set(reg.get("voice_speaker_map") or {}), "utterances": len(utt),
            "audio_refs": len(ref_inventory(shot)["audio"]),
            "silent": not any(not u.get("is_offscreen_voiceover") for u in utt)}


def english_speech_problems(text, voice):
    """Speech checks of an EMITTED English H3 prompt: SL-01 ids must be in the story map, SL-02 only [English] tags,
    SL-03 one <d>...</d> per English line."""
    out = []
    for m in SPEAKER_ID_RE.finditer(text):
        for sid in re.findall(r"S\d+", m.group(0)):
            if sid not in voice["speaker_ids"]:
                out.append(("SL-01", f"speaker id {sid} is not in voice_speaker_map"))
    for m in LANG_TAG_RE.finditer(text):
        if m.group(0) != "[English]":
            out.append(("SL-02", f"dialogue tag {m.group(0)} must be [English] in English H3 speech"))
    opens, closes = len(re.findall(r"<d>", text, re.I)), len(re.findall(r"</d>", text, re.I))
    if opens != closes or opens != voice["utterances"]:
        out.append(("SL-03", f"{opens} <d> wrapper(s) for {voice['utterances']} English line(s)"))
    return out


def speaking_seconds(shot):
    """Second keys ("0", "1", ...) overlapped by an on-screen English line: their mouth_state is "speaking"."""
    out = set()
    for u in (shot.get("dialogue_and_lip_lock") or {}).get("utterances") or []:
        if isinstance(u, dict) and not u.get("is_offscreen_voiceover"):
            s, e = float(u["start_sec"]), float(u["end_sec"])
            out |= {str(k) for k in range(0, math.ceil(e) + 1) if k < e and k + 1 > s}
    return out


def stripped_tags_of(shot):
    """Every Flow chip or storyboard tag that clean_text removes from the shot's text fields."""
    return [hit for _, value in iter_strings(shot) for hit in strip_tags(value)[1]]


def sentence_count(text):
    return len([p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p])


def prompt_lock_problems(text, text_events=0, voice=None):
    """[(code, message)] locks on an EMITTED prompt: SL-01..03, AU-01, TG-01, TX-01, LEN-01, MO-01, SX-01 (text).
    voice=None: pure Foley (every speech pattern and every <Audio N> refused). voice=voice_context(...): English H3 speech,
    where the speech tags are checked by english_speech_problems and <Audio N> must point at a reference of the shot."""
    if voice is None:
        out = speech_problems(text)
        if AUDIO_TAG_RE.search(text):
            out.append(("AU-01", "<Audio N> tag in the prompt: voice references are refused"))
    else:
        out = english_speech_problems(text, voice)
        for m in AUDIO_TAG_RE.finditer(text):
            k = int(re.search(r"\d+", m.group(0)).group(0))
            if not 1 <= k <= voice["audio_refs"]:
                out.append(("AU-01", f"{m.group(0)} has no matching reference audio in the shot"))
    tags = [m.group(0) for rx in TAG_RES for m in rx.finditer(text)]
    if tags:
        out.append(("TG-01", f"storyboard or Flow tags on the prompt: {tags[:3]}"))
    quotes = QUOTE_RE.findall(text)
    if text_events > 1 or len(quotes) > text_events:
        out.append(("TX-01", f"{len(quotes)} double-quoted on-screen text span(s), {text_events} typography event(s) requested"))
    if len(text) > PROMPT_CHAR_LIMIT:
        out.append(("LEN-01", f"prompt is {len(text)} characters, the hard limit is {PROMPT_CHAR_LIMIT}"))
    if MOUTH_LOCK_PHRASE not in text and not MOUTH_PERSON_RE.search(text) and (voice is None or voice["silent"]):
        out.append(("MO-01", f"positive mouth lock {MOUTH_LOCK_PHRASE!r} is missing from the description"))
    m = re.search(r"^overall_soundscape: (.*)$", text, re.M)
    if m is None:
        out.append(("SX-01", "overall_soundscape line is missing"))
    else:
        snd = m.group(1)
        n = sentence_count(snd)
        if not 1 <= n <= SX_MAX_SENTENCES:
            out.append(("SX-01", f"overall_soundscape has {n} sentences, need 1-{SX_MAX_SENTENCES}"))
        if re.search(r"[^\x00-\x7f–—‘’“”]", snd):
            out.append(("SX-01", "overall_soundscape must be English (ASCII)"))
    return out


def cue_head_noun(text):
    """First content word of a sound cue ('a veil snaps' -> 'veil'). Articles, prepositions and plain adjectives are skipped."""
    for word in re.findall(r"[a-z]+", text.lower()):
        if len(word) > 2 and word not in SX02_STOP:
            return word
    return None


def sx02_problems(soundscape, sound_cues):
    """SX-02 (D1 = B): the head noun of every blocking sound cue appears in the soundscape, in t order.
    soundscape: the overall_soundscape text; sound_cues: blocking [{t, text}]. Returns problem strings (empty = pass).
    Heuristic: a plural 's'/'es' is accepted; each cue is searched after the previous cue's match."""
    text, out, last = soundscape.lower(), [], 0
    cues = [c for c in sound_cues if isinstance(c, dict) and isinstance(c.get("text"), str)]
    for cue in sorted(cues, key=lambda c: c.get("t") if isinstance(c.get("t"), (int, float)) else 0):
        noun = cue_head_noun(cue["text"])
        if noun is None:
            continue
        m = re.compile(r"\b" + re.escape(noun) + r"(?:s|es)?\b").search(text, last)
        if m is None:
            out.append(f"SX-02 cue {cue['text']!r} (head noun {noun!r}) is missing from the soundscape or out of t order")
        else:
            last = m.end()
    return out


def mouth_state_problems(shot, fps, speaking=None):
    """MO-01 source rules: narrator_mouth_closed must be true; mouth_state covers every second with a valid state.
    Both fields are required (owner V4 spec): narrator_mouth_closed true on every shot plus a per-second mouth_state.
    speaking: None (pure Foley) or the speaking_seconds set of English H3 voice mode: then a second is "speaking" exactly
    when an on-screen line is spoken in it."""
    d = shot["dialogue_and_lip_lock"]
    out = []
    if d.get("narrator_mouth_closed") is not True:
        out.append("narrator_mouth_closed must be present and true (H3 never voices the narrator)")
    ms = d.get("mouth_state")
    if ms is None:
        return out + ["mouth_state is required (second -> closed or open_non_verbal_breath)"]
    if not isinstance(ms, dict):
        return out + ["mouth_state must be an object of second -> state"]
    pf = shot["timing_and_lattice"]["pixel_frames"]
    need = {str(s) for s in range(math.ceil(pf / fps))}
    if set(ms) != need:
        out.append(f"mouth_state must have exactly the keys {sorted(need, key=int)}")
    allowed = MOUTH_STATES + (("speaking",) if speaking is not None else ())
    bad = {k: v for k, v in ms.items() if v not in allowed}
    if bad:
        out.append(f"mouth_state values must be one of {allowed}, got {bad}")
    if speaking is not None:
        for k, v in ms.items():
            if (k in speaking) != (v == "speaking"):
                out.append(f"mouth_state {k} must be 'speaking' exactly inside an on-screen English line")
    return out


def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def diegetic_text_events(shot):
    """Typography events the shot explicitly requests (metadata.diegetic_text_events, default 0). A value that is not a
    whole number >= 0 counts as 0 here; _check_metadata reports it (SC-02)."""
    meta = shot.get("metadata")
    n = meta.get("diegetic_text_events", 0) if isinstance(meta, dict) else 0
    return n if _is_count(n) else 0


class _Log:
    def __init__(self, sid):
        self.sid, self.errors, self.warnings = sid, [], []

    def err(self, code, msg):
        self.errors.append(f"{self.sid}: {code} {msg}")

    def warn(self, code, msg):
        self.warnings.append(f"{self.sid}: {code} {msg}")


def sanitize_single_line(text):
    return re.sub(r"\s+", " ", text).strip()


def lattice_n_to_frames_and_slots(n):
    return 17 * n + 5, 5 * n + 2


def read_png_dimensions_on_disk(path):
    """[w, h] from the IHDR chunk; raises ValueError if the file is not a PNG."""
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != PNG_SIG or head[12:16] != b"IHDR":
        raise ValueError(f"not a PNG file: {path}")
    w, h = struct.unpack(">II", head[16:24])
    return [w, h]


def write_minimal_valid_png(path, w, h):
    """Test helper: solid-black RGB PNG of size w x h, stdlib only."""
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = (b"\x00" + bytes(w * 3)) * h
    data = (PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def load_default_profile(name):
    """registry.execution_profile from h3/profiles/<name>.json."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles", name + ".json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)["registry"]["execution_profile"]


def _validate_id(value, kind, log):
    """Emit ID-01 if value does not match ID_PATTERN."""
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        log.err("ID-01", f"{kind} id {value!r} is unsafe; must match ^[A-Za-z0-9][A-Za-z0-9_-]{{0,63}}$")


def picture_path_problem(rel):
    """None when rel is a safe relative picture path; otherwise the reason it is refused (KF-07).
    Refused: non-strings, absolute paths, drive letters, and any '..' segment (either slash style)."""
    if not isinstance(rel, str) or not rel:
        return "must be a non-empty string"
    if rel[:1] in ("/", "\\") or os.path.isabs(rel) or re.match(r"^[A-Za-z]:", rel):
        return "must be relative and must not contain a drive letter"
    if ".." in re.split(r"[\\/]", rel):
        return "must not contain '..'"
    return None


def _check_picture_path(log, label, rel):
    """KF-07 for one picture path. Returns True when the path is safe."""
    problem = picture_path_problem(rel)
    if problem:
        log.err("KF-07", f"{label} path {rel!r} {problem}")
    return problem is None


def resolve_keyframes(shot, upstream_shot_or_None, asset_root):
    """Reuse rule: own picture_1 wins when the file exists; otherwise REUSED from upstream picture_2.
    An unsafe own path is never replaced by a reuse: it is returned as-is so KF-07 blocks the shot."""
    k = shot.get("fl2va_keyframes") or {}
    own = k.get("picture_1_path")
    reuse_id = k.get("reuse_upstream_b_id")
    if own is None:   # Q-R4-5: no own picture_1 at all: reuse the upstream picture_2 when a reuse id and an upstream shot exist
        if reuse_id and upstream_shot_or_None is not None:
            upstream_kf = upstream_shot_or_None.get("fl2va_keyframes") or {}
            return {"picture_1": upstream_kf.get("picture_2_path"), "picture_2": k.get("picture_2_path"), "reused": True}
        return {"picture_1": None, "picture_2": k.get("picture_2_path"), "reused": False}
    if (reuse_id and upstream_shot_or_None is not None and picture_path_problem(own) is None
            and not os.path.exists(os.path.join(asset_root, own))):
        upstream_kf = upstream_shot_or_None.get("fl2va_keyframes") or {}
        return {"picture_1": upstream_kf.get("picture_2_path"),
                "picture_2": k.get("picture_2_path"), "reused": True}
    return {"picture_1": own, "picture_2": k.get("picture_2_path"), "reused": False}


def lint_profile(profile):
    """Profile-level rules: PO-03 missing keys, PO-01 base not divisible by 32, PO-02/PO-W2 aspect."""
    out = {"errors": [], "warnings": []}
    miss = sorted(PROFILE_KEYS - set(profile))
    if miss:
        out["errors"].append(f"PO-03 execution_profile missing keys {miss}")
        return out
    msa = profile["model_sampling_av"]
    if not (isinstance(msa.get("video_shift"), dict) and {"keyframe", "ref2va"} <= set(msa["video_shift"])
            and "audio_shift" in msa):
        out["errors"].append("PO-04 model_sampling_av needs video_shift {keyframe, ref2va} and audio_shift")
    fps = profile["fps"]
    if not (_is_count(fps) and fps > 0):  # ponytail: zero fps divides by zero in the timing rules; reject it here once
        out["errors"].append(f"PO-06 fps must be a positive whole number, got {fps!r}")
        return out
    br = profile["base_resolution"]
    if not (isinstance(br, list) and len(br) == 2 and all(_is_count(x) for x in br)):
        out["errors"].append(f"PO-01 base_resolution must be [width, height] whole numbers, got {br!r}")
        return out
    w, h = br
    if w % 32 or h % 32:
        out["errors"].append(f"PO-01 base_resolution {w}x{h} is not divisible by 32")
    parts = str(profile["aspect_ratio"]).split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        out["errors"].append(f"PO-02 aspect_ratio {profile['aspect_ratio']!r} must be 'a:b' with whole numbers")
        return out
    a, b = (int(p) for p in parts)
    if w * b != h * a:
        msg = f"base_resolution {w}x{h} is not exactly {profile['aspect_ratio']}"
        if profile.get("aspect_strict", True):
            out["errors"].append(f"PO-02 {msg}")
        else:
            out["warnings"].append(f"PO-W2 {msg} (aspect_strict false)")
    return out


def _run(log, fn, *args):
    try:
        fn(log, *args)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as e:
        log.err("SC-03", f"{fn.__name__[7:]} could not read the shot: {e!r}")


def _keyset(log, name, obj, required, optional=frozenset()):
    if not isinstance(obj, dict):
        log.err("SC-02", f"{name} must be an object")
        return
    miss = sorted(set(required) - set(obj))
    extra = sorted(set(obj) - set(required) - set(optional))
    if miss:
        log.err("SC-02", f"{name} missing keys {miss}")
    if extra:
        log.err("SC-02", f"{name} extra keys {extra}")


def _check_keys(log, shot):
    miss = sorted(SHOT_KEYS - set(shot))
    extra = sorted(set(shot) - SHOT_KEYS - {"metadata"})
    if miss:
        log.err("SC-01", f"missing top-level keys {miss}")
    if extra:
        log.err("SC-01", f"extra top-level keys {extra}")
    for name, (req, opt) in BLOCKS.items():
        if name in shot:
            _keyset(log, name, shot[name], req, opt)
    spans = (shot.get("motion_7_stage") or {}).get("stage_frame_spans")
    if spans is not None:
        _keyset(log, "stage_frame_spans", spans, STAGES)


def _check_metadata(log, shot):
    meta = shot.get("metadata")
    if meta is None:
        return
    if not isinstance(meta, dict):
        log.err("SC-02", "metadata must be an object")
    elif "diegetic_text_events" in meta and not _is_count(meta["diegetic_text_events"]):
        log.err("SC-02", f"metadata.diegetic_text_events must be a whole number >= 0, got {meta['diegetic_text_events']!r}")


def _check_timing(log, shot, prof):
    t, fps = shot["timing_and_lattice"], prof["fps"]
    n, pf = t["lattice_n"], t["pixel_frames"]
    lo, hi = prof["valid_lattice_n_range"]
    if not lo <= n <= hi:
        log.err("PF-01", f"lattice_n={n} outside {lo}..{hi}")
    if pf != 17 * n + 5:
        log.err("PF-02", f"pixel_frames={pf} must be 17*{n}+5={17 * n + 5}")
    if t["latent_slots"] != 5 * n + 2:
        log.err("PF-03", f"latent_slots={t['latent_slots']} must be 5*{n}+2={5 * n + 2}")
    if not 4.0 <= pf / fps <= 15.0:
        log.err("PF-04", f"duration {pf / fps:.2f}s outside [4.00, 15.00]")
    if t["fps"] != fps:
        log.err("TM-01", f"fps={t['fps']} != profile fps {fps}")
    ti, to, ed = t["trim_in_frame"], t["trim_out_frame"], t["editorial_frames"]
    head, tail = t["head_handle_frames"], t["tail_handle_frames"]
    if not all(_is_count(x) for x in (ti, to, ed, head, tail)):
        log.err("TM-02", "trim, editorial and handle frame counts must be whole numbers >= 0 (not booleans)")
    elif head != ti or tail != pf - to or ed != to - ti or not 0 <= ti < to <= pf:
        log.err("TM-02", f"handles/editorial mismatch: trim {ti}..{to}, head {head}, tail {tail}, editorial {ed}, pixel {pf}")
    for sec_key, frame_key in SEC_FRAMES.items():
        if t[sec_key] != round(t[frame_key] / fps, 2):
            log.err("TM-03", f"{sec_key}={t[sec_key]} != round({t[frame_key]}/{fps},2)")
    if t["prompt_alignment_sec_str"] != f"{pf / fps:.2f}":
        log.err("TM-06", f"prompt_alignment_sec_str={t['prompt_alignment_sec_str']!r} != {pf / fps:.2f}")


def _check_window(log, shot, running, fps):
    t = shot["timing_and_lattice"]
    ed = t["editorial_frames"]
    if list(t["master_reel_frame_window"]) != [running, running + ed]:
        log.err("TM-04", f"master_reel_frame_window must be [{running}, {running + ed}]")
    if list(t["master_reel_window_sec"]) != [round(running / fps, 2), round((running + ed) / fps, 2)]:
        log.err("TM-04", "master_reel_window_sec does not match the frame window")


def _check_continuity(log, shot, prof):
    c, t = shot["continuity_and_seam_lock"], shot["timing_and_lattice"]
    inc, out = c["incoming_seam_type"], c["outgoing_seam_type"]
    pf, ti, to = t["pixel_frames"], t["trim_in_frame"], t["trim_out_frame"]
    head, tail = t["head_handle_frames"], t["tail_handle_frames"]
    for seam in (inc, out):
        if seam not in SEAM_TYPES:
            log.err("CN-01", f"unknown seam type {seam!r}")
    if inc in STATIC_SEAMS and (ti != 0 or head != 0):
        log.err("CN-02", f"incoming {inc} needs trim_in 0 and head handle 0")
    if inc == DYN and not 8 <= head <= 35:
        log.err("CN-04", f"incoming DYNAMIC head handle {head} outside [8, 35]")
    if out in STATIC_SEAMS and (to != pf or tail != 0):
        log.err("CN-03", f"outgoing {out} needs trim_out == {pf} and tail handle 0")
    if out == DYN and not 24 <= tail <= 47:
        log.err("CN-05", f"outgoing DYNAMIC tail handle {tail} outside [24, 47]")
    if inc == DYN and out == DYN:
        n = t["lattice_n"]
        if n in LATTICE_CUT_BOUNDS:
            (elo, ehi), (hlo, hhi) = LATTICE_CUT_BOUNDS[n]
            ed = t["editorial_frames"]
            if not (elo <= ed <= ehi and hlo <= head + tail <= hhi):
                log.err("CN-06", f"both-dynamic cut at n={n}: editorial {ed} (want {elo}..{ehi}), handle sum {head + tail} (want {hlo}..{hhi})")
        else:
            log.warn("CN-W1", f"no LATTICE_CUT_BOUNDS for n={n}; both-dynamic cut bounds skipped")


def _check_motion(log, shot):
    m, t = shot["motion_7_stage"], shot["timing_and_lattice"]
    pf = t["pixel_frames"]
    spans = m["stage_frame_spans"]
    expect = 0
    for k in STAGES:
        a, b = spans[k]
        if a != expect or b < a:
            log.err("MO-02", f"stage {k} span [{a},{b}] breaks contiguity (expected start {expect})")
        expect = b + 1
    if spans[STAGES[-1]][1] != pf:
        log.err("MO-02", f"last stage must end at pixel_frames {pf}")
    if shot["continuity_and_seam_lock"]["outgoing_seam_type"] == DYN:
        a, b = spans["6_impact_result"]
        if not a <= t["trim_out_frame"] <= b:
            log.err("MO-03", f"DYNAMIC outgoing trim_out {t['trim_out_frame']} outside 6_impact_result [{a},{b}]")


def _check_cadence(log, shot):
    c, pf = shot["anime_timing_cadence"], shot["timing_and_lattice"]["pixel_frames"]
    wins = sorted((c[k] for k in ("hold_window_frames", "burst_window_frames", "impact_or_settle_frames")),
                  key=lambda w: w[0])
    expect = 0
    for a, b in wins:
        if a != expect or b < a:
            log.err("CD-01", f"cadence window [{a},{b}] breaks contiguity (expected start {expect})")
        expect = b + 1
    if wins[-1][1] != pf:
        log.err("CD-01", f"cadence windows must end at pixel_frames {pf}")


def _check_camera(log, shot):
    cam = shot["camera"]
    clause = sanitize_single_line(cam["compiled_clause"]).lower()
    phrases = OFFICIAL_CAMERA_MOTION_PHRASES.get(cam["motion_type"])
    if phrases is None:
        log.err("CM-01", f"motion_type {cam['motion_type']!r} is not an official camera motion")
    elif not any(p in clause for p in phrases):
        log.err("CM-02", f"camera clause {clause!r} lacks a phrase for {cam['motion_type']!r}")
    for key, omitted, allowed, word in (("amplitude", "medium_omitted", AMPLITUDES, "amplitude"),
                                        ("speed", "normal_omitted", SPEEDS, "speed")):
        v = cam[key]
        if v == omitted:
            if word in clause:
                log.err("CM-04", f"{key} is {omitted} but the clause mentions {word!r}")
        elif v not in allowed:
            log.err("CM-03", f"{key} {v!r} is not allowed")
        elif v not in clause:
            log.err("CM-03", f"clause lacks {key} phrase {v!r}")


def _check_stage_words(log, shot, imd):
    """M-03 on the emitted description: exactly one camera sentence (CM-05), shake only as 'a short shake at second N'
    (CM-06), a time point is never a range (TP-02). Old stories carry no time points, so a missing one is not a rule."""
    n = len(re.findall(r"\bthe camera\b", imd, re.I))
    if n != 1:
        log.err("CM-05", f"the description has {n} camera sentences, need exactly 1")
    rest = re.sub(r"a short shake at second \d+(?:\.\d+)?", "", imd)
    if re.search(r"\bshak", rest, re.I) and not str(shot["camera"].get("motion_type")).startswith("Shake"):
        log.err("CM-06", "shake must be written 'a short shake at second N'")
    if re.search(r"\b(?:At|By) second \d+(?:\.\d+)?\s*(?:-|–|to)\s*\d", imd):
        log.err("TP-02", "a stage names a time range; use a single time point ('At second 2.5,')")


def _check_dialogue(log, shot, reg):
    d, chars = shot["dialogue_and_lip_lock"], reg["characters"]
    if bool(d["has_dialogue"]) != bool(d["utterances"]):
        log.err("DL-01", "has_dialogue disagrees with utterances")
    for u in d["utterances"]:
        _keyset(log, "utterance", u, UTTERANCE_KEYS)
        if not isinstance(u, dict):
            continue
        if u.get("character_id") not in chars:
            log.err("DL-02", f"utterance character_id {u.get('character_id')!r} not in registry.characters")
    if voice_mode(reg):  # English H3 speech: one speaker id per character across the story, each speaker has an anchor
        smap = reg.get("voice_speaker_map") or {}
        for u in d["utterances"]:
            if not isinstance(u, dict):
                continue
            sid, cid = u.get("speaker_id"), u.get("character_id")
            if sid not in smap:
                log.err("VA-01", f"speaker {sid!r} has no entry in voice_speaker_map")
            elif smap[sid] != cid:
                log.err("VA-04", f"speaker {sid!r} is mapped to {smap[sid]!r}, not {cid!r} (same speaker in every shot)")
            ch = chars.get(cid)
            if not (isinstance(ch, dict) and ch.get("voice_anchor")):
                log.err("VA-01", f"{cid!r} speaks English but has no voice anchor")


def _check_keyframes(log, shot, prof, root, prev):
    k, base = shot["fl2va_keyframes"], list(prof["base_resolution"])
    if k.get("mode") not in ("FL2VA", "REF2VA"):
        log.err("KF-01", f"mode {k.get('mode')!r} must be FL2VA or REF2VA")
    reuse = k.get("reuse_upstream_b_id")
    if reuse and (prev is None or prev.get("shot_id") != reuse):
        log.err("KF-05", f"reuse_upstream_b_id {reuse!r} is not the previous shot")
    kf = resolve_keyframes(shot, prev, root)
    if kf.get("reused"):
        log.warn("KF-W1", f"picture_1 REUSED from upstream {prev.get('shot_id')} picture_2")
    if list(k.get("dimensions_verified", [])) != base:
        log.err("KF-04", f"dimensions_verified {k.get('dimensions_verified')} != base_resolution {base}")
    refs = k.get("reference_images") or []
    if not isinstance(refs, list):
        log.err("KF-08", "reference_images must be a list of picture paths")
        refs = []
    start_only = route_shot(shot) == "I2VA"   # M-02: a start-only shot needs picture_1 only
    if not refs and not (kf.get("picture_1") and (kf.get("picture_2") or start_only)):   # the resolved frames: a REUSED picture_1 counts (Q-R4-5)
        log.err("KF-06", "both boundary frames are required unless reference_images are given")
    # KF-07 on picture paths and optional flow sources; unsafe paths never reach the disk checks
    pics = [("picture_1", kf.get("picture_1")), ("picture_2", k.get("picture_2_path"))]
    pics += [(f"reference_images[{i}]", r) for i, r in enumerate(refs)]
    safe = {}
    for label, rel in pics + [("flow_source_a", k.get("flow_source_a")), ("flow_source_b", k.get("flow_source_b"))]:
        if rel is not None:
            safe[label] = _check_picture_path(log, label, rel)
    # Disk checks
    for label, rel in pics:
        if rel is None or not safe.get(label):
            continue
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            log.err("KF-02", f"{label} file missing: {rel}")
            continue
        try:
            dims = read_png_dimensions_on_disk(path)
        except ValueError as e:
            log.err("KF-03", str(e))
            continue
        if dims != base:
            log.err("KF-03", f"{label} is {dims[0]}x{dims[1]}, base_resolution is {base[0]}x{base[1]}")


def _check_cross_shot(log, shot, prev, root):
    cur, pc = shot["continuity_and_seam_lock"], prev["continuity_and_seam_lock"]
    if cur.get("cut_in_biomechanical_state_tag") != pc.get("cut_out_biomechanical_state_tag"):
        log.err("CN-07", f"cut_in state tag {cur.get('cut_in_biomechanical_state_tag')!r} != previous cut_out {pc.get('cut_out_biomechanical_state_tag')!r}")
    a, b = pc.get("cut_out_pose_vector", {}), cur.get("cut_in_pose_vector", {})
    if (abs(a.get("torso_pitch_deg", 0) - b.get("torso_pitch_deg", 0)) > 5.0 or
        abs(a.get("knee_flex_deg", 0) - b.get("knee_flex_deg", 0)) > 5.0 or
        abs(a.get("com_y_ratio", 0) - b.get("com_y_ratio", 0)) > 0.03 + 1e-9):
        log.err("CN-08", "pose jump from the previous cut_out_pose_vector exceeds 5.0 deg / 5.0 deg / 0.03")
    if cur.get("incoming_seam_type") == CHAINED:
        if resolve_keyframes(shot, prev, root).get("picture_1") != prev.get("fl2va_keyframes", {}).get("picture_2_path"):
            log.err("CN-09", "CHAINED_POSE_HOLD picture_1 must equal the previous picture_2_path")


def sound_beds_of(registry):
    """registry.sound_beds as a dict; anything else is reported as SD-04 and read as no beds."""
    beds = (registry or {}).get("sound_beds", {})
    return beds if isinstance(beds, dict) else {}


def soundscape_bed(shot, registry):
    """Cleaned bed phrase for the shot's location, or "" when none is defined or it is not a string."""
    loc = (shot.get("continuity_and_seam_lock") or {}).get("location_id")
    bed = sound_beds_of(registry).get(loc)
    return clean_text(bed) if isinstance(bed, str) else ""


def compiled_soundscape(shot, registry):
    """THE builder of the compiled overall_soundscape: "Sound effects only: <bed> <shot effects>".
    The compiler and the linter (SD-03) both call it. The prefix and the bed are never doubled."""
    raw = (shot.get("sound_plan") or {}).get("overall_soundscape")
    text = clean_text(raw) if isinstance(raw, str) else ""
    bed = soundscape_bed(shot, registry)
    if text.startswith(SOUND_PREFIX):
        text = text[len(SOUND_PREFIX):].strip()
    if bed and (text == bed or text.startswith(bed + " ")):
        text = text[len(bed):].strip()
    return " ".join(p for p in (SOUND_PREFIX, bed, text) if p)


def _compiled_soundscape_line(compiled):
    m = re.search(r"^overall_soundscape: (.*)$", compiled, re.M)
    return m.group(1) if m else None


def _check_sound_plan(log, shot, prof, reg, compiled=None):
    """SD-01, SD-02 (the shot's own text), SD-03 (compiled soundscape), SD-04 (sound_beds)."""
    snd = shot["sound_plan"]
    raw_sc, raw_mu = snd.get("overall_soundscape"), snd.get("non_diegetic_music")
    soundscape = clean_text(raw_sc) if isinstance(raw_sc, str) else ""
    # SD-01: soundscape non-empty single sentence, at least 40 chars. It reads the shot's own text, never the
    # compiled one: the prefix and bed would pad an empty soundscape past 40 characters.
    if not soundscape:
        log.err("SD-01", "sound_plan.overall_soundscape must be a non-empty single sentence of at least 40 characters")
    elif len(soundscape) < 40:
        log.err("SD-01", f"sound_plan.overall_soundscape too short ({len(soundscape)} chars), need at least 40")
    # SD-01: non_diegetic_music must be "N/A" unless profile allows model music (owner rule 2026-11-06)
    music = clean_text(raw_mu) if isinstance(raw_mu, str) else None
    if music is None or music.lower() != "n/a":
        if prof.get("allow_model_music") is not True:
            log.err("SD-01", 'sound_plan.non_diegetic_music must be "N/A" (case-insensitive) unless profile sets allow_model_music=true')
    # SD-02: warning if soundscape names no sound at all (catches empty placeholders)
    if soundscape and not SOUNDSCAPE_WORD_RE.search(soundscape):
        log.warn("SD-02", "sound_plan.overall_soundscape names no sound (sound, hiss, rustle, splash, wind, water, step, breath, hum, whoosh, roar, crack, thud, drip, flow, ring, voice)")
    # SD-04: every sound_beds entry is a string of at most 12 words (non-object sound_beds is refused too)
    beds = reg.get("sound_beds", {})
    if not isinstance(beds, dict):
        log.err("SD-04", "sound_beds must be an object of location_id -> phrase")
    elif (shot.get("continuity_and_seam_lock") or {}).get("location_id") in beds:
        bed = beds[shot["continuity_and_seam_lock"]["location_id"]]
        if not isinstance(bed, str) or len(bed.split()) > BED_MAX_WORDS:
            log.err("SD-04", f"sound_beds entry for this location must be a string of at most {BED_MAX_WORDS} words")
    # SD-03: the compiled soundscape starts with "Sound effects only:", has the location bed right after it,
    # and is exactly the shared builder's output (checked against the compiled prompt when one is given)
    expected = compiled_soundscape(shot, reg)
    got = _compiled_soundscape_line(compiled) if isinstance(compiled, str) else expected
    head = " ".join(p for p in (SOUND_PREFIX, soundscape_bed(shot, reg)) if p)
    if got is None or got != expected or not (got == head or got.startswith(head + " ")):
        log.err("SD-03", f"compiled overall_soundscape {got!r} must be {expected!r}, starting with {head!r}")


def _check_prompt(log, shot, prof, reg, compiled):
    from h3.compile_h3_sing8 import compile_fl2va_prompt  # lazy: compile module imports this one
    if compiled is None:
        try:
            compiled = compile_fl2va_prompt(shot, reg)["compiled_prompt"]
        except PromptRefused as e:
            log.err(e.code, e.msg)
            return
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            log.err("PR-00", f"prompt could not be compiled: {e!r}")
            return
    text, style = compiled, reg["style_lock"]
    ref = route_shot(shot) == REF2VA
    if ref:
        m = REF2VA_RE.match(text)
        if not m:
            log.err("PR-01", "Ref2VA prompt does not match the 6-section layout")
            imd = text
        else:
            imd = m.group("det")
            inv, subjects = ref_inventory(shot), shot["continuity_and_seam_lock"]["subjects_present"]
            limits = {"Subject": len(subjects), "Picture": len(inv["images"]), "Video": len(inv["videos"])}
            for kind, num in re.findall(r"<(Subject|Picture|Video) (\d+)>", text):
                if not 1 <= int(num) <= limits[kind]:
                    log.err("RF-03", f"<{kind} {num}> has no matching reference ({limits[kind]} available)")
    else:
        start_only = route_shot(shot) == "I2VA"   # M-02 S profile: no Picture 2 header, no end-frame mark
        m = (PROMPT_I2VA_RE if start_only else PROMPT_RE).match(text)
        if not m:
            log.err("PR-01", "prompt does not match the 4-part layout")
            imd = text
        else:
            imd = m.group("imd")
            pf, fps = shot["timing_and_lattice"]["pixel_frames"], prof["fps"]
            if not start_only and m.group("sec") != f"{pf / fps:.2f}":
                log.err("PR-01", f"header second mark {m.group('sec')} != {pf / fps:.2f}")
            if not imd.startswith(f"[Shot 1] {clean_text(style['mandatory_prefix'])}, preserving the exact character design"):
                log.err("PR-01", "description does not start with the mandatory prefix")
    # the S header "(from [Shot 1])" is the official I2VA line, not a body tag
    if re.findall(r"\[Shot (\d+)\]", re.sub(r"\(from \[Shot 1\]\)", "", text)) != ([] if ref else ["1"]):
        log.err("PR-02", "the only [Shot N] tag must be [Shot 1] (none in Ref2VA)")
    for code, msg in prompt_lock_problems(text, text_events=diegetic_text_events(shot), voice=voice_context(shot, reg)):
        log.err(code, msg)
    if re.search(r"\bAt \d{1,2}:\d{2}(?:\.\d+)?", text):
        log.err("PR-03", "At MM:SS timestamp found")
    for tok in style.get("banned_style_tokens", []):
        if tok.lower() in text.lower():
            log.err("PR-04", f"banned style token {tok!r}")
    if not prof["min_imd_body_chars"] <= len(imd) <= prof["max_imd_body_chars"]:
        log.err("PR-05", f"description length {len(imd)} outside [{prof['min_imd_body_chars']}, {prof['max_imd_body_chars']}]")
    if len(text) > prof["max_total_prompt_chars"]:
        log.err("PR-06", f"prompt length {len(text)} > {prof['max_total_prompt_chars']}")
    d = shot["dialogue_and_lip_lock"]
    # M-01: mouth_state_rule is no longer emitted (per-person mouth sentence; MO-01 checks it), so it is not a piece here
    pieces = [clean_text(shot["anime_timing_cadence"]["cadence_clause"]),
              clean_text(shot["camera"]["compiled_clause"])]
    for p in pieces:
        if p not in imd:
            log.err("PR-07", f"{p[:60]!r} is not a substring of the description")
    _check_stage_words(log, shot, imd)
    rx = style.get("banned_negative_words_regex")
    if rx:
        try:
            hit = re.search(rx, text, re.I)
        except re.error as e:  # a bad pattern in the registry is a registry error, not a crash
            log.err("PR-08", f"banned_negative_words_regex {rx!r} is not a valid regex: {e}")
            hit = None
        if hit:
            log.warn("PR-W1", f"banned negative word pattern {rx!r} matches the prose")


def _check_workflow(log, workflow, shot, prof):
    nodes = workflow["nodes"]
    want = {"1": "MiniMaxH3CheckpointLoader", "2": "LoraLoaderModelOnly", "3": "ModelSamplingAV",
            "4": "MiniMaxH3TextEncode", "5": "MiniMaxH3ImageToVideo", "6": "BasicGuider",
            "7": "KSampler", "8": "VideoVAEDecode", "9": "AudioVAEDecode"}
    for key, cls in want.items():
        got = nodes.get(key, {}).get("class_type")
        if got != cls:
            log.err("WF-01", f"node {key} must be {cls}, got {got}")
    if workflow.get("_unverified_node_classes") is not True:
        log.err("WF-08", "workflow must carry _unverified_node_classes: true")
    mode = shot["fl2va_keyframes"].get("mode")
    route = route_shot(shot)
    if route not in ("FL2VA", REF2VA, "I2VA"):
        log.err("WF-09", f"route {route} has no sing8 workflow (only FL2VA, Ref2VA and I2VA)")
        return
    lora = prof["mode_to_lora_map"].get(f"{workflow_mode(route)}_{prof['checkpoint_architecture_namespace']}")
    if sum(1 for n in nodes.values() if n.get("class_type") == "LoraLoaderModelOnly") != 1:
        log.err("WF-02", "exactly one LoraLoaderModelOnly node is required")
    lo = nodes["2"]["inputs"]
    if lo["lora_name"] != lora or lo["strength_model"] != prof["runtime_lora_strength"]:
        log.err("WF-02", f"LoRA must be {lora!r} at strength {prof['runtime_lora_strength']}, got {lo['lora_name']!r} at {lo['strength_model']}")
    ms = nodes["3"]["inputs"]
    if (sum(1 for n in nodes.values() if n.get("class_type") == "ModelSamplingAV") != 1
            or ms["video_shift"] != video_shift_for(prof, route)
            or ms["audio_shift"] != prof["model_sampling_av"]["audio_shift"]):
        log.err("WF-03", "ModelSamplingAV must have one node with the mode's video_shift and audio_shift")
    gd = nodes["6"]["inputs"]
    if gd["cfg"] != prof["cfg"] or gd["has_negative_branch"] is not False:
        log.err("WF-04", "guider must use profile cfg and no negative branch")
    ks = nodes["7"]["inputs"]
    if (ks["steps"] != prof["steps_nfe"] or ks["sampler_name"] != prof["sampler_name"]
            or ks["scheduler"] != prof["scheduler"]):
        log.err("WF-05", f"KSampler must be steps {prof['steps_nfe']}, {prof['sampler_name']}, {prof['scheduler']}")
    cond, (w, h) = nodes["5"]["inputs"], prof["base_resolution"]
    if (cond["width"], cond["height"]) != (w, h) or cond["length"] != shot["timing_and_lattice"]["pixel_frames"]:
        log.err("WF-06", f"conditioning must be {w}x{h} with length {shot['timing_and_lattice']['pixel_frames']}")
    if mode == "FL2VA" and lora and "ref2va" in lora.lower():
        log.warn("WF-W1", f"unverified combination: FL2VA on ref2va LoRA {lora!r}")


def _check_mouth_lock(log, shot, prof, reg=None):
    for msg in mouth_state_problems(shot, prof["fps"], speaking_seconds(shot) if voice_mode(reg) else None):
        log.err("MO-01", msg)


def _check_pure_foley(log, shot, prof, reg=None):
    """Source-level rules: MO-01 mouth lock, SX-01 sound cue in the action sentences, Ref2VA limits.
    English H3 voice mode (reg voice_engine en=h3): mouth_state follows the on-screen lines, reference_audio lists the
    voice anchors of the shot's speakers (VA-05..07)."""
    voice = voice_mode(reg)
    _run(log, _check_mouth_lock, shot, prof, reg)  # own _run: a malformed mouth block must not hide SX-01 and the VA rules
    if route_shot(shot) == REF2VA:  # any audio ref routes the shot here, so AU-01 is reported by this call only
        for code, msg in ref2va_limit_problems(shot, voice):
            log.err(code, msg)
    if voice:
        inv, chars = ref_inventory(shot), reg["characters"]
        sid = shot.get("shot_id")
        anchors = []
        for cid in inv["audio"]:
            a = (chars.get(cid) or {}).get("voice_anchor") if isinstance(chars.get(cid), dict) else None
            if a is not None and not isinstance(a, dict):   # a non-object anchor is treated as missing
                log.err("VA-01", f"reference_audio {cid!r} has a voice anchor that is not an object")
                continue
            if a is None:
                log.err("VA-01", f"reference_audio {cid!r} has no voice anchor")
            elif a.get("audio") is None:  # UNVERIFIED timbre stability: the anchor is the first approved H3 clip's audio
                log.err("VA-08", f"voice anchor of {cid!r} is pending: extract its audio from {a.get('clip_shot_id')!r} first")
            else:
                anchors.append(a)
        for code, msg in audio_ref_problems(anchors):
            log.err(code, msg)
        for u in (shot.get("dialogue_and_lip_lock") or {}).get("utterances") or []:
            cid = u.get("character_id") if isinstance(u, dict) else None
            if cid is None or cid in inv["audio"]:
                continue
            a = (chars.get(cid) or {}).get("voice_anchor") if isinstance(chars.get(cid), dict) else None
            a = a if isinstance(a, dict) else {}
            if a.get("audio") is None and a.get("clip_shot_id") == sid:
                continue  # this shot is the anchor's source render: it is rendered without its own anchor
            log.err("VA-07", f"{cid!r} speaks but its voice anchor is not in reference_audio")


def lint_shot(shot, profile, registry, asset_root, prev=None, compiled_prompt=None):
    """Per-shot rules. prev = previous shot in the episode (enables cross-shot and reuse rules).
    compiled_prompt: optional already-compiled prompt text (or its compile dict) to check instead of recompiling."""
    if not isinstance(shot, dict):   # Q-R4-8: a bad row is a lint error, never a crash
        return {"errors": [f"<shot ?>: SH-00 shot must be an object, got {type(shot).__name__}"], "warnings": []}
    sid = shot.get("shot_id", "<shot ?>")
    log = _Log(sid if isinstance(sid, str) else "<shot ?>")
    _validate_id(sid, "shot", log)  # ID-01: the id names files, so it must be path-safe
    if isinstance(compiled_prompt, dict):
        compiled_prompt = compiled_prompt["compiled_prompt"]
    _run(log, _check_keys, shot)
    _run(log, _check_metadata, shot)
    _run(log, _check_timing, shot, profile)
    _run(log, _check_continuity, shot, profile)
    _run(log, _check_motion, shot)
    _run(log, _check_cadence, shot)
    _run(log, _check_camera, shot)
    _run(log, _check_dialogue, shot, registry)
    _run(log, _check_pure_foley, shot, profile, registry)
    _run(log, _check_keyframes, shot, profile, asset_root, prev)
    if prev is not None:
        _run(log, _check_cross_shot, shot, prev, asset_root)
    _run(log, _check_sound_plan, shot, profile, registry, compiled_prompt)
    _run(log, _check_prompt, shot, profile, registry, compiled_prompt)
    return {"errors": log.errors, "warnings": log.warnings}


def lint_workflow(workflow, shot, profile):
    """Route C payload rules (WF-*). Node classes are unverified; see the _unverified_node_classes flag."""
    log = _Log(shot.get("shot_id", "<shot ?>"))
    _run(log, _check_workflow, workflow, shot, profile)
    return {"errors": log.errors, "warnings": log.warnings}


def _routed_s(routes, sid):
    row = routes.get(sid) if isinstance(routes, dict) and isinstance(sid, str) else None
    if isinstance(row, dict):
        return row.get("image_prompt_type") == "S" or row.get("route") == "S"
    return row == "S"


def _start_only_copy(shot):
    """A copy of the shot as the S route sees it: no end picture (so route_shot gives I2VA and the linter uses the
    start-only layout)."""
    import copy
    out = copy.deepcopy(shot)
    kf = out.get("fl2va_keyframes")
    if isinstance(kf, dict):
        kf.pop("picture_2_path", None)
    return out


def lint_story(story, compiled=None, asset_root_override=None, routes=None):
    """Lint every episode. compiled: optional {shot_id: prompt text or compile dict} to check instead of recompiling.
    routes (M-03): optional {shot_id: route row} (the routes file's "routes" map, or a plain id -> "S"); a shot whose row says
    image_prompt_type "S" (or route "S") is linted as start-only, even though the story still carries its picture_2.
    Story-level structure errors (no registry/episodes) raise KeyError; profile errors are attributed to the first shot."""
    from h3.compile_h3_sing8 import compile_fl2va_prompt, compile_comfyui_workflow  # lazy: avoids import cycle
    reg = story["registry"]
    prof = reg["execution_profile"]
    out = {"errors": [], "warnings": []}
    compiled_map = compiled if isinstance(compiled, dict) else {}
    all_shots = [s for ep in story["episodes"] for s in ep["shots"]]
    anchor = all_shots[0].get("shot_id", "<shot 1>") if all_shots and isinstance(all_shots[0], dict) else "<story>"
    if compiled is not None and not isinstance(compiled, dict):   # a non-object map: reported, then every shot is compiled again
        out["errors"].append(f"{anchor}: PR-00 compiled must be an object {{shot_id: prompt}}, got {type(compiled).__name__}")
    pl = lint_profile(prof)
    out["errors"] += [f"{anchor}: {m}" for m in pl["errors"]]
    out["warnings"] += [f"{anchor}: {m}" for m in pl["warnings"]]
    if pl["errors"]:
        return out
    if "style_lock" not in reg:  # the prompt prefix; compile_fl2va_prompt refuses without it
        out["errors"].append(f"{anchor}: PO-05 registry has no style_lock (the prompt prefix and banned tokens)")
        return out
    # Check for duplicate shot_ids across the whole story
    seen_ids = {}
    for ep in story["episodes"]:
        for shot in ep["shots"]:
            sid = shot.get("shot_id") if isinstance(shot, dict) else None
            if not isinstance(sid, str):
                continue  # lint_shot reports the bad id
            if sid in seen_ids:
                out["errors"].append(f"{sid}: ID-01 duplicate shot_id {sid!r} also in episode {seen_ids[sid]}")
            else:
                seen_ids[sid] = ep["episode_id"]
    for ep in story["episodes"]:
        root = asset_root_override or ep.get("asset_root")
        if not isinstance(root, str) or not root:
            out["errors"].append(f"{ep.get('episode_id')}: EP-AR asset_root is missing (the folder with the picture paths)")
            continue
        shots, running = ep["shots"], 0
        # Validate episode_id
        log_ep = _Log("episode")
        _validate_id(ep.get("episode_id"), "episode", log_ep)
        out["errors"] += log_ep.errors
        out["warnings"] += log_ep.warnings
        for i, shot in enumerate(shots):
            if not isinstance(shot, dict):   # Q-R4-8: reported once, then skipped
                out["errors"].append(f"{ep.get('episode_id')}: SH-00 shot {i + 1} must be an object, got {type(shot).__name__}")
                continue
            sid = shot.get("shot_id", f"<shot {i + 1}>")
            prev = shots[i - 1] if i and isinstance(shots[i - 1], dict) else None
            c = compiled_map.get(sid) if isinstance(sid, str) else None
            if isinstance(c, dict):
                c = c["compiled_prompt"]
            if _routed_s(routes, sid):   # M-03: lint what build_h3_batch compiles: the start-only shot, no picture_2
                shot = _start_only_copy(shot)
            r = lint_shot(shot, prof, reg, root, prev=prev, compiled_prompt=c)
            out["errors"] += r["errors"]
            out["warnings"] += r["warnings"]
            log = _Log(sid)
            _run(log, _check_window, shot, running, prof["fps"])
            out["errors"] += log.errors
            tl = shot.get("timing_and_lattice")
            ed = tl.get("editorial_frames") if isinstance(tl, dict) else None
            running += ed if isinstance(ed, int) and not isinstance(ed, bool) else 0   # bool is an int: True must not count as 1
            try:
                text = c or compile_fl2va_prompt(shot, reg)["compiled_prompt"]
            except (KeyError, TypeError, ValueError, AttributeError):
                continue  # lint_shot already reported the prompt failure (PR-00 / SL-*)
            try:
                wf = compile_comfyui_workflow(shot, reg, text, False, resolve_keyframes(shot, prev, root))
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                out["errors"].append(f"{sid}: PR-00 workflow could not be compiled: {e!r}")
                continue
            r = lint_workflow(wf, shot, prof)
            out["errors"] += r["errors"]
            out["warnings"] += r["warnings"]
        ep_plan = ep.get("episode_plan")
        if ep_plan is not None and not isinstance(ep_plan, dict):
            out["errors"].append(f"TM-05 episode {ep.get('episode_id')} episode_plan must be an object")
            ep_plan = {}
        target = ep_plan.get("target_editorial_frames") if ep_plan else None
        if target is not None and running != target:
            last = shots[-1].get("shot_id", f"<shot {len(shots)}>") if shots and isinstance(shots[-1], dict) else anchor
            out["errors"].append(f"{last}: TM-05 episode {ep['episode_id']} total editorial {running} != target {target}")
    return out
