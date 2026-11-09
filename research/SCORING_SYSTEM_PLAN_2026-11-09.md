# Anime Studio Scoring System Plan (Ableton + Serum)

Nov 9, 2026 · @Sangeeta

## Bottom line

Build one new stage, **Score**, that runs after the 10 clips are rendered and before Gate D mixes the reel. It reads `shots.json`, composes one continuous score per reel in Ableton Live 12.3 with Serum 2, renders a 48 kHz stereo WAV of exactly the reel length, and hands it to Gate D as the single BGM track Gate D already supports. Sound effects (H3 model audio) and voice stay untouched.

What the repos actually say, read on 2026-11-09 (several points in the attached plan were wrong):

| Topic | Attached plan said | Repo says |
| --- | --- | --- |
| Where BGM enters | New `ableton_serum_director.py` + 3-stem mix | `h3/gate_d_audio.py` (branch merge-v4-universal) already takes ONE continuous BGM track, ducks it under voice (`sidechaincompress` ratio 6, attack 15 ms, release 500 ms) and checks presence: median BGM 15 to 21.5 dB under voice, never below -50 dB |
| BGM manifest | `bpm 120, lufs -18` | `audio/bgm_manifest.json` needs `track_id, path, license_type, bpm, lufs`; empty list = no BGM |
| Loudness | -14 LUFS | Reel target -16 LUFS, true peak -1.5 dB, AAC 192k (`core/core.json`) |
| Hold-Burst-Hold spans | `stage_frame_spans` in shots | Not in the writer's `shots.json`; only in the H3 shot JSON after `tools/convert_deva_shots.py` (`motion_7_stage.stage_frame_spans`, `anime_timing_cadence`). The pack has `per_second_directives`, `look.impact_frames`, `look.hold_purpose`, `deliberate_flip_marker` |
| Colour acts | PH-DAWN-PLAY, PH-POISON | Field is `look.act` / `look.phase` (e.g. HOOK / PH-HOOK) + `look.palette_id` |
| Extended Ableton MCP | In ableton-claude-final | Not in any GitHub repo. Rule 31 says it lives at `D:\ableton` and connects when Live is open. Your PC was not linked to this chat, so I could not read it |
| NL to Serum preset | Celian-mrc/serum-mcp | Not in your GitHub either. `ableton-claude-final` has `serum2/compiler/mcp_intent.py`, which maps text to only 7 of Serum's 127 Ableton-exposed parameters; as you said, that repo is a tutorial-learning project, not this use case |

The plan below is written so it works with whatever tool names your local MCP and preset generator expose: Claude Code calls them through a thin adapter, and everything musical is decided in files first.

## Cross-check results (2026-11-09): what was missing and the fix

I checked the plan against the repo, the Kalika pack, the Ableton Live API and the web. Each gap below now has a fix in the code, the skill or this doc.

| # | Gap found | Fix |
| --- | --- | --- |
| 1 | The tempo map changed tempo at 41 s, which is neither a hard cut nor an act change | Tempo changes only at act changes; the cue sheet solves valid BPMs per act (BUILD 128, DROP 176) |
| 2 | The re-hook at 26 s was outside the retention window (31.5 to 42.0 s) | Re-hook at 34.0 s, where drum and bass enters on the act change |
| 3 | Live's API cannot automate song tempo or change the time signature | Clock mode: the set runs at 60 BPM, notes are placed at absolute seconds, synced effects in free time |
| 4 | Arrangement locators are read-only | A MARKERS MIDI track with one named clip per shot |
| 5 | The API has no audio export | Owner export, or the MCP records in real time; the render is trimmed to exactly 3,360,000 samples |
| 6 | Gate D supports BGM, but `post.py` and `render_controller` pass `bgm=None` | Wire the manifest in build step 10 (needs your go) |
| 7 | H3 effects overlap planned hits (bell at 0 to 0.8 s, 43.0 to 43.5 s, 48 to 49 s) | The cue sheet lists every effect; the score never fills the same band at the same moment |
| 8 | The plan rounded the first white-out to 43.1 s | Frame-exact times from the cue sheet: 43.083 s (frame 1034) |
| 9 | The 60.0 s white-out and the end sting fall under speech | A low-hit rule: sub and low drum only under voice; the cue sheet flags `in_voice` and the last word (69.8 s) |
| 10 | Shiva's reveal at 48 s sits inside the drum and bass act | A 0.4 s drop-out, then his theme in half-time feel; never a drop on a divine reveal |
| 11 | Live imports reference video as .mov only | The picture reference for Live is exported as .mov |
| 12 | Whether Serum macros follow clip automation is not verified | Confirmed once in Live before the first build (open item) |
| 13 | Hybrid-cinematic or electronic style not chosen | The music bible states the style; you choose at gate M0 |
| 14 | Phones roll off below about 200 Hz and play mono when held upright | Mono bass, a mid harmonic on every bass note, and a mono check |
| 15 | Your MCP's tool names are unknown (`D:\ableton` is not on GitHub) | The adapter is written after the connection check (build step 1) |
| 16 | `PROJECT_LOG.md` lives on your PC, which I cannot reach from here | Log lines are handed to you to paste |
| 17 | `story_plan.json` says 68 s, the shots add up to 70.0 s | The score follows the shots (70.0 s) unless you say otherwise |
| 18 | Cue sheet v1 reads voice windows from the pack, not from the rendered voice | Gate D's presence check catches drift; v2 can read the rendered timings |
| 19 | Drums, chants and vocal horns need real recordings | Your own recordings or cleared packs only; never a sample of a film or song |

