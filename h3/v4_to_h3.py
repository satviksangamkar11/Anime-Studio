"""V4 writer pack -> H3 story (sing8, pure Foley). Pure functions over dicts; file reads only in convert_pack(path).

Input: a pack folder (shots.json, bible.json, optional stage_1*.json, keyframes/<shot_id>-A.png and -B.png, optional
h3_authored/<shot_id>.json) or a dict {"shots": [...], "bible": {...}, "stage": {...} (optional), "asset_root": str (optional)}.

What maps: lattice and timing (column 1), continuity text (column 2), reference anchors and hook fields (kept under
registry.v4_rows, environments copied from the bible), per-second directives (column 5) -> the 7 motion stages,
sfx_cues -> sound_plan.overall_soundscape, performance_notes -> the mouth fields. Narration and dialogue are never put
in the H3 prompt (ElevenLabs voices them); they stay in registry.v4_rows.

The H3-only fields (research/DECISION_H3_FIELDS_2026-11-07.md) come from three tiers, per field, first hit wins:
  1. explicit row["h3_fields"] (backward compatible),
  2. derive_fields(): deterministic tier 1 (seam types, trim and handles, location, props, story_beat, picture paths),
  3. authored results: h3/h3_author.py (a model, cached in <pack>/h3_authored/<shot_id>.json, valid only while the hash
     of row, derived fields, blueprint and bible subset is unchanged).
A field that no tier provides stays empty and is reported in `problems`; lint_story reports it too.
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

from h3.asset_manifest import canonical_json, hash_frame_file, sha256_text
from h3.schema_and_linter import (CAMERA_MOVE_CLAUSES, CHAINED, DYN, ID_PATTERN, INTER, LATTICE_CUT_BOUNDS, OFFICIAL_CAMERA_MOTION_PHRASES,
                                  SEAM_TYPES, SFX_CUE_RE, STATIC_SEAMS, lint_story, load_default_profile, sx02_problems)
from h3.shot_table_spec import FPS, lattice

LANGS = ("en", "hi", "mr")
MOTION_WORDS = (("push in", "Push In"), ("pull out", "Pull Out"), ("pull back", "Pull Out"), ("crane down", "Pedestal Down"), ("crane up", "Pedestal Up"),
                ("arc ", "Arc Shot"), ("zoom in", "Zoom In"), ("zoom out", "Zoom Out"),
                ("pan left", "Pan Left"), ("pan right", "Pan Right"), ("truck left", "Truck Left"),
                ("truck right", "Truck Right"), ("tilt up", "Tilt Up"), ("tilt down", "Tilt Down"),
                ("track", "Tracking Shot"), ("hold", "Static Shot"), ("static", "Static Shot"))
H3_FIELDS = ("story_beat", "emotional_objective", "location_id", "shot_scale", "screen_direction_vector",
             "camera_axis_side", "horizon_line_y_ratio", "incoming_seam_type", "outgoing_seam_type",
             "cut_in_biomechanical_state_tag", "cut_out_biomechanical_state_tag", "cut_in_pose_vector",
             "cut_out_pose_vector", "props_present", "hold_window_frames", "burst_window_frames",
             "impact_or_settle_frames", "cadence_clause")
DERIVED_FIELDS = ("story_beat", "location_id", "props_present", "incoming_seam_type", "outgoing_seam_type")
AUTHOR_FIELDS = ("emotional_objective", "shot_scale", "screen_direction_vector", "camera_axis_side",
                 "horizon_line_y_ratio", "cut_in_biomechanical_state_tag", "cut_out_biomechanical_state_tag",
                 "cut_in_pose_vector", "cut_out_pose_vector", "hold_window_frames", "burst_window_frames",
                 "impact_or_settle_frames", "cadence_clause")
HEAD_HANDLE = (8, 35)          # CN-04
TAIL_HANDLE = (24, 47)         # CN-05
AUTHORED_DIR = "h3_authored"
BIBLE_KEYS_FOR_HASH = ("characters", "environments", "props", "style_lock", "forbidden_looks")
STAGE_NAMES = ("1_starting_state", "2_anticipation", "3_initiation", "4_drive", "5_contact_approach",
               "6_impact_result", "7_settled_end_state")
SEC = lambda frames: round(frames / FPS, 2)  # noqa: E731  (seconds with the 2-decimal rounding the linter checks)


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)  # JSON Infinity/NaN are not timings


def _text(x):
    return x.strip() if isinstance(x, str) else ""


def _id_set(ids):
    return "{" + ", ".join(sorted(set(ids))) + "}"


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
        if isinstance(data, dict) and ("output_languages" in data or "voice_engine" in data or "story_gate_checks" in data):
            stage = data
            break
    if not stage:   # the V4 writer keeps languages and voice engines in the story's story.json (audit 11-08), not in stage_1
        try:
            story = json.loads((d.resolve().parent / "story.json").read_text(encoding="utf-8"))
            stage = {k: story[k] for k in ("output_languages", "voice_engine") if isinstance(story, dict) and k in story}
        except (OSError, ValueError):
            pass
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


def _camera_from_sheet(sheet, ti=0):
    """M-03: the one camera sentence of a blocking/1.1 sheet: the camera.move enum phrase plus ', because <motivation>',
    or 'The camera stays locked'; a shake only as '; a short shake at second N' (clip second). ti = head handle frames."""
    cam = sheet.get("camera") if isinstance(sheet.get("camera"), dict) else {}
    motion, clause = CAMERA_MOVE_CLAUSES.get(cam.get("move"), CAMERA_MOVE_CLAUSES[None])
    why = _text(cam.get("motivation")).rstrip(".")
    if why:
        clause += ", because " + why
    shake = cam.get("shake")
    if isinstance(shake, dict) and _is_num(shake.get("t")):
        clause += f"; a short shake at second {round(shake['t'] + ti / FPS, 1):g}"
    return {"motion_type": motion, "amplitude": "medium_omitted", "speed": "normal_omitted",
            "compiled_clause": clause + "."}


def _time_point(t):
    """Seconds as a half-second tick: 0 -> '0', 2.4 -> '2.5'."""
    return f"{round(t * 2) / 2:g}"


def _lead(text):
    """Lower-case a leading article so 'At second 3, the figure ...' reads right; names keep their capital."""
    for art in ("The ", "A ", "An "):
        if text.startswith(art):
            return text[0].lower() + text[1:]
    return text


# M-32: time points are opt-in (profile time_points); off = natural sequencing words, no time number
SEQ_LEADS = ("First, ", "Then, ", "As that settles, ", "While that continues, ", "Next, ", "Later, ",
             "Toward the end, ")


def _stages(directives, pf, sid, problems, ti=0, beats=None, hold_names=(), time_points=False):
    """The 7 action sentences, each starting with ONE time point ('At second 2.5,'; stage 7 'By second N,'; never a range).
    The point is the start of the stage span, or the clip time of a blocking beat that falls inside the span (beats[].t is
    editorial time; ti = head handle frames). A second belongs to the stage holding its midpoint; a stage with no second
    takes the nearest one. A stage with nothing new holds: '<name> does not move.' per hold_names (M-03).
    Audio cues are NOT in these sentences (D1 = B, M-01): _stage_cues() sends them to overall_soundscape."""
    spans = _stage_spans(pf)
    beat_t = sorted(float(b["t"]) + ti / FPS for b in beats or [] if isinstance(b, dict) and _is_num(b.get("t")))
    points, prev_pt = [], 0.0
    for k, (a, b) in enumerate(spans):
        inside = [t for t in beat_t if a <= round(t * FPS) <= b]
        pt = 0.0 if k == 0 else max(prev_pt + 0.5, float(_time_point(inside[0] if inside else a / FPS)))
        points.append(pt)
        prev_pt = pt
    rows = []
    for d in directives:
        a, b = round(float(d["t0"]) * FPS) + ti, round(float(d["t1"]) * FPS) + ti   # editorial time -> clip frames: the head handle comes first
        rows.append(((a + b) / 2, d))
    out, used = {}, set()   # M-01b: an action is emitted once in the whole description (duplicate guard)
    for k, (name, (a, b)) in enumerate(zip(STAGE_NAMES, spans)):
        picked = [d for mid, d in rows if a <= mid <= b]
        if not picked and rows:
            centre = (a + b) / 2
            picked = [min(rows, key=lambda r: abs(r[0] - centre))[1]]
        texts = [_text(d.get("action_pose_expression")).rstrip(".") for d in picked]
        if not any(texts):
            problems.append(f"{sid}: stage {name} has no action in per_second_directives")
        fresh = [t for t in dict.fromkeys(texts) if t and t.lower() not in used]
        if not fresh and rows:
            centre = (a + b) / 2
            spare = [(abs(mid - centre), _text(d.get("action_pose_expression")).rstrip(".")) for mid, d in rows]
            spare = [t for _, t in sorted(spare) if t and t.lower() not in used]
            fresh = spare[:1]
        lead = (("By" if k == 6 else "At") + f" second {points[k]:g}, ") if time_points else SEQ_LEADS[k]
        if fresh:
            used.update(t.lower() for t in fresh)
            out[name] = lead + _lead("; ".join(fresh).rstrip(".")) + "."
        else:   # nothing new left for this stage: each held person names their stillness (unique by its time point)
            who = "; ".join(f"{n} does not move" for n in hold_names) or "the scene holds still"
            out[name] = lead + who + "."
    return out, [list(s) for s in spans]


def _mouth(track, pf, sid, problems, ed=None, ti=0):
    """mouth_state keyed by CLIP second (MO-01). The V4 row keys it by EDITORIAL second, and the clip starts `ti` frames
    (the head handle) before the editorial start, so each clip second takes the state of the editorial second holding its
    midpoint; a second made only of handle frames (before the cut-in or after the editorial end) is never seen: closed."""
    pn = track.get("performance_notes") if isinstance(track.get("performance_notes"), dict) else {}
    if pn.get("narrator_mouth_closed") is not True:
        problems.append(f"{sid}: performance_notes.narrator_mouth_closed must be true")
    ms = pn.get("mouth_state") if isinstance(pn.get("mouth_state"), dict) else {}
    states = {}
    for s in range(math.ceil(pf / FPS)):
        mid = (s * FPS + min(s * FPS + FPS, pf)) / 2 - ti          # editorial frame of this clip second's midpoint
        if ed is not None and not 0 <= mid < ed:
            states[str(s)] = "closed"
            continue
        e = int(mid // FPS) if mid >= 0 else 0
        v = ms.get(str(e))
        if v is None:
            problems.append(f"{sid}: no mouth_state for second {e} in performance_notes")
        states[str(s)] = v
    # M-01: the breath exception is gone. The prompt's mouth sentence is per person (prompt_hygiene.mouth_sentence, from
    # the blocking speaks flags), so this rule text is only kept for the record and is not emitted.
    return states, "The figure's mouth stays closed for the whole shot."


def _stage_cues(directives):
    """[(t, text)] of the per-second audio_cue values (D1 = B: they leave the action sentences for the soundscape)."""
    out = []
    for d in directives:
        text = _text(d.get("audio_cue")).rstrip(".")
        if text:
            out.append((float(d["t0"]), text))
    return out


def _time_of(cue):
    """Start second of a V4 sfx cue from its time_range ('1.0-1.5s' -> 1.0); 0 when there is none."""
    m = re.search(r"\d+(?:\.\d+)?", _text(cue.get("time_range")))
    return float(m.group(0)) if m else 0.0


def _soundscape(track, sid, problems, extra=()):
    """overall_soundscape: the V4 sfx cues plus the stage cues (extra = [(t, text)]), in t order, duplicates dropped.
    Packed into 1-4 sentences: 'First <cue>; then <cue>; finally <cue>.' (SX-01: 1 to 4 sentences)."""
    cues = [(_time_of(c), _text(c.get("description")).rstrip(".")) for c in (track.get("sfx_cues") or [])
            if isinstance(c, dict) and _text(c.get("description"))]
    cues += [(float(t), text) for t, text in extra if text]
    items, seen = [], set()
    for _, text in sorted(cues, key=lambda c: c[0]):
        if text.lower() not in seen:
            seen.add(text.lower())
            items.append(text)
    if not items:
        problems.append(f"{sid}: no sfx_cues with a description; overall_soundscape is empty")
        return ""
    n = len(items)
    labelled = [items[0] if n == 1 else
                (f"First {items[0]}" if i == 0 else f"finally {text}" if i == n - 1 else f"then {text}")
                for i, text in enumerate(items)]
    size = math.ceil(n / 4)   # at most 4 sentences
    sentences = []
    for j in range(0, n, size):
        text = "; ".join(labelled[j:j + size])
        sentences.append(text[:1].upper() + text[1:] + ".")
    return " ".join(sentences)


# ---------- timing, grouping, tier 1 ----------

def _timing_inputs(row, sid):
    """(lattice_n, pixel_frames, editorial_frames, None) or (None, None, None, reason) for an unusable column 1."""
    t1 = row.get("lattice_n")
    if not (isinstance(t1, int) and not isinstance(t1, bool) and 6 <= t1 <= 20):
        return None, None, None, f"{sid}: lattice_n {t1!r} is not an int in 6..20; shot skipped"
    pf = lattice(t1)["pixel_frames"]
    e_sec = row.get("editorial_duration_sec")
    if not _is_num(e_sec) or not 0 < round(e_sec * FPS) <= pf:
        return None, None, None, (f"{sid}: editorial_duration_sec {e_sec!r} must be > 0 and within {SEC(pf)} s; "
                                  "shot skipped")
    return t1, pf, round(e_sec * FPS), None


def group_rows(shots):
    """(items, problems). One item per row that has an episode, in row order, its neighbours inside the episode:
    {idx, row, ep, prev, next, first, last}. first/last = first/last row of the episode (the reel)."""
    problems, valid, by_ep = [], [], {}
    for idx, row in enumerate(shots, 1):
        ep = row.get("episode") if isinstance(row, dict) else None
        if ep is None:
            problems.append(f"row {idx}: no episode number; row skipped")
            continue
        valid.append((idx, row, ep))
        by_ep.setdefault(ep, []).append((idx, row))
    items = []
    for idx, row, ep in valid:
        group = by_ep[ep]
        pos = next(k for k, (i, _) in enumerate(group) if i == idx)
        items.append({"idx": idx, "row": row, "ep": ep,
                      "prev": group[pos - 1][1] if pos > 0 else None,
                      "next": group[pos + 1][1] if pos + 1 < len(group) else None,
                      "first": pos == 0, "last": pos == len(group) - 1})
    return items, problems


def _seam_defaults(is_first, is_last, ed, pf):
    """Seam types when the row says nothing: the first shot of a reel takes the INTER handshake, the last shot gives it;
    between them a cut is DYNAMIC when the editorial length is shorter than the lattice, CHAINED when it fills it."""
    inc = INTER if is_first else (DYN if ed < pf else CHAINED)
    out = INTER if is_last else (DYN if ed < pf else CHAINED)
    return inc, out


def _static_plan(pf, ed):
    return {"trim_in_frame": 0, "trim_out_frame": ed, "head_handle_frames": 0, "tail_handle_frames": pf - ed}


def _plan_handles(sid, pf, ed, inc, out, n):
    """Trim and handle frames from the seam types and the editorial length. Returns (plan, problems). plan always has the
    four frame fields; when no split fits, the static plan is returned and the problem names the cause (the linter then
    reports the same cut as CN-03..06)."""
    a6, b6 = _stage_spans(pf)[5]
    dyn_in, dyn_out = inc == DYN, out == DYN
    if not dyn_in and not dyn_out:
        if ed == pf:
            return {"trim_in_frame": 0, "trim_out_frame": pf, "head_handle_frames": 0, "tail_handle_frames": 0}, []
        return _static_plan(pf, ed), [f"{sid}: static seams ({inc}, {out}) need the full {pf} frames; editorial is {ed}"]
    if dyn_in and dyn_out:
        H = pf - ed
        best = None
        for tail in range(TAIL_HANDLE[0], TAIL_HANDLE[1] + 1):
            head, to = H - tail, pf - tail
            if HEAD_HANDLE[0] <= head <= HEAD_HANDLE[1] and a6 <= to <= b6:
                score = (abs(to - (a6 + b6) / 2), -tail)     # cut point nearest the middle of 6_impact_result, then longer tail
                if best is None or score < best[0]:
                    best = (score, head, tail, to)
        if best is None:
            return _static_plan(pf, ed), [
                f"{sid}: no dynamic split fits: head 8..35 and tail 24..47 frames, trim_out inside the 6_impact_result span "
                f"{a6}..{b6}, must add up to {H} (pixel {pf} - editorial {ed}); the V4 editorial length cannot be cut"]
        _, head, tail, to = best
        probs = []
        if n in LATTICE_CUT_BOUNDS:
            (elo, ehi), (hlo, hhi) = LATTICE_CUT_BOUNDS[n]
            if not (elo <= ed <= ehi and hlo <= H <= hhi):
                probs.append(f"{sid}: both-dynamic cut at n={n} needs editorial {elo}..{ehi} and handle sum {hlo}..{hhi}; "
                             f"V4 gives editorial {ed} and handle sum {H}")
        return {"trim_in_frame": head, "trim_out_frame": to, "head_handle_frames": head, "tail_handle_frames": tail}, probs
    if dyn_in:   # outgoing static: trim_out is the full lattice, so the head is the whole difference
        head = pf - ed
        if not HEAD_HANDLE[0] <= head <= HEAD_HANDLE[1]:
            return _static_plan(pf, ed), [f"{sid}: incoming DYNAMIC head handle {head} outside 8..35 frames (editorial {ed} "
                                          f"of pixel {pf}; with a static outgoing cut the head is pixel - editorial)"]
        return {"trim_in_frame": head, "trim_out_frame": pf, "head_handle_frames": head, "tail_handle_frames": 0}, []
    tail, probs = pf - ed, []   # incoming static: trim_in 0, the tail is the whole difference
    if not TAIL_HANDLE[0] <= tail <= TAIL_HANDLE[1]:
        probs.append(f"{sid}: outgoing DYNAMIC tail handle {tail} outside 24..47 frames (editorial {ed} of pixel {pf})")
    if not a6 <= ed <= b6:
        probs.append(f"{sid}: MO-03 trim_out {ed} must sit inside the 6_impact_result span {a6}..{b6} for a dynamic outgoing cut")
    return {"trim_in_frame": 0, "trim_out_frame": ed, "head_handle_frames": 0, "tail_handle_frames": tail}, probs


def fit_lattice(shots):
    """Re-pick lattice_n / pixel_frames / latent_slots of every row so that H3 can cut it (audit gap 2, 2026-11-08).

    The writer used to take the smallest lattice that holds the editorial length, which leaves 4..14 spare frames; a cut
    needs a head handle of 8..35 and a tail handle of 24..47 frames (CN-04/05), so such a row can never be rendered.
    Pure and deterministic, no model call: rows are taken in reel order; a row keeps its n when that already gives a legal
    handle plan whose seam class matches the previous cut, else the smallest n that does. editorial_duration_sec, the
    per-second directives and the narration never change (only frames the viewer never sees are added).
    Returns (new_shots, changes, problems); changes = ["SHOT-002: n 7 -> 9 (pixel 124 -> 158)"]."""
    from h3.shot_table_spec import LATTICE_N_MAX, LATTICE_N_MIN
    out = copy.deepcopy(shots)
    changes, problems = [], []
    items, _ = group_rows(out)
    prev_out = {}
    for it in items:
        row, ep = it["row"], it["ep"]
        sid, e_sec = row.get("id"), row.get("editorial_duration_sec")
        if not _is_num(e_sec) or e_sec <= 0:
            continue
        ed = round(e_sec * FPS)
        cur = row.get("lattice_n")
        cands = ([cur] if isinstance(cur, int) and not isinstance(cur, bool) and LATTICE_N_MIN <= cur <= LATTICE_N_MAX else [])             + [n for n in range(LATTICE_N_MIN, LATTICE_N_MAX + 1) if n != cur]
        chosen, why = None, ""
        if it["first"] and it["last"]:                       # a one-shot reel has no cut inside it: keep the model's n
            if cands and lattice(cands[0])["pixel_frames"] >= ed:
                prev_out[ep] = INTER
                continue
        for n in cands:
            pf = lattice(n)["pixel_frames"]
            if pf < ed:
                continue
            inc, outt = _seam_defaults(it["first"], it["last"], ed, pf)
            before = prev_out.get(ep)
            if before is not None and (before in STATIC_SEAMS) != (inc in STATIC_SEAMS):
                why = f"seam class of the cut from the previous shot ({before} -> {inc})"
                continue
            _, probs = _plan_handles(sid, pf, ed, inc, outt, n)
            if probs:
                why = probs[0]
                continue
            chosen = (n, outt)
            break
        if chosen is None:
            problems.append(f"{sid}: no lattice n in {LATTICE_N_MIN}..{LATTICE_N_MAX} gives a legal cut ({why})")
            continue
        n, outt = chosen
        prev_out[ep] = outt
        if n != cur:
            L = lattice(n)
            changes.append(f"{sid}: n {cur} -> {n} (pixel {row.get('pixel_frames')} -> {L['pixel_frames']})")
            row["lattice_n"], row["pixel_frames"], row["latent_slots"] = n, L["pixel_frames"], L["latent_slots"]
    return out, changes, problems


def _own_keyframe(keyframes_dir, sid, letter):
    if not keyframes_dir or not isinstance(sid, str) or not ID_PATTERN.match(sid):
        return None
    if os.path.isfile(os.path.join(keyframes_dir, f"{sid}-{letter}.png")):
        return f"keyframes/{sid}-{letter}.png"
    return None


def _location(row, bible):
    """ENV id: an ENV token inside fixed_landmarks, else the one bible ENV card whose continuity_landmarks list all of them."""
    envs = bible.get("environments") if isinstance(bible.get("environments"), dict) else {}
    anchors = row.get("reference_anchors") if isinstance(row.get("reference_anchors"), dict) else {}
    lm = [x for x in anchors.get("fixed_landmarks") or [] if isinstance(x, str)]
    if not lm:
        return None, "no fixed_landmarks"
    tokens = []
    for s in lm:
        for tok in re.findall(r"ENV-[A-Za-z0-9_-]+", s):
            if tok in envs and tok not in tokens:
                tokens.append(tok)
    if len(tokens) == 1:
        return tokens[0], ""
    if tokens:
        return None, f"fixed_landmarks name several ENV ids {tokens}"
    cands = [eid for eid, env in envs.items()
             if isinstance(env, dict) and all(x in [y for y in (env.get("continuity_landmarks") or []) if isinstance(y, str)]
                                              for x in lm)]
    if len(cands) == 1:
        return cands[0], ""
    return None, f"{len(cands)} bible ENV cards list all of these fixed_landmarks"


def _props(row, bible):
    props = bible.get("props") if isinstance(bible.get("props"), dict) else {}
    body = {k: v for k, v in row.items() if k not in ("h3_fields", "audio_and_dialogue_track")}
    text = json.dumps(body, ensure_ascii=False)
    return [pid for pid in props if isinstance(pid, str)
            and re.search(r"(?<![A-Za-z0-9_-])" + re.escape(pid) + r"(?![A-Za-z0-9_-])", text)]


def _story_beat(row):
    purpose = row.get("purpose") if isinstance(row.get("purpose"), str) else ""
    if not purpose.strip():
        cont = row.get("continuity_handoff") if isinstance(row.get("continuity_handoff"), dict) else {}
        purpose = cont.get("incoming") if isinstance(cont.get("incoming"), str) else ""
    text = " ".join(purpose.split())
    if not text:
        return None
    first = re.split(r"(?<=[.!?])\s", text)[0]
    if len(first) > 140:                       # cut at a word boundary, never mid-word, no added dots
        first = first[:141].rsplit(" ", 1)[0].rstrip(",;:")
    return first or None


def derive_fields(row, prev_row, next_row, bible, is_first_in_reel, is_last_in_reel, keyframes_dir):
    """Tier 1, deterministic, never invents. Returns (fields, notes).

    fields: shot_id, lattice_n, pixel_frames, editorial_frames, trim_in_frame, trim_out_frame, head_handle_frames,
    tail_handle_frames, incoming_seam_type, outgoing_seam_type (the row's own h3_fields seam type wins when given),
    picture_1_path (None for CHAINED: the converter takes the previous shot's picture_2), picture_2_path, and
    location_id, props_present, story_beat when they can be derived. A field that cannot be derived is absent.
    notes: info lines; lines starting with 'PROBLEM: ' are problems the converter reports as they are.
    The input is never changed."""
    notes, fields = [], {}
    sid = row.get("id") if isinstance(row, dict) else None
    if not isinstance(sid, str) or not sid:
        return fields, ["PROBLEM: row has no shot id"]
    fields["shot_id"] = sid
    t1, pf, ed, err = _timing_inputs(row, sid)
    if err:
        return fields, ["PROBLEM: " + err]
    h3 = row.get("h3_fields") if isinstance(row.get("h3_fields"), dict) else {}
    bible = bible if isinstance(bible, dict) else {}
    fields.update(lattice_n=t1, pixel_frames=pf, editorial_frames=ed)
    inc_d, out_d = _seam_defaults(is_first_in_reel, is_last_in_reel, ed, pf)
    inc = h3["incoming_seam_type"] if "incoming_seam_type" in h3 else inc_d
    out = h3["outgoing_seam_type"] if "outgoing_seam_type" in h3 else out_d
    fields["incoming_seam_type"], fields["outgoing_seam_type"] = inc, out
    if inc == CHAINED and prev_row is None:
        notes.append(f"PROBLEM: {sid}: CHAINED incoming but no previous shot in this reel to hold the pose from")
    if inc in SEAM_TYPES and out in SEAM_TYPES:
        plan, probs = _plan_handles(sid, pf, ed, inc, out, t1)
    else:                                       # unknown seam type: the converter reports it; static plan kept
        plan, probs = _static_plan(pf, ed), []
    fields.update(plan)
    notes.extend("PROBLEM: " + p for p in probs)
    fields["picture_2_path"] = _own_keyframe(keyframes_dir, sid, "B")
    fields["picture_1_path"] = None if inc == CHAINED else _own_keyframe(keyframes_dir, sid, "A")
    loc, why = _location(row, bible)
    if loc:
        fields["location_id"] = loc
    else:
        notes.append(f"{sid}: location_id not derived ({why})")
    fields["props_present"] = _props(row, bible)
    beat = _story_beat(row)
    if beat:
        fields["story_beat"] = beat
    else:
        notes.append(f"{sid}: story_beat not derived (no purpose or continuity text)")
    return fields, notes


def requested_fields(row, derived, blueprint):
    """The authored fields this shot still needs: not explicit in the row, not derived, not fixed by the blueprint."""
    explicit = row.get("h3_fields") if isinstance(row.get("h3_fields"), dict) else {}
    fixed = (blueprint or {}).get("fixed") or {}
    return [f for f in AUTHOR_FIELDS if f not in explicit and f not in fixed and f not in (derived or {})]


def build_blueprint(derived, prev_cut=None):
    """The fixed part the author step must copy: frame plan, seams, stage spans, and (when a previous shot exists) the
    cut-in tag and pose copied from its cut-out, which CN-07/CN-08 require. prev_cut = {"tag", "pose"} or None."""
    keys = ("shot_id", "lattice_n", "pixel_frames", "editorial_frames", "trim_in_frame", "trim_out_frame",
            "head_handle_frames", "tail_handle_frames", "incoming_seam_type", "outgoing_seam_type")
    bp = {k: derived[k] for k in keys if k in derived}
    if isinstance(derived.get("pixel_frames"), int):
        bp["stage_frame_spans"] = _stage_spans(derived["pixel_frames"])
    bp["fixed"] = ({"cut_in_biomechanical_state_tag": prev_cut["tag"], "cut_in_pose_vector": prev_cut["pose"]}
                   if prev_cut else {})
    return bp


def cut_out_of(h3):
    """{"tag", "pose"} of a finished shot's cut-out, or None while it is not known."""
    if not isinstance(h3, dict):
        return None
    tag, pose = h3.get("cut_out_biomechanical_state_tag"), h3.get("cut_out_pose_vector")
    if isinstance(tag, str) and tag and isinstance(pose, dict):
        return {"tag": tag, "pose": pose}
    return None


def merge_h3(row, derived, authored, blueprint):
    """H3 field values, priority explicit row h3_fields > derived > blueprint fixed > authored. Only H3 names are kept."""
    explicit = row.get("h3_fields") if isinstance(row.get("h3_fields"), dict) else {}
    out = {k: v for k, v in (authored or {}).items() if k in AUTHOR_FIELDS}
    out.update((blueprint or {}).get("fixed") or {})
    out.update({k: derived[k] for k in DERIVED_FIELDS if k in derived})
    out.update({k: v for k, v in explicit.items() if k in H3_FIELDS})
    return out


def authored_key(row, derived, blueprint, bible, root):
    """Hash that makes an authored result stale: row, derived fields, blueprint, bible subset, keyframe file bytes."""
    sid = derived.get("shot_id") or row.get("id")
    pics = {}
    for letter in ("A", "B"):
        p = _own_keyframe(os.path.join(root, "keyframes") if root else None, sid, letter)
        pics[letter] = hash_frame_file(os.path.join(root, p)) if p else None
    subset = {k: bible.get(k) for k in BIBLE_KEYS_FOR_HASH} if isinstance(bible, dict) else {}
    return sha256_text(canonical_json({"row": row, "derived": derived, "blueprint": blueprint,
                                       "bible": subset, "pictures": pics}))


def load_fresh_authored(root, row, derived, blueprint, bible):
    """(fields, status). status: 'fresh' (fields usable), 'none' (no cache file), 'stale' or 'failed' (no fields)."""
    sid = derived.get("shot_id")
    if not root or not isinstance(sid, str) or not ID_PATTERN.match(sid):
        return None, "none"
    path = os.path.join(root, AUTHORED_DIR, sid + ".json")
    if not os.path.isfile(path):
        return None, "none"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None, "stale"
    if not isinstance(data, dict) or data.get("status") != "ok":
        return None, "failed"
    if data.get("hash") != authored_key(row, derived, blueprint, bible, root) or not isinstance(data.get("fields"), dict):
        return None, "stale"
    return data["fields"], "fresh"


# ---------- shot and story assembly ----------

def _shot(row, seq, ctx, h3, derived, p1, p2, notes, problems):
    """One H3 shot dict, or None. h3 = merged H3 fields, derived = tier-1 frame plan (always present when we get here)."""
    sid = row["id"]
    t1, pf, ed = derived["lattice_n"], derived["pixel_frames"], derived["editorial_frames"]
    ti, to = derived["trim_in_frame"], derived["trim_out_frame"]
    head, tail = derived["head_handle_frames"], derived["tail_handle_frames"]
    lat = lattice(t1)
    pixel_claim = row.get("pixel_frames")
    if ("pixel_frames" in row and pixel_claim != pf) or ("latent_slots" in row and row["latent_slots"] != lat["latent_slots"]):
        problems.append(f"{sid}: pixel_frames/latent_slots do not match lattice_n {t1} ({pf}/{lat['latent_slots']}); lattice used")
    for k in H3_FIELDS:
        if k not in h3:
            problems.append(f"{sid}: h3_fields.{k} missing (H3-only field, not in the V4 columns)")
    if "location_id" in h3 and h3["location_id"] not in ctx["environments"]:
        problems.append(f"{sid}: h3_fields.location_id {h3.get('location_id')!r} is not an ENV id of the bible")
    seam_in, seam_out = h3.get("incoming_seam_type"), h3.get("outgoing_seam_type")
    for label, seam in (("incoming", seam_in), ("outgoing", seam_out)):
        if seam not in SEAM_TYPES:
            problems.append(f"{sid}: h3_fields.{label}_seam_type {seam!r} is not a known seam type")
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
    sheet0 = (ctx.get("blocking") or {}).get(sid) if ctx.get("blocking") is not None else None
    sheet0 = sheet0 if isinstance(sheet0, dict) else None
    members0 = [m for m in (sheet0 or {}).get("cast") or [] if isinstance(m, dict) and isinstance(m.get("id"), str)]
    held = [_text(m.get("name")) or m["id"] for m in members0 if m.get("hold") is True]
    hold_names = held or [_text(m.get("name")) or m["id"] for m in members0]   # M-03: no hold flags = all stand still
    stage_text, spans = _stages(directives, pf, sid, problems, ti, (sheet0 or {}).get("beats"), hold_names, bool(ctx["profile"].get("time_points", False))) if directives else ({k: "" for k in STAGE_NAMES}, _stage_spans(pf))
    for name in STAGE_NAMES:
        if not stage_text[name]:
            problems.append(f"{sid}: motion stage {name} has no text")
    ed_sec = row.get("editorial_duration_sec")
    mouth, mouth_rule = _mouth(track, pf, sid, problems, round(ed_sec * FPS) if _is_num(ed_sec) else None, ti)
    cont = row.get("continuity_handoff") if isinstance(row.get("continuity_handoff"), dict) else {}
    positions = row.get("reference_anchors", {}).get("character_positions") if isinstance(row.get("reference_anchors"), dict) else []
    positions = positions if isinstance(positions, list) else []  # a scalar here (e.g. 42) must not abort the shot
    cast_lock = None   # X-05: set from the blocking sheet only
    subjects = [c["id"] for c in positions or [] if isinstance(c, dict) and isinstance(c.get("id"), str)]
    if ctx.get("blocking") is not None:   # W-07: the cast is the blocking sheet's cast; the anchors must agree
        sheet = ctx["blocking"].get(sid)
        if not isinstance(sheet, dict):
            problems.append(f"{sid}: no blocking sheet for this shot")
        else:
            members = [m for m in sheet.get("cast") or [] if isinstance(m, dict) and isinstance(m.get("id"), str)]
            blk_ids = [m["id"] for m in members]
            if set(blk_ids) != set(subjects):
                problems.append(f"{sid}: cast {_id_set(subjects)} != blocking {_id_set(blk_ids)}")
            subjects = blk_ids
            ctx["cast_names"][sid] = [_text(m.get("name")) or m["id"] for m in members]
            cast_lock = _blocking_module().prompt_args(sheet)   # X-05: the cast, mouth and sound inputs of the prompt
            header = _chain_header(sid, sheet, ctx["blocking"], problems)   # M-03: chained clip, CURRENT CHARACTER STATE
            if header:
                cast_lock["chain_header"] = header
    for cid in subjects:
        if cid not in ctx["characters"]:
            problems.append(f"{sid}: character {cid} is not in the bible characters")

    running = ctx["running"]
    timing = {"lattice_n": t1, "pixel_frames": pf, "latent_slots": lat["latent_slots"], "generation_duration_sec": SEC(pf),
              "exact_generation_duration_sec": SEC(pf), "prompt_alignment_sec_str": f"{pf / FPS:.2f}", "fps": FPS,
              "trim_in_frame": ti, "trim_out_frame": to, "head_handle_frames": head, "tail_handle_frames": tail,
              "trim_in_sec": SEC(ti), "trim_out_sec": SEC(to), "head_handle_sec": SEC(head), "tail_handle_sec": SEC(tail),
              "editorial_frames": ed, "editorial_duration_sec": SEC(ed),
              "master_reel_frame_window": [running, running + ed],
              "master_reel_window_sec": [SEC(running), SEC(running + ed)]}
    if "end_frame_position" in derived:          # set only from a timeline lock; nothing reads it until W-10
        timing["end_frame_position"] = derived["end_frame_position"]
    if sheet0 is not None and sheet0.get("schema") == "blocking/1.1":   # M-03: the camera sentence from the blocking enum
        camera = _camera_from_sheet(sheet0, ti)
    else:
        camera = _camera(directives, sid, problems, notes)
    soundscape = _soundscape(track, sid, problems, extra=_stage_cues(directives))
    sheet_cues = (ctx["blocking"] or {}).get(sid) if ctx.get("blocking") is not None else None
    if isinstance(sheet_cues, dict):   # SX-02: every blocking cue's head noun is in the soundscape, in t order
        problems.extend(f"{sid}: {p}" for p in sx02_problems(soundscape, sheet_cues.get("sound_cues") or []))
    return {
        "shot_id": sid, "episode_id": ctx["episode_id"], "sequence_order": seq,
        "story_beat": h3.get("story_beat"), "emotional_objective": h3.get("emotional_objective"),
        "mute_animatic_verification": False,
        "timing_and_lattice": timing,
        "continuity_and_seam_lock": {
            "location_id": h3.get("location_id"), "shot_scale": h3.get("shot_scale"), "subjects_present": subjects,
            "props_present": h3.get("props_present"), "screen_direction_vector": h3.get("screen_direction_vector"),
            "camera_axis_side": h3.get("camera_axis_side"), "horizon_line_y_ratio": h3.get("horizon_line_y_ratio"),
            "incoming_seam_type": seam_in, "incoming_seam_note": _text(cont.get("incoming")),
            "cut_in_biomechanical_state_tag": h3.get("cut_in_biomechanical_state_tag"),
            "cut_in_pose_vector": h3.get("cut_in_pose_vector"),
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
        "sound_plan": {"overall_soundscape": soundscape, "non_diegetic_music": "N/A"},
        **({"cast_lock": cast_lock} if cast_lock is not None else {}),
        **({"metadata": {"look": copy.deepcopy(row["look"]), "purpose": _text(row.get("purpose")), "captions": []}}
           if isinstance(row.get("look"), dict) else {}),   # audit C 11-08: post.py and assemble_reel read metadata.look (palette, act, hook, impacts)
    }


def _chain_header(sid, sheet, blocking, problems):
    """M-03: 'CURRENT CHARACTER STATE: <state>. Continue directly from this exact frame with no reset.' for a clip that
    continues the last kept frame of sheet.chain_from (director/chain_step.chain_header). The state is the sheet's
    chain_state, else the last beat action of the chained-from sheet; neither = a problem. '' when the sheet is not chained."""
    src = sheet.get("chain_from")
    if not src:
        return ""
    state = _text(sheet.get("chain_state"))
    prev = blocking.get(src) if isinstance(blocking, dict) else None
    beats = [b for b in (prev or {}).get("beats") or [] if isinstance(b, dict) and _text(b.get("action"))]
    if not state and beats:
        state = _text(max(beats, key=lambda b: b.get("t") or 0)["action"])
    if not state:
        problems.append(f"{sid}: chain_from {src} needs chain_state (the CURRENT CHARACTER STATE sentence) or a beat of {src}")
        return ""
    from director.chain_step import chain_header   # lazy: it needs numpy and PIL, which the other converters do not
    return chain_header(state.rstrip("."))


def _apply_lock(shots, lock, problems):
    """Rows copied from the timeline lock: lattice_n, pixel_frames, latent_slots, editorial_duration_sec and the seam
    types (h3_fields, which win over the row's own). Returns
    (rows, want); want maps shot id -> the lock's trims, pixel frames and end_frame_position. A row whose id is not in
    the lock is dropped with a problem. The input rows are never changed."""
    from director.timeline_lock_io import lock_rows   # the lock is read in one place: director/timeline_lock_io.py
    from h3.shot_table_spec import LATTICE_N_MAX, LATTICE_N_MIN
    by_lock = {r["id"]: r for r in lock_rows(lock)}
    by_shot = {s["id"]: s for s in lock.get("shots", [])}
    out, want = [], {}
    for row in copy.deepcopy(shots):
        sid = row.get("id") if isinstance(row, dict) else None
        if not isinstance(sid, str) or not sid:
            out.append(row)   # no id: convert_pack reports it
            continue
        if sid not in by_lock:
            problems.append(f"{sid}: not in the timeline lock")
            continue
        pixel = by_shot[sid]["pixel_frames"]
        n = next((k for k in range(LATTICE_N_MIN, LATTICE_N_MAX + 1) if lattice(k)["pixel_frames"] == pixel), None)
        if n is None:
            problems.append(f"{sid}: lock pixel_frames {pixel} is not on the H3 lattice; shot skipped")
            continue
        lock_row = by_lock[sid]
        row["lattice_n"], row["pixel_frames"], row["latent_slots"] = n, pixel, lattice(n)["latent_slots"]
        row["editorial_duration_sec"] = lock_row["editorial_duration_sec"]
        if "incoming_seam_type" in by_shot[sid] and "outgoing_seam_type" in by_shot[sid]:   # plan_lock writes both
            h3 = row.get("h3_fields") if isinstance(row.get("h3_fields"), dict) else {}
            row["h3_fields"] = dict(h3, incoming_seam_type=by_shot[sid]["incoming_seam_type"],
                                    outgoing_seam_type=by_shot[sid]["outgoing_seam_type"])
        want[sid] ={"trim_in_frame": lock_row["trim_in_frame"], "trim_out_frame": lock_row["trim_out_frame"],
                     "pixel_frames": pixel, "end_frame_position": by_shot[sid].get("end_frame_position")}
        out.append(row)
    return out, want


def _blocking_module():
    """X-05: director/blocking.py. It is imported by its bare name (it does `import shot_router`), so director/ goes on
    sys.path first. The sheets are read in one place: that module."""
    d = str(Path(__file__).resolve().parents[1] / "director")
    if d not in sys.path:
        sys.path.insert(0, d)
    import blocking as blk
    return blk


def _lint_module():
    """director/blocking_lint.py (rules L01..L10). It imports its neighbours by bare name, so director/ goes on sys.path."""
    d = str(Path(__file__).resolve().parents[1] / "director")
    if d not in sys.path:
        sys.path.insert(0, d)
    import blocking_lint as bl
    return bl


def _lint_sheets(blocking, shots, lock, problems):
    """Gap haiku-gap2 (test_e2e_blocking_lock: convert_pack ran blocking.validate only): every sheet in use also goes
    through blocking_lint. Shot seconds come from the lock (lint reads its edit_frames) or else the row's
    editorial_duration_sec. Lint problems already read 'SHOT-nnn: Lnn ...'. No sheet, no lint."""
    if not blocking:
        return
    bl = _lint_module()
    secs = {r.get("id"): r.get("editorial_duration_sec") for r in shots if isinstance(r, dict)}
    for sid, sheet in blocking.items():
        if not isinstance(sheet, dict):
            problems.append(f"{sid}: L01 sheet is not a dict")
            continue
        checked = dict(sheet)
        sec = secs.get(sid)
        if isinstance(sec, (int, float)) and not isinstance(sec, bool) and sec > 0:
            checked["writer_seconds"] = sec
        pack = [checked]
        if checked.get("chain_from") and isinstance(blocking.get(checked["chain_from"]), dict):   # L17 needs the previous shot
            pack = [blocking[checked["chain_from"]], checked]
        problems.extend(p for p in bl.lint(pack, lock=lock) if len(pack) == 1 or p.startswith(f"{sid}:"))


def _load_blocking_dir(directory, shots, problems):
    """X-05: {shot_id: sheet} read from <directory>/<shot_id>.json by director/blocking.load_sheet. A sheet that fails
    validation is a problem; a shot with no file gets no entry, so _shot reports 'no blocking sheet for this shot'."""
    blk = _blocking_module()
    sheets = {}
    for row in shots:
        sid = row.get("id") if isinstance(row, dict) else None
        if not isinstance(sid, str) or not sid or sid in sheets:
            continue
        if not os.path.exists(os.path.join(directory, sid + ".json")):
            continue
        try:
            sheets.update(blk.load_reel(directory, [sid]))   # M-01: the pack's blocking files, read by blocking.load_reel
        except blk.BlockingError as exc:
            problems.extend(exc.args[0])
        except (OSError, ValueError) as exc:   # bad JSON or unreadable file
            problems.append(f"{sid}: blocking sheet unreadable: {exc}")
    return sheets


def convert_pack(pack_dir_or_dicts, *, languages=None, profile="sing8_864x1536", authored=None, lock=None,
                 blocking=None, blocking_dir=None):
    """Returns {"story": {...}, "problems": [...], "notes": [...]}. Problems are data the H3 story cannot take as is;
    lint_story(story) reports the same gaps as rule codes. The input is never changed.

    blocking: optional {shot_id: blocking sheet} (director/blocking.load_sheet). Its cast ids become subjects_present
    and its names go to registry.cast_names; a mismatch with the V4 character positions is a problem.
    blocking_dir: optional folder of <shot_id>.json sheets, read into blocking when blocking is None (X-05).
    With a sheet, the shot also gets cast_lock (blocking.prompt_args) for the prompt compiler.

    authored: optional {shot_id: {H3 author fields}} taken as fresh by the caller. When None and the input is a folder,
    <pack>/h3_authored/<shot_id>.json is used only while its hash matches (otherwise the field stays a problem)."""
    shots, bible, stage, root, problems = _source(pack_dir_or_dicts)
    notes = []
    if not isinstance(shots, list) or not isinstance(bible, dict):
        problems.append("shots.json and bible.json are required (a list of rows and a bible object)")
        return {"story": None, "problems": problems, "notes": notes}
    lock_want = None
    if lock is not None:
        shots, lock_want = _apply_lock(shots, lock, problems)
    from_folder = isinstance(pack_dir_or_dicts, (str, os.PathLike))
    if blocking is None and blocking_dir is None and from_folder and root:   # M-01: <pack>/blocking/SHOT-NNN.json by default
        if os.path.isdir(os.path.join(root, "blocking")):
            blocking_dir = os.path.join(root, "blocking")
    if blocking is None and blocking_dir is not None:
        blocking = _load_blocking_dir(blocking_dir, shots, problems)
    _lint_sheets(blocking, shots, lock, problems)
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
           "running": 0, "episode_id": None, "blocking": blocking, "cast_names": {}}
    keyframes_dir = os.path.join(root, "keyframes") if root else None
    items, group_problems = group_rows(shots)
    problems.extend(group_problems)
    episodes, order, last = {}, [], {}
    for it in items:
        idx, row, ep = it["idx"], it["row"], it["ep"]
        if ep not in episodes:
            episodes[ep] = {"episode_id": f"EP{ep}", "asset_root": root, "shots": [], "episode_plan": {}}
            order.append(ep)
            ctx["running"] = 0
            last.pop(ep, None)
        ctx["episode_id"] = episodes[ep]["episode_id"]
        ep_shots = episodes[ep]["shots"]
        sid = row.get("id")
        if not isinstance(sid, str) or not sid:
            problems.append(f"row {idx}: no shot id; row skipped")
            continue
        registry["v4_rows"][sid] = copy.deepcopy(row)
        t1, pf, ed, err = _timing_inputs(row, sid)
        if err:
            problems.append(err)
            continue
        derived, dnotes = derive_fields(row, it["prev"], it["next"], bible, it["first"], it["last"], keyframes_dir)
        for n in dnotes:
            (problems.append(n[len("PROBLEM: "):]) if n.startswith("PROBLEM: ") else notes.append(n))
        if lock_want is not None and sid in lock_want:
            w = lock_want[sid]
            g_in, g_out, g_pf = derived.get("trim_in_frame"), derived.get("trim_out_frame"), derived.get("pixel_frames")
            if (g_in, g_out, g_pf) != (w["trim_in_frame"], w["trim_out_frame"], w["pixel_frames"]):
                problems.append(f"{sid}: lock trims {w['trim_in_frame']}..{w['trim_out_frame']} in {w['pixel_frames']} "
                                f"pixel frames != derived {g_in}..{g_out} in {g_pf} pixel frames")
            derived.update(trim_in_frame=w["trim_in_frame"], trim_out_frame=w["trim_out_frame"],
                           head_handle_frames=w["trim_in_frame"],
                           tail_handle_frames=w["pixel_frames"] - w["trim_out_frame"],
                           end_frame_position=w["end_frame_position"])
        prev = last.get(ep)
        cut = cut_out_of(prev["h3"]) if prev else None
        bp = build_blueprint(derived, cut)
        req = requested_fields(row, derived, bp)
        auth = {}
        if req:
            if authored is not None:
                entry = (authored or {}).get(sid) or {}
                if isinstance(entry, dict):
                    auth = dict(entry)
                else:
                    notes.append(f"{sid}: authored entry is not an object; ignored")
            elif from_folder:
                found, status = load_fresh_authored(root, row, derived, bp, bible)
                auth = dict(found or {})
                if status in ("stale", "failed"):
                    notes.append(f"{sid}: authored fields {status}; re-run h3/h3_author.py (missing ones are listed below)")
        h3 = merge_h3(row, derived, auth, bp)
        p2 = derived.get("picture_2_path")
        if h3.get("incoming_seam_type") == CHAINED:
            p1 = prev["p2"] if prev else None
        else:
            p1 = derived.get("picture_1_path")
        if prev:
            pout, pin = prev["h3"].get("outgoing_seam_type"), h3.get("incoming_seam_type")
            if pout in SEAM_TYPES and pin in SEAM_TYPES and ((pout in STATIC_SEAMS) != (pin in STATIC_SEAMS)):
                problems.append(f"{sid}: cut from {prev['shot_id']} mixes a static and a dynamic side: outgoing {pout}, "
                                f"incoming {pin} (both sides of a cut must match)")
        shot =_shot(row, len(ep_shots) + 1, ctx, h3, derived, p1, p2, notes, problems)
        if shot is None:
            continue
        ep_shots.append(shot)
        ctx["running"] += shot["timing_and_lattice"]["editorial_frames"]
        last[ep] = {"shot_id": sid, "h3": h3, "p2": p2, "row": row}
    for ep in order:
        ep_data = episodes[ep]
        total = sum(s["timing_and_lattice"]["editorial_frames"] for s in ep_data["shots"])
        ep_data["episode_plan"] = {"target_editorial_frames": total}
    notes.append("narration and dialogue are not in the H3 prompt (pure Foley); they stay in registry.v4_rows")
    if blocking is not None:   # W-07: names of the blocking cast, read by the compiler's cast line
        registry["cast_names"] = ctx["cast_names"]
    story = {"output_languages": langs, "output_language": langs[0] if langs else None,
             "registry": registry, "episodes": [episodes[ep] for ep in order]}
    if isinstance(stage.get("voice_engine"), dict):
        story["voice_engine"] = copy.deepcopy(stage["voice_engine"])
        registry["voice_engine"] = copy.deepcopy(stage["voice_engine"])   # Q-R4-4: the linter and Gate D read the registry copy; H3 English speech is on only when en = "h3" is set explicitly
    if isinstance(stage.get("story_gate_checks"), dict):              # the V4 writer's six red-line checks, as written
        registry["story_gate_checks"] = copy.deepcopy(stage["story_gate_checks"])
    return {"story": story, "problems": problems, "notes": notes}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Convert a V4 writer pack to an H3 story and lint it.")
    ap.add_argument("pack_dir")
    ap.add_argument("--out", help="write the H3 story JSON here")
    ap.add_argument("--lang", help="output languages, e.g. en,hi,mr (default: stage_1 file)")
    ap.add_argument("--lock", help="timeline lock JSON: its lattice and trims are used; a stale lock exits 2")
    args = ap.parse_args(argv)
    if not os.path.isfile(os.path.join(args.pack_dir, "shots.json")):
        print(f"no shots.json in {args.pack_dir}", file=sys.stderr)
        return 2
    lock = None
    if args.lock:
        from director.timeline_lock_io import StaleLockError, load_lock, verify_lock
        try:
            lock = load_lock(args.lock)
            verify_lock(args.lock, lock["inputs"], lock["params"])
        except (OSError, ValueError, KeyError, StaleLockError) as exc:
            print(f"timeline lock not usable: {exc}", file=sys.stderr)
            return 2
    languages = None
    if args.lang:
        languages = [c.strip() for c in args.lang.split(",") if c.strip()]
        if not languages or any(c not in LANGS for c in languages):
            print(f"--lang must be a list of {','.join(LANGS)}", file=sys.stderr)
            return 2
    try:
        res = convert_pack(args.pack_dir, languages=languages, lock=lock)
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
