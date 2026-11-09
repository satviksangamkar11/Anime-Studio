"""Score stage S2: the checker of score_plan.json (v1). Run it before any note is written.

Pure: stdlib only, no model, no ffmpeg, no Ableton. Never raises on bad input; every problem is reported.
Same report shape as score/cue_sheet.py:  {"ok", "errors": [{"code", "where", "message"}], "warnings": [...], "stats": {...}}

Inputs: the plan (.claude/skills/score-reel/SKILL.md, "score_plan.json (v1)"), the cue sheet (score/cue_sheet.py output,
read as JSON), and the story's music_bible.json.

Codes (checklist section A): PLAN_COVERAGE, TEMPO_NOT_CANDIDATE, TEMPO_CHANGE_OFF_ACT, CUT_MISSING, CUT_OFF_FRAME,
IMPACT_NO_HIT, HIT_OFF_FRAME, HIT_BRIGHT_UNDER_VOICE, DROPOUT_BAD, DROPOUT_MISSING, BUSY_IN_VOICE, BUSY_UNGATED,
GOD_DROP, REHOOK_WINDOW, PEAK, LOGO, END_STING, BIBLE_REF, PLAN_SHAPE.
Warning: HIT_NEAR_VOICE (D5). Other codes are listed under D9.

Decisions (the stricter reading wherever the checklist is open):
  D1  A plan time matches a cue time within one frame (1/24 s + 1e-9). Where the rule says "==" or "on" (coverage,
      sonic logo, peak, section boundaries) the match is exact to 1e-6 s.
  D2  Cuts pair one-to-one. Pass 1: each cue cut takes the nearest unused plan cut within ONE frame. Pass 2: a cue cut
      still unpaired takes the nearest unused plan cut within 1.0 s and reports CUT_OFF_FRAME (the plan cut is moved,
      not extra). No plan cut at all: CUT_MISSING. Pass 3: every plan cut still unused is CUT_EXTRA (an extra or a
      duplicate). Every plan cut's transition is checked: against its cue cut when paired, against the vocabulary
      when extra (CUT_TRANSITION_BAD).
  D3  Cut transitions: an unknown transition, a hard cut without reverse_swell / swell / key colour, and act_change on a
      same-act non-hard cut: CUT_TRANSITION_BAD. One fault gives one code.
  D4  Impacts: each cue impact pairs with the nearest plan hit within one frame. None within 1.0 s: IMPACT_NO_HIT.
      Nearest hit more than one frame away (within 1.0 s): HIT_OFF_FRAME.
  D5  Hits under voice: every hit that starts inside the voice union, or that pairs with an in_voice impact, needs
      band "low" (a missing band counts as bright). Reported as HIT_BRIGHT_UNDER_VOICE only. A bright hit that starts
      0 to 0.1 s before a voice window gets the warning HIT_NEAR_VOICE (not an error; it may ring into speech).
      BUSY_IN_VOICE skips type "hit" so one fault gives one code.
  D6  Voice windows are half-open [start, end): a time exactly at a window's end is in the gap. (The cue union window
      [44.2, 47.899) ends before the SHIVA entry at 48.0, so 48.0 sits in the gap.)
  D7  An impact hit (one that needs a drop-out) is a hit within one frame of a cue impact.
  D8  Drop-outs: every event that carries preceded_by_dropout_s must hold a number in (0, 0.45], else DROPOUT_BAD.
  D9  Codes outside the checklist list, one per fault: SECTION_ACT_MISMATCH, THEME_IN_VOICE, DROP_IN_VOICE,
      SECTION_FIELD_MISSING, PLAN_SCHEMA_VERSION, PLAN_NUMBER_NOT_FINITE, CUE_SHAPE,
      BIBLE_SHAPE, ACT_UNKNOWN, CUT_EXTRA, CUT_TRANSITION_BAD, GOD_FEEL, EVENT_TYPE_UNKNOWN, EVENT_ROLE_MISSING,
      GENRE_UNKNOWN, TEMPO_NOT_IN_BIBLE, GENRE_NOT_IN_BIBLE, HOME_KEY_MISMATCH, EPISODE_MISMATCH, CHECK_CRASH
      (last-resort guard; a test asserts it never fires).
  D10 Tempo and genre (owner rule 45, 2026-11-09): a section's genre must be a genre the cue sheet lists for its act, or
      a genre the bible authorises (tempo_map.genre or tempo_map.shot_genres values); otherwise GENRE_UNKNOWN. A genre the
      cue sheet does not list is checked against the bpms the cue sheet lists for its act (TEMPO_NOT_CANDIDATE).
      A genre the cue sheet lists is checked against its own bpms. The bible tempo_map then applies: bpm must equal
      tempo_map[act] or one of alternatives[act] (TEMPO_NOT_IN_BIBLE). The genre must equal tempo_map.genre[act], or the
      tempo_map.shot_genres value of a shot the section overlaps (GENRE_NOT_IN_BIBLE). Either bible check is skipped when
      the bible lacks its key. A section with a fault above is not judged further (one fault, one code).
      Change rule between two adjacent sections: a BPM change needs a cue act_change cut within one frame of their
      boundary (TEMPO_CHANGE_OFF_ACT). A genre change alone may happen at an act_change cut, or, inside the same act with
      the same BPM, at any cue-sheet cut within one frame of the boundary; otherwise TEMPO_CHANGE_OFF_ACT.
  D11 Required keys: every key the SKILL format lists is required; a section also needs feel, harmony, density_per_beat
      and intensity (SECTION_FIELD_MISSING; the section is still judged). A missing "why" is a warning.
  D20 Act span (PCR2-1): a section's act is the cue act whose span [start_s, end_s) holds its start, and the section may
      not run past that span's end (SECTION_ACT_MISMATCH). Candidate and bible checks then use that act.
  D21 Voice (PCR2-2): a theme_entry or a drop may not START inside the voice union, whatever its role (THEME_IN_VOICE,
      DROP_IN_VOICE). Other busy non-hit events are still BUSY_IN_VOICE. Hits under speech need band "low" (D5).
  D22 Cut transitions (PCR2-8): a cue act_change cut must use act_change or a hard transition (swell, key colour).
      NWR3-6: a cut that is both hard and act_change must use reverse_swell_to_cut or swell_to_cut (CUT_TRANSITION_BAD).
  D26 Transforms: a theme_entry may carry "transform"; it must be a key of that bible theme's transforms (BIBLE_REF).
  D23 Warning NOTHING_NEW_AT_CUT (PCR2-5, SKILL rule 6): a plan cut with no section boundary, no event within 1.0 s after
      it, and a transition of none or bed_continues.
  D24 End sting (PCR2-10): at_s + tail_s must not run past the cue total_s (END_STING).
  D25 Feel "quad" (PCR2-R-3): 4 notes per beat, used to fit a motif into a short voice gap. Accepted by FEELS like
      normal, half and double; any other feel is PLAN_SHAPE.
  D12 Presets: a plan refers to a preset by a "preset" string on a section or event, or a "presets" list at top level.
      The value must be a preset NAME (a value of bible presets; keys starting with "_" are notes, not presets).
  D13 God themes (SHIVA, BRAHMA, KALI, VISHNU; name matched case-insensitively): a theme_entry in a FAST section (its
      section bpm >= 120) needs a drop-out (DROPOUT_MISSING) and feel "half" (GOD_FEEL). In a slow section (bpm < 120) both
      are optional; a drop-out given there is still range-checked (DROPOUT_BAD). GOD_DROP fires for every god entry, fast
      or slow, when within 1.0 s of the entry there is any of: a drop event (any case), a hit whose band is not "low", or
      an event with role hits or brass whose feel is not "half".
  D14 Sonic logo: exactly one sonic_logo event at 0.0. End sting: exactly one; inside the end-hook window; band "low"
      if it starts before last_speech_end_s (the scripted last word is the speech boundary on purpose: voice windows
      are permission, not speech); 0 <= tail_s <= 0.45.
  D15 Busy: a role is busy when track_roles[role].busy is true. A section listing a busy role needs voice_gated true
      (BUSY_UNGATED). A non-hit event with a busy role must not start inside the voice union (BUSY_IN_VOICE).
      Every event except sonic_logo and end_sting must carry a role (EVENT_ROLE_MISSING), so no event skips these checks.
  D16 Peak: peak_at_s is one number (a list is PEAK) equal to an event time or a section boundary.
  D17 Rehook: a closed interval [start, end] from cue retention.rehook_window_s. A missing window is REHOOK_WINDOW.
  D18 Event types are compared lower-cased (and stripped). Accepted types: sonic_logo, hit, theme_entry, drop, end_sting.
      Any other type is EVENT_TYPE_UNKNOWN.
  D19 Identity: plan home_key must equal bible home_key (HOME_KEY_MISMATCH); plan episode must equal cue episode when
      both are present, compared as strings (EPISODE_MISMATCH).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

SCHEMA_VERSION = 1
FRAME_S = 1.0 / 24
TOL_S = FRAME_S + 1e-9
EXACT_S = 1e-6
NEAR_S = 1.0
NEAR_VOICE_S = 0.1
DROPOUT_MAX_S = 0.45
GOD_THEMES = frozenset({"SHIVA", "BRAHMA", "KALI", "VISHNU"})
GOD_DROP_WINDOW_S = 1.0
GOD_FAST_BPM = 120.0
TRANSITIONS = frozenset({"none", "theme_handover", "bed_continues", "reverse_swell_to_cut", "swell_to_cut",
                         "key_colour_on_downbeat", "act_change"})
HARD_CUT_TRANSITIONS = frozenset({"reverse_swell_to_cut", "swell_to_cut", "key_colour_on_downbeat"})
SWELL_TO_CUT = frozenset({"reverse_swell_to_cut", "swell_to_cut"})  # NWR3-6: the only transitions for a hard act_change cut
EVENT_TYPES = frozenset({"sonic_logo", "hit", "theme_entry", "drop", "end_sting"})
ROLELESS_TYPES = frozenset({"sonic_logo", "end_sting"})
FEELS = frozenset({"normal", "half", "double", "quad"})
LOW_BAND = "low"
TAIL_MAX_S = 0.45
MACROS = (1, 2, 3, 4)
REQUIRED_KEYS = ("schema_version", "episode", "style", "home_key", "sections", "events", "cuts", "automation",
                 "rehook_at_s", "peak_at_s")
LIST_KEYS = ("sections", "events", "cuts", "automation")
WINDOW_OPTIONAL = frozenset({"rehook_at_s", "peak_at_s"})  # variant A (a window) has no re-hook; peak only if given
VARIANTS = ("A", "B")  # A = window plan judged against bible ab_test_m1.A_tempo_map; B (or none) = full reel
MAX_DEPTH = 40
SECTION_FIELDS = ("harmony", "density_per_beat", "intensity")


# ---------------------------------------------------------------- small helpers

def _err(code, where, message):
    return {"code": code, "where": where, "message": message}


def _report(errors, warnings=(), stats=None):
    return {"ok": not errors, "errors": list(errors), "warnings": list(warnings), "stats": dict(stats or {})}


def _shape_fail(errors, code, where, message):
    errors.append(_err(code, where, message))
    return False


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _is_str(x):
    return isinstance(x, str) and x != ""


def _is_pair(x):
    return isinstance(x, list) and len(x) == 2 and all(_is_num(v) for v in x)


def _in(value, container):
    """Membership that never raises: a non-string is simply not in the set."""
    return isinstance(value, str) and value in container


def _in_window(t, windows):
    return any(a <= t < b for a, b in windows)


def _as_list(x):
    return x if isinstance(x, list) else []


def _as_dict(x):
    return x if isinstance(x, dict) else {}


def _etype(e):
    """Event type, lower-cased and stripped (D18). Shape checks guarantee a string."""
    return e["type"].strip().lower()


# ---------------------------------------------------------------- shape of the three inputs (A14)

def _cue_shape(cue, errors):
    if not isinstance(cue, dict):
        return _shape_fail(errors, "CUE_SHAPE", "cue_sheet", "the cue sheet must be a JSON object")
    n = len(errors)
    if not (_is_num(cue.get("total_s")) and cue["total_s"] > 0):
        _shape_fail(errors, "CUE_SHAPE", "cue_sheet.total_s", "must be a positive number")
    for key in ("cuts", "acts", "tempo_candidates", "shots"):
        if not isinstance(cue.get(key), list):
            _shape_fail(errors, "CUE_SHAPE", f"cue_sheet.{key}", "must be a list")
    for i, c in enumerate(_as_list(cue.get("cuts"))):
        if not (isinstance(c, dict) and _is_num(c.get("at_s")) and isinstance(c.get("hard_cut"), bool)
                and isinstance(c.get("act_change"), bool)):
            _shape_fail(errors, "CUE_SHAPE", f"cue_sheet.cuts[{i}]", "needs at_s, hard_cut (bool), act_change (bool)")
    for i, a in enumerate(_as_list(cue.get("acts"))):
        if not (isinstance(a, dict) and _is_str(a.get("act")) and _is_num(a.get("start_s")) and _is_num(a.get("end_s"))):
            _shape_fail(errors, "CUE_SHAPE", f"cue_sheet.acts[{i}]", "needs an act name and start_s, end_s")
    for i, t in enumerate(_as_list(cue.get("tempo_candidates"))):
        if not (isinstance(t, dict) and _is_str(t.get("act")) and isinstance(t.get("candidates"), dict)):
            _shape_fail(errors, "CUE_SHAPE", f"cue_sheet.tempo_candidates[{i}]", "needs act and a candidates object")
    for i, s in enumerate(_as_list(cue.get("shots"))):
        imps = s.get("impacts") if isinstance(s, dict) else None
        if not (isinstance(imps, list) and all(isinstance(x, dict) and _is_num(x.get("at_s")) for x in imps)):
            _shape_fail(errors, "CUE_SHAPE", f"cue_sheet.shots[{i}]", "needs an impacts list with at_s")
    ret = cue.get("retention")
    if not isinstance(ret, dict):
        _shape_fail(errors, "CUE_SHAPE", "cue_sheet.retention", "must be an object")
    else:
        for key in ("rehook_window_s", "end_hook_window_s"):
            if ret.get(key) is not None and not _is_pair(ret.get(key)):
                _shape_fail(errors, "CUE_SHAPE", f"cue_sheet.retention.{key}", "must be null or [start, end]")
        if ret.get("last_speech_end_s") is not None and not _is_num(ret.get("last_speech_end_s")):
            _shape_fail(errors, "CUE_SHAPE", "cue_sheet.retention.last_speech_end_s", "must be null or a number")
    voice = cue.get("voice")
    union = voice.get("union") if isinstance(voice, dict) else None
    if not (isinstance(union, list) and all(_is_pair(w) for w in union)):
        _shape_fail(errors, "CUE_SHAPE", "cue_sheet.voice.union", "must be a list of [start, end] pairs")
    return len(errors) == n


def _bible_shape(bible, errors):
    if not isinstance(bible, dict):
        return _shape_fail(errors, "BIBLE_SHAPE", "bible", "the bible must be a JSON object")
    n = len(errors)
    for key in ("themes", "track_roles", "presets"):
        if not isinstance(bible.get(key), dict):
            _shape_fail(errors, "BIBLE_SHAPE", f"bible.{key}", "must be an object")
    for role, info in _as_dict(bible.get("track_roles")).items():
        if not isinstance(info, dict):
            _shape_fail(errors, "BIBLE_SHAPE", f"bible.track_roles.{role}", "must be an object")
    atm = _ab_tempo(bible)  # variant A: {act: {"bpm": number, "genre": string}}
    if atm is not None and not (isinstance(atm, dict) and all(
            isinstance(v, dict) and _is_num(v.get("bpm")) and _is_str(v.get("genre")) for v in atm.values())):
        _shape_fail(errors, "BIBLE_SHAPE", "bible.ab_test_m1.A_tempo_map", "must map each act to {bpm (number), genre (string)}")
    if "tempo_map" in bible:  # PCR2-7: a malformed tempo_map is BIBLE_SHAPE, never a crash
        tm = bible["tempo_map"]
        if not isinstance(tm, dict):
            _shape_fail(errors, "BIBLE_SHAPE", "bible.tempo_map", "must be an object")
        else:
            for key in ("alternatives", "genre", "shot_genres"):
                if key in tm and not isinstance(tm[key], dict):
                    _shape_fail(errors, "BIBLE_SHAPE", f"bible.tempo_map.{key}", "must be an object")
            for key in ("genre", "shot_genres"):
                if isinstance(tm.get(key), dict) and not all(_is_str(v) for v in tm[key].values()):
                    _shape_fail(errors, "BIBLE_SHAPE", f"bible.tempo_map.{key}", "every value must be a genre name")
    return len(errors) == n


def _finite(value, where, errors, depth=0):
    """PLAN_NUMBER_NOT_FINITE for every NaN or infinity anywhere in the plan."""
    if depth > MAX_DEPTH:
        return
    if isinstance(value, float) and not math.isfinite(value):
        errors.append(_err("PLAN_NUMBER_NOT_FINITE", where, f"{value} is not a finite number"))
    elif isinstance(value, dict):
        for k, v in value.items():
            _finite(v, f"{where}.{k}", errors, depth + 1)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _finite(v, f"{where}[{i}]", errors, depth + 1)


def _plan_top_shape(plan, errors, window=False):
    for key in REQUIRED_KEYS:
        if window and key in WINDOW_OPTIONAL:
            continue
        if key not in plan:
            _shape_fail(errors, "PLAN_SHAPE", f"plan.{key}", "required key missing")
    if "schema_version" in plan and not (type(plan["schema_version"]) is int and plan["schema_version"] == SCHEMA_VERSION):
        _shape_fail(errors, "PLAN_SCHEMA_VERSION", "plan.schema_version", f"must be the integer {SCHEMA_VERSION}")
    for key in ("style", "home_key"):
        if key in plan and not _is_str(plan[key]):
            _shape_fail(errors, "PLAN_SHAPE", f"plan.{key}", "must be a non-empty string")
    if "episode" in plan and not (type(plan["episode"]) is int or _is_str(plan["episode"])):
        _shape_fail(errors, "PLAN_SHAPE", "plan.episode", "must be an integer or a string")
    for key in LIST_KEYS:
        if key in plan and not isinstance(plan[key], list):
            _shape_fail(errors, "PLAN_SHAPE", f"plan.{key}", "must be a list")


def _shape_section(s, where, errors):
    if not isinstance(s, dict):
        return _shape_fail(errors, "PLAN_SHAPE", where, "a section must be an object")
    n = len(errors)
    ok = _shape_section_body(s, where, errors, n)
    for key in SECTION_FIELDS:  # PCR2-4: reported, but the section is still judged
        if key not in s:
            errors.append(_err("SECTION_FIELD_MISSING", f"{where}.{key}", "required section key missing"))
    return ok


def _shape_section_body(s, where, errors, n):
    """The type checks of one section (the required-field check is in _shape_section)."""
    for key in ("start_s", "end_s", "bpm"):
        if not _is_num(s.get(key)):
            _shape_fail(errors, "PLAN_SHAPE", f"{where}.{key}", "must be a finite number")
    for key in ("act", "genre"):
        if not _is_str(s.get(key)):
            _shape_fail(errors, "PLAN_SHAPE", f"{where}.{key}", "must be a non-empty string")
    if not _in(s.get("feel"), FEELS):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.feel", "must be normal, half or double")
    roles = s.get("roles_on")
    if not (isinstance(roles, list) and all(_is_str(r) for r in roles)):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.roles_on", "must be a list of role names")
    if _is_num(s.get("start_s")) and _is_num(s.get("end_s")) and s["end_s"] <= s["start_s"]:
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.end_s", "must be after start_s")
    return len(errors) == n


def _shape_event(e, where, errors):
    if not isinstance(e, dict):
        return _shape_fail(errors, "PLAN_SHAPE", where, "an event must be an object")
    n = len(errors)
    if not _is_num(e.get("at_s")):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.at_s", "must be a finite number")
    if not _is_str(e.get("type")):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.type", "must be a non-empty string")
    for key in ("role", "band", "feel"):
        if key in e and not _is_str(e[key]):
            _shape_fail(errors, "PLAN_SHAPE", f"{where}.{key}", "must be a non-empty string")
    if _is_str(e.get("type")) and _etype(e) == "theme_entry" and not _is_str(e.get("theme")):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.theme", "a theme_entry needs a theme name")
    return len(errors) == n


def _shape_cut(c, where, errors):
    if not isinstance(c, dict):
        return _shape_fail(errors, "PLAN_SHAPE", where, "a cut must be an object")
    n = len(errors)
    if not _is_num(c.get("at_s")):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.at_s", "must be a finite number")
    if not _is_str(c.get("transition")):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.transition", "must be a non-empty string")
    return len(errors) == n


def _shape_automation(a, where, errors):
    if not isinstance(a, dict):
        return _shape_fail(errors, "PLAN_SHAPE", where, "an automation entry must be an object")
    n = len(errors)
    if not _is_str(a.get("role")):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.role", "must be a role name")
    m = a.get("macro")
    if not (m == "volume" or (type(m) is int and m in MACROS)):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.macro", "must be 1, 2, 3, 4 or \"volume\"")
    pts = a.get("points")
    if not (isinstance(pts, list) and all(_is_pair(p) for p in pts)):
        _shape_fail(errors, "PLAN_SHAPE", f"{where}.points", "must be a list of [time, value] pairs")
    return len(errors) == n


def _items(plan, key, shaper, errors):
    """(index, item) for every item of plan[key] that passes its shape check. A non-list gives []."""
    value = plan.get(key)
    if not isinstance(value, list):
        return []
    out = []
    for i, item in enumerate(value):
        if shaper(item, f"plan.{key}[{i}]", errors):
            out.append((i, item))
    return out


# ---------------------------------------------------------------- rules

def _check_coverage(secs, total_s, errors):
    """A1: sections contiguous from 0.0 to the cue total_s."""
    if not secs:
        errors.append(_err("PLAN_COVERAGE", "plan.sections", "no valid section; the plan must cover 0 to total_s"))
        return
    first_i, first = secs[0]
    if abs(first["start_s"]) > EXACT_S:
        errors.append(_err("PLAN_COVERAGE", f"plan.sections[{first_i}]",
                           f"starts at {first['start_s']}; the first section must start at 0.0"))
    for (ia, a), (ib, b) in zip(secs, secs[1:]):
        gap = b["start_s"] - a["end_s"]
        if gap > EXACT_S:
            errors.append(_err("PLAN_COVERAGE", f"plan.sections[{ib}]",
                               f"gap of {gap:.6g} s between sections[{ia}] and sections[{ib}]"))
        elif gap < -EXACT_S:
            errors.append(_err("PLAN_COVERAGE", f"plan.sections[{ib}]",
                               f"overlap of {-gap:.6g} s between sections[{ia}] and sections[{ib}]"))
    last_i, last = secs[-1]
    if abs(last["end_s"] - total_s) > EXACT_S:
        errors.append(_err("PLAN_COVERAGE", f"plan.sections[{last_i}]",
                           f"ends at {last['end_s']}; the cue total_s is {total_s}"))


def _bible_genres(tm):
    """Genres the bible authorises: the tempo_map genre values and the shot_genres values (rule 45)."""
    if tm is None:
        return set()
    out = {v for v in _as_dict(tm.get("genre")).values() if _is_str(v)}
    out |= {v for v in _as_dict(tm.get("shot_genres")).values() if _is_str(v)}
    return out


def _ab_tempo(bible):
    """bible.ab_test_m1.A_tempo_map (variant A's tempo and genre per act), or None when absent."""
    ab = bible.get("ab_test_m1")
    return ab.get("A_tempo_map") if isinstance(ab, dict) else None


def _window_tempo_map(bible):
    """Variant A: A_tempo_map in the tempo_map form used by the checks: {act: bpm, "genre": {act: genre}}."""
    out = {"genre": {}}
    for act, v in _ab_tempo(bible).items():
        out[act] = float(v["bpm"])
        out["genre"][act] = v["genre"]
    return out


def _window_end(plan, cue, errors):
    """None for a full-reel plan (no variant, or variant B). Variant A needs window_s [0, end] with 0 < end <= total_s."""
    variant = plan.get("variant")
    if variant is None or variant == "B":
        if "window_s" in plan:
            _shape_fail(errors, "PLAN_SHAPE", "plan.window_s", "window_s is only for variant A")
        return None
    if variant not in VARIANTS:
        _shape_fail(errors, "PLAN_SHAPE", "plan.variant", f"variant must be one of {list(VARIANTS)}")
        return None
    w = plan.get("window_s")
    total = float(cue["total_s"])
    if not (_is_pair(w) and abs(w[0]) <= EXACT_S and 0 < w[1] <= total + EXACT_S):
        _shape_fail(errors, "PLAN_SHAPE", "plan.window_s", f"variant A needs [0, end] with 0 < end <= {total}")
        return None
    return float(w[1])


def _window_filter(items, end, where, errors):
    """Variant A: keep (index, item) pairs that start before the window end; each later one is WINDOW_OUTSIDE."""
    kept = []
    for i, item in items:
        if float(item["at_s"]) < end - TOL_S:
            kept.append((i, item))
        else:
            errors.append(_err("WINDOW_OUTSIDE", f"{where}[{i}]",
                               f"at {item['at_s']} s is outside the variant window 0 to {end} s"))
    return kept


def _shot_windows(cue):
    """(start, end, shot id) for each cue shot with numeric start_s and end_s."""
    out = []
    for shot in cue["shots"]:
        if _is_num(shot.get("start_s")) and _is_num(shot.get("end_s")):
            out.append((float(shot["start_s"]), float(shot["end_s"]), str(shot.get("id", ""))))
    return out


def _bible_tempo_ok(s, tm, windows, where, errors):
    """D10: the bible tempo_map (bpm and genre per act). Skipped for any key the bible lacks."""
    if tm is None:
        return
    act, bpm, genre = s["act"], s["bpm"], s["genre"]
    if _is_num(tm.get(act)):
        alts = _as_list(_as_dict(tm.get("alternatives")).get(act))
        allowed = [tm[act]] + [a for a in alts if _is_num(a)]
        if not any(abs(bpm - a) <= 1e-6 for a in allowed):
            errors.append(_err("TEMPO_NOT_IN_BIBLE", where,
                               f"bpm {bpm} is not tempo_map[{act}] {tm[act]} or one of its alternatives {alts}"))
    genres = _as_dict(tm.get("genre"))
    if act not in genres or genre == genres[act]:
        return
    shot_genres = _as_dict(tm.get("shot_genres"))
    overlapped = {shot_genres[sid] for a, b, sid in windows
                  if sid in shot_genres and _is_str(shot_genres[sid])
                  and s["start_s"] < b - EXACT_S and s["end_s"] > a + EXACT_S}
    if genre not in overlapped:
        errors.append(_err("GENRE_NOT_IN_BIBLE", where,
                           f"genre {genre!r} is not the bible genre {genres[act]!r} for {act}, "
                           f"nor the shot_genres of a shot this section overlaps"))


def _section_in_act_span(s, spans, where, errors):
    """PCR2-1: the cue act whose span holds the section's start must be the section's act, and the section may not
    run past that span's end (a section may not cross an act boundary)."""
    holder = [(act, b) for act, a, b in spans if a <= s["start_s"] < b]
    if holder and holder[0][0] == s["act"] and s["end_s"] <= holder[0][1] + EXACT_S:
        return True
    where_act = holder[0] if holder else ("none", None)
    errors.append(_err("SECTION_ACT_MISMATCH", where,
                       f"act {s['act']!r} does not match the cue act span holding {s['start_s']} s "
                       f"({where_act[0]} ending {where_act[1]}); a section may not cross an act boundary"))
    return False


def _check_tempo(secs, acts, cands, ccuts, tm, windows, spans, errors):
    """A2 and D10: genre and bpm against the cue candidates and the tempo map (tempo_map, or A_tempo_map for variant A). A3 and rule 45: the change rule."""
    authorised = _bible_genres(tm)
    for i, s in secs:
        where = f"plan.sections[{i}]"
        if s["act"] not in acts:
            errors.append(_err("ACT_UNKNOWN", where, f"act {s['act']!r} is not an act in the cue sheet"))
            continue
        if not _section_in_act_span(s, spans, where, errors):
            continue
        by_genre = cands.get(s["act"], {})
        if s["genre"] in by_genre:
            pool = by_genre[s["genre"]]
        elif s["genre"] in authorised:
            # the cue sheet lists no tempo for this genre (e.g. club_folk_groove): judge the bpm by the act's candidates
            pool = set().union(*by_genre.values())
        else:
            errors.append(_err("GENRE_UNKNOWN", where, f"genre {s['genre']!r} has no cue-sheet tempo candidates for {s['act']}"))
            continue
        if not any(abs(s["bpm"] - c) <= 1e-6 for c in pool):
            errors.append(_err("TEMPO_NOT_CANDIDATE", where,
                               f"bpm {s['bpm']} is not a cue-sheet candidate for genre {s['genre']} in act {s['act']}"))
            continue
        _bible_tempo_ok(s, tm, windows, where, errors)
    for (ia, a), (ib, b) in zip(secs, secs[1:]):
        if a["bpm"] == b["bpm"] and a["genre"] == b["genre"]:
            continue
        boundary = a["end_s"]
        act_cut = any(c["act_change"] and abs(c["at_s"] - boundary) <= TOL_S for c in ccuts)
        any_cut = any(abs(c["at_s"] - boundary) <= TOL_S for c in ccuts)
        same_act_same_bpm = a["act"] == b["act"] and a["bpm"] == b["bpm"]
        if act_cut or (same_act_same_bpm and any_cut):
            continue
        errors.append(_err("TEMPO_CHANGE_OFF_ACT", f"plan.sections[{ib}]",
                           f"bpm or genre changes at {boundary} s, which is not a cue act_change cut "
                           f"(a genre-only change needs a cue cut inside the same act)"))


def _cut_transition(p, c, where, errors):
    t = p["transition"]
    if not _in(t, TRANSITIONS):
        errors.append(_err("CUT_TRANSITION_BAD", where, f"transition {t!r} is not one of {sorted(TRANSITIONS)}"))
    elif c["hard_cut"] and c["act_change"] and not _in(t, SWELL_TO_CUT):
        errors.append(_err("CUT_TRANSITION_BAD", where,
                           f"a cut that is both hard and act_change needs one of {sorted(SWELL_TO_CUT)}, got {t!r}"))
    elif c["hard_cut"] and not _in(t, HARD_CUT_TRANSITIONS):
        errors.append(_err("CUT_TRANSITION_BAD", where,
                           f"a hard cut needs one of {sorted(HARD_CUT_TRANSITIONS)}, got {t!r}"))
    elif c["act_change"] and not _in(t, HARD_CUT_TRANSITIONS | {"act_change"}):
        errors.append(_err("CUT_TRANSITION_BAD", where,
                           "an act_change cut needs act_change or a swell or key-colour transition, got " + repr(t)))
    elif not c["hard_cut"] and not c["act_change"] and t == "act_change":
        errors.append(_err("CUT_TRANSITION_BAD", where, "a same-act cut must not use act_change"))


def _check_cuts(cuts, ccuts, errors):
    """A4 with D2: one-to-one pairing; off-frame moved cuts; missing cues; extra and duplicate plan cuts."""
    used = set()
    paired = set()
    for ci, c in enumerate(ccuts):  # pass 1: exact (one frame)
        at = float(c["at_s"])
        exact = [(abs(p["at_s"] - at), pi) for pi, (_, p) in enumerate(cuts)
                 if pi not in used and abs(p["at_s"] - at) <= TOL_S]
        if exact:
            _, pi = min(exact)
            used.add(pi)
            paired.add(ci)
            _cut_transition(cuts[pi][1], c, f"plan.cuts[{cuts[pi][0]}]", errors)
    for ci, c in enumerate(ccuts):  # pass 2: moved by more than a frame, or missing
        if ci in paired:
            continue
        at = float(c["at_s"])
        where = f"cue_sheet.cuts[{ci}] at {at}"
        near = [(abs(p["at_s"] - at), pi) for pi, (_, p) in enumerate(cuts)
                if pi not in used and abs(p["at_s"] - at) <= NEAR_S]
        if near:
            dist, pi = min(near)
            used.add(pi)
            errors.append(_err("CUT_OFF_FRAME", where,
                               f"nearest plan cut is {cuts[pi][1]['at_s']} s, {dist * 1000:.1f} ms away (limit one frame)"))
            _cut_transition(cuts[pi][1], c, f"plan.cuts[{cuts[pi][0]}]", errors)
        else:
            errors.append(_err("CUT_MISSING", where, "no plan cut within one second of this cue cut"))
    for pi, (i, p) in enumerate(cuts):  # pass 3: unpaired plan cuts
        if pi in used:
            continue
        errors.append(_err("CUT_EXTRA", f"plan.cuts[{i}]",
                           f"cut at {p['at_s']} s pairs with no cue-sheet cut (extra or duplicate)"))
        if not _in(p["transition"], TRANSITIONS):
            errors.append(_err("CUT_TRANSITION_BAD", f"plan.cuts[{i}]", f"transition {p['transition']!r} is not in the vocabulary"))


def _check_impacts(events, impacts, union, errors, warnings):
    """A5: every cue impact has a hit within one frame; hits under voice are low (HIT_NEAR_VOICE warns). A6: impact hits need a drop-out."""
    hits = [(i, e) for i, e in events if _etype(e) == "hit"]
    for sid, imp in impacts:
        at = float(imp["at_s"])
        where = f"cue impact {sid} at {at}"
        if any(abs(h["at_s"] - at) <= TOL_S for _, h in hits):
            continue
        if any(abs(h["at_s"] - at) <= NEAR_S for _, h in hits):
            errors.append(_err("HIT_OFF_FRAME", where, "the nearest plan hit is more than one frame away"))
        else:
            errors.append(_err("IMPACT_NO_HIT", where, "no plan hit within 1.0 s of this impact"))
    for i, h in hits:
        where = f"plan.events[{i}]"
        at = float(h["at_s"])
        paired = [imp for _, imp in impacts if abs(imp["at_s"] - at) <= TOL_S]
        if paired and "preceded_by_dropout_s" not in h:
            errors.append(_err("DROPOUT_MISSING", where, f"a hit on impact {at} s needs preceded_by_dropout_s"))
        under_voice = _in_window(at, union) or any(imp.get("in_voice") is True for imp in paired)
        if under_voice and h.get("band") != LOW_BAND:
            errors.append(_err("HIT_BRIGHT_UNDER_VOICE", where,
                               f"hit at {at} s is under speech and must have band \"low\""))
        elif h.get("band") != LOW_BAND and any(0 < a - at <= NEAR_VOICE_S + 1e-9 for a, _ in union):
            warnings.append(_err("HIT_NEAR_VOICE", where,
                                 f"bright hit at {at} s starts up to {NEAR_VOICE_S} s before speech; it may ring into it"))


def _check_dropouts(events, errors):
    """A6: a drop-out, where given, is in (0, 0.45]."""
    for i, e in events:
        if "preceded_by_dropout_s" in e:
            v = e["preceded_by_dropout_s"]
            if not (_is_num(v) and 0 < v <= DROPOUT_MAX_S):
                errors.append(_err("DROPOUT_BAD", f"plan.events[{i}]",
                                   f"preceded_by_dropout_s {v!r} must be in (0, {DROPOUT_MAX_S}]"))


def _check_busy(secs, events, bible, union, errors):
    """A7: busy roles are gated in their sections and kept out of speech (hits are judged by A5)."""
    busy = {r for r, info in bible["track_roles"].items() if info.get("busy") is True}
    for i, s in secs:
        for r in s["roles_on"]:
            if r in busy and s.get("voice_gated") is not True:
                errors.append(_err("BUSY_UNGATED", f"plan.sections[{i}]",
                                   f"lists busy role {r!r} but voice_gated is not true"))
                break
    for i, e in events:  # PCR2-2: a theme or a drop may not start in speech, whatever its role (D21)
        t = _etype(e)
        if t in ("theme_entry", "drop") and _in_window(float(e["at_s"]), union):
            code = "THEME_IN_VOICE" if t == "theme_entry" else "DROP_IN_VOICE"
            errors.append(_err(code, f"plan.events[{i}]", f"{t} at {e['at_s']} s starts inside speech; it must start in a gap"))
            continue
        role = e.get("role")
        if t == "hit" or not _is_str(role) or role not in busy:
            continue
        if _in_window(float(e["at_s"]), union):
            errors.append(_err("BUSY_IN_VOICE", f"plan.events[{i}]",
                               f"busy role {role!r} starts at {e['at_s']} s, inside speech"))


def _intrudes_on_god(x):
    """D13: an event that would break a god's reveal: a drop, a bright hit, or a non-half hits/brass event."""
    t = _etype(x)
    if t == "drop":
        return True
    if t == "theme_entry":
        return False
    if t == "hit" and x.get("band") != LOW_BAND:
        return True
    return x.get("role") in ("hits", "brass") and x.get("feel") != "half"


def _section_bpm_at(t, secs):
    """The bpm of the section that holds time t (start inclusive, end exclusive), or None."""
    for _, s in secs:
        if s["start_s"] <= t < s["end_s"]:
            return s["bpm"]
    return None


def _check_gods(events, secs, errors):
    """A8 (D13): a god's entry in a fast section needs a drop-out and feel half; any god entry needs nothing intruding within 1.0 s."""
    for i, e in events:
        if _etype(e) != "theme_entry":
            continue
        name = e["theme"].strip().upper()
        if name not in GOD_THEMES:
            continue
        where = f"plan.events[{i}] {e['theme']}"
        bpm = _section_bpm_at(float(e["at_s"]), secs)
        fast = bpm is None or bpm >= GOD_FAST_BPM  # no section found: judge it as fast (the strict reading)
        if fast and "preceded_by_dropout_s" not in e:
            errors.append(_err("DROPOUT_MISSING", where, "a god's theme entry in a fast section needs preceded_by_dropout_s"))
        if fast and e.get("feel") != "half":
            errors.append(_err("GOD_FEEL", where, "a god's theme entry in a fast section must have feel \"half\""))
        near = [j for j, x in events if j != i
                and abs(float(x["at_s"]) - float(e["at_s"])) <= GOD_DROP_WINDOW_S + 1e-9 and _intrudes_on_god(x)]
        if near:
            errors.append(_err("GOD_DROP", where, "a drop, a bright hit or a non-half hits/brass event lies within 1.0 s of a god's theme entry"))


def _check_rehook(plan, retention, errors):
    """A9: rehook_at_s inside cue retention.rehook_window_s."""
    r = plan.get("rehook_at_s")  # may be missing: the shape check already reported it
    win = retention.get("rehook_window_s")
    if not _is_num(r):
        errors.append(_err("REHOOK_WINDOW", "plan.rehook_at_s", "must be one finite number"))
    elif not _is_pair(win):
        errors.append(_err("REHOOK_WINDOW", "plan.rehook_at_s", "the cue sheet has no rehook window"))
    elif not (win[0] <= r <= win[1]):
        errors.append(_err("REHOOK_WINDOW", "plan.rehook_at_s", f"{r} is outside the rehook window {win}"))


def _check_peak(plan, secs, events, errors):
    """A10: exactly one peak, on an event or a section boundary."""
    p = plan.get("peak_at_s")  # may be missing: the shape check already reported it
    if p is None:
        errors.append(_err("PEAK", "plan.peak_at_s", "missing; one peak is required"))
    elif isinstance(p, list):
        errors.append(_err("PEAK", "plan.peak_at_s", f"exactly one peak is allowed; got a list of {len(p)}"))
    elif not _is_num(p):
        errors.append(_err("PEAK", "plan.peak_at_s", "must be one finite number"))
    else:
        marks = [e["at_s"] for _, e in events] + [s["start_s"] for _, s in secs] + [s["end_s"] for _, s in secs]
        if not any(abs(m - p) <= EXACT_S for m in marks):
            errors.append(_err("PEAK", "plan.peak_at_s", f"peak {p} is not an event time or a section boundary"))


def _check_logo(events, errors):
    """A11: exactly one sonic logo, at 0.0."""
    logos = [(i, e) for i, e in events if _etype(e) == "sonic_logo"]
    if len(logos) != 1:
        errors.append(_err("LOGO", "plan.events", f"expected one sonic_logo event, found {len(logos)}"))
    elif abs(logos[0][1]["at_s"]) > EXACT_S:
        errors.append(_err("LOGO", f"plan.events[{logos[0][0]}]", f"sonic_logo at {logos[0][1]['at_s']} s; it must be 0.0"))


def _check_nothing_new(cuts, secs, events, warnings):
    """Warning NOTHING_NEW_AT_CUT (PCR2-5, SKILL rule 6): a cut with no section boundary, no event within 1.0 s after it,
    and a transition of none or bed_continues."""
    bounds = [s["start_s"] for _, s in secs] + [s["end_s"] for _, s in secs]
    times = [float(e["at_s"]) for _, e in events]
    for i, c in cuts:
        at = float(c["at_s"])
        if any(abs(b - at) <= TOL_S for b in bounds):
            continue
        if any(at - EXACT_S <= t <= at + NEAR_S + 1e-9 for t in times):
            continue
        if c["transition"] in ("none", "bed_continues"):
            warnings.append(_err("NOTHING_NEW_AT_CUT", f"plan.cuts[{i}]",
                                 f"cut at {at} s has no section boundary, no event within 1.0 s after it, and a "
                                 f"{c['transition']!r} transition (SKILL rule 6)"))


def _check_end(events, retention, total_s, errors):
    """A12 (D14): one end sting, inside the end-hook window, low before the last spoken word, tail 0.45 s or less."""
    stings = [(i, e) for i, e in events if _etype(e) == "end_sting"]
    if len(stings) != 1:
        errors.append(_err("END_STING", "plan.events", f"expected one end_sting event, found {len(stings)}"))
        return
    i, e = stings[0]
    where = f"plan.events[{i}]"
    at = float(e["at_s"])
    eh = retention.get("end_hook_window_s")
    last = retention.get("last_speech_end_s")
    if not _is_pair(eh):
        errors.append(_err("END_STING", where, "the cue sheet has no end hook window"))
    elif not (eh[0] <= at <= eh[1]):
        errors.append(_err("END_STING", where, f"end sting at {at} s is outside the end hook window {eh}"))
    if not _is_num(last):
        errors.append(_err("END_STING", where, "the cue sheet has no last_speech_end_s"))
    elif at < last - EXACT_S and e.get("band") != LOW_BAND:
        errors.append(_err("END_STING", where,
                           f"end sting at {at} s is before the last spoken word {last} s; band must be low"))
    tail = e.get("tail_s")
    if not (_is_num(tail) and 0 <= tail <= TAIL_MAX_S):
        errors.append(_err("END_STING", where, f"tail_s {tail!r} must be a number from 0 to {TAIL_MAX_S}"))
    elif at + tail > total_s + EXACT_S:  # D24
        errors.append(_err("END_STING", where, f"the sting ends at {at + tail} s, past the reel's {total_s} s"))


def _preset_bad(v, presets):
    return not (_is_str(v) and v in presets)


def _check_refs(plan, secs, events, autos, bible, errors):
    """A13: every theme, role and preset the plan names exists in the bible."""
    themes = bible["themes"]
    roles = bible["track_roles"]
    presets = {v for k, v in bible["presets"].items() if not str(k).startswith("_") and _is_str(v)}
    for i, s in secs:
        for r in s["roles_on"]:
            if r not in roles:
                errors.append(_err("BIBLE_REF", f"plan.sections[{i}].roles_on", f"role {r!r} is not in track_roles"))
        if "preset" in s and _preset_bad(s["preset"], presets):
            errors.append(_err("BIBLE_REF", f"plan.sections[{i}].preset", f"preset {s['preset']!r} is not in bible presets"))
    for i, e in events:
        if "theme" in e and not (_is_str(e["theme"]) and e["theme"] in themes):
            errors.append(_err("BIBLE_REF", f"plan.events[{i}].theme", f"theme {e['theme']!r} is not in bible themes"))
        if "role" in e and e["role"] not in roles:
            errors.append(_err("BIBLE_REF", f"plan.events[{i}].role", f"role {e['role']!r} is not in track_roles"))
        if "preset" in e and _preset_bad(e["preset"], presets):
            errors.append(_err("BIBLE_REF", f"plan.events[{i}].preset", f"preset {e['preset']!r} is not in bible presets"))
    for i, e in events:  # a theme_entry's transform must be one the bible theme lists (PCR-transform)
        if "transform" in e:
            name = e.get("theme")
            theme = themes.get(name) if isinstance(name, str) else None
            transforms = _as_dict(_as_dict(theme).get("transforms"))
            if not (_is_str(e["transform"]) and e["transform"] in transforms):
                errors.append(_err("BIBLE_REF", f"plan.events[{i}].transform",
                                   f"transform {e['transform']!r} is not in the bible transforms of theme {name!r}"))
    for i, a in autos:
        if a["role"] not in roles:
            errors.append(_err("BIBLE_REF", f"plan.automation[{i}].role", f"role {a['role']!r} is not in track_roles"))
    if "presets" in plan:
        names = plan["presets"]
        if not isinstance(names, list):
            errors.append(_err("BIBLE_REF", "plan.presets", "must be a list of preset names"))
        else:
            for k, n in enumerate(names):
                if _preset_bad(n, presets):
                    errors.append(_err("BIBLE_REF", f"plan.presets[{k}]", f"preset {n!r} is not in bible presets"))


def _check_identity(plan, cue, bible, errors):
    """D19: the plan's home key and episode agree with the bible and the cue sheet."""
    bh = bible.get("home_key")
    if _is_str(bh) and plan.get("home_key") != bh:
        errors.append(_err("HOME_KEY_MISMATCH", "plan.home_key", f"plan home_key {plan.get('home_key')!r} is not the bible home_key {bh!r}"))
    if "episode" in cue and "episode" in plan and str(plan["episode"]) != str(cue["episode"]):
        errors.append(_err("EPISODE_MISMATCH", "plan.episode", f"plan episode {plan['episode']!r} is not the cue episode {cue['episode']!r}"))


# ---------------------------------------------------------------- the check

def _check(plan, cue, bible):
    errors, warnings = [], []
    cue_ok = _cue_shape(cue, errors)
    bible_ok = _bible_shape(bible, errors)
    if not (cue_ok and bible_ok):
        return _report(errors)
    if not isinstance(plan, dict):
        return _report([_err("PLAN_SHAPE", "plan", "the plan must be a JSON object")])

    _finite(plan, "plan", errors)
    window_end = _window_end(plan, cue, errors)
    window = window_end is not None
    if window and _ab_tempo(bible) is None:
        return _report(errors + [_err("BIBLE_SHAPE", "bible.ab_test_m1.A_tempo_map", "variant A needs A_tempo_map")])
    _plan_top_shape(plan, errors, window)
    secs = _items(plan, "sections", _shape_section, errors)
    events = _items(plan, "events", _shape_event, errors)
    cuts = _items(plan, "cuts", _shape_cut, errors)
    autos = _items(plan, "automation", _shape_automation, errors)
    for i, e in events:
        t = _etype(e)
        if t not in EVENT_TYPES:
            errors.append(_err("EVENT_TYPE_UNKNOWN", f"plan.events[{i}]", f"event type {e['type']!r} is not one of {sorted(EVENT_TYPES)}"))
        if t not in ROLELESS_TYPES and not _is_str(e.get("role")):
            errors.append(_err("EVENT_ROLE_MISSING", f"plan.events[{i}]", f"event {e['type']!r} needs a role"))

    total_s = float(cue["total_s"])
    acts = {a["act"] for a in cue["acts"]}
    cands = {}  # act -> genre -> set of bpm
    for row in cue["tempo_candidates"]:
        by_genre = cands.setdefault(row["act"], {})
        for genre, lst in row["candidates"].items():
            bucket = by_genre.setdefault(genre, set())
            for c in _as_list(lst):
                if isinstance(c, dict) and _is_num(c.get("bpm")):
                    bucket.add(float(c["bpm"]))
    ccuts = cue["cuts"]
    impacts = [(str(shot.get("id", "?")), imp) for shot in cue["shots"] for imp in shot["impacts"]]
    union = [(float(a), float(b)) for a, b in cue["voice"]["union"]]
    retention = cue["retention"]
    tm = bible.get("tempo_map") if isinstance(bible.get("tempo_map"), dict) else None
    if window:  # variant A: coverage, events, cuts and impacts count only inside 0 to window_end; A_tempo_map
        tm = _window_tempo_map(bible)
        total_s = window_end
        events = _window_filter(events, window_end, "plan.events", errors)
        cuts = _window_filter(cuts, window_end, "plan.cuts", errors)
        ccuts = [c for c in ccuts if float(c["at_s"]) < window_end - TOL_S]
        impacts = [(sid, imp) for sid, imp in impacts if float(imp["at_s"]) < window_end - TOL_S]

    _check_identity(plan, cue, bible, errors)
    _check_coverage(secs, total_s, errors)
    spans = [(a["act"], float(a["start_s"]), float(a["end_s"])) for a in cue["acts"]]
    _check_tempo(secs, acts, cands, ccuts, tm, _shot_windows(cue), spans, errors)
    _check_cuts(cuts, ccuts, errors)
    _check_impacts(events, impacts, union, errors, warnings)
    _check_dropouts(events, errors)
    _check_busy(secs, events, bible, union, errors)
    _check_gods(events, secs, errors)
    if not window:  # variant A has no re-hook or end sting (both are in the full reel)
        _check_rehook(plan, retention, errors)
        _check_end(events, retention, total_s, errors)
    if not window or "peak_at_s" in plan:
        _check_peak(plan, secs, events, errors)
    _check_logo(events, errors)
    _check_nothing_new(cuts, secs, events, warnings)
    _check_refs(plan, secs, events, autos, bible, errors)

    for i, s in secs:
        if not _is_str(s.get("why")):
            warnings.append(_err("SECTION_WHY_MISSING", f"plan.sections[{i}]", "no one-sentence why (SKILL step 3)"))
    stats = {"sections": len(secs), "events": len(events), "hits": sum(1 for _, e in events if _etype(e) == "hit"),
             "cuts": len(cuts), "cue_cuts": len(ccuts), "impacts": len(impacts), "voice_windows": len(union),
             "total_s": total_s}
    return _report(errors, warnings, stats)


def check_plan(plan, cue_sheet, bible):
    """Check one score plan against its cue sheet and bible. Returns the report. Never raises."""
    try:
        return _check(plan, cue_sheet, bible)
    except Exception as exc:  # last-resort guard: the checker reports, it never crashes the caller
        return _report([_err("CHECK_CRASH", "plan_check", f"{type(exc).__name__}: {exc}")])


# ---------------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m score.plan_check",
                                description="Check a score_plan.json against its cue sheet and music bible.")
    p.add_argument("--plan", required=True, help="score_plan.json")
    p.add_argument("--cue-sheet", required=True, help="cue_sheet.json (score/cue_sheet.py output)")
    p.add_argument("--bible", required=True, help="stories/<slug>/music_bible.json")
    a = p.parse_args(argv)
    loaded = {}
    for label, path in (("plan", a.plan), ("cue sheet", a.cue_sheet), ("bible", a.bible)):
        try:
            loaded[label] = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError, MemoryError) as exc:
            print(f"cannot read {label} {path}: {exc}", file=sys.stderr)
            return 2
    report = check_plan(loaded["plan"], loaded["cue sheet"], loaded["bible"])
    for e in report["errors"]:
        print(f"ERROR {e['code']} {e['where']}: {e['message']}", file=sys.stderr)
    for w in report["warnings"]:
        print(f"warn  {w['code']} {w['where']}: {w['message']}", file=sys.stderr)
    verdict = "ok" if report["ok"] else "FAILED"
    print(f"{verdict}: {len(report['errors'])} errors, {len(report['warnings'])} warnings, "
          f"{report['stats'].get('sections', 0)} sections, {report['stats'].get('events', 0)} events")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
