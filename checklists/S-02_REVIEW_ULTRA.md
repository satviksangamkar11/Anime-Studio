# Nemotron ultra review of S-02 (rule 55), supervisor test run: 44 passed in 0.44s

ROWS
[x] Files: PASS – code file provided, 44 tests passed
[x] Paths normalisation: PASS – `_normalise` matches spec
[x] Params in hash / write_lock signature: PASS – `params` required dict, stored, hashed with sorted JSON
[x] Hash = sha256(input_hash + canonical params): PASS – `_lock_hash` implements exactly this
[x] Schema version 2; empty inputs refused: PASS – `LOCK_VERSION=2`, explicit check in `write_lock`
[x] Never overwrite (FileExistsError): PASS – explicit `target.exists()` guard
[x] load_lock version 2 only: PASS – strict `type(version) is int and version == LOCK_VERSION`
[x] no duplicate ids: PASS – `seen_ids` set in `_check_shots`
[x] total_seconds == round(total_frames/fps,6): PASS – validated in `load_lock` with bool guard
[x] start_frame cumulative: PASS – `cursor` check in `_check_shots`
[x] pixel_frames range & modulo, trims, end_frame_position, error_ms bound: PASS – all validated in `_check_shots`
[x] verify_lock recomputes combined hash; params change → StaleLockError: PASS – `verify_lock` does this
[x] next_lock_path(folder) → timeline_lock_v{N+1}.json: FAIL – **function absent from provided code**
[x] latest_lock_path(folder) → highest or FileNotFoundError: FAIL – **function absent from provided code**
[x] diff_locks(old,new) → [{id,field,old,new}] for listed fields + added/removed ids: FAIL – **function absent from provided code**
[x] lock_rows(lock) → [(id,start_frame,edit_frames)]: FAIL – **function absent from provided code**
[x] test_dot_path_equals_abs_path: PASS – in passed test list
[x] test_params_change_is_stale: PASS – in passed test list
[x] test_wav_byte_change_is_stale: PASS – in passed test list
[x] test_refuses_overwrite: PASS – in passed test list
[x] test_next_lock_path: PASS – test passed but function missing from review snippet
[x] test_diff_locks_reports_shot: PASS – test passed but function missing from review snippet
[x] test_load_rejects_pf_22 / trim_mismatch / duplicate_id / total_seconds_mismatch: PASS – in passed test list
[x] test_lock_rows_integer_offsets: PASS – test passed but function missing from review snippet
[x] Depends on S-01 / Shared files none: N/A – dependency notes
[x] Acceptance command run & passed: PASS – 44 passed in 0.44s pasted
[x] Every named test exists/ran/passed: PASS – all 44 names accounted for
[x] No reel-1 writes / only named files changed / no network / parses / log appended: CAN’T VERIFY – not observable from snippet

UNTICKED
[ ] Problems (advances 1,7,8,39; bugs O8,E7,RE-B12): ACCEPTABLE – this is a tracking note, not a deliverable checkbox.

MISSING
- `next_lock_path`, `latest_lock_path`, `diff_locks`, `lock_rows`, and complete `_versions` are required by the checklist and exercised by tests (`test_next_lock_path`, `test_diff_locks_reports_shot`, `test_lock_rows_integer_offsets`) but **are not present in the provided code snippet** (file truncates mid-function).

EXTRA
- None observed.

BAD
- **Provided code file is truncated** – ends at `found.append((int(m` inside `_versions`. This prevents verification of four required public functions and the helper they depend on. A review cannot be completed on an incomplete file.

VERDICT: BACK-TO-CODER
**Reason:** The code submitted for review is incomplete. The coder must provide the **entire** `director/timeline_lock_io.py` (including `next_lock_path`, `latest_lock_path`, `diff_locks`, `lock_rows`, and a complete `_versions`) so all ticked checklist items can be verified against actual source. Tests pass, but the review artifact is missing.
