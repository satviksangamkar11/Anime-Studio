**Defects in `director/story_shape.py`:**

1. **`is_new_format` returns `False` for old packs**  
   `return "premise" in story or any("arc_beat" in r for r in rows)`  
   When `story` is `None`, `"premise" in None` raises `TypeError`. The function must handle a non-dict `story` (e.g., `story = story or {}`).

2. **`lint` always uses `errors` for `SHAPE-02`**  
   `errors.append("SHAPE-02 ...")` is used instead of `add(...)`. On old packs this raises `NameError` (the `add` helper is not defined in that scope) and violates the card’s warning-only rule.

3. **`_narrated` returns `True` for empty narration**  
   `any(bool(v) for v in narr.values())` passes when `narration_by_lang` is `{"en": ""}`. The card requires a narrated reel; empty strings should not count as narration.

4. **`SHAPE-06` uses `payoff < PAYOFF_MIN` instead of `<=`**  
   The test `test_payoff_under_5_seconds_is_error` uses 4.9 s, which fails, but 5.0 s would be allowed. The card says “covers the last >= 5 s”, so the condition should be `payoff <= PAYOFF_MIN`.

5. **`SHAPE-07` uses `>` instead of `>=`**  
   `if not any(d <= SHORT_MAX ...)` and `if not any(d >= CENTRE_MIN ...)` use strict inequalities. The card says “at least one shot <= 4.4 s” and “one centrepiece shot >= 10 s”, so the comparisons should be non-strict.

6. **`SHAPE-08` uses `<=` instead of `<`**  
   `abs(durs[i] - durs[i + 1]) <= METRO_GAP` flags exactly 0.5 s differences as metronome, but the card says “within +-0.5 s”, which is exclusive.

**Defects in `director/test_story_shape.py`:**

7. **`test_old_pack_ten_even_shots_loads_with_warnings_only` is tautological**  
   It asserts `has(warnings, "SHAPE-08")` and `has(warnings, "SHAPE-07")` for a 30 s pack of ten 3.0 s shots. The metronome rule fires for every consecutive pair, and the 30 s total triggers the short/centrepiece rules. The test cannot fail because the input is engineered to produce exactly those warnings; it does not verify that the rules are applied conditionally or that other warnings appear.

8. **`test_writer_gate_old_pack_gets_no_shape_problems` does not test the old-pack path**  
   It calls `writer_gate(..., story={})` with rows that lack `arc_beat`, which makes `is_new_format` return `False`. However, the test only checks that no `SHAPE-` problems exist and that warnings contain `SHAPE-01`. It never exercises the code path where `story_shape.lint` is called with `new=False`; the assertion is satisfied by the empty `problems` list regardless of the `story_shape` logic.

**Fixes:**

1. In `is_new_format`:  
   `story = story if isinstance(story, dict) else {}`  
   `return "premise" in story or any("arc_beat" in r for r in rows)`

2. In `lint`, replace `errors.append("SHAPE-02 ...")` with `add("SHAPE-02", ...)`.

3. In `_narrated`:  
   `return isinstance(narr, dict) and any(isinstance(v, str) and v.strip() for v in narr.values())`

4. In `lint`, change `payoff < PAYOFF_MIN` to `payoff <= PAYOFF_MIN`.

5. In `lint`, change `d <= SHORT_MAX` to `d < SHORT_MAX` and `d >= CENTRE_MIN` to `d > CENTRE_MIN`.

6. In `lint`, change `<= METRO_GAP` to `< METRO_GAP`.

7. Replace the tautological test with a case that can fail, e.g., a 20 s pack with varied durations that should produce no `SHAPE-07` warnings.

8. Add a test that calls `writer_gate` with `story=None` (or omits `story`) and verifies that shape rules produce warnings, not errors.

VERDICT: FIX-FIRST