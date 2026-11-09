# MUSIC PHASE: background score for Anime Studio reels (checklist, 2026-11-09)

Owner: build the BACKGROUND SCORE (music only) for every reel; Kalika Puran reel 1 first. Owner's spec = `reel score/SKILL.md`
(12 rules, copied to `.claude/skills/score-reel/SKILL.md`). Target tree: `D:\aai work\anime_studio_merge`
(branch merge-v4-universal-2026-11-07). Worker: the "Anime studio music producer" session, with Haiku MEDIUM sub-agents
(coder + independent reviewer, one writer per file set). Log every step in `D:\aai work\anime_studio\PROJECT_LOG.md` (blot.md format).

## SCOPE (owner correction 2026-11-09 12:50, overrides anything above it)
- BACKGROUND SCORE / BACKGROUND MUSIC ONLY. No sound effects (H3 makes them), no voice work, no mixing of voices.
- BACKEND ONLY, wired into the pipeline. DO NOT TOUCH the UI (`ui/`, any wizard or page): the owner does the UI later.
- The REAL reel 1 (Kalika Puran bhag 1, 10 shots, 70 s), not demos. The owner already built the skill and the Ableton tools precisely:
  FOLLOW `.claude/skills/score-reel/SKILL.md` step by step and COMPLETE each step; do not redesign it, do not invent extra stops.
  The only stops are the owner gates written in that skill (M0 bible, M1 plan, M2 preview).
