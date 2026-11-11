Implement this gap card by editing ONLY the allowed module files; the test file director/test_lock_rows_x12.py is frozen (do not touch it). Keep everything else byte-identical.

CARD:
**X-12 | lock_rows helper (one integer clock)**
- **Files:** `director/timeline_lock_io.py` (append); `director/test_timeline_lock_io.py` (append).
- **Change:** `lock_rows(lock) -> list[dict]` in lock order: `{id, start_frame, edit_frames, offset_sec = start_frame/fps, editorial_duration_sec = edit_frames/fps, trim_in_frame, trim_out_frame}`.
  - Recompute start_frame as a running integer sum and raise ValueError if a recorded `start_frame` differs.
  - Missing trim keys raise KeyError naming the shot (D-LOCK provides them).
- **Tests:** `test_lock_rows_hand`: edit_frames [168,120,192] → start [0,168,288], offsets **[0.0, 7.0, 12.0]**, total 480 = **20.0 s**; `test_start_frame_mismatch_raises`.
- **Closes:** 6 (shared helper).
- **Depends on:** D-LOCK.
- **Collision:** timeline_lock_io.py is also edited by D-LOCK (params). Run after it.
- **Acceptance:** `python -m pytest director/test_timeline_lock_io.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** low.

