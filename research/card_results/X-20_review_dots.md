**Defects found**

1. **`test_only_audition_constant_is_minus_14` is tautological and cannot fail on the constant itself.**  
   The helper `_is_negative_float_literal(node, value=14.0)` accepts both `-14.0` *and* `+14.0` (positive 14.0) because the `UnaryOp` branch only checks for `USub`, but the `Constant` branch does not require the value to be negative. A positive literal `14.0` anywhere in the scanned files would satisfy the check, making the test pass even if the audition constant were incorrectly set to `+14.0`.  
   **Fix:** In `_is_negative_float_literal`, require `node.value == -value` for the `Constant` branch (or remove the `Constant` branch entirely and only accept `UnaryOp` with `USub`).

2. **`test_deliverables_use_core` does not verify the card's requirement that the one-target path uses `load_core()`.**  
   The card states: *If the owner chooses "one target": use `load_core()["delivery"]["audio"]["lufs"]` instead.* The test only checks that `LOUDNESS["target_lufs"]` equals the value in `core.json`; it never exercises or inspects the code that calls `load_core()`. A change that hard-codes the value (e.g., `target_lufs = -23.0`) would still pass.  
   **Fix:** Add an AST scan (similar to the first test) to confirm that `h3/shot_table_spec.py` contains a subscript chain `load_core()["delivery"]["audio"]["lufs"]` (or equivalent) used to set `LOUDNESS["target_lufs"]`.

VERDICT: FIX-FIRST