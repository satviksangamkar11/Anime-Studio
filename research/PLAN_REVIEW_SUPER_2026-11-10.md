# Nemotron Super merged plan review

# Merged Pipeline Review Report

## 1. MUST-FIX DEFECTS (ranked, deduplicated, exact change)

1. **Missing contract writer — `director/timeline_lock.py` absent from both branches.** Plan 1a requires it as the shared timeline contract.  
   *Change:* Create `director/timeline_lock.py` with CLI `--pack --story --vo-report --langs --write`; read `vo_tracks_report.json` (en/hi/mr); per shot `edit_frames = max_lang(ceil(sec*24)) + margin`; snap `edit + head_handle + tail_handle` to H3 lattice `17n+5`; compute `sha256` over text/voice/clip inputs; write `timeline_lock.json` with identical entries for en/hi/mr, the input hash, and no tempo-limit/beat fields.

2. **Merge-only files dropped by v4 — `core/core.json`, `director/build_vo_tracks.py`, `director/voice_cast.py`, `director/build_final_reel.py`.** `core/core.json` is the sole loudness source (1e); losing it drops the -14 exclusion guarantee, and v4-only code referencing the others breaks after merge.  
   *Change:* Keep these in `main`; if v4 is the source tree, port them into v4 before merge.

3. **`director/editorial_by_lang.py` not deleted.** Plan 1a replaces it with `timeline_lock.json`.  
   *Change:* Delete `director/editorial_by_lang.py` (`FILE`, `MAX_SPEEDUP`, `load`, `apply_rows`, `apply_shots`, `plan`, `main`) from merge branch and main.

4. **`h3/v4_to_h3.py` lattice/handle stripped.** `_source` may return unbound `stage`; `_stages`/`_mouth` lost `ti` head-handle offset; `fit_lattice` deleted; `MOTION_WORDS` entries removed.  
   *Change:* Init `stage=None` before the file loop; restore `_stages(directives, pf, sid, problems, ti=0)` with `a,b = round(t0*FPS)+ti, round(t1*FPS)+ti`; restore `_mouth(track, pf, sid, problems, ed=None, ti=0)` midpoint mapping with `ed` bounds and `"closed"` handling; restore `fit_lattice(shots)` and call before per-shot `_shot`; restore missing motion-word mappings.

5. **`h3/v4_to_h3.py` drops `metadata.look`.** `post.py` and `assemble_reel` read `metadata.look`.  
   *Change:* Restore the merge-branch metadata spread before the shot dict close.

6. **`h3/render_controller.py` breaks single timeline and loudness.** `_write_assembly` omits `loudness=loud`, `attach_colour_seams`, and `colour_seams`; `prepare` drops the loudness guard and never reads/verifies `timeline_lock.json`; docstring says "no ffmpeg" while code builds ffmpeg artifacts.  
   *Change:* Import `attach_colour_seams, build_ffmpeg_assembly_plan, load_loudness_plan, write_assembly_script` from `h3.assemble_reel`; forward `loudness=loud` from `core/core.json`; call `attach_colour_seams`; emit `colour_seams`; load `loudness.json` before `compile_episode`; read `timeline_lock.json`, verify input sha256, raise `ValueError` on mismatch; correct docstring.

7. **`h3/h3_author.py` regresses owner-gated authoring.** `scheduler_caller` references deleted `e2e_sample`; `claude_caller`, `--model`, `--opus`, `_placeholder_png`, temp-dir keyframe staging, and Opus bypass before `LIVE_FLAG_ENV` are removed.  
   *Change:* Re-add `from h3 import e2e_sample`; `scheduler_caller(model=None)`; `claude_caller(model="opus", effort="low")`; `_placeholder_png`; temp-dir keyframe staging in `_lint_candidate`; `main` args `--model`/`--opus`; caller selection `(claude_caller() if args.opus else scheduler_caller(args.model)) if args.live else None`; Opus bypass before the live-flag check.

8. **`h3/schema_and_linter.py` `SFX_CUE_RE` narrowed.**  
   *Change:* Restore the full merge-branch alternation (add `bird|song|stream|...|thunk`) so SX-01 lint does not false-negative.

