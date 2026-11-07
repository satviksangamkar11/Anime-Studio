# Anime Studio

Indian-mythology anime pipeline: story -> production pack -> keyframes -> MiniMax H3 video -> edit -> post.

| Step | File | What it does |
|---|---|---|
| Brief | `director/MASTER_PROMPT_v2.1.md` | The 5-gate studio brief (story, art bible, shots, prompts, sound/QA) ending in a machine-readable shot list |
| 1 Writer | `director/write_pack.py` | Story -> `PACK.md` + `shots.json`. Default `--writer super-vl` (free OpenRouter `nvidia/nemotron-3.5-super-vl:free`, streamed); `--writer ultra` (free OpenRouter Nemotron 3 Ultra); `--writer opus` (Claude CLI, effort medium). Lower-level: `--via claude / nvidia / openrouter` with `--model` (OpenRouter free models only unless `--allow-paid`). `--staged` makes one call per gate |
| Run log | `director/run_registry.py` | Every story, writer and analysis run, with its model and each step: `stories/<slug>/story.json`, append-only `RUNS.jsonl`, and `RUN_REPORT.md` (`report(studio, slug)`). Shown in the UI wizard under "Runs & documents" (`GET /api/registry`). Old stories: `director/backfill_registry.py --only <slug>` (idempotent) |
| 2 Settings | `director/h3_director.py` | `shots.json` -> one Wan2GP settings file per shot (MiniMax H3 + Pika H3 Flex 6 steps) |
| 3 Kaggle | `director/run_kaggle.py` | Packs shots + keyframes into one Kaggle T4 run (Wan2GP headless); `--fetch` downloads only the videos |
| 4 Check | `director/clip_tools.py` | First/middle/last frame sheet, duration, loudness; real last frame -> next shot's start |

The Universal Pipeline v1.2 layer (colour script, retention rules, flash safety, captions, post) lives in `core/`, `styles/`, `director/post.py` and `tools/`; see `STATUS.md`, `OPEN_QUESTIONS.md` (Q1-Q8) and `docs/PIPELINE_AUDIT_2026-11-07.md`.

## Layout

| Folder | What is in it |
|---|---|
| `core/` | `style_pack.py`, `timeline.py`, `pack_rules.py` (P0-P13), `retention_rules.py` (R1-R10), `frame_metrics.py`, `flash_check.py` (F1/F2), `lut.py`, `captions.py`, `caption_text.py`, `caption_export.py`, `cvd.py`, `retention_report.py`, `core.json` (tune values) |
| `styles/` | Style packs: `braj_earth.json`, `deva_neon.json` |
| `director/` | `check_pack.py` (`--strict`), `clip_tools.py` (`gates` subcommand), `post.py`, `shot_schema.py`, `write_pack.py` (`--style-pack`, `--prompt-version`), `MASTER_PROMPT_v2.3.md` |
| `h3/` | `assemble_reel.py` (delivery flags, G3 colour seams, loudness pass-through), `render_controller.py`, `schema_and_linter.py`, `profiles/` |
| `flow/scripts/` | `palette_check.py` (G1), `file_flow_download.py` (filer hook), image job tools |
| `tools/` | `convert_bible.py`, `convert_deva_bible.py`, `lint_pack.py`, `make_lut.py`, `convert_deva_shots.py` (flat and `--h3`), `measure_plate.py`, `calibrate_sat_ceiling.py` |
| `ui/` | Local pipeline wizard (`server.py`, `pipeline.py`, `static/`) |

Stories live in `stories/<name>/`. Keys are never stored in the repository.

## Commands

Run from the repository root unless noted.

- `cd director && python check_pack.py PACK_DIR [--story PATH] [--strict]`
- `cd director && python post.py EPISODE_BUILD_DIR --story PATH [--episode-json PATH] [--styles-dir DIR] [--fonts-dir DIR] [--upscale-cmd CMD] [--out PATH] [--no-captions] [--no-sidecars] [--platform reels|shorts|youtube] [--dry-run]`
- `python core/retention_report.py BUILD_DIR ANALYTICS_JSON`
- `python tools/lint_pack.py PACK_ID [--styles-dir DIR]`
- `python tools/make_lut.py PACK ACT [--styles-dir DIR] [--size N] [--force]`
- `python tools/calibrate_sat_ceiling.py FILE [FILE ...] [--percentile 99] [--write]` (sets `gates.sat_avg_ceiling` from approved reference frames; `ANIME_RELEASE=1 python -m pytest core` fails while it is null)
- `python tools/convert_deva_shots.py IN.json [--out FILE] [--pack NAME] [--h3] [--h3-profile NAME]`

## Tests

- `cd core && python -m pytest -q -p no:cacheprovider`
- `cd director && python -m pytest -q`
- `cd h3 && python -m pytest -q -p no:cacheprovider`
- `cd flow/scripts && python -m pytest -q`
- `cd ui && python -m pytest -q`

Tests build their own fixtures in a temporary folder. ffmpeg-based tests skip when ffmpeg is not on PATH.

Tests (V4 layer): `cd director && python -m pytest -q`


## Where to resume (2026-11-07)
Read `blot.md` (log every step), then `PROJECT_LOG.md` (NOW block), `CHECKLIST_ARCHITECTURE_2026-11-07.md` and `HANDOFF_2026-11-07.md`.
