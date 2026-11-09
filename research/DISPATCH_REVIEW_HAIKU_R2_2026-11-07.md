# Dispatch review round 2 (RD2, Haiku medium), 2026-11-07
Scope: research/UI_PARALLEL_DISPATCH_2026-11-07.md (rev 2 after lead fixes), ui/test_parity.py, ui/i18n_merge.py, docs/UI_REDESIGN_PLAN section 7 and 9.1. Read-only; one pytest run.

## Round-1 fixes checked
- Round-1 #1 PARITY_BUILT: FIXED. test_parity.py:25 reads it. `PARITY_BUILT=T2,T3 pytest ui/test_parity.py -q`: 213 passed, 10 skipped, 14 failed. All 14 failures are T3 rows (12 NEW-T3/T02/A03/I04/R01-R03 anchors, write_pack_claude, GET /api/writers). Expected until T3 is built.
- Round-1 #2 absolute path and log command in both prompts: FIXED.
- Round-1 #4 row ownership: PARTLY (see 2, 3, 4 below).
- Round-1 #8 i18n_merge docstring: FIXED (line 5).
- Round-1 #9 English report: FIXED in both prompts.
- Round-1 #3 banner/dialog: moved to T3/T4 in dispatch, but plan 3.4 still says T2 (see 5).
- Round-1 #6 retarget: NOT FIXED (see 6).

## Findings
1. HIGH | dispatch section 7, T3 prompt, group list | The T3 prompt lists "ok, scope, step, story, next, warn, plan, writer, gate, pics, sum, video, files, runs, ops, icon" and omits `banner`, which section 2 gives to T3. The T3 coder cannot add banner.* keys (helper refuses). Fix: add `banner` to the T3 prompt list and to the `--prefix` example; add a 2b line: banner moved from T2 (plan 3.4) to T3.
2. MEDIUM | dispatch section 5 | D03 (packet modal) is listed for both T3 and T4, so it is not owned exactly once. Fix: split into D03-wiz (T3) and D03-app (T4), or give D03 to T4 alone and mark it read-only for T3.
3. MEDIUM | dispatch section 5 | T01 (plan 9.1 Task column "T2/T3") is in no coder list. Fix: add T01 to T3 (its step-analysis anchor is the wizard stepper), or name T2 as its owner in the report.
4. MEDIUM | dispatch section 5 | Ten rows whose plan Task is T2 (H01, H07, H10, H11, H12, H13, D04, D05, E00, E01) are in no coder list, so the "every owned row ticked" rule never reaches them. Fix: one sentence in section 5: these are ticked in the T2 report and confirmed by the lead's PARITY run.
5. MEDIUM | dispatch section 2 vs plan 3.4 vs en.json | T2 groups differ from plan 3.4: banner 0 of 6 and dialog 0 of 16 (moved to T3/T4, no 2b line for plan 3.4); common 3 of ~30; lang 2 of 8; err 26 of ~45; app 13 of 12. Groups app, lang, common, status, err, risk belong to no coder, so a coder that needs common.close or err.* is refused, while 2b.4 says new keys in existing groups are allowed. Fix: 2b line stating T2 groups are closed and missing keys go under REQUESTS, or assign common/err to a coder.
6. MEDIUM | plan line 761 (round-1 #6, not fixed) | Retarget still reads `assert "Pick a shot file." in body or "'adv.video.err_pick_shot_file'" in body`, which passes if the key is unused. en.json has no adv.video.err_pick_shot_file yet; app.js:1178 and :1197 still hold the literal. Fix: plan and dispatch T4 to say `assert "'adv.video.err_pick_shot_file'" in body[:400]` and check en.json value == "Pick a shot file.".
7. MEDIUM | prompts sections 7 and 8 | The log line uses `<your id>`, but section 4 names coderT3(haiku,xhigh) and coderT4(haiku,xhigh). The TYPE list has no AGENT-START, which CLAUDE.md and blot.md require (start and finish lines, WHO with model and effort). Fix: write the literal id in each prompt and add AGENT-START.
8. LOW | plan lines 736, 762, 764 | Still say T4 removes the xfail marker and "run one after another". The LEAD NOTE at line 680 overrides section 7 generally, so this is a clarity fix. Fix: amend the three lines to point to dispatch 2b.
9. LOW | en.json line with key `_status` | The key has no dot, so it fails the helper's KEY_RE, and no UI file references it in the files grepped (i18n.js, pipeline.js, app.js). Fix: confirm whether it is a metadata key; if so, document it in 2b; otherwise remove it.

Checked and fine: row ids. test_parity INVENTORY+NEW_ROWS (115 non-NEW-T3 rows) equals plan 9.1 exactly, no duplicates, both ways. Unowned-by-coder ids are only the T2 rows in finding 4. Owner rules and no-Colab/no-Claude/no-commit wording present in both prompts. Both prompts give the absolute dispatch path. Writes outside the worktree are limited to PROJECT_LOG.md and en.json/mr.json (lock).

FINAL: 9 findings (1 HIGH, 6 MEDIUM, 2 LOW). Verdict: NEEDS FIXES. Fix 1 to 7 before sending T3 and T4. Items 8 and 9 can follow.
