# Loop observer 9 (round 10, 2026-11-10): J11, J12, J13, J14

Scope: findings from _loop/<job>/review_*_codex.md, review_*_ultra.md, review_*_judge.md and J14 TEST_FINDINGS.md, triaged against the current director/ modules and tests. Modules and job JSONs were not edited. No model, API or network calls. No reel 1 files touched.

| job | REAL | NOISE | SPEC-GAP | tests added | pytest before -> after |
|---|---|---|---|---|---|
| J11 image_gates | none | codex r0 (NaN/inf in feasible_motion: already raises GateError); codex r1 (int dtypes other than uint8: already rejected); judge failed (tool error, all rounds); ultra No defects | none | 4 functions: feasible_motion NaN displacement, feasible_motion inf inputs, dilate(-1), to_float01 int16/int32 | 38 pass -> 42 pass |
| J12 plate_composite | none (code) | codex r0 (composite non-uint8: already raises CompositeError); codex r1 (2-D shape: already raises; test gap only); ultra LOW (unreachable second block in test_save_rgb_refuses_bad_array, not removed: frozen test, covered by observer 7 tests) | none | 2 functions: composite float images, composite/diff_mask 2-D images. Added `import pytest` to the test file | 20 pass -> 22 pass |
| J13 clip_gates | end_frame_pass: NaN passes the gate (spec item 1, code) | codex r0 (int luma / non-bool mask: numerically harmless, spec gives types but no rejection rule); codex r1 (zero-count class: already handled, test added); judge failed; ultra No defects | tail_spike, scene_cut, flicker_score: NaN silently passes (spec items 2-4) | 5 functions: zero-count class, end_frame NaN, tail NaN, scene_cut NaN, flicker NaN | 55 pass -> 56 pass, 4 expected fail (items 1-4 pending) |
| J14 shot_router | route_shot returns lists shared with _ROUTE_TABLE (spec item 1, observer-found, confirmed) | none | none | TEST_FINDINGS codex: non-dict features (3 cases); alias test (1) | 42 pass -> 45 pass, 1 expected fail (alias, pending item 1) |

Spec sections appended (append-only):
- specs/J13_clip_gates.md: "## Review findings to fix (round 10, 2026-11-10; observer 9)", items 1-4 with exact lines and corrected logic.
- specs/J14_shot_router.md: same heading, item 1 (copy.deepcopy in route_shot), item 2 (tests).
- J11 and J12: no spec append (no REAL code or SPEC-GAP findings).

Infrastructure note: the judge reviewer failed in every round for all four jobs (the claude CLI call broke on a PowerShell command string). Its verdicts are not evidence.