9. **`director/build_vo_tracks.py` uses retired contract and wrong audio contract.** Imports `editorial_by_lang`; hardcodes `MAX_TEMPO=1.15`; `pack_shot` not minimal; `render_shot` writes `editorial-TAIL`; `adelay={ms}|{ms}` invalid for mono; writes `<id>.wav`; no RIFF/WAVE/ID3 header check; no input sha256.  
   *Change:* Remove `editorial_by_lang` import; load `timeline_lock.json`; `editorial = edit_frames/24`; binary-search minimal tempo over `[1.0, max_tempo]`; `render_shot` `end=editorial`, `apad`/`atrim` to `end`, `adelay={ms}`; output `lang/<id>.<lang>.wav`; reject headers not `RIFF....WAVE` or `ID3`; add per-entry sha256 of shots/voice/clip.

10. **`director/voice_cast.py` ledger, naming, and paid-call defects.** `Ledger.reserve` never releases fd/lock; `load_plan` subscripts missing keys; `build_jobs` `KeyError` on missing lang; `Ledger.rows` crashes on blank/corrupt lines; `export_wavs` writes `<id>.wav` and applies in-place atempo; `load_slots` only reads `en`; `latest_ok` blind-overwrites; `fit_report` float equality; `run` reuses stale cache on mp3 sha only; no header check; no timeline_lock hash.  
    *Change:* Release `os.close(fd)`/`lock.unlink()` in `reserve` finally; explicit existence/equal-length checks in `load_plan`; missing-lang `SystemExit` in `build_jobs`; blank/JSON-continue in `rows`; `export_wavs` path `wav/<lang>/<id>.<lang>.wav`, header validation, delete atempo block; `load_slots` max over all languages; `latest_ok` by greatest `t`; tolerance `tempo <= 1.0+1e-6`; reject non-ID3 bytes; compare `text_sha256`; require contract script hash in `measured`.

11. **`director/build_final_reel.py` mux/caption/loudness defects.** VO path `<id>.wav`; SFX entries reference inputs never appended; offsets from `editorial_duration_sec` not `edit_frames/24`; no contract hash refusal; silent `CAPTION_FIXES` replace; `PLAY_W,H = 1080,1920` vs plan 768x1344; `probe_frames` incomplete; missing VO silent fallback; `assemble_video` `KeyError` on missing shot; no core.json loudness guard; `measure` lacks `check=True`; `spoken_cues_real` `KeyError` on missing offset; missing-report fallback hides data; `correct_loudness` doesn't block; double measure; `stop` undefined.  
    *Change:* Path `<id>.<lang>.wav`, `raise FileNotFoundError` when missing; append SFX inputs with integer indices; load `timeline_lock.json`, verify sha, compute `t` from `edit_frames/24`; remove `CAPTION_FIXES`, use `caption_text` when `caption_diff_approved` else `spoken_text`; `PLAY_W,H = 768,1344`, `CAPTION_MAX_W=592`, `CAPTION_POS=(360,903)`; `probe_frames` raise on empty/non-numeric and `trim_in_frame >= got`; `assemble_video` verify `shot_id in clips`; assert core delivery is only -16 LUFS/-1 dBTP and no "-14"; `check=True` in `measure`; `offsets.get` guard; remove fallback, `raise SystemExit` on missing report; block after `tries`; single measure call; define `stop`.

12. **`h3/compile_h3_sing8.py` plan 2b/2c defects.** `_mouth_lock` single rule not per-character; no auto cast line; `compiled_soundscape` no creature/object ban; direct indexing crashes; `fps==0` division; unknown audio `cid` KeyError; `k`/`t` undefined in `compile_comfyui_workflow`; node 5 forces both frames; lint runs before keyframes; `compile_fl2va_prompt` missing blank-line/glue/duplicate/mouth/creature/auto-line fixes.  
    *Change:* `_mouth_lock(dlg, registry, on_screen_ids, silent=True)` per-character join; add `_auto_cast_line` and append in `_fl2va`/`_ref2va`; reject banned creature/object nouns before `overall_soundscape`; `shot.get` guards; validate `fps`/`pixel_frames`; `cid in chars` check; fix `k`/`t` to `shot`; node 5 `last_frame` only when `image_prompt_type=="SE"`; move Phase B lint after `resolve_keyframes`; apply plan 2b prompt cleanup.

