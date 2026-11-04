# Anime Studio status checklist (updated 2026-11-04, evening)

## Running now
- [ ] Opus independent review (high effort): checks both owner-supplied audits, throughput maths for a full series on Kaggle T4s, a better plan if one exists, first-two-weeks plan, ranked repo changes. Output: `research/OPUS_INDEPENDENT_REVIEW_2026-11-04.md`.

## Done today
- [x] H3 proven on Kaggle T4 (Wan2GP headless, FL2VA pruned 20B + Pika 6-step): 5.17 s 832x480 clip, 8m50s generation, 16m54s incl. downloads, 3.3 GB GPU peak. Veda (Singularity v2 recipe) not supported on T4.
- [x] Director v2.0: `write_pack.py` (story -> PACK.md + shots.json), `h3_director.py`, `run_kaggle.py`, `clip_tools.py`; Haiku review, 8 of 9 findings fixed, 9th closed.
- [x] Three writing paths, any model: Claude CLI, NVIDIA build API, OpenRouter (free models only unless `--allow-paid`).
- [x] Rule: Kaggle fetch downloads only the `.mp4` (saved as a memory and in `run_kaggle.py`).
- [x] Kaliya Mardan source written (`stories/kaliya_mardan/SOURCE.md`); first pack by Nemotron 3 Ultra (26 shots, all valid for H3, but episodes too short and multi-action shots).
- [x] Four-video research (guide, transcripts, descriptions, 10 workflow JSONs) in `research/four_videos_2026-11-04/`.
- [x] Director v2.2 (from the owner's audit), built by 3 Haiku agents on one spec (`director/SPEC_v2.2.md`):
  - [x] `shot_schema.py`: rich shot contract (timed acting beats, cast/facing/poses, camera, layers, light, compositing, start/end state)
  - [x] `layout_validator.py`: 180-degree rule, eyelines, shot-to-shot state hand-off, cut in/out
  - [x] `h3_director.py`: compiles a rich shot into the H3 prompt and keeps the full spec as `<id>.direction.json`
  - [x] `check_pack.py`: also checks contract fields and layout
  - [x] `style/kaliya_mardan.json` + `style_bible.py`: Indian-anime visual language (palette, proportions, skin, eyes, costume physics, Braj places, iconography, sources)
  - [x] `acting_library.py`: 13 bhavas as ordered acting progressions (eyes -> face -> hands -> body -> cloth), incl. Krishna-Balarama mischief
  - [x] `MASTER_PROMPT_v2.2.md`: Indian design rules + anime direction rules + rich contract + staged output; story decides shot/reel count (example shot fixed to pass its own rules)
  - [x] `write_pack.py --staged`: one call per gate (1, 2, 3+4 per episode, 5), resumable, per-stage path/model
  - [x] `visual_qa.py`: 9-criterion frame review via NVIDIA / free OpenRouter vision model, or manual sheet
  - [x] Tests: 218 passing, no model or network calls in tests

## Not done / open
- [ ] Run the staged writer for real on Kaliya Mardan (v2.2 brief) and check the pack.
- [ ] Flow reference families (identity, turnaround/pose, acting) per character; then keyframes.
- [ ] First controlled Kaggle batch (audit's 16 renders: 4 scenes x 2 configs x 2 seeds), then visual QA on the frames.
- [ ] Prompt upgrades from the second audit (Ref2VA `retention_analysis`, FL2VA picture-to-time alignment), PNG instead of JPEG references, 768p test, render manifests: waiting for the Opus review.
- [ ] Unverified: Met Museum reference (HTTP 429), MiniMax H3 licence text, sthayi bhava names from general knowledge, all palette hex values are design targets.
- [ ] Loop system: untouched; the old-base branch `owner-free-review-opus-low-2026-11-04` in loop_p0 is uncommitted, for the owner to keep or discard.
- [ ] Granth Studio / Gajanan Maharaj: paused.
