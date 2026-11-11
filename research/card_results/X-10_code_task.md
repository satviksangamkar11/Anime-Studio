Implement this gap card by editing ONLY the allowed module files; the test file director/test_keyframe_gate.py is frozen (do not touch it). Keep everything else byte-identical.

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

