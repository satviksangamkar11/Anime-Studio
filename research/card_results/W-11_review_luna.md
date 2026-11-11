- `director/run_colab_batch.py:277-278` calls `rs.preflight` without the card’s required `max_script_mb=7.0` gate. As written, an oversized `run.py` can pass preflight if its upload parts pass. Add the 7.0 MiB script-size check and pass the required argument to `preflight`.

- `director/run_colab_batch.py:237` excludes any requirement line containing the substring `"win32"`, even when it lacks `sys_platform == "win32"`. That can silently skip a URL that must be checked. Exclude only lines whose environment marker specifies `sys_platform == "win32"`.

- The required regression tests are missing or renamed: there is no `test_11_3mb_script_fails`, `test_head_504_blocks_dry_run`, or `test_all_done_verified_stops`; the supplied file has `test_head_504_blocks` and `test_all_done_verified_stops_then_checks_sessions` instead. Add the named tests, with the 11.3 MiB script case asserting `"script too large"`.

- `director/test_run_colab_batch_w11.py:406` checks that the download path is merely present in `sent`. The card requires the download argument to equal the specified path. Assert `sent == [f"{t0.OUT}/SHOT-001/Picture 1 0.mp4"]`.

VERDICT: FIX-FIRST.