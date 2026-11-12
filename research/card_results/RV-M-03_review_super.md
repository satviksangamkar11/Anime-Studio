1. Missing card-listed test name.
Faulty line: `def test_one_camera_sentence_from_enum_and_locked_default():` (h3/tests/test_opus_examples.py); there is no `def test_one_camera_sentence():`.
Why: The card requires a test named `test_one_camera_sentence`. A differently named test does not cover that listed test name.
Fix: Rename the function to `def test_one_camera_sentence():` (keep the same assertions) so the card-listed test name exists.

2. `_stages` hard-codes stage 1 to `0.0` and ignores `beats` for the first stage.
Faulty line: `pt = 0.0 if k == 0 else max(prev_pt + 0.5, float(_time_point(inside[0] if inside else a / FPS)))` (h3/v4_to_h3.py, `_stages`).
Why: When the sheet has beats, the first stage’s time point must be derived from `beats[].t`; the code forces `0.0` for `k == 0` even when a beat falls inside the first span.
Fix:
```
base = inside[0] if inside else (0.0 if k == 0 else a / FPS)
pt = float(_time_point(base)) if k == 0 else max(prev_pt + 0.5, float(_time_point(base)))
```

3. `_camera_from_sheet` crashes on an unmapped `camera.move`.
Faulty line: `motion, clause = CAMERA_MOVE_CLAUSES[cam.get("move")]` (h3/v4_to_h3.py, `_camera_from_sheet`).
Why: A `camera.move` value absent from `CAMERA_MOVE_CLAUSES` raises `KeyError` instead of falling back to the locked camera sentence the card permits ("or 'The camera stays locked.'").
Fix: `motion, clause = CAMERA_MOVE_CLAUSES.get(cam.get("move"), CAMERA_MOVE_CLAUSES[None])`

VERDICT: FIX-FIRST