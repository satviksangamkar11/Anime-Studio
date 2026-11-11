# Nemotron Super review of S-14 (rule 55), supervisor test run: 45 passed in 0.25s

ROWS:
Files director image_gates.py director/test_image_gates.py: PASS
Change Done in image_gates.py as: PASS
to_float01 accepts uint8 only floats: PASS
background_lock min_area_fraction=0.25 when area_fraction: PASS
dilate clamps px to max: PASS
cast_parity and limb_parity refuse bool: PASS
The docstring marks 0.97 and: PASS
Tests Four named tests exist: PASS
test_float_image_refused director/test_image_gates.py: PASS
test_small_area_fails 64x64 frame comparable: PASS
test_huge_dilate_fast px 10**6 on: PASS
test_bool_count_refused test_image_gates.py test_bool_count_refused: PASS
Depends on none No other card: PASS
Acceptance python -m pytest director/test_image_gates.py: PASS
Waits on none No dependency used: PASS
No reel 1 file is edited: PASS
Only the files named in this: PASS
No network Colab ElevenLabs renderer or: PASS
Every changed .py file parses ast: PASS
The card's acceptance command was run: PASS

UNTICKED:
- Problems advances 20/21/25 (close at step 8 wiring): reason acceptable — out of card scope; bugs E8/O16/H7-J11 are implemented in the ticked code rows.
- Second-attempt risk low: reason acceptable — a forecast, not a deliverable.
- Every test named in the card exists ...: reason acceptable — left for reviewer judgment; test_float_image_refused passes (in the 45) and checks the float-refusal behavior.
- Nothing was deleted from existing tests: reason acceptable — deletion of test_to_float01_float_0_255_scales and the rename are card-sanctioned.

MISSING: none — every card requirement is present and verified in code/tests: uint8-only to_float01 with float GateError("convert to uint8 0..255 first"), min_area_fraction=0.25 with "reasons" list and non-finite ssim → pass False, dilate clamp `min(int(px), max(mask.shape))`, `_check_int` bool/non-int refusal in both cast_parity and limb_parity, uncalibrated-knob docstring, and the four named tests all included in the 45 passed.

EXTRA: none — test_float_inputs_refused_by_background_lock is a card-sanctioned rename of test_uint8_and_float_inputs_give_same_result, not an unasked addition.

BAD: NONE — no faulty/fragile line found; all 45 tests pass and the code matches the card.

VERDICT: DONE
