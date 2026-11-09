

# BATCH dispatch_rules (supervl) 11-07 18:06

Six real findings. `ui/i18n_merge.py` and its test were not included in the review set, so I cannot verify its code line-by-line; findings about it are spec/environment risks.

1. **High** — `UI_PARALLEL_DISPATCH_2026-11-07.md:18,24` vs `_plan_section7_extract.md:57,83,85`: contradiction over `ui/test_i18n.py`. Dispatch says test_i18n.py is lead-only/read-only for coders and the lead removes check-5's `xfail` marker only after both tasks are verified. The plan (which coders must read first) says T4 removes the marker (line 83), "T4 is not done while it is xfail" (line 57), and "all i18n checks must now pass without xfail" (line 85). But check 5 scans both `app.js` and `pipeline.js`, so neither coder can pass it alone. Failing situation: T4 either edits a forbidden file or cannot meet its own done-criteria and stalls; or a coder ships with a red check it was told must be green. Fix: coders never edit `test_i18n.py`; they list needed data/anchors under REQUESTS; the lead applies them and removes the marker after both are verified; drop "without xfail"/"removed by T4" from T4's done list.

2. **High** — `UI_PARALLEL_DISPATCH_2026-11-07.md:5,28,32,33` vs `_plan_section7_extract.md:1,4`: "each ends with all suites green" / "run one after another" conflicts with parallel T3/T4. T3's end-of-task full suite (`PARITY_BUILT=T2,T3`) fails `test_i18n` check 5 on `app.js` literals and `test_parity` on T4's missing anchors (and vice versa). Failing situation: a coder forces the suite green by editing the other task's file (forbidden) or reports done with red tests. Fix: all-suites-green applies only to the lead's run after both tasks finish; each coder's final full-suite run is diagnostic, cross-task failures go in PROBLEMS and are never fixed by touching the other's file.

3. **High** — `ui/i18n_merge.py` (not provided for review): its claimed cross-process lock, atomic write, and key/group checks are unverified. On Windows/Git Bash an `fcntl`-style lock is unavailable, so concurrent T3/T4 merges — the only allowed string path (dispatch :11,:21) — can interleave and corrupt `en.json`/`mr.json`. Failing situation: both coders merge strings at the same time; one write is lost or the JSON is left half-written, breaking the UI and i18n tests. Fix: before sending prompts, confirm the helper uses a Windows-compatible cross-process lock (e.g. `O_CREAT|O_EXCL` lockfile) and writes via temp file + `os.replace` in the same directory.

4. **Medium** — `UI_PARALLEL_DISPATCH_2026-11-07.md:37` vs prompts :46,:51: coders must "work only in" `D:\aai work\anime_studio_merge` but append logs to `D:\aai work\anime_studio\PROJECT_LOG.md`, a different directory outside the worktree. Failing situation: the append fails from the worktree, or it silently modifies the main worktree's tracked log, breaking the lead's audit. Fix: point the log at a path inside the merge worktree or a shared writable location outside both worktrees, and keep it consistent.

5. **Medium** — `UI_PARALLEL_DISPATCH_2026-11-07.md:37`: two coders append to the same `PROJECT_LOG.md` with `echo ... >>`; concurrent appends are not guaranteed atomic and lines can interleave or be lost. Failing situation: simultaneous steps from both coders garble or overwrite each other; the lead's log audit misses steps. Fix: serialize logging (one lead-owned logger or per-coder files merged by the lead).

6. **Medium** — `_plan_section7_extract.md:1`: "Implementation tasks (run one after another; each ends with all suites green)" contradicts the dispatch's parallel T3/T4 (dispatch :5). Coders told to read the plan first may serialize work or start in parallel against the plan's text. Fix: amend the plan header to state the dispatch overrides it and T3/T4 run in parallel once T2 is verified.

