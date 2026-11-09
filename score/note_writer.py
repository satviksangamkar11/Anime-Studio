"""Score stage S5: exact notes per track role on the reel clock, and a clock-mode standard MIDI file.

Pure: no models, no Ableton, no network, no random. Never raises on bad input: it returns a report.
Inputs: the score plan (score_plan.json v1, see .claude/skills/score-reel/SKILL.md), the cue sheet
(score/cue_sheet.py output: total_s, voice.union, retention, shots, cuts) and the story's music_bible.json.

write_notes(plan, cue_sheet, bible) -> {"ok", "errors", "warnings", "tracks", "markers", "automation", "stats"}
  tracks: {role: [{"t_s", "dur_s", "pitch", "vel"}]}, absolute reel seconds, sorted by time.
  markers: [{"t_s", "name"}], one per cue-sheet shot.
write_midi(tracks, path, markers=None) -> {"ok", "errors", "path", "notes"}
  Type-1 .mid, 480 ppq, tempo 1,000,000 us per quarter (60 BPM, so 1 beat = 1 s). Track 0 holds the tempo, the
  time signature and the markers (meta events). Each role is one track on its own channel.

Decisions:
1. Pitch names: C4 = MIDI 60 (scientific pitch). D3 = 50 is the low-band ceiling under voice (rule 2, C6).
2. Busy roles come from bible track_roles (busy: true); with no track_roles the default is drums, ostinato, pluck,
   lead, hits. Brass is not busy, but low brass only under voice (bible note), so brass is gated the same way for
   pitches above 50. Under a voice window, a gated note with pitch above 50 is cut at the window start, or dropped if
   it starts inside. Drums, hits and brass at pitch <= 50 are exempt. Drone, pad and bass are not gated.
3. A hit (and the end sting) that starts inside a voice window is forced to D2 (38) and warned (HIT_FORCED_LOW).
   The end sting's low cluster is always D2 E2 A2 (38, 40, 45); after the last speech the bright D5 E5 A5 joins
   (Decision 34).
4. Drop-outs cut every role. A sustained note cut by a drop-out resumes at the drop-out's end. A drop-out over 0.45 s
   is an error. A swell cut by a drop-out is lost and warned (SWELL_CUT_BY_DROPOUT): silence wins over the swell (the
   reel-1 swell into the 48 s cut is one such case, a decision for the owner).
5. Felt tempo: normal = one step per beat, half = one step per 2 beats, double = two steps per beat. The beat is
   60/bpm of the section that holds the time, for every feel (so density is per real beat, C2.6).
6. Theme entries play the bible degrees, one note per felt step, each lasting 0.9 step, on the event's role. The role
   must be one of the theme's bible roles (THEME_ROLE_NOT_IN_BIBLE). Any theme note cut or dropped is counted in a
   THEME_TRUNCATED warning per entry.
7. Sonic logo: the lowest note of bible sonic_logo.notes is the sub; the others are bells. Sonic logo at 0 s.
8. Swell transitions (reverse_swell_to_cut, swell_to_cut): a 1 s pad note on E4 (64) ending exactly on the
   cut time, in its own tag so the chord merge does not swallow it. Other transitions write no notes.
9. Markers: one per cue-sheet shot at its start. Name: "<id> closing" when closing_hook, "<id> opening <hook_type>"
   when opening_hook, else "<id> <hook_type>".
10. Deterministic: no random is used, so the same input gives the same output and the same MIDI bytes.
11. Re-hook and peak (plan fields): rehook_at_s must carry a MAIN theme_entry within one frame (REHOOK_NO_THEME).
    peak_at_s must lie in the section with the highest mean intensity (PEAK_NOT_HIGHEST). Peak is also the loudest
    section by velocity.
12. Malformed plan, cue sheet or bible: tracks, markers and automation are empty and ok is False. A last-resort
    guard reports any unexpected exception as an INTERNAL error.
13. Bass plays the root (D2 = 38) and a mid harmonic one octave plus a fifth up (A3 = 57) at 60% of the root velocity,
    sustained like the root. The harmonic is never gated (rule 11).
14. Ostinato density is per real beat (section bpm) and ramps linearly from density_per_beat[0] to [1] across each
    section. Pitches cycle D3 F3 A3 C4.
15. Pad sustains D4 and A4 (200-1000 Hz); drone sustains D2; kick is C2 (36) on each felt step.
16. Overlapping notes of the same role and pitch are merged into one note (theme notes only with theme notes,
    Decision 38). A MIDI channel cannot hold two open notes
    of one pitch, so the file would pair the offs wrongly.
17. Shot rules (hook_type from the cue sheet; closing_hook takes precedence over hook_type):
    reveal: only drone and pad before the shot's first theme_entry; the others are cut out of that part.
            No theme_entry in the shot is an error (REVEAL_NO_ENTRY).
    expression-beat: pad only in the whole shot, except the heartbeat (Decision 30); theme notes inside a voice window
            are removed (fragments only in gaps).
    suspense: ostinato is replaced by a ramp across the shot (lo to hi per real beat) whose pitches never start on
            D (pitch class 2) on a strong beat. Only where the section has the ostinato role (Decision 24: a
            hypnotic-techno loop has no ostinato to replace). Skipped where it overlaps the quiet moment (the bible's
            quiet window wins, SHOT_RULE_SKIPPED says so).
    reversal: from the first hit in the shot to the shot end, base pad is replaced by a darker pad one octave lower
            plus Eb and G (51, 55). The drop-out before the turn is already silence on all roles.
    closing (closing_hook): base pad is replaced by Dsus2 (D4 E4 A4); ostinato, pluck, lead, brass and hits are cut
            (the end sting stays); notes are clipped to last_speech_end_s + 0.45 s. Decision 22: the old C2 kick
            every 2 beats is gone; the drums of the closing shot are its genre pattern (unplugged tick).
18. Quiet moment (bible quiet_moment at_s, roles, theme): inside its range only notes of the listed roles survive
    (drums only the tick, pitch 42), plus every note of the listed theme on any role, plus the end sting. Everything
    else is cut. QUIET_SUPPRESSED reports what was cut. The old hard-coded drone + MUNIS pad rule is gone.
19. Cue cuts with no plan transition are an error (CUT_MISSING). Sections must cover 0 to total_s without gaps or
    overlaps (SECTION_GAP, SECTION_OVERLAP). Unhashable feel or role values are SECTION_FEEL or ROLE_BAD.
20. Phone first (rule 11): phone speakers do not reproduce much below 200 Hz. Every theme note below G3 (55) gets an
    octave-up partner on the same role, same start and duration, velocity round(0.7 * original), minimum 1. The partner
    is +12, or +24 when +12 is still below 55, so D2 (38) doubles to D4 (62). The partner is made with its theme note,
    so the voice, drop-out, quiet and shot rules treat it the same. Hits, bass and other non-theme notes are never
    doubled. THEME_TRUNCATED counts original theme notes only.
21. Roles (bible track_roles): ROLES adds risers, vocal, piano, folk_perc, horn. Track output and the MIDI writer hold
    one track per role that has notes (empty roles are omitted). The sonic logo plays on its bible role (vocal). Vocal
    and folk_perc are in LOW_OK: their sub or low-band notes stay under voice, the rest is gated like the other busy roles.
22. Genre drum patterns (plan section genre, per section, on the section's own beat grid): hypnotic_techno kick each
    beat and closed hat on the off-beat 8ths; melodic_techno kick each beat, clap on 2 and 4, open hat off-beats;
    club_folk_groove kick each beat plus folk_perc on 2/3-beat onsets (3 against 4), low tom 41 accent on bar beat 1,
    mid 47 otherwise; drum_and_bass kick on 1 and 3 with the 'and' of 2, snare on 2 and 4, 16th hats whose density ramps
    from density_per_beat; half_time_dnb kick on 1, snare on 3 of each 4-beat bar, closed hat on beats 2 and 4;
    unplugged a soft closed-hat tick on every beat; ambient the heartbeat (Decision 30). Drums are written only where
    roles_on has drums
    (folk_perc: folk_perc). A section with no genre keeps the old kick on every felt step.
23. Under voice, drums and folk_perc are soft (velocity max 50) as before; every pattern pitch is <= 50 and so exempt.
24. Suspense rule (Decision 17) only applies in a section that has the ostinato role.
25. The sonic logo (frame 0) is exempt from the reveal rule (Decision 17): reveal shot 1 cuts everything but drone and
    pad before its first entry, which now comes at 3.5 s, and the logo must still sound on frame 0 (rule 6).
26. Section clip: after the shot pass and before the merge, every note is clipped at the end of the section its start
    lies in (NW4 round 3). A new section's downbeat is therefore never extended by the previous section's notes.
28. Theme hang (NW4 round 4, round 5 wording): the last note of every theme_entry ends at the earliest of the end of the
    voice gap it starts in, the section end and its start + 1.5 s. A short last note is held to that time; a last note
    that would run past its gap is trimmed to the gap end, so it is not counted as a voice cut. A last note that starts
    inside a voice window does not hang and keeps its step length. Its octave partner hangs with it.
29. Feel "quad" (FEEL_STEP 0.25: four notes per beat) exists only for a motif that must fit a short voice gap.
27. Merge (Decision 16) joins only strictly overlapping notes of one role and pitch. Touching notes (one ends exactly
    where the next starts) stay separate; the MIDI writer puts the off before the on at the same tick, so pairing holds.
30. Heartbeat (NWR3-5a, round 6): an ambient section with drums in roles_on gets a kick (36) on each beat and at
    +0.25 beat, velocity min(60, section velocity), tag ("heart",). The expression-beat shot keeps it (Decision 17).
    Under voice it is soft (Decision 23).
31. Soft under voice (NWR3-1, round 6): piano, brass and horn notes overlapping a voice window are capped at velocity 50,
    like drums. Horn is gated like brass (GATED_EXTRA), and low horn stays under voice (LOW_OK).
32. God entries (NWR3-2, round 6): a theme_entry of SHIVA, BRAHMA, KALI or VISHNU silences drums and folk_perc from its
    time until its last note has ended (after the hang, Decision 28). Other roles are not changed.
33. Bounds (NWR3-3, round 6): bpm must be 20-300 (SECTION_BPM), density_per_beat values 0-16 (SECTION_DENSITY). Values
    out of range are errors before any note loop runs.
34. End sting (NWR3-4, round 6): an end_sting after last_speech_end_s also writes bright D5 E5 A5 (74, 76, 81) on its
    role, tag ("end",), next to the low Dsus2 cluster. Before the last speech only the low cluster is written.
35. Transforms (NWR3-5b/c, round 6): a theme_entry may carry "transform": the name of a transform in the theme's bible
    transforms, whose notes replace the degrees. A transform that is not a string, not in the bible, or has an
    unreadable note gives THEME_TRANSFORM_BAD.
36. Theme roles (NWR3-11, round 6): a bible theme that has a roles key must give a list that contains the event role.
    Otherwise THEME_ROLE_NOT_IN_BIBLE (a string such as "lead" is not a list).
37. MIDI channels (NWR3-9, round 6): drums are on channel index 9 (GM channel 10). Every other role has its own channel
    from MIDI_CHANNEL, so no other role shares the drum channel.
38. Origin (NWR3-R-1, R-2, round 7): a theme note never merges with a base note of the same role and pitch. A base
    note is cut out of the span of any theme note of its pitch and resumes after it (a new attack), so both sound and
    the MIDI writer never has two open notes of one pitch. The base note keeps its own velocity.
39. Theme velocity (NWR3-R-3, round 7): round(55 + 45 * upper intensity of the section at the note time). The entry at
    plan peak_at_s (SHIVA at 48.0 s) plays at velocity 120 with its octave partners, the loudest attack of the reel.
    Hits stay at 110 or below. The voice cap (Decision 31) still applies to the soft roles only.
"""
from __future__ import annotations

