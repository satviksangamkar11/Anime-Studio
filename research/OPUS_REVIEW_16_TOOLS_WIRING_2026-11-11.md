# Opus read-only review of the 16 tools and their wiring (2026-11-11; one call approved by the owner; nothing was run, all from reading files)

## 1. Merged-review findings that are wrong or overstated
- E7 timeline_lock_io hash: overstated. verify_lock also compares the normalised path set (io.py:171-174). Leftover: "./x" vs "D:/x" vs "d:/x" gives a false stale (fails safe).
- E3 can_stop([]) raising: correct fail-closed behaviour, not a bug (runner_safety.py:57-58).
- W-B: wrong premise. Job id is already f"{i}.{lang}" (voice_cast.py:107); export_wavs writes wav/<lang>/<line>.<lang>.wav (line 302) which build_vo_tracks.py:91 reads. Naming half of problem 13 is consistent. Real defects: in-place atempo (voice_cast.py:305-314) and measuring after TRIM/atempo. wav_contract names by shot but raw files are per line ("SHOT-001-N"): call it with line ids.
- W-C / 42: wrong file. build_final_reel reads only core.json -16 (build_final_reel.py:231-237, gate_d_audio.py:393-402; test_loudness_single_source locks it). The surviving -14 is score/stem_builder.py:503 (write_noduck(target_lufs=-14.0)).
- W-I: no wrapper hiding failing tests in this tree. .githooks/pre-push only runs secret_scan; no tests at push; core.hooksPath unset.
- E1 understated: REF_S also emits "S" (shot_router.py:56) and raises in shot_mode; POST emits None and shot_mode.py:14-16 raises "unknown image_prompt_type None"; SOFT_SE and KFI lose input_video_strength and the MID keyframe (frame_row shot_mode.py:67-77 does not copy them): the soft end renders as a hard SE.
- E8 understated: a float 0..1 image is divided by 255 again (image_gates.py:18-19); any two float images pass background_lock (silent PASS).
- E4 NUL byte: doubtful; _CONTROL_CHAR_RE includes \x00 (precommit_check.py:18) and runs before ast.parse. Re-check.
- E5: verdict({}) also passes; flicker without flicker_limit passes (clip_gates.py:127-150).
- W-A "cue sheet reads frames_for" cannot work: the lock stores no bpm, act start or cue id (timeline_lock_core.py:197-209).

