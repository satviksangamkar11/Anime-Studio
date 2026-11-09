# Dispatch review (Haiku medium, reviewer RD), 2026-11-07
Scope: UI_PARALLEL_DISPATCH rev 2, ui/i18n_merge.py + test (8 pass), ui/test_parity.py, ui/test_i18n.py, plan sections 7 and 9.1, committed tree d115e65, round-2 SUPERVL and DOTS outputs.
Baseline (read-only): test_i18n_merge 8 passed; test_parity with PARITY_BUILT=T2,T3 gives 213 passed, 24 skipped (env var ignored); test_i18n --runxfail gives 1 fail (check 5, app.js literals, expected until T4).

## Findings (mine)
1. HIGH | ui/test_parity.py:24 | PARITY_BUILT is not read; BUILT is hard-coded {"T0","T1","T2"}. Dispatch 1.3 and 2b.5 depend on it. A T3 run skips all T3 NEW_ROWS and write_pack_claude and still reports green. Fix (lead): BUILT = {"T0","T1","T2"} | {x for x in os.environ.get("PARITY_BUILT","").split(",") if x.strip()}; then T3 runs must show 0 T3 skips.
2. HIGH | research/UI_PARALLEL_DISPATCH sections 7 and 8 (the two prompts) | Prompts say "section 2b of the dispatch rules", "your rows are listed in the dispatch rules above" and "log as described", but give no path. The dispatch lives outside the worktree and a fresh coder cannot see the overrides, row lists or log command. Fix: paste 2b, the task row list, the log command and TYPE list into each prompt, or give the absolute path D:\aai work\anime_studio\research\UI_PARALLEL_DISPATCH_2026-11-07.md.
3. HIGH | ui/static/i18n/en.json and mr.json (committed d115e65) | Dispatch 1.2 says banner and dialog groups exist. They do not (0 keys for banner.* and dialog.*); plan 3.4 gives T2 6 and 16 keys. Fix: T2 fix-up, or lead confirms T2 complete before sending T3/T4.
4. MEDIUM | Dispatch section 5 lists vs plan 9.1 Task column | Rows in no list: H02, H03, H04 (T2/T3), H09 (T3), H05, H06, H08 (T2/T4), D03 app.js part (T4/T3). Done rule "every owned row ticked" leaves them open. Fix: add H02-H04 and H09 to T3; H05, H06, H08 and D03-app to T4. test_parity checks anchors, not ownership, so nothing catches this.
5. MEDIUM | en.json and mr.json step.* (12 keys) and runs.title | T3 groups were pre-filled by T2. The helper refuses changed text without --replace. Fix: lead settles wording before sending; T3 lists differences under REQUESTS.
6. MEDIUM | Plan T4 retarget of ui/test_r3_fixes.py:121 | Planned line `"Pick a shot file." in body or "'adv.video.err_pick_shot_file'" in body` passes if either string is anywhere, so the key can stay unused, which weakens the test. Plan wants the key within 400 chars of h3Run. Fix: assert the key in body[:400] and en.json adv.video.err_pick_shot_file == "Pick a shot file.".
7. MEDIUM | docs/UI_REDESIGN_PLAN_2026-11-07.md:678, 734, 760, 762 | Plan says "run one after another; each ends with all suites green", T4 removes the xfail marker, and "T4 is not done while it is xfail". Dispatch 2b overrides these, but coders read the plan first. Fix: amend those lines to point to dispatch 2b.
8. MEDIUM | ui/i18n_merge.py:5 | Docstring says either side may be empty or missing; lines 67-71 refuse both. Fix: "both sides must hold the same non-empty key set".
9. LOW | Both prompts | No instruction to write the coder's final report in English (owner rule). Fix: add it.
10. LOW | ui/i18n_merge.py:131, 133 | --prefix and --dir are agent-controlled, so group isolation depends on the coder. An env var is equally agent-controlled. Fix: lead checks git diff of en.json and mr.json after each merge (only that coder's groups change); drop --dir from main() (tests can call merge()).
11. LOW | ui/i18n_merge.py:105-108, 116-117 | Rollback uses plain write_bytes; a failed staging leaves .tmp files. Fix: rollback via tmp and os.replace; remove tmp files in finally.
12. LOW | ui/i18n_merge.py:120-125 and :39 | finally unlinks .lock even after a stale takeover by another process. Needs a stall over 120 s, so low risk. Fix: write PID into the lock; unlink only if it matches.
13. LOW | ui/i18n_merge.py:109-118 | Two os.replace calls; a kill between them leaves en and mr out of step. Fix: fsync temps; refuse if on-disk en and mr key sets differ.
14. LOW | ui/i18n_merge.py:107-108 | No fsync before os.replace. Fix: flush and os.fsync each temp.
15. LOW | Dispatch 1.4 | Says helper has 7 tests; file has 8, all pass. Fix: change the count.
16. LOW | Dispatch section 5 "State" | Says T2 "is running"; T2 is committed (d115e65). Fix: update the text.
17. LOW | PROJECT_LOG.md (two coders, echo >>) | One short line per append; interleave risk is small. Keep; lead checks the log lines.

## Round-2 reviewer outputs: verdicts
SUPERVL dispatch review
- #1 xfail contradiction: REAL (finding 7 and 6-area).
- #2 "all suites green" impossible: PARTLY WRONG. Dispatch section 3 and 2b.2 already cover cross-task failures; only the plan header is real (finding 7).
- #3 i18n_merge lock unverified on Windows: WRONG. Lock is O_CREAT|O_EXCL (line 36); write is temp plus os.replace; 8 of 8 tests pass.
- #4 log path outside worktree: REAL, LOW. Owner rule needs PROJECT_LOG.md; add one sentence saying the log append is the only allowed write outside the worktree.
- #5 concurrent log appends: REAL, LOW (finding 17).
- #6 plan header "one after another": REAL (finding 7).
SUPERVL helper review
- #1 finally unlinks another process's lock: REAL, LOW (finding 12).
- #2 two non-atomic replaces: REAL, LOW (finding 13).
- #3 no fsync: REAL, LOW (finding 14).
DOTS dispatch review
- #1 NEW_ROWS not added to test_parity: WRONG as stated. T3 NEW_ROWS are already at test_parity.py:66-77. Real part is PARITY_BUILT (finding 1).
- #2 plan line 83 xfail: REAL (finding 7).
- #3 helper not provided: OBSOLETE; it is provided and reviewed here.
- #4 "video" vs "adv.video": WRONG. The helper matches the prefix "video." with the dot, so "adv.video.x" does not match.
- #5 log appends: REAL, LOW (finding 17).
- #6 T2 NEW_ROWS not applied: WRONG. H12 (ui-lang-mr) is in NEW_ROWS at line 65.
DOTS helper review
- #1 --prefix agent-controlled: REAL as a design limit, rated MEDIUM here (finding 10).
- #2 --dir agent-controlled: REAL, LOW (finding 10).
- #3 docstring contradiction: REAL (finding 8).
- #4 helper must log: WRONG as a requirement. The owner rule is per coder step in PROJECT_LOG.md; the coder logs it.
- #5 and #6 rollback and leftover tmp: REAL, LOW (finding 11).
- #7 os.replace on a file open by the server (Windows): REAL, LOW. The helper refuses with exit 2 and writes nothing, so a retry is enough.
- #8 stale lock by mtime: REAL, LOW (finding 12).

## Checked and fine
- Helper key, group, refusal and atomic path logic, as tested.
- Ports: no test uses 8765 (test_ui.py uses make_server(cfg, 0)). The owner UI holds 8765 (server.py:33); T5 must not start on 8765 while it runs.
- Owner rules in both prompts: no Colab, no paid or Claude call, no commit or push, no Granth Studio or story data. Missing only English report (finding 9).
- File ownership: pipeline.js (T3) and app.js plus test_r3_fixes.py (T4) are disjoint. Key groups are disjoint (video. vs adv.video.). Shared writes are only en.json and mr.json (lock) and PROJECT_LOG.md.
- Check 5 xfail marker is at test_i18n.py:180; the lead removes it after both reports.

FINAL: 17 findings: 3 HIGH (1, 2, 3), 5 MEDIUM (4-8), 9 LOW (9-17). Verdict: NEEDS FIXES. Fix 1 to 4 and 7 before sending T3 and T4.
