Defect:

- Faulty line (in `director/MASTER_PROMPT_v2.4.md`, inside the ```json example-blocking fence):
  `"blocking": {"schema": "blocking/1", "shot_id": "SHOT-07", ...`
- Why it is wrong: Card M-05 requires the sheet to be written as `blocking/1.1`. The acceptance test `test_v24_example_sheet_passes_blocking_validate` asserts `sheet["schema"] == "blocking/1.1"`, and `test_v24_example_sheet_lints_clean` expects the sheet to lint clean. `"blocking/1"` is the old schema and fails the schema assertion.
- Exact fix: Change `"schema": "blocking/1"` to `"schema": "blocking/1.1"` in the example-blocking fence.

VERDICT: FIX-FIRST