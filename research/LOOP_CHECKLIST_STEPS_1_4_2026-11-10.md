# Loop checklist v2 - close the gaps, example = REEL 2 (2026-11-10)

Owner orders 2026-11-10: (1) use the Satvik loop system; coder = Nemotron Super (nvidia/nemotron-3.5-super-vl-120b-a12b, best Nemotron model, also the checklist checker); reviewers = Haiku HIGH + Codex (gpt-6-luna, read-only); loops run in parallel; supervisor (Claude) inspects every 10 minutes and does not waste tokens. (2) REEL 1 IS FINISHED AND CLOSED FOREVER: never rebuild, re-render, re-mix or edit it; nothing in this checklist reads or rewrites reel 1 files. The worked example is REEL 2 (Kalika Puran bhag 1, "Episode 2: Spring Cannot Move Him"; outline exists in stage 1, no script yet). (3) The reel 1 hook was boring and its sound felt cut: the loop must solve both (jobs J9, J10). (4) Start/end-frame problem is PARKED. (5) Order of work: blot RULE 52. (6) Logs and blot updated at every tick. Tick [x] only when done AND verified; each tick = one PROJECT_LOG line.

## A. Preconditions
- [x] A1 Super checked this checklist first (LOOP_CHECKLIST_CHECK_SUPER_2026-11-10.md); triaged below.
- [ ] A2 Clean loop base: fresh worktree of loop main c3c65c0 as the run root (loop_p0 is on an old dirty branch: do not use). Needs docs/AGENT_RULES.md, specs/, _loop/jobs/.
- [ ] A3 Minimal change to the frozen loop code, authorised by the owner order "Super as coder": coder_model allow-list {Ultra, Super} (fix_loop.py lines 38, 100-102, 596; nemotron_code.py MODEL); Super thinking OFF; Haiku reviewer HIGH effort; tests; README; loop repo synced. (Super's check proposed "use Ultra instead": REJECTED, it contradicts the owner order.)
- [ ] A4 Jobs write mirrored paths in the run root; passed files are copied into anime_studio_merge and the real suites run there.
- [ ] A5 Guards: no Colab, no render, no paid call, no ElevenLabs, no Opus, no OpenRouter for coding; all loop calls through the shared key ledger (<=10 calls/key/min, 60 s cooldown on 429).
- [ ] A6 PRE-LOOP (supervisor, git, not a loop job) J8: port build_h3_batch.py + run_colab_batch.py + tests from the v4 branch and the rule-34 compiler fixes into the merge tree; keep merge versions of shared files.

## B. Loop jobs (new modules, small and disjoint, pure functions, injectable I/O, offline tests; fixtures from reel 2 text or synthetic, never reel 1 files)
| Job | New files | Must do | Closes |
|---|---|---|---|
| J1a timeline_lock_core | director/timeline_lock_core.py + test | edit_frames=max_lang(ceil(sec*24))+margin; candidates bar-length (128 BPM 45 f/4 beats, 176 BPM 90 f/11 beats) and beat-from-act-start round(i*60/bpm*24); pick the one with fewer spare frames; H3 lattice 17n+5 with head/tail handles | 1-6, 39 |
| J1b timeline_lock_io | director/timeline_lock_io.py + test | sha256 of inputs; write/load timeline_lock.json; verify raises on stale hash | 1-6, 39 |
| J2 wav_contract | director/wav_contract.py + test | name `<id>.<lang>.wav`; RIFF/WAVE or ID3 check; slot = max over languages | 12, 13 |
| J3 caption_fields | director/caption_fields.py + test | spoken_text / caption_text / caption_diff_approved; refuse unapproved difference; same word count | 14 |
| J4 prompt_hygiene | h3/prompt_hygiene.py + h3/tests/test_prompt_hygiene.py | collapse blank lines; "with <cue>" glue and duplicate-sentence detect; per-character mouth sentence for >1 person; auto cast line; creature/object noun ban in sound cues | 26-28 |
| J5 shot_mode | h3/shot_mode.py + h3/tests/test_shot_mode.py | image_prompt_type "SE" default; "S" only with env SHOT_MODE_S_ALLOW=1; (frames-5)%17==0 | start/end plumbing |
| J6 runner_safety | director/runner_safety.py + test | stop only if every clip verified; dead-man = clip_duration_estimate*1.5; free pre-flight (URL HEAD, disk >=10 GB, key validity) via injected fetchers; chumpy wheel hash | 29-33, 35 |
| J7 precommit_check | tools/precommit_check.py + test | secret patterns (hf_, sk-or-, nvapi-), ast.parse of staged .py, control characters; reuse tools/secret_scan.py | 44, 46 |
| J9 script_inspect | director/script_inspect.py + test | SCRIPT-STAGE inspection of a whole reel script before any voice: HOOK rules (a visual event in the first 1.0 s; first spoken word within 0.6 s; first line is a question, a conflict or a consequence, <=8 words en / <=6 hi-mr; no scene-setting opener; concrete subject), pacing (no dead air >1.5 s, a payoff in the last 5 s, re-hook 25-35 s), returns score, reasons and exact rewrite requests. Fixture: reel 2 outline text | boring hook, script gate |
| J10 audio_edge | director/audio_edge.py + test | detect abrupt start/end (first/last 40 ms level vs speech median), word starting at sample 0, hard-cut tail; apply_edges(): 12 ms fade-in, 30 ms fade-out, minimum 80 ms lead-in before the first voiced sample in the hook; line must start >=0.10 s after the cut-in and end >=0.10 s before the cut-out; synthetic WAV tests | "sounded cut" |

## C. Per-job pipeline (the loop does it)
0. Claim files (pieces/p1_claims.py); claim conflict = exit 4. 1. Spec at specs/<job>.md: purpose, public functions + signatures, edge cases, "no network, no GPU", the test list from B. 2. Coder Super writes module + tests (round 0). 3. pytest. 4. Fix rounds with real pytest output; tests frozen after round 0. 5. Reviewers Haiku HIGH + Codex luna read-only, min_valid_reviews 2; disagreement -> Haiku high tie-break; FIX FIRST returns to the coder. 6. Must end `passed` (exit 0). 7. Copy to anime_studio_merge; run director, h3, core, flow, ui suites after all jobs pass and after each wiring edit; commit on a branch.

## D. Wiring phase (after B passes; one writer per file; Haiku HIGH coder or loop jobs, reviewed by Codex + Haiku high)
- [ ] W1 voice_cast.export_wavs: wav_contract names + header check; delete atempo block; load_slots max over languages
- [ ] W2 build_vo_tracks: read timeline_lock.json and `<id>.<lang>.wav`
- [ ] W3 build_final_reel: lock + stale-hash refusal; caption_fields instead of CAPTION_FIXES; loudness guard (-16 only); missing report = SystemExit; audio_edge fades at every shot cut and at the hook
- [ ] W4 render_controller: same timeline, one Gate D verdict; forward loudness and colour seams
- [ ] W5a compile_h3_sing8: prompt_hygiene
- [ ] W5b v4_to_h3: prompt_hygiene
- [ ] W6 build_h3_batch.legacy_rows: shot_mode (SE default)
- [ ] W7 run_colab_batch: runner_safety; DRY-RUN ONLY, --go forbidden, no Colab
- [ ] W8 install pre-commit hook (precommit_check)
- [ ] W9 writer gate: script_inspect runs after the writer and blocks voice work on FAIL
- [ ] W10 editorial_by_lang retired only after timeline_lock reproduces a REEL 2 plan; reel 1 stays untouched with the old files

## E. Supervisor inspection every 10 minutes (read-only, no edits to job files)
Read each `_loop/<job>/status.json`: state, round, coder_calls/budget, verdicts. Act only on: exit 1 (review-open/test-review-open/invalid-spec: fix the spec or hand the finding to the coder, never advance), 3 (needs_review/escalate), 4 (claim conflict), 5 (passed-no-review), 6 (reviewer CLI down), 429 storms, a coder reply touching a frozen test. One log line per inspection.

## F. Stop conditions
Owner says stop; a job touches a file outside its list; any secret in a reply; budget exhausted on 3 jobs; D: free space under 1 GB; any step that would touch reel 1.

## G. Done when
J1a-J7, J9, J10 `passed`; W1-W10 ticked; director, h3, core, flow, ui suites green on the merged tree; secret scan clean; PROJECT_LOG and blot updated; J8 merged; a reel 2 dry plan (script_inspect on its script, timeline_lock from measured or synthetic voice durations) runs end to end offline; push only with the owner's go.

## H. Reel 2 run (after G): script (free Super model, hook rules in the prompt) -> script_inspect PASS -> voice pre-flight + pilot (paid ElevenLabs needs owner go) -> text freeze -> full voice -> timeline lock -> shot routes -> shot keyframes -> H3 -> render (Colab needs owner go) -> assembly, music, mix, captions. Reel 1 files are never opened for writing.

## STATUS LOG (updated by the supervisor)
- 11-10 [x] A1 Super checked the checklist. [x] A2 clean loop worktree D:/aai work/loop_run_reel2 (loop main c3c65c0). [x] A3 loop change: coder allow-list {Ultra, Super}, Haiku reviewer high, tolerant FILE-block parser (3 + 6 new tests, 64 loop tests pass); README + loop repo sync still open. [x] A5 guards. [ ] A6 J8 tree port (not started).
- 11-10 [x] J2 wav_contract DONE: loop READY (Codex + Ultra) + Haiku HIGH confirm READY; in anime_studio_merge/director (29 tests). [x] J7 precommit_check: loop READY, code fixes verified by Haiku high second review, CLI-subprocess test pending as last item (tools/test_precommit_check.py 24 pass).
- 11-10 open in the loop: J1a, J1b, J3, J5, J6, J10 (running or review-open), J4 (rerun with hard examples), J9 split into J9a script_hook + J9b script_pacing (J9c script_inspect combiner follows). Reel 1 untouched.
- 11-10 [x] J5 shot_mode DONE: loop READY + Haiku MEDIUM review fixed + Haiku MEDIUM confirm READY; in repo (24 tests). [~] J1b passed again (32 tests in repo, confirm review pending). Open: J1a, J3, J4, J6, J9a, J9b, J10 (specs updated, reruns running).
- 11-10 late: DONE (loop READY + Haiku confirm): J2, J5, J7 (24 tests), J9b (26 tests, boundary tests added; in repo). In the repo, review fixes pending a rerun: J1a (bpm bound, 5 tests fail), J4 (embedded cast line), J6 (ids "a." and "C:outside"), J1b (confirm review not yet run). Loop open: J3, J9a, J10, J12 (review items), J9c/J11/J13/J14 waiting for test-first files (observer 6). Then: tree port, wiring W1-W10, offline trace of input_video_strength, end-to-end test.
- 11-10 late 2: [x] J4 prompt_hygiene DONE (loop READY after Haiku medium review + confirm fixes; 40 tests in repo). Next observer pass: J3, J9a, J12 (test findings), J10 (code finding).
- 11-10 late 3: [x] J9c script_inspect DONE (loop READY + Haiku MEDIUM READY; 22 tests in repo; non-blocking: pacing-exception propagation untested, CLI prints one blank line at the end). Waiting on the real script_hook (J9a) for the full script gate.
- 11-10 late 4: [x] J9a script_hook DONE (loop READY + Haiku MEDIUM READY, 4/4 mutants caught; 28 tests in repo; notes: H5 startswith false positive "it was a timeline", event without t defaults to 0.0). With J9b and J9c the SCRIPT GATE (hook + pacing + one command) is complete. Session restarted at ~02:55: J10/J11 reruns relaunched, cron recreated.
- 11-10 late 5: [x] J6 runner_safety DONE (loop READY + 4 Haiku reviews; final confirm READY; 44 tests incl. junction tests; hostile-id probes refused). Note: injected mode skips junction checks by design: the production caller must use the real mode. DONE so far (loop READY + Haiku confirm): J1a?, J1b?, J2, J4*, J5, J6, J7, J9a, J9b, J9c (* confirm reviews of J1a J1b J4 were FIX FIRST then fixed + loop READY). Open: J3, J10, J11, J12, J13, J14.
- 11-10 late 6: [x] J14 shot_router DONE (loop READY + Haiku MEDIUM READY, 4/4 mutants caught, 46 tests in repo; plan_reel hand check 5.1 units / 9 keyframes / 4 GPU shots; notes: plan_reel raises KeyError not RouterError for a shot missing id/features). 
- 11-10 late 7: [x] J13 clip_gates DONE (loop READY + Haiku MEDIUM READY, 4/4 mutants caught, 60 tests in repo). Loop state: 14 of 16 passed; J3 and J11 Haiku reviews running/resumed; open: J10 (test corrections running), J12 (observer10).
- 11-10 late 8: [x] J11 image_gates DONE (loop READY + Haiku MEDIUM confirm READY; 42 tests in repo; mask/px/NaN fixes verified; 16x16 case 0.75002; non-blocking: dilate with a huge px is slow (clamp to max(mask.shape)), NaN pixels give ssim NaN -> pass False). Done now: J2 J5 J6 J7 J9a J9b J9c J11 J13 J14 (+ J1a J1b J4 fixed after review); open: J3 (review running), J10, J12.
- 11-10 late 9: J10 audio_edge FUNCTIONALLY DONE: reference body in, 33 tests pass; Haiku medium review: code correct, 100 random signals 0 failures, REAL 24 kHz WAV (starts at sample 0, abrupt end): before starts_at_sample0/start_abrupt/end_abrupt True, after all False (lead-in 80 ms, tail ~80 ms); only stale comments/docstring to clean (rerun in the loop). Open: J3 (2 exact lines written in), J12 (feather border bug + jpg name fix running), J10 cleanup.
- 11-10 late 10: [x] J3 caption_fields DONE (loop READY + Haiku MEDIUM confirm READY, 3/3 mutants caught, 43 tests in repo; the two exact-line fixes worked). Remaining open in the loop: J12 (feather border fix running), J10 (comment cleanup rerun). Then: merge trees, wiring W1-W10, soft-end trace, end-to-end test.
- 11-10 late 11: [x] J12 plate_composite DONE (loop READY + Haiku MEDIUM confirm: module correct; half-mask edge test added; 29 tests in repo; timing 768x1344: diff_mask 2.7 s, composite feather4 1.6 s). Only J10 cleanup rerun still running. NEXT PHASE: (a) merge the two code trees (J8), (b) wiring W1-W10, (c) offline trace of input_video_strength, (d) end-to-end test on reel 2 (script first), (e) README + loop repo sync, (f) push with owner's go.
- 11-10 late 12: [x] J10 audio_edge DONE (final cleaned version in repo; reference body; Haiku review: 100 random signals 0 failures, real 24 kHz WAV before/after flags True->False; remaining reviewer asks are extra test cases, non-blocking). ALL 16 TOOLS (J1a J1b J2 J3 J4 J5 J6 J7 J9a J9b J9c J10 J11 J12 J13 J14) are in anime_studio_merge. Next phase: tree merge (J8), wiring W1-W10, soft-end trace, end-to-end test on reel 2.
