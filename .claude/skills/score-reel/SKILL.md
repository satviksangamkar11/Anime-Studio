---
name: score-reel
description: Score one Anime-Studio reel with background music only (no sound effects, no voice) in Ableton Live 12 + Serum, locked to the reel's shot list. Use when the owner asks to score, compose, plan or rebuild the music of a reel or episode.
---

# Score a reel (background music only)

You are the composer for one reel. The picture, the H3 sound effects and the voice are finished and must not change.
You decide music only, you write every decision to a file first, and a checker must pass before anything reaches Ableton.
Read this whole file before you start. Follow the steps in order. Log every step in PROJECT_LOG.md (blot.md format).

## The owner's specification (non-negotiable)

1. **Music only.** Never write sound effects or Foley. Risers, swells, hits and drops are made from score instruments.
2. **Voice first.** Most of a reel has narration or dialogue (Kalika reel 1: 83%, cue_sheet `voice.coverage`). Inside
   every voice window: drone, pad, bass and a soft pulse only; nothing busy between 1 and 4 kHz; themes, plucks and
   bright hits go in the voice gaps (cue_sheet `voice.gaps`). A picture-locked moment that falls under speech (an impact
   with `in_voice: true`, or the end sting before `retention.last_voice_end_s`) still gets its music on the frame, but
   only as a **low hit**: sub, kick, low drum or low brass below 250 Hz, short, nothing between 1 and 4 kHz. Any bright
   attack waits for the next gap or the last word. Gate D ducks the score again under voice (ratio 6) and checks it sits
   15 to 21.5 dB under the voice.
3. **Every emotion is scored.** Use each shot's `hook_type`, `purpose`, act and per-second beats (rules below).
4. **Every cut is scored.** Each cut gets a transition type from the cut table below. Tempo changes only at act changes; genre colour may also change at a shot boundary inside an act when the BPM stays the same (owner, 2026-11-09) (the cue sheet solves tempo per act). Key colour (mode, chord colour) may also change at a hard cut.
   Inside an act, change feel (half-time, double-time) and density instead.
5. **Frame lock.** Every planned hit, swell end, downbeat and drop-out lands within one frame (42 ms) of its picture time.
   Use the cue sheet's frame-exact times (for example the white-out is at 43.083 s, not 43.1 s).
6. **Retention.** Sonic logo on frame 0. The main musical re-hook must sit inside `retention.rehook_window_s`
   (31.5 to 42.0 s for a 70 s reel). The end sting and an unresolved chord sit inside `retention.end_hook_window_s`.
   Something new enters or leaves at every shot boundary (every 5 to 8 s).
7. **Contrast, not loudness.** One elevation (peak) per reel. Silence before the big hits: drop-outs of 0.4 s, never
   longer than 0.45 s.
8. **Reverence.** Gods (Kali, Shiva, Brahma, ...) get awe and weight. Never comic hits or an EDM-style drop on a divine
   reveal. Comic timing only for playful characters (Kamadeva). When a god is revealed inside a fast act, the drums
   stop for the reveal: a drop-out of at most 0.45 s, then a low swell and the god's theme on weighty instruments
   (low brass, choir pad, conch-like horn) in half-time feel. The fast groove may return only after the theme has
   been heard, under the act's own tempo.
9. **Continuity across the series.** Home key, main theme, sonic logo, character themes and presets come from the
   story's `music_bible.json` and are reused, transformed (tempo, mode, instrument), never replaced.
10. **One score for every language.** The cue sheet warns when en/hi/mr speech windows differ; use `voice.union`.
11. **Phone first.** Bass below 200 Hz in mono, plus a mid harmonic so phones can hear it. The mix must survive mono.
12. **Original only.** Never sample or copy an existing recording, melody or chant (Coolie's teaser drew a copyright
    claim for a sample). Chants and vocal horns come from the owner's recordings or cleared packs, or a fitting sample from the owner's Ableton library.

## Style (from the owner's research; the bible says which style a story uses)

- Modern hybrid anime-cinematic (orchestra + Serum synths + modern drums), or
- the electronic experiment (Anirudh / Sai Abhyankkar inspired): melodic techno (about 122 to 130 BPM) and hypnotic techno (examples found 131 to 135; we use 128 so one BUILD tempo serves both),
  club + Tamil folk groove, drum and bass and half-time drum and bass at 170 to 176 BPM, ambient or unplugged at 60.
- Patterns to use (from their score albums): a short entry theme (under 90 s) per hero or god; one named theme per
  character; a dedicated set piece for the big turn (our re-hook and cliffhanger); fight music built from the reel's own
  themes; the song or anthem hook reused as score; a sonic logo that runs across all episodes; voice as an instrument.
- Mistakes critics punished: loud all the time, the same texture repeated, music fighting the picture or the dialogue,
  no quiet moment. Each reel needs one quiet melodic moment.

## Rules by shot (hook_type)

| hook_type | Music does |
| --- | --- |
| reveal | Starts thin, blooms on the reveal second (from `beats`); the character's theme enters on that second |
| expression-beat | Holds one chord; a theme fragment only in voice gaps |
| suspense | Ostinato, unresolved (no tonic on strong beats), density rising across the shot |
| reversal | Drop-out 0.4 s before the turn, one hit on the turn, re-enter darker |
| closing (closing_hook) | Unresolved chord, sparse pulse under the last line, end sting, tail 0.45 s or less |

## Rules by cut (cue_sheet `cuts`)

