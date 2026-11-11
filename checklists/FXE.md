# Checklist FXE (rule 55) - fix wave, spec: loop_run_reel2/specs/FXE_clip_gates_dates.md

Coder = Nemotron Super (loop). Reviewer = Haiku medium: verify each row independently from the files and a real test run; PASS or FAIL with evidence; then add the human pass.

| Row | Requirement | Reviewer (PASS/FAIL + evidence) |
|---|---|---|
| 1 | Test exists, is run and passes, and asserts what its name says: test_valid_date_accepted |  |
| 2 | Test exists, is run and passes, and asserts what its name says: test_month_13_refused |  |
| 3 | Test exists, is run and passes, and asserts what its name says: test_feb_30_refused |  |
| 4 | Test exists, is run and passes, and asserts what its name says: test_day_first_format_refused |  |
| 5 | Test exists, is run and passes, and asserts what its name says: test_unpadded_refused |  |
| 6 | Test exists, is run and passes, and asserts what its name says: test_int_date_refused |  |
| 7 | Only the files named in the spec were changed by this job (module + its new/edited test file); the frozen existing test files are untouched except the ones the spec says to update. |  |
| 8 | All tests of the changed module pass in anime_studio_merge (existing + new): run the module's old test file AND the new test file and paste the counts. |  |
| 9 | Every changed .py parses (ast.parse) and has no line over 120 characters. |  |
| 10 | No network, Colab, ElevenLabs, renderer or paid call; no reel 1 file touched. |  |
| 11 | The fix does not weaken an existing check (read the diff against the backup in the scratchpad backup_before_fixwave when the file existed before). |  |

## Human pass
- Missing:
- Extra:
- Bad:
