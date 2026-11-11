# Nemotron ultra review of S-07 (rule 55), supervisor test run: 31 passed in 0.05s

ROWS
Files: PASS (both files present)
Change/check_pixel_frames: PASS (imports LATTICE_N_MIN/MAX, validates n range, 22 refused)
Change/image_prompt_type None: PASS (raises "POST shots never reach the batch")
Change/frame_row copies route/strength/efp: PASS (copies route, validates strength None/float(0,1], validates efp int(0,pf), requires efp for SE)
Change/KFI mid/mid_frame: PASS (requires mid and mid_frame with 0<mid_frame<efp)
Tests/pf_22_107_345_362: PASS (tests exist, run, pass)
Tests/post_none_refused: PASS (test exists, runs, passes)
Tests/soft_se_keeps_strength_efp: PASS (test exists, 0.6 and 151 survive)
Tests/kfi_without_mid_raises: PASS (test exists, runs, passes)
Tests/router_rows_accepted: PASS (test exists, runs, passes)
Rewrite tests accepting 22/39: PASS (no test accepts 22/39; test_pf_22_refused present)
Depends on S-06: PASS (acknowledged)
Acceptance command: PASS (31 passed in 0.05s pasted)
Waits on D1/D15: PASS (acknowledged)
No reel 1 edits: PASS (checklist confirmed)
Only named files changed: PASS (checklist confirmed)
No network/paid calls: PASS (checklist confirmed)
Parses/line length: PASS (checklist confirmed)
All named tests exist/run/pass: PASS (31 tests listed, all passed)
No deletions from existing tests: PASS (checklist confirmed)
Log line appended: PASS (checklist confirmed)

UNTICKED
Problems (advances 3, bugs E1/O1/O9/O3): ACCEPTABLE (status field, not a requirement)
Second-attempt risk low: ACCEPTABLE (assessment field, not a requirement)

MISSING: NONE

EXTRA: NONE

BAD: check_pixel_frames lines 47-51 — when remainder % 17 != 0 and below ≤ 5, code hardcodes `above = 22` but 22 is invalid (LATTICE_N_MIN ≥ 6 ⇒ first valid is 107). Misleads users for inputs 0–21. Fix: replace `above = 22` with `above = 5 + 17 * LATTICE_N_MIN`.

VERDICT: BACK-TO-CODER
