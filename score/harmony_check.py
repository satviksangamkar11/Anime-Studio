"""Harmony checker for the reel's score: scale, themes, chords, bass and the MIDI round trip.

Pure: no models, no network, no random. Reads the output of score/note_writer.py write_notes (or any tracks dict in
the same shape) plus the score plan, the cue sheet and the story's music_bible.json. Never edits the inputs.

check_harmony(plan, cue_sheet, bible) -> result (runs write_notes first)
check_tracks(tracks, plan, cue_sheet, bible, markers=None) -> result (for tracks built by hand, e.g. in tests)
render_report(result, title) -> markdown text
CLI: python -m score.harmony_check [--plan P] [--cue C] [--bible B] [--report OUT.md] [--json OUT.json]

Checks (ids are the summary keys):
  1 scale   every non-drum note is D natural minor (D E F G A Bb C) plus the colour the section's harmony text names
            (Dorian: B, Lydian: G#, Phrygian: Eb, Mixolydian/Kamadeva: F# and C). A note that is a bible theme or
            transform note (same role, onset and pitch as a theme_entry) is checked by check 2 instead.
  2 themes  every theme_entry sounds its bible degrees (or transform pitches) in order on its role, with the octave
            partner +12 (or +24 when +12 is still below G3) at the same onset.
  3 chords  a chord name at every onset of a non-drum note. Flags:
              a  minor 2nd / major 7th between two sustained non-theme voices, overlap over 0.25 s
              b  bass root (below 200 Hz) not in the pitch classes of the voices above it
              c  resolved D minor tonic (D F A, D in the bass) on a strong beat in a suspense shot or the closing shot
              d  end sting chord not D E A (Dsus2 shape)
              e  pad or drone holding a pitch a minor 2nd from a theme note at the same time (the theme wins)
  4 bass    every bass root below 200 Hz has its phone mid harmonic root + 19 (A3 above D2) at the same onset;
            drone notes stay below 200 Hz.
  5 midi    write_midi output re-read with the test-side parser gives the same notes and markers.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from score import note_writer as nw

EPS = 1e-9
TOL = 0.006                 # onset match tolerance, s (one frame is 0.042 s)
ONSET_CLUSTER = 0.02        # onsets closer than this are one onset
HOME_PCS = frozenset({2, 4, 5, 7, 9, 10, 0})  # D E F G A Bb C
COLOUR_WORDS = (("Dorian", frozenset({11}), "B natural"),
                ("Lydian", frozenset({8}), "G# (raised 4th)"),
                ("Phrygian", frozenset({3}), "Eb (flat 2nd)"),
                ("Mixolydian", frozenset({6, 0}), "F# and C"),
                ("Kamadeva", frozenset({6, 0}), "F# and C"))
DRUM_ROLES = frozenset({"drums", "folk_perc"})
PAD_ROLES = frozenset({"pad", "drone"})
CHORD_LAYER_ROLES = frozenset({"drone", "pad", "bass", "ostinato"})  # item B: only these make a chord for check 3c
PEDAL_ROLES = frozenset({"bass", "drone"})                          # item C: a D pedal under a Phrygian bII pad
OCTAVE_MINOR2ND = 13                                                 # item C: a minor 9th or wider
CLASH = (1, 11)             # minor 2nd and major 7th, as pitch-class distance
LOW_HZ = 200.0
PHONE_MIN = nw.PHONE_MIN    # 55 = G3: theme notes below it get an octave partner
PC_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B")
CHORD_SHAPES = (("", (0, 4, 7)), ("m", (0, 3, 7)), ("dim", (0, 3, 6)), ("aug", (0, 4, 8)),
                ("sus2", (0, 2, 7)), ("sus4", (0, 5, 7)), ("5", (0, 7)),
                ("maj7", (0, 4, 7, 11)), ("7", (0, 4, 7, 10)), ("m7", (0, 3, 7, 10)),
                ("m7b5", (0, 3, 6, 10)), ("add9", (0, 2, 4, 7)), ("madd9", (0, 2, 3, 7)))
CHORD_FLAG_TEXT = {
    "a": "minor 2nd / major 7th between two sustained non-theme voices",
    "b": "bass root not in the chord above it",
    "c": "resolved D minor tonic on a strong beat in suspense or closing",
    "d": "end sting is not Dsus2 (D E A)",
    "e": "pad or drone clashes a minor 2nd with a theme note (theme wins)",
}
_TOKEN = re.compile(r"(?<![A-Za-z])([A-G])(#|b)?(-?\d+)(?!\d)")
_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACC = {"#": 1, "b": -1, "": 0}


# ---------------------------------------------------------------- helpers

def pname(p):
    """MIDI pitch -> name in scientific pitch (60 = C4)."""
    return f"{PC_NAMES[p % 12]}{p // 12 - 1}"


def hz(p):
    return 440.0 * 2 ** ((p - 69) / 12.0)


def parse_pitches(text):
    """Pitches of the note names in a bible degrees string ('A3 D4 F4 E4'). None if there are none."""
    if not isinstance(text, str):
        return None
    out = [12 * (int(octv) + 1) + _SEMI[letter] + _ACC[acc] for letter, acc, octv in _TOKEN.findall(text)]
    return out or None


def partner_of(p):
    """Octave partner rule of note_writer (rule 20): +12, or +24 when +12 is still below G3."""
    if p >= PHONE_MIN:
        return None
    return p + 12 if p + 12 >= PHONE_MIN else p + 24


def colour_of(harmony):
    """(pitch classes the harmony text adds to D natural minor, the names it adds)."""
    text = harmony if isinstance(harmony, str) else ""
    pcs, names = set(), []
    for word, extra, label in COLOUR_WORDS:
        if word in text:
            pcs |= extra
            names.append(f"{word}: {label}")
    return frozenset(pcs), names


def chord_name(pcs, bass_pc=None):
    """Chord name for a set of pitch classes. Bass root is tried first; 'cluster {...}' when nothing matches."""
    pcs = frozenset(pcs)
    if not pcs:
        return "none"
    if len(pcs) == 1:
        return PC_NAMES[next(iter(pcs))] + " (single pitch class)"
    roots = sorted(pcs, key=lambda r: (r != bass_pc, r))
    for r in roots:
        rel = frozenset((p - r) % 12 for p in pcs)
        for suffix, shape in CHORD_SHAPES:
            if rel == frozenset(shape):
                name = PC_NAMES[r] + suffix
                if bass_pc is not None and bass_pc != r:
                    name += "/" + PC_NAMES[bass_pc]
                return name
    return "cluster {" + " ".join(PC_NAMES[p] for p in sorted(pcs)) + "}"


def _sections(plan):
    out = []
    for i, s in enumerate(plan.get("sections") or []):
        if not isinstance(s, dict):
            continue
        out.append({"idx": i + 1, "start": float(s["start_s"]), "end": float(s["end_s"]),
                    "bpm": float(s.get("bpm", 60)), "feel": s.get("feel", "normal"),
                    "harmony": s.get("harmony", ""), "genre": s.get("genre", ""), "act": s.get("act", ""),
                    "roles": s.get("roles_on", [])})
    return out


def _sec_at(secs, t):
    for s in secs:
        if s["start"] - EPS <= t < s["end"] - EPS:
            return s
    if secs and abs(t - secs[-1]["end"]) <= 1e-6:
        return secs[-1]
    return None


def _windows(cue):
    voice, susp, clos = [], [], []
    v = cue.get("voice") if isinstance(cue.get("voice"), dict) else {}
    for w in v.get("union") or []:
        if isinstance(w, (list, tuple)) and len(w) == 2:
            voice.append((float(w[0]), float(w[1])))
    shots = [s for s in (cue.get("shots") or []) if isinstance(s, dict)]
    for s in shots:
        win = (float(s["start_s"]), float(s["end_s"]))
        if s.get("hook_type") == "suspense":
            susp.append(win)
        if s.get("closing_hook") or s.get("hook_type") == "closing":
            clos.append(win)
    return voice, susp, clos


def _in(wins, t):
    return any(a - EPS <= t < b - EPS for a, b in wins)


def _flatten(tracks):
    out = []
    for role, notes in tracks.items():
        for n in notes:
            t = float(n["t_s"])
            out.append({"role": role, "t": t, "e": t + float(n["dur_s"]), "p": int(n["pitch"]),
                        "v": int(n["vel"]), "tag": None})
    out.sort(key=lambda n: (n["t"], n["p"], n["role"]))
    return out


def _expand_themes(plan, bible, secs, flags):
    """Expected theme notes: one dict per (entry, step, kind). Bad entries are flagged and skipped."""
    themes = bible.get("themes") if isinstance(bible.get("themes"), dict) else {}
    entries, expected = [], []
    for i, ev in enumerate(plan.get("events") or []):
        if not isinstance(ev, dict) or ev.get("type") != "theme_entry":
            continue
        where = f"plan.events[{i}]"
        name = ev.get("theme")
        entry = themes.get(name) if isinstance(name, str) else None
        try:
            at = float(ev["at_s"])
        except (KeyError, TypeError, ValueError):
            flags.append(_flag("2 themes", "bad", at=None, role=None, p=None, sec=None,
                               reason=f"{where}: at_s missing"))
            continue
        role = ev.get("role") or "lead"
        if not isinstance(entry, dict):
            flags.append(_flag("2 themes", "bad", at, role, None, None, f"{where}: theme {name!r} not in the bible"))
            continue
        pitches = parse_pitches(entry.get("degrees"))
        tr = ev.get("transform")
        if tr is not None:
            trs = entry.get("transforms") if isinstance(entry.get("transforms"), dict) else {}
            pitches = parse_pitches(trs.get(tr)) if isinstance(tr, str) else None
            if pitches is None:
                flags.append(_flag("2 themes", "bad", at, role, None, None,
                                   f"{where}: transform {tr!r} is not a bible transform of {name}"))
                continue
        if pitches is None:
            flags.append(_flag("2 themes", "bad", at, role, None, None, f"{where}: {name} has no bible degrees"))
            continue
        allowed = entry.get("roles")
        if isinstance(allowed, list) and role not in allowed:
            flags.append(_flag("2 themes", "bad", at, role, None, None,
                               f"{where}: {name} may play {allowed}, not {role}"))
        sec = _sec_at(secs, at)
        bpm = sec["bpm"] if sec else 60.0
        step = 60.0 / bpm * nw.FEEL_STEP.get(ev.get("feel", "normal"), 1.0)
        idx = len(entries)
        steps = []
        for k, p in enumerate(pitches):
            t = at + k * step
            steps.append({"k": k, "t": t, "p": p, "key": (idx, k, "degree"), "role": role})
            q = None if role == "pad" else partner_of(p)  # item A: a pad entry sounds its bible pitches exactly
            if q is not None:
                steps.append({"k": k, "t": t, "p": q, "key": (idx, k, "octave"), "role": role})
        entries.append({"idx": idx, "event": i, "theme": name, "role": role, "transform": tr, "at": at,
                        "step": step, "pitches": pitches, "steps": steps, "sec": sec["idx"] if sec else None})
        expected.extend(steps)
    return entries, expected


def _tag(out, expected):
    """Mark the notes that are theme notes: same role, onset within TOL and pitch. Returns key -> note."""
    by_role = {}
    for ex in expected:
        by_role.setdefault(ex["role"], []).append(ex)
    times = {}
    for role, lst in by_role.items():
        lst.sort(key=lambda x: x["t"])
        times[role] = [x["t"] for x in lst]
    found = {}
    for n in out:
        lst = by_role.get(n["role"])
        if not lst:
            continue
        i = bisect.bisect_left(times[n["role"]], n["t"] - TOL)
        while i < len(lst) and lst[i]["t"] <= n["t"] + TOL:
            if lst[i]["p"] == n["p"] and lst[i]["key"] not in found:
                n["tag"] = lst[i]["key"]
                found[lst[i]["key"]] = n
                break
            i += 1
    return found


def _flag(check, sub, at, role, p, sec, reason):
    return {"check": check, "sub": sub, "t": None if at is None else round(at, 3), "role": role,
            "pitch": None if p is None else pname(p), "midi": p, "section": sec, "reason": reason}


# ---------------------------------------------------------------- checks

def _check_themes(entries, found, voice, gated, flags):
    rows, ok_notes, bad_notes = [], 0, 0
    for en in entries:
        want, got, bad = [], [], False
        for st in en["steps"]:
            want.append(pname(st["p"]) if st["key"][2] == "degree" else "(+oct)")
            n = found.get(st["key"])
            if n is None:
                bad = True
                bad_notes += 1
                why = "not in the output"
                if st["p"] > nw.LOW_MAX and st["role"] in gated and _in(voice, st["t"]):
                    why = "cut by the voice gate (rule 2: pitch above D3 under voice)"
                got.append("—")
                flags.append(_flag("2 themes", "missing", st["t"], st["role"], st["p"], en["sec"],
                                   f"{en['theme']} {'octave partner' if st['key'][2] == 'octave' else 'note'} "
                                   f"{pname(st['p'])} at {st['t']:.3f} s: {why}"))
            else:
                ok_notes += 1
                got.append(pname(n["p"]))
        rows.append({"idx": en["idx"], "theme": en["theme"], "role": en["role"], "at": en["at"],
                     "transform": en["transform"], "want": " ".join(w for w in want if w != "(+oct)"),
                     "got": " ".join(g for g in got)})
        if bad:
            pass
    return rows, ok_notes, bad_notes


def _check_scale(out, secs, flags):
    checked = 0
    for n in out:
        if n["role"] in DRUM_ROLES:
            continue
        checked += 1
        if n["tag"] is not None:
            continue
        sec = _sec_at(secs, n["t"])
        if sec is None:
            flags.append(_flag("1 scale", "", n["t"], n["role"], n["p"], None, "outside every section"))
            continue
        colour, names = colour_of(sec["harmony"])
        if n["p"] % 12 in HOME_PCS or n["p"] % 12 in colour:
            continue
        ctext = "; ".join(names) if names else "no colour in the harmony text"
        flags.append(_flag("1 scale", "", n["t"], n["role"], n["p"], sec["idx"],
                           f"not in D natural minor; section {sec['idx']} harmony '{sec['harmony']}' "
                           f"({ctext})"))
    return checked


def _onset_rows(out):
    """Non-drum notes grouped into onsets. Yields (t, sounding notes) with the sounding set built by a sweep."""
    nd = [n for n in out if n["role"] not in DRUM_ROLES]
    onsets = []
    for n in nd:
        if not onsets or n["t"] - onsets[-1] > ONSET_CLUSTER:
            onsets.append(n["t"])
    active, j = [], 0
    for t in onsets:
        while j < len(nd) and nd[j]["t"] <= t + 0.005:
            active.append(nd[j])
            j += 1
        active = [n for n in active if n["e"] > t + 0.005]
        yield t, list(active), nd


def _check_chords(out, secs, voice, susp, clos, events_end, flags):
    rows = []
    for t, sounding, nd in _onset_rows(out):
        sec = _sec_at(secs, t)
        pcs = {n["p"] % 12 for n in sounding}
        low = min(sounding, key=lambda n: n["p"])["p"] % 12 if sounding else None
        name = chord_name(pcs, low)
        rows.append({"t": round(t, 3), "sec": sec["idx"] if sec else None, "name": name,
                     "pcs": sorted(pcs), "low": low})
        roots = [n for n in sounding if n["role"] == "bass" and abs(n["t"] - t) <= 0.005 and n["p"] <= 55]
        uppers = [n for n in sounding if n["role"] != "bass"]
        upper = {n["p"] % 12 for n in uppers}
        for r in roots:  # (b)
            # item C: in a Phrygian section a bII pad an octave and a minor 2nd or more over the D pedal is the colour
            phrygian_pedal = bool(sec) and "Phrygian" in str(sec["harmony"]) and bool(uppers) and \
                all(n["p"] >= r["p"] + OCTAVE_MINOR2ND for n in uppers)
            if upper and r["p"] % 12 not in upper and not phrygian_pedal:
                flags.append(_flag("3 chords", "b", t, "bass", r["p"], sec["idx"] if sec else None,
                                   f"bass {pname(r['p'])} not in the voices above ({chord_name(upper)})"))
        layer = [n for n in sounding if n["role"] in CHORD_LAYER_ROLES and n["tag"] is None]  # item B
        lpcs = {n["p"] % 12 for n in layer}
        llow = min(layer, key=lambda n: n["p"])["p"] % 12 if layer else None
        if sec and {2, 5, 9} <= lpcs and llow == 2:  # (c)
            beat = 60.0 / sec["bpm"]
            k = (t - sec["start"]) / beat
            strong = abs(k - round(k)) * beat <= 0.02
            in_end = any(a - 0.005 <= t <= a + 0.5 for a in events_end)
            if strong and (_in(susp, t) or _in(clos, t) or in_end):
                flags.append(_flag("3 chords", "c", t, "all", None, sec["idx"],
                                   "resolved D minor tonic (D F A, D in the bass) on a strong beat in "
                                   "suspense/closing: must stay unresolved"))
    return rows


def _check_chord_clashes(out, flags, secs=()):
    nd = [n for n in out if n["role"] not in DRUM_ROLES and n["tag"] is None]
    for i, a in enumerate(nd):
        for b in nd[i + 1:]:
            if b["t"] >= a["e"] - 0.25:
                break
            overlap = min(a["e"], b["e"]) - b["t"]
            if overlap > 0.25 and abs(a["p"] - b["p"]) % 12 in CLASH:
                # item C: a pad an octave and a minor 2nd (or more) over a pedal in a Phrygian section is the colour
                roles = {a["role"], b["role"]}
                sec = _sec_at(secs, b["t"])
                if "pad" in roles and roles & PEDAL_ROLES and abs(a["p"] - b["p"]) >= OCTAVE_MINOR2ND \
                        and sec is not None and "Phrygian" in str(sec["harmony"]):
                    continue
                flags.append(_flag("3 chords", "a", b["t"], f"{a['role']}/{b['role']}", b["p"], None,
                                   f"{pname(a['p'])} ({a['role']}) and {pname(b['p'])} ({b['role']}) "
                                   f"a minor 2nd / major 7th apart for {overlap:.2f} s"))
    pads = [n for n in nd if n["role"] in PAD_ROLES]
    for th in out:
        if th["tag"] is None:
            continue
        for pd in pads:
            if pd["t"] <= th["t"] + 0.005 and pd["e"] > th["t"] + 0.005 and abs(pd["p"] - th["p"]) % 12 in CLASH:
                flags.append(_flag("3 chords", "e", th["t"], pd["role"], pd["p"], None,
                                   f"{pname(pd['p'])} ({pd['role']}) sounds a minor 2nd from theme note "
                                   f"{pname(th['p'])} ({th['role']}); the theme wins"))


def _check_end_sting(out, events, secs, flags):
    rows = []
    for ev in events:
        if not isinstance(ev, dict) or ev.get("type") != "end_sting":
            continue
        at = float(ev["at_s"])
        notes = [n for n in out if n["role"] not in DRUM_ROLES and abs(n["t"] - at) <= 0.01]
        pcs = {n["p"] % 12 for n in notes}
        name = chord_name(pcs, min(notes, key=lambda n: n["p"])["p"] % 12 if notes else None)
        sec = _sec_at(secs, at)
        rows.append({"t": round(at, 3), "name": name, "pcs": sorted(pcs)})
        if pcs != {2, 4, 9}:
            flags.append(_flag("3 chords", "d", at, "hits", None, sec["idx"] if sec else None,
                               f"end sting sounds {name}, not Dsus2 (D E A)"))
    return rows


def _check_bass(out, flags):
    bass_at = {}
    for n in out:
        if n["role"] == "bass":
            bass_at.setdefault(round(n["t"] * 1000), set()).add(n["p"])
    roots = ok = 0
    for n in out:
        if n["role"] == "drone" and hz(n["p"]) >= LOW_HZ:
            flags.append(_flag("4 bass", "drone", n["t"], "drone", n["p"], None,
                               f"drone {pname(n['p'])} is {hz(n['p']):.0f} Hz, above 200 Hz (mono low range)"))
        if n["role"] != "bass":
            continue
        at = round(n["t"] * 1000)
        if hz(n["p"]) < LOW_HZ:
            roots += 1
            if n["p"] + 19 in bass_at.get(at, ()):
                ok += 1
            else:
                flags.append(_flag("4 bass", "harmonic", n["t"], "bass", n["p"], None,
                                   f"root {pname(n['p'])} has no phone mid harmonic {pname(n['p'] + 19)}"))
        elif n["p"] - 19 not in bass_at.get(at, ()):
            flags.append(_flag("4 bass", "range", n["t"], "bass", n["p"], None,
                               f"bass {pname(n['p'])} is above 200 Hz and has no root 19 semitones below"))
    return roots, ok


def _roundtrip(tracks, markers, flags):
    """Write the MIDI, read it back with the test-side parser, compare notes per role and the markers."""
    from score.tests.test_note_writer import _parse_midi  # stdlib parser kept with the note writer tests
    tmp = tempfile.mkdtemp(prefix="harm_rt_")
    path = os.path.join(tmp, "roundtrip.mid")
    detail = {"ok": False, "notes_written": 0, "notes_read": 0, "mismatch": []}
    try:
        res = nw.write_midi(tracks, path, markers or [])
        if not res["ok"]:
            flags.append(_flag("5 midi", "write", None, None, None, None, f"write_midi failed: {res['errors']}"))
            return detail
        fmt, ntrk, div, parsed = _parse_midi(Path(path).read_bytes())
    except (AssertionError, IndexError, ValueError, OSError) as exc:
        flags.append(_flag("5 midi", "parse", None, None, None, None, f"{type(exc).__name__}: {exc}"))
        return detail
    finally:
        for f in (path,):
            try:
                os.remove(f)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass
    roles = list(tracks.keys())
    if ntrk != len(roles) + 1:
        flags.append(_flag("5 midi", "tracks", None, None, None, None,
                           f"{ntrk} tracks written, {len(roles) + 1} expected"))
        return detail
    for i, role in enumerate(roles):
        want = []
        for n in tracks[role]:
            on = round(float(n["t_s"]) * nw.PPQ)
            off = max(on + 1, round((float(n["t_s"]) + float(n["dur_s"])) * nw.PPQ))
            want.append((on, off, int(n["pitch"])))
        got = sorted(parsed[i + 1]["notes"])
        detail["notes_written"] += len(want)
        detail["notes_read"] += len(got)
        if sorted(want) != got:
            detail["mismatch"].append(role)
            flags.append(_flag("5 midi", "notes", None, role, None, None,
                               f"role {role}: {len(want)} notes written, {len(got)} read back, or pitches differ"))
    want_m = sorted((round(float(m["t_s"]) * nw.PPQ), m["name"]) for m in (markers or []))
    if sorted(parsed[0]["markers"]) != want_m:
        flags.append(_flag("5 midi", "markers", None, None, None, None, "markers differ after the round trip"))
    detail["ok"] = not detail["mismatch"] and sorted(parsed[0]["markers"]) == want_m
    return detail


def _fmt_t(t):
    return f"{t:.3f}"


def check_tracks(tracks, plan, cue_sheet, bible, markers=None):
    """Run the five checks on a tracks dict ({role: [{t_s, dur_s, pitch, vel}]}). Never raises on bad content."""
    flags = []
    result = {"ok": True, "errors": [], "warnings": [], "summary": {}, "flags": flags, "sections": [],
              "themes": [], "onsets": [], "end_sting": [], "bass": {}, "midi": {}, "notes": 0}
    if not isinstance(tracks, dict) or not isinstance(plan, dict) or not isinstance(cue_sheet, dict) \
            or not isinstance(bible, dict):
        result["ok"] = False
        result["errors"].append("inputs must be dicts")
        return result
    secs = _sections(plan)
    voice, susp, clos = _windows(cue_sheet)
    gated = nw.busy_roles(bible) | nw.GATED_EXTRA
    events = plan.get("events") or []
    events_end = [float(e["at_s"]) for e in events if isinstance(e, dict) and e.get("type") == "end_sting"
                  and isinstance(e.get("at_s"), (int, float))]
    out = _flatten(tracks)
    result["notes"] = len(out)

    entries, expected = _expand_themes(plan, bible, secs, flags)
    found = _tag(out, expected)
    theme_rows, th_ok, th_bad = _check_themes(entries, found, voice, gated, flags)
    result["themes"] = theme_rows
    n_checked = _check_scale(out, secs, flags)
    onset_rows = _check_chords(out, secs, voice, susp, clos, events_end, flags)
    _check_chord_clashes(out, flags, secs)
    result["onsets"] = onset_rows
    result["end_sting"] = _check_end_sting(out, events, secs, flags)
    roots, roots_ok = _check_bass(out, flags)
    result["bass"] = {"roots": roots, "ok": roots_ok}
    if markers is None:
        markers = []
    mid = _roundtrip(tracks, markers, flags)
    result["midi"] = mid

    counts = {}
    for f in flags:
        counts[f["check"]] = counts.get(f["check"], 0) + 1
    def cnt(prefix):
        return sum(v for k, v in counts.items() if k.startswith(prefix))
    chord_onsets_flagged = len({f["t"] for f in flags if f["check"] == "3 chords" and f["t"] is not None})
    result["summary"] = {
        "1 scale": {"ok": n_checked - cnt("1"), "flagged": cnt("1"), "unit": "non-drum notes"},
        "2 themes": {"ok": th_ok, "flagged": cnt("2"),
                     "unit": f"theme notes found ({th_ok}); flagged = missing or bad theme notes/entries"},
        "3 chords": {"ok": len(onset_rows) - chord_onsets_flagged, "flagged": cnt("3"),
                     "unit": f"onsets ({len(onset_rows)}); flagged = flag records"},
        "4 bass": {"ok": roots_ok, "flagged": cnt("4"), "unit": "bass roots with harmonic"},
        "5 midi": {"ok": int(mid["ok"]), "flagged": cnt("5"),
                   "unit": f"round trip, {mid['notes_read']} notes read back"},
    }
    result["ok"] = not result["errors"]
    result["sections_index"] = secs
    result["voice_windows"] = voice
    return result


def check_harmony(plan, cue_sheet, bible):
    """write_notes, then the checks. A plan that write_notes rejects is reported, not raised."""
    rep = nw.write_notes(plan, cue_sheet, bible)
    if not rep["ok"]:
        return {"ok": False, "errors": rep["errors"], "warnings": rep["warnings"], "summary": {}, "flags": [],
                "sections": [], "themes": [], "onsets": [], "end_sting": [], "bass": {}, "midi": {}, "notes": 0}
    res = check_tracks(rep["tracks"], plan, cue_sheet, bible, markers=rep["markers"])
    res["warnings"] = rep["warnings"]
    return res


# ---------------------------------------------------------------- report

FIX_TEXT = {
    "1 scale": "note_writer.py: the constant or rule that emits the note (PAD_CHORD, OSTINATO, SUS_PITCHES, DARK_PAD, "
               "END_CLUSTER, BASE pitches in _base_pitch / _sus_pitch). Either use D-minor tones or only the colour "
               "the section's harmony text names. Plan fix (plan.sections[].harmony) only if the colour is really "
               "meant to be there.",
    "2 themes": "note_writer.py _event_segments / _theme_pitches, or the plan event (theme, transform, role). A theme "
                "note cut under voice needs the plan's gap moved, not a pitch change.",
    "3 chords a": "note_writer.py _base_segments: the pad or drone that sits a minor 2nd under a sustained voice. "
                  "Shorten the overlap to 0.25 s or move the held note a whole tone (plan harmony owner decision).",
    "3 chords b": "note_writer.py _base_segments (bass root) or the upper voices: a bass root D2 under a chord with no D "
                  "is the bible's 'Bb over D' only if that is the intent; otherwise add the root to the upper chord.",
    "3 chords c": "note_writer.py _sus_pitch / suspense ramp (Decision 17): keep D F A off strong beats in suspense "
                  "shots (SHOT-003, SHOT-006, SHOT-010) and the closing shot.",
    "3 chords d": "note_writer.py END_CLUSTER (must be D2 E2 A2 = 38, 40, 45) and END_BRIGHT (D5 E5 A5 = 74, 76, 81).",
    "3 chords e": "note_writer.py PAD_CHORD / DARK_PAD / DRONE: remove the held pad pitch that clashes with the theme note "
                  "during the theme entry (theme wins).",
    "4 bass harmonic": "note_writer.py _base_segments: MID_PITCH must be root + 19 for every root (D2 38 -> A3 57).",
    "4 bass range": "note_writer.py _base_segments: bass root must stay below 200 Hz (MIDI 55 or lower).",
    "4 bass drone": "note_writer.py DRONE_PITCH / drone segments: keep the drone below 200 Hz.",
    "5 midi": "note_writer.py _midi_bytes / write_midi: the written events do not match the note list.",
}


def _fix_key(f):
    if f["check"].startswith("3") and f["sub"]:
        return f"3 chords {f['sub']}"
    if f["check"].startswith("4") and f["sub"]:
        return f"4 bass {f['sub']}"
    return f["check"]


def render_report(res, title="Harmony report", inputs=""):
    lines = [f"# {title}", "", inputs, "",
             "Checker: `score/harmony_check.py` (pure; no model calls). Home key D minor (music_bible.json). "
             "Notes come from `score/note_writer.py` write_notes, unchanged.", "",
             "## Summary", "", "| Check | OK | Flagged | Unit |", "|---|---:|---:|---|"]
    for k, v in res.get("summary", {}).items():
        lines.append(f"| {k} | {v['ok']} | {v['flagged']} | {v['unit']} |")
    lines += ["", f"Notes read: {res.get('notes', 0)}. write_notes ok: {res.get('ok')}. "
              f"write_notes warnings: {len(res.get('warnings', []))}.", ""]
    if res.get("errors"):
        lines += ["write_notes errors:", ""] + [f"- {e}" for e in res["errors"]] + [""]
    secs = res.get("sections_index", [])
    onsets = res.get("onsets", [])
    flags = res.get("flags", [])
    lines += ["## Sections", ""]
    for s in secs:
        mine = [o for o in onsets if o["sec"] == s["idx"]]
        seq, prev = [], None
        for o in mine:
            if o["name"] != prev:
                seq.append(f"{o['t']:.2f} {o['name']}")
                prev = o["name"]
        more = ""
        if len(seq) > 60:
            more = f" ... (+{len(seq) - 60} more)"
            seq = seq[:60]
        sflags = [f for f in flags if f["section"] == s["idx"]]
        colour, names = colour_of(s["harmony"])
        lines += [f"### S{s['idx']}  {s['start']:.3f}-{s['end']:.3f} s  {s['act']}, {s['genre']}, "
                  f"{s['bpm']:g} bpm, feel {s['feel']}", "",
                  f"- Harmony text: `{s['harmony']}`. Colour allowed: "
                  f"{'; '.join(names) if names else 'none (D natural minor only)'}",
                  f"- Chord sequence (changes only): {' | '.join(seq) if seq else 'none'}{more}",
                  f"- Flags in this section: {len(sflags)}", ""]
        if sflags:
            lines += ["| Time (s) | Check | Role | Pitch | Why |", "|---:|---|---|---|---|"]
            for f in sflags[:200]:
                lines.append(f"| {f['t'] if f['t'] is not None else '-'} | {f['check']}{' ' + f['sub'] if f['sub'] else ''} "
                             f"| {f['role'] or '-'} | {f['pitch'] or '-'} | {f['reason']} |")
            if len(sflags) > 200:
                lines.append(f"| | | | | ... {len(sflags) - 200} more, see the JSON |")
            lines.append("")
    loose = [f for f in flags if f["section"] is None and f["check"] != "5 midi"]
    if loose:
        lines += ["### Flags outside any section", "", "| Time (s) | Check | Role | Pitch | Why |", "|---:|---|---|---|---|"]
        for f in loose[:100]:
            lines.append(f"| {f['t'] if f['t'] is not None else '-'} | {f['check']} | {f['role'] or '-'} | "
                         f"{f['pitch'] or '-'} | {f['reason']} |")
        lines.append("")
    lines += ["## Theme entries (check 2)", "", "| # | Theme | Role | At (s) | Transform | Bible pitches | Sounding | OK |",
              "|---:|---|---|---:|---|---|---|---|"]
    for r in res.get("themes", []):
        ok = "yes" if r["want"].split() == r["got"].split() else "NO"
        lines.append(f"| {r['idx']} | {r['theme']} | {r['role']} | {r['at']:.3f} | {r['transform'] or '-'} | "
                     f"{r['want']} | {r['got']} | {ok} |")
    lines += ["", "## End sting (check 3d)", ""]
    for e in res.get("end_sting", []):
        lines.append(f"- {e['t']} s: {e['name']} (pitch classes {e['pcs']})")
    lines += ["", "## Bass and MIDI (checks 4 and 5)", "",
              f"- Bass roots below 200 Hz: {res.get('bass', {}).get('roots', 0)}, with harmonic: "
              f"{res.get('bass', {}).get('ok', 0)}",
              f"- Round trip: {'match' if res.get('midi', {}).get('ok') else 'MISMATCH'}, notes written "
              f"{res.get('midi', {}).get('notes_written', 0)}, read back {res.get('midi', {}).get('notes_read', 0)}", ""]
    if res.get("warnings"):
        lines += ["## write_notes warnings", ""] + [f"- {w['code']} {w['where']}: {w['message']}" for w in res["warnings"]] + [""]
    keys = []
    for f in flags:
        k = _fix_key(f)
        if k not in keys:
            keys.append(k)
    lines += ["## Fixes needed", ""]
    if not keys:
        lines.append("None. Every check passed.")
    for k in keys:
        n = sum(1 for f in flags if _fix_key(f) == k)
        lines.append(f"- **{k}** ({n} flags): {FIX_TEXT.get(k, FIX_TEXT.get(k.split(' ')[0], 'see the flags'))}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

_REEL = Path(__file__).resolve().parents[1]
_PACK = _REEL / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "score" / "ep1"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Harmony check of the reel score (pure).")
    ap.add_argument("--plan", default=str(_PACK / "score_plan.json"))
    ap.add_argument("--cue", default=str(_PACK / "cue_sheet.json"))
    ap.add_argument("--bible", default=str(_REEL / "stories" / "kalika_puran_bhag1" / "music_bible.json"))
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    cue = json.loads(Path(a.cue).read_text(encoding="utf-8"))
    bible = json.loads(Path(a.bible).read_text(encoding="utf-8"))
    res = check_harmony(plan, cue, bible)
    for k, v in res.get("summary", {}).items():
        print(f"{k}: ok {v['ok']}, flagged {v['flagged']}")
    print(f"write_notes ok: {res['ok']}, flags: {len(res.get('flags', []))}")
    if a.report:
        inputs = f"Inputs: plan `{a.plan}`, cue `{a.cue}`, bible `{a.bible}`."
        Path(a.report).write_text(render_report(res, "Harmony report: Kalika reel 1, 2026-11-09", inputs),
                                  encoding="utf-8")
        print(f"report: {a.report}")
    if a.json:
        slim = {k: v for k, v in res.items()}
        Path(a.json).write_text(json.dumps(slim, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"json: {a.json}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
