# Reviewer RC3 (haiku, medium): round 3 of colour research prompt, 2026-11-07

Reviewed: research/_prompt_colour_research.md (read-only). Round-2 report: COLOUR_PROMPT_REVIEW_HAIKU_R2_2026-11-07.md.
Checked by grep: test_static.py 469, 491-493, 499, 503, 510-513; plan 367, 395, 734; v1 guide 70, 109-120.

Round-2 status: fixed = 1 (line 10), 2 (lines 3 and 15), 3 (line 17), 4 (pipe as /), 6 (line 9), 7 (line 10), 8 (line 5 _v2 path). Partly = 5 (see finding 4).

1. MEDIUM | line 15 | New contradiction: "section 6 ... is the only v1 section allowed to shrink", but sections 4-5 lose pipeline items under the scope rule (line 15 itself lists them as removed). Fix: "Pipeline items in sections 4-5 are removed with [v2: removed, scope rule]; section 6 is replaced by the scope rule. Only these may shrink."
2. LOW | lines 3 and 15 | Wording: line 3 says section 6 is "reduced to one rule", line 15 says "replaced". Fix: use "replaced by one scope rule" in both.
3. LOW | line 17 | TYPE list omits AGENT-START, which blot.md rule 1 requires. Fix: add AGENT-START to the TYPE list.
4. LOW | line 9 | Round-2 finding 5 only partly applied. Reading secondary 4.77 uses #59635E (v1 line 70); v1 has no reading secondary token (v1 lines 109-120 define only the reading background). Fix: "reading secondary 4.77 assumes #59635E (v1 line 70); v1 defines no reading secondary token."
5. LOW (lead decision, plan not prompt) | line 10 vs plan lines 367 and 734 | Plan says "Add test_no_font_size_below_17px" and "(new test)", but the test already exists at test_static.py:510 and reads rem only (line 513). Fix in plan: "keep test_no_font_size_below_17px and make it check the 125% root"; the prompt line 10 is already correct.

Process note (not a prompt defect): blot.md rules 5 and 6 require Super VL + Dots review of agent prompts and of each fixed round. This Haiku-only review does not meet that; the lead must run it before the prompt is sent.

FINAL: 5 findings (1 MEDIUM, 4 LOW). Verdict: NEEDS FIXES (fix finding 1; 2-5 are cheap).
