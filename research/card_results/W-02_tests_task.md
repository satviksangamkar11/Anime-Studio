Write ONLY the test file director/test_voice_cast_w02.py (plain pytest, standard library, tmp_path, no network, no model call; start with sys.path.insert of its own folder and the project root so the modules import by bare name or package as the neighbouring tests do). It is the frozen test gate for this gap card; the module change is made later by someone else, so the tests must FAIL on the current code and pass on a correct implementation. Use the hand-computed values written in the card; do not copy code from the module under test. Cover every test name the card lists.

CARD:
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



EXTRA HINT: 