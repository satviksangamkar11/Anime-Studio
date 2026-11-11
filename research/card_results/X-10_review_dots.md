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