`director/MASTER_PROMPT_v2.4.md`, section **(c2) BLOCKING SHEET** still shows `"schema": "blocking/1"` in its example, while the final checklist requires every blocking sheet to be `"blocking/1.1"`. The test validates only the separate c4 worked sheet, so this conflicting example slips through.

**Fix:** Change the c2 example’s schema value to `"blocking/1.1"`.

VERDICT: FIX-FIRST.