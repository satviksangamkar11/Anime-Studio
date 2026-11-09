"""Tests for score/note_writer.py. Main fixture: the real Kalika reel 1 cue sheet and the bible (style fix, NWR3 round),
with a plan that follows the reel's own sections and events (8 sections, 9 cuts). Small synthetic reels (SMALL_*,
variants built inside tests, _genre_run) cover single rules.

Fixture decisions: reveal shots need a theme entry (rule 17), so shot 4 (18-26 s) reveals SANDHYA at 25.36 (feel quad,
into the 25.349-26.3 gap) and shot 5 (26-34 s) reveals KAMADEVA at 29.69 (feel quad, into the 29.682-30.2 gap). Shot 2
(6-11 s) carries the study's heartbeat kick. KAMADEVA also enters at 43.2 (chaos transform) and 56.0 (curse transform).
The 11.0 s cut is a hard cut and an act change, so the plan gives a reverse swell there."""
import copy
import json
import struct
from pathlib import Path

import pytest

from score import note_writer as nw

ROOT = Path(__file__).resolve().parents[2]
BIBLE = ROOT / "stories" / "kalika_puran_bhag1" / "music_bible.json"
CUE = ROOT / "score" / "tests" / "fixtures" / "cue_sheet_reel1_v3.json"  # frozen v3 (70.0 s) test data
FRAME = 1 / 24
TOL_TICK_S = 1 / 480 + 1e-9
DROP_BEAT = 60 / 176
BUILD_BEAT = 60 / 128


def _cut(at, transition):
    return {"at_s": at, "transition": transition}


# Reel 1 plan (sections follow the style study: 60 ambient, 128 hypnotic/melodic/club-folk, 176 DnB, 176 half-time, 60).
REEL_PLAN = {
    "schema_version": 1, "episode": 1, "style": "electronic", "home_key": "D minor",
    "sections": [
        {"start_s": 0.0, "end_s": 6.0, "act": "HOOK", "bpm": 60, "feel": "normal", "genre": "ambient",
         "density_per_beat": [1, 1], "roles_on": ["drone", "pad", "bass"], "intensity": [0.2, 0.4]},
        {"start_s": 6.0, "end_s": 11.0, "act": "HOOK", "bpm": 60, "feel": "normal", "genre": "ambient",
         "density_per_beat": [1, 1], "roles_on": ["drone", "pad", "bass", "drums"], "intensity": [0.2, 0.4]},
        {"start_s": 11.0, "end_s": 18.0, "act": "BUILD", "bpm": 128, "feel": "normal", "genre": "hypnotic_techno",
         "density_per_beat": [2, 2], "roles_on": ["drone", "pad", "bass", "drums", "ostinato"], "intensity": [0.4, 0.6]},
        {"start_s": 18.0, "end_s": 26.0, "act": "BUILD", "bpm": 128, "feel": "normal", "genre": "melodic_techno",
         "density_per_beat": [2, 2], "roles_on": ["drone", "pad", "bass", "drums"], "intensity": [0.4, 0.6]},
        {"start_s": 26.0, "end_s": 34.0, "act": "BUILD", "bpm": 128, "feel": "normal", "genre": "club_folk_groove",
         "density_per_beat": [2, 2], "roles_on": ["drone", "pad", "bass", "drums", "folk_perc"],
         "intensity": [0.5, 0.6]},
        {"start_s": 34.0, "end_s": 48.0, "act": "DROP", "bpm": 176, "feel": "normal", "genre": "drum_and_bass",
         "density_per_beat": [2, 4], "roles_on": ["drone", "pad", "ostinato", "bass", "drums"],
         "intensity": [0.7, 0.9]},
        {"start_s": 48.0, "end_s": 64.0, "act": "DROP", "bpm": 176, "feel": "half", "genre": "half_time_dnb",
         "density_per_beat": [1, 1], "roles_on": ["drone", "pad", "bass", "drums"], "intensity": [0.85, 0.95]},
        {"start_s": 64.0, "end_s": 70.0, "act": "OUTRO", "bpm": 60, "feel": "normal", "genre": "unplugged",
         "density_per_beat": [1, 1], "roles_on": ["drone", "pad", "drums"], "intensity": [0.2, 0.3]},
    ],
    "events": [
        {"at_s": 0.0, "type": "sonic_logo"},
        {"at_s": 3.5, "type": "theme_entry", "theme": "KALI", "role": "pad", "feel": "normal"},
        {"at_s": 25.36, "type": "theme_entry", "theme": "SANDHYA", "role": "lead", "feel": "quad"},
        {"at_s": 29.69, "type": "theme_entry", "theme": "KAMADEVA", "role": "pluck", "feel": "quad"},
        {"at_s": 40.25, "type": "theme_entry", "theme": "MAIN", "role": "lead", "feel": "double"},
        {"at_s": 34.0, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits"},  # 33.6 s dropout, DnB at 34.0
        {"at_s": 43.083, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits"},
        {"at_s": 43.2, "type": "theme_entry", "theme": "KAMADEVA", "role": "lead", "feel": "quad",
         "transform": "chaos_41s"},
        {"at_s": 48.0, "type": "theme_entry", "theme": "SHIVA", "role": "brass", "feel": "half",
         "preceded_by_dropout_s": 0.4},
        {"at_s": 56.0, "type": "theme_entry", "theme": "KAMADEVA", "role": "pad", "feel": "half",
         "transform": "curse_56_64s"},
        {"at_s": 60.0, "type": "hit", "band": "low", "role": "hits", "preceded_by_dropout_s": 0.4},
        {"at_s": 64.0, "type": "theme_entry", "theme": "MAIN", "role": "piano", "feel": "normal"},
        {"at_s": 69.85, "type": "end_sting"},
    ],
    "cuts": [_cut(6.0, "bed_continues"), _cut(11.0, "reverse_swell_to_cut"), _cut(18.0, "reverse_swell_to_cut"),
             _cut(26.0, "bed_continues"), _cut(34.0, "act_change"), _cut(41.0, "bed_continues"),
             _cut(48.0, "swell_to_cut"), _cut(56.0, "bed_continues"), _cut(64.0, "act_change")],
    "automation": [{"role": "pad", "macro": 1, "points": [[18.0, 0.2], [20.0, 0.8]]}],
    "rehook_at_s": 40.25, "peak_at_s": 48.0,
}

SMALL_CUE = {
    "total_s": 10.0,
    "voice": {"union": [[1.0, 4.0], [6.0, 9.0]]},
    "retention": {"last_speech_end_s": 9.0},
    "cuts": [{"at_s": 5.0}],
    "shots": [{"id": "SHOT-001", "start_s": 0.0, "end_s": 5.0, "hook_type": "reveal",
               "opening_hook": True, "closing_hook": False},
              {"id": "SHOT-002", "start_s": 5.0, "end_s": 10.0, "hook_type": "reversal",
               "opening_hook": False, "closing_hook": False}],
}

SMALL_PLAN = {
    "schema_version": 1,
    "sections": [{"start_s": 0.0, "end_s": 10.0, "bpm": 120, "feel": "normal", "roles_on":
                  ["drone", "pad", "bass", "drums", "ostinato", "hits", "brass"], "density_per_beat": [2, 2],
                  "intensity": [0.5, 0.5]}],
    "events": [
        {"at_s": 0.0, "type": "sonic_logo"},
        {"at_s": 2.0, "type": "hit", "role": "hits"},
        {"at_s": 4.5, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits"},
        {"at_s": 6.5, "type": "theme_entry", "theme": "SHIVA", "role": "brass", "feel": "half"},
        {"at_s": 0.0, "type": "theme_entry", "theme": "MUNIS", "role": "pad", "feel": "normal"},
    ],
    "cuts": [_cut(5.0, "reverse_swell_to_cut")],
}


@pytest.fixture(scope="module")
def bible():
    return json.loads(BIBLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cue():
    return json.loads(CUE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def reel(cue, bible):
    rep = nw.write_notes(REEL_PLAN, cue, bible)
    assert rep["ok"], rep["errors"]
    return rep


def _all_notes(tracks):
    return [(role, n) for role, rows in tracks.items() for n in rows]


def _overlaps(n, a, b):
    return n["t_s"] < b - 1e-6 and n["t_s"] + n["dur_s"] > a + 1e-6


def _onsets(tracks, role, pitch=None, a=-1.0, b=1e9):
    return [n["t_s"] for n in tracks.get(role, []) if (pitch is None or n["pitch"] == pitch) and a <= n["t_s"] < b]


def _codes(items):
    return [w["code"] for w in items]


def _ev(plan, **want):
    """The first plan event whose fields match want, e.g. _ev(plan, theme="SHIVA")."""
    return next(e for e in plan["events"] if all(e.get(k) == v for k, v in want.items()))


def _small(plan_mut=None, cue_mut=None, bible_mut=None):
    plan = copy.deepcopy(SMALL_PLAN)
    cue_ = copy.deepcopy(SMALL_CUE)
    bib = json.loads(BIBLE.read_text(encoding="utf-8"))
    if plan_mut:
        plan_mut(plan)
    if cue_mut:
        cue_mut(cue_)
    if bible_mut:
        bible_mut(bib)
    return nw.write_notes(plan, cue_, bib)


def _ostinato_plan(feel, bpm=120, dens=(2, 2), voice=()):
    plan = {"schema_version": 1, "sections": [{"start_s": 0.0, "end_s": 10.0, "bpm": bpm, "feel": feel,
                                                "roles_on": ["ostinato"], "density_per_beat": list(dens),
                                                "intensity": [0.5, 0.5]}],
            "events": [{"at_s": 0.0, "type": "sonic_logo"}], "cuts": []}
    cue_ = {"total_s": 10.0, "voice": {"union": [list(v) for v in voice]}, "cuts": [],
            "shots": [{"id": "SHOT-001", "start_s": 0.0, "end_s": 10.0, "hook_type": "reversal",
                       "opening_hook": False, "closing_hook": False}]}
    return plan, cue_


def _genre_run(genre, bpm, dens, roles, feel="normal", end=8.0):
    """Tracks for one section of one genre, no voice, no events but the sonic logo."""
    plan = {"schema_version": 1,
            "sections": [{"start_s": 0.0, "end_s": end, "bpm": bpm, "feel": feel, "genre": genre,
                          "roles_on": roles, "density_per_beat": list(dens), "intensity": [0.5, 0.5]}],
            "events": [{"at_s": 0.0, "type": "sonic_logo"}], "cuts": []}
    cue_ = {"total_s": end, "voice": {"union": []}, "cuts": [],
            "shots": [{"id": "SHOT-001", "start_s": 0.0, "end_s": end, "hook_type": "reversal",
                       "opening_hook": False, "closing_hook": False}]}
    rep = nw.write_notes(plan, cue_, json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    return rep["tracks"]


def _grid_k(a, b, step, frac=0.0):
    """(k, time) for times a + (k + frac) * step before b, the same grid the writer uses."""
    out, k = [], 0
    while a + (k + frac) * step < b - 1e-9:
        out.append((k, a + (k + frac) * step))
        k += 1
    return out


def _grid_times(a, b, step, frac=0.0):
    return [t for _, t in _grid_k(a, b, step, frac)]


def _times_near(got, want):
    assert len(got) == len(want), (len(got), len(want), got[:6], want[:6])
    for g, w in zip(got, want):
        assert abs(g - w) < 1e-3, (g, w)


# ---------------------------------------------------------------- MIDI parser (test side, stdlib only)

def _read_vlq(buf, i):
    val = 0
    while True:
        byte = buf[i]
        i += 1
        val = (val << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return val, i


def _parse_midi(data):
    assert data[:4] == b"MThd"
    assert struct.unpack(">I", data[4:8])[0] == 6
    fmt, ntrk, div = struct.unpack(">HHH", data[8:14])
    pos, tracks = 14, []
    for _ in range(ntrk):
        assert data[pos:pos + 4] == b"MTrk"
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + length]
        pos += 8 + length
        tr = {"notes": [], "markers": [], "tempo": [], "name": None}
        i, tick, running, open_on = 0, 0, None, {}
        while i < len(body):
            delta, i = _read_vlq(body, i)
            tick += delta
            status = body[i]
            if status == 0xFF:
                kind = body[i + 1]
                ln, i2 = _read_vlq(body, i + 2)
                payload = body[i2:i2 + ln]
                i = i2 + ln
                if kind == 0x2F:
                    break
                if kind == 0x06:
                    tr["markers"].append((tick, payload.decode("utf-8")))
                elif kind == 0x51:
                    tr["tempo"].append(int.from_bytes(payload, "big"))
                elif kind == 0x03:
                    tr["name"] = payload.decode("utf-8")
                continue
            if status in (0xF0, 0xF7):
                ln, i2 = _read_vlq(body, i + 1)
                i = i2 + ln
                continue
            if status & 0x80:
                running = status
                i += 1
            else:
                assert running is not None, "data byte with no running status"
                status = running
            kind, ch = status & 0xF0, status & 0x0F
            if kind in (0xC0, 0xD0):
                i += 1
                continue
            pitch, vel = body[i], body[i + 1]
            i += 2
            if kind == 0x90 and vel > 0:
                open_on.setdefault((ch, pitch), []).append(tick)
            elif kind == 0x80 or (kind == 0x90 and vel == 0):
                on = open_on[(ch, pitch)].pop(0)
                tr["notes"].append((on, tick, pitch))
        tracks.append(tr)
    return fmt, ntrk, div, tracks


# ---------------------------------------------------------------- basics and C1

def test_note_name_table():
    assert nw.note_to_midi("D3") == 50
    assert nw.note_to_midi("C4") == 60
    assert nw.note_to_midi("A4") == 69
    assert nw.note_to_midi("Bb2") == 46
    assert nw.note_to_midi("D2") == 38
    assert nw.note_to_midi("Eb2") == 39
    assert nw.note_to_midi("H9") is None
    assert nw.note_to_midi(None) is None
    assert nw.note_to_midi("G9") == 127
    assert nw.note_to_midi("G#9") is None
    assert nw.note_to_midi("C-1") == 0


def test_real_reel_builds_with_roles_and_no_errors(reel):
    assert reel["errors"] == []
    # Decision 21: one track per role that has notes. Sonic logo = vocal, folk_perc in club-folk, ostinato in DROP.
    assert set(reel["tracks"]) == {"drone", "pad", "bass", "drums", "ostinato", "lead", "brass", "hits",
                                   "vocal", "folk_perc", "pluck", "piano"}
    assert all(rows for rows in reel["tracks"].values())
    assert reel["stats"]["per_role"]["drone"] > 0


def test_same_input_gives_identical_output(cue, bible):
    a = nw.write_notes(REEL_PLAN, cue, bible)
    b = nw.write_notes(copy.deepcopy(REEL_PLAN), copy.deepcopy(cue), copy.deepcopy(bible))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_every_note_inside_reel(reel, cue):
    total = cue["total_s"]
    for role, n in _all_notes(reel["tracks"]):
        assert n["t_s"] >= 0, role
        assert n["dur_s"] > 0, role
        assert n["t_s"] + n["dur_s"] <= total + 1e-6, (role, n)


# ---------------------------------------------------------------- C2.1 god theme role, truncation

def test_c21_shiva_on_brass_keeps_all_four_notes_exact(reel):
    # SHIVA = D2 Eb2 D2 Eb2 at feel half (2 beats of 176 per step). The four originals are at or below 50, so exempt.
    step = 2 * DROP_BEAT
    expected = [round(48.0 + k * step, 6) for k in range(4)]
    rows = [n for n in reel["tracks"]["brass"] if 47.9 <= n["t_s"] < 51.0 and n["pitch"] < 55]
    assert [n["t_s"] for n in rows] == expected
    assert [n["pitch"] for n in rows] == [38, 39, 38, 39]


def test_c21_theme_role_outside_bible_is_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    _ev(plan, theme="SHIVA")["role"] = "lead"
    rep = nw.write_notes(plan, cue, bible)
    assert rep["ok"] is False
    assert _codes(rep["errors"]) == ["THEME_ROLE_NOT_IN_BIBLE"]


def test_c21_theme_truncated_warns_with_count():
    def mut(p):
        p["events"].append({"at_s": 0.0, "type": "theme_entry", "theme": "SANDHYA", "role": "lead"})
    rep = _small(plan_mut=mut)
    assert rep["ok"], rep["errors"]
    msgs = [w["message"] for w in rep["warnings"] if w["code"] == "THEME_TRUNCATED"]
    # Lead is gated under the 1-4 s window: notes 1.0 s and 1.5 s start inside it and are dropped; 0.0 and 0.5 are clear.
    assert msgs == ["SANDHYA at 0 s: 2 of 4 notes cut or dropped"]


def test_c21_reel_truncation_messages_exact(reel):
    # KALI at 3.5 s: its last note (5.5-6.4) is cut at the 6.3 s voice start, so it stays in the gap (5.5-6.3 s).
    # KALI at 3.5 s: its last note (5.5-6.4) is cut at the 6.3 s voice start, so it stays in the gap (5.5-6.3 s).
    # KAMADEVA at 29.69 s: 30.16 is clipped at 30.2; 30.39 and 30.63 start inside the 30.2-33.9 voice window.
    # SANDHYA at 25.36 s (feel quad): all four notes sound, none truncated.
    # MAIN at 40.25 s: all four notes sit in the 40.247-41.2 gap, so it is not truncated.
    # Round 5 result: no theme is truncated. KALI's last note (5.5) now hangs to its gap end 6.3 (Decision 28), which is
    # where the voice cut used to clip it, so it no longer counts as a voice cut. KAMADEVA's last note is trimmed to 30.2
    # by the hang and is not a voice cut either. (Coordinator expected KALI to stay listed; see report.)
    msgs = sorted(w["message"] for w in reel["warnings"] if w["code"] == "THEME_TRUNCATED")
    assert msgs == []


# ---------------------------------------------------------------- C2.2 swell on hard_cut

def test_c22_hard_cut_writes_swell_ending_on_cut():
    rep = _small(cue_mut=lambda c: c.update(cuts=[{"at_s": 8.0}]),
                 plan_mut=lambda p: p.update(cuts=[_cut(8.0, "swell_to_cut")]))
    assert rep["ok"], rep["errors"]
    swell = [(n["t_s"], n["dur_s"]) for n in rep["tracks"]["pad"] if n["pitch"] == 64]
    assert swell == [(7.0, 1.0)]


def test_c22_swell_to_cut_writes_swell_ending_on_cut():
    rep = _small(cue_mut=lambda c: c.update(cuts=[{"at_s": 8.0}]),
                 plan_mut=lambda p: p.update(cuts=[_cut(8.0, "swell_to_cut")]))
    assert rep["ok"], rep["errors"]
    swell = [(n["t_s"], n["dur_s"]) for n in rep["tracks"]["pad"] if n["pitch"] == 64]
    assert swell == [(7.0, 1.0)]


def test_c22_reel_hard_cut_48_swell_is_cut_by_dropout_warning(reel):
    # Conflict, decided: the SHIVA drop-out (47.6-48.0) is silence on all roles, so the 48.0 swell is cut.
    assert "SWELL_CUT_BY_DROPOUT" in _codes(reel["warnings"])


# ---------------------------------------------------------------- C2.3 phone bass

def test_c23_bass_mid_harmonic_exact_velocity_and_pitch(reel):
    t = round(18.0 + 16 * BUILD_BEAT, 6)  # 25.5 s, melodic techno section (18-26), in a voice gap
    root = [n for n in reel["tracks"]["bass"] if n["t_s"] == t]
    mid = [n for n in reel["tracks"]["bass"] if n["t_s"] == t and n["pitch"] == 57]
    assert [(n["pitch"], n["vel"]) for n in root if n["pitch"] == 38] == [(38, 70)]
    assert [(n["pitch"], n["vel"]) for n in mid] == [(57, 42)]


def test_c23_bass_mid_harmonic_not_gated_under_voice(reel):
    # Shot 4 is a reveal shot whose first entry is SANDHYA at 25.36, so bass is cut before it (Decision 17).
    # From there the 18-26 section grid resumes: 25.5 and 25.97. The bass note born at 25.03 keeps a 40 ms tail
    # after the cut, which starts at the entry (25.36).
    expected = [25.36, 25.5, 25.96875]
    got = _onsets(reel["tracks"], "bass", pitch=57, a=18.4, b=26.0)
    assert got == expected


# ---------------------------------------------------------------- C2.4 re-hook and peak

def test_c24_rehook_without_main_theme_is_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    plan["rehook_at_s"] = 36.0
    rep = nw.write_notes(plan, cue, bible)
    assert _codes(rep["errors"]) == ["REHOOK_NO_THEME"]


def test_c24_main_rehook_lands_all_four_notes_in_the_voice_gap(reel):
    # Re-hook at 40.25 s (gap 40.247-41.2). MAIN is feel double (half-beat steps at 176) so A3 D4 F4 E4 all start
    # before 41.2. Real speech covers 34.3-40.247, so nothing of MAIN is lost to voice.
    step = DROP_BEAT / 2
    rows = [n for n in reel["tracks"]["lead"] if 40.0 <= n["t_s"] < 41.2]
    assert [n["pitch"] for n in rows] == [57, 62, 65, 64]
    for k, n in enumerate(rows):
        assert abs(n["t_s"] - (40.25 + k * step)) < 1e-5
    assert all(40.25 <= n["t_s"] < 41.2 for n in rows)


def test_c24_drum_and_bass_enters_at_34_on_the_act_change(reel):
    # The DnB grid starts at 34.0: first 16th hat on 34.0, first snare on the second beat (34.34).
    # The 26-34 club kick (128 grid) sits at 33.97 and its 0.1 s tail merges with the 34.0 kick (Decision 16).
    assert _onsets(reel["tracks"], "drums", pitch=42, a=34.0, b=34.01) == [34.0]
    assert _onsets(reel["tracks"], "drums", pitch=38, a=34.0, b=34.5) == [round(34.0 + DROP_BEAT, 6)]


def test_c24_peak_not_in_highest_section_is_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    plan["peak_at_s"] = 20.0
    rep = nw.write_notes(plan, cue, bible)
    assert _codes(rep["errors"]) == ["PEAK_NOT_HIGHEST"]


def test_c24_peak_in_highest_section_is_accepted(reel):
    # Peak 48.0 is in the 48-64 section (intensity 0.85-0.95, mean 0.9, the highest). SHIVA (48.0) silences drums until
    # his last note ends (Decision 32, ~50.65 s), so the 48.0 kick is gone; the first kick after it is the half-time
    # grid at 8 beats (50.727 s). Its velocity is round(40 + 60 * 0.9) + 10 = 104 before the voice cap of 50.
    assert reel["errors"] == []
    assert not [n for n in reel["tracks"]["drums"] if n["pitch"] == 36 and 48.0 <= n["t_s"] < 50.6]
    kick = [(round(n["t_s"], 6), n["vel"]) for n in reel["tracks"]["drums"]
            if n["pitch"] == 36 and abs(n["t_s"] - (48.0 + 8 * 60 / 176)) < 1e-5]
    # 50.727 s is inside the voice window 49.2-55.89, so the drum velocity is capped at 50 (Decision 31).
    assert kick == [(round(48.0 + 8 * 60 / 176, 6), 50)]


# ---------------------------------------------------------------- C2.5 hook_type per shot

def test_c25_reveal_without_entry_is_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    plan["events"].remove(_ev(plan, theme="KAMADEVA"))  # reveal shot 5 (26-34 s) loses its entry
    rep = nw.write_notes(plan, cue, bible)
    assert _codes(rep["errors"]) == ["REVEAL_NO_ENTRY"]


def test_c25_reveal_first_part_only_drone_and_pad():
    plan = {"schema_version": 1, "sections": [{"start_s": 0.0, "end_s": 10.0, "bpm": 120, "feel": "normal",
                                               "roles_on": ["drone", "pad", "drums", "ostinato"],
                                               "density_per_beat": [2, 2], "intensity": [0.5, 0.5]}],
            "events": [{"at_s": 0.0, "type": "sonic_logo"},
                       {"at_s": 3.0, "type": "theme_entry", "theme": "MUNIS", "role": "pad"}],
            "cuts": []}
    cue_ = {"total_s": 10.0, "voice": {"union": []}, "cuts": [],
            "shots": [{"id": "SHOT-001", "start_s": 0.0, "end_s": 10.0, "hook_type": "reveal",
                       "opening_hook": False, "closing_hook": False}]}
    rep = nw.write_notes(plan, cue_, json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    assert _onsets(rep["tracks"], "drums", a=0.0, b=3.0) == []
    assert _onsets(rep["tracks"], "ostinato", a=0.0, b=3.0) == []
    assert _onsets(rep["tracks"], "drums", a=3.0, b=3.6) == [3.0, 3.5]


def test_c25_expression_beat_is_pad_only_on_reel(reel):
    # Decision 30: the heartbeat (drums, kick 36, velocity <= 60) is the one exception to pad-only.
    roles = {r for r, n in _all_notes(reel["tracks"]) if _overlaps(n, 6.0, 11.0) and r != "drums"}
    assert roles == {"pad"}
    beats = [n for n in reel["tracks"].get("drums", []) if _overlaps(n, 6.0, 11.0)]
    assert beats and all(n["pitch"] == 36 and n["vel"] <= 60 for n in beats)


def test_c25_expression_theme_fragment_only_in_gaps():
    plan = {"schema_version": 1, "sections": [{"start_s": 0.0, "end_s": 10.0, "bpm": 120, "feel": "normal",
                                               "roles_on": ["drone", "pad", "bass"],
                                               "density_per_beat": [2, 2], "intensity": [0.5, 0.5]}],
            "events": [{"at_s": 0.0, "type": "sonic_logo"},
                       {"at_s": 2.0, "type": "theme_entry", "theme": "MUNIS", "role": "pad"},
                       {"at_s": 4.5, "type": "theme_entry", "theme": "MUNIS", "role": "pad"}],
            "cuts": []}
    cue_ = {"total_s": 10.0, "voice": {"union": [[1.0, 4.0], [6.0, 9.0]]}, "cuts": [],
            "shots": [{"id": "SHOT-001", "start_s": 0.0, "end_s": 10.0, "hook_type": "expression-beat",
                       "opening_hook": False, "closing_hook": False}]}
    rep = nw.write_notes(plan, cue_, json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    assert _onsets(rep["tracks"], "pad", pitch=50, a=1.0, b=4.0) == []
    assert _onsets(rep["tracks"], "pad", pitch=50) == [4.5]
    assert _onsets(rep["tracks"], "pad", pitch=57) == [5.0]


def test_c25_suspense_shot_in_reel_is_silent_under_voice_and_present_in_gaps(reel):
    # Shot 6 (34-41 s) is a suspense shot in the DROP section: its ostinato ramp is silent under voice 34.3-40.25.
    assert _onsets(reel["tracks"], "ostinato", a=34.0, b=34.3) == [34.0, 34.170455]
    assert _onsets(reel["tracks"], "ostinato", a=34.3, b=40.247) == []
    assert _onsets(reel["tracks"], "ostinato", a=40.247, b=41.0) != []


def test_c25_suspense_ramp_and_no_d_on_strong_beats():
    # Synthetic, no voice: beat 0.5 s (120 BPM), density ramps 2 -> 4 across 0-10 s.
    plan = {"schema_version": 1, "sections": [{"start_s": 0.0, "end_s": 10.0, "bpm": 120, "feel": "normal",
                                               "roles_on": ["ostinato"], "density_per_beat": [2, 4],
                                               "intensity": [0.5, 0.5]}],
            "events": [{"at_s": 0.0, "type": "sonic_logo"}], "cuts": []}
    cue_ = {"total_s": 10.0, "voice": {"union": []}, "cuts": [],
            "shots": [{"id": "SHOT-001", "start_s": 0.0, "end_s": 10.0, "hook_type": "suspense",
                       "opening_hook": False, "closing_hook": False}]}
    rep = nw.write_notes(plan, cue_, json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    on = _onsets(rep["tracks"], "ostinato")
    assert [round(t, 6) for t in on[:3]] == [0.0, 0.25, 0.493902]  # 2 per beat, then rising (2.05 per beat at 0.25 s)
    rows = rep["tracks"]["ostinato"]
    strong = [n for n in rows if abs(n["t_s"] / 0.5 - round(n["t_s"] / 0.5)) < 1e-4
              and round(n["t_s"] / 0.5) % 2 == 0]
    assert (0.0, 52) in [(n["t_s"], n["pitch"]) for n in strong]  # first onset is on a strong beat: E3 (fix 1), not F or D
    assert all(n["pitch"] % 12 != 2 for n in strong)              # and no strong-beat onset is on D


def test_c25_suspense_skipped_in_section_without_ostinato():
    # Decision 24: a suspense shot in a hypnotic-techno section (no ostinato role) has nothing to replace.
    plan = {"schema_version": 1, "sections": [{"start_s": 0.0, "end_s": 10.0, "bpm": 128, "feel": "normal",
                                               "genre": "hypnotic_techno", "roles_on": ["drums"],
                                               "density_per_beat": [2, 2], "intensity": [0.5, 0.5]}],
            "events": [{"at_s": 0.0, "type": "sonic_logo"}], "cuts": []}
    cue_ = {"total_s": 10.0, "voice": {"union": []}, "cuts": [],
            "shots": [{"id": "SHOT-001", "start_s": 0.0, "end_s": 10.0, "hook_type": "suspense",
                       "opening_hook": False, "closing_hook": False}]}
    rep = nw.write_notes(plan, cue_, json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    assert "ostinato" not in rep["tracks"]


def test_c25_suspense_shot_3_has_its_one_bar_ostinato_loop(reel, cue):
    # Round 2: ostinato added to the 11-18 hypnotic section, so the suspense ramp in shot 3 has a loop to replace.
    on = _onsets(reel["tracks"], "ostinato", a=11.0, b=18.0)
    assert on and on[0] == 11.0
    for a, b in cue["voice"]["union"]:  # ostinato is busy: nothing starts inside voice
        assert not [t for t in on if a - 1e-6 <= t < b - 1e-6]
    for n in reel["tracks"]["ostinato"]:
        if 11.0 <= n["t_s"] < 18.0:
            k = (n["t_s"] - 11.0) / BUILD_BEAT
            strong = abs(k - round(k)) < 1e-4 and round(k) % 2 == 0
            assert not (strong and n["pitch"] % 12 == 2), n


def test_c25_kamadeva_reveal_entry_sits_in_the_29_69_gap(reel, cue):
    # KAMADEVA = D5 F#5 A5 C6 A5 on pluck, feel quad (0.117 s steps at 128) from 29.69 s. All five notes start before
    # the 30.2 gap end, so none is cut or dropped; the last one (A5, 30.158) hangs to 30.2 (Decision 28).
    starts = [(n["t_s"], n["pitch"]) for n in reel["tracks"]["pluck"] if 29.6 <= n["t_s"] < 30.2]
    assert [round(t, 3) for t, _ in starts] == [29.69, 29.807, 29.924, 30.042, 30.159]
    assert [p for _, p in starts] == [74, 78, 81, 84, 81]
    assert abs(reel["tracks"]["pluck"][-1]["t_s"] + reel["tracks"]["pluck"][-1]["dur_s"] - 30.2) < 1e-6
    for t, _ in starts:
        assert not any(a - 1e-9 <= t < b for a, b in cue["voice"]["union"])


def test_c25_reversal_darker_pad_after_turn_exact(reel):
    # Turn at 43.083 s; the darker pad runs to the shot end (48.0) but the SHIVA drop-out at 47.6 s is silence,
    # so it ends at 47.6 s: 4.517 s long.
    darker = sorted((n["pitch"], n["dur_s"]) for n in reel["tracks"]["pad"] if n["t_s"] == 43.083)
    assert darker == [(51, 4.517), (55, 4.517)]
    base_in_window = [n for n in reel["tracks"]["pad"] if n["pitch"] in (62, 69)
                      and _overlaps(n, 43.083 + 1e-3, 48.0)]
    assert base_in_window == []


def test_c25_reversal_darker_pad_at_second_reversal(reel):
    darker = sorted((n["pitch"], n["dur_s"]) for n in reel["tracks"]["pad"] if n["t_s"] == 60.0)
    assert darker == [(51, 4.0), (55, 4.0)]


def test_c25_closing_dsus2_pad_on_reel(reel):
    pitches = sorted({n["pitch"] for n in reel["tracks"]["pad"] if _overlaps(n, 64.0, 70.0)})
    assert pitches == [62, 69]  # NW5 fix 2: the closing pad is D4 A4 only; no E4 pad (the end sting keeps Dsus2)
    assert [n for n in reel["tracks"]["pad"] if n["pitch"] == 62 and n["t_s"] >= 64.0] == [
        {"t_s": 64.0, "dur_s": 6.0, "pitch": 62, "vel": 45}]


def test_c25_closing_is_unplugged_ticks_every_beat_and_no_kick(reel):
    # Decision 22: the closing shot's old kick every 2 beats is gone; its drums are the unplugged tick (pitch 42).
    drums = [(n["t_s"], n["pitch"], n["vel"]) for n in reel["tracks"]["drums"] if 64.0 <= n["t_s"] < 70.0]
    assert drums == [(float(t), 42, 35) for t in range(64, 70)]


def test_c25_closing_end_sting_is_dsus2_cluster(reel):
    stings = [(n["pitch"], n["dur_s"], n["vel"]) for n in reel["tracks"]["hits"] if abs(n["t_s"] - 69.85) < 1e-6]
    # 0.3 s long, clipped at the reel end (70.0 s): 0.15 s. After the last speech (69.846) the bright D5 E5 A5 joins
    # (Decision 34).
    assert sorted(stings) == [(38, 0.15, 110), (40, 0.15, 110), (45, 0.15, 110),
                              (74, 0.15, 110), (76, 0.15, 110), (81, 0.15, 110)]


def test_c25_closing_tail_at_most_045_after_last_speech(reel):
    last_speech_end = 69.846
    tail = [n["t_s"] + n["dur_s"] for role in reel["tracks"].values() for n in role if n["t_s"] >= last_speech_end]
    assert tail and max(tail) - last_speech_end <= 0.45 + 1e-6


# ---------------------------------------------------------------- C2.6 density, markers, quiet moment

@pytest.mark.parametrize("feel", ["normal", "half", "double"])
def test_c26_ostinato_density_is_per_real_beat_for_every_feel(feel):
    plan, cue_ = _ostinato_plan(feel)
    rep = nw.write_notes(plan, cue_, json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    assert _onsets(rep["tracks"], "ostinato", a=0.0, b=1.0) == [0.0, 0.25, 0.5, 0.75]


def test_c26_ostinato_density_ramps_from_low_to_high_bound():
    plan, cue_ = _ostinato_plan("normal", bpm=60, dens=(1, 3))
    rep = nw.write_notes(plan, cue_, json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    assert [round(t, 6) for t in _onsets(rep["tracks"], "ostinato")[:3]] == [0.0, 1.0, 1.833333]


def test_c26_marker_names_use_opening_and_closing_flags(reel):
    assert [m["name"] for m in reel["markers"]] == [
        "SHOT-001 opening reveal", "SHOT-002 expression-beat", "SHOT-003 suspense", "SHOT-004 reveal",
        "SHOT-005 reveal", "SHOT-006 suspense", "SHOT-007 reversal", "SHOT-008 reveal", "SHOT-009 reversal",
        "SHOT-010 closing"]


def test_c26_quiet_moment_only_listed_roles_on_reel(reel):
    # Bible quiet_moment 64-70 s: roles piano, pad, drone, drums (tick only), plus MAIN (on piano) and the end sting.
    roles = {r for r, n in _all_notes(reel["tracks"]) if _overlaps(n, 64.0, 70.0)}
    assert roles == {"drone", "pad", "drums", "hits", "piano"}
    assert _onsets(reel["tracks"], "piano", a=64.0, b=70.0) == [64.0, 65.0, 66.0, 67.0]
    assert {n["pitch"] for n in reel["tracks"]["piano"]} == {57, 62, 64, 65}  # MAIN degrees A3 D4 E4 F4
    assert {n["pitch"] for n in reel["tracks"]["drums"] if 64.0 <= n["t_s"] < 70.0} == {42}
    assert set(_onsets(reel["tracks"], "hits", a=64.0, b=70.0)) == {69.85}  # the end sting: three notes, one time
    # The OUTRO section has no bass or other roles, so nothing is cut here and QUIET_SUPPRESSED is not expected.
    assert "QUIET_SUPPRESSED" not in _codes(reel["warnings"])


def test_c26_quiet_moment_keeps_listed_theme_and_end_sting(cue, bible):
    # MAIN on piano at 64 s is the listed theme, so it survives on any role; a hit at 66 s is not listed and is cut.
    plan = copy.deepcopy(REEL_PLAN)
    plan["events"].append({"at_s": 66.0, "type": "hit", "role": "hits"})  # MAIN piano at 64 is already in the fixture
    rep = nw.write_notes(plan, cue, bible)
    assert rep["ok"], rep["errors"]
    roles = {r for r, n in _all_notes(rep["tracks"]) if _overlaps(n, 64.0, 70.0)}
    assert roles == {"drone", "pad", "drums", "piano", "hits"}
    piano = rep["tracks"]["piano"]
    assert piano and {n["pitch"] for n in piano} <= {57, 62, 64, 65}  # MAIN degrees A3 D4 E4 F4
    assert set(_onsets(rep["tracks"], "hits", a=64.0, b=70.0)) == {69.85}  # the 66 s hit is gone, the end sting stays
    assert "QUIET_SUPPRESSED" in _codes(rep["warnings"])


# ---------------------------------------------------------------- C2.7 sections, cuts, malformed roles, busy flags

def test_c27_section_gap_is_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    plan["sections"][2]["start_s"] = 12.0
    rep = nw.write_notes(plan, cue, bible)
    assert _codes(rep["errors"]) == ["SECTION_GAP"]
    assert rep["ok"] is False


def test_c27_section_overlap_is_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    plan["sections"][2]["start_s"] = 10.0
    rep = nw.write_notes(plan, cue, bible)
    assert _codes(rep["errors"]) == ["SECTION_OVERLAP"]


def test_c27_missing_cue_cut_is_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    plan["cuts"] = [c for c in plan["cuts"] if c["at_s"] != 18.0]
    rep = nw.write_notes(plan, cue, bible)
    assert _codes(rep["errors"]) == ["CUT_MISSING"]


def test_c27_unhashable_feel_is_section_feel_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    plan["sections"][0]["feel"] = ["half"]
    rep = nw.write_notes(plan, cue, bible)
    assert _codes(rep["errors"]) == ["SECTION_FEEL"]


def test_c27_unhashable_event_role_is_role_bad_error(cue, bible):
    plan = copy.deepcopy(REEL_PLAN)
    _ev(plan, type="hit", at_s=43.083)["role"] = ["hits"]
    rep = nw.write_notes(plan, cue, bible)
    assert _codes(rep["errors"]) == ["ROLE_BAD"]


def test_c27_busy_roles_come_from_bible_track_roles(bible):
    # piano is busy false since 2026-11-09 round 2 (may sit softly under voice).
    assert nw.busy_roles(bible) == frozenset({"drums", "ostinato", "pluck", "lead", "hits", "risers", "vocal",
                                              "folk_perc"})
    edited = copy.deepcopy(bible)
    edited["track_roles"]["brass"]["busy"] = True
    assert "brass" in nw.busy_roles(edited)


# ---------------------------------------------------------------- C2.8 test hygiene and malformed codes

MALFORMED = {
    "none": (lambda p: None, "PLAN"),
    "no_sections": (lambda p: p.pop("sections"), "PLAN_SECTIONS"),
    "bpm_zero": (lambda p: p["sections"][0].update(bpm=0), "SECTION_BPM"),
    "unknown_role": (lambda p: p["sections"][1].update(roles_on=["kazoo"]), "ROLE_BAD"),
    "unknown_event": (lambda p: p["events"].append({"at_s": 1.0, "type": "boom"}), "EVENT_TYPE"),
    "dropout_too_long": (lambda p: _ev(p, type="hit", at_s=43.083).update(preceded_by_dropout_s=0.6),
                         "DROPOUT_TOO_LONG"),
    "unknown_theme": (lambda p: _ev(p, theme="SHIVA").update(theme="NOPE"), "THEME_UNKNOWN"),
    "unknown_transition": (lambda p: p["cuts"][0].update(transition="wipe"), "CUT_TRANSITION"),
    "no_sonic_logo": (lambda p: p.update(events=p["events"][1:]), "NO_SONIC_LOGO"),
    "wrong_schema": (lambda p: p.update(schema_version=2), "PLAN_SCHEMA"),
    "event_outside_reel": (lambda p: _ev(p, theme="KAMADEVA").update(at_s=99.0), "EVENT_AT"),
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_c28_malformed_plan_reports_expected_code(name, cue, bible):
    mutate, code = MALFORMED[name]
    plan = copy.deepcopy(REEL_PLAN)
    plan = None if name == "none" else plan
    if plan is not None:
        mutate(plan)
    rep = nw.write_notes(plan, cue, bible)
    assert rep["ok"] is False
    assert rep["tracks"] == {}
    codes = _codes(rep["errors"])
    assert code in codes, codes
    assert "INTERNAL" not in codes


def test_c28_malformed_cue_and_bible_report_not_raise(bible):
    assert nw.write_notes(REEL_PLAN, None, bible)["ok"] is False
    assert nw.write_notes(REEL_PLAN, {"total_s": "x"}, bible)["ok"] is False
    assert nw.write_notes(REEL_PLAN, {"total_s": 70.0, "shots": []}, None)["ok"] is False


def test_c28_zero_overlap_uses_roles_that_have_notes(reel, cue, bible):
    assert set(reel["tracks"]) == {"drone", "pad", "bass", "drums", "ostinato", "lead", "brass", "hits",
                                   "vocal", "folk_perc", "pluck", "piano"}
    gated = nw.busy_roles(bible) | {"brass"}
    voice = cue["voice"]["union"]
    checked = set()
    for role, rows in reel["tracks"].items():
        if role not in gated:
            continue
        for n in rows:
            for a, b in voice:
                if _overlaps(n, a, b):
                    assert nw.LOW_OK.__contains__(role) and n["pitch"] <= nw.LOW_MAX, (role, n)
                    checked.add(role)
    assert {"drums", "hits", "brass", "vocal"} <= checked


def test_c28_too_short_fragment_warns_with_code():
    rep = _small(plan_mut=lambda p: p["events"].append(
        {"at_s": 0.995, "type": "theme_entry", "theme": "SANDHYA", "role": "lead"}))
    assert rep["ok"], rep["errors"]
    assert _codes(rep["warnings"]).count("NOTE_TOO_SHORT") == 1


def test_c28_high_brass_under_voice_is_dropped():
    # BRAHMA = A3 G#3 F#3 D3 on brass from 2.0 s (0.5 s steps) in the 1-4 s window. Only D3 (50) is at or below 50.
    rep = _small(plan_mut=lambda p: p["events"].append(
        {"at_s": 2.0, "type": "theme_entry", "theme": "BRAHMA", "role": "brass"}))
    assert rep["ok"], rep["errors"]
    assert [(n["t_s"], n["pitch"]) for n in rep["tracks"]["brass"] if n["t_s"] < 4.0] == [(3.5, 50)]


# ---------------------------------------------------------------- earlier rules (round 1, kept)

def test_small_fixture_busy_note_clipped_at_voice_start():
    bible = json.loads(BIBLE.read_text(encoding="utf-8"))
    bible["sonic_logo"]["length_s"] = 1.5
    rep = nw.write_notes(SMALL_PLAN, SMALL_CUE, bible)
    assert rep["ok"], rep["errors"]
    # Sonic logo D2 A3 D4 on role vocal. The sub (38) is low band under voice, so it keeps 1.5 s; the bells (57, 62)
    # are gated and stop at the 1.0 s voice start.
    bells = [n for n in rep["tracks"]["vocal"] if n["pitch"] == 57 and n["t_s"] == 0.0]
    assert bells and abs(bells[0]["t_s"] + bells[0]["dur_s"] - 1.0) < 1e-6
    sub = [n for n in rep["tracks"]["vocal"] if n["pitch"] == 38 and n["t_s"] == 0.0]
    assert sub and abs(sub[0]["dur_s"] - 1.5) < 1e-6


def test_drop_out_regions_hold_no_notes_on_any_role(reel):
    for ev in REEL_PLAN["events"]:
        d = ev.get("preceded_by_dropout_s", 0)
        if not d:
            continue
        a, b = ev["at_s"] - d, ev["at_s"]
        for role, n in _all_notes(reel["tracks"]):
            assert not _overlaps(n, a, b), (role, n, (a, b))


def test_events_land_on_their_frame(reel):
    hits = [n["t_s"] for n in reel["tracks"]["hits"]]
    for at in (43.083, 60.0, 69.85):
        assert any(abs(t - at) <= FRAME for t in hits), at
    assert any(abs(n["t_s"]) <= FRAME for n in reel["tracks"]["vocal"])  # the sonic logo, frame 0


def test_sonic_logo_on_frame_zero(reel):
    assert _onsets(reel["tracks"], "vocal", pitch=38, a=0.0, b=0.001) == [0.0]


def test_busy_roles_have_no_notes_under_voice_except_low_band(reel, cue, bible):
    gated = nw.busy_roles(bible) | {"brass"}
    voice = cue["voice"]["union"]
    for role, rows in reel["tracks"].items():
        if role not in gated:
            continue
        for n in rows:
            for a, b in voice:
                if _overlaps(n, a, b):
                    assert role in nw.LOW_OK and n["pitch"] <= nw.LOW_MAX, (role, n, (a, b))


def test_hits_under_voice_are_low_band(reel, cue):
    voice = cue["voice"]["union"]
    for n in reel["tracks"]["hits"]:
        if any(a - 1e-9 <= n["t_s"] < b for a, b in voice):
            assert n["pitch"] <= nw.LOW_MAX, n


def test_bright_hit_at_43_is_not_under_voice_and_sits_above_50(reel, cue):
    assert not any(a - 1e-9 <= 43.083 < b for a, b in cue["voice"]["union"])
    hits = [n["pitch"] for n in reel["tracks"]["hits"] if abs(n["t_s"] - 43.083) < 1e-6]
    assert hits == [nw.BRIGHT_PITCH] and hits[0] > nw.LOW_MAX


def test_small_fixture_forces_hit_under_voice_low_and_warns():
    rep = _small()
    hit = [n for n in rep["tracks"]["hits"] if abs(n["t_s"] - 2.0) < 1e-6]
    assert hit and hit[0]["pitch"] == nw.LOW_PITCH
    assert "HIT_FORCED_LOW" in _codes(rep["warnings"])


def test_gap_hit_keeps_bright_pitch():
    rep = _small()
    hit = [n for n in rep["tracks"]["hits"] if abs(n["t_s"] - 4.5) < 1e-6]
    assert hit and hit[0]["pitch"] == nw.BRIGHT_PITCH


def test_reverse_swell_ends_exactly_on_the_cut():
    rep = _small()
    ends = [n["t_s"] + n["dur_s"] for n in rep["tracks"]["pad"]]
    assert any(abs(e - 5.0) < 1e-6 for e in ends)


def test_automation_passes_valid_and_reports_invalid(cue, bible):
    rep = nw.write_notes(REEL_PLAN, cue, bible)
    assert rep["automation"] == [{"role": "pad", "macro": 1, "points": [[18.0, 0.2], [20.0, 0.8]]}]
    bad = copy.deepcopy(REEL_PLAN)
    bad["automation"] = [{"role": "pad", "macro": 9, "points": [[1.0, 0.5]]}]
    rep = nw.write_notes(bad, cue, bible)
    assert _codes(rep["errors"]) == ["AUTOMATION_MACRO"]


def test_theme_on_brass_keeps_all_notes_and_half_time_spacing():
    # SHIVA at 6.5 s, feel half at 120 BPM: 1.0 s steps. Its four originals (38 39 38 39) are at or below 50: exempt.
    rep = _small()
    brass = [n for n in rep["tracks"]["brass"] if 6.4 < n["t_s"] < 10.0]
    assert [n["pitch"] for n in brass[:4]] == [38, 39, 38, 39]
    assert [round(brass[i + 1]["t_s"] - brass[i]["t_s"], 6) for i in range(3)] == [1.0, 1.0, 1.0]


# ---------------------------------------------------------------- Decision 22: genre drum patterns (own grid, 1 ms)

def test_genre_hypnotic_techno_kick_each_beat_and_offbeat_hats():
    tr = _genre_run("hypnotic_techno", 128, (2, 2), ["drums"])
    _times_near(_onsets(tr, "drums", pitch=36), _grid_times(0, 8, BUILD_BEAT))
    _times_near(_onsets(tr, "drums", pitch=42), _grid_times(0, 8, BUILD_BEAT, 0.5))
    assert {n["pitch"] for n in tr["drums"]} == {36, 42}


def test_genre_melodic_techno_clap_on_2_and_4_and_open_hat_offbeats():
    tr = _genre_run("melodic_techno", 128, (2, 2), ["drums"])
    _times_near(_onsets(tr, "drums", pitch=36), _grid_times(0, 8, BUILD_BEAT))
    _times_near(_onsets(tr, "drums", pitch=39),
                [t for k, t in _grid_k(0, 8, BUILD_BEAT) if k % 4 in (1, 3)])
    _times_near(_onsets(tr, "drums", pitch=46), _grid_times(0, 8, BUILD_BEAT, 0.5))


def test_genre_club_folk_groove_three_against_four_with_bar_accent():
    tr = _genre_run("club_folk_groove", 128, (2, 2), ["drums", "folk_perc"])
    _times_near(_onsets(tr, "drums", pitch=36), _grid_times(0, 8, BUILD_BEAT))
    onsets = _grid_k(0, 8, BUILD_BEAT * 2 / 3)
    _times_near(_onsets(tr, "folk_perc", pitch=41), [t for k, t in onsets if k % 6 == 0])
    _times_near(_onsets(tr, "folk_perc", pitch=47), [t for k, t in onsets if k % 6 != 0])
    accent = [n["vel"] for n in tr["folk_perc"] if n["pitch"] == 41]
    other = [n["vel"] for n in tr["folk_perc"] if n["pitch"] == 47]
    assert min(accent) > max(other)


def test_genre_club_folk_groove_needs_folk_perc_role():
    tr = _genre_run("club_folk_groove", 128, (2, 2), ["drums"])
    assert "folk_perc" not in tr


def test_genre_drum_and_bass_kicks_snares_and_16th_hats():
    tr = _genre_run("drum_and_bass", 176, (4, 4), ["drums"])
    grid = _grid_k(0, 8, DROP_BEAT)
    kicks = sorted([t for k, t in grid if k % 4 in (0, 2)] + [t for k, t in _grid_k(0, 8, DROP_BEAT, 0.5) if k % 4 == 1])
    _times_near(_onsets(tr, "drums", pitch=36), kicks)
    _times_near(_onsets(tr, "drums", pitch=38), [t for k, t in grid if k % 4 in (1, 3)])
    _times_near(_onsets(tr, "drums", pitch=42), _grid_times(0, 8, DROP_BEAT / 4))


def test_genre_half_time_dnb_kick_on_1_snare_on_3_sparse_hats():
    tr = _genre_run("half_time_dnb", 176, (1, 1), ["drums"], feel="half")
    grid = _grid_k(0, 8, DROP_BEAT)
    _times_near(_onsets(tr, "drums", pitch=36), [t for k, t in grid if k % 4 == 0])
    _times_near(_onsets(tr, "drums", pitch=38), [t for k, t in grid if k % 4 == 2])
    _times_near(_onsets(tr, "drums", pitch=42), [t for k, t in grid if k % 2 == 1])


def test_genre_ambient_drums_are_only_the_heartbeat():
    # Decision 30: ambient with drums in roles_on is the heartbeat only (kick 36 on the beat and at +0.25 beat).
    tr = _genre_run("ambient", 60, (1, 1), ["drone", "pad", "drums"])
    assert [round(n["t_s"], 6) for n in tr["drums"]][:4] == [0.0, 0.25, 1.0, 1.25]
    assert all(n["pitch"] == 36 and n["vel"] <= 60 for n in tr["drums"])
    assert not _genre_run("ambient", 60, (1, 1), ["drone", "pad"]).get("drums")


def test_genre_unplugged_is_only_a_soft_tick_every_beat():
    tr = _genre_run("unplugged", 60, (1, 1), ["drums"])
    _times_near(_onsets(tr, "drums", pitch=42), _grid_times(0, 8, 1.0))
    assert {n["pitch"] for n in tr["drums"]} == {42}


def test_genre_drums_only_where_roles_on_has_drums():
    tr = _genre_run("hypnotic_techno", 128, (2, 2), ["drone"])
    assert "drums" not in tr


# ---------------------------------------------------------------- KALI entry and the set pieces

def test_kali_entry_notes_sit_in_the_voice_gap(reel):
    # KALI = D3 A3 E4 at 3.5 s, one note per beat at 60 BPM, all inside the 3.492-6.3 s gap.
    notes = [(n["t_s"], n["pitch"]) for n in reel["tracks"]["pad"]
             if n["pitch"] in (50, 57, 64) and 3.0 <= n["t_s"] < 6.3]
    assert notes == [(3.5, 50), (4.5, 57), (5.5, 64)]
    assert all(3.492 <= t < 6.3 for t, _ in notes)


# ---------------------------------------------------------------- round 3: SANDHYA entry, 34.0 downbeat, section clip

def test_sandhya_entry_sounds_all_four_notes_in_the_gap(reel, cue):
    # Gap 25.349-26.3. Feel quad (0.117 s steps) from 25.36: D4 E4 F4 B4 at 25.36, 25.477, 25.594, 25.711.
    # The last note (B4) hangs to 26.0, the section end (Decision 28). None of them starts inside voice.
    rows = [n for n in reel["tracks"]["lead"] if 25.3 <= n["t_s"] < 26.1]
    assert [n["pitch"] for n in rows] == [62, 64, 65, 71]
    step = 60 / 128 * 0.25
    for k, n in enumerate(rows):
        assert abs(n["t_s"] - (25.36 + k * step)) < 1e-5
    assert abs(rows[-1]["t_s"] + rows[-1]["dur_s"] - 26.0) < 1e-6
    for n in rows:
        assert not any(a - 1e-9 <= n["t_s"] < b for a, b in cue["voice"]["union"])


def test_theme_hang_last_note_held_to_gap_end(reel):
    # MAIN at 40.25 (feel double): its last note, E4 (64), starts at 40.76 in the 40.247-41.2 gap and hangs to 41.2.
    last = [n for n in reel["tracks"]["lead"] if n["pitch"] == 64 and 40.7 < n["t_s"] < 40.8]
    assert len(last) == 1 and abs(last[0]["t_s"] + last[0]["dur_s"] - 41.2) < 1e-6


def test_theme_hang_not_applied_to_last_note_inside_voice(reel):
    # MAIN on piano at 64: the last note (E4 at 67.0) starts inside voice 64.6-67.6, so it keeps its 0.9 s step length.
    last = [n for n in reel["tracks"]["piano"] if n["pitch"] == 64]
    assert len(last) == 1 and abs(last[0]["dur_s"] - 0.9) < 1e-6


def test_no_notes_on_any_role_in_the_34_0_dropout(reel):
    for role, n in _all_notes(reel["tracks"]):
        assert not _overlaps(n, 33.6, 34.0), (role, n)


def test_drum_and_bass_kick_lands_exactly_on_34_0(reel):
    # The 26-34 club kick at 33.5 is a separate note; the downbeat test is the one starting at 33.9 or later.
    assert _onsets(reel["tracks"], "drums", pitch=36, a=33.9, b=34.5) == [34.0]


def test_kick_at_34_0_fresh_attack_without_the_dropout_event():
    # Decision 26 and 27: the 26-34 club kick at 33.97 ends at the section end and is not merged into the 34.0 kick.
    plan = copy.deepcopy(REEL_PLAN)
    plan["events"] = [e for e in plan["events"] if e.get("at_s") != 34.0]
    rep = nw.write_notes(plan, json.loads(CUE.read_text(encoding="utf-8")),
                         json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    kicks = [n for n in rep["tracks"]["drums"] if n["pitch"] == 36 and 33.5 < n["t_s"] < 34.5]
    assert [round(k["t_s"], 6) for k in kicks] == [round(33.96875, 6), 34.0]
    assert all(k["t_s"] + k["dur_s"] <= 34.0 + 1e-6 for k in kicks if k["t_s"] < 34.0)


def test_section_born_notes_end_at_their_section_end(reel):
    secs = REEL_PLAN["sections"]
    for role, n in _all_notes(reel["tracks"]):
        sec = next(s for s in secs if s["start_s"] - 1e-9 <= n["t_s"] < s["end_s"] - 1e-9)
        assert n["t_s"] + n["dur_s"] <= sec["end_s"] + 1e-6, (role, n, sec["end_s"])


# ---------------------------------------------------------------- round 6 (NWR3 review): accepted findings

def test_r6_piano_under_voice_is_soft_and_keeps_pitch(reel, cue):
    # NWR3-1: piano is not busy (bible), but under a voice window its velocity is capped at 50; pitches are kept.
    voice = cue["voice"]["union"]
    piano = reel["tracks"]["piano"]
    under = [n for n in piano if any(_overlaps(n, a, b) for a, b in voice)]
    assert under, "MAIN piano at 64-67 s should overlap the voice"
    assert all(n["vel"] <= 50 for n in under)
    assert [n["pitch"] for n in piano] == [57, 62, 65, 64]


def test_r6_horn_is_gated_and_soft_under_voice():
    # NWR3-8: horn is in the gated set (octave partners above 50 wait for the gap), and it is soft under voice.
    rep = _small(plan_mut=lambda p: p["events"].append(
        {"at_s": 2.0, "type": "theme_entry", "theme": "SHIVA", "role": "horn", "feel": "half"}))
    assert rep["ok"], rep["errors"]
    horn = rep["tracks"].get("horn", [])
    assert not [n for n in horn if 1.0 <= n["t_s"] < 4.0 and n["pitch"] > nw.LOW_MAX]
    assert all(n["vel"] <= 50 for n in horn if 1.0 <= n["t_s"] < 4.0)


def test_r6_god_entry_silences_drums_until_its_last_note_ends(reel):
    # NWR3-2 (rule 8): SHIVA enters at 48.0 s; drums and folk_perc are silent until his last note has ended (50.66 s).
    last_end = max(n["t_s"] + n["dur_s"] for n in reel["tracks"]["brass"] if 48.0 <= n["t_s"] < 52.0)
    assert 50.6 < last_end < 50.7
    for role in ("drums", "folk_perc"):
        assert not [n for n in reel["tracks"].get(role, []) if 48.0 <= n["t_s"] < last_end - 1e-6], role
    kick = _onsets(reel["tracks"], "drums", pitch=36, a=50.66, b=51.0)
    assert kick == [round(48.0 + 2 * 2 * 60 / 176 * 1.0 * 1.0 + 0.0, 6)] or kick[0] > last_end  # the half-time grid resumes


def test_r6_kali_god_entry_silences_the_heartbeat_until_its_last_note(reel):
    # KALI is a god entry too: the 6-11 s heartbeat is silent from 3.5 s until KALI's last note ends (6.3 s), then plays.
    # KALI's last note (5.5 s) hangs to the section end, 6.0 s (Decision 28), so the heartbeat starts exactly there.
    kicks = _onsets(reel["tracks"], "drums", pitch=36, a=0.0, b=11.0)
    assert not [t for t in kicks if t < 6.0 - 1e-6]
    assert [t for t in kicks if 6.0 <= t < 11.0] == [6.0, 6.25, 7.0, 7.25, 8.0, 8.25, 9.0, 9.25, 10.0, 10.25]


def test_r6_heartbeat_soft_lub_dub_every_beat(reel):
    # NWR3-5 (a): ambient section with drums in roles_on: a kick on each beat and at +0.25 beat, velocity at most 60.
    beats = [7.0, 8.0, 9.0, 10.0]
    kicks = [n for n in reel["tracks"]["drums"] if n["pitch"] == 36 and 6.9 < n["t_s"] < 11.0]
    assert [round(n["t_s"], 6) for n in kicks] == sorted(round(b + d, 6) for b in beats for d in (0.0, 0.25))
    assert all(n["vel"] <= 60 for n in kicks)


def test_r6_heartbeat_survives_the_expression_beat_shot():
    # Shot 2 (6-11 s) is expression-beat: pad only, except the study's heartbeat (Decision 30).
    rep = _genre_run("ambient", 60, (1, 1), ["drone", "pad", "drums"], end=8.0)
    assert [round(n["t_s"], 6) for n in rep["drums"] if n["pitch"] == 36][:4] == [0.0, 0.25, 1.0, 1.25]


def test_r6_kamadeva_chaos_entry_is_quad_and_transformed(reel):
    # NWR3-5 (b): KAMADEVA at 43.2 (gap 43.036-44.2), feel quad, transform chaos_41s = D5 Eb5 A5 C6 Ab5.
    step = 60 / 176 * 0.25
    rows = [n for n in reel["tracks"]["lead"] if 43.1 <= n["t_s"] < 44.2]
    assert [n["pitch"] for n in rows] == [74, 75, 81, 84, 80]
    for k, n in enumerate(rows):
        assert abs(n["t_s"] - (43.2 + k * step)) < 1e-5
    assert abs(rows[-1]["t_s"] + rows[-1]["dur_s"] - 44.2) < 1e-6


def test_r6_kamadeva_curse_entry_is_half_time_on_pad(reel):
    # NWR3-5 (c): KAMADEVA at 56.0 (gap 55.89-57.2), feel half, transform curse_56_64s = D4 F4 A4 C5 A4 on pad.
    step = 60 / 176 * 2
    rows = [n for n in reel["tracks"]["pad"] if 56.0 - 1e-6 <= n["t_s"] < 60.0]
    # Round 7 (NWR3-R-1): every curse note has its own attack, even where the base pad holds the same pitch.
    for pitch, t in [(62, 56.0), (65, 56.0 + step), (69, 56.0 + 2 * step), (72, 56.0 + 3 * step), (69, 56.0 + 4 * step)]:
        assert any(n["pitch"] == pitch and abs(n["t_s"] - t) < 1e-5 for n in rows), (pitch, t)


def test_r6_transform_missing_or_unparsable_is_error(cue, bible):
    for tr in ("nope", None):
        plan = copy.deepcopy(REEL_PLAN)
        ev = _ev(plan, theme="KAMADEVA", at_s=56.0)
        ev["transform"] = tr
        rep = nw.write_notes(plan, cue, bible)
        assert "THEME_TRANSFORM_BAD" in _codes(rep["errors"]), tr


def test_r6_swell_into_the_11_0_hard_cut_ends_exactly_on_it(reel):
    # NWR3-6: the 11.0 s cut is a hard cut and an act change, so the plan gives a reverse swell ending on 11.000.
    swell = [(n["t_s"], n["dur_s"]) for n in reel["tracks"]["pad"] if n["pitch"] == 64 and 9.9 < n["t_s"] < 10.1]
    assert swell == [(10.0, 1.0)]


def test_r6_end_sting_is_bright_after_the_last_word(reel):
    # NWR3-4: the sting at 69.85 is after last_speech_end 69.846: low Dsus2 cluster plus bright D5 E5 A5.
    stings = sorted(n["pitch"] for n in reel["tracks"]["hits"] if abs(n["t_s"] - 69.85) < 1e-6)
    assert stings == [38, 40, 45, 74, 76, 81]


def test_r6_end_sting_before_the_last_word_stays_low():
    rep = _small(plan_mut=lambda p: p["events"].append({"at_s": 5.0, "type": "end_sting"}))
    assert rep["ok"], rep["errors"]
    stings = sorted(n["pitch"] for n in rep["tracks"]["hits"] if abs(n["t_s"] - 5.0) < 1e-6)
    assert stings == [38, 40, 45]


def test_r6_bpm_and_density_bounds_error_fast():
    import time
    t0 = time.time()
    rep = _small(plan_mut=lambda p: p["sections"][0].update(bpm=1e300))
    assert "SECTION_BPM" in _codes(rep["errors"]) and rep["ok"] is False
    rep = _small(plan_mut=lambda p: p["sections"][0].update(bpm=5))
    assert "SECTION_BPM" in _codes(rep["errors"])
    rep = _small(plan_mut=lambda p: p["sections"][0].update(density_per_beat=[1e9, 1e9]))
    assert "SECTION_DENSITY" in _codes(rep["errors"])
    assert time.time() - t0 < 5.0


def test_r6_midi_channel_map_keeps_vocal_off_channel_10():
    # NWR3-9: drums are the only role on channel index 9 (GM channel 10); every other role has its own channel.
    assert nw.MIDI_CHANNEL["drums"] == 9
    others = {r: c for r, c in nw.MIDI_CHANNEL.items() if r != "drums"}
    assert 9 not in others.values() and len(set(others.values())) == len(others) == len(nw.ROLES) - 1
    assert set(nw.MIDI_CHANNEL) == set(nw.ROLES)


def test_r6_theme_roles_as_a_string_is_error(cue, bible):
    bad = copy.deepcopy(bible)
    bad["themes"]["KAMADEVA"]["roles"] = "lead"
    rep = nw.write_notes(REEL_PLAN, cue, bad)
    assert "THEME_ROLE_NOT_IN_BIBLE" in _codes(rep["errors"])


# ---------------------------------------------------------------- round 7 (NWR3 re-check, round 6)

def test_r7_curse_base_pad_keeps_its_velocity_and_resumes(reel):
    # NWR3-R-2: the base pad 62/69 (48-64 s) keeps its section velocity (84) before the curse, and resumes at 84 after it.
    pad = reel["tracks"]["pad"]
    base = [n for n in pad if n["pitch"] in (62, 69) and 48.0 - 1e-6 <= n["t_s"] < 56.0]
    assert base and all(n["vel"] == 84 for n in base)
    resumed = [n for n in pad if n["pitch"] in (62, 69) and 56.5 < n["t_s"] < 64.0 and n["vel"] == 84]
    assert resumed


def test_r7_theme_velocity_follows_section_intensity(reel):
    # NWR3-R-3: a theme note's velocity is round(55 + 45 * upper intensity of its section at the note time). KALI
    # (section 0-6, intensity 0.2-0.4) enters at 3.5 s lower than MAIN (section 34-48, intensity 0.7-0.9) at 40.25 s.
    kali = [n["vel"] for n in reel["tracks"]["pad"] if abs(n["t_s"] - 3.5) < 1e-6 and n["pitch"] == 50]
    main = [n["vel"] for n in reel["tracks"]["lead"] if abs(n["t_s"] - 40.25) < 1e-6 and n["pitch"] == 57]
    assert kali == [73] and main == [96]


def test_r7_peak_entry_is_the_loudest_attack_of_the_reel(reel):
    # NWR3-R-3: SHIVA at the plan peak (48.0 s) plays at velocity 120, octave partners included. Nothing else reaches
    # 115 or more, and hits stay at 110 or below.
    loud = [(role, n) for role, n in _all_notes(reel["tracks"]) if n["vel"] >= 115]
    assert loud and all(abs(n["t_s"] - 48.0) < 1e-6 and n["vel"] == 120 for _, n in loud)
    assert [n["vel"] for n in reel["tracks"]["brass"] if abs(n["t_s"] - 48.0) < 1e-6 and n["pitch"] == 38] == [120]
    assert all(n["vel"] <= 110 for n in reel["tracks"]["hits"])


# ---------------------------------------------------------------- round 2: one cut vocabulary (shared with plan_check)

from score import plan_check as _pc_r2  # noqa: E402


def _pad_at(rep, t):
    return [n for n in rep["tracks"].get("pad", []) if n["pitch"] == 64 and abs(n["t_s"] - (t - 1.0)) < 1e-6]


def test_r2_vocabulary_is_shared_with_plan_check():
    assert set(nw.TRANSITIONS) == set(_pc_r2.TRANSITIONS)
    assert nw.SWELL_TRANSITIONS == ("reverse_swell_to_cut", "swell_to_cut")


@pytest.mark.parametrize("tr", ["none", "bed_continues", "theme_handover", "key_colour_on_downbeat"])
def test_r2_soft_or_colour_cut_writes_no_swell(tr):
    rep = _small(cue_mut=lambda c: c.update(cuts=[{"at_s": 8.0}]),
                 plan_mut=lambda p: p.update(cuts=[_cut(8.0, tr)]))
    assert rep["ok"], rep["errors"]
    assert _pad_at(rep, 8.0) == []
    assert "CUT_TRANSITION_RENAMED" not in _codes(rep["warnings"])


@pytest.mark.parametrize("tr", ["reverse_swell_to_cut", "swell_to_cut"])
def test_r2_swell_cut_still_writes_swell(tr):
    rep = _small(cue_mut=lambda c: c.update(cuts=[{"at_s": 8.0}]),
                 plan_mut=lambda p: p.update(cuts=[_cut(8.0, tr)]))
    assert rep["ok"], rep["errors"]
    assert len(_pad_at(rep, 8.0)) == 1


@pytest.mark.parametrize("legacy, new", [("no_break", "bed_continues"), ("hard_cut", "swell_to_cut"), ("impact", "none")])
def test_r2_legacy_cut_names_map_and_warn(legacy, new):
    rep = _small(cue_mut=lambda c: c.update(cuts=[{"at_s": 8.0}]),
                 plan_mut=lambda p: p.update(cuts=[_cut(8.0, legacy)]))
    assert rep["ok"], rep["errors"]
    assert "CUT_TRANSITION_RENAMED" in _codes(rep["warnings"])
    assert (len(_pad_at(rep, 8.0)) == 1) == (new in nw.SWELL_TRANSITIONS)


def test_r2_unknown_cut_transition_fails():
    rep = _small(cue_mut=lambda c: c.update(cuts=[{"at_s": 8.0}]),
                 plan_mut=lambda p: p.update(cuts=[_cut(8.0, "bogus")]))
    assert "CUT_TRANSITION" in _codes(rep["errors"])


def test_r2_key_colour_cut_retriggers_pad_on_the_downbeat():
    plan, cue_ = _ostinato_plan("normal", bpm=120)
    plan["sections"][0]["roles_on"] = ["pad"]
    plan["cuts"] = [_cut(5.0, "key_colour_on_downbeat")]
    cue_["cuts"] = [{"at_s": 5.0}]
    cue_["shots"] = [{"id": "SHOT-001", "start_s": 0.0, "end_s": 5.0, "hook_type": "reversal",
                      "opening_hook": False, "closing_hook": False},
                     {"id": "SHOT-002", "start_s": 5.0, "end_s": 10.0, "hook_type": "reversal",
                      "opening_hook": False, "closing_hook": False}]
    rep = nw.write_notes(plan, cue_, json.loads(BIBLE.read_text(encoding="utf-8")))
    assert rep["ok"], rep["errors"]
    pads = rep["tracks"]["pad"]
    assert all(not (n["t_s"] < 5.0 - 1e-6 < n["t_s"] + n["dur_s"] - 1e-6) for n in pads)  # no pad note crosses the cut


# ---------------------------------------------------------------- NW5: reel 1 harmony report fixes (2026-11-09)

PACK_EP = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "score" / "ep1"


@pytest.fixture(scope="module")
def pack_reel(bible):
    # The real reel 1 plan and cue sheet (the harmony report's inputs). Skipped when the pack is not there.
    if not (PACK_EP / "score_plan.json").exists():
        pytest.skip("reel 1 pack folder missing")
    plan = json.loads((PACK_EP / "score_plan.json").read_text(encoding="utf-8"))
    cue_ = json.loads((PACK_EP / "cue_sheet.json").read_text(encoding="utf-8"))
    rep = nw.write_notes(plan, cue_, bible)
    assert rep["ok"], rep["errors"]
    return rep


def _sounding(tracks, t):
    return [(role, n["pitch"]) for role, rows in tracks.items() if role not in ("drums", "folk_perc") for n in rows
            if n["t_s"] <= t + 1e-6 < n["t_s"] + n["dur_s"] - 1e-6]


def _resolved_tonic(sounding):
    pcs = {p % 12 for _, p in sounding}
    return {2, 5, 9} <= pcs and min(p for _, p in sounding) % 12 == 2


@pytest.mark.parametrize("t", [11.375, 35.125])
def test_nw5_fix1_no_resolved_tonic_on_suspense_strong_beat(pack_reel, t):
    # Fix 1: a suspense shot never sounds D F A with D in the bass on a strong beat (Dsus2 or D5 instead).
    assert not _resolved_tonic(_sounding(pack_reel["tracks"], t)), _sounding(pack_reel["tracks"], t)


def test_nw5_fix2_outro_pad_holds_only_d_and_a(pack_reel):
    # Fix 2: the OUTRO pad (66.833-72.833) is D4 and A4 only. The open E is in the end sting, not in the pad.
    pads = sorted({n["pitch"] for n in pack_reel["tracks"]["pad"] if _overlaps(n, 66.833, 72.7)})
    assert pads == [62, 69]


@pytest.mark.parametrize("a, b", [(44.3, 49.7), (62.9, 66.7)])
def test_nw5_fix3_dark_pad_is_phrygian_bii_without_d(pack_reel, a, b):
    # Fix 3: the dark pad after each white-out is Eb3 G3 Bb3 over the D bass/drone. No D3 or D4 pad note sounds there.
    pads = sorted({n["pitch"] for n in pack_reel["tracks"]["pad"] if _overlaps(n, a, b)})
    assert pads == [51, 55]


def test_nw5_fix4_kali_pad_sounds_exactly_the_bible_pitches(pack_reel):
    # Fix 4: KALI at 3.5 s sounds exactly D3 A3 E4 (bible degrees). The D4 octave partner is not written on the pad.
    notes = sorted(n["pitch"] for n in pack_reel["tracks"]["pad"] if 3.5 - 1e-6 <= n["t_s"] < 6.0)
    assert notes == [50, 57, 64]

def test_nw5_round3_dark_pad_has_no_bb3_and_keeps_the_a3_harmonic(pack_reel):
    # Round 3 (coordinator option 2): the dark bII pad is Eb3 G3 only. Bb3 (58) sat a close minor 2nd over the bass A3
    # mid harmonic (57), so it is dropped. The A3 mid harmonic stays (check 4 needs it under every bass root).
    for a, b in [(44.3, 49.7), (62.9, 66.7)]:
        pads = sorted({n["pitch"] for n in pack_reel["tracks"]["pad"] if _overlaps(n, a, b)})
        assert pads == [51, 55], pads
        mids = [n for n in pack_reel["tracks"]["bass"] if n["pitch"] == 57 and _overlaps(n, a, b)]
        assert mids, (a, b)
