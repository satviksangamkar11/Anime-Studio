# Checklist FXC (rule 55) - fix wave, spec: loop_run_reel2/specs/FXC_script_inspect_errors.md

Coder = Nemotron Super (loop). Reviewer = Haiku medium: verify each row independently from the files and a real test run; PASS or FAIL with evidence; then add the human pass.

| Row | Requirement | Reviewer (PASS/FAIL + evidence) |
|---|---|---|
| 1 | Requirement 1: A row that is not a dict, or has no "id": raise ValueError("row <index>: missing id") (index = 0-based position in rows). |  |
| 2 | Requirement 2: Missing "editorial_duration_sec" or "audio_and_dialogue_track": ValueError("row <id>: missing <key>"). |  |
| 3 | Requirement 3: A directive with a non-empty action_pose_expression but no "t0" (or a t0 that is not a number): ValueError("row <id>: directive <i> has no usable t0"). |  |
| 4 | Requirement 4: A dialogue or narration item without "text" or "time_range": ValueError("row <id>: item without text or time_range"). |  |
| 5 | Test exists, is run and passes, and asserts what its name says: test_row_without_id_raises_value_error |  |
| 6 | Test exists, is run and passes, and asserts what its name says: test_row_without_duration_raises |  |
| 7 | Test exists, is run and passes, and asserts what its name says: test_row_without_track_raises |  |
| 8 | Test exists, is run and passes, and asserts what its name says: test_directive_without_t0_raises |  |
| 9 | Test exists, is run and passes, and asserts what its name says: test_item_without_text_raises |  |
| 10 | Test exists, is run and passes, and asserts what its name says: test_main_returns_2_for_incomplete_row |  |
| 11 | Test exists, is run and passes, and asserts what its name says: test_import_from_other_folder_still_finds_siblings |  |
| 12 | Only the files named in the spec were changed by this job (module + its new/edited test file); the frozen existing test files are untouched except the ones the spec says to update. |  |
| 13 | All tests of the changed module pass in anime_studio_merge (existing + new): run the module's old test file AND the new test file and paste the counts. |  |
| 14 | Every changed .py parses (ast.parse) and has no line over 120 characters. |  |
| 15 | No network, Colab, ElevenLabs, renderer or paid call; no reel 1 file touched. |  |
| 16 | The fix does not weaken an existing check (read the diff against the backup in the scratchpad backup_before_fixwave when the file existed before). |  |

## Human pass
- Missing:
- Extra:
- Bad:
