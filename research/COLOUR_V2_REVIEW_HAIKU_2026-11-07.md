# Colour guide v2 review (Haiku medium, reviewer CV), 2026-11-07
Verdict: NEEDS FIXES. 13 findings (0 critical, 1 high, 6 medium, 6 low). Saved by the lead from the reviewer's hand-back (its own Write was blocked by the worktree path guard).

Checks passed: 60 contrast pairs recomputed, none differs by more than 0.05; v1 section 1 Git rules copied word for word (only the commit line carries the [v2: no-commit override] prefix); DOI 10.3389/fpsyg.2025.1627013 verified (n=40, 20 women, mean age 22.6, pupil effect, no reliable RT/accuracy effect); WCAG Focus Appearance (2 px inset fails, 3 px passes) and 3:1 change rule verified; style.css, index.html (error-bar line 32, story-text line 149, modal line 380), i18n.js (studio.lang in try/catch) and test_static.py (lines 447-510) match; scope clean apart from finding 11.

1. HIGH, v2 section 4.1 and section 8 item 6: existing style.css tokens --indigo, --hover (#eaeaea), --th-bg, --input-bg, --field-line, --line, --panel, --page-bg and dark --muted (#c9c4ba) have no old-to-new mapping; tokens.css could drop them silently. Fix: add an old-to-new token table covering every existing name.
2. MEDIUM, section 10 row 4: "tables = --th-bg" but --th-bg is absent from the 4.1 token tables. Fix: add the row with a ratio or drop the claim.
3. MEDIUM, section 4.1: new --hover-bg collides in meaning with existing --hover. Fix: pick one name in the rename table.
4. MEDIUM, section 8 item 1: proposes pairs ("text-secondary","surface"); real BODY_TEXT_PAIRS (test_static.py line 499) uses fg, panel, muted, page-bg, err-fg, ok-fg, amber-fg. Fix: use the real names; note the existing 7:1 test already checks muted on panel and page-bg, so v1 #59635E (5.51) would fail it.
5. MEDIUM, section 2 and section 10 row 5: timeline, scene editor, properties, asset browser, character/environment/object controls, layer panels, toolbars are marked "not present" instead of [v2: removed, scope rule]. Fix: tag each pipeline item with the removal tag.
6. MEDIUM, section 5: font path "styles/fonts/NotoSansDevanagari-Variable.ttf" is wrong; style.css @font-face uses "fonts/NotoSansDevanagari-Variable.ttf" relative to ui/static, and the file is not in ui/ today (T2 adds it). Fix: correct path, mark file pending.
7. MEDIUM, section 6 steps 3 and 5: "meta theme-color" and the inline-head pattern are tagged moderate with no URL. Fix: add an MDN or spec URL or tag as unsourced.
8. MEDIUM, section 8 manual checks vs section 10 row 12: row 12 says "kept" but the timeline, editor, preview-unchanged, all-routes and exported-video checks are not all listed. Fix: list each, marking "not present in this app" where true.
9. LOW, section 3: cites E14-E16 for the no-clinical-claim restriction; E14 is "none found". Fix: cite E15 only.
10. LOW, section 9 and section 6 step 1: cites "plan section 3b" (no such heading) and "PARITY_BUILT" (not in the plan). Fix: cite the lead brief or the correct plan section.
11. LOW, section 2: "Audio, voice, export settings" and "Rendering controls" rows say Yes. Fix: "forms and status only; no pipeline behaviour".
12. LOW, notes section 3: table has 20 rows (C1-C20), not 9; C20 is an owner rule; missing rows: dark muted #c9c4ba vs v2 #B9C2BA, and the --hover, --th-bg, --indigo, --input-bg renames.
13. LOW, notes S3 and S9: editor's-draft URL and MDN color-scheme page not fetched; tags say so; fetch before shipping.
