**Defect 1 — `test_mix_one_frame_short_refused` is tautological and does not test the card's refusal rule.**

The test constructs a WAV that is one frame short (`NEED - 2000` samples) and expects `SystemExit`. However, `intake()` pads short inputs to `need` samples via the `fit` lambda (line 306 in `build_final_reel.py`):
```python
fit = lambda arr: arr[:need] if arr.shape[0] >= need else np.vstack([arr, np.zeros((need - arr.shape[0], arr.shape[1]))])
```
Because the missing 2000 samples are silently zero-filled, the function proceeds to the level checks and only fails if the levels are out of range. The test does not assert that the "short" refusal path is taken; it would pass even if the length check were completely removed. The card requires: "Length < need − 1 → refuse ('mix N samples short')".

**Fix:** Remove the padding in `intake` for inputs shorter than `need - 1` and raise `SystemExit` with the exact shortfall message before any processing. Then the test will correctly fail if the check is missing.

**Defect 2 — `test_mix_one_frame_short_refused` uses a sine wave that violates the level gate, masking the length check.**

Even if the length check were fixed, the test uses `sine(n, 0.55)` for mix and `sine(n, 0.5)` for voice. Because both signals are identical sine waves in phase, the bus (`mix - voice`) is a sine wave of amplitude `0.05`. The voice-over-bus ratio over the 1-second window is `20*log10(0.5 / 0.05) ≈ 20 dB`, which is inside the `[15, 21.5]` median range and above the `12 dB` minimum. This means the test would still pass after the length check is fixed, but it does not isolate the length check from the level check.

**Fix:** Use non-sine signals (e.g., white noise or DC offsets) that pass the level gate so that the only reason for `SystemExit` is the length check. Alternatively, split the test into two: one for length refusal with valid levels, and one for level refusal.

---

**Defect 3 — `test_mix_long_trimmed_to_960000` does not verify the trimmed content.**

The test only checks that the output WAV has `NEED` frames and the correct rate. It does not verify that the trim actually took the *first* `NEED` samples (the card says "trimmed copy of exactly `need` samples"). If the code accidentally took the last `NEED` samples or padded, the test would still pass.

**Fix:** Write a known pattern (e.g., a ramp or distinct sine) to the mix, then read back the trimmed file and assert that the first `NEED` samples match the input's first `NEED` samples.

---

**Defect 4 — `test_next_version_r3_and_r1_untouched` leaves a stray file in `tmp_path`.**

The test writes `kalika_x_en_r7.mp4` to `tmp_path` but never cleans it up. While `tmp_path` is isolated, this is untidy and could interfere with parallel test runs if the fixture is reused.

**Fix:** Add a `tmp_path cleanup` or use a subdirectory that is explicitly removed.

---

**Defect 5 — `test_low_disk_refused` does not test the default `min_gb` parameter.**

The test calls `check_free_disk` with `min_gb=2.0` explicitly, but the card says the default is `MIN_FREE_GB_EXPORT * 2**30`. The test should also verify that calling `check_free_disk` without `min_gb` uses the default.

**Fix:** Add a call to `b.check_free_disk(tmp_path, disk_usage=low)` (without `min_gb`) and assert it raises `SystemExit`.

---

VERDICT: FIX-FIRST