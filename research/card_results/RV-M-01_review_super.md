Defect 1 — missing required tests (card requirement not met).

h3/tests/test_prompt_wiring.py: (absent) the card requires `test_sx_min_zero_no_stage_error` and `test_mo01_accepts_mouth_sentence`; neither test exists in the file.

Why: the card explicitly lists these test names as additions. `python -m pytest h3/tests -q` cannot verify that `SX_MIN_STAGE_CUES = 0` removes the stage error, nor that MO-01 accepts `prompt_hygiene.mouth_sentence`, so those requirements are unverified.

Fix: add `test_sx_min_zero_no_stage_error` and `test_mo01_accepts_mouth_sentence` to `h3/tests/test_prompt_wiring.py`.

Defect 2 — `_soundscape` violates the mandated single-cue format.

h3/v4_to_h3.py:
```python
                labelled = [items[0] if n == 1 else
                            (f"First {items[0]}" if i == 0 else f"finally {text}" if i == n - 1 else f"then {text}")
                            for i, text in enumerate(items)]
```

Why: the card specifies the packing pattern as "First <cue>; then <cue>; finally <cue>."; with exactly one cue the branch `items[0] if n == 1` emits the bare cue without the required "First" prefix, producing a wrong result for n == 1.

Fix: remove the `items[0] if n == 1 else` special case so the first cue is always labelled "First":
```python
                labelled = [f"First {items[0]}" if i == 0 else f"finally {text}" if i == n - 1 else f"then {text}"
                            for i, text in enumerate(items)]
```

VERDICT: FIX-FIRST