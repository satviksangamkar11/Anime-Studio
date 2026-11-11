# GAP REGISTER (2026-11-11): every gap, its closing card, its status. Nothing is closed until the card's wiring is done AND the reviewer confirmed the checklist.

Status key: OPEN = nothing done; ADVANCED = a tool/fix exists, nothing calls it yet (Step 0 gives this for most); CLOSED = wired, tested, reviewer-confirmed; RULE = closed by rule/owner decision only.
Rule: this register is updated after every card; a gap leaves the register only as CLOSED or RULE.

## 1. The 46 problems -> closing cards (from the Opus plan, part P3). ALL are currently OPEN or ADVANCED; none CLOSED.
## Per-problem closure map (all parts)

Abbreviations for jobs in other parts (described by file + function):
- **LOCKW**: lock writer CLI + timeline_lock_core.plan_shots (snap flag, trims from v4_to_h3._plan_handles, needed_sec input, versioned lock).
- **VOX**: voice_cast.py run/export (voices check, pilot.json, require_wav, no atempo).
- **VOT**: build_vo_tracks.py (reads the lock, MAX_TEMPO 1.0).
- **RUN**: run_colab_batch.py after D-J8 (runner_safety preflight 7 MB, URLs/wheel, G4, clip_verified, stop, canary proof, render_ready).
- **PROMPT**: v4_to_h3:160 + compile_h3_sing8 + schema_and_linter.
- **J8**: git port.

`[rule/owner]` marks problems closed only by a rule or an owner decision.

