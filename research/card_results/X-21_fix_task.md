Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything else byte-identical; do not add code that reads files at import time.

CARD:
**X-21 | precommit_check: project key patterns, staged blob, binaries**
- **Files:** `tools/precommit_check.py`; `tools/test_precommit_check.py` (append).
- **Change:**
  - Add to SECRET_PATTERNS (precommit_check.py:11-16):
    - `"elevenlabs": r"sk_[0-9a-f]{40,}"`
    - `"anthropic": r"sk-ant-[A-Za-z0-9_-]{20,}"`
    - `"google": r"AIza[0-9A-Za-z_-]{35}"`
    - `"github": r"gh[pousr]_[A-Za-z0-9]{36,}"`
  - `_CONTROL_CHAR_RE` also matches `\x7f`.
  - `check_file(path, staged=True)` reads `git show :<path>` bytes (the staged blob), not the working copy (precommit_check.py:60).
  - Skip extensions `{.png,.jpg,.jpeg,.webp,.gif,.wav,.mp3,.mp4,.mov,.ttf,.otf,.zip,.pdf}` (no "not UTF-8" failure). The size limit still applies.
- **Tests:** secrets built at runtime (`"sk_" + "a"*48`) so the test file never trips the scanner.
  - `test_elevenlabs_key_found`, `test_anthropic_key_found`, `test_google_key_found`, `test_github_token_found`.
  - `test_nul_byte_found`.
  - `test_del_found`.
  - `test_staged_blob_scanned_after_worktree_cleaned`: tmp git repo; stage a file with a key, then clean the working file → still found.
  - `test_png_skipped`.
- **Closes:** 46 (patterns + staged blob), 44 (partly: syntax/control characters). Bug: Opus 12, merged E4.
- **Depends on:** none.
- **Collision:** none.
- **Acceptance:** `python -m pytest tools/test_precommit_check.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** low.



REVIEW BY LUNA:
- **The card’s Anthropic pattern is missing.** The implementation delegates to `secret_scan.content_findings`, whose `RULES` include a generic `sk-` rule but no `sk-ant-` rule. The supplied Anthropic test uses a token that the generic rule catches, so it does not verify the required pattern. Add a dedicated `sk-ant-[A-Za-z0-9_-]{20,}` rule to the shared scanner and assert its rule ID in the test.

- **Several required tests are absent from the acceptance target.** The card names `test_elevenlabs_key_found`, `test_google_key_found`, `test_nul_byte_found`, `test_del_found`, and `test_staged_blob_scanned_after_worktree_cleaned`. Those exact tests are in `tools/test_precommit_cards.py`, not the specified `tools/test_precommit_check.py`; that file has no Google test, and its staged test calls `check_staged`, not `check_file(..., staged=True)`. Move or add the required tests to `tools/test_precommit_check.py`, using the named tests and the staged `check_file` path.

VERDICT: FIX-FIRST

REVIEW BY DOTS:
**REAL DEFECTS:**

1. **`check_file` ignores `staged=True` when reading the working file**  
   `precommit_check.py:60`  
   `raw = fh.read()`  
   When `staged=True`, the code still opens the working file instead of reading the staged blob via `git show :<path>`. This means the test `test_staged_blob_scanned_after_worktree_cleaned` will read the cleaned working file and fail to find the secret.  
   **Fix:**  
   ```python
   if staged:
       result = subprocess.run(["git", "show", f":{path}"], capture_output=True)
       if result.returncode != 0:
           return [f"{path}: cannot read staged blob"]
       raw = result.stdout
   else:
       with open(path, "rb") as fh:
           raw = fh.read()
   ```

2. **`check_staged` is dead code; `main()` uses it but it duplicates `check_file` with `staged=True`**  
   `precommit_check.py:103`  
   `findings.extend(check_staged(path))`  
   `check_staged` does the same thing as `check_file(path, staged=True)` but is a separate function. This is redundant and confusing.  
   **Fix:**  
   Replace `check_staged(path)` with `check_file(path, staged=True)` and remove `check_staged`.

3. **`_CONTROL_CHAR_RE` does not match `\x7f` as required by the card**  
   `precommit_check.py:19`  
   `_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")`  
   The card says `_CONTROL_CHAR_RE` also matches `\x7f`. The regex includes `\x7f`, so this is actually correct. **No defect here.**

4. **`check_file` does not skip blocked extensions when reading the staged blob**  
   `precommit_check.py:60-63`  
   The card says "Skip extensions `{.png,.jpg,...}` (no 'not UTF-8' failure). The size limit still applies."  
   Currently, `check_file` calls `check_blob`, which does skip blocked extensions. However, the size check happens *after* reading the blob. If a staged blob is over 1 MB and is a blocked extension, it should still be skipped (size limit does not apply to blocked extensions).  
   **Fix:**  
   In `check_blob`, move the size check *after* the blocked extension check, or skip size check for blocked extensions. Currently, the size check is first, which is incorrect for blocked extensions.

5. **`check_blob` size check applies to blocked extensions**  
   `precommit_check.py:74-75`  
   `if len(raw) > _MAX_FILE_SIZE: return [f"{path}: over 1 MB"]`  
   The card says "The size limit still applies" for blocked extensions. So this is correct. **No defect here.**

6. **Tests use wrong rule IDs**  
   `tools/test_precommit_cards.py:44,50,56,62`  
   The tests assert `"K-ELEVEN"`, `"K-OPENAI"`, `"K-GOOGLE"`, `"K-GITHUB"` in findings. However, the card does not specify rule IDs. The actual rule IDs come from `secret_scan`. If `secret_scan` uses different IDs (e.g., `"ELEVENLABS"` instead of `"K-ELEVEN"`), the tests will fail.  
   **Fix:**  
   Check the actual rule IDs in `secret_scan` and update the tests accordingly.

7. **`test_anthropic_key_found` uses `"K-OPENAI"` instead of `"K-ANTHROPIC"`**  
   `tools/test_precommit_cards.py:50`  
   `assert any("K-OPENAI" in f for f in findings)`  
   This is likely a copy-paste error. The card says `"anthropic"` pattern, so the rule ID should be something like `"K-ANTHROPIC"`.  
   **Fix:**  
   Change `"K-OPENAI"` to the correct rule ID for Anthropic.

8. **`check_file` does not handle `staged=True` for blocked extensions**  
   `precommit_check.py:60-63`  
   When `staged=True`, the code reads the staged blob but does not skip blocked extensions before reading. It should skip blocked extensions without reading the blob.  
   **Fix:**  
   Check the extension before reading the blob when `staged=True`.

**VERDICT: FIX-FIRST**