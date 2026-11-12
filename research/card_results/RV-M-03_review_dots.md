**Real defects found**

1. **`h3/v4_to_h3.py` — `_camera_from_sheet` shake rounding**  
   Line: `clause += f"; a short shake at second {round(shake['t'] + ti / FPS, 1):g}"`  
   For `shake={'t': 1.25, 'dur': 1.0}` with `ti=0`, `round(1.25, 1)` is `1.2` (banker’s rounding). The test expects `"a short shake at second 1.2"` but the linter check `_check_stage_words` will accept it; however, the rounding is not the half-up convention used elsewhere and can produce `1.2` where the spec intends `1.3`. It also drops the `dur` field entirely, which is required by the card (shake duration must be emitted).  
   **Fix:** `clause += f"; a short shake at second {shake['t'] + ti / FPS:.1f} for {shake['dur']:.1f}s"` (or use `Decimal` with `ROUND_HALF_UP`).

2. **`h3/v4_to_h3.py` — `_stages` time-point generation ignores `beats` when span has no beat**  
   Line: `pt = 0.0 if k == 0 else max(prev_pt + 0.5, float(_time_point(inside[0] if inside else a / FPS)))`  
   When a stage span contains no beat, it falls back to `a / FPS` (the span start), which may be a fractional second that `_time_point` rounds to a half-second tick. This can produce a time point that is *not* derived from any beat and may collide with the previous point (the `max(prev_pt + 0.5, …)` only guarantees monotonicity, not uniqueness). The card says the point is “the start of the stage span, or the clip time of a blocking beat that falls inside the span” — the fallback must use the beat list, not the raw span boundary.  
   **Fix:** When `inside` is empty, use the nearest beat time (or the previous beat time + 0.5) instead of `a / FPS`.

3. **`h3/tests/test_opus_examples.py` — `test_example5_close_up_locked_and_shake_wording` asserts on `dur` but the code drops it**  
   Line: `assert "a short shake at second 3" in cams[0]`  
   The test only checks for the time, but the card requires the shake to include its duration. The current code emits only the time; the test cannot fail on the missing duration.  
   **Fix:** Add `assert "for 0.5s" in cams[0]` (or similar) and fix `_camera_from_sheet` to emit the duration.

4. **`h3/v4_to_h3.py` — `_stages` duplicate guard can produce “the scene holds still” instead of per‑person holds**  
   Line: `who = "; ".join(f"{n} does not move" for n in hold_names) or "the scene holds still"`  
   When `hold_names` is empty (no cast members with `hold` flag and no cast at all), the fallback string `"the scene holds still"` is emitted. The card requires “holds emit `"<name> does not move.`” — there is no provision for a generic placeholder. The test `test_hold_without_cast_names_still_unique_and_no_placeholder` only checks that the output has 7 unique sentences and no `"of 7"`, but it does not check that every sentence contains a name. A shot with an empty cast will produce a sentence that violates the hold wording rule and the linter will not catch it.  
   **Fix:** Either require a non‑empty `hold_names` (problem if empty) or emit a generic but card‑compliant phrase such as `"the shot holds still"` (if the card allows it) — but the card does not, so the safest fix is to append a problem when `hold_names` is empty.

5. **`h3/tests/test_opus_examples.py` — `test_example3_chained_second_clip_has_current_character_state` does not verify the camera sentence is present**  
   The test checks the `CURRENT CHARACTER STATE` header and the camera sentence, but the camera sentence assertion is inside the same test and will fail if missing. However, the test does not verify that the camera sentence comes *after* the header and *before* the time points, only that the header is between `[Shot 1]` and `At second 0`. The ordering assertion is weak but not tautological. No fix needed.

6. **`h3/v4_to_h3.py` — `_camera_from_sheet` does not validate `shake['t']` is within the clip**  
   Line: `if isinstance(shake, dict) and _is_num(shake.get("t")):`  
   A shake time outside the clip duration (e.g. `t=100.0`) is silently accepted and emitted. The linter has no rule for this.  
   **Fix:** Add a check that `0 <= shake['t'] <= pf / FPS - ti / FPS` and emit a problem otherwise.

---

VERDICT: FIX-FIRST