

# BATCH dispatch_rules (dots) 11-07 18:06



1. File-ownership and string-merge rules mostly prevent cross‑coder damage, but the i18n_merge.py lock must be robust (no file provided to verify). PROJECT_LOG.md appends can interleave on Windows; whole-suite runs are read‑only and safe.  
2. Dropping browser checks from T3/T4 is safe – only T5 will drive the browser after both are done.  
3. The prompts are clear, but the plan extract still says T4 removes the xfail marker (contradicting the dispatch override), and the test_parity workflow is broken (coders run with their own NEW_ROWS that the lead hasn’t added yet). These could mislead a coder into editing a file they shouldn’t or into thinking their parity work is incomplete.  
4. The order in section 6 is correct: T2 verified → PARITY_BUILT set → T3/T4 parallel → T5 → reviewers.  
5. ui/i18n_merge.py was not provided; I cannot check its locking, atomic write, key checks, or Windows behaviour. The description sounds correct, but the implementation must be reviewed.

FINAL:
- **High** — `research/UI_PARALLEL_DISPATCH_2026-11-07.md:24,28,32-34` – The coders are told to run `test_parity` with `PARITY_BUILT=T2,T3` (or T2,T4), but their NEW_ROWS anchors are not added to `test_parity.py` until after both reports (section 2b). The test will fail because the anchors are missing, causing confusion and blocking parity verification. **Fix:** Either have the lead add each coder’s NEW_ROWS before that coder runs, or instruct coders to run `test_parity` without their own NEW_ROWS and verify those anchors manually, reporting the missing anchors in REQUESTS.
- **Medium** — `_plan_section7_extract.md:83` – The plan says “Remove the xfail marker from test_i18n.py check 5 (allowed edit of that one marker)” for T4, but the dispatch override (section 2b) says the lead removes it after both T3 and T4 are verified. A coder reading the plan might edit `test_i18n.py`, violating file ownership. **Fix:** Update the plan extract to match the dispatch override, or strike the line and reference section 2b.
- **Medium** — `ui/i18n_merge.py` (not provided; referenced in dispatch line 11) – The script is described as holding a lock, writing atomically, and checking keys, but the file is missing from the review package. Cannot verify that it correctly implements these safety mechanisms, especially on Windows. **Fix:** Provide `ui/i18n_merge.py` and its test for review.
- **Medium** — `research/UI_PARALLEL_DISPATCH_2026-11-07.md:21` – String groups: T3 owns “video”, T4 owns “adv”. T4’s app.js includes a Video section that needs keys (e.g., `adv.video.err_pick_shot_file`). While T4 uses the `adv` prefix, the ownership of “video” by T3 could mislead a coder into thinking they cannot add any video-related keys. **Fix:** Clarify that T4’s keys are under the “adv” prefix (e.g., `adv.video.*`) and are independent of T3’s top-level “video” group.
- **Low** — `research/UI_PARALLEL_DISPATCH_2026-11-07.md:37` – Both coders append to `PROJECT_LOG.md` using `>>`, which on Windows (Git Bash) could interleave lines if they write simultaneously. **Fix:** Use a lock file for the log, or have the lead aggregate the logs from the coders’ reports.
- **Low** — `research/UI_PARALLEL_DISPATCH_2026-11-07.md:8-11` – The prerequisites for sending T3/T4 include T2 finished and committed, but do not explicitly state that the lead has applied T2’s REQUESTS (including any NEW_ROWS) to `test_parity.py`. If T2’s NEW_ROWS are missing, T3/T4’s `test_parity` runs could fail. **Fix:** Add a check that the lead has applied T2’s REQUESTS and that `test_parity.py` includes T2’s NEW_ROWS.


# BATCH merge_helper (dots) 11-07 18:08



## Review of `ui/i18n_merge.py` and `test_i18n_merge.py`

**Caveat:** the review input only contained `ui/i18n_merge.py` and `test_i18n_merge.py`. The dispatch file (`research/UI_PARALLEL_DISPATCH_2026-11-07.md`), the two coder prompts, and the plan task extract were **not** pasted, so I could not answer the five dispatch questions, nor check the prompts for conflicts with this script.

