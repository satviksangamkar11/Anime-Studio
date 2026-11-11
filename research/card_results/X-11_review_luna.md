`test_three_layers_present` only checks that the words “timing,” “source,” and “staging” appear. It passes even if the sheet contains none of the required layer data.

Faulty lines: [director/test_approval_sheet.py](/D:/aai%20work/anime_studio_merge/director/test_approval_sheet.py:74)–[76)

Exact fix: assert representative values from each layer in the generated sheet, such as `24` and the voice range for timing, `ref_01` and `ok` for source, and `route_A`, the gate result, and image path for staging.

VERDICT: FIX-FIRST.