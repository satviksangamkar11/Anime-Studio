"""DEVA shots template -> shots with a `look` block (flat mode, WP4 part 4).

  python tools/convert_deva_shots.py IN.json [--out OUT.json] [--pack deva_neon] [--styles-dir DIR]
  python tools/convert_deva_shots.py IN.json --h3 [--h3-profile sing8_864x1536] [--out OUT.json]
  convert(shots, pack) -> shots      (pack = the dict from core.style_pack.load_pack)
  to_h3(shots, profile) -> shots     (profile = the dict from h3.schema_and_linter.load_default_profile)

Flat mode: moves top-level palette_id, grade, hook_type, impact_frames and vfx_tokens into `look`.
grade -> look.act, hook_type -> look.hook (first shot of an episode only), impact names -> at_s seconds,
vfx tokens -> {color, role}. Every other key is kept. Input is not mutated. Output: indent 2, UTF-8, LF.

H3 mode (--h3, A25): runs flat mode, then writes h3 shot JSON that h3/schema_and_linter.py accepts.
The look block moves to metadata.look and converter_notes to metadata.converter_notes (the linter
allows no other top-level keys, SC-01). Values the template lacks get the DECISION defaults below.
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from core.style_pack import load_pack  # noqa: E402
from h3.schema_and_linter import (LATTICE_CUT_BOUNDS, OFFICIAL_CAMERA_MOTION_PHRASES,  # noqa: E402
                                  STAGES, load_default_profile)

HOOK_CAPTION_PLACEHOLDER = "<hook caption>"   # the owner or writer supplies the real caption
TOKEN_ROLE_ALIASES = {"core": "energy"}      # token suffix -> role; any other suffix word is its own role
_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s\b")
_THIRD_EYE = re.compile(r"third[\s_-]*eye", re.I)


def _words(text):
    return [w for w in re.split(r"[^a-z0-9]+", str(text).lower()) if w]


def _neon_colour(token, pal):
    """Name of the first neon colour whose name shares a word with the token, else None."""
    tw = set(_words(token))
    for name, colour in (pal.get("colors") or {}).items():
        if isinstance(colour, dict) and colour.get("neon") is True and tw & set(_words(name)):
            return name
    return None


def _token_role(token, colour, pal, action):
    suffix = _words(token)[-1]
    role = TOKEN_ROLE_ALIASES.get(suffix, suffix)
    for law in pal.get("special_laws") or []:
        if not isinstance(law, dict) or law.get("color") != colour:
            continue
        only = law.get("only_roles") or []
        if suffix == "burn" and "third_eye" in only and _THIRD_EYE.search(action):
            role = "third_eye"
    return role


def _impact_seconds(name, action, seconds):
    """End of the a-b s range whose text holds the most name words (prefix match); ties go to the first range.
    No range matches: middle of the shot."""
    name_words = _words(name)
    best, best_score = None, 0
    parts = [p for p in str(action).split(";")]
    for part in parts:
        m = _RANGE.search(part)
        if not m:
            continue
        part_words = _words(part[m.end():])
        score = sum(1 for w in name_words if any(t.startswith(w) for t in part_words))
        if score > best_score:
            best, best_score = float(m.group(2)), score
    if best is not None:
        return best
    return round(float(seconds) / 2.0, 3) if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else 0.0


def _convert_shot(shot, pack, first_in_episode):
    out = copy.deepcopy(shot)
    notes = []
    pal_id = out.pop("palette_id", None)
    grade = out.pop("grade", None)
    hook_type = out.pop("hook_type", None)
    impacts = out.pop("impact_frames", None) or []
    tokens = out.pop("vfx_tokens", None) or []
    pal = (pack.get("palettes") or {}).get(pal_id) or {}
    acts = pack.get("acts") or {}
    act_phase = (acts.get(grade) or {}).get("phase") if isinstance(grade, str) else None
    action = out.get("action") if isinstance(out.get("action"), str) else ""

    look = {"palette_id": pal_id, "act": grade, "phase": act_phase,
            "focal": (pal.get("characters") or [None])[0], "focal_value": "lightest"}
    if hook_type is not None:
        if first_in_episode:
            look["hook"] = {"type": hook_type, "caption": HOOK_CAPTION_PLACEHOLDER}
            notes.append(f"hook caption is {HOOK_CAPTION_PLACEHOLDER} (placeholder; the owner or writer supplies it)")
        else:
            notes.append(f"hook_type {hook_type!r} dropped: look.hook is allowed on the first shot only")

    look["impact_frames"] = []
    for imp in impacts:
        if not isinstance(imp, dict):
            notes.append(f"impact entry {imp!r} is not an object; dropped")
            continue
        at_s = _impact_seconds(imp.get("at", ""), action, out.get("seconds"))
        look["impact_frames"].append({"at_s": at_s, "type": imp.get("type"), "frames": imp.get("frames")})

    look["vfx"] = []
    for token in tokens:
        colour = _neon_colour(token, pal) if isinstance(token, str) and _words(token) else None
        if colour is None:
            notes.append(f"vfx token {token!r} matches no neon colour of the palette; dropped")
            continue
        look["vfx"].append({"color": colour, "role": _token_role(token, colour, pal, action)})

    look["accent_use"] = False
    look["hold_purpose"] = None
    out["look"] = look
    if notes:
        out["converter_notes"] = notes
    return out


def convert(shots, pack):
    """Return a new list of shots with the look block. Non-dict items pass through unchanged."""
    seen = set()
    result = []
    for shot in shots:
        if not isinstance(shot, dict):
            result.append(copy.deepcopy(shot))
            continue
        ep = shot.get("episode")
        key = json.dumps(ep, sort_keys=True)
        first = key not in seen
        seen.add(key)
        result.append(_convert_shot(shot, pack, first))
    return result


# ---- H3 mode (A25) ----------------------------------------------------------
# DECISIONS (A25). Each default fills an h3 field the DEVA template has no value for.
H3_DEFAULT_PROFILE = "sing8_864x1536"   # h3/profiles/<name>.json: fps, base_resolution, lattice range
DEFAULT_SECONDS = 4                     # used only when a shot's `seconds` is missing or not a positive number
HEAD_DYNAMIC = 12                       # head handle (frames) of a DYNAMIC incoming cut; linter bounds [8, 35]
TAIL_BOUNDS = (24, 47)                  # tail handle (frames) of a DYNAMIC outgoing cut (CN-05)
IMPACT_HALF = 6                         # motion stage 6 spans trim_out -/+ 6 frames (MO-03: trim_out must sit in it)
PF_SECONDS = (4.0, 15.0)                # duration bounds of pixel_frames (PF-04)
SEAM_FIRST = "INTER_REEL_HANDSHAKE"     # first shot of an episode: static incoming seam (trim_in 0, head 0)
SEAM_DYN = "DYNAMIC_MATCH_ON_ACTION"    # every later incoming seam and every outgoing seam
UNSPECIFIED = "unspecified"
UNSET_LOCATION = "UNSET"
POSE_DEFAULT = {"torso_pitch_deg": 0.0, "knee_flex_deg": 0.0, "com_y_ratio": 0.5}
CAMERA_RULES = (  # first match wins; (regex on the lower-cased template camera text, official motion_type)
    (r"\bpush[ -]?in\b", "Push In"), (r"\bpull[ -]?out\b", "Pull Out"),
    (r"\bzoom in\b", "Zoom In"), (r"\bzoom out\b", "Zoom Out"),
    (r"\bpan left\b", "Pan Left"), (r"\bpan right\b", "Pan Right"),
    (r"\btilt[ -]?up\b", "Tilt Up"), (r"\btilt[ -]?down\b", "Tilt Down"),
    (r"\btrack(?:s|ing)?\b", "Tracking Shot"), (r"\bstatic\b", "Static Shot"),
)
H3_CONSUMED = {"id", "episode", "mode", "seconds", "start", "end", "subjects", "camera", "sound", "action",
               "look", "converter_notes"}


def _seconds(value, notes):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return value
    notes.append(f"seconds {value!r} missing or not positive; timing uses {DEFAULT_SECONDS} s (DECISION)")
    return DEFAULT_SECONDS


def _camera(text, notes):
    """(motion_type, compiled_clause). Rule: first CAMERA_RULES keyword in the template camera text.
    The clause is the official phrase for that motion, so CM-02 passes by construction."""
    low = text.lower() if isinstance(text, str) else ""
    for pattern, motion in CAMERA_RULES:
        if re.search(pattern, low):
            return motion, f"The camera {OFFICIAL_CAMERA_MOTION_PHRASES[motion][0]}."
    notes.append(f"camera motion not determinable from template camera text {text!r}; motion_type None")
    return None, ""


def _lattice(ed, head, both_dynamic, fps, lo, hi):
    """Smallest lattice_n whose pixel_frames = 17n+5 gives a tail in TAIL_BOUNDS, a duration in PF_SECONDS,
    and (both-dynamic cuts with a table entry) the LATTICE_CUT_BOUNDS. Returns (n, pixel_frames, note|None)."""
    for n in range(lo, hi + 1):
        pf = 17 * n + 5
        tail = pf - head - ed
        if not PF_SECONDS[0] <= pf / fps <= PF_SECONDS[1] or not TAIL_BOUNDS[0] <= tail <= TAIL_BOUNDS[1]:
            continue
        if both_dynamic and n in LATTICE_CUT_BOUNDS:
            (elo, ehi), (hlo, hhi) = LATTICE_CUT_BOUNDS[n]
            if not (elo <= ed <= ehi and hlo <= head + tail <= hhi):
                continue
        return n, pf, None
    for n in range(lo, hi + 1):  # fallback: shortest clip that holds the editorial part plus a minimal tail
        if 17 * n + 5 >= head + ed + TAIL_BOUNDS[0] and (17 * n + 5) / fps >= PF_SECONDS[0]:
            break
    else:
        n = hi
    return n, 17 * n + 5, (f"no lattice_n in {lo}..{hi} meets the tail, duration and cut bounds for editorial {ed} "
                           f"frames; lattice_n {n} used, linter will flag it")


def _stage_spans(pf, trim_out):
    """Seven contiguous inclusive spans 0..pf. Stage 6 is trim_out -/+ IMPACT_HALF; stages 1-5 split the frames
    before it evenly; stage 7 takes the rest. Rule chosen because the template has no stage timing."""
    lo, hi = max(0, trim_out - IMPACT_HALF), min(pf, trim_out + IMPACT_HALF)
    starts = [i * lo // 5 for i in range(6)]
    spans = [[starts[i], starts[i + 1] - 1] for i in range(5)] + [[lo, hi], [hi + 1, pf]]
    return dict(zip(STAGES, spans))


def _action_stages(action, spans, fps, notes):
    """Template 'a-bs text' segments go to the stage whose span holds the segment midpoint (generation frames)."""
    text = {k: [] for k in STAGES}
    for part in str(action).split(";"):
        m = _RANGE.search(part)
        if not m:
            if part.strip():
                notes.append(f"action part {part.strip()!r} has no a-b s time range; not mapped to a stage")
            continue
        mid = (float(m.group(1)) + float(m.group(2))) / 2.0 * fps
        stage = next((k for k in STAGES if spans[k][0] <= mid <= spans[k][1]), STAGES[-1])
        text[stage].append(part[m.end():].strip(" ,"))
    empty = [k for k in STAGES if not text[k]]
    if empty:
        notes.append("motion stages with no template action text left empty: " + ", ".join(empty))
    return {k: "; ".join(text[k]) for k in STAGES}


def _h3_shot(shot, idx, ep, running, profile):
    """One flat shot -> one h3 shot. Returns (h3_shot, editorial_frames)."""
    fps, base = profile["fps"], list(profile["base_resolution"])
    lo, hi = profile["valid_lattice_n_range"]
    notes = list(shot.get("converter_notes") or [])
    ep_id = f"EP{ep}" if isinstance(ep, int) and not isinstance(ep, bool) else "EP0"
    if ep_id == "EP0":
        notes.append(f"episode {ep!r} is not an int; episode_id EP0 (DECISION)")
    ed = int(round(_seconds(shot.get("seconds"), notes) * fps))
    first = idx == 0
    head = 0 if first else HEAD_DYNAMIC
    n, pf, lnote = _lattice(ed, head, not first, fps, lo, hi)
    if lnote:
        notes.append(lnote)
    to = head + ed
    tail = pf - to

    def sec(frames):
        return round(frames / fps, 2)

    timing = {"lattice_n": n, "pixel_frames": pf, "latent_slots": 5 * n + 2,
              "generation_duration_sec": sec(pf), "exact_generation_duration_sec": sec(pf),
              "prompt_alignment_sec_str": f"{pf / fps:.2f}", "fps": fps,
              "trim_in_frame": head, "trim_out_frame": to, "head_handle_frames": head, "tail_handle_frames": tail,
              "trim_in_sec": sec(head), "trim_out_sec": sec(to), "head_handle_sec": sec(head),
              "tail_handle_sec": sec(tail), "editorial_frames": ed, "editorial_duration_sec": sec(ed),
              "master_reel_frame_window": [running, running + ed],
              "master_reel_window_sec": [sec(running), sec(running + ed)]}
    notes.append("seams, poses and state tags are DECISION defaults; template has no seam data")
    loc = UNSET_LOCATION
    notes.append("location_id UNSET: template world text is not a registry location id")
    subjects = shot.get("subjects")
    if not isinstance(subjects, list):
        notes.append(f"subjects {subjects!r} is not a list; subjects_present []")
    continuity = {
        "location_id": loc, "shot_scale": UNSPECIFIED,
        "subjects_present": [s for s in subjects if isinstance(s, str)] if isinstance(subjects, list) else [],
        "props_present": [], "screen_direction_vector": UNSPECIFIED, "camera_axis_side": UNSPECIFIED,
        "horizon_line_y_ratio": None,
        "incoming_seam_type": SEAM_FIRST if first else SEAM_DYN, "incoming_seam_note": "DECISION default",
        "cut_in_biomechanical_state_tag": UNSPECIFIED, "cut_in_pose_vector": dict(POSE_DEFAULT),
        "outgoing_seam_type": SEAM_DYN, "outgoing_seam_note": "DECISION default",
        "cut_out_biomechanical_state_tag": UNSPECIFIED, "cut_out_pose_vector": dict(POSE_DEFAULT)}

    spans = _stage_spans(pf, to)
    motion = _action_stages(shot.get("action"), spans, fps, notes)
    motion["stage_frame_spans"] = spans
    cadence_a, cadence_b = pf // 3, 2 * pf // 3
    cadence = {"hold_window_frames": [0, cadence_a], "burst_window_frames": [cadence_a + 1, cadence_b],
               "impact_or_settle_frames": [cadence_b + 1, pf], "cadence_clause": ""}
    notes.append("anime_timing_cadence split in thirds and cadence_clause empty (DECISION; template has no cadence)")

    motion_type, clause = _camera(shot.get("camera"), notes)
    camera = {"motion_type": motion_type, "amplitude": "medium_omitted", "speed": "normal_omitted",
              "compiled_clause": clause}

    keyframes = {"mode": shot["mode"].upper() if isinstance(shot.get("mode"), str) else shot.get("mode"),
                 "picture_1_path": shot.get("start"), "picture_2_path": shot.get("end"),
                 "dimensions_verified": base}
    if shot.get("end") is None:
        notes.append("end keyframe missing; picture_2_path None")
    notes.append("dimensions_verified set to profile base_resolution; KF-03 checks the PNG on disk")

    sound = shot.get("sound")
    if not isinstance(sound, str):
        notes.append(f"sound {sound!r} is not a string; overall_soundscape empty")
    sound_plan = {"overall_soundscape": sound if isinstance(sound, str) else "", "non_diegetic_music": "N/A"}
    notes.append("non_diegetic_music N/A (DECISION: no music, owner rule)")

    dialogue = {"has_dialogue": False, "utterances": [], "mouth_state_rule": "Mouths stay closed for the whole shot."}
    notes.append("dialogue none and mouth_state_rule default (DECISION; template has no speech)")

    extra = {k: copy.deepcopy(v) for k, v in shot.items() if k not in H3_CONSUMED}
    if extra:
        notes.append(f"kept in metadata.deva, not mapped to h3 fields: {sorted(extra)}")

    action = shot.get("action")
    h3 = {"shot_id": shot.get("id"), "episode_id": ep_id, "sequence_order": idx + 1,
          "story_beat": action if isinstance(action, str) else "",
          "emotional_objective": UNSPECIFIED, "mute_animatic_verification": False,
          "timing_and_lattice": timing, "continuity_and_seam_lock": continuity, "fl2va_keyframes": keyframes,
          "motion_7_stage": motion, "anime_timing_cadence": cadence, "camera": camera,
          "dialogue_and_lip_lock": dialogue, "sound_plan": sound_plan,
          "metadata": {"look": copy.deepcopy(shot.get("look")), "converter_notes": notes, "deva": extra}}
    return h3, ed


def to_h3(shots, profile):
    """Flat-mode shots (output of convert) -> h3 shot list. Non-dict items pass through. Running frame windows are
    per episode. Input is not mutated."""
    running, count, result = {}, {}, []
    for shot in shots:
        if not isinstance(shot, dict):
            result.append(copy.deepcopy(shot))
            continue
        ep = shot.get("episode")
        key = json.dumps(ep, sort_keys=True)
        idx, run = count.get(key, 0), running.get(key, 0)
        h3, ed = _h3_shot(shot, idx, ep, run, profile)
        count[key], running[key] = idx + 1, run + ed
        result.append(h3)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert a DEVA shots template to shots with a look block (flat mode), "
                                             "or to h3 shot JSON (--h3).")
    ap.add_argument("inp")
    ap.add_argument("--out", default=None, help="output file (default: print to stdout)")
    ap.add_argument("--pack", default="deva_neon")
    ap.add_argument("--styles-dir", default=None)
    ap.add_argument("--h3", action="store_true", help="write h3 shot JSON instead of flat shots")
    ap.add_argument("--h3-profile", default=H3_DEFAULT_PROFILE, help="h3/profiles/<name>.json (default sing8_864x1536)")
    a = ap.parse_args(argv)
    try:
        shots = json.loads(Path(a.inp).read_text(encoding="utf-8"))
        if not isinstance(shots, list):
            raise ValueError("input must be a JSON list of shots")
        pack = load_pack(a.pack, a.styles_dir)
        profile = load_default_profile(a.h3_profile) if a.h3 else None
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out = convert(shots, pack)
    if a.h3:
        out = to_h3(out, profile)
    text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_bytes(text.encode("utf-8"))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
