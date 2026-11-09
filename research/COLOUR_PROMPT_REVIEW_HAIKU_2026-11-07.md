# Reviewer RC (haiku, medium): colour research prompt review, 2026-11-07

Reviewed: research/_prompt_colour_research.md (read-only). Checked against docs/UI_COLOUR_SYSTEM_GUIDE_2026-11-07.md (v1), docs/UI_REDESIGN_PLAN_2026-11-07.md, ui/static/style.css, index.html, ui/test_static.py.

Verified OK: all paths in the prompt exist (plan, ui/test_*.py, research/ in anime_studio_merge). All contrast numbers in line 9 recomputed with WCAG formula: correct (light 10.54/11.10/5.51/5.88/1.21/6.65/9.69; dark 12.09/10.43/9.49/9.51/1.74/7.22; reading 9.12/5.09). Index has Story, Images, Bridge, Export, Video, Ops, Runs; no timeline, scene or asset browser found. Scope rule (line 3) is correct.

1. HIGH | line 8 and 10 | Prompt says "no ThemeProvider" but omits that style.css already has data-theme and prefers-color-scheme token blocks (lines 59-110, --page-bg #14130f, --accent #f0b45a). The redesign plan (lines 373-390) defines a third palette (--page-bg #f7f5f0, --fg #1c1b1a, dark --fg #f3f1ec). This is a real conflict with the owner palette. Fix: add to line 8: "style.css lines 59-110 already define theme tokens with a different palette; docs/UI_REDESIGN_PLAN lines 373-390 define another. List every conflict in the report; do not choose silently."

2. MEDIUM | line 13 | v1 section 7 says body text 16-18px; the plan (line 395) sets body 1rem = 20px. Prompt asks to "say how it fits the larger (>=20px) plan" but does not flag the v1 vs plan conflict. Fix: add "v1 sec 7 says 16-18px, plan says 20px: report as a conflict for the lead."

3. MEDIUM | line 12 and 14 | Prompt asks for a new contrast test. ui/test_static.py already has TEXT_ON_BG (line 469) and the plan (line 731) proposes test_body_text_contrast_is_at_least_7. Fix: "Propose extending TEXT_ON_BG in ui/test_static.py, not a new test file."

4. MEDIUM | line 16 | Logging says "after every step run with the Bash tool". WebSearch and WebFetch steps are not Bash. Fix: "After every step, including web steps, run the echo via Bash."

5. LOW | line 16 | Pipe rule has no fallback. Fix: "Write | inside a result as /."

6. LOW | line 14 | v1 section 1 is copied word for word, and the override (no commit/push) is stated in the same line. Still, a reader could be confused. Fix: "Put a one-line v2 note above the copied section: the commit and push steps do not apply to this agent."

7. LOW | line 14 | "Keep every requirement of v1" conflicts with "section 6 is the only section allowed to shrink". Fix: "Section 6 may shrink to the scope line; all other v1 requirements stay."

8. LOW | line 9(a) | The 3:1 rule (WCAG 1.4.11) applies only to boundaries needed to identify a control, not decorative dividers. Fix: "border/bg 1.21 and 1.74 fail 3:1 only where the border identifies an input or control."

9. LOW | line 9 | Reading "secondary/bg 4.77" is valid only if #59635E is used; v1 section 3C has no reading secondary token. Fix: add "(assumes #59635E, not in v1)".

10. LOW | line 5 and 14 | Overwrite risk: v1 and v2 names differ only by _v2. The prompt says open v1 read-only, so the risk is small. Fix: optional, "check v2 path differs from v1 before write."

11. LOW | line 3 and 5 | v1 section 5 lists caption editor, rendering and export controls. Forms for these in index.html are UI scope; preview and rendered output are not. Fix: add "control-panel forms are in scope; caption preview and rendered output are not."

Review of the two free reviewers' outputs (research/COLOUR_PROMPT_REVIEW_SUPERVL and _DOTS):
- SUPERVL F1 (log path anime_studio vs merge): WRONG. CLAUDE.md in both trees names D:\aai work\anime_studio\PROJECT_LOG.md as the one log. Intentional.
- SUPERVL F2 ("do not touch ui/" vs reads): WRONG. Line 16 already says read-only inspection is allowed.
- DOTS HIGH 1 (same log path): WRONG, same as SUPERVL F1.
- DOTS HIGH 2 (copied git rules vs no-commit): PARTLY. Line 14 already overrides. Downgrade to low (finding 6).
- DOTS MED 3 (overwrite risk): WEAK. Downgrade to low (finding 10).
- DOTS MED 4 (non-Bash logging): REAL (finding 4).
- DOTS MED 5 (pipe rule): REAL but minor (finding 5).
- DOTS LOW 6 and 7 (no priority, table placement): REAL, low. Not listed above; add "table goes in an appendix" if you want it fixed.

Note (not in prompt): anime_studio_merge/PROJECT_LOG.md also exists. The CLAUDE.md rule names only anime_studio/PROJECT_LOG.md. Lead should check whether the merge copy is stale.

FINAL: 11 findings (1 high, 3 medium, 7 low). Verdict: NEEDS FIXES. Fix findings 1-4 before the research agent starts; the rest are optional.
