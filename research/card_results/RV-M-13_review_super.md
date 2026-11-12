Defect 1 — `prepare_chain` never verifies the seam, though the card requires it.

Faulty lines:
```python
def prepare_chain(clip, kept_frames: int, pack, shot_id: str, depth: int, state: str, size=RENDER_SIZE) -> dict:
    """The chain step after an accepted clip: refuse depth > 2, write <pack>/chain/<SHOT>-last.png from the last kept
    frame, return {"png", "depth", "header"}. Nothing is written when the depth is refused."""
    check_depth(depth)
    png = last_kept_frame(clip, kept_frames, chain_png_path(pack, shot_id), size=size)
    return {"png": png, "depth": depth, "header": chain_header(state)}
```
Why wrong: The card requires the chain step to verify frame 0 of the next clip against the saved PNG (SSIM >= 0.90). `prepare_chain` never calls `verify_seam`, accepts no `next_clip`, and returns without enforcing the seam gate.
Exact fix:
```python
def prepare_chain(clip, kept_frames: int, pack, shot_id: str, depth: int, state: str, next_clip, size=RENDER_SIZE) -> dict:
    """The chain step after an accepted clip: refuse depth > 2, write <pack>/chain/<SHOT>-last.png from the last kept
    frame, verify frame 0 of next_clip against it, return {"png", "depth", "header", "seam"}."""
    check_depth(depth)
    png = last_kept_frame(clip, kept_frames, chain_png_path(pack, shot_id), size=size)
    first = first_frame(next_clip, chain_png_path(pack, shot_id).with_name(shot_id + "-next-first.png"), size=size)
    seam = verify_seam(png, first)
    if not seam["ok"]:
        raise ChainError(f"seam SSIM {seam['ssim']} below {seam['min_ssim']}")
    return {"png": png, "depth": depth, "header": chain_header(state), "seam": seam}
```

Defect 2 — `last_kept_frame` crashes with `subprocess.CalledProcessError` instead of `ChainError` when `kept_frames` is out of range.

Faulty lines:
```python
    _run(["-i", str(clip), "-vf", f"select=eq(n\\,{kept_frames - 1}),scale={w}:{h}", "-frames:v", "1",
          str(out_png)])
    if not out_png.is_file():
        raise ChainError(f"no frame {kept_frames - 1} in {clip}")
```
Why wrong: If `kept_frames` exceeds the clip length, ffmpeg exits non-zero and `_run` raises `subprocess.CalledProcessError` before the `is_file` check. The caller gets an unhandled crash instead of the documented `ChainError` refusal for “no kept frame”.
Exact fix:
```python
    try:
        _run(["-i", str(clip), "-vf", f"select=eq(n\\,{kept_frames - 1}),scale={w}:{h}", "-frames:v", "1",
              str(out_png)])
    except subprocess.CalledProcessError as exc:
        raise ChainError(f"no frame {kept_frames - 1} in {clip}") from exc
    if not out_png.is_file():
        raise ChainError(f"no frame {kept_frames - 1} in {clip}")
```

VERDICT: FIX-FIRST