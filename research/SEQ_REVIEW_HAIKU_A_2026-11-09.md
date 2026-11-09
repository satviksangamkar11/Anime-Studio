# Sequence review, reel 1 (Kalika Puran bhag 1), Haiku A, 2026-11-09

Scope: order of pipeline steps (story -> writer -> voice -> timeline -> keyframes -> H3 -> render -> QA -> assembly -> score -> mix -> captions). Facts come only from: blot.md, MISTAKES_AND_LESSONS.md (C, F, P, Q, V, W ids), docs/PIPELINE_AUDIT_2026-11-07.md, docs/AUDIT_2026-11-08_REEL1.md, research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md, research/VOICE_SYSTEM_DESIGN_2026-11-09.md, research/AUDIT_PLAN_FROZEN_2026-11-06.md (AUDIO_PLAN_FROZEN_2026-11-06.md), and the 615 FAIL/DECISION/OWNER/FIX lines of PROJECT_LOG.md (log times as MM-DD HH:MM where the line has a date; a few lines have only HH:MM). I did not run code, did not open the scripts, and did not check the media files. "Log" below means PROJECT_LOG.md.

## 1. The root order mistake in one paragraph

The picture was fixed before the sound. On 11-07 01:52 the owner chose "option A: render once (shared foley), ElevenLabs for en/hi/mr after render" (log 11-07 01:52, decision chain 01:47-01:53). The final reel 1 render then ran on Colab (attempt 6, started 11-09 01:34, log 454; 10 clips home, RULE 31). Voices were only approved on 11-09 02:42 (log 463) and the first paid voice batch committed 648 credits by 05:27 (log 491). Every later problem with voice fit, shot length, cue timing and captions follows from that one inversion. The owner's own correction came too late: "audio first, then video made to the audio length" was ordered on 11-09 05:09 (log 479), after the render existed.

## 2. PROBLEMS grouped by stage

### A. Story and source
- A1. Source fidelity is checked only by hash, not by meaning. SRC-01 ties story.json to SOURCE.md (AUDIT_2026-11-08 gap 5); "semantic fidelity is NOT automated". Root cause: no independent check stage. Evidence: MISTAKES Q11; audit gap 5. Cost: wrong beats reached the picture: staging of SHOT-007 and SHOT-009 (sages, Shiva) missing (MISTAKES V7, W7; RULE 36).
- A2. Kalika part 2 and the sacred text were added after the writer had started (log 11-07 22:13-22:15); the Opus run was restarted on the combined source, and a weekly Claude limit then blocked stage 2 from 11-08 06:24 to 11-12 (log 237, 239). Cost: about 25 USD more Opus (log 199-200), and the stage 2 answer lost to a CLI turn split (C8, RULE 23; 2.62 USD).

### B. Writer and pack gates
- B1. The writer's validator passed a reel that could not render. Audit 11-08 gap 2: 73 H3 timing, seam, mouth and sound lint errors on reel 1, after every writer gate had passed. Root cause: H3 timing checks were not in the writer's validator. Fixed later by fit_lattice (AUDIT_2026-11-08 gap 2). Cost: pixel frames grew about 20-30 percent (192 to 243 frames for an 8 s shot), i.e. more GPU time (AUDIT_2026-11-08).
- B2. Writer shot durations (time_range) were set before any clip or any voice length existed. Clip lengths turned out 158-243 frames (6.6-10.1 s) against editorial 5-8 s (RULE 42, RULE 39 wrong basis, MISTAKES W19).
- B3. Speech-rate check existed only as an estimate. SPEECH-01 (3.2 w/s en, 3.6 hi, 3.0 mr) was added on 11-08 (AUDIT gap 3), but RULE 38 / V9 measured 1.7-2.4 w/s for real slow voices, so 19 of 32 batch-1 clips overran (up to 2.6x). The estimate was not used as a gate before the render.