The cue sheet also passed a fuzz test (648 broken inputs) and an independent code review (13 findings, all fixed and re-checked). It refuses to build when a shot is unreadable or a hit lies outside its shot, so a score is never built on a shorter or wrong reel clock.

## How Claude is taught to score to your specification

Claude is not trained on music. It is taught by six things that live in the repo, and each one is checked:

1. **The skill** (`.claude/skills/score-reel/SKILL.md`, written). Claude Code loads it whenever you ask it to score a reel. It holds your specification as 12 rules (music only, voice first, every emotion, every cut, frame lock, retention, contrast, reverence, continuity, one score for all languages, phone first, original only), the style options from the Anirudh and Sai study, a rule table per `hook_type` and per cut type, and the tempo rules.
2. **The cue sheet** (`score/cue_sheet.py`, built). Claude never measures time itself. It reads every cut, act, impact, voice window, voice gap, effect, retention window and valid tempo from this file, frame-exact.
3. **The plan format** (`score_plan.json`). Claude writes every musical decision (section, tempo, feel, harmony, theme entry, hit, transition, automation) with a one-line reason, before any note is written.
4. **The checker** (`score/plan_check.py`, the next build step). It enforces the rules in code. The skill forbids weakening a rule to pass.
5. **Your gates.** M0 approves the music bible, M1 approves the plan with a stock-sound MIDI audition, M2 approves the Gate D preview with picture, effects and voice. Gate D also checks loudness and that the score sits 15 to 21.5 dB under the voice.
6. **Approved examples.** Every plan you approve is saved in `score_examples/`. New emotion templates go into the bible. The next reel uses them as its reference, so Claude's choices move towards your taste over time.

The split of work: Claude makes the musical choices (emotion, harmony, themes, transitions). Code does the timing, note positions and checks, where an LLM would make mistakes.

## Where scoring sits in the pipeline

Scoring can start as soon as Gate A approves the pack, because `editorial_duration_sec` per shot is fixed there and a re-render (like SHOT-008) never changes it. It only needs the rendered clips for the final check against picture.

1. Gate A: story pack approved (`story_plan.json`, `bible.json`, `shots.json`). The edit clock is now locked.
2. **Score S1, cue sheet (new):** `audio/score/cue_sheet.json` built from `shots.json`. Runs in parallel with Flow and render.
3. **Score S2, spotting + musical plan (new, owner gate M1):** key, raga, tempo map, which shots get which motif, where music swells or drops out.
4. Gate B and Gate C: keyframes and H3 render, unchanged. Clips come home per Rule 29.
5. **Score S3, build in Ableton (new):** Claude Code drives your Ableton MCP and Serum preset generator.
6. **Score S4, render + check against the real reel (new, owner gate M2):** listen with the joined picture and H3 sound effects.
7. Gate D: `gate_d_audio.py` mixes voice + H3 effects + the score, ducks the score under voice, normalises to -16 LUFS. Small code change needed: director/post.py and render\_controller still pass bgm=None; they must read story.json "bgm": {"enabled": true, "manifest": ...}, which the UI's set\_bgm already writes.
8. Export, unchanged.

One score serves all three language reels (en, hi, mr): in the Kalika pack every language uses the same `time_range` per line, so the voice windows the score avoids are identical.

## Inputs: the cue sheet

A pure script, `score/cue_sheet.py` (built 2026-11-09; no model, no network; 32 tests), turns `shots.json` into `cue_sheet.json` on the reel clock. Every field it reads already exists:

- Shot windows: `editorial_duration_sec`, summed in order (fps 24 from `timing_and_lattice`).
- Emotion: `hook_type`, `purpose`, `look.act`, `look.phase`, `look.palette_id`, `look.hold_purpose`, `is_opening_0_2s_hook`, `is_closing_hook`.
- Hit points: `look.impact_frames` (`at_s`, `type`, `frames`) and `deliberate_flip_marker` (HARD CUT, new place).
- Voice windows: `audio_and_dialogue_track.narration.time_range` and `dialogue[].time_range` + `speaker`.
- Per-second beats: `per_second_directives[]` (`action_pose_expression`, `audio_cue`), used for small swells inside a shot.
- Cut character: `continuity_handoff.outgoing` / `incoming`, `loop_seam`.

Kalika Puran Reel 1 ("Kama's First Arrow", 70.0 s, 10 shots), computed from the merge-v4 pack:

| Shot | Reel time (s) | hook\_type | Act / palette | Hits | Voice on reel clock (s) |
| --- | --- | --- | --- | --- | --- |
| 001 | 0-6 | reveal | HOOK / durga\_kali\_shakti |  | Narr 0.5-5.5 |
| 002 | 6-11 | expression-beat | HOOK / durga\_kali\_shakti |  | Narr 6.3-10.7 |
| 003 | 11-18 | suspense | BUILD / hanuman\_vayu | hard cut in | Narr 11.3-13.1, Munis 13.3-15.4, Markandeya 15.6-17.8 |
| 004 | 18-26 | reveal | BUILD / karna\_surya | hard cut in | Narr 18.4-25.6 |
| 005 | 26-34 | reveal | BUILD / karna\_surya |  | Narr 26.3-29.6, Kamadeva 30.2-33.6 |
| 006 | 34-41 | suspense | DROP / karna\_surya |  | Brahma 34.3-37.6, Narr 37.9-40.8 |
| 007 | 41-48 | reversal | DROP / karna\_surya | white-out 43.083 (frame 1034) | Kamadeva 41.2-42.8, Narr 44.2-47.8 |
| 008 | 48-56 | reveal | DROP / shiva\_neelkanth |  | Shiva 49.2-52.4, Narr 52.8-55.7 |
| 009 | 56-64 | reversal | DROP / karna\_surya | white-out 60.0 | Brahma 57.2-61.2, Narr 61.6-63.8 |
| 010 | 64-70 | suspense, closing | OUTRO / karna\_surya | held fear | Kamadeva 64.6-67.4, Narr 67.8-69.8 |

Two facts drive the music design. First, voice covers 83% of the reel, so this is an underscore: the score lives in the gaps (0.0-0.5, 5.5-6.3, 40.8-41.2 and so on) and stays sparse under speech. Second, the cue sheet lists, per act, the tempos at which every cut and the act end land within one frame of an 8th note (see the tempo map).

## System architecture

The rule that keeps this reliable: **every musical decision is written to a JSON file and tested before Ableton is touched.** Ableton is the place the decisions are played, not the place they are made. Then a failed MCP call, a crashed Live set or a changed preset never loses the composition, and any step can be re-run.

| # | Component | File (new, under `audio/score/` in Anime-Studio) | Does | Model call? |
| --- | --- | --- | --- | --- |
| 1 | Series music bible | `stories/<story>/music_bible.json` | Main theme, sonic logo, character themes, harmony colour, track roles, emotion templates. Written once per story, reused every reel | Once, owner approves |
| 2 | Cue sheet builder | `score/cue_sheet.py (built)` | `shots.json` to reel-clock cue sheet (section above) | No |
| 3 | Spotting planner | Claude Code + the score-reel skill (`SKILL.md`), checked by `score/plan_check.py` | Cue sheet + bible to `score_plan.json`: tempo map, key per section, motif per shot, intensity curve, entries, drop-outs, transition type per cut | Yes (Claude), owner gate M1 |
| 4 | Note writer | `write_notes.py` | `score_plan.json` to exact MIDI notes per track, in beats, as `notes/*.json` + a `.mid` for audition | Partly (melody), rest rule-based |
| 5 | Sound designer | adapter to your NL-to-Serum tool | One text brief per track (e.g. "tanpura-like drone, warm, slow bloom") to a `.SerumPreset` per track, saved in `presets/` | Yes, via your generator |
| 6 | Ableton builder | `ableton_build.py` (adapter over your MCP) | Creates tracks, loads Serum + preset, writes clips and notes, sets clip automation envelopes and a MARKERS track | No (MCP calls only) |
| 7 | Render + check | `check_score.py` | Length = reel length to the sample, no clipping, voice-window level, hit alignment, Gate D presence check | No |
| 8 | Manifest writer | `write_bgm_manifest.py` | Adds the track to `audio/bgm_manifest.json` with `license_type: "original"` | No |

The two adapters (5 and 6) are the only code that knows tool names. Everything else is plain Python with tests, matching how `h3/` is built (pure builders, "never runs ffmpeg").

## Series music bible (modern style)

The sound is a **modern hybrid anime-cinematic score**: orchestral weight (strings, brass, choir), modern synths from Serum (pads, plucks, pulses, bass), and modern drums (trailer percussion, sub hits, risers). No ragas. Each story gets one `music_bible.json`, written once and reused for all 13 Kalika episodes so every character sounds the same in episode 9 as in episode 1. Everything below is my proposal for your approval at gate M0.

**Series identity, the same in every episode:**

- Home key **D minor**, so every reel and every transition shares one home.
- **Main theme**: a 4-note hook that anyone can hum after two episodes.
- **Sonic logo**: one signature sound (e.g. a processed vocal swell into a low hit) on frame 0 of every reel, and the same **end sting** on every cliffhanger. Viewers learn "this is the show" in under a second.
- **Indian colour, light touch (your call):** at most one or two textures, such as a breathy flute-like lead or a frame-drum hit, layered inside the modern sound for identity. Off is also fine.

**Character themes (melody + harmony colour + signature timbre):**

| Character | Feel | Harmony colour | Theme shape | Signature sound |
| --- | --- | --- | --- | --- |
| Adya Kali | Awe, calm power | Minor with suspended chords, no resolution until she wills it | 3 rising notes (her three eyes), very slow | Choir pad + deep sub swell |
| Brahma | Grand, a little proud | Lydian (bright, raised 4th) | Stately 4-note descent | Low brass stack |
| Sandhya | Gentle, new | Dorian (soft minor) | Short rising phrase that hangs | Breathy airy lead |
| Kamadeva | Playful, daring | Major / Mixolydian, syncopated | Bouncy 5-note pluck figure | Bright golden pluck + finger-snap groove |
| Shiva | Threat, vastness | Phrygian (flat 2nd), very low | 2 low notes a half-step apart | Distorted sub + taiko-style hits |
| Narrator / frame story | Storytelling | Plain minor | No theme; the bed under the voice | Soft pad + clock-like pulse |

Themes transform, they do not just repeat: at the curse (SHOT-009) Kamadeva's bouncy figure comes back slow, in minor, under Shiva's Phrygian colour, so the music tells you his fate before Brahma finishes.

**Track roles, the same in every reel (8):** 1 sonic logo + hits, 2 pad/bed, 3 theme lead, 4 ostinato/arp, 5 bass (sub + a mid harmonic so it is heard on phones), 6 drums/percussion, 7 risers/transitions, 8 choir/vocal texture.

## Tempo map (final, after the 2026-11-09 cross-check)

Tempo sets the energy. Harmony, register and sound decide whether that energy feels happy or frightening. So the plan controls three things separately: **actual BPM**, **felt tempo** (half-time or double-time) and **density** (notes per beat). Actual BPM changes rarely. Felt tempo and density do most of the emotional work.

**Rules:**

- Actual BPM and genre change only at act changes. Key colour may also change at a hard cut. Inside an act, only the feel and the density change.
- The cue sheet works out the BPM values per act. At those values every cut inside the act, and the act end, land within one frame (41.7 ms) of an 8th note. The plan may only use those values.
- Kalika Reel 1: HOOK (0 to 11 s) **60**. BUILD (11 to 34 s) **128** (124 also fits, 126 does not). DROP (34 to 64 s) **176** (the only drum and bass value that fits). OUTRO (64 to 70 s) **60**.
- The old 60/120 map is replaced, for two reasons. 120 suits neither the techno nor the drum and bass experiment. It also changed tempo at 41 s, a cut that is neither a hard cut nor an act change, which broke its own rule. The chaos at 41 s now comes from density (16ths, more drums) at the same 176.
- The re-hook moves from 26 s to **34.0 s**: drum and bass enters on the act change. That is inside the retention window (31.5 to 42.0 s) from core.json. The old 26 s point was outside it.
- Reverence: Shiva's reveal at 48 s is not a drop. The drums stop for a 0.4 s drop-out (47.6 to 48.0 s). Then his theme enters in half-time feel (88 felt) on low brass, choir pad and a conch-like horn, in the voice gap 47.8 to 49.2 s.
- **Clock mode** (Ableton cannot change tempo or time signature from a script). The Live set runs at 60 BPM, so one beat is one second. The note writer places every note at its absolute second from the plan's own tempo map. Tempo-synced delays, LFOs and arpeggiators are set to free time (ms or Hz). No short 2/4 or 3/4 bars are needed.
- Hybrid scoring: one continuous theme per act plus exact hits on the impact frames. No hit on every expression, and no Mickey-Mousing for deities.

