- [director/continuity_sheet.py](/D:/aai%20work/anime_studio_merge/director/continuity_sheet.py:66) — The sheet prints facing words, but the card requires screen direction **arrows**. Change the direction formatter to include arrows, for example `right →` and `left ←`, and add an assertion that the SVG contains them.

- [director/continuity_sheet.py](/D:/aai%20work/anime_studio_merge/director/continuity_sheet.py:68) — `end_state()` records each cast member’s ending `x` and `y`, but the generated sheet omits both, so it does not show the full end state. Include `x` and `y` in this line’s output and assert their values in the SVG test.

VERDICT: FIX-FIRST.