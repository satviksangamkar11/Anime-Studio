# Colour guide v2 verification R2 (CV2, Haiku medium), 2026-11-07
Scope: 13 findings in COLOUR_V2_REVIEW_HAIKU_2026-11-07.md checked against docs/UI_COLOUR_SYSTEM_GUIDE_2026-11-07_v2.md and research/COLOUR_RESEARCH_NOTES_2026-11-07.md. Read-only except this report and PROJECT_LOG lines.

Findings 1-13: all 13 resolved in the files (grep and read check).
- F1 (4.0 map): all 42 names from style.css covered (31 colour, shadow, s1-s7, r-sm/radius/r-lg); dark blocks identical; "Test reads" column matches the test file.
- F2 table-head row present (4.1). F3 --hover retired, --hover-bg only. F4 section 8.1 pairs match BODY_TEXT_PAIRS (test_static.py 499-500). F5 removed tags on timeline/editor/properties/asset/toolbar rows. F6 font path = style.css line 7; ui/static/fonts absent (marked pending). F7 theme-color and inline-head tagged unsourced. F8 manual checks each listed with tag. F9 section 3 cites E15 only. F10 "3b" replaced by 4.1; PARITY_BUILT tied to the NOW block (8f061a2 confirmed). F11 rows say forms and status only. F12 notes table has C21-C25. F13 S3 editor's draft and S9 flagged not fetched.

Ratio recompute (print-only python, WCAG 2):
- table-head light 9.80, dark 10.46 (guide: 9.80 / 10.46) OK
- input-bg light 11.92, dark 12.67 (guide: 11.92 / 12.67) OK
- header-bg white on light 16.53, on dark 13.03 (guide: 16.53 / 13.03) OK
- accent-fg light 6.65, dark 9.51 (guide: 6.65 / 9.51) OK
- Extra: text-secondary light 7.49 bg, 7.89 surface, 7.11 editor; 4.2 info 7.02 / 7.94 OK. Red white 7.19 and grey 7.77 OK.

Remaining real defects:
1. LOW, guide 4.2 grey row: shows "7.8 (plan figure, not recomputed)" while 4.0 says "7.77 (the plan's 7.8 is confirmed)". Fix: write 7.77 in the 4.2 row for light and dark, drop "not recomputed".
2. LOW, guide 4.0 red row: "no v2 row yet (add to 4.2)"; amber, tint-red, tint-grey say "no v2 row". All names are kept, but the TODO is open. Fix: add a red row to 4.2 (light #FFFFFF on #A8231B 7.19; dark #1A0606 on #FF9B91 9.65) and state a one-word decision for amber, tint-red, tint-grey (kept as is, no ratio needed).

COUNT: 2 remaining defects (0 critical, 0 high, 0 medium, 2 low).
VERDICT: NEEDS FIXES (both low; the 13 original findings are closed).