**Kalika Reel 1, shot by shot:**

| Shot (s) | Emotion | BPM | Feels like | Density | Harmony / sound | Sync points (frame-exact) |
| --- | --- | --- | --- | --- | --- | --- |
| 001 (0-6) | Awe, revelation | 60 | Broad, almost no pulse | Sustained | D minor sus, choir pad + sub swell | Sonic logo on frame 0 (voice gap 0.0-0.5); under narration only drone and swell; theme fragment in the gap 5.5-6.3 |
| 002 (6-11) | Power, meaning | 60 | Slow heartbeat | 1 per beat | Same, low pulse added | Reverse swell ends on the 11 s hard cut (gap 10.7-11.3) |
| 003 (11-18) | Curiosity, frame story | 128 | Calm, half-time feel | 2 per beat, soft | Plain minor, narrator bed | New tempo lands on the 11 s cut; swell in the gap 17.8-18.4 into the 18 s hard cut |
| 004 (18-26) | Wonder, creation | 128 | Half-time | Expanding | Lydian lift, wide strings, Sandhya's airy theme | Key colour changes on the 18 s hard cut; her theme in the nearest voice gap after her birth |
| 005 (26-34) | Delight (Kamadeva) | 128 | Full time, bouncy | 4 per beat, syncopated | Major, golden pluck, light techno groove | Groove builds; 0.4 s drop-out in the gap 33.6-34.3 |
| 006 (34-41) | Playful suspense | 176 | Drum and bass, full time | Rolling breaks | Minor ostinato under Brahma | **Re-hook at 34.0 s** on the act change |
| 007 (41-48) | Mischief to chaos | 176 | Same tempo, denser | 16ths + drums | Kamadeva's theme turns dissonant | No tempo change at 41 s; drop-out 42.683-43.083, hit on the **43.083 s** white-out (frame 1034, voice gap) |
| 008 (48-56) | Fear, vastness (Shiva) | 176 | Half-time (88 felt), heavy | Low and sparse | Phrygian, low brass, choir pad, conch-like horn; the reel's one peak | Drop-out 47.6-48.0; Shiva's theme at 48.0 s |
| 009 (56-64) | Shock, doom | 176 | Half-time, falling | Thins out | Kamadeva's theme slow in minor | The 60.0 s white-out is under speech: drop-out from 59.6, then a **low hit only** (sub and low drum, nothing at 1-4 kHz) |
| 010 (64-70) | Held fear, cliffhanger | 60 | Sudden slow-down, ticking | 1 per beat | Unresolved chord, no tonic | Tempo falls at the 64 s act change (gap 63.8-64.6); end sting's bright attack at **69.8 s**, after the last word |

The sudden fall from 176 to 60 at 64 s is the research's sudden tempo change for shock: the music stops running as Kamadeva freezes in fear.

## What else makes it modern and engaging

These go into the planner as fixed rules, next to the tempo map:

1. **Hook in the first second.** The sonic logo hits on frame 0, together with the visual hook in 0-2 s. A Reel that opens on silence loses swipers.
2. **A change every 5-8 s.** Every shot boundary brings something new (a layer in, a layer out, a drop, a lift), matching the shot lengths. That is the music's share of attention retention.
3. **Contrast beats loudness.** Silence and thin moments make the hits land: 0.4 s drop-outs before the two white-outs, sparse under voice, full only at the peak (Shiva, 48 s). No wall of sound for 70 s.
4. **Voice comes first.** 83% of the reel has narration or dialogue. Under voice: pad, bass and soft pulse only, nothing busy at 1-4 kHz; themes and hits go in the gaps.
5. **Phone speakers.** Most viewers hear this on a phone. Sub-bass alone is inaudible there, so every bass note gets a mid harmonic (saturation); the mix must also hold up in mono.
6. **Reverence.** Kali, Shiva and Brahma get awe and weight, never comic hits or EDM-style drops on a divine reveal. Comic timing is allowed only for Kamadeva's mischief.
7. **Episode cliffhanger.** Every reel ends on an unresolved chord and the same end sting, so the next episode feels promised.
8. **Rewatch.** The end tail resolves into the sonic logo's first note, so an auto-replay sounds intentional.
9. **Copyright safety.** Only original notes and your own presets; no sample packs with Content ID claims, no melodies resembling known film or song themes. The manifest says `license_type: "original"`.
10. **Reusable emotion templates.** Each transition used (e.g. playful to chaos, awe to fear) is saved once as a template in the bible (start/end BPM, curve, feel, density, harmony, sync rule), as your research suggests, and reused across all 13 episodes.
11. **One score for three languages.** Hindi and Marathi lines use the same time windows as English, so the voice gaps hold for all three. If a future pack differs per language, the planner checks all three before writing notes.

