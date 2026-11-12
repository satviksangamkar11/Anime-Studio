Defect 1 — Missing required test: router maps S correctly.
Faulty lines: (absence) `h3/tests/test_m02_start_only.py` ends with:
```python
    assert "PR-01" not in found
    assert "KF-06" not in found
```
Why wrong: The card lists “router maps S correctly” as a required test. The file never imports `director.shot_router` and never asserts that route `S` maps to `image_prompt_type == "S"` (and `h3_mode == "I2VA"` via `plan_from_blocking`) when the flag is on, or to SE fallback when off. A broken router mapping cannot fail any test here.
Fix: Add a test that calls `route_shot(features, allow_s=True)` and asserts `result["route"] == "S"` and `result["image_prompt_type"] == "S"`, calls `plan_from_blocking` and asserts `h3_mode == "I2VA"`, and asserts `allow_s=False` yields route `"SE"` with reason `"S not approved: SE fallback"`.

Defect 2 — Missing required test: S settings dry run has image_prompt_type "S" and no end keys.
Faulty lines: (absence) The file tests `shot_mode.frame_row` in `test_s_row_drops_end_keys` but never invokes `build_h3_batch` dry run or inspects a settings file.
Why wrong: The card lists “S settings dry run has image_prompt_type "S" and no end keys” as a required test. Row-level checks do not cover the batch settings writer, so a settings file that still contains `end` / `end_frame_position` for S would pass.
Fix: Add a dry-run test through `build_h3_batch.legacy_rows` (or `main`) that builds an S route and asserts the emitted row/settings has `image_prompt_type == "S"` and no `end` / `end_frame_position` keys.

Defect 3 — Missing required test: compile an S shot golden.
Faulty lines: (absence) The file defines only `FL2VA_GOLDEN` and `test_fl2va_golden_unchanged`; there is no `S_GOLDEN` constant and no hash assertion for `start_only=True` output.
Why wrong: The card lists “compile an S shot golden” as a required test. Without it, regressions in the start-only prompt/workflow layout cannot fail.
Fix: Add `S_GOLDEN` and a test that hashes `compile_fl2va_prompt(sh, reg, start_only=True)` together with `compile_comfyui_workflow(..., start_only=True)` and asserts equality.

Defect 4 — Bad input passes silently: invalid `end_frame_position` is accepted for mode S.
Faulty line:
```python
    if "end_frame_position" in shot and mode == "SE":   # S has no end anchor: the key is dropped, not sent
        row["end_frame_position"] = _check_end_frame_position(shot["end_frame_position"], checked)
```
Why wrong: For mode `S` the key is dropped without calling `_check_end_frame_position`, so a wrongly typed or out-of-range `end_frame_position` passes silently instead of raising `ShotModeError`.
Fix: Validate whenever the key is present, store only for SE:
```python
    if "end_frame_position" in shot:
        checked_efp = _check_end_frame_position(shot["end_frame_position"], checked)
        if mode == "SE":
            row["end_frame_position"] = checked_efp
```

VERDICT: FIX-FIRST