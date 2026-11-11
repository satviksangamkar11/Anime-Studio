# P2: wiring job cards W-01 to W-12 (pipeline scripts → the 16 tools)

## Rules that apply to every card
- **Gate:** each card starts only after the owner approves it (rule 52 order, rule 55 checklist at `checklists/<W-id>.md`). Owner decisions are listed below as D1 to D6.
- **No outside services:** no job calls Colab, ElevenLabs, a renderer, Opus or any paid service. HTTP and colab calls are always injected fakes. Use the Edit tool only, never heredocs (rule 20). Run commands from `D:\aai work\anime_studio_merge`.
- **Reel 1:** no reel 1 file is written. The existing tests that read the reel 1 pack only read it. New fixtures are synthetic or reel 2 style (ids `SHOT-001...`). For H3 stories use `h3/tests/synth.build_story`.
- **P1 preconditions:** a card that needs a P1 module fix starts with a check of that fix. If the check fails, the coder stops and reports. The coder never patches a P1 module.

### Owner decisions these cards wait on
| ID | Decision | Blocks |
|---|---|---|
| D1 | SX-01: **B (recommended)** sound cues leave the action sentences and go to `overall_soundscape`, SX_MIN_STAGE_CUES 7→0; or **A**: keep 7 and join cues with `"; "` instead of `", with "` | W-07 |
| D2 | Mouth sentence wording (problem 28). Stays open: W-07 does not touch `MOUTH_LOCK_SENTENCE` | — |
| D3 | Who writes `acts.json` ({shot: bpm, snap, cue}). Accept a beat error of up to ±½ frame (20.83 ms). Where `hard_names.json` lives (proposed: per pack, `<pack>/hard_names.json`) | W-02, W-03 |
| D4 | Soft end: Wan2GP bd1ff59 drops `input_video_strength` (see W-08). (a) **recommended now:** SOFT_SE/KFI render as hard SE; (b) patch the handler on the VM, then a paid one-shot A/B canary; (c) move the Wan2GP pin | W-09, W-10 |
| D5 | `--min-free-gb` value: D: has about 3 GB free; the preflight default is 10 GB | W-11 |
| D6 | Amend R28 to "script ≤ 7 MB, upload parts ≤ 3 MiB" (MISTAKES C4, §5.7) | W-11 |

### Files touched by more than one card (run strictly in ID order)
| File | Cards |
|---|---|
| director/build_h3_batch.py (+test) | W-01 → W-09 → W-10 |
| director/run_colab_batch.py (+test) | W-01 → W-11 |
| director/h3_director.py | W-01 → W-10 |
| h3/v4_to_h3.py | W-06 → W-07 |
| h3/compile_h3_sing8.py, h3/schema_and_linter.py | W-07 → W-10 |
| director/build_vo_tracks.py (+test) | W-04 → W-12 |
| score/cue_sheet.py (+test) | W-05 → W-12 |
| director/write_timeline_lock.py | W-03 → W-12 (one import line) |
| editorial_by_lang.py | read by W-03, deleted by W-12 |
| P1-only modules (shot_mode, shot_router, runner_safety, audio_edge, timeline_lock_core/io) | never edited here |

Parallel groups: W-02 runs alongside W-01. W-04 and W-05 run alongside each other once W-03 is done. W-08 can run any time after W-01.

---