## 2. Bugs and gaps all four reviewers missed
1. LATTICE RANGE (most important). H3 accepts only n in 6..20 = 107..345 frames (h3/shot_table_spec.py:8, 60-65). fit_lattice returns 22/39/56/73/90 for short shots (core.py:17-21) and has no upper bound; check_pixel_frames accepts any n>=1 (shot_mode.py:47-51), so 22 passes shot_mode then fails in lattice(). Fix: fit_lattice gives max(107, ...) and raises above 345 ("split the shot"); check_pixel_frames requires LATTICE_N_MIN <= n <= LATTICE_N_MAX (import them).
2. Lock handles are made up: plan_shots hard-codes head 8 / tail 24 (core.py:195, 205-206) but v4_to_h3 picks real trims from seam types (v4_to_h3.py:257-299). INTER first shot gets head 0. CHAINED needs editorial == pixel, never produced (pixel >= edit+32), so v4_to_h3:248 never picks CHAINED. Handle sum 32..48; H=48 (1 shot in 17) breaks the one-sided tail limit 24..47 (v4_to_h3.py:295). v4_to_h3.fit_lattice (line 302) re-picks n: a second lattice picker (problem 3). Fix: plan_shots computes pixel_frames by calling v4_to_h3._plan_handles per candidate n (or v4_to_h3.fit_lattice takes edit_frames from the lock and writes trims back); the lock stores trim_in_frame / trim_out_frame.
3. End keyframe at the wrong frame: prompt header pins Picture 2 at pf/fps (compile_h3_sing8.py:80-82; linter regex schema_and_linter.py:79), i.e. the end of the tail handle, 24-47 frames after the cut, so the end pose is never on screen. SOFT_SE row says "placed at the cut" but nothing carries a position. Fix: lock stores end_frame_position = trim_out_frame; shot_mode frame_row emits it plus input_video_strength; the batch builder maps it to Wan2GP image_end_frame_position.
4. Silent shots cannot be planned: edit_frames_for_shot({}) raises (core.py:32-33); plan_shots raises KeyError for a shot missing from voice_seconds (line 189). Fix: shot may carry min_seconds; need = max(voice need, ceil(min_seconds*fps)); empty dict allowed when min_seconds present.
5. Lock vs voice packer measure different things: packer places lines at scripted starts with GAP 0.12 / TAIL 0.10 (build_vo_tracks.py:31-47). Raw WAV seconds under-size any shot whose line starts after 0. Fix: lock input seconds = editorial_by_lang.needed_sec(lines, 1.0) (includes TAIL) with margin_frames=0 (or keep 6 and accept double margin). Set build_vo_tracks MAX_TEMPO = 1.0 once lock-driven.
6. Beat grid lost after planning: result has no bpm / act_start_frame (core.py:197-209). Acts detected only by bpm change (line 184): two consecutive 128 BPM cues merge. "bar" is really smallest exact-integer beat count from the shot start; at 176 BPM that is 11 beats (90 frames), bar_beats unused. 128 BPM error bounded <= 20.83 ms (half a frame, absolute grid, no drift) = physical floor at 24 fps. Fix: add "bpm", "act_start_frame", optional "cue" (act resets on cue change); rename method "exact_beats".
7. Float rounding in edit_frames_for_shot: ceil(49/24*24) can give 50 (line 48); use ceil(product - 1e-9). margin_frames not validated (negative accepted).
8. Lock does not cover plan parameters or all inputs: margin_frames, handles, bpm not hashed; nothing forces WAVs and script into inputs; load_lock does not re-check pixel_frames against the lattice. Fix: write_lock stores a params dict hashed with the inputs; wiring passes every <line>.<lang>.wav + shots.json + FINAL_TEXT + eleven_manifest.json; load_lock checks lattice range.
9. Router conflict fix: add an "SE" row to _ROUTE_TABLE (image_prompt_type SE, keyframes A,B, strength None, no flag). route_shot(features, allow_s=False) maps S->SE and REF_S->SE (refs kept) when not allowed. plan_reel: catch KeyError -> RouterError. shot_mode frame_row: refuse None ("POST shots never reach the batch"); copy input_video_strength, end_frame_position, mid; raise on KFI if no MID path. compile_h3_sing8.py:147 only knows FL2VA/Ref2VA, so start-only (I2VA) has no workflow: S is dead on that path too. POST has no producer (no 2.5D renderer); assemble_video would KeyError on the clip (build_final_reel.py:44).
10. prompt_hygiene would break every compiled prompt if wired as-is: (a) FL2VA format requires the "\n\n" blank line after the header (compile_h3_sing8.py:83; regex schema_and_linter.py:79) while clean_prompt strips blank lines (problem 30 killer vs linter). (b) clean_prompt appends mouth and cast lines after non_diegetic_music, breaking \Z in FL2VA and REF2VA regexes (schema_and_linter.py:79, 114-116). (c) Linter SX-01 (SX_MIN_STAGE_CUES=7, line 112, owner rule 11-07) requires a sound cue inside every action sentence: contradicts "cue words out of the visual sentence" (26/27): OWNER DECISION. (d) A second mouth sentence collides with required MOUTH_LOCK_SENTENCE (schema_and_linter.py:117). (e) mouth_sentence returns a fragment "While A and B keep their lips completely closed." (prompt_hygiene.py:169): drop "While". (f) GLUE_RE matches every v4_to_h3:160 output (", with a thud echoes"): wiring before fixing line 160 raises on every shot.
11. runner_safety silent passes: max_script_mb=12.0 (line 119) passes the 11.3 MB hung script (problem 29): default 7.0 or each upload part <= 3 MB. script_path=None and urls=[] skip checks silently: make required in the wiring. Production clip check accepts any .mp4 over 50 KB (lines 47-50) incl. partial/wrong clip: add expected_frames (ffprobe nb_read_frames == pixel_frames from the lock), ignore *.part.
12. precommit_check misses this project's keys and scans the wrong copy: no ElevenLabs pattern (sk_ + hex); Anthropic sk-ant-... missed (generic_sk needs [A-Za-z0-9]{32,} right after sk-); no Google AIza or GitHub ghp_. Reads working-tree file, not staged blob (line 60): use git show :<path>. Binaries: skip known media extensions instead of failing "not UTF-8" (line 71).
13. audio_edge on real ElevenLabs output: lead-in measured on exact-zero runs (audio_edge.py:190), any noise floor makes first=0 and adds the full 80 ms. Fade only when the single edge sample > 0.02 (lines 209, 213): a loud onset starting on a quiet sample is not faded. Fix: decide by rms of the fade window vs voiced_threshold. No WAV writer. Padding changes WAV length, so it must run in voice_cast export BEFORE the lock measures.
14. Captions checked against the wrong text: spoken_text must be the text actually voiced (manifest row text after voices.prep_text, voice_cast.py:103/107), not shots.json.
15. clip_gates looks at wrong frames: tail check scans the last 30 frames of the clip (clip_gates.py:10-26), mostly the discarded tail handle. Pass the window [trim_in, trim_out] from the lock.
16. image_gates background_lock ignores area_fraction (image_gates.py:107-113): masks covering nearly everything let one 8x8 tile decide. Add min_area_fraction (e.g. 0.25). Thresholds 0.97 / 3/255 uncalibrated for diffusion-edited B frames: keep as tuning parameters.
17. build_final_reel silent passes: missing VO WAV becomes silence (lines 72-76); missing vo_tracks_report falls back to writer title cards (lines 288-291); shot offsets are summed float seconds (lines 66-70, 156-159) not frames/fps (third clock, problem 6); --reel defaults to "kalika_reel1" (line 253): reel-1 overwrite risk under rule 53: make it required.
18. script_inspect imports script_hook / script_pacing as top-level modules (script_inspect.py:22-23): works only inside director/. Pacing runs on writer seconds; re-run P2-P4 on lock seconds after the lock.

