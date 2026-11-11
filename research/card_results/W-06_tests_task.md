Write ONLY the test file h3/tests/test_v4_to_h3_lock.py (plain pytest, standard library, tmp_path, no network, no model call; start with sys.path.insert of its own folder and the project root so the modules import by bare name or package as the neighbouring tests do). It is the frozen test gate for this gap card; the module change is made later by someone else, so the tests must FAIL on the current code and pass on a correct implementation. Use the hand-computed values written in the card; do not copy code from the module under test. Cover every test name the card lists.

CARD:
### W-06: v4_to_h3 takes lattice and trims from the lock
- **Files:** h3/v4_to_h3.py; h3/tests/test_v4_to_h3_lock.py NEW.
- **Change:**
  1. `convert_pack(..., lock=None)`. With a lock, work on a deep copy of the rows: `lattice_n = L.lattice_n`, `editorial_duration_sec = L.edit_frames / FPS`, and `h3_fields` incoming/outgoing seam types set from the lock. A row whose id is missing from the lock gets the problem `"<sid>: not in the timeline lock"` and is skipped.
  2. After `derive_fields` (line 672): trim_in, trim_out or pixel_frames different from the lock adds the problem `"<sid>: lock trims ... != derived ..."`.
  3. `timing_and_lattice` carries `end_frame_position` from the lock (data only; nothing reads it until W-10).
  4. `main`: `--lock`, checked through the recorded inputs; stale returns exit 2.
- **Tests (pack dicts built with the helper in h3/tests/test_v4_to_h3.py; lock rows from `write_timeline_lock.plan_lock`):**
  - `test_timing_equals_lock`: pixel_frames, trims and editorial_frames equal the lock rows for every shot.
  - `test_shot_missing_from_lock_problem`.
  - `test_tampered_lock_trim_problem`: trim_in + 1 gives the mismatch problem.
- **Closes:** 3 (the second lattice picker is bypassed), 4.
- **Depends on:** W-03.
- **Collisions:** v4_to_h3 is also edited by W-07, which runs after this card.
- **Acceptance:** `python -m pytest h3/tests -q`.
- **Owner decision:** none. **Risk:** med.



EXTRA HINT: 