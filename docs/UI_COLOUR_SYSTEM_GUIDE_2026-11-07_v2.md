# Agent Implementation Guide

## Anime Studio control panel: research-hardened UI colour system (version 2)

Version 1 is the owner's guide, unchanged: `docs/UI_COLOUR_SYSTEM_GUIDE_2026-11-07.md`. Sources and conflicts: `research/COLOUR_RESEARCH_NOTES_2026-11-07.md`.

**SCOPE (owner, 2026-11-07, binding):** this guide is ONLY for the control-panel UI in `ui/static/` (colours, theme switch, text). It does not apply anywhere else in the pipeline: not the render, caption styling, video, audio, image generation, director, h3, core or any exported file. No pipeline file is touched or proposed for change. [v2: change, scope rule, owner 2026-11-07]

Repository: https://github.com/satviksangamkar11/Anime-Studio.git
Working directory: D:\aai work\anime_studio_merge
Status: PROPOSAL. Nothing in this file has been implemented. The colour work starts only after the wizard and expert-tool tasks (T3, T4) are verified (section 9).

Tag key: `[v2: change, reason, source]` marks a change from v1. `[v2: removed, scope rule]` marks a v1 pipeline item that is out of scope. `owner-assumption` and `lead-input` are claims with no URL. Confidence in the evidence table: strong, moderate, weak, none found.

---

## 1. IMPORTANT GIT SAFETY RULES

Copied word for word from v1 section 1. [v2: no-commit override] applies to the line that needs a commit.

Before editing anything:

1. Work exclusively inside D:\aai work\anime_studio_merge.
2. Verify the current branch is merge-v4-universal-2026-11-07.
3. Preserve all existing local commits, particularly f330c61 and 4268ab5.
4. Do not switch branches.
5. Do not perform destructive Git operations.
6. Never execute git reset --hard, git clean -fd, or destructive history rewrites.
7. Do not push anything to GitHub.
8. Do not overwrite existing user changes.
9. Do not modify the other V4, Universal or main worktrees.

First inspect:

    git status --short
    git branch --show-current
    git log --oneline -8

If the branch or repository state differs from expectations, report the discrepancy before making changes.

[v2: no-commit override] Do not commit changes unless explicitly authorized. (This research pass made no commits; the no-commit rule in the research brief overrides any commit step here.)

---

## 2. SCOPE AND WHAT EXISTS (one section: what exists, what does not, applies to this app)

Checked by reading `ui/static/index.html`, `style.css`, `i18n.js`, `pipeline.js` and the test file layout in `ui/test_*.py`. [v2: change, v1 listed screens that are not in this app, source: the files above]

| Area (v1 section 5) | Exists today? | Where | Applies to this app |
|---|---|---|---|
| Main background, header, footer | Yes (header with chips, no footer) | index.html header, `#chip-*` | Yes |
| Navigation, sidebar | Stepper (`nav#stepper`, six `li#step-*`) and the Experts `details#advanced-tools` | index.html | Yes |
| Top toolbar, panel separators | Not present as such | - | not present [v2: removed, scope rule] |
| Timeline, scene editor, preview workspace | not present | - | not present (no timeline or scene editor in this app) [v2: removed, scope rule] |
| Properties panel | not present | - | not present [v2: removed, scope rule] |
| Asset browser, character/environment/object controls, layer panels | not present | - | not present [v2: removed, scope rule] |
| Script editor, caption editor | not present as editors; `textarea#story-text` only | index.html line 149 | Yes, the story text box (plain form) |
| Audio, voice, export settings | Form fields in the Experts area and `#export-*` | index.html | Yes, forms and status only; no pipeline behaviour |
| Rendering controls, pipeline status, progress | `#progress-table`, `#jobs-table`, `pre#log-tail`, `#pipe-banner` | index.html | Yes, forms and status only; no pipeline behaviour |
| Dialog boxes and confirmations | `div#modal.overlay > .dialog` | index.html line 380 | Yes |
| Popovers, dropdowns | `select` elements only | index.html | Yes (native controls) |
| Buttons | `button`, `.btn-main`, `.btn-quiet`, `.danger` | style.css | Yes |
| Inputs, checkboxes, radio controls | `input[type=checkbox|radio]`, `select`, `textarea` | index.html | Yes |
| Tabs | not present | - | not present |
| Tables | `.tablewrap > table` (about 10 tables) | index.html | Yes |
| Notifications, errors | `#error-bar` (role alert), `#pipe-banner`, success bar | index.html line 32 | Yes |
| Empty states, loading | `No job output yet.`, `No job running.` (`data-i18n` idle text) | index.html | Yes |
| Status chips | `.chip`, `.status-locked` etc. on `li` | style.css line 540 | Yes |
| Writer cards (radio) | planned, not built | plan section 2.4 | Planned only |
| Theme switch | not present: no JS sets `data-theme`; `prefers-color-scheme` is the only switch | style.css lines 59-95 | Planned (section 6) |
| Reading theme | not present | - | Optional, low priority |
| Charts, graphs | not present | - | not present |
| Tooltips | `title` attributes only | index.html | Yes (plain title attributes) |
| Code syntax highlighting | not present (`pre.log` is plain text) | - | not present |
| Scrollbars | browser default | - | Yes, `color-scheme` covers them |
| Caption previews, rendered output | out of scope (scope rule) | - | `[v2: removed, scope rule]` |

Step names: the six steps in index.html today are story, analysis, images, readout, render, export. The redesign plan renames them (Story, Plan, Pictures, Summary, Video, Files). Which names v2 uses is a lead decision (notes C18). This guide does not depend on the names.

---

## 3. DESIGN OBJECTIVE

Build one colour system for the control panel. [v2: change, scope narrowed to the control panel]

The control panel must support:

* Light Mode.
* Dark Mode.
* System preference when no manual override is set.
* Manual theme override that persists.
* Readable typography and controls.
* Clear visual hierarchy.
* Contrast that meets WCAG 2.2 AA and the owner's 7:1 body-text target.
* Comfortable long use.

Scientific restriction (kept from v1): do not advertise any HEX code as clinically proven to prevent eye fatigue. The palette is research-informed. Its performance must be checked by usability testing with the owner and the helper. [v2: kept, v1 section 2; source for the restriction: the evidence table, row E15 only (E14 is "none found" and is not cited; E16 is the 7:1 target, not this restriction)]

---

## 4. APPROVED PALETTE (owner's v1 starting point) AND THE v2 CORRECTIONS

The owner's v1 palette stays the starting point. v2 changes only the values that fail a measured rule. Each change carries its tag.

### 4.0 Old-to-new token map (every custom property in `ui/static/style.css`) [v2: change, finding 1; source: style.css lines 15-127 read in this pass]

`grep` of `--name:` in `style.css` gives 42 names: 31 colour names (light block lines 15-56; dark block lines 61-91 under `@media (prefers-color-scheme: dark)`; explicit `:root[data-theme="dark"]` block lines 96-127, which repeats the same dark values), plus `--shadow`, 7 spacing names (`--s1` to `--s7`) and 3 radius names. The two dark blocks have the same values. Column "Test reads" marks names that `ui/test_static.py` reads (lists at lines 469-500). A rename breaks those tests, so the rename must go in one change with the test update (section 8, item 6). This guide does not edit `ui/test_static.py`.

