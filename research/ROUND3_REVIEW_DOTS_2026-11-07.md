

# BATCH r1_director (dots) 11-07 04:32



## Review — Round 3 (files provided: `pack_validator.py`, `write_pack.py`, `story_state.py`)

I checked the three supplied files against the round-2 fix claims and for regressions/spec violations/crashes. The round-2 fixes **in these three files are mostly correct**:
- `pack_validator`: tone required (L296), single-language ML-06 (L465-467) + multilingual ML-06 (L499-501), bool-not-int at L111/L263/L559/L599, non-empty screen/depth (L257-258) — all present and correct.
- `write_pack`: shot-id/duplicate validation (L311-315), key-file + catalog-unreachable errors (L154-156, L170-173), JSON-decode error in `answer_text` (L280-281), shared retry policy in `call_path` with `ModelRefused` (L226-241) — correct.
- `story_state`: "resume with no missing stage" (L117-119) — correct, no `IndexError`.

---

### Findings

**[medium] write_pack.py:913 (via `episodes_from`, L368-388) — uncaught `ValueError` crashes the staged run with a traceback.**
`episodes_from(text1)` is called inside `run_staged` outside any `run_stage`/`checked_call` handler. If stage 1's `json story` block has an `"episodes"` list but **no element carries an integer `episode`** (e.g. `[{"title": "Intro"}]`), `found` is empty → `episodes_from` raises "stage 1 names no episodes". `_validate_story` (L689-717) only checks `story_gate_checks` *structure* (pass/evidence), not episode content — so stage 1 passes validation, then the pipeline dies with a raw traceback instead of `StageFailed`. `main()` (L1018-1021) only catches `StageFailed`.
Concrete failing input: `stage_1_raw.json` envelope whose result contains
```json
```json story
{"episodes": [{"title": "Intro"}], "story_gate_checks": {"episode_plan": {"pass": true, "evidence": "ok"}}}
```
```
One-line fix: make the story branch fall through to the line-regex path when it yields no integer episodes (move `found` init + `if not found:` around the elif/else), so a malformed block recovers instead of raising.

**[low] pack_validator.py:489-504 — `narration_by_lang[lang].language` is never validated against its key.**
ML-01 checks text + time_range, ML-05 checks cross-language timing, ML-06 checks within shot — but nothing requires `narration_by_lang["hi"].language == "hi"`. The writer's own `_narration_by_lang_errors` (LANG-01) checks it, but for stage 3 in staged mode `gate(..., merge=False)` runs the validator *only*, so a wrong `language` field slips through and is copied verbatim into the flat `narration` mirror by `apply_captions` (write_pack L852-853). Low probability (needs specific model output), but it is a real validation gap.
One-line fix: in the `for lang, e in nb.items()` loop add `and e.get("language") == lang` to the ML-01 condition (or emit a new ML code).

**[low] write_pack.py:955 (`run_single`) — `parse()` `ValueError` is uncaught → traceback.**
Single-call mode has no validator and no try/except around `parse(raw_path.read_text(...))`. A `raw_response.json` with no shots block, duplicate ids, or non-dict rows raises `ValueError` straight to `main()` (only `StageFailed` is caught). Pre-existing, not a round-2 regression, but it is a crash on bad input at a trust boundary.
One-line fix: wrap the parse/write block in `run_single` and convert `ValueError` to a clean `StageFailed`/error exit.

**[unverified — flagged] write_pack.py:176 — "empty-price model is NOT free" cannot be confirmed.**
`openrouter_is_free()` defers to `retry_policy.is_free_model(model, catalog)`, which is in a file not provided. The docstring (L169) says "True when every price field … is 0". If `is_free_model` treats a model with *missing/empty* pricing as free (vacuously "every field is 0"), then a paid model with no pricing data would be allowed — violating the owner's "no paid calls" rule. Verify `retry_policy.is_free_model` returns `False` when pricing fields are absent/empty.

**[unverified] Round-2 fixes in files not provided could not be checked.**
`ui/static/app.js` (X-UI, loadStory guard), `pipeline.js` (save-story pack scoping, loadDetail single-flight), `server.py` (record_spend timing, episode sort on mixed types), `pipeline.py` (zero/negative shot seconds), `h3/router.py` (RF-03 non-dict keyframes), `schema_and_linter.py` (non-object timing_and_lattice/episode_plan, asset_root), `compile_h3_sing8.py` (compile_episode exception wrapping, episode-not-found, missing profile key), `gate_d_audio.py` (PLAN-01, TIME-01, empty BGM, reel id sanitize), `render_controller.py` (default language hi), `v4_to_h3.py`/`h3_author.py` (trim/handles/seams, author lint+repair, cache), plus `run_registry.py`, `retry_policy.py`, `h3/voice_engine.py`, `writer_prompts.py`, `h3_director.py`, `story_links.py`, `simple_language.py` — none of these were supplied, so their round-2 fixes are **unverified**. Also note `story_state.py` still documents (L11-12) that gate approvals count for the whole story "until the UI scopes approvals per pack" — the owner spec requires story+pack scoping; that fix is expected in the UI layer, not here.

---

FINAL:
1. **medium** — `write_pack.py:913`/`episodes_from`: stage-1 block with an `episodes` list but no integer `episode` crashes the staged run (uncaught `ValueError`); fall through to the line-regex path instead of raising.
2. **low** — `pack_validator.py:489-504`: `narration_by_lang[lang].language` not checked against the key in the validator (only the writer's own check covers it, which is skipped for stage 3).
3. **low** — `write_pack.py:955` `run_single`: `parse()` `ValueError` uncaught → traceback on a malformed `raw_response.json`.
4. **unverified/flagged** — `write_pack.py:176` `retry_policy.is_free_model`: confirm empty/missing pricing is treated as NOT free (otherwise a paid model with no pricing data is allowed).
5. **unverified** — ~16 files (app.js, pipeline.js, server.py, pipeline.py, router.py, schema_and_linter.py, compile_h3_sing8.py, gate_d_audio.py, render_controller.py, v4_to_h3.py, h3_author.py, run_registry.py, retry_policy.py, voice_engine.py, writer_prompts.py, h3_director.py, story_links.py, simple_language.py) not supplied; their round-2 fixes could not be checked.


# BATCH r2_registry_retry (dots) 11-07 05:04



=== FILE run_registry.py ===
1. **Medium** — `detect_language` (line 255‑258) uses a hard threshold of 20 Devanagari characters; a short Hindi text such as “नमस्ते” (5 chars) is misclassified as English.  
   *Failing input*: `detect_language("नमस्ते")` returns `"en"`.  
   *Fix*: lower the threshold or use Hindi‑specific markers (e.g. the presence of “ह”/“हैं”) instead of a raw count.

2. **Low** — `_checked` (line 366‑371) allows `voice_engine` to be an empty dict `{}`. Downstream code that expects at least one language key will crash (e.g. `engine["en"]`).  
   *Failing input*: `append_event(dir, run, "test", None, "ok", voice_engine={})` succeeds; later `voice_engine["en"]` raises `KeyError`.  
   *Fix*: require at least one key when `voice_engine` is present.

3. **Low** — `pack_summary` (line 140) sums `seconds` only when the value is an `int` or `float`; a valid numeric string (e.g. `"3.5"`) is silently ignored, under‑reporting total duration.  
   *Failing input*: `shots.json` with `{"seconds": "3.5"}` → `pack_summary` returns `seconds: 0.0`.  
   *Fix*: attempt `float(s["seconds"])` in a try/except after the type check, or normalise the data earlier.

=== FILE retry_policy.py ===
1. **Low** — `CircuitBreaker.allow` (lines 144‑150) has a race condition: two threads can both see `self.trial is False`, both set it to `True`, and both be allowed a trial call.  
   *Failing input*: two concurrent calls to `call_with_retry` when the breaker is half‑open.  
   *Fix*: guard the check‑and‑set with a lock or use an atomic compare‑and‑set.

2. **Low** — `call_with_retry` (lines 172‑195) can raise `AssertionError("unreachable")` if `policy.max_attempts` is 0 (the loop body never executes).  
   *Failing input*: `call_with_retry(fn, policy=Policy(max_attempts=0))`.  
   *Fix*: validate `max_attempts > 0` when the `Policy` is created or at the start of `call_with_retry`.

=== FILE simple_language.py ===
1. **Low** — `_check_en` (lines 221‑225) splits sentences with the regex `(?<=[.!?…])\s+|\n+`, which does not split when punctuation is followed by a closing quote. A long sentence ending in `."` will be kept whole and can falsely trigger SEN‑01.  
   *Failing input*: `"This sentence is far too long and should be split."` (25 words) is not split, flagged as SEN‑01.  
   *Fix*: add `["”"‘’]` to the look‑behind or post‑process quotes.

2. **Low** — `check_shot_texts` (lines 440‑453) treats invalid language hints inconsistently: a strict caption (from `captions_by_lang`) with a bad key gets a LANG‑02 flag, but a non‑strict caption with the same bad key is silently skipped when any `captions_by_lang` block exists.  
   *Failing input*: a shot with `caption: {text: "hi", language: "xyz"}` and a `captions_by_lang` block → the invalid key is not flagged.  
   *Fix*: apply the same LANG‑02 check to non‑strict captions before skipping.

=== FINAL ===
1. **run_registry.py:255** — `detect_language` threshold misclassifies short Hindi as English (medium).
2. **run_registry.py:366** — empty `voice_engine` dict passes validation and can crash downstream (low).
3. **run_registry.py:140** — numeric strings in `seconds` are ignored by `pack_summary` (low).
4. **retry_policy.py:144** — `CircuitBreaker.allow` race condition allows multiple trial calls (low).
5. **simple_language.py:221** — sentence‑split regex misses punctuation‑quote boundaries, causing false SEN‑01 flags (low).


# BATCH r3_h3_core (dots) 11-07 05:15



After reviewing the three provided files against the round-2 fix list and the owner spec, here are my findings.

## Verification of round-2 fixes in the provided files

**router.py RF-03 (non-dict keyframes):** Correct. `ref2va_limit_problems()` at line 56-57 checks `not isinstance(k.get(key), list)` for `reference_images`, `reference_videos`, `reference_audio`. This catches strings, dicts, numbers, etc. It does not break existing logic — the check is additive and only fires on malformed refs.

**schema_and_linter.py non-object timing_and_lattice:** Correct. Lines 959-961 guard `tl.get("editorial_frames")` with `isinstance(tl, dict)`, and `_check_timing` is wrapped in `_run` so a non-dict `timing_and_lattice` produces SC-03 instead of crashing. The `running` accumulator stays at the previous shot's value, which is the safe fallback.

**schema_and_linter.py non-object episode_plan:** Correct. Lines 975-977 report TM-05 and replace a non-dict `episode_plan` with `{}` so the subsequent `.get("target_editorial_frames")` returns None and the target check is skipped rather than crashing.

**compile_h3_sing8.py compile_episode wraps TypeError/ValueError/AttributeError:** Partially correct. Lines 204-205 wrap `compile_comfyui_workflow` correctly. However, `compile_fl2va_prompt` at line 199 is called **outside** any try/except. If it raises after `lint_story` passes, the function crashes with an unhandled exception.

---

## Real defects found

**LOW — schema_and_linter.py:915,941 — `lint_story` crashes on an episode missing `shots`**
Lines 915 (`all_shots = [s for ep in story["episodes"] for s in ep["shots"]]`) and 941 (`shots, running = ep["shots"], 0`) access `ep["shots"]` directly. If an episode dict lacks the `shots` key, `lint_story` raises an unhandled `KeyError` instead of reporting a validation error. This is a trust-boundary crash on malformed input.
*One-line fix:* Guard with `ep.get("shots", [])` and report an `EP-01` error when `shots` is missing or not a list.

**LOW — compile_h3_sing8.py:199 — `compile_fl2va_prompt` unwrapped in `compile_episode`**
Line 199 calls `compile_fl2va_prompt(shot, reg)` outside the try/except that wraps line 201. While `lint_story` at line 189 should catch any prompt failure first, if a prompt compiles successfully during lint but fails during the second call (e.g., due to a state mutation, a non-deterministic `refuse_speech_in_source` path, or a future code change), the pipeline crashes with an unhandled exception instead of a clean `ValueError`.
*One-line fix:* Move line 199 inside the existing try/except or add a separate `except (KeyError, TypeError, ValueError, AttributeError) as exc: raise ValueError(f"{sid}: prompt could not be compiled ({type(exc).__name__}: {exc})") from exc`.

**LOW — schema_and_linter.py:843-873 — `_check_pure_foley` can partially fail, skipping later checks**
`_check_pure_foley` is called via `_run` (line 892). If `mouth_state_problems` at line 843 raises (e.g., `dialogue_and_lip_lock` is not a dict), `_run` catches it and reports SC-03, but the SX-01 sound-cue check (line 846-848), the RF-03 ref check (line 849-851), and all VA-* voice-anchor checks (lines 852-873) are silently skipped. A single malformed field can suppress multiple real errors.
*One-line fix:* Wrap each major section of `_check_pure_foley` in its own try/except, or restructure so that a failure in one section does not prevent later sections from running.

---

## Files with no real defects

**router.py** — No findings. The RF-03 fix is correct, `ref_inventory` handles non-list refs safely via `_ref_list`, and `route_shot` guards with `_has`. No regressions.

**schema_and_linter.py** (other than the three items above) — No findings. The non-object `timing_and_lattice` and `episode_plan` fixes are correct and complete. All other `_check_*` functions are properly wrapped in `_run`.

**compile_h3_sing8.py** (other than the one item above) — No findings. The `compile_episode` wrapping of `compile_comfyui_workflow` is correct. The `episode not found` check (line 186-187) and the `KeyError`→`ValueError` conversion for profile entries (line 202-203) are correct.

---

FINAL:
1. LOW — schema_and_linter.py:915,941 — `lint_story` crashes with unhandled `KeyError` if an episode dict lacks the `shots` key; guard with `ep.get("shots", [])` and report EP-01.
2. LOW — compile_h3_sing8.py:199 — `compile_fl2va_prompt` is called outside the try/except in `compile_episode`; wrap it to prevent an unhandled exception if lint somehow misses a prompt failure.
3. LOW — schema_and_linter.py:843 — `_check_pure_foley` can skip SX-01, RF-03, and VA-* checks if `mouth_state_problems` raises; isolate each section so one failure does not suppress others.
4. No findings — router.py RF-03 fix is correct and non-breaking.
5. No findings — schema_and_linter.py non-object `timing_and_lattice` and `episode_plan` fixes are correct and complete.


# BATCH r4_h3_gate_ctrl (dots) 11-07 05:22



## Findings

### Verified round-2 fixes (correct, no regression)
- **gate_d_audio**: per-language PLAN-01 guard (814-818), TIME-01 on bad range (809-811, 834-865), empty BGM tracks = no BGM (668), reel id sanitized (794) — all present and correct.
- **render_controller**: default language `hi` fallback (566) — correct.
- **voice_engine**: `H3_SPEECH_LANGS = ("en",)`, VE-01 rejects h3 for hi/mr (78-79), VE-04 warning (82-83) — correct.

### Real defects

**1. medium — gate_d_audio.py:187-192 — `mouth_state` crash on non-dict**
`pn.get("mouth_state") or {}` does not protect against a non-dict truthy value (string, list). If `performance_notes.mouth_state` is `"closed"` or `["closed"]`, `mouth.get(str(sec))` raises `AttributeError: 'str' object has no attribute 'get'`. Not caught by the `except` at line 826.
**Fix:** `mouth = pn.get("mouth_state"); if not isinstance(mouth, dict): mouth = {}`

**2. medium — gate_d_audio.py:99-102 — `dialogue` items crash on non-dict**
`for d in trk.get("dialogue") or []:` then `d.get("time_range")`. If `dialogue` contains a non-dict element (string, number), `d.get` raises `AttributeError`. The `except (ValueError, KeyError, TypeError)` at line 826 does not catch `AttributeError`.
**Fix:** guard with `isinstance(d, dict)` or add `AttributeError` to the except clause.

**3. medium — gate_d_audio.py:848 — `same_timing_problems` crash on non-dict `*_by_lang`**
`(trk.get(key) or {}).items()` — if `narration_by_lang`/`dialogue_by_lang`/`captions_by_lang` is a non-dict truthy value (e.g., a string), `.items()` raises `AttributeError`. Only `ValueError` is caught at line 810.
**Fix:** guard with `isinstance(..., dict)` or catch `AttributeError` at line 810.

**4. medium — render_controller.py:550 — `_gate_d_result` does not catch `AttributeError`**
`except (KeyError, TypeError, ValueError)` misses `AttributeError`. Since `plan_language_outputs` can raise `AttributeError` (from defects 2, 3, 6, 7), a bad story JSON can crash the entire pipeline planning with an unhandled traceback.
**Fix:** add `AttributeError` to the except tuple.

**5. medium — gate_d_audio.py:170 — `story_gate_checks` crash on non-dict**
`(story_gate_checks or {}).get(...)` — if `story_gate_checks` is a non-dict truthy value (list, string), `.get()` raises `AttributeError`. Not caught at line 826.
**Fix:** `gate = story_gate_checks if isinstance(story_gate_checks, dict) else {}`

**6. medium — gate_d_audio.py:628-632 — `_lang_view_track` crash on non-dict `audio_and_dialogue_track`**
`trk = shot.get("audio_and_dialogue_track") or {}` then `_lang_track(trk, lang)` calls `trk.get(...)`. If the track is a non-dict truthy value, `AttributeError` propagates uncaught (line 826 misses it).
**Fix:** `trk = shot.get("audio_and_dialogue_track"); if not isinstance(trk, dict): trk = {}`

**7. low — gate_d_audio.py:829-830 — VE-04 warning mis-applied to non-English languages**
`if eng == "h3":` adds the "en=h3 breaks the render-once rule" warning for any language. For `hi`/`mr` with `h3`, the PLAN-01 error is already emitted at line 814-818, but the misleading warning is also appended.
**Fix:** `if eng == "h3" and lang == "en":`

---

FINAL:
1. medium, gate_d_audio.py:187-192, `mouth_state` non-dict crashes `.get()` (AttributeError uncaught at 826) — `mouth = pn.get("mouth_state"); if not isinstance(mouth, dict): mouth = {}`
2. medium, gate_d_audio.py:99-102, `dialogue` non-dict elements crash `.get()` (AttributeError uncaught at 826) — guard `isinstance(d, dict)`
3. medium, gate_d_audio.py:848, `*_by_lang` non-dict crashes `.items()` (AttributeError uncaught at 810) — guard `isinstance(..., dict)`
4. medium, render_controller.py:550, `_gate_d_result` except misses `AttributeError` — add `AttributeError` to the tuple
5. medium, gate_d_audio.py:170, `story_gate_checks` non-dict crashes `.get()` (AttributeError uncaught at 826) — `story_gate_checks if isinstance(story_gate_checks, dict) else {}`
6. medium, gate_d_audio.py:628-632, `_lang_view_track` non-dict track crashes `.get()` (AttributeError uncaught at 826) — `if not isinstance(trk, dict): trk = {}`
7. low, gate_d_audio.py:829-830, VE-04 warning fired for non-English `h3` languages — `if eng == "h3" and lang == "en":`


# BATCH r5_h3_convert_author (dots) 11-07 05:32

", "", text or "", flags=re.S)
if "</think>" in text:
    text = text.rsplit("</think>", 1)[1]
return text.split("<think>", 1)[0].strip()
```
First removes all  pairs. Then if  remains, takes everything after the last . Then takes everything before the first . 

Wait — this is odd. If the text is "thinking...ANSWER", after removing  pairs (none),  not in text → skip. Then `text.split("


# BATCH r6_ui_server (dots) 11-07 05:36



FINAL:

- **medium**, `pipeline.py:96-101` — `shot_seconds` returns negative values when `editorial_duration_sec` or `seconds` is negative, but the spec says zero or negative shot seconds count as 0. The later clamping in `summary` is a workaround, not a fix.  
  **Fix:** `return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else 0.0`

- **medium**, `pipeline.py:690-691` — `summary` sorts episodes with `key=lambda x: str(x[0])`, which sorts “10” before “2” for numeric episode ids. The server-side `read_pack` already has a mixed-type sort; this was missed.  
  **Fix:** use the same mixed-type key as `server.py:742-744` (separate numeric and string episodes).

- **low**, `server.py:733-739` — `read_pack` uses `num()` for shot seconds, which does not clamp negative values to 0, while `pipeline.py` now does. This inconsistency can show negative seconds in the pack view.  
  **Fix:** in `num()` or at the call site, treat negative seconds as 0.

- **low**, `server.py:1249-1250` — `Api.run` sets `rec["used"] = True` before calling `_start`. If `_start` raises (e.g., Popen fails), the token is already spent and the client must preview again.  
  **Fix:** move `rec["used"] = True` to after a successful `_start`, or reset it in a `finally` block.

- **medium**, `pipeline.py:279-282` — `h3_plan` accesses `g["episode"]["episode_id"]` and `sh["id"]` without `.get()`. If the H3 modules return a malformed group (e.g., missing keys), the server crashes with a 500.  
  **Fix:** use `.get()` with sensible defaults or wrap the access in a try/except that reports a clear error.


# BATCH r7_ui_js (dots) 11-07 06:04



## Findings

### 1. `confirmDialog` resets `State.busy` before the user responds
**Severity: medium**  
**File: pipeline.js, lines 954-990 (runLink), 1048-1055 (analysisActions), 1270-1281 (buildImageJobs), 1448-1457 (renderActions prepare), 1567-1576 (authorPanel)**

In every command that uses `confirmDialog`, the `.finally` block attached to the `post('/api/preview', ...)` promise runs immediately after the `.then` callback returns — **before** the user clicks Run or Cancel. That `.finally` sets `State.busy = false`, so the UI re-renders (or could re-render on the next poll) while the confirmation modal is still open. The user could then click another button or the page could appear "not busy" mid-confirmation.

The same pattern also means `State.busy` is already `false` when the `onConfirm` callback runs (except in `runLink` and `buildImageJobs`, where `onConfirm` manually sets it back to `true`).

**Concrete failing path:**  
Click "Run story analysis" → server responds with preview → confirmation modal appears → `.finally` fires → `State.busy = false` → a poll tick re-renders the wizard → the modal is detached or the page shows "No job running" while the modal is still open.

**One-line fix:**  
Move `State.busy = true` into the `onConfirm` callback and remove the premature `.finally` reset, or restructure so the confirmation is awaited before the outer `.finally` runs.

---

### 2. `onConfirm` callbacks in `analysisActions`, `authorPanel`, and `renderActions` prepare do not set `State.busy = true`
**Severity: medium**  
**File: pipeline.js, lines 1048-1052 (analysisActions), 1567-1573 (authorPanel), 1448-1454 (renderActions prepare)**

After the `.finally` block resets `State.busy = false`, the `onConfirm` callback should set it back to `true` before starting the job. In these three places, `onConfirm` goes straight to `post('/api/run', ...)` without setting `State.busy = true`. The job runs with no busy flag, so the UI does not show a "running" state and the user could start another operation concurrently.

**Concrete failing path:**  
Click "Run author (free model)" → type the phrase → click "Run" in the modal → `onConfirm` fires → `post('/api/run', ...)` starts immediately → `State.busy` is still `false` → the page shows "No job running" while the author job is executing.

**One-line fix:**  
Add `State.busy = true;` as the first statement inside each `onConfirm` callback (or ensure the caller sets it before invoking `onConfirm`).

---

### 3. `NEXT_STAGE` fallback hardcodes `fix_failed_stage` → `analysis`
**Severity: low**  
**File: pipeline.js, line 628**

The `NEXT_STAGE` map is used only when the server's `next_step` object does not include a `stage` field. If the server sends `key: 'fix_failed_stage'` without `stage`, the UI always jumps to the `analysis` stage, even if the actual failed stage was `images` or `render`. This is a incorrect fallback that could misdirect the user.

**Concrete failing path:**  
A render-stage job fails → server sends `next_step: { key: 'fix_failed_stage', label: '…' }` (no `stage`) → the "Continue" button sets `State.jumpTo = 'analysis'` → the user is scrolled to the analysis card instead of the render card where the failure occurred.

**One-line fix:**  
Remove `fix_failed_stage` from the `NEXT_STAGE` map (or map it per-stage based on additional server fields) so that a missing `stage` falls through to no jump rather than jumping to the wrong stage.

---

### Unverified

- **`findJobsFile` path prefix (`'flow/' + names[i]`)**: The function filters jobs to those under `generated/<slug>/` and then prepends `flow/`. If the job `file` field already contains `flow/`, the resulting path would be duplicated. Cannot confirm without the server contract.
- **`loadStory` expects `data.text`**: The code does `data && data.text ? data.text : ''`. If the server ever returns the story text as a plain string instead of `{text: "…"}`, the textarea would be cleared. The API contract is not visible.

---

FINAL:  
1. `confirmDialog` resets `State.busy` before user confirmation (medium) — pipeline.js:954-990, 1048-1055, 1270-1281, 1448-1457, 1567-1576  
2. `onConfirm` in `analysisActions`, `authorPanel`, `renderActions` prepare does not set `State.busy = true` (medium) — pipeline.js:1048-1052, 1567-1573, 1448-1454  
3. `NEXT_STAGE` fallback hardcodes `fix_failed_stage` → `analysis` (low) — pipeline.js:628


# BATCH r8_ui_app_html_css (dots) 11-07 06:15



## Analysis

I reviewed the three provided files (`app.js`, `index.html`, `style.css`) against the round-2 UI fixes: "api() sends X-UI on every request" and "loadStory array guard". Both fixes are correctly implemented. The static panel removal in `index.html` is also correct. The other round-2 fixes live in files I don't have (`pipeline.js`, `server.py`, `pipeline.py`, `h3/router.py`, `schema_and_linter.py`, `compile_h3_sing8.py`, etc.) and cannot be verified.

Beyond the round-2 fixes, I found the following real defects in the provided files:

---

### 1. `h3Run()` omits shot-file validation that `videoPrepare()` has

**Severity:** medium
**File:** `app.js:1187-1200`

`videoPrepare()` (line 1171-1172) checks `if (!shots) return showError('Pick a shot file.')` before building args. `h3Run()` skips this check, so when the `video-shotfile` dropdown is empty (e.g. before `/api/video` has loaded, or if it returned no files), it sends `args.story = ""` to the server. The server may interpret an empty story path as a default or crash. The fix is to add the same guard:

```js
var shots = $('video-shotfile').value;
if (!shots) return showError('Pick a shot file.');
```

**Concrete failing path:** Open the Video section → click "Prepare (H3, no GPU)" before the shot-file dropdown has populated → an empty `story` field is sent to `h3_prepare`.

---

### 2. `openPacket()` sends an unvalidated `shot_id` inside an array

**Severity:** low
**File:** `app.js:771-778`

```js
var r = await api('POST', '/api/packet', { jobs: JOBS_DIR + j.file, shots: [j.shot_id] });
```

If the server returns a job entry with a missing `shot_id`, `j.shot_id` is `undefined`. `JSON.stringify([undefined])` produces `[null]`, sending a literal `null` shot id to `/api/packet`. The server may reject this with a confusing error. The fix is to coerce or guard:

```js
shots: [String(or(j.shot_id, ''))]
```

**Concrete failing input:** Server returns `{file: "flow_x.json"}` (no `shot_id` key) → `shots: [null]` is POSTed.

---

### 3. `loadExport()` depends on `window.StudioWizard` defined outside app.js

**Severity:** unverified
**File:** `app.js:1321-1322`

```js
var pj = (window.StudioWizard && window.StudioWizard.project && window.StudioWizard.project()) || {};
if (!pj.story_slug || !pj.pack) return showError('Pick a story and run its analysis first; export works per pack.');
```

The safe-access chain prevents a crash, but the export feature is gated on a global that `app.js` itself never creates. If `pipeline.js` (which is supposed to build the wizard panels) does not define `window.StudioWizard.project()`, every export load will fail with "Pick a story and run its analysis first" even when a story is loaded. I cannot verify whether `pipeline.js` defines this without seeing that file.

---

### Other observations (not defects)

- The `GUARD_403` text at line 62 tells users "Every request needs header X-UI", while the comment at line 254 admits the server "checks POST only today". The UI correctly sends the header on all requests, so there is no functional break — the text is just stricter than the server enforcement.
- `style.css` and `index.html` contain no defects. The static panel removal is clean, all `id`s referenced by `app.js` still exist in the static HTML, and the CSS rules for `#wiz-panels` are harmless if `pipeline.js` does not create that element.

---

FINAL:
1. medium — app.js:1187-1200 — `h3Run()` sends an empty `story` arg when the shot-file dropdown is empty; `videoPrepare()` has a guard that `h3Run()` lacks — add `if (!shots) return showError('Pick a shot file.');`
2. low — app.js:771-778 — `openPacket()` POSTs `shots: [j.shot_id]` without guarding a missing `shot_id`, producing `[null]` in the JSON body — coerce with `String(or(j.shot_id, ''))`
3. unverified — app.js:1321-1322 — `loadExport()` depends on `window.StudioWizard.project()` which is not defined in any provided file; export may always fail if `pipeline.js` does not supply it
4. no findings — `index.html` (static panel removal is correct, all referenced ids remain)
5. no findings — `style.css` (no regressions, no dangling selectors that cause layout breakage)