13. **`director/build_h3_batch.py` batch/frame defects.** `legacy_rows` unconditional start/end, no `image_prompt_type`, no `17n+5` check; `jpg_embedder` PNG-as-JPG; `harden` missing `import time` and undefined `note`/`OUT`; `split_blobs` misses single-quoted blobs; `wheel`/`sha` unbound; `main` no SE/S handling; unconditional `run_kaggle.build(...,"colab",...)` paid path.  
    *Change:* `mode = sh.get("image_prompt_type","SE")`; add `image_prompt_type`; `end` only for SE; raise if `(frames-5)%17 != 0`; use `jpeg_b64`; prepend `import time` and pass `note`/`OUT`; handle single quotes; bind `wheel`/`sha`; default SE, owner-gated S for SHOT-008; gate Colab/paid calls behind owner flag.

## 2. CHANGES PER STEP (build order)

**1a — Contract & lattice**
- `director/timeline_lock.py` (new): write contract per 1a (edit_frames, 17n+5, sha256).
- `director/editorial_by_lang.py`: delete.
- `h3/v4_to_h3.py` `_source`, `_stages`, `_mouth`, `_shot`, `fit_lattice`: restore head handle, lattice re-pick, metadata.look.
- `director/build_vo_tracks.py`: switch to `timeline_lock.json`, `<id>.<lang>.wav`, header check, binary tempo.
- `director/voice_cast.export_wavs`: `<id>.<lang>.wav`, header check, no atempo.

**1b — Single timeline / Gate D**
- `h3/render_controller.py` `_write_assembly`, `prepare`, `_gate_d_result`: forward loudness, attach colour seams, refuse stale `timeline_lock.json` hash.
- `director/build_final_reel.py` `mux_argv`, `spoken_cues_real`, `main`, `measure`, `correct_loudness`, `assemble_video`, `probe_frames`: contract hash, `edit_frames/24`, loudness guard, SFX inputs, caption fields.

**1c — Voice naming**
- `director/voice_cast.export_wavs`: `<id>.<lang>.wav`.
- `director/build_vo_tracks.py`: read `<id>.<lang>.wav`.

**1d — Captions**
- `director/build_final_reel.py` `spoken_cues_real`: remove `CAPTION_FIXES`; use `spoken_text`/`caption_text` + `caption_diff_approved: true`.

**1e — Loudness single source**
- `core/core.json`: ensure only -16 LUFS / -1 dBTP, no -14.
- `director/build_final_reel.py` `assemble_video`: assert single loudness target.
- `h3/tests/test_loudness_single_source.py`: port to v4.

**1f — Keep merge as main; port only missing/newer**
- `h3/v4_to_h3.py`: restore `metadata.look`.
- `h3/h3_author.py`: restore `e2e_sample`, `claude_caller`, `--model`/`--opus`, `_placeholder_png`, temp staging.
- `h3/schema_and_linter.py`: restore `SFX_CUE_RE`.

**2a — Per-character mouth**
- `h3/compile_h3_sing8.py` `_mouth_lock`, `_fl2va`, `_ref2va`: per-character join with `registry`/`on_screen_ids`.

**2b — Prompt hygiene**
- `h3/compile_h3_sing8.py` `compile_fl2va_prompt`: collapse blanks, no "with <cue>" glue, no duplicates, auto cast line, creature/object ban.

**2c — image_prompt_type SE/S**
- `h3/compile_h3_sing8.py` `compile_comfyui_workflow` node 5: `last_frame` only for SE.
- `director/build_h3_batch.py` `legacy_rows`: `image_prompt_type`, `end` only for SE, `17n+5` check.

**2d — Keyframes / phase order**
- `h3/compile_h3_sing8.py` `compile_comfyui_workflow`: fix `k`/`t`; `compile_episode`: Phase B lint after `resolve_keyframes`.

