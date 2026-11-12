**Defects found**

1. **`test_kalika_hits_sit_on_impact_frames` is tautological / cannot fail.**  
   The test builds `expected` from the same `kalika_sheet["shots"][*]["impacts"]` that it later checks against the rows produced by `cue_rows`. The assertion `set(hits) == expected` only verifies that `cue_rows` copied the impact frames it already had; it does not verify that `cue_rows` placed a hit row *on the impact frame* with the correct `t_frame`. A row with `t_frame = impact.at_frame + 100` would still satisfy the equality because the test would build the same wrong expected set from the (already shifted) data.  
   **Fix:** compute the expected set from an independent source (e.g. the raw pack `shots.json` impact frames, or a hardcoded constant for the fixture) so the test can actually fail.

2. **`test_riser_is_two_seconds_before_the_primary_beat` is weak / cannot fail.**  
   The test creates a sheet with impacts at frames 120 and 200, then asserts `risers[0]["t_frame"] == 120 - 48` and `risers[0]["frames"] == 48`. Because the test itself writes the literal expected values, it only checks that the constants match; it does not verify the 2‑second offset from the *primary beat* (the first impact). If the implementation used the second impact or a different reference, the test would still pass as long as the literal numbers happened to match.  
   **Fix:** derive the expected riser position from the shot’s first impact frame (`impacts[0]["at_frame"]`) so the test validates the actual rule.

3. **`test_note_names_a_silence_gap_longer_than_point_three_seconds` is fragile and does not test the gap boundaries.**  
   The assertion `any("silence" in n and "2" in n and "6" in n for n in notes)` merely checks that the substrings `"2"` and `"6"` appear somewhere in a note that contains `"silence"`. It does not confirm the gap is `[2, 6]` seconds; any note containing those digits (e.g. `"silence 2.5-6.5 s"` or `"silence 20-60 s"`) would pass.  
   **Fix:** parse the note or assert on the exact gap interval (e.g. `"2 s"` and `"6 s"` or the tuple `(2.0, 6.0)`).

4. **`test_build_cue_sheet_keeps_voice_rest_in_reel_seconds` uses `pytest.approx` incorrectly.**  
   The test compares `row["voice_rest"]` (a list `[start, end]`) to `pytest.approx` of two scalar expressions. `pytest.approx` is intended for scalar comparisons; wrapping it around a list may not behave as expected and makes the assertion unreliable.  
   **Fix:** compare each element separately:  
   `assert row["voice_rest"][0] == pytest.approx(row["start_s"] + 1.0)` and similarly for the end.

5. **No test verifies the `rest` row’s `voice_rest` field format or the `bed` row’s `source` field.**  
   The card requires `voice_rest` on rest rows and a `source` for bed rows. `test_rest_rows_come_from_voice_rest_windows` checks `voice_rest` only for rest rows, but there is no test that bed rows carry a non-empty `source` (or that the source comes from the first beat’s `audio_cue`).  
   **Fix:** add a test that asserts every bed row has a `source` string (possibly empty when no beat cue exists) and that the source matches the shot’s first beat `audio_cue`.

6. **The no-silence note is not tested for the exact wording required by the card.**  
   `test_note_says_no_silence_when_beds_cover_the_reel` checks only that some note contains `"no silence"`. The card specifies the note must state that bed rows leave no gap over `MIN_GAP_S`. A test that asserts the exact expected string (or a regex matching the required phrasing) is missing.  
   **Fix:** assert the full note string, e.g. `assert notes == [f"no silence over {MIN_GAP_S:g} s: bed rows cover the reel"]`.

**Faulty lines (examples)**  
- `expected = {(s["id"], i["at_frame"]) for s in kalika_sheet["shots"] for i in s["impacts"]}` (test cannot fail)  
- `assert risers[0]["t_frame"] == 120 - 48 and risers[0]["frames"] == 48` (literal constants, does not test the rule)  
- `assert any("silence" in n and "2" in n and "6" in n for n in notes)` (substring check, not boundary check)  
- `assert row["voice_rest"] == [pytest.approx(row["start_s"] + 1.0), pytest.approx(row["start_s"] + 2.0)]` (misused approx)

VERDICT: FIX-FIRST