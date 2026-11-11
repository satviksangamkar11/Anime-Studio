Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything else byte-identical; do not add code that reads files at import time.

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



REVIEW BY LUNA:
`export_wavs` writes the edged audio directly to `dst`:

> `audio_edge.write_wav_mono(dst, edged, sr)`

The card requires writing to a temporary file and then replacing `dst`. Write to a temporary WAV in the same directory, call `require_wav` on it, then `os.replace(tmp, dst)`.

VERDICT: FIX-FIRST.

REVIEW BY DOTS:
The file `director/test_voice_cast_w02.py` is missing entirely from the module. The card requires tests to be added to `director/test_voice_cast.py`, but a separate file `test_voice_cast_w02.py` is present. This means the acceptance test (`python -m pytest director/test_voice_cast.py ...`) will not run these tests, and the requirements for the test names listed on the card are not met.

Additionally, the test `test_preflight_skips_underscore_keys` expects exactly 6 GET calls (2 languages × 3 speakers = 6), but the cast has 3 languages (en, hi, mr) and 2 speakers (NARRATOR, BRAHMA), which would be 6 calls only if the loop structure were correct. However, the test name and assertion do not cover the case where `_models` is present in the cast; the loop skips `_models` but the test does not verify that the model override is used correctly for Hindi/BRAHMA (it only checks that no GET is made for `_models`). More importantly, the test `test_preflight_model_not_verified` uses `hi_models=("eleven_multilingual_v2",)` but the cast does not have `_models` set, so the preflight uses the default model `eleven_v4` for all voices. The test expects `verified` to be False for Hindi, but the fake GET returns `verified_languages` with `model_id` `eleven_multilingual_v2`, while the code checks against the model from `voice_model(cast, lang, speaker, model)`. Since `cast.get("_models")` is None, the model used is `eleven_v4`, which does not match `eleven_multilingual_v2`, so `verified` is correctly False. However, the test does not set `_models` in the cast, so it does not test the actual override mechanism described in the card (where `cast._models[lang][speaker]` is used).

The test `test_export_trims_no_atempo` uses `slots={"L": 0.9}` but the `export_wavs` function expects `slots` to be a dict keyed by line id, and the test passes `slots={"L": 0.9}` which is correct. However, the test also calls `v.load_slots(pack)` and checks `slots["SHOT-001-N"] == 2.0`, which is correct, but the card requires that `main export` calls `load_slots(Path(a.pack))` without the FINAL_TEXT_v2 path. The test does not verify that `main export` is called; it only tests `load_slots` directly.

The test `test_no_atempo_in_source` checks that `"atempo" not in text and "MAX_TEMPO" not in text`, but the card also requires that the `atempo` branch (lines 305-311) and `MAX_TEMPO` (line 265) are deleted. The test only checks the string absence, which is weak but acceptable.

The most critical defect is the missing test file for the acceptance command.

VERDICT: FIX-FIRST