**3 — Tests**
- Add all Section 3 tests under `h3/tests/`.

**4 — Render / assembly wiring**
- `h3/assemble_reel.py`: confirm `build_ffmpeg_assembly_plan(shots, name, loudness=)`, `load_loudness_plan`, `attach_colour_seams` signatures.
- `h3/gate_d_audio.py`: confirm Gate D reads same `timeline_lock.json` as `render_controller`.
- `h3/render_controller.py`: wire `assemble_reel` and `timeline_lock` refusal.

## 3. TESTS TO ADD (name + assertion)

- `test_timeline_lock_contract`: `timeline_lock.json` exists; input sha256 matches; every shot length is `17n+5`; `edit_frames >= max_lang(ceil(sec*24)) + margin`.
- `test_timeline_lock_shared_contract`: entries identical across en/hi/mr.
- `test_timeline_lock_input_hash_rejected`: flip one input byte; hash changes and consumer stub raises on stale hash.
- `test_last_shot_start_only`: head spare reduces `trim_in_frame`, never `trim_out_frame`.
- `test_loudness_single_source`: `core/core.json` only -16 LUFS/-1 dBTP; no -14 anywhere.
- `test_voice_naming`: `export_wavs` writes `<id>.<lang>.wav`; `build_vo_tracks` reads it; RIFF/WAVE header; no speed-rewrite call.
- `test_gate_d_single_verdict`: `render_controller._gate_d_result` and `build_final_reel` load same `timeline_lock.json` hash and return identical duration verdict.
- `test_caption_diff_approved`: hi SHOT-003-D1 and SHOT-010-D1 carry `spoken_text`, `caption_text`, `caption_diff_approved: true`.
- `test_source_no_stage_returns_tuple`: `_source` with no matching file returns 5-tuple, no `UnboundLocalError`.
- `test_stages_head_handle_offset`: `t0=1.0,t1=2.0,ti=8,FPS=24` → `a==32,b==56`.
- `test_mouth_handle_seconds_closed`: `pf=72,ed=48,ti=20,{"0":"open"}` → `states["0"]=="closed"`, `states["1"]=="open"`.
- `test_fit_lattice_bumps_too_small_n`: `editorial_duration_sec=10.0`, `lattice_n=7` → `changes` non-empty, `pixel_frames>=240`.
- `test_v4_to_h3_metadata_look_present/absent`: look round-trips; absent look → no `metadata`.
- `test_render_controller_write_assembly_forwards_loudness_and_seams`: `loudness=` forwarded; `attach_colour_seams` called; `colour_seams` in output.
- `test_render_controller_prepare_rejects_corrupt_loudness_before_write`: invalid `loudness.json` → `ValueError`, `compile_episode` not invoked.
- `test_render_controller_prepare_refuses_stale_timeline_lock`: sha mismatch → `ValueError` before `compile_episode`.
- `test_scheduler_caller_imports_and_sets_model`: fake scheduler `.model` set; `_ask` invoked.
- `test_placeholder_png_valid`: starts PNG signature; IHDR 864/1536.
- `test_lint_candidate_missing_keyframes_no_crash`: returns list, no `FileNotFoundError`.
- `test_claude_caller_returns_text`: monkeypatched `call_claude` → `"ok"`.
- `test_main_opus_bypasses_live_flag`: `--live --opus` with flag unset → exit 0, no refusal.
- `test_sfx_cue_re_matches_restored_tokens`: regex matches all restored tokens plus `thump/buzz/chime/bell`.
- `test_sx_min_stage_cues_met`: 7-action-sentence fixture yields ≥ 7 cues.
- `test_pack_shot_minimal_tempo`: returns true minimum (~1.053); last end ≤ 2.4 s.
- `test_render_shot_exact_duration`: output seconds == `editorial`, not `editorial-TAIL`.
- `test_output_name_lang_suffix`: dst == `<id>.<lang>.wav`.
- `test_rejects_invalid_header`: non-RIFF/ID3 → rejected.
- `test_refuses_stale_lock`: sha mismatch → raise/refuse.
- `test_load_plan_missing_hi_narration`: `SystemExit` with clear message.
- `test_load_plan_dialogue_count_mismatch`: unequal dialogue lengths → `SystemExit`.
- `test_build_jobs_missing_lang`: missing `mr` → `SystemExit`.
- `test_ledger_reserve_releases_lock`: second `reserve` in same process succeeds.
- `test_ledger_rows_blank_line`: trailing blank line → no crash.
- `test_export_wavs_names_id_lang_wav`: `<id>.<lang>.wav` exists; `<id>.wav` does not.
- `test_export_wavs_no_atempo`: ffmpeg args have no `atempo`.
- `test_export_wavs_riff_wave_header`: output starts `RIFF`, bytes 8:12 == `WAVE`.
- `test_load_slots_max_over_languages`: en 2.0 s, hi 3.0 s → slot 3.0.
- `test_fit_report_fits_tolerance`: tempo 1.0000002 → verdict "fits".
- `test_run_rejects_non_id3`: non-ID3 bytes → `RuntimeError`, no mp3 written.
- `test_export_wavs_naming_no_atempo`: no `.fit.wav`, no atempo, invalid header rejected.
- `test_measured_contract_hash`: per-lang durations + sha256 over text+voice+clips.
- `test_run_blocks_without_allow_paid`: non-zero exit before paid call.
- `test_voice_path_uses_lang_suffix`: `<id>.<lang>.wav`; missing → `FileNotFoundError`.
- `test_timeline_lock_hash_refusal`: bad sha → raise before ffmpeg.
- `test_caption_text_field_not_CAPTION_FIXES`: no `CAPTION_FIXES`; cues use `caption_text`.
- `test_core_loudness_single_target`: no "-14"; loudness -16 LUFS/-1 dBTP.
- `test_reel_caption_resolution`: `PLAY_W==768`, `PLAY_H==1344`.
- `test_probe_frames_empty_ffprobe`: empty stdout → `ValueError`.
- `test_timeline_lock_stale_hash_rejected`: `main` → `SystemExit` stale lock.
- `test_measure_ffmpeg_fails`: nonzero probe → `CalledProcessError`.
- `test_spoken_cues_real_missing_offset`: missing shot → `KeyError`.
- `test_correct_loudness_blocks_after_tries`: always `ok=False` → `SystemExit`.
- `test_no_editorial_by_lang`: module does not import/reference `editorial_by_lang`.
- `test_build_final_reel_stale_contract_returns_1`: corrupt lock → `main()` returns 1.
- `test_build_final_reel_ok_returns_0`: valid contract, no errors → returns 0.
- `test_loudness_single_target_in_core_json`: only -16 LUFS/-1 dBTP from `core/core.json`.
- `test_mouth_lock_per_character_two_people`: prompt contains rule prefixed by each disambiguator.
- `test_auto_cast_line_emitted`: prompt contains `Only <cast> appear in this shot; no extra figures or creatures.`
- `test_creature_noun_in_soundscape_refused`: banned noun → `ValueError`.
- `test_zero_fps_guarded`: `fps=0` → `ValueError`, not `ZeroDivisionError`.
- `test_unknown_audio_character`: audio `cid` absent → `ValueError`.
- `test_missing_dialogue_and_lip_lock`: missing key → silent mouth lock, no `KeyError`.
- `test_workflow_keyframes_fallback_no_name_error`: `keyframes=None` → no `NameError`; node 5 `first_frame` from `shot`.
- `test_image_prompt_type_S_omits_last_frame`: `"S"` → node 5 lacks `last_frame`; default SE has it.
- `test_episode_phase_b_after_keyframes`: invalid keyframe → `ValueError` after resolution, no `workflow.json`.
- `test_fl2va_prompt_plan_2b`: multi-cast + creature + duplicate + glue → clean output, per-character mouth, auto line.
- `test_legacy_rows_default_se`: `image_prompt_type=="SE"`, both `start`/`end`.
- `test_legacy_rows_s_omits_end`: `"S"` → no `end` key.
- `test_legacy_rows_rejects_bad_frames`: `pixel_frames=100` → `ValueError` 17n+5.
- `test_jpg_embedder_uses_jpeg`: `jpeg_b64` sentinel returned.
- `test_split_blobs_moves_large_literal`: 150k double-quoted blob → external file read.

