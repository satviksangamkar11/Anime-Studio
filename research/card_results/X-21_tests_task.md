Write ONLY the test file tools/test_precommit_cards.py (plain pytest, standard library, tmp_path, no network, no model call; start with sys.path.insert of its own folder and the project root so the modules import by bare name or package as the neighbouring tests do). It is the frozen test gate for this gap card; the module change is made later by someone else, so the tests must FAIL on the current code and pass on a correct implementation. Use the hand-computed values written in the card; do not copy code from the module under test. Cover every test name the card lists.

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

