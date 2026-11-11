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