The test `test_lock_wins_over_row_seam_and_input_unchanged` asserts that the lock’s `outgoing_seam_type` for shot 1 is `"DYNAMIC_MATCH_ON_ACTION"` (line 158) and that the shot in the story carries that value (line 159). The lock is built by `wtl.plan_lock`, which in turn relies on `_seam_defaults` in `h3/v4_to_h3.py`. For a first shot of a reel with `ed < pf`, `_seam_defaults` returns `DYN` (line 311), but the schema’s canonical name for that seam is `"DYNAMIC_MATCH_ON_ACTION"`, not `"DYNAMIC"` (see `SEAM_TYPES` in `schema_and_linter.py`). Because the lock writes the raw enum value, the lock and the story end up with a seam string that is not in `SEAM_TYPES`, so `lint_story` will reject it and downstream consumers will not recognise the seam. The seam type written into the lock must be the schema’s canonical string.

**Faulty line:** `h3/v4_to_h3.py`, line 311 (inside `_seam_defaults`):
```python
out = INTER if is_last else (DYN if ed < pf else CHAINED)
```

**Fix:** Replace `DYN` with the canonical seam name `"DYNAMIC_MATCH_ON_ACTION"`:
```python
out = INTER if is_last else ("DYNAMIC_MATCH_ON_ACTION" if ed < pf else CHAINED)
```
(The same change must be applied to the `inc` assignment on the line above to keep the incoming seam consistent.)

VERDICT: FIX-FIRST