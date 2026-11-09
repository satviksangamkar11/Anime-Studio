

# BATCH merge_helper (supervl) 11-07 17:58

Note: `research/UI_PARALLEL_DISPATCH_2026-11-07.md` and the plan task extract were not included in the prompt, so I cannot answer the dispatch file's five questions or check for contradictions with the plan. Findings below are limited to the two provided files.

1) **Severity: high** — `i18n_merge.py:91-94`
   - Why: `en.json` is `os.replace`d before `mr.json`. A crash, kill, or error (e.g. disk full) between the two replaces leaves one language updated and the other stale, breaking the "en and mr of one batch must hold the same keys" invariant and silently losing strings.
   - Failing situation: a merge adds `step.go` to both languages; the `en.json` replace succeeds, then `mr.json` temp write fails → `en.json` contains `step.go`, `mr.json` does not.
   - Fix: stage both temp files, then replace both; if the second replace fails, restore the first from a pre-replace backup before re-raising.

2) **Severity: medium** — `i18n_merge.py:93`
   - Why: `Path.write_text(..., newline="\n")` only exists in Python 3.10+; on Python 3.9 it raises `TypeError`, which `main` does not catch, crashing every merge.
   - Failing situation: the server runs Python 3.9; `im.merge` raises `TypeError` on `write_text` → no strings written, traceback/exit 1.
   - Fix: write the temp via `tmp.open("w", encoding="utf-8", newline="\n")` (builtin `open` supports `newline` on all versions).

3) **Severity: medium** — `i18n_merge.py:99`
   - Why: `except OSError: pass` swallows lock-file unlink failures; on Windows (or if an indexer/AV holds the sentinel) `.lock` remains and blocks every later merge for the 30 s timeout each time.
   - Failing situation: a merge finishes but `unlink` raises `PermissionError` (Windows) and is swallowed; the next merge waits 30 s then refuses with exit 2.
   - Fix: retry unlink briefly and, if it still fails, raise `Refused` with a clear message instead of silently leaving a stale lock.

4) **Severity: low** — `i18n_merge.py:61-63`
   - Why: `--prefix` values are never validated, so a coder can pass another task's group or an over-broad prefix; the script only matches keys against it and cannot enforce "a coder may only add its own groups."
   - Failing situation: a coder assigned `step` passes `--prefix app` and adds `app.title` (another task's group) when the key is new — accepted.
   - Fix: validate each prefix against `^[a-z0-9_]+(\.[a-z0-9_]+)*$` and reject invalid ones (group assignment stays with the dispatcher).

FINAL: 1) i18n_merge.py:91-94 high — non-atomic cross-language write; 2) i18n_merge.py:93 medium — Path.write_text newline needs Python 3.10+; 3) i18n_merge.py:99 medium — swallowed lock unlink leaves stale lock; 4) i18n_merge.py:61-63 low — prefixes never validated.


# BATCH dispatch_rules (supervl) 11-07 18:00

Findings (concrete bugs only):

**1. HIGH — `test_i18n.py` edited by both coders in parallel, contradicting the ownership table.**
File:line: `UI_PARALLEL_DISPATCH_2026-11-07.md:16-18` (T3 edits only `pipeline.js`; T4 only `app.js` + `test_r3_fixes.py`; both only read tests) and `:43` (T4 told to remove the `test_i18n.py` xfail marker); `_plan_section7_extract.md:71` (T3 told to add data to `test_i18n.py`) and `:83` (T4 told to remove `test_i18n.py` xfail).
Why: The plan/prompts make T3 and T4 edit the same T2-owned test file at the same time. A coder following the prompt's "edit ONLY …" literally either leaves the xfail/parity data undone (incomplete) or edits a forbidden file; parallel edits to one file also race.
Fix: Make `test_i18n.py` a T4-only edit (the xfail marker); move T3's data additions to REQUESTS for the lead to apply; correct the ownership table and both prompts.

**2. HIGH — `test_parity.py`: dispatch says coders never edit it, but the plan makes T3 add rows to it.**
File:line: dispatch `:10` (§1.3: coder never edits `test_parity.py`; lead adds `PARITY_BUILT` names) and `:37` (T3 runs `test_parity` with `PARITY_BUILT=T2,T3`); plan `:71` (T3 adds `NEW_ROWS` anchors to `test_parity.py`).
Why: T3's own `test_parity` run cannot pass if its rows/anchors aren't registered, yet T3 is barred from editing the file; T4's rows (D02, ES1-ES14, …) have no assigned owner to register them. Parallel editing would also race.
Fix: T3/T4 do not edit `test_parity.py`; T3 reports its `NEW_ROWS` anchors via REQUESTS; the lead registers all anchors (T3+T4) in `test_parity.py` per §1.3/§6 before the final suite run.

**3. HIGH — T4's "done" depends on T3's unfinished file.**
File:line: dispatch `:43` (T4 removes the `test_i18n` check-5 xfail only after every literal is converted); plan `:57` (check 5 scans `app.js` + `pipeline.js`) and `:83` (T4 removes the marker; T4 is not done while xfail).
Why: check 5 covers `pipeline.js`, which T3 owns and is converting in parallel. T4 cannot edit `pipeline.js`, so T4 is either blocked waiting for T3 or removes the marker too early and check 5 fails on leftover `pipeline.js` literals.
Fix: Sequence the xfail removal to the lead after T3 completes (post-merge step in §6); T4's done-criterion must not depend on T3's unfinished file.

**4. MEDIUM — The logging command is Unix-only, but the stack is Windows.**
File:line: dispatch `:28` (`echo "$(date +%m-%d\ %H:%M) ..." >> "D:/aai work/anime_studio/PROJECT_LOG.md"`).
Why: `$(date …)` is bash command substitution; the worktree is `D:\…` and Python is `C:\Python314\python.exe`. In cmd.exe/PowerShell the timestamp is literal or errors, so the owner rule "log every step" cannot be followed as written.
Fix: Use a Windows-compatible timestamp (e.g., PowerShell `Get-Date -Format "MM-dd\ HH:mm"`) or require Git Bash.

**5. MEDIUM — `i18n_merge --prefix` multi-group handling is unspecified.**
File:line: dispatch `:18` (`--prefix GROUPS`), `:37` (`--prefix <groups>`), `:43` (`--prefix adv`).
Why: T3 must add keys across 15 groups (ok, scope, …, icon). If `--prefix` accepts only one prefix, T3's keys are refused as "outside the coder's groups"; the coder may then hardcode literals or edit `en.json` directly — both forbidden.
Fix: Specify comma-separated `--prefix ok,scope,…` and document that keys are validated against the listed groups.

**6. MEDIUM (conditional) — `ui/i18n_merge.py` was not provided, so its locking/atomic-write/key checks cannot be verified.**
File:line: dispatch `:20` ("holds a lock while writing, and writes atomically"); `ui/i18n_merge.py` — not in review materials.
Why: If the lock covers only the write and not the full read-modify-write, parallel T3/T4 merges to the same `en.json`/`mr.json` lose strings (lost update). Atomic temp+rename is fine on Windows only if same volume.
Fix: Include `i18n_merge.py` and its test in the review; hold the lock across the entire read-modify-write; confirm the temp file and target are on the same volume.

**7. LOW — The `adv` group is shared between T2 (index.html static text) and T4 (app.js).**
File:line: dispatch `:20` (helper refuses to change an existing text); plan T2 `:51` ("These exact English phrases must stay in en.json values (Experts strings)").
Why: T2 already owns `adv.*` keys; if T4's new key collides with an existing T2 `adv.*` key, the merge refuses and T4 is blocked (it cannot edit `en.json`).
Fix: Clarify that adding a new key in an existing group is allowed (only changing an existing key's text is refused); collisions go to REQUESTS.

Answers to the five questions:

1. No. The rules do not prevent breakage: `test_i18n.py` and `test_parity.py` are edited by both coders in parallel despite the ownership table, and `en.json`/`mr.json` are merged concurrently by a helper whose lock scope is unverified (file not provided). Missing: an owner for T4's parity anchors, serialization of `test_i18n.py` edits, and a rule that the `i18n_merge` lock covers read-modify-write.

2. Yes — dropping browser checks from T3/T4 is the safe choice for one browser pane, and T5 doing them once is fine. The real sequencing problem is not the browser; it's that T4's done-criterion (xfail removal over `pipeline.js`) already depends on T3, so "parallel" is illusory.

3. Yes. The T4 prompt contradicts itself ("edit ONLY `app.js` + `test_r3_fixes.py`" vs. "remove the xfail from `test_i18n.py`"), and the T3 prompt says "edit ONLY `pipeline.js`" while the incorporated plan tells T3 to edit `test_i18n.py` and `test_parity.py`. A coder reading the prompt literally either leaves parity rows unticked / xfail in place or edits forbidden files. The logging command is Unix-only on Windows (a rule that cannot be followed), and `--prefix` multi-group handling is ambiguous. Missing rules: who registers T4's parity anchors, and the `i18n_merge` lock scope.

4. Broadly yes (T2 verified first, lead sets `PARITY_BUILT`, T3/T4 in parallel, then T5 and reviewers), but §6 must also cover the lead-applied `test_i18n.py`/`test_parity.py` changes, and the parallel T3/T4 step is not cleanly achievable because of the shared test files and the T4-on-T3 xfail dependency.

5. Cannot be verified — `ui/i18n_merge.py` and its test were not included in the review materials. The described behavior ("holds a lock while writing") is ambiguous: the lock must cover read-modify-write or parallel merges lose strings; `--prefix` multi-group handling is unspecified; atomic temp+rename is fine on Windows if same volume.

FINAL: 1 HIGH test_i18n.py parallel edit conflict (dispatch:16-18,43; plan:71,83); 2 HIGH test_parity.py edit vs lead-only rule (dispatch:10,37; plan:71); 3 HIGH T4 xfail removal depends on T3's pipeline.js (dispatch:43; plan:57,83); 4 MEDIUM Unix-only logging command on Windows (dispatch:28); 5 MEDIUM i18n_merge --prefix multi-group unspecified (dispatch:18,37,43); 6 MEDIUM i18n_merge.py not provided; lock may not cover read-modify-write (dispatch:20); 7 LOW adv group collision T2 vs T4 (dispatch:20; plan:51).


# BATCH merge_helper (supervl) 11-07 18:02

I reviewed `ui/i18n_merge.py` and `test_i18n_merge.py`. The dispatch file (`research/UI_PARALLEL_DISPATCH_2026-11-07.md`) and the plan task extract were not included in the provided files, so I cannot answer that file's five questions or check for contradictions with the plan; this review covers only the two i18n files provided.

**HIGH — i18n_merge.py:39-41 (`_lock`)**
Why: `_lock` evicts any `.lock` older than `STALE_LOCK_SEC` (120 s) purely by mtime, with no holder identity. If a live merge blocks longer than 120 s (disk/I/O stall), a second coder deletes the first coder's live lock and enters the critical section; both then `os.replace` en.json/mr.json and the last replace silently overwrites the first coder's keys — dropped strings, breaking the no-drop rule and the parallel-coder safety goal.
Failing situation: coder A's merge stalls >120 s; coder B evicts A's lock and merges its group; A resumes and replaces en.json/mr.json, erasing B's keys (or vice versa).
Fix: stop evicting by age alone; record the holder PID in the lock file and remove it only when the holder process is confirmed dead (e.g., `os.kill(pid, 0)` fails on POSIX), or use `fcntl.flock`/`msvcrt` locking that releases automatically on process death.

**MEDIUM — i18n_merge.py:112-113 (`merge`)**
Why: en.json and mr.json are `os.replace`d sequentially. If the process is killed between them, one language file is updated and the other is not, durably leaving en and mr with different key sets and dropping Marathi strings, violating the "en and mr must hold the same keys" rule. The `except OSError` undo covers in-process exceptions only, not SIGKILL.
Failing situation: merge is killed after en.json is replaced but before mr.json; en now contains the new keys while mr does not.
Fix: on any replace failure restore BOTH languages from `backup` (not just `done`) and unlink the tmp files; the SIGKILL window needs a two-file commit journal to close fully, so document per-file atomicity as the guarantee and reconcile on startup.

**LOW — i18n_merge.py:113 (`os.replace`, Windows)**
Why: on Windows `os.replace` fails with `PermissionError` if the destination JSON is open by another process without `FILE_SHARE_DELETE` (e.g., the owner's server reading en.json). The merge aborts; the in-process undo prevents data loss, but the coder's merge is blocked while the server runs on Windows.
Failing situation: on Windows, the server has en.json open; a coder's merge fails at `os.replace` for en.json/mr.json.
Fix: document that the i18n files must not be held open by the server during a merge on Windows (no pure-Python fix); alternatively retry the replace.

The test file `test_i18n_merge.py` shows no defects; its concurrent-merge, stale-lock, and rollback cases pass.

FINAL: HIGH i18n_merge.py:39-41 stale-lock eviction of a live holder lets two coders enter the critical section and silently overwrite each other's keys; MEDIUM i18n_merge.py:112-113 en.json and mr.json are replaced non-atomically so a kill between them leaves the language pair divergent and drops Marathi strings; LOW i18n_merge.py:113 os.replace on Windows fails if the server holds the destination JSON open, blocking merges.
