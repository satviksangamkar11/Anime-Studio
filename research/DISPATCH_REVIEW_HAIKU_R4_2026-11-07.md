# Dispatch review round 4 (RD4, Haiku medium), 2026-11-07
Scope: research/UI_PARALLEL_DISPATCH_2026-11-07.md after round-3 fixes; checked against docs/UI_REDESIGN_PLAN_2026-11-07.md and ui/test_parity.py, ui/test_r3_fixes.py, ui/test_i18n.py, ui/i18n_merge.py (anime_studio_merge). Read-only.

## Round-3 fixes
- R3 #1 (t() literal, 2b.8): FIXED. #2 (dialog to T3, sec 2 and 2b.7): FIXED in sec 2, but see N1. #3 (2b.4 closed groups): FIXED. #4 (5.9 item 1 to T3): PARTLY, see N2. #5 (NEW-T3 anchors, 2b.9): FIXED (six anchors match test_parity lines 73-78). #6 (retarget, 2b.7/2b.9): FIXED (test_r3_fixes line 119-120 uses body = js[start:start+400]). #7 (no foreground sleep): FIXED. #8 (numbering): still open, cosmetic, not counted.

## Row check (all verified by script)
- Plan 9.1 has 115 rows (127 table lines minus 12 headers), no duplicate ids.
- Dispatch: T2 10, T3 47, T4 58 = 115. Disjoint and complete (no missing, no extra).
- Owners match plan column Task for every single-owner row; multi-owner rows resolved as intended (H02-H04, T01 to T3; H05, H06, H08, ER to T4; D03 to T4 alone).

## NEW findings
N1. MEDIUM | dispatch sec 1 item 2 (line 9) | still says "dialog ... added by T4 (dialog)". Sec 2 and 2b.7 say T3. 2b.7 also states "dialog from T2 to T4" before correcting itself. Fix: line 9 to "T3 (banner and dialog)"; reword 2b.7 to one sentence.
N2. MEDIUM | T3 prompt sec 7 (line 49) | explicit list is "5.1-5.8, 5.10". Plan T3 done-when (plan line 744) requires 5.9 item 1 (#expert-ops, #ops-colab-check). Only 2b.9 covers it by reference. Fix: add "5.9 item 1" to line 49.
N3. MEDIUM | B7 (plan line 666: renderBanner in pipeline.js, index.html dead #stale-banner removal) | in no prompt. T3 prompt lists B1, B10, B11, B14 only; plan T3 done-when omits B7 too. Banner-recheck anchor (NEW-T3) depends on it. Fix: add "B7 (pipeline.js half)" to T3 prompt; lead confirms index.html half is T2 and done.
N4. MEDIUM | 5.9 items 2-4 (msg-bar, nav, log footer, adv.intro) | 2b.9 says "T4's (app.js) or static index.html (T2, done)": an either/or. T4 prompt (line 54-55) and plan T4 done-when (plan 754-766) do not list 5.9 at all. Fix: T4 prompt names the owner per item, and the lead states which items are already in index.html.
N5. LOW | dialog keys in plan 3.4 (plan line 261: "show exact command, preview expires, preview expired") vs T4 modal/expiry strings (plan T4 done-when, adv.modal.*). Unclear which group holds the expiry lines. Fix: one line in 2b.7 saying T4 uses adv.modal.* for its modal and expiry text.
N6. LOW | stale plan text still contradicts overrides: plan line 261 (Dialog owner T2), line 723 (T2 owns banner and dialog), line 250-251 and B2 line 661 (t(STATUS_KEY[s]...), t(Q_KEY[res]...)). Coders are told 2b wins; no action needed beyond keeping 2b explicit.

## Verdict
FINAL: 6 new findings (0 HIGH, 4 MEDIUM, 2 LOW). Verdict: NEEDS FIXES. Fix N1 to N4 before sending T3 and T4 (prompt text and one leftover line only; no structural change). N5 and N6 can follow.
