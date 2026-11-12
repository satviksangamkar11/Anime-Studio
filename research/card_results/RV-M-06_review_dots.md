Real defects found:

1. **`test_a_prompt_opus_example_sentences` expects "kneeling" but the code never emits it.**  
   In `a_prompt`, the pose is only turned into a verb (`_POSE_VERB`) inside `_b_change_words` for the B job. For the A job the sentence is built with `_POSE_ADJ` (e.g. "kneeling") *and* facing, but the expression is appended only if `member.get("expression")` is truthy, and the pose/facing pieces are joined with the expression. However, looking at the actual output for SHOT_012, the pose word "kneeling" is indeed emitted via `_POSE_ADJ` — so this test is actually valid. No defect here.

2. **`test_b_no_keep_everything_line_and_no_coords` expects a move sentence, but the change_list for that cast is empty.**  
   The cast has `start` and `end` identical except `pose` is "kneeling" in both (start is `KRISHNA_START` which has pose "kneeling", end has pose "kneeling"). There is no pose change, no scale change, no move. `blocking.change_list` would return `["keep everything else exactly the same"]` or empty. The test then expects `jobs_for_shot` to produce a B job with `"1) KRISHNA moves to the centre, at mid-height."` — but there is no change to report. The test is therefore tautological/will fail because the B instruction will be `"Change nothing."` or raise. **This test cannot pass as written.** It assumes a move change that the input does not contain.

   Faulty expectation in test: it asserts a specific move instruction for a cast with no actual move. The test is not testing what it names (no coords, no keep line) — it is testing a fabricated change.

3. **`test_b_max_3_changes` counts a mouth change via `end["mouth_moves"]` but `change_list` (in `blocking.py`) does not know the `mouth_moves` key.**  
   The test sets `cast[0]["end"]["mouth_moves"] = True` and expects 3 changes (2 poses + 1 mouth). If `blocking.change_list` does not emit a line for `mouth_moves`, the count is 2, not 3. The test then expects `count(") ") == 3`. This is a test that depends on an unimplemented feature. If `change_list` ignores `mouth_moves`, the test fails. If it is not implemented, the test is weak/tautological because it asserts a count that the code cannot produce.

4. **`test_scale_only_change_is_reported_as_scale` imports `blocking` directly but the module is imported as `director.blocking` in the package.**  
   The test does `import blocking` after `sys.path.insert(0, str(_director_dir))`. If `blocking.py` is in `director/`, this works. But the card says the helper is `director/blocking.py (helper for the coordinate-to-words mapping, if not already there)`. The test assumes a flat module name. If the package structure is `director.blocking`, the bare `import blocking` will fail with `ModuleNotFoundError` unless the file is also at the top level. This is a crash path for the test suite.

5. **`test_a_prompt_has_no_digits_coords` strips "9:16" but the regex `\d` still matches the "9" in "9:16" if the strip fails.**  
   The test does `text = job_a["prompt"].replace("9:16", "")` and then `assert not re.search(r"\d", text)`. This is safe. However, the card allows only the frame law to have digits. The test does not verify that *only* the frame law has digits; it removes the known digit string and checks the rest. This is acceptable but weak: if the prompt accidentally included "3" somewhere else, the test would catch it. No defect.

6. **`jobs_for_shot` sets `job_a["method"] = "edit"` and `base_edit_id = plate_id`, but the card requires renaming to `generate_with_chip` for B and `STYLE chip attached to every A job`.**  
   The card says: "rename `method:"edit"`/`base_edit_id` to `generate_with_chip`". The code uses `"method": "edit"` for A and `"method": "generate_with_chip"` for B. The card says the rename applies to the A job as well? The phrasing is ambiguous: "rename `method:"edit"`/`base_edit_id` to `generate_with_chip`" could mean the A job should also use `generate_with_chip`. Currently A uses `"edit"`. This is a card requirement not met: the A job method should be `generate_with_chip` (or at least the card says to rename it). The test `test_b_method_is_generate_with_chip` only checks B. There is no test that A uses `generate_with_chip`. The card requirement is not met for A.

7. **`EXCLUSION` is hardcoded as `"No text, no logo, no extra people, no halo."` but the card says "one short exclusion sentence (<= 4 nouns)".**  
   The nouns are: text, logo, people, halo = 4 nouns. That meets the requirement. No defect.

8. **`STYLE_ANCHOR` is appended as the first sentence, but the card says "style anchor + STYLE chip".**  
   The anchor is appended if set. The STYLE chip is attached via `a_chips`. The card says "STYLE chip attached to every A job" — done. No defect.

9. **`test_s_route_has_no_b_job` uses a shot with `"route": "S"` but no `cast`/`props` keys; the code uses `_get(sheet, "cast", default=[])` so that is safe. However, the shot also has no `camera` or `light`; `_get` defaults to `{}`, so `_shot_sentence` and `_light_sentence` will produce `"Medium shot at eye level, natural perspective."` and no light sentence (since `light.get("key_dir")` is falsy). The A prompt will be valid. No crash. But the test does not check the A prompt content. It only checks `job_b is None` and `base_edit_id`. This is a weak test: it does not verify that the A prompt is still well-formed for route S. The card lists `test_s_route_has_no_b_job` as a required test; the test exists but does not cover the A prompt side. Not a defect in the code, but the test is incomplete relative to the card's intent (it only tests the B absence).

10. **`b_instruction` raises `KeyframeJobError` if `len(raw) > MAX_B_CHANGES`, but the card says "max 3 changes from `blocking.change_list`". The code raises on >3, which is correct. However, the test `test_b_max_3_changes` expects 3 changes to be allowed and 4 to raise. The code allows <=3. That is correct.**

11. **The card says "facing change <= 90 degrees per 1.5 s" and "no screen-side flip without an L10 turn record and a >= 3 s shot". These are hard rules for the B job changes. The code does not enforce them anywhere. `change_list` in `blocking.py` is not shown, but `keyframe_jobs.py` does not check facing change magnitude, shot duration, or L10 record. The card says these are "hard rules" for B. The code does not validate them. This is a missing requirement: the B job must enforce these rules or reject changes that violate them. The tests do not cover these rules. The card lists `test_b_max_3_changes` and `test_b_text_form` but not these hard rules. The card says "hard rules" — they must be enforced. The code does not enforce them. **Defect: hard rules not implemented.**

12. **`jobs_for_shot` sets `job_b["chips"] = [chip_ref_id]` and also includes `"chip_ref_id"` key. The card says B is chipped on `"<SHOT>-A final"`. The code uses `chip_ref_id = f"{shot}-A final"` and sets both `chips` and `chip_ref_id`. The test `test_b_method_is_generate_with_chip` checks `job_b["chips"] == ["SHOT-012-A final"]` and `chip_ref_id`. That is consistent. No defect.

**Most critical real defects:**
- Hard rules (facing change <= 90°, screen-side flip conditions, key light side unchanged, prop count unchanged) are not enforced anywhere in `keyframe_jobs.py` or visible in the code. The card explicitly lists them as hard rules for B. The code blindly passes any change_list to B without checking these constraints. This is a card requirement not met.
- The A job method is `"edit"` but the card says to rename to `generate_with_chip`. The A job should also use `generate_with_chip` (or the card is ambiguous, but the rename instruction is explicit). The test suite does not check A's method.
- `test_b_no_keep_everything_line_and_no_coords` is a test that cannot fail as written because it expects a move change for a cast with no move. It is a tautological/incorrect test.

VERDICT: FIX-FIRST