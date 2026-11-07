# Universal Pipeline v1.2 status (branch universal-v1.1, updated 2026-11-07)

## Current state
- WP0-WP9 are implemented as commits on `universal-v1.1`. Nothing is pushed. Any push needs the owner's go.
- README.md and STATUS.md edits from this pass are not committed yet (the lead commits).

## Owner must supply
- Fonts: DONE 2026-11-07 (`styles/fonts` holds Rajdhani, Yatra One, Inter and Noto Sans Devanagari under SIL OFL; P10 passes).
- Caption text.
- Go-ahead for any push.

## Known open items
1. A26: `gates.sat_avg_ceiling` is still null. It needs approved reference frames, and the release test is not added.
2. Kaliya real shots are not regenerated. The old T0 shots have no look block.
3. FIXED 2026-11-07: `render_controller.prepare` now reads `loudness.json` before it writes shot files.
4. FIXED 2026-11-07: the `render_controller` docstring now says when ffmpeg runs.
5. F1 counting rounds odd transitions up (8 alternating frames = 4 flashes). Owner confirmed 2026-11-07: keep. P1 missing story.json = FAIL also confirmed.

Judgement calls are listed in `OPEN_QUESTIONS.md` (Q1-Q8).

## Next
- Owner: supply fonts and caption text, decide item 5, and say whether to push.
- Then fix items 1-4 in their owning files, with a second review round after the fixes.
