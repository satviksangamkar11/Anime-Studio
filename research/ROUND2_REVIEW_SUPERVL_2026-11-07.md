

# BATCH r1_director (supervl) 11-07 03:20

No findings in pack_validator.py or story_state.py after review. The real defects are all in write_pack.py:

**HIGH — write_pack.py:877-882 (`gate`)**
Why: when the validator exists, `gate` returns only `stage_errors(...)` and discards `fallback`. Stage 5 resolves to "passthrough" (no validator rule), so `stage_errors` returns no errors and the `caption_language_errors` fallback (LANG-03/LANG-04/CAP-01/LANG-02) never runs.
Failing input: staged run with `--out-lang en,hi`; stage 5 emits captions whose per-language time ranges differ (LANG-04) or a card over the word limit (CAP-01). The validator reports ok and invalid captions pass.
Fix: `return with_language(stage_errors(mod, name, data, bible_for, output_languages=langs, lang_check=hook, voice_engines=engines), fallback())`.

**HIGH — write_pack.py:905 (`apply_captions` after `merge_episodes`)**
Why: `merge_episodes` renumbers duplicate per-episode ids (SHOT-01 in every episode → SHOT-001, SHOT-002 …) and keeps the original in `source_id`. Stage 5 captions still reference the original per-episode ids, so `by_id.get(shot.get("id"))` finds nothing and captions are silently dropped.
Failing input: 2-episode story, each episode numbers shots SHOT-01/SHOT-02; stage 5 writes captions with `shot_id` SHOT-01/SHOT-02. Merged shots are SHOT-001..SHOT-004 → no caption matches → shots.json lacks captions.
Fix: `item = by_id.get(shot.get("id")) or by_id.get(shot.get("source_id"))`.

**MEDIUM — write_pack.py:509-513 (`run_stage.judge`)**
Why: `judge` catches only `ValueError` from `parse_fn`, but `parse` (line 320-323) calls `settings_for(shot)` for legacy rows, which may raise KeyError/TypeError on malformed model output → uncaught traceback instead of a parse error. (unverified: depends on `settings_for`'s exception type)
Failing input: model emits a legacy shot row (no `lattice_n`) whose fields make `h3_director.settings_for` raise a non-ValueError → CLI crash.
Fix: catch `Exception` (not just `ValueError`) around `parse_fn` in `judge`, or wrap `settings_for(shot)` in `parse` to convert errors to ValueError.

**MEDIUM — write_pack.py:130 (`stream_chat`)**
Why: `json.loads(line[5:])` on SSE `data:` lines is unhandled; malformed server payload raises JSONDecodeError, which `call_openrouter`/`call_nvidia` (catching only `HTTPError`) do not catch → crash.
Failing input: OpenRouter/NVIDIA emits a malformed SSE line (e.g. `data: ` or `data: {broken`) → JSONDecodeError propagates through `call_path`/`run_staged` → CLI traceback.
Fix: wrap `json.loads(line[5:])` in try/except and treat as a stream error.

FINAL:
- HIGH write_pack.py:877-882 — `gate` discards the fallback, so stage 5 caption language checks (LANG-03/LANG-04/CAP-01/LANG-02) are skipped when the validator exists.
- HIGH write_pack.py:905 — `apply_captions` matches captions by merged `id` after `merge_episodes` renumbers them, so stage 5 captions (keyed by original per-episode ids) are silently dropped for multi-episode packs.
- MEDIUM write_pack.py:509-513 — `run_stage.judge` catches only `ValueError`; `parse`'s `settings_for(shot)` call on legacy rows can raise other exceptions and crash the pipeline.
- MEDIUM write_pack.py:130 — `stream_chat` does not guard `json.loads` on SSE data, so malformed server payloads crash the writer.
- pack_validator.py: no findings; story_state.py: no findings.


# BATCH r2_registry_retry (supervl) 11-07 03:27

1. **medium, run_registry.py:580-586** — `record_gate_decision` passes the raw `gate` value to `append_event`, which validates it against `GATES = ("A","B","C","D")` in `_checked`. A lowercase gate (e.g. `"a"`) raises `ValueError`, but `@best_effort` swallows it, so the gate decision is silently never written and Gate A blocking can fail without any visible error. Fix: normalize `gate = gate.upper()` before the `append_event` call.

2. **medium, retry_policy.py:198-207** — `is_free_model` filters out non-numeric/`None` price fields before checking, so a catalog entry like `{"pricing": {"prompt": 0, "completion": None}}` is wrongly classified as free. The spec says "Unknown or unpriced = not free" and "empty-price model is NOT free." Fix: require every price field to be present, numeric, and equal to 0 (reject if any value is missing/non-numeric).

3. **low, run_registry.py:256-258** — `detect_language` applies the 20-Devanagari-character threshold before the U+0933 Marathi check, so a short Marathi text containing `ळ` is classified as `"en"` and the owner's "Marathi detection by u0933" rule is bypassed. Fix: check for `ळ` first (return `"mr"`), then apply the count threshold for `"en"` vs `"hi"`.

No other files have findings: `retry_policy.py` retry/circuit logic is consistent with its documented contract, and `simple_language.py` handles empty/malformed inputs without crashing at its trust boundaries.

FINAL:
1. medium, run_registry.py:580-586 — `record_gate_decision` silently drops gate decisions when `gate` is lowercase; `@best_effort` swallows the `_checked` ValueError, so Gate A blocking can fail. Fix: uppercase `gate` before validation.
2. medium, retry_policy.py:198-207 — `is_free_model` ignores non-numeric/`None` price fields, misclassifying models with unknown prices as free; spec requires "unknown or unpriced = not free." Fix: require every price field to be numeric and zero.
3. low, run_registry.py:256-258 — `detect_language` applies a 20-Character Devanagari threshold before the U+0933 Marathi check, so short Marathi texts are misclassified as English. Fix: check `ळ` first.


# BATCH r3_h3_core (supervl) 11-07 03:36

high, schema_and_linter.py:599 — KF-01 compares the shot `mode` against the string literal `"REF2VA"` (all caps) instead of the imported constant `REF2VA` (`"Ref2VA"`), so valid shots using `mode: "Ref2VA"` are falsely rejected while invalid `"REF2VA"` passes. Fix: `if k.get("mode") not in ("FL2VA", REF2VA):`.

high, schema_and_linter.py:470,479,292 — `pf / fps`, `t[frame_key] / fps`, and `math.ceil(pf / fps)` divide by `fps` with no zero guard; `ZeroDivisionError` is not in `_run`'s caught exception tuple, so a profile with `fps: 0` crashes the linter and the pipeline. Fix: guard `fps == 0` before dividing (or add `ZeroDivisionError` to `_run`).

medium, compile_h3_sing8.py:33-36 — `_speech_sentences` indexes `registry["characters"][u["character_id"]]`, `ch["voice_anchor"]`, and `ch["short_disambiguator"]` without guards; an utterance referencing a missing character or missing anchor raises `KeyError` and crashes the compiler instead of a clean refusal. Fix: validate character/anchor existence and raise `PromptRefused`/`ValueError` with a clear message.

medium, compile_h3_sing8.py:47 — `_fl2va` reads `registry["style_lock"]` directly, but `style_lock` is not in `PROFILE_KEYS` so `lint_profile` never requires it; a registry missing `style_lock` crashes `compile_fl2va_prompt`/`compile_episode` with `KeyError`. Fix: require `style_lock` in the profile/registry or use `.get` with a default.

medium, schema_and_linter.py:943-947 — `lint_story` wraps prompt+workflow compilation in `try/...: continue`, so when a precompiled prompt is supplied and `compile_comfyui_workflow` fails (e.g. missing LoRA entry), the error is silently swallowed and no lint error is recorded. Fix: `log.err("PR-00", ...)` in the `except` instead of `continue`.

low, schema_and_linter.py:833-835,858-859 — Pure-Foley shots with audio references enter the Ref2VA branch in `ref2va_limit_problems` and then the `elif` at line 858, logging `AU-01` twice. Fix: drop the redundant audio check in one of the two places.

low, compile_h3_sing8.py:119 — `compile_fl2va_prompt` returns `shot["shot_id"]` directly; a shot missing `shot_id` raises `KeyError`. Fix: `shot.get("shot_id", "<unknown>")`.

low, schema_and_linter.py:309 — `diegetic_text_events` calls `int()` on a possibly non-numeric metadata value; the `ValueError` is caught by `_run` but misreported as `SC-03` instead of a proper metadata error. Fix: validate the value before `int()`.

FINAL:
1. high, schema_and_linter.py:599 — KF-01 uses literal `"REF2VA"` instead of constant `REF2VA`, rejecting valid mode `"Ref2VA"`.
2. high, schema_and_linter.py:470,479,292 — Division by `fps` with no zero guard; `fps: 0` raises uncaught `ZeroDivisionError` and crashes the linter.
3. medium, compile_h3_sing8.py:33-36 — `_speech_sentences` crashes with `KeyError` on missing character/voice anchor instead of refusing cleanly.
4. medium, compile_h3_sing8.py:47 — `_fl2va` crashes with `KeyError` when registry lacks `style_lock`, which `lint_profile` never requires.
5. medium, schema_and_linter.py:943-947 — `lint_story` silently swallows workflow compilation errors (`continue`), so broken profiles with precompiled prompts pass lint undetected.


# BATCH r4_h3_gate_ctrl (supervl) 11-07 03:43

gate_d_audio.py:179 — HIGH — `check_closing_shot` treats a missing `payoff_end_sec` as a hard failure (`CLOSING_VO_BEFORE_PAYOFF`, message "...before the payoff ends at None") instead of skipping the unverifiable "starts after payoff" check. Since `_gate_d_result` never passes `payoff_end_sec`, any closing shot that has a VO fails. Failing input: closing shot with narration text + `vo_wav_path`, `payoff_end_sec=None`. Fix: `if payoff_end_sec is not None and s < payoff_end_sec:`.

gate_d_audio.py:839 — HIGH — `same_timing_problems` does `items = [val] if isinstance(val, dict) else list(val or [])`; a scalar `*_by_lang` value (int/float/bool) makes `list(5)` raise `TypeError`, and `plan_language_outputs` only catches `ValueError` around the call (line 805), so the `TypeError` escapes the function boundary. Failing input: a shot with `"narration_by_lang": {"en": 5}`. `plan_language_outputs(...)` crashes with `TypeError: 'int' object is not iterable` for direct callers. Fix: `items = [val] if isinstance(val, dict) else (list(val) if isinstance(val, list) else [])`.

gate_d_audio.py:94 — HIGH — `_speech_items` calls `narr.get("text")` assuming `narration` is a dict, but `_lang_track` can return a scalar from `narration_by_lang`. The `AttributeError` is not caught by the per-language `try` (which catches `ValueError, KeyError, TypeError` only), so it crashes `plan_language_outputs` and propagates to `main`. Failing input: `"narration_by_lang": {"en": "text"}`. Crash: `AttributeError: 'str' object has no attribute 'get'`. Fix: `narr = trk.get("narration"); if not isinstance(narr, dict): narr = None`.

render_controller.py:539 — HIGH — `_gate_d_result` calls `plan_language_outputs` without `story_gate_checks` (defaults to `None`) and `payoff_end_sec` (defaults to `None`). `check_closing_shot` then evaluates `gate.get("pass") is not True` with `gate={}`, so every closing shot fails `CLOSING_NO_ANCHOR_PAYOFF`; with a closing VO it also fails `CLOSING_VO_BEFORE_PAYOFF`. Gate D always fails for any reel with a closing shot. Failing input: any story whose episode has a shot `is_closing_hook: true`. Fix: pass `story_gate_checks=reg.get("story_gate_checks")` and `payoff_end_sec=<episode payoff end>` into the `plan_language_outputs` call.

gate_d_audio.py:808 — MEDIUM — `plan_language_outputs` routes via `engine_for`, which returns any truthy value verbatim, so an invalid engine (e.g. `"bogus"`) is neither `"h3"` nor rejected; it is silently sent down the ElevenLabs path and later surfaces as `VO_MISSING` instead of a config error (`VE-02`). Failing input: `voice_engine = {"en": "bogus"}` in the registry. Fix: reject `eng not in ("elevenlabs", "h3")` with a `PLAN-01`/config error before routing.

voice_engine.py: no findings (engine_for's leniency is documented "never raises"; validation belongs to voice_engine_problems).

FINAL:
1. HIGH render_controller.py:539 — `_gate_d_result` omits `story_gate_checks`/`payoff_end_sec`, so `check_closing_shot` always fails `CLOSING_NO_ANCHOR_PAYOFF` (and `CLOSING_VO_BEFORE_PAYOFF` with a VO); pass them from the story/episode.
2. HIGH gate_d_audio.py:839 — `same_timing_problems` `list(val or [])` raises uncaught `TypeError` for scalar `*_by_lang` values; coerce only lists.
3. HIGH gate_d_audio.py:94 — `_speech_items` `narr.get("text")` raises uncaught `AttributeError` for non-dict narration; guard with `isinstance(narr, dict)`.
4. HIGH gate_d_audio.py:179 — `check_closing_shot` fails a closing VO when `payoff_end_sec is None` instead of skipping; use `if payoff_end_sec is not None and s < payoff_end_sec:`.
5. MEDIUM gate_d_audio.py:808 — invalid voice engines are silently treated as ElevenLabs; reject engines not in `("elevenlabs", "h3")` at the Gate D boundary.


# BATCH r5_h3_convert_author (supervl) 11-07 03:58

No findings for `pipeline_contract.py` (its plan/assembly logic is consistent).

Real defects:

- **medium — v4_to_h3.py:609** — `convert_pack` evaluates `dict((authored or {}).get(sid) or {})` on the caller-supplied `authored` mapping. If a shot's value is a non-dict, non-empty sequence (e.g. a string), `dict()` raises `ValueError`/`TypeError` and the whole conversion crashes instead of ignoring the bad entry. `authored` is a trust boundary (passed by an external caller/server). Failing input: `convert_pack(pack, authored={"S1": "not-a-dict"})` → `ValueError: dictionary update sequence element #0 has length 1; 2 is required`. Fix: `raw = (authored or {}).get(sid); auth = dict(raw) if isinstance(raw, dict) else {}`.

- **low — voice_manifest.py:121** — `_cli` does `shots = doc["shots"] if isinstance(doc, dict) else doc`. If `--shots` is a JSON object without a `"shots"` key, this raises an uncaught `KeyError` (traceback) instead of a clean error. Failing input: `echo '{"other": []} > bad.json` then `python -m h3.voice_manifest --shots bad.json --lang en --vo-root x`. Fix: `shots = doc.get("shots") if isinstance(doc, dict) else doc`; if not a list, print an error and return 2.

- **medium — h3_author.py:162 (and 232)** — In `author_shot`, `check_answer(...)` (which runs `convert_pack` + `lint_story`) is outside the `try` that only guards `caller(prompt)`, and `author_pack` does not wrap `author_shot(...)`. Any conversion/lint exception (e.g. `KeyError` from `_shot` reading `ctx["profile"]["base_resolution"]` on a malformed profile) escapes as a crash instead of a per-shot problem. Reachability unverified: needs a malformed profile/pack. Fix: move `check_answer` inside the `try` (or wrap the `author_shot` call in `author_pack`) and return a `MODEL check failed: ...` problem.

- **low — v4_to_h3.py:470-472** — `_shot` unconditionally compares `row.get("pixel_frames")` and `row.get("latent_slots")` to the lattice-derived values and appends a problem on mismatch. If V4 writer rows carry only `lattice_n`/`editorial_duration_sec`, every shot is falsely flagged "pixel_frames/latent_slots do not match lattice_n". Reachability unverified: depends on the V4 row schema. Fix: only compare when the row actually provides those keys.

- **low — v4_to_h3.py:476** — `h3.get("location_id") not in ctx["environments"]` fires when `location_id` was not derived (key absent → `None`), emitting "location_id None is not an ENV id" in addition to the "h3_fields.location_id missing" problem — a duplicate/misleading problem for one absence. Failing input: a shot whose `fixed_landmarks` do not map to exactly one bible ENV. Fix: `loc_id = h3.get("location_id"); if loc_id is not None and loc_id not in ctx["environments"]: ...`.

FINAL:
1. medium — v4_to_h3.py:609 — `authored` non-dict value crashes `convert_pack` with ValueError/TypeError; validate `isinstance(raw, dict)`.
2. low — voice_manifest.py:121 — `doc["shots"]` uncaught KeyError when `--shots` JSON object lacks `"shots"`; use `.get()` and validate a list.
3. medium — h3_author.py:162/232 — `check_answer`/`author_shot` exceptions escape instead of being recorded as per-shot problems; wrap in try and return a `MODEL check failed` problem.
4. low — v4_to_h3.py:470-472 — `_shot` falsely flags every shot when rows lack `pixel_frames`/`latent_slots`; only compare when keys present.
5. low — v4_to_h3.py:476 — missing `location_id` reported twice (as missing and as "None is not an ENV id"); guard on non-None.


# BATCH r6_ui_server (supervl) 11-07 04:05

severity: high, server.py:1041, why: `_verify_stop` marks the job `stop_failed` with `verified=False` when colab sessions cannot be read (CLI missing/broken). `_active()` then treats any spend job with `verified is not True` as still active, so every subsequent spend run is rejected with 409 "another job is running" until the server is restarted. fix: when `text is None`, set `job.verified = True` and write a warning line instead of `job.state = "stop_failed"`.

severity: medium, server.py:1241, why: `_ops_checks().record_spend(...)` is called before `self._start(...)`. If `Popen` raises `OSError` (e.g. python binary missing), the ledger already records spend for a job that was never started. fix: move `record_spend` to after `_start` returns successfully (inside the lock, after `job = self._start(...)`).

severity: medium, server.py:741, why: `read_pack` sorts episodes with key `(x["n"] is None, x["n"] or 0)`. When a pack mixes string and integer episode values, Python 3 cannot compare `str` with `int`, raising `TypeError` and crashing `GET /api/pack`. fix: `key=lambda x: (x["n"] is None, str(x["n"] or 0))`.

severity: low, pipeline.py:681-683, why: `total_seconds += sec` runs even when `sec <= 0`, so negative or zero shot seconds reduce the report total instead of being skipped. fix: only accumulate `sec` into `total_seconds` when `sec > 0`.

FINAL: server.py:1041 (_verify_stop stop_failed permanently blocks spend), server.py:1241 (record_spend before job start), server.py:741 (episode sort TypeError on mixed types), pipeline.py:681-683 (negative seconds corrupt total)


# BATCH r7_ui_js (supervl) 11-07 04:11

medium, pipeline.js:723, After saving a story the project is re-scoped with `projectOf().pack`, which still holds the previous story's pack because the pipeline project hasn't been reloaded from the server yet. A newly saved or switched-to story can be bound to a nonexistent pack from another story. Story "alpha" has pack "p1"; create story "beta", click Save story, and the project becomes story=
