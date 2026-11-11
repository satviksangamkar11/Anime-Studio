Implement this gap card by editing ONLY the allowed module files; the test file director/test_approval_sheet.py is frozen (do not touch it). Keep everything else byte-identical.

CARD:
**X-11 | approval sheet (3 layers) + Gate B record**
- **Files:** `director/approval_sheet.py` NEW; `director/test_approval_sheet.py` NEW.
- **Change:**
  - `build(lock, sheets, source_check, keyframe_gates, routes, vo_report=None)` writes `approval_sheet.md` + `.csv`, one row per shot, three independent layers (the reel-1 approval_sheet_18x3 idea, rule 36):
    - **timing**: edit_frames, seconds, voice lines start/end.
    - **source**: refs + verdicts.
    - **staging**: start→end summary, change_list, route, keyframe_gate pass and metrics, image paths.
  - `approve(shot, by, gate_b_path)`: refuses unless that shot's keyframe_gate pass is true. Appends `{shot, by, date, keyframe_gate_sha256}` to `gate_b.json` (append-only).
  - `gate_b_ok(gate_b, keyframe_gate_dir, shot_ids) -> list[problems]`: missing approval, or approved keyframe_gate sha ≠ current file sha.
- **Tests:**
  - `test_three_layers_present`.
  - `test_approve_refused_on_failed_gate`.
  - `test_gate_b_stale_after_new_B` (gate file rewritten → problem).
  - `test_csv_row_count_equals_lock_shots`.
- **Closes:** 21 and 25 (Gate B is a record, not a note); 35 partly (explicit approvals).
- **Depends on:** X-08, X-10, X-04.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_approval_sheet.py -q`
- **OWNER DECISION:** owner approves each shot (the `approve` command is run by the owner or with the owner's word).
- **Second-attempt risk:** low.

---