## 3. Per problem: the change that truly closes it, and the test that proves it ("owner" = needs an owner decision; "rule" = no code)
1. render_controller main/plan_pipeline adds a timeline result: verify_lock(lock, inputs) must pass or abort; run_colab_batch does the same before --go. Test: plan_pipeline with no lock gives results["timeline"]["ok"] False and main --go exits non-zero.
2. Lock from needed_sec; build_vo_tracks takes ed = frames_for(lock,id)/fps with MAX_TEMPO = 1.0. Test: for every lock shot pack_shot(lines, ed, max_tempo=1.0) does not raise.
3. Delete apply_rows/apply_shots calls (build_vo_tracks.py:80-81, build_final_reel.py:261-265). v4_to_h3.fit_lattice reads edit_frames from the lock. Remove 1.03 and 1.15. Test: v4_to_h3 pixel_frames/editorial_frames equal the lock's per shot; grep finds no MAX_SPEEDUP / MAX_TEMPO = 1.15.
4. Lock records real trims from _plan_handles before keyframes exist. Test: _plan_handles returns problems == [] for every lock shot.
5. Beat grid absolute (already); store error_ms and bpm in the lock. OWNER: accept +-1/2 frame. Test: max(error_ms) <= 1000/48 over a 128/176 plan.
6. build_final_reel offsets and render_controller._gate_d_result (render_controller.py:551-552) both build editorial_duration_sec = edit_frames/fps from the lock. Test: identical per-shot seconds and same Gate D verdict.
7. Lock inputs include the measured file and the WAVs. Test: change one WAV byte -> verify_lock raises StaleLockError.
8. Lock inputs include FINAL_TEXT / shots.json; render refuses a stale lock. Test: edit one script byte -> render_controller timeline result not ok.
9. voice_cast run calls GET /v1/voices and SystemExit before led.reserve if any vmap voice_id missing. Test: fake http without the voice -> SystemExit and zero POST.
10. rule.
11. Plan lines with hard names need pronunciation_ok: true (after owner listens); measured() adds a problem otherwise. OWNER listens. Test: measured() on an unflagged hard-name line reports a problem.
12. export_wavs calls wav_contract.require_wav(dst) after ffmpeg. Test: a .wav holding MP3 bytes raises ValueError.
13. Delete voice_cast.py:305-311 (keep report rows), run audio_edge before the lock, lock hashes the exported WAVs. Test: exported duration == trimmed duration and no "fit by atempo" verdict.
14. Delete build_final_reel.py:95 and 168-170; build text from caption_fields.caption_lines (spoken_text = manifest text; caption_text and approval from the pack). Test: grep finds no CAPTION_FIXES; unapproved diff raises CaptionError in spoken_cues_real.
15. Writer stage end runs script_inspect and writes a report with the script sha; voice_cast run refuses without a PASS report matching the sha. Test: failing script -> SystemExit before any POST.
16. OWNER must define fidelity; then code matches lines to source lines. Test: a fabricated line is flagged.
17. rule. 18. rule.
19. Make --reel required (build_final_reel.py:253) + per-story smoke test. Test: argparse fails without --reel.
20. Keyframe approval runs plate_composite.plan + image_gates.background_lock, writes keyframe_gate.json; v4_to_h3._own_keyframe refuses B without a passing record. Test: B with shifted background gives a v4_to_h3 problem.
21. OWNER: pick a detector or accept manual counts. Code: keyframe_review.json (cast count, arms, posture per A/B) feeds cast_parity / limb_parity / posture_matches before approval. Test: a missing sage gives a problem.
22. rule. 23. rule. 24. OWNER.
25. Run the item-20 gate at keyframe approval before Gate B; render_controller lint uses its record. Test: lint not disabled when no boundary PNG exists yet.
26. v4_to_h3:160 drops ", with " + cues join (cues go to overall_soundscape); compile_h3_sing8 refuses on find_cue_glue / duplicates. Needs OWNER SX-01 decision. Test: compiled prompt for cue "a veil snaps" has no "with a veil".
27. compile_h3_sing8 runs check_sound_cue on the soundscape with visible = subjects and puts cast_line in the body (format permitting). Test: "serpents hiss" with no serpent subject raises.
28. OWNER picks mouth wording; then _mouth_lock uses fixed mouth_sentence and MOUTH_LOCK_SENTENCE / linter change together.
29. run_colab_batch: preflight(script_path=required, max_script_mb=7). Test: 11.3 MB script fails.
30. Change compiler and linter regex (compile_h3_sing8.py:83, schema_and_linter.py:79) to a single "\n"; assert in batch builder. Test: no compiled prompt contains "\n\n".
31. run_colab_batch calls clip_verified(expected_frames) after each shot. Test: truncated mp4 not verified.
32. run_colab_batch calls stop_decision on ALL DONE and really stops; argv lists not split strings; dead-man timer. Test: fake colab, all clips verified -> stop issued; a name with spaces stays one argument.
33. preflight URLs include the chumpy URL + wheel_ok(vendor wheel, sha). Test: fake HEAD 504 -> failure.
34. run_colab_batch refuses an accelerator other than G4. Test: "A100" refused.
35. --go requires a canary proof file whose batch hash matches the current batch. Test: no proof -> non-zero exit.
36. J8 git port of build_h3_batch.py and run_colab_batch.py (+tests). Test: both exist in merge tree, suites pass.
37. New frame extractor (ffmpeg + numpy) feeding clip_gates; verdict requires all keys. Test: verdict({}) raises or fails.
38. rule.
39. Lock stores bpm, act, cue; the score cue-sheet builder reads the lock via verify_lock. Test: stale lock makes cue-sheet build refuse.
40. OWNER sets SFX policy; then Gate D sets SFX gain against voice.
41. rule 51 (existing caption tests).
42. stem_builder.py:503 reads core.json lufs, or OWNER declares the no-duck mp3 a separate deliverable. Test: grep finds no -14 outside tests.
43. manual doc edits (owner/supervisor), not code.
44. Install pre-commit hook (core.hooksPath + .githooks/pre-commit running precommit_check). Partial: a corrupted "\n" that still parses is not caught. Test: staged .py with a raw line break inside a string gets a syntax-error finding.
45. Disk check in preflight exists; add a local free-space check before export. Drive access OWNER.
46. Add secret patterns (bug 12), read the staged blob, run pytest in pre-push. Key rotation OWNER. Test: an sk_<48 hex> string gets a finding.

