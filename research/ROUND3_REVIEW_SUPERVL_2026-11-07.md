

# BATCH r1_director (supervl) 11-07 04:32

=== FILE pack_validator.py ===
medium, pack_validator.py:475-478, why: when any `*_by_lang` key is present on a shot row, the validator emits ML-03 ("multilingual row is missing this key") for every one of the three keys (`narration_by_lang`, `dialogue_by_lang`, `captions_by_lang`) that is absent. The owner addendum allows one/two/all *languages* (en/hi/mr), and a shot may legitimately carry only narration (no dialogue/captions), so this is a false positive. It can also reject write_pack's own output when a shot omits `dialogue_by_lang`. concrete failing input: a shot row with `narration_by_lang: {en: {...}, hi: {...}, mr: {...}}` but no `dialogue_by_lang`/`captions_by_lang` → ML-03 errors for the missing keys. one-line fix: remove the "missing key" loop (lines 475-478); keep only the per-language coverage checks (479-483) and the no-`*_by_lang` check (484-485).

=== FILE write_pack.py ===
medium, write_pack.py:913, why: `episodes_from(text1)` is called directly in `run_staged` and raises ValueError ("stage 1 names no episodes") when the stage-1 answer names no episodes. That happens *after* stage 1 already passed `_validate_story` (which does not require episodes), the ValueError is not caught by `run_stage`, and `main` only catches `StageFailed`, so a stage-1 answer without episodes crashes the CLI with a traceback instead of a clean stage failure. concrete failing input: a stage-1 model answer whose ```json story block has no `episodes` list and no "Episode N:" lines → passes validation, then `episodes_from` raises → uncaught traceback. one-line fix: wrap the episode extraction so the failure is reported as a clean stage-1 failure (e.g. catch the ValueError in `run_staged` and raise StageFailed).

=== FILE story_state.py ===
no findings

FINAL:
- medium pack_validator.py:475-478 — ML-03 false positive requiring all three `*_by_lang` keys when any is present; remove the missing-key loop.
- medium write_pack.py:913 — `episodes_from(text1)` ValueError escapes `run_staged` uncaught (traceback when stage 1 names no episodes); catch and report as a clean stage-1 failure.


# BATCH r2_registry_retry (supervl) 11-07 04:40

Reasoning: I reviewed the three provided files for regressions, wrong/incomplete fixes, logic errors, spec violations, trust-boundary crashes, contract mismatches, and un-failable tests.

- `run_registry.py`: All write paths are wrapped in `@best_effort`/`_safe` and never raise; read paths (`summary`, `report_text`, `steps`, `runs`, `pack_models`, `pack_route`) use `.get()` and handle missing/malformed events gracefully. `_checked` is only invoked from `append_event`, which always supplies `kind`/`status`/`run_id`. Event pairing in `steps`, run status rollup, pack model attribution, source-hash drift checks, and atomic report writing all match the documented contract. No crashes on bad input were found at the boundaries exercised here.
- `retry_policy.py`: `classify_http`/`classify_exception`/`answer_kind` cover the documented kinds. `call_with_retry` honors the circuit breaker at call start, retries only `IN_PLACE` kinds within the wait budget, and raises `ModelGaveUp`/`CircuitOpen` (a subclass) for `call_chain` to handle. `is_free_model` requires every pricing value to be zero; `require_free` rejects non-free chains up front. No logic errors or contract mismatches found.
- `simple_language.py`: Whitelist masking, strict/non-strict caption handling, per-language blocks, fallback language resolution, and CLI error codes all match the documented behavior. Data-file errors raise `SimpleLanguageDataError`; malformed shot rows yield `ROW-01` instead of crashing. No defects found.

run_registry.py: no findings
retry_policy.py: no findings
simple_language.py: no findings

FINAL: no real defects found


# BATCH r3_h3_core (supervl) 11-07 04:46

**Reasoning (brief):** I checked the three files for regressions, wrong/incomplete fixes, logic errors, spec violations, and trust-boundary crashes. The in-scope round-2 fixes are correct: `schema_and_linter.py` guards non-object `timing_and_lattice` (SC-03 via `_run`) and non-object `episode_plan` (TM-05); `compile_h3_sing8.py` `compile_episode` wraps `KeyError`/`TypeError`/`ValueError`/`AttributeError` around workflow compilation, and `compile_fl2va_prompt` is safe because `lint_story` pre-validates; `router.py` `_ref_list`/`ref2va_limit_problems` handle non-list/non-dict keyframes (RF-03). The real defects are all uncaught exceptions on malformed profile/style input in `schema_and_linter.py`.

- **medium — schema_and_linter.py:408-429 & 912-917** — `lint_profile` unpacks `base_resolution` (419) and `aspect_ratio` (422) without type checks, and `lint_story` indexes `reg["execution_profile"]` (913) and calls `lint_profile` directly (917) with no try/except, so a corrupt profile crashes the lint with uncaught `KeyError`/`TypeError`/`ValueError` instead of a clean PO error attributed to the first shot. Failing input: `execution_profile.base_resolution = [1920]`, `aspect_ratio = "16:9:extra"`, or a missing `execution_profile`. Fix: validate `base_resolution` (2 ints) and `aspect_ratio` (`"int:int"`) in `lint_profile` before unpacking (report PO-03/PO-01), and guard `lint_story`'s profile access so errors are attributed to the first shot.
- **medium — schema_and_linter.py:292,486,495,506,768** — `pf / fps` (and `round(.../fps)`) in `_check_timing`, `_check_prompt`, `mouth_state_problems`, and `_check_window` raises uncaught `ZeroDivisionError` when profile `fps` is 0; `lint_profile` never validates `fps > 0`, and `ZeroDivisionError` is not in `_run`'s caught tuple. Failing input: profile with `fps: 0`. Fix: add an `fps > 0` check to `lint_profile` (report a PO error) so divisions are safe.
- **medium — schema_and_linter.py:792** — `re.search(rx, text, re.I)` with `rx = style.get("banned_negative_words_regex")` raises uncaught `re.error` (not in `_run`'s caught tuple) when the regex is invalid, crashing the lint. Failing input: `style_lock.banned_negative_words_regex = "["`. Fix: validate/compile `banned_negative_words_regex` (report a PO/PR error) or wrap the `re.search` in `try/except re.error`.

`compile_h3_sing8.py`: no findings. `router.py`: no findings.

FINAL:
1. medium schema_and_linter.py:408-429,912-917 — `lint_profile`/`lint_story` crash with uncaught KeyError/TypeError/ValueError on a malformed profile (bad `base_resolution`/`aspect_ratio`/missing `execution_profile`) instead of a clean PO error attributed to the first shot; validate profile field types and guard the `lint_story` profile access.
2. medium schema_and_linter.py:292,486,495,506,768 — uncaught `ZeroDivisionError` (`pf / fps`) when profile `fps` is 0; add `fps > 0` validation to `lint_profile`.
3. medium schema_and_linter.py:792 — uncaught `re.error` from an invalid `style_lock.banned_negative_words_regex` in `_check_prompt`; validate/compile the regex or wrap `re.search` in `try/except re.error`.


# BATCH r4_h3_gate_ctrl (supervl) 11-07 04:55

Brief reasoning: I reviewed the three supplied files against the owner spec (render once, en/hi/mr = ElevenLabs by default, h3 off-by-default for en only, BGM default none, captions bottom margin 896/top 360/sides 160, no default ElevenLabs/Colab/ffmpeg/model calls). `gate_d_audio.py` and `voice_engine.py` are consistent with the spec (the caption geometry only makes sense on a vertical/reel canvas, which matches "bottom margin 896", so `build_ass` does not reject every caption; `engine_for`/`resolve_engines`/`voice_engine_problems` correctly implement the off-by-default h3 rule). `render_controller.py` has real defects in the `--allow-partial` path and seconds computation.

gate_d_audio.py: no findings.
voice_engine.py: no findings.

- severity: medium, file:line: render_controller.py:329-333, why: `--allow-partial` calls `_write_shot` (which runs `resolve_keyframes`/`compile_fl2va_prompt`/`compile_comfyui_workflow`) with no try/except, so one compilation failure in a lint-ready shot propagates out of `prepare` and writes none of the ready shots, defeating `--allow-partial`; concrete: `python -m h3.render_controller --story-file S.json --scope shots --ids A,B --allow-partial` where A is lint-clean but `compile_fl2va_prompt(A)` raises → exit 1, zero partial writes although B is ready; fix: wrap each per-shot `_write_shot(...)` in try/except, skip failures, and continue writing the other ready shots.
- severity: low, file:line: render_controller.py:305-307, why: `seconds` is not clamped to 0 for negative `pixel_frames` and is `None` for float/`None` fps, contradicting the pipeline.py rule that zero/negative seconds count as 0; concrete: a shot with `pixel_frames=-50` and `fps=25` yields `seconds=-2.0` in readiness.json; fix: clamp `secs` to `max(0.0, round(pf / fps, 2))` and coerce numeric fps.

FINAL: medium render_controller.py:329-333 — `--allow-partial` aborts all partial writes when one ready shot fails to compile; low render_controller.py:305-307 — readiness seconds can be negative/None instead of clamped to 0. No real defects found in gate_d_audio.py or voice_engine.py.


# BATCH r5_h3_convert_author (supervl) 11-07 05:05

v4_to_h3.py:
- high, v4_to_h3.py:61 — `_is_num` admits `float("inf")`/`float("nan")`; `round(inf * FPS)` raises `OverflowError`, which `main` (line 666) does not catch (only OSError/ValueError/KeyError), so JSON `Infinity` in `editorial_duration_sec` or a directive `t0`/`t1` crashes the converter with an uncaught traceback (Python's `json` accepts `Infinity`/`NaN` by default). Concrete input: a `shots.json` row with `"editorial_duration_sec": Infinity` (or `"t0": Infinity` in `per_second_directives`). One-line fix: `return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)`.
- medium, v4_to_h3.py:502-503 — `reference_anchors.character_positions` holding a non-list scalar (e.g. `42` or `true`) makes `for c in positions or []` raise `TypeError: 'int' object is not iterable` in `_shot`, aborting conversion (lists/strings are iterable and filtered by the `isinstance(c, dict)` guard, but scalars crash before it). Concrete input: a shot row with `"reference_anchors": {"character_positions": 42}`. One-line fix: coerce `positions = positions if isinstance(positions, list) else []` right after line 502.

h3_author.py: no findings.

pipeline_contract.py: no findings.

voice_manifest.py:
- medium, voice_manifest.py:80 and :96 — `build_manifest` calls `narration_text(shot, lang)` (`shot.get(...)`) and `stale_entries` builds `{shot_id(s): s for s in shots}` (`s.get(...)`) without confirming each list item is a dict, so a non-dict item raises `AttributeError`. Concrete input: `python -m h3.voice_manifest --shots '[42]'` or `--shots '[{"id":"s1"}, 7]'`. One-line fix: skip non-dict items (`if not isinstance(shot, dict): continue`) in `build_manifest` and `stale_entries`.

FINAL: high v4_to_h3.py:61 `_is_num` admits inf/nan and `round(inf*FPS)` raises uncaught OverflowError in `main` (JSON `Infinity` crashes the converter); medium v4_to_h3.py:502-503 non-list `character_positions` scalar (e.g. `42`) raises TypeError in `_shot`; medium voice_manifest.py:80/96 non-dict shot items raise AttributeError in `build_manifest`/`stale_entries`.


# BATCH r6_ui_server (supervl) 11-07 05:12

severity: medium
file: pipeline.py:96-101
why: `shot_seconds` does not implement the round-2 rule that zero or negative seconds count as 0. It uses `editorial_duration_sec or seconds`, so a value of 0 or 0.0 is treated as missing and falls back to `seconds`; negative values are returned unchanged.
concrete failing input: a shot row `{"editorial_duration_sec": 0, "seconds": 10}` returns 10.0 instead of 0.0; `{"editorial_duration_sec": -5}` returns -5.0 instead of 0.0.
one-line fix: read `editorial_duration_sec` first, fall back to `seconds` only when it is `None`, then return `max(0.0, float(v))` after the non-bool numeric check.

severity: medium
file: pipeline.py:351
why: `facts` sets `n_shots = len(shots_data)` and `planned_clips = n_shots * takes`, counting non-dict items in `shots.json` even though `rows` already filters to dicts. This overstates shot count and planned clips.
concrete failing input: `shots.json` = `[{"id": "S1"}, "garbage", {"id": "S2"}]` reports `n_shots: 3` and `planned_clips: 3*takes` instead of 2 and 2*takes.
one-line fix: change to `n_shots = len(rows)` and `planned_clips = len(rows) * takes`.

severity: medium
file: pipeline.py:855-856
why: `_manifest_status` does `clips = manifest.get("clips", {})` then `clips.values()`. If `asset_manifest.json` has `"clips"` as a list or other non-dict, `.values()` raises AttributeError and the render-status endpoint crashes with 500.
concrete failing input: `asset_manifest.json` containing `{"clips": []}` or `{"clips": [{"id": "S1"}]}`.
one-line fix: `clips = manifest.get("clips", {}) if isinstance(manifest.get("clips"), dict) else {}`.

severity: low
file: server.py:734
why: `read_pack` uses `s.get("editorial_duration_sec") or s.get("seconds")`, so a shot with `editorial_duration_sec` of 0 falls back to `seconds` and displays the wrong value in the pack view.
concrete failing input: a shot row `{"editorial_duration_sec": 0, "seconds": 5}` shows 5 seconds instead of 0 in `/api/pack`.
one-line fix: `v = s.get("editorial_duration_sec"); if v is None: v = s.get("seconds"); "seconds": v`.

severity: low
file: pipeline.py:670-673
why: `summary` does `sid = shot.get("id")` then `sid in shot_ids` / `shot_ids.add(sid)`. If a shot row has a non-string unhashable `id` (list/dict), this raises TypeError and crashes the summary endpoint.
concrete failing input: `shots.json` containing `{"id": [1, 2]}`.
one-line fix: `sid = shot.get("id"); if not isinstance(sid, str): continue` (or coerce to str) before set operations.

FINAL:
1. pipeline.py:96-101 — `shot_seconds` does not clamp zero/negative seconds to 0 and `or` skips zero values, violating the round-2 fix.
2. pipeline.py:351 — `facts` counts non-dict shots in `n_shots`/`planned_clips`, overstating render scope.
3. pipeline.py:855-856 — `_manifest_status` crashes when manifest `clips` is not a dict.
4. server.py:734 — `read_pack` uses `or` for shot seconds, so zero seconds falls back to the `seconds` field.
5. pipeline.py:670-673 — `summary` raises TypeError on unhashable shot ids.


# BATCH r7_ui_js (supervl) 11-07 05:14

Reviewed `pipeline.js` (the only file provided) against the Round‑2 fixes and the owner spec.

- `api()` sends `X-UI: 1` on every request (line 179) and aborts after 120 s (lines 18–19, 181–182).
- Save‑story keeps the pack only when the slug matches the current project story, otherwise clears it (lines 735–737).
- `loadDetail` is single‑flight with a `detailAgain` rerun (lines 298–306); each sub‑request swallows its own errors so one panel failure cannot break the rest (lines 319–360).
- `next_step` reads `stage` or maps `key` via `NEXT_STAGE`, displays `label`/`text`, and passes `pack` to `continueStory` (lines 648–656, 756–766).
- Spec alignment: H3 English is off‑by‑default (lines 814–820), BGM defaults off (lines 836–837), safe‑zone text matches the spec (line 13), Gate A is blocked while the validator reports errors or has not run (lines 1135, 1161–1164, 1665), and gate decisions send story+pack (line 1757).
- Malformed server data is guarded (`&&`, `|| []`, `Array.isArray` not needed because non‑objects yield safe defaults); no trust‑boundary crash, no regressions, no logic errors found in this file.

pipeline.js: no findings

FINAL: no real defects found


# BATCH r8_ui_app_html_css (supervl) 11-07 05:21

Reasoning: I reviewed the three provided files (app.js, index.html, style.css) against the owner spec and the round-2 fixes that touch them. The only round-2 app.js fixes in scope are "api() sends X-UI on every request" (present at app.js:254) and "loadStory array guard" (present at app.js:590); both are correctly implemented and match the documented contract. index.html has the static panels/job bar removed as noted, and style.css is presentational only. The remaining round-2 fixes (pipeline.js, server.py, pipeline.py, h3 router.py, schema_and_linter.py, compile_h3_sing8.py, etc.) are not in the provided files, so I cannot verify them. Scanning the provided files for real defects: app.js uses textContent/createElement only (no XSS), sends X-UI on all requests, guards arrays, and validates inputs with PAT. No high-severity crash or injection was found. Issues observed: no fetch timeout in the only fetch path; a slug fallback that can read a missing property; an unguarded JSON.stringify on server data; an export dependency on an external global not present here; and a path helper that pops segments unconditionally.

- medium, app.js:252-278, `api()` runs `fetch` with no timeout; a non-responsive server hangs modals and the poller indefinitely, and the advertised round-1 API timeout is absent from the only fetch path. Fix: Add an AbortController with a ~30s timeout to `fetch` in `api()` and reject on timeout.
- low, app.js:596, `loadStory` falls back to `S.slugs[0].slug` without checking the property; a server slug entry missing `slug` makes the story `<select>` display the literal string "undefined". Fix: Use `(S.slugs[0] && S.slugs[0].slug) || ''` as the fallback slug.
- low, app.js:690, `renderPack` calls `JSON.stringify(p.check)` directly on server-supplied data; a circular or non-serializable `check` value throws and aborts the pack render. Fix: Wrap `JSON.stringify(p.check)` in try/catch and fall back to a safe string on error.
- medium (unverified), app.js:1321, `loadExport` reads `window.StudioWizard.project()` which is not defined in the provided files; if `pipeline.js` does not expose it, export always errors even with a valid story/pack selected. Fix: Source `story_slug`/`pack` from the local story UI state (`S.story.slug`, `$('story-pack').value`) instead of the external global.
- low, app.js:1107-1113, `qaDirFor` pops two path segments unconditionally; a clip path with fewer than two segments yields a bogus out_dir such as "/qa". Fix: Guard that `parts.length >= 2` before popping, otherwise use the clip's own directory.

FINAL: medium app.js:252-278 no fetch timeout; low app.js:596 slug fallback can be undefined; low app.js:690 JSON.stringify on untrusted check data can throw; medium (unverified) app.js:1321 loadExport depends on undefined window.StudioWizard; low app.js:1107-1113 qaDirFor can produce bogus out_dir.
