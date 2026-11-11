# Nemotron Super review of S-08 (rule 55), supervisor test run: 51 passed in 0.37s

ROWS:
Files: director/runner_safety.py director/test_runner_safety.py: PASS
preflight(urls, disk_path, *, min_free_gb, script_path, max_script_mb=7.0: FAIL: row claims signature has `max_script_mb=7.0`, but code line `def preflight(urls, disk_path, *, min_free_gb, script_path, part_paths=(), max_part_mb=3.0,` has no `max_script_mb` and no script-size check (in-code comment: owner decision 6 removed the cap). Other sub-claims (no-default min_free_gb/script_path, empty urls → ValueError, parts ≤ 3 MB) hold.
A HEAD that returns 405: PASS
clip_verified(results_dir, shot_id, expected_frames, probe_frames=None, exists=None, size=None): PASS
Skips *.part.mp4 and *.tmp.mp4.: PASS
Requires probe_frames(entry) == expected_frames. The default: PASS
The injected path also runs the folder-containment: PASS
can_stop and stop_decision take expected_frames: PASS
test_part_over_3mb_fails: PASS
test_script_path_required: PASS
test_empty_urls_refused: PASS
test_head_405_get_206_ok: PASS
test_wrong_frame_count_not_verified: probe 100 vs: PASS
test_part_file_ignored: PASS
test_injected_escape_refused: PASS
Update the existing tests for the new signature: PASS
Depends on: none. Shared files: none.: PASS
Acceptance: python -m pytest director/test_runner_safety.py -q: PASS
No reel 1 file is edited or opened: PASS
No network, Colab, ElevenLabs, renderer or paid: PASS
Every changed .py file parses (ast.parse): PASS
The card's acceptance command was run and: PASS
Nothing was deleted from the existing tests: PASS
One log line was appended to D:/aai: PASS

UNTICKED:
**Change:** — section header only; acceptable (sub-rows carry the requirements).
test_11_3mb_script_fails (11.3 MB > 7.0) — acceptable to leave unticked: owner decision 6 removed the script cap, so no "script fails" test; `test_11_3mb_script_ok_in_parts` exists and passed instead.
**Tests:** — section header only; acceptable.
**Problems:** … / **Waits on:** D8b, D10. / **Second-attempt risk:** low … — informational/dependency notes; acceptable.
Only the files named in this card were changed … — not verifiable from supplied material; acceptable as process (no evidence of other changes).
Every test named in the card exists, was run, and passed … — acceptable: all 51 passed and the named card tests appear in the run list.

MISSING: none. (The script cap was intentionally removed per the in-code owner decision 6; the stale ticked claim is flagged FAIL above rather than treated as a missing feature.)
BAD: NONE
VERDICT: BACK-TO-CODER (failing row: preflight signature — `max_script_mb=7.0` claimed but absent; code intentionally omits it per owner decision 6, so correct the stale checklist row rather than the code).
