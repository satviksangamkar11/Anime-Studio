# Checklist FXA (rule 55) - fix wave, spec: loop_run_reel2/specs/FXA_shot_mode.md

Coder = Nemotron Super (loop). Reviewer = Haiku medium: verify each row independently from the files and a real test run; PASS or FAIL with evidence; then add the human pass.

| Row | Requirement | Reviewer (PASS/FAIL + evidence) |
|---|---|---|
| 1 | Requirement 1: frame_row(): for a route-KFI shot, after the existing validation of "mid" and "mid_frame" (lines about 111-118 of h3/shot_mode.py), COPY them into the returned row: row["mid"] = shot["mid"] and row["mid_frame"] = mid_frame (the validated int). For every other route the keys "mid" and "mid_frame" must NOT appear in the row. |  |
| 2 | Requirement 2: check_pixel_frames(): replace ONLY the block that starts with `if remainder % 17 != 0:` (lines about 45-54) by exactly this logic (the later range check stays as it is): |  |
| 3 | Test exists, is run and passes, and asserts what its name says: test_kfi_row_carries_mid_and_mid_frame |  |
| 4 | Test exists, is run and passes, and asserts what its name says: test_non_kfi_row_has_no_mid_keys |  |
| 5 | Test exists, is run and passes, and asserts what its name says: test_message_below_minimum_names_107_only |  |
| 6 | Test exists, is run and passes, and asserts what its name says: test_message_above_maximum_names_345_only |  |
| 7 | Test exists, is run and passes, and asserts what its name says: test_message_between_names_both |  |
| 8 | Only the files named in the spec were changed by this job (module + its new/edited test file); the frozen existing test files are untouched except the ones the spec says to update. |  |
| 9 | All tests of the changed module pass in anime_studio_merge (existing + new): run the module's old test file AND the new test file and paste the counts. |  |
| 10 | Every changed .py parses (ast.parse) and has no line over 120 characters. |  |
| 11 | No network, Colab, ElevenLabs, renderer or paid call; no reel 1 file touched. |  |
| 12 | The fix does not weaken an existing check (read the diff against the backup in the scratchpad backup_before_fixwave when the file existed before). |  |

## Human pass
- Missing:
- Extra:
- Bad:
