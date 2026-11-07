

# BATCH r4_director (supervl) 11-07 08:34

**High — retry_policy.py:52** — `class CircuitOpen(ModelGaveUp): Pass`: `Pass` is not a keyword; the class body executes `Pass` as a name, raising `NameError` at import, so the retry module (and `write_pack.call_path`, which imports it) cannot load. Fix: `pass`.

**High — retry_policy.py:55** — `class PaidModelRefused(ValueError): Pass`: same `Pass` NameError at import; module unloadable. Fix: `pass`.

**High — retry_policy.py:229** — `breaker = breakers.set Default(model, CircuitBreaker(clock=clock))`: `set Default` is invalid syntax (meant `setdefault`); `SyntaxError` at import, module unloadable. Fix: `breakers.setdefault(model, CircuitBreaker(clock=clock))`.

**High — run_registry.py:387-388** — `unknown = set_field` / `s) - EVENT_FIELDS`: mangled `set(fields) - EVENT_FIELDS`; `SyntaxError`, the module will not parse, so no registry event can ever be recorded. Fix: `unknown = set(fields) - EVENT_FIELDS`.

**High — run_registry.py:489** — `print(F"...{getattr_fn, '__name__', 'write'}...")`: `getattr_fn` is undefined and `getattr` lacks parentheses; when any wrapped registry write fails, `_safe`'s except block raises `NameError` instead of logging, masking the original failure and crashing best-effort writes. Fix: `getattr(fn, '__name__', 'write')`.

No findings in pack_validator.py, write_pack.py, or simple_language.py (their round-2 logic reads correctly; no regressions or contract mismatches detected in the supplied code).

FINAL: retry_policy.py:52 `Pass` NameError; retry_policy.py:55 `Pass` NameError; retry_policy.py:229 `set Default` syntax error; run_registry.py:387-388 `set_field` syntax error; run_registry.py:489 `getattr_fn` NameError in the error handler — all five are import/crash-level defects that break the modules.


# BATCH r4_h3 (supervl) 11-07 08:36

severity: high, file: gate_d_audio.py:803-806, why: `plan_language_outputs` computes `t += float(s["editorial_duration_sec"])` for every shot before the `same_timing_problems` guard. A shot with a missing, non-numeric, or boolean `editorial_duration_sec` raises KeyError/ValueError/TypeError and crashes gate-D planning for every language, instead of being reported as TIME-01. Concrete input: a shot row `{id: "S1", editorial_duration_sec: "bad"}` (or missing the key) with any language. fix: validate each shot's `editorial_duration_sec` (positive number, not bool) before the offsets loop and fold bad values into `timing_errs`.

severity: medium, file: render_controller.py:328-333, why: `--allow-partial` calls `_write_shot` for ready shots, but `_write_shot` invokes `compile_fl2va_prompt` which can raise `PromptRefused` (ValueError). The exception is not caught here, so one shot that passes lint but fails compilation aborts the entire partial write and all other ready shots. Concrete input: an episode where one selected shot is lint-clean but its prompt refuses; `--scope shots --ids A,B --allow-partial` writes nothing even though B is ready. fix: wrap the `_write_shot` call in try/except, skip shots that fail to compile, and continue with the rest.

severity: medium, file: schema_and_linter.py:937,959,963, why: `lint_story` accesses `ep["shots"]`, `ep.get("asset_root")`, and `ep.get("episode_id")` without checking that `ep` is a dict. A malformed story (episode is a non-dict, or lacks `shots`/`asset_root`) raises uncaught TypeError/KeyError/AttributeError instead of lint errors. Concrete input: `{"registry": {...}, "episodes": [{"episode_id": "E1"}]}` (no `shots`) or `{"registry": {...}, "episodes": ["not-a-dict"]}`. fix: guard per-episode access with `isinstance(ep, dict)` checks and report EP-AR/SC errors.

severity: low, file: schema_and_linter.py:504, why: TM-02 (`head != ti or tail != pf - to or ed != to - ti ...`) does not exclude booleans, so `ti=True`/`to=True` pass as 1/0 while other rules (`_is_count`) reject bools. Concrete input: a shot with `trim_in_frame: true` and matching values can slip through TM-02. fix: apply `_is_count` to `ti`, `to`, `pf`, `ed`, `head`, `tail` in TM-02.

no findings for: voice_manifest.py (all reads guarded, `except Exception` on wav, non-dict rows skipped, CLI validates languages/shots).

FINAL:
1. high — gate_d_audio.py:803-806 — unprotected `float(s["editorial_duration_sec"])` crashes all-language gate-D planning on a malformed shot; validate editorial_duration_sec before the offsets loop.
2. medium — render_controller.py:328-333 — `--allow-partial` aborts on `_write_shot` compile failure; wrap in try/except and skip failing shots.
3. medium — schema_and_linter.py:937,959,963 — `lint_story` crashes on non-dict/malformed episodes; guard episode access with isinstance checks.
4. low — schema_and_linter.py:504 — TM-02 accepts booleans as frame numbers; use `_is_count` for the frame fields.


# BATCH r4_ui (supervl) 11-07 08:47

no findings for most areas; here are the real defects:

medium, pipeline.py:689, `episodes_map[ep]` raises `TypeError` when a shot's `episode` is unhashable (list/dict). The `sid` value is guarded against this (line 673-674) but `ep` is not, so a pack with a non-scalar episode crashes the summary. Coerce unhashable `ep` to `str(ep)` before using it as a dict key, matching the `sid` guard.

medium, server.py:739, `eps.setdefault(s.get("episode"), ...)` raises `TypeError` when a shot's `episode` is unhashable. `read_pack` already converts `sid` to `str` (line 731) but not the episode key. Coerce the episode key to `str()` when it is a list/dict, consistent with the `sid` handling.

low, pipeline.py:685-687, `all_have_seconds` stays `True` when every shot lacks an episode because the `if ep is None: continue` skips the `sec <= 0` check. The "every shot has seconds>0" check can report OK even when episode-less shots have zero/negative seconds. Move the seconds check before the episode `continue` (or don't skip it for episode-less shots).

high, server.py:1763, unverified — `return api.render_choice_body)` appears to be a syntax error (unmatched `)`); it should be `return api.render_choice(body)`. As written the module cannot be imported.

high, server.py:1766, unverified — `return api.author_status_body.get("pack", "")` accesses a non-existent attribute `author_status_body`; it should be `return api.author_status(body.get("pack", ""))`. Causes `AttributeError` on POST /api/author/preview.

Verified fixes that look correct: app.js `api()` sends `X-UI` on every request (line 254); `loadStory` array guard (line 596, `Array.isArray(d && d.slugs) ? d.slugs : []`); pipeline.js Save-story keeps pack only for same story (line 736); `loadDetail` single-flight with rerun (lines 298-306); server.py `record_spend` after `_start`/Popen (lines 1253-1256); episode sort on mixed types in both pipeline.py (695-698) and server.py (745-746) use type-separated sort keys so no `TypeError`; `shot_seconds` clamps to 0 and rejects bools (pipeline.py 96-103).

FINAL: medium pipeline.py:689 unhashable episode key crashes summary; medium server.py:739 unhashable episode key crashes read_pack; low pipeline.py:685-687 all_have_seconds wrongly stays True when all shots lack episodes; high server.py:1763 possible syntax error `api.render_choice_body)` (unverified); high server.py:1766 `api.author_status_body.get(...)` should be `api.author_status(body.get("pack",""))` (unverified).


# BATCH r4_tests (supervl) 11-07 08:56

high — server.py / pipeline.py (exposed by test_r3_fixes.py:89-91): `read_pack` returns the raw negative `editorial_duration_sec` (`-3`) in the shot row while only clamping the episode total to `0.0`, violating the spec that zero or negative shot seconds count as 0. A shot with `editorial_duration_sec: -3` shows `-3` seconds in the UI. Fix: clamp shot-level seconds to `0` in `read_pack` output before returning to the UI.

high — write_pack.py (exposed by test_r3_write_pack.py:16): The staged runner invokes stage 2 before validating that stage 1’s answer is usable, so a bad stage 1 still triggers a model call and only then raises `StageFailed`. A stage-1 answer with no episode numbers causes a wasted stage-2 call. Fix: validate stage 1 answer usability before dispatching stage 2.

medium — server.py (spec: episode sort on mixed types): No provided test covers server-side episode sorting with mixed `int`/`str` episode values; Python 3 raises `TypeError` comparing `1` and `"2"`. Episodes `[1, "2", 3]` crash the sort. Fix: sort episodes with a type-safe key such as `str(episode)`.

medium — test_r3_v4_to_h3.py:25-28: `test_scalar_character_positions_do_not_abort_the_shot` only asserts the converter returns a story; it never asserts a problem is recorded for the scalar `character_positions`, so it cannot fail if `compile_episode` silently drops the bad anchor. Fix: add `assert any("character_positions" in p for p in res["problems"])`.

medium — test_r3_fixes.py:89: The test asserts `rows["S2"]["seconds"] == -3`, codifying the spec violation above; if the source is corrected to clamp, this test fails. Fix: change the assertion to `== 0` and remove the raw-negative expectation.

low — test_r3_retry_policy.py:10: Only `max_attempts=0` is refused; negative `max_attempts` is not validated and could cause unexpected retry behavior. Fix: reject `max_attempts < 1` up front.

low — h3/router.py (RF-03, non-dict keyframes): No test provided; ref lists containing non-dict keyframes could raise `AttributeError`/`TypeError` during reference resolution. Unverified.

low — schema_and_linter.py: Non-object `timing_and_lattice` and `episode_plan` are not covered by the provided tests; a non-object block could crash the linter with `AttributeError`. Unverified.

low — compile_h3_sing8.py: `compile_episode` wrapping of `TypeError/ValueError/AttributeError` is not covered by the provided tests; an uncaught exception from a bad episode could abort the run. Unverified.

low — test_r3_gate_d_audio.py:20: The case "closing_mouth_state_is_a_string" sets `mouth_state="closed"`, a valid string scalar, not a non-object block, so it may not exercise the intended `AttributeError`→`PLAN-01` path. Unverified.

FINAL: high — server.py/pipeline.py shows raw negative shot seconds instead of 0 (test_r3_fixes.py:89-91); high — write_pack.py runs stage 2 before validating stage 1 (test_r3_write_pack.py:16); medium — server.py episode sort crashes on mixed int/str types (no covering test); medium — test_r3_v4_to_h3.py:25-28 cannot fail to detect missing scalar-anchor problem; medium — test_r3_fixes.py:89 asserts the wrong raw-negative behavior.
