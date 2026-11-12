**REAL DEFECTS**

1. **`test_route_s_uses_key_a_as_the_end_key` is tautological.**  
   In `director/test_post_fetch_qa.py`, the test calls `pq.run(...)` with `load_key=lambda p: "key:" + str(p)`. Because `key_a` and `key_b` are the same string `"a.png"` in `_plan`, the S‑route branch `key_b = key_a` produces the same value as the normal path would. The assertion `calls[0]["key_b"] == calls[0]["key_a"]` therefore cannot fail; it does not verify that the route‑S logic was taken.  
   **Fix:** give `key_b` a distinct value in the plan (e.g. `"b.png"`), so the test proves that `key_b` is replaced by `key_a` only when `route == "S"`.

2. **`test_inputs_error_fails_the_shot` is tautological.**  
   The test defines `bad(sid)` which raises `ValueError(f"{sid}: no route in the routes file")`. The assertion `"no route" in out["SHOT-001"]["reason"]` matches the literal string `"no route"` that the test itself supplied. The test would pass even if `pq.run` swallowed the exception and returned a hardcoded reason; it does not prove that the exception is caught and converted into a failure entry.  
   **Fix:** use a different error message in the `bad` function (e.g. `"broken"`) and assert on that distinct token, or assert that the reason contains the exception text.

3. **`test_qa_plan_without_routes_is_refused_before_any_render` is weak.**  
   The test passes `--qa-plan plan.json` without `--routes`/`--pack` and expects exit 1 and no clip folder. The code checks `if a.qa_plan and not (a.routes and a.pack): return 1` before `batch()` is called, so the clip is never created. However, the test does not verify that the refusal happens *before* the render; it only checks the side effect. More importantly, the test does not cover the case where `--routes` is given but `--pack` is missing, or vice‑versa. The card requires the QA inputs to be refused when either is missing.  
   **Fix:** add a separate test for `--qa-plan plan.json --routes routes.json` (missing `--pack`) and for `--qa-plan plan.json --pack pk` (missing `--routes`), asserting exit 1 and no clip.

4. **`test_go_qa_pass_exits_zero` mocks `run_from_files` but not `exit_code`.**  
   The test sets `r.post_fetch_qa.run_from_files` to a lambda returning `{"SHOT-001": {"ok": True}}`. The real `exit_code` is still used, which is correct. However, the test does not verify that `exit_code` is called with the QA results; it only checks the return code. This is acceptable but the test name is misleading—it should be `test_go_qa_pass_exits_zero_via_exit_code`.

5. **`test_go_records_render_in_default_history` does not check `drift_step`.**  
   The test asserts `doc["shots"]["SHOT-001"][0]["settings_sha256"]` but ignores `drift_step`. The card requires recording the drift step; the test should also assert `doc["shots"]["SHOT-001"][0]["drift_step"] is None` (or the value from `new_log`).

VERDICT: FIX-FIRST