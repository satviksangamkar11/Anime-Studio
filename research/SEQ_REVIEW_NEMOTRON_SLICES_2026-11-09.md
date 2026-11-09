# Nemotron Super slice reviews

## blot.md rules part 1/4
PROBLEMS:
- [RULE 20] Scripted edits inserted control characters (newline in string, backspace in regex) on 11-07/11-08 | python/heredoc edits skipped parse and control-character checks | cost not stated
- [RULE 15] Haiku xhigh coders stalled twice on 2700-line pipeline.js | big UI file given to Haiku xhigh instead of Sonnet high | cost: two >20-minute stalls, agents replaced
- [RULE 14] Google Drive not reachable from this machine | no Drive connector or desktop drive letter | cost: heavy outputs wait; D: needs owner OK; C: nearly full, D: few GB
- [RULE 10] Worktree copies of blot.md are stale | blot.md not synced to worktrees on rule change | cost not stated
- [RULE 12] Dots reviewer was slow | Dots used as free reviewer | cost: slow reviews

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- Add a post-script-edit gate: `ast.parse`, `node --check`, and `grep -c $'\x08\x0c'` after every python/heredoc edit before the step is logged complete
- Route large UI files (e.g., 2700-line pipeline.js) to Sonnet high by default; enforce 20-minute stall detection with immediate agent replacement
- Add Google Drive connector, point `flow_outputs`/render outputs to the Drive folder, and move finished heavy files off D:
- Keep one authoritative `blot.md` and sync it to all worktrees on every rule change; prohibit stale worktree copies
- Use Nemotron Super VL + Xing via `research/_run_uifinal_reviews.py` instead of Dots

## blot.md rules part 2/4
FAILED after 3 tries: OK 200

## blot.md rules part 3/4
FAILED after 3 tries: OK 200

## blot.md rules part 4/4
PROBLEMS:
- [Rule 46] libass silently drew a system font instead of Mukta ExtraBold | ASS family set to plain "Mukta" rather than font file name ID 1 "Mukta ExtraBold" | wrong font rendered on captions.
- [Rule 46 amendment] FINAL_TEXT_v2.json windows wrong for 14 of 54 lines | scoring used permission windows instead of REAL speech from vo_tracks_report.json | rebuild to final_reel1_v4 (rule 42).
- [Rule 48] Stock-synth/init-patch sketches sent as music | default Ableton patches used for sketches | owner rejected ("sounds shit"), sketches unus

## MISTAKES_AND_LESSONS part 1/3
FAILED after 3 tries: OK 200

## MISTAKES_AND_LESSONS part 2/3
FAILED after 3 tries: OK 200

## MISTAKES_AND_LESSONS part 3/3
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 1/12
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 2/12
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 3/12
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 4/12
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 5/12
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 6/12
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 7/12
PROBLEMS:
• [20:16 R1/R2/R3 FAIL] Flow jobs attempted while Flow pane not signed in to Google | agents launched before owner completed browser sign-in | all R1–R3 stopped, 0 jobs done, relaunch needed after 20:17 sign-in.
• [20:37 R1 FAIL] review_shot.py cp1252 UnicodeEncodeError printing Devanagari reason | script output encoding not UTF-8 | rerun with PYTHONIOENCODING=utf-8 required for 001A B.
• [20:45 me DECISION] SHOT-001A 8183af84 rejected at full size: Devanagari letters in sparks | no-text rule violated at generation; full-size check occurred after initial acceptance | regen with no-glyph sentence, max 3 submits; keeper retired.
• [21:13 R5 FAIL] SHOT-001A title SHOT-001A__v01 sits on edit 1f1d26c1, not log id 8aa727e3 | duplicate/aliased gallery titles | unique-title verification required before 2K download; wrong-tile risk.
• [21:15 R5 FAIL] Click opened wrong tile a1019a88 (RETIRED-SHOT-006B-D); text typed into its edit box | UI tile targeting error amid duplicate/retired titles | no submit; page abandoned; wasted action.
• [21:18 R7 DECISION] SHOT-006B attempt 1 submitted with “no pillars” | environment spec applied before coordinator confirmation; pillars belong to ENV_BRAHMA_SABHA | wrong direction; corrections re-sent; resubmit required.
• [20:29 R3 DECISION] SHOT-002A/002B moved to R4; 002A chip attach stopped, nothing submitted; composer discarded by reload | agent handoff/reload discarded composer state | 002A chip attach not submitted; work lost.
• [20:23 R1 DECISION] SHOT-003A coordinator ids c989ad77/66571c66 not found in gallery | coordinator gallery ID mismatch | manual content mapping required; selection risk.

