# Anime Studio status (merged branch: V4 + universal v1.2, 2026-11-07)

This branch is the merge of `v4-architecture-2026-11-07` (writer, validator, H3, Gate D audio, UI wizard) and `universal-v1.1` (colour, retention, flash, captions, post). Audit of every part: `docs/PIPELINE_AUDIT_2026-11-07.md`.

## V4 layer (writer, validator, H3, Gate D, UI)
- [x] V4 architecture built and reviewed (Super VL + Dots): validator, writer V4 + voice_map, H3 router/compiler/locks, Gate D audio + captions, Step 9 QC functions, fallback ladder, asset manifest, voice engine, UI wizard.
- [x] Suites before the merge: director 663, h3 595, ui 253, flow/scripts 116.
- [ ] Not built: Step 9 runner, Gate D assembly runner, live author run, any real render (no Colab calls, owner rule), ElevenLabs use (needs owner go).
- [x] Captions follow the output language (owner rule 2026-11-07): `director/post.py --language en|hi|mr` burns the SPOKEN script of that language; a caption in the wrong script is a FAIL. The voice is ElevenLabs for every language by default (H3 speech is English only, rule VE-01).
- [x] One caption engine (decision brief 2026-11-07): `core/caption_cues.py` (cue model, the one script validator, spoken-script reader, hook policy), `core/captions.py` (ASS burn list: cards, karaoke, face avoidance, fonts, safe zones), `core/caption_export.py` (the one SRT and WebVTT serializer). Gate D's private builder is deleted: it calls the engine (`h3.gate_d_audio.build_captions`) and its caption tests are in `h3/tests/test_gate_d_captions.py`. Gate D's default fonts are now `styles/fonts` (Inter, Noto Sans Devanagari).
- [x] Voice mixing in `post.py` (`--voice elevenlabs|h3`, `--vo-dir`; story.json `voice_engine[lang]` when no flag): the per-language voice file `<vo-dir>/<lang>/<shot_id>.wav` is required for every shot with narration or dialogue (missing = refusal naming the file, never a fallback to the H3 audio); the H3 clips' audio stays as the SFX bed ducked under the voice (frozen audio plan: H3 makes all SFX), mixed by the same `build_voice_branch` chain and loudness target as Gate D; planned before the captions are burned. English with `--voice h3` keeps the H3 audio and needs no voice file.
- [x] Hook caption policy: the hook stays on frame 1 even when a spoken script exists (window until the first spoken cue, shortened by `look.hook.duration_s`; `look.hook.caption_by_lang[lang]` gives each language its own hook; text burned once when it equals the first spoken line; the hook is the first SRT/WebVTT cue otherwise).
- [x] Ungraded exports are loud: an act with neither a LUT file nor grade numbers gives a `POST-UNGRADED` warning and `colour_report.json` carries `graded: false` and `graded_by_act`. No grade numbers were invented (braj_earth still has none).
- [ ] Open, owner decision: loudness target. `post.py` and the voice mix use the delivery value in `core/core.json` (-16 LUFS, TP -1.5); Gate D's own spec still says -14 LUFS for its post-AAC check (`h3/shot_table_spec.py`). One target is needed.
- [ ] Owner inputs that code cannot supply: approved plates (one per place, per story), braj_earth grade numbers for HOOK, BUILD, DROP, OUTRO (or approved plates to derive them), LUT approval (about three stills per act), the story and its caption and hook text per language, ElevenLabs voice files for each language (the ElevenLabs call needs the owner's go).
- [ ] Not built: Step 9 runner, Gate D assembly runner (the post.py voice mix replaces its mux for the final reel; the Gate D plan stays as the pre-render gate), live author run, any real render.

## Universal layer (colour, retention, flash, captions, post)
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

---
Older V4 status (kept from the V4 branch)

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
- [ ] `post.py` (join, trim, drop H3 audio, add voice/SFX, anime upscale).
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
