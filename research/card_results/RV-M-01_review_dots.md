**Defects found:**

1. **`h3/v4_to_h3.py` line ~605 (inside `_shot`)**  
   The line `sheet_cues = (ctx["blocking"] or {}).get(sid) if ctx.get("blocking") is not None else None` reads `ctx["blocking"]` again, but `ctx["blocking"]` is not guaranteed to be a dict when `ctx.get("blocking") is not None`. If `ctx["blocking"]` is `None`, the condition is `False` and the line is safe, but if `ctx["blocking"]` is a non-dict truthy value (e.g., a list), `(ctx["blocking"] or {}).get(sid)` will raise `AttributeError`. The code earlier assumes `ctx["blocking"]` is a dict or `None`; this line should use the already-validated `sheet0` (which is `None` when `ctx["blocking"]` is not a dict).  
   **Fix:** Replace with `sheet_cues = sheet0.get("sound_cues") if isinstance(sheet0, dict) else None` (or simply reuse `sheet0`).

2. **`h3/tests/test_prompt_wiring.py` `test_no_breath_exception`**  
   The test calls `v._mouth(track, 175, "S", [], ed=None, ti=0)`. The fourth positional argument is `problems`, but the test passes a list `[]` which is mutable and may be mutated by `_mouth`. More critically, the signature of `_mouth` in `v4_to_h3.py` is `_mouth(track, pf, sid, problems, ed=None, ti=0)`. The test passes `ed=None` correctly. However, the test asserts `states["3"] == "open_non_verbal_breath"` but `_mouth` computes states for seconds `0..ceil(pf/FPS)-1`. With `pf=175` and `FPS=24` (assumed), `ceil(175/24)=8`, so seconds `0..7` exist. The test sets `ms["3"]` but the mapping from clip second to editorial second uses `mid = (s*FPS + min(s*FPS+FPS, pf))/2 - ti`. For `s=3`, `mid = (72 + min(72+24,175))/2 = (72+96)/2 = 84`. Then `e = int(mid//FPS) = int(84//24) = 3`. So it should work. **But** the test does not import or set `FPS`; it relies on the default from `shot_table_spec`. If `FPS` is not 24, the math may break. The test is brittle but not a defect in the code.  
   **No fix needed** — but the test is weak: it doesn't verify that the breath exception is *removed* from the rule text; it only checks that `"breath"` is not in `rule`. The card says "delete the breath exception", so the test should assert the exact old phrase is absent.

3. **`h3/v4_to_h3.py` line ~605 (same as above) — duplicate variable `sheet_cues`**  
   The variable `sheet_cues` is assigned but never used; the `sx02_problems` call uses `sheet_cues.get("sound_cues")` immediately. This is not a defect, just dead code.

4. **`h3/schema_and_linter.py` `sx02_problems`**  
   The function expects `sound_cues` to be a list of dicts with `"text"` and `"t"`. In `_shot`, `sheet_cues.get("sound_cues")` is passed. If the blocking sheet has `sound_cues` as `None` or missing, `.get()` returns `None`, and `sx02_problems` will iterate over `None` → `TypeError`. The card says "every `blocking.sound_cues[].text` head noun appears...", implying `sound_cues` may be absent. The function should handle `None` or empty list gracefully.  
   **Fix:** In `sx02_problems`, add `if not sound_cues: return []` at the start.

5. **`h3/tests/test_prompt_wiring.py` `test_soundscape_max_4_sentences_with_7_cues`**  
   The test uses `v._soundscape({"sfx_cues": []}, "SHOT-001", problems, extra=extra)`. The `_soundscape` function signature is `_soundscape(track, sid, problems, extra=())`. The test passes `problems` as a list, which is mutated. This is acceptable. However, the test asserts `text.startswith("First bell 0 rings")` but the packing logic in `_soundscape` may produce `"First bell 0 rings; then bell 1 rings; ..."`. The assertion is correct. **No defect.**

6. **`h3/compile_h3_sing8.py` `_tail` function**  
   The `_tail` function returns `[st["6_impact_result"]] + ([st["7_settled_end_state"]] if st["7_settled_end_state"] != st["6_impact_result"] else [])`. This is intended to avoid duplicate sentences. However, the duplicate guard in `compile_fl2va_prompt` uses `find_duplicate_sentences(body)` which checks the *entire* body. If stage 6 and 7 are identical, `_tail` drops stage 7, but `find_duplicate_sentences` may still flag other duplicates. This is correct behavior. **No defect.**

7. **`h3/v4_to_h3.py` `_mouth` function**  
   The function returns `states, "The figure's mouth stays closed for the whole shot."` but the card says "delete the breath exception". The rule text still contains `"The figure's mouth stays closed for the whole shot."` which is a hardcoded string. The card says the rule text is "only kept for the record and is not emitted". The test `test_no_breath_exception` only checks that `"breath"` is not in the rule, but the rule still says "mouth stays closed" which is the *opposite* of the breath exception. This is confusing but not a defect per se. **No fix.**

8. **`h3/tests/test_prompt_wiring.py` `test_glue_gone`**  
   The test calls `_stages([...], 107, "S1", [])` with `hold_names=[]`. The `_stages` function expects `hold_names` to be a list of strings. The test passes `[]` which is fine. The test asserts `"with a veil" not in sentence` and `find_cue_glue(...) == []`. This is correct. **No defect.**

9. **`h3/v4_to_h3.py` `_soundscape` function**  
   The function packs cues into 1-4 sentences using `size = math.ceil(n / 4)`. For `n=7`, `size=2`, so sentences are grouped as `[0,1], [2,3], [4,5], [6]` → 4 sentences. The labelling logic uses `labelled` list where index 0 gets "First", last gets "finally", others get "then". But when `n=7`, the last item is index 6, which gets "finally". The grouping `labelled[j:j+size]` for `j=0` gives indices 0,1; `j=2` gives 2,3; `j=4` gives 4,5; `j=6` gives 6. The sentence for `j=6` is `"finally bell 6 rings."` which is correct. **No defect.**

10. **`h3/schema_and_linter.py` `SX_MIN_STAGE_CUES = 0`**  
    The card says `SX_MIN_STAGE_CUES = 0` and remove the stage check. The constant is set to 0, but the stage check removal is not visible in the provided code. If the stage check is still present elsewhere (e.g., in `lint_story`), it would be a defect. The provided code does not show the stage check, so **no defect visible**.

**VERDICT: FIX-FIRST**