| # | Closing card(s) | Single proving check |
|---|---|---|
| 1 | X-13 + RUN (`--go` needs render_ready.json) | `test_plan_pipeline_no_lock_blocks` |
| 2 | LOCKW + VOT | VOT test: every lock shot packs with max_tempo 1.0 without raising |
| 3 | LOCKW, VOT, X-15, X-19, X-04 | `test_three_consumers_same_offsets` (X-24) |
| 4 | LOCKW (trims from `_plan_handles`) | LOCKW test: `_plan_handles` problems == [] for every lock shot |
| 5 | LOCKW (snap flag, error_ms) `[owner: accept ±½ frame]` | LOCKW test: max error_ms ≤ 20.84 on a 128/176 BPM plan |
| 6 | X-12, X-13, X-15, X-19 | `test_same_gate_d_verdict` (X-24) |
| 7 | LOCKW (WAVs in lock inputs) | changing one WAV byte raises StaleLockError (`test_stale_lock_blocks_all_three`) |
| 8 | LOCKW (script in inputs) + X-13 | `test_stale_script_byte_blocks` |
| 9 | VOX (GET /v1/voices before reserve) | VOX test: missing voice → SystemExit, 0 POST |
| 10 | `[rule]` (Granth library copied) | none needed (rule 35) |
| 11 | VOX pilot.json + pronunciation_ok `[owner listens]` | VOX test: unflagged hard-name line is a problem |
| 12 | VOX require_wav | VOX test: a .wav holding MP3 bytes raises |
| 13 | VOX (no atempo, audio_edge before the lock) | VOX test: exported duration == trimmed duration |
| 14 | X-16 | `test_unapproved_caption_diff_raises` + `test_no_caption_fixes_symbol` |
| 15 | X-07 (writer_gate.json) + VOX (refuse without PASS) | `test_writer_gate_written_and_blocks_on_lint` |
| 16 | X-08 `[owner defines pass]` | `test_cast_without_ref_fails` |
| 17 | `[rule 19]` | none needed (existing STYLE-01/02 tests) |
| 18 | X-06, X-07 | `test_repair_only_named_shots` |
| 19 | X-15 (required --reel) + X-24 (reel-2 fixture) | `test_reel_required` |
| 20 | X-09, X-10 | `test_b_is_edit_of_a` + `test_background_moved_fails` |
| 21 | X-02, X-03, X-10, X-11 `[owner: manual review vs detector]` | `test_missing_sage_fails` |
| 22 | `[rule 25]` + X-10 (full_size required) | `test_not_full_size_refused` |
| 23 | `[rule 26]` + X-09 (complete job) | `test_job_keys_match_build_jobs` |
| 24 | `[owner: watermark tool]`; then flow/scripts/remove_sparkle.py / lama_inpaint.py exit non-zero on no input (other part) | owner decision recorded |
| 25 | X-10, X-11, X-13 | `test_missing_gate_b_blocks` |
| 26 | PROMPT `[owner: SX-01]` | PROMPT test: cue "a veil snaps" gives no "with a veil" |
| 27 | X-02 (L08), X-05, PROMPT (check_sound_cue in the compiler) | `test_serpents_hiss_fails` |
| 28 | PROMPT `[owner: mouth wording]`; X-05 supplies speaking | `test_cast_lock_equals_prompt_args` + the PROMPT mouth test |
| 29 | RUN (max_script_mb 7) + X-23 (R28) | RUN test: an 11.3 MB script fails preflight |
| 30 | PROMPT (single `\n`) + J8 (builder raise survives) | PROMPT test: no compiled prompt contains `"\n\n"` |
| 31 | `[rule 29]` + RUN clip_verified(expected_frames) | RUN test: truncated mp4 is not verified |
| 32 | RUN (stop on ALL DONE, argv lists) | RUN test: fake colab, all verified → stop issued |
| 33 | RUN (preflight URLs + wheel sha) | RUN test: fake HEAD 504 → failure |
| 34 | RUN (refuse non-G4; survives J8) | RUN test: "A100" refused |
| 35 | RUN (canary proof) + X-13 (render_ready) | `test_render_ready_written_only_when_clean` |
| 36 | J8 | both files exist in the merge tree and their suites pass |
| 37 | X-14, X-15 (+ D-CLIP) | `test_snake_not_known_blocks` |
| 38 | `[rules 44, 48]` | none needed |
| 39 | X-19 (+ LOCKW bpm/snap/act) | `test_stale_wav_exit_2` |
| 40 | X-14, X-17, X-18 `[rule 50(6) decided]` | `test_bed_louder_than_voice_minus_22_fails` |
| 41 | `[rule 51]` + X-16 + X-23 | `test_export_probes_1080x1920` |
| 42 | X-20 `[owner confirms audition-only]` | `test_only_audition_constant_is_minus_14` |
| 43 | X-23 `[owner approves texts]` | the two blot.md copies are byte-identical |
| 44 | X-21, X-22 `[rule 20; partial]` | `test_precommit_blocks_staged_key` (a control character or syntax error blocks the same way) |
| 45 | X-17 (local free-space check) + RUN (min_free_gb) `[owner: Drive access, disk numbers]` | `test_low_disk_refused` |
| 46 | X-06, X-21, X-22 `[owner rotates keys]` | `test_elevenlabs_key_found` + `test_prepush_fails_on_failing_test` |

**Run order inside P3:**
- Wave 1, all parallel: X-01, X-06, X-08, X-12, X-20, X-21.
- Then X-02 and X-03.
- Then X-04, X-09, X-10, X-14, X-19, X-22.
- Then X-11, X-13, X-15.
- Then X-16, then X-17, then X-18.
- X-05 and X-07 run after their other-part collisions.
- Then X-24, then X-23.

Every card waits for the owner's go.


