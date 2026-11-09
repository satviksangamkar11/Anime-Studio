# Nemotron Super merged report

# ANIME-REEL PIPELINE POST-MORTEM — MERGED REPORT

## 1. PROBLEMS (deduplicated, grouped by stage, most expensive first)

### STORY / WRITER
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| W1 | Writer models lacked web context; story facts wrong | No `--web` flag / `WEB_NOTES.md` for free models | Days of rework, 2.62 USD Opus lost | RULE 16, C8 |
| W2 | Opus `--output-format json` kept only last turn, lost 90% of answer | CLI contract misunderstood; should use `stream-json` + `join_stream` | 2.62 USD, 90% content lost | C8, R23 |
| W3 | Repair prompt allowed full rewrite instead of targeted diff → validator failure | No targeted-repair contract | 1 Opus call, failed stage | C9 |
| W4 | Weekly Claude limit hit mid-pipeline; blocked Opus/CLI reviewers for days | All heavy writer work on one sub, no budget watch | Days blocked | C10 |
| W5 | Kalika parts 1+2 mixed narratives from two YouTube links | Owner sent mixed sources; no source-separation step | Rework, confusion | LOG 4/12 22:13 |
| W6 | Writer V4 emitted `route=Ref2VA` but `run_kaggle` only accepts `{pika6,sing4,sing8}` | Writer contract not validated against runner | Pipeline gap, 44 HIGH gaps | LOG 4/12 01:16, P6 |
| W7 | `v4_to_h3._source` reads `stage_1*.json` (CLI envelope) not `story_plan.json` | Converter reads wrong file | Converter produces garbage | LOG 4/12 01:16 |
| W8 | Converter still emits `"with <cue>"` glue (e.g., `"with a veil snaps"`) | Glue not fixed at source with test in live tree | Every shot prompt corrupted | W9 |
| W9 | Writer stage 2 repair rewrote 3e1 as 11 shots, failed validators | Repair prompt allowed full rewrite | 1 Opus call, failed stage | LOG 5/12 13:57 |
| W10 | ML-08 checker false positives: `aai` (mother) flagged as Hindi leak; standalone `ne` flagged as Hindi ergative but was in MR_ONLY | Checker logic wrong for Marathi | Redo needed | LOG 5/12 10:33 |

### KEYFRAME IMAGES
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| K1 | Full-size review revealed defects hidden in thumbnails: letters in sparks, wink, cropped sages, wrong crowns | Reviewer advisory only; thumbnails hide defects | Many hrs, ~150 Flow submits | F1 |
| K2 | A/B keyframes generated as independent options, not start/end frames → mismatched (8A standing vs 8B seated) | A/B treated as "pick better" not start/end | Many hrs, ~150 Flow submits | F2, N4 |
| K3 | Owner misunderstood "A and B are two options" vs start/end frames | Not explained in packet/UI | Rework rounds | F3 |
| K4 | Repeated long-prompt regenerations (1A: 5, 6A/6B: 8 submits) instead of single change-list on reference | No rework rule | Many hrs, ~150 Flow submits | F4 |
| K5 | `@` chip picker showed stale OLD- tiles; agents picked wrong, renames silently failed half the time | Duplicated/stale names, UI quirks | Agent stops, wrong picks | F5 |
| K6 | Tab cap ~9; finished agents left tabs open → download agents couldn't start; agent without `tabId` renamed whole project | No tab discipline | Project rename, blocked agents | F6 |
| K7 | 2K download: 4 Haiku agents clicked x=615 not x=668 for 20+ min → null captures | Coordinate clicks without screenshot | 20+ min agent time | F7 |
| K8 | Flow project signed out; 3 agents started/stopped, reported "done"/"blocked" silently | No sign-in check before launch | Silent failures | F8 |
| K9 | Edit IDs in notes didn't match gallery → agent lost time searching | IDs from partial notes | Agent time | F9 |
| K10 | Watermark detector missed sparkle on 4/20 (bright/gold backgrounds); 6A had baked-in ghost star from edit ref | Threshold tuned on dark; edits copy watermark | Missed detections, ghost artifacts | F10 |
| K11 | Viewport-dependent picker UI (9:16 vs desktop) breaks chip attachment flow | Picker contract changes with aspect ratio | Shots blocked, retries wasted | LOG 6/12 19:00-19:09 |
| K12 | JS data-URL capture overflowed tool output (~262k chars); no files written | Capture method exceeds tool output limit | Tile lost, no review/rename | LOG 6/12 19:05 |
| K13 | Canvas fetch fails (CORS); canvas tainted; no file written | Cross-origin image fetch blocks canvas-to-file | Tile lost, shot stopped | LOG 6/12 19:06 |
| K14 | Composer state machine breaks after first chip: second `@` stays literal | Picker/composer not reset cleanly | Shot blocked on chip 2 | LOG 6/12 19:07-19:09 |
| K15 | Rename flow (title input click, type, Done editing) not persisting after reload | Flow UI rename persistence failure | Tile not renamed, retry-once rule triggered stop | LOG 6/12 19:09, 19:44, 19:59, 20:00 |
| K16 | Reviewer advisory blocks despite coordinator later overruling | Mandatory regen on advisory block | Rework cycle | LOG 6/12 19:19, 19:27 |
| K17 | Review script crashes on exit (exit 1 after printing verdict) | `review_shot.py` health monitor missing | Review result lost | LOG 6/12 19:48-19:52 |
| K18 | External tab closure breaks submit confirmation | No tab/process isolation | Unknown state | LOG 6/12 20:00 |
| K19 | Keyframe generation ran before shot script verification against per-second directives | No verification gate | Keyframes mismatch script (Brahma seated vs rises) | W7 |
| K20 | Picture reviewer (Super VL) wrong: claimed two attendants + Sandhya facing Kamadeva in 007B; actual has three sages + Sandhya facing viewer | Reviewer not verified at full size | False acceptance | W8 |
| K21 | Sheet prompts written with '9:16 vertical' while brief says 16:9 plates | Prompt authoring ran before brief aspect-ratio contract enforced | Plates wrong aspect | LOG 5/12 18:15 |
| K22 | Chip name collisions (CHAR-BRAHMA, CHAR-KAMADEVA, CHAR-SHIVA each match 2 rows: exact + OLD-) | STYLE_CHIP_SHEET identical v01 for every story; no rebuild after accepted flags | 6 shots blocked | LOG 5/12 18:58-18:59, LOG 4/12 01:17 |
| K23 | `@` picker shows no rows in narrow pane (typed @CHAR-BRAHMA, no menu) | Coordinator rule: exact-name match only | BLOCKED pending picker | LOG 5/12 18:59 |

