**Defects**

1. **`test_handles_legal` is tautological.**  
   `write_timeline_lock.py:130` builds the lock rows from `core.plan_shots`, and `test_handles_legal` calls `v4._plan_handles` with the same `pf`, `ed`, `seam` values that were just produced by the lattice step. The test therefore cannot fail: any lattice output is automatically consistent with itself. It never validates the H3 handle rules independently (e.g. that `pf` is in 107..345, `(pf-5)%17==0`, or that the seams are legal).  
   **Fix:** compute the expected `pf`/`seam` independently (e.g. from `v4.fit_lattice` or fixed constants) and assert `_plan_handles` rejects invalid combinations, or replace the test with a direct call to `v4._plan_handles` using hand-picked bad inputs.

2. **`test_handles_legal` does not cover the card’s `end_frame_position` rule.**  
   The card requires `end_frame_position = trim_out_frame - 1`. The test asserts it, but only because `plan_shots` already sets it that way. The assertion is a copy of the implementation, not a check of the card requirement. (No independent oracle exists.)

3. **`test_non_snap_mid_act_refused` does not test the card’s “last shot of its act” escape.**  
   The card allows a non-snap shot with `bpm ∉ {None,60}` if it is the last shot of its act. The test only checks the mid-act refusal; it never verifies that a trailing non-snap shot with `bpm=128` is accepted. (This is a missing test name from the card.)

4. **`test_versioned_never_replaced` diff assertion is order-sensitive but the diff is unsorted.**  
   `write_timeline_lock.py:162` collects changes in `diff_locks` order (reel order), but the test expects exactly `[{"id":"S2",...}]`. If multiple shots changed, the list order would not match the expected literal. (Minor, but fragile.)

5. **`test_wav_byte_change_is_stale` and `test_params_change_is_stale` do not verify the `inputs` list contains the params file.**  
   The card requires the params file to be an input so that a param change makes the lock stale. The tests only mutate the params file and expect `StaleLockError`; they never assert the params file is present in `lock["inputs"]`. (Missing coverage of the card requirement.)

6. **`test_silent_shot_needs_min_seconds` uses `narr={}` but the row still has `bpm=None, snap=False`; `plan_lock` does not reject a silent shot with an invalid `snap`/`bpm` combination.**  
   The card says a shot with no lines and no `min_seconds` must raise. The test passes, but the row’s `snap=False` with `bpm=None` is allowed by `EXEMPT_BPM`; the test does not check that a silent shot with `snap=True` (which would need a bpm) is also rejected. (Edge case not covered.)

**Fixes**

- For defect 1: rewrite `test_handles_legal` to call `v4._plan_handles` with independently chosen `pf`/`ed`/`seam` values, including invalid ones, and assert the expected problems.
- For defect 3: add a test `test_non_snap_last_shot_of_act_ok` with a 128 BPM non-snap shot as the last of its act, asserting no `SystemExit`.
- For defect 4: sort the diff by `id` before writing, or make the test order-insensitive.
- For defect 5: add `assert params_path in lock["inputs"]` after loading the lock.
- For defect 6: add a test for a silent shot with `snap=True` expecting `SystemExit`.

VERDICT: FIX-FIRST