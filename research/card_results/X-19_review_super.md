**Defect 1 — `build_locked_cue_sheet` is missing (card requirement not met; crash path).**  
Quote: the module ends inside `build_cue_sheet` (`   
...(cut)`); there is no `def build_locked_cue_sheet(...)` anywhere in the provided source.  
Why: The card requires `build_locked_cue_sheet(shots, lock, vo_reports, episode=None)`. The new tests call `cue_sheet.build_locked_cue_sheet`; without it every one of those tests crashes with `AttributeError` instead of exercising the lock path.  
Fix: Add `build_locked_cue_sheet` per card: copy shots, set `editorial_duration_sec` from the matching lock row, call `build_cue_sheet(shots, episode=episode, vo_reports=vo_reports)` (no `voice_windows`, no `editorial`), report `LOCK_MISMATCH` when `sheet.total_frames != lock.total_frames` or shot ids differ, copy `bpm`/`snap`/`act` from lock rows into each shot row, and report `NO_VO_REPORT` when `vo_reports` is empty.

**Defect 2 — `main` is missing (card requirement not met; crash path).**  
Quote: no `def main(...)` is present; the card cites `cue_sheet.py:592-652`.  
Why: The card requires CLI changes (`--lock` required, `--lock-inputs-check`, `--vo-report` required, `--editorial`/`--voice-windows` removed). The CLI tests call `cue_sheet.main`; without it they crash with `AttributeError`.  
Fix: Implement `main` per card with the required arguments, required `--lock` and `--vo-report`, `--lock-inputs-check` gating `verify_lock`, `StaleLockError` → exit 2, and `--editorial`/`--voice-windows` removed.

**Defect 3 — Wrong empty-VO error code in test.**  
Quote: `assert sheet is None and [e["code"] for e in report["errors"]] == ["VO_REPORTS_REQUIRED"]` (`test_no_vo_report_is_an_error`).  
Why: The card requires error code `NO_VO_REPORT` when `vo_reports` is empty. The test asserts `VO_REPORTS_REQUIRED`, validating the wrong result and passing a non-compliant implementation.  
Fix: Change to `== ["NO_VO_REPORT"]` and make `build_locked_cue_sheet` emit that code.

**Defect 4 — Stale-lock test never exercises `--lock-inputs-check`.**  
Quote: `rc = cue_sheet.main(["--shots", str(shots), "--lock", str(lock_path), "--vo-report", str(vo), "--out", str(tmp_path / "o.json")])` (`test_stale_wav_exit_2`).  
Why: The card adds `--lock-inputs-check` to run `verify_lock(lock, lock["inputs"])`; `StaleLockError` → exit 2. The test mutates an input byte but never passes `--lock-inputs-check`. If verification is gated on that flag, the stale lock is accepted and the test cannot fail; if verification is unconditional, the flag is untested.  
Fix: Add `--lock-inputs-check` to the `main` argv in this test (and gate `verify_lock` on that flag in `main`).

**Defect 5 — `vo_reports` passed as a list, but the contract is `{lang: [rows]}` (crash path).**  
Quote: `return [{"shot": sid, "lang": "en", "editorial": n / 24, "tempo": 1.0, "file": "", "lines": []} ...]` in `vo_rows()`, and `cue_sheet.build_locked_cue_sheet(pack3(), lock_dict(), vo_rows())`.  
Why: The card defines `vo_reports` as `{lang: [rows]}`. The visible `_index_vo_reports` calls `vo_reports.items()`; a list has no `.items()`, so any non-empty `vo_reports` crashes with `AttributeError`. The happy-path tests pass a list and will crash.  
Fix: Change `vo_rows()` to return `{"en": [...]}` (and update `write_inputs`/CLI fixtures to match the dict contract).

**Defect 6 — Test asserts unrequired `ACT_MISMATCH`.**  
Quote: `assert sheet is None and any(e["code"] == "ACT_MISMATCH" for e in report["errors"])` after `lock["shots"][0]["act"] = "not-the-pack-act"` (`test_bpm_snap_copied_and_act_checked`).  
Why: The card only requires copying `bpm`, `snap`, `act` from the lock into each shot row. It does not define an `ACT_MISMATCH` error. A card-compliant implementation copies the act and keeps the sheet, so this assertion demands behavior outside the card and cannot pass.  
Fix: Remove the act-mismatch assertion; keep only the `bpm`/`snap` copy assertion (rename the test to `test_bpm_snap_copied` if desired).

VERDICT: FIX-FIRST