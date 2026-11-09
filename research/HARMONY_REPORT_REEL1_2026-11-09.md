# Harmony report: Kalika reel 1, 2026-11-09

Inputs: plan `stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/score/ep1/score_plan.json`, cue `stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/score/ep1/cue_sheet.json`, bible `stories/kalika_puran_bhag1/music_bible.json`.

Checker: `score/harmony_check.py` (pure; no model calls). Home key D minor (music_bible.json). Notes come from `score/note_writer.py` write_notes, unchanged.

## Summary

| Check | OK | Flagged | Unit |
|---|---:|---:|---|
| 1 scale | 288 | 0 | non-drum notes |
| 2 themes | 34 | 4 | theme notes found (34); flagged = missing or bad theme notes/entries |
| 3 chords | 142 | 6 | onsets (147); flagged = flag records |
| 4 bass | 94 | 0 | bass roots with harmonic |
| 5 midi | 1 | 0 | round trip, 573 notes read back |

Notes read: 573. write_notes ok: True. write_notes warnings: 7.

## Sections

### S1  0.000-6.000 s  HOOK, ambient, 60 bpm, feel normal

- Harmony text: `D Dorian (raised 6th), held Kali drone`. Colour allowed: Dorian: B natural
- Chord sequence (changes only): 0.00 D5 | 5.50 Dsus2
- Flags in this section: 0

### S2  6.000-11.375 s  HOOK, ambient, 60 bpm, feel normal

- Harmony text: `D Dorian, held chord with a soft heartbeat`. Colour allowed: Dorian: B natural
- Chord sequence (changes only): 6.00 D5 | 10.38 Dsus2
- Flags in this section: 0

### S3  11.375-18.833 s  BUILD, hypnotic_techno, 128 bpm, feel normal

- Harmony text: `D minor one-bar loop, filter opening very slowly`. Colour allowed: none (D natural minor only)
- Chord sequence (changes only): 11.38 Dsus2 | 11.61 D5 | 17.83 Dsus2 | 18.41 cluster {C D E A} | 18.64 Dsus2
- Flags in this section: 0

### S4  18.833-26.833 s  BUILD, melodic_techno, 128 bpm, feel normal

- Harmony text: `D Lydian lift on Sandhya's birth`. Colour allowed: Lydian: G# (raised 4th)
- Chord sequence (changes only): 18.83 D5 | 26.31 Dsus2 | 26.42 Dm | 26.54 cluster {D A B}
- Flags in this section: 0

### S5  26.833-35.125 s  BUILD, club_folk_groove, 128 bpm, feel normal

- Harmony text: `D Dorian, golden pluck hook`. Colour allowed: Dorian: B natural
- Chord sequence (changes only): 30.72 D5 | 30.84 D | 30.95 A (single pitch class) | 31.05 D5
- Flags in this section: 2

| Time (s) | Check | Role | Pitch | Why |
|---:|---|---|---|---|
| 31.072 | 2 themes missing | pluck | C6 | KAMADEVA note C6 at 31.072 s: cut by the voice gate (rule 2: pitch above D3 under voice) |
| 31.189 | 2 themes missing | pluck | A5 | KAMADEVA note A5 at 31.189 s: cut by the voice gate (rule 2: pitch above D3 under voice) |

### S6  35.125-49.792 s  DROP, drum_and_bass, 176 bpm, feel normal

