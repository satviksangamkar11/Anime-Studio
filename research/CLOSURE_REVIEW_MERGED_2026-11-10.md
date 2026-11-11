# Closure review, merged (2026-11-10)

Reviewers: Codex Luna medium (read-only, whole tree), Haiku medium (read-only, whole tree), Nemotron Super (16 per-module calls, 11 first came back empty, retried; timeline_lock_core still empty), Nemotron Ultra (16 per-module calls, 3 empty: timeline_lock_core, caption_fields, plate_composite). Raw outputs: NEMOTRON_*_REVIEW_16_TOOLS_*.md; Codex and Haiku reports were in the chat.

## Headline
No problem of the 46 is closed by the 16 tools yet: nothing calls them (only script_inspect imports script_hook and script_pacing). All reviewers agree. Tests: 569 collected = handout; nobody has re-run them in this review.

## A. Closed earlier by a rule or manual step (no code guard, can come back)
7 measured speech, 10 voice claims, 17 style pack, 18 writer limits, 19 other stories, 22 full-size review, 23 Flow agents, 31 clips saved per shot, 34 GPU identity, 38 music order, 41 captions (rule 51).

## B. Tool exists, nothing calls it (PARTLY)
2 3 4 5 6 8 (timeline_lock) | 9 (preflight key hook; no voice-account check) | 12 13 (wav_contract) | 14 (caption_fields) | 15 (script_inspect) | 20 (plate_composite, image_gates) | 26 27 28 30 (prompt_hygiene) | 29 32 33 45 (runner_safety.preflight, stop_decision) | 37 (clip_gates; no frame extractor) | 44 46 (precommit_check; no hook installed).

## C. Open: no tool and no code guard
1 (order is a rule only; no gate refuses a render before the voice lock) | 11 pronunciation check | 16 source-fidelity check | 21 (image_gates needs a cast/posture extractor that does not exist) | 24 watermark tool | 25 image_gates before Gate B | 35 one-shot proof gate | 36 two code trees (build_h3_batch.py, run_colab_batch.py absent here) | 39 cue sheet reads the lock | 40 SFX plan-ahead policy | 42 second loudness target | 43 log/doc conflicts.

## D. Fastest way to close B and C (grouped by file to edit)
- W-A timeline: build_vo_tracks.py, voice_cast.py, build_final_reel.py call timeline_lock_core.plan_shots then timeline_lock_io.write_lock; verify_lock before any voice or render work; cue sheet reads frames_for. Closes 1 (gate), 2 3 4 5 6 8 39. Include the script file in the lock inputs.
- W-B voice_cast.py: write wav_name(shot,lang), require_wav on export, delete the atempo call (line ~310), add voice-account check and a pronunciation_ok flag per hard-name line. Closes 9 11 12 13.
- W-C build_final_reel.py: caption_fields.resolve_caption instead of CAPTION_FIXES (lines ~95, 155-168); delete the second loudness target (keep -16). Closes 14 42.
- W-D prompts: prompt_hygiene.clean_prompt in v4_to_h3.py (line ~160 still emits ", with ") and compile_h3_sing8.py; mouth sentence needs the owner decision (28). Closes 26 27 28 30.
- W-E runner (after J8 port, problem 36): run_colab_batch.py calls runner_safety.preflight (script size 3 MB, URLs, disk, wheel), clip_verified after each shot, stop_decision, refuses --go without a one-shot proof file. Closes 29 30 31 32 33 35 45. DRY-RUN only until the owner says go.
- W-F writer gate: run script_inspect after the writer; add a source-line match script. Closes 15 16.
- W-G keyframes: call image_gates.background_lock and plate_composite.plan; write the cast/posture extractor; run before Gate B. Closes 20 21 25.
- W-H clip QA: write a frame extractor that feeds clip_gates.verdict. Closes 37.
- W-I git: .githooks/pre-commit running precommit_check (fix the binary-file case first); remove the wrapper hiding failing tests in pre-push. Closes 44 46.
- W-J docs: reconcile blot rule 41 vs shot 7, caption rule numbered 46 and 51, stale NOW block; 43. Owner: 24 (watermark tool), 40 (SFX policy).

## E. Bugs to fix BEFORE wiring (confirmed by running or reading the code)
1. shot_router default route S vs shot_mode refusing S unless SHOT_MODE_S_ALLOW=1: every plain shot would raise in the batch (Haiku B1). Needs the owner flag decision plus a cross-module test.
2. script_hook: a first shot with no spoken line skips H2-H5 and can score 100; missing t / start_s default to 0.0 (hook) but raise KeyError (pacing); non-dict events crash. script_pacing: length 60-75 s is documented as not a hard fail but fails the pass; nested keys unvalidated. script_inspect: accepts any non-empty JSON, ValueError ends as traceback with exit 1.
3. runner_safety: production clip check accepts any large .mp4 in the shot folder; injected path skips the folder-containment check; can_stop([]) raises (verified).
4. precommit_check: any staged binary (png, wav, mp4) fails as "not UTF-8" so a wired hook blocks every binary commit; DEL (0x7f) not matched; NUL byte case returns no finding (verified).
5. clip_gates (verified by running): best_cut_frame([nan,0.5,0.9]) returns 0; new_object_classes with after_frame=-1 reports every class; verdict({"end":{}}) passes because of end.get("pass", True).
6. shot_router: missing id/features raise KeyError, not RouterError.
7. timeline_lock_io: input hash uses file name + bytes, not the full path; load_lock does not check total_seconds or duplicate shot ids.
8. wav_contract: Windows reserved names (CON, NUL, COM1) not refused. plate_composite: slow per-pixel loops (performance only). image_gates: float images assumed 0..255 (locked by a test, document it). runner_safety: HEAD requests can give false 405 failures.

## F. Claims rejected after checking
- Codex: "Hindi/Marathi constants in script_hook are corrupted": false (0 replacement characters, 248 Devanagari characters).
- Super: audio_edge fade divisor wrong: false (hand-checked ramp reaches exactly 0.0 at the edge sample).
- Super/Ultra: "? counts as stakes" in script_hook: the hook rule allows a question as an opener; not a bug.
- shot_router "more than 3 moving people" reason on a crowd shot with <=3 people: cosmetic text only.

## G. Handout lines to correct
J3 does not replace CAPTION_FIXES yet; J6 does not stop any session (run_colab_batch absent); J5 (SE default) and J14 (else S) conflict (E1); J10 "real WAV" tests use synthetic sine/burst WAVs; test comments in test_audio_edge, test_plate_composite, test_runner_safety still say FAIL-until-fixed although the code passes.
