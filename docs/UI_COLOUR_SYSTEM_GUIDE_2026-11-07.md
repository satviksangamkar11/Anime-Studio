# Agent Implementation Guide

## Anime Studio: Evidence-Informed UI Colour System Redesign

Source: owner-supplied guide, saved verbatim on 2026-11-07 (version 1). The research-hardened version 2 is written next to this file by the research agent; this file stays unchanged as the owner's original.

Repository: https://github.com/satviksangamkar11/Anime-Studio.git
Target branch: merge-v4-universal-2026-11-07
Working directory: D:\aai work\anime_studio_merge

Objective: Redesign the entire Anime Studio application UI with a consistent, accessible, low-glare dual-theme colour system suitable for prolonged daily use.

---

## 1. IMPORTANT GIT SAFETY RULES

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

Do not commit changes unless explicitly authorized.

## 2. DESIGN OBJECTIVE

Build a unified colour architecture for Anime Studio.

The application must support:

* Light Mode.
* Dark Mode.
* Consistent colour behaviour across every screen.
* User-controlled theme switching.
* Persistent theme preferences.
* Readable typography and interface components.
* Clear visual hierarchy.
* Accessible contrast.
* Comfortable long-duration interface usage.

The design must be based on measurable visual accessibility and ergonomic considerations, not merely aesthetic trends.

Important scientific restriction:

Do not advertise any HEX code as clinically proven to prevent eye fatigue. The selected palette is research-informed, and its actual performance must be evaluated through usability and accessibility testing.

## 3. APPROVED PRIMARY COLOUR PALETTE

### A. Light Mode

| UI element | HEX |
|---|---|
| Application background | #F3F1E8 |
| Cards and surfaces | #F8F7F0 |
| Primary text | #343834 |
| Secondary text | #59635E |
| Primary links and accents | #28665F |
| Borders | #D9DED6 |
| Primary button background | #28665F |
| Primary button text | #FFFFFF |
| Selection background | #DCEBE6 |
| Code/editor background | #EAECE4 |
| Focus indicator | #28665F |

Design objective:

Use warm ivory instead of pure white, neutral charcoal for readable text, and restrained teal accents.

Keep card surfaces subtly different from the main page background.

Avoid unnecessarily bright backgrounds and excessive decorative colour.

### B. Dark Mode

| UI element | HEX |
|---|---|
| Application background | #181B1A |
| Cards and surfaces | #232826 |
| Primary text | #DED7C5 |
| Secondary text | #B9C2BA |
| Primary links and accents | #9CC9BE |
| Borders | #3A4540 |
| Primary button background | #9CC9BE |
| Primary button text | #181B1A |
| Selection background | #2B4540 |
| Code/editor background | #1D2421 |
| Focus indicator | #9CC9BE |

Design objective:

Use deep charcoal rather than absolute black, warm cream instead of pure white, and muted turquoise accents.

Avoid excessive brightness, especially in large surfaces and sidebars.

### C. Optional experimental reading theme

Keep this optional, not the default:

| UI element | HEX |
|---|---|
| Reading background | #CFE8CC |
| Primary text | #343834 |
| Surface | #E0EFDD |
| Accent | #28665F |

This is based on an experimental 2025 light-green-background reading study.

Do not force this theme on all users. It must be selectable and independently testable.

## 4. CENTRALIZED DESIGN TOKEN ARCHITECTURE

Do not scatter HEX codes across components.

Create or extend one centralized theme configuration.

Suggested CSS:

    :root,
    [data-theme="light"] {
      color-scheme: light;
      --app-bg: #F3F1E8;
      --surface: #F8F7F0;
      --text-primary: #343834;
      --text-secondary: #59635E;
      --accent: #28665F;
      --border: #D9DED6;
      --button-bg: #28665F;
      --button-text: #FFFFFF;
      --selection-bg: #DCEBE6;
      --editor-bg: #EAECE4;
      --focus-ring: #28665F;
    }
    [data-theme="dark"] {
      color-scheme: dark;
      --app-bg: #181B1A;
      --surface: #232826;
      --text-primary: #DED7C5;
      --text-secondary: #B9C2BA;
      --accent: #9CC9BE;
      --border: #3A4540;
      --button-bg: #9CC9BE;
      --button-text: #181B1A;
      --selection-bg: #2B4540;
      --editor-bg: #1D2421;
      --focus-ring: #9CC9BE;
    }

Extend the tokens where necessary for:

* Hover states.
* Active states.
* Disabled states.
* Tooltips.
* Modals.
* Dropdowns.
* Inputs.
* Form validation.
* Notifications.
* Scrollbars.
* Tables.
* Graphs and visualizations.
* Code syntax highlighting.

Use semantic tokens instead of hardcoded colours.

## 5. COMPLETE APPLICATION-WIDE AUDIT

Inspect every screen and component before changing colours.

Do not redesign only the homepage.

Audit these areas:

**Application shell**

* Main background.
* Navigation.
* Sidebar.
* Top toolbar.
* Header.
* Footer.
* Panel separators.

**Animation workspace**

* Timeline.
* Scene editor.
* Preview workspace.
* Properties panels.
* Asset browser.
* Character controls.
* Environment controls.
* Object controls.
* Layer panels.
* Toolbars.

**Production pipeline**

* Project configuration.
* Script editor.
* Caption editor.
* Audio settings.
* Voice controls.
* Rendering controls.
* Export settings.
* Pipeline status.
* Progress indicators.

**General interface**

* Dialog boxes.
* Confirmation windows.
* Popovers.
* Dropdowns.
* Buttons.
* Input fields.
* Checkboxes.
* Radio controls.
* Tabs.
* Tables.
* Notifications.
* Error messages.
* Empty states.
* Loading states.

Every screen must use the same semantic tokens.

## 6. IMPORTANT: PROTECT THE ACTUAL ANIMATION OUTPUT

Anime Studio is an animation production application.

Changing the application interface must NOT accidentally change the generated animation.

Keep the following separate:

1. Application UI theme.
2. Animation preview.
3. Generated character colours.
4. Environment and background artwork.
5. Subtitle and caption styling.
6. Exported video colour settings.
7. User-created visual assets.

The theme should change the application chrome, not automatically recolour user artwork, character designs, animation frames, subtitle presets or exported video.

Do not modify the rendering pipeline unless a specific rendering-related colour issue is identified and separately authorized.

## 7. TYPOGRAPHY AND READING ERGONOMICS

Preserve existing font choices unless a genuine usability problem is found.

Recommended starting settings:

| Parameter | Recommendation |
|---|---|
| General body text | 16-18px |
| Main reading content | 18px |
| Line height | 1.5-1.7 |
| Reading column width | 60-75 characters |
| Heading hierarchy | Clearly differentiated |
| Links | Underlined |
| Focus indicator | Clearly visible |
| Paragraph spacing | Consistent |
| Text truncation | Avoid for critical information |

For dense professional controls, smaller text may be necessary, but it must remain readable.

Do not shrink the entire UI to make the application appear more compact.

## 8. THEME SWITCHING

Implement a functional theme selector.

Requirements:

* Light Mode.
* Dark Mode.
* Optional experimental Reading Mode.
* System preference support.
* Manual user override.
* Persistent selection.
* No unnecessary page refresh.
* No flashing white screen during theme initialization.

Follow existing state-management and storage architecture.

Do not introduce a new library for theme switching unless genuinely necessary.

If there is already a theme provider or theme-management mechanism, extend it rather than creating a competing implementation.

## 9. ACCESSIBILITY AND CONTRAST VALIDATION

Use WCAG 2.2 AA as the minimum target.

For normal text, target at least 4.5:1 contrast.

For large text, target at least 3:1.

Check all combinations, including:

* Primary text on backgrounds.
* Secondary text on cards.
* Links on backgrounds.
* Button text on buttons.
* Placeholder text.
* Disabled controls.
* Form errors.
* Focus indicators.
* Tooltips.
* Chart labels.

Reference combinations:

| Combination | Expected contrast |
|---|---|
| Light primary text / background | 10.54:1 |
| Light primary text / surface | 11.10:1 |
| Light secondary text / background | 5.51:1 |
| Light accent / background | 5.88:1 |
| Dark primary text / background | 12.09:1 |
| Dark primary text / surface | 10.43:1 |
| Dark secondary text / background | 9.49:1 |
| Dark accent / background | 9.51:1 |

Do not rely on colour alone to communicate success, failure, warnings or selection.

Use text, icons, shapes or other appropriate indicators.

## 10. COMPONENT IMPLEMENTATION RULES

Create reusable theme-aware components or extend existing ones.

Examples:

* ThemeProvider.
* ThemeToggle.
* AppBackground.
* SurfaceCard.
* PrimaryButton.
* SecondaryButton.
* ThemeAwareInput.
* ThemeAwareModal.
* ThemeAwareTooltip.

These are suggested responsibilities, not mandatory new component names. Avoid unnecessary component proliferation.

All components should read from the centralized theme tokens.

Avoid:

* Inline hardcoded colour values.
* Duplicate theme definitions.
* Inconsistent button colours.
* Unreadable muted text.
* Pure white surfaces throughout Dark Mode.
* Absolute black everywhere.
* Flashing transitions.
* Unnecessary gradients.
* Excessive shadows.
* Arbitrary colour overrides in individual pages.

Do not blindly replace all existing HEX values. Some existing colours may represent semantic statuses, chart data or user-controlled artwork.

## 11. ANIMATION AND TRANSITION POLICY

Theme transitions should be subtle and should not interfere with prolonged usage.

Use a short transition for ordinary surface and text colour changes.

Respect:

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
        animation-duration: 0.01ms !important;
      }
    }

Do not add unnecessary animated background effects.

Avoid flashing, pulsating or rapidly changing interface colours.

## 12. TESTING PLAN

Before marking the task complete:

**Functional testing**

* Theme selector works.
* Theme preference survives reload.
* System preference works when no manual override is set.
* Manual preference takes priority.
* All routes render correctly.
* Modals and dropdowns use the correct theme.
* Timeline remains functional.
* Editor remains functional.
* Preview remains unchanged.
* Exported video is not recoloured.
* Existing production pipeline is unaffected.

**Visual testing**

Capture screenshots in both themes for:

* Main dashboard.
* Animation workspace.
* Timeline.
* Script editor.
* Caption editor.
* Asset panels.
* Audio workspace.
* Rendering workspace.
* Export screen.
* Settings.

Check desktop and mobile layouts where supported.

**Technical testing**

Run the repository's existing:

* Formatter.
* Linter.
* Type checker.
* Unit tests.
* Integration tests.
* Production build.

Do not introduce a new test framework without a reason.

Add theme-related regression tests using the existing testing infrastructure.

## 13. REQUIRED FINAL REPORT

When implementation is complete, provide:

1. Current branch and Git status.
2. Files inspected.
3. Files modified.
4. Centralized theme architecture.
5. Light Mode implementation details.
6. Dark Mode implementation details.
7. Optional Reading Mode implementation status.
8. Screens covered.
9. Accessibility contrast results.
10. Tests executed and their results.
11. Any remaining hardcoded colours.
12. Any unresolved visual issues.
13. Confirmation that exported animation colours were preserved.
14. Confirmation that no Git push occurred.

Show before-and-after screenshots wherever possible.

Do not report a test as passed unless it was actually executed successfully.

## 14. DEFINITION OF DONE

The task is complete only when:

* [ ] Light Mode works across the application.
* [ ] Dark Mode works across the application.
* [ ] The optional Reading Mode is independently selectable if implemented.
* [ ] Theme tokens are centralized.
* [ ] No major screen is left with the old inconsistent theme.
* [ ] Contrast requirements are validated.
* [ ] Text and controls remain readable.
* [ ] Theme selection persists.
* [ ] Existing functionality remains intact.
* [ ] Animation previews and exports retain their intended colours.
* [ ] Relevant tests and production build pass.
* [ ] No unrelated architecture changes were introduced.
* [ ] No Git push was performed.

Priority: Preserve the working V4 + Universal implementation. A colour redesign must never compromise the animation engine, production pipeline, captioning system, export functionality or existing project architecture.

Final instruction: Inspect first, design a centralized theme system, implement incrementally, test every major screen, review screenshots, and report the actual results. Do not push changes to GitHub.
