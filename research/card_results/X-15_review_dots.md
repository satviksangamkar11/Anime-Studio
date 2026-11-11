**Defects**

1. **`test_offsets_from_lock` is tautological / cannot fail.**  
   `test_build_final_reel_lock.py` (line ~83) monkeypatches `gd.build_mix_filter` to a `spy` that records the `sfx` list, then asserts `seen["sfx"]` has the expected offsets. But `mux_argv` (line ~117) builds that list **from the lock rows’ `offset_sec`/`editorial_duration_sec` directly**; the `spy` is only called *after* the list is already constructed, so the assertion verifies nothing about whether `mux_argv` actually used the lock values. It would pass even if the code summed floats.  
   **Fix:** do not monkeypatch `gd.build_mix_filter`. Instead, monkeypatch `gd.build_final_mux_argv` (or `subprocess.run`) and inspect the real filter string / argv that `mux_argv` returns for the actual offset values.

2. **`test_missing_vo_with_lines_raises` does not test the reported condition.**  
   It creates `vo_dir/hi` (the *language* folder) but never creates a `vo_tracks_report.json` in `vo_dir`. `mux_argv` itself does not look for that report, so the test exercises only the “missing WAV” path — it does not verify that a shot with lines raises when the WAV is absent *while* the report exists. The test name promises coverage that is not delivered.  
   **Fix:** write a minimal `vo_tracks_report.json` into `vo_dir` before calling `mux_argv`, so the test truly isolates the missing-WAV case.

3. **`test_reel2_no_waivers_blocks_dead_air` is weak (no SystemExit).**  
   It asserts `load_waivers` returns `frozenset()` and that `split_findings` behaves correctly, but `main()` is never called. The card requires that a build with no waivers file **blocks** (exits) on `DEAD_AIR_PAUSE`; this test would pass even if `main` silently printed warnings and returned 0.  
   **Fix:** call `run_main(...)` inside the test and expect `pytest.raises(SystemExit)` when the gate errors contain an unwaived `DEAD_AIR_PAUSE`.

4. **`test_waivers_reel_mismatch_raises` leaves the `waivers.json` on disk for later tests.**  
   The file is written into `tmp_path` (the test’s own scratch dir, so it is isolated), but the test does not clean up; more importantly it asserts `b.load_waivers(tmp_path, "kalika_reel1")` succeeds — this depends on the file still being present and is an accidental cross-test coupling if `tmp_path` were ever shared. Not fatal, but fragile.

5. **`test_stale_lock_blocks` uses a malformed `shots.json` that may not trigger the intended path.**  
   It overwrites `shots.json` with `"[]"`. `lock_rows_for_pack` will then see an empty `pack_rows` dict and the lock rows list will be non-empty, so the id/order check raises `SystemExit` with the message `"lock shots and pack shots.json differ in id or order"`. The test expects `match="lock"`, which matches, but the real X-15 requirement is that a **stale** lock (inputs changed) is refused; writing `"[]"` is a different failure mode. Acceptable, but the test name is misleading.

6. **`test_reel_name_must_match_the_pattern` uses `--reel "Kalika Reel 2"` which contains uppercase and spaces; the regex `^[a-z0-9_]+$` correctly rejects it, but the test does not verify the *specific* error message or that lowercase-with-underscores is accepted. Minor.

7. **`test_clip_qa_owner_accept_passes_and_sha_mismatch_blocks` writes the clip with `owner_accept` set, then immediately overwrites the bytes and re-checks. The `owner_accept` dict in the test uses key `"code"` for the waived finding code, but `clip_qa_problems` (line ~221) reads `qa.get("owner_accept")` only as a presence check (`is None`) and never inspects its contents. If the X-14 contract requires the accepted code to match the failing reason, this is not enforced.**

VERDICT: FIX-FIRST