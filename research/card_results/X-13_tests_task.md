Write ONLY the test file h3/tests/test_render_controller_wiring_x13.py (plain pytest, standard library, tmp_path, no network, no model call; start with sys.path.insert of its own folder and the project root so the modules import by bare name or package as the neighbouring tests do). It is the frozen test gate for this gap card; the module change is made later by someone else, so the tests must FAIL on the current code and pass on a correct implementation. Use the hand-computed values written in the card; do not copy code from the module under test. Cover every test name the card lists.

CARD:
**X-13 | render_controller: timeline gate, Gate B gate, Gate D on lock seconds, render_ready.json**
- **Files:** `h3/render_controller.py`; `h3/pipeline_contract.py`; `h3/tests/test_render_controller_wiring.py` (append).
- **Change:**
  - pipeline_contract.py:11-22: add `("timeline", "Timeline lock matches its inputs")` and `("keyframes", "Gate B: every shot approved with a passing keyframe gate")` to STEP_ORDER before `lint`, and to PRE_ASSEMBLY. `build_plan` refuses unknown step ids (pipeline_contract.py:33), so this edit is required.
  - `plan_pipeline(..., lock_path=None, gate_b_path=None, keyframe_gate_dir=None)` (render_controller.py:567):
    - `results["timeline"]`: no path → ok False "no timeline lock". Otherwise `verify_lock(lock_path, load_lock(lock_path)["inputs"])` (StaleLockError → ok False), plus the lock shot ids must equal the selected shot ids.
    - `results["keyframes"] = approval_sheet.gate_b_ok(...)`.
  - `_gate_d_result` (render_controller.py:537-556): pass shots copied with `editorial_duration_sec = row["editorial_duration_sec"]` from `timeline_lock_io.lock_rows(lock)`, never the story value. Gate D then uses the same clock as build_final_reel.
  - CLI: add `--lock`, `--gate-b`, `--keyframe-gates`. `--mode execute` without `--lock` returns 2. When `assembly_allowed` is false, execute returns 1.
  - When all pre-render gates pass, write `<out>/render_ready.json {lock_input_sha256, gate_b_sha256, story_sha256, ok: true}`.
  - The runner side is another part: run_colab_batch.main `--go` must refuse without a matching render_ready.json (D-J8 runner job).
- **Tests:**
  - `test_plan_pipeline_no_lock_blocks` (results timeline ok False; assembly_allowed False).
  - `test_stale_script_byte_blocks` (edit one byte of an input → not ok).
  - `test_missing_gate_b_blocks`.
  - `test_gate_d_uses_lock_seconds`: story says 6.0 s, lock 168 → Gate D sees 7.0.
  - `test_execute_without_lock_exit_2`.
  - `test_render_ready_written_only_when_clean`.
- **Closes:** 1, 6, 8, 25, 35 (gate half). Bug: two Gate D verdicts (render_controller.py:551-552).
- **Depends on:** X-12, X-11, D-LOCK.
- **Collision:** none in this part. D-J8 runner reads render_ready.json.
- **Acceptance:** `python -m pytest h3/tests/test_render_controller_wiring.py h3/tests/test_render_controller.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** med.



EXTRA HINT: 