### W-01: J8 port of the batch builder and Colab runner (git, not a folder diff)
- **Files:** director/build_h3_batch.py NEW; director/run_colab_batch.py NEW; director/test_build_h3_batch.py NEW; director/test_run_colab_batch.py NEW (all four from branch `v4-architecture-2026-11-07`); director/h3_director.py (one line).
- **Change:**
  1. Record in the checklist: `git diff --stat merge-v4-universal-2026-11-07 v4-architecture-2026-11-07 -- director/run_kaggle.py director/t0_pack/run_t0_colab.py director/h3_director.py h3/compile_h3_sing8.py h3/v4_to_h3.py h3/schema_and_linter.py`.
  2. Run `git checkout v4-architecture-2026-11-07 -- <the 4 NEW paths>`. Only those paths, never a whole-tree checkout.
  3. Edit merge h3_director.py:350. The faulty line is `"prompt": prompt_for(shot, frames, bible), "image_mode": 0, ...`. It becomes `"prompt": shot.get("prompt_override") or prompt_for(shot, frames, bible), ...`, which is the other tree's line 350. Without it, every `prompt_override` the builder writes (build_h3_batch.py:141) is silently replaced by the old director prompt.
  4. Keep the merge versions of all h3/* files (MISTAKES W6).
  5. Run the `harden()` anchors check: merge run_kaggle.py lines 40, 44, 51, 68, 69 must hold the exact strings that harden counts (already checked by reading: identical).
- **Tests to add (append to test_build_h3_batch.py):**
  - `test_prompt_override_reaches_settings`: synth story; `rows = legacy_rows(story, ep)`; `s = h3_director.settings_for(rows[0])`. Assert `s["prompt"] == rows[0]["prompt_override"]` and that the prompt does not start with `"[Shot 1] A "` (the prompt_for body).
  - `test_real_compiler_prompt_has_no_blank_line`: the same rows, built with the real compiler (no monkeypatch). Assert `"\n\n" not in prompt_override`. Today the raw compiler output has `"\n\n"` (compile_h3_sing8.py:83) and the builder collapses it.
  - `test_crlf_blank_line_collapsed`: monkeypatched compiler returns `"a\r\n\r\nb"`. Assert the result is `"a\nb"`. Note: the raise at build_h3_batch.py:138 cannot be reached after the regex on line 137. The real guard is the regex, and W-07 adds a compiler guard.
  - The existing `test_wrong_gpu_is_stopped` and `test_prompt_has_no_blank_line` must pass in the merge tree. They are the survival proof for problems 34 and 30.
- **Closes:** 36; 30 and 34 shown to survive the port. Bugs MISTAKES W6; prompt_override drop (new).
- **Depends on:** none.
- **Collisions:** creates the files used by W-09, W-10, W-11.
- **Acceptance:** `python -m pytest director/test_build_h3_batch.py director/test_run_colab_batch.py director/test_h3_director.py -q`; `git status --short director` lists exactly the 4 new files and h3_director.py.
- **Owner decision:** none. **Risk of a second attempt:** low. Note: `test_vendored_wheel_*` needs `D:\aai work\vendor\chumpy_0.71\...whl` to exist.

### W-02: voice_cast.py: preflight.json, pilot.json, wav_contract, audio_edge, no atempo, pronunciation flag, voice-account check
- **Files:** director/voice_cast.py; director/test_voice_cast.py.
- **Precondition (P1 audio_edge card):** `audio_edge` has a WAV writer (`write_wav_mono(path, samples, sr)` or the name P1 gave it) and decides fades by rms. Otherwise stop.
- **Change:**
  1. Add `sys.path.insert(0, str(Path(__file__).resolve().parent))`, `from wav_contract import require_wav, wav_name`, `import audio_edge`.
  2. **New `preflight(cast, script_sha, cast_sha, key, get=http, model="eleven_v4")`:**
     - For every lang/speaker/voice_id in the cast (keys starting with `_` skipped), call `get("GET", f"/v1/voices/{vid}", key)`. A RuntimeError means `present=False`.
     - `verified` is False only when `verified_languages` is non-empty and has no `{language==lang, model_id==cast._models[lang][speaker] or model}` entry. An empty list gives a warning `"no verified_languages"`.
     - `sharing.rate > 1` gives a warning `"rate x"`.
     - It returns `{script_sha256, cast_sha256, voices:[...], ok}`.
     - Subcommand `preflight` writes `<out>/preflight.json` and exits 0 if ok, else 1.
     - Source for the fields: https://elevenlabs.io/docs/api-reference/voices/get (`verified_languages[].language/model_id`, `sharing.rate`).
  3. **New `require_records(out, script_sha, cast_sha, jobs, pilot_mode)`**, called in `main` before `run()` (that is, before `led.reserve`, voice_cast.py:211):
     - `preflight.json` must exist, `ok` must be True, both shas must match (script sha = sha256 of shots.json bytes, as at line 368; cast sha = sha256 of voices_cast.json bytes), and every job `voice_id` must be present.
     - `--pilot`: every (lang, voice) appears at most once in the jobs.
     - Otherwise `pilot.json` must exist with the same shas, and every (lang, voice) of the jobs needs `owner_heard: true`.
     - Any failure raises SystemExit.
  4. **New subcommand `pilot-record --heard en/NARRATOR,... --names-ok hi/BRAHMA,...`:** writes `pilot.json` `{script_sha256, cast_sha256, voices:{"<lang>/<VOICE>":{line, seconds, chars, s_per_char, owner_heard, hard_names_ok}}}` from the manifest. Offline only.
  5. **`measured(..., hard_names=None, pilot=None)`:** `hard_names` comes from `<pack>/hard_names.json` `{lang:[names]}` (a missing file means none). A clip whose text contains a hard name, without `hard_names_ok` true for its voice, adds the problem `"<id>: hard name <n> not owner-approved"`.
  6. **`export_wavs`:**
     - `dst = wav_dir/"wav"/lang/wav_name(r["line"], r["lang"])`.
     - After ffmpeg TRIM: `require_wav(dst)`, then `audio_edge.read_wav_mono` → `apply_edges` → writer to a tmp file → `os.replace`.
     - **Delete** voice_cast.py:305-311 (the `atempo` branch, `.fit.wav`) and `MAX_TEMPO = 1.15` (line 265).
     - Report rows: `seconds_trimmed`, `seconds_final`, `slot`, verdict `"fits"` or `"longer than scripted slot (the timeline lock sizes the shot)"`. `fit_report` gets the same verdict wording.
     - `main export` calls `load_slots(Path(a.pack))` without the FINAL_TEXT_v2 path (line 357).
     - Before export: `shutil.disk_usage(wav_dir)` free < 1 GiB raises SystemExit.
- **Tests (tmp reel-2-style shots.json: 2 shots, N + D1, en/hi/mr, hi text containing "मन्मथ"):**
  - `test_preflight_missing_voice_blocks_run`: fake GET raises `"HTTP 404"` for one voice. Expect `ok False`; `require_records` raises SystemExit; fake POST was called 0 times.
  - `test_preflight_model_not_verified`: `verified_languages [{hi, eleven_multilingual_v2}]`, cast model eleven_v4. Expect `verified False`, `ok False`.
  - `test_run_without_pilot_exits_before_reserve`: no pilot.json, non-pilot. Expect SystemExit and the ledger file does not exist.
  - `test_pilot_mode_one_line_per_voice`: 1 line per voice passes; 2 lines for the same voice raise SystemExit.
  - `test_hard_name_unapproved_is_a_problem`: the problems list contains `"hard name मन्मथ"`.
  - `test_export_rejects_mp3_bytes`: monkeypatch ffmpeg to write `b"ID3"+b"\0"*20` to dst. Expect ValueError.
  - Replace `test_export_trims_edge_silence_and_fits_by_atempo` with `test_export_trims_no_atempo` (skip if no ffmpeg): 1 s sine + 0.3 s pad on each side; `seconds_trimmed` is between 0.95 and 1.1; `seconds_final >= seconds_trimmed` (no speed-up); `seconds_final <= seconds_trimmed + 0.17` (at most 80 ms lead + 60 ms tail + 30 ms slack); with slot 0.9 the verdict starts with `"longer than"`.
  - Update `test_fit_report_and_post_sends_job_model`: both verdict asserts become `startswith("longer than")`.
  - `test_no_atempo_in_source`: `"atempo" not in voice_cast.py` text.
- **Closes:** 9, 11 (in code; the owner still listens), 12, 13, 45 (local disk, partly). Bugs: Opus §2.13 (padding before the lock), §3 items 9/11/12/13; reverse-engineering B13.
- **Depends on:** P1 audio_edge.
- **Collisions:** none.
- **Acceptance:** `python -m pytest director/test_voice_cast.py director/test_wav_contract.py director/test_audio_edge.py -q`; `Select-String -Path director/voice_cast.py -Pattern atempo,MAX_TEMPO` finds nothing.
- **Owner decision:** D3 (hard_names location and list). Is an empty `verified_languages` acceptable for en? The 1 GiB floor. **Risk:** med.

### W-03: lock writer CLI (versioned)
- **Files:** director/write_timeline_lock.py NEW; director/test_write_timeline_lock.py NEW.
- **Change:**
  1. **Pure `plan_lock(rows, wav_seconds_fn, langs, acts, min_seconds) -> list`**, plus a CLI: `--pack --wav-root <.../wav_export/wav> --manifest --out-dir --langs [--acts acts.json] [--blocking-dir]`. Add `sys.path.insert(0, HERE); sys.path.insert(0, HERE.parent)`.
  2. **Seconds per shot and language:** `needed_sec([{id, start, natural: wav_seconds(wav_root/lang/wav_name(id, lang))}], 1.0)`, using `build_vo_tracks.scripted_lines` and `editorial_by_lang.needed_sec` (this already includes TAIL 0.10). `voice_seconds[sid] = {lang: need}`. If the blocking `min_seconds` is present, add `"min": min_seconds`. A shot with no lines and no `min_seconds` raises SystemExit(`"<sid>: silent shot needs blocking min_seconds"`). This fixes Opus bug 4 at the caller.
  3. **Beat grid:** `plan_shots([{id, bpm: bpm if snap else None}], voice_seconds, margin_frames=0)`. A shot with snap False and bpm not in {None, 60} that is not the last shot of its act (act = run of shots with the same cue, or the same bpm when there is no cue) raises SystemExit. The non-snap shot at the end of an act also resets the act start inside plan_shots, so two acts with the same BPM do not merge.
  4. **Handles:**
     - `v4_to_h3.fit_lattice([{id, episode:1, editorial_duration_sec: ed/24}])`. Its problems raise SystemExit; a reel of one shot raises SystemExit (`"one-shot reel unsupported"`).
     - Then `_seam_defaults(first, last, ed, pf)` and `_plan_handles(...)` must return problems `[]`.
     - Assert `trim_out - trim_in == edit_frames`.
     - `end_frame_position = trim_out_frame - 1`: the last frame shown, 0-based with trim_out exclusive. Opus wrote trim_out_frame, which is one frame past the cut.
     - The `head_handle`/`tail_handle` keys from plan_shots are made up (core.py:195): drop them.
  5. **Lock row:** `id, edit_frames, start_frame, method, beats, error_ms, spare, lattice_n, pixel_frames, trim_in_frame, trim_out_frame, head_handle_frames, tail_handle_frames, incoming_seam_type, outgoing_seam_type, end_frame_position, bpm, snap, cue, act_start_frame`. bpm is kept even when snap is False, because the cue sheet needs it.
  6. **Params:** first write `timeline_lock_vN.params.json` `{margin_frames:0, tail:TAIL, gap:GAP, tempo:1.0, fps:24, langs, lattice:"v4_to_h3.fit_lattice"}`. Inputs = shots.json, the manifest, the params file, every wav used, acts.json, and the blocking files used. So any change to a param or an input makes the lock stale without a P1 io change.
  7. **Versioning:** N = max existing + 1. If the target exists, raise SystemExit. Write `timeline_lock_vN.json` with `write_lock`, and `timeline_lock_vN.diff.json` listing the `[{id, old, new}]` edit_frames changes against vN-1 (rule 47: tell the music session what changed).
- **Tests (synthetic WAVs written with the `wave` module at 24 kHz):**
  - `test_needed_seconds_drive_edit_frames`: narration start 0.5, en 2.40 s, hi 2.00 s. needed = max(0.5+2.4+0.1, 0.5+2.0+0.1) = 3.0 s, so **72** frames, method `"free"`.
  - `test_snap_only_groove_shots`: S1 128 BPM snap, need 72. One beat = 11.25 frames; beat k=7 gives round(78.75) = **79** (spare 7). The bar candidate gives 90 (spare 18), so 79 wins. S2 128 BPM snap False (last of its act), need 72, gives 72. S3 60 BPM snap False gives 72. bpm column [128, 128, 60].
  - `test_non_snap_mid_act_refused`: SystemExit.
  - `test_handles_legal`: every row has 107 ≤ pf ≤ 345, (pf-5) % 17 == 0, `trim_out - trim_in == edit_frames`, `_plan_handles` problems `[]`, `end_frame_position == trim_out_frame - 1`.
  - `test_silent_shot_needs_min_seconds`: SystemExit without it; min 4.0 gives **96** frames.
  - `test_wav_byte_change_is_stale`: `verify_lock(p, lock["inputs"])` raises StaleLockError.
  - `test_params_change_is_stale`: same check after editing the params file.
  - `test_versioned_never_replaced`: two runs give v1 and v2; v1 bytes unchanged; the diff lists the changed shot.
- **Closes:** 2, 4, 5 (stored; owner accepts ±½ frame), 7, 8; 3 and 39 in part (one lattice picker; bpm, snap, cue stored). Bugs: Opus §2 items 2, 4, 5, 6, 8; reverse-engineering B12.
- **Depends on:** W-02 (exported WAVs with edges).
- **Collisions:** imports `needed_sec` from editorial_by_lang; W-12 moves that import. Uses the private v4_to_h3 functions read-only.
- **Acceptance:** `python -m pytest director/test_write_timeline_lock.py director/test_timeline_lock_core.py director/test_timeline_lock_io.py -q`.
- **Owner decision:** D3 (acts.json, ±20.83 ms). **Risk:** med.

### W-04: build_vo_tracks.py reads the lock
- **Files:** director/build_vo_tracks.py; director/test_build_vo_tracks.py.
- **Change:**
  1. Line 23 `MAX_TEMPO = 1.15` becomes `MAX_TEMPO = 1.0`.
  2. Line 44 `if cur <= limit:` becomes `if cur <= limit + 1e-9:`, because a lock length can equal the need exactly.
  3. **Delete** lines 80-81 (the editorial_by_lang import and `apply_rows`).
  4. `build(pack, raw_dir, out_dir, langs, lock_path)`: `lock = tl.verify_lock(p, tl.load_lock(p)["inputs"])`; `ed = tl.frames_for(lock, sid) / lock["fps"]`. A KeyError adds the problem `"<sid>: not in the timeline lock"`. The report row gets `edit_frames`.
  5. `main`: `--lock` is required. StaleLockError or FileNotFoundError makes it print and return 2.
- **Tests:**
  - `test_lock_length_fits_at_natural_speed`: start 0.5, natural 2.4, ed 72/24 = 3.0. Expect tempo 1.0, end **2.9**.
  - `test_exact_boundary`: natural 3.4, start 0, ed 3.5 (limit 3.4). No raise.
  - `test_stale_lock_exit_2`.
  - `test_lock_wins_over_editorial_file`: a tmp pack whose editorial_by_lang.json says +12 frames; monkeypatched `render_shot` captures editorial == **3.0**.
  - `test_tempo_limit_is_one`: `MAX_TEMPO == 1.0`.
- **Closes:** 2, 3 (the 1.15 limit gone here), 6 in part.
- **Depends on:** W-03.
- **Collisions:** W-12 later adds `needed_sec` here.
- **Acceptance:** `python -m pytest director/test_build_vo_tracks.py director/test_editorial_by_lang.py -q` (the latter still passes because editorial_by_lang still imports TAIL and pack_shot).
- **Owner decision:** none. **Risk:** low.

### W-05: cue_sheet reads the lock (must come before any editorial_by_lang retirement)
- **Files:** score/cue_sheet.py; score/tests/test_cue_sheet.py.
- **Change:**
  1. `build_cue_sheet(..., lock=None)`. When a lock is given:
     - `vo_reports is None` gives error `VO_REPORTS_REQUIRED`; `editorial is not None` gives error `LOCK_AND_EDITORIAL`.
     - New `apply_lock(shots, lock, fps)` sets `editorial_duration_sec = edit_frames / fps`. A missing id gives `LOCK_SHOT_MISSING`; an extra id gives `LOCK_SHOT_EXTRA`.
     - After `build_episodes` (line 412), any `view["frames"] != edit_frames` gives `LOCK_FRAMES_MISMATCH`. This guards against core.timeline rounding.
     - Shot rows get `bpm, snap, cue, act_start_frame`.
  2. `main`: `--lock`. Lazy `sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "director")); import timeline_lock_io as tl`; `verify_lock(p, load_lock(p)["inputs"])`. Stale or missing makes it print to stderr and return 2. `--editorial` stays and prints `"deprecated: use --lock"` (W-12 removes it).
- **Tests (reuse the synthetic builder in test_cue_sheet.py; never write EDITORIAL_V4):**
  - `test_lock_sets_frames`: edit_frames [79, 72] give shot frames [79, 72], total_frames **151**, shot 2 start_frame **79**.
  - `test_lock_requires_vo_reports`: sheet None, code `VO_REPORTS_REQUIRED`.
  - `test_main_missing_lock_exit_2`.
  - `test_main_stale_lock_exit_2`.
  - `test_lock_bpm_on_rows`: a non-snap shot still carries bpm 128.
- **Closes:** 39; 6 in part. Reverse-engineering B5 and the new collision (retirement order).
- **Depends on:** W-03.
- **Collisions:** W-12 later.
- **Acceptance:** `python -m pytest score/tests/test_cue_sheet.py -q`.
- **Owner decision:** none. **Risk:** med (build_episodes internals; the mismatch check guards them).

### W-06: v4_to_h3 takes lattice and trims from the lock
- **Files:** h3/v4_to_h3.py; h3/tests/test_v4_to_h3_lock.py NEW.
- **Change:**
  1. `convert_pack(..., lock=None)`. With a lock, work on a deep copy of the rows: `lattice_n = L.lattice_n`, `editorial_duration_sec = L.edit_frames / FPS`, and `h3_fields` incoming/outgoing seam types set from the lock. A row whose id is missing from the lock gets the problem `"<sid>: not in the timeline lock"` and is skipped.
  2. After `derive_fields` (line 672): trim_in, trim_out or pixel_frames different from the lock adds the problem `"<sid>: lock trims ... != derived ..."`.
  3. `timing_and_lattice` carries `end_frame_position` from the lock (data only; nothing reads it until W-10).
  4. `main`: `--lock`, checked through the recorded inputs; stale returns exit 2.
- **Tests (pack dicts built with the helper in h3/tests/test_v4_to_h3.py; lock rows from `write_timeline_lock.plan_lock`):**
  - `test_timing_equals_lock`: pixel_frames, trims and editorial_frames equal the lock rows for every shot.
  - `test_shot_missing_from_lock_problem`.
  - `test_tampered_lock_trim_problem`: trim_in + 1 gives the mismatch problem.
- **Closes:** 3 (the second lattice picker is bypassed), 4.
- **Depends on:** W-03.
- **Collisions:** v4_to_h3 is also edited by W-07, which runs after this card.
- **Acceptance:** `python -m pytest h3/tests -q`.
- **Owner decision:** none. **Risk:** med.

### W-07: v4_to_h3 + compile_h3_sing8 + schema_and_linter, one coordinated group (one commit)
- **Files:** h3/v4_to_h3.py; h3/compile_h3_sing8.py; h3/schema_and_linter.py; h3/tests/test_prompt_locks.py (fixture line 18 `"\n\n"` becomes `"\n"`); h3/tests/test_prompt_wiring.py NEW.
- **Precondition:** the BLOCKING-part loader exists (`load_blocking(pack, sid)` → `{cast:[{id,...}], sound_cues, ...}`). Otherwise stop.
- **Change:**
  1. **Blank line:**
     - compile_h3_sing8.py:83 `f"{header}\n\nintegrated_multimodal_description: ..."` becomes `\n`.
     - schema_and_linter.py:79 PROMPT_RE `target video\.\n\nintegrated_multimodal_description` becomes `\.\nintegrated_multimodal_description`.
     - At the end of `compile_fl2va_prompt`: `if "\n\n" in prompt: raise ValueError(f"{sid}: blank line in compiled prompt")`. This closes problem 30 in the file that runs.
  2. **Glue / SX-01 (D1):**
     - D1=B: v4_to_h3.py:160 becomes `sentence = "; ".join(x for x in actions if x)`. The stage cues go into `_soundscape(track, sid, problems, extra=stage_cues)` (deduplicated, lowercase match, still 1-4 sentences). Delete the SX vocabulary problem at lines 163-164. Linter: `SX_MIN_STAGE_CUES = 0` (line 112), and remove the stage check at lines 874-876.
     - D1=A: line 160 becomes `... + ("; " + "; ".join(x for x in cues if x) if any(cues) else "")`. SX-01 unchanged.
     - Both: the compiler raises ValueError if `prompt_hygiene.find_cue_glue(body)` or `find_duplicate_sentences(body)` is non-empty.
  3. **Sound nouns:** `check_sound_cue(snd, visible=[short_disambiguator of subjects_present] + props_present)` in `_fl2va` and `_ref2va`. A PromptError is a ValueError, so the linter's PR-00 catches it (schema_and_linter.py:761).
  4. **Cast from blocking:**
     - `convert_pack(..., blocking=None)`: `subjects_present` = the blocking cast ids. If the `character_positions` ids differ from them as sets, add the problem `"<sid>: cast {..} != blocking {..}"`.
     - The compiler inserts `cast_line([names])` into the body list after `speech` and before `_mouth_lock` (one line, so the regexes still match; used only when the subject list is non-empty).
     - Do **not** call `clean_prompt` (it breaks the `\Z` format) or `mouth_sentence` (D2 is still open).
  5. Start-only header and end position are **not** in this card (S is off, W-10 is conditional).
- **Tests (synth `story` fixture):**
  - `test_no_blank_line_any_shot`: no compiled prompt contains `"\n\n"`, and PROMPT_RE or REF2VA_RE matches.
  - `test_lint_errors_not_increased`: the `lint_story` error codes do not gain PR-01.
  - `test_glue_gone`: `_stages([{t0:0, t1:1, action_pose_expression:"Sati lifts the veil", audio_cue:"a veil snaps"}], 107, "S1", [])`: no sentence contains `"with a veil"` and `find_cue_glue` returns `[]`.
  - `test_banned_noun_refused`: soundscape `"serpents hiss softly in the dark corners of the hall"` raises with `"banned sound noun: serpents"`.
  - `test_cast_line_from_blocking`: the body contains `"Only Sati and Shiva appear in this shot; no extra figures or creatures appear."`
  - `test_cast_mismatch_problem`.
  - `test_duplicate_sentence_refused`: stage 5 text == stage 6 text raises ValueError.
- **Closes:** 26, 27, 30; Q4 (cast line). Bugs: Opus §2.10 a, b, f (c waits on D1); MISTAKES W9, Q3, Q4; reverse-engineering B9.
- **Depends on:** W-06; the BLOCKING loader (other part).
- **Collisions:** compile and linter files are edited again by W-10.
- **Acceptance:** `python -m pytest h3/tests -q`; `Select-String -Path h3/v4_to_h3.py -Pattern '", with "'` finds nothing.
- **Owner decision:** D1 (D2 stays open). **Risk:** high (format and regex coupling across about 40 h3 test files).

### W-08: offline trace: does `input_video_strength` survive? (pinned source `D:\aai work\kaggle_h3_test\wan2gp_src`, bd1ff59)
- **Files:** director/test_wan2gp_pin_trace.py NEW; research/WAN2GP_SOFT_END_TRACE_2026-11-11.md NEW.
- **What I found by reading (the test pins each fact):**
  1. Our side, first hop: `h3_director.settings_for` builds a fixed key set (h3_director.py:347-352), so any `input_video_strength` on a row is dropped before Wan2GP.
  2. The CLI path: `--process` → `_parse_settings_json` (wgp.py:2248) → `validate_task` → `clean_settings` (9734) → `fix_settings` (1993) → `minimax_h3_handler.fix_settings` **pops it** (handler:1360; also at 1416).
  3. The H3 model_def has no `"input_video_strength"` entry (the handler's only two mentions are the pops). So `input_video_strength_visible` is False (wgp.py:940-945), and `validate_settings` **forces 1.0** (wgp.py:1510-1511), applied through `inputs.update` (9744-9747).
  4. The pipeline itself can soften the end (pipeline.py:967; end and injected frames at 1010-1016), but no setting reaches it.
  5. `image_end_frame_position` is not a setting. It is computed as `current_video_length - tail_trim_frames - 1` (wgp.py:8318, with tail_trim from 8262). B lands on the last generated frame, the end of the tail handle.
  - Conclusion: on this pin SOFT_SE/KFI render as a hard SE, and "B at the cut" cannot be set.
- **Tests (skip if the source folder is missing):**
  - `test_pin_matches`: `run_kaggle.WAN2GP_COMMIT == "bd1ff5903cbc18b46c3cce3b75bd140870b536a2"`, and the local `.git/HEAD` equals it when present.
  - `test_settings_for_drops_strength`.
  - `test_handler_fix_settings_pops_strength`: AST of `fix_settings` and `update_default_settings`.
  - `test_h3_model_def_has_no_strength_key`: count of `"input_video_strength"` in the handler == 2, both `.pop`.
  - `test_wgp_forces_strength_1`: lines 1510-1511 text.
  - `test_end_position_not_read_from_inputs`: `inputs.get("image_end_frame_position"` occurs 0 times.
  - `test_task_json_dry_run`: synth story + tmp keyframe PNGs → `legacy_rows` → `run_kaggle.build(..., target="colab")`; decode the `__SETTINGS__` blob with the regex `settings in json\.loads\(base64\.b64decode\("([A-Za-z0-9+/=]+)"\)\)`. Assert that neither `input_video_strength` nor `image_end_frame_position` is a key. Do not call `build_h3_batch.main` (it writes into the repo).
- **Research note:** the 5 facts with file:line, and options D4 (a), (b), (c). For (b): handler patch plus a paid A/B canary.
- **Closes:** handoff step 3 (the trace). Bugs: Opus §1 E1 (strength lost), §2.3.
- **Depends on:** W-01.
- **Collisions:** none.
- **Acceptance:** `python -m pytest director/test_wan2gp_pin_trace.py -q`.
- **Owner decision:** D4 after reading the note. **Risk:** low.

### W-09: build_h3_batch rows from routes + shot_mode + lock (fails closed on soft end)
- **Files:** director/build_h3_batch.py; director/test_build_h3_batch.py.
- **Precondition (P1 shot_mode + shot_router):** `frame_row` copies `input_video_strength`/`end_frame_position`/`mid`, refuses `image_prompt_type` None, and enforces n in 6..20; the router has an SE row and maps S/REF_S to SE without the flag. Otherwise stop.
- **Change:**
  1. `legacy_rows(story, episode_id, resolution, ids=None, routes=None, lock=None, env=None) -> (rows, post_ids)`. `routes` (the `shot_router.plan_reel` output, from the router-wiring part) is required, else ValueError.
  2. A POST route is left out and its id added to `post_ids`.
  3. `frame = shot_mode.frame_row({id, image_prompt_type, pixel_frames: story pf, start, end, input_video_strength, end_frame_position}, env)`.
  4. Lock given and pf != lock pixel_frames: ValueError.
  5. `frame["input_video_strength"] not in (None, 1.0)`: ValueError(`"<sid>: route <r> needs input_video_strength <v>, which Wan2GP bd1ff59 drops (research/WAN2GP_SOFT_END_TRACE_2026-11-11.md); owner decision D4"`).
  6. Row: `end` only for SE (S has no end key, so `settings_for` gives image_prompt_type "S"). Keep the blank-line collapse.
  7. `main`: `--routes` and `--lock` are required (lock checked through the recorded inputs). Print the POST ids. Before `split_blobs`, decode the `__SETTINGS__` blob and add `settings_sha256 = sha256(json.dumps(settings[sid], sort_keys=True))` to each manifest shot (used by W-11's canary proof).
- **Tests:**
  - `test_se_route_has_end`.
  - `test_s_route_needs_flag`: env {} raises ShotModeError; with `{"SHOT_MODE_S_ALLOW":"1"}` the row has no `end`.
  - `test_post_route_skipped`: `post_ids == ["SHOT-002"]`.
  - `test_soft_se_refused_until_d4`: `match="drops"`.
  - `test_lock_pixel_mismatch_refused`.
  - `test_manifest_settings_sha` (monkeypatch `b.HERE = tmp_path`): the sha equals a recomputation.
- **Closes:** E1 (router/mode conflict wired); 35 in part (settings hash). Bugs: Opus §1 E1, §2.9.
- **Depends on:** W-01, W-07, W-08; P1 shot_mode/router; the router-wiring part.
- **Collisions:** build_h3_batch is edited again by W-10.
- **Acceptance:** `python -m pytest director/test_build_h3_batch.py h3/tests/test_shot_mode.py director/test_shot_router.py -q`.
- **Owner decision:** D4. **Risk:** med.

### W-10: soft end through a VM handler patch (CONDITIONAL: only if D4 = b)
- **Files:** director/build_h3_batch.py; director/h3_director.py; director/test_build_h3_batch.py.
- **Change:**
  1. `harden()` adds a step after `git checkout __COMMIT__`: an on-VM Python snippet edits `models/minimax_h3/minimax_h3_handler.py`.
     - It replaces both `ui_defaults.pop("input_video_strength", None)` with `pass`.
     - It inserts `"input_video_strength": {"label": "End Image Strength"},` after `"image_end_frame_position": True,` (handler:767).
     - Anchor counts must be exactly 2 and 1, else `note("SETUP FAILED: handler patch anchor")` and exit 1.
  2. `settings_for` copies `shot["input_video_strength"]` when the row has it (keep line 350 as is).
  3. `legacy_rows` passes the strength instead of refusing it (the W-09 refusal is removed).
  4. End position stays out of scope: placing B at the cut on this pin needs frame injection or rendering without a tail. That is a separate research item for the owner.
- **Tests:**
  - `test_handler_patch_applies_to_pinned_source`: run the snippet on a tmp copy of the pinned handler. Expect 0 pops left, the label present, and `wgp.input_video_strength_visible`-equivalent logic (label non-empty and "E" in "SE") True.
  - `test_patch_refuses_wrong_anchor`.
  - `test_strength_in_settings`: 0.6 appears in the decoded `__SETTINGS__`.
- **Closes:** SOFT_SE/KFI strength (E1) in code. The real proof is a paid one-shot A/B canary with the owner's go (not in this job).
- **Depends on:** W-09; D4 = b.
- **Collisions:** build_h3_batch, h3_director.
- **Acceptance:** `python -m pytest director/test_build_h3_batch.py director/test_h3_director.py -q`.
- **Owner decision:** D4 plus the canary units. **Risk:** med.

### W-11: run_colab_batch: preflight, G4, clip_verified with expected frames, stop_decision, sessions check, canary proof (DRY RUN only)
- **Files:** director/run_colab_batch.py; director/test_run_colab_batch.py.
- **Precondition (P1 runner_safety):** `clip_verified(results_dir, shot_id, expected_frames=None, frames_of=None)` (ffprobe `nb_read_frames`, `*.part` ignored); `stop_decision(..., expected_frames=None)` accepts a {id: int} dict; `preflight` default `max_script_mb` is 7.0. Otherwise stop.
- **Change:**
  1. **GPU:** line 208 `choices=("G4", "A100", "L4", "T4")` becomes `choices=("G4",)`.
  2. **`preflight_urls(req_text)`:** returns `"https://github.com/deepbeepmeep/Wan2GP.git"` plus every `@ https://...` URL whose line has no `sys_platform == "win32"`. chumpy is excluded because it is vendored and checked by `wheel_ok`. Pinned requirements.txt:98 is chumpy, :99 is smplfitter, :72-74 are win32 lines.
  3. **`free_checks(batch_dir, results, req_path, min_free_gb, head=None, disk_usage=None)`** returns a list of failures:
     - `runner_safety.preflight(urls, results, min_free_gb, script_path=run_py, max_script_mb=7.0, head=..., disk_usage=...)`.
     - Each `upload_*.py` larger than 3 MiB (3,145,728 bytes) fails; a split chunk is 3,000,000 characters plus a wrapper of about 80 bytes, which is under the limit.
     - `wheel_ok(build_h3_batch.WHEEL, WHEEL_SHA256)` must be True.
  4. **`main`:** the dry run **and** `--go` both run `free_checks`; any failure prints and returns 1. `--min-free-gb` is required (D5) and `--requirements` gives the pinned path.
  5. **Canary:** the manifest has n shots. If n > 1 and `--go`, `--canary-proof` is required; the proof's shot must be in the batch, its `settings_sha256` must equal this manifest's entry, and `clip_verified` and `owner_ok` must be true. Otherwise return 1 before any colab call. New offline flag `--write-canary-proof --owner-ok` (n == 1 only) writes the proof after `clip_verified(expected_frames)`.
  6. **`batch(..., expected, frames_of)`:**
     - `fetch_ready` marks a shot home only if `clip_verified(results, sid, expected_frames=expected[sid])`; this replaces the size-only test at lines 115-118.
     - After the final fetch: `d = stop_decision(ids, results, all_done=(rc == 0), expected_frames=expected)`. When rc == 0 and `d["stop"]` is False, keep the session, print `d["reason"]`, and raise RunError.
  7. **Sessions:** after a failed `colab new` (lines 129-134), print `"STRAY SESSION?: <line>"` for each listed session. In `finally`, after `stop`, run `run_cli(["sessions"], capture=True, check=False)`; if our name is still listed, print `"SESSION STILL LISTED: ..."`.
  8. **Dead-man:** `max_seconds = min(MAX_BATCH_SECONDS, deadman_seconds(0.75*max_frames, n))`.
  9. Never run `--go` in this job.
- **Tests (fake cli and popen; no network):**
  - `test_a100_refused`: argparse exit code 2.
  - `test_11_3mb_script_fails`: a sparse file of 11.3×2^20 bytes gives `"script too large"`.
  - `test_upload_part_limit`: 3,145,729 bytes fails; 3,000,080 passes.
  - `test_preflight_urls`: a fixture with chumpy, smplfitter and a win32 line gives `[wan2gp_git, smplfitter]`.
  - `test_head_504_blocks_dry_run`: returns 1 and output contains `"HTTP 504"`.
  - `test_go_without_canary_refused`: 2-shot manifest, returns 1, no `"new"` call.
  - `test_canary_wrong_sha_refused`.
  - `test_truncated_clip_not_home`: `frames_of` returns 100 against 175 expected; `got` stays empty.
  - `test_all_done_verified_stops` / `test_missing_clip_keeps_session`.
  - `test_failed_new_reports_stray`.
  - `test_sessions_checked_after_stop`.
  - `test_name_with_spaces_one_argument`: the download argument equals `f"{t0.OUT}/SHOT-001/Picture 1 0.mp4"`.
  - `test_deadman`: 2 × 175 frames gives (900 + 2×131.25) × 1.5 = **1744**.
  - Update the existing asserts `calls[-1] == "stop"` (test lines 52, 58, and any similar) to `"stop" in calls and calls.index("stop") < len(calls) - 1 and calls[-1] == "sessions"`.
- **Closes:** 29, 31, 32, 33, 34, 35 (gate), 45 (owner value). Bugs: MISTAKES C3-C7, W16, W17, P8; Opus §2.11; reverse-engineering B8.
- **Depends on:** W-01, W-09 (settings_sha256); P1 runner_safety.
- **Collisions:** run_colab_batch.
- **Acceptance:** `python -m pytest director/test_run_colab_batch.py director/test_runner_safety.py -q`; `python director/run_colab_batch.py <synthetic batch> --results <tmp> --min-free-gb 1 --requirements "D:\aai work\kaggle_h3_test\wan2gp_src\requirements.txt"`, a dry run that prints only (HEAD requests are free; the owner approves that network use).
- **Owner decision:** D5, D6. A real one-shot canary needs a later paid go. **Risk:** high.

### W-12: retire editorial_by_lang (last)
- **Files:** director/build_vo_tracks.py; director/write_timeline_lock.py (import line); score/cue_sheet.py; score/tests/test_cue_sheet.py; director/test_build_vo_tracks.py; director/editorial_by_lang.py DELETE; director/test_editorial_by_lang.py DELETE (with `git rm`).
- **Gate:** (1) the reel 2 voices exist, and the W-03 lock for reel 2 is shown next to the `editorial_by_lang.plan` output, shot by shot, and the owner accepts it; (2) the build_final_reel card (another part) no longer imports editorial_by_lang (build_final_reel.py:261-265); (3) W-04 and W-05 are done.
- **Change:**
  1. Move `needed_sec` (editorial_by_lang.py:76-80) unchanged into build_vo_tracks.py. write_timeline_lock imports it from there.
  2. cue_sheet: delete `apply_editorial` (339-382), the `editorial` parameter and branch (387, 395-400), and `--editorial` (601, 609-615).
  3. Delete the v4 editorial tests from line 452 of test_cue_sheet.py (they only read the reel 1 file).
- **Tests:** `test_needed_sec_at_a_speed_up_is_shorter` moves to test_build_vo_tracks: lines (start 0, natural 3.5) at tempo 1.0 give 3.5 + TAIL = **3.6**; at 1.5 give 2.5 + TAIL.
- **Closes:** 3 (the 1.03 limit gone), 39 (only one clock). Reverse-engineering D (retirement order).
- **Depends on:** W-04, W-05, the build_final_reel card, the owner gate.
- **Collisions:** build_vo_tracks, cue_sheet, write_timeline_lock.
- **Acceptance:** `python -m pytest director score/tests h3/tests -q`; `Select-String -Path director\*.py,score\*.py,h3\*.py -Pattern 'editorial_by_lang|apply_rows|apply_shots|MAX_SPEEDUP'` finds nothing.
- **Owner decision:** the gate in (1). **Risk:** low.

---
**Wiring owed by other parts (not P2):**
- **Owned by other cards:** render_controller timeline gate and Gate D on lock seconds; build_final_reel (lock rows, caption_fields, required `--reel`, delivery crop); the writer gate (script_inspect `from_pack`); `routes.json` from blocking via shot_router; the blocking.json schema and loader (needed by W-03 and W-07); the pre-commit hook install.
- **Needs a decision about who owns it:** the image_gates and clip_qa wiring.
