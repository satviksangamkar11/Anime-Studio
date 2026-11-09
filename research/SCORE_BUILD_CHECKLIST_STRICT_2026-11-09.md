# SCORE BUILD: STRICT CHECKLIST WITH EXPECTED RESULTS (2026-11-09)
Scope: background music ONLY, backend ONLY (no ui/), real reel 1 (Kalika Puran bhag 1, 10 shots, 70.0 s, 3,360,000 samples at 48 kHz).
Spec = `.claude/skills/score-reel/SKILL.md` (do not redesign). Reuse owner tools (AbletonMCP extended, serum-mcp); never rebuild them.
Tick `[x]` ONLY when the expected result was READ by the coordinator (not taken from an agent report). Each tick gets a PROJECT_LOG line.
Agents: Haiku MEDIUM. One writer per file. Coder and reviewer are different agents. No agent commits, pushes, touches ui/, render files, voices/, shots.json, or calls Colab/Flow/Opus/paid APIs.
Log command every agent must use after every step: `echo "$(date +%m-%d\ %H:%M) | <agent id> | <TYPE> | <files> | <result>" >> "D:/aai work/anime_studio/PROJECT_LOG.md"`

## G0 Done already (verified by coordinator)
- [x] G0.1 cue sheet in repo; `python -m pytest score -q` -> 34 passed.
- [x] G0.2 real pack cue sheet: 70.0 s, 3,360,000 samples, 0 warnings; with FINAL_TEXT_v2 windows voice coverage 90%, 8 gaps, `retention.last_speech_end_s` 69.8.
- [x] G0.3 draft `music_bible.json` + 3 mp3 auditions sent (gate M0 = OWNER decision, pending).

## A. score/plan_check.py + score/tests/test_plan_check.py (agent PC)
API: `check_plan(plan, cue_sheet, bible) -> {"ok","errors":[{"code","where","message"}],"warnings":[],"stats":{}}`; CLI `python -m score.plan_check --plan P --cue-sheet C --bible B`, exit 0 ok / 1 errors / 2 unreadable. Never raises on malformed input.
Error codes, each with a test that FAILS the rule and a test that passes it (frame = 1/24 s, tolerance 1/24 + 1e-9):
- [ ] A1 PLAN_COVERAGE: sections contiguous, start 0.0, last end == cue total_s, no gap, no overlap.
- [ ] A2 TEMPO_NOT_CANDIDATE: section bpm must be in the cue sheet tempo_candidates of that section's act (any genre list). Section act must exist.
- [ ] A3 TEMPO_CHANGE_OFF_ACT: bpm or genre may change between sections only at a boundary that is a cue-sheet act_change cut.
- [ ] A4 CUT_MISSING / CUT_OFF_FRAME: every cue-sheet cut has a plan `cuts` entry within 1 frame, with a transition from {none, theme_handover, bed_continues, reverse_swell_to_cut, swell_to_cut, key_colour_on_downbeat, act_change}; hard_cut cuts need reverse_swell_to_cut or swell_to_cut (or key_colour_on_downbeat); same-act non-hard cuts must not use act_change.
- [ ] A5 IMPACT_NO_HIT: every cue-sheet impact has a plan event type "hit" within 1 frame (HIT_OFF_FRAME otherwise); `in_voice` impacts need `band: "low"` (HIT_BRIGHT_UNDER_VOICE); any hit inside the voice union needs band low.
- [ ] A6 DROPOUT_BAD: `preceded_by_dropout_s` must be in (0, 0.45]; impact hits and god theme entries REQUIRE it (DROPOUT_MISSING).
- [ ] A7 BUSY_IN_VOICE: events whose role is busy in the bible (track_roles busy true) must not start inside a voice-union window unless they are low-band hits. A busy role listed in a section roles_on needs `"voice_gated": true` on that section (the note writer then mutes it inside voice windows) else BUSY_UNGATED.
- [ ] A8 GOD_THEME_RULE: theme_entry of a god theme (SHIVA, BRAHMA, KALI, VISHNU) needs a drop-out, `feel: "half"`, and no event type "drop" within 1.0 s (GOD_DROP).
- [ ] A9 REHOOK_WINDOW: `rehook_at_s` inside cue retention.rehook_window_s. A10 PEAK: exactly one `peak_at_s`, and it is an event or section boundary time. 
- [ ] A11 LOGO: event sonic_logo at_s == 0.0. A12 END_STING: event end_sting inside retention.end_hook_window_s and at_s >= retention.last_speech_end_s (else band low), tail ("tail_s") <= 0.45.
- [ ] A13 BIBLE_REF: every theme in events and every role in sections/events exists in the bible themes/track_roles; presets referenced exist in bible presets.
- [ ] A14 shape: schema_version 1, required keys, numbers finite; fuzz test (>= 100 malformed plans) never raises.
- [ ] A15 Expected run: a hand-built GOOD plan for the real Kalika cue sheet (fixture in tests) -> ok True; each rule's BAD variant -> exactly that code.
Verify (coordinator): `python -m pytest score/tests/test_plan_check.py -q` all pass, count >= 40; `ast.parse` ok.

