Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything else byte-identical; do not add code that reads files at import time.

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



REVIEW BY LUNA:
`main` does not enforce the card’s execute requirement when assembly is blocked. It checks `pre_render_ready(gates["steps"])` instead:

> `if not pre_render_ready(gates["steps"]):`

The card requires execute to return 1 when `assembly_allowed` is false. Check `if not gates["assembly_allowed"]:` here and return 1 before `prepare` or writing `render_ready.json`.

VERDICT: FIX-FIRST.

REVIEW BY DOTS:
**REAL DEFECTS FOUND**

1. **`h3/render_controller.py` line 551-552 — two Gate D verdicts (card's own bug note):**
   ```python
   ok_by_episode[ep_id] = {lang: bool(rep["ok"]) and not rep["errors"] for lang, rep in res["reports"].items()}
   for lang, rep in res["reports"].items():
       problems += [f"{ep_id} {lang}: {e['code']} {e['where']}: {e['message']}" for e in rep["errors"]]
   ```
   The `and not rep["errors"]` is redundant: `plan_language_outputs` already sets `rep["ok"] = False` when `rep["errors"]` is non‑empty. The second loop then re‑emits the same errors into `problems`, making `gate_d` double‑count its failures. The card explicitly lists this as a bug to fix.

   **Fix:** delete the `and not rep["errors"]` clause and remove the duplicate error‑collection loop (or merge them into one pass):
   ```python
   ok_by_episode[ep_id] = {lang: bool(rep["ok"]) for lang, rep in res["reports"].items()}
   for lang, rep in res["reports"].items():
       problems += [f"{ep_id} {lang}: {e['code']} {e['where']}: {e['message']}" for e in rep["errors"]]
   ```

2. **`h3/render_controller.py` line 555 (inside `_gate_d_result`) — crash path on `KeyError`:**
   ```python
   shots = [dict(s, editorial_duration_sec=lock_seconds[s["shot_id"]]) for s in shots]
   ```
   If a shot row in `groups` does not contain the key `"shot_id"`, `s["shot_id"]` raises `KeyError`. The function's `except` tuple (line 547) does **not** include `KeyError`, so the exception propagates and crashes `plan_pipeline`.

   **Fix:** add `KeyError` to the except clause, or use `s.get("shot_id")` and handle `None`:
   ```python
   except (KeyError, TypeError, ValueError, AttributeError) as e:
   ```

3. **`h3/render_controller.py` line 548 — `lock_rows` called on a lock loaded without `lock_sha256`:**
   ```python
   lock_seconds = {row["id"]: row["editorial_duration_sec"] for row in lock_rows(load_lock(lock_path))}
   ```
   `lock_rows` expects a lock dict that contains a `"lock_sha256"` key (it verifies the lock's integrity). If `load_lock` returns a dict without that key (e.g. a malformed lock file), `lock_rows` raises `KeyError`, which is again not caught.

   **Fix:** add `KeyError` to the except clause (same as #2) or validate the lock structure before calling `lock_rows`.

4. **Test `test_render_ready_written_only_when_clean` cannot fail (weak/tautological):**
   The test stubs `plan_pipeline` to return `all_ready` (every PRE_RENDER gate `ok: True`). The real `main()` then calls `pre_render_ready(gates["steps"])`, which is guaranteed to be `True` by the stub. The test never verifies that `render_ready.json` is *not* written when a gate fails — it only checks the happy path. The card requires a test that the file is written **only when clean**, but the negative case is missing.

   **Fix:** add a second call to `rc.main` with a stubbed `plan_pipeline` that returns a blocked step, and assert `not ready_path.exists()` and `code == 1`.

5. **Test `test_gate_d_uses_lock_seconds` does not cover the card's test name fully:**
   The card lists `test_gate_d_uses_lock_seconds` and specifies "story says 6.0 s, lock 168 → Gate D sees 7.0". The test checks that `SYN_A` gets `7.0`, but it never verifies that the *story's* `editorial_duration_sec` (6.0) is **not** used. The assertion `assert all(s.get("editorial_duration_sec") != 7.0 for s in story_rows)` only proves the story rows don't already equal 7.0; it does not prove Gate D ignored them. A stronger assertion would confirm the story value is 6.0 and that the passed shots carry 7.0.

   **Fix:** change the assertion to explicitly check the story value and the overridden value:
   ```python
   assert all(s.get("editorial_duration_sec") == 6.0 for s in story_rows)
   ```

VERDICT: FIX-FIRST