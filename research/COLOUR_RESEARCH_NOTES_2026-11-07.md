# Colour research notes, 2026-11-07 (control-panel UI only)

Scope: the control panel in `ui/static/`. Nothing in the pipeline (render, captions, video, audio, images, export) is in scope.
Agent: colourRes(haiku,medium). Writes: this file, `docs/UI_COLOUR_SYSTEM_GUIDE_2026-11-07_v2.md`, PROJECT_LOG lines. No commits, no code, no model calls.

## 1. Sources and what each supports

Confidence tags: strong, moderate, weak, none found. "Read" means fetched in this run; "snippet" means a search summary only.

| # | Claim | Source | Read how | Confidence |
|---|---|---|---|---|
| S1 | WCAG 1.4.3: normal text 4.5:1, large text 3:1; large text = 18 pt or 14 pt bold; inactive UI components have no contrast requirement; ratios are not rounded | https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html | Read | strong |
| S2 | WCAG 1.4.11: UI component states and boundaries need 3:1 against adjacent colours; a boundary need not meet 3:1 when visible text already identifies the control; inactive components exempt | https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html | Read | strong |
| S3 | WCAG 2.4.13 Focus Appearance is Level AAA: indicator area at least a 2 CSS px perimeter; change in contrast 3:1 between focused and unfocused states; a 2px inset outline fails, a 3px inset passes | https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance | Read (published page) | strong for the text; the page is the published Understanding doc. The editor's-draft URL "focus-appearance-enhanced" (https://w3c.github.io/wcag/understanding/focus-appearance-enhanced) was NOT fetched and is not cited as normative (finding 13) |
| S4 | APCA is not normative. Recent secondary sources say it was pulled from the WCAG 3 working draft; WCAG 2.x ratios remain the compliance basis in most law and policy | https://adrianroselli.com/2026/04/wcag3-contrast-as-of-april-2026.html ; https://a11ybot.pages.dev/news/wcag-3-working-draft-2026/ ; https://github.com/Myndex/apca-w3 | Snippet (search summaries) | moderate. The W3C's own draft page was not checked. Treat "pulled" as unconfirmed. |
| S5 | 2.4.11 Focus Not Obscured (Minimum) is WCAG 2.2 Level AA: the focused control must not be fully hidden (for example by a sticky header) | https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html | Not fetched | strong for existence and level (normative criterion); text paraphrased, not re-read this run |
| S6 | 1.4.1 Use of Colour: colour must not be the only visual means of conveying information | https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html | Not fetched | strong (normative criterion) |
| S7 | 1.4.12 Text Spacing and 2.4.7 Focus Visible | https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html ; https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html | Not fetched | strong (normative criteria) |
| S8 | `prefers-contrast` values: no-preference, more, less, custom; widely available; the custom value matches the forced-colors palette | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-contrast | Read | strong |
| S9 | `color-scheme` tells the browser which colour scheme the page uses, so built-in controls and scrollbars follow it | https://developer.mozilla.org/en-US/docs/Web/CSS/color-scheme | Not fetched | moderate (from the spec and MDN knowledge). OPEN: fetch this page before shipping (finding 13) |
| S10 | Light-green reading study: Li, Guan, Wu and Bai, Frontiers in Psychology 2025, doi 10.3389/fpsyg.2025.1627013. Design details in section 2 below | https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1627013/full | Read | see section 2 |
| S11 | Positive-polarity (dark text on light) helped visual acuity and proofreading for both younger and older adults in a 2024 arXiv study; the NN/g summary of Piepenbrock et al. reports no daytime polarity effect and a night-time advantage for light mode | https://arxiv.org/pdf/2409.10841v1.pdf ; https://www.nngroup.com/articles/dark-mode/ | Snippet | moderate for the direction, weak for generalisation (small, lab-based, not a pilot with a 60-year-old reader) |
| S12 | Contrast sensitivity falls from about age 65, mainly at mid and high spatial frequencies; causes are pupil size, lens and vitreous changes, and neural factors | https://livrepository.liverpool.ac.uk/3086081/ (colour constancy across the life span) and a 2006 Vision Research study on simulated lens yellowing (title and year from snippet; not read) | Snippet | moderate |
| S13 | Lens yellowing increases absorption of short-wavelength light and is linked to acquired blue-yellow (tritan) colour loss; discrimination of small colour differences worsens with age, colour appearance is largely stable | the same Liverpool source and the lens-yellowing sources surfaced by the search | Snippet | moderate for the mechanism; weak for how much it affects a screen reader's day |
| S14 | Blue-light claims for screens (sleep, eye strain): no usable primary source found in this run | none found | - | none found |
| S15 | Astigmatism and dark mode: no controlled study found. Some blog posts claim both that dark mode helps and that it hurts | none found (only blogs and retailer pages) | - | none found |
| S16 | Warm off-white backgrounds vs pure white: no study found in this run that compares them | none found | - | none found |

## 2. The 2025 light-green reading study (v1 section 3C)

Found: yes. Li, Guan, Wu and Bai, "Light green background enhances reading performance in visual display terminal tasks", Frontiers in Psychology, 25 July 2025, doi 10.3389/fpsyg.2025.1627013.

- Design: within-subjects background (light green RGB 207,232,204 = #CFE8CC vs white #FFFFFF) crossed with between-subjects gender; separate Chinese (Exp 1) and English (Exp 2) reading tasks.
- Sample: 40 native Chinese-speaking university students, 20 women and 20 men, mean age 22.6. The paper reports no age range. A G*Power estimate of 34 was used.
- Task: timed multiple-choice reading comprehension, 20 questions per set, 4 options; a 13-inch laptop at 1366 x 768 and 38 cd/m2.
- Key results: pupil diameter larger under green in both experiments (Exp 1 eta_p2 = 0.28; Exp 2 eta_p2 = 0.31), but in Exp 2 only for women. Negative affect lower under green in Exp 1 (eta_p2 = 0.10). A subjective difficulty rating lower under green in Exp 1 (eta_p2 = 0.12). Reaction time and accuracy: no significant effect in either experiment (reaction time: marginal, p < 0.1).
- Limits stated by the authors: no pre-test mood measure; reading material valence not rated; short exposure; mediation hypotheses not supported; 2.5 to 15% of data excluded.
- Our reading: the study does not show better reading performance. The abstract's "improved reading performance" rests on one subjective rating. The pupil measure is the main finding, and it is a fatigue proxy with unclear meaning. Participants were young, and the English result was limited to women. The green colour is #CFE8CC, which is the owner's optional reading background.
- Rating: weak evidence for a reading benefit; the reading mode is a reasonable optional theme for the owner to test, not a default. Rated "weak" in v2.

## 3. Conflicts found (for the lead)

Values compared: v1 owner palette (`UI_COLOUR_SYSTEM_GUIDE_2026-11-07.md`), current `ui/static/style.css` lines 13-127, and the redesign plan (`docs/UI_REDESIGN_PLAN_2026-11-07.md` section 4.1, lines ~365-391). The table has rows C1-C20 (C20 is an owner rule); review fix 12 added rows C21-C25 for the dark muted value and the four renamed or unmapped tokens (`--hover`, `--th-bg`, `--indigo`, `--input-bg`).

| # | Token / item | v1 owner palette | style.css (now) | redesign plan | v2 decision |
|---|---|---|---|---|---|
| C1 | Light background | #F3F1E8 | #f7f5f0 | #f7f5f0 | v1 (owner approved) |
| C2 | Light card surface | #F8F7F0 | #ffffff | #ffffff | v1 |
| C3 | Light body text | #343834 | #1c1b1a | #1c1b1a | v1 |
| C4 | Light secondary text | #59635E (5.51 bg) | #4a4744 (muted) | #4a4744 | v2 uses #464F4A (7.49 bg / 7.89 surf): meets the 7:1 target the plan sets. Both v1 and style.css fail/pass differently; this is a change. |
| C5 | Accent / primary | teal #28665F | primary blue #1f4e8c, accent amber #f0b45a | blue #1f4e8c, amber #f0b45a | Conflict the lead must decide. v2 keeps v1 teal for accent and button, and maps the plan's blue to the running state only (see section 4 of v2). |
| C6 | Border | #D9DED6 (1.21, fails 3:1 for controls) | #8a847b line, #6b6660 field-line | same | v2: decorative border #D9DED6 kept; control boundary #66706A (4.54). |
| C7 | Dark background / surface | #181B1A / #232826 | #14130f / #1e1d19 | #14130f / #1e1d19 | v1 |
| C8 | Dark text | #DED7C5 | #f3f1ec | #f3f1ec | v1 |
| C9 | Dark accent | #9CC9BE | #f0b45a (amber) | #f0b45a | Conflict C5 again. |
| C10 | Dark border | #3A4540 (1.74) | #5a564f | #5a564f | v2: decorative #3A4540; control boundary #808C86 (4.97 bg). |
| C11 | Focus ring | #28665F | #0b57d0 (light) / #8ab4ff (dark) | same | Conflict. v2 proposes v1 teal (5.88 bg, 6.20 surf). The plan's blue #0b57d0 gives 6.4 on panel and is also valid; the lead picks one. |
| C12 | Body text size | 16-18 px (section 7) | 1rem at 125% root = 20 px | >= 20 px | v2 follows the plan (owner's 16-18 px is the lower bound for dense UI; the 60-year-old reader wins). Lead decides. |
| C13 | Minimum font | 16 px (section 7) | 17 px (test) | 17 px | v2: 17 px floor (plan). |
| C14 | Touch target | not stated | button min-height 44px test | 48 px (test changed) | v2: 48 px. |
| C15 | 7:1 body test | v1 section 9 gives 4.5 for normal text | `test_body_text_contrast_is_at_least_7` exists (BODY_TEXT_PAIRS lines 499-507) | plan asks for a new test | Plan's new test duplicates the existing one. v2 proposes extending BODY_TEXT_PAIRS only. |
| C16 | 4.5 floor test | - | `test_text_contrast_meets_wcag_aa_in_light_and_dark` uses TEXT_ON_BG (4.5) | - | Keep. |
| C17 | Theme switch | required (section 8) | no JS switch; `data-theme` read by CSS but never set; system preference only | not in plan | v2 adds a switch plan (section 6 of v2); no code now. |
| C18 | Step names | steps not named | six steps: story, analysis, images, readout, render, export (index.html) | Story, Plan, Pictures, Summary, Video, Files | Real screens are the index.html ones. The plan names differ; the lead decides which names v2 uses. v2 lists the file names and says the names are not final. |
| C19 | Reading theme | optional (section 3C) | none | none | v2 keeps it as an optional, separately testable theme, low priority. |
| C20 | Protect animation output (section 6) | rule | n/a | n/a | Replaced by the one-line scope rule (owner, 2026-11-07). C20 is an owner rule, not a colour conflict. |
| C21 | Dark secondary text (`--muted`) | #c9c4ba (dark block of style.css, both blocks) | #c9c4ba | not stated | v2 dark secondary is #B9C2BA (9.49 bg, 8.19 surf). Dark muted changes value; row added in finding 12 review. |
| C22 | `--hover` name | #eaeaea light / #33333d dark (old name) | `--hover` | not named | Renamed to `--hover-bg` in the v2 map (guide 4.0). The v2 table's new `--hover-bg` collided with the old name; one name kept. |
| C23 | `--th-bg` (table header) | #e9e9e6 / #26262e | `--th-bg` | not named | Not in the v2 token tables before the review fix; now `--table-head-bg` (guide 4.0, 4.1), value kept. |
| C24 | `--indigo` (header) | #1d1b3a / #2d2b5c | `--indigo` | not named | Not in the v2 token tables before the review fix; now `--header-bg` (guide 4.0), value kept. |
| C25 | `--input-bg` (input fill) | #ffffff / #15151b | `--input-bg` | not named | Not in the v2 token tables before the review fix; kept name and value (guide 4.0, 4.1). |

## 4. What I could not find or verify

- Open before shipping (finding 13): the MDN `color-scheme` page (S9) and the WCAG 2.4.13 editor's-draft URL (S3) were not fetched.
- APCA's official W3C status (S4): secondary sources only.
- Any study on astigmatism and polarity (S15).
- Any usable blue-light study for screens (S14).
- Any study on warm off-white vs white (S16).
- Whether colour contrast of disabled controls matters for this owner (WCAG exempts them; no evidence either way).
- Exact text sizes in the 2025 green study (font size not reported in the text we read).

## 5. Method and limits

- Contrast ratios: WCAG 2 relative luminance formula, computed with a throw-away Python snippet that printed numbers and wrote no file. The lead's figures for v1 pairs were reproduced exactly (10.54, 11.10, 5.51, 5.80, 5.88, 6.20, 6.65, 1.21, 9.69; dark 12.09, 10.43, 9.49, 8.19, 9.51, 8.21, 1.74, 7.22; reading 9.12, 4.77 (assumed #59635E), 5.09).
- The 4.77 figure for the reading theme secondary is the lead's assumption: v1 defines no reading-theme secondary token. v2 uses primary text for reading body copy instead.
- Owner-assumption and lead-input claims (60-year-old reader, 4.77 figure, the 7:1 target) carry those tags in v2 and have no URL.
