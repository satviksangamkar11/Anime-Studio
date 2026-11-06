

The scripts were reviewed for the requested failure modes. A high-severity path traversal was found in the filer, a medium-severity secret leak in the collector, and several low-severity crashes, race conditions, and minor logic errors. No issues were found with dHash correctness, queue items lacking aspect/fingerprint, or unsafe moves in `tidy_final` (beyond an edge case with empty titles).

FINAL:

HIGH:
- file_flow_download.py:34,54 — The `sub` argument is used directly in the destination path without validation; an absolute path or `..` escapes the root directory, allowing arbitrary file writes. Fix: validate that `sub` is a relative path without `..` segments, e.g., `sub_path = Path(sub); if sub_path.is_absolute() or '..' in sub_path.parts: refuse(...)`.

MEDIUM:
- download_queue.py:122-124 — `env=dict(os.environ, ...)` passes all parent environment variables to the subprocess, potentially leaking API keys, passwords, or other secrets. Fix: start with an empty dict and only add the variables required by the filer (FLOW_OUT_ROOT, FLOW_ADHYAY, FLOW_OPERATOR, FLOW_MAX_AGE_S, PYTHONIOENCODING, FLOW_ASPECT, FLOW_APPROVED_DHASH, FLOW_LINEAGE, FLOW_DECIDED_BY).
- file_flow_download.py:94,95 — If the job dict from the jobs file lacks `prompt_sha256` or `chips`, the script crashes with KeyError instead of refusing. Fix: use `job.get("prompt_sha256")` and `job.get("chips")`.

LOW:
- file_flow_download.py:55-56,82 — TOCTOU race condition: the existence check for `jpg`/`png` and the later `copy2` are not atomic; another process could create the file in between, leading to overwrite. Fix: write to a temporary file and rename atomically, or catch `FileExistsError`.
- file_flow_download.py:82-85 — Partial filing: if the process is killed after `copy2` but before the PNG is saved and the log written, a partial file remains without a log entry. Fix: write to a temporary file and rename after both files are created, or install a signal handler to clean up.
- file_flow_download.py:45 — Unhandled ValueError: if `FLOW_ADHYAY` is not an integer, `int()` raises and the script crashes instead of exiting cleanly. Fix: validate the environment variable and fall back to the default if invalid.
- file_flow_download.py:48 — Unhandled JSONDecodeError: if the jobs file is malformed, `json.loads` raises and the script crashes. Fix: catch `json.JSONDecodeError` and refuse with a clear message.
- download_queue.py:106 — Glob injection: the `title` is interpolated directly into a glob pattern; if the title contains special characters (e.g., `*`), it matches unintended files. Fix: use `glob.escape(title)` or validate the title.
- download_queue.py:56 — TypeError if job prompt is None: `job.get("prompt", "")` returns `None` if the key exists with value `None`, causing `in` to raise. Fix: use `job.get("prompt") or ""`.
- download_queue.py:64 — Unhandled exception from dhash_file: if `approved_image` is not a valid image, `dhash_file` raises and the script crashes. Fix: catch the exception and raise a ValueError with a user-friendly message.
- download_queue.py:97 — Malformed log lines ignored: lines in `flow_log.jsonl` missing `image_id` or `version` are silently skipped, which can cause items to be considered pending even when filed. Fix: skip only lines that are invalid JSON, but still check the keys; or validate the log format.
- tidy_final.py:23 — Empty title: if a file is exactly a variant name (e.g., `__candidate_v01.png`), the title becomes an empty string, which could cause moves of files without a title prefix. Fix: filter out empty titles in the set comprehension.