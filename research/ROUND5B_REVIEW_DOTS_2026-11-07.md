

# BATCH r5b_ui_server (dots) 11-07 12:30



After thorough analysis of server.py against the round-2 fix claims and the owner spec, here are my findings:

## Verified round-2 fixes in server.py

1. **record_spend only after the job starts** (line 1264-1268): `_start()` spawns the job at 1264, `rec["used"] = True` at 1265, then `record_spend()` at 1268. Correct order. If the ledger write fails, the warning path at 1271-1272 correctly reports it without hiding the running job.

2. **Episode sort on mixed types** (lines 748-751): The `ep_key` lambda wraps numeric and string episodes in tuples with a type discriminant `(is_none, type_flag, value)`, preventing TypeError when comparing int with str. Handles bool, None, list, dict (converted to str at line 742), and all other types safely.

3. **Zero or negative shot seconds count as 0** (lines 737-738, 745): `max(0, secs)` for rows and `max(0.0, num(secs))` for episode totals. Bool is explicitly excluded via `not isinstance(secs, bool)`.

## Other checks

- X-UI header: server requires it on POST only (line 1821), which is correct per spec (the JS sending it on every request is harmless for GET).
- Spend gate: `_active()` blocks new spend while any job runs or any spend job is unverified (line 994-996). Re-check at line 1262 after the spend gate window closes the race.
- `read_pack` stages, episodes, rows, modes, check: all handle missing/malformed data without crashing.
- `safe_path` and all input validators (`SHOT`, `SLUG`, `NAME`, `_int`, `_bool`, `_note`, etc.) reject bad input at trust boundaries.
- `dispatch` route matching: more-specific regexes are checked before less-specific ones for both GET and POST, preventing `/api/story/slug/state` from matching `/api/story/slug`.
- `_body` rejects non-JSON, non-object bodies; `_guard` checks Host, Origin, and X-UI in order.

## Pre-existing issue (not a regression)

- **`export()` episode comparison** (server.py:1563): `s.get("episode") == n` where `n` is an int. If `shots.json` stores episode as a string (e.g. `"1"`), the comparison fails and the export returns empty clips. The round-2 fix for mixed-type episode sorting in `read_pack` (lines 748-751) highlights that episode types can vary, making this assumption fragile. However, this is pre-existing, not introduced by round-2 fixes.
  - **Fix**: compare `str(s.get("episode")) == str(n)` or normalize episode to int at read time.

## Unverified (files not provided)

- `ui/static/app.js` (api() X-UI, loadStory array guard)
- `ui/pipeline.js` (Save-story pack scoping, loadDetail single-flight)
- `h3/router.py` (RF-03 ref lists, non-dict keyframes)
- `schema_and_linter.py` (non-object timing_and_lattice, episode_plan)
- `compile_h3_sing8.py` (compile_episode exception wrapping)
- `pipeline.py` (zero/negative seconds, save-story pack scoping)
- `h3_author.py`, `v4_to_h3.py`, `voice_manifest.py`, `gate_d_audio.py`, `render_controller.py`, `voice_engine.py`, `director/write_pack.py`, `pack_validator.py`, `run_registry.py`, `retry_policy.py`

FINAL:
1. medium, server.py:1563, `export()` compares `s.get("episode") == n` with int `n`; string episodes yield empty clips, pre-existing but fragile given mixed-type sort fix, change to `str(s.get("episode")) == str(n)`
2. no other real defects found in server.py


# BATCH r5b_tests (dots) 11-07 12:47



Looking at this round-3 regression test file plus the round-2 fix list, most items are covered by tests that *can* fail (the bool/None seconds test, the single-use preview tests, the unhashable-id test, the vanished-file test all have real assertions). The tests look mostly well-formed. The real concerns are in **untested logic** and a couple of test-coverage/contract gaps.

## Findings

**[medium] run_registry.py — Marathi detection by a single Devanagari codepoint also matches Hindi**
The fix is described as "Marathi detection by u0933." U+0933 (ण) is used in **both** Hindi and Marathi — there is no single codepoint that distinguishes the two scripts. Since the spec runs `en`/`hi`/`mr` through ElevenLabs, a `if '\u0933' in text → lang='mr'` check will misroute Hindi narration to the Marathi voice path. No test covers this, so it would ship silently.
Fix: detect Marathi with a real language classifier or a Marathi-specific token set, not one shared Devanagari consonant.

**[medium] pipeline.py read_pack / seconds guard — described fix is narrower than the test demands**
The fix summary says "zero or negative shot seconds count as 0," but `test_row_seconds_bool_and_none_are_zero` requires `editorial_duration_sec: True` (a `bool`, which is an `int` subclass with value `1`) and `None` to both yield `0`. A naive `max(0, v)` / `v <= 0` guard returns `1` for `True` and the test fails. The test was added together with the fix, so the implementation probably special-cases `bool`/non-numeric — but verify the guard explicitly excludes `bool` (e.g. `isinstance(v, bool) or not isinstance(v, (int, float)) → 0`), otherwise this is a latent regression.

**[low] test_bf_fixes.py:85-88 — second half of the unhashable-id test may not exercise what it claims**
`runs2` is built under `tmp_path / "b"`, but `pipeline.facts(studio_dir, runs2)` is called with `studio_dir = tmp_path / "studio"`. If `pipeline.facts` matches runs by their *recorded studio path*, the `pending == 0` assertion passes trivially (no run matches `studio_dir`) and the dq→fl cancellation is never actually tested — a "test that cannot fail" for that half. Verify `make_runs`/`pipeline.facts` semantics; if the run's stored studio is `tmp_path/"b"`, restructure so the fulfilment is checked against the same studio the demand was registered under.

**[low] test_bf_fixes.py:92-96 — vanished-file test covers `_size`, not the listing contract**
The fix promises "size is None, **file still listed**." The test only asserts `server._size(missing) is None` and `server._size(real) == 3`. It never checks that a listing still *includes* the vanished entry with a `None` size. If the listing code drops `None`-size files, nothing in this test fails. Add a listing-level assertion (glob → filter → assert the vanished path is present with `size is None`).

**[low] compile_h3_sing8.py — broad `TypeError/ValueError/AttributeError` wrap can mask real bugs**
Wrapping all three broadly (especially `AttributeError`) will silently swallow genuine mistakes — a misspelled key after a dependency upgrade, a renamed field in a newer schema — and convert them into a generic compile failure with no traceback. If the intent is "recover from bad input," narrow the catch to the specific expected errors and log/attach the original exception chain.

## Unverified (not counted above)
- `episode sort on mixed types`: the key function isn't visible; a `(type, value)` tuple key works, a bare `key=lambda e: e` crashes. Can't confirm without the code.
- `render_controller` default language `hi`: spec only pins BGM default to none; the `hi` default is plausible but not confirmed against spec.
- `record_spend only after the job starts` + `used` marking ordering on `_start` failure: tests mock `_start` to succeed, so the failure path is untested.
- UI fixes (`api()` X-UI header, `loadStory` array guard, `pipeline.js` panels): JS, not visible in this Python test file — contract mismatch with the server can't be checked here.

## FINAL
1. **[medium]** `run_registry.py` — Marathi detected by U+0933 also matches Hindi → wrong voice for `hi`. Fix: real Marathi classification, not one shared Devanagari codepoint.
2. **[medium]** `pipeline.py` seconds guard — "zero/negative → 0" doesn't cover `bool`/`None`; verify the guard excludes `bool` or `test_row_seconds_bool_and_none_are_zero` fails.
3. **[low]** `test_bf_fixes.py:85-88` — `runs2` under `tmp_path/"b"` vs `studio_dir` may make the fulfilment half a non-failing test; confirm `pipeline.facts` matching semantics.
4. **[low]** `test_bf_fixes.py:92-96` — only tests `_size`; "file still listed" part of the fix is untested.
5. **[low]** `compile_h3_sing8.py` — broad `TypeError/ValueError/AttributeError` wrap risks masking genuine bugs; narrow and preserve the traceback.
