# Anime Studio

Indian-mythology anime pipeline: story -> production pack -> keyframes -> MiniMax H3 video on a free Kaggle T4 -> edit.

| Step | File | What it does |
|---|---|---|
| Brief | `director/MASTER_PROMPT_v2.1.md` | The 5-gate studio brief (story, art bible, shots, prompts, sound/QA) ending in a machine-readable shot list |
| 1 Writer | `director/write_pack.py` | Story -> `PACK.md` + `shots.json`. Default `--writer super-vl` (free OpenRouter `nvidia/nemotron-3.5-super-vl:free`, streamed); `--writer ultra` (free OpenRouter Nemotron 3 Ultra); `--writer opus` (Claude CLI, effort medium). Lower-level: `--via claude / nvidia / openrouter` with `--model` (OpenRouter free models only unless `--allow-paid`). `--staged` makes one call per gate |
| Run log | `director/run_registry.py` | Every story, writer and analysis run, with its model and each step: `stories/<slug>/story.json`, append-only `RUNS.jsonl`, and `RUN_REPORT.md` (`report(studio, slug)`). Shown in the UI wizard under "Runs & documents" (`GET /api/registry`). Old stories: `director/backfill_registry.py --only <slug>` (idempotent) |
| 2 Settings | `director/h3_director.py` | `shots.json` -> one Wan2GP settings file per shot (MiniMax H3 + Pika H3 Flex 6 steps) |
| 3 Kaggle | `director/run_kaggle.py` | Packs shots + keyframes into one Kaggle T4 run (Wan2GP headless); `--fetch` downloads only the videos |
| 4 Check | `director/clip_tools.py` | First/middle/last frame sheet, duration, loudness; real last frame -> next shot's start |

Stories live in `stories/<name>/SOURCE.md`. Keys are never stored here: the scripts read them at run time from folders outside the repository.

Tests: `cd director && python -m pytest -q`


## Where to resume (2026-11-07)
Read `blot.md` (log every step), then `PROJECT_LOG.md` (NOW block), `CHECKLIST_ARCHITECTURE_2026-11-07.md` and `HANDOFF_2026-11-07.md`.
