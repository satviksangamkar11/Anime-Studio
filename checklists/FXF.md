# Checklist FXF (rule 55) - fix wave, spec: loop_run_reel2/specs/FXF_waivers_strict.md

Coder = Nemotron Super (loop). Reviewer = Haiku medium: verify each row independently from the files and a real test run; PASS or FAIL with evidence; then add the human pass.

| Row | Requirement | Reviewer (PASS/FAIL + evidence) |
|---|---|---|
| 1 | Requirement 1: "reel" must be an int and not a bool (True is refused) before the comparison with the reel being built. |  |
| 2 | Requirement 2: "owner", "reason" and each entry of "codes" must be strings ("reason" may be empty; "owner" and every code must be non-empty); "codes" must be a list. |  |
| 3 | Requirement 3: "date" must be a string in the form YYYY-MM-DD and a real calendar date (datetime.date.fromisoformat after a four-two-two digit regex check). Otherwise ValueError with a message naming the key. |  |
| 4 | Requirement 4: Unknown keys and missing keys keep raising ValueError (name the key). |  |
| 5 | Test exists, is run and passes, and asserts what its name says: test_bool_reel_refused |  |
| 6 | Test exists, is run and passes, and asserts what its name says: test_string_reel_refused |  |
| 7 | Test exists, is run and passes, and asserts what its name says: test_empty_owner_refused |  |
| 8 | Test exists, is run and passes, and asserts what its name says: test_non_string_code_refused |  |
| 9 | Test exists, is run and passes, and asserts what its name says: test_codes_not_a_list_refused |  |
| 10 | Test exists, is run and passes, and asserts what its name says: test_date_wrong_format_refused |  |
| 11 | Test exists, is run and passes, and asserts what its name says: test_date_not_real_refused |  |
| 12 | Test exists, is run and passes, and asserts what its name says: test_unknown_key_refused |  |
| 13 | Test exists, is run and passes, and asserts what its name says: test_missing_key_refused |  |
| 14 | Test exists, is run and passes, and asserts what its name says: test_empty_reason_allowed |  |
| 15 | Only the files named in the spec were changed by this job (module + its new/edited test file); the frozen existing test files are untouched except the ones the spec says to update. |  |
| 16 | All tests of the changed module pass in anime_studio_merge (existing + new): run the module's old test file AND the new test file and paste the counts. |  |
| 17 | Every changed .py parses (ast.parse) and has no line over 120 characters. |  |
| 18 | No network, Colab, ElevenLabs, renderer or paid call; no reel 1 file touched. |  |
| 19 | The fix does not weaken an existing check (read the diff against the backup in the scratchpad backup_before_fixwave when the file existed before). |  |

## Human pass
- Missing:
- Extra:
- Bad:
