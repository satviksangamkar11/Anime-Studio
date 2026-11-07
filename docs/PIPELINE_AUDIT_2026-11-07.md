# Pipeline audit, 2026-11-07

Scope: every part of the Anime Studio pipeline on both branches, what each part does, what is done, what is tested, what is not built, and what is risky.
Method: file inventory of both branches (`git ls-tree`), a dry-run merge, all test suites re-run, the spec's acceptance checks re-run on real files, test-to-module cross-reference. No model call, no render, no story file was touched. Everything below was observed in this session unless marked "not verified".

## 1. Verdict in ten lines

1. The code for the whole path exists and is tested, but it sits on **two branches that have never been merged**: `v4-architecture-2026-11-07` (writer, validator, H3 compile/lint/route, Gate D audio, UI wizard: 17 commits, 196 files) and `universal-v1.1` (colour, retention, flash, captions, post.py: 24 commits, 86 files). A dry-run merge gives **4 conflicted files, 8 hunks** (`README.md`, `STATUS.md`, `director/write_pack.py`, `h3/render_controller.py`). It is small and mechanical, but until it is done no single checkout runs the whole path.
2. **Universal branch (the colour/retention/post layer): complete against the spec.** WP0-WP9, amendments A1-A28 and the caption components 9.1-9.8 are built; core 387 tests (+1 release gate that is skipped on purpose), director 488, h3 178; flow and ui show only the failures that already existed on main.
3. **V4 branch: complete as code, with three named holes** (section 6): the Step 9 QC runner, the Gate D assembly runner, and the live author run are not built; the pre-render controller has no GPU backend wired.
4. **Nothing has been rendered for production.** The only real video work is the 2026-11-06 T0 test (8 clips of one scene, on Colab). `post.py` has run only on synthetic clips.
5. **No story has gone through the finished pipeline.** The real Kaliya pack does not exist in the new form (the old T0 shots have no `look` block, so 8 of 8 fail P2).
6. **Two caption engines exist:** the new one in `core/` (universal) and the older one inside `h3/gate_d_audio.py` (V4). They must be unified at the merge.
7. **The style packs are structurally complete but not measured:** no plate has a measured Lab value, no LUT file exists, `braj_earth` has no grade numbers, `gates.sat_avg_ceiling` is still null, and the gate limits are untuned starting values.
8. The free reviewers (Super VL, Dots) were run on every changed area; Dots is unreliable on long inputs (empty answers), so some batches were covered by Super VL only.
9. Fonts are now committed to git (four SIL OFL families, 2.9 MB). The spec said "no fonts staged"; this was a deliberate change after you supplied them. Licences are kept beside the files.
10. Nothing under `granthstudio` was touched (checked by file times). No key, image, clip or model weight is tracked (secret scan clean, no file over 1 MB).

## 2. The pipeline, stage by stage

| # | Stage | What it does | Where it lives | Tests | State |
|---|---|---|---|---|---|
| 0 | Story intake | A YouTube link or pasted text becomes `SOURCE.md`; ASR fallback when a video has no captions | `director/yt_transcript.py`, `asr_transcribe.py` (both branches) | yes (no network in tests) | done |
| 1 | Writer | Story text becomes a production pack (`PACK.md`, `shots.json`, bible) through five gates; three model paths, free models by default; v2.3 prompt is now the staged default | `director/write_pack.py`, `writer_prompts.py` (V4), `MASTER_PROMPT_v2.3.md` | yes, 16 test files touch `write_pack` | code done; **no live v2.3 or V4 writer run on a real story in this session** (model call needs your go) |
| 2 | Pack checks (V4) | Validates every stage of the writer output: schema, voices, languages, simple-language rule, retries and fallback for free models | `director/pack_validator.py`, `simple_language.py`, `retry_policy.py`, `run_registry.py` | yes | done |
| 3 | Pack checks (universal) | P0-P13 rules (palette, look block, flash, fonts...), R1-R10 retention rules, timeline builder; `check_pack.py --strict` | `core/pack_rules.py`, `retention_rules.py`, `timeline.py`, `director/check_pack.py` | yes (59 + 34 + 24 + fixtures) | done |
| 4 | Style packs | The look as data: palettes, acts, phases, grades, typography, flash colours | `styles/braj_earth.json`, `deva_neon.json`, `core/style_pack.py`, converters in `tools/` | yes | structure done; **values not measured** (section 6) |
| 5 | Flow images | Builds image jobs from a pack, files downloaded 2K images, removes the corner sparkle, reviews candidates, G1 palette gate | `flow/scripts/*` | yes (flow 130 pass) | code done; the image generation itself is a manual browser step in Flow, not code |
| 6 | H3 prep (V4) | V4 pack becomes an H3 story, 5-mode router, prompt compiler, linter, asset manifest, fallback ladder, voice engine | `h3/v4_to_h3.py`, `router.py`, `compile_h3_sing8.py`, `schema_and_linter.py`, `asset_manifest.py`, `fallback_policy.py`, `voice_engine.py` | yes (h3 595) | done |
| 7 | Pre-render controller | Lints, compiles, writes prompts, workflows and the assembly script per shot; blocks on any error | `h3/render_controller.py` | yes | done as "prepare only"; **no GPU backend wired** |
| 8 | Render | The H3 model makes video and audio per shot, on Colab or Kaggle | `director/run_kaggle.py`, Colab CLI (research notes) | run_kaggle tested | **not part of the controller; T0 test only, no production render** |
| 9 | Clip QA | Frame sheet, luma flicker, drift, saturation, loudness, flash F1/F2, colour criteria and colour-blind panel | `director/clip_tools.py` (`gates`), `visual_qa.py`, `core/flash_check.py`, `frame_metrics.py`, `cvd.py` | yes | done |
| 10 | Step 9 QC (V4) | Final review gate: SFX, continuity, closing payoff, labels | `h3/step9_qc.py` | yes | functions done; **runner not built** |
| 11 | Audio plan (V4) | Per-language voice files, BGM presence, VO fit, post-AAC loudness, its own `.ass` captions | `h3/gate_d_audio.py`, `voice_manifest.py` | yes | plan code done; **assembly runner not built; ElevenLabs needs your go** |
| 12 | Assembly | ffmpeg plan with BT.709 delivery flags, loudness pass-through, G3 colour seams | `h3/assemble_reel.py` | yes | done (plans only, it never runs ffmpeg) |
| 13 | Post | Shot match, act grade, impacts, one 16-bit-to-8-bit conversion, captions, encode, final gates, refuse on FAIL, `colour_report.json`, SRT/WebVTT sidecars | `director/post.py` | 17 tests on synthetic episodes | done; **never run on real clips** |
| 14 | Analytics | Maps retention-graph dips to shots | `core/retention_report.py` | yes (24) | tool done; no analytics file exists yet |
| 15 | UI wizard (V4) | Local control panel: Story, Analysis, Gates A-D, Images, Render, Export | `ui/server.py`, `ui/pipeline.py`, `ui/static/` | yes (ui 253) + browser check at phone and desktop width | done; **not verified:** how it will display the new rule results (`rules` list from the universal `check_pack`) once the branches are merged |

## 3. Part by part: what each module is

### 3.1 `core/` (universal branch, 13 modules, 3,829 lines, 387 tests)
- `style_pack.py`: loads `core.json` and style packs; CIEDE2000, sRGB to Lab, WCAG contrast, pack validation.
- `core.json`: every tunable number (delivery flags, flash limits, retention windows, gate limits, safe zones). Safe zone default is now your Reels decision (top 14%, bottom 35%, caption band 50-65%); `safe_zone_templates` holds reels, shorts and youtube.
- `timeline.py`: turns shots into episodes with frame-exact timing; reports episode-length problems.
- `pack_rules.py`: rules P0-P13 (malformed input is a P0 FAIL, never a traceback).
- `retention_rules.py`: R1-R10 (cold open, motion by 0.5 s, face change, hook caption, no hold in the first 3 s, change cadence, re-hook, end loop, sound from frame 0).
- `frame_metrics.py`: ffmpeg signalstats and Pillow frame statistics.
- `flash_check.py`: F1 (more than 3 flashes in one second refuses) and F2 (red flash warns). Odd transitions count as a flash (owner-confirmed).
- `lut.py`: LUT maths: shot match (clamped), act grade, `.cube` read and write.
- `cvd.py`: deuteranopia simulation for the colour-blind panel.
- `captions.py`: builds the `.ass` file: safe band, lockup, contrast, minimum on-screen time, measured two-line wrapping, glyph check, hook-word emphasis, karaoke with phrase fallback, mixed-script fonts, platform templates.
- `caption_text.py`: grapheme clusters (Devanagari conjuncts), script runs, a pure-Python font cmap reader, glyph coverage, measured wrapping, mixed-script font markup.
- `caption_export.py`: SRT and WebVTT, ElevenLabs alignment parser (no API call), karaoke text, contact-sheet plan (argv only), frame hashing, ffmpeg libass/HarfBuzz preflight.
- `retention_report.py`: dip-to-shot mapping from an analytics file.

### 3.2 `director/` (both branches; universal 17 modules, V4 23 modules)
- Writer and prompts: `write_pack.py`, `writer_prompts.py` (V4), `style_bible.py`, `acting_library.py`, `shot_schema.py` (look block validation in universal).
- Checks: `check_pack.py` (universal version runs the P and R rules; the V4 version is the old 43-line one), `layout_validator.py`, `pack_validator.py`, `simple_language.py`, `retry_policy.py`.
- Registry and state: `run_registry.py`, `backfill_registry.py`, `story_state.py`, `story_links.py`, `ops_checks.py` (disk, server freshness, Colab guard).
- Render side: `h3_director.py`, `dry_run.py`, `run_kaggle.py`, `t0_variants.py`.
- Clip side: `clip_tools.py` (QA sheet, loudness, `gates`), `visual_qa.py`.
- Post: `post.py` (universal only, 600 lines).

### 3.3 `h3/` (V4 17 modules; universal has the older 6)
Router, compiler, linter, render controller, asset manifest, fallback ladder (4 rungs), Step 9 QC functions, voice engine, voice manifest, Gate D audio, V4-to-H3 converter, author step, pipeline contract (the ten ordered steps the UI shows), free-model end-to-end sample.

### 3.4 `flow/scripts/` (18 files)
Job builder, pack-to-spec, download queue and filer, sparkle removal (LaMa), neighbour and review sheets, reviewer of candidates, bridge from a Flow keyframe to the video size, the free-model coder and reviewer helpers (`dots_coder.py`, `dots_review.py`), and the new G1 `palette_check.py`.

### 3.5 `tools/` (universal 7 + V4 2)
`convert_bible.py`, `convert_deva_bible.py`, `convert_deva_shots.py` (flat and H3 mode), `lint_pack.py`, `make_lut.py`, `measure_plate.py`, `calibrate_sat_ceiling.py` (universal); `secret_scan.py` and `auto_log.py` (V4).

### 3.6 `ui/`
`server.py` (1,905 lines, local API on 127.0.0.1) and `pipeline.py` plus static JS. The JS has no unit tests (syntax check and a manual browser check only).

## 4. Spec acceptance (section 6.3), re-run today

| Check | Result |
|---|---|
| All suites pass, counts before and after | Before (spec baseline): director 385, h3 159, flow 114, ui 161. After: core 387 (+1 skipped release gate), director 488, h3 178, flow 130 pass + 2 failures, ui 161 pass + 1 failure. The 3 failures are the same real-pack tests that fail on main: they need a local, untracked pack folder. |
| check_pack on Kaliya with story.json: no P1, P2, P4 FAIL for Krishna | The real new pack does not exist. On the old T0 shots: 8 P2 FAIL (no look block), 1 R1 FAIL, 8 R6 FAIL (5.17 s static gaps), no P1 or P4 FAIL. All are real content problems of the old shots. |
| DEVA template + Shiva story: only P5 FAILs on SHOT-02 | pass (test `test_deva_template_after_convert_gives_only_the_known_p5_fails`); P10 now passes because fonts exist |
| WP4 regression fixtures | pass (28 tests across `test_check_pack_rules.py` and `test_post.py` re-run) |
| post.py on a synthetic episode: yuv420p, bt709 x3, tv, `colour_report.json`, `loudness.json`; injected 4-flash second refuses | pass |
| `lint_pack.py deva_neon` lists Hanuman, Karna, Durga gaps | pass (also lists Shiva, found by the role rule) |
| OPEN_QUESTIONS.md exists | yes; all eight questions closed with the recommended defaults |
| Nothing under granthstudio; no images, clips, keys staged | pass for images, clips, keys; **fonts are staged** (see verdict 9) |
| README and STATUS updated; each WP one commit; not pushed until your go | updated; WP commits exist (some WPs are split into parts); pushed after your approval |

## 5. How much is tested

Every module on both branches is referenced by at least one test file. Counts today: universal 1,348 tests across the five suites (1,344 pass, 3 known data-dependent failures, 1 release gate skipped on purpose); V4 1,627 (director 663, h3 595, ui 253, flow 116, all pass). Seven review rounds by two free reviewers each found real defects that were fixed with tests; the last rounds found only low-severity ones (round 7: three small calibration-tool defects, plus one contact-sheet bug found by a real libass render, not by a reviewer).

## 6. What is NOT done, ranked by impact

1. **Merge the two branches.** 4 conflicts, 8 hunks. After the merge: run all suites, wire the universal gates into the UI, and replace Gate D's own caption code with `core/captions.py` and `caption_export.py` so there is one caption engine.
2. **No production render and no real post.py run.** Needed to tune the limits (G1/G2 dE 6, G3 dE 8, static 3.5/4.0 s) and to check LUTs on real frames.
3. **Style packs are unmeasured.** No `measured` plate values (G1 is skipped with a warning), no LUT files (`styles/luts` does not exist; post.py falls back to the pack's grade numbers), `braj_earth` has no grade numbers at all (Kaliya would export ungraded), `gates.sat_avg_ceiling` is null (G2 uses a provisional 181.02 with a warning). Tools exist for all of it (`measure_plate`, `make_lut`, `calibrate_sat_ceiling`); they need approved plates and reference frames.
4. **V4 runners not built:** Step 9 QC runner, Gate D assembly runner, live author run. The functions behind them exist and are tested.
5. **Render backend not wired** into the controller.
6. **Paid ElevenLabs:** parser and karaoke path exist; the API shape is from public documentation and unverified; any live use needs your go.
7. **Story work:** the writer run, caption text and hook words, Kaliya defects, Mahadev fourth reel. Not started, by your instruction.
8. **Manual checks from spec 6.4:** approve LUTs on 3 stills per act, review one episode on a D65 monitor and two phones, check caption placement against the platform overlays, run DEVA's publish gate.

## 7. Known limits and risks

- Caption widths are measured with Pillow basic layout (no libraqm here): Devanagari conjunct widths can be slightly over-estimated, so line breaks may differ a little from the real render. A real libass render of Marathi conjunct text looked correct (HarfBuzz shaper active).
- Caption size defaults (34 px at 1080 wide, outline 8%) are tune values; the shorts and youtube safe zones are tune values.
- Free reviewers: Dots returns empty answers on long inputs; Super VL occasionally cites code it was not shown. Every finding was checked by hand against the code before acting.
- The automatic log hook is installed but was not seen firing in this session (needs a new session).
- Stale docs on the V4 branch: its `STATUS.md` still shows the older suite counts.
- Two review claims were rejected as by design (karaoke gap handling, caption centre shifted away from the right button rail); both are documented in `research/TRIAGE_R7_2026-11-07.md`.

## 8. Suggested next steps

1. Merge the branches (one session, then all suites, then a free review round on the merged files).
2. Start the actual story; the pipeline is ready for it. Order: writer run (your go), caption text and hook words, approved plates (`measure_plate`), first render of one episode, then `calibrate_sat_ceiling` and limit tuning.
3. Build the three V4 runners and wire the controller to the render backend.
