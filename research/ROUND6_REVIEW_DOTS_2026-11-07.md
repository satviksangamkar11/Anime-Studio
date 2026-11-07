

# BATCH r6_router (dots) 11-07 12:59



## Reasoning

I was given only `router.py` and `test_router.py` to review (the two files tied to the round-2 fix "h3 router.py ref lists (RF-03, non-dict keyframes)"). I traced every function and every test for crashes on bad input, logic errors, spec violations, and tests that cannot fail.

The round-2 fix added `isinstance(k, dict)` guards in `ref_inventory` (line 18) and `ref2va_limit_problems` (line 53) so a non-dict `fl2va_keyframes` is treated as empty instead of crashing. However, `route_shot` (line 33) still uses `shot.get("fl2va_keyframes") or {}`. The `or {}` only swallows *falsy* values (None, {}, [], 0). A **truthy non-dict** — a string like `"x.png"`, a non-empty list, a number — passes through unchanged, and line 34 then calls `.get()` on it → `AttributeError`. So the "non-dict keyframes" fix is incomplete: the primary routing entry point is not hardened the way its sibling functions now are, and there is no test covering a non-dict keyframes value for `route_shot` (so nothing can catch it). Whether it's reachable depends on whether `lint_story`/compile calls `route_shot` before schema validation, but the inconsistency with the rest of the same fix is real and the crash is trivially reproducible.

I also checked every test in `test_router.py`: all are parametrized or have concrete assertions and can genuinely fail; none is a no-op. The `parametrize` spelling is the correct pytest form. The remaining `video_shift_for` KeyError-on-missing-key case is guarded upstream by the PO-04 lint, so I treat it as unverified rather than a defect.

All other files named in the prompt (pipeline.js, server.py, compile_h3_sing8.py, schema_and_linter.py, etc.) were **not provided**, so those round-2 fixes are unverified.

## Findings

**[medium] router.py:33 — `route_shot` crashes on a truthy non-dict `fl2va_keyframes`**
The round-2 "non-dict keyframes" fix guards `ref_inventory` (line 18) and `ref2va_limit_problems` (line 53) with `k = k if isinstance(k, dict) else {}`, but `route_shot` uses `k = shot.get("fl2va_keyframes") or {}`, which yields a truthy non-dict (string/list/int). Line 34 then calls `k.get(...)`, raising `AttributeError: 'str'/'list' object has no attribute 'get'`.
Failing input: `route_shot({"fl2va_keyframes": "x.png"})` → AttributeError. No test covers this case.
One-line fix: use the same guard as the sibling functions — `k = shot.get("fl2va_keyframes"); k = k if isinstance(k, dict) else {}`.

**[low] router.py:18,33,52 — non-dict `shot` (e.g. `None`) crashes `.get` before any guard**
`ref_inventory`, `route_shot`, and `ref2va_limit_problems` all call `shot.get(...)` assuming `shot` is a dict. A malformed shot entry (`null` in the shots array) raises `AttributeError`. Reachability is unverified (likely blocked by an earlier lint/schema step), but it is the same trust-boundary class as the fix above and is currently unguarded.

**[unverified] test_router.py:144-149 — `compile_comfyui_workflow` called with 3 args (keyframes omitted)**
Line 95 passes `voice=False, resolve_keyframes(...)` explicitly, but lines 144/147 omit both, relying on defaults. Whether the workflow/lint still produce a clean result for FL2VA with `keyframes=None` depends on `compile_h3_sing8.py`, which was not provided. No defect confirmed; unverified.

**[unverified] all other round-2 fixes** — `pipeline.js`, `server.py`, `compile_h3_sing8.py`, `schema_and_linter.py`, `gate_d_audio.py`, `render_controller.py`, `v4_to_h3`, `h3_author`, `voice_manifest`, `voice_engine`, `director write_pack`, `pack_validator`, `run_registry`, `retry_policy`, `story_state`, `write_pack`, `UI (index.html/pipeline.js/server routes)` — files not supplied, so correctness and regression status cannot be checked.

## FINAL:
1. **[medium] router.py:33** — `route_shot` is not hardened for non-dict `fl2va_keyframes` (unlike `ref_inventory`/`ref2va_limit_problems`); `or {}` lets a truthy string/list through and line 34 crashes on `.get()`. Fix: `k = shot.get("fl2va_keyframes"); k = k if isinstance(k, dict) else {}`.
2. **[low] router.py:18,33,52** — a non-dict `shot` (e.g. `None`) crashes `.get` before any guard; unverified reachability but same trust-boundary class.
3. **[unverified] test_router.py:144** — 3-arg `compile_comfyui_workflow` call relies on defaults not visible in the provided files.
4. **[unverified] pipeline.js / server.py / compile_h3_sing8.py / schema_and_linter.py / gate_d_audio.py / render_controller.py** and the remaining round-2 fixes — not provided, cannot verify.
5. No other real defects found in the two provided files; all provided tests can fail.
