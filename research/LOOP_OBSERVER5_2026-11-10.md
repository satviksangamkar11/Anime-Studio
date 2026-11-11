# Loop observer 5 report, 2026-11-10 (Haiku, fifth pass)

Scope: J1a, J3, J4, J6, J9a, J9b, J10 in `D:/aai work/loop_run_reel2`. No module (non-test .py) edited, no job json or existing spec text edited, no model/API/network call, no reel 1 file touched. Spec changes are appended sections only ("## Review findings to fix (round 2, 2026-11-10; observer 5)", or the J3 escalation note).

| job | findings read | REAL | NOISE | SPEC-GAP | tests added / corrected | pytest before -> after |
|---|---|---|---|---|---|---|
| J1a_timeline_lock_core | codex r1 (MED, LOW), ultra r1 (READY), judge r1, codex/ultra r0, TEST_FINDINGS | 1 code (huge int raises OverflowError, not ValueError; spec item 1 added), 1 test gap | 0 | 0 | added `test_edit_frames_huge_int_seconds_refused` (10**1000). Fails until module fix (intended) | 39 pass -> 39 pass + 1 fail |
| J3_caption_fields | ESCALATE.md, SONNET_DIAGNOSIS.md (weekly limit, no diagnosis), attempt/ module, original/ | 2 (non-str spoken gives "missing" not "not text" in attempt; original lacks fifth/sixth-run hardening) | 0 | 1 (labels by id vs `<index>`; frozen tests use id) | none (frozen tests contradict sixth-run `<index>` rule; owner decides) | 27 pass, 5 fail -> 27 pass, 5 fail |
| J4_prompt_hygiene | codex r0/r1, ultra r0/r1, TEST_FINDINGS | 1 test gap (plural verb, codex LOW) | 3 (case-insensitive "and"/glue already fixed; rename target test absent) | 0 | 2 mouth_sentence plural tests | 34 pass -> 36 pass |
| J6_runner_safety | codex r0/r1, ultra r0/r1, judge r1 | 1 style (line 157 is 138 chars; spec says max 120) | 6 (ultra r1 injected-mode; r0 scan, symlink, string ids, traversal already done) | 0 | none | 35 pass -> 35 pass |
| J9a_script_hook | codex r0/r1, ultra r0/r1, TEST_FINDINGS | 4: multi-word stakes entries dead (code); 8 lines over 120 chars (style); 2 test gaps (missing-key message, constants) | 4 (hi/mr count is 8; H2/H3/H4 with no lines already guarded) | 1 (H6 English noun list, still open, owner to confirm) | 2 (missing-key message, word lists) | 17 pass -> 19 pass |
| J9b_script_pacing | codex r0/r1, ultra r0/r1, judge r1, TEST_FINDINGS | 1 test gap (later-shot within-shot gap) | 3 (negative event time already rejected; P1 already all shots) | 0 | 1 (later-shot dead air) | 22 pass -> 23 pass |
| J10_audio_edge | codex r0/r1, ultra r0/r1, judge r1, TEST_FINDINGS | 2 test-level (fade not tested; 1e-6 tolerance at line 77 contradicted 1e-3 clarification) | 2 (os/array imports already removed; sys import needed for bare-name import) | 1 (fade-out skipped on exact-0.0 end vs idempotence; owner picks option a/b) | 1 added (fade values); 1 corrected (line 77 1e-6 -> 1e-3, listed) | 26 pass -> 27 pass |

## Notes
- J1a: the fifth-run "bar error_ms" hard example is already implemented in the module and passes.
- J3: `SONNET_DIAGNOSIS.md` is empty because the weekly limit was hit (resets Nov 12). The escalated attempt fails 4 tests; the restored original fails 5. The SPEC-GAP note in specs/J3_caption_fields.md lays out the recommended id-based labelling for owner confirmation.
- J10 fade-out: the codex MED is real in effect, but fixing it conflicts with the idempotence test. Owner choice (a) keep plus ponytail comment, or (b) always fade and change the idempotence test.
- Frozen-test corrections (listed as required): `director/test_audio_edge.py` line 77, `1e-6` changed to `1e-3` (second-run clarification on 16-bit round trips). No other frozen test was changed.
- Full pytest after observer 5: timeline_lock_core 39 pass/1 fail (intended), caption_fields 27/5 (unchanged module), prompt_hygiene 36/0, runner_safety 35/0, script_hook 19/0, script_pacing 23/0, audio_edge 27/0.
