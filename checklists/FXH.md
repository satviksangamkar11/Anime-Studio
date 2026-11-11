# Checklist FXH (rule 55) - fix wave, spec: loop_run_reel2/specs/FXH_script_hook_stakes.md

Coder = Nemotron Super (loop). Reviewer = Haiku medium: verify each row independently from the files and a real test run; PASS or FAIL with evidence; then add the human pass.

| Row | Requirement | Reviewer (PASS/FAIL + evidence) |
|---|---|---|
| 1 | Test exists, is run and passes, and asserts what its name says: test_question_mark_alone_is_not_stakes |  |
| 2 | Test exists, is run and passes, and asserts what its name says: test_stakes_word_still_counts |  |
| 3 | Test exists, is run and passes, and asserts what its name says: test_h3_still_passes_for_a_question_opener |  |
| 4 | Only the files named in the spec were changed by this job (module + its new/edited test file); the frozen existing test files are untouched except the ones the spec says to update. |  |
| 5 | All tests of the changed module pass in anime_studio_merge (existing + new): run the module's old test file AND the new test file and paste the counts. |  |
| 6 | Every changed .py parses (ast.parse) and has no line over 120 characters. |  |
| 7 | No network, Colab, ElevenLabs, renderer or paid call; no reel 1 file touched. |  |
| 8 | The fix does not weaken an existing check (read the diff against the backup in the scratchpad backup_before_fixwave when the file existed before). |  |

## Human pass
- Missing:
- Extra:
- Bad:
