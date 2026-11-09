"""Tests for score/harmony_check.py. Small synthetic tracks for single rules, plus one smoke run on the real reel.

Each test states the rule it guards. The real-reel test is skipped when the pack folder is missing.
"""
import json
from pathlib import Path

import pytest

from score import harmony_check as hc
from score import note_writer as nw

ROOT = Path(__file__).resolve().parents[2]
BIBLE = ROOT / "stories" / "kalika_puran_bhag1" / "music_bible.json"
PACK = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "score" / "ep1"


def _note(t, dur, p, vel=80):
    return {"t_s": float(t), "dur_s": float(dur), "pitch": int(p), "vel": int(vel)}


def _plan(harmony="D minor", bpm=60, events=None, end=10.0):
    return {"schema_version": 1,
            "sections": [{"start_s": 0.0, "end_s": end, "act": "HOOK", "bpm": bpm, "feel": "normal",
                          "genre": "ambient", "harmony": harmony, "roles_on": ["pad"]}],
            "events": events or []}


def _cue(hook="reveal", closing=False):
    return {"total_s": 10.0, "voice": {"union": []}, "retention": {},
            "shots": [{"start_s": 0.0, "end_s": 10.0, "hook_type": hook, "closing_hook": closing}]}


def _flags(res, check, sub=None):
    return [f for f in res["flags"] if f["check"].startswith(check) and (sub is None or f["sub"] == sub)]


BIBLE_MIN = {"themes": {}}


def test_out_of_key_c_sharp_flagged_in_plain_minor():
    # rule 1: C# is not in D natural minor, and a plain D minor section adds no colour
    res = hc.check_tracks({"pad": [_note(1.0, 0.5, 61)]}, _plan("D minor"), _cue(), BIBLE_MIN)
    f = _flags(res, "1 scale")
    assert len(f) == 1 and f[0]["pitch"] == "C#4", f
    assert res["summary"]["1 scale"]["flagged"] == 1


def test_g_sharp_is_ok_inside_lydian_section():
    # rule 1: the Lydian colour adds G#, so the same note passes in a Lydian section
    tracks = {"pad": [_note(1.0, 0.5, 68)]}  # G#4
    assert not _flags(hc.check_tracks(tracks, _plan("D Lydian lift"), _cue(), BIBLE_MIN), "1 scale")
    assert _flags(hc.check_tracks(tracks, _plan("D minor"), _cue(), BIBLE_MIN), "1 scale")


def test_resolved_dm_on_strong_beat_in_suspense_is_flagged():
    # check 3c: D F A with D in the bass on a whole beat (60 bpm, so 2.0 s is strong) inside a suspense shot
    tracks = {"bass": [_note(2.0, 0.8, 38)],
              "pad": [_note(2.0, 0.8, 62), _note(2.0, 0.8, 65), _note(2.0, 0.8, 69)]}
    res = hc.check_tracks(tracks, _plan("D minor"), _cue(hook="suspense"), BIBLE_MIN)
    assert _flags(res, "3 chords", "c"), res["flags"]
    # control: the same chord off the beat (2.5 s) is not flagged
    tracks_off = {"bass": [_note(2.5, 0.8, 38)],
                  "pad": [_note(2.5, 0.8, 62), _note(2.5, 0.8, 65), _note(2.5, 0.8, 69)]}
    res2 = hc.check_tracks(tracks_off, _plan("D minor"), _cue(hook="suspense"), BIBLE_MIN)
    assert not _flags(res2, "3 chords", "c")


def test_dsus2_end_sting_passes_and_dm_end_sting_is_flagged():
    # check 3d: end sting must be D E A
    events = [{"type": "end_sting", "at_s": 9.0}]
    ok = {"hits": [_note(9.0, 0.3, 38), _note(9.0, 0.3, 40), _note(9.0, 0.3, 45),
                   _note(9.0, 0.3, 74), _note(9.0, 0.3, 76), _note(9.0, 0.3, 81)]}
    res = hc.check_tracks(ok, _plan(events=events), _cue(closing=True, hook="suspense"), BIBLE_MIN)
    assert not _flags(res, "3 chords", "d"), res["flags"]
    bad = {"hits": [_note(9.0, 0.3, 38), _note(9.0, 0.3, 41), _note(9.0, 0.3, 45)]}  # D F A
    res2 = hc.check_tracks(bad, _plan(events=events), _cue(closing=True, hook="suspense"), BIBLE_MIN)
    assert _flags(res2, "3 chords", "d")


BIBLE_KAMA = {"themes": {"KAMA": {"degrees": "D4 F4 A4", "roles": ["lead"]}}}


def test_theme_notes_match_bible_degrees_in_order():
    # check 2: D4 F4 A4 on the lead at the entry times, no flags when they match
    events = [{"type": "theme_entry", "at_s": 2.0, "theme": "KAMA", "role": "lead", "feel": "normal"}]
    good = {"lead": [_note(2.0, 0.9, 62), _note(3.0, 0.9, 65), _note(4.0, 0.9, 69)]}
    res = hc.check_tracks(good, _plan(events=events), _cue(), BIBLE_KAMA)
    assert not _flags(res, "2 themes"), res["flags"]
    assert res["themes"][0]["want"] == res["themes"][0]["got"] == "D4 F4 A4"
    # a missing middle note is flagged
    bad = {"lead": [_note(2.0, 0.9, 62), _note(4.0, 0.9, 69)]}
    res2 = hc.check_tracks(bad, _plan(events=events), _cue(), BIBLE_KAMA)
    assert _flags(res2, "2 themes", "missing")


def test_bass_root_needs_phone_mid_harmonic():
    # check 4: D2 needs A3 (root + 19) at the same onset
    res = hc.check_tracks({"bass": [_note(0.0, 0.8, 38)]}, _plan(), _cue(), BIBLE_MIN)
    assert _flags(res, "4 bass", "harmonic")
    res2 = hc.check_tracks({"bass": [_note(0.0, 0.8, 38), _note(0.0, 0.8, 57)]}, _plan(), _cue(), BIBLE_MIN)
    assert not _flags(res2, "4 bass")


def test_midi_round_trip_is_exact():
    # check 5: write_midi output read back with the test parser gives the same notes
    tracks = {"pad": [_note(0.0, 1.0, 62), _note(1.0, 0.5, 69)], "bass": [_note(0.0, 0.8, 38), _note(0.0, 0.8, 57)],
              "drums": [_note(0.5, 0.1, 36, 100)]}
    res = hc.check_tracks(tracks, _plan(), _cue(), BIBLE_MIN, markers=[{"t_s": 0.0, "name": "SHOT-001 reveal"}])
    assert res["midi"]["ok"], res["midi"]
    assert res["summary"]["5 midi"]["ok"] == 1


def test_real_reel_smoke():
    # the real reel: write_notes must be ok and the checker must run every check
    if not (PACK / "score_plan.json").exists():
        pytest.skip("reel pack not present")
    plan = json.loads((PACK / "score_plan.json").read_text(encoding="utf-8"))
    cue = json.loads((PACK / "cue_sheet.json").read_text(encoding="utf-8"))
    bible = json.loads(BIBLE.read_text(encoding="utf-8"))
    res = hc.check_harmony(plan, cue, bible)
    assert res["ok"], res["errors"]
    assert set(res["summary"]) == {"1 scale", "2 themes", "3 chords", "4 bass", "5 midi"}
    assert res["summary"]["5 midi"]["ok"] == 1
    assert res["summary"]["1 scale"]["flagged"] == 0
    assert hc.render_report(res).startswith("# ")

# ---------------------------------------------------------------- round 2 (coordinator triage, 2026-11-09)

BIBLE_KALI = {"themes": {"KALI": {"degrees": "D3 A3 E4", "roles": ["pad"]}}}


def test_pad_theme_entry_expects_no_octave_partner():
    # Item A: a pad entry sounds its bible pitches exactly (note_writer fix 4), so no octave partner is expected.
    events = [{"type": "theme_entry", "at_s": 2.0, "theme": "KALI", "role": "pad", "feel": "normal"}]
    tracks = {"pad": [_note(2.0, 0.9, 50), _note(3.0, 0.9, 57), _note(4.0, 0.9, 64)]}
    res = hc.check_tracks(tracks, _plan(events=events), _cue(), BIBLE_KALI)
    assert not _flags(res, "2 themes"), res["flags"]


def test_melody_note_under_resolved_tonic_is_not_a_chord_flag():
    # Item B: check 3c judges only the chord layers (drone, pad, bass, ostinato). A piano or lead note is not a chord.
    cue_s = _cue(hook="suspense")
    melody = {"drone": [_note(2.0, 0.8, 38)], "pad": [_note(2.0, 0.8, 62), _note(2.0, 0.8, 69)],
              "piano": [_note(2.0, 0.8, 65)]}
    assert not _flags(hc.check_tracks(melody, _plan("D minor"), cue_s, BIBLE_MIN), "3 chords", "c")
    # control: the full D F A held in the chord layers on the strong beat is still flagged
    chords = {"drone": [_note(2.0, 0.8, 38)], "pad": [_note(2.0, 0.8, 62), _note(2.0, 0.8, 65), _note(2.0, 0.8, 69)]}
    assert _flags(hc.check_tracks(chords, _plan("D minor"), cue_s, BIBLE_MIN), "3 chords", "c")


def test_phrygian_bii_pad_over_d_pedal_is_intended_colour():
    # Item C: in a Phrygian section, Eb3 over a D2 pedal (13 semitones: octave plus minor 2nd) is not flagged.
    # Close minor 2nds stay flagged: Bb3 over A3 is 1 semitone apart and is flagged in the same section.
    phry = _plan("D Phrygian, rolling reese bass")
    pedal = {"bass": [_note(1.0, 2.0, 38)], "pad": [_note(1.0, 2.0, 51), _note(1.0, 2.0, 55), _note(1.0, 2.0, 58)]}
    assert not _flags(hc.check_tracks(pedal, phry, _cue(), BIBLE_MIN), "3 chords")
    # control: the same pad over the same pedal in a plain D minor section is flagged (3a and 3b)
    assert _flags(hc.check_tracks(pedal, _plan("D minor"), _cue(), BIBLE_MIN), "3 chords")
    close = {"bass": [_note(1.0, 2.0, 57)], "pad": [_note(1.0, 2.0, 58)]}
    assert _flags(hc.check_tracks(close, phry, _cue(), BIBLE_MIN), "3 chords", "a")
