Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything else byte-identical; do not add code that reads files at import time.

CARD:
**X-14 | clip_qa.py (frame extractor + clip_gates inside the lock window + clip_qa.json)**
- **Files:** `director/clip_qa.py` NEW; `director/test_clip_qa.py` NEW.
- **Change:**
  - `extract(clip, trim_in, trim_out, size=(192,336), run=subprocess.run) -> np.ndarray[F,H,W] float32 0..1`:
    - `ffmpeg -v error -i clip -vf "select='between(n\,TI\,TO-1)',scale=192:336,format=gray" -vsync 0 -f rawvideo -pix_fmt gray -`.
    - Frame count must equal `trim_out - trim_in`, else ClipQAError.
  - `features(frames, key_a, key_b)` →
    - `flow_p95` = 95th percentile of abs diff of consecutive frames;
    - `sim_to_a` per frame (image_gates.block_ssim);
    - end metrics against B (`end_frame_pass` inputs ssim/lpips/cosine: lpips not available → pass `lpips=0.0` and record "lpips not measured");
    - flicker (clip_gates.flicker_score on every 2nd frame).
  - `new_classes`: `clip_review.json` (counts per sampled frame, every 6th frame per rule 33; written by the reviewer like keyframe_review) is checked against `blocking.known_classes(sheet)`. Any class not known is new. Do not use clip_gates.new_object_classes's own learned set (clip_gates.py:82-93).
  - Audio: `score.sfx_study.find_hits(audio, 48000)` + `match_cues(hits, sheet sound_cues)` give `sfx_keep: [(t0,t1)]` and `bed_db` (sfx_study.py:142, 248). Import functions only; never call `main` (its constants point at reel 1).
  - `verdict = clip_gates.verdict({tail, end, cuts, new_classes, flicker, flicker_limit})` (D-CLIP requires all keys).
  - Writes `<results>/<SHOT>/clip_qa.json {clip_sha256, window: [ti,to], results, verdict, sfx_keep, bed_db, owner_accept: null}`.
  - CLI `accept --shot S --code NEW_OBJECT --note ...` records `owner_accept {code, date, note}`.
  - `clip_ok(path, clip) -> problems`: sha mismatch, or verdict fail without owner_accept.
- **Tests:**
  - `test_extract_window_count`: lavfi `testsrc=size=768x1344:rate=24:duration=7.6667` (184 frames), ti 8, to 176 → **168** frames.
  - `test_snake_not_known_blocks`.
  - `test_owner_accept_unblocks_and_is_recorded`.
  - `test_sha_mismatch_blocks`.
  - `test_sfx_keep_matches_cue` (synthetic click at 2.0 s, cue t 2.1 → kept, tol 0.4).
- **Closes:** 37, 40 (data for the policy). Bug: verdict({}) passes; owner overrides not recorded (reverse-engineering row 7).
- **Depends on:** X-03, D-CLIP, D-LOCK.
- **Collision:** none.
- **Acceptance:** `python -m pytest director/test_clip_qa.py -q`
- **OWNER DECISION:** clip_review by reviewer vs detector; owner_accept record format (default above).
- **Second-attempt risk:** med.



REVIEW BY LUNA:
`new_classes` accepts arbitrary JSON object values as per-frame class counts and silently assumes every value is a mapping. If `clip_review.json` is missing or malformed, QA crashes; more importantly, the test does not verify the required every-sixth-frame sampling rule. The card says the reviewer writes sampled-frame counts, so this module need not enforce sampling? But named test requirement only five. The supplied snake test uses frame IDs 0 and 6, checking class detection, not that sampling is enforced. Card explicitly says clip_review is written by reviewer like keyframe_review, so no requirement QA validates sample intervals. Thus no defect.

Other meaningful: ACCEPT_CODES `NEW_OBJECT` legacy and clip gates code is NEW_CLASS; accept check not tied to actual verdict failure. Requirement "accept --code NEW_OBJECT" records; owner override doesn't state validation. fine.

Question exact verdict. tests listed all present. test name test_owner... exact. Okay. Could point empty/short audio failure, acceptable ClipQAError. `features` with 1 frame ValueError but gate requires tail minimum anyway, crash path maybe malformed input. Not card.

Maybe workflow runs tests? User says review, no. final one line verdict only terminal. Could say OK. Maybe exact one line end. No findings. Our final answer only VERDICT. Could better no issues. Exactly one line.

REVIEW BY DOTS:
**REAL DEFECTS FOUND**

1. **`test_extract_window_count` uses wrong scale (size=(192,336) vs 768x1344) — cannot pass**
   - Faulty line: `assert frames.shape == (168, 336, 192), f"Unexpected shape: {frames.shape}"`
   - The test generates a 768x1344 clip, but `extract` scales to 192x336. The expected shape should be `(168, 336, 192)` — that is correct. Wait, the card says `size=(192,336)`, so the output should be (H=336, W=192). The test asserts `(168, 336, 192)` which matches. So this is actually correct. No defect here.

2. **`test_snake_not_known_blocks` asserts exact reasons list, but `clip_gates.verdict` may return additional reasons**
   - Faulty line: `assert [r["code"] for r in verdict["reasons"]] == ["NEW_CLASS"]`
   - If `clip_gates.verdict` returns multiple reasons (e.g., `["NEW_CLASS", "FLICKER"]`), this test fails even if the verdict is correctly failing. The test should only check that `"NEW_CLASS"` is in the reasons, not that it is the only one. This makes the test brittle and potentially false-negative.

3. **`test_owner_accept_unblocks_and_is_recorded` uses `NEW_OBJECT` but `accept` does not verify it matches the verdict reason**
   - Faulty line: `clip_qa.accept(shot, "NEW_OBJECT", "test note", root=str(tmp_path))`
   - The card says: `owner_accept {code, date, note}` and the CLI uses `--code NEW_OBJECT`. However, in `accept()`, the code is stored as-is without checking if it corresponds to the actual failure reason in the verdict. The function comment says: "ponytail: accept is not checked against the verdict reasons". This is a known gap, but the test does not cover the requirement that the code must match the verdict reason. The card implies that the code should be one of the failing reasons (e.g., `NEW_CLASS`), but the test uses `NEW_OBJECT` which is not in the verdict reasons (`[{"code": "NEW_CLASS", ...}]`). This is a mismatch: the test accepts a code that is not in the verdict reasons, which may be allowed by the code but is semantically incorrect per the card's intent.

4. **`test_sfx_keep_matches_cue` checks `abs(t0 - 2.0) < 0.4`, but `sfx_keep` uses `HIT_WINDOW = (-0.05, 0.25)`**
   - Faulty line: `if abs(t0 - 2.0) < 0.4:`
   - The card says: `match_cues(hits, sheet sound_cues)` and `sfx_keep: [(t0,t1)]` with `HIT_WINDOW = (-0.05, 0.25)`. So `t0 = hit_time - 0.05`, `t1 = hit_time + 0.25`. For a hit at 2.0s, `t0 = 1.95`, `t1 = 2.25`. The test checks `abs(t0 - 2.0) < 0.4` which is `|1.95 - 2.0| = 0.05 < 0.4` → passes. But the card says "tol 0.4" for matching the cue. The cue is at 2.1s, and the hit is at 2.0s. The tolerance should be on the cue time, not the hit time. The test is checking the hit time (2.0) against the kept interval start (t0=1.95), which is correct. However, the card says: "synthetic click at 2.0 s, cue t 2.1 → kept, tol 0.4". This means the cue at 2.1s should match the hit at 2.0s within 0.4s tolerance. The test does not verify that the cue was matched; it only checks that there is a kept interval near 2.0s. It does not check that the cue at 2.1s was actually used. This is a weak test: it does not verify the matching logic, only that some interval exists.

5. **`test_extract_frame_count_mismatch_raises` uses `pytest.raises(clip_qa.ClipQAError)` but `extract` may raise `subprocess.CalledProcessError`**
   - Faulty line: `with pytest.raises(clip_qa.ClipQAError):`
   - If `ffmpeg` fails (e.g., because the clip is too short), `subprocess.run(..., check=True)` raises `subprocess.CalledProcessError`, which is not caught and converted to `ClipQAError` in all paths. The `try-except` in `extract` catches `subprocess.CalledProcessError` and raises `ClipQAError`, so this is actually handled. No defect.

6. **`test_clean_clip_has_no_problems` does not test `clip_ok` with a passing verdict and matching sha — it does, but it uses a hardcoded verdict with `"accepted": []` which is not used by `clip_ok`**
   - Faulty line: `"verdict": {"pass": True, "reasons": [], "accepted": []}`
   - The `clip_ok` function only checks `verdict.get("pass") is not True` and `owner_accept is None`. It does not check `"accepted"`. So this is fine.

7. **`test_accept_rejects_unknown_code` tests that `accept` raises for unknown codes, but the card says `ACCEPT_CODES = set(clip_gates.CLIP_CODES) | {"NEW_OBJECT"}` — the test uses `MADE_UP_CODE` which is not in `ACCEPT_CODES`, so it should raise. This is correct.**

**Most critical issue:**
The test `test_snake_not_known_blocks` is brittle because it asserts an exact list of reasons. If `clip_gates.verdict` returns more than one reason (e.g., due to flicker or other checks), the test fails even though the verdict is correctly failing due to `NEW_CLASS`. This is a test that cannot fail in the intended way — it fails for the wrong reason.

Additionally, `test_owner_accept_unblocks_and_is_recorded` uses `NEW_OBJECT` which is not in the verdict reasons (`NEW_CLASS`). The card says the code should be `NEW_OBJECT` for new classes, but the verdict reason is `NEW_CLASS`. The `accept` function does not validate this, so the test passes, but it is semantically inconsistent.

**Fix for test_snake_not_known_blocks:**
Change:
```python
assert [r["code"] for r in verdict["reasons"]] == ["NEW_CLASS"]
```
to:
```python
assert "NEW_CLASS" in [r["code"] for r in verdict["reasons"]]
```

**Fix for test_owner_accept_unblocks_and_is_recorded:**
Change:
```python
clip_qa.accept(shot, "NEW_OBJECT", "test note", root=str(tmp_path))
```
to:
```python
clip_qa.accept(shot, "NEW_CLASS", "test note", root=str(tmp_path))
```
to match the verdict reason.

VERDICT: FIX-FIRST