Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything else byte-identical; do not add code that reads files at import time.

CARD:
**X-22 | hooks: pre-commit NEW, pre-push runs pytest, core.hooksPath**
- **Files:** `.githooks/pre-commit` NEW (sh); `.githooks/pre-push`; `tools/test_git_hooks.py` NEW.
- **Change:**
  - pre-commit: same PY lookup as pre-push lines 6-8, then `"$PY" "$ROOT/tools/precommit_check.py"`. A non-zero exit blocks.
  - pre-push: `cd "$ROOT"`, then `"$PY" -m pytest ${PUSH_TEST_PATHS:-director h3 score tools} -q -p no:cacheprovider`. Its exit code is used directly (no wrapper; log 11-07 push with hidden failing tests). Then the existing secret_scan.
  - Install: the owner runs `git config core.hooksPath .githooks` (the hook never changes config, pre-push line 3).
- **Tests (tmp git repo, ANIME_PY = sys.executable):**
  - `test_precommit_blocks_staged_key` (`git commit` exit ≠ 0).
  - `test_precommit_allows_clean`.
  - `test_prepush_fails_on_failing_test`: PUSH_TEST_PATHS = tmp failing test; stub secret_scan exit 0 → exit 1, and the output contains "failed".
  - `test_prepush_passes_on_passing_test`.
- **Closes:** 44, 46 (enforced at commit and push).
- **Depends on:** X-21.
- **Collision:** none.
- **Acceptance:** `python -m pytest tools/test_git_hooks.py -q`, then (owner) `git config --get core.hooksPath` prints `.githooks`.
- **OWNER DECISION:** the owner sets core.hooksPath; the push test scope (full suites may take minutes).
- **Second-attempt risk:** med (sh on Windows Git Bash; LF line endings required: write the files with `newline="\n"`).

---



REVIEW BY LUNA:
`_make_repo` copies the hooks without setting their executable bit:

```python
(hooks / name).write_bytes((HOOKS / name).read_bytes())
```

On systems where Git requires executable hooks, `test_precommit_blocks_staged_key` and the other commit tests can pass without running `pre-commit`. After copying each hook, set its executable bit, for example with `os.chmod(hooks / name, 0o755)`. The `_need_sh` check does not restrict these tests to Windows, so this can make the tests fail to verify the hook on Unix.

VERDICT: FIX-FIRST.

REVIEW BY DOTS:
**Analysis of defects:**

1. **`test_precommit_blocks_staged_key` assertion is tautological and does not verify the intended secret detection.**  
   The test builds a fake NVIDIA key with `nvapi-` prefix and expects the commit to be blocked. However, the assertion `assert fake_key not in result.stdout + result.stderr` is not a meaningful check for correctness; the real failure is that the test does not confirm that the hook actually detected the secret. The test only checks that the commit failed and that the key is not printed, but it does not verify that the failure was *due to* the secret. A weak or missing check on the actual detection mechanism makes the test unable to fail if `precommit_check.py` is broken or removed.

2. **`test_prepush_fails_on_failing_test` does not ensure the failing test is actually discovered and run.**  
   The test writes `test_fail.py` to the repo root but runs `_run_prepush(repo, "test_fail.py")`, which sets `PUSH_TEST_PATHS=test_fail.py`. However, the pre-push hook runs `pytest test_fail.py` from the repo root. While this should work, the test does not verify that pytest actually executed the test and failed — it only checks that the exit code is 1 and "failed" is in the output. If pytest fails to collect or run the test for any other reason (e.g., import error, missing conftest), the test would still pass falsely. The test lacks specificity: it does not confirm that the *intended* test failure caused the block.

3. **`test_precommit_blocks_python_syntax_error` is missing from the test file.**  
   The card lists four tests:
   - `test_precommit_blocks_staged_key`
   - `test_precommit_allows_clean`
   - `test_prepush_fails_on_failing_test`
   - `test_prepush_passes_on_passing_test`

   However, the test file also includes `test_precommit_blocks_python_syntax_error`, which is **not listed in the card**. While this test is reasonable, its presence does not compensate for the *missing* required test: the card explicitly requires `test_precommit_allows_clean`, which is present, but the card does not require the syntax error test. More critically, the card does not list `test_precommit_blocks_python_syntax_error` as a required test, so its inclusion is extraneous but not a defect. The real issue is that the card’s required tests are all present, so this is not a missing test.

4. **The pre-push hook does not change directory to the repo root before running pytest in a way that ensures correct module resolution.**  
   The hook does `cd "$ROOT"` before running pytest, which is correct. However, the test `_run_prepush` runs the hook with `cwd=repo`, and the hook itself does `cd "$ROOT"` (which is `repo`), so it should be fine. No defect here.

5. **The pre-commit hook does not use the same PY lookup as pre-push lines 6–8.**  
   The card says: "pre-commit: same PY lookup as pre-push lines 6–8". Looking at pre-push:
   ```
   PY="${ANIME_PY:-C:/Python314/python.exe}"
   [ -f "$PY" ] || PY=python
   ```
   Pre-commit has:
   ```
   PY="${ANIME_PY:-C:/Python314/python.exe}"
   [ -f "$PY" ] || PY=python
   ```
   They are identical. No defect.

6. **The pre-push hook runs `secret_scan.py` with `--remote "$remote"`, but the test stubs `secret_scan.py` to exit 0 immediately, ignoring arguments. This is acceptable for testing, but the test does not verify that `secret_scan` is called with the correct remote. However, the card does not require testing the remote argument, so this is not a defect.

7. **The test `test_prepush_passes_on_passing_test` does not verify that the secret_scan was actually executed.**  
   It stubs `secret_scan.py` to exit 0, but if the hook failed to call it (e.g., due to a path error), the test would still pass if pytest passed. The test does not confirm that the full pipeline (pytest + secret_scan) ran. This is a gap: the test is weak because it does not ensure that the second stage (secret_scan) was reached and executed. A failure in secret_scan (e.g., crash) would not be detected if the stub is too permissive.

**Critical Defect:**

The most serious issue is in `test_precommit_blocks_staged_key`: the test does not verify that the hook actually detected the secret. It only checks that the commit was blocked and the key was not printed. If `precommit_check.py` were replaced with a script that always exits 1 (e.g., `exit 1`), the test would still pass, even though the secret detection is broken. The test is **tautological** — it cannot fail if the hook blocks the commit for any reason, not specifically because of the secret. This violates the requirement that the test must verify the specific behavior.

Similarly, `test_prepush_fails_on_failing_test` does not verify that the failure was due to the test failure. If the hook failed to run pytest at all (e.g., due to a missing `python` command), it might exit 1, and the output might contain "failed" (e.g., from an error message), giving a false positive.

**Fix:**

For `test_precommit_blocks_staged_key`, add a check that the output indicates a secret was found (e.g., assert "secret" in output or "leak" in output, depending on what `precommit_check.py` prints). Alternatively, assert that the exit code is specifically due to secret detection by checking for a known message from the tool.

For `test_prepush_fails_on_failing_test`, ensure that the output contains specific evidence that pytest ran and failed (e.g., "1 failed" or "test_x" in the output).

But since we must quote the faulty line and give the exact fix, and the most clear-cut defect is the tautological assertion in `test_precommit_blocks_staged_key`:

**Faulty line:**
```python
assert fake_key not in result.stdout + result.stderr  # the secret text is never printed
```

This line is not the problem; the problem is the missing assertion that the secret was actually detected. The test lacks:
```python
assert "secret" in result.stdout + result.stderr or "leak" in result.stdout + result.stderr
```
But since we don't know the exact output, 