## 4. Shortest safe order of work
- Step 0 fix the modules (pure, parallel, no collisions): timeline_lock_core (bugs 1, 4, 6, 7, 8), timeline_lock_io (params), shot_mode + shot_router (bug 9), image_gates (E8 float pass, area check), clip_gates (verdict, window), runner_safety (bug 11), precommit_check (bug 12), script_hook (no defaults), prompt_hygiene ("While"), audio_edge (rms test + writer).
- Step 1 owner decisions (block steps 6-7): S default / SE fallback; SX-01 vs cues out of the sentence; mouth wording (28); SFX policy (40); the no-duck -14 target; watermark tool (24).
- Step 2 J8 git port of build_h3_batch and run_colab_batch (needed before steps 7 and 8).
- Step 3 voice_cast export: no atempo, audio_edge, require_wav, voice preflight, pronunciation flag.
- Step 4 new lock writer: small CLI reusing editorial_by_lang.needed_sec and v4_to_h3._plan_handles (import cycle: editorial_by_lang imports build_vo_tracks, build_vo_tracks lazily imports editorial_by_lang).
- Step 5 build_vo_tracks + v4_to_h3 lattice/trims from the lock (v4_to_h3 is also touched in step 7: sequence them).
- Step 6 build_final_reel (lock, captions, offsets, required --reel, no silent fallbacks) and render_controller (timeline gate, Gate D on lock seconds), build_final_reel in one job.
- Step 7 compile_h3_sing8 + schema_and_linter + v4_to_h3:160 together (regex, SX-01 and compiler format in one commit).
- Step 8 build_h3_batch: shot_mode rows, input_video_strength, end_frame_position, then the offline trace that Wan2GP keeps them.
- Step 9 run_colab_batch: runner_safety + clip_gates, DRY RUN only.
- Step 10 hooks (core.hooksPath, pre-commit, pre-push pytest), then retire editorial_by_lang once the lock reproduces the reel 2 plan.
Colliding files: v4_to_h3.py (steps 5, 7), build_final_reel.py (steps 3 via audio_edge, and 6), schema_and_linter.py (step 7), editorial_by_lang.py/build_vo_tracks.py (import cycle). No reel 1 file needs editing; the --reel default "kalika_reel1" is the only reel-1 hazard.