| Cut | Transition |
| --- | --- |
| same act, same palette | No break; theme hands over; bed continues |
| hard_cut | Swell or reverse swell ends exactly on the cut frame; new key colour may land on the cut downbeat |
| act_change | The only place for a tempo change (key colour too); genre colour may also change at a shot boundary inside an act when the BPM stays the same (owner, 2026-11-09) |
| impact inside a shot | Drop-out 0.4 s, hit on the impact frame; low hit only if `in_voice`; never mask the H3 effect in the same band (see `sfx`) |

## Tempo

- Use only BPM values listed in the cue sheet's `tempo_candidates` for that act (every cut and the act end then land
  within one frame of an 8th note). Kalika reel 1: BUILD 128 (or 124), DROP 176, HOOK and OUTRO 60. The DROP holds
  Shiva's reveal at 48 s: by rule 8 that second is a drop-out and his theme in half-time (88 felt), not a drop;
  full drum and bass runs around it (34 to 47.6 s, and after the theme).
- Perceived tempo (half-time, double-time) and density (notes per beat) do most of the emotional work.
- Ableton cannot change tempo or metre from a script. Build in **clock mode**: the Live set runs at 60 BPM, so one beat
  is one second, and the note writer places every note at its absolute time from the plan's own tempo map. Tempo-synced
  effects (delay, LFO, arpeggiator) must be set to free time (ms / Hz). Arrangement locators cannot be written: use a
  MARKERS MIDI track with one empty, named clip per shot.

## Steps

Build status (2026-11-09): step 1 is built and tested (`score/cue_sheet.py`). Not built yet: `music_bible.json`
(step 2, written once per story with the owner), `score/plan_check.py` (step 4, next build step), the note writer
(step 5) and `check_score` (step 8). Until a step's tool exists, stop at that step and tell the owner.

1. **Cue sheet.** `python -m score.cue_sheet --shots stories/<slug>/<pack>/shots.json --episode <n> --out stories/<slug>/<pack>/score/ep<n>/cue_sheet.json`.
   Stop on any error. Read every warning; report them to the owner.
2. **Bible.** Read `stories/<slug>/music_bible.json` (create it once per story at gate M0: home key, sonic logo,
   main theme, character themes and signature sounds, track roles, presets, style, emotion templates).
3. **Plan.** Write `score_plan.json` (format below) from the cue sheet + bible + these rules. Write the reason for each
   section in one plain sentence (`why`). Do not write notes yet.
4. **Check the plan.** Run the plan checker (score/plan_check.py, next build step). Fix every error. Never weaken a rule
   to pass. Then the owner approves the plan at gate M1 (one-page table + a stock-sound MIDI audition).
5. **Notes.** The note writer turns the plan into exact notes per track role (positions in seconds) and a `.mid`.
6. **Sounds.** One text brief per track role to the owner's natural-language Serum preset tool; every preset has
   Macros 1-4 routed (1 brightness, 2 motion, 3 width, 4 space). Reuse presets listed in the bible.
7. **Build.** Through the owner's extended Ableton MCP: clock mode, one MIDI track per role, Serum + preset, arrangement
   clips at exact beats, clip automation envelopes for the 4 macros and volume, MARKERS track. Check `get_session_info`
   first. Never inject state into .als files.
8. **Render and check.** Owner exports (or the MCP records in real time) 48 kHz / 24-bit; `check_score` trims to the
   cue sheet's `total_samples` and runs the checks; then Gate D preview with picture, H3 effects and voice (gate M2).
9. **Learn.** When the owner approves, copy the plan into `stories/<slug>/score_examples/` and add any new emotion
   template to the bible. Approved examples are the reference for the next reel.

## score_plan.json (v1)

```json
{
  "schema_version": 1, "episode": 1, "style": "electronic", "home_key": "D minor",
  "sections": [
    {"start_s": 11.0, "end_s": 34.0, "act": "BUILD", "bpm": 128, "feel": "normal|half|double|quad",
     "genre": "hypnotic_techno", "harmony": "D minor, Lydian lift at 18 s", "density_per_beat": [2, 4],
     "roles_on": ["drone", "pad", "ostinato", "bass", "drums"], "intensity": [0.4, 0.6],
     "why": "Frame story and creation: calm curiosity rising into wonder."}
  ],
  "events": [
    {"at_s": 0.0, "type": "sonic_logo"},
    {"at_s": 43.083, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits"},
    {"at_s": 48.0, "type": "theme_entry", "theme": "SHIVA", "role": "lead", "feel": "half", "preceded_by_dropout_s": 0.4},
    {"at_s": 60.0, "type": "hit", "band": "low", "role": "hits"},
    {"at_s": 69.85, "type": "end_sting", "tail_s": 0.15}
  ],
  "cuts": [{"at_s": 11.0, "transition": "reverse_swell_to_cut"}],
  "automation": [{"role": "pad", "macro": 1, "points": [[18.0, 0.2], [20.0, 0.8]]}],
  "rehook_at_s": 34.0, "peak_at_s": 48.0
}
```

The checker enforces: tempo boundaries only at act changes (genre colour may change at a shot boundary inside an act when the BPM stays the same); every BPM is a cue-sheet candidate for its act;
every cut has a transition; hits within 1 frame of impacts, and `band: "low"` on every hit under voice; drop-outs at
most 0.45 s; busy roles silent inside voice windows; a god's theme entry has a drop-out and half feel, never a drop;
the re-hook inside the retention window; one peak; sonic logo at 0; end sting inside the end-hook window; themes and
presets exist in the bible; the plan covers exactly 0 to `total_s`.
