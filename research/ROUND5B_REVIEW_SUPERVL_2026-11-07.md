

# BATCH r5b_ui_server (supervl) 11-07 12:30

Reviewing server.py for the Round‑2 fixes and any regressions:

**Round‑2 server.py fixes verified correct:**
- `record_spend only after the job starts` (api.run, ~1264‑1272): `record_spend` is called after `self._start(...)` launches the process; `rec["used"]` is set before the ledger write so a failed ledger write still consumes the preview and returns a `spend_recorded: False` warning rather than silently hiding the spend. Correct.
- `episode sort on mixed types` (read_pack, ~749‑751): the sort key separates numbers `(False, 0, n)` from non‑numbers/None via the second tuple element, so a number is never compared to a string at index 2 — no `TypeError` on mixed int/str/None/bool episode values. Correct.
- `zero or negative shot seconds count as 0` (read_pack, ~737, ~745): both the row display (`max(0, secs)`) and the episode accumulator (`max(0.0, num(secs))`) clamp negatives and non‑numbers to 0, and `editorial_duration_sec = 0` is preserved as a real value (only `None`/missing falls back to `seconds`). Correct.

**Other checks:** path traversal is blocked by `safe_path`/`PACK_REL`/`SLUG`/`NAME` at every trust boundary; the `X-UI` guard is enforced on all POST (`_guard`, ~1821) while GET endpoints are read‑only, so the client sending it on every request causes no contract mismatch; spend previews/gates, job single‑use tokens, `_active()` re‑check, and `check_argv` bans all behave as specified. No crashes on malformed input were found (all query/body args are validated before use; `jsonl`, `load_list`, `_size`, globs handle missing/malformed files gracefully).

No regressions, wrong/incomplete fixes, logic errors, spec violations, or JS/server contract mismatches in server.py.

no findings

FINAL: no real defects found


# BATCH r5b_tests (supervl) 11-07 12:36

Only `test_bf_fixes.py` was provided; the source files it exercises are not visible, so source-level regressions cannot be confirmed directly. The review below is limited to defects visible in this test file and to spec mismatches encoded in its expectations.

medium, test_bf_fixes.py:25, `disk_paths=(str(studio), str(studio))` passes the studio root twice instead of distinct studio/flow/download roots, so `Config` may resolve assets against the wrong directory and every test in the module can operate on the wrong tree. Pass distinct paths matching `Config`'s expected arguments.

medium, test_bf_fixes.py:45-55, The test mocks `_start` and `record_spend` independently and never asserts call order, so a regression where `record_spend` is invoked before the job starts (violating the owner rule) would still pass. Assert that `record_spend` is called only after `_start` returns, e.g. with a sequence mock.

low, test_bf_fixes.py:51,66, The success path asserts the response is exactly `{"job_id": "job1"}` while the failure path expects `spend_recorded` and `warning` keys, indicating an unstable server response contract. Include `spend_recorded` in all responses and assert with a subset matcher.

medium, test_bf_fixes.py:21-22, `editorial_duration_sec: True` is asserted to yield `seconds == 0`, but the spec only requires zeroing zero-or-negative numeric shot seconds and `pack_validator` flags "bool not int"; silently coercing a boolean to 0 is a spec violation/wrong fix. Reject boolean durations as invalid and coerce only int/float `<= 0` to 0.

low, test_bf_fixes.py:83, `pipeline.facts(studio_dir, runs)` passes a `runs` path object whose type is unspecified; if `facts` expects a string or manifest the test may pass trivially or break on refactor. Pass the documented argument type and assert on the concrete pending structure.

FINAL: medium test_bf_fixes.py:25 disk_paths duplicates studio root; medium test_bf_fixes.py:45-55 spend/order not asserted so record_spend-before-start regression undetectable; low test_bf_fixes.py:51,66 inconsistent response contract between success and failure; medium test_bf_fixes.py:21-22 boolean duration coerced to 0 contradicts zero-or-negative spec and bool-not-int rule; low test_bf_fixes.py:83 pipeline.facts called with unverified runs argument type.
