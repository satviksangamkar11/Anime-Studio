# Dispatch review round 3 (RD3, Haiku medium), 2026-11-07
Scope: research/UI_PARALLEL_DISPATCH_2026-11-07.md checked against docs/UI_REDESIGN_PLAN_2026-11-07.md (anime_studio_merge), ui/test_i18n.py, ui/test_parity.py, ui/i18n_merge.py, ui/test_r3_fixes.py. Read-only, no pytest run.

## Round-2 fixes
- R2 #1 banner in T3: FIXED (sec 2, 2b.7, T3 prompt). #2 D03: FIXED (sec 5, T4 alone). #3 T01: FIXED (sec 5). #4 T2 rows: FIXED (sec 5).
- R2 #5 closed groups: PARTLY (sec 5 says closed; 2b.4 contradicts, see 3).
- R2 #6 retarget: FIXED (plan line 761 and 2b.7 agree). #7 literal coder ids and AGENT-START: FIXED. #8: accepted via LEAD NOTE line 680.
- R2 #9: resolved, test_i18n skips keys starting with underscore, so _status is metadata.
- Row check: plan 9.1 has 115 rows. Dispatch: T2 10, T3 47 (incl. H02-H04, T01), T4 58 (incl. H05, H06, H08, ER, D03). Complete and disjoint.

## Findings
1. HIGH | prompts sec 7 and 8; plan 3.4 (line 250-251), B2 (line 661), B15, sec 5 literal maps | test_i18n test_2b (lines 115-120) fails any t( call whose first argument is not a quoted literal. The plan's pattern t(STATUS_KEY[s] || 'status.unknown') and B2's t(Q_KEY[res] || ...) both fail it (regex dry run confirmed). Fix before sending: either the prompts say every t() takes a literal and maps become one function per entry (if/return t('status.locked')), or the lead relaxes test_2b. Pick one and say it in both prompts.
2. HIGH | sec 2, sec 5 (dialog to T4 only) vs plan 2.4 steps 4-6, 5.3, 5.5 | T3 wizard needs dialog.yes_start, yes_approve, yes_claude, type_word, no_back. None exist in en.json and T3 may not add them. T4 may add the same keys with other wording (collision). Fix: move the dialog group to T3, or the lead pre-fills the 16 dialog keys from plan 3.4 before sending, as with step.*.
3. MEDIUM | 2b.4 vs sec 5 | 2b.4 allows new keys in any group that already has keys. Sec 5 closes app, lang, common, status, err, risk, and all of them have keys. A coder could add err.* via --prefix err. Fix: 2b.4 to read "new keys only in your own sec 2 groups; closed groups go under REQUESTS".
4. MEDIUM | T3 prompt (sec 7) vs plan T3 done-when line 744 | Done-when requires 5.9 item 1 (opsPanel into #expert-ops, #ops-colab-check), but the T3 explicit list is 5.1-5.8, 5.10. 5.9 items 2-4 have no owner. Fix: add "5.9 item 1" to the T3 list and name the owner of 5.9 items 2-4.
5. LOW | sec 5 | Six NEW-T3 anchors (writer-opt-or-super-vl, writer-claude-ack, confirm-typed, ops-colab-check, banner-recheck, plan-show-all; test_parity NEW_ROWS lines 73-78) appear only in plan line 750. Fix: one line in sec 5 saying T3 creates them as literals in pipeline.js and lists them under REQUESTS.
6. LOW | T4 prompt (sec 8) | test_r3_fixes asserts the single-quoted text 'adv.video.err_pick_shot_file' inside js[start:start+400] from "function h3Run()". Fix: say "use single quotes and keep the call within 400 characters of function h3Run()".
7. LOW | sec 3 | "wait 2 minutes" cannot run as foreground sleep in the Bash tool. Fix: "re-run later or use Monitor".
8. LOW | sec 2b | Numbering runs 1,2,3,4,5,7,6. Cosmetic.

FINAL: 8 findings (2 HIGH, 2 MEDIUM, 4 LOW). Verdict: NEEDS FIXES. Fix 1 to 4 before sending T3 and T4. Items 5 to 8 can follow.
