# REVIEW: score/plan_check.py and score/tests/test_plan_check.py (agent PCR, 2026-11-09)

Reviewed against checklist section A (A1-A15), SKILL.md "The checker enforces", score/cue_sheet.py fields, and music_bible.json.
Pytest: `python -m pytest score/tests/test_plan_check.py -q` -> 72 passed in 0.24 s.
Probe method: python -c snippets import score.plan_check and mutate the GOOD fixture (score/tests/test_plan_check.py) against the real cue sheet (stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/score/ep1/cue_sheet.json). Nothing was written to the repo.

Real cue facts used (read from the cue sheet):
- cuts: 6.0, 11.0 (hard, act_change), 18.0 (hard), 26.0, 34.0 (act_change), 41.0, 48.0, 56.0, 64.0 (act_change)
- voice.union ends `[67.8, 70.0]`; retention.last_voice_end_s = 70.0; retention.last_speech_end_s = 69.8
- retention.end_hook_window_s = [68.0, 70.0]; rehook_window_s = [31.5, 42.0]
- DROP candidates: ambient 60, cinematic 90, melodic_techno 124, drum_and_bass 176

## Findings

### F1 HIGH: bright end sting under speech passes (wrong voice-end field)
- File: score/plan_check.py:468 and 473-477 (`_check_end`). The band test uses `retention.last_speech_end_s` (69.8), the scripted last word. SKILL.md rule 2 says the end sting goes after `retention.last_voice_end_s` (70.0, the union end). The cue sheet's own comment says audio windows count as permission, so the union runs 0.2 s past the scripted word.
- Repro: end_sting moved to 69.9 with band "bright" (the plan's end_sting is not type "hit", so no hit rule applies):
  `ok=True codes=[]`. 69.9 is inside union window [67.8, 70.0).
- Fix: compare against `last_voice_end_s` (or the max of the two), and keep the 69.8 fixture valid by giving the GOOD end sting `band: "low"`, or move the sting to 70.0. Add a test: end sting at 69.9 bright -> exactly END_STING.

### F2 HIGH: a drop (or theme) with no role is never checked against speech
- File: score/plan_check.py:395-401 (`_check_busy`). `if e.get("type") == "hit" or not _is_str(role) or role not in busy: continue` skips every non-hit event that has no role. A drop has no role in the plan format, so a full-kit drop under dialogue passes.
- Repro: append `{"at_s": 20.0, "type": "drop"}` (inside union [18.4, 26.0)): `ok=True codes=[]`.
- Fix: treat every non-hit event of type drop, theme_entry or sonic-like full-kit event as busy regardless of role, or require `role` in `_shape_event` for those types. Test: drop at 20.0 -> exactly BUSY_IN_VOICE.

### F3 HIGH: event type matched case-sensitively; "Drop" slips past the god rule
- File: score/plan_check.py:406 (`e.get("type") == "drop"`), :408 and :451 and :354. The type is any non-empty string (`_shape_event` line 229-230), and no enum is checked.
- Repro: `{"at_s": 47.5, "type": "Drop"}` next to SHIVA at 48.0: `ok=True codes=[]`. GOD_DROP should fire.
- Fix: validate event types against a fixed set in `_shape_event` (unknown type -> PLAN_SHAPE) and/or normalise with `.strip().lower()` in the rule code. Add a test with "Drop" -> GOD_DROP.

### F4 HIGH: plan cuts near (within 1 s) a cue cut are never validated; a bad transition passes
- File: score/plan_check.py:346 (transition checked only for the nearest partner of each cue cut) and :347-349 (CUT_EXTRA only fires beyond NEAR_S = 1.0 s). A plan cut that is a second cut 0.4 to 1.0 s from a real cut is never examined.
- Repro (all `ok=True codes=[]`):
  - extra cut `{"at_s": 11.4, "transition": "fade"}` (unknown transition, after real cut 11.0)
  - extra cut `{"at_s": 11.4, "transition": "bed_continues"}` (a cut that is not in the picture)
  - duplicate cut `{"at_s": 11.0, "transition": "fade"}` (same time as a real cut)
- This is against SKILL "every cut has a transition" and D2/D3 intent (one fault, one code).
- Fix: every plan cut must pair with a cue cut within TOL_S, else CUT_EXTRA (frame-exact, not 1.0 s); run `_cut_transition` on every plan cut, not only the nearest partner. Note D2 chose 1.0 s on purpose; this is the case where that choice lets a BAD plan through.

### F5 MED: bpm is checked against any genre of the act; bible tempo_map and genre are not used
- File: score/plan_check.py:302-318 (`_check_tempo`) and D10. The bible `tempo_map` (HOOK 60, BUILD 128 or 124, DROP 176, OUTRO 60) is never read.
- Repro: DROP section changed to `bpm 124, genre melodic_techno`: `ok=True codes=[]` (124 is a DROP candidate under melodic_techno). HOOK at `bpm 125, genre melodic_techno`: `ok=True codes=[]`.
- The checklist A2 wording allows this ("any genre list"), so the checker is literally compliant. The SKILL intent ("BPM from the wrong act" and the bible tempo map) is not enforced.
- Fix: also require the section's genre to own the bpm (cue `candidates[genre]`), and compare the bpm with `bible.tempo_map[act]` when that key exists (at least as a warning, or an error for DROP/HOOK/OUTRO).

### F6 MED: plan home_key, style and episode are not checked against the bible or the cue sheet
- File: score/plan_check.py:187-200 (`_plan_top_shape` only checks type) and :520-569 (`_check`; bible home_key and cue episode are never read).
- Repro: `home_key: "C major"` (bible: "D minor") -> `ok=True`. `episode: 2` on the ep1 cue sheet (cue episode "1") -> `ok=True`.
- SKILL rule 9 (continuity from the bible) and the cue sheet episode field are both unchecked.
- Fix: error PLAN_CONTINUITY when plan.home_key != bible.home_key, and PLAN_EPISODE when plan.episode != cue.episode (string compare).

### F7 MED: CLI crashes with a traceback on deeply nested JSON (exit 1, not 2)
- File: score/plan_check.py:592-593. The loader catches `(OSError, ValueError)`; `json.loads` raises `RecursionError` on deep nesting, which is neither.
- Repro: a 100000-deep "[" file as the plan: `exit 1 | stderr last: RecursionError: Stack overflow ... while decoding a JSON array`. Expected exit 2 with "cannot read".
- Same loader serves the cue sheet and bible.
- Fix: catch `Exception` (or `(OSError, ValueError, RecursionError)`) in the loader loop and return 2.

### F8 LOW: a bright hit may start 0.1 s before speech; the rule has no duration and no margin
- File: score/plan_check.py:370 (`_in_window(at, union)` only tests the start). Repro: bright hit at 15.5, union gap ends at 15.6: `ok=True`. The hit rings into speech.
- Fix: for non-low hits require the gap to hold at least a margin (e.g. 0.5 s) after the hit, or add an optional `duration_s` to hit events and check the end.

### F9 LOW: GOD rule only looks at type "drop"; a bright hit right after a god entry passes
- File: score/plan_check.py:406-419. Repro: bright hit at 48.05 (0.05 s after SHIVA at 48.0): `ok=True`. SKILL rule 8 says no comic hits and no EDM-style drop on a divine reveal.
- Fix: count any non-half event of role hits/brass inside the 1.0 s window, or any hit with band "bright" there.

### F10 LOW: tests assert absence only, and some rules have no test
- No test that a god entry without `preceded_by_dropout_s` raises DROPOUT_MISSING (the code does, checked by hand: `DROPOUT_MISSING` only).
- No test for an extra or duplicate plan cut with a bad transition (F4).
- No test for END_STING against `last_voice_end_s` (F1); the one band test uses 69.0, which is far from the edge.
- `test_a5_bright_hit_in_voice_gap_passes`, `test_a4_cut_within_one_frame_passes`, `test_a7_busy_theme_in_voice_gap_passes` assert only that one code is absent. Make them assert the exact empty set.
- No CLI test for a deeply nested file (F7).

### F11 LOW (outside plan_check, noted for the coder): cue_sheet.py caps candidates at 5 per genre
- File: score/cue_sheet.py:360 `solve_tempo(...)[:5]`. Real cue data is under the cap (max 5 in HOOK/OUTRO), so no GOOD plan is rejected today. A future reel with more than 5 valid tempos would reject a valid plan silently. Fix: raise the cap or report when truncated.

## Checklist A status (reviewer reading, not the coder's claims)
- A1 coverage: OK (exact 1e-6; gap 0.01 s caught, P9).
- A2 tempo candidate: OK literally; F5 for the bible intent.
- A3 tempo change at act_change only: OK (P8 caught).
- A4 cuts: PARTIAL. Paired cuts OK; unpaired/extra cuts unchecked (F4).
- A5 impacts and bright-under-voice: OK for paired hits; F8 margin.
- A6 dropout range and DROPOUT_MISSING: OK (P10 path works; untested).
- A7 busy: PARTIAL (F2). Ungated busy roles OK.
- A8 god: PARTIAL (F3, F9).
- A9 rehook: OK (closed window, D17).
- A10 peak: OK (list and missing handled; section boundary exact).
- A11 logo: OK.
- A12 end sting: WRONG FIELD (F1).
- A13 bible refs: OK (themes, roles, presets, automation, plan.presets).
- A14 shape, no raise: OK for 4000 random mutations (0 CHECK_CRASH). CLI exit-code contract broken on deep JSON (F7).
- A15 GOOD plan ok and one BAD variant per code: OK for the codes in the test file; F1-F5 have no BAD test.

## Decisions D1-D17 I disagree with
- D2 (NEAR_S = 1.0 s for cut pairing and CUT_EXTRA): disagree. It lets extra and duplicate cuts through unchecked (F4). Frame-exact pairing with CUT_EXTRA for everything else.
- D6 (half-open windows): agree on the window test, but the end sting uses the scripted word, not the union end. Disagree with the choice of field (F1).
- D10 (genre not matched to the list): disagree (F5). The genre must own the bpm and the bible tempo map should be read.
- D13 (god themes: type "drop" exact): disagree (F3, F9).
- D14 (last_speech_end_s for the end sting): disagree (F1). Use last_voice_end_s; SKILL says so.
- D15 (BUSY skips non-role events): disagree (F2).
- D5 (hit under voice judged by start time only): accept as a stated limit, but add the margin in F8.
- D1, D9, D11, D16, D17: agree.

## Totals
HIGH 4 (F1, F2, F3, F4). MED 3 (F5, F6, F7). LOW 4 (F8, F9, F10, F11).