## 2. Follow-up items found while Step 0 was coded (each needs a card or a fix; none may be dropped)
F-01 S-07: KFI shots - mid / mid_frame are validated but not copied into the batch row (step 8 builds rows from it). Card: S-07b.
F-02 S-07: check_pixel_frames first branch message still says "nearest valid counts are None and 22" (22 is no longer valid); a test asserts the old wording. Card: S-07b.
F-03 S-01: LATTICE_CUT_BOUNDS (h3/schema_and_linter.py) covers n=6,7,8,10 only; middle shots up to n=18 have no bound check in plan_pixels. Card: S-01b (or step 5 spec).
F-04 S-13: read_wav_mono scales 1/32768, write_wav_mono 1/32767 - round trip off by ~4.6e-5 at full scale. Card: S-13b.
F-05 S-12: a pack row missing id / editorial_duration_sec / t0 still raises a raw KeyError and traceback (exit 1). Card: S-12b.
F-06 S-12: test_runs_from_repo_root passes without the sys.path insert it is meant to prove. Card: S-12b.
F-07 S-12: from_pack uses action_pose_expression of the first directive as "action" - owner/assistant to confirm.
F-08 S-08: expected_frames dict - an id absent from the dict raises ValueError but no test covers it; script_path only checked for existence. Card: S-08b.
F-09 S-14: non-finite SSIM branch has no test; four tests changed to uint8, one renamed (confirm intent kept).
F-10 S-15: hole_fraction non-ndarray refusal has no test.
F-11 S-16: owner_accept date only checked non-empty (should be YYYY-MM-DD); clip_qa.json writer/reader is a later card (X-14).
F-12 S-17: owner/date/unknown-key errors untested; waiver file name not enforced; wiring into build_final_reel is X-15.
F-13 S-09: main(staged=[...]) still reads working files; one finding per rule means an OpenRouter-style line gives two findings.
F-14 S-06/S-07/S-08/S-11/S-14/S-16/S-09: existing test assertions were changed or removed because the cards change behaviour - the reviewer must confirm each change keeps the original intent.
F-15 NEW REQUIREMENT (owner decision 7): the pipeline must take a WHOLE STORY, plan the reels itself, then run reel 1, 2, 3, 4 one after another. The Opus plan has no card for the story -> reel planner. Card to add: X-25.
F-16 Mouth wording (S-05) waits for the owner (research done).
F-17 Reviews pending: Nemotron Super on 15 cards; any BACK-TO-CODER lines become new rows here.
F-18 S-02 (timeline_lock_io v2): field names follow S-01 (trim_in_frame/trim_out_frame); combined hash stored as lock_sha256 (input_sha256 kept); write_lock also validates shots (not in card); start_frame must begin at 0 and be cumulative; diff_locks format "added"/"removed"; never-overwrite is check-then-write (race possible, not atomic); v1 locks are now refused (script_inspect --lock will raise on them, by design); 5 existing tests renamed/changed (version 1->2, failed-write test now expects TypeError on a new target). Card: S-02b if the reviewer wants atomic create.
F-15 UPDATE (owner 2026-11-11): the story -> reels planner is said to exist locally. Found: director/write_pack.py stage 1 produces the story block, story_plan.json and the episode list (episodes_from, --episodes / ONLY_EPISODES) and writer_prompts.py holds the stage prompts. DEFERRED by the owner ("we will deal with it later"): later check that it plans N reels from a whole story and that every reel then runs the same pipeline; no card X-25 for now.
F-19 NEW (owner 2026-11-11): AUTOMATED WATERMARK REMOVAL AT EVERY IMAGE FINALISATION (replaces the manual workaround, decision D6). Card X-26: when a keyframe/plate/reference image is finalised (2K download filed from Flow), the pipeline automatically (1) keeps the original byte-identical in final/_original_with_watermark, (2) runs flow/scripts/remove_sparkle.py (alpha inversion), (3) verifies there is no stamp residue left (template match on the bottom-right window; and a pixel-difference check that nothing outside the window changed), (4) falls back to flow/scripts/lama_inpaint.py when residue remains, (5) writes watermark_record.json per image (method, residue score, sha256 before/after), (6) REFUSES with a clear error when the input folder is empty or an image fails both methods (no quiet exit), (7) is called by the keyframe flow BEFORE keyframe_gate (X-10) so no image reaches a gate or a render with a watermark. Existing known failures to cover: detector missed 4 of 20 images, ghost stars inherited by edits (log 11-06..11-09, MISTAKES).
F-20 NEW (owner idea 2026-11-11): optional per-language retime of the rendered clip (picture speed +/- a few percent) as the FALLBACK when a language's voice does not fit the lock, instead of speeding the voice (voice atempo is removed, MAX_TEMPO 1.0). Needs a decision, see APPROVALS_NEEDED section E.
F-21 OPEN QUESTION to owner: "packaging scene 12" (dictated sentence about sound effects) not understood.
F-20 UPDATE (owner 2026-11-11, third message): the owner wants EACH LANGUAGE (en / hi / mr) to have its OWN video length matching its own voice, with the picture speed managed by a "dial" (per-language, per-shot retime). Design impact (not yet decided): per-language lock (edit_frames per language instead of the max), retime factor per shot stored in the lock and bounded, retime of picture (setpts) and of the clip's own sound (atempo) in build_final_reel, never of the voice, per-language clip-QA window, and the MUSIC problem: the score and cue sheet are snapped to one timeline (128/176 BPM beats), so shot lengths that differ per language shift the cuts against the music. Options and recommendation are in the owner message of 2026-11-11 (A: one master timeline + small dial; B: per-language timelines with per-language cue sheet/score). Needs the owner's choice before S-01b is written.