ORDER-PROBLEMS:
• [20:16 R1/R2/R3] Flow submission/edits ran before Flow pane owner sign-in | should have waited for owner to sign in to Flow in the pane, then relaunch from brief.
• [21:13 R5] SHOT-001A rename/edit ran before verifying unique gallery title / correct tile ID | should have waited for title-ID verification before rename or 2K download.
• [21:15 R5] Edit-box input ran on wrong tile a1019a88 before confirming target tile | should have waited for correct tile focus before typing.
• [21:18 R7] SHOT-006B submission ran before confirming environment contract (

## PROJECT_LOG decisions/fails/owner lines part 8/12
PROBLEMS:
- [11-08 21:31 R7 SHOT-006B] Submit cap of 4 reached before owner edit order; 5th submit needed | cap not extended/verified before edit order | edit order not run; shot kept NEEDS_REVIEW
- [11-08 21:34 R5 SHOT-001A] Submit 5/6 crop failed; last allowed submit consumed | edit/crop prompt did not yield valid framing | final submit wasted on failed crop
- [11-08 21:34 R6 SHOT-006A] Edit rejected: Brahma off-centre, sage cut by edge; submit 4/4 last allowed | wrong base (SHOT-005A) used instead of accepted 6B layout | rework required; cap extended to 6
- [11-08 21:42–21:55 D/L agents] 2K capture fails: window.__dl null, no blob/network download after repeated clicks | download hook/recipe not capturing file | only 10 of 20 filed; 003A, 009A, 010A, 010B open for re-run
- [11-08 21:42 D3/L1–L4] Browser tab cap reached (9 flow tabs); tabs_create refused; agents had no own tab | tab/pane gate blocks concurrent agent tabs | 0 shots downloaded initially; runs stopped pending tab free
- [11-08 22:30 h3_author] Claude weekly limit (429) for opus and sonnet | model quota exhausted | fallback to free NVIDIA scheduler; failed run wrote nothing
- [11-08 23:21 render dry run] Only 4/10 shots ready; SX-01 errors in 3,4,5,8,9,10; controller has no GPU backend wired | gaps unfixed; GPU backend not wired | render not green; delayed
- [11-09 00:16 render kalika_reel1] run.py 19.7 MB never started on VM; /content lacks out/ or Wan2GP; kernel idle; local exec stuck; ~2 units spent | oversized embed and VM environment unprepared | units wasted; run killed and rebuilt
- [11-08 21:47 watermark] Watermark remover blocked waiting for downloads 20/20 | upstream downloads incomplete | pipeline stall

ORDER-PROBLEMS:
- [11-08 21:42 D/L agents] Download agents launched | should have waited for a free browser tab / tab cap freed
- [11-09 00:16 render kalika_reel1] Render attempted | should have waited for GPU backend wired, VM out/ and Wan2GP present, and all shot gaps fixed

ARCH-CHANGES:
- Add submit-cap verification gate before owner-ordered edits: check/extend cap before accepting edit orders
- Add download-manifest gate between 2K download and Gate B/watermark/render: require 20/20 filed downloads with capture receipts
- Add render preflight gate before run_colab_batch.py --go: verify GPU backend wired, VM out/ and Wan2GP present, embed size under threshold, all shots ready
- Add model-quota check before h3_author opus/sonnet runs with automatic fallback model selection
- Add browser-tab scheduler/queue for download agents so launches wait for an available tab

## PROJECT_LOG decisions/fails/owner lines part 9/12
PROBLEMS:
- [11-09 01:10] Render attempt 3 terminated ~2 min after pip install began; no clips; local runner and exec killed | Colab session terminated (likely by owner while closing extra notebook, not proven) | balance 185.30; time lost
- [11-09 01:22] Render attempt 5: all 10 shots rc=1 in 10 s | blank line in H3 prompt parsed into 2 generation requests | ~0.9 units spent (balance 184.86)
- [11-09 02:50] SHOT-008 re-render v2: cobras rose behind Brahma from frame ~48 to end | sound cues in prompt ('serpents hiss softly', etc.) caused model to draw serpents; only 16 frames reviewed earlier | re-render required
- [11-09 03:01] Render started before full compiled prompt was read | render launched without reading run.py + prompt in full | render stopped; runner killed by PID; session stopped; prompt defects found after start
- [11-09 05:21] SHOT-007A rename to SHOT-007A__v02 not saved after 2 tries | save failed after 'Done editing' + small check | tile title still wrong; SHOT-007B delayed
- [11-09 05:27] SHOT-007B download clicked but window.__dl stayed null | download window returned null | retry later needed

ORDER-PROBLEMS:
- [11-09 02:34] SHOT-008 video render (batch kalika_shot008, GO on G4) ran before voices were generated (owner go at 02:42) | should have waited for voices/audio to lock length (owner: audio first, then video built to audio length)
- [11-09 01:10–01:55] Render attempts 3–6 ran before voices were generated | should have waited for voices/audio
- [11-09 03:01] Render attempt started before full compiled prompt was read and reviewed | should have waited for full prompt read + reviewer sign-off

ARCH-CHANGES:
- Add an audio-first gate: no GPU render batch may start until voices/music/sound mix are complete and a per-shot audio manifest (lengths/cues) is handed to the video stage; render builds to that length.
- Add a pre-render gate: full compiled prompt and run.py must be read and reviewer-approved before any render GO; block start until gate passes.
- Make build_h3_batch blank-line rejection a hard prompt-compile gate (reject blank lines before batch build, not after rc=1).
- Separate audio cues from visual prompts: shots.json audio_cue must be resolved by the audio stage and not injected into image/video generation prompts before audio exists.

## PROJECT_LOG decisions/fails/owner lines part 10/12
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 11/12
FAILED after 3 tries: OK 200

## PROJECT_LOG decisions/fails/owner lines part 12/12
PROBLEMS:
- [SMP2] FAIL restore stems | wrong path used; stems/ removed then restored from backup | restore disruption (stems_v3 intact)
- [ABL2] FAIL create_clip track 5 slot 1 | clip slot occupied; no delete-session-clip or clear-notes tool | nothing written; arrangement blocked
- [SFX1] FAIL onset test | log-flux + 2048 frames put clicks 56 ms early | test failure; fix to linear flux/512 frames and retest
- [MIX1 v6 round 1 triage] voice over SFX+music below target | no voice-priority ducker before checks | round 2 remix required
- [EQ1 v5] noduck pre at -2.7 LUFS clipped; no sustained clashes cut | raw stems measured without global gain; SUSTAIN 0.25 too high | clipping; no clash cuts
- [18:00 owner] mixing done in code outside Ableton; stems not brought back | Ableton export access denied; MCP cannot write arrangement/automation/render | owner anger; code-native mix; Ableton-native rework proposed
- [18:20 render naming] r1–r4 overwritten in place | no unique render naming before r5 | r1–r4 settings/results lost

ORDER-PROBLEMS:
- EQ1 v5 loudness/clipping check ran before global gain on raw stems; should wait for stem global gain then 2-pass loudness
- MIX1 round 1 compliance checks ran before voice-priority ducker; should wait for ducker application
- Code-based mixing/render ran before Ableton-native mixing / stems returned to Ableton; should wait for Ableton access or mix in Ableton

ARCH-CHANGES:
- Add a path-validated, versioned stem manifest stage before any delete/restore
- Add a delete-session-clip / clear-notes tool to the Ableton MCP interface
- Add an onset-alignment QA gate (max ms offset

## docs/PIPELINE_AUDIT_2026-11-07.md part 1/2
FAILED after 3 tries: OK 200

## docs/PIPELINE_AUDIT_2026-11-07.md part 2/2
FAILED after 3 tries: OK 200

## docs/AUDIT_2026-11-08_REEL1.md part 1/1
- [Gap 1 / pack_to_spec / Gate B] pack_to_spec refuses writer V4 shots ("unsafe set id None"); Gate B image prompts cannot be built from new writer output | pack_to_spec reads shot.set, shot.cast, shot.props and shot.keyframes, which V4 rows lack | cost: not stated
- [Gap 2 / v4_to_h3 + linter / writer gates] 73 H3 lint errors on reel 1; missing authored fields, bad dynamic splits/handles, missing 7th-second mouth state and sound cues; reel passes writer gates but is unrenderable | H3A author step has not run; writer validator never runs H3 timing/seam checks | cost: ~20–30% more GPU time per clip (pixel frames 192→243 for an 8 s shot) from H3 head/tail spare frames
- [Gap 3 / SPEECH-01 / Gate D vo_fit] No speech-rate check before voice; 20 lines above 3.2 wps (EN SHOT-003 4.4); Gate D vo_fit needs paid ElevenLabs wav first | fit check deferred until after real voice is generated | cost: not stated
- [Gap 4 / check_pack / pack_validator / edit] Retention rules and check_pack measure pixel frames (70.8 s); pack_validator and edit use editorial seconds (70.0 s); time-window rules off by handle frames | two clocks (pixel vs editorial) not unified | cost: not stated
- [Gap 5 / story gate checks / SRC-01] Story gates self-graded by writer with its own evidence strings; no script vs SOURCE.md comparison | no automated source-fidelity comparison; semantic fidelity needs reviewer pass | cost: not stated
- [Gap 6 / P1 / style_pack] story.json with no style_pack; writer uses deva_neon; check_pack fails P1 (loud, not silent) | missing/default style_pack not enforced | cost: not stated

- Voice/paid ElevenLabs wav (Gate D vo_fit) produced before speech-rate validation | should wait for SPEECH-01 per-language words-per-second check
- Writer gates pass before H3 timing/seam/mouth/sound validation (v4_to_h3 + linter, H3A author step) | should wait for H3 timing and seam checks before the reel is declared renderable

- Add SPEECH-01 pre-voice gate (director/pack_validator.py, writer_prompts.py): script must pass per-language wps limits before any paid voice wav is commissioned
- Merge H3 authoring/timing/seam checks into writer gates: add H3A author step and validator rule H3-01 so writer gates cannot pass until v4_to_h3/linter timing, mouth, and sound-cue checks pass
- Unify on one editorial clock: check_pack and core/timeline use editorial seconds (70.

## research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md part 1/1
PROBLEMS:
- [cue_sheet.json] Cue sheet built on v3 lengths instead of v4 lengths | created before v4 editorial timeline was final | cost: must re-run cue sheet on v4 lengths.
- [v3 voices / old vo folders] v3 voices at up to 1.12 speed vs v4 natural 1.00; old voice folders use v3 lengths | voice assets built before final timeline | cost: v3 superseded; v4 rebuild required.
- [final_reel1_v4] Reel finished without music | BGM slot passed as None in build_mix_filter; video rendered before music | cost: music must score to locked picture; no regeneration allowed.
- [white-outs] White-outs must be recomputed as "shot N + X" | placed against pre-extension timeline | cost: manual recompute after extensions.

ORDER-PROBLEMS:
- Cue sheet/score ran before `editorial_by_lang.json` v4 was frozen; should have waited for v4 lengths.
- Video render (`final_reel1_v4`) ran before music/BGM; should have waited for audio lock so picture fits audio length.
- White-outs computed before timeline extensions were final; should have waited for frozen editorial timeline.
- Old voice assets (`vo/`, `vo_{lang}/`) built on v3 lengths; should have waited for v4 editorial timeline.

ARCH-CHANGES:
- Add a gate that freezes `editorial_by_lang.json` as a timeline contract before cue sheet, white-outs, voice tracks, and video render may proceed.
- Make `build_final_reel.py` / `build_mix_filter` reject a `None` BGM slot; require a validated BGM manifest/track before final render.
- Add an audio-lock stage: voice track report and BGM manifest must exist and pass validation before `build_final_reel.py` runs.
- Derive white-outs automatically from the frozen timeline ("shot N + X") instead of manual recompute.

## CHECKLIST_ARCHITECTURE_2026-11-07.md part 1/1
PROBLEMS:
- none in this slice

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- none in this slice

## STATUS.md part 1/2
FAILED after 3 tries: OK 200

## STATUS.md part 2/2
PROBLEMS:
- [Open: Run the staged writer for real on Kaliya Mardan (v2.2 brief) and check the pack] Staged writer not run end-to-end on v2.2 brief; pack unchecked. | Root cause: not executed. | Cost: none stated.
- [Open: Flow reference families (identity, turnaround/pose, acting) per character; then keyframes] Character reference families not completed before keyframes. | Root cause: not done. | Cost: none stated.
- [Open: First controlled Kaggle batch (audit's 16 renders: 4 scenes x 2 configs x 2 seeds), then visual QA on the frames] Controlled Kaggle render batch and frame visual QA not performed. | Root cause: not done. | Cost: none stated.
- [Open: Prompt upgrades from the second audit (Ref2VA retention_analysis, FL2VA picture-to-time alignment), PNG instead of JPEG references,

## research/AUDIO_PLAN_FROZEN_2026-11-06.md part 1/1
PROBLEMS:
- [Decision 5 / loudness measurements] Loudness varies up to 14 dB between clips (arm A −23.7/−21.1, arm C −24.3/−23.2, arm D −12.3/−10.2 LUFS) | Independently rendered clips have no shared audio state and no pre-join gain matching | Gain matching required before join; uneven loudness at cuts otherwise
- [Decision 6] Music or vocal leaks can appear at clip 4 or later and be missed | QA checks only the first clip; drift can appear later | Not stated (missed leaks force re-render of affected clips)
- [Decision 2] Negative prompt wording such as "No music, no score..." violates H3 rules | Nemotron proposed negation-based wording; linter warns on negations | Not stated
- [Decision 1] No shared background score can exist across clips | Independently generated clips have no shared audio state between renders | Owner must add music separately over the finished reel
- [Decision 4 / rejected review] Vocals can leak into model audio and cannot be separated from effects | Vocal tools do not separate effects from music | Owner removes vocals in post with his own tools
- [Decision 5] Dynamic loudnorm second pass is unreliable on 5 s clips and changes dynamics per clip | Loudness-range logic is unreliable on short audio | Not stated
- [Code changes / linter SD-03] No automated check that soundscape starts with "Sound effects only:" and includes the location's bed | Missing SD-03 rule next to SD-01/SD-02 | Not stated
- [Decision 6] Single-shot patching is used instead of template fix + re-render | Plan is prevention via shared template and QA, not post separation | Re-rendering affected clips costs GPU/video render time

ORDER-PROBLEMS:
- [Decision 6] Separate audio test render ran while rendering | Should be folded into normal clip QA on real clips only
- [Decision 5] Clips joined before gain matching | Every clip must be measured and gain-matched to −16 LUFS before the join
- [Decision 5] 5 ms fades applied before gain | Fades must be applied after gain, at every cut
- [Decision 6] Single shots patched after a leak is found | Shared template must be changed first and affected clips re-rendered with owner approval

ARCH-CHANGES:
- Add `loudness_plan(measured)` stage in `assemble_reel.py` (pure gain computation, target −16 LUFS, limiter) before the join, writing `loudness.json`; gate: no join until gain is computed
- Add linter SD-03 as a pre-render gate validating soundscape starts with "Sound effects only:" and includes the location's bed when defined
- Add registry `sound_beds` (location id → phrase ≤12 words, fixed casing/punctuation) and have the compiler inject "Sound effects only: <bed> <effects>" into every soundscape
- Make the audio chain an ordered stage: gain → 5 ms fades → join, with fades strictly after gain
- Remove the separate audio test render stage; fold audio QA into normal clip QA covering every clip, not just the first
- Add a re-render gate: on music/vocal leak,

## research/VOICE_SYSTEM_DESIGN_2026-11-09.md part 1/1
PROBLEMS:
- [bible.json voice_map] placeholder IDs (`placeholder-NARRATOR-hi`) for every speaker/language | voice map not resolved to real voice IDs | cost not stated
- [h3/voice_engine.py, h3/voice_manifest.py] no calls to ElevenLabs | voice pipeline not integrated with API | cost not stated
- [Gate D h3/gate_d_audio.py] `vo_fit` checks audio length against the slot | slot/timing fixed before audio duration is measured | cost not stated
- [ElevenLabs account] no Hindi voice in the account | Hindi voices missing from account | cost not stated
- [Models] eleven_multilingual_v2, flash_v2_5, turbo_v2_5 support hi but not mr | model does not cover Marathi | cost not stated

ORDER-PROBLEMS:
- [Gate D h3/gate_d_audio.py] `vo_fit` checked audio length against the slot before ffprobe-measured duration existed | should wait for S7 measure/ffprobe duration before fixing slot/timing
- [bible.json voice_map] placeholder IDs used before cast resolution | should wait for owner voice choice and linted `voices_cast.json` (S2) before voice-dependent steps

ARCH-CHANGES:
- Add a hard gate: slot/timing lock and `vo_fit` require ffprobe-measured duration and freeze file first; derive slot width from measured audio seconds.
- Add mandatory pre-spend stage: `voices_library.json` + free previews → owner cast → linted `voices_cast.json` resolving all speaker×language, before `jobs`/`run` or Gate D.
- Contract: measured audio duration file handed from voice stage to timeline/slot stage as authoritative input for slot length.

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 1/4
PROBLEMS:
- [Cross-check #6] `post.py` and `render_controller` pass `bgm=None` | build step 10 not wired; director code does not read `story.json` bgm manifest | no BGM mixed into reel
- [Cross-check #12] Serum macro clip automation not verified | not confirmed in Live before first build | open item
- [Cross-check #13] Hybrid-cinematic or electronic style not chosen | decision deferred to gate M0 | style undecided
- [Cross-check #15] MCP tool names unknown; `D:\ableton` not in any repo | adapter written only after connection check; PC not linked to chat | build step 1 blocked
- [Cross-check #16] `PROJECT_LOG.md` on owner's PC, unreachable | log not in repo | log lines must be manually pasted
- [Cross-check #17] `story_plan.json` says 68 s, shots sum

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 2/4
PROBLEMS:
- [Old 60/120 tempo map] 120 BPM unsuited to techno/drum and bass; tempo changed at 41 s, a cut that is neither a hard cut nor an act change, breaking the act-change-only rule | Root cause: map violated genre fit and act-change-only rule | Cost: not stated.
- [Re-hook at 26 s] Re-hook placed at 26 s, outside retention window (31.5–42.0 s) from core.json | Root cause: not aligned to act change / retention window | Cost: not stated.

ORDER-PROBLEMS:
none in this slice

ARCH-CHANGES:
- Add a hard gate before component 6 (Ableton builder): block MCP calls until `score_plan.json`, `notes/*.json`, and per-track `.SerumPreset` files exist and pass validation (JSON/assets before DAW).
- Enforce tempo contract: `ableton_build.py` runs a fixed 60 BPM Live set and must not change tempo from script; all tempo authority stays in `score_plan.json` with absolute-second note placement.
- Make owner gates M0 (music bible) and M1 (spotting plan) mandatory file gates: downstream components cannot start until the upstream JSON is approved and on disk.

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 3/4
PROBLEMS:
- [Injecting Serum state into `.als` XML] reopen failed with "Unknown Compound Stream Type" | Ableton cannot parse injected Serum state in XML | set fails to reopen
- [`render_to_file`] tool was fabricated; none exists | nonexistent render tool | no automated render available
- [Serum parameter contracts] filter cutoff not among 37 verified contracts | Ableton only exposes Configure-mode parameters | raw Serum knobs cannot be automated; must route via Macros 1-4
- [Gate D `post.py`] passed `None` instead of manifest track | code did not pass score manifest | Gate D mix lacked correct score track
- [Live API] cannot write song tempo or time-signature changes | API limitation | note writer must apply tempo map externally
- [Arrangement locators] read-only from API | API limitation | shot markers must be MIDI clips, not locators

ORDER-PROBLEMS:
- [Build sequence] automation envelopes created before Serum macro response confirmed in Live | should wait for macro confirmation before first build | automation may target unresponsive parameters
- [Gate D mix] `post.py` passed `None` instead of manifest track | Gate D mixed before receiving score manifest track | score not correctly handed to mix
- [Set run] set run without `get_session_info` connection check first | should check connection before running | connection failure during build
- [Reel build] reel build before presets generated and listed in bible | presets generated once per story, then reused | missing or inconsistent presets
- [M2 gate] final listen before Gate D preview mix exists | M2 consumes Gate D preview mix | no mix to review

ARCH-CHANGES:
- Add a pre-build gate confirming Serum macro response in Live before automation envelopes are written.
- Make the manifest track a required contract input to Gate D `post.py` (no `None`).
- Insert `get_session_info` connection check as the first step of every Ableton set run.
- Add a preset-generation and bible-lock stage that must complete before any reel build consumes presets.
- Enforce render-before-GateD: `check_score.py`-validated WAV must exist before Gate D mix is invoked.
- Enforce stage order M0 (story) → M1 (reel) → M2 (reel), with M2 gated on Gate D preview mix.

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 4/4
FAILED after 3 tries: OK 200