| Old name (style.css) | Light (old) | Dark (old) | v2 name | Light (v2) | Dark (v2) | Status | Test reads |
|---|---|---|---|---|---|---|---|
| `--indigo` | #1d1b3a | #2d2b5c | `--header-bg` | #1D1B3A | #2D2B5C | new name, value kept | yes |
| `--page-bg` | #f7f5f0 | #14130f | `--app-bg` | #F3F1E8 | #181B1A | renamed, value changed to v1 owner palette (C1, C7) | yes |
| `--panel` | #ffffff | #1e1d19 | `--surface` | #F8F7F0 | #232826 | renamed, value changed (C2, C7) | yes |
| `--fg` | #1c1b1a | #f3f1ec | `--text-primary` | #343834 | #DED7C5 | renamed, value changed (C3, C8) | yes |
| `--muted` | #4a4744 | #c9c4ba | `--text-secondary` | #464F4A | #B9C2BA | renamed, value changed (C4; dark conflict row C21) | yes |
| `--line` | #8a847b | #5a564f | `--border` (decorative) and `--control-border` (controls) | #D9DED6 / #66706A | #3A4540 / #808C86 | split by use, value changed (C6, C10) | no |
| `--field-line` | #6b6660 | #8a8a94 | `--control-border` | #66706A | #808C86 | renamed, value changed (C6, C10) | no |
| `--input-bg` | #ffffff | #15151b | `--input-bg` | #FFFFFF | #15151B | name and value kept; computed in 4.1 | no |
| `--th-bg` | #e9e9e6 | #26262e | `--table-head-bg` | #E9E9E6 | #26262E | new name, value kept; computed in 4.1 (finding 2) | no |
| `--hover` | #eaeaea | #33333d | `--hover-bg` | #E6E9E1 | #2E3431 | renamed; `--hover` is retired, `--hover-bg` is the only hover name (finding 3) | no |
| `--focus` | #0b57d0 | #8ab4ff | `--focus-ring` | #28665F | #9CC9BE | renamed, value changed; the blue alternative stays open (C11) | yes |
| `--primary` | #1f4e8c | #9ec1ff | `--button-bg` | #28665F | #9CC9BE | renamed, value changed; the blue is kept for the running state only (`--blue`) | no |
| `--primary-fg` | #ffffff | #0d1b2e | `--button-text` | #FFFFFF | #181B1A | renamed, dark value changed | no |
| `--accent` | #f0b45a | #f0b45a | `--accent` | #28665F | #9CC9BE | name kept, meaning changed from amber to teal; OPEN, conflict C5 (the amber is lost unless the lead keeps it under another name) | yes |
| `--accent-fg` | #1c1b1a | #1c1b1a | `--accent-fg` | #FFFFFF | #181B1A | name kept, value changed for the teal accent (6.65 light, 9.51 dark) | yes |
| `--ok` | #165c33 | #165c33 | `--ok` | #165C33 | #165C33 | kept; white on it 8.04; not in v2 4.2 as a fill | yes |
| `--ok-fg` | #14532d | #bdf0cf | `--ok-fg` | #14532D | #BDF0CF | kept (matches 4.2) | yes |
| `--amber` | #c27a00 | #f0b429 | `--amber` | #C27A00 | #F0B429 | kept as is; decorative or status accent, no text-contrast claim; check its uses when T2 colour work starts | no |
| `--amber-bg` | #ffe2a8 | #ffd27a | `--amber-bg` | #FFE2A8 | #3D3210 (dark warning tint, 4.2) | light kept; dark role changed (old dark fill becomes text, 4.2) | yes |
| `--amber-fg` | #3d2c00 | #2a1f00 | `--amber-fg` | #3D2C00 | #FFD27A | light kept; dark changed to the 4.2 warning text | yes |
| `--red` | #a8231b | #ff9b91 | `--red` | #A8231B | #FF9B91 | kept; white on it 7.19; status row: light white on #A8231B 7.19; dark #1A0606 on #FF9B91 9.65 (recomputed 2026-11-07) | yes |
| `--red-fg` | #ffffff | #1a0606 | `--red-fg` | #FFFFFF | #1A0606 | kept; dark 9.65 | yes |
| `--err-fg` | #7a1010 | #ffd9d6 | `--err-fg` | #7A1010 | #FFD9D6 | kept (4.2) | yes |
| `--blue` | #1f4e8c | #9ec1ff | `--blue` | #1F4E8C | #9EC1FF | kept; the running state only (4.2 info) | yes |
| `--blue-fg` | #ffffff | #0d1b2e | `--blue-fg` | #FFFFFF | #0D1B2E | kept | yes |
| `--grey` | #55524e | #55524e | `--grey` | #55524E | #55524E | kept; white on it 7.77 (the plan's 7.8 is confirmed) | yes |
| `--tint-amber` | #fff4d6 | #3d3210 | `--tint-amber` | #FFF4D6 | #3D3210 | kept; dark value is the 4.2 warning tint | no |
| `--tint-green` | #e7f5ec | #163626 | `--tint-green` | #E7F5EC | #163626 | kept (4.2) | yes |
| `--tint-red` | #fde8e8 | #3f1d1d | `--tint-red` | #FDE8E8 | #3F1D1D | kept as is; background tint only, text on it uses primary text (checked via 4.1 text/surface ratios) | no |
| `--tint-error-bar` | #fde8e8 | #3e1715 | `--tint-error-bar` | #FDE8E8 | #3E1715 | kept (4.2) | yes |
| `--tint-grey` | #efeeea | #26262e | `--tint-grey` | #EFEEEA | #26262E | kept as is; background tint only, text on it uses primary text (checked via 4.1 text/surface ratios) | no |
| `--shadow` | 0 2px 8px rgba(0,0,0,0.1) | 0 2px 8px rgba(0,0,0,0.5) | `--shadow` | kept | kept | kept | no |
| `--s1` to `--s7` | 4px to 48px | same | `--s1` to `--s7` | kept | kept | kept (plan 4.1 spacing) | no |
| `--r-sm`, `--radius`, `--r-lg` | 8px, 12px, 16px | same | same | kept | kept | kept | no |

Rules behind the map: every name above is kept, mapped or retired; none is dropped silently. `--line` and `--field-line` are split by use: decorative rules go to `--border`, control and table borders go to `--control-border`. Old values in the dark column are the same in both dark blocks.

### 4.1 Corrected token table (both themes) with computed contrast

Computed with the WCAG 2 formula. Ratios are rounded to two places. Rule: body text 7:1 (owner target, v1 section 9 and the plan); normal text 4.5:1 (WCAG 1.4.3); non-text boundaries and focus 3:1 (WCAG 1.4.11, 2.4.13).

**Light**

| Token | v1 HEX | v2 HEX | Use | Contrast (v2) | Tag |
|---|---|---|---|---|---|
| `--app-bg` | #F3F1E8 | #F3F1E8 | page | - | kept |
| `--surface` | #F8F7F0 | #F8F7F0 | cards | - | kept |
| `--text-primary` | #343834 | #343834 | body text | 10.54 on bg, 11.10 on surface | kept |
| `--text-secondary` | #59635E | #464F4A | hints, secondary labels | 7.49 on bg, 7.89 on surface, 7.11 on editor | [v2: change, v1 5.51 on bg fails the owner 7:1 body target, source: WCAG 1.4.3 S1 and plan 7:1] |
| `--accent` | #28665F | #28665F | links, current step | 5.88 on bg, 6.20 on surface | kept (passes 4.5; links are underlined, v1 section 7) |
| `--border` | #D9DED6 | #D9DED6 | decorative separators only | 1.21 on bg | kept, but not for controls: [v2: change, 1.21 fails the 3:1 control rule, source: WCAG 1.4.11 S2] |
| `--control-border` (new) | - | #66706A | input, select, checkbox and button outlines | 4.54 on bg, 4.78 on surface, 4.31 on editor | [v2: change, new token for control boundaries, source: S2] |
| `--button-bg` | #28665F | #28665F | main button | - | kept |
| `--button-text` | #FFFFFF | #FFFFFF | main button text | 6.65 | kept |
| `--selection-bg` | #DCEBE6 | #DCEBE6 | selected text, selected row | text #343834 on it 9.69 | kept |
| `--editor-bg` | #EAECE4 | #EAECE4 | log and code boxes | text 10.00 | kept |
| `--focus-ring` | #28665F | #28665F | focus outline, 3 px | 5.88 on bg, 6.20 on surface (3:1 change rule met) | kept; see 4.3 |
| `--hover-bg` (new) | - | #E6E9E1 | hover on buttons, rows | text #343834 9.71 | [v2: change, new token, source: plan section 4.2 and v1 section 4] |
| `--active-bg` (new) | - | #D3DBD0 | pressed state | text #343834 8.41 | [v2: change, new token, source: as above] |
| `--placeholder` (new) | - | #5E6661 | placeholder text only | 5.23 on bg, 5.51 on surface | [v2: change, new token; placeholder is not a label and must never be the only label, source: WCAG 1.4.3 S1 applies to placeholder text] |
| `--disabled-text` (new) | - | #7A827D | disabled controls | 3.68 on surface | exempt from contrast (S2, S1); shown with the reason in words next to it |
| `--table-head-bg` (new name; old `--th-bg`) | - | #E9E9E6 | table header cells | text #343834 9.80 | [v2: change, finding 2; new name, old value kept; computed in this pass] |
| `--input-bg` (name and value kept from style.css) | - | #FFFFFF | input, select, textarea fill | text #343834 11.92 | [v2: change, finding 1; computed in this pass] |
| `--header-bg` (new name; old `--indigo`) | - | #1D1B3A | header, active tab | white #FFFFFF 16.53 | [v2: change, finding 1; old value kept; computed in this pass] |
| `--accent-fg` (value for the teal accent) | - | #FFFFFF on `--accent` #28665F | text on accent fill | 6.65 | [v2: change, needed because the v2 accent is teal, not amber; computed in this pass] |

**Dark**

| Token | v1 HEX | v2 HEX | Use | Contrast (v2) | Tag |
|---|---|---|---|---|---|
| `--app-bg` | #181B1A | #181B1A | page | - | kept |
| `--surface` | #232826 | #232826 | cards | - | kept |
| `--text-primary` | #DED7C5 | #DED7C5 | body text | 12.09 on bg, 10.43 on surface | kept |
| `--text-secondary` | #B9C2BA | #B9C2BA | hints | 9.49 on bg, 8.19 on surface | kept (passes 7:1) |
| `--accent` | #9CC9BE | #9CC9BE | links, current step | 9.51 on bg, 8.21 on surface | kept |
| `--border` | #3A4540 | #3A4540 | decorative separators only | 1.74 on bg | kept for decoration only; [v2: change, 1.74 fails 3:1 for controls, source: S2] |
| `--control-border` (new) | - | #808C86 | input, select, checkbox and button outlines | 4.97 on bg, 4.29 on surface | [v2: change, new token, source: S2] |
| `--button-bg` | #9CC9BE | #9CC9BE | main button | - | kept |
| `--button-text` | #181B1A | #181B1A | main button text | 9.51 | kept |
| `--selection-bg` | #2B4540 | #2B4540 | selection | text #DED7C5 7.22 | kept |
| `--editor-bg` | #1D2421 | #1D2421 | log and code boxes | text 11.03 | kept |
| `--focus-ring` | #9CC9BE | #9CC9BE | focus outline | 9.51 on bg, 8.21 on surface | kept |
| `--hover-bg` (new) | - | #2E3431 | hover | text #DED7C5 (primary) on it | [v2: change, new token; body text on hover uses primary text, not secondary, because secondary on hover measures 6.96] |
| `--active-bg` (new) | - | #3A4540 | pressed | text #DED7C5 6.95 | [v2: change, new token; 6.95 is under the 7:1 target but above 4.5; the owner may choose a lighter text if this matters] |
| `--placeholder` (new) | - | #9AA39C | placeholder | 6.69 on bg, 5.77 on surface | [v2: change, new token] |
| `--disabled-text` (new) | - | #6E776F | disabled | 3.23 on surface | exempt (S1, S2) |
| `--table-head-bg` (new name; old `--th-bg`) | - | #26262E | table header cells | text #DED7C5 10.46 | [v2: change, finding 2; as light; computed in this pass] |
| `--input-bg` (name and value kept from style.css) | - | #15151B | input fill | text #DED7C5 12.67 | [v2: change, finding 1; computed in this pass] |
| `--header-bg` (new name; old `--indigo`) | - | #2D2B5C | header, active tab | white #FFFFFF 13.03 | [v2: change, finding 1; computed in this pass] |
| `--accent-fg` (value for the teal accent) | - | #181B1A on `--accent` #9CC9BE | text on accent fill | 9.51 | [v2: change, computed in this pass] |

### 4.2 Status colours (new; the palette had none) [v2: change, status tokens are new, source: WCAG 1.4.1 S6 and the plan's status words]

Every status is shown with an icon and a word, never colour alone (v1 section 9, WCAG 1.4.1 S6).

| Status | Icon (plan section 4.3) | Light text / tint | Light contrast | Dark text / tint | Dark contrast |
|---|---|---|---|---|---|
| success / done | check | `--ok-fg` #14532D on `--tint-green` #E7F5EC | 8.10 | #BDF0CF on #163626 | 10.40 |
| warning / waiting | clock | #3D2C00 on `--amber-bg` #FFE2A8 | 10.71 | #FFD27A on #3D3210 | 8.88 |
| error / failed | alert | `--err-fg` #7A1010 on `--tint-error-bar` #FDE8E8 | 9.37 | #FFD9D6 on #3E1715 | 12.07 |
| info / running | info | #1F4E8C on #E3EDF9 | 7.02 | #9EC1FF on #1B2A40 | 7.94 |
| locked / not run | lock | `--grey` #55524E with white text | 7.77 (recomputed) | #55524E with white text | 7.77 (same colour in both themes) |

Note: the plan's blue (`--primary` #1F4E8C) is used for the running chip only, not as the button colour, so there is one button colour (teal, v1). See conflict C5 in the notes.

### 4.3 Focus rules [v2: change, source: S3 and S5]

* The focus indicator is a solid outline of 3 px with an outline offset of 2 px (current style.css rule; the 2.4.13 pass needs an area at least a 2 px perimeter; a 3 px inset outline passes, a 2 px inset fails).
* Contrast of the indicator against the unfocused state and the surface is at least 3:1 (6.20 on surface in light, 8.21 in dark).
* Focus must not be hidden under the sticky header or the error bar (2.4.11 Focus Not Obscured, WCAG 2.2 AA). The error bar and the sticky header scroll the focused element into view with `scrollIntoView({block: 'nearest'})` (plan section 4.2).

### 4.4 Placeholder, disabled, hover and active [v2: change, source: S1, S2]

* Placeholder: #5E6661 light / #9AA39C dark. Placeholder never replaces a label.
* Disabled: exempt from contrast by WCAG 1.4.3 and 1.4.11 (S1, S2). The reason is always written in text next to the control (plan section 4.2), never only in a tooltip.
* Hover: body text stays `--text-primary`.
* Active: no new hex claimed beyond the table above.

### 4.5 Reading theme (optional, not default) [v2: change, weak evidence, source: S10]

* Colours: bg #CFE8CC, surface #E0EFDD, text #343834 (9.12 on bg, 9.97 on surface), accent #28665F (5.09 on bg, 5.56 on surface).
* The reading theme uses primary text only for body copy. The v1 secondary figure of 4.77 is the lead's assumption (no reading-theme secondary token exists); it is not used.
* Evidence: Li et al. 2025 (n = 40, students, young adults) found a pupil-size effect and a subjective rating effect; objective reading time and accuracy did not differ. Rated weak. The theme must stay selectable and be tested separately, as v1 says.

---

## 5. TYPOGRAPHY AND READING ERGONOMICS

