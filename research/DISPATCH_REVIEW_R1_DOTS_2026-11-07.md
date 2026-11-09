

# BATCH merge_helper (dots) 11-07 17:58



## Review of `ui/i18n_merge.py` + `test_i18n_merge.py`

**Materials gap:** the dispatch file (`research/UI_PARALLEL_DISPATCH_2026-11-07.md`) and the plan task-section extract were **not pasted**, so I could not check cross-coder file/resource conflicts, plan contradictions, or the five questions at the end of the dispatch file. Please resend those two files; everything below is from the helper script and its test only.

### Findings

**[HIGH] `i18n_merge.py:29-37, 96-101` — A crashed/timeout agent permanently deadlocks the entire merge pipeline.**
The lock is a bare `.lock` file created with `O_EXCL`. If the process is killed (OOM, SIGKILL, agent timeout) while holding it, the file is never removed. Every later coder then burns the full 30 s timeout and is `Refused`, and the `.lock` stays on disk forever — the only recovery is manual deletion, which the docstring itself admits ("remove it only if no merge is running"). For autonomous parallel agents this is a single point of failure: one dead agent silently drops **every subsequent coder's UI feature**. Fix: make it crash-recoverable — write the PID into the lock file and, on contention, check `os.kill(pid, 0)`; if the holder is dead, unlink the stale lock and retry (or use `fcntl.flock`, which is released automatically on process death).

**[MEDIUM] `i18n_merge.py:91-94` — The two language files are not written atomically as a pair.**
`en.json` is written+replaced, *then* `mr.json`. If the second `os.replace` fails (disk full, Windows file lock), `en.json` already holds the new keys while `mr.json` does not — permanently breaking the invariant the script enforces on input ("a missing Marathi string is a missing string"), and leaving a half-merged batch. Fix: write **both** `.tmp` files first, then `os.replace` both; if either replace fails, roll back / clean up so neither file changed.

**[LOW] `i18n_merge.py:94` — `os.replace` is not safe on Windows when the server has the file open.**
On POSIX, replacing a file a reader holds open is fine (reader keeps the old inode); on Windows `ReplaceFileW` fails with a sharing violation if the target is open. If the owner's server reads `en.json`/`mr.json` at request time and the merge races it, the merge crashes (exit 2) on Windows. Fix: use a unique temp name per write, or document POSIX-only, or have the server open with read sharing.

**[LOW] `i18n_merge.py:55` — An empty/missing batch silently succeeds.**
`batch.get("en") or {}` turns a missing/`null` side into `{}`, so a batch with no keys passes every check, rewrites both files under the lock (wasted I/O), and prints `added 0, kept 0, replaced 0` with exit 0. A coder expecting a refusal gets a false success. Fix: refuse when the batch contains no keys at all.

**[LOW] `i18n_merge.py:61-69` — `--prefix` edge cases produce confusing all-refused errors.**
A trailing comma (`"step,"`) yields group `"."`, which no valid key can start with, so every key is refused "outside your groups" despite the coder meaning just `step`. Fix: drop empty segments earlier and/or reject a prefix that no key can match.

**[LOW] `test_i18n_merge.py` — Missing coverage for the real failure modes.**
There is no test for (a) lock crash/staleness recovery, (b) a same-group/same-key conflict under real concurrency (the concurrency test uses disjoint groups, so it never exercises contention), or (c) a failed second write leaving a half-merged pair. These are exactly the cases the script's correctness depends on.

### Summary of the one-line fixes
1. PID-based stale-lock recovery (or `fcntl.flock`).
2. Write both temp files, then replace both atomically as a pair.
3. Unique temp name / POSIX-only / server read-sharing.
4. Refuse an empty batch.
5. Validate/drop empty `--prefix` segments.
6. Add crash-recovery, same-key-concurrency, and pair-atomicity tests.

FINAL: HIGH stale-lock deadlock (i18n_merge.py:29-37,96-101); MEDIUM non-atomic pair write (i18n_merge.py:91-94); LOW Windows os.replace vs open file (i18n_merge.py:94); LOW empty-batch silent success (i18n_merge.py:55); LOW --prefix edge cases (i18n_merge.py:61-69); LOW missing test coverage (test_i18n_merge.py). Dispatch file and plan extract not provided — the five dispatch questions and cross-coder conflict review could not be completed; please resend.


# BATCH dispatch_rules (dots) 11-07 18:00



## Findings

**H1 — test_i18n.py is edited by both coders concurrently; the ownership table omits it.**
`ui/i18n_merge.py`-adjacent file `ui/test_i18n.py` is written to by both plan tasks: plan L71 ("T3 … add to `test_i18n.py`'s data only") and plan L83 ("T4 … Remove the xfail marker from `test_i18n.py` check 5"). Dispatch L17/L18 lets T3 edit only `pipeline.js` and T4 only `app.js` + `test_r3_fixes.py`, so the table neither authorizes nor serializes this. Two agents editing one file at the same time ⇒ lost updates, and the "different files ⇒ parallel" claim (dispatch L5) is false.
*Fix:* assign `test_i18n.py` to one owner (e.g. T4 owns both its marker removal and the T3-key data block), or the lead edits it after both finish; update the ownership table.

