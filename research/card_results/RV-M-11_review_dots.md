The code implements the M-11 card but contains a critical logic error that causes the chain check to fail on every valid clip, violating the requirement "SSIM >= 0.90" for the chain check. The faulty line is in `chain_check`:

```python
ssim = float(image_gates.block_ssim(_rgb8(first), _rgb8(prev), np.ones(first.shape, dtype=bool)))
```

The function `block_ssim` expects a boolean validity mask of shape `(H, W)` (2D), but `np.ones(first.shape, ...)` creates a 3D mask of shape `(H, W, 3)` because `first` is a 3-channel RGB image. This shape mismatch will cause `block_ssim` to either crash or return an incorrect result, failing the chain check on identical frames (as seen in `test_chain_same_frame_passes`).

The fix is to use a 2D mask matching the spatial dimensions of the frames:

```python
ssim = float(image_gates.block_ssim(_rgb8(first), _rgb8(prev), np.ones(first.shape[:2], dtype=bool)))
```

VERDICT: FIX-FIRST