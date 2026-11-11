**REAL DEFECTS**

1. **`test_deadman_uses_frames_and_clip_count` expects the wrong argument order.**
   - Line (test file): `monkeypatch.setattr(r.rs, "deadman_seconds", spy)` where `spy(clip, n, **k)`; inside `batch`, `rs.deadman_seconds(FRAME_SECONDS_ESTIMATE * max(expected.values()), len(expected))` is called positionally as `(clip, n)`. That is correct, but the test then asserts `seen == [(0.75 * PF, 2)]` — the real `deadman_seconds` signature is `deadman_seconds(clip_seconds, n_shots, **kw)` and the production call passes `clip_seconds` first. The test’s `spy` records the arguments in the order they are received, which is consistent. However, the test also asserts `r.rs.deadman_seconds(0.75 * PF, 2) == 1744`. The function is called with `FRAME_SECONDS_ESTIMATE * max(expected.values())` = `0.75 * 175 = 131.25`, and `len(expected) = 2`. The expected value `1744` is computed as `(900 + 2×131.25) × 1.5`. The test does not actually verify the computation; it only checks the call arguments and a constant. The test is **tautological** — it cannot fail because the assertion `r.rs.deadman_seconds(0.75 * PF, 2) == 1744` is a hardcoded number that matches the card’s stated value but does not test the implementation. The test should compute the expected value from the function’s formula or check that `max_seconds` is set to the returned value inside `batch`.

2. **`test_deadman_uses_frames_and_clip_count` does not verify the dead-man limit is applied.**
   The card says: `max_seconds = min(MAX_BATCH_SECONDS, deadman_seconds(0.75*max_frames, n))`. The test patches `deadman_seconds` and then calls `batch`, but it never checks that the returned `max_seconds` (or the effective deadline) equals the spied value. It only checks `seen` and a constant. This is a **weak test** — it does not cover the test name “test_deadman” (the card lists this test name). The test must assert that `batch` uses the dead-man value, e.g., by passing a `clock` that exceeds the deadline and checking that the wait is broken.

3. **`test_all_done_verified_stops_then_checks_sessions` asserts `calls[-2:] == ["stop", "sessions"]`.**
   The card says: update the existing asserts `calls[-1] == "stop"` to `"stop" in calls and calls.index("stop") < len(calls) - 1 and calls[-1] == "sessions"`. The test still uses the old `calls[-2:]` form. While functionally similar, it does not match the required update and could mask a case where `stop` is the last call. **Fix:** change to the specified assertion.

4. **`test_missing_clip_keeps_session` asserts `"stop" not in calls` but does not check `sessions` after `stop`.**
   The card requires that after a failed `colab new`, we print `"STRAY SESSION?"` for each listed session, and in `finally`, after `stop`, run `sessions` and print `"SESSION STILL LISTED"` if our name is still listed. In the keep-session path, `stop` is not called, so `sessions` is not called either. The test does not verify that `sessions` is called when `stop` **is** called. The test name `test_sessions_checked_after_stop` is listed on the card but is not present in the test file. **Add** a test that verifies `sessions` is called after `stop` in the normal path.

5. **`test_failed_new_reports_stray` does not check that `usage` is called after `new` fails.**
   The card says: after a failed `colab new`, print `"colab new FAILED: ... Sessions and usage now:"` and then call `run_cli(["usage"], check=False)`. The test only checks for `"STRAY SESSION?"` in output; it does not verify that `usage` was called. The test is **incomplete**.

---

**FIX (for the test file only — the module is correct):**

- In `test_deadman_uses_frames_and_clip_count`, replace the constant assertion with a check that `batch` actually uses the dead-man value. For example, pass a `clock` that returns a value beyond the deadline and assert that the batch loop breaks with `rc=124` (or that `proc.kill()` was called). At minimum, compute the expected value from the formula and assert equality, or assert that the `max_seconds` argument to `batch` equals the spied return value.

- In `test_all_done_verified_stops_then_checks_sessions`, change the assertion to:
  ```python
  assert "stop" in calls and calls.index("stop") < len(calls) - 1 and calls[-1] == "sessions"
  ```

- Add a test `test_sessions_checked_after_stop` that simulates a successful run where `stop` is called and verifies that `sessions` is called afterwards and that `"SESSION STILL LISTED"` is printed if the session is still listed.

- In `test_failed_new_reports_stray`, add an assertion that `calls` contains `"usage"` after the `"new"` failure.

---

VERDICT: FIX-FIRST