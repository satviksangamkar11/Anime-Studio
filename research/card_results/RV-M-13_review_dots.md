The following real defects are found in `director/chain_step.py` and `director/test_chain_step.py`:

**1. `chain_step.py` line 102: `prepare_chain` calls `last_kept_frame` with positional `out_png` instead of using the computed `chain_png_path`.**
The function ignores the `pack` and `shot_id` arguments for the output path. It writes the last frame to a literal file named `"chain"` inside the current working directory, then returns that path. The card requires `<pack>/chain/<SHOT>-last.png`. The test only checks the returned path string and the existence of the file at that path; it never verifies that the file is inside `pack/chain/`. A caller using a different working directory gets the wrong file location, and the `pack`/`shot_id` arguments are silently unused.

Fix:
```python
def prepare_chain(clip, kept_frames: int, pack, shot_id: str, depth: int, state: str, size=RENDER_SIZE) -> dict:
    check_depth(depth)
    png = last_kept_frame(clip, kept_frames, chain_png_path(pack, shot_id), size=size)
    return {"png": png, "depth": depth, "header": chain_header(state)}
```

**2. `test_chain_step.py` line 167: `test_prepare_chain_writes_png_and_returns_header` asserts `res["png"] == pack / "chain" / "SHOT-003-last.png"` but the module writes to a file literally named `"chain"` in the current directory. The test cannot fail because the assertion is on the returned value, not on the actual filesystem location. It also does not assert that `pack/chain/SHOT-003-last.png` exists. The test is tautological with respect to the card requirement.**

Fix: Add an assertion that the expected pack-relative path exists:
```python
    assert res["png"] == pack / "chain" / "SHOT-003-last.png" and res["png"].is_file()
    assert (pack / "chain" / "SHOT-003-last.png").exists()
```

**3. `chain_step.py` lines 84-85: `last_kept_frame` uses `select=eq(n\,{kept_frames-1})` which selects by input frame index `n`, but the card says “the last KEPT decoded frame after trim”. If the clip has been trimmed (e.g. first 10 frames removed), the input frame index `n` no longer corresponds to the kept-frame count. The function silently extracts the wrong frame. The test clips are full untrimmed clips, so this is not covered.**

Fix: Use a trim-aware select, for example:
```python
    _run(["-i", str(clip), "-vf", f"trim=start_frame={trim_start}:end_frame={trim_start+kept_frames},select=eq(n\\,{kept_frames-1}),scale={w}:{h}", "-frames:v", "1", str(out_png)])
```
or document that `clip` must be the already-trimmed input and `kept_frames` counts frames in that trimmed clip.

VERDICT: FIX-FIRST