## Scoring rules per shot and per cut

The planner applies fixed rules, then Claude adds the musical detail inside them. Fixed rules make the score repeatable across 13 episodes; the detail keeps it from sounding mechanical.

**Per shot, by `hook_type`:**

| hook\_type | Music does | Serum automation (where exposed) |
| --- | --- | --- |
| reveal | Starts thin, blooms to full on the reveal second from `per_second_directives`; the character's motif enters on that second | Filter cutoff and macro 1 rise across the reveal second; pad attack long |
| expression-beat | Holds one chord; motif fragment in the voice gaps only | Static; a small wavetable drift |
| suspense | Ostinato pulse, unresolved (no Sa on strong beats), slowly rising density | LFO rate up over the shot; resonance up slightly |
| reversal | Everything drops out 0.4 s before the turn, a single low hit on the turn, re-enters darker | Cutoff snaps down, detune up on re-entry |
| closing (is\_closing\_hook) | Unresolved chord held through the payoff, sparse pulse under the last line, tail of 0.45 s or less | Release long, cutoff slowly closing |

**Per cut (shot N to N+1):**

- Same act, same palette: no break. The motif hands over across the cut; the drone never stops.
- `deliberate_flip_marker` HARD CUT (new place, e.g. 11 s and 18 s): a 1-beat reverse swell on track 7 ends exactly on the cut frame; the new palette's chord lands on the cut downbeat.
- Act change (HOOK to BUILD at 11 s, BUILD to DROP at 34 s, DROP to OUTRO at 64 s): harmony colour and, if the tempo map says so, the actual tempo change only here, always in the home key of D minor, so it reads as one score.
- Impact frames (`white`-out at 43.083 s, frame 1034, and 60.0 s): a 0.4 s drop-out, then a hit on the exact frame. In clock mode a note can sit at any second. An impact under speech (the cue sheet marks it in\_voice, here 60.0 s) gets a low hit only: sub and low drum, nothing at 1 to 4 kHz.

**Under voice (all shots):** during every `time_range` only drone, pad and sub play, with nothing busy between 1 and 4 kHz; motif and plucks use the gaps. Gate D's sidechain then does the final ducking, so the score must already sit 15 to 21.5 dB under voice without fighting it.

