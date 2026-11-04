# Anime Studio

Indian-mythology anime pipeline: story -> production pack -> keyframes -> MiniMax H3 video on a free Kaggle T4 -> edit.

| Step | File | What it does |
|---|---|---|
| Brief | `director/MASTER_PROMPT_v2.1.md` | The 5-gate studio brief (story, art bible, shots, prompts, sound/QA) ending in a machine-readable shot list |
| 1 Writer | `director/write_pack.py` | Story -> `PACK.md` + `shots.json` in one model call: `--via claude` (Claude CLI), `--via nvidia` (NVIDIA build API), `--via openrouter` (free models only unless `--allow-paid`) |
| 2 Settings | `director/h3_director.py` | `shots.json` -> one Wan2GP settings file per shot (MiniMax H3 + Pika H3 Flex 6 steps) |
| 3 Kaggle | `director/run_kaggle.py` | Packs shots + keyframes into one Kaggle T4 run (Wan2GP headless); `--fetch` downloads only the videos |
| 4 Check | `director/clip_tools.py` | First/middle/last frame sheet, duration, loudness; real last frame -> next shot's start |

Stories live in `stories/<name>/SOURCE.md`. Keys are never stored here: the scripts read them at run time from folders outside the repository.

Tests: `cd director && python -m pytest -q`