### C. Voice (text, cast, generation, fit)
- C1. Voice text was changed after the picture existed: 8 lines shortened on 11-09 12:47 (log 524, "7 shot-language groups cannot fit even with atempo 1.15"); RULE 42 names eight lines rewritten and regenerated (002-N hi, 003-D2 hi/mr, 005-D1 hi, 006-N en/hi/mr, 007-N mr). Cost: extra credits and a second voice pass.
- C2. Cast chosen before the account pre-flight. Log 11-09 04:03-04:36 chose the cast by ear; V6 then found 16 of 18 cast voices were not in the account (Starter: 10 slots), Hindi voices verified only on another model, rate-2.0 voices may cost double, and 9 Hindi lines over the limit. The fix (free pre-flight) came after the choice. Cost: blocked voice removal (log 11-09 05:54, permission classifier) and a stalled slot plan.
- C3. Hard names and Devanagari spelling checked after the voices were generated: spelling check of FINAL_TEXT_v2 by the owner on 11-09 18:40 (log 613), caption spelling fixes CAPTION_FIXES (RULE 51). The VOICE design (D5) asked for a pronunciation test before the full run; no record shows it ran first (V5: a preview is not a test).
- C4. Voice fit repaired by changing the basis of the window, not the source of the length: RULE 39 sized windows to the clip, then RULE 42 (editorial) made 14 of 54 lines wrong; editorial_by_lang (RULE 47) then extended shots at the END of each clip, using frames the render already produced. First build of v4 failed Gate D VO_OVERFLOW_ERROR on shots 5, 7, 8 (log 11-09 15:10). Cost: a repair stage plus a full rebuild.
- C5. The per-line measured length exists (fit_report.json, latest_ok, vo_tracks_report.json) but was produced after the render, so it could only repair, not size, the picture.

### D. Timeline (the missing stage)
- D1. No frozen timeline existed before the render. Three different clocks were in use: writer time_range, clip frames (70.8 s pixel), editorial (70.0 s) (AUDIT gap 4; RULE 47 "freeze it before music gate M1"). Frozen only on 11-09 (editorial_by_lang, 72.833 s = 1748 frames, HANDOFF section 2). Cost: two reel totals (70.0 s and 72.833 s) and rebuilt cue sheets.
- D2. Cue sheet built on the v3 lengths and then re-run after editorial changed (HANDOFF section 3: "The cue sheet ... was built on the v3 lengths: re-run"; log 11-09 15:20 CS3 applied editorial after the cue sheet existed).

### E. Keyframes (images)
- E1. Images were approved before the staging was checked against source. Gate B approved all 20 keyframes on 11-08 22:06 (log 438). Shots 007 and 009 then failed a source check: 009 "Brahma rises" vs seated in both keyframes; 007/009 prompts did not name the sages and Shiva who appear in the pictures (W7, V7, MISTAKES Q5). Result: 009 and 007 redone (RULE 36) after the render.
- E2. A and B keyframes of one shot were made as two separate generations (F2; shot 8: Brahma standing in A, seated in B; RULE 25; N4). Root cause: no start/end pairing check before the render; the render had to invent the change.
- E3. Keyframes were generated and approved from a pack whose H3 cut plan changed afterward (lattice fix on 11-08 12:10, boundary frames only after Gate B). The H3 author step needs the boundary PNGs (KF-06, PR-00), which exist only after Gate B (log 11-08 14:54 FAIL). Fix applied: the author step ignores image codes (log 14:54). So a check that needs the picture was disabled to get past the dependency, not run later.
- E4. Shot 7 and shot 9 were rendered from OLD keyframes while new keyframes existed (W5, dated 11-08 20:31/20:38 renders). Owner later decided shot 7 stays on the old-keyframe clip (log 11-09 13:01), while RULE 41 still says "shots 9 and 7 re-render". The rule and the decision disagree in the blot file.

### F. H3 authoring and compiled prompts
- F1. Sound cues named creatures and the model drew them. "serpents hiss softly" produced two cobras behind Brahma from frame 48 (Q1; log 11-09 02:50). Also bees, birdsong, thunder and fire words sit in other shots (log 02:50 note; log 12:4x 10:51 bee noun removed from shot 7). Root cause: no lint of sound words against the picture; SX-01 only checked that a sound word exists.
- F2. The render controller found SX-01 errors only after authoring (P7: 6 of 10 shots "not ready"; log 11-08 23:21: "dry run so far 4/10 shots ready"). Run `render_controller --dry-run` before authoring is the stated fix (P7), not yet a gate.
- F3. Compiled prompt was not read before the paid start. Log 11-09 03:01: "I read the full compiled prompt only AFTER starting". Defects found then: duplicated last sentence, "with the wind drops", "at seconds 7", pronoun clash (Q3; RULE 32). Also `with <cue>` glue from v4_to_h3.py line 153 still in the converter (W9, log 10:40).
- F4. Blank line in the H3 prompt: every shot failed in 10 seconds (MISTAKES C6; RULE 30(2); log 11-09 01:22 attempt 5). The live run found it, not a free check.

