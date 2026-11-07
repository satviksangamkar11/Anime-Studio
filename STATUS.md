# Universal Pipeline v1.2 status (branch universal-v1.1, updated 2026-11-07)

## Current state
- WP0-WP9 are implemented as commits on `universal-v1.1`. Nothing is pushed. Any push needs the owner's go.
- README.md and STATUS.md edits from this pass are not committed yet (the lead commits).

## Owner must supply
- Fonts: `styles/fonts` is not in the repo, so real packs get P10 FAIL.
- Caption text.
- Go-ahead for any push.

## Known open items
1. A26: `gates.sat_avg_ceiling` is still null. It needs approved reference frames, and the release test is not added.
2. Kaliya real shots are not regenerated. The old T0 shots have no look block.
3. `render_controller.prepare` writes shot files before it reads `loudness.json`.
4. The `render_controller` module docstring says "no ffmpeg", but `attach_colour_seams` runs ffmpeg.
5. F1 counting rounds odd transitions up (8 alternating frames = 4 flashes). The owner may revert this.

Judgement calls are listed in `OPEN_QUESTIONS.md` (Q1-Q8).

## Next
- Owner: supply fonts and caption text, decide item 5, and say whether to push.
- Then fix items 1-4 in their owning files, with a second review round after the fixes.