### VIDEO RENDER
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| V1 | Render attempted before GPU backend wired (controller explicitly says not wired) | No GPU_BACKEND_READY gate | Wasted sessions | LOG 8/12 23:21 |
| V2 | Render attempted before shots pass quality gate (6/10 shots have SX-01 errors) | No SHOTS_QUALITY_PASS gate | Failed renders | LOG 8/12 23:21 |
| V3 | Render attempted before mandatory review gate complete (owner said "fix all gaps, start render after fixes") | No MULTI_REVIEW_SIGN_OFF gate | Wasted GPU units | LOG 8/12 00:01, 23:37 |
| V4 | External download (chumpy-0.71) returned HTTP 504 not checked before paid Colab session | No pre-flight curl check of external URLs | 3 failed paid renders, 0.58 units | RULE 40, W10 |
| V5 | Blind pip retry after first 504 without diagnosing cause; 2nd/3rd attempts only confirmed persistence | Retry before root cause analysis | Wasted sessions | W12 |
| V6 | Run.py 19.7 MB never starts (/content empty after 13 min, kernel idle); local exec stuck sending | No script-start proof gate (size limit unknown, no `/content/out` check within 180s) | ~2 GPU units spent | LOG 8/12 00:16, C3, C4, R28 |
| V7 | All 10 shots rc=1 in 10s: blank line in H3 prompt parsed as 2 generation requests (T0 used single newlines) | Prompt builder didn't collapse blank lines; no GPU test-run before batch | ~0.9 units, 15 min | C6, R30 |
| V8 | Fetch split `FILES.txt` on spaces (names contain spaces), downloaded garbage, didn't stop session | Untested with real filenames | Extra billed minutes | C7 |
| V9 | Failed 'colab new' left unnamed G4 session billing 10 units/hr; CLI couldn't stop (no state record) | No immediate `colab sessions`/`colab usage` check after failure | ~1.16 units, 25 min | W16 |
| V10 | Runner didn't stop after RESULT.json=ALL DONE; polled timeline.txt in loop, G4 billed 10 units/hr until manual stop ~10 min later | No auto-stop logic | ~1.67 units | W17 |
| V11 | Three setup failures hid behind each other (GitHub 504, colab connection drop, upload websocket drop); each fix found only by running | No pre-flight validation of all steps on real VM via free checks | 6 failed paid attempts before attempt 7 passed | W18 |
| V12 | Render dry run: only 4/10 shots ready; SX-01 errors in shots 3,4,5,8,9,10; controller reports "no GPU backend wired" | Sound-cue rule SX-01 appeared only in render controller after authoring → authoring ran twice | Authoring ran twice | P7, LOG 8/12 23:21 |

### VOICES / AUDIO
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| A1 | Voices generated AFTER video render; no voice clips supplied | Wrong step order (video before audio) | Extra 'editorial timeline' repair step needed | LOG 1/12 01:47 |
| A2 | Voice windows sized to rendered clip length (6.6–10.1s) not editorial length (5–8s); 14/54 lines overran cut up to 1.46s | Used clip timing instead of assembler's editorial plan (`timing_and_lattice.trim_in/out`, `editorial_duration_sec`) | 8 lines rewritten shorter, regenerated | RULE 42, W19, RULE 46 amend |
| A3 | No pre-voice speech-rate check; 20 lines >3.2 wps | Missing gate before voice generation | Rework | LOG 5/12 12:10 (3) |
| A4 | Gate D reported script-level retention failures (narration coverage 86% vs 90%, 27 vs 38 words, dead air 1.5s); waived only by owner order with codes in report | Findings about script not build; waiver process informal | Not stated | W20 |
| A5 | Audio cues in prompt ("serpents hiss softly") interpreted visually by video model | Audio cues not stripped from video prompt | Re-render needed | LOG 9/12 02:50 |
| A6 | Batch 1 (32 clips) had 19 clips over slot, up to 2.6× length | Words-per-second estimation used instead of real measurement | 19 oversized clips; 52 credits wasted | RULE 38 |
| A7 | ElevenLabs speed 1.15 had no effect on pilot | Speed parameter not validated | Credits wasted | RULE 38 |

### MUSIC
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| M1 | No music stage defined in pipeline; music generation never attempted | Pipeline gap | Missing music track | Implicit from gaps |

### SFX / MIX
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| X1 | Gate D's own -14 LUFS target conflicts with -16 LUFS standard | Duplicate loudness config | Inconsistency | LOG 2/12 16:02 |
| X2 | Cue-layer hardening coerced malformed blocks silently instead of explicit ValueError | Silent coercion | Broken code pushed | LOG 2/12 16:12 |
| X3 | Sound-cue rule SX-01 (7 action sentences need sound word) appeared only in render controller after authoring → 6/10 shots "not ready" | Authoring ran before `render_controller --dry-run` | Authoring ran twice | P7 |

### CAPTIONS
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| P1 | Python heredocs turned `\n` in strings to real line breaks (≥8 times) | Heredoc used for text with backslashes | Wasted rounds | P1, W14 |
| P2 | Caption modules not formalized; `core/caption_text.py` + `core/caption_export.py` built by agents, lead integrates into `core/captions.py` with defined interface | No module contract | Collection errors block suite | LOG 2/12 13:17 |
| P3 | `test_caption_text.py` collection error blocks full core run | Collection error in test file | Blocks test suite | LOG 2/12 13:20 |

### ASSEMBLY / QC
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| Q1 | Review round ends without second review of fixes; process allowed single review | No mandatory second review gate | Defects escape | RULE 5 |
| Q2 | Agent prompts sent unreviewed; no pre-flight review gate | No Super VL + Xing review before send | Bad instructions propagate | RULE 6 |
| Q3 | UI task marked done without 375/1280px browser test in both languages + cold test | No exit gate | High defects in UI | RULE 9 |
| Q4 | Log gaps; stale `blot.md` copies in worktrees | No single log discipline + no sync | Context loss, drift | RULE 10 |
| Q5 | Steps/facts hidden behind folds, hash links, hover | UI designed for power users | 60-year-old user blocked | RULE 18 |
| Q6 | Style pack only named, not enforced; off-style bibles passed | No gate, no swatch check | Rework in image stage | RULE 19 |
| Q7 | Two control-char slips (newline in string, backspace in regex) on 11-07/11-08 | Scripted edits unchecked | Parse failures | RULE 20 |
| Q8 | Flow agent packet items missing | No completeness test | Pipeline breaks | RULE 21 |
| Q9 | Only Kaliya works end-to-end; no non-Kaliya verification | Pipeline not general | 2 audits, 44 HIGH gaps closed late | RULE 22, P6 |
| Q10 | Push ce74e37 went out with 2 failing Gate D tests; wrapper hid failure | Tests trusted through wrapper | Bad push | LOG 2/12 16:12, P2 |
| Q11 | Nemotron empty at 30k tokens; Xing only thoughts; OpenRouter 429 when parallel | Reviewers unreliable | Hrs of review time | P5 |
| Q12 | Dry-run only prints commands; no real one-shot test before 10-shot batch | No real GPU test gate | 4 failed starts | P8, RULE 3 |
| Q13 | Agent briefs/reports trusted: sign-in blocks, wrong tab, fake "done", "can't open tile" | No verification of agent claims | Repeated reruns | P9 |
| Q14 | Owner rules changed mid-task not always obeyed first | No rule-change propagation discipline | Wasted calls/sends | P10 |
| Q15 | `core/tests/test_retention_report.py` ImportError `retention_report` missing | Missing module in other agent's file | Blocks suite | LOG 1/12 04:59 |
| Q16 | `core/tests/test_convert_deva_h3.py` linter 15 ERRORs (KF-02×8, SD-01×2, CM-01×1, PR-05×4) | Template/registry content errors | No commit | LOG 1/12 08:25 |
| Q17 | `retention_rules.py` R2/R5 inverted vs spec (COLOUR_AUDIT.md) | Every V4 row failed | LOG 4/12 02:41 |
| Q18 | `pack_to_spec` refuses V4 shots (no set/cast/props/keyframes) | Schema drift | Pipeline gap | LOG 5/12 12:10 (1) |
| Q19 | `v4_to_h3` lint 73 errors incl. non-authored timing: dynamic split, MO-03, MO-01 7th second, SX-01 5/7; writer validator does not run them | Validator incomplete | LOG 5/12 12:10 (2) |
| Q20 | Pixel-frame vs editorial seconds 70.8 vs 70.0 | No reconciliation gate | LOG 5/12 12:10 (4) |
| Q21 | Story gates self-graded, no source fidelity check | No independent validator | LOG 5/12 12:10 (5) |
| Q22 | No styl(?) — gap list truncated | — | LOG 5/12 12:10 (6) |

### TOOLING / PROCESS
| # | Problem | Root Cause | Cost | Source |
|---|---------|------------|------|--------|
| T1 | Unauthorized Colab/render/ElevenLabs/paid calls; no enforced ban | No hard ban until owner lifts | Spend + wrong order risk | RULE 4,11 |
| T2 | C: drive hit 0 GB free (Claude temp folder) causing command failures | Cache not cleaned, heavy output not redirected to D: | Commands began to fail | RULE 37 |
| T3 | Google Drive not reachable; C: nearly full, D: few GB | No Drive connector | Heavy outputs wait/block | RULE 14 |
| T4 | Haiku xhigh coders stalled twice on 2700-line pipeline.js (no log line 20 min) | No stall watchdog | Time lost, replacement needed | RULE 15 |
| T5 | Two code trees drifted (anime_studio vs anime_studio_merge); compile mixed them | Fixes split across trees, no sync before fix | Fixes lost if not synced | W6 |
| T6 | Shell wrapper hid 2 failing Gate D tests → bad push (ce74e37) | Tests trusted through wrapper | Bad push | P2 |
| T7 | Log lines for steps that didn't happen (fake "applied fixes", DONE for retired tiles) | Wrong state believed | Wrong state | P3 |
| T8 | Kill by command pattern matched own shell (twice) → exit 255, next steps skipped | Lost min, session left running | Lost min | P4 |
| T9 | Pipeline hard-wired to first story (Kaliya): folders, `LEAP-*`, same chip name, rejected route, no V4 GPU path | No per-story folder structure + dry-run | 2 audits, 44 HIGH gaps | P6, R21, R22 |
| T10 | Converter used with "with <cue>" glue before fixing at source with test in live tree | No gate before converter use | W9 |
| T11 | Session stopped before fetching `setup.log` (error text lost) | No fetch-before-stop rule | W11 |
| T12 | Secret (HF token) pasted in chat; now in chat history and tool call | Secret not saved to `secrets/` and sent via stdin | Security risk | W15 |
| T13 | Research/UI_PARALLEL_DISPATCH write blocked by worktree path guard | File missing → both reviewer runs failed | LOG 3/12 17:59 |
| T14 | Edit script failed (backslash escapes); no change made despite log claiming fixes | Heredoc used for text with backslashes | LOG 3/12 18:47 |
| T15 | UI background pytest left no output and no process | No output capture | Time lost | LOG 3/12 19:27 |
| T16 | `ui/static/tokens.css` ignored by `.gitignore '*token*'` line 6 | Not changed (outside scope) | LOG 3/12 19:48 |
| T17 | Shell stray `cat >> /dev/null` waited on stdin | Hung | LOG 3/12 21:52 |
| T18 | Agents stopped by user around Assay interruption; cannot resume, work cancelled | No gap-cleared-before-Assay rule | Partial uncommitted edits remain | LOG 3/12 21:56 |
| T19 | HTTP 429 after 5 retries (both reviewers on one OpenRouter key simultaneously) | No key isolation for parallel reviewers | Retry delayed | LOG 5/12 03:03 |
| T20 | `refuse_finished` guard (PACK.md exists = pack finished, new call needs unfinished pack) | No re-entry mechanism | No model call, nothing spent | LOG 5/12 10:37 |
| T21 | `h3_author` lint runs on SHOT-001 counting missing boundary PNGs (KF-06, PR-00 route T2VA) which only exist after Gate B | Author lint ran before Gate B assets exist | Shots 2-10 blocked | LOG 5/12 14:54 |
| T22 | Keyframe agents attempt to pick chips before sheet renames saved / OLD- rows cleaned up | Keyframe picking ran before sheet acceptance & rename verification complete | Shots blocked | LOG 5/12 18:58 |
| T23 | Monitor process tracking broken: `ps grep` matched nothing; v03 review still running | No health monitor | Review orphaned | LOG 6/12 19:48 |
| T24 | Tab cap (9 flow tabs) blocks all download agents; no dedicated tab pool | 0/20 shots downloaded initially, ~15 min lost | LOG 8/12 21:42-21:55 |
| T25 | 2K download capture fails repeatedly: `window.__dl` null, no blob, no network request | Menu closes without toast | 10/20 shots filed after 40+ min | LOG 8/12 21:44-21:55 |
| T26 | Claude weekly usage limit (429) for opus AND sonnet; fallback to free NVIDIA model required | No model-version gate / quota watch | Step delayed, Ultra run stopped mid-way | LOG 8/12 22:30 |
| T27 | Owner adds RULE 32 (Flow prompt wording), then removes it minutes later | Owner rule churn | Confusion; rule recorded then deleted | LOG 9/12 02:29→02:30 |
| T28 | Flow UI rename persistence failure (SHOT-007A rename not saved after 2 tries) | Manual coordinator intervention needed | LOG 9/12 05:21-05:22 |
| T29 | Audio script approval pending (owner asked to explain simply; shorter text proposed) | Owner reply pending | Batch 2 + regeneration waiting | LOG 9/12 05:27 |
| T30 | SHOT-007B: Sandhya shows 3 arms (needs 4); both tiles wrong | Generated keyframe doesn't match spec | Additional edit round | LOG 9/12 05:30 |

---

## 2. ORDER PROBLEMS (every place a step ran before its dependency)

| # | Step Ran Early | Dependency Not Met | Source |
|---|----------------|-------------------|--------|
| O1 | Video render | Approved voice clips / voice_map + anchor clip | LOG 1/12 01:47, RULE 7 |
| O2 | Colour work | T3/T4 (wizard + expert-tool) verified | RULE 7 |
| O3 | Agent instructions sent | Super VL + Xing review finish + triage + re-review | RULE 6, RULE 5 |
| O4 | Fixes applied | Second review of fixed files | RULE 5 |
| O5 | Stage 2 (bible) | STYLE-01/STYLE-02 gate (style_pack_errors=0 + swatch check) | RULE 19 |
| O6 | Style chooser UI review (ASCII) | Style chooser built + simplification verified | RULE 13 |
| O7 | Authoring | `render_controller --dry-run` (sound-cue validation) | P7 |
| O8 | Full 10-shot batch render | One-shot real test on GPU | P8, RULE 3 |
| O9 | Prompt batch sent to GPU | Single prompt test-run on GPU | C6 |
| O10 | Clips fetched only at run end | Per-shot fetch during run | C1, R29 |
| O11 | A and B keyframes generated as independent options | B as edit of A (single reference + change list) | F2, N4 |
| O12 | Script uploaded | Proof it starts (size, 180s `/content/out` check) | C3, C4, R28 |
| O13 | Fetch after run | Stopping session first | C7 |
| O14 | Opus writer used `--output-format json` | `stream-json` + `join_stream` | C8, R23 |
| O15 | Repair prompt allowed full rewrite | Targeted diff contract | C9 |
| O16 | Pipeline built for one story | Per-story dry-run for each new story | P6, R21, R22 |
| O17 | `h3_prepare` called | Converter step writes H3 story (episode.json) | LOG 4/12 01:11 |
| O18 | `post.py` expects metadata.look/audio_and_dialogue_track | Converter `v4_to_h3._shot` produces them | LOG 4/12 01:13 |
| O19 | Gate B counts *__final.png | `images_dir` wired in wizard (not only API) | LOG 4/12 01:14 |
| O20 | `run_kaggle.build` expects route in {pika6,sing4,sing8} | Writer V4 emits only valid routes | LOG 4/12 01:16 |
| O21 | `v4_to_h3._source` reads `stage_1*.json` | Reads `story_plan.json` | LOG 4/12 01:16 |
| O22 | `h3_author` lint runs | Boundary PNGs present (after Gate B) | LOG 5/12 14:54 |
| O23 | Keyframe agents pick chips | Sheet renames saved + OLD- rows archived + manifest of exact chip names | LOG 5/12 18:58 |
| O24 | Sheet prompts written | Brief aspect-ratio contract enforced (16:9) | LOG 5/12 18:15 |
| O25 | SHOT-005A/5B/6A/6B generation | CHAR-KAMADEVA-v02 chip verified in picker | LOG 6/12 19:58 |
| O26 | SHOT-001A/1B/2A/2B redo | CHAR-KALI-v03 chip rename persisted | LOG 6/12 19:59 |
| O27 | SHOT-003A/B regeneration | ENV_MARKANDEYA_ASHRAM__v01 rename persisted | LOG 6/12 19:44, 19:50 |
| O28 | SHOT-008A accepted | Reviewer advisory blocks resolved | LOG 6/12 19:19, 19:27, 19:45 |
| O29 | Coordinator ordered keep best after review | SHOT-004A v03 review completion | LOG 6/12 19:49, 19:51 |
| O30 | Agents R1/R2/R3 launched | Flow sign-in verified (project URL loads, not /about) | LOG 7/12 20:16 |
| O31 | R7 submitted SHOT-006B with "no pillars" | Coordinator clarification acknowledged | LOG 7/12 21:19 |
| O32 | Owner accepted SHOT-001A | Mandatory second full-size review before final accept | LOG 7/12 20:50, 21:22 |
| O33 | R5 renamed keeper | Title/id reconciliation verified | LOG 7/12 21:13 |
| O34 | Render attempted | GPU_BACKEND_READY (backend wired + test clip renders) | LOG 8/12 23:21 |
| O35 | Render attempted | SHOTS_QUALITY_PASS (all shots green on SX-01) | LOG 8/12 23:21 |
| O36 | Render attempted | MULTI_REVIEW_SIGN_OFF (R1, R2, Super VL, Xing, Nemotron all clear) | LOG 8/12 23:37, 00:01 |
| O37 | `h3_author` started | DOWNLOADS_COMPLETE (20/20 keyframes downloaded + watermark removal verified) | LOG 8/12 22:29 |
| O38 | Boundary frames started | All keyframes downloaded and watermark-removed | LOG 8/12 22:06 |
| O39 | Voices generation started | SHOT-008 video render already GO (audio-first violated) | LOG 9/12 02:42, 02:34 |
| O40 | Render started | Reading compiled prompt/run.py (prompt review skipped) | LOG 9/12 03:01 |
| O41 | Keyframe generation | Shot script verification against per-second directives | W7 |
| O42 | Paid GPU sessions started | Free curl checks on all external download URLs | W10 |
| O43 | Pip retry ran | Root cause analysis of 504 error | W12 |
| O44 | After failed 'colab new' | `colab sessions`/`colab usage` check for orphaned VM | W16 |
| O45 | Runner continued polling | RESULT.json=ALL DONE and clips home → should stop immediately | W17 |
| O46 | Setup steps run on VM | Prior proof of each step via free checks (URL, sed requirements, wheel hash) | W18 |
| O47 | Code fix attempted | Code tree sync verified (single live tree) | W6 |
| O48 | Converter used | "with <cue>" glue fixed at source with test in live tree | W9 |
| O49 | Voice generation (audio window sizing) | Assembler's editorial timing plan (`timing_and_lattice.trim_in/out`, `editorial_duration_sec`) | W19 |
| O50 | CV review of colour v2 | v2 file existed (write completed) | LOG 3/12 19:12 |
| O51 | UI plan finalized | Brief requirements covered (voice choice, per-language caption/voice state, hook text, plate coverage, graded flag) | LOG 3/12 19:07 |
| O52 | Implementation waiting for T3/T4 verify + CV review | v2 file written | LOG 3/12 19:11 |
| O53 | Step 2 validation triggers | Step 1 (languages) saved | LOG 3/12 21:00 |
| O54 | Assay interruption | Gaps cleared before Assay | LOG 3/12 21:35, 21:56 |
| O55 | Writers for Ashtavakra + Kalika started in parallel | Owner decision: only Kalika Puran | LOG 3/12 22:01, 22:05 |
| O56 | Nemotron Kalika run started | Owner model selection finalized (switched to Claude Opus high) | LOG 3/12 21:38, 22:07 |

---

## 3. THE CORRECT SEQUENCE (numbered stage order, audio-first justified)

| # | Stage | Input Contract (from previous) | Output Contract (to next) | Gate Before Next Stage |
|---|-------|-------------------------------|---------------------------|------------------------|
| 1 | **STORY SOURCE & STYLE PACK** | Owner provides SOURCE.md + style pack name (default `deva_neon` from `core/core.json`) | `story_plan.json` (beats, characters, locales, per-second directives) + `style_pack.json` (swatches, look_rules, aspect=16:9) | **GATE S1**: Style pack lint `style_pack_errors=0` + swatch check vs `core/style_packs/<name>.json`; story_plan passes source-fidelity checker (independent validator) |
| 2 | **WRITER (V4) — AUDIO-FIRST** | `story_plan.json` + `style_pack.json` | `stage_1_raw.json` (CLI envelope) → `story_plan.json` (canonical) + `bible.json` (shots with `metadata.look`, `audio_and_dialogue_track`, `route∈{pika6,sing4,sing8}`, `editorial_duration_sec`) | **GATE W1**: Writer validator runs ALL lint codes (ML-01, ML-08, STIFF-01, SX-01, MO-01, MO-03, KF-02, SD-01, CM-01, PR-05, BIBLE-06); zero HIGH; `route` validated; `editorial_duration_sec` present per shot |
| 3 | **CONVERTER (V4→H3)** | `story_plan.json` (canonical) + `bible.json` | `episode.json` (H3 story) + `shots.json` (H3 shots with `audio_cue` stripped, `voice_window_sec = editorial_duration_sec`) | **GATE C1**: Converter lint zero errors; `v4_to_h3._source` reads `story_plan.json`; no `"with <cue>"` glue; `voice_window_sec` matches `editorial_duration_sec` ±0.5s |
| 4 | **VOICE GENERATION (PRE-RENDER)** | `shots.json` (with `voice_window_sec`, `editorial_duration_sec`) + approved voice_map (speaker→voice_id) + anchor clip from first approved H3 clip | `vo_tracks_report.json` (per-line: `clip_path`, `duration_sec`, `wps`, `fits:bool`) + `voice_map.json` | **GATE V1**: `vo_fit_check` (Gate D) — all lines `fits=true`, `wps ≤ 3.2`, narration coverage ≥90%, dead air ≤0.5s; **GATE V2**: Owner waiver only with explicit codes in report; no silent waiver |
| 5 | **SHEET JOBS & PLATE GENERATION** | `bible.json` (set/cast/props/keyframes) + `style_pack.json` + brief aspect=16:9 | `sheet_jobs.json` (ENV/CHAR/PROP chips, prompts validated aspect=16:9) → Flow submissions → accepted sheets renamed `__v01`, OLD- rows archived | **GATE P1**: `sheet_jobs.json` prompt aspect matches brief (16:9); **GATE P2**: All accepted sheets renamed `__v01` + OLD- archived; manifest `chip_manifest.json` lists exact chip names; picker smoke test at target aspect (9:16 & desktop) passes |
| 6 | **KEYFRAME GENERATION (A→B EDIT PAIRS)** | `chip_manifest.json` + `shots.json` (per-shot change list for B frame) | `keyframe_pairs.json` (A=start, B=end per shot) + Flow tiles renamed `SHOT-<id>A__v01`, `SHOT-<id}B__v01` | **GATE K1**: Full-size (100%) review of every kept keyframe by coordinator before accept; **GATE K2**: A/B pair verified side-by-side (B is edit of A, not independent option); **GATE K3**: Reviewer advisory non-blocking — coordinator can accept immediately; review script health monitor captures stdout/stderr on exit≠0 |
| 7 | **WATERMARK REMOVAL & 2K DOWNLOAD** | `keyframe_pairs.json` + Flow tiles | Local `keyframes/<shot>_A.png`, `<shot>_B.png` (watermark-free, anchor fallback `stamps_or_anchor`, all corners checked, ghost-star removal manual) | **GATE D1**: 20/20 keyframes downloaded + watermark removal verified; capture via server-side fetch (bypass CORS, size limit); rename persistence gate: reload + title verify before downstream reads name |
| 8 | **H3 AUTHOR & BOUNDARY FRAMES** | `shots.json` + `keyframe_pairs.json` (local) | `h3_shots.json` (authored prompts, boundary frames generated) | **GATE H1**: `h3_author` lint runs ONLY after Gate D1 (boundary PNGs exist); ignores image-dependent codes (KF-06, PR-00 route T2VA) until Gate B assets delivered |
| 9 | **RENDER CONTROLLER DRY-RUN** | `h3_shots.json` + `vo_tracks_report.json` + `voice_map.json` | `render_plan.json` (per-shot: `gpu_backend`, `duration_sec`, `audio_cue` stripped) | **GATE R1**: `render_controller --dry-run` — all shots green on SX-01 (7 action sentences have sound word), GPU backend wired, test clip renders; **GATE R2**: `SHOTS_QUALITY_PASS` (all shots pass criteria) |
| 10 | **MULTI-REVIEW SIGN-OFF** | `render_plan.json` + all prior artifacts | `review_signoff.json` (R1, R2, Super VL, Xing, Nemotron all clear) | **GATE M1**: Mandatory second review (Super VL + Xing) after every fix round; repeat until zero HIGH; escalation path for unfixed REAL items when rounds exhausted |
| 11 | **GPU RENDER (ONE-SHOT FIRST)** | `review_signoff.json` + `render_plan.json` | `clips/<shot>.mp4` (per-shot) | **GATE G1**: One-shot real test (`--ids SHOT-001`) passes on GPU before full batch; **GATE G2**: Script-start proof — `/content/out` exists within 180s of `--go`, else stop session; **GATE G3**: Run.py embed size ≤9 MB (JPEG q90 4:2:0) pre-upload check |
| 12 | **FETCH & ASSEMBLE** | `clips/<shot>.mp4` (remote) + `vo_tracks_report.json` | Local `clips/<shot>.mp4` + `timing_and_lattice.json` (trim_in/out, editorial_duration_sec reconciled ±0.5s) | **GATE F1**: Per-shot fetch during run (save each clip to PC the minute its shot ends); folders created before use; **GATE F2**: Pixel-frame vs editorial seconds reconciliation gate (tolerance ±0.5s) |
| 13 | **POST & QC** | Local clips + `vo_tracks_report.json` + `timing_and_lattice.json` | `episode.mp4` (final reel) + `step9_qc.json` (Gate D pass, loudness -16 LUFS single source in `core.json`) | **GATE Q1**: Gate D loudness uses `core.json` single source (not local -14); cue-layer hardening = explicit ValueError on malformed blocks; **GATE Q2**: Caption export (`core/caption_text.py` + `core/caption_export.py` → `core/captions.py` defined interface) |
| 14 | **EXPORT & DELIVERY** | `episode.mp4` + `step9_qc.json` | `G12_export.json` (YouTube metadata, thumbnails, captions) + Drive upload | **GATE E1**: `G12` export implementation complete; `asset_manifest.json` + `fallback_history.json` written; Drive connector moves finished files off D: when reachable |

**Audio-first justification**: Voice windows must derive from `editorial_duration_sec` (assembler's plan), not rendered clip length. Generating voices before render prevents 14/54 line overruns (RULE 42, W19, RULE 46 amend), eliminates sync repair, and lets render use exact audio durations. Gate V1 (`vo_fit_check`) is the critical audio-first gate.

---

## 4. ARCHITECTURAL CHANGES (ranked: what to build/change, which problem it removes)

| Rank | Change | Problems Removed (IDs) |
|------|--------|------------------------|
| 1 | **Single live code tree + sync gate**: Designate one repo (e.g., `anime_studio`); add pre-fix gate "code tree sync verified" (git status clean, no drift) before any code/prompt fix. | T5, W6, T9, T47 |
| 2 | **Hard ban on paid calls until owner lifts**: CLI flag `--allow-paid` required for Colab, renders, ElevenLabs, Opus; default deny. Log every attempted paid call. | T1, RULE 4,11, V4, V5, V9, V10, V11, W10, W12, W16, W17, W18 |
| 3 | **Audio-first pipeline with `vo_fit_check` gate (Gate V1)**: Voice generation uses `editorial_duration_sec` from assembler; `build_vo_tracks.py` validates `wps ≤ 3.2`, coverage ≥90%, dead air ≤0.5s; owner waiver only with explicit codes. | A1, A2, A3, A4, W19, RULE 42, RULE 46 amend, O39, O49 |
| 4 | **Per-story folder structure + end-to-end dry-run**: `flow_outputs/anime_<slug>/`; `packet_completeness_test` (`ui/test_packet_and_roots.py`); non-Kaliya story must pass e2e before pipeline general. | T9, Q9, RULE 22, P6, R21, R22, W13, O16 |
| 5 | **Converter fix at source + regression test**: Remove `"with <cue>"` glue from `v4_to_h3.py:153`; add test in live tree; `v4_to_h3._source` reads `story_plan.json`; writer V4 emits only valid `route`. | W8, W9, W10, O17, O18, O20, O21, T10 |
| 6 | **Writer contract: `stream-json` + `join_stream` + `num_turns` check**: Enforce in `write_pack.py`; `--web` for all models; free models get `WEB_NOTES.md` (Haiku low effort, web search) per story. | W2, W3, C8, C9, R23, RULE 16, O14, O15 |
| 7 | **Keyframe pair generation (B as edit of A)**: Single reference + change list; side-by-side pair review; full-size (100%) coordinator review gate before accept; reviewer advisory non-blocking. | K1, K2, K3, K4, K19, K20, O11, O28, O29 |
| 8 | **Chip/Sheet rename verification gate**: All accepted sheets → `__v01` + OLD- archived before keyframe agents start; `chip_manifest.json` with exact names; picker smoke test at 9:16 & desktop; viewport-agnostic picker contract. | K5, K11, K22, K23, O22, O23, O25, O26, O27 |
| 9 | **Capture gateway (server-side fetch)**: Replace JS data-URL capture with server-side fetch + save (bypass CORS, size limit); gate post-process on file-on-disk verification. | K12, K13, T25 |
| 10 | **GPU validation gates**: (a) Pre-flight curl check all external URLs before paid session; (b) One-shot real test (`--ids SHOT-001`) must pass before full batch; (c) Script-start proof: `/content/out` within 180s of `--go` else stop; (d) Run.py embed size ≤9 MB pre-upload check; (e) Auto-stop runner when `RESULT.json=ALL DONE` and clips home. | V4, V5, V6, V7, V8, V9, V10, V11, V12, O8, O9, O12, O13, O34, O35, O36, O42, O43, O44, O45, W10, W11, W12, W16, W17, W18 |
| 11 | **Mandatory second review + escalation**: Super VL + Xing review every prompt/instruction file before send; log review start/finish/send; repeat until zero HIGH; escalation path for unfixed REAL items (owner gate, BF agent auto-assign). | Q1, Q2, Q11, RULE 5, RULE 6, RULE 8, O3, O4, T19 |
| 12 | **UI exit gates + accessibility**: Browser test at 375/1280px in EN+MR + independent cold test (`research/UI_COLD_TEST_*.md`) with no HIGH; no folds/hidden/hash-only/hover for needed facts; story choice always top; locked steps visible with reason. | Q3, Q5, RULE 9, RULE 18, T13, T14, T15, T16 |
| 13 | **Style pack enforcement**: `core/core.json` `default_style_pack = deva_neon`; writer/UI read from there; API `GET /api/styles`, `POST /api/story/<slug>/style`; Stage 2 gate: `STYLE-01/STYLE-02` (style_pack_errors=0 + swatch check); off-style bible fails → repair call. | Q6, RULE 19, O5, O51 |
| 14 | **Scripted-edit guards**: Reject control chars (newline `\n`, backspace `\x08`) in string literals; prefer Edit tool for escapes; post-edit checks: `grep -c $'\x08\x0c'`, `ast.parse`, `node --check`. | Q7, T20, RULE 20, LOG 4/12 02:18, 02:40, W14 |
| 15 | **Single log discipline**: `PROJECT_LOG.md` at `D:\aai work\anime_studio\PROJECT_LOG.md`; worktree copies read-only; sync `blot.md` on every rule change; backfill gaps with `BACKFILL` lines; NOW block (≤8 lines) at top overwritten after every agent finish/checklist tick; LIVE LOG line format + max 200 chars; FAIL lines include cause + next; OWNER lines quote decision. | Q4, T3, T7, RULE 1, RULE 10, RULE 1