Answers to the five dispatch questions:
1. Mostly yes for source edits (disjoint files), but shared races remain: concurrent `en.json`/`mr.json` merges (helper lock unverified), concurrent `PROJECT_LOG.md` appends, `test_i18n.py` check 5 scanning both files (cross-task red tests), and `test_parity.py` must skip the other task's rows under `PARITY_BUILT`. Nothing serializes the final whole-suite run to the lead.
2. Yes — dropping browser checks from T3/T4 is the safe call for one browser pane; it defers UI verification to T5 (late defect discovery) but avoids two agents driving one pane.
3. Yes: findings 1, 2, 4, and 6 are ambiguous/misreadable and a coder could edit a forbidden file to force green or stall waiting for the other. No owner rule is missing beyond verifying `test_parity` skips non-`PARITY_BUILT` rows; the no-paid/Claude/Colab/no-server rules are repeated in both prompts.
4. Yes — T2 verified first, `PARITY_BUILT` for subsets, parallel T3/T4, then lead merges/applies REQUESTS, removes the marker, sets final `PARITY_BUILT=T2,T3,T4`, runs all suites, T5, reviewers, fix/review loop, restart. Make the lead's final `PARITY_BUILT` value explicit.
5. Cannot be confirmed — `ui/i18n_merge.py` and its test were not included. Based on the dispatch claims and Windows/Git Bash, the lock must be Windows-compatible (`fcntl` will not work) and the write must be temp + atomic replace; key/group/refusal logic matches the spec but is unverified.

FINAL: findings 1-6 (high: test_i18n.py xfail/ownership contradiction at dispatch :18,:24 vs plan :57,:83,:85; whole-suite "all green" impossible in parallel at dispatch :5,:28,:32,:33 vs plan :1,:4; i18n_merge lock/atomic write unverified and unsafe on Windows); medium: log path outside the confined worktree at dispatch :37 vs prompts :46,:51; concurrent non-atomic PROJECT_LOG.md appends at dispatch :37; plan header "run one after another" vs parallel dispatch at plan :1.


# BATCH merge_helper (supervl) 11-07 18:11

Note: the dispatch file (`research/UI_PARALLEL_DISPATCH_2026-11-07.md`) and the plan task extract were not included in the review materials, so I cannot answer its five questions or review those documents. I reviewed only `ui/i18n_merge.py` and `test_i18n_merge.py`.

Findings:

**1. high — i18n_merge.py:120-125**
Why: `finally` unconditionally unlinks `.lock` after `os.close(fd)`. If process A holds the lock, process B treats it as stale (>120 s), deletes it and creates its own lock; when A finally runs it unlinks B’s lock file. A third process can then enter the critical section while B is still writing, causing concurrent `os.replace` calls and lost batches (dropped strings, violating the owner’s “no feature dropped” rule).
Failing situation: Coder A’s merge hangs >120 s; coder B removes the stale lock, acquires its own, and starts merging; A resumes, closes its fd, and deletes `.lock` (now B’s); coder C acquires the lock and merges concurrently with B; the last `os.replace` overwrites the other, dropping one coder’s keys.
Fix: Write the creating PID into the lock file at creation and unlink in `finally` only if the file still contains this PID (or switch to `fcntl.flock` and never unlink on release).

**2. medium — i18n_merge.py:109-118**
Why: `en.json` and `mr.json` are replaced with two separate `os.replace` calls. If the process is killed between them, one language is updated and the other is not, leaving the pair inconsistent; the lock file is also left behind as stale.
Failing situation: A merge adds keys to en and mr; `os.replace` for en succeeds; the process is SIGKILLed before mr is replaced; en.json now contains the new keys but mr.json does not, so the UI shows missing/unmatched Marathi strings.
Fix: Make on-disk en/mr key-set equality a precondition (refuse if the existing files already differ, directing the operator to restore from backup); two `os.replace` calls cannot be made atomic otherwise.

**3. low — i18n_merge.py:107-108**
Why: The staged temp file is written but not `fsync`ed before `os.replace`. On power/OS crash, the replacement may persist as empty or stale content.
Failing situation: Merge writes en.json.tmp and mr.json.tmp; power fails before the page cache is flushed; after reboot the directory entry points to a zero-length or old file.
Fix: Add `fh.flush(); os.fsync(fh.fileno())` after writing each temp file.

FINAL: 1) high i18n_merge.py:120-125 — finally unconditionally unlinks .lock and can delete another process’s lock after a stale-lock takeover, enabling concurrent merges and lost strings; fix by PID-gating the unlink or using fcntl.flock. 2) medium i18n_merge.py:109-118 — en and mr are replaced with two non-atomic os.replace calls, so a kill between them leaves languages inconsistent; fix by refusing when on-disk en/mr key sets differ. 3) low i18n_merge.py:107-108 — temp files are not fsynced before os.replace, risking empty/stale files after a crash; fix by flushing and fsyncing each temp file.