### G. Render (Colab)
- G1. Paid start before the free checks. Attempt 1 (11-09 00:16): 19.7 MB run.py never reached the VM; 13 min billed (C3, 1.68 units). Attempt 2: 11.3 MB, same hang (C4, 0.57 units). Rule R28 (prove the script within 3 minutes) came after this.
- G2. Render script and settings reviewed after the first GO attempts. Log 11-09 00:16: "STOP; review the script properly with all reviewers ... only then start"; GO was given at 00:48 (log 449) after reviews.
- G3. External URL unchecked before paid session. Attempts for S009 on 11-09 10:56, 11:05, 11:10, 11:47 (log 501-507): GitHub 504 on the chumpy wheel (`chumpy-0.71`), "4 failed pip attempts", then an orphan unnamed G4 at 10.05 units/hour that colab stop could not see (log 507). W10 says the free URL check "would have saved three paid sessions" (0.58 units, about 25 min). RULE 40 added after.
- G4. Session kept after failure and billed. W17: after "ALL DONE" the runner kept downloading and the G4 billed about 10 minutes at 10 units/h until stopped by hand. W16: `colab new` failed after creating the VM, leaving a stray session billing 10 units/h (about 1.16 units).
- G5. Runner error text lost: runner downloads only timeline.txt and gpu.csv; setup.log never reached the PC (W11; log 503). Failure cause hidden for two attempts.
- G6. Clip save: RULE 29 (each clip saved at its shot's end) was built after the first clip loss (C1; 2026-11-05 six clips lost). Correct in order, but late.
- G7. Shot-level one-shot test skipped: P8 "a one-shot run is the first real test" was not done before the full 10-shot batch; 4 failed starts followed (C3-C6).

### H. Clip QA
- H1. Clips judged from few frames: "I looked at 16 frames and said it looked good" (Q2), later "not five stills" (RULE 31/33). Missed SHOT-002 arms, SHOT-008 set morph. QA came after the render and could only trigger a re-render (2 units each).
- H2. Audio in the clip never measured (Q7): the H3 model's own sound track (AAC) was not checked for speech-like noise until the mix. It became the "model SFX as loud as the voice" problem (RULE 49(8)).

### I. Assembly and Gate D
- I1. Gate D checks ran last. VO_OVERFLOW_ERROR on 15:10 (C4), TIME-01 and the H-r4-1 raise (log 08:50 round), and script-level retention failures (W20: narration coverage 86% vs 90%, dead air to 1.5 s) appeared only at build. Owner waived these codes by order; they are still script-level findings, not build findings.
- I2. Gate D's own loudness target (-14 LUFS) conflicted with the rule (-16 LUFS, core.json) until a late owner decision (log 11-07 16:02). One source of truth was missing for a long time.

### J. Music
- J1. Style study read after the bible was drafted. The bible was written from SKILL.md only (log 11-09 13:13); the study arrived 13:50 (log 543); 11 direction errors found against the study (log 544); RULE 44 says "the study must be read in full before any bible or plan work".
- J2. Music built offline first, Ableton second. Code mix v4 to v6 (log 17:55-17:56), then Ableton: "the new score was never in Ableton" (log 606; 607). Owner rule 50: the reel mix is done in Ableton. Result: r1-r10 Ableton mixes after the code mix, r1-r4 overwritten (log 609).
- J3. Sample selection before the timeline freeze: stems built on v4 lengths; HANDOFF section 4 says the BGM slot is None until the manifest exists. Music timing had to be recomputed on the frozen timeline (RULE 47).

### K. Mix
- K1. Mix levels were not planned before the render. The model SFX were rendered at voice loudness (RULE 49(8): gaps -18.6 dBFS vs voice -18.4). The policy (script-cue hits only, beds 22 dB under voice) came after the mix (RULE 50(6)). The render prompt carried the SFX cues already.
- K2. Ableton mix r8-r10 were tuned by trial and error until the owner said to compute settings (log 610). Final: en voice-over median 20.6 dB, min 9.1 dB, 11.3 dB at 13.7 s (below the 12 dB target, accepted "to stop iterating", log 611).

### L. Captions
- L1. Captions were built last and redone three times. Default engine (34 px) judged "very bad" (log 533, 11-09 13:08; log 612, 18:37). Rule 46 then rule 51 (CAPTION_SPEC_v2). v3 handed over with the default captions (log 547), v7 -> v8 -> v8b after the Ableton mix. Caption text depends on final voice text and final timing, so every change to them burned a new reel.
- L2. Caption engine fork: `core/captions.py` (universal) and `h3/gate_d_audio.py` (V4) both existed (AUDIT 2026-11-07 point 6). Merge to one engine is not done.

### M. Process and logs (affects order control)
- M1. Log lines written before the result. Examples: "EDIT done" for a file that was blocked by the path guard (V1); "applied fixes" when the edit script failed (log 11-07 18:47); CV review said "written" but was not (log 19:12). RULE 24 now asks for a result read before the line.
- M2. Two code trees drifted: anime_studio and anime_studio_merge differ (W6). A fix in one tree is lost in the other.
- M3. Blot and CLAUDE.md contradict: CLAUDE.md said the Claude limit "ended 2026-11-12" (fixed log 02:25); RULE 41 vs log 531 on shot 7 (E4).

## 3. ORDER PROBLEMS (a step ran before the step it depends on)

| # | Step that ran first | Dependency that came later | Evidence | Cost |
|---|---|---|---|---|
| O1 | Colab picture render (attempt 6 started 11-09 01:34) | Voice audio: lengths decide each shot's length | log 11-07 01:52 (option A), log 454, log 463 (voice go 02:42), RULE 31, HANDOFF section 2 | the whole repair chain C4, RULE 42, RULE 47, cue sheet rebuild |
| O2 | Clip frame counts (set by the render and the H3 lattice) | Editorial shot length (what the reel actually shows) | RULE 42, RULE 47, MISTAKES W19 | 14 of 54 voice lines wrong basis; 8 lines rewritten |
| O3 | Render (paid) | Speech-rate measurement (w/s per voice) | AUDIT gap 3 (11-08), RULE 38, V9 | 19 of 32 batch-1 clips over slot |
| O4 | Voice text final (after render) | Text must fit slot before a paid run | log 11-09 12:47 (8 lines), RULE 42 | extra voice credits and a second regeneration |
| O5 | Keyframe approval (Gate B, 11-08 22:06) | Source check of staging per shot | W7, V7, Q5, RULE 36, log 11-09 10:40 triage | 007 and 009 redone; shot 7 kept old-keyframe clip |
| O6 | Authoring/lint of H3 shots | Boundary keyframe PNGs (exist only after Gate B) | log 11-08 14:54 FAIL (KF-06, PR-00) | check disabled instead of ordered |
| O7 | SHOT-008 paid render (v1 02:34, v2 02:59) | Compiled prompt read and sound-cue audit | log 11-09 02:50, 03:01; Q1; RULE 32 | two extra renders (about 1.2 units per re-render, Q1) |
| O8 | Paid Colab start for S009 (4 attempts) | Free URL pre-flight (curl the setup downloads) | log 501-507; W10; RULE 40 | about 0.58 units plus an orphan G4 (10 units/h) |
| O9 | Live `--go` attempt 1 (00:16, 19.7 MB script) | Script size and review (R28) | C3; log 447-449 | 1.68 units, 13 min |
| O10 | Live run attempt 5 (01:22) | Dry check for blank lines before a paid start | C6, P8, RULE 30(2) | about 0.9 units, 15 min |
| O11 | Cue sheet built on v3 lengths | Frozen editorial timeline (RULE 47, before M1) | HANDOFF section 3; log 11-09 15:20 | cue sheet re-run |
| O12 | Bible drafted from SKILL.md | Style study (RULE 44 "study first") | log 11-09 13:13 vs 13:50; log 544 | 11 direction errors fixed after M0 draft |
| O13 | Code music mix v4-v6 (17:55) | Ableton mix in the owner's Project (rule 50) | log 606, 607, 609 | r1-r4 overwritten; trial and error r8-r10 |
| O14 | Model SFX rendered at voice loudness | SFX level policy (sound cue audit, RULE 49(8)) | log RULE 50(6) | open problem at the end; reel "jumbled" |
| O15 | Captions burned into each reel (v3-v7) | Final caption style and final spelling | log 533, 612, 613; RULE 51 | three caption rebuilds, v8b |
| O16 | Voice cast chosen by ear (11-09 04:03-04:36) | Account pre-flight: slots, verified languages, rate, w/s | V6 (five blockers), log 496 | cast partly unusable; slot removal blocked |

## 4. Recommended STAGE SEQUENCE (with the file/contract and the gate)

Existing file names are kept; a file in the contract column is what the next stage may read.

| Stage | Does | Hands on (contract file) | Gate before next stage |
|---|---|---|---|
| S0 Source lock | SOURCE.md fixed; semantic fidelity check against source (reviewer pass, not hash) | `SOURCE.md` + `source_check.json` | fidelity pass; owner OK on any cut |
| S1 Writer text | Scenes, dialogue, narration in en/hi/mr; story gates; simple-language | `stage_1..5`, `shots.json` (text only, no time) | simple-language and easy-language check; no timing yet |
| S2 Voice pilot (paid, small) | One real line per voice per language (the hardest slot), plus hard names; measure seconds per character | `voices_cast.json` (ids verified in account), `pilot_measure.json` | every line fits slot at tempo <= 1.15, else shorten text now (before the run) |
| S3 Timeline freeze | editorial frames per shot = max over languages of measured line + margin, beat grid for music acts | `editorial_by_lang.json` (frozen, hash) | hash frozen; any later change = new plan and owner note |
| S4 Voice full run (paid, once, cap) | Generate every line once per language; job-key reuse | `voices/<lang>/SHOT-nnn.wav`, `vo_tracks_report.json`, ledger | Gate D VO fit against S3 frames: zero overflow by construction |
| S5 Keyframes | A and B of one shot (B as edit of A or the reverse); staging checked against script per shot | `keyframes/SHOT-nnn-A/B.png` at full size, `shots_progress` | full-size review; A/B side by side; source staging check per shot |
| S6 H3 author and lint | Author fields with S5 boundary PNGs present; lint timing, mouth, sound words (no creature nouns), prompt grammar and duplicates | `h3_story.json`, compiled prompts (read in full) | lint 0 errors incl. image codes; prompt read; `render_controller --dry-run` 10/10 |
| S7 Render pre-flight (free) | curl every setup URL from the PC; sha of wheels; script size under 12 MB; reviewers read script + prompts | `preflight.json` | all URLs 200; reviewers done; one-shot proof (SHOT-001) |
| S8 Render (paid) | One shot first, then the batch; each clip saved on its end | `clips/SHOT-nnn/` (frame count must equal S3 frames exactly) | per-clip check: frame count, end-frame vs keyframe B, flicker |
| S9 Clip QA | Frame scan every 6th frame plus full-size crops of figures and props; audio measured | `clip_qa.json` per shot | no extra creatures, set changes, arm counts ok; else re-render that shot only |
| S10 Assembly | Trim each clip to its S3 frames; voices to S3 start | `build_final_reel` inputs | Gate D checks (overflow zero, loudness source = core.json) |
| S11 Score (music) | Cue sheet built on S3 timeline; plan; samples; M1/M2 owner gates | `score/` cue sheet, BGM manifest | M1 plan on frozen timeline; M2 preview |
| S12 Mix | SFX cut to script hits; voice priority; Ableton mix on the stems; named renders | `renders/ableton_mix_<lang>_rN.wav` | voice-over vs bus measured (12 dB target or owner accepts) |
| S13 Captions | Spoken text as subtitles, word timings from S4; style frozen before S12; burn last | `captions/*.srt/.vtt`, burned reel | contact sheet on real frames; spelling check on FINAL_TEXT |
| S14 Delivery | Final reel per language; phone copy if over 30 MiB | `final_reel<n>_<lang>.mp4` | owner listen and look |

## 5. ARCHITECTURAL CHANGES, ranked by value

1. Freeze the timeline before any picture (S3 before S5/S8). This removes O1, O2, O11, the C4 repair, RULE 42/47 patches and the second caption and cue rebuilds. Largest value. Cost: one measured pilot (S2) and one editorial plan file.
2. Measure speech before text and before the render (S2 pilot per voice and language, with the measured seconds per character stored in the cast file). Replaces the 3.2 w/s estimate (SPEECH-01) that RULE 38 showed is wrong. Cost: a few dozen credits.
3. Dependency gates by hash, enforced in code: each stage refuses to run unless the upstream contract file exists with a matching hash (`editorial_by_lang`, boundary PNGs, `preflight.json`, read-stamp of compiled prompts). This turns O6 (check disabled) and O7 (render before read) into hard errors instead of notes.
4. Free pre-flight before every paid call, as one command: URL check of the setup, voice slot and verified-language check, key validity (OpenRouter 401 seen at log 11-09 10:36), prompt lint, one-shot plan. Covers O8, O9, O10, O16.
5. Sound and staging lint before authoring: a sound-word list with creature and object nouns banned from audio cues (F1), and a per-shot source check of who is on screen (E1, C-staging). Cheaper than a re-render (about 1-2 units each).
6. Single runner that never leaves a paid session without a status check: stop on ALL DONE, fetch setup logs into the status file, and list `colab sessions` at the end (G4, G5, W16, W17).
7. Music order: style study and bible approval before drafting (J1), code mix as a preview only, Ableton as the one mix location (J2, O13).
8. One caption engine and one code tree (L2, M2). Caption style frozen before the final mix (O15).
9. Automated frame scan as the first QA gate (H1, Q2), with a human look at full size for the flagged frames only.

## 6. Limits of this review
- Facts only from the seven files named above and the flagged log lines. I did not read the full 600 KB log, the code, or the media. The non-flagged log lines may hold further order facts.
- Log times in some lines have no date (for example "17:11" and "18:25"); I did not reorder them.
- Two places disagree in the blot file and need the owner: RULE 41 (re-render shot 7) against log 11-09 13:01 (shot 7 kept), and the caption rule number (46 vs 51).

## 7. SHORTEST FIX per problem (minimum change that removes the root cause; delete or reuse first, then build; verify)

Rule used: delete or reuse existing code first; the new piece is one gate or one contract file; each row names the check that proves it is closed. Ids match section 2.

| Id | SHORTEST FIX (delete / reuse first, then the minimum build) | How to verify it is closed |
|---|---|---|
| A1 | Reuse SRC-01 hash. Add one per-shot list of names and events in `source_check.json`, checked by one reviewer pass against SOURCE.md. | Plant a wrong name in a shot; the gate fails. |
| A2 | Freeze source_sha256 before stage 1 runs; reuse RULE 23 stream-json join. No new code. | Stage 1 refuses if SOURCE.md hash differs from story.json. |
| B1 | Call the existing H3 linter (lint_story) as a writer gate; delete the duplicate timing checks in the writer. | Known-bad reel fixture (73 errors) fails the writer. |
| B2 | Remove time_range as a writer output; take lengths from the S3 editorial file only. | Changing a voice length changes shot lengths only through the S3 rebuild. |
| B3 | Delete the SPEECH-01 estimate constants once the S2 pilot exists; the pilot sets words per second per voice. | A line over its slot is refused before S4. |
| C1 | Freeze the text per language (FINAL_TEXT file + hash) before S2; any change forces a new pilot. | Hash mismatch blocks S4. |
| C2 | Reuse voice_cast.py account listing as a pre-flight before the cast is written: slots, verified languages, rate. | A cast id not in the account is rejected at write time. |
| C3 | Add one pilot line per hard name to S2 (reuse the pilot call). | pilot_measure.json has one entry per hard name with a listener OK. |
| C4 | Set S3 frames first; delete the editorial_by_lang end-extension once S3 exists. | Fresh build reaches Gate D with zero overflow and no patch step. |
| C5 | Keep vo_tracks_report.json, but write it in S4 before S5 starts. | S5 refuses to start without it. |
| D1 | One clock: frames at 24 fps from S3. Delete the 70.0 s / 70.8 s duplicate totals. | check_pack, timeline and build report print one total. |
| D2 | Cue sheet stores the S3 hash; a changed S3 makes the cue sheet refuse until rebuilt. | Edit S3, run cue build: refused. |
| E1 | Add a per-shot staging check (who is on screen, against the script) before Gate B; reuse the per-second directives. | Planted missing character in a shot fails Gate B. |
| E2 | Make B an edit of A through the existing edit route (one chip, exact change list); review A and B side by side. | Pair checklist item present for every shot; no pair built as two independent generations. |
| E3 | Two lint passes: S6 without image codes first, then the image codes after Gate B. Reuse the existing author step. | Both passes run in the log; the second is not skipped. |
| E4 | Decide shot 7 once in blot (kept or re-rendered); delete the conflicting line. | grep blot for shot 7 shows one rule. |
| F1 | Reuse SFX_CUE_RE; add a ban list of creature and object nouns that appear in audio cues. | Fixture "serpents hiss" fails the lint. |
| F2 | Run render_controller --dry-run inside the writer gate, not after authoring. | Writer returns not-ready on the SX-01 fixture. |
| F3 | Add a compiled-prompt gate: no duplicate sentence, no "with <verb>" glue, a read stamp. | Fixture prompts with the Q3 defects fail. |
| F4 | Keep the blank-line collapse and raise; move it into the S7 free pre-flight. | Zero blank lines in the compiled batch before any --go. |
| G1 | S7 pre-flight: one-shot proof plus script size under 12 MB before any paid start. | 19.7 MB fixture refused with no session created. |
| G2 | The --go command refuses unless preflight.json lists every reviewer's pass. | --go without the review file is refused. |
| G3 | Free curl check of every setup URL (reuse the URL list) before colab new. | A URL returning 504 fails the check. |
| G4 | Runner stops the session on ALL DONE and lists colab sessions on exit. | Mocked RESULT.json with ALL DONE stops the session in the test. |
| G5 | Runner fetches setup.log into the status file. | Test shows the setup error text in the status file. |
| G6 | Keep fetch_ready (each clip saved at its shot's end). | Each clip file is over 50 KB at the end of a run. |
| G7 | Batch refuses to start unless the SHOT-001 one-shot proof exists. | Batch command without proof is refused. |
| H1 | Automatic frame scan (every 6th frame) counting figures against S5; human look only on flagged frames. | Planted extra figure is flagged. |
| H2 | Measure each clip's audio level and speech with ffprobe into clip_qa.json. | A silent fixture clip is flagged. |
| I1 | Run the Gate D overflow check on S3 frames at S4, not at build time. | Gate D passes at S4 before any assembly. |
| I2 | Delete Gate D's own loudness target; read the -16 LUFS value from core.json only. | grep finds no second loudness target. |
| J1 | Gate the bible on the style study file and its hash (RULE 44). | Bible step refuses without the study hash. |
| J2 | Ableton is the only final mix location; code writes stems only. Delete the code final mix path. | Final reel is built from an Ableton render only. |
| J3 | Build stems from S3 only; record the S3 hash in the stem manifest. | Changing S3 marks stems stale. |
| K1 | Put the SFX policy (script-cue hits only, beds 22 dB under voice) in the S5/S6 rules before the render. | Measured SFX in gaps is under the policy level. |
| K2 | One split measurement script; compute the settings once from it (RULE 50(4)); no blind tries. | One run reaches the 12 dB target or the owner accepts the number. |
| L1 | Freeze caption style and text before S12; burn captions only once, last. | One contact sheet check on real frames, then done. |
| L2 | Keep core/captions.py only; route Gate D's captions through it; delete the V4 caption writer. | grep finds one .ass writer. |
| M1 | Log gate: a DONE line needs the artifact path to exist; wrong lines become FIX lines. | Log check fails on a DONE line with a missing file. |
| M2 | One code tree: sync from the merge tree and delete the other copy's drifted code. | Diff between the two trees is empty. |
| M3 | Fix the single rule numbers (RULE 41 vs shot 7; caption 46 vs 51) in one blot file. | grep finds each rule number once. |