## B. Gate D bridge: score/gate_d_bridge.py + score/tests/test_gate_d_bridge.py (agent GB). Reads h3/gate_d_audio.py, does NOT edit it.
- [ ] B1 `check_score_stem(path, cue_sheet) -> report`: ffprobe/ffmpeg read; sample rate 48000, length == cue total_samples (+-1 frame 2000 samples; error STEM_LENGTH), 24-bit or float wav accepted, mp3 rejected for final (STEM_FORMAT).
- [ ] B2 MONO_SAFE: below 200 Hz the side (L-R) energy must be <= -20 dB under mid, else STEM_BASS_NOT_MONO; folded mono loses <= 3 dB RMS vs stereo (STEM_MONO_LOSS).
- [ ] B3 NO_SFX_LEAK is NOT checkable; skip. LOUDNESS: integrated LUFS measured with ffmpeg ebur128, written to the manifest.
- [ ] B4 `write_bgm_manifest(stem_path, cue_sheet, out_json, bpm, lufs)` -> file accepted by `h3.gate_d_audio.validate_bgm_manifest` (ok True): one track {track_id "kp-r1-score", path, license_type "original_score", bpm, lufs}.
- [ ] B5 `presence_levels(voice_wav, stem_wav, win_s=0.5)` -> (voice_db, bgm_db) lists, fed to `gate_d_audio.check_music_presence` (15 to 21.5 dB under voice median, p95 floor -50). Tests on synthetic numpy wavs: a stem 18 dB under voice passes, 5 dB under fails BGM_MEDIAN_OUT_OF_BAND, silence fails BGM_SILENT_FLOOR.
- [ ] B6 `plan_language_outputs` accepts the manifest path unchanged: a test calls `gate_d_audio._bgm_track(manifest_path)` and gets (no errors, stem path).
- [ ] B7 CLI `python -m score.gate_d_bridge --cue-sheet C --stem S --voice V --out-manifest M` prints report, exit 0/1/2.
Verify: `python -m pytest score/tests/test_gate_d_bridge.py h3/tests/test_gate_d_audio.py -q` all pass.

## C. Note writer: score/note_writer.py + score/tests/test_note_writer.py (agent NW). Pure; no Ableton.
- [ ] C1 `write_notes(plan, cue_sheet, bible) -> {"tracks":{role:[{"t_s","dur_s","pitch","vel"}]}, "markers":[{"t_s","name"}], "automation":[...]}`; deterministic (same input -> same output; seeded, no random without seed).
- [ ] C2 Every note time is absolute reel seconds in [0, total_s]; no note ends after total_s; every busy-role note in a `voice_gated` section is dropped or moved out of voice-union windows (test: zero overlap).
- [ ] C3 Events are on the frame: hit/downbeat notes within 1 frame of event at_s; drop-out region (at_s - preceded_by_dropout_s .. at_s) holds NO notes on any role (test).
- [ ] C4 One marker per shot (10) named with the shot id and hook_type, at the shot start.
- [ ] C5 `write_midi(tracks, path)` writes a standard type-1 .mid in clock mode (60 BPM, 480 ppq, 1 beat = 1 s); read back with a tiny parser in the test: note count and times match C1 (+-1 tick). No new dependency: write the bytes by hand.
- [ ] C6 Low-band rule: hits under voice use pitch <= D3 (MIDI <= 50) only (test).
Verify: pytest file passes, count >= 15.

## D. Ableton build recipe: score/ableton_build.py + score/tests/test_ableton_build.py (agent AB). Pure; emits JSON, never calls Ableton.
FIRST read the owner docs and server (do not rebuild): `D:\ableton claude\CLAUDE.md`, `D:\ableton claude final best\README.md`, `PLAYBOOK_2026-09-25.md`, `D:\ableton claude final best\serum2\ableton\ableton_mcp_extended\server.py` (tool names and argument names).
- [ ] D1 `build_recipe(notes, plan, bible) -> [{"tool","args"}...]` using ONLY tool names that exist in server.py (test reads server.py text and asserts each tool name appears there; skip with reason if the path is absent).
- [ ] D2 Order: get_session_info, set_tempo 60 (clock mode), one create_serum_track / create_midi_track per role, load preset, one create_arrangement_midi_clip + add_notes_to_clip per role, manage_clip_automation for macros 1-4 and volume, MARKERS track with 10 empty named clips, cue points.
- [ ] D3 Clip start/length in beats == seconds (60 BPM). No .als edits anywhere. Each Serum track gets Macros 1-4 routed (brightness, motion, width, space) as set_device_parameter steps.
- [ ] D4 `serum_briefs(bible, plan) -> {role: text brief}` one per role for serum-mcp generate_preset (read its docs in `D:\ableton claude final best\vendor\serum-mcp`); text only, no call.
Verify: pytest passes, count >= 12; recipe JSON for the Kalika fixture is < 5 MB and valid JSON.

