# Reviewer RC2 (haiku, medium): round 2 of colour research prompt, 2026-11-07

Reviewed: research/_prompt_colour_research.md (read-only). Round 1: COLOUR_PROMPT_REVIEW_HAIKU_2026-11-07.md.
Checked: style.css 55-115, UI_REDESIGN_PLAN 365-397, test_static.py 466-516, v1 guide headings and sections 3C, 7.

Round 1 status: applied = 1 (palette conflict, line 10), 2 (v1 vs plan size, line 13), 3 (TEXT_ON_BG, line 12, but see finding 1), 6, 7, 8 (line 9a). Partly = 4 (see finding 3). Not applied = 5 (pipe), 9 (hex assumption), 11 (forms). 10 optional, not applied.

Verified correct: style.css dark blocks lines 59-94 and 95-110 (--page-bg #14130f, --accent #f0b45a); plan lines 373-390 (--page-bg #f7f5f0, --fg #1c1b1a / #f3f1ec); v1 section 1 at line 15 and section 6 at line 242; v1 section 3C at lines 109-120 (the 2025 study is named only generically: "not found" is the right answer); v1 section 7 body 16-18px (line 270) vs plan 1rem = 20px (line 395).

1. MEDIUM | line 12 | The 7:1 test already exists: ui/test_static.py line 503 test_body_text_contrast_is_at_least_7, over BODY_TEXT_PAIRS (line 499). TEXT_ON_BG (line 469) is checked only at 4.5 (line 493). The prompt's "extend TEXT_ON_BG" would make a duplicate or wrongly raise the 4.5 floor. Fix: "The 7:1 test exists at test_static.py:503 over BODY_TEXT_PAIRS (line 499). Extend BODY_TEXT_PAIRS and the status pairs there. Do not add a second 7:1 test. TEXT_ON_BG stays a 4.5 floor."

2. MEDIUM | lines 3 and 14 | New contradiction. Line 3 limits the guide to the control panel and removes the render, captions, video and export. Line 14 says "keep every requirement of v1 (nothing dropped)". v1 sections 4-5 (token architecture, application-wide audit) include pipeline items. The two rules cannot both hold. Fix: "Requirements of v1 that concern pipeline output are removed by the scope rule. Each one is listed in v2 as [v2: removed, scope rule, owner 2026-11-07]. Nothing is dropped silently."

3. MEDIUM | line 17 | Logging rule conflict. Line 17 exempts "a search or fetch alone" from a log line. CLAUDE.md says "after EVERY step, with no exception". Fix: "Log one line per research item finished, plus one per search batch. Never skip a step."

4. LOW | line 17 | Round 1 finding 5 not applied: the pipe rule has no fallback. Fix: "Write | inside a result as /."

5. LOW | line 9 | Round 1 finding 9 not applied: "secondary/bg 4.77" uses #59635E, which is v1 light-mode secondary text (v1 line 70), not a reading-theme token. Fix: "reading secondary 4.77 assumes #59635E (v1 line 70); v1 has no reading secondary token."

6. LOW | lines 3 and 5 | Round 1 finding 11 not applied: control-panel forms are in scope; caption preview and rendered output are not. Fix: add that one line under the scope.

7. LOW | line 16 | New: the existing 17px test (test_static.py:510) reads rem and accepts >= 0.85rem. That is 17px only if html is 125% (plan line 367). Fix: "test_no_font_size_below_17px assumes html 125% root; check it when the root changes."

8. LOW | line 5 | Round 1 finding 10 (path differs by _v2) not applied. Optional; no change needed if the agent checks paths before writing.

FINAL: 8 findings (0 HIGH, 3 MEDIUM, 5 LOW). Verdict: NEEDS FIXES. Fix findings 1-3 before the research agent starts; 4-8 are optional but cheap.
