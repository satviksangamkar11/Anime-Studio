"""Score stage D: Ableton build recipe and Serum sound briefs. Pure stdlib; never calls Ableton or serum-mcp.

Input: notes (checklist C1 shape: {"tracks": {role: [{"t_s","dur_s","pitch","vel"}]}, "markers": [{"t_s","name"}],
"automation": [{"role","macro","points": [[t_s, value]]}]}), a score plan (score_plan.json v1) and the music bible.
Output: build_recipe -> ordered list of {"tool", "args", "expect"} calls for the owner's AbletonMCP server
(D:/ableton claude final best/serum2/ableton/ableton_mcp_extended/server.py), plus {"manual": text} steps for anything
that server cannot do. serum_briefs -> {role: text brief} for the owner's serum-mcp generate_preset. A later step replays
the recipe; this module only writes JSON and text. Nothing here calls a tool.

Conventions copied from the owner's docs and server.py:
- Clock mode: set_tempo 60, so 1 beat = 1 second. Every start_beat, start_time, duration and length is seconds.
- Track indices are integers (1-based). Serum role tracks are created in bible order, so role i (from 1) is track i;
  the MARKERS track is track N+1 (N = number of Serum roles). get_session_info with track_count 0 runs first, and one
  readback after the track block expects track_count N+1.
- "expect" on every tool step: {"not_startswith": "Error"} for text results, {"json_status_not": "FAILED"} for the JSON
  results (get_session_info, create_serum_track). The replayer checks it after each call.
- A Serum track is made by create_serum_track, which loads a .SerumPreset file. That file comes from serum-mcp
  generate_preset first, so each create step is preceded by a manual step and carries "needs": ["preset_path:<role>"].
  The replayer refuses the step until the path is filled (server.py rejects anything that is not a .serumpreset file).
- Macros: every Serum preset has Macro 1 brightness, Macro 2 motion, Macro 3 width, Macro 4 space (routing lives in the
  preset). set_device_parameter sets each macro to 0.5 ("Macro n" is an alias there only). Automation (manage_clip_automation)
  uses the same names, and a manual step asks the owner to verify them against the generated preset.
- MARKERS: a MIDI track with one empty arrangement clip per shot; set_arrangement_clip_property gives each clip its name
  (server.py create_arrangement_midi_clip accepts name but does not send it).

Decisions:
- Serum roles = keys of bible["presets"] that do not start with "_". Roles in notes without a preset are skipped with a
  manual step.
- Notes go through a session clip (create_clip, length = total_s beats, slot 1), add_notes_to_clip, then
  duplicate_clip_to_arrangement at bar 1 beat 0, then set_arrangement_clip_property names it after the role. No
  add-notes-to-arrangement tool exists in server.py, so this session-clip route is the only one.
- total_s = largest end_s in plan["sections"] (plan_check requires the sections to cover 0..total_s).
- Automation: for every role that has an arrangement clip, manage_clip_automation creates envelopes for volume and
  Macro 1-4 (no points argument exists in server.py). The points stay manual: ONE manual step per role lists its points
  from notes["automation"] as [t_s, value] so the owner can replay them. No points writer is invented.
- Cue points: create_cue_point with bar=0 so the server uses beat as-is (seconds). SKILL.md says Live cannot write
  locators; the recipe ends with get_cue_points as a readback, and a failed readback is a finding, not a pass.
- Duplicate marker times: the first marker keeps its time, later ones are dropped with a manual step naming both.
- Malformed notes, markers or automation are skipped and reported (manual steps and check_inputs errors); nothing raises.
- Times are rounded to 6 decimals; a note must start inside [0, total_s] and end by total_s; automation points need
  t in [0, total_s] and value in [0, 1].
- Brief text is plain text, one per Serum role, built from the bible and the plan sections that use the role.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

TEMPO_BPM = 60.0
MACROS = {1: "brightness", 2: "motion", 3: "width", 4: "space"}
JSON_TOOLS = {"get_session_info", "create_serum_track"}
MAX_REPORT = 50


def _dict(x):
    return x if isinstance(x, dict) else {}


def _list(x):
    return x if isinstance(x, list) else []


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _r(x):
    return round(float(x), 6)


def _step(tool, args, expect=None, needs=None):
    exp = {"json_status_not": "FAILED"} if tool in JSON_TOOLS else {"not_startswith": "Error"}
    if expect:
        exp.update(expect)
    step = {"tool": tool, "args": args, "expect": exp}
    if needs:
        step["needs"] = needs
    return step


def _presets(bible):
    raw = _dict(_dict(bible).get("presets"))
    return {k: v for k, v in raw.items()
            if isinstance(k, str) and not k.startswith("_") and isinstance(v, str) and v}


def _total_s(plan):
    ends = [s["end_s"] for s in _list(_dict(plan).get("sections"))
            if isinstance(s, dict) and _num(s.get("end_s"))]
    if not ends or max(ends) <= 0:
        return None
    return float(max(ends))


def _clean_note(item, total):
    """Return (note_dict, None) or (None, reason)."""
    if not isinstance(item, dict):
        return None, "note is not an object"
    t, dur, pitch, vel = item.get("t_s"), item.get("dur_s"), item.get("pitch"), item.get("vel")
    if not (_num(t) and _num(dur) and _num(pitch) and _num(vel)):
        return None, "note has a non-numeric field"
    if t < 0 or dur <= 0 or t >= total or t + dur > total + 1e-9:
        return None, "note outside 0..total_s or zero length (t_s=%s dur_s=%s)" % (t, dur)
    if int(pitch) != pitch or not 0 <= pitch <= 127:
        return None, "pitch not an integer 0-127"
    if int(vel) != vel or not 0 <= vel <= 127:
        return None, "velocity not an integer 0-127"
    return {"pitch": int(pitch), "start_time": _r(t), "duration": _r(dur),
            "velocity": int(vel), "mute": False}, None


def _markers(notes, total):
    """(rows, problems): rows are (t, length, name) sorted by time; duplicate times and bad rows become problems."""
    raw, problems = [], []
    for m in _list(_dict(notes).get("markers")):
        if not (isinstance(m, dict) and _num(m.get("t_s")) and isinstance(m.get("name"), str)):
            problems.append("marker malformed: %r" % (m,))
            continue
        raw.append((float(m["t_s"]), m["name"]))
    raw.sort()
    kept, seen = [], {}
    for t, name in raw:
        if t in seen:
            problems.append("duplicate marker time %s: %s and %s (second dropped)" % (_r(t), seen[t], name))
            continue
        seen[t] = name
        kept.append((t, name))
    out = []
    for i, (t, name) in enumerate(kept):
        end = kept[i + 1][0] if i + 1 < len(kept) else total
        length = end - t
        if t < 0 or t >= total or length <= 0:
            problems.append("marker %s outside 0..total_s" % name)
            continue
        out.append((_r(t), _r(length), name))
    return out, problems


def _points_problem(points, total):
    if not (isinstance(points, list) and points):
        return "points not a non-empty list"
    for p in points:
        if not (isinstance(p, list) and len(p) == 2 and _num(p[0]) and _num(p[1])):
            return "point %r is not [t_s, value]" % (p,)
        if not 0 <= p[0] <= total:
            return "point time %s outside 0..total_s" % p[0]
        if not 0 <= p[1] <= 1:
            return "point value %s outside 0..1" % p[1]
    return None


def _automation_param(macro):
    if macro == "volume":
        return "volume"
    if isinstance(macro, int) and not isinstance(macro, bool) and macro in MACROS:
        return "Macro %d" % macro
    return None


def build_recipe(notes, plan, bible):
    """Ordered tool steps plus manual steps. Never raises."""
    notes, plan, bible = _dict(notes), _dict(plan), _dict(bible)
    presets = _presets(bible)
    roles = list(presets)
    idx = {role: i + 1 for i, role in enumerate(roles)}
    marker_idx = len(roles) + 1
    recipe = [_step("get_session_info", {}, {"track_count": 0}),
              _step("set_tempo", {"tempo": TEMPO_BPM})]
    total = _total_s(plan)
    if total is None:
        recipe.append({"manual": "PLAN: no section with end_s > 0; clips cannot be sized. Fix the plan first."})
        return recipe

    # 1. Tracks: one Serum track per role in bible order, each with its macros at the start position.
    for role in roles:
        preset = presets[role]
        recipe.append({"manual": "Generate Serum preset %s with serum-mcp generate_preset from "
                                 "serum_briefs()[%s]; fill preset_path before this step runs." % (preset, role)})
        recipe.append(_step("create_serum_track",
                            {"preset_path": "<path of %s>" % preset, "name": role},
                            needs=["preset_path:" + role]))
        for n in MACROS:
            recipe.append(_step("set_device_parameter",
                                {"track_index": idx[role], "device_index": 1, "chain_index": 0,
                                 "parameter_name": "Macro %d" % n, "value": 0.5}))
    recipe.append(_step("create_midi_track", {"index": -1}))
    recipe.append(_step("set_track_name", {"track_index": marker_idx, "name": "MARKERS"}))
    recipe.append(_step("get_session_info", {}, {"track_count": marker_idx}))

    # 2. Role clips: session clip with notes, copied to the arrangement at bar 1, then named.
    tracks = _dict(notes.get("tracks"))
    placed = []
    for role, items in tracks.items():
        if role not in presets:
            recipe.append({"manual": "Role %s has no Serum preset in the bible; its %d notes were not placed."
                                     % (role, len(_list(items)))})
            continue
        good = []
        for item in _list(items):
            note, why = _clean_note(item, total)
            if note is None:
                recipe.append({"manual": "SKIPPED note in role %s: %s" % (role, why)})
            else:
                good.append(note)
        if not good:
            continue
        placed.append(role)
        ti = idx[role]
        recipe.append(_step("create_clip", {"track_index": ti, "clip_index": 1, "length": _r(total)}))
        recipe.append(_step("add_notes_to_clip", {"track_index": ti, "clip_index": 1, "notes": good}))
        recipe.append(_step("duplicate_clip_to_arrangement",
                            {"track_index": ti, "clip_index": 1, "destination_bar": 1, "destination_beat": 0.0}))
        recipe.append(_step("set_arrangement_clip_property", {"track_index": ti, "clip_index": 1, "name": role}))

    # 3. MARKERS: one empty named arrangement clip per shot, then its name, cue points and a readback.
    markers, problems = _markers(notes, total)
    for p in problems:
        recipe.append({"manual": "SKIPPED %s" % p})
    for pos, (t, length, name) in enumerate(markers, start=1):
        recipe.append(_step("create_arrangement_midi_clip",
                            {"track_index": marker_idx, "start_bar": 0, "end_bar": 0, "start_beat": t,
                             "length_beats": length, "name": name}))
        recipe.append(_step("set_arrangement_clip_property",
                            {"track_index": marker_idx, "clip_index": pos, "name": name}))
    for t, _length, name in markers:
        recipe.append(_step("create_cue_point", {"bar": 0, "beat": t, "name": name}))
    if markers:
        recipe.append(_step("get_cue_points", {}))

    # 4. Automation: envelopes for every role clip; points listed by hand (no points argument exists).
    by_role = {}
    for entry in _list(notes.get("automation")):
        entry = _dict(entry)
        role = entry.get("role")
        param = _automation_param(entry.get("macro"))
        if role not in presets or param is None:
            recipe.append({"manual": "SKIPPED automation entry %r" % (entry,)})
            continue
        why = _points_problem(entry.get("points"), total)
        if why:
            recipe.append({"manual": "SKIPPED automation for role %s %s: %s" % (role, param, why)})
            continue
        by_role.setdefault(role, {})[param] = entry["points"]
    for role in placed:
        ti = idx[role]
        for param in ["volume"] + ["Macro %d" % n for n in MACROS]:
            recipe.append(_step("manage_clip_automation",
                                {"track_index": ti, "clip_index": 1, "action": "create", "parameter_name": param}))
        recipe.append({"manual": "Verify the parameter names volume and Macro 1-4 exist in the generated preset %s "
                                 "for role %s before writing points." % (presets[role], role)})
        recipe.append({"manual": "Write automation points for role %s on arrangement clip 1 (no points tool in "
                                 "server.py): %s" % (role, json.dumps(by_role.get(role, {}), sort_keys=True))})
    for role in by_role:
        if role not in placed:
            recipe.append({"manual": "SKIPPED automation for role %s: no arrangement clip on that track" % role})
    return recipe


def check_inputs(notes, plan, bible):
    """List of error strings for the three inputs (empty list = ok). Never raises."""
    errs = []
    n = _dict(notes)
    if not isinstance(notes, dict):
        errs.append("notes: not an object")
    if not isinstance(n.get("tracks"), dict):
        errs.append("notes.tracks: not an object")
    total = _total_s(plan)
    if total is None:
        errs.append("plan: no section with end_s > 0")
    check_total = total if total is not None else math.inf
    for role, items in _dict(n.get("tracks")).items():
        if not isinstance(items, list):
            errs.append("notes.tracks.%s: not a list" % role)
            continue
        for i, item in enumerate(items):
            why = _clean_note(item, check_total)[1]
            if why:
                errs.append("notes.tracks.%s[%d]: %s" % (role, i, why))
    for prob in _markers(n, check_total)[1]:
        errs.append("notes.markers: " + prob)
    if not isinstance(n.get("automation", []), list):
        errs.append("notes.automation: not a list")
    for i, entry in enumerate(_list(n.get("automation"))):
        entry = _dict(entry)
        if entry.get("role") not in _presets(bible):
            errs.append("notes.automation[%d]: unknown role %r" % (i, entry.get("role")))
        if _automation_param(entry.get("macro")) is None:
            errs.append("notes.automation[%d]: macro %r is not 1-4 or volume" % (i, entry.get("macro")))
        why = _points_problem(entry.get("points"), check_total)
        if why:
            errs.append("notes.automation[%d]: %s" % (i, why))
    if not _presets(bible):
        errs.append("bible: no presets (role -> preset name)")
    return errs[:MAX_REPORT]


def serum_briefs(bible, plan):
    """{role: text brief} for serum-mcp generate_preset. Text only; no call is made."""
    bible, plan = _dict(bible), _dict(plan)
    meta_all = _dict(bible.get("track_roles"))
    sections = [s for s in _list(plan.get("sections")) if isinstance(s, dict)]
    out = {}
    for role, preset in _presets(bible).items():
        meta = _dict(meta_all.get(role))
        lines = [
            "Serum 2 preset for the '%s' track of a background score (music only: no sound effects, no voice)." % role,
            "Preset name: %s. Make it with generate_preset, name = preset name." % preset,
            "Home key: %s. Style: %s." % (bible.get("home_key", "?"), bible.get("style", "?")),
        ]
        if meta.get("range"):
            lines.append("Range: %s." % meta["range"])
        if meta.get("note"):
            lines.append("Role note: %s." % meta["note"])
        if meta.get("busy"):
            lines.append("Busy role: stays out of 1-4 kHz inside voice windows; the note writer gates it there.")
        for s in sections:
            if role in _list(s.get("roles_on")):
                lines.append("Used %s-%s s, act %s, %s BPM, feel %s, genre %s, intensity %s."
                             % (s.get("start_s"), s.get("end_s"), s.get("act"), s.get("bpm"),
                                s.get("feel"), s.get("genre"), s.get("intensity")))
        lines.append("Macros (every preset): Macro 1 brightness, Macro 2 motion, Macro 3 width, Macro 4 space. "
                     "Route each macro to at least two destinations.")
        lines.append("Original sound design only: no samples, copied recordings or chants.")
        out[role] = "\n".join(lines) + "\n"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the Ableton recipe JSON and one Serum brief per role.")
    ap.add_argument("--notes", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--bible", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    try:
        notes, plan, bible = (json.loads(Path(p).read_text(encoding="utf-8"))
                              for p in (a.notes, a.plan, a.bible))
    except (OSError, ValueError) as e:
        print(json.dumps({"ok": False, "errors": ["unreadable input: %s" % e]}))
        return 2
    errs = check_inputs(notes, plan, bible)
    if errs:
        print(json.dumps({"ok": False, "errors": errs}, indent=1))
        return 1
    out = Path(a.out_dir)
    (out / "briefs").mkdir(parents=True, exist_ok=True)
    recipe = build_recipe(notes, plan, bible)
    (out / "ableton_recipe.json").write_text(json.dumps(recipe, indent=1), encoding="utf-8")
    for role, text in serum_briefs(bible, plan).items():
        (out / "briefs" / ("%s.txt" % role)).write_text(text, encoding="utf-8")
    print(json.dumps({"ok": True, "steps": len(recipe)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
