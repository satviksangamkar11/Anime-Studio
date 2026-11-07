# Universal Pipeline v1.2 status (branch universal-v1.1, updated 2026-11-07)

## Current state
- The architecture is complete: WP0-WP9, all amendments, the caption components (checklist 9.1-9.8), the audit items (see `docs/COLOUR_AUDIT_DECISIONS.md`) and the saturation-ceiling calibration (A26) are built and tested. Nothing in it is specific to one story.
- Suites (2026-11-07): core 386 pass + 1 release-gate skip, director 488, h3 178, flow 130 pass (2 known failures on the real pack), ui 161 pass (1 known failure on the real pack).
- Open questions Q1-Q8 are closed with the recommended defaults (`OPEN_QUESTIONS.md`); the owner may reopen any.
- Fonts are in `styles/fonts` (Rajdhani, Yatra One, Inter, Noto Sans Devanagari, SIL OFL licences kept), so rule P10 passes.

## What a story still has to bring (no story work has started)
1. The story and its shots written with the v2.3 writer (a model call, needs the owner's go).
2. Caption text and hook words (`look.hook.caption`, `look.hook.emphasis`).
3. Owner-approved reference frames and plates: run `tools/measure_plate.py` on the plates and `tools/calibrate_sat_ceiling.py FILES --write` on the reference frames; then `ANIME_RELEASE=1 python -m pytest core` must pass (it fails while `gates.sat_avg_ceiling` is null).
4. Renders and tuning of the gate limits (G1/G2 dE 6, G3 dE 8, static 3.5/4.0 s) after the first approved render. No render has been run.
5. Paid word alignment (ElevenLabs) only with the owner's go; the parser (`caption_export.words_from_elevenlabs`) and the karaoke path with phrase fallback exist and never call an API.

## Known limits
- Caption widths are measured with Pillow basic layout (no libraqm here), so Devanagari conjunct widths can be slightly over-estimated; line breaks may differ a little from the real libass render. A Pillow build with raqm removes the approximation.
- The `shorts` and `youtube` entries of `core.json` `safe_zone_templates` are tune values; the `reels` numbers (top 14%, bottom 35%, caption band 50-65%) are the owner's decision and the default.
- The ElevenLabs alignment shape was written from the public documentation and is unverified against a live response.
- F1 counting rounds odd transitions up (8 alternating frames = 4 flashes) and P1 missing story.json = FAIL: both confirmed by the owner 2026-11-07.

## Next
- Owner: start the actual story (story file, caption text, approved plates and reference frames).
- Then: the writer run, the first render, and the tuning above.
