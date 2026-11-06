

FINAL:

1. **High**, `run_registry.py:92-93` – `story_folder` checks the folder name against `SLUG` but does not resolve symlinks. A symlink `stories/evil -> /etc` passes the check and all subsequent writes go outside `stories/`.  
   **Fix:** Resolve the real path and ensure it starts with `stories/` before returning the folder.

2. **High**, `run_registry.py:209-220` – `update_story` writes `title`, `owner_request_text`, `tags` and other fields directly into `story.json` without redaction. A title containing a secret (e.g. `"Bearer sk-..."`) is persisted.  
   **Fix:** Apply `redact()` to every string field before writing `story.json`.

3. **High**, `run_registry.py:556-560` – `write_report` renders the report from `story.json` and events but never redacts the story fields, so `RUN_REPORT.md` can leak secrets.  
   **Fix:** Redact the story dict in `report_text` (or in `render_markdown`) before formatting.

4. **Medium**, `run_registry.py:285-286` – `append_event` opens `RUNS.jsonl` with `"a"` and writes a line. Two concurrent writers can interleave half‑lines, corrupting the log.  
   **Fix:** Use a lock file or write to a temporary file and rename (append‑only is not enough; a proper append requires locking).

5. **Low**, `run_registry.py:266-267` – The `files` list in an event is not redacted; a file name containing a token would be written to `RUNS.jsonl`.  
   **Fix:** Run each file name through `redact()` before validation.

6. **High**, `backfill_registry.py:202-203` – `backfill_story` calls `update_story` with `owner_request_text` and a `source` dict that are taken directly from `SOURCE.md` without redaction, so secrets land in `story.json`.  
   **Fix:** Redact `owner_request_text` and all string values in `source` before calling `update_story`.

7. **High**, `backfill_registry.py:232-234` – The main loop selects folders by matching `SLUG.fullmatch(p.name)` but does not resolve symlinks; a symlink with a valid name can point outside the studio.  
   **Fix:** Resolve each folder and skip it if its real path is not under `stories/`.

8. **High**, `backfill_registry.py:88-89, 136-137` – `_log_runs` and `_pack_plans` use `story_dir.glob` and `pdir.glob` without checking whether the matched paths are symlinks, allowing reads (and subsequent writing of derived data) from arbitrary locations.  
   **Fix:** After globbing, verify that each path’s real path is inside the story folder.

9. **High**, `backfill_registry.py:206-208` – `pack_folders` (via `is_pack_folder`) only checks the folder name, not whether the folder is a symlink; a symlinked pack folder can cause writes outside the story directory.  
   **Fix:** In `is_pack_folder` (or before calling it), resolve the path and ensure it stays within the story directory.