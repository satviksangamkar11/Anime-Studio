# Triage of Nemotron Super's plan review (2026-11-10), checked against the code

Source: PLAN_REVIEW_SUPER_2026-11-10.md (20 slices, 0 failed). Verdicts below come from reading the code, not from Super.

## Answers to Super's questions (verified)
- h3/assemble_reel.py: build_ffmpeg_assembly_plan(shots, output_mp4, loudness=None) [loudness optional], write_assembly_script, load_loudness_plan, attach_colour_seams(plan, clip_paths, shots, core=None) all exist.
- core/core.json delivery.audio: lufs -16.0, true_peak_db -1.0, tolerance_lu 0.5, loudnorm_tp_db -1.3, lra 11; no "-14" anywhere in the file.
- h3/gate_d_audio.py has build_mix_filter, build_loudness_verify_argv, check_post_aac_loudness, build_sfx_split_filter.
- h3/shot_table_spec.py exists (merge tree). director/timeline_lock.py does NOT exist in either tree: it is new work.
- Export size: build_final_reel.py PLAY_W, PLAY_H = 1080, 1920 is CORRECT (blot rule 51: 1080x1920 lanczos crop of the 768x1344 picture). Super's "set 768x1344" is WRONG; the plan header was imprecise (render 768x1344, export 1080x1920).

## Accepted (real, build in this order)
1. New director/timeline_lock.py + timeline_lock.json (contract with input sha256, edit_frames, 17n+5 lattice, bar/beat frames). Super's draft omitted the beat fields the plan requires: keep them.
2. Consumers refuse a stale hash: build_vo_tracks, build_final_reel, render_controller (one timeline, one Gate D verdict), music cue sheet.
3. Voice naming <id>.<lang>.wav, header check (RIFF/WAVE or ID3), no atempo in voice_cast.export_wavs; load_slots uses the max over languages (currently en only).
4. voice_cast ledger robustness (fd/lock release in reserve, blank-line tolerance, missing-language SystemExit) before the next paid run.
5. build_final_reel: remove silent CAPTION_FIXES in favour of spoken_text / caption_text / caption_diff_approved; guard missing report/offset instead of fallback; fail loudly when the loudness correction does not converge.
6. build_h3_batch.legacy_rows (v4 tree, line 141) always writes start AND end and no image_prompt_type: add per-shot "SE" (default) / "S"; raise if (frames-5) % 17 != 0.
7. Compiler: per-character mouth lock when more than one person is on screen, auto cast line, creature/object noun ban in sound cues, blank-line collapse inside the compiler (not only the batch).
8. render_controller: forward loudness and colour seams, refuse a stale timeline_lock.json.

## Accepted with a different meaning
- Super items 4-8 (v4_to_h3 head handle / fit_lattice / metadata.look, h3_author features, SFX_CUE_RE, render_controller loudness): these are things the v4 branch LACKS or has older. They are warnings against porting v4 versions over the merge branch, not code to write. Rule for the merge: keep the merge-branch version of every shared file, take from v4 only the new files (build_h3_batch.py, run_colab_batch.py, their tests) and the two compiler fixes of blot rule 34.

## Rejected or unproven (do not build from these)
- "PLAY_W, PLAY_H = 768, 1344" and caption box numbers derived from it: wrong, see above.
- "adelay={ms}|{ms} is invalid for mono": no evidence; v4 and v8b reels were built with it.
- "build_h3_batch has an unconditional paid path": the run is dry unless --go is passed (blot rule 27/28); keep, add a test that --go is required.
- "delete editorial_by_lang.py now": only after timeline_lock exists and the reel 1 rebuild reproduces the same frames; until then it stays.
- The 60+ listed tests are a good list but too many to write at once; build the ones for items 1-8 first.

## Open questions for the owner
1. BPM: keep whole-bar / beat-grid frames (plan) - or accept 120 BPM everywhere (rejected earlier for style).
2. Enable "S" start-only for the SHOT-008 A/B test on the G4 (about 2 units).
3. Commit the 61 KB chumpy wheel into the repo, or keep the absolute path D:/aai work/vendor/chumpy_0.71.