- Use the owner's existing tools, read their docs first, never rebuild them:
  - Ableton control: the AbletonMCP server (extended), source `D:\ableton claude final best\serum2\ableton\ableton_mcp_extended\` (server.py, serum_loader.py, plugin_aliases.py);
    tools include get_session_info, create_midi_track, create_serum_track, create_arrangement_midi_clip, add_notes_to_clip, manage_clip_automation, set_device_parameter, set_arrangement_clip_property, cue points.
  - Serum presets: the vendored serum-mcp (`D:\ableton claude final best\vendor\serum-mcp`, generate_preset / edit_preset from a text brief); project docs `D:\ableton claude\CLAUDE.md`, `D:\ableton claude final best\README.md`, `PLAYBOOK_2026-09-25.md`.
- PIPELINE WIRING (backend): find how Gate D takes music (`h3/gate_d_audio.py`, `h3/assemble_reel.py`, `h3/voice_manifest.py`, `core/`), and add a backend entry so the finished score stem enters Gate D with the skill's own mix limits (duck ratio 6, score 15 to 21.5 dB under voice, mono-safe bass). Tests for it. Nothing in `ui/`.

## Status at start (verified 2026-11-09 12:40)
- Built (in Downloads/reel score, NOT yet in the repo): `cue_sheet.py` (step 1), `test_cue_sheet.py` (32 tests), `SKILL.md`, `__init__.py`.
- Not built: `music_bible.json` (step 2), `score/plan_check.py` (step 4), note writer (step 5), `check_score` (step 8).
- Reel 1 picture: shots 1-6, 8, 10 rendered 11-08; shots 7 and 9 are being re-rendered by the render session (shot 9 done, shot 7 in progress).
  Frame counts and shot lengths do not change, so the cue sheet clock is stable.
- Voice: 54 clips (en/hi/mr) exist; REAL audio windows are in
  `D:\aai work\flow_outputs\anime_kalika_puran_bhag1\voices\pack_opus_high_20261108_v4_deva\FINAL_TEXT_v2.json` (start_s, window_s). Not mixed yet.

## Do NOT touch (the render session works there)
`anime_studio\director\run_colab_batch.py`, `build_h3_batch.py`, `colab_batches\`, `flow_outputs\...\rework79`, `...\voices`, any Colab/Flow call,
`stories\kalika_puran_bhag1\pack_*\shots.json` (read only). No push, no commit without the owner. No Opus unless asked.

## Phase 0: integrate what exists (no new design)
- [x] 0.1 Copy into `anime_studio_merge`: `score/__init__.py`, `score/cue_sheet.py`, `score/tests/test_cue_sheet.py` (+ `score/tests/__init__.py` if the other test folders have one), `.claude/skills/score-reel/SKILL.md`.
- [x] 0.2 `python -m pytest score -q` (use `python`, not `python -I`: packages live in user site). READ the output yourself. Expect 32 pass.
- [x] 0.3 Run the CLI on the real pack: `python -m score.cue_sheet --shots stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/shots.json --episode 1 --out stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/score/ep1/cue_sheet.json`. Expect 70.0 s, 3,360,000 samples; report every warning.
- [x] 0.4 Run the core/h3/director suites to prove nothing else broke (log counts; compare with the 1881 pass in your log).
- [x] 0.5 The 24 BACKFILL lines of `PROJECT_LOG_lines_score_2026-11-09.md` are already appended to the live log by the render session (11-09 12:4x). Verify with grep, do not duplicate.
- [x] 0.6 Voice windows: make `voice.union` read the REAL windows from `voices/.../FINAL_TEXT_v2.json` when present (blot RULE 39), fall back to shots.json time_range. Add tests. Re-run 0.3 and compare voice coverage (was 83%).

## Phase 1: music bible (gate M0, owner decides, do not invent)
- [x] 1.1 Draft `stories/kalika_puran_bhag1/music_bible.json`: home key, sonic logo, main theme, character themes (Kamadeva playful, Brahma, Shiva reverence, Sandhya, sages), signature sounds, track roles, presets, style (modern hybrid / electronic experiment), emotion templates.
- [x] 1.2 One-page table for the owner + 3 short stock-sound MIDI auditions as REAL mp3 (ID3, libmp3lame 128k mono; check with ffprobe format_name=mp3, MISTAKES V4) so the owner can hear them on a phone.
- [ ] 1.3 STOP. Owner approves or changes (gate M0).

## Phase 2: plan checker (Haiku medium coder, Haiku medium reviewer)
- [ ] 2.1 `score/plan_check.py` exactly as SKILL.md "The checker enforces" (tempo only at act changes, cue-sheet BPMs, every cut has a transition, hits within 1 frame, `band: low` under voice, drop-outs <= 0.45 s, busy roles silent in voice windows, god theme = drop-out + half feel, re-hook in window, one peak, sonic logo at 0, end sting in window, themes/presets in the bible, plan covers 0..total_s) + tests incl. fuzz.
- [ ] 2.2 Independent review (Haiku medium, another agent) then fix, then re-review until clean (blot rule 5). Triage every finding against the file; reviewers are advisory.

## Phase 3: reel 1 plan (gate M1)
- [ ] 3.1 `score_plan.json` v1 for reel 1 from cue sheet + bible; one plain `why` per section. Run `plan_check`; fix errors, never weaken a rule.
- [ ] 3.2 One-page table + MIDI audition (mp3) for the owner. STOP at gate M1.

## Phase 4: after M1 only (ask the owner first, every time)
- [ ] 4.1 Note writer (plan -> notes per role + .mid), with tests.
- [ ] 4.2 Serum preset briefs (one text brief per role, Macros 1-4 routed).
- [ ] 4.3 Ableton build through the owner's Ableton MCP in clock mode (60 BPM, 1 beat = 1 s): `get_session_info` first; never write into .als files; MARKERS track.
- [ ] 4.4 `check_score` + Gate D preview with picture + H3 effects + the 3 voice tracks (gate M2).
- [ ] 4.5 Learn: approved plan -> `score_examples/`; new emotion templates -> bible.

## Working rules (from MISTAKES_AND_LESSONS.md)
- Code with backslashes: Edit tool, then `ast.parse`. Never a python heredoc (P1, 9 times).
- Read test output yourself; verify every agent report against the file (P9, Q8). Log after the result is read; a correction is a new FIX line.
- Haiku MEDIUM for coder and reviewer agents (owner order 2026-11-09); free NVIDIA models for extra review (OpenRouter key is expired); max one writer per file set.
- Report to the owner in short English, one checklist, what is verified and what is not.