**Intensity by act for Reel 1:** HOOK 0.3 to 0.5, BUILD 0.4 to 0.6, DROP 0.7 to 0.9 (peak at Shiva's entrance, 48 s), OUTRO 0.5, held unresolved.

## Ableton + Serum production engine

Claude Code builds one Live set per reel, `audio/score/<reel>/score.als`, with your extended MCP. Tool names below are the ones your earlier projects already used (from the ahujasid-style base); the adapter maps them to your extended names once I can read `D:\ableton`.

**Build sequence (one reel):**

1. Clock mode: the set runs at 60 BPM, so one beat is one second. Live's API cannot write song tempo or time-signature changes, so the note writer applies the plan's tempo map, not Ableton. Tempo-synced effects run in free time.
2. A MARKERS MIDI track with one empty, named clip per shot (SHOT-001 reveal and so on). Arrangement locators are read-only from the API, so they cannot be written.
3. Per track role: `create_midi_track`, load Serum 2 (browser path Plugins > Xfer Records > Serum 2; `search_browser` does not search Plug-Ins, found in probe 16.5.57), then load the track's `.SerumPreset` with your preset loader.
4. `create_clip` + `add_notes_to_clip` from `notes/*.json`, positions in beats on the arrangement (in clock mode a beat is a second).
5. Automation from `score_plan.json`: clip automation envelopes for Macros 1-4 and volume (the Live API's create\_automation\_envelope). Whether Serum's macros respond to them is confirmed once in Live before the first build.
6. Save the set. The owner opens it to tweak by hand any time: it is a normal Live project.

**The Serum parameter problem, and the fix.** Ableton only sees the Serum parameters that were added in Configure mode (127 here, and only some were exposed in your probes; filter cutoff was not among the 37 verified contracts). So Claude does not automate raw Serum knobs. Instead, the NL-to-Serum generator writes each preset with **Macros 1-4 already routed inside Serum** (1 = brightness: cutoff + wavetable position; 2 = motion: LFO rate/depth; 3 = width/detune; 4 = space: reverb/delay mix). Ableton then automates only 4 macros + track volume per track. Same 5 controls on every preset, every reel. Your own evidence marks `macro_field_value` as CAUSAL\_VERIFIED.

**Preset generation:** one text brief per track role per palette (e.g. "Kamadeva pluck: golden, bright attack, short decay, glassy, Macro 1 opens the filter"). Generated once per story, stored in `presets/`, listed in the bible, reused every reel: consistency comes from reusing presets, not regenerating.

**Fallback if a Serum load fails:** Ableton's own Wavetable or Drift on that track (every parameter visible to the MCP), logged in `build_log.json`, never silent.

**What not to do (from your own probes):** do not inject Serum state into `.als` XML (it loaded once, then reopen failed with "Unknown Compound Stream Type"); do not expect a render tool (none exists; `render_to_file` was found to be fabricated); do not run the set without checking the connection first (`get_session_info`).

## Render and Gate D hand-off

Ableton's API has no offline export, so the render is one of two routes, chosen per run:

| Route | How | Time for 70 s | Use when |
| --- | --- | --- | --- |
| A, owner export (default) | Owner presses File > Export Audio, 0:00 to 70.000 s, 48 kHz, 24-bit WAV, master + stems | About 1 minute | Every final score |
| B, MCP record | `record_section` records in real time to a temporary track | About 75 s plus setup | Drafts while the owner is away |

After render, `check_score.py` trims or pads to exactly 3,360,000 samples (70.0 s at 48 kHz), adds 5 ms fades, and refuses a file that differs by more than one frame (42 ms) before trimming.

Files written:

- `stories/kalika_puran_bhag1/<pack>/audio/score/reel1/score_reel1.wav` (master) and `stems/*.wav` (one per track role, for later remixing).
- `audio/bgm_manifest.json`: `{"tracks": [{"track_id": "SCORE-KALIKA-R1", "path": "audio/score/reel1/score_reel1.wav", "license_type": "original", "bpm": 128, "lufs": <measured>}]}`. The score is rendered at about -20 LUFS integrated; Gate D's `loudnorm` brings the full mix to -16.
- `story.json`: `"bgm": {"enabled": true, "manifest": ...}`.

Gate D then mixes as it already does: voice, H3 effects (ducked ratio 4), score (ducked ratio 6), and runs `check_music_presence`. The only Gate D code change is making `post.py` pass the manifest track instead of `None`.

Per Rule 14 the WAVs and `.als` go to Google Drive, not the public repo; the repo keeps `cue_sheet.json`, `score_plan.json`, `notes/*.json`, preset briefs and the manifest.

## Quality checks and owner gates

Three owner gates, each a listen or a read, never a technical approval:

1. **M0, music bible** (once per story): you approve tonic, raga per character, motif sketches as short MIDI auditions.
2. **M1, spotting plan** (per reel): a one-page table of what each shot does musically, plus a 70 s MIDI-only audition rendered with Ableton stock sounds.
3. **M2, final listen** (per reel): the score under the joined reel with H3 effects and voice, from a Gate D preview mix.

Automatic checks in `check_score.py`, all must pass before M2:

| Check | Pass rule |
| --- | --- |
| Length | Exactly 70.000 s at 48 kHz after trim; raw render within 42 ms |
| Peaks | True peak at or below -3 dBTP on the score alone |
| Cuts | Every planned swell/downbeat within 1 frame (42 ms) of its cut, measured by onset detection |
| Hits | Stingers within 1 frame of `impact_frames` times |
| Voice windows | Score energy 1-4 kHz at least 10 dB lower inside `time_range` windows than outside |
| Presence | Gate D `check_music_presence` passes (median 15-21.5 dB under voice, floor above -50 dB) |
| Silence | No gap over 0.45 s anywhere except the planned reversal drop-outs |
| Continuity | Every motif used matches the bible (pitch classes), every preset is from `presets/` |

Reviews follow your rules: build agents' code reviewed by Super VL + Xing before first live use (Rules 5, 6, 12), and every step logged in `PROJECT_LOG.md` + `blot.md` (Rules 1, 17, 24).

## What to take from the Cinescope opinion

The Cinescope plan is written for scoring footage you know nothing about. Your pipeline already knows every cut, line and emotion exactly, so its whole analysis department is unneeded.

| Idea | Verdict | Reason |
| --- | --- | --- |
| Series music bible, leitmotifs, continuity across episodes | Take | Core of this plan (bible section) |
| Spotting sheet approved before composing | Take | Gate M1 |
| Human gates between stages | Take | M0, M1, M2 |
| Ableton has no bounce API, render is real time | Take | Matches your probe 16.5.57; render section |
| Stems + cue sheet + project in the delivery | Take | Stems kept on Drive |
| PySceneDetect shot detection | Reject | `shots.json` gives cuts to the frame; detection could only add error |
| faster-whisper transcription | Reject | Voice `time_range` is in the pack, the same for en/hi/mr |
| Install CanArslanDev/ableton-live-mcp | Reject for now | You already have an extended MCP; two Remote Scripts compete for the control surface. Revisit only if yours lacks a tool you need |
| Separate D:\\CinescopeAI workspace | Reject | Keep it in Anime-Studio under `audio/score/` so `shots.json` stays the one source of truth (Rule 22: must work for any story) |
| 13-group orchestral template, Spitfire/Kontakt | Later | 7 roles cover a 70 s underscore; orchestral libraries can replace a Serum role later without changing the plan |
| Music Composition Skills plugin | Optional | Not verified by me; useful for harmony checks only |

## Build order and first test

First test target: **Kalika Puran Reel 1, SHOT-001 to SHOT-003 (0-18 s)**. Those 18 s contain a reveal, an expression-beat, a suspense shot, a hard cut and an act change, so they test every rule before a full 70 s run. Kaliya Mardan has no committed pack on any branch, so it cannot be the first test.

Build on `merge-v4-universal-2026-11-07` (it has Gate D, `post.py` and the Kalika pack); note the Colab runner exists only on `v4-architecture`, which does not matter for audio.

- [ ] 1\. Connection check: Claude Code lists your extended MCP's tools from `D:\ableton` and your NL-to-Serum tool's interface; I write the two adapters against the real names. No Live set changed.
- [x] 2\. Done 2026-11-09: `score/cue_sheet.py` + 32 tests on the Kalika pack (pure Python, no Ableton), reviewed independently and re-checked.
- [ ] 3\. `music_bible.json` for Kalika + motif auditions as `.mid`. Owner gate M0.
- [ ] 4\. Claude Code follows the score-reel skill (`.claude/skills/score-reel/SKILL.md`, written) and writes `score_plan.json` for 0-18 s. `score/plan_check.py` (the next build step) must pass. Owner gate M1.
- [ ] 5\. `write_notes.py`: notes JSON + `.mid`; check against cue sheet (cuts on beats, voice windows clear).
- [ ] 6\. Generate 7 presets with Macros 1-4 routed; load each once in Live to confirm.
- [ ] 7\. `ableton_build.py` builds the 18 s set in clock mode (60 BPM, MARKERS track); owner exports; `check_score.py` passes.
- [ ] 8\. Gate D preview with the real SHOT-001..003 clips and voice. Owner gate M2.
- [ ] 9\. Full 70 s Reel 1, same steps 4-8.
- [ ] 10\. `post.py` BGM wiring + tests, then Reel 2 reusing the bible and presets (the continuity test).

Steps 2, 4, 5 and the checks can be built by Haiku agents and reviewed by Super VL + Xing, as with `h3/`. Steps 1, 6, 7 need your PC with Live open.

## Open items for the owner

- [ ] Link your PC to this chat (open it in the Claude desktop app) or push the extended Ableton MCP from `D:\ableton` to GitHub, so the adapters use real tool names.
- [ ] Name the NL-to-Serum preset tool: its folder or repo, and what it outputs (`.SerumPreset` file, or a state loaded straight into Live).
- [ ] Live's API cannot write locators, song tempo or time signature (web check 2026-11-09), so the plan uses clock mode and a MARKERS track. Please confirm your MCP exposes clip automation envelopes, and that Serum's Macros 1-4 respond to them.
- [ ] Confirm the audio decision: main's frozen plan (2026-11-06) says music removed, and the v4 handoff (2026-11-07) says one optional BGM track. This plan assumes the 11-07 rule, with the score as your own music.
- [ ] Confirm the modern style, home key D minor, the character themes, and whether to keep a light Indian colour or none (gate M0).
- [ ] Reel length: `story_plan.json` says Reel 1 `reel_seconds` 68.0 while the 10 shots sum to 70.0 s. The score follows the shots (70.0) unless you say otherwise.

## Sources

All read on 2026-11-09 from your repos: `satviksangamkar11/Anime-Studio` branches main, `v4-architecture-2026-11-07`, `merge-v4-universal-2026-11-07` (`research/AUDIO_PLAN_FROZEN_2026-11-06.md`, `h3/assemble_reel.py`, `h3/gate_d_audio.py`, `h3/shot_table_spec.py`, `core/core.json`, `blot.md` Rules 14 and 27-31, `stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/`); `satviksangamkar11/ableton-claude-final` branch `step-4-q-authority-audit` (`CLAUDE.md`, `ROADMAP.md`, `serum2/compiler/mcp_intent.py`, `experiments/16_5_57_probe/`, `experiments/CAPABILITY_FRONTIER_FREEZE.json`).
