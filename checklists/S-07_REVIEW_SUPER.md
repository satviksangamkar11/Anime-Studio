# Nemotron Super review of S-07 (rule 55), supervisor test run: 31 passed in 0.04s

ROWS:
Files: h3/shot_mode.py, h3/tests/test_shot_mode.py: PASS
Change: PASS
check_pixel_frames requires LATTICE_N_MIN ≤ n ≤ LATTICE_N_MAX,: PASS
image_prompt_type: a None mode raises ShotModeError("POST: PASS
frame_row copies route, input_video_strength (None, or a float: PASS
For route KFI, mid and mid_frame (0 < mid_frame: PASS
Tests: test_pf_22_refused, test_pf_107_and_345_ok, test_pf_362_refused: PASS
test_post_none_refused: PASS
test_soft_se_keeps_strength_and_end_position: 0.6 and 151: PASS
test_kfi_without_mid_raises: PASS
test_router_rows_accepted: for every shot_router route: PASS
Rewrite the existing tests that accept 22 or 39: PASS
Acceptance: python -m pytest h3/tests/test_shot_mode.py -q: PASS
No reel 1 file is edited or opened for writing;: PASS
Only the files named in this card were changed: PASS
No network, Colab, ElevenLabs, renderer or paid call;: PASS
Every changed .py file parses (ast.parse) and has no: PASS
The card's acceptance command was run and its full: PASS
Every test named in the card exists, was run,: PASS
Nothing was deleted from the existing tests; tests added: PASS
One log line was appended to D:/aai work/anime_studio/: PASS

UNTICKED:
- Problems: advances 3 (closes at step 8, build_h3_batch). Bugs: E1 (shot_mode half), O1 (shot_mode), O9 (shot_mode), O3 (carries the field). — Acceptable: tracked known issues deferred to later steps, not part of this card's acceptance.

MISSING: none
EXTRA: none
BAD: NONE
VERDICT: DONE
