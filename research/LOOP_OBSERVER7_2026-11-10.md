# Loop observer 7 report (2026-11-10, Haiku)

Scope: J3_caption_fields, J9a_script_hook, J12_plate_composite, J10_audio_edge (worktree D:/aai work/loop_run_reel2).
No module (non-test .py) or job json edited. No model, API or network call. No reel 1 file touched.

| job | REAL | NOISE | SPEC-GAP | tests added | pytest before -> after |
|---|---|---|---|---|---|
| J3_caption_fields | 2 test-level: ultra (exact "line 1: not a mapping"), codex (full problem list for non-str spoken) | none | none | 2 | 32 passed -> 34 passed |
| J9a_script_hook | 2 test-level: codex (multiword hi/mr stakes phrase), codex (reason + rewrite for H1-H6); 1 style: script_hook.py line 265 is 123 chars | none | none | 9 (3 functions + 6 parametrized H1-H6) | 19 passed -> 28 passed |
| J12_plate_composite | 3 test-level: codex 130 and ultra 108 / codex 177 (dtype and shape checks unreachable after early return, split into 2 tests); codex 19 (no connected-component test; the current labelling passes it) | none | none | 3 | 17 passed -> 20 passed |
| J10_audio_edge | 1 code: fade-in not idempotent (review_1_codex), confirmed by probe; 1 style: fade-out comment 130 chars (review_1_ultra) | ultra "comment missing": a one-line comment already exists, only its length is wrong | none | 1 (fails until fix) | 27 passed -> 27 passed + 1 failed (expected) |

Spec sections appended ("Review findings to fix (round 8, 2026-11-10; observer 7)"):
- specs/J10_audio_edge.md: fade-in condition `(pad_front > 0 or result[0] != 0.0)`, comment update, comment <= 120 chars. Verified on a scratch copy: 27 existing tests pass, probe becomes idempotent.
- specs/J9a_script_hook.md: wrap script_hook.py line 265 (no text change).

Notes:
- Frozen test lines over 120 characters in test_script_hook.py (16-19, 22, 23, 88, 99, 213, 214) and reported only, not edited.
- Reviewer "judge" entries for J3, J9a, J12 are failed CLI calls (wildcard in a command string); not used for triage.
- Git reports director/ and specs/ as untracked in this worktree; nothing was committed.