## E. Review and close (coordinator + one Haiku MEDIUM reviewer per A-D, different from the coder)
- [ ] E1 Reviewer reads the file + tests + this checklist; reports findings with file:line. Coordinator triages EVERY finding against the file (accept/reject with reason, logged), coder fixes, ONE re-review (blot rule 8). Ends when a round has no HIGH finding.
- [ ] E2 Coordinator runs the full suites and READS counts: score, h3, core (director only if a shared file changed). No regression vs core 422, h3 624, director 815.
- [ ] E3 Real run: cue sheet -> (after owner gate M1) plan -> `plan_check` ok on the real reel 1 plan -> note_writer -> recipe. Until M1 these use the fixture plan only.
- [ ] E4 Log line per tick; NOW block overwritten; checklist copy in `research/` updated.

## OWNER GATES (the only stops)
M0 bible (pending) -> M1 plan -> M2 preview with picture + H3 effects + voices. No Ableton writes before M1.

## C2. Note writer round 2 (after review NWR, 19 findings; owner order: no shortcuts) - agent NW
Expected results; each needs a test that FAILS on the old code and a non-vacuous assertion (exact notes/times/pitches or exact error code):
- [ ] C2.1 H1/M6/L6 god theme role: a theme_entry whose bible theme has roles uses a role from them; otherwise error THEME_ROLE_NOT_IN_BIBLE. Truncation of any theme note by a voice window or a drop-out gives a warning THEME_TRUNCATED (count). SHIVA at 48.0 on role brass keeps all 4 notes (D2 A2 C3 D3).
- [ ] C2.2 H2 hard_cut/swell: every cut with a swell transition writes the 1 s pad swell ending exactly on the cut frame, hard_cut at 48.0 included (also swell_to_cut).
- [ ] C2.3 H3 phone bass (rule 11): bass role also plays the root one octave+fifth up (mid harmonic, 200-1000 Hz, velocity 60% of the root), sustained like the root, never gated.
- [ ] C2.4 H4 re-hook: rehook_at_s must carry a MAIN theme_entry (error REHOOK_NO_THEME otherwise); MAIN notes land at that time; peak_at_s gets the section's highest intensity: its intensity>=every other section (error PEAK_NOT_HIGHEST).
- [ ] C2.5 H5 hook_type per shot (hook_type read from the cue sheet): reveal = only drone+pad in the first part of the shot, full roles from the shot's theme_entry second (REVEAL_NO_ENTRY error if none); expression-beat = pad chord only, no ostinato/drums, theme fragments only in voice gaps; suspense = ostinato whose pitches never start on D on a strong beat, density rising linearly from density_per_beat[0] to [1] across the shot; reversal = silence on all roles during the section's drop-out, the hit on the turn, then pad one octave lower plus Eb (darker) to the shot end; closing_hook = unresolved Dsus2 chord (D E A) pad, sparse low pulse every 2 beats under the last line, end sting as a Dsus2 cluster (low notes only if inside voice), tail <= 0.45 s.
- [ ] C2.6 M1/M2 density is per REAL beat (bpm of the section) regardless of feel; upper bound used (rising). M3 end sting is a chord. M4 marker names use closing_hook / opening_hook when set (SHOT-010 marker says closing). M5 bible quiet_moment range: only drone and MUNIS-theme pad notes inside it.
- [ ] C2.7 M7 section gaps/overlaps and cue cuts without a plan cut give errors (SECTION_GAP, SECTION_OVERLAP, CUT_MISSING), not ok True. L4 unhashable feel/role gives SECTION_FEEL / ROLE_BAD. L5 busy flags come from bible track_roles (brass is NOT busy).
- [ ] C2.8 M8/L1-L3 tests: no vacuous assertions (len(lead) < 4 removed); zero-overlap tests use roles that actually have notes; malformed tests assert the error code.
- [ ] C2.9 Result: tests >= 70 in test_note_writer.py; reel-1 fixture plan uses SHIVA on brass; second independent review (new reviewer) finds no HIGH.
