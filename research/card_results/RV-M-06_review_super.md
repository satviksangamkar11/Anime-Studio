1. **Faulty line:** No such line — `director/test_keyframe_jobs_m06.py` defines `test_b_text_form_opus_example` but not `test_b_text_form`.
   **Why wrong:** The card lists `test_b_text_form` as a required test. The suite has no test by that name, so the B text form is not covered by the mandated test.
   **Fix:** Add `def test_b_text_form(kj):` that builds a shot with a change and asserts the instruction starts with `B_PREFIX`, contains `Change only:`, uses numbered items, contains no `(`, and does not contain `keep everything else`.

2. **Faulty line:** `    return f"{B_PREFIX} Change only: {items}"`
   **Why wrong:** The card requires hard rules (same framing/angle, no screen-side flip without an L10 turn record and a >= 3 s shot, key light side unchanged, prop count unchanged, facing change <= 90 degrees per 1.5 s). `b_instruction` never validates any of them; it blindly formats whatever `change_list` returns.
   **Fix:** Before building `items`, validate the sheet against those rules and raise `KeyframeJobError` on any violation (compare camera framing/angle, require `light.key_dir` unchanged, require prop count unchanged, reject screen-side facing flip unless an L10 turn record exists and shot duration >= 3 s, reject facing changes > 90 degrees per 1.5 s).

3. **Faulty line:** `    with open(os.path.join(plates_dir, "plates.json"), "r", encoding="utf-8") as fh:`
   **Why wrong:** If the plates registry file is absent, `plates_index` raises `FileNotFoundError` instead of the documented `KeyframeJobError`, so a missing registry crashes the caller rather than being reported as a plate problem.
   **Fix:** Wrap the open/load in `try/except FileNotFoundError` and raise `KeyframeJobError("plates registry missing: {p}".format(p=os.path.join(plates_dir, "plates.json")))`.

4. **Faulty line:** `    sentences.append(FRAME_LAW)`
   **Why wrong:** The card requires eight plain sentences including continuity. `a_prompt` never appends a continuity sentence, so it emits six or seven sentences depending on `STYLE_ANCHOR`.
   **Fix:** Insert before `FRAME_LAW`: `sentences.append(_get(sheet, "continuity", default="Action continues from the previous shot."))`

VERDICT: FIX-FIRST