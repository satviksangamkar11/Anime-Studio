"""Shot schema, rule linter and PNG helpers for the h3 sing8 route. Story-agnostic.

Every error/warning string is "<shot_id>: <CODE> <message>" so tests can assert on codes.
"""
import json
import os
import re
import struct
import zlib

STAGES = ("1_starting_state", "2_anticipation", "3_initiation", "4_drive",
          "5_contact_approach", "6_impact_result", "7_settled_end_state")
CHAINED, INTER, DYN = "CHAINED_POSE_HOLD", "INTER_REEL_HANDSHAKE", "DYNAMIC_MATCH_ON_ACTION"
STATIC_SEAMS = {CHAINED, INTER}
SEAM_TYPES = STATIC_SEAMS | {DYN}
LATTICE_CUT_BOUNDS = {6: ((45, 75), (32, 62)), 7: ((64, 92), (32, 60)),
                      8: ((81, 109), (32, 60)), 10: ((115, 143), (32, 60))}
OFFICIAL_CAMERA_MOTION_PHRASES = {
    "Zoom In": ("zooms in",), "Zoom Out": ("zooms out",), "Push In": ("pushes in",),
    "Pull Out": ("pulls out",), "Pan Left": ("pans left",), "Pan Right": ("pans right",),
    "Truck Left": ("trucks left",), "Truck Right": ("trucks right",),
    "Tilt Up": ("tilts up",), "Tilt Down": ("tilts down",),
    "Pedestal Up": ("pedestals up",), "Pedestal Down": ("pedestals down",),
    "Arc Shot": ("arcs", "moves in an arc"), "Tracking Shot": ("tracks",),
    "Static Shot": ("holds a static shot", "remains static"),
    "Shake Slightly": ("shakes slightly",), "Shake Strongly": ("shakes strongly",),
    "POV": ("point of view", "pov"), "Roll Clockwise": ("rolls clockwise",),
    "Roll Counterclockwise": ("rolls counterclockwise",)}
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
    "fl2va_keyframes": ({"mode", "picture_1_path", "picture_2_path", "dimensions_verified"},
                        {"flow_source_a", "flow_source_b", "reuse_upstream_b_id"}),
    "motion_7_stage": (set(STAGES) | {"stage_frame_spans"}, set()),
    "anime_timing_cadence": (CADENCE_KEYS, set()),
    "camera": (CAMERA_KEYS, set()),
    "dialogue_and_lip_lock": (DIALOGUE_KEYS, set()),
    "sound_plan": (SOUND_KEYS, set()),
}
PROFILE_KEYS = {"route_id", "checkpoint_name", "mode_to_lora_map", "checkpoint_architecture_namespace",
                "runtime_lora_strength", "steps_nfe", "cfg", "sampler_name", "scheduler",
                "model_sampling_av", "fps", "aspect_ratio", "base_resolution",
                "ref_image_size_policy", "min_imd_body_chars", "max_imd_body_chars",
                "max_total_prompt_chars", "valid_lattice_n_range"}
PROMPT_RE = re.compile(
    r"""\AHow the reference pictures align with the target video — Picture 1 \(from Shot 1\) aligns with the 0\.00-second mark of the target video; Picture 2 \(from Shot 1\) aligns with the (?P<sec>\d+\.\d{2})-second mark of the target video\.\n\nintegrated_multimodal_description: (?P<imd>[^\n]+)\noverall_soundscape: (?P<snd>[^\n]*)\nnon_diegetic_music: (?P<music>[^\n]*)\Z""")
PNG_SIG = b"\x89PNG\r\n\x1a\n"

# ID safety pattern: alphanumeric start, then alphanumeric/underscore/hyphen up to 64 chars total
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# SD-02: a soundscape must name at least one sound (whole word, inflections allowed: sounds, ringing, winds)
SOUNDSCAPE_WORD_RE = re.compile(
    r"\b(?:sound|hiss|rustle|splash|wind|water|step|breath|hum|whoosh|roar|crack|thud|drip|flow|ring|voice)\w*",
    re.IGNORECASE)
SOUND_PREFIX = "Sound effects only:"  # fixed words that open every compiled overall_soundscape
BED_MAX_WORDS = 12  # registry.sound_beds phrases: same casing and punctuation, at most 12 words


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
    if own is None:
        # Required key, but guard anyway
        return {"picture_1": None, "picture_2": k.get("picture_2_path"), "reused": False}
    reuse_id = k.get("reuse_upstream_b_id")
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
    w, h = profile["base_resolution"]
    if w % 32 or h % 32:
        out["errors"].append(f"PO-01 base_resolution {w}x{h} is not divisible by 32")
    a, b = (int(x) for x in profile["aspect_ratio"].split(":"))
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
    if head != ti or tail != pf - to or ed != to - ti or not 0 <= ti < to <= pf:
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
    # KF-07 on picture paths and optional flow sources; unsafe paths never reach the disk checks
    safe = {}
    for label, rel in (("picture_1", kf.get("picture_1")), ("picture_2", k.get("picture_2_path")),
                       ("flow_source_a", k.get("flow_source_a")), ("flow_source_b", k.get("flow_source_b"))):
        if rel is not None:
            safe[label] = _check_picture_path(log, label, rel)
    # Disk checks
    for label, rel in (("picture_1", kf.get("picture_1")), ("picture_2", k.get("picture_2_path"))):
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
    """Sanitized bed phrase for the shot's location, or "" when none is defined or it is not a string."""
    loc = (shot.get("continuity_and_seam_lock") or {}).get("location_id")
    bed = sound_beds_of(registry).get(loc)
    return sanitize_single_line(bed) if isinstance(bed, str) else ""


def compiled_soundscape(shot, registry):
    """THE builder of the compiled overall_soundscape: "Sound effects only: <bed> <shot effects>".
    The compiler and the linter (SD-03) both call it. The prefix and the bed are never doubled."""
    raw = (shot.get("sound_plan") or {}).get("overall_soundscape")
    text = sanitize_single_line(raw) if isinstance(raw, str) else ""
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
    soundscape = sanitize_single_line(raw_sc) if isinstance(raw_sc, str) else ""
    # SD-01: soundscape non-empty single sentence, at least 40 chars. It reads the shot's own text, never the
    # compiled one: the prefix and bed would pad an empty soundscape past 40 characters.
    if not soundscape:
        log.err("SD-01", "sound_plan.overall_soundscape must be a non-empty single sentence of at least 40 characters")
    elif len(soundscape) < 40:
        log.err("SD-01", f"sound_plan.overall_soundscape too short ({len(soundscape)} chars), need at least 40")
    # SD-01: non_diegetic_music must be "N/A" unless profile allows model music (owner rule 2026-11-06)
    music = sanitize_single_line(raw_mu) if isinstance(raw_mu, str) else None
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
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            log.err("PR-00", f"prompt could not be compiled: {e!r}")
            return
    text, style = compiled, reg["style_lock"]
    m = PROMPT_RE.match(text)
    if not m:
        log.err("PR-01", "prompt does not match the 4-part layout")
        imd = text
    else:
        imd = m.group("imd")
        pf, fps = shot["timing_and_lattice"]["pixel_frames"], prof["fps"]
        if m.group("sec") != f"{pf / fps:.2f}":
            log.err("PR-01", f"header second mark {m.group('sec')} != {pf / fps:.2f}")
        if not imd.startswith(f"[Shot 1] {sanitize_single_line(style['mandatory_prefix'])}, preserving the exact character design"):
            log.err("PR-01", "description does not start with the mandatory prefix")
    if re.findall(r"\[Shot (\d+)\]", text) != ["1"]:
        log.err("PR-02", "the only [Shot N] tag must be [Shot 1]")
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
    pieces = [sanitize_single_line(shot["anime_timing_cadence"]["cadence_clause"]),
              sanitize_single_line(d["mouth_state_rule"]),
              sanitize_single_line(shot["camera"]["compiled_clause"])]
    pieces += [sanitize_single_line(u["voiceover_action_cue"]) for u in d["utterances"]]
    pieces += re.findall(r"<d>.*?</d>", text)
    for p in pieces:
        if p not in imd:
            log.err("PR-07", f"{p[:60]!r} is not a substring of the description")
    rx = style.get("banned_negative_words_regex")
    if rx and re.search(rx, text, re.I):
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
    lora = prof["mode_to_lora_map"].get(f"{mode}_{prof['checkpoint_architecture_namespace']}")
    if sum(1 for n in nodes.values() if n.get("class_type") == "LoraLoaderModelOnly") != 1:
        log.err("WF-02", "exactly one LoraLoaderModelOnly node is required")
    lo = nodes["2"]["inputs"]
    if lo["lora_name"] != lora or lo["strength_model"] != prof["runtime_lora_strength"]:
        log.err("WF-02", f"LoRA must be {lora!r} at strength {prof['runtime_lora_strength']}, got {lo['lora_name']!r} at {lo['strength_model']}")
    ms = nodes["3"]["inputs"]
    if (sum(1 for n in nodes.values() if n.get("class_type") == "ModelSamplingAV") != 1
            or ms["video_shift"] != prof["model_sampling_av"]["mode_to_video_shift_map"][mode]
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


def lint_shot(shot, profile, registry, asset_root, prev=None, compiled_prompt=None):
    """Per-shot rules. prev = previous shot in the episode (enables cross-shot and reuse rules).
    compiled_prompt: optional already-compiled prompt text (or its compile dict) to check instead of recompiling."""
    sid = shot.get("shot_id", "<shot ?>")
    log = _Log(sid if isinstance(sid, str) else "<shot ?>")
    _validate_id(sid, "shot", log)  # ID-01: the id names files, so it must be path-safe
    if isinstance(compiled_prompt, dict):
        compiled_prompt = compiled_prompt["compiled_prompt"]
    _run(log, _check_keys, shot)
    _run(log, _check_timing, shot, profile)
    _run(log, _check_continuity, shot, profile)
    _run(log, _check_motion, shot)
    _run(log, _check_cadence, shot)
    _run(log, _check_camera, shot)
    _run(log, _check_dialogue, shot, registry)
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


def lint_story(story, compiled=None, asset_root_override=None):
    """Lint every episode. compiled: optional {shot_id: prompt text or compile dict} to check instead of recompiling.
    Story-level structure errors (no registry/episodes) raise KeyError; profile errors are attributed to the first shot."""
    from h3.compile_h3_sing8 import compile_fl2va_prompt, compile_comfyui_workflow  # lazy: avoids import cycle
    reg = story["registry"]
    prof = reg["execution_profile"]
    out = {"errors": [], "warnings": []}
    all_shots = [s for ep in story["episodes"] for s in ep["shots"]]
    anchor = all_shots[0].get("shot_id", "<shot 1>") if all_shots else "<story>"
    pl = lint_profile(prof)
    out["errors"] += [f"{anchor}: {m}" for m in pl["errors"]]
    out["warnings"] += [f"{anchor}: {m}" for m in pl["warnings"]]
    if pl["errors"]:
        return out
    # Check for duplicate shot_ids across the whole story
    seen_ids = {}
    for ep in story["episodes"]:
        for shot in ep["shots"]:
            sid = shot.get("shot_id")
            if not isinstance(sid, str):
                continue  # lint_shot reports the bad id
            if sid in seen_ids:
                out["errors"].append(f"{sid}: ID-01 duplicate shot_id {sid!r} also in episode {seen_ids[sid]}")
            else:
                seen_ids[sid] = ep["episode_id"]
    for ep in story["episodes"]:
        root = asset_root_override or ep["asset_root"]
        shots, running = ep["shots"], 0
        # Validate episode_id
        log_ep = _Log("episode")
        _validate_id(ep.get("episode_id"), "episode", log_ep)
        out["errors"] += log_ep.errors
        out["warnings"] += log_ep.warnings
        for i, shot in enumerate(shots):
            sid = shot.get("shot_id", f"<shot {i + 1}>")
            prev = shots[i - 1] if i else None
            c = (compiled or {}).get(sid)
            if isinstance(c, dict):
                c = c["compiled_prompt"]
            r = lint_shot(shot, prof, reg, root, prev=prev, compiled_prompt=c)
            out["errors"] += r["errors"]
            out["warnings"] += r["warnings"]
            log = _Log(sid)
            _run(log, _check_window, shot, running, prof["fps"])
            out["errors"] += log.errors
            ed = (shot.get("timing_and_lattice") or {}).get("editorial_frames")
            running += ed if isinstance(ed, int) else 0
            try:
                text = c or compile_fl2va_prompt(shot, reg)["compiled_prompt"]
                wf = compile_comfyui_workflow(shot, reg, text, False, resolve_keyframes(shot, prev, root))
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            r = lint_workflow(wf, shot, prof)
            out["errors"] += r["errors"]
            out["warnings"] += r["warnings"]
        target = (ep.get("episode_plan") or {}).get("target_editorial_frames")
        if target is not None and running != target:
            last = shots[-1].get("shot_id", f"<shot {len(shots)}>") if shots else anchor
            out["errors"].append(f"{last}: TM-05 episode {ep['episode_id']} total editorial {running} != target {target}")
    return out