## 3. STATUS UPDATE 2026-11-11 (after the fix wave; 743 tests pass in 27 touched test files)
Fix wave jobs (coder Nemotron Super via the loop, reviewer Haiku medium; checklists/FXA..FXI.md, specs in loop_run_reel2/specs):
- F-01 CLOSED (FXA: KFI mid / mid_frame copied into the row, test). F-02 CLOSED (FXA + FXM2: message names real valid counts 107..345; docstring fixed; 2 old assertions updated by Haiku, owner-approved).
- F-03 OPEN (S-01b: lattice bound check for every n in plan_pixels; belongs to the lock rework that waits for the owner's A/B choice, F-20).
- F-04 CLOSED (FXB: writer scale 32768, round trip <= half LSB). F-05 CLOSED and F-06 CLOSED (FXC + FXJ: clean ValueError / exit 2 for incomplete pack rows, bool t0, non-dict directive/item, pack-row detection by pack keys; real test that the sys.path insert works from another folder; "invalid input" asserted).
- F-07 ACCEPTED (action = first directive's action_pose_expression; owner said the rest looks okay). F-08 CLOSED (FXD + FXK: script_path must be a file, one failure for a missing path, missing-id tests). F-09 CLOSED / F-10 CLOSED (FXI: tests for the NaN SSIM branch and hole_fraction refusals; note: a literal full-True mask makes background_lock raise "no comparable area", the tests use all-False masks). F-11 CLOSED (FXE + FXM1: YYYY-MM-DD real dates, imports at the top). F-12 CLOSED (FXF + FXM4: strict types/dates, tests for every error; waiver file name still not enforced -> X-15 wiring). F-13 CLOSED (FXG + FXM3: main() returns 1 with a message when git fails; staged= documented as working-tree list).
- Review findings fixed: S-10 _has_stakes no longer counts "?" (FXH + FXL tests).
- F-14 ACCEPTED (changing old tests is approved when behaviour changes; every change was reviewed).
- F-17 PARTLY: Haiku medium reviews of the 9 fix jobs + round two DONE; Haiku medium reviews of the 17 original Step 0 cards (S-01..S-17) still to run (Super reviews: DONE for S-03 S-09 S-10 S-11 S-12 S-14 S-15 S-17; Super/Ultra gave nothing or unreliable text for the rest).
- Still OPEN: F-15 (deferred), F-18 (S-02 judgement calls), F-19 (X-26 watermark), F-20/F-21 (owner choice), and all wiring waves W1..W7 (no problem of the 46 is CLOSED yet: nothing calls the tools).

## 4. ROUND 3: findings of the Haiku medium reviews of the 17 original Step 0 cards (2026-11-11 late)
Verdict: S-06 DONE, S-14 DONE, S-15 DONE (+ notes), S-17 DONE (+ notes); BACK-TO-CODER: S-01 S-02 S-03 S-04 S-05 S-07 S-08 S-09 S-10 S-11 S-12 S-13 S-16. Items (R3-xx), all to be fixed by Nemotron Super (modules + new test files) or a Haiku one-line edit (existing test files; the loop never edits an existing test file):
R3-01 S-01 timeline_lock_core.plan_pixels silently truncates when len(ids) != len(edit_frames) (zip). Checklist said 21 keys, card lists 20.
R3-02 S-02 timeline_lock_io: never-overwrite is check-then-write (use os.link + unlink); load_lock accepts inputs []; no test that v1 locks are refused; no negative tests for end_frame_position / error_ms.
R3-03 S-03 wav_contract: "con .hi" passes the reserved-name check (strip trailing spaces first); refuse Windows-illegal characters < > | ? * ".
R3-04 S-04 caption_fields.manifest_lines keeps ok=False rows (voice_cast writes a failed row into the manifest): skip them, with a test.
R3-05 S-05 prompt_hygiene: MOUTH_STAY_RE misses the old wordings "keeps their lips closed" / "lips remain closed" so two lip sentences can remain; checklist evidence about D3 wrong (D3 is now owner-approved).
R3-06 S-06 shot_router: unhashable shot id raises TypeError, not RouterError; checklist test name wrong.
R3-07 S-07 h3/tests/test_shot_mode.py:366 calls the renamed test_22_is_valid() in __main__ (NameError when run directly); frame_row never copies h3_mode (step 8 gap, noted); test_shot_mode_fx.py is outside the card (kept).
R3-08 S-08 runner_safety.stop_decision: all_done=False returns before the missing-id check (check ids first); test_runner_safety_checks.py:63 over 120 chars; part_paths=() default lets a 12 MB script through (step 9 must pass part_paths).
R3-09 S-09 precommit_check: git diff --cached without -z mis-handles non-ASCII paths (use -z); line 104 over 120; secret_scan split("\n") change documented as intended (form-feed line numbers); K-OPENAI duplicate finding for sk-or-v1 keys accepted.
R3-10 S-10 script_hook: older key-check messages do not name the shot id; ENGLISH_NOUNS differs from the J9a snapshot (traced: it comes from the loop's J9a rounds, not from the S-10 coder).
R3-11 S-11 script_pacing: unlisted P2 change (event must also be <= last duration) -> revert to >= payoff_start; seconds_override not validated (negative / non-finite); two test names say "problem" but now test warnings; checklist B7 wrong; long test lines.
R3-12 S-12 script_inspect: string track -> AttributeError (must be ValueError naming the row); lock ids not matching the script (both directions) silently ignored -> ValueError; line 185 over 120; the thin-shot test asserts only two strings.
R3-13 S-13 audio_edge: failed write leaves path.tmp; write_wav scale 32768 deviates from the card text (justified by FXB; OWNER to accept); checklist evidence row 5 wrong.
R3-14 S-16 clip_gates: missing tail["flag"] silently counts as no spike; flicker None/NaN gives TypeError or a silent pass; the 13 clip_tools gate tests that lived in the committed test_clip_gates.py were lost and are RESTORED as director/test_clip_tools_gates.py (13 pass).
R3-15 S-17 waivers: directory path -> IsADirectoryError (use isfile); [0-9] regex; test_empty_reason_allowed weakens the audit trail -> require a non-empty reason (assistant decision); checklist S-17 has ~50 stray unticked rows from another card.
R3-16 S-15 plate_composite: _remove_small is O(components x frame) (bincount); _dilate_square must cast px to int; S-14 image_gates.dilate cost comment.
F-21 CLOSED (owner 2026-11-11): the dictated sentence "packaging scene 12 / packing sync well" was a dictation mistake; ignore.

## 5. STATUS UPDATE 2026-11-11 (end of Step 0 fixes): all R3-01..R3-16 coded, 810 tests pass in 43 touched test files
CLOSED by round 3 (Super coder, Haiku medium reviewer, loop + small Haiku test edits): R3-01 (plan_pixels length), R3-02 (atomic lock write with os.link, empty inputs refused on load, v1 locks refused, negative/non-finite error_ms refused, tests), R3-03 (reserved names with trailing space, Windows-illegal chars), R3-04 (failed voice rows skipped), R3-05 (all old lip sentences removed; D3 evidence corrected), R3-06 (non-str shot id -> RouterError), R3-07 (test_shot_mode.py __main__ call), R3-08 (stop_decision checks ids first), R3-09 (git diff -z), R3-10 (shot id in script_hook errors; ENGLISH_NOUNS traced to the loop rounds), R3-11 (P2 bound reverted, override validated, test names), R3-12 (script_inspect bad types, lock/script id mismatch), R3-13 (audio writer tmp cleanup; 32768 accepted by owner), R3-14 (clip_gates flag/flicker checks; 13 clip_tools tests restored), R3-15 (waivers isfile, ASCII digits, non-empty reason), R3-16 (plate_composite bincount, int px).
Mistakes caught by the full suite and fixed before they stayed: R3B diff_locks corruption (new_by_id[new_by_id]) and R3N bincount IndexError, plus earlier FXC/FXJ format_report .get() change. Lesson: every Super module is diffed against its backup and the whole suite is run before it stays.
STILL OPEN: S-01b (lock with per-language retime dial, option A, dial +-6%), F-03 (lattice bound check, part of S-01b), F-15 (planner, deferred), F-18, F-19 (X-26 watermark), and all wiring waves W1..W7. Owner rule 2026-11-11: NO reel 2 script / shot / scene writing until the pipeline is done and its tests pass.
S-01b CLOSED (data model): lock v2 holds optional per-shot per-language retime factors (0.94..1.06), retime_for(), suggest_retime(); the master shot lengths are unchanged (option A). NOTE for the assembly step (W6): with option A the cut points are identical in all languages (music stays on the beat); the factor is a duration multiplier whose application inside a shot is decided there; it cannot remove a quiet tail by shortening shots (only option B does).
F-03 covered: plan_pixels hand-checked cases (middle 258 -> pf 311, 259 raises) are tested in S-01; no extra bound card.
WAVE 1 STARTED (blocking sheet): tests first (Haiku observer: director/test_blocking.py, director/test_blocking_lint.py), then Super writes director/blocking.py + director/blocking_lint.py with the tests frozen. Cards X-01 X-02 X-03. Writer guard X-06/X-07, source_check X-08 next. Reel 2 content stays BLOCKED until the pipeline is complete and tested.
F-22 BLOCKING KNOBS (owner asked for evidence, Haiku research done: research/BLOCKING_KNOBS_RESEARCH_2026-11-11.md): no official numbers exist; the four knobs stay UNCALIBRATED. Suggested changes (low confidence, need a real render to confirm): MAX_SPEED_H 0.25 would reject a normal walk (0.43-0.52 FH/s in a medium-full shot) -> 0.5 for walking, 0.25 only for a slow class; POSE_CHANGE_MIN_SEC 1.0 sit<->stand, 1.5 kneel/lie, 2.0 lying<->standing; CONT_TOL 0.05 plus pose and facing match; MAX_MOVING 3 provisional. Frozen tests currently assume 0.25 / 1.0 / 0.05 / 3. DECISION left open until the canary render; constants live at the top of director/blocking_lint.py.
F-23 "TURNING AN OBJECT": three meanings (turnaround sheet workflow, timed subject turn in the prompt, camera orbit). The sheet's facing enum covers start/end state only. Proposed card X-01b: optional per-character turn {deg, sec} in blocking/1 + lint L10 (|deg| >= 90 needs sec >= 1.0; |deg| >= 180 needs >= 2.0; facing change without a turn record fails) + the change list says "turn <deg> degrees <direction>"; camera orbit stays in the camera block. Needs owner OK (schema extension).

## 6. BLOCKING WAVE review (Haiku medium, 2026-11-11): all five cards BACK-TO-CODER, 57 tests passed. Items B-01..B-20:
blocking.py: B-01 pace error code BLK-S17 collides with the mismatch code (use BLK-S19); B-02 NaN/inf arc_sec and writer_seconds pass (finite check); B-03 pose keys facing/pose/mouth_moves not required; B-04 camera without move key passes; B-05 duplicate cast ids; B-06 entries/exits naming a char not in cast, or without char; B-07 speaks 'yes', arms 2.5/True/<2 pass; B-08 change_list props appears/disappears inverted (A = start image, B = end image); B-09 change_list turn branch drops the mouth open/closed lines (continue); B-10 unused _POSE_CHANGE_MIN_SEC.
blocking_lint.py: B-11 L08 crashes on a None cast name or prop class; B-12 lock shot with edit_frames 0 silently skips the speed check; B-13 lint(None) returns [] silently, non-dict sheets; B-14 member with missing start/end raises KeyError/TypeError; B-15 entry/exit char not in cast silent in L09; B-16 L10 timing checks only run when the facing changes (turn 180 deg in 0.5 s with unchanged facing accepted) and L10(a) suppressed by an invalid turn dict; B-17 unused import timeline_lock_io; B-18 lock seconds read directly (accepted, same result as frames_for); B-19 shot missing from the lock falls back to writer_seconds (accepted, documented); B-20 pose-change L02/L03 split (accepted: the frozen test allows both).
Plan: tests first by a Haiku observer (director/test_blocking_r2.py, test_blocking_lint_r2.py), then Super fixes blocking.py then blocking_lint.py.
BLOCKING FIXES B-01..B-17 CLOSED (Super, tests first by a Haiku observer: test_blocking_r2.py 15 + test_blocking_lint_r2.py 13; blocking.py passed on run 2, blocking_lint.py needed 4 runs because the specs had to carry the exact code: geometry guard, valid-turn definition, no facing gate; one run was lost to a Windows folder lock from my shell). 90 blocking tests pass (17+13+15+17+10+13... see log). B-18/19/20 accepted as documented. A final short Haiku re-check of the wave is the last step before wave 1 moves on to the writer guard and source check.
WAVE 1 progress: X-06 writer_guard (cap in cents via WRITER_CAP_CENTS, fail-closed, limit/auth/billing detection from the stream, usage log, validate_pack) and X-08 source_check (line ids, citations C1-C3, different-model review, report with hashes, --citations-only) DONE (Super first-run passes, 32 tests); .gitignore has ledgers/. Still wave 1: X-07 (write_pack wiring: guard each stage, targeted repair, writer gate). Haiku review of X-06/X-08 + blocking re-check pending.

## 7. WRITER GUARD + SOURCE CHECK review (Haiku medium, hostile probes): both BACK-TO-CODER; blocking wave re-check green (90 passed, 16 hostile sheets all rejected cleanly) except 1 crash. Items W-01..W-20:
writer_guard: W-01 call_fn raising leaves the reservation OPEN (blocks every later reserve) and loses the usage row; W-02 empty stream / stream without a result line passes silently; W-03 negative cost lowers committed spend (cap bypass); W-04 NaN/inf/string cost raises after reserve with the reservation left open; W-05 est_cents negative/zero/float/bool accepted; W-06 the env cap WRITER_CAP_CENTS is never the cap (the ledger's own cap governs) and garbage values raise ValueError instead of SystemExit; W-07 LEDGERS constant unused; W-08 cli_ready does not wrap OSError; W-09 validate_pack crashes on non-dict rows / missing id, silently passes string directives and duplicate ids; W-10 dead try/except and a sys.path side effect.
source_check: W-11 UnboundLocalError for a cast member with an unknown ref; W-12 non-str / list refs, refs given as a string; W-13 non-dict cast members / rows; W-14 CRLF and unicode line numbering (use splitlines); W-15 the reviewer never receives the source text (cited_lines always empty); W-16 unknown verdicts pass; W-17 an empty review passes (decision by the assistant: every cast member needs at least one verdict); W-18 unused import re.
blocking_lint: W-19 a string x/y/scale crashes lint with TypeError instead of an L01 problem.
Plan: frozen tests by a Haiku observer (test_writer_guard_r2.py, test_source_check_r2.py, test_blocking_lint_r3.py), then Super fixes the three modules.
- W-04 build_vo_tracks reads lock: DONE 2026-11-11 (11 tests)


## 8. Status at 11-11 22:03 (cards; source of truth = research/card_results)
CLOSED at tool level: S-01..S-17; X-01..X-23; X-26; W-01, W-02, W-03, W-04, W-05, W-06, W-08, W-09, W-11 (49 of 54).
PARTIAL: W-07 (D1 owner), X-16 (rule 51 + voice manifest not built).
IN PROGRESS: W-12 (editorial_by_lang shim), X-24 (end-to-end offline test).
CONDITIONAL / NOT BUILT: W-10 (soft-end handler patch; owner D4 + paid canary).
REVIEWS: Dots + Luna done for 14 cards, findings fixed for X-09 X-10 X-11 X-13 X-14 X-15 X-20 X-21 X-22 W-01 W-02; running for W-03 W-09 X-04 X-12 X-19 X-26 W-11; still to start: X-05..X-18 re-check, W-12, X-24; then the final cross-review of this register.
