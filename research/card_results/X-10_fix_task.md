Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything else byte-identical; do not add code that reads files at import time.

CARD:
**X-10 | keyframe_gate.py (keyframe_review.json + image_gates + plate_composite → keyframe_gate.json)**
- **Files:** `director/keyframe_gate.py` NEW; `director/test_keyframe_gate.py` NEW.
- **Change:**
  - `validate_review(review, sheet)`: keyframe_review.json is written by the full-size reviewer, human or agent. Shape: `{shot_id, full_size: true, reviewer, A: {cast_count, chars: {id: {arms, posture: standing|seated|unknown}}, extra_figures: [], marks_or_letters: bool}, B: {...}}`. `full_size` must be true (rule 25 / problem 22).
  - `gate(plate, img_a, img_b, sheet, review, lock)`:
    - masks: `ma = plate_composite.diff_mask(plate, A)`, `mb = diff_mask(plate, B)` (plate_composite.py:154). The empty plate makes character masks free.
    - `image_gates.background_lock(A, B, ma, mb)`, plus `area_fraction >= MIN_AREA = 0.25` (D-IMG).
    - `plate_composite.plan(A, B, ma, mb)`. On `use == "composite"`, write `B_final = composite(A, B, mb, feather_px=4)`; otherwise B_final = B.
    - `cast_parity(review.A.cast_count, review.B.cast_count, expect.required_cast_count, expect.entry_exit_allowed)`.
    - `limb_parity` per char against `expect.arms`.
    - `posture_matches` per char against `expect.posture`.
    - `feasible_motion(displacement, seconds, MAX_SPEED_H)` with seconds from the lock.
    - `extra_figures` non-empty or `marks_or_letters` → fail.
  - Writes `<flow_root>/keyframe_gate/<SHOT>.json {sha256 of plate, A, B, B_final, sheet, review, lock.input_sha256; checks; pass}`.
- **Tests (synthetic 64×64):**
  - `test_shift_2px_composites`: square 10×10, diff_mask dilate 6 → 22×22; holes 2×22 = 44/4096 = **0.0107 ≤ 0.02**.
  - `test_shift_20px_keeps_b`: 440/4096 = **0.107**.
  - `test_background_moved_fails` (np.roll of background by 3 px).
  - `test_missing_sage_fails` (review A cast 2, required 3).
  - `test_seated_vs_standing_fails`.
  - `test_not_full_size_refused`.
  - `test_record_hashes_change_with_B`.
- **Closes:** 20, 21, 22 (enforced), 25 (gate runs at approval with real frames). Bug: 8A/8B pose mismatch, shots 7/9 missing cast.
- **Depends on:** X-03, D-IMG, D-LOCK.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_keyframe_gate.py -q`
- **OWNER DECISION (problem 21):** manual keyframe_review.json counts (default) or a detector.
- **Second-attempt risk:** med.



REVIEW BY LUNA:
- [keyframe_gate.py](D:/aai%20work/anime_studio_merge/director/keyframe_gate.py:38): `if not review.get("full_size"):` accepts truthy non-booleans such as `"yes"` or `1`, although the card requires `full_size: true`. Require `review.get("full_size") is True`.

- [keyframe_gate.py](D:/aai%20work/anime_studio_merge/director/keyframe_gate.py:107): `if cast_a != cast_b:` can accept invalid counts when both sides contain the same string, for example `"3"`, and the required count is also `"3"`. Validate that each review `cast_count` is a non-negative integer (excluding booleans) and that the required count has the same valid type before parity checks.

- [keyframe_gate.py](D:/aai%20work/anime_studio_merge/director/keyframe_gate.py:166): `checks["area_ok"]` uses `1 - mb.sum()/mb.size`, which measures the area outside B’s character mask. The card requires the D-IMG area gate; `background_lock` already returns the comparable background `area_fraction`, excluding both frames’ masks. Set this check from `bg_result["area_fraction"] >= MIN_AREA`. The current check can pass when the comparable background area is below the required minimum.

- [keyframe_gate.py](D:/aai%20work/anime_studio_merge/director/keyframe_gate.py:224): `float(seconds)` crashes when the lock has `seconds=None`; `feasible_motion` explicitly accepts `None`, so that accepted input reaches the crash. Record `seconds` without an unconditional float conversion, or reject invalid lock seconds before this point and write a failing gate record.

VERDICT: FIX-FIRST.

REVIEW BY DOTS:
**REAL DEFECTS FOUND:**

1. **Test `test_shift_2px_composites` cannot fail on `area_fraction` (tautological).**  
   The card requires `area_fraction >= MIN_AREA = 0.25` (D-IMG). The test hard-codes `assert checks["area_fraction"] == pytest.approx(0.970458984375)`. This is an exact equality check on a pre-computed constant; if `area_fraction` were computed differently or the mask changed, the assertion would fail, but it does not test the *threshold logic*. More critically, the card's requirement is a *gate*: `area_ok` must be `True` when `area_fraction >= 0.25`. The test never asserts `checks["area_ok"] is True`. If the implementation regressed and set `area_ok = False` unconditionally, the test would still pass because it only checks the raw float. This is a weak/tautological test: it verifies a constant, not the requirement.

   **Fix:** Add `assert checks["area_ok"] is True` to `test_shift_2px_composites`.

2. **Test `test_shift_20px_keeps_b` asserts `plan_use == "keep_b"` but the implementation returns `"keep"`.**  
   In `keyframe_gate.py:167`, the code does:
   ```python
   use = _get(plan_result, "use", "keep")
   checks["plan_use"] = str(use)
   ```
   If `plan_result["use"]` is `"keep_b"` (as implied by the test comment "keep B"), the record will contain `"keep_b"`. But the fallback default is `"keep"`, and the card says "otherwise B_final = B". The test expects `"keep_b"`, but the code has no logic to produce `"keep_b"`; it just passes through whatever `plan()` returns. This is a silent mismatch: the test will fail if `plan()` returns `"keep"`, but the test author assumed `"keep_b"`. The test is brittle and does not cover the actual requirement (that `B_final` is unchanged).

   **Fix:** Either change the test to `assert checks["plan_use"] in ("keep", "keep_b")` or ensure `plan()` returns `"keep_b"` consistently. The card does not specify the exact string, so the test should not hard-code it.

3. **Test `test_background_moved_fails` uses `_moved(bg)` which adds 6 to every pixel, but the plate is a gradient. This may not trigger `background_lock` failure reliably.**  
   The test rolls the background by 3 px (via `np.roll`), but `_moved` adds a constant offset. The card requires `background_lock` to fail when the background moves. The test's `_moved` function does not simulate a *spatial shift*; it simulates a brightness change. `background_lock` may or may not detect this as a background movement. The test is not guaranteed to cover the requirement (background movement detection). It is a weak test because it relies on a specific implementation detail of `background_lock` rather than the card's requirement.

   **Fix:** Use `np.roll` to shift the background spatially, as the test name suggests: `b = _with_square(np.roll(plate, 3, axis=1), 22)`.

4. **Test `test_missing_approval_fails` tests `reviewer=""` but the card does not require a non-empty reviewer.**  
   The card says `reviewer` must be present (`review.get("reviewer")`), but `validate_review` only checks `if not review.get("reviewer")`. An empty string is falsy, so it fails. However, the card does not specify that `reviewer` must be non-empty; it only requires the key to exist. The test is testing an implementation detail (empty string rejection) that is not a card requirement. This is a test that cannot fail in a meaningful way: if the implementation accepted empty strings, the test would fail, but the card does not forbid it.

   **Fix:** Remove `test_missing_approval_fails` or change it to test `reviewer=None` (which is not a string) to cover the "must be present" requirement.

5. **Test `test_record_hashes_change_with_B` does not verify that `B_final` changes when `B` changes (if composite).**  
   The test checks that `B` hash changes, but the card requires `B_final` to be written. If `plan_use == "composite"`, `B_final` should differ from `B`. The test does not assert `first["B_final"] != second["B_final"]`. This is a missing coverage: the card says "write `B_final = composite(...)`", but the test does not verify that the composite is actually computed and stored.

   **Fix:** Add `assert first["B_final"] != second["B_final"]` (only if the first run was composite; the test uses `b_left=22` which is composite).

---

**VERDICT: FIX-FIRST**