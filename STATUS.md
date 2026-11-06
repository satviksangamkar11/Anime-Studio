# Anime Studio status checklist (updated 2026-11-06)

## Current (2026-11-06)
- [x] **AUDIO PLAN FROZEN 2026-11-06** (`research/AUDIO_PLAN_FROZEN_2026-11-06.md`): music removed, effects-only soundscape with fixed per-location bed, dialogue allowed, per-clip gain match to -16 LUFS then 5 ms fades, no separate audio test render, no paid audio tool.
- [x] **DECISION (owner 2026-11-06): the video model generates ALL the sound effects** (MiniMax H3 makes video+audio in one pass from the prompt's `overall_soundscape`). No separate SFX library, no ElevenLabs for effects, and `post.py` must KEEP the model's audio (the earlier plan to drop H3 audio is cancelled). **Background music is the owner's own separate step**; video prompts keep `non_diegetic_music: N/A`. Everything else in the pipeline is frozen.
- [x] **RULE (owner 2026-11-06): Flow image generation and download agents run on Haiku effort LOW.** Details: `flow/IMAGE_SYSTEM_FULL.md`. (Build and review agents are separate.)
- [x] **UI pipeline wizard built (2026-11-06)**: Story -> Analysis -> Gate A -> Images -> Gate B -> Read-out -> Gate C (typed START) -> Render -> Gate D -> Export. Coders: Dots (round 3) then Haiku xhigh (owner order: Dots too slow); reviewers: Haiku xhigh (found 5 HIGH, fixed), Dots and Nemotron Ultra in parallel (no real bugs). Suites: h3 159, ui 162, flow/scripts 115, director 352.
- [x] h3 hardening (ids, paths, SD-01/SD-02), audio rules C8 (sound_beds, SD-03/SD-04, loudness_plan, loudness.json), `flow/scripts/pack_to_spec.py` (pack -> Flow spec+series, any story) and UI commands `build_spec` / `build_jobs_cmd` + "Build image jobs" button. Gap: render_controller does not pass `loudness` to the assembly plan yet (needs measured clips).
- [ ] **Kaliya pack defects before Gate A**: reels 2-5 short (60.0/47.6/51.1/55.6 s vs 65-75 s target); CHAR-INDRA/BRAHMA/NARADA/SARASVATI and PROP-KALI-KAMLI used by shots but missing from bible; PROP-KANSA suspicious. Owner has not answered; do not approve the plan until fixed.
- [ ] Known leftovers: wizard rejected-stage does not auto re-open after a re-run (decide again works); typed pack name reverts on poll; app.js message bar success class; PLACE_TEXT_OVERRIDES in build_jobs is Kaliya-only.
- [x] 18 Flow images final at 2K, watermark removed (LaMa).
- [x] Colab CLI works (T4/L4/A100/G4); T0 test done: 8 clips of LEAP-03 (arms A, B, C, D x seeds 42 and 123). B (Singularity + Turbo 4-step) breaks the scene; A, C, D hold identity and scene.
- [x] **OWNER DECISION 2026-11-06: video route = arm C** (Singularity v2 pruned + Pika-Labs Turbo 8-step HD LoRA, `route: "sing8"`, Ref2VA with face + front refs, euler, CFG 1, shift 12, 768x1344, 124 frames). Arm A (`pika6`) stays as the fallback. Reasons and plus/minus: `research/workflow_review/DECISION_best_workflow_2026-11-05.md`.
- [x] Retry-on-429 for Hugging Face downloads in the Colab runner; Drive model cache dropped (Drive cannot be mounted from the Colab CLI).
- [ ] Render LEAP-01..05 with `sing8` (3 takes each, one G4 session, ~7 min model download + ~2.2 min/clip warm), then owner picks takes.
- [ ] `post.py` (join, trim, keep H3 audio, add voice/SFX, anime upscale).
- [ ] Open images: LEAP-02A/02B water still pale; KRISHNA_ACTION_POSES bottom row broken (do not use as ref).
- [ ] Commit and push code/docs only (repo is public; never images, weights, notebooks, clips).

---
Older status (2026-11-04) below.


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
