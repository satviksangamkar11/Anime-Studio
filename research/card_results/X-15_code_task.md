Implement this gap card by editing ONLY the allowed module files; the test file director/test_build_final_reel_lock.py is frozen (do not touch it). Keep everything else byte-identical.

CARD:
**X-15 | build_final_reel part 1: required --reel, lock_rows, no silent fallbacks, waivers.json, clip_qa gate**
- **Files:** `director/build_final_reel.py`; `director/test_build_final_reel_lock.py` NEW.
- **Change:**
  - build_final_reel.py:253: `--reel` becomes `required=True`, regex `^[a-z0-9_]+$`; `REEL_CLOSED = {"kalika_reel1"}` exits (rule 53).
  - Add `--lock` (required). Delete the `editorial_by_lang` import and apply_rows/apply_shots (lines 261-265). Rows take `editorial_duration_sec` from `timeline_lock_io.lock_rows(verify_lock(...))`, and h3_shots `timing_and_lattice` trims are checked equal to the lock.
  - `mux_argv` (lines 66-76): offsets from lock_rows `offset_sec`, not float sums. A missing VO WAV for a shot that has lines in shots.json raises SystemExit (today it becomes silence).
  - Lines 287-291: a missing `vo_tracks_report.json` raises unless `--title-cards`. Remove the second fallback path.
  - Delete `WAIVED` (line 32). `load_waivers(pack, reel)` reads `<pack>/waivers.json {reel, codes, signed_by: "owner", date}`. Missing file → none; reel mismatch or no signed_by → SystemExit. Report lists waived codes.
  - Before assembly: `clip_qa.clip_ok` for every clip in `--clips`; any problem → SystemExit.
- **Tests (pure functions; ffmpeg not run):**
  - `test_reel_required` (argparse SystemExit).
  - `test_reel1_refused`.
  - `test_offsets_from_lock` (**[0.0, 7.0, 12.0]**).
  - `test_missing_vo_with_lines_raises`.
  - `test_missing_report_raises`.
  - `test_reel2_no_waivers_blocks_dead_air` (DEAD_AIR_PAUSE stays blocking).
  - `test_waivers_reel_mismatch_raises`.
  - `test_clip_qa_fail_blocks`.
- **Closes:** 3, 6, 19, 37 (assembly side). Bug: Opus 17 (silent fallbacks, float offsets, --reel default), hard-coded reel-1 waiver.
- **Depends on:** X-12, X-14, D-LOCK.
- **Collision:** build_final_reel.py is also edited by X-16 and X-17 (sequential X-15 → X-16 → X-17), and by any other-part audio_edge job. Coordinate order.
- **Acceptance:** `python -m pytest director/test_build_final_reel_lock.py -q` and the existing build_final_reel tests (Glob `director/test_*final_reel*`).
- **OWNER DECISION:** per-reel waivers file format.
- **Second-attempt risk:** med.

