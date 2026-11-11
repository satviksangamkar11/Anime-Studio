**REAL DEFECTS FOUND:**

1. **`test_gate_b_stale_after_new_B` is weak / does not fully cover the test name.**
   - The test name says "gate file rewritten → problem". The test only rewrites the gate file with a *passing* gate, then checks `gate_b_ok`. But `gate_b_ok` also has a branch for "keyframe gate no longer passes". The test never exercises that branch (it doesn't test a gate that was approved, then rewritten to `pass: False`). More critically, the test does not verify that `gate_b_ok` returns *only* the expected problem string, nor does it check that other shots are unaffected. The assertion `any("shot_01" in problem for problem in problems)` is tautological given the previous line already asserts `problems` is truthy and the only shot checked is `shot_01`.
   - **Fix:** Strengthen the assertion to check the exact problem message, e.g.:
     ```python
     assert problems == ["shot_01: keyframe gate changed after approval (stale), re-approve"]
     ```
     And add a second sub-test (or extend this one) to also cover the "gate no longer passes" branch by writing a gate with `"pass": False` and asserting the corresponding message.

2. **`test_csv_seconds_from_lock_frames` is not listed in the card's test names.**
   - The card lists exactly four tests: `test_three_layers_present`, `test_approve_refused_on_failed_gate`, `test_gate_b_stale_after_new_B`, `test_csv_row_count_equals_lock_shots`. The extra test `test_csv_seconds_from_lock_frames` is not required and is not mentioned; it is not a defect in itself, but it means the test file contains an unlisted test. (Not a failure, but note: the card's acceptance criteria is `python -m pytest director/test_approval_sheet.py -q` — extra tests do not break that, so this is informational only.)

3. **`test_approve_refused_when_gate_file_missing` is not listed in the card's test names.**
   - Same as above: extra test, not required. No functional defect.

4. **`_load_approvals` in `approval_sheet.py` does not handle an empty file or a file with only whitespace.**
   - If `gate_b_path` exists but is empty (0 bytes), `path.read_text()` returns `""`, and `json.loads("")` raises `json.JSONDecodeError`. The test `test_approve_refused_on_failed_gate` writes `"[]"` (not empty), so this path is not hit. But a real run could leave an empty file. This is a crash path.
   - **Fix:** Guard against empty content:
     ```python
     content = path.read_text(encoding="utf-8").strip()
     if not content:
         return []
     data = json.loads(content)
     ```

5. **`gate_b_ok` does not check that the approval record itself is valid (e.g., missing `keyframe_gate_sha256` key).**
   - If a malformed approval record exists (e.g., `{"shot": "shot_01", "by": "owner"}` without the sha key), `record.get("keyframe_gate_sha256")` returns `None`, and the comparison `_sha256(gate_file) != None` will always be `True`, producing a spurious "stale" problem. This is an input that passes silently in `approve` (if someone manually edits the JSON) but causes incorrect output in `gate_b_ok`.
   - **Fix:** Validate the record structure:
     ```python
     if "keyframe_gate_sha256" not in record:
         problems.append(f"{sid}: approval record missing keyframe_gate_sha256")
         continue
     ```

**VERDICT: FIX-FIRST**