- Harmony text: `D Phrygian, rolling reese bass`. Colour allowed: Phrygian: Eb (flat 2nd)
- Chord sequence (changes only): 35.12 Dsus2 | 35.30 D5 | 41.49 cluster {C D A} | 41.55 cluster {C D} | 41.58 D (single pitch class) | 41.60 D5 | 41.67 Dm | 41.84 Dm7 | 41.89 cluster {C D E} | 41.93 cluster {D E} | 42.02 Dmadd9 | 42.10 Dsus2 | 42.16 cluster {C D E A} | 42.28 cluster {D E} | 42.62 D5 | 44.21 cluster {D Eb G A} | 44.36 cluster {C D Eb G A} | 44.47 cluster {D Eb G A} | 44.57 cluster {D Eb F G A} | 44.67 cluster {D Eb G G# A} | 44.78 cluster {C D Eb G G# A} | 44.88 cluster {D Eb G G# A} | 44.98 cluster {D Eb F G G#} | 45.01 cluster {D Eb F G G# A} | 45.08 cluster {D Eb G G# A} | 45.19 cluster {C D Eb G G# A} | 45.29 cluster {D Eb G G#} | 45.35 cluster {D Eb G A}
- Flags in this section: 0

### S7  49.792-66.833 s  DROP, half_time_dnb, 176 bpm, feel half

- Harmony text: `D Phrygian, Shiva theme on low brass and horn`. Colour allowed: Phrygian: Eb (flat 2nd)
- Chord sequence (changes only): 49.79 D5 | 50.47 cluster {D Eb A} | 51.16 D5 | 51.84 cluster {D Eb A} | 52.52 D5 | 59.52 Dm | 60.20 D5 | 60.88 cluster {C D A} | 61.57 D5 | 62.83 cluster {D Eb G A}
- Flags in this section: 2

| Time (s) | Check | Role | Pitch | Why |
|---:|---|---|---|---|
| 51.156 | 2 themes missing | brass | D4 | SHIVA octave partner D4 at 51.156 s: cut by the voice gate (rule 2: pitch above D3 under voice) |
| 51.837 | 2 themes missing | brass | Eb4 | SHIVA octave partner Eb4 at 51.837 s: cut by the voice gate (rule 2: pitch above D3 under voice) |

### S8  66.833-72.833 s  OUTRO, unplugged, 60 bpm, feel normal

- Harmony text: `MAIN on piano, unresolved Dsus2 over D`. Colour allowed: none (D natural minor only)
- Chord sequence (changes only): 66.83 D5 | 68.83 Dm | 69.83 Dsus2
- Flags in this section: 0

### Flags outside any section

| Time (s) | Check | Role | Pitch | Why |
|---:|---|---|---|---|
| 44.33 | 3 chords | pad | Eb3 | Eb3 (pad) sounds a minor 2nd from theme note D5 (lead); the theme wins |
| 44.415 | 3 chords | drone | D2 | D2 (drone) sounds a minor 2nd from theme note Eb5 (lead); the theme wins |
| 44.671 | 3 chords | pad | G3 | G3 (pad) sounds a minor 2nd from theme note G#5 (lead); the theme wins |
| 50.474 | 3 chords | pad | D4 | D4 (pad) sounds a minor 2nd from theme note Eb2 (brass); the theme wins |
| 50.474 | 3 chords | pad | D4 | D4 (pad) sounds a minor 2nd from theme note Eb4 (brass); the theme wins |
| 51.837 | 3 chords | pad | D4 | D4 (pad) sounds a minor 2nd from theme note Eb2 (brass); the theme wins |

## Theme entries (check 2)

| # | Theme | Role | At (s) | Transform | Bible pitches | Sounding | OK |
|---:|---|---|---:|---|---|---|---|
| 0 | KALI | pad | 3.500 | - | D3 A3 E4 | D3 A3 E4 | yes |
| 1 | SANDHYA | lead | 26.190 | - | D4 E4 F4 B4 | D4 E4 F4 B4 | yes |
| 2 | KAMADEVA | pluck | 30.720 | - | D5 F#5 A5 C6 A5 | D5 F#5 A5 — — | NO |
| 3 | MAIN | lead | 41.380 | - | A3 D4 F4 E4 | A3 D4 F4 E4 | yes |
| 4 | KAMADEVA | lead | 44.330 | chaos_41s | D5 Eb5 A5 C6 G#5 | D5 Eb5 A5 C6 G#5 | yes |
| 5 | SHIVA | brass | 49.792 | - | D2 Eb2 D2 Eb2 | D2 D4 Eb2 Eb4 D2 — Eb2 — | NO |
| 6 | KAMADEVA | pad | 58.840 | curse_56_64s | D4 F4 A4 C5 A4 | D4 F4 A4 C5 A4 | yes |
| 7 | MAIN | piano | 66.833 | - | A3 D4 F4 E4 | A3 D4 F4 E4 | yes |

## End sting (check 3d)

- 72.7 s: Dsus2 (pitch classes [2, 4, 9])

## Bass and MIDI (checks 4 and 5)

- Bass roots below 200 Hz: 94, with harmonic: 94
- Round trip: match, notes written 573, read back 573

## write_notes warnings

- QUIET_SUPPRESSED quiet 64-70 s: 12 segments outside the quiet roles ['drone', 'drums', 'pad', 'piano'] and theme MAIN were cut
- NOTE_TOO_SHORT ostinato at 49.3862 s: pitch 50 lost: 0.006 s left after cuts
- NOTE_TOO_SHORT drums at 49.3862 s: pitch 42 lost: 0.006 s left after cuts
- NOTE_TOO_SHORT drums at 49.7841 s: pitch 38 lost: 0.008 s left after cuts
- NOTE_TOO_SHORT bass at 49.7841 s: pitch 57 lost: 0.008 s left after cuts
- NOTE_TOO_SHORT bass at 49.7841 s: pitch 38 lost: 0.008 s left after cuts
- THEME_TRUNCATED plan.events[3]: KAMADEVA at 30.72 s: 3 of 5 notes cut or dropped

## Fixes needed

- **2 themes** (4 flags): note_writer.py _event_segments / _theme_pitches, or the plan event (theme, transform, role). A theme note cut under voice needs the plan's gap moved, not a pitch change.
- **3 chords e** (6 flags): note_writer.py PAD_CHORD / DARK_PAD / DRONE: remove the held pad pitch that clashes with the theme note during the theme entry (theme wins).