**What is working well (so I don't flag them):** all JSON writes happen only inside the exclusive `.lock` (lines 85–125); every merge re-reads `cur` *inside* the lock (lines 88–89), so two coders with disjoint groups lose nothing; temp-file + `os.replace` makes each language file atomic (lines 104–118); every refusal exits 2 and writes no JSON; the threaded test (lines 83–96) is consistent with the code.

### Findings

**HIGH**

1. **`ui/i18n_merge.py:131` — `--prefix` is supplied by the agent, so group isolation is not enforced.** The docstring rule says "a coder may only add its own groups," but the only check is `k.startswith(groups)` (line 81) against whatever the *caller* passed. A parallel agent can pass `--prefix app,step,adv` (or `--replace`) and overwrite another coder's keys or the owner's existing keys — directly enabling "edit a file it must not" and dropping an existing feature. Fix: read the coder's groups from a dispatcher-controlled source (e.g. env var `I18N_GROUPS` / a manifest the agent cannot write), not from an agent-controlled CLI arg.

**MEDIUM**

2. **`ui/i18n_merge.py:133` — `--dir` is also agent-controlled.** Default is correct, but an agent can pass `--dir /tmp/elsewhere` and its keys land outside the canonical `ui/static/i18n`, so the feature silently never reaches the served file (a dropped feature) or is written outside the repo. Fix: take the target dir from a dispatcher-set env var / constant and don't let the agent override it (keep `--dir` only for tests).

3. **`ui/i18n_merge.py:5` — docstring contradicts the code it describes.** Usage says `{"en": {...}, "mr": {...}} (either side may be empty or missing)`, but lines 67–71 refuse unequal/empty sides. An agent reading the docstring will produce a batch that gets REFUSED and waste a step. Fix: change line 5 to "both sides must hold the same keys; an empty batch is refused".

4. **No logging anywhere — violates the owner's "log every step" rule.** The mutation step prints only one summary line to stdout on success (line 141) and nothing persistent; there is no record of *who* (which group) changed *which* keys. Fix: append one line per successful merge to a log file (e.g. `ui/static/i18n/merge.log`, written under a separate append lock or with `O_APPEND`).

**LOW**

5. **`ui/i18n_merge.py:116–117` — rollback is not atomic.** On a failed second `os.replace`, the undo uses a direct `write_bytes`; if that write also fails, the restored file can be left corrupted. Fix: write the rollback to a `.tmp` and `os.replace` it.

6. **`ui/i18n_merge.py:105–108` — leftover `.tmp` files on failure.** If the merge raises after staging temp files (missing input file, failed replace), `en.json.tmp`/`mr.json.tmp` remain in the i18n dir. Harmless today (truncated on next run) but clutter. Fix: clean up temp files in the `finally`.

7. **`ui/i18n_merge.py:113` — Windows: `os.replace` fails if the target is open by the owner's running server.** If the server serves `ui/static/i18n` live and runs on Windows, every merge would raise `OSError` and be refused. On Linux (rename-while-open is fine) this doesn't occur. Fix: note the target must not be the live-served copy, or handle the error explicitly.

8. **`ui/i18n_merge.py:39` — stale-lock removal trusts mtime with a 120 s window.** On a loaded or network filesystem a live lock could be wrongly deleted, allowing two concurrent merges (lost update). Merges are milliseconds, so risk is low, but the window is unbounded by actual work time. Fix: tie the lock to a pid/heartbeat instead of mtime, or lower the risk by requiring the lock file to contain a pid and checking it is alive.

**No defects found** in `test_i18n_merge.py` (all cases are consistent with the implementation, including the `["step", ""]` trailing-comma case at line 54, which works because line 72 filters empty groups).

FINAL: HIGH: i18n_merge.py:131 --prefix is agent-controlled, defeating group isolation and allowing a coder to edit/overwrite files it must not (fix: read groups from a dispatcher-controlled env/manifest, not a CLI arg). MEDIUM: i18n_merge.py:133 --dir is agent-controlled, allowing writes outside the canonical i18n dir / dropped features. MEDIUM: i18n_merge.py:5 docstring says empty/missing sides are allowed but lines 67-71 refuse them (contradiction). MEDIUM: no persistent logging, violating "log every step". LOW: i18n_merge.py:116-117 rollback is a non-atomic direct write that can corrupt on failure. LOW: i18n_merge.py:105-108 leftover .tmp files on refusal after staging. LOW: i18n_merge.py:113 os.replace fails on Windows if the target is open by the live server. LOW: i18n_merge.py:39 stale-lock detection via mtime can wrongly remove a live lock on slow/network FS. NOTE: dispatch file, coder prompts, and plan extract were not provided — the five dispatch questions could not be answered and the prompts could not be cross-checked against this script.
