# Checklist FXD (rule 55) - fix wave, spec: loop_run_reel2/specs/FXD_runner_safety_checks.md

Coder = Nemotron Super (loop). Reviewer = Haiku medium: verify each row independently from the files and a real test run; PASS or FAIL with evidence; then add the human pass.

| Row | Requirement | Reviewer (PASS/FAIL + evidence) |
|---|---|---|
| 1 | Requirement 1: preflight(): script_path is currently only stat-ed (os.path.getsize, around line 197). It must also be a regular FILE: if not os.path.isfile(script_path) add the failure "script check failed: not a file: <path>" (a missing path keeps its existing "cannot stat" failure). Keep the existing parts rule (each upload part at most max_ |  |
| 2 | Requirement 2: can_stop / stop_decision already raise ValueError when an expected id is absent from expected_frames (line about 85). Do not change that behaviour; it only needs tests. |  |
| 3 | Test exists, is run and passes, and asserts what its name says: test_can_stop_missing_id_in_expected_frames_raises |  |
| 4 | Test exists, is run and passes, and asserts what its name says: test_stop_decision_missing_id_raises |  |
| 5 | Test exists, is run and passes, and asserts what its name says: test_preflight_script_path_directory_fails |  |
| 6 | Test exists, is run and passes, and asserts what its name says: test_preflight_script_path_file_ok |  |
| 7 | Test exists, is run and passes, and asserts what its name says: test_preflight_missing_script_path_still_cannot_stat |  |
| 8 | Only the files named in the spec were changed by this job (module + its new/edited test file); the frozen existing test files are untouched except the ones the spec says to update. |  |
| 9 | All tests of the changed module pass in anime_studio_merge (existing + new): run the module's old test file AND the new test file and paste the counts. |  |
| 10 | Every changed .py parses (ast.parse) and has no line over 120 characters. |  |
| 11 | No network, Colab, ElevenLabs, renderer or paid call; no reel 1 file touched. |  |
| 12 | The fix does not weaken an existing check (read the diff against the backup in the scratchpad backup_before_fixwave when the file existed before). |  |

## Human pass
- Missing:
- Extra:
- Bad:
