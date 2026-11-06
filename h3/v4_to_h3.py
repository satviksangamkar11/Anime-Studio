"""V4 writer pack -> H3 story (sing8, pure Foley). Pure functions over dicts; file reads only in convert_pack(path).

Input: a pack folder (shots.json, bible.json, optional stage_1*.json, keyframes/<shot_id>-A.png and -B.png) or a dict
{"shots": [...], "bible": {...}, "stage": {...} (optional), "asset_root": str (optional)}.

What maps: lattice and timing (column 1), continuity text (column 2), reference anchors and hook fields (kept under
registry.v4_rows, environments copied from the bible), per-second directives (column 5) -> the 7 motion stages,
sfx_cues -> sound_plan.overall_soundscape, performance_notes -> the mouth fields. Narration and dialogue are never put
in the H3 prompt (ElevenLabs voices them); they stay in registry.v4_rows.

What does not map: the H3 schema needs seam types, pose vectors, biomechanical tags, cadence windows, shot scale, screen
direction, location and props. The V4 contract has none of them, so they are read from the row's optional
"h3_fields" block. A missing field is reported in `problems` and left empty, so lint_story reports it too.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as `python h3/v4_to_h3.py`: the h3 package sits one folder up
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h3.schema_and_linter import (CHAINED, DYN, OFFICIAL_CAMERA_MOTION_PHRASES, SEAM_TYPES, SFX_CUE_RE, STATIC_SEAMS,
                                  lint_story, load_default_profile)
from h3.shot_table_spec import FPS, lattice

LANGS = ("en", "hi", "mr")
MOTION_WORDS = (("push in", "Push In"), ("pull out", "Pull Out"), ("zoom in", "Zoom In"), ("zoom out", "Zoom Out"),
                ("pan left", "Pan Left"), ("pan right", "Pan Right"), ("truck left", "Truck Left"),
                ("truck right", "Truck Right"), ("tilt up", "Tilt Up"), ("tilt down", "Tilt Down"),
                ("track", "Tracking Shot"), ("hold", "Static Shot"), ("static", "Static Shot"))
H3_FIELDS = ("story_beat", "emotional_objective", "location_id", "shot_scale", "screen_direction_vector",
             "camera_axis_side", "horizon_line_y_ratio", "incoming_seam_type", "outgoing_seam_type",
             "cut_in_biomechanical_state_tag", "cut_out_biomechanical_state_tag", "cut_in_pose_vector",
             "cut_out_pose_vector", "props_present", "hold_window_frames", "burst_window_frames",
             "impact_or_settle_frames", "cadence_clause")
STAGE_NAMES = ("1_starting_state", "2_anticipation", "3_initiation", "4_drive", "5_contact_approach",
               "6_impact_result", "7_settled_end_state")
SEC = lambda frames: round(frames / FPS, 2)  # noqa: E731  (seconds with the 2-decimal rounding the linter checks)


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _text(x):
    return x.strip() if isinstance(x, str) else ""


def _stage_spans(pf):
    """Seven contiguous inclusive frame spans from 0 to pf (the linter's MO-02 layout)."""
    bounds = [round(k * pf / 7) for k in range(8)]
    spans, start = [], 0
    for k in range(7):
        end = pf if k == 6 else bounds[k + 1] - 1
        spans.append([start, end])
        start = end + 1
    return spans


def _motion_of(text):
    low = _text(text).lower()
    for word, motion in MOTION_WORDS:
        if word in low:
            return motion
    return None


def _source(pack):
    """(shots, bible, stage, root, problems). Reads a folder or takes a dict. Never mutates the input."""
    problems = []
    if isinstance(pack, dict):
        return (copy.deepcopy(pack.get("shots")), copy.deepcopy(pack.get("bible")), copy.deepcopy(pack.get("stage") or {}),
                pack.get("asset_root"), problems)
    d = Path(pack)
    shots = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    bible = json.loads((d / "bible.json").read_text(encoding="utf-8"))
    stage = {}
    for p in sorted(d.glob("stage_1*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and ("output_languages" in data or "voice_engine" in data):
            stage = data
            break
    return shots, bible, stage, str(d.resolve()), problems


def _languages(languages, stage, problems):
    if languages is not None:
        langs = list(languages)
    else:
        langs = stage.get("output_languages")
        if not isinstance(langs, list) or not langs:
            problems.append("stage_1: no output_languages found; story has none (pass languages= or --lang)")
            return []
    bad = [c for c in langs if c not in LANGS]
    if bad or len(set(langs)) != len(langs):
        problems.append(f"output_languages {langs} must be a non-repeating subset of {LANGS}")
    return langs


def _exists(root, rel):
    return root is not None and os.path.isfile(os.path.join(root, rel))


def _camera(directives, sid, problems, notes):
    """One official motion per shot (H3 has one camera slot): the motions named by the seconds, in order."""
    motions = []
    for d in directives:
        m = _motion_of(d.get("camera"))
        if m and m not in motions:
            motions.append(m)
    if not motions:
        problems.append(f"{sid}: no camera motion word in per_second_directives.camera (H3 needs one official motion)")
        return {"motion_type": None, "amplitude": "medium_omitted", "speed": "normal_omitted", "compiled_clause": ""}
    if len(motions) > 1:
        problems.append(f"{sid}: camera differs across seconds {motions}; H3 takes one motion per shot, first one used")
    motion = motions[0]
    notes.append(f"{sid}: amplitude and speed not in V4, set to the schema's omitted values")
    return {"motion_type": motion, "amplitude": "medium_omitted", "speed": "normal_omitted",
            "compiled_clause": f"The camera {OFFICIAL_CAMERA_MOTION_PHRASES[motion][0]}."}


def _stages(directives, pf, sid, problems):
    """The 7 action sentences. A second belongs to the stage holding its midpoint; a stage with no second takes the
    nearest one. Each sentence keeps the audio cues of the seconds it covers (SX-01 needs one in every stage)."""
    spans = _stage_spans(pf)
    rows = []
    for d in directives:
        a, b = round(float(d["t0"]) * FPS), round(float(d["t1"]) * FPS)
        rows.append(((a + b) / 2, d))
    out = {}
    for k, (name, (a, b)) in enumerate(zip(STAGE_NAMES, spans)):
        picked = [d for mid, d in rows if a <= mid <= b]
        if not picked and rows:
            centre = (a + b) / 2
            picked = [min(rows, key=lambda r: abs(r[0] - centre))[1]]
        actions = list(dict.fromkeys(_text(d.get("action_pose_expression")).rstrip(".") for d in picked))
        cues = list(dict.fromkeys(_text(d.get("audio_cue")).rstrip(".") for d in picked))
        sentence = "; ".join(x for x in actions if x) + (", with " + " and ".join(x for x in cues if x) if any(cues) else "")
        if not sentence:
            problems.append(f"{sid}: stage {name} has no action or audio_cue in per_second_directives")
        elif not SFX_CUE_RE.search(sentence):
            problems.append(f"{sid}: stage {name} has no sound word H3 recognises (SX-01 vocabulary): {cues}")
        out[name] = sentence.rstrip(".") + "." if sentence else ""
    return out, [list(s) for s in spans]


def _mouth(track, pf, sid, problems):
    pn = track.get("performance_notes") if isinstance(track.get("performance_notes"), dict) else {}
    if pn.get("narrator_mouth_closed") is not True:
        problems.append(f"{sid}: performance_notes.narrator_mouth_closed must be true")
    ms = pn.get("mouth_state") if isinstance(pn.get("mouth_state"), dict) else {}
    states = {}
    for s in range(math.ceil(pf / FPS)):
        v = ms.get(str(s))
        if v is None:
            problems.append(f"{sid}: no mouth_state for second {s} in performance_notes")
        states[str(s)] = v
    open_secs = [k for k, v in states.items() if v == "open_non_verbal_breath"]
    rule = ("The figure's mouth stays closed for the whole shot." if not open_secs else
            "The figure's mouth stays closed except for non-verbal breaths at seconds " + ", ".join(open_secs) + ".")
    return states, rule


def _soundscape(track, sid, problems):
    cues = [c for c in (track.get("sfx_cues") or []) if isinstance(c, dict) and _text(c.get("description"))]
    if not cues:
        problems.append(f"{sid}: no sfx_cues with a description; overall_soundscape is empty")
        return ""
    n = min(4, len(cues))     # SX-01: 1 to 4 sentences; every cue lands in exactly one sentence
    sentences = []
    for j in range(n):
        chunk = [_text(c["description"]).rstrip(".") for c in cues[j * len(cues) // n:(j + 1) * len(cues) // n]]
        text = "; ".join(chunk)
        sentences.append(text[:1].upper() + text[1:] + ".")
    return " ".join(sentences)


def _shot(row, idx, ctx, notes, problems):
    """One H3 shot dict, or None when column 1 is unusable (the reason goes to problems)."""
    sid = row.get("id") if isinstance(row, dict) else None
    if not isinstance(sid, str) or not sid:
        problems.append(f"row {idx}: no shot id; row skipped")
        return None
    t1 = row.get("lattice_n")
    if not (isinstance(t1, int) and not isinstance(t1, bool) and 6 <= t1 <= 20):
        problems.append(f"{sid}: lattice_n {t1!r} is not an int in 6..20; shot skipped")
        return None
    lat = lattice(t1)
    pf = lat["pixel_frames"]
    if row.get("pixel_frames") != pf or row.get("latent_slots") != lat["latent_slots"]:
        problems.append(f"{sid}: pixel_frames/latent_slots do not match lattice_n {t1} ({pf}/{lat['latent_slots']}); lattice used")
    e_sec = row.get("editorial_duration_sec")
    if not _is_num(e_sec) or not 0 < round(e_sec * FPS) <= pf:
        problems.append(f"{sid}: editorial_duration_sec {e_sec!r} must be > 0 and within {SEC(pf)} s; shot skipped")
        return None
    ed = round(e_sec * FPS)
    h3 = row.get("h3_fields") if isinstance(row.get("h3_fields"), dict) else {}
    for k in H3_FIELDS:
        if k not in h3:
            problems.append(f"{sid}: h3_fields.{k} missing (H3-only field, not in the V4 columns)")
    if h3.get("location_id") not in ctx["environments"]:
        problems.append(f"{sid}: h3_fields.location_id {h3.get('location_id')!r} is not an ENV id of the bible")
    seam_in, seam_out = h3.get("incoming_seam_type"), h3.get("outgoing_seam_type")
    for label, seam in (("incoming", seam_in), ("outgoing", seam_out)):
        if seam not in SEAM_TYPES:
            problems.append(f"{sid}: h3_fields.{label}_seam_type {seam!r} is not a known seam type")
    if DYN in (seam_in, seam_out):
        problems.append(f"{sid}: dynamic seam needs head/tail handles; V4 has no handle fields, handles set to 0")
    if seam_out in STATIC_SEAMS and ed != pf:
        problems.append(f"{sid}: static outgoing seam needs the full {pf} frames; editorial is {ed}")

    # keyframes: own boundary files first; CHAINED incoming takes picture_1 from the previous shot's picture_2
    prev = ctx["prev"]
    p2 = f"keyframes/{sid}-B.png" if _exists(ctx["root"], f"keyframes/{sid}-B.png") else None
    p1 = f"keyframes/{sid}-A.png" if _exists(ctx["root"], f"keyframes/{sid}-A.png") else None
    if p1 is None and seam_in == CHAINED and prev is not None:
        p1 = prev["fl2va_keyframes"].get("picture_2_path")
    if p1 is None or p2 is None:
        problems.append(f"{sid}: boundary frames missing (keyframes/{sid}-A.png, -B.png); FL2VA needs both")
    kf = {"mode": "FL2VA", "dimensions_verified": list(ctx["profile"]["base_resolution"])}
    kf.update({k: v for k, v in (("picture_1_path", p1), ("picture_2_path", p2)) if v is not None})

    track = row.get("audio_and_dialogue_track") if isinstance(row.get("audio_and_dialogue_track"), dict) else {}
    directives = row.get("per_second_directives") if isinstance(row.get("per_second_directives"), list) else []
    if not directives:
        problems.append(f"{sid}: per_second_directives empty; motion_7_stage cannot be filled")
    for j, d in enumerate(directives):
        if not (isinstance(d, dict) and _is_num(d.get("t0")) and _is_num(d.get("t1"))):
            problems.append(f"{sid}: per_second_directives[{j}] needs numeric t0 and t1")
            directives = []
            break
    stage_text, spans = _stages(directives, pf, sid, problems) if directives else ({k: "" for k in STAGE_NAMES}, _stage_spans(pf))
    for name in STAGE_NAMES:
        if not stage_text[name]:
            problems.append(f"{sid}: motion stage {name} has no text")
    mouth, mouth_rule = _mouth(track, pf, sid, problems)
    cont = row.get("continuity_handoff") if isinstance(row.get("continuity_handoff"), dict) else {}
    positions = row.get("reference_anchors", {}).get("character_positions") if isinstance(row.get("reference_anchors"), dict) else []
    subjects = [c["id"] for c in positions or [] if isinstance(c, dict) and isinstance(c.get("id"), str)]
    for cid in subjects:
        if cid not in ctx["characters"]:
            problems.append(f"{sid}: character {cid} is not in the bible characters")

    running = ctx["running"]
    timing = {"lattice_n": t1, "pixel_frames": pf, "latent_slots": lat["latent_slots"], "generation_duration_sec": SEC(pf),
              "exact_generation_duration_sec": SEC(pf), "prompt_alignment_sec_str": f"{pf / FPS:.2f}", "fps": FPS,
              "trim_in_frame": 0, "trim_out_frame": ed, "head_handle_frames": 0, "tail_handle_frames": pf - ed,
              "trim_in_sec": 0.0, "trim_out_sec": SEC(ed), "head_handle_sec": 0.0, "tail_handle_sec": SEC(pf - ed),
              "editorial_frames": ed, "editorial_duration_sec": SEC(ed),
              "master_reel_frame_window": [running, running + ed],
              "master_reel_window_sec": [SEC(running), SEC(running + ed)]}
    camera = _camera(directives, sid, problems, notes)
    sid_char = h3.get("cut_in_biomechanical_state_tag")
    shot = {
        "shot_id": sid, "episode_id": ctx["episode_id"], "sequence_order": idx,
        "story_beat": h3.get("story_beat"), "emotional_objective": h3.get("emotional_objective"),
        "mute_animatic_verification": False,
        "timing_and_lattice": timing,
        "continuity_and_seam_lock": {
            "location_id": h3.get("location_id"), "shot_scale": h3.get("shot_scale"), "subjects_present": subjects,
            "props_present": h3.get("props_present"), "screen_direction_vector": h3.get("screen_direction_vector"),
            "camera_axis_side": h3.get("camera_axis_side"), "horizon_line_y_ratio": h3.get("horizon_line_y_ratio"),
            "incoming_seam_type": seam_in, "incoming_seam_note": _text(cont.get("incoming")),
            "cut_in_biomechanical_state_tag": sid_char, "cut_in_pose_vector": h3.get("cut_in_pose_vector"),
            "outgoing_seam_type": seam_out, "outgoing_seam_note": _text(cont.get("outgoing")),
            "cut_out_biomechanical_state_tag": h3.get("cut_out_biomechanical_state_tag"),
            "cut_out_pose_vector": h3.get("cut_out_pose_vector")},
        "fl2va_keyframes": kf,
        "motion_7_stage": {**stage_text, "stage_frame_spans": {k: s for k, s in zip(STAGE_NAMES, spans)}},
        "anime_timing_cadence": {"hold_window_frames": h3.get("hold_window_frames"),
                                 "burst_window_frames": h3.get("burst_window_frames"),
                                 "impact_or_settle_frames": h3.get("impact_or_settle_frames"),
                                 "cadence_clause": h3.get("cadence_clause")},
        "camera": camera,
        "dialogue_and_lip_lock": {"has_dialogue": False, "utterances": [], "mouth_state_rule": mouth_rule,
                                  "narrator_mouth_closed": True, "mouth_state": mouth},
        "sound_plan": {"overall_soundscape": _soundscape(track, sid, problems), "non_diegetic_music": "N/A"},
    }
    return shot


def convert_pack(pack_dir_or_dicts, *, languages=None, profile="sing8_864x1536"):
    """Returns {"story": {...}, "problems": [...], "notes": [...]}. Problems are data the H3 story cannot take as is;
    lint_story(story) reports the same gaps as rule codes. The input is never changed."""
    shots, bible, stage, root, problems = _source(pack_dir_or_dicts)
    notes = []
    if not isinstance(shots, list) or not isinstance(bible, dict):
        problems.append("shots.json and bible.json are required (a list of rows and a bible object)")
        return {"story": None, "problems": problems, "notes": notes}
    langs = _languages(languages, stage, problems)
    prof = load_default_profile(profile)
    chars_in = bible.get("characters") if isinstance(bible.get("characters"), dict) else {}
    characters = {}
    for cid, c in chars_in.items():
        name = _text(c.get("name")) if isinstance(c, dict) else ""
        if not name:
            problems.append(f"{cid}: bible character has no name (used as short_disambiguator)")
        characters[cid] = {"short_disambiguator": name or cid}
    style = bible.get("style_lock") if isinstance(bible.get("style_lock"), dict) else {}
    prefix = _text(style.get("prefix")).rstrip(".")
    if not prefix:
        problems.append("bible style_lock.prefix missing: no mandatory style prefix for the prompt")
    registry = {"execution_profile": prof,
                "style_lock": {"mandatory_prefix": prefix,
                               "banned_style_tokens": [t for t in bible.get("forbidden_looks") or [] if isinstance(t, str)]},
                "characters": characters,
                "environments": bible.get("environments") or {}, "props": bible.get("props") or {}, "v4_rows": {}}
    ctx = {"root": root, "profile": prof, "characters": characters, "environments": registry["environments"],
           "running": 0, "prev": None, "episode_id": None}
    episodes, order = {}, []
    for idx, row in enumerate(shots, 1):
        ep = row.get("episode") if isinstance(row, dict) else None
        if ep is None:
            problems.append(f"row {idx}: no episode number; row skipped")
            continue
        if ep not in episodes:
            episodes[ep] = {"episode_id": f"EP{ep}", "asset_root": root, "shots": [], "episode_plan": {}}
            order.append(ep)
            ctx["running"] = 0
            ctx["prev"] = None
        ctx["episode_id"] = episodes[ep]["episode_id"]
        ep_shots = episodes[ep]["shots"]
        ctx["prev"] = ep_shots[-1] if ep_shots else None
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            registry["v4_rows"][row["id"]] = copy.deepcopy(row)
        shot = _shot(row, len(ep_shots) + 1, ctx, notes, problems)
        if shot is None:
            continue
        ep_shots.append(shot)
        ctx["running"] += shot["timing_and_lattice"]["editorial_frames"]
        ctx["prev"] = shot
    for ep in order:
        ep_data = episodes[ep]
        total = sum(s["timing_and_lattice"]["editorial_frames"] for s in ep_data["shots"])
        ep_data["episode_plan"] = {"target_editorial_frames": total}
    notes.append("narration and dialogue are not in the H3 prompt (pure Foley); they stay in registry.v4_rows")
    story = {"output_languages": langs, "output_language": langs[0] if langs else None,
             "registry": registry, "episodes": [episodes[ep] for ep in order]}
    if isinstance(stage.get("voice_engine"), dict):
        story["voice_engine"] = copy.deepcopy(stage["voice_engine"])   # metadata only: never switches H3 speech on
    return {"story": story, "problems": problems, "notes": notes}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Convert a V4 writer pack to an H3 story and lint it.")
    ap.add_argument("pack_dir")
    ap.add_argument("--out", help="write the H3 story JSON here")
    ap.add_argument("--lang", help="output languages, e.g. en,hi,mr (default: stage_1 file)")
    args = ap.parse_args(argv)
    if not os.path.isfile(os.path.join(args.pack_dir, "shots.json")):
        print(f"no shots.json in {args.pack_dir}", file=sys.stderr)
        return 2
    languages = None
    if args.lang:
        languages = [c.strip() for c in args.lang.split(",") if c.strip()]
        if not languages or any(c not in LANGS for c in languages):
            print(f"--lang must be a list of {','.join(LANGS)}", file=sys.stderr)
            return 2
    try:
        res = convert_pack(args.pack_dir, languages=languages)
    except (OSError, ValueError, KeyError) as exc:
        print(f"pack could not be read: {exc!r}", file=sys.stderr)
        return 2
    if res["story"] is None:
        for p in res["problems"]:
            print("PROBLEM", p)
        return 2
    try:
        lint = lint_story(res["story"])
        lint_errors = lint["errors"]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        lint_errors = [f"lint could not run: {exc!r}"]
    for p in res["problems"]:
        print("PROBLEM", p)
    for e in lint_errors:
        print("LINT", e)
    for n in res["notes"]:
        print("NOTE", n)
    if args.out:
        Path(args.out).write_text(json.dumps(res["story"], indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"story -> {args.out}")
    clean = not res["problems"] and not lint_errors
    print("OK: converted and lint clean" if clean else f"{len(res['problems'])} problem(s), {len(lint_errors)} lint error(s)")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