## 4. PLAN CORRECTIONS (plan vs code contradictions)

- Plan 1a requires `director/timeline_lock.py`; slice shows it in neither branch.
- Plan 1e assumes `core/core.json` is available; slice shows it is D (merge-only) and missing from v4.
- Plan 1b requires `build_final_reel` and `render_controller` to share one timeline; `build_final_reel.py` is D/absent from v4 while `render_controller.py` is M.
- Plan 1c requires `voice_cast` and `build_vo_tracks` everywhere; both are D/absent from v4.
- Plan header fixes reel at 768x1344; code uses `PLAY_W,H = 1080,1920`.
- Plan header allows ffmpeg only for G3 colour-seam check; v4 docstring says "no ffmpeg" while code builds ffmpeg filter/cmd artifacts.
- Plan 1f says keep merge as main and port only missing/newer; slices delete merge functionality (`metadata.look`, `h3_author` features, `SFX_CUE_RE`) instead.
- Plan 2c says sing8/pika6 must not force both frames; `legacy_rows` unconditionally writes `start`+`end` and lacks `image_prompt_type`.
- Plan 1d says remove silent `CAPTION_FIXES`; code retains it.
- Plan 1a last-shot start-only rule; `editorial_by_lang.plan` extends last shot at END when tail exists.