import math
import re
import struct
from pathlib import Path

from score.plan_check import TRANSITIONS as SHARED_TRANSITIONS

PPQ = 480
TEMPO_US = 1_000_000               # 60 BPM: clock mode, 1 beat = 1 s
FRAME_S = 1 / 24
MIN_DUR_S = 0.01
EPS = 1e-9
LOW_MAX = 50                       # MIDI 50 = D3, the low-band ceiling under voice
LOW_PITCH = 38                     # D2, sub hit
BRIGHT_PITCH = 74                  # D5, bright bell in a voice gap
MAX_DROPOUT_S = 0.45
TAIL_S = 0.45
ROLES = ("drone", "pad", "bass", "drums", "ostinato", "pluck", "lead", "brass", "hits",
         "risers", "vocal", "piano", "folk_perc", "horn")
DEFAULT_BUSY = frozenset({"drums", "ostinato", "pluck", "lead", "hits"})
GATED_EXTRA = frozenset({"brass", "horn"})  # not busy in the bible, but low brass and horn only under voice
LOW_OK = frozenset({"drums", "hits", "brass", "horn", "vocal", "folk_perc"})
SOFT_ROLES = frozenset({"drums", "folk_perc", "piano", "brass", "horn"})  # Decision 31
SOFT_UNDER_VOICE = 50
MIDI_CHANNEL = {"drums": 9, **dict(zip((r for r in ROLES if r != "drums"), (c for c in range(16) if c != 9)))}  # Decision 37
GOD_THEMES = frozenset({"SHIVA", "BRAHMA", "KALI", "VISHNU"})  # Decision 32
GOD_SILENT_ROLES = ("drums", "folk_perc")
HEART = ("heart",)                 # Decision 30: the ambient heartbeat's tag
END_BRIGHT = (74, 76, 81)          # D5 E5 A5: bright sting after the last speech (Decision 34)
BPM_MIN, BPM_MAX, DENSITY_MAX = 20, 300, 16  # Decision 33
GENRES = ("ambient", "hypnotic_techno", "melodic_techno", "club_folk_groove", "drum_and_bass", "half_time_dnb",
          "unplugged")
DRUM_KICK, DRUM_SNARE, DRUM_CLAP, DRUM_HAT, DRUM_OPEN_HAT = 36, 38, 39, 42, 46
FOLK_LOW, FOLK_MID = 41, 47        # low tom, mid tom: folk_perc
DRUM_TICK = DRUM_HAT               # unplugged pulse, also the quiet moment's only drum
FEEL_STEP = {"normal": 1.0, "half": 2.0, "double": 0.5, "quad": 0.25}  # quad: Decision 29
EVENT_TYPES = ("sonic_logo", "hit", "theme_entry", "end_sting")
EVENT_ROLE = {"sonic_logo": "hits", "hit": "hits", "theme_entry": "lead", "end_sting": "hits"}
# One cut vocabulary, shared with plan_check (round 2, coordinator). Swell cuts write the swell; none, bed_continues,
# theme_handover and key_colour_on_downbeat write no swell (key colour re-strikes the pad on the downbeat); act_change
# is the act change. Old names are read with a CUT_TRANSITION_RENAMED warning (Decision: no_break -> bed_continues,
# hard_cut -> swell_to_cut, impact -> none).
SWELL_TRANSITIONS = ("reverse_swell_to_cut", "swell_to_cut")
TRANSITIONS = SHARED_TRANSITIONS
COLOUR_TRANSITION = "key_colour_on_downbeat"
LEGACY_TRANSITIONS = {"no_break": "bed_continues", "hard_cut": "swell_to_cut", "impact": "none"}
SHOT_HOOKS = ("reveal", "expression-beat", "suspense", "reversal", "closing")
REVEAL_KEEP = ("drone", "pad")
OSTINATO = (50, 53, 57, 60)        # D3 F3 A3 C4
SUS_PITCHES = (53, 57, 60, 50)     # suspense cycle; D3 is moved off strong beats
PAD_CHORD = (62, 69)               # D4 A4
OUTRO_PAD = (62, 69)               # D4 A4 only: the closing pad (no E; the piano MAIN theme sounds F4 over it)
DARK_PAD = (51, 55)                # Eb3 G3: Phrygian bII dyad over the D bass; Bb3 dropped (close m2 over the A3 harmonic)
END_CLUSTER = (38, 40, 45)         # D2 E2 A2: Dsus2 cluster, low band
SWELL_PITCH = 64                   # E4: a separate pad note, so the swell does not merge into the chord
DRONE_PITCH = 38                   # D2
MID_PITCH = 57                     # A3: octave plus a fifth above the bass root
KICK = 36                          # C2
PHONE_MIN = 55                     # G3: theme notes below this get an octave-up partner (Decision 20)
_NOTE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_NOTE_TOKEN = re.compile(r"(?<![A-Za-z])([A-G][#b]?-?\d+)(?!\d)")
_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACC = {"#": 1, "b": -1, "": 0}


# ---------------------------------------------------------------- helpers

def _err(code, where, message):
    return {"code": code, "where": where, "message": message}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def busy_roles(bible):
    """Roles flagged busy in the bible's track_roles. The default set when the bible has no track_roles."""
    tr = bible.get("track_roles") if isinstance(bible, dict) else None
    if not isinstance(tr, dict):
        return DEFAULT_BUSY
    return frozenset(r for r, v in tr.items() if r in ROLES and isinstance(v, dict) and v.get("busy") is True)


def note_to_midi(name):
    """'D3' -> 50, 'C4' -> 60, 'Bb2' -> 46. None for anything else or a pitch outside 0-127."""
    if not isinstance(name, str):
        return None
    m = _NOTE.match(name.strip())
    if not m:
        return None
    letter, acc, octave = m.groups()
    pitch = 12 * (int(octave) + 1) + _SEMI[letter.upper()] + _ACC[acc]
    return pitch if 0 <= pitch <= 127 else None


def _theme_pitches(text):
    """MIDI pitches of the note names in a bible degrees string, or None when there are none or one is unreadable."""
    if not isinstance(text, str):
        return None
    names = _NOTE_TOKEN.findall(text)
    pitches = [note_to_midi(n) for n in names]
    if not pitches or None in pitches:
        return None
    return pitches


def _windows(raw, where, errors):
    """Sorted (start, end) pairs from [[a, b], ...]; bad items are reported and skipped."""
    out = []
    if not isinstance(raw, list):
        errors.append(_err("VOICE_UNION", where, "must be a list of [start, end] pairs"))
        return out
    for w in raw:
        if isinstance(w, (list, tuple)) and len(w) == 2 and all(_num(x) for x in w) and w[1] >= w[0]:
            out.append((float(w[0]), float(w[1])))
        else:
            errors.append(_err("VOICE_UNION", where, f"bad window {w!r}"))
    return sorted(out)


def _inside(windows, t):
    return any(a - EPS <= t < b - EPS for a, b in windows)


def _first_overlap(windows, t, end):
    for a, b in windows:
        if a < end - EPS and b > t + EPS:
            return (a, b)
    return None


def _section_at(sections, t):
    for sec in sections:
        if sec["start"] - EPS <= t < sec["end"] - EPS:
            return sec
    return None


def _is_theme(sg):
    return sg[5] is not None and sg[5][0] == "theme"


def _result(ok, tracks, markers, automation, errors, warnings, stats):
    return {"ok": ok, "errors": errors, "warnings": warnings, "tracks": tracks, "markers": markers,
            "automation": automation, "stats": stats}


# ---------------------------------------------------------------- plan readers

def _sections(raw, total, errors):
    if not isinstance(raw, list) or not raw:
        errors.append(_err("PLAN_SECTIONS", "plan.sections", "needs a non-empty list"))
        return []
    out = []
    n_before = len(errors)
    for i, s in enumerate(raw):
        where = f"plan.sections[{i}]"
        if not isinstance(s, dict):
            errors.append(_err("SECTION", where, "not an object"))
            continue
        a, b, bpm = s.get("start_s"), s.get("end_s"), s.get("bpm")
        if not (_num(a) and _num(b) and 0 <= a < b <= total + EPS):
            errors.append(_err("SECTION_BOUNDS", where, f"need 0 <= start_s < end_s <= {total:g}"))
            continue
        if not (_num(bpm) and BPM_MIN <= bpm <= BPM_MAX):
            errors.append(_err("SECTION_BPM", where, f"bpm must be a number from {BPM_MIN} to {BPM_MAX}"))
            continue
        feel = s.get("feel", "normal")
        if not (isinstance(feel, str) and feel in FEEL_STEP):
            errors.append(_err("SECTION_FEEL", where, f"feel must be one of {tuple(FEEL_STEP)}"))
            continue
        roles = s.get("roles_on", [])
        if not isinstance(roles, list) or any(not (isinstance(r, str) and r in ROLES) for r in roles):
            errors.append(_err("ROLE_BAD", where, f"roles_on must use only {ROLES}"))
            continue
        dens = s.get("density_per_beat", [1, 1])
        if not (isinstance(dens, list) and dens and all(_num(x) and 0 <= x <= DENSITY_MAX for x in dens[:2])):
            errors.append(_err("SECTION_DENSITY", where,
                               f"density_per_beat must start with numbers from 0 to {DENSITY_MAX}"))
            continue
        inten = s.get("intensity", [0.5, 0.5])
        if not (isinstance(inten, list) and len(inten) == 2 and all(_num(x) and 0 <= x <= 1 for x in inten)):
            errors.append(_err("SECTION_INTENSITY", where, "intensity must be two numbers in 0-1"))
            continue
        imean = (inten[0] + inten[1]) / 2
        genre = s.get("genre")
        out.append({"start": float(a), "end": float(min(b, total)), "bpm": float(bpm), "feel": feel,
                    "genre": genre if isinstance(genre, str) else None,
                    "roles": list(roles), "dlo": float(dens[0]),
                    "dhi": float(dens[1]) if len(dens) > 1 else float(dens[0]),
                    "ihi": float(inten[1]), "imean": imean,
                    "vel": int(min(127, max(1, round(40 + 60 * imean))))})
    out.sort(key=lambda x: x["start"])
    if out and len(errors) == n_before:  # a rejected section is already reported; no coverage error on top of it
        if out[0]["start"] > 1e-6:
            errors.append(_err("SECTION_GAP", "plan.sections", f"nothing covers 0 to {out[0]['start']:g} s"))
        for prev, cur in zip(out, out[1:]):
            if cur["start"] > prev["end"] + 1e-6:
                errors.append(_err("SECTION_GAP", "plan.sections",
                                   f"gap {prev['end']:g} to {cur['start']:g} s is not covered"))
            elif cur["start"] < prev["end"] - 1e-6:
                errors.append(_err("SECTION_OVERLAP", "plan.sections",
                                   f"sections overlap at {cur['start']:g} to {prev['end']:g} s"))
        if out[-1]["end"] < total - 1e-6:
            errors.append(_err("SECTION_GAP", "plan.sections", f"nothing covers {out[-1]['end']:g} to {total:g} s"))
    return out


def _events(raw, total, themes, errors):
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        errors.append(_err("PLAN_EVENTS", "plan.events", "must be a list"))
        return []
    out = []
    for i, ev in enumerate(raw):
        where = f"plan.events[{i}]"
        if not isinstance(ev, dict):
            errors.append(_err("EVENT", where, "not an object"))
            continue
        typ = ev.get("type")
        if not (isinstance(typ, str) and typ in EVENT_TYPES):
            errors.append(_err("EVENT_TYPE", where, f"type must be one of {EVENT_TYPES}, got {typ!r}"))
            continue
        at = ev.get("at_s")
        if not (_num(at) and 0 <= at <= total):
            errors.append(_err("EVENT_AT", where, f"at_s must be inside 0-{total:g}"))
            continue
        drop = ev.get("preceded_by_dropout_s")
        drop = 0.0 if drop is None else drop
        if not (_num(drop) and drop >= 0):
            errors.append(_err("DROPOUT", where, "preceded_by_dropout_s must be a number >= 0"))
            continue
        if drop > MAX_DROPOUT_S + EPS:
            errors.append(_err("DROPOUT_TOO_LONG", where, f"{drop:g} s is over {MAX_DROPOUT_S} s (rule 7)"))
            continue
        if drop > at + EPS:
            errors.append(_err("DROPOUT_BEFORE_START", where, "the drop-out starts before 0 s"))
            continue
        role = ev.get("role", EVENT_ROLE.get(typ, "hits"))
        if not (isinstance(role, str) and role in ROLES):
            errors.append(_err("ROLE_BAD", where, f"role must be one of {ROLES}"))
            continue
        feel = ev.get("feel", "normal")
        if not (isinstance(feel, str) and feel in FEEL_STEP):
            errors.append(_err("EVENT_FEEL", where, f"feel must be one of {tuple(FEEL_STEP)}"))
            continue
        band = ev.get("band")
        if band not in (None, "low"):
            errors.append(_err("EVENT_BAND", where, "band must be 'low' or absent"))
            continue
        item = {"type": typ, "at": float(at), "drop": float(drop), "role": role, "feel": feel,
                "band": band, "where": where, "idx": i, "pitches": None, "theme": None}
        if typ == "theme_entry":
            name = ev.get("theme")
            entry = themes.get(name) if isinstance(name, str) else None
            pitches = _theme_pitches(entry.get("degrees")) if isinstance(entry, dict) else None
            if pitches is None:
                errors.append(_err("THEME_UNKNOWN", where, f"theme {name!r} has no note degrees in the bible"))
                continue
            allowed = entry.get("roles")
            if "roles" in entry and (not isinstance(allowed, list) or role not in allowed):  # Decision 36
                errors.append(_err("THEME_ROLE_NOT_IN_BIBLE", where,
                                   f"theme {name} may play {allowed}, not {role}"))
                continue
            if "transform" in ev:  # Decision 35
                tr = ev.get("transform")
                trs = entry.get("transforms") if isinstance(entry.get("transforms"), dict) else {}
                tpitches = _theme_pitches(trs.get(tr)) if isinstance(tr, str) else None
                if tpitches is None:
                    errors.append(_err("THEME_TRANSFORM_BAD", where,
                                       f"transform {tr!r} is not a bible transform of {name} with readable notes"))
                    continue
                pitches = tpitches
            item["pitches"] = pitches
            item["theme"] = name
        out.append(item)
    return out


def _cuts(raw, cue, total, errors, warnings):
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        errors.append(_err("PLAN_CUTS", "plan.cuts", "must be a list"))
        return []
    out = []
    for i, c in enumerate(raw):
        where = f"plan.cuts[{i}]"
        if not isinstance(c, dict) or not (_num(c.get("at_s")) and 0 <= c["at_s"] <= total):
            errors.append(_err("CUT", where, "needs at_s inside the reel"))
            continue
        t = c.get("transition")
        if t in LEGACY_TRANSITIONS:
            warnings.append(_err("CUT_TRANSITION_RENAMED", where,
                                 f"{t!r} is an old name; read as {LEGACY_TRANSITIONS[t]!r} (shared cut vocabulary)"))
            t = LEGACY_TRANSITIONS[t]
        if t not in TRANSITIONS:
            errors.append(_err("CUT_TRANSITION", where, f"transition must be one of {sorted(TRANSITIONS)}"))
            continue
        out.append({"at": float(c["at_s"]), "transition": t})
    planned = [c["at"] for c in out]
    for cc in cue.get("cuts") or []:
        if isinstance(cc, dict) and _num(cc.get("at_s")):
            if not any(abs(p - cc["at_s"]) <= FRAME_S + EPS for p in planned):
                errors.append(_err("CUT_MISSING", "plan.cuts",
                                   f"cue cut at {cc['at_s']:g} s has no transition in the plan"))
    return out


def _automation(raw, total, errors):
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors.append(_err("PLAN_AUTOMATION", "plan.automation", "must be a list"))
        return []
    out = []
    for i, a in enumerate(raw):
        where = f"plan.automation[{i}]"
        if not isinstance(a, dict) or not (isinstance(a.get("role"), str) and a.get("role") in ROLES):
            errors.append(_err("AUTOMATION_ROLE", where, f"role must be one of {ROLES}"))
            continue
        macro = a.get("macro")
        if not (isinstance(macro, int) and not isinstance(macro, bool) and 1 <= macro <= 4):
            errors.append(_err("AUTOMATION_MACRO", where, "macro must be 1-4"))
            continue
        pts = a.get("points")
        good = isinstance(pts, list) and pts and all(
            isinstance(p, (list, tuple)) and len(p) == 2 and _num(p[0]) and _num(p[1])
            and 0 <= p[0] <= total and 0 <= p[1] <= 1 for p in pts)
        if not good:
            errors.append(_err("AUTOMATION_POINTS", where, "points must be [time_s, 0-1] pairs inside the reel"))
            continue
        pts = sorted((float(p[0]), float(p[1])) for p in pts)
        out.append({"role": a["role"], "macro": macro, "points": [[round(t, 6), round(v, 6)] for t, v in pts]})
    return out


def _shots(raw, total, errors):
    if not isinstance(raw, list) or not raw:
        errors.append(_err("SHOTS", "cue_sheet.shots", "needs the cue sheet shot list"))
        return []
    out = []
    for i, s in enumerate(raw):
        where = f"cue_sheet.shots[{i}]"
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not _num(s.get("start_s")):
            errors.append(_err("SHOT", where, "needs id and start_s"))
            continue
        hook = s.get("hook_type") if isinstance(s.get("hook_type"), str) else ""
        end = s.get("end_s") if _num(s.get("end_s")) else None
        out.append({"id": s["id"], "start": float(s["start_s"]), "end": end, "hook": hook,
                    "closing": s.get("closing_hook") is True, "opening": s.get("opening_hook") is True})
    out.sort(key=lambda x: x["start"])
    for i, sh in enumerate(out):
        if sh["end"] is None:
            sh["end"] = out[i + 1]["start"] if i + 1 < len(out) else total
        sh["end"] = min(float(sh["end"]), total)
    return out


def _marker_name(sh):
    if sh["closing"]:
        return f"{sh['id']} closing"
    if sh["opening"]:
        return f"{sh['id']} opening {sh['hook']}".rstrip()
    return f"{sh['id']} {sh['hook']}".rstrip()


def _sonic(bible, errors):
    s = bible.get("sonic_logo")
    if not isinstance(s, dict):
        errors.append(_err("SONIC_LOGO", "bible.sonic_logo", "missing"))
        return None
    pitches = sorted({note_to_midi(t) for t in _NOTE_TOKEN.findall(str(s.get("notes", "")))} - {None})
    length = s.get("length_s", 0.8)
    if not pitches or not _num(length) or length <= 0:
        errors.append(_err("SONIC_LOGO", "bible.sonic_logo", "needs note names in notes and a positive length_s"))
        return None
    role = s.get("role") if s.get("role") in ROLES else "hits"
    return {"sub": pitches[0], "bells": pitches[1:], "length": float(length), "role": role}


def _quiet(bible, errors):
    q = bible.get("quiet_moment")
    if q is None:
        return None
    at = q.get("at_s") if isinstance(q, dict) else None
    if isinstance(at, list) and len(at) == 2 and all(_num(x) for x in at) and at[1] > at[0]:
        return (float(at[0]), float(at[1]))
    errors.append(_err("QUIET_BAD", "bible.quiet_moment", "needs at_s as [start, end]"))
    return None


def _quiet_rule(bible):
    """(roles, theme) the quiet moment keeps, from bible quiet_moment. Defaults: drone and pad, no theme."""
    q = bible.get("quiet_moment") if isinstance(bible, dict) else None
    roles = q.get("roles") if isinstance(q, dict) else None
    if not (isinstance(roles, list) and all(isinstance(r, str) and r in ROLES for r in roles)):
        roles = ["drone", "pad"]
    theme = q.get("theme") if isinstance(q, dict) else None
    return frozenset(roles), theme if isinstance(theme, str) else None


def _peak_rehook(plan, sections, events, errors):
    r = plan.get("rehook_at_s")
    if r is not None:
        if not _num(r):
            errors.append(_err("REHOOK_BAD", "plan.rehook_at_s", "must be a number"))
        elif not any(ev["type"] == "theme_entry" and ev.get("theme") == "MAIN"
                     and abs(ev["at"] - r) <= FRAME_S + EPS for ev in events):
            errors.append(_err("REHOOK_NO_THEME", "plan.rehook_at_s",
                               f"no MAIN theme_entry at {r:g} s (rule 6)"))
    pk = plan.get("peak_at_s")
    if pk is not None:
        if not _num(pk):
            errors.append(_err("PEAK_BAD", "plan.peak_at_s", "must be a number"))
            return
        sec = _section_at(sections, pk)
        if sec is None:
            errors.append(_err("PEAK_OUTSIDE", "plan.peak_at_s", f"{pk:g} s is in no section"))
        elif sections and sec["imean"] + EPS < max(s["imean"] for s in sections):
            errors.append(_err("PEAK_NOT_HIGHEST", "plan.peak_at_s",
                               f"{pk:g} s is in a section with intensity {sec['imean']:g}, not the highest (rule 7)"))


# ---------------------------------------------------------------- note generation

def _ramp_onsets(a, b, beat, lo, hi):
    """Onset times from a to b, one per beat / density, density ramping linearly from lo to hi across [a, b)."""
    out, t, span = [], a, b - a
    while t < b - EPS:
        out.append(t)
        frac = min(1.0, max(0.0, (t - a) / span))
        t += beat / max(lo + (hi - lo) * frac, 1e-6)
    return out


def _ostinato_segs(a, b, beat, lo, hi, vel, pitch_for):
    times = _ramp_onsets(a, b, beat, lo, hi)
    out = []
    for i, t in enumerate(times):
        nxt = times[i + 1] if i + 1 < len(times) else b
        out.append(("ostinato", t, min(b, t + 0.8 * (nxt - t)), pitch_for(i, t, a, beat), max(1, vel - 10), None))
    return out


def _base_pitch(i, t, a, beat):
    return OSTINATO[i % len(OSTINATO)]


def _sus_pitch(i, t, a, beat):
    p = SUS_PITCHES[i % len(SUS_PITCHES)]
    k = (t - a) / beat
    r = round(k)
    strong = abs(k - r) < 1e-6
    if strong and p % 12 in (2, 5):
        p = 52  # fix 1: E3 on a strong beat (Dsus2 with the D bass and A), never D or F over the D bass
    return p


def _grid(s, e, step, frac=0.0):
    """(k, time) for times s + (k + frac) * step that fall before e."""
    out, k = [], 0
    while True:
        t = s + (k + frac) * step
        if t >= e - EPS:
            return out
        out.append((k, t))
        k += 1


def _drum_segs(genre, roles, s, e, beat, dlo, dhi, v):
    """Genre drum pattern for one section (Decision 22). Only roles listed in roles_on are written."""
    segs = []

    def add(role, t, pitch, dv, dur=0.1):
        if role in roles and t < e - EPS:
            segs.append((role, t, min(e, t + dur), pitch, max(1, min(127, v + dv)), None))

    if genre == "hypnotic_techno":
        for _, t in _grid(s, e, beat):
            add("drums", t, DRUM_KICK, 10)
        for _, t in _grid(s, e, beat, 0.5):
            add("drums", t, DRUM_HAT, -12, 0.05)
    elif genre == "melodic_techno":
        for k, t in _grid(s, e, beat):
            add("drums", t, DRUM_KICK, 10)
            if k % 4 in (1, 3):
                add("drums", t, DRUM_CLAP, 0)
        for _, t in _grid(s, e, beat, 0.5):
            add("drums", t, DRUM_OPEN_HAT, -12, 0.2)
    elif genre == "club_folk_groove":
        for _, t in _grid(s, e, beat):
            add("drums", t, DRUM_KICK, 10)
        for k, t in _grid(s, e, beat * 2 / 3):  # 3 against 4: six onsets per 4-beat bar
            if k % 6 == 0:
                add("folk_perc", t, FOLK_LOW, 10)
            else:
                add("folk_perc", t, FOLK_MID, 0)
    elif genre == "drum_and_bass":
        for k, t in _grid(s, e, beat):
            if k % 4 in (0, 2):
                add("drums", t, DRUM_KICK, 10)
            if k % 4 in (1, 3):
                add("drums", t, DRUM_SNARE, 0)
        for k, t in _grid(s, e, beat, 0.5):
            if k % 4 == 1:  # the 'and' of beat 2
                add("drums", t, DRUM_KICK, 0)
        for t in _ramp_onsets(s, e, beat, dlo, dhi):
            add("drums", t, DRUM_HAT, -15, 0.05)
    elif genre == "half_time_dnb":
        for k, t in _grid(s, e, beat):
            if k % 4 == 0:
                add("drums", t, DRUM_KICK, 10)
            if k % 4 == 2:
                add("drums", t, DRUM_SNARE, 0)
            if k % 2 == 1:
                add("drums", t, DRUM_HAT, -15, 0.05)
    elif genre == "ambient" and "drums" in roles:  # Decision 30: heartbeat, soft lub-dub on each beat
        for _, t in _grid(s, e, beat):
            for off in (0.0, 0.25 * beat):
                if t + off < e - EPS:
                    segs.append(("drums", t + off, min(e, t + off + 0.1), DRUM_KICK, min(60, v), HEART))
    elif genre == "unplugged":
        for _, t in _grid(s, e, beat):
            add("drums", t, DRUM_TICK, -20, 0.05)
    return segs


def _base_segments(sections):
    segs = []
    for sec in sections:
        s, e, v, roles = sec["start"], sec["end"], sec["vel"], sec["roles"]
        beat = 60.0 / sec["bpm"]
        step = beat * FEEL_STEP[sec["feel"]]
        if "drone" in roles:
            segs.append(("drone", s, e, DRONE_PITCH, max(1, v - 10), None))
        if "pad" in roles:
            for p in PAD_CHORD:
                segs.append(("pad", s, e, p, max(1, v - 10), None))
        if "bass" in roles:
            t = s
            while t < e - EPS:
                segs.append(("bass", t, min(e, t + 0.8 * step), DRONE_PITCH, v, None))
                segs.append(("bass", t, min(e, t + 0.8 * step), MID_PITCH, max(1, round(0.6 * v)), None))
                t += step
        if sec.get("genre") in GENRES:
            segs += _drum_segs(sec["genre"], roles, s, e, beat, sec["dlo"], sec["dhi"], v)
        elif "drums" in roles:  # no genre in the plan: the old kick on every felt step
            t = s
            while t < e - EPS:
                segs.append(("drums", t, min(e, t + 0.1), KICK, min(127, v + 10), None))
                t += step
        if "ostinato" in roles:
            segs += _ostinato_segs(s, e, beat, sec["dlo"], sec["dhi"], v, _base_pitch)
    return segs


def _hang_end(t, natural_end, voice, sec_end):
    """Decision 28: end of a theme's last note. It is set to the earliest of its voice gap's end, the section end and
    t + 1.5 s (a note that runs past its gap is trimmed to the gap end, a short one is held). A note that starts inside
    a voice window does not hang and keeps its step length."""
    if _inside(voice, t):
        return natural_end
    gap_ends = [a for a, _ in voice if a > t - EPS]
    target = min([min(gap_ends) if gap_ends else math.inf, sec_end, t + 1.5])
    return target if target > t + MIN_DUR_S else natural_end


def _theme_vel(sections, t):
    """Decision 39: a theme note's velocity follows the upper intensity of the section at its time."""
    sec = _section_at(sections, t)
    return 100 if sec is None else int(round(55 + 45 * sec["ihi"]))


def _event_segments(events, sections, sonic, voice, warnings, ledger, lse, peak):
    segs = []
    for ev in events:
        at, role, where, typ = ev["at"], ev["role"], ev["where"], ev["type"]
        if typ == "sonic_logo":
            segs.append((sonic["role"], at, at + sonic["length"], sonic["sub"], 90, ("sonic",)))
            for p in sonic["bells"]:
                segs.append((sonic["role"], at, at + sonic["length"], p, 70, ("sonic",)))
        elif typ == "hit":
            low = ev["band"] == "low"
            if low or _inside(voice, at):
                if not low:
                    warnings.append(_err("HIT_FORCED_LOW", where, "hit under voice forced to band low (D2)"))
                pitch = LOW_PITCH
            else:
                pitch = BRIGHT_PITCH
            segs.append((role, at, at + 0.25, pitch, 110, None))
        elif typ == "theme_entry":
            sec = _section_at(sections, at)
            if sec is None:
                warnings.append(_err("EVENT_OUTSIDE_SECTIONS", where, "no section covers this time; 60 BPM used"))
                bpm = 60.0
            else:
                bpm = sec["bpm"]
            step = (60.0 / bpm) * FEEL_STEP[ev["feel"]]
            ledger["theme_total"][ev["idx"]] = len(ev["pitches"])
            ledger["theme_meta"][ev["idx"]] = (ev["theme"], at)
            loud = peak is not None and abs(at - peak) <= FRAME_S + EPS  # Decision 39: the peak entry
            for k, p in enumerate(ev["pitches"]):
                t = at + k * step
                tag = ("theme", ev["idx"], k, ev["theme"])
                end_k = t + 0.9 * step
                if k == len(ev["pitches"]) - 1:  # Decision 28: the last note hangs
                    end_k = _hang_end(t, end_k, voice, sec["end"] if sec is not None else math.inf)
                    if ev["theme"] in GOD_THEMES:  # Decision 32: drums go silent until this note ends
                        ledger["god"].append((at, end_k))
                vel = 120 if loud else _theme_vel(sections, t)
                segs.append((role, t, end_k, p, vel, tag))
                if p < PHONE_MIN and role != "pad":  # fix 4: a pad entry sounds its bible pitches exactly
                    partner = p + 12 if p + 12 >= PHONE_MIN else p + 24
                    segs.append((role, t, end_k, partner, 120 if loud else max(1, round(0.7 * vel)),
                                 tag + ("octave",)))
        elif typ == "end_sting":
            for p in END_CLUSTER + (END_BRIGHT if at > lse + EPS else ()):  # Decision 34
                segs.append((role, at, at + 0.3, p, 110, ("end",)))
    return segs


def _swell_segments(cuts):
    return [("pad", max(0.0, c["at"] - 1.0), c["at"], SWELL_PITCH, 40, ("swell", c["at"]))
            for c in cuts if c["transition"] in SWELL_TRANSITIONS and c["at"] > EPS]


def _colour_splits(segs, cuts):
    """key_colour_on_downbeat (no swell): pad and drone notes that sustain across that cut are split on the cut
    downbeat, so the chord is struck again exactly there. The new colour comes from the next section's own notes."""
    ats = [c["at"] for c in cuts if c["transition"] == COLOUR_TRANSITION]
    if not ats:
        return segs
    out = []
    for sg in segs:
        role, a, b = sg[0], sg[1], sg[2]
        cut = next((t for t in ats if role in ("pad", "drone") and a + EPS < t < b - EPS), None)
        if cut is None:
            out.append(sg)
        else:
            out.append((role, a, cut) + sg[3:])
            out.append((role, cut, b) + sg[3:])
    return out


def _cut_out(segs, pred, a, b, ledger):
    """Remove the part of every matching segment that lies in [a, b). Returns (segments, pieces touched)."""
    if b - a <= EPS:
        return segs, 0
    out, touched = [], 0
    for sg in segs:
        role, t, end, p, v, tag = sg
        if not (t < b - EPS and end > a + EPS) or not pred(sg):
            out.append(sg)
            continue
        touched += 1
        if tag is not None and tag[0] == "theme":
            ledger["altered"].add(tag)
        if t < a - EPS:
            out.append((role, t, a, p, v, tag))
        if end > b + EPS:
            out.append((role, b, end, p, v, tag))
    return out, touched


def _quiet_pass(segs, quiet, rule, ledger, warnings):
    """Decision 18: inside the quiet window keep only the listed roles, the listed theme and the end sting."""
    if quiet is None:
        return segs
    a, b = quiet
    roles, theme = rule

    def pred(sg):  # True = cut
        role, tag = sg[0], sg[5]
        if tag == ("end",):
            return False
        if theme is not None and tag is not None and tag[0] == "theme" and tag[3] == theme:
            return False
        if role not in roles:
            return True
        if role == "drums":
            return sg[3] != DRUM_TICK
        return False

    segs, n = _cut_out(segs, pred, a, b, ledger)
    if n:
        warnings.append(_err("QUIET_SUPPRESSED", f"quiet {a:g}-{b:g} s",
                             f"{n} segments outside the quiet roles {sorted(roles)} and theme {theme} were cut"))
    return segs


def _closing(segs, s, e, sec, lse, total, ledger):
    v = sec["vel"]

    def pred(sg):
        if sg[0] in ("ostinato", "pluck", "lead", "brass"):
            return True
        if sg[0] == "hits":
            return sg[5] != ("end",)
        if sg[0] == "pad":
            return sg[5] is None
        return False

    segs, _ = _cut_out(segs, pred, s, e, ledger)
    segs += [("pad", s, e, p, max(1, v - 10), None) for p in OUTRO_PAD]
    tail = lse + TAIL_S
    if tail < total - EPS:
        segs, _ = _cut_out(segs, lambda sg: True, tail, total, ledger)
    return segs


def _clip_to_sections(segs, sections):
    """Decision 26: a note born in a section ends at that section's end, so the next downbeat is a fresh attack."""
    out = []
    for role, t, end, p, v, tag in segs:
        sec = _section_at(sections, t)
        if sec is not None and end > sec["end"] + EPS:
            end = sec["end"]
        out.append((role, t, end, p, v, tag))
    return out


def _shot_pass(segs, shots, sections, events, voice, lse, total, quiet, ledger, errors, warnings):
    for sh in shots:
        s, e, hook, where = sh["start"], sh["end"], sh["hook"], sh["id"]
        sec = _section_at(sections, s)
        if sec is None:
            continue
        beat = 60.0 / sec["bpm"]
        v = sec["vel"]
        if sh["closing"] or hook == "closing":
            segs = _closing(segs, s, e, sec, lse, total, ledger)
        elif hook == "reveal":
            entries = [ev["at"] for ev in events if ev["type"] == "theme_entry" and s - EPS <= ev["at"] < e - EPS]
            if not entries:
                errors.append(_err("REVEAL_NO_ENTRY", where, "reveal shot has no theme_entry (rule 3)"))
                continue
            # Decision 25: the sonic logo at 0 s is the one exception to the reveal rule.
            segs, _ = _cut_out(segs, lambda sg: sg[0] not in REVEAL_KEEP and sg[5] != ("sonic",),
                               s, min(entries), ledger)
        elif hook == "expression-beat":
            segs, _ = _cut_out(segs, lambda sg: sg[0] != "pad" and sg[5] != HEART, s, e, ledger)
            for va, vb in voice:
                if va < e and vb > s:
                    segs, _ = _cut_out(segs, _is_theme, max(va, s), min(vb, e), ledger)
        elif hook == "suspense":
            if "ostinato" not in sec["roles"]:
                continue  # Decision 24: nothing to replace in this section
            if quiet is not None and s < quiet[1] and e > quiet[0]:
                warnings.append(_err("SHOT_RULE_SKIPPED", where,
                                     "suspense ostinato skipped: the bible quiet moment wins here"))
                continue
            segs, _ = _cut_out(segs, lambda sg: sg[0] == "ostinato", s, e, ledger)
            segs += _ostinato_segs(s, e, beat, sec["dlo"], sec["dhi"], v, _sus_pitch)
        elif hook == "reversal":
            turns = [ev["at"] for ev in events if ev["type"] == "hit" and s - EPS <= ev["at"] < e - EPS]
            if turns:
                turn = min(turns)
                segs, _ = _cut_out(segs, lambda sg: sg[0] == "pad" and sg[5] is None, turn, e, ledger)
                segs += [("pad", turn, e, p, max(1, v - 10), None) for p in DARK_PAD]
        else:
            warnings.append(_err("SHOT_HOOK_UNKNOWN", where, f"hook_type {hook!r} has no rule"))
    return segs


def _mark(ledger, tag, reason=None):
    if tag is None:
        return
    if tag[0] == "theme":
        ledger["altered"].add(tag)
    if tag[0] == "swell" and reason == "dropout":
        ledger["swell_drop"].add(tag)


def _cut_spans(items, spans):
    """Decision 38: cut every (start, end, vel) base note out of the theme spans; a note resumes after a span."""
    out = []
    for t, end, v in items:
        pieces = [(t, end)]
        for a, b in spans:
            nxt = []
            for x, y in pieces:
                if b <= x + EPS or a >= y - EPS:
                    nxt.append((x, y))
                    continue
                if x < a - EPS:
                    nxt.append((x, a))
                if y > b + EPS:
                    nxt.append((b, y))
            pieces = nxt
        out += [(x, y, v) for x, y in pieces]
    return out


def _merge_runs(items):
    """Decision 16 and 27: join strictly overlapping notes of one pitch; touching notes stay apart."""
    merged = []
    for t, end, v in sorted(items):
        if merged and t < merged[-1][1] - EPS:
            merged[-1] = [merged[-1][0], max(merged[-1][1], end), max(merged[-1][2], v)]
        else:
            merged.append([t, end, v])
    return merged


def _fit(segs, dropouts, voice, gated, total, ledger, warnings):
    """Apply drop-outs (all roles) and the voice rule (gated roles), cutting or splitting notes. Returns role -> rows."""
    drops = sorted(dropouts)
    stats = ledger["stats"]
    kept = {r: [] for r in ROLES}
    stack = list(segs)
    while stack:
        role, t, end, p, v, tag = stack.pop()
        end = min(end, total)
        if end - t < MIN_DUR_S:
            stats["too_short"] += 1
            _mark(ledger, tag)
            warnings.append(_err("NOTE_TOO_SHORT", f"{role} at {t:g} s",
                                 f"pitch {p} lost: {max(0.0, end - t):.3f} s left after cuts"))
            continue
        hit = _first_overlap(drops, t, end)
        if hit:
            a, b = hit
            _mark(ledger, tag, "dropout")
            if t < a - EPS:
                stack.append((role, t, a, p, v, tag))
            if end > b + EPS:
                stack.append((role, b, end, p, v, tag))
            stats["dropout_cuts"] += 1
            continue
        in_voice = _first_overlap(voice, t, end)
        if role in SOFT_ROLES and in_voice:
            v = min(v, SOFT_UNDER_VOICE)
        exempt = role in LOW_OK and p <= LOW_MAX
        if role in gated and not exempt and in_voice:
            a, _ = in_voice
            _mark(ledger, tag, "voice")
            if t < a - EPS:
                stack.append((role, t, a, p, v, tag))
                stats["voice_clips"] += 1
            else:
                stats["voice_drops"] += 1
            continue
        kept[role].append((t, end, p, v, tag is not None and tag[0] == "theme"))

    tracks = {}
    for role in ROLES:
        rows, by_pitch = [], {}
        for t, end, p, v, th in kept[role]:
            by_pitch.setdefault(p, []).append((t, min(end, total), v, th))
        for p, items in by_pitch.items():
            spans = [(t, end) for t, end, _, th in items if th]
            own = _cut_spans([(t, end, v) for t, end, v, th in items if not th], spans)
            theirs = [(t, end, v) for t, end, v, th in items if th]
            for t, end, v in _merge_runs(own) + _merge_runs(theirs):
                t6, e6 = round(t, 6), round(end, 6)
                if e6 - t6 < MIN_DUR_S - EPS:
                    continue
                rows.append({"t_s": t6, "dur_s": round(e6 - t6, 6), "pitch": int(p), "vel": int(v)})
        if rows:  # Decision 21: one track per role that has notes
            tracks[role] = sorted(rows, key=lambda r: (r["t_s"], r["pitch"]))
    return tracks


def _build(plan, cue, bible, errors, warnings, stats):
    if not isinstance(plan, dict):
        errors.append(_err("PLAN", "plan", "must be a dict"))
        return None
    if plan.get("schema_version") != 1:
        errors.append(_err("PLAN_SCHEMA", "plan.schema_version", "must be 1"))
        return None
    if not isinstance(cue, dict) or not _num(cue.get("total_s")) or cue["total_s"] <= 0:
        errors.append(_err("CUE_TOTAL", "cue_sheet.total_s", "missing or not positive"))
        return None
    if not isinstance(bible, dict) or not isinstance(bible.get("themes"), dict):
        errors.append(_err("BIBLE", "bible.themes", "must be a dict"))
        return None
    total = float(cue["total_s"])
    voice_obj = cue.get("voice") if isinstance(cue.get("voice"), dict) else {}
    voice = _windows(voice_obj.get("union"), "cue_sheet.voice.union", errors)
    ret = cue.get("retention") if isinstance(cue.get("retention"), dict) else {}
    lse = ret.get("last_speech_end_s") if _num(ret.get("last_speech_end_s")) else total
    sections = _sections(plan.get("sections"), total, errors)
    events = _events(plan.get("events"), total, bible["themes"], errors)
    cuts = _cuts(plan.get("cuts"), cue, total, errors, warnings)
    automation = _automation(plan.get("automation"), total, errors)
    shots = _shots(cue.get("shots"), total, errors)
    sonic = _sonic(bible, errors)
    quiet = _quiet(bible, errors)
    _peak_rehook(plan, sections, events, errors)
    if not any(ev["type"] == "sonic_logo" for ev in events):
        errors.append(_err("NO_SONIC_LOGO", "plan.events", "the sonic logo event at 0 s is missing"))
    for ev in events:
        if ev["type"] == "sonic_logo" and abs(ev["at"]) > EPS:
            errors.append(_err("SONIC_NOT_AT_ZERO", ev["where"], "the sonic logo must sit on frame 0 (rule 6)"))
    if errors or sonic is None:
        return None

    busy = busy_roles(bible)
    gated = busy | GATED_EXTRA
    ledger = {"altered": set(), "swell_drop": set(), "theme_total": {}, "theme_meta": {}, "god": [],
              "stats": stats}
    dropouts = [(ev["at"] - ev["drop"], ev["at"]) for ev in events if ev["drop"] > 0]
    segs = _base_segments(sections)
    peak = plan.get("peak_at_s") if _num(plan.get("peak_at_s")) else None
    segs += _event_segments(events, sections, sonic, voice, warnings, ledger, lse, peak)
    for a, b in ledger["god"]:  # Decision 32
        segs, _ = _cut_out(segs, lambda sg: sg[0] in GOD_SILENT_ROLES, a, b, ledger)
    segs += _swell_segments(cuts)
    segs = _colour_splits(segs, cuts)
    segs = _quiet_pass(segs, quiet, _quiet_rule(bible), ledger, warnings)
    segs = _shot_pass(segs, shots, sections, events, voice, lse, total, quiet, ledger, errors, warnings)
    if errors:
        return None
    segs = _clip_to_sections(segs, sections)
    stats["segments"] = len(segs)
    tracks = _fit(segs, dropouts, voice, gated, total, ledger, warnings)
    for tag in sorted(ledger["swell_drop"]):
        warnings.append(_err("SWELL_CUT_BY_DROPOUT", f"cut at {tag[1]:g} s",
                             "the swell into this cut is cut by a drop-out; silence wins (rules 7-8)"))
    for idx, n_total in sorted(ledger["theme_total"].items()):
        altered = sum(1 for tg in ledger["altered"] if tg[1] == idx and len(tg) == 4)
        if altered:
            name, at = ledger["theme_meta"][idx]
            warnings.append(_err("THEME_TRUNCATED", f"plan.events[{idx}]",
                                 f"{name} at {at:g} s: {altered} of {n_total} notes cut or dropped"))
    markers = [{"t_s": round(sh["start"], 6), "name": _marker_name(sh)} for sh in shots]
    stats["notes"] = sum(len(v) for v in tracks.values())
    stats["per_role"] = {r: len(v) for r, v in tracks.items()}
    automation_out = automation
    return tracks, markers, automation_out


def write_notes(plan, cue_sheet, bible):
    """Exact notes per role (absolute reel seconds). Never raises: problems are returned in errors."""
    errors, warnings = [], []
    stats = {"dropout_cuts": 0, "voice_clips": 0, "voice_drops": 0, "too_short": 0}
    built = None
    try:
        built = _build(plan, cue_sheet, bible, errors, warnings, stats)
    except Exception as exc:  # last-resort guard: report, never raise
        errors.append(_err("INTERNAL", "write_notes", f"{type(exc).__name__}: {exc}"))
    if errors or built is None:
        return _result(False, {}, [], [], errors, warnings, stats)
    tracks, markers, automation = built
    return _result(True, tracks, markers, automation, errors, warnings, stats)


# ---------------------------------------------------------------- MIDI writer (stdlib only)

def _vlq(n):
    buf = [n & 0x7F]
    n >>= 7
    while n:
        buf.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(buf))


def _tick(t):
    return int(round(t * PPQ))


def _meta(kind, payload):
    return b"\xff" + bytes([kind]) + _vlq(len(payload)) + payload


def _chunk(events):
    events = sorted(events, key=lambda e: (e[0], e[1]))
    body = bytearray()
    last = 0
    for tick, _, data in events:
        body += _vlq(tick - last) + data
        last = tick
    body += _vlq(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def _midi_bytes(tracks, markers, errors):
    if not isinstance(tracks, dict):
        errors.append(_err("MIDI_TRACKS", "tracks", "must be a dict of role -> notes"))
        return b"", 0
    head = [(0, -1, _meta(0x03, b"CONDUCTOR")),
            (0, -1, _meta(0x51, TEMPO_US.to_bytes(3, "big"))),
            (0, -1, _meta(0x58, bytes([4, 2, 24, 8])))]
    for m in markers:
        if not (isinstance(m, dict) and _num(m.get("t_s")) and m["t_s"] >= 0 and isinstance(m.get("name"), str)):
            errors.append(_err("MIDI_MARKER", "markers", f"bad marker {m!r}"))
            continue
        head.append((_tick(m["t_s"]), 0, _meta(0x06, m["name"].encode("utf-8"))))
    chunks = [_chunk(head)]
    count = 0
    for idx, (role, notes) in enumerate(tracks.items()):
        if not isinstance(notes, list):
            errors.append(_err("MIDI_TRACK", str(role), "notes must be a list"))
            continue
        ch = MIDI_CHANNEL.get(str(role), idx % 16)  # Decision 37
        events = [(0, -1, _meta(0x03, str(role).encode("utf-8")))]
        for n in notes:
            ok = (isinstance(n, dict) and _num(n.get("t_s")) and _num(n.get("dur_s"))
                  and n["t_s"] >= 0 and n["dur_s"] > 0
                  and isinstance(n.get("pitch"), int) and 0 <= n["pitch"] <= 127
                  and isinstance(n.get("vel"), int) and 1 <= n["vel"] <= 127)
            if not ok:
                errors.append(_err("MIDI_NOTE", str(role), f"bad note {n!r}"))
                continue
            on = _tick(n["t_s"])
            off = max(on + 1, _tick(n["t_s"] + n["dur_s"]))
            events.append((on, 1, bytes([0x90 | ch, n["pitch"], n["vel"]])))
            events.append((off, 0, bytes([0x80 | ch, n["pitch"], 0])))
            count += 1
        chunks.append(_chunk(events))
    if errors:
        return b"", 0
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQ)
    return header + b"".join(chunks), count


def write_midi(tracks, path, markers=None):
    """Write a type-1 clock-mode .mid. Never raises: returns ok, errors and the note count."""
    errors = []
    try:
        data, count = _midi_bytes(tracks, markers or [], errors)
        if errors:
            return {"ok": False, "errors": errors, "path": str(path), "notes": 0}
        Path(path).write_bytes(data)
        return {"ok": True, "errors": [], "path": str(path), "notes": count}
    except (OSError, TypeError, ValueError, AttributeError) as exc:
        errors.append(_err("MIDI_WRITE", str(path), f"{type(exc).__name__}: {exc}"))
        return {"ok": False, "errors": errors, "path": str(path), "notes": 0}
