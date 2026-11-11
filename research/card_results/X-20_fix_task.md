Two independent reviewers found problems in the finished gap card below. Fix every finding that is CORRECT (check it against the code first; the Dots review is noisier than the Luna review and may be wrong or describe a line that does not exist: ignore a finding you can show is wrong). For each fixed defect add or strengthen a test in the card's test file so the test fails before the fix. Keep every existing test passing. Edit only the allowed files; keep everything else byte-identical; do not add code that reads files at import time.

CARD:
**X-20 | stem_builder −14 → named audition constant**
- **Files:** `score/stem_builder.py`; `score/tests/test_loudness_targets.py` NEW.
- **Change:**
  - `AUDITION_NODUCK_LUFS = -14.0  # music-only audition file, not a deliverable (log 11-09 17:23)`.
  - stem_builder.py:503 `write_noduck(..., target_lufs=AUDITION_NODUCK_LUFS)`; output file name gets the suffix `_audition`.
  - If the owner chooses "one target": use `load_core()["delivery"]["audio"]["lufs"]` instead.
- **Tests:** `test_only_audition_constant_is_minus_14`: an AST scan of director/, h3/, score/ (non-test files) finds the literal −14.0 only in stem_builder's AUDITION_NODUCK_LUFS. `test_deliverables_use_core`: gate_d LOUDNESS target equals core.json lufs.
- **Closes:** 42.
- **Depends on:** none.
- **Collision:** none.
- **Acceptance:** `python -m pytest score/tests/test_loudness_targets.py -q`
- **OWNER DECISION:** confirm −14 audition-only (reverse-engineering F, downgraded).
- **Second-attempt risk:** low.

---



REVIEW BY LUNA:
`stem_builder.py` calls `write_noduck` without the card’s required explicit target:

```python
nd_mp3, nd_before, nd_after, nd_gain = write_noduck(noduck, total, v)
```

Pass the named constant at the call site:

```python
nd_mp3, nd_before, nd_after, nd_gain = write_noduck(
    noduck, total, v, target_lufs=AUDITION_NODUCK_LUFS
)
```

VERDICT: FIX-FIRST.

REVIEW BY DOTS:
**Defects found**

1. **`test_only_audition_constant_is_minus_14` is tautological and cannot fail on the constant itself.**  
   The helper `_is_negative_float_literal(node, value=14.0)` accepts both `-14.0` *and* `+14.0` (positive 14.0) because the `UnaryOp` branch only checks for `USub`, but the `Constant` branch does not require the value to be negative. A positive literal `14.0` anywhere in the scanned files would satisfy the check, making the test pass even if the audition constant were incorrectly set to `+14.0`.  
   **Fix:** In `_is_negative_float_literal`, require `node.value == -value` for the `Constant` branch (or remove the `Constant` branch entirely and only accept `UnaryOp` with `USub`).

2. **`test_deliverables_use_core` does not verify the card's requirement that the one-target path uses `load_core()`.**  
   The card states: *If the owner chooses "one target": use `load_core()["delivery"]["audio"]["lufs"]` instead.* The test only checks that `LOUDNESS["target_lufs"]` equals the value in `core.json`; it never exercises or inspects the code that calls `load_core()`. A change that hard-codes the value (e.g., `target_lufs = -23.0`) would still pass.  
   **Fix:** Add an AST scan (similar to the first test) to confirm that `h3/shot_table_spec.py` contains a subscript chain `load_core()["delivery"]["audio"]["lufs"]` (or equivalent) used to set `LOUDNESS["target_lufs"]`.

VERDICT: FIX-FIRST