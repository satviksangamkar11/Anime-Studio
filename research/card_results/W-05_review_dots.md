**Defect 1: `build_locked_cue_sheet` ignores `VO_REPORTS_REQUIRED` when `lock` is malformed**

In `score/cue_sheet.py`, the function `build_locked_cue_sheet` checks `vo_reports` first, but if the lock is malformed (not a dict or missing a "shots" list), it returns a `LOCK_SHAPE` error instead of `VO_REPORTS_REQUIRED`. The card explicitly requires that `vo_reports is None` gives error `VO_REPORTS_REQUIRED` when a lock is given. A caller passing a malformed lock and no VO reports would see `LOCK_SHAPE` instead of the required error.

- **Faulty line:**  
  `if not isinstance(lock, dict) or not isinstance(lock.get("shots"), list):` (in `build_locked_cue_sheet`)
- **Exact fix:** Move the `vo_reports` check before the lock shape check, or ensure the lock shape check is skipped when `vo_reports` is empty so the required error is raised first. For example:

```python
    if not vo_reports:  # None or an empty list: the speech positions are required
        return None, _report([_err("VO_REPORTS_REQUIRED", "vo_reports", "give at least one vo_tracks_report (one per language)")])
    if not isinstance(lock, dict) or not isinstance(lock.get("shots"), list):
        return None, _report([_err("LOCK_SHAPE", "lock", "expected a timeline lock with a shots list")])
```

**Defect 2: `test_lock_sets_frames` does not verify the required `bpm`, `snap`, `cue`, `act_start_frame` fields**

The card lists `test_lock_bpm_on_rows` (and the test file contains `test_lock_bpm_snap_cue_and_act_on_rows`), but `test_lock_sets_frames` only checks frames and start_frame. It does not assert that the lock’s `bpm`, `snap`, `cue`, and `act_start_frame` are copied onto the shot rows, which is a core requirement of the card.

- **Faulty line:**  
  `assert sheet["shots"][1]["start_frame"] == 79` (end of `test_lock_sets_frames`)
- **Exact fix:** Add assertions for the copied fields, e.g.:

```python
    assert sheet["shots"][0]["bpm"] == 128 and sheet["shots"][0]["snap"] is True
    assert sheet["shots"][1]["bpm"] == 128 and sheet["shots"][1]["snap"] is False
    assert sheet["shots"][0]["cue"] == "c1" and sheet["shots"][0]["act_start_frame"] == 0
    assert sheet["shots"][1]["cue"] == "c1" and sheet["shots"][1]["act_start_frame"] == 0
```

**Defect 3: `test_main_missing_lock_exit_2` does not assert that stderr contains the required message**

The card requires that a missing lock prints to stderr and returns 2. The test checks the return code but never verifies that the expected error message was printed, so a regression that returns 2 without printing would pass.

- **Faulty line:**  
  `assert rc == 2` (in `test_main_missing_lock_exit_2`)
- **Exact fix:** Capture stderr and assert the expected message:

```python
    captured = capsys.readouterr()
    assert rc == 2
    assert "--lock is required" in captured.err
```

VERDICT: FIX-FIRST