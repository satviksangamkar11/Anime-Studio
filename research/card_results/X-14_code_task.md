Implement this gap card by editing ONLY the allowed module files; the test file director/test_clip_qa.py is frozen (do not touch it). Keep everything else byte-identical.

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

