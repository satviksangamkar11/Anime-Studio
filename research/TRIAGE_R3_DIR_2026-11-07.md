# Triage R3 director (batches r1_director, r2_registry_retry) - 2026-11-07

Sources: research/ROUND3_REVIEW_SUPERVL_2026-11-07.md, research/ROUND3_REVIEW_DOTS_2026-11-07.md. Baseline before work: director 634 passed. After: 647 passed (634 + 13 new regression tests).

| id | file:line | verdict | evidence (one line) | action |
|---|---|---|---|---|
| S-R1 (supervl r1) | director/pack_validator.py:475-478 | FALSE | Probe: narration_by_lang-only row raises ML-03 for dialogue_by_lang and captions_by_lang. This is the documented rule: HANDOFF W1 "all selected languages must be present in ... all three keys", and pack_validator.py:364 comment; owner-era decision logged as skipped by design (PROJECT_LOG 02:14). | none; see OPEN_QUESTIONS Q1 |
| S-R2 = D-R1 (supervl r1 #2, dots r1 #1) | director/write_pack.py:913 (episodes_from called in run_staged) | REAL | Probe: episodes_from on a story block with episodes [{"title":"Intro"}] raises ValueError; run_staged did not catch it and main() catches only StageFailed, so the CLI prints a traceback. | FIXED: try/except ValueError -> StageFailed("stage 1 answer is unusable ... delete stage_1_raw.json"). Test: test_r3_write_pack.py |
| D-R2 (dots r1 #2) | director/pack_validator.py:489-504 | REAL (low) | Probe: narration_by_lang.hi with language "en" gives no ML-* error; the validator never compares the block language with its key. | FIXED: ML-01 on narration_by_lang.<key>.language when label is not None and not the key. Test: test_r3_pack_validator.py |
| D-R3 (dots r1 #3) | director/write_pack.py:955 (run_single parse) | REAL (low) | Probe: wp.parse on text with no shots block raises ValueError; run_single had no catch, main() catches only StageFailed, so traceback on a bad saved raw_response.json. | FIXED: parse wrapped -> StageFailed("the saved answer is unusable ... delete raw_response.json"). Test: test_r3_write_pack.py |
| D-R4 (dots r1 unverified) | director/write_pack.py:176 -> director/retry_policy.py:198-209 | FALSE | Probe: is_free_model returns False for missing pricing, empty pricing dict, and a None price value; True only when every price is numeric 0. Model not in catalog also False. | none |
| D-R5 (dots r1 unverified list, ~16 files not supplied) | repo-wide | UNVERIFIED | Not in director/ batches; out of scope for this triage. | none |
| D-R6 (dots r2 #1) | director/run_registry.py:255-258 detect_language | REAL (medium) but deferred | Probe: detect_language("नमस्ते") returns "en" (20-char threshold). HANDOFF W1 records "Skipped by decision: detect_language threshold". Changing it changes language labels for all short Hindi text in every caller. | NOT changed (prior owner-era decision). See OPEN_QUESTIONS Q2 |
| D-R7 (dots r2 #2) | director/run_registry.py:366-371 _checked | REAL (low) | Probe: append_event(..., voice_engine={}) was accepted and written. The check `all(...)` is vacuously true for {}. | FIXED: require a non-empty engines dict. Test: test_r3_run_registry.py |
| D-R8 (dots r2 #3) | director/run_registry.py:140 pack_summary | FALSE | Probe: {"seconds": "3.5"} is ignored (seconds 2.0 from a numeric 2). Contract is numeric: director/shot_schema.py:31-34 "seconds must be a positive number", so a string is an invalid row, not a valid under-report. | none |
| D-R9 (dots r2 #4) | director/retry_policy.py:144-150 CircuitBreaker.allow | FALSE (latent) | No threading in director/ (grep); ui/ does not import retry_policy (grep). Breaker is only reached from one thread today. | none; note for when a thread pool is added |
| D-R10 (dots r2 #5 / retry) | director/retry_policy.py:162-195 call_with_retry | REAL (low) | Probe: Policy(max_attempts=0) reaches `raise AssertionError("unreachable")`, no call made. | FIXED: ValueError up front for max_attempts < 1. Test: test_r3_retry_policy.py |
| D-R11 (dots r2 #6) | director/simple_language.py:47 _SENT_SPLIT | REAL (low) | Probe: "...should be split in two parts ... now.” Next." (two 15-word sentences) gave SEN-01; plain-quote control did not. | FIXED: look-behind also accepts closing quote/bracket after the stop. Test: test_r3_simple_language.py |
| D-R12 (dots r2 #7) | director/simple_language.py:440-453 check_shot_texts | REAL (low) | Probe: non-strict caption language "xyz" gave no LANG-02, with or without a captions_by_lang block; strict key "xyz" already flagged. Dots' stated inconsistency is only half right (the no-block case is also unflagged) but the gap is real. | FIXED: unknown non-strict language hint flagged LANG-02 before the block skip. Tests: test_r3_simple_language.py |
| S-R3 (supervl r2, all three files) | run_registry.py, retry_policy.py, simple_language.py | no findings | Supervl reported none for this batch. Not re-checked beyond the dots items above. | none |

## REQUESTS
None. All fixes are inside director/. No change needed outside director/.

## OPEN_QUESTIONS
- Q1 (S-R1 / ARCH_REVIEW_DOTS): a multilingual story with a shot that has legitimately no narration, dialogue or captions. Current rule (all three *_by_lang keys required, every selected language) rejects it, and single-language rows allow narration null. Owner call: keep all-keys rule, or allow an empty block per shot.
- Q2 (D-R6): detect_language treats "नमस्ते" (5 Devanagari letters) as en because of the 20-letter threshold. Earlier decision skipped it. Owner call whether to change it now (affects all callers of detect_language).
- Q3 (dots r1 unverified): whether the ~16 files not supplied in the review have their round-2 fixes intact. Not checked here.

## Test results
- before: director 634 passed
- after: director 647 passed (includes 13 new: test_r3_write_pack.py 2, test_r3_pack_validator.py 2, test_r3_run_registry.py 2, test_r3_retry_policy.py 1, test_r3_simple_language.py 6)
- Before-fix behaviour was observed by probe for each fixed item; the new tests were not separately run against the unfixed code.

## Re-review (RULE 5)
Not run here. A second review of the fixed files (Super VL + Dots) is still required by blot.md RULE 5.
