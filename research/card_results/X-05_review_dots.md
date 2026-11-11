**REAL DEFECTS**

1. **`test_no_blocking_dir_unchanged` cannot fail (tautological).**  
   The test calls `convert_pack(...)` twice with identical arguments and asserts the two results are equal. Even if `blocking_dir=None` were ignored and the default behaviour silently changed, the two calls would still be identical and the assertion would pass. The test never compares against the pre-X-05 baseline.  
   *Fix:* store the pre-X-05 output (e.g. `EXPECTED_NO_BLOCKING`) and assert `res == EXPECTED_NO_BLOCKING`; remove the second `convert_pack` call or assert it against the same baseline.

2. **`test_empty_blocking_dir_reports_missing_sheet` is missing.**  
   The card lists four tests: `test_subjects_from_blocking`, `test_cast_mismatch_is_problem`, `test_cast_lock_equals_prompt_args`, `test_no_blocking_dir_unchanged`. The file adds a fifth (`test_invalid_sheet_file_is_problem`) but omits `test_empty_blocking_dir_reports_missing_sheet`, which is required by the card.

3. **`test_cast_lock_equals_prompt_args` hand-computed `visible` incorrectly.**  
   The test asserts `"visible": ["Sati", "Raj", "throne"]`, but the sheet's `props` list has `"class": "throne"` and the card’s own comment says “visible = cast names then prop classes”. The `visible` list should contain `"throne"` (the class), not `"throne"` as a bare string if the code expects class names — but more importantly, the test’s hand-computed expectation does not match the actual `blocking.prompt_args` output; the test will fail because the code produces `"visible": ["Sati", "Raj", "throne"]` only if the prop class is extracted correctly, but the test hard-codes the wrong shape. The test is wrong, not the code.

4. **`test_invalid_sheet_file_is_problem` is not in the card’s test list.**  
   The card specifies exactly four tests; this extra test is not required and may be a collision with another card.

**VERDICT: FIX-FIRST**