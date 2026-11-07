# Colour and attention-retention audit: what entered the pipeline (checklist 10.1)

Source: research/COLOUR_ATTENTION_RETENTION_AUDIT_2026-11-07.md (audit of the colour research doc). Decision date: 2026-11-07.
Rule: the audit's specs are built as data-driven, story-independent code. Nothing story-specific was touched.

## Build order of the audit, step by step

| Audit step | Decision | Where it lives | Status |
|---|---|---|---|
| 1. Fix the three repo contradictions (Krishna skin line, 4.5 vs 5-6 heads, `post.py` audio note) | Built (WP0) | `director/style/kaliya_mardan.json`, `director/test_bible_consistency.py`, `STATUS.md` | closed |
| 2. Correct the research doc, give it a source list | Built (WP9a) | `docs/COLOUR_RESEARCH.md`, `docs/RESEARCH_SOURCES.md` | closed |
| 3. `colour_script` and per-environment `measured` values in the bible schema | Built as style packs: acts, phases, `luma_mean`, `sat_mean`, `grade`, `measured` per environment | `core/style_pack.py`, `styles/*.json`, `tools/measure_plate.py` | closed (the measured values come from owner-approved plates, supplied with the story) |
| 4. `colour` block in the shot contract, checked by `check_pack` | Built as the `look` block (act, phase, focal, focal_value, accent_use, hook, impact_frames) | `director/shot_schema.py`, `core/pack_rules.py` (P0-P13), `director/check_pack.py` | closed |
| 5. G1 image palette gate | Built | `flow/scripts/palette_check.py` (hooked into `file_flow_download.py`) | closed |
| 6. `retention_lint.py` R1-R9 | Built as R1-R10 in the core library, run by `check_pack` | `core/retention_rules.py`, `core/timeline.py` | closed |
| 7. `assemble_reel.py`: explicit codec, `yuv420p`, BT.709 tags and matrix, G3 `colour_seams` | Built | `h3/assemble_reel.py`, `core/core.json` `delivery` | closed |
| 8. G2 in `clip_tools.py` (signalstats) and G4 criteria in `visual_qa.py` | Built (thumbnail panel and deuteranopia panel included) | `director/clip_tools.py`, `director/visual_qa.py`, `core/cvd.py` | closed |
| 9. `post.py`: upscale hook, shot match, act LUT, grain, one 16-bit to 8-bit conversion, captions, encode, `colour_report.json` | Built, plus flash safety (F1, F2), impacts, loop-seam check, SRT/VTT sidecars | `director/post.py`, `core/lut.py`, `core/flash_check.py`, `core/captions.py` | closed |
| 10. Render LEAP-01..05, tune the limits | Not done: no renders are allowed yet. The limits are `core.json` values marked as starting values; `tools/calibrate_sat_ceiling.py` and the `ANIME_RELEASE=1` test turn the saturation ceiling into a measured number once approved reference frames exist | `core/core.json`, `tools/calibrate_sat_ceiling.py` | open by design (needs approved renders) |
| 11. Upload, analytics, `retention_report.py`, feed the dip shots back | Tool built; the first real analytics file comes after the first upload | `core/retention_report.py` | tool closed, data open |

## Audit section 5 (retention) and 4.6 (Indian colour meaning)

- R1-R10 are rules over the `look` block and the timeline, with FAIL and WARN levels in `core/core.json` (`retention`). 5.2 (applying the rules to the milestone leap `DIRECTION.md`) is story work and is not touched now.
- 4.6 is guidance for the story writer (white and mourning, saffron and gold as sacred). It stays in `docs/COLOUR_RESEARCH.md` and the writer prompt `director/MASTER_PROMPT_v2.3.md`; there is no code gate for it, because meaning is story-specific.
- 5.4 (captions on a phone): contrast at least 7:1, minimum 1.2 s on screen, libass burn-in after the colour conversion, a safe area above the platform UI. Built in `core/captions.py` with the owner-decided Reels numbers (top 14%, bottom 35%, caption band 50-65%) as the default and `safe_zone_templates` for reels, shorts and youtube. The shorts and youtube numbers are tune values until they are checked on real devices.

## Caption research (checklist 9.1-9.8)

| Item | Built |
|---|---|
| 9.1 SRT and WebVTT sidecars per language | `core/caption_export.py` `to_srt`, `to_vtt`, `write_sidecars`; `post.py` writes them next to the final file |
| 9.2 Safe-zone templates | `core/core.json` `safe_zone_templates`; `build_ass(template=...)`; `post.py --platform` |
| 9.3 Glyph-coverage QA | `core/caption_text.py` `check_font_coverage` (own cmap reader, no fontTools); `build_ass` fails a cue whose glyphs are missing |
| 9.4 Hook-word emphasis | cue `emphasis` list; `look.hook.emphasis` in a shot |
| 9.5 Measured wrapping, graphemes, at most 2 lines | `caption_text.clusters`, `wrap_lines`, `fit_text`; used when a fonts dir is given. Widths are Pillow basic layout (no raqm here), a documented approximation |
| 9.6 Contact sheet and reference-frame QA | `caption_export.contact_sheet_plan` (argv only, never run), `frame_hash`, `compare_frames` |
| 9.7 Word alignment into karaoke with phrase fallback | `caption_export.words_from_elevenlabs` (parser only, no API call), `karaoke_text`, cue `words`; low confidence or bad timing falls back to the plain line |
| 9.8 Mixed-script fallback, libass and HarfBuzz preflight | `caption_text.fallback_markup`, `caption_export.ffmpeg_preflight` (run by a real `post.py` run) |
