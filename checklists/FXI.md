# Checklist FXI (rule 55) - fix wave, spec: loop_run_reel2/specs/FXI_gate_tests.md

Coder = Nemotron Super (loop). Reviewer = Haiku medium: verify each row independently from the files and a real test run; PASS or FAIL with evidence; then add the human pass.

| Row | Requirement | Reviewer (PASS/FAIL + evidence) |
|---|---|---|
| 1 | Requirement 1: test_background_lock_nonfinite_ssim_fails: use monkeypatch to make the function that background_lock really calls to get the ssim (find it by reading the code; probably image_gates.block_ssim) return float("nan"); two equal small uint8 images and a full mask; background_lock(...) must report a failure (check the exact return sha |  |
| 2 | Requirement 2: test_background_lock_equal_images_pass (sanity): identical 64x64 uint8 images with a full-True mask pass. |  |
| 3 | Requirement 3: test_hole_fraction_rejects_lists: plate_composite.hole_fraction([[1]], np.zeros((2, 2), bool)) raises CompositeError; the same for the second argument. |  |
| 4 | Requirement 4: test_hole_fraction_shape_mismatch_raises: masks of different shapes raise CompositeError. |  |
| 5 | Test exists, is run and passes: test_background_lock_nonfinite_ssim_fails |  |
| 6 | Test exists, is run and passes: test_background_lock_equal_images_pass |  |
| 7 | Test exists, is run and passes: test_hole_fraction_rejects_lists |  |
| 8 | Test exists, is run and passes: test_hole_fraction_shape_mismatch_raises |  |
| 9 | Only the files named in the spec were changed by this job (module + its new/edited test file); the frozen existing test files are untouched except the ones the spec says to update. |  |
| 10 | All tests of the changed module pass in anime_studio_merge (existing + new): run the module's old test file AND the new test file and paste the counts. |  |
| 11 | Every changed .py parses (ast.parse) and has no line over 120 characters. |  |
| 12 | No network, Colab, ElevenLabs, renderer or paid call; no reel 1 file touched. |  |
| 13 | The fix does not weaken an existing check (read the diff against the backup in the scratchpad backup_before_fixwave when the file existed before). |  |

## Human pass
- Missing:
- Extra:
- Bad:
