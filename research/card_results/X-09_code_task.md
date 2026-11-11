Implement this gap card by editing ONLY the allowed module files; the test file director/test_keyframe_jobs.py is frozen (do not touch it). Keep everything else byte-identical.

CARD:
**X-09 | plates registry + A/B Flow jobs from the sheet**
- **Files:** `director/keyframe_jobs.py` NEW; `director/test_keyframe_jobs.py` NEW.
- **Change:**
  - `plates_index(flow_root) -> {plate_id: {path, sha256}}`, reading `<flow_root>/plates/plates.json` plus files.
  - `jobs_for_shot(sheet, plate, bible_names)` returns two jobs with exactly the key set of flow/scripts/build_jobs.py:301-325:
    - **A**: `method: "edit"`, `chips: [plate path]` (single reference, rule 25), prompt = "same set, add: <name> at (x,y), scale s, facing f, pose p ..." from `start`, `base_edit_id: plate_id`.
    - **B**: `base_edit_id: "<SHOT>-A"`, `chips: ["<SHOT>-A final"]`, `edit_instruction = "same picture, make these exact changes only: 1) … n)"` from `blocking.change_list(sheet)`.
    - `people_count` = on-screen cast count.
  - A missing plate raises `KeyframeJobError("plate PLATE-x missing: make it once per location first")`.
  - CLI writes `<flow_root>/adhyay_NN/keyframe_jobs.json`. Never calls Flow.
- **Tests:**
  - `test_job_keys_match_build_jobs`: key set equality with a build_jobs fixture job.
  - `test_b_is_edit_of_a` (base_edit_id, single chip).
  - `test_b_instruction_from_change_list` (exact text from the X-03 hand case).
  - `test_missing_plate_raises`.
  - `test_people_count`.
- **Closes:** 20 (B as an edit of A in code), 23 (job carries everything; rule).
- **Depends on:** X-03.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_keyframe_jobs.py -q`
- **OWNER DECISION:** none.
- **Second-attempt risk:** low.