v1 section 7 gives body text 16-18 px. The redesign plan gives 1rem at a 125% root, which is 20 px. [v2: change, plan 20 px body for the 60-year-old owner's reader; lead decides, conflict C12]

| Parameter | v2 value | Tag |
|---|---|---|
| Body text | 1rem = 20 px at 125% root | [v2: change, plan; v1 16-18 px is the lower bound for dense text] |
| Hints | 0.9rem = 18 px | [v2: change, plan] |
| Smallest allowed text | 0.85rem = 17 px floor (test `test_no_font_size_below_17px`) | [v2: change, v1 had none; plan] |
| Main reading content | 1rem; 18 px only where the plan says | kept |
| Line height | 1.55 (1.7 in Marathi) | [v2: change, v1 1.5-1.7; plan] |
| Reading column width | 60-75 characters | kept |
| Heading hierarchy | h1 1.2rem, h3 1.3rem, h2 1.4rem | kept, plan |
| Links | underlined | kept |
| Focus | 3 px ring (4.3) | kept |
| Paragraph spacing | `--s3` 12 px | kept |
| Truncation | never for critical text | kept |
| Compact shrink | not allowed | kept |

Fonts: keep the existing choice. The Devanagari face is `ui/static/fonts/NotoSansDevanagari-Variable.ttf`, referenced by `url("fonts/NotoSansDevanagari-Variable.ttf")` in `style.css` line 7 (relative to `ui/static`; plan section 3.6). [v2: change, path corrected from `styles/fonts/`; the file is pending: `ui/static/fonts/` does not exist today and T2 adds it] The plan's licence path `styles/fonts/LICENSES/` (plan 3.6) was not checked in this pass; open item for the lead. No external font. [kept]

Ageing evidence for these choices (S12, S13): contrast sensitivity drops from about age 65, mainly at mid and high spatial frequencies, and the lens yellows and reduces sensitivity to short-wavelength (blue) light. This supports larger text, higher text contrast and avoiding blue-on-dark text. The strength is moderate for the mechanism and weak for any particular size; no study gives a size for a 60-year-old reader.

---

## 6. THEME SWITCHING (control panel only)

v1 section 8 requirements, kept. [v2: change, plan for the current code; the switch is not built]

Requirements:

* Light, Dark, optional Reading, and System (default).
* Manual override that persists.
* No page refresh.
* No white flash before the theme is known.

Mechanism (v2 proposal, no code now):

1. One new file `ui/static/theme.js` (about 30 lines) and one new file `ui/static/tokens.css`. The existing `style.css` colour blocks move into `tokens.css` [v2: change, one tokens file, plan section 4.1 (the plan has no section 3b)]. `style.css` keeps layout only.
2. The theme value is stored in `localStorage` under the key `studio.theme` with values `system`, `light`, `dark`, `reading`. Every read and write is wrapped in try/catch; when storage fails, the page uses `system`. [v2: change, mirrors the existing `studio.lang` pattern in i18n.js line 6 and its try/catch, source: i18n.js lines 6-49 read in this run]
3. No flash: a 5-line inline script in `<head>` (before the stylesheet) sets `document.documentElement.dataset.theme` from storage, before first paint. [v2: change, unsourced: the inline-head pattern has no URL and was not fetched; confidence none found. The `color-scheme` property it relies on is S9, not fetched]
4. CSS:
   * `:root { color-scheme: light; }` and `:root[data-theme="dark"] { color-scheme: dark; }`.
   * `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]):not([data-theme="reading"]) { color-scheme: dark; ...dark tokens... } }` so the system choice follows the OS when no override is set.
   * `@media (prefers-contrast: more)` raises `--control-border` and `--text-secondary` one step (S8). `@media (forced-colors: active)` leaves system colours alone (no custom colours).
5. `<meta name="theme-color">` is set to the app background of the active theme (light #F3F1E8, dark #181B1A). [v2: change, unsourced: no URL was fetched for this meta tag; confidence none found]
6. Transitions: `transition: background-color .15s, color .15s` only on surfaces and text, with the reduced-motion block from v1 section 11 (kept verbatim). [kept]
7. Theme and language are independent: `studio.theme` and `studio.lang` are two keys, and the language switch (`ui-lang-en`, `ui-lang-mr`) does not touch the theme. The Marathi line-height and font rules apply in both themes. [v2: change, fits the i18n plan section 3]

Files this touches (later task, after T3 and T4 are verified): `ui/static/tokens.css` (new), `ui/static/theme.js` (new), `ui/static/index.html` (the inline head script and two link tags only), `ui/static/style.css` (remove the colour blocks, keep layout). No change to `app.js` or `pipeline.js` except the `studio:lang` listener is unaffected. No pipeline file. Tests: `ui/test_static.py` reads tokens from the new file (section 8).

---

## 7. ACCESSIBILITY AND CONTRAST VALIDATION

v1 section 9 kept. [v2: change, WCAG 1.4.3 and 1.4.11 applied exactly; disabled exempt; source S1, S2]

Pairs to check (existing list plus v2 additions):

* Primary text on background and surface, both themes (kept).
* Secondary text on surface (changed to #464F4A light).
* Links on background (kept).
* Button text on button (kept).
* Placeholder text (new token).
* Disabled controls (exempt; still written with words).
* Form errors (`--err-fg` on `--tint-error-bar`).
* Focus indicators (3:1 rule).
* Tooltips (native `title`; no custom tooltip colours).
* Status text on tints (4.2).

Chart labels: the app has no charts (section 2), so this item is `not present`.

Reference combinations (v1 section 9, all re-computed; v1 values reproduced exactly):

| Combination | v1 expected | v2 computed | Note |
|---|---|---|---|
| Light text / bg | 10.54 | 10.54 | kept |
| Light text / surface | 11.10 | 11.10 | kept |
| Light secondary / bg | 5.51 | 7.49 (v2 #464F4A) | v1 fails 7:1 |
| Light accent / bg | 5.88 | 5.88 | kept |
| Dark text / bg | 12.09 | 12.09 | kept |
| Dark text / surface | 10.43 | 10.43 | kept |
| Dark secondary / bg | 9.49 | 9.49 | kept |
| Dark accent / bg | 9.51 | 9.51 | kept |
| Border / bg (light) | 1.21 | 1.21 decorative; control 4.54 | v1 fails 3:1 for controls |
| Border / bg (dark) | 1.74 | 1.74 decorative; control 4.97 | v1 fails 3:1 for controls |
| Selection text | 9.69 / 7.22 | 9.69 / 7.22 | kept |
| Reading text / bg | 9.12 | 9.12 | kept |
| Reading secondary / bg | 4.77 (lead assumption) | not used | v2 uses primary text |
| Reading accent / bg | 5.09 | 5.09 | kept |

---

## 8. TEST PLAN (existing pytest style in `ui/test_static.py`)

The control-panel tests are pytest functions that read `ui/static/style.css` text and parse colour tokens with regular expressions (`_css_tokens`, `_lum`, `_ratio`, existing lines 447-507). The style is kept. No new test framework.

Existing tests kept as they are: `test_text_contrast_meets_wcag_aa_in_light_and_dark` (4.5 floor, TEXT_ON_BG), `test_css_focus_ring_is_three_pixels_on_every_control`, `test_css_44px_touch_targets_and_pills` (min-height moves to 48 px, plan section 4.2).

Proposed additions (proposals, not code to commit):

1. **Extend `BODY_TEXT_PAIRS`, do not add a second 7:1 test.** The test `test_body_text_contrast_is_at_least_7` already exists (test_static.py lines 499-507). Its real pairs (`BODY_TEXT_PAIRS`, lines 499-500) use the current token names: `("fg","panel")`, `("fg","page-bg")`, `("muted","panel")`, `("muted","page-bg")`, `("err-fg","tint-error-bar")`, `("ok-fg","tint-green")`, `("amber-fg","amber-bg")`. The secondary-text-on-surface check is already `("muted","panel")`; no new pair is needed for it. Placeholder is excluded (4.5 target, not 7:1). After the rename in 4.0, the same pairs are read under the new names in the same change. The v1 secondary #59635E gives 5.51 on the background and would fail this existing test; v2 #464F4A passes. The plan's proposed new test (plan line 733) duplicates this test and is not needed. [v2: change, finding 4, source: test_static.py lines 499-507 and plan line 733]
2. **Control boundary test (3:1).** A test that reads `--control-border` (light and both dark blocks) and asserts 3:1 against `--surface` and `--app-bg`. Fails below the limit. [v2: change, S2]
3. **Status pairs test.** Every status pair in 4.2 must reach 7:1 (body-like) in both themes. [v2: change, source: 4.2]
4. **Focus ring test.** `outline: 3px solid var(--focus-ring)` exists (kept); a new check that `--focus-ring` reaches 3:1 on `--app-bg` and `--surface` in both themes. [v2: change, S3]
5. **Font floor.** Existing `test_no_font_size_below_17px` (kept).
6. **Token source.** After the tokens file exists, the `_css_tokens` helper reads `tokens.css` instead of `style.css`. The test is written first and fails until the move is done, so the move cannot silently drop a token. [v2: change]
7. **Theme init test.** Assert that `index.html` contains the inline head script before the stylesheet link and that the script wraps storage access in try/catch. [v2: change, section 6]
8. **Reduced-motion test.** Assert the `prefers-reduced-motion: reduce` block exists in `tokens.css` or `style.css` (already present at style.css line 1094; kept).

Manual checks before the task is marked done (owner's test plan, v1 section 12, control panel only), one line each:

* Theme selector works. [kept]
* Preference survives a reload. [kept]
* System preference works with no override. [kept]
* Manual choice beats system. [kept]
* All six steps and the Experts area render in both themes. [kept]
* All hash routes (`#story` to `#export`, `app.js` lines 1389-1393) render in both themes. [kept; the app has hash routes, so this check applies]
* Modals and the dialog (`div#modal`, index.html line 380) use the right theme. [kept]
* The Marathi page is readable in both themes. [kept]
* Error bar and form errors are readable in both themes. [kept]
* Timeline and scene editor checks. [v2: removed, scope rule; not present in this app]
* Preview-unchanged check for caption previews. [v2: removed, scope rule; out of scope]
* Exported video check. [v2: removed, scope rule; export is out of scope]
* No pipeline output is recoloured (nothing in the pipeline reads these tokens). [kept]

---

## 9. ORDER OF WORK (after the redesign program's coders finish)

1. Wait until T3 (pipeline.js wizard) and T4 (app.js expert tools) are verified and their suites pass, with the `PARITY_BUILT` env set as the lead requires (lead commit 8f061a2, per the NOW block of PROJECT_LOG.md; it is a lead rule, not a plan item). No colour work runs in parallel with a coder that owns `style.css` or `index.html`.
2. Add the test in 8.6 first; it fails.
3. Create `ui/static/tokens.css` and move the token blocks; add `ui/static/theme.js`; add the inline head script to `index.html`.
4. Apply the corrected tokens from section 4.1 and the status tokens from 4.2.
5. Run the existing suites (`ui` 252 pass plus the known one real-pack failure; the rules in the plan section 1) and the new tests.
6. Owner review in both themes. Screenshots of the six steps and the Experts area in each theme.

The English/Marathi switch is independent of the theme (section 6, point 7). The larger text plan (body 20 px, section 5) is applied in the same CSS pass as the tokens, so each token is tested once.

---

## 10. V1 REQUIREMENTS LEDGER

Every v1 requirement is listed here, so nothing is dropped silently.

| v1 section | Item | v2 status |
|---|---|---|
| 1 | Git safety rules | kept; line 'Do not commit' overridden (section 1) |
| 2 | Design objective (light, dark, consistent, readable, accessible, comfort) | kept, section 3 |
| 2 | No HEX clinically proven | kept, section 3 |
| 3A | Light palette (11 values) | kept; `--text-secondary`, `--border`, `--control-border` changed (4.1) |
| 3B | Dark palette (11 values) | kept; `--control-border` new (4.1) |
| 3C | Optional reading theme | kept, optional, weak evidence (4.5) |
| 4 | Centralised tokens | kept, section 6 (`tokens.css`) |
| 4 | Extra tokens: hover, active, disabled, tooltips, modals, dropdowns, inputs, validation, notifications, scrollbars, tables, graphs, code | hover, active, placeholder, disabled, control border, status (4.1, 4.2); tooltips = native title; modals = `--surface`; dropdowns = native select; validation = `--err-fg`; notifications = status tokens; scrollbars = `color-scheme`; tables = `--table-head-bg` (4.0, 4.1); graphs = `not present`; code = `--editor-bg` |
| 5 | Audit of every screen | replaced by section 2 (what exists) |
| 6 | Protect the animation output | [v2: removed, scope rule] replaced by the one-line scope rule (top of this file) |
| 7 | Typography 16-18 px, line height, column width | changed to plan 20 px body (section 5); conflict C12 |
| 7 | Preserve font choices | kept |
| 7 | Do not shrink the UI | kept |
| 8 | Light, dark, reading, system, manual, persistent, no refresh, no flash | kept, section 6 |
| 8 | Do not introduce a library | kept (no library) |
| 9 | WCAG 2.2 AA; 4.5 normal, 3 large | kept; 7:1 body target from the owner; `[v2: change, S1]` large text = 18 pt or 14 pt bold |
| 9 | Pairs list (placeholder, disabled, errors, focus, tooltips, chart labels) | kept (section 7; chart labels not present) |
| 9 | Reference combinations | kept, re-computed (section 7) |
| 9 | Do not rely on colour alone | kept, icon and word (4.2; S6) |
| 10 | Reusable components | kept as the component table in the plan; no new library |
| 10 | Avoid list | kept |
| 11 | Transition and reduced motion | kept (section 6, point 6) |
| 12 | Functional testing list | kept (section 8, manual checks, each line listed); three lines removed by the scope rule (timeline and scene editor, caption preview, exported video) |
| 12 | Visual testing in both themes | kept (section 9, step 6) |
| 12 | Technical testing | kept; existing pytest suites |
| 13 | Final report items | kept for the implementation task |
| 14 | Definition of done | kept for the implementation task |
| 4-5 pipeline items (caption styling, character colours, export colour settings, user artwork) | - | [v2: removed, scope rule]; none of these are touched by the theme |

---

## 11. EVIDENCE TABLE

| # | Claim | Source (URL) | Confidence |
|---|---|---|---|
| E1 | WCAG 1.4.3: 4.5:1 normal, 3:1 large; large = 18 pt or 14 pt bold; disabled exempt | https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html | strong |
| E2 | WCAG 1.4.11: 3:1 for UI states and boundaries; boundary may be exempt when text identifies control; disabled exempt | https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html | strong |
| E3 | WCAG 2.4.13 Focus Appearance is AAA; 2 px perimeter; 3:1 change; 2 px inset fails | https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance | strong |
| E4 | WCAG 2.4.11 Focus Not Obscured (Minimum) is AA | https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html (not fetched) | strong |
| E5 | APCA not normative; WCAG 2.x is the compliance basis | https://adrianroselli.com/2026/04/wcag3-contrast-as-of-april-2026.html (secondary) | moderate |
| E6 | `prefers-contrast` values | https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-contrast | strong |
| E7 | `color-scheme` property | https://developer.mozilla.org/en-US/docs/Web/CSS/color-scheme (not fetched) | moderate |
| E8 | Light-green background reading study, n = 40, pupil effect, objective performance n.s. | https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1627013/full | weak for reading benefit; moderate for the pupil measure |
| E9 | Positive polarity helped older and younger adults in visual tasks (lab) | https://arxiv.org/pdf/2409.10841v1.pdf (snippet) ; NN/g summary https://www.nngroup.com/articles/dark-mode/ | moderate direction; weak generalisation |
| E10 | Contrast sensitivity falls from about 65, mid and high frequencies | https://livrepository.liverpool.ac.uk/3086081/ (snippet) | moderate |
| E11 | Lens yellowing reduces short-wavelength light, linked to tritan loss; small colour discrimination worsens with age | same Liverpool source; 2006 Vision Research lens-yellowing study (snippet) | moderate mechanism; weak for screens |
| E12 | Blue-light claims for screens (sleep, strain) | none found | none found |
| E13 | Astigmatism and dark mode | none found | none found |
| E14 | Warm off-white vs white | none found | none found |
| E15 | No hex is clinically proven to prevent eye fatigue | owner rule (v1 section 2) | owner-assumption |
| E16 | Owner target 7:1 body text; 60-year-old non-technical reader | redesign plan (`docs/UI_REDESIGN_PLAN_2026-11-07.md`) | lead-input / owner-assumption |
| E17 | 4.77 reading secondary | lead assumption (v1 defines no reading secondary) | lead-input |

---

## 12. OPEN ITEMS FOR THE LEAD

1. Accent colour: v1 teal (#28665F) vs the plan's blue and amber (conflict C5, C9, C11).
2. Body size: 16-18 px (v1) vs 20 px (plan) (C12).
3. Step names: the plan's names vs index.html (C18).
4. Whether the 7:1 target covers hints and secondary text, or body text only (this file applies 7:1 to secondary text).
5. Whether the reading theme ships at all (C19).
6. Test duplication: use the existing `test_body_text_contrast_is_at_least_7` and extend it (C15).