**H2 — test_parity.py `NEW_ROWS` is written by T3 (and possibly T4) despite being forbidden.**
Plan L71 tells T3 "add to `test_parity.py` `NEW_ROWS` anchors"; dispatch L17/L18 forbid T3 from editing any test. If T3 obeys the dispatch, its anchors are never registered and T5's "every anchor must be found" (plan L15–16) fails; if T3 obeys the plan, it violates ownership and collides with T4's rows.
*Fix:* remove the "add to test_parity.py" line from the T3 prompt and add an explicit lead step "populate `NEW_ROWS` with T3+T4 anchors" before T5 (dispatch L33–34 lacks it).

**H3 — T4 prompt contradicts itself on editing test_i18n.py; strict table-following deadlocks T4.**
Prompt L43 says "do not edit … other tests" yet also "Remove the xfail marker from `test_i18n.py` check 5". Plan L83 says "T4 is not done while it is xfail." A coder reading only the ownership table (L17) leaves the marker → T4 never done; a coder reading the prompt edits a file the table forbids.
*Fix:* add `ui/test_i18n.py` (that one marker line) to T4's "May edit" list in L17, and move the actual removal to the lead after both finish.

**H4 — Browser-check paragraphs in both prompts directly violate dispatch L25.**
L25: "NEITHER T3 NOR T4 does browser checks … To avoid two agents driving one browser pane." Yet prompt L72–73 (T3: writer radio cards, stale-banner DOM) and L86 (T4: open every Advanced section including Video) are full browser-check instructions. A coder following the prompt drives the browser while the other agent does too.
*Fix:* delete the "Browser checks" paragraphs from both prompts; T5 does them once (L25 already says so).

**H5 — i18n_merge.py lock likely covers only the write, not the read‑merge‑write ⇒ lost update between T3 and T4.**
Dispatch L20 says the helper "holds a lock while writing." If the lock is acquired only for the write phase, T3 and T4 can each read the same base, merge, and overwrite each other's keys → silently dropped strings (owner's "no feature dropped" rule). Also nothing in the dispatch requires a **Windows-safe** lock (all paths are `D:\…`); `fcntl.flock` is a no-op there, so two concurrent merges would not be mutually exclusive at all. File not provided, so this is unverified — but the description as written is exactly the lost-update pattern.
*Fix:* lock the entire read→merge→write; use a cross-platform lock (PID + stale detection); add a two-process concurrency test to the 7 existing tests.

**H6 — Single shared `PROJECT_LOG.md` with non-atomic `echo … >>` append; path doesn't match the worktree.**
L28 hardcodes `D:\aai work\anime_studio/PROJECT_LOG.md` while the worktree is `D:\aai work\anime_studio_merge` (L37/L42), and both coders append to the same file. Concurrent `>>` appends can drop lines, so owner rule 4 ("log every step") becomes unverifiable by the lead.
*Fix:* each coder logs to its own worktree file (`PROJECT_LOG_T3.md`) that the lead merges; or wrap the append in a lock; correct the path.

**H7 — test_i18n check-5 xfail removal has an unhandled parallel-ordering dependency.**
Plan L83: T4 removes the xfail "only after every literal is converted" — but check 5 scans **both** `app.js` and `pipeline.js`, and T3 owns `pipeline.js`. T3 and T4 run in parallel, so T4 cannot know when T3 is done. If T4 removes the marker early, T4's own final suite run fails (check 5 now strict); if T4 waits, parallelism is defeated.
*Fix:* have the lead remove the marker after both finish; T4's "done" condition should be "all `app.js` literals converted" (a targeted scan), not the global check 5.

**H8 — Final whole-suite run lacks `PARITY_BUILT` for the owning task.**
Prompt L39/L44 tell each coder to run "the whole ui suite once at the end" but only specify `PARITY_BUILT` for the subset run. Without the env set to include its own task, the coder's parity rows are skipped and cannot be ticked.
*Fix:* state `PARITY_BUILT=T2,T3` (T3) / `T2,T4` (T4) for the final whole-suite run too, or note that the lead sets it (L33).

**H9 — T3 prompt says "do not edit … tests" while the plan says "add to test_i18n.py's data" (internal contradiction in the same prompt).**
L38 ("do not edit … tests") vs plan L71 ("add to `test_i18n.py`'s data only"). A coder could drop the T3-key test data (breaking the 3.8.x checks that need T3's keys) or edit a forbidden file.
*Fix:* resolve ownership as in H1 and make the prompt self-consistent.

**H10 — i18n_merge.py correctness cannot be verified (file not provided).**
Design-level risks to check once the file is available: (a) en.json and mr.json must be written together or a killed mid-write leaves invalid JSON that breaks the other coder's `test_i18n`; (b) "refuses to change an existing text" must also refuse re-adding an existing key with different text; (c) "same keys in English and Marathi" must be enforced per batch, not per file; (d) atomic write must survive a killed process (temp file + `os.replace`, and cleanup of stale `.lock` via PID).

*Lower severity (no fix required, noted for completeness):* L1 `node --check` path separators differ (plan `\`, prompts `/`) — cosmetic. L2 log line uses `|` delimiter with a free-text "result" field — a result containing `|` breaks column parsing. L3 owner rules "never touch Granth Studio", "no story data", "no real render" are not restated in the T3/T4 prompts (only "no model/Claude/paid/Colab/network").

## Answers to the five questions

1. **No.** Shared resources missing from the "different files" claim: `en.json`/`mr.json` (merge race unless the lock covers read+merge+write and is Windows-safe), `test_i18n.py` (both plan tasks edit it), `test_parity.py` (T3 adds `NEW_ROWS`), and `PROJECT_LOG.md` (concurrent append).
2. **Yes, drop them** — but only if the browser-check paragraphs are actually removed from both prompts; as written they contradict L25 and would put two agents in one browser pane. T5 doing them once is the right design.
3. **Yes, several.** Contradictions: ownership table vs plan on `test_i18n.py`/`test_parity.py` edits (H1/H2); T4 prompt "do not edit other tests" vs marker removal (H3); T3 prompt "do not edit tests" vs "add to test_i18n.py data" (H9); browser checks present despite L25 (H4); `NEW_ROWS` ownership gap (H8); final-run `PARITY_BUILT` gap (H8); log path vs worktree (H6). A coder could easily drop a feature (e.g. T3 dropping its i18n test data, or T4 never removing the xfail).
4. **Mostly right.** Add two explicit lead steps before T5: populate `NEW_ROWS` with all T3/T4 anchors, and remove the `test_i18n` check-5 xfail. Also specify `PARITY_BUILT` for each coder's final whole-suite run.
5. **Not fully reviewable — the file was not provided.** The described behaviour ("lock while writing", "atomically", "requires same keys in en and mr", "refuses to change existing text") is sound in intent but the lock must cover the whole read-modify-write and must work on Windows, or T3/T4 will silently lose each other's keys.

FINAL: H1 (test_i18n.py dual ownership), H2 (test_parity.py NEW_ROWS), H3 (T4 marker-removal contradiction), H4 (browser checks violate L25), H5 (i18n_merge lock/lost-update + Windows), H6 (shared PROJECT_LOG.md append + path mismatch), H7 (check-5 xfail parallel ordering), H8 (NEW_ROWS + PARITY_BUILT gaps), H9 (T3 prompt internal contradiction), H10 (i18n_merge unverified)


# BATCH merge_helper (dots) 11-07 18:02



The dispatch file `research/UI_PARALLEL_DISPATCH_2026-11-07.md` and the plan extract were not provided, so the five questions at the end of that file cannot be answered. The following findings are based on the two supplied files.

**Findings**

1. **High** – Missing review materials: `research/UI_PARALLEL_DISPATCH_2026-11-07.md` and the plan task extract are not included. Without them it is impossible to check the exact coder prompts for ambiguity, contradictions with the plan, or missing safety/owner rules.  
   *Fix*: Supply the dispatch file and plan extract before the instructions are sent to agents.

2. **High** – Race condition in lock acquisition (TOCTOU): `i18n_merge.py:39-41` checks staleness with `stat` then unlinks, but another process can create a fresh lock between the two operations. The new lock is then deleted, breaking mutual exclusion and allowing two coders to merge simultaneously, which can corrupt `en.json` / `mr.json`.  
   *Fix*: Replace the file‑based lock with an atomic primitive (e.g., `os.mkdir` for a lock directory, or `fcntl.flock`) or write the PID into the lock file and check process liveness instead of blindly unlinking.

3. **Medium** – Temp files not cleaned up on failure: `i18n_merge.py:105-108,115-118` writes `.tmp` files but has no `finally` to remove them if an exception occurs before or during `os.replace`. Stale `.tmp` files can interfere with later merges.  
   *Fix*: Add a `finally` block that deletes any created temp files.

4. **Medium** – Default output directory may conflict with the running server: `i18n_merge.py:133` defaults to `ui/static/i18n/`, which is likely served by the owner’s running server. Running the script while the server is active can serve inconsistent or missing strings.  
   *Fix*: The dispatch rules must explicitly forbid running this script against the production i18n files and direct coders to use a development copy.

5. **Low** – Key regex may be too restrictive: `i18n_merge.py:22` requires at least two dot‑separated parts (`^[a-z0-9_]+(\.[a-z0-9_]+)+$`). If the plan allows single‑word keys (e.g., `title`), they will be refused.  
   *Fix*: Confirm the plan’s naming convention; if single‑word keys are allowed, relax the regex accordingly.

6. **Low** – Parallel test uses threads, not processes: `test_i18n_merge.py:83-96` simulates concurrency with threads inside one process, which does not replicate real parallel processes and may not expose the TOCTOU race in the lock.  
   *Fix*: Add a test that uses `multiprocessing` to better validate the locking mechanism.

FINAL: [1] High: missing dispatch file/plan extract; [2] High: TOCTOU race in lock; [3] Medium: temp files not cleaned; [4] Medium: running server conflict; [5] Low: key regex; [6] Low: test uses threads.