## 5. OPEN QUESTIONS FOR THE OWNER

- Confirm `h3/assemble_reel.py` signatures: is `loudness` required in `build_ffmpeg_assembly_plan`? Do `load_loudness_plan` and `attach_colour_seams` still exist?
- Confirm `director/timeline_lock.json` schema field names (`edit_frames`, `max_tempo`, sha256 inputs, per-shot start times).
- Confirm `core/core.json` loudness field path and that no -14 target remains.
- Confirm `h3/e2e_sample.py`, `director/write_pack.py`, and the `conv` module expose `live_scheduler`, `call_claude`, and `load_default_profile`.
- Confirm `gd.py`/`core/gd.py` exposes `build_loudness_verify_argv`, `check_post_aac_loudness`, `build_sfx_split_filter`, `build_mix_filter`.
- Confirm `vo_tracks_report.json` schema contains en/hi/mr durations per shot.
- Owner decision: enable `image_prompt_type="S"` for SHOT-008 A/B test (currently off pending approval).
- Owner decision: who gates Colab/paid calls in `run_colab_batch.py` and `build_h3_batch.py`?
- Confirm `h3/gate_d_audio.py` exists and reads the same `timeline_lock.json` as `render_controller`.

## NEED requests
- `director/build_vo_tracks.py`
- `director/h3_director.py`
- `director/h3_director.py` (around line 346) to confirm start/end string building and sing8/pika6 frame forcing.
- `director/timeline_lock.py`
- `director/timeline_lock.py` or `timeline_lock.json` schema (field names for `edit_frames`, `max_tempo`, sha256 inputs, per-shot start times).
- `h3/assemble_reel.py` — confirm `build_ffmpeg_assembly_plan` signature (is `loudness` required?) and that `load_loudness_plan` / `attach_colour_seams` still exist.
- `h3/shot_table_spec.py` (lattice, LATTICE_N_MIN/MAX, STATIC_SEAMS, INTER, FPS)
- director/build_vo_tracks.py (confirm it reads `<id>.<lang>.wav` and consumes slots)
- director/run_colab_batch.py part 2/2
- director/voice_cast.py parts 2/3 (export_wavs, run, measured)
- h3/compile_h3_sing8.py part 1/2
- h3/schema_and_linter.py (to confirm `compiled_soundscape` shape, `clean_text`, `san`, `MOUTH_LOCK_SENTENCE`, and whether the creature/object ban already exists there)
- none
director/build_final_reel.py
director/build_h3_batch.py
director/run_colab_batch.py part 1/2
director/timeline_lock.py
director/voice_cast.py parts 1/3 and 2/3 (export_wavs, MAX_TEMPO, measured, paths, load_slots)
h3/e2e_sample.py
post.py
