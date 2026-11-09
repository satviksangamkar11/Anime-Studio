# Nemotron Super slice reviews

## blot.md rules part 1/4
PROBLEMS:
- [RULE 1] lines skipped in log | session/account change loses context | context lost
- [RULE 4,11] unauthorized Colab/render/ElevenLabs/paid calls | no enforced ban | spend + wrong order risk
- [RULE 5] review round ends without second review of fixes | process allowed single review | defects escape
- [RULE 6] agent prompts sent unreviewed | no pre-flight review gate | bad instructions propagate
- [RULE 7] colour work started in parallel with coder owning style.css/index.html | no gate after T3/T4 | UI/style conflicts
- [RULE 9] UI task marked done without 375/1280px browser test in both languages + cold test | no exit gate | high defects in UI
- [RULE 10] log gaps; stale blot.md copies in worktrees | no single log discipline + no sync | context loss, drift
- [RULE 14] Google Drive not reachable; C: nearly full, D: few GB | no Drive connector | heavy outputs wait/block
- [RULE 15] Haiku xhigh coders stalled twice on 2700-line pipeline.js (no log line 20 min) | no stall watchdog | time lost, replacement needed
- [RULE 16] writer models lacked web context | no --web / WEB_NOTES.md | story context errors
- [RULE 17] log line and blot.md update not in same step | no atomic rule-change discipline | drift
- [RULE 18] steps/facts hidden behind folds, hash links, hover | UI designed for power users | 60-year-old user blocked
- [RULE 19] style pack only named, not enforced; off-style bibles passed | no gate, no swatch check | rework in image stage
- [RULE 20] two control-char slips (newline in string, backspace in regex) on 11-07/11-08 | scripted edits unchecked | parse failures
- [RULE 21] Flow agent packet items missing | no completeness test | pipeline breaks
- [RULE 22] only Kaliya works end-to-end | no non-Kaliya verification | pipeline not general

ORDER-PROBLEMS:
- [RULE 7] colour work ran before T3/T4 (wizard + expert-tool) verified | should wait for T3/T4 gate
- [RULE 6] agent instructions sent before Super VL + Xing review | should wait for review finish + triage + re-review (RULE 5)
- [RULE 5] fixes applied before second review of fixed files | should wait for second review pass
- [RULE 19] Stage 2 (bible) ran without STYLE-01/STYLE-02 gate | should wait for style_pack_errors=0 + swatch check
- [RULE 13] style chooser UI review (ASCII) ran before style chooser built + simplification verified | should wait for those

ARCH-CHANGES:
- [RULE 1] add NOW block (≤8 lines) at top of PROJECT_LOG.md; overwrite after every agent finish/checklist tick
- [RULE 1] enforce LIVE LOG line format + max 200 chars; FAIL lines include cause + next; OWNER lines quote decision
- [RULE 2] checklist tick only when done AND verified; log the tick
- [RULE 3] agent brief template: must include "append lines in blot.md format to PROJECT_LOG.md after every step" + file ownership
- [RULE 4,11] hard ban: no Colab, no renders, no ElevenLabs, no Opus, no paid calls until owner lifts
- [RULE 5] mandatory second review (Super VL + Xing) after every fix round; repeat until zero HIGH
- [RULE 6] gate: Super VL + Xing review every prompt/instruction file before send; log review start/finish/send
- [RULE 7] gate: colour work starts ONLY after T3/T4 verified; never parallel with style.css/index.html owner
- [RULE 8] review cap: 1 pass + 1 fix check; round with no HIGH ends review
- [RULE 9] exit gate: UI task not done until browser test at 375/1280px in EN+MR + independent cold test (research/UI_COLD_TEST_*.md) with no HIGH
- [RULE 10] single log at D:\aai work\anime_studio\PROJECT_LOG.md; worktree copies read-only; sync blot.md on every rule change; backfill gaps with BACKFILL lines
- [RULE 12] reviewers = Nemotron 3.5 Super VL + Xing (OpenRouter free); runner research/_run_uifinal_reviews.py
- [RULE 13] core/core.json default_style_pack = deva_neon; writer/UI read from there; API GET /api/styles, POST /api/story/<slug>/style
- [RULE 14] heavy outputs → Google Drive folder; set flow_outputs/render outputs there; move finished files off D: when Drive reachable
- [RULE 15] stall watchdog: agent with no log line 20 min → FAIL line + replace (Sonnet high for big UI files); brief demands log line every 5 min
- [RULE 16] write_pack.py --web for all models; free models get WEB_NOTES.md (Haiku low effort, web search) per story; SOURCE.md remains authority
- [RULE 17] atomic step: every change → PROJECT_LOG line + blot.md update (both copies) in same turn
- [RULE 18] UI rule: no folds/hidden/hash-only/hover for needed facts; story choice always top; locked steps visible with reason; only raw tech in fold
- [RULE 19] Stage 2 gate: STYLE-01/STYLE-02 (style_pack_errors); off-style bible fails → repair call; pre-image swatch check vs pack; new look field → _look_rules + test
- [RULE 20] post-scripted-edit checks: grep -c $'\x08\x0c', ast.parse, node --check; prefer Edit tool for escapes
- [RULE 21] per-story flow folder flow_outputs/anime_<slug>; packet completeness test ui/test_packet_and_roots.py
- [RULE 22] gate: a non-Kaliya story must pass end-to-end before pipeline considered general

## blot.md rules part 2/4
FAILED after 3 tries: OK 200

## blot.md rules part 3/4
PROBLEMS:
- [RULE 37] C: drive hit 0 GB free (Claude temp folder) causing command failures | cache not cleaned, heavy output not redirected to D: | commands began to fail
- [RULE 38] Batch 1 (32 clips) had 19 clips over slot, up to 2.6× length | words-per-second estimation used instead of real measurement | 19 oversized clips; 52 credits wasted on pilot where ElevenLabs speed 1.15 had no effect
- [RULE 39] Using approval_sheet csv as text baseline regressed 8 lines | baseline should be shots.json but older csv used | 8 lines regressed
- [RULE 40] Render S009 failed 3× | external download (chumpy-0.71) returned HTTP 504 not checked before paid Colab session | 3 failed paid renders
- [RULE 42] RULE 39 sized voice windows to whole clip (6.6–10.1 s) but editorial cuts are shorter (6,5,7,8,8,7,7,8,8,6 = 70 s), causing 14 of 54 lines to overflow | voice windows sized to clip length instead of editorial duration | 8 lines rewritten shorter and regenerated

## blot.md rules part 4/4
**PROBLEMS**
- [Rule 46 amend] FINAL_TEXT_v2.json windows wrong for 14/54 lines (permission windows used instead of real speech windows) | root cause: scored against permission windows not vo_tracks_report

## MISTAKES_AND_LESSONS part 1/3
PROBLEMS:
- [C1] T0 run lost 6 clips: results folder missing locally, final download failed, VM stopped | clips fetched only at end, folder never created, download untested | 1 full G4 session + 1 A100 re-render
- [C2] A100 re-render failed: HF 429 on model download, hang at "Preparing Models" | no HF token, no retry, unproven GPU chosen | 1 A100 session, 0 clips
- [C3] Attempt 1: 19.7 MB script hung `colab exec -f`, never reached GPU | no proof script started, size limit unknown | 1.68 units (13 min G4)
- [C4] Attempt 2: same hang with 11.3 MB script | size fix guessed, not tested | 0.57 units
- [C5] Attempt 3: G4 session killed 2 min into install (owner closed wrong notebook), local exec hung | no "which session is whose" rule | ~0.3–0.9 units
- [C6] Attempt 5: all shots failed in 10s (rc=1): blank line in H3 prompt read as second generation | prompt never test-run on GPU before batch; T0 prompts had single line breaks only | ~0.9 units, 15 min
- [C7] Fetch split `FILES.txt` on spaces (names contain spaces), downloaded garbage, didn't stop session | untested with real filenames | extra billed minutes
- [C8] Opus writer stage 2: CLI `--output-format json` kept only last turn, lost first 90% | json joins nothing | 2.62 USD
- [C9] Opus repair rewrote 3e1 stage as 11 shots, failed validators | repair prompt allowed full rewrite | 1 Opus call, failed stage
- [C10] Claude weekly limit hit mid-pipeline, blocked Opus/CLI reviewers for days | all heavy writer work on one sub, no budget watch | days of blocked work
- [F1] Keyframes passed reviewer/thumbnails but full-size revealed defects (letters in sparks, wink, cropped sages, wrong crowns) | reviewer advisory; thumbnails hide defects | many hrs, ~150 Flow submits
- [F2] A/B keyframes generated separately, disagree (8A standing vs 8B seated, 2A/2B arms) → video invents transition | A/B treated as "pick better" not start/end frames | many hrs, ~150 Flow submits
- [F3] Owner misunderstanding: "A and B are two options" vs start/end frames | not explained in packet/UI | rework rounds
- [F4] Repeated long-prompt regenerations (1A: 5, 6A/6B: 8 submits) instead of single change-list on reference | no rework rule | many hrs, ~150 Flow submits
- [F5] `@` chip picker showed stale OLD- tiles; agents picked wrong, renames silently failed half the time | duplicated/stale names, UI quirks | agent stops, wrong picks
- [F6] Tab cap ~9; finished agents left tabs open → download agents couldn't start; agent without `tabId` renamed whole project; closed tab in use | no tab discipline | project rename, blocked agents
- [F7] 2K download: 4 Haiku agents clicked x=615 not x=668 for 20+ min → null captures | coordinate clicks without screenshot | 20+ min agent time
- [F8] Flow project signed out; 3 agents started/stopped, reported "done"/"blocked" silently | no sign-in check before launch | silent failures
- [F9] Edit IDs in notes (c989ad77, 89444d2c) didn't match gallery → agent lost time searching | IDs from partial notes | agent time
- [F10] Watermark detector missed sparkle on 4/20 (bright/gold backgrounds); 6A had baked-in ghost star from edit ref | threshold tuned on dark; edits copy watermark | missed detections, ghost artifacts
- [F11] Handoff note said A100, log said G4 → owner/assistant argued from wrong note | memory from plans, not run log | confusion, wasted discussion
- [P1] Python heredocs turned `\n` in strings to real line breaks (≥8 times) | broken files caught late | wasted rounds
- [P2] Shell wrapper hid 2 failing Gate D tests → bad push (ce74e37) | tests trusted through wrapper | bad push
- [P3] Log lines for steps that didn't happen (fake "applied fixes", DONE for retired tiles) | wrong state believed | wrong state
- [P4] Kill by command pattern matched own shell (twice) → exit 255, next steps skipped | lost min, session left running | lost min
- [P5] Reviewers: Nemotron empty at 30k tokens; Xing only thoughts; OpenRouter 429 when parallel | hrs of review time | hrs
- [P6] Pipeline hard-wired to first story (Kaliya): folders, `LEAP-*`, same chip name, rejected route, no V4 GPU path | 2 audits, 44 HIGH gaps closed late | 2 full audits
- [P7] Sound-cue rule SX-01 (7 action sentences need sound word) appeared only in render controller after authoring → 6/10 shots "not ready" | authoring ran twice (stale fields) | authoring ran twice
- [P8] Dry-run only prints commands; no real one-shot test before 10-shot batch | 4 failed starts | 4 failed starts
- [P9] Agent briefs/reports trusted: sign-in blocks, wrong tab, fake "done", "can't open tile" | repeated reruns | repeated reruns
- [P10] Owner rules changed mid-task (send clips → don't; Haiku low→high; Pro reworks only; stop) not always obeyed first | wasted calls/sends | wasted calls/sends

ORDER-PROBLEMS:
- Authoring ran before `render_controller --dry-run` (sound-cue validation) → 6/10 shots not ready [P7]
- Full 10-shot batch rendered before any one-shot real test on GPU → 4 failed starts [P8, Rule 3]
- Prompt batch sent to GPU before single prompt test-run on GPU → blank-line failure [C6]
- Clips fetched only at run end (folder missing, download failed) instead of per-shot during run → lost 6 clips [C1, R29]
- A and B keyframes generated as independent options instead of B as edit of A → mismatched frames [F2, N4]
- Script uploaded without proof it starts (size, 180s `/content/out` check) → hung sessions [C3, C4, R28]
- Fetch after run without stopping session → extra billing [C7]
- Opus writer used `--output-format json` (loses turns) instead of stream-json + join_stream → lost 90% answer [C8, R23]
- Repair prompt allowed full rewrite instead of targeted diff → validator failure [C9]
- Pipeline built for one story, reused for next without per-story dry-run → 44 HIGH gaps [P6, R21, R22]

ARCH-CHANGES:
- Add `fetch_ready` stage: save each clip to PC the minute its shot ends; create folders before use [R29]
- Add GPU validation gate: one-shot real test (`--ids SHOT-001`) must pass before full batch [Rule 3, P8]
- Add script-start proof gate: verify `/content/out` exists within 180s of `--go`, else stop session [R28]
- Change Opus writer contract: require `stream-json` + `join_stream`, check `num_turns` [R23]
- Add full-size image review gate: coordinator opens every kept keyframe at 100% before accept [R25, F1]
- Change keyframe generation: B frame produced as edit of A (single reference + change list); pair review side-by-side [N4, R25, F2]
- Add tab discipline contract: one tab per agent, `tabId` on every action, close only finished agents' tabs [R26, F6]
- Add screenshot-before-click requirement for all UI automation (record ref in `Satvik notes refer.md`) [R30, F7]
- Add sign-in check gate before launching any Flow agents [F8]
- Add tile matching by exact prompt+title (not IDs) [F9]
- Add watermark detection with anchor fallback (`stamps_or_anchor`), check all corners, manual ghost-star removal [F10]
- Add run-log verification gate: GPU type from `gpu.csv` + `colab new` lines only [F11]
- Add test-reading gate: read test output directly, never through wrapper [P2]
- Add per-story folder structure + end-to-end dry-run for each new story [R21, R22, P6]
- Add `render_controller --dry-run` gate immediately after writer, before authoring [P7]
- Add prompt builder: collapse blank lines, raise if any remain; test on GPU [R30, C6]
- Change `FILES.txt` to one path per line [C7]
- Add targeted repair contract: diff

## MISTAKES_AND_LESSONS part 2/3
FAILED after 3 tries: OK 200

## MISTAKES_AND_LESSONS part 3/3
PROBLEMS:
- W6: two code trees drifted (anime_studio vs anime_studio_merge); compile mixed them | fixes split across trees, no sync before fix | fixes lost if not synced
- W7: keyframes made without checking shot script; 009 script says Brahma rises but keyframes show seated; 007/009 prompts miss sages/Shiva; 007A shows full draw vs script start | no verification against per-second directives before approval | not stated
- W8: picture reviewer (Super VL) wrong: claimed two attendants + Sandhya facing Kamadeva in 007B; actual has three sages + Sandhya facing viewer | reviewer not verified at full size | not stated
- W9: converter (v4_to_h3.py:153) still emits "with <cue>" glue; every shot prompt reads "with a veil snaps" | glue not fixed at source with test in live tree | not stated
- W10: three paid GPU sessions wasted on chumpy-0.71 HTTP 504 | no pre-flight curl check of external download URLs | 0.58 units, 3 sessions, ~25 min
- W11: runner fetches only timeline.txt and gpu.csv, not setup.log; first failure showed only "exit 1" | setup.log not fetched before session stop | not stated
- W12: blind pip retry after first 504 without diagnosing cause; 2nd/3rd attempts only confirmed persistence | retry before root cause analysis | not stated (wasted sessions implied)
- W14: python heredoc turned escaped newline into real line break in test file (9th occurrence) | heredoc used for text with backslashes | caught by ast.parse
- W15: Hugging Face token pasted in chat; now in chat history and tool call | secret not saved to secrets/ and sent via stdin | not stated (security risk)
- W16: failed 'colab new' left unnamed G4 session billing 10 units/hr; CLI couldn't stop (no state record) | no immediate 'colab sessions'/'colab usage' check after failure | ~1.16 units, 25 min attention
- W17: runner didn't stop after RESULT.json=ALL DONE; polled timeline.txt in loop, G4 billed 10 units/hr until manual stop ~10 min later | no auto-stop logic when ALL DONE and clips home | ~1.67 units (10 min at 10 units/hr)
- W18: three setup failures hid behind each other (GitHub 504, colab connection drop, upload websocket drop); each fix found only by running | no pre-flight validation of all steps on real VM | 6 failed paid attempts before attempt 7 passed
- W19: voice windows sized to rendered clip length (6.6–10.1s) not editorial length (5–8s); 14/54 lines overran cut up to 1.46s; reported "54/54 fit" | used clip timing instead of assembler's editorial plan (timing_and_lattice.trim_in/out, editorial_duration_sec) | rework: rule 42, 8 shorter lines, build_vo_tracks.py
- W20: Gate D reported script-level retention failures (narration coverage 86% vs 90%, 27 vs 38 words, dead air 1.5s); waived only by owner order with codes in report | findings about script not build; waiver process informal | not stated

ORDER-PROBLEMS:
- W19: voice generation (audio window sizing) ran using rendered clip length; should have waited for assembler's editorial timing plan (timing_and_lattice.trim_in/out, editorial_duration_sec)
- W7: keyframe generation ran before shot script verification against per-second directives
- W10: paid GPU sessions started before free curl checks on all external download URLs
- W12: pip retry ran before root cause analysis of 504 error
- W16: after failed 'colab new', continued without checking 'colab sessions'/'colab usage' for orphaned VM
- W17: runner continued polling after RESULT.json=ALL DONE and clips home; should have stopped immediately
- W18: setup steps run on VM without prior proof of each step via free checks (URL, sed requirements, wheel hash)
- W6: code fix attempted before syncing two drifted code trees
- W9: converter used with "with <cue>" glue before fixing at source with test in live tree
- W11: session stopped before fetching setup.log (error text lost)
- W14: heredoc used for text with backslashes before using Edit tool
- W15: secret pasted in chat before saving to secrets/ and sending via stdin
- W13: reel 1 production started before fixing known gaps (chumpy wheel, code tree, converter glue, etc.) — owner decision but order dependency exists

ARCH-CHANGES:
- W6: add gate "code tree sync verified" before any code/prompt fix; designate single live tree
- W7: add stage "picture review against per-second directives" before image approval; mandatory keyframe-vs-script check
- W8: add verification step: each picture claim verified at full size (F1, Q8) before acceptance
- W9: remove "with <cue>" glue from converter (v4_to_h3.py:153) at source; add regression test in live tree
- W10: add pre-flight gate "free URL check" (curl all external download URLs: requirements, model files, git clone) before any paid session
- W11: runner must fetch setup.log before session stop, or setup must write all learnings to timeline.txt (sh_retry writes log tail)
- W12: add gate "root cause found (free) before retry" after any failed paid start
- W13: maintain gap registry with owner sign-off for parked items
- W14: enforce rule: for any text with backslash, use Edit tool only, never heredoc
- W15: secrets protocol: save to secrets/ once, never echo, send to VM via stdin only, request owner rotation after job
- W16: mandatory post-failure check: after ANY failed 'colab new', runner and waiter must run 'colab sessions' and 'colab usage' immediately; terminate stray G4 via browser or owner
- W17: runner auto-stop: when RESULT.json=ALL DONE and all clips home, fetch logs once and terminate session immediately
- W18: add pre-flight validation stage: prove every setup step on real VM via free checks (URL, sed requirements line, wheel hash) before paid run
- W19: add gate "timing basis confirmed from assembler" (timing_and_lattice.trim_in/out, editorial_duration_sec) before voice generation; add gate "vo_fit_check (Gate D)" before reporting "fits"
- W20: formalize waiver process: Gate D findings are information; waiver only by owner order, specific codes written in report, never silent

## PROJECT_LOG decisions/fails/owner lines part 1/12
PROBLEMS:
- [11-07 01:47 OWNER] voices generated after video render; no voice clips supplied | wrong step order (video before audio) | extra 'editorial timeline' repair step needed (implied)
- [11-07 02:00 GAP] checklist item 2.5 open: V4-to-H3 converter missing | not implemented | blocks H3 pipeline completion
- [11-07 03:46 W1 FAIL] test_stage_1_data_carries_the_selected_languages fails after gate merge | LANG-03 from writer fallback | test failure, investigation time
- [11-07 04:16 usage limit] multiple UI bugs: server.py record_spend before _start succeeds; read_pack episode sort TypeError (key str); pipeline.py total_seconds only sec>0; pipeline.js stale pack on Save story (line 723), overlapping polls/stale loadDetail | race conditions, incorrect guards, state staleness | session stopped, pending fixes
- [11-07 04:57 B1 FAIL] core suite collection blocked by other workers' test_pack_rules.py, test_cvd.py (missing modules) | missing modules in shared test files | 3×60s wait, blocked run
- [11-07 04:57 B4a FAIL] core suite collection errors in test_lut.py, test_make_lut.py, test_cvd.py, test_pack_rules.py (other workers' files) | missing modules in other workers' files | collection failure
- [11-07 04:57 B5 FAIL] core suite 2 collection errors (test_pack_rules, test_timeline: core modules missing, other worker) | missing core modules from other worker | 60s wait
- [11-07 04:59 B8a FAIL] core/tests/test_retention_report.py ImportError retention_report missing | missing module in other agent's file | not fixed, blocks suite
- [11-07 08:25 A25 FAIL] core/tests/test_convert_deva_h3.py linter 15 ERRORs (KF-02×8, SD-01×2, CM-01×1, PR-05×4) | template/registry content errors | no commit
- [11-07 08:28 T-DIR FAIL] stray cat hung 120s, task stopped | shell command issue | 120s lost
- [11-07 08:30 flash_check] flashes = ceil(transitions/2); 8 alternating frames = 3 flashes (not refused) vs owner acceptance 4-flash refusal | spec line 650 interpretation mismatch | owner may revert

ORDER-PROBLEMS:
- video render ran before voice generation (11-07 01:47: "voices after render; no voice clips supplied") — should wait for approved audio clips / voice_map + anchor clip
- h3_fields implementation proceeded before research gate (11-07 02:29: owner ordered "research git history 3-5 days + repos for the proven way, conclude, fix") — should wait for research conclusion
- UI server.py record_spend called before _start succeeds (11-07 04:16) — should wait for _start success
- pipeline.js Save story triggers stale pack load (11-07 04:16: pipeline.js:723) — should wait for fresh pack fetch / invalidate cache on save

ARCH-CHANGES:
- add audio-first gate: require approved voice clips (voice_map + anchor from first approved H3 clip) before any video render; hand off audio manifest (duration per shot) to render stage
- add checklist gate for 2.5: V4-to-H3 converter must pass lint/repair (e2e_sample pattern) before H3 compile stage
- add research gate for h3_fields: deterministic tier derivation + separate model-authoring step with lint/repair + report must be approved before writer/converter work
- fix UI contract: server.py record_spend only after _start succeeds; read_pack episode sort handle string keys; pipeline.py total_seconds guard sec>0; pipeline.js invalidate pack cache on Save story, debounce polls
- add test-collection health check: verify all worker test modules import before suite run (fail fast on missing modules)
- clarify flash_check spec: make flash threshold configurable or align formula to owner's 4-flash refusal (spec line 650)

## PROJECT_LOG decisions/fails/owner lines part 2/12
PROBLEMS:
- [11-07 08:39 FAIL] dots attempt 1 empty (token budget) | token budget exhausted | retry at 48000
- [11-07 08:49 FAIL] unmocked call_path hit NVIDIA endpoint with fake model (HTTP 404, no paid) | probes not mocking external calls | wasted API call, 404
- [11-07 09:58 DECISION] OPEN: gate_d step keys from own writer, episode str/int, story_links.check contract | contract ambiguities | blocking r4c_director dots
- [11-07 10:08 DECISION] 3 review rounds reached; round-3 findings triaged, not fixed (no 4th review allowed) | hard round limit | unclean report, REAL items unfixed
- [11-07 10:27 DECISION] NOW block not refreshed (write denied by permission) | permission denied on write | stale NOW block
- [11-07 10:33 FAIL] r3 test pins PLAN-01 for captions_by_lang string; reverted that guard | test pinning outdated guard | test failure
- [11-07 12:29 DECISION] stat race REAL low | race condition in stat | low severity but real
- [11-07 12:48 DECISION] Dots r5b export episode str vs int: OPEN (same contract as Q-R4-14) | contract ambiguity str vs int | blocking
- [11-07 12:57 FAIL] one transient failure in first final run (581 pass, 1 fail); not reproduced in 3 reruns | flaky test | wasted reruns
- [11-07 13:20 FAIL] core/tests/test_caption_text.py collection error blocks full core run | collection error in test file | blocks test suite
- [11-07 13:20 FAIL] PROJECT_LOG.md correction on test counts (325 vs 331) | inaccurate reporting | misleading metrics
- [11-07 16:02 DECISION] Gate D's own -14 LUFS target conflicts with -16 LUFS standard | duplicate loudness config | inconsistency
- [11-07 16:12 FAIL] push ce74e37 went out with 2 failing Gate D tests; wrapper hid failure; cue-layer hardening coerced malformed blocks silently | test wrapper hiding failures, silent coercion | broken code pushed
- [11-07 17:03 UI-REV FAIL] 8 selectors target removed #wiz-panels (dead CSS) | CSS for removed element | dead code
- [11-07 17:04 UI-REV FAIL] Gate A Approve enabled while stale-server banner says restart first | UI state mismatch | safety gap
- [11-07 17:05 UI-REV FAIL] Images Shots tab shows [object Object] in Q1-Q6 cells (fillReview String of object) | object not stringified | UI display bug
- [11-07 17:07 UI-REV FAIL] phone Advanced toggle click did not expand (advancedOpen=false after click) | click handler not updating state | mobile UX broken
- [11-07 17:48 DECISION] write_pack_claude kept in CLAUDE_COMMANDS not COMMANDS; test_ui test_1 pins COMMANDS | command categorization mismatch | test failure
- [11-07 17:48 DECISION] 4 plan needles had closing quote not in JS (/api/images?, /api/review?, /api/export?, /log?tail=) | string matching error in test | test false negatives

ORDER-PROBLEMS:
- [11-07 16:12 FAIL] push executed before Gate D tests passed; wrapper hid failures | should wait for clean test run
- [11-07 17:04 UI-REV] Video section calls loadColab (Colab CLI) but blot RULE 4 forbids | video code runs before Colab-free implementation
- [11-07 13:20 FAIL] caption_text tests run before collection error fixed | blocks entire core test suite
- [11-07 17:48 DECISION] test_ui test_1 pins COMMANDS before write_pack_claude categorization finalized | test needs retarget after command move
- [11-07 10:27 DECISION] commit attempted before write permission granted | NOW block stale

ARCH-CHANGES:
- [11-07 08:49] add mandatory mocking for all external endpoints in probes (NVIDIA, etc.)
- [11-07 10:08] add escalation path for unfixed REAL items when review rounds exhausted (e.g., owner gate, BF agent auto-assign)
- [11-07 10:27] make NOW block refresh non-blocking or add pre-write permission check
- [11-07 12:29] add atomic _size helper for file stat to eliminate race
- [11-07 13:17] formalize caption modules: core/caption_text.py + core/caption_export.py built by agents, lead integrates into core/captions.py with defined interface
- [11-07 14:14] establish recurring pipeline audit gate (docs/PIPELINE_AUDIT_<date>.md) with evidence from both trees
- [11-07 16:02] centralize loudness config in core.json as single source of truth for post.py and Gate D; remove Gate D local target
- [11-07 16:12] change cue-layer hardening from silent coercion to explicit ValueError on malformed blocks
- [11-07 17:04] enforce blot RULE 4 at architecture level: video path must not call Colab CLI (static analysis or runtime guard)
- [11-07 17:17] implement parity testing framework: inventory checklist + parity tests + tasks acceptance = inventory rows ticked
- [11-07 17:35] use PARITY_BUILT env var for parity test configuration instead of editing test_parity.py
- [11-07 17:56] formalize parallel agent execution: file ownership (disjoint files), locked merge helper for shared assets (ui/i18n_merge.py), port isolation (8767/8768), PARITY_BUILT env

## PROJECT_LOG decisions/fails/owner lines part 3/12
PROBLEMS:
- [17:59] research/UI_PARALLEL_DISPATCH_2026-11-07.md write blocked by worktree path guard | file missing → both reviewer runs failed (110 chars) | rewrite file + re-run reviewers
- [18:47] research/_prompt_colour_research.md edit script failed (backslash escapes) | no change made despite log claiming fixes | redo edit
- [19:12] research/COLOUR_V2_REVIEW_HAIKU_2026-11-07.md write blocked by worktree path guard | file not written, review delivered as handback text only | review incomplete
- [19:27] ui/static key-check command started Python REPL by mistake | hung (background bmp71oyjb) | stopped, redo as script file
- [19:27] ui background pytest left no output and no process | rerun with output to scratchpad file | time lost
- [19:48] ui/static/tokens.css ignored by .gitignore '*token*' line 6 | not changed (outside scope) | lead must add negation or force-add
- [21:00] UI bug: 'Save the languages first (step 1).' error always shows on step 2 when story finished but languages none ticked | blocks step 2 progression | user cannot proceed
- [21:52] shell stray 'cat >> /dev/null' waited on stdin | hung | TaskStop, nothing else lost
- [21:56] coderW and coderE stopped by user around Assay interruption | cannot resume, work cancelled | partial uncommitted edits remain

ORDER-PROBLEMS:
- [19:12] CV review of colour v2 ran before v2 file existed (write blocked by worktree guard) | should have waited for file write to complete
- [19:07] UI plan finalized without covering brief requirements (voice choice, per-language caption/voice state, hook text, plate coverage, graded flag) | should have incorporated brief before plan lock
- [19:11] implementation waiting for T3/T4 verify + CV review of v2 (per blot rule 7) but v2 file not yet written | write v2 must precede CV review
- [21:00] step 2 validation triggers before step 1 languages saved (error shows when languages none ticked) | step 2 should be gated behind step 1 completion
- [21:56] Assay interruption caused user to stop coderW/coderE before they finished | gaps should be cleared before Assay (per 21:35 owner instruction)
- [22:01] writers for Ashtavakra + Kalika started in parallel (22:01 decision) but owner at 22:05 said only Kalika Puran | Ashtavakra writer started prematurely
- [22:07] Nemotron Kalika run started (21:38) but owner at 22:07 switched to Claude Opus high | writer model changed after run started

ARCH-CHANGES:
- Enforce gate: reviewer review before agent dispatch (blot rules, 17:56)
- Add gate: lead checks git diff of en/mr after each merge (deferred 18:54)
- Add review gate: Haiku medium reviewers + free Super VL/Dots pass on final prompt before dispatch (18:55)
- Add UI addendum stage T6 after pipeline items for missing brief items (voice choice, caption/voice state, hook, plate coverage, graded flag) (19:07)
- Enforce order: write colour v2 → CV review v2 → T3/T4 verify → implementation (blot rule 7, 19:11)
- Fix .gitignore to allow tokens.css (negate '*token*' or force-add) (19:48)
- Add validation gate: step 2 (story) only enabled after step 1 (languages) saved (21:00 bug)
- Add rule: update NOW block in blot.md after every agent finish (21:23)
- Add Assay as final UI test stage, gated after all gaps cleared and style additions done (21:35, 21:50)
- Add style selection architecture: (A) default deva_neon in director/core, (B) /api/styles + set-style endpoint + wizard step-1 chooser (21:46)
- Merge coder S into W2 (frontend) and E2 (backend) to eliminate a stage (22:01)
- Add writer model selection per story with explicit owner override (Opus for Kalika, Super VL for others) (22:07)

## PROJECT_LOG decisions/fails/owner lines part 4/12
**PROBLEMS:**
- [11-07 22:13] Kalika parts 1+2 mixed stories | owner sent two separate YouTube links with mixed narratives | –
- [11-07 22:26] Google Drive connector missing in session | connectors list shows only Claude Docs, Kaggle, AbletonMCP, Desktop Commander, research servers | –
- [11-07 22:38] coderW2/coderE2 agents stalled/disappeared | no log lines since 22:04/22:05, no file changes since 22:05, agents no longer exist | –
- [11-07 22:51] Kalika opus writer v2_parts12 stage 2 failed after repair | validator regex rejects 'plain neutral grey backdrop' (BIBLE-06) | –
- [11-07 23:06] npm view assay-ui 404 | package not on npm, identity unknown | –
- [11-07 23:10] No visible UI way to choose/continue unfinished stories | owner disappointed, Assay paused | –
- [11-07 23:11] UI audit needed for 60-year-old user | hidden steps suspected | –
- [11-07 23:13] Owner asks if image generation/watermark removal elements dropped | pipeline elements possibly missing | –
- [11-07 23:29] assay run 1: server served only '/' (404) for /index.html | not a real pass | –
- [11-07 23:34] assay run 2: venv lacked Pillow → /api/images errors | setup issue, not UI | –
- [11-07 23:34] assay run 2 crashed printing Marathi to cp1252 console | no report generated | –
- [11-07 23:56] Kalika v3_web writer stopped at stage 3e4 after 1 repair | S55-6 Virini screen left→right SHOT-040→041 unmarked (validator correct) | –
- [11-08 01:07] Kalika v4 stage 2 answer began mid-JSON (18.5k of bible) | CLI 'result' keeps only text after last tool call; writer stopped during repair call | ~25 USD Opus projected more |
- [11-08 01:10] auditB: queue_add/queue_accept/neighbour/review w/o story arg; pack_to_spec outputs_root template lacks anime_ prefix | code gaps | –
- [11-08 01:10] auditB: read_images uses story_links root not flow_root; api.review uses Kaliya; sheet job title vs chip mismatch | wiring errors | –
- [11-08 01:10] auditB: download_queue.py collect→'final' for sheets; palette gate not wired | missing wiring | –
- [11-08 01:11] auditB: bridge_flow_to_h3.py PATTERN LEAP-* ; server.py b_bridge no --pattern | HIGH | –
- [11-08 01:11] auditC: wizard Prepare sends shots.json to h3_prepare, b_h3 refuses it; no convert step writes H3 story; export G12 'not built' | pipeline gap | –
- [11-08 01:13] auditC: converter shot has no metadata.look/audio_and_dialogue_track → post._shot_facts 'missing metadata.look'; nothing writes episode.json or clip.mp4; step9_qc.json never written; images_dir/results_dir never set by wizard | multiple missing outputs | –
- [11-08 01:14] auditB: images_dir never set by wizard (only API); Gate B finals counts *__final.png incl sheets | HIGH | –
- [11-08 01:14] auditC: run_t0_parallel playable() 4.5-6.5s; run_kaggle.build KeyError 'mode' on V4 rows; style_bible.load(deva_neon) FileNotFound; nothing writes asset_manifest/fallback_history; post vs gate_d output paths differ | multiple failures | –
- [11-08 01:15] auditB: pipeline.js findJobsFile ids SHOT-001 vs jobs SHOT-001A; server.py packet() 1..60 cap; queue_add/accept/review/neighbour no story arg PROVED | ID mismatch + caps + missing args | –
- [11-08 01:15] auditB: pack_to_spec/bible_to_sheet_jobs written for old bible schema; V4 bible has style_lock, card_prompt, no age/heads/layers | schema drift | –
- [11-08 01:16] auditC: writer V4 rows have route=Ref2VA → run_kaggle ValueError 'route must be one of pika6,sing4,sing8'; v4_to_h3._source reads only stage_1*.json with output_languages (writer stage_1_raw.json is CLI envelope; story_plan.json unread) | route mismatch + wrong source read | –
- [11-08 01:17] auditB: shared Flow project: STYLE_CHIP_SHEET__v01 identical chip name for every story; build_spec/jobs cannot rebuild after accepted flags (no overwrite) | collision + no rebuild | –
- [11-08 02:18] director/test_writer_v4.py:496 rule 20 slip (real newlines in string, SyntaxError) | scripted edit bug | –
- [11-08 02:40] scripted edit of core/timeline.py escape slip (newline in string) caught by assert | same class as 23:1x newline slip | –
- [11-08 02:41] core/retention_rules.py R2/R5 inverted vs spec (COLOUR_AUDIT.md) | every V4 row failed | –

**ORDER-PROBLEMS:**
- [11-07 23:13] Owner asks where image generation/watermark removal are → answered: writer finish, plan check, Gate A, build jobs, Flow packet come BEFORE images | images step expected earlier but pipeline gates it after writer+Gate A |
- [11-08 01:11] wizard Prepare sends shots.json to h3_prepare → b_h3 refuses it (no convert step writes H3 story) | h3_prepare called before converter exists |
- [11-08 01:13] post.py expects metadata.look/audio_and_dialogue_track on shot → converter v4_to_h3._shot doesn't write them | post runs before converter produces required metadata |
- [11-08 01:14] Gate B counts *__final.png including sheets → images_dir never set by wizard (only API) | Gate B runs before images_dir is wired |
- [11-08 01:16] run_kaggle.build expects route in {pika6,sing4,sing8} → writer V4 emits route=Ref2VA | writer runs before route validation/contract |
- [11-08 01:16] v4_to_h3._source reads stage_1*.json (CLI envelope) → story_plan.json unread | converter reads wrong file before writer produces correct one |

**ARCH-CHANGES:**
- Add Gate A (owner approval) as mandatory gate after writer finish + plan check, before build jobs + Flow packet (per 23:17 answer)
- Add converter step that writes H3 story (episode.json) between wizard Prepare and h3_prepare (auditC 01:11)
- Wire images_dir/results_dir in wizard (not only API) so Gate B and post have correct paths (auditB 01:14, auditC 01:13)
- Add route validation/contract: writer V4 must emit only {pika6,sing4,sing8} or run_kaggle must accept Ref2VA (auditC 01:16)
- Make v4_to_h3._source read story_plan.json (not stage_1_raw.json CLI envelope) (auditC 01:16)
- Make pack_to_spec outputs_root include anime_ prefix (auditB 01:10)
- Make queue_add/queue_accept/neighbour/review require story arg (auditB 01:10, 01:15)
- Make download_queue.py collect sheets to correct stage (not 'final') and wire palette gate (auditB 01:10)
- Add --pattern flag to server.py b_bridge matching bridge_flow_to_h3.py LEAP-* (auditB 01:11)
- Make build_spec/jobs support overwrite/rebuild after accepted flags (auditB 01:17)
- Make STYLE_CHIP_SHEET unique per story (not identical v01 for all) (auditB 01:17)
- Add episode.json writer, step9_qc.json writer, clip.mp4 writer in post/export (auditC 01:13)
- Add G12 export implementation (auditC 01:11)
- Fix retention_rules.py R2/R5 to match COLOUR_AUDIT.md spec (02:41)
- Add scripted-edit guard: reject control chars (newline, backspace) in string literals (02:18, 02:32, 02:40)

## PROJECT_LOG decisions/fails/owner lines part 5/12
**PROBLEMS:**
- [11-08 03:03] gapfix R1 xing | HTTP 429 after 5 retries (both reviewers on one OpenRouter key simultaneously) | retry delayed until supervl finishes
- [11-08 06:23] Kalika writer stage 2 | parse_bible needs block last; answer = whole valid bible block + trailing note; repair retry claude exited 1 (stderr empty) | no new answer saved
- [11-08 06:24] Kalika writer stage 2 repair retry | claude API 429 usage_limit_reached: weekly limit hit (resets Nov 12 15:30 IST); same cause as earlier exit 1 | no Opus call possible until reset; writer stopped
- [11-08 06:37] Kalika writer 429 root cause | writer spawns claude CLI using satviksangamkar@gmail.com (Pro, org 651b7a3d) weekly limit used; app session runs on sangeetasangamkar@gmail.com (org 4df5dc07) with limit left | waiting for owner login (needs browser) to fix CLAUDE_CONFIG_DIR separation
- [11-08 10:33] Kalika writer run _10 | 3e1 failed after repair on 2 ML-08 flags, both checker false positives: (a) aai = mother valid Marathi listed as Hindi leak (b) standalone ne = Hindi ergative but was in MR_ONLY so Hindi lines read as Marathi | redo needed
- [11-08 10:37] Kalika writer run _12 | refuse_finished guard (PACK.md exists = pack finished, new call needs unfinished pack) | no model call, nothing spent
- [11-08 12:10] audit reel 1 gaps | (1) pack_to_spec refuses V4 shots (no set/cast/props/keyframes) (2) v4_to_h3 lint 73 errors incl. non-authored timing: dynamic split, MO-03, MO-01 7th second, SX-01 5/7; writer validator does not run them (3) no pre-voice speech-rate check, 20 lines >3.2 wps (4) pixel-frame vs editorial seconds 70.8 vs 70.0 (5) story gates self-graded, no source fidelity check (6) no styl | multiple pipeline gaps
- [11-08 13:57] Kalika reel 1 writer rerun | Opus repair rewrote 3e1 as 11 shots, ML-01/STIFF-01 errors, stage failed | originals restored, failed answer kept .repair_11shots_failed.bak
- [11-08 14:54] h3/h3_author.py --live | SHOT-001 failed 5 rounds: author lint counts missing boundary PNGs (KF-06, PR-00 route T2VA) which only exist after Gate B; shots 2-10 blocked | fixing author to ignore image-dependent codes
- [11-08 18:15] sheet_jobs.json | STOP before submit: ENV-MARKANDEYA-ASHRAM and ENV-BRAHMA-SABHA prompts say '9:16 vertical' but job aspect is 16:9 (brief: 16:9 plates) | pasted prompt cleared, nothing submitted
- [11-08 18:19] CHAR-SANDHYA | tile A first capture WRONG image (Markandeya from hidden strip image); moved to _wrong_capture_CHAR-SANDHYA_A | recaptured with visible-main-image filter
- [11-08 18:19] CHAR-SANDHYA | earlier B capture and A recapture were plain Sandhya sheet, not tile f962 (four-armed SANDHYA sheet) | recaptured f962 via elementFromPoint -> CHAR-SANDHYA__v01_B2.png; first A/B files set aside
- [11-08 18:21] MARKANDEYA | B has garbled label text (TRIMME FRAVE) and invented labels -> B not kept | retrying reviewer once
- [11-08 18:29] CHAR-SHIVA | first submit left no tile (prompt box showed 'Prompt must be provided'); reloaded, no Shiva tile | retyping prompt via keyboard
- [11-08 18:58] shots_progress.jsonl | SHOT-005A stopped before submit: chip name collisions (CHAR-BRAHMA, CHAR-KAMADEVA), ENV_BRAHMA_SABHA and STYLE_CHIP_SHEET not found | keyframe agent B stopped
- [11-08 18:58] SHOT-008A,008B | chip CHAR-SHIVA matches 2 rows (CHAR-SHIVA + OLD-CHAR-SHIVA-B); not submitted; per brief STOP and report | nothing submitted, no tiles renamed
- [11-08 18:59] SHOT-008A..010B (all 6) | @ picker: CHAR-BRAHMA, CHAR-KAMADEVA, CHAR-SHIVA each match 2 rows (exact + OLD-). Chip rule blocks all 6 jobs | nothing submitted, Tab-10 left open
- [11-08 18:59] SHOT-004A | @ picker shows no rows in narrow pane (typed @CHAR-BRAHMA, no menu); coordinator rule: exact-name match only | BLOCKED pending picker

**ORDER-PROBLEMS:**
- [11-08 14:54] h3_author lint runs on SHOT-001 counting missing boundary PNGs (KF-06, PR-00 route T2VA) which only exist after Gate B → author lint ran before Gate B assets exist
- [11-08 18:58] keyframe agents (B, C, A) attempt to pick chips (ENV_BRAHMA_SABHA__v01, STYLE_CHIP_SHEET__v01, CHAR-SHIVA, CHAR-BRAHMA, CHAR-KAMADEVA) before sheet renames saved / OLD- rows cleaned up → keyframe picking ran before sheet acceptance & rename verification complete
- [11-08 18:15] sheet prompts written with '9:16 vertical' while brief says 16:9 plates → prompt authoring ran before brief aspect-ratio contract enforced

**ARCH-CHANGES:**
- Add separate CLAUDE_CONFIG_DIR per account (app vs personal) so writer CLI uses correct org quota; gate writer launch on verified config dir
- Move author lint (h3_author.py) after Gate B asset delivery; add gate: "boundary PNGs present" before author lint runs
- Add sheet rename-verification gate: all accepted sheets must be renamed to __v01 and OLD- rows archived before keyframe agents start; keyframe agents read a manifest file listing exact chip names
- Enforce aspect-ratio contract at sheet_jobs.json creation: validate prompt aspect matches brief (16:9) before any agent submits
- Add pre-voice speech-rate check stage (max 3.2 wps) before video render; fail fast if lines exceed
- Add pixel-frame vs editorial seconds reconciliation gate (tolerance ±0.5s) before final render
- Replace self-graded story gates with source-fidelity checker (independent validator)
- Make refuse_finished guard configurable per-stage (allow re-entry with --force or versioned pack dirs)

## PROJECT_LOG decisions/fails/owner lines part 6/12
PROBLEMS:
- [11-08 19:00 keyframeC FAIL SHOT-008A] CHAR-SHIVA/BRAHMA/MANASA-PUTRAS chips not attaching in picker at 9:16 viewport; picker shows 0 rows | viewport-dependent picker UI (different panel at 9:16 vs desktop) breaks chip attachment flow | shots blocked, retries wasted
- [11-08 19:02 flow-keyframe-agentA FAIL SHOT-004A] @CHAR-BRAHMA typed, Down key, no picker rows at 1280x900 | same viewport picker bug | shot blocked
- [11-08 19:03 flow-keyframe-agentA FAIL SHOT-004A] clicking exact CHAR-BRAHMA row closes menu but no chip appears in prompt | picker row-click does not attach chip at this viewport | shot blocked
- [11-08 19:03 keyframeC FAIL SHOT-008A] 9:16 picker panel: row click closes without attaching; Add-to-prompt flow required | UI contract changes with aspect ratio | shot blocked, viewport reset needed
- [11-08 19:04 keyframe-agent-B FAIL shots_progress.jsonl] SHOT-005A chip attach not completed in wide @ picker; 005B-007B not started | picker attachment unreliable | cascade block on 3 shots
- [11-08 19:05 flow-keyframe-agentA FAIL SHOT-001A] tile B capture via JS data URL overflowed tool output (~262k chars); no files written | capture method exceeds tool output limit | tile lost, no review/rename
- [11-08 19:06 flow-keyframe-agentA FAIL SHOT-001A] fetch of flow-content img src fails (CORS); canvas tainted; no file written | cross-origin image fetch blocks canvas-to-file | tile lost, shot stopped
- [11-08 19:07 keyframeC FAIL SHOT-008A] second @ after a chip does not open picker (literal @ stays); clicking prompt line no help | composer state machine breaks after first chip | shot blocked on chip 2
- [11-08 19:09 keyframeC FAIL SHOT-008A] retry: chip2 @ still literal after ref click; aspect must be re-set | picker/composer not reset cleanly | shot blocked
- [11-08 19:09 flow-keyframe-agentA DECISION SHOT-001A] rename of tile A to SHOT-001A__v01 FAILED twice (title still old after reload) | rename flow (title input click, type, Done editing) not persisting | tile not renamed, retry-once rule triggered stop
- [11-08 19:19 keyframeC FAIL SHOT-008A] reviewer BLOCK A and B (advisory); both need regenerate; progress NEEDS_REVIEW | reviewer advisory blocks despite coordinator later overruling | rework cycle
- [11-08 19:27 keyframeC FAIL SHOT-008B] reviewer BLOCK A and B; not kept; NEEDS_REVIEW | same | rework cycle
- [11-08 19:37 AGENT-D DECISION ENV-MARKANDEYA-ASHRAM-v02] A BLOCK (no kusha mats, smoke off kunda) | asset missing required props | plate rejected
- [11-08 19:37 flow-keyframe-agentA FAIL SHOT-002A] regen1 A and B both BLOCK on Q2 (palm/gaze); not kept | prompt not enforcing pose constraints | regen loop
- [11-08 19:42 AGENT-D DECISION SHOT-007A] A NEEDS_REVIEW (reviewer UNSURE, own check PASS), B BLOCK | reviewer uncertainty stalls | shot pending
- [11-08 19:44 flow-keyframe-agentA FAIL ENV_MARKANDEYA_ASHRAM] new plate rename to ENV_MARKANDEYA_ASHRAM__v01 FAILED twice (title still 'Sacred fire pit...') | rename persistence bug | CHAR-KALI-v03 and SHOT-003A/B not started
- [11-08 19:48 H3 FAIL monitor bwiel7e68] exited early: ps grep matched nothing; v03 review still running | monitor process tracking broken | review orphaned
- [11-08 19:49 H3 FAIL review_shot.py v03] bg task exited code 1 after printing verdict (stdout complete) | review script crash on exit | review result lost
- [11-08 19:51 H1 DECISION CHAR-KALI__v03_B.png] expression row is grey pencil sketch (off cel style); weaker than A | style drift in generation | tile rejected
- [11-08 19:52 H3 FAIL review_shot.py v03] background run exit 1, no result | same script crash | coordinator had to accept on visual check
- [11-08 19:58 H3 OWNER coordinator] new job SHOT-005A/5B/6A/6B with new CHAR-KAMADEVA; judge existing 005A tiles, regen max 4 | dependency on new char chip not yet in picker | shots must wait for chip
- [11-08 19:59 H1 FAIL d012df26 rename] title still CHAR-KALI after 2 tries (Done editing clicked); batch navigate opened extra tab-22 | rename flow flaky, tab management side-effect | chip name not updated for downstream shots
- [11-08 20:00 H3 FAIL tab-22] my tab closed by something after submit click (not by me); submit status unknown | external tab closure breaks submit confirmation | unknown state
- [11-08 20:02 H2 DECISION SHOT-003A] r1 review BLOCK both (mala not held); submit 2 with regen sentence | prop (mala) missing in generation | regen needed
- [11-08 20:05 H2 DECISION SHOT-010A] KEEP A renamed SHOT-010A__v01 verified, B retired | success but only after manual verify | rename verification manual
- [11-08 20:15 me DECISION shots_progress.jsonl] board: DONE 4A 4B 5A 5B 7B 8A 10A; pending 1A/1B/2A/2B redo, 3A r2 verdict,3B,6A,6B,7A/9A rename,8B v03 verdict,9B,10B; old agents gone, relaunching Haiku high | massive rework backlog from cascading failures | high agent effort, timeline slip
- [11-08 20:20 me DECISION SHOT-003A v02_A] accepted at full size (kunda, 4 munis+sage, mala, dawn); rename SHOT-003A__v01, retire B | success after regen | rework cost

ORDER-PROBLEMS:
- SHOT-005A/5B/6A/6B generation started (11-08 19:58) before CHAR-KAMADEVA-v02 chip was verified in picker (CHAR-KAMADEVA-v02 accepted 11-08 19:27, but rename of v01/OLD to RETIRED-* and picker unambiguity not confirmed until later) | shots generated with stale/ambiguous char chip
- SHOT-001A/1B/2A/2B redo requested (11-08 19:59) before CHAR-KALI-v03 chip rename persisted (rename failed 11-08 20:00, still CHAR-KALI) | shots would use old chip name
- ENV_MARKANDEYA_ASHRAM__v01 rename failed twice (11-08 19:44) but SHOT-003A/B regeneration ordered (11-08 19:50) | shot regeneration would reference unrenamed plate
- SHOT-008A accepted (11-08 19:45) before reviewer advisory blocks (11-08 19:19, 19:27) were resolved | coordinator overruled reviewer but process order had review before accept
- SHOT-004A v03 review still running (11-08 19:49) but coordinator ordered keep best after review (11-08 19:51) | decision before review completion

ARCH-CHANGES:
- Add viewport-agnostic picker contract: chip attachment must work identically at 9:16 and desktop; gate keyframe start on picker smoke test at target aspect
- Add capture gateway stage: replace JS data-URL capture with server-side fetch + save (bypass CORS, size limit); gate post-process on file-on-disk verification
- Add rename persistence gate: after any rename (char, env, shot), require reload + title verify before downstream stages can read the name; block picker/chip resolution until verified
- Add chip-availability gate: before shot generation, assert required CHAR/ENV/PROP chips exist in picker with exact expected names; fail fast if missing
- Move reviewer advisory to non-blocking: reviewer writes NEEDS_REVIEW but coordinator can accept immediately; remove mandatory regen on advisory block
- Add review-script health monitor: watchdog that captures stdout/stderr on exit code !=0 and surfaces verdict; no silent loss
- Add tab/process isolation: each agent owns a dedicated browser context; submit confirmation recorded before tab close; external tab kills not allowed
- Add shot dependency graph: explicit DAG (char sheet -> chip rename verified -> env plate rename verified -> shot gen -> review -> rename -> done); scheduler enforces topological order

## PROJECT_LOG decisions/fails/owner lines part 7/12
PROBLEMS:
- [11-08 20:16 R1/R2/R3 FAIL] Flow pane signed out (project URL redirects to /about) | root cause: owner not signed in to Flow in built-in browser pane | cost: all 3 agents stopped, 0 jobs done, owner must sign in manually then relaunch R1-R3
- [11-08 20:37 R1 FAIL] review_shot.py cp1252 UnicodeEncodeError printing Devanagari reason | root cause: script default encoding cannot handle Devanagari | cost: rerun with PYTHONIOENCODING=utf-8 needed for 001A B
- [11-08 21:13 R5 FAIL] Flow gallery title SHOT-001A__v01 shows on edit 1f1d26c1 but keeper id is 8aa727e3 | root cause: alias/stale title in Flow UI | cost: verification needed before 2K download; risk of retiring wrong asset
- [11-08 21:19 R7 DECISION] R7 added "no pillars" sentence per misunderstood correction | root cause: agent acted on initial coordinator message before clarification arrived | cost: wasted submission, wrong direction (pillars belong to ENV_BRAHMA_SABHA)
- [11-08 21:22 me DECISION] Owner rejected SHOT-001A a200e328 after accepting at 20:50 | root cause: second full-size look revealed wink look, crown dominates, not eye close-up | cost: redo with 3 submits left, rename to RETIRED-SHOT-001A-v3
- [11-08 21:25 me OWNER] Model version mismatch: reworks must use Nano Banana PRO, agents were on 2.1 | root cause: no model-version gate for rework phase | cost: stop on any payment/upgrade prompt, must log model+credit cost
- [11-08 21:19 R5 FAIL] Edit route opens a200e328 for tile B click (duplicate titles) | root cause: dup titles in Flow gallery | cost: cannot open tile B at full size, judgment from gallery zoom only
- [11-08 20:23 R1 DECISION] Coordinator ids c989ad77/66571c66 not found in gallery for SHOT-003A | root cause: Flow gallery search by id failed | cost: manual content mapping required
- [11-08 20:25 R1 DECISION] SHOT-003B gallery tiles lack 'yajna kunda' | root cause: existing tiles not generated to exact job prompt | cost: fresh submit required
- [11-08 21:18 R7 DECISION] SHOT-006B attempt 1 both BLOCK (4 sages + pillars; Brahma left + pillars) | root cause: prompt/chips insufficient for composition | cost: submit 2 with stronger wording (no pillars, count six)

ORDER-PROBLEMS:
- Agents R1/R2/R3 launched keyframe generation before Flow sign-in verified (20:16) | should have waited for owner sign-in confirmation in pane
- R7 submitted SHOT-006B with "no pillars" before coordinator clarification that pillars are OK (21:19) | should have waited for correction acknowledgment
- Owner accepted SHOT-001A at 20:50 then rejected at 21:22 | acceptance gate should have required mandatory second full-size review before final accept
- R5 renamed keeper 8aa727e3 to RETIRED-SHOT-001A-v1 before verifying it matches gallery title (21:13) | should verify title/id reconciliation first

ARCH-CHANGES:
- Add pre-flight gate: verify Flow sign-in (project URL loads, not /about) before launching any agent jobs
- Add global encoding config: set PYTHONIOENCODING=utf-8 in review_shot.py and all helper scripts
- Add title/id reconciliation step: before any rename/retire, confirm Flow gallery title matches keeper id; log alias conflicts
- Add model-version gate: rework phase reads a "model.contract" file (e.g., Nano Banana PRO only); agents block on 2.1 or payment prompt
- Add coordinator-acknowledgment protocol: agents must receive explicit "correction acknowledged" before acting on new instructions
- Add double-review acceptance gate: owner must sign off on second full-size view before shot moves to DONE; first accept = "tentative"
- Add Flow gallery dedup check: before 2K download phase, scan for duplicate titles; resolve or flag for manual merge

## PROJECT_LOG decisions/fails/owner lines part 8/12
PROBLEMS:
- [21:42-21:55] download agents (D1-D4, L1-L4) fail to get browser tabs | tab cap (9 flow tabs) blocks all agents; no dedicated tab pool | 0/20 shots downloaded initially, ~15 min lost
- [21:44-21:55] 2K download capture fails repeatedly | window.__dl null, no blob, no network request; menu closes without toast | 10/20 shots filed after 40+ min; 3B,4A,4B,5A,5B,9A,10A,10B left for re-run
- [22:30] h3_author fails | Claude weekly usage limit (429) for opus AND sonnet; fallback to free NVIDIA model required | step delayed, Ultra run stopped mid-way (shots 1-5 authored)
- [23:21] render dry run: only 4/10 shots ready | SX-01 errors in shots 3,4,5,8,9,10; controller reports "no GPU backend wired" | render not viable
- [00:16] render kalika_reel1 fails on VM | run.py 19.7 MB never starts (/content empty after 13 min, kernel idle); local exec stuck sending; ~2 GPU units spent | wasted spend, blocked pipeline
- [21:25-21:37] keyframe generation excessive retries | SHOT-001A 6 submits, SHOT-006A cap extended to 6, SHOT-006B 4 submits used + edit approach needed | time/cost overrun on Nano Banana Pro credits

ORDER-PROBLEMS:
- render attempted (23:21, 00:01) before GPU backend wired (controller explicitly says not wired at 23:21)
- render attempted (23:21) before shots pass quality gate (6/10 shots have SX-01 errors)
- render attempted (00:01) before mandatory review gate complete (owner at 23:37 says "fix all gaps, start render after fixes, review by Super model; honor no units in test run" but 00:01 goes anyway)
- h3_author started (22:29) while 2K downloads still failing (last download fail at 21:55; watermark remover waits for 20/20 downloads per 21:47)
- boundary frames started (22:06) before all keyframes downloaded and watermark-removed (downloads incomplete, watermark step not run)

ARCH-CHANGES:
- add gate: DOWNLOADS_COMPLETE (20/20 keyframes downloaded + watermark removal verified) before h3_author / boundary frames
- add gate: GPU_BACKEND_READY (controller reports backend wired + test clip renders) before any render --go
- add gate: SHOTS_QUALITY_PASS (all shots green on SX-01 or defined criteria) before render --go
- add gate: MULTI_REVIEW_SIGN_OFF (R1, R2, Super VL, Xing, Nemotron all clear) before render --go; enforce "dry runs only until fixes done"
- enforce run.py embed size limit (JPEG q90 4:2:0 ≤ 9 MB) with pre-upload check; reject oversized payloads
- replace shared browser tab pool with dedicated tab pool per download agent or sequential download scheduler to avoid tab cap starvation

## PROJECT_LOG decisions/fails/owner lines part 9/12
PROBLEMS:
- [01:10] Render attempt 3 terminated by Colab (owner closing extra notebook) | Colab session management interference | No clips; balance 185.30
- [01:12] Owner stops attempt 4, switches GPU G4→A100 mid-process | Owner GPU preference change | No clips rendered
- [01:22] Attempt 5: all 10 shots rc=1 in 10s (wgp error) | Blank line in H3 prompt parsed as 2 generation requests (T0 used single newlines) | ~0.9 units spent (balance 184.86)
- [02:29→02:30] Owner adds RULE 32 (Flow prompt wording), then removes it minutes later | Owner rule churn | Confusion; rule recorded then deleted
- [02:50] SHOT-008 v2 FAIL: "snakes coming from Brahma" | Audio cues in prompt ("serpents hiss softly") interpreted visually by video model | Re-render needed; FIX: shots.json audio_cue x2 removed
- [03:01] Render started BEFORE reading compiled prompt/run.py | Prompt review skipped | Render stopped, runner killed, session stopped; defects found (duplicate sentence, "with the wind drops", "at seconds 7", pronouns)
- [05:21] SHOT-007A rename 8746c61d→SHOT-007A__v02 not saved after 2 tries | Flow UI rename persistence failure | Manual coordinator intervention
- [05:22] Rename 56530241→RETIRED-SHOT-007A__v02-x not saved (1 try) | Same rename persistence failure | Manual coordinator intervention
- [05:27] Audio script approval pending (owner asked to explain simply; shorter text proposed) | Owner reply pending | Batch 2 + regeneration waiting; 10 batch-1 voices in account; 648/3000 credits committed
- [05:30] SHOT-007B: Sandhya shows 3 arms (needs 4); both tiles wrong | Generated keyframe doesn't match spec | Additional edit round (submit 2 of 4)

ORDER-PROBLEMS:
- Voices generation started [02:42] AFTER SHOT-008 video render already GO [02:34] — owner later mandates audio-first: "nothing causes audio/video sync problems later" [05:09] and working order: 1) pre-flight+voice add, 2) run audio, 3) then render
- Render started [03:01] BEFORE reading compiled prompt/run.py — "I read the full compiled prompt only AFTER starting"
- Flow reworks (SHOT-007/009) running in parallel [05:16+] while audio approval still pending [05:27] and voice account provisioning incomplete [04:03: Titan voice not in account]
- Video prompt contained audio cues ("serpents hiss softly") that leaked into visual generation [02:50] — audio cues should not be in video prompt

ARCH-CHANGES:
- Add mandatory **Prompt Review Gate** before any render GO: compiled prompt + run.py must be read, linted, and signed off
- Add **Audio-First Pipeline Gate**: voice generation + approval (final audio lengths known) must complete before video batch build/render
- Separate **audio cues from video prompts**: store audio cues in shots.json for TTS only; strip from video generation prompts
- Add **Voice Account Provisioning Step** before voice generation: verify all voice IDs exist in account (ElevenLabs GET /v1/voices/<id>), add missing via slot
- Add **Owner Audio Script Approval Gate** before batch TTS run: signed-off text per language, length cap enforced
- Add **Flow Rename Verification Step**: automated check after rename (reload + confirm title) before marking tile kept/retired
- Add **Rule Change Control**: rule additions require owner confirmation + 10-min freeze before commit; prevent add/remove churn within same session

## PROJECT_LOG decisions/fails/owner lines part 10/12
PROBLEMS:
- [05:43 rule 37] C: drive 0 GB free | disk exhaustion on system drive | worked from D:/tmp, no clip loss stated
- [05:54] voice_add.py remove blocked by permission classifier | ElevenLabs classifier blocked deletion | 10 KP voices not freed, 6 cast voices need slots
- [10:36] OpenRouter HTTP 401 API key expired | key file loop_p0/secrets/openrouter_paid_key.txt not renewed | fallback to NVIDIA Super VL used; save step dict/str mismatch fixed
- [10:56] render S009 attempt 1 pip install exit 1 | GitHub HTTP 504 on chumpy wheel (external, transient) | no clip rendered; retry exists for HF 429 only
- [11:05] render S009 attempt 2 pip install failed 4× | same chumpy wheel 504, not one-off | setup.log not downloaded, balance 176.25 → 175.81 (0.44 units)
- [11:10] render S009 attempt 3 same chumpy URL 504 | chumpy release file unreachable (external) | 3 attempts, all stopped, no clip
- [11:34] test file edit heredoc newline bug (P1, 9th time) | python heredoc turned escaped newline into real line break | caught by ast.parse, fixed with Edit tool
- [11:47] render S009 attempt 4 ConnectionError, ORPHAN session left | colab new died, orphan G4 session billing 10.05 units/hr | balance 175.67 → 175.34 falling; colab stop cannot find it
- [11:58] render S009 attempt 5 ConnectionError before setup | Remote end closed connection | no units spent, wheel/pip untested
- [12:02] render S009 attempt 6 WebSocketConnectionClosedException | upload_00.py socket already closed | runner stopped session, balance 174.51
- [12:34] render S007 attempt 1 Service Unavailable | ColabRequestError: no G4 free? | guard ran, balance 171.34, nothing spent
- [12:53] score/gate_d_bridge.py probes fail | NaN/inf stem passes, anti-phase f32 misses BASS_NOT_MONO, presence_levels raises on nan win_s | —
- [12:54] score/plan_check.py fuzz KeyError CHECK_CRASH | missing rehook_at_s/peak_at_s keys | fixed with .get and explicit PEAK
- [12:47] voice text v3: 7 shot-language groups cannot fit editorial length | even with atempo 1.15, 8 lines too long | shorter text needed for 8 lines, owner to confirm 006 narration
- [13:08] captions very bad (engine default style) | 34px at 1080w, plain fallback, 10 title cards only, not owner's IG/YT Shorts spec | NOT touched now, current reels keep default captions
- [13:13] score bible written from SKILL.md only | admitted shortcuts: Ableton docs read by agents not owner, audition.py written by owner | owner said start the study

ORDER-PROBLEMS:
- [10:45] render attempted before "check everything before the render" | owner ordered: go start render, then check everything before render; render NOT started; rework pack prepared with all checks before --go
- [12:47] voices generated for editorial lengths but 7 shot-language groups cannot fit | reel cuts at editorial length (6,5,7,8,8,7,7,8,8,6s); voices generated before validating fit against timeline
- [13:08] captions generated with engine default before owner's caption spec applied | current final reels keep default captions; owner's IG/YT Shorts spec not found/applied first
- [13:13] score bible written before studying owner's curated docs + core | bible from SKILL.md only; Ableton docs read by agents not owner

ARCH-CHANGES:
- Add pre-flight URL check gate for external deps (chumpy wheel) + keep error text (RULE 40)
- Add order-enforcement gate: all checks/reviewers must pass before --go render (RULE 41)
- Add persistent Colab session tracker/cleanup for orphan sessions (colab stop cannot find unnamed sessions)
- Add retry/fallback for GitHub releases (currently only HF 429 retry exists)
- Mandate setup.log download on every render failure (missing in attempt 2)
- Add voice-length validation against editorial timeline before voice generation (gate: voice duration ≤ editorial slot at max atempo)
- Add caption-spec gate: require owner's caption spec file before generating captions
- Add study gate for score phase: owner's curated docs + core must be read before bible writing
- Add C: drive space monitor/gate (rule 37)
- Add ElevenLabs voice-slot management workflow (permission classifier block handling)
- Add API key rotation monitor for OpenRouter (key expiry detection)

## PROJECT_LOG decisions/fails/owner lines part 11/12
PROBLEMS:
- [11-09 13:13 DECISION study finding] Ableton recipe lacks readback after mutations (only get_session_info) | recipe incomplete vs CLAUDE.md rules 4/6/8/10/11/12 | rework to add readbacks
- [11-09 13:13 DECISION study not finished] Critical docs unread (README 400-end, serum-mcp, core modules, owner style study) | audit cannot complete without them | blocked audit of built modules + bible
- [11-09 13:40 FAIL style study GA43TUfaKAxzBJRD1cDFiP] Docs access denied, artifact not found, no local copy | owner must share/paste | study unavailable for reference
- [11-09 13:40 DECISION music_bible SHIVA] SHIVA theme D2-D3 all <200 Hz = silent on phones at peak (rule 11) | low octave theme | fix: octave-up doubling of low theme notes
- [11-09 13:33 NW3 FAIL test_note_writer.py] C29 red before impl: partners test fails (no partner notes) | test written before implementation | test failure blocking
- [11-09 13:50 DECISION music_bible.json vs study] 11 direction errors found (logo, MAIN length, Shiva half-step, deity shapes, roles, quiet moment, per-shot genres, deity signatures); 2 rule conflicts | bible diverges from study | owner arbitration needed
- [11-09 13:39 DECISION captions faces] Face overlap left as-is; final reels v3 handed over | known visual defect accepted | shipped with overlap
- [11-09 14:02 DECISION PCR2 triage] Multiple rejections: #3 (sting timing), #6 (owner rule 8 = fast act only), #9 (timing conflict) | note_writer behavior vs bible/owner rules | PC2 fixes required
- [11-09 14:12 DECISION PCR2 re-check] Reject R-1 (low brass allowed under voice but note_writer drops high brass), R-2 (handover/swell audible), R-4 (writer truncates by design) | implementation vs spec mismatch | test_c28 fails, plan_check review closed after R-3 only
- [11-09 14:14 NWR3 FAIL _probe_nwr3_reel.py] python -I cannot import pytest (fixture module imports it) | test environment isolation flag breaks imports | rerun without -I needed
- [11-09 14:18 NWR3 DECISION REVIEW_NOTE_WRITER_R3] HIGH: piano under speech; Shiva reveal drums | note_writer violations | 2 HIGH, 4 MED, 6 LOW findings
- [11-09 14:29 FAIL NW4 r6 + PC2 r3 agents] Stopped on session restart (not code error); 15 failed, 331 passed in tests-first stage | process instability | work lost at red stage
- [11-09 14:43 NWR3 DECISION re-check] NEW HIGH: R-1 curse swallowed by merge; MED: R-2 merge velocity leak, R-3 theme velocity flat 100 (peak) | merge logic defects | NW4 round 7 required
- [11-09 15:10 FAIL final_reel1_v4 first build] Gate D VO_OVERFLOW_ERROR shots 5/7/8 all langs: padded VO = editorial-0.10 exactly, frame-based editorial (8.2917) rounds up one sample | frame rounding vs sample precision | build fails at gate
- [11-09 15:22 CS3 FAIL test_audition.py] test_cli_builds_three_files failed after live regenerate | test flakiness post-regeneration | investigating
- [11-09 16:30 SMP2 FAIL sound_select.py] Selection crashed on zero centroid (silent sample) in zone_score | no guard for silent samples | fixed with guard, rerun
- [11-09 16:31 SMP2 FAIL sound_select.py] Relax logic applied to modern layers (S5 groove/bass shown as Indian relaxed) | incorrect layer classification | fixed to Indian-required only, rerun
- [11-09 16:33 SMP2 FAIL sound_select.py] 4 empty slots (S5-groove, S5-bass, S6-bed, S7-bass): cap 30 consumed by clipped/key-failing files; 6s snippet key re-measure noisy on bass | cap too low, short snippet unreliable | measure beyond cap up to 300 until 12 scored
- [11-09 16:54 SMP2 FAIL v3 build] S3 indian stem -53 dBFS (<-40) and windows 14-15 at -30.7/-27.1 (riding clamp +12) | per-slot level too low | fix: SLOT_LEVEL_DB S3 +15, S8-bed +12
- [11-09 16:58 SMP2 FAIL v3 rebuild 2] Window 67.4-70.4 s still -26.0 (outro bed -37.8 dBFS) | S8-bed level_db insufficient | fix: S8-bed level_db 12 -> 18
- [11-09 15:35 PLAN FAIL note_writer.py] write_notes rejects plan_check transitions (theme_handover, key_colour_on_downbeat) | vocabulary clash between plan_check and note_writer | forced swells on 5 soft cuts (style fault)
- [11-09 15:56 OWNER gate M1] Stock sketches not acceptable; build properly in Ableton with built-in instruments/samples | overrides no-Ableton-before-M1 | rework required
- [11-09 16:07 OWNER key] Key not set properly; need measured key (chroma) for every tonal sample, D minor/F major only, shift <=3 st else reject | key management missing | re-measure stems, key report in sample_log

ORDER-PROBLEMS:
- [11-09 13:13 DECISION study not finished] Audit of built modules + bible started BEFORE reading critical docs (README 400-end, serum-mcp, core modules, owner style study) | should wait for full doc review
- [11-09 13:33 NW3 FAIL test_note_writer.py] Test written (C29 red) BEFORE implementation exists | test-first but partners test fails because no partner notes implemented yet
- [11-09 13:50 DECISION music_bible.json vs study] Bible direction errors (11 found) discovered AFTER bible was drafted and used | bible should have been validated against study before use
- [11-09 14:14 NWR3 FAIL _probe_nwr3_reel.py] Test run with python -I BEFORE checking fixture imports pytest | should verify test environment compatibility first
- [11-09 15:10 FAIL final_reel1_v4] VO_OVERFLOW_ERROR at Gate D because editorial timeline (frame-based) rounds up one sample vs padded VO | editorial timeline should be finalized and validated BEFORE VO padding/render
- [11-09 15:35 PLAN FAIL note_writer.py] plan_check emits transitions (theme_handover, key_colour_on_downbeat) that note_writer REJECTS | shared vocabulary should be defined BEFORE either generates/consumes transitions
- [11-09 15:56 OWNER gate M1] Owner rejects stock sketches AFTER M1 plan written, requires Ableton build BEFORE M1 | Ableton build should be prerequisite for M1 gate, not after
- [11-09 16:07 OWNER key] Key measurement (chroma) for every tonal sample required AFTER sound selection ran | key validation should gate sound selection, not follow it
- [11-09 16:30 SMP2 FAIL sound_select.py] Selection crashed on silent samples BEFORE guard added | input validation should precede scoring
- [11-09 16:33 SMP2 FAIL sound_select.py] 6s snippet key re-measure used BEFORE verifying reliability (E min at 30s vs E maj at 6s) | measurement method should be validated before depending on it

ARCH-CHANGES:
- Add "Doc Review Complete" gate before audit stage: require README 400-end, serum-mcp, core modules, owner style study read and signed off
- Add shared vocabulary contract file (e.g., score/transitions_vocab.json) that both plan_check and note_writer import; CI fails if either uses undefined transition
- Move Ableton build to PRE-M1 stage; M1 gate requires Ableton project with built-in instruments/samples, not sketches
- Add key validation stage BEFORE sound_select: measure chroma for all tonal samples, enforce D minor/F major, shift <=3 st, write sample_log; sound_select reads sample_log
- Add silent-sample guard in zone_score (already fixed) + make it a pre-selection filter with log
- Increase sound_select cap from 30 to 300 with "measure until 12 scored" logic; deprecate 6s snippet key measure, use full-stem or >=30s window
- Add editorial timeline validation step: compute exact sample-accurate shot lengths from VO + frame math BEFORE VO padding; fail fast if rounding mismatch
- Add "transition vocabulary sync" test in CI: plan_check emits -> note_writer accepts round-trip
- Add per-slot level_db calibration stage after sound_select v1: measure stem loudness in context, write SLOT_LEVEL_DB overrides, re-run build
- Add process checkpointing for long agent runs (NW4/PC2) so session restart doesn't lose red-stage progress

## PROJECT_LOG decisions/fails/owner lines part 12/12
PROBLEMS:
- [11-09 17:01 SMP2] restore stems used wrong path | root cause: human error in path selection | cost: time to restore from ep1/sound_v2_backup/stems_v2
- [11-09 17:11 ABL2] create_clip refused: clip slot already occupied, no delete-session-clip/clear-notes tool | root cause: missing tool to clear clip slot | cost: nothing written, arrangement clip not deleted
- [11-09 17:40 SFX1] onset test failed: log-flux + 2048 frames put clicks 56 ms early | root cause: incorrect onset detection parameters | cost: fixed by changing to linear flux, 512 frames (tests now 5 passed)
- [11-09 17:55 EQ1] v5 run: 0 sustained clashes (max frac 0.19 < SUSTAIN 0.25) so no clash cuts made; noduck pre at -2.7 LUFS clipped | root cause: SUSTAIN threshold too high; raw stems without global gain | cost: not stated
- [11-09 18:00 OWNER] mixing done in code outside Ableton | root cause: computer-use access for Ableton export denied, MCP cannot write arrangement notes/automation/render; owner rejected stock MIDI -> library loops conformed by code; mistake: not brought back into Ableton for mixing | cost: owner angry, rework proposed (Ableton-native mix)
- [11-09 18:20 OWNER] renders r1-r4 overwritten in place | root cause: not following versioning discipline | cost: settings/results lost (only backfill lines remain)
- [11-09 18:28 DECISION] r10 chosen but min voice over music+SFX 9.1 dB (final line) and 11.3 dB (13.7 s) below 12 dB target | root cause: accepted to stop iterating per owner | cost: quality

## docs/PIPELINE_AUDIT_2026-11-07.md part 1/2
PROBLEMS:
- [1.1] Two branches never merged (v4-architecture-2026-11-07, universal-v1.1) | parallel development on separate branches | no single checkout runs whole path; 4 conflicted files, 8 hunks
- [1.3] V4 branch has three named holes: Step 9 QC runner, Gate D assembly runner, live author run not built; pre-render controller has no GPU backend wired | incomplete implementation | cannot execute full pipeline
- [1.4] Nothing rendered for production | only T0 test (8 clips, one scene, on Colab) | zero production video output
- [1.5] No story gone through finished pipeline | real Kaliya pack missing in new form; old T0 shots lack `look` block → 8/8 fail P2 | end-to-end validation impossible
- [1.6] Two caption engines exist (core/captions.py and h3/gate_d_audio.py) | parallel development on two branches | must unify at merge
- [1.7] Style packs structurally complete but not measured: no plate has measured Lab value, no LUT file exists, braj_earth has no grade numbers, gates.sat_avg_ceiling=null, gate limits untuned | measurement tools exist but not run | colour grading not production-ready
- [1.8] Dots reviewer unreliable on long inputs (empty answers) | model limitation | some batches covered by Super VL only
- [1.9] Fonts committed to git (spec said "no fonts staged") | deliberate change after owner supplied them | licence compliance maintained (SIL OFL)
- [2.1] Writer: no live v2.3 or V4 writer run on real story | model call needs owner go | writer unvalidated on real input
- [2.5] Flow images: image generation is manual browser step in Flow, not code | Flow designed as manual tool | not automated
- [2.7] Pre-render controller: no GPU backend wired | controller is "prepare only" | cannot trigger renders
- [2.8] Render: not part of controller; T0 test only, no production render | render step disconnected from controller | no production rendering path
- [2.10] Step 9 QC: runner not built | functions done but no runner | final review gate not executable
- [2.11] Audio plan: assembly runner not built; ElevenLabs needs go | runner missing; API key needed | audio assembly not executable
- [2.12] Assembly: plans only, never runs ffmpeg | assembly script doesn't execute | no actual assembly
- [2.13] Post: never run on real clips | only synthetic clips tested | post-processing unvalidated on real data
- [2.14] Analytics: no analytics file exists yet | tool done but no data | analytics not functional
- [2.15] UI wizard: not verified how it will display new rule results once branches merged | merge not done | UI integration unknown
- [3.6] UI JS has no unit tests | only syntax check and manual browser check | JS reliability untested

ORDER-PROBLEMS:
- Stage 8 Render (video) ran before Stage 11 Audio plan (voices) | video rendered to fixed lengths, voices generated later didn't match | required editorial timeline repair step

ARCH-CHANGES:
- Merge v4-architecture and universal-v1.1 branches into single trunk
- Build three missing V4 runners: Step 9 QC runner, Gate D assembly runner, live author run
- Wire GPU backend into pre-render controller (Stage 7) so it can trigger renders
- Unify two caption engines (core/captions.py and h3/gate_d_audio.py) into single engine
- Run measurement tools (measure_plate.py, calibrate_sat_ceiling.py, make_lut.py) to populate Lab values, LUT files, grade numbers, sat_avg_ceiling, tune gate limits
- Replace manual Flow browser step with automated generation or formalize as gated manual handoff with contract
- Connect Render (Stage 8) to controller (Stage 7) so controller orchestrates render
- Build Audio plan assembly runner (Stage 11) and secure ElevenLabs access
- Make Assembly (Stage 12) execute ffmpeg (not just plan)
- Run Post (Stage 13) on real clips as validation gate
- Generate analytics file for Analytics (Stage 14) consumption
- Verify UI wizard displays merged rule results post-merge
- Add unit tests for UI JS
- Enforce audio-first ordering: move Audio plan (voice generation) before Render (video generation) so video built to audio length

## docs/PIPELINE_AUDIT_2026-11-07.md part 2/2
PROBLEMS:
- [§6.1] Two caption engines (Gate D own + core/captions.py) | branches diverged; Gate D built with private caption code | 4 conflicts, 8 hunks to merge; must replace Gate D code post-merge
- [§6.2] No production render / real post.py run | not executed yet | limits untuned (G1/G2 dE 6, G3 dE 8, static 3.5/4.0 s); LUTs unchecked on real frames
- [§6.3] Style packs unmeasured | no approved plates/reference frames for measure_plate, make_lut, calibrate_sat_ceiling | G1 skipped (warning); no LUT files (styles/luts missing); braj_earth has no grade numbers → Kaliya exports ungraded; gates.sat_avg_ceiling null → G2 uses provisional 181.02 (warning)
- [§6.4] V4 runners not built (Step 9 QC, Gate D assembly, live author) | not built yet | functions exist and tested but not runnable
- [§6.5] Render backend not wired into controller | not wired yet | controller cannot trigger renders
- [§6.6] Paid ElevenLabs API shape unverified | parser/karaoke path from public docs only | live use needs approval; risk of API mismatch
- [§6.7] Story work not started | by instruction | writer run, caption text/hook words, Kaliya defects, Mahadev reel 4 pending
- [§6.8] Manual checks (spec 6.4) not done | not done | LUTs unapproved on 3 stills/act; episode unreviewed on D65+phones; caption placement vs overlays unchecked; DEVA publish gate not run
- [§7.1] Caption widths measured with Pillow basic layout (no libraqm) | Devanagari conjunct widths over-estimated | line breaks may differ from real render (libass/HarfBuzz render looked correct)
- [§7.2] Caption size defaults (34 px @1080, outline 8%) and safe zones are tune values | not calibrated | may need adjustment
- [§7.3] Free reviewers unreliable (Dots empty on long inputs; Super VL cites unseen code) | tool limitations | every finding must be hand-checked
- [§7.4] Automatic log hook installed but not firing | needs new session | hook unverified in current session
- [§7.5] Stale docs on V4 branch (STATUS.md shows old suite counts) | not updated after test runs | misleading status
- [Test results] 3 known data-dependent failures | real pack folder local+untracked | 3 failures in universal suite
- [Test results] Kaliya check_pack: real new pack missing; old T0 shots have 8 P2 FAIL (no look block), 1 R1 FAIL, 8 R6 FAIL (5.17 s static gaps) | old shots have real content defects | content problems block clean pack validation

ORDER-PROBLEMS:
- [§6.3] post.py grading runs (falls back to pack grade numbers) before measure_plate → make_lut → calibrate_sat_ceiling have produced approved plates/LUTs | post.py should wait for measured plates and generated LUTs
- [§6.1] Gate D assembled with private caption code before universal caption engine (core/captions.py) was merged/available | Gate D should have used or waited for the single caption engine
- [§6.2] Limit tuning (G1/G2 dE, G3 dE, static thresholds) requires production render on real frames first | tuning should wait for real render output

ARCH-CHANGES:
- [§6.1] Merge branches; then replace Gate D caption code with core/captions.py + caption_export.py (single caption engine)
- [§6.3] Add gate: require approved plates (measure_plate output) + LUT files (make_lut output) + calibrated sat ceiling (calibrate_sat_ceiling output) before post.py grading runs
- [§8.2] Formalize story-to-render pipeline as gated stages: writer run → caption text/hook words → approved plates (measure_plate) → first render → calibrate_sat_ceiling + limit tuning
- [§6.4] Build three V4 runners (Step 9 QC, Gate D assembly, live author) and wire them
- [§6.5] Wire render backend into controller
- [§6.6] Add contract test / verification step for ElevenLabs API shape against real endpoint before live use
- [§7.4] Fix automatic log hook to fire in current session (not only new session)
- [§7.5] Sync STATUS.md on V4 branch after merge and suite runs (automate in merge gate)
- [§6.3] Create styles/luts directory; generate LUT files via make_lut after measure_plate approval
- [§6.3] Add grade numbers for braj_earth style pack

## docs/AUDIT_2026-11-08_REEL1.md part 1/1
PROBLEMS:
- [Gap 1] pack_to_spec refuses V4 shots ("unsafe set id None") | V4 rows lack shot.set, shot.cast, shot.props, shot.keyframes | Gate B image prompts cannot be built
- [Gap 2] H3 prep reports 73 lint errors; writer validator lacks H3 timing/seam checks | 13 authored fields missing, dynamic split fits fail (shots 2,3,6,7), mouth state MO-01 missing (shots 1,10), sound cues SX-01 only 5/7 | Pixel frames grow 20-30% more GPU time per clip (e.g., 192→243 frames for 8s shot)
- [Gap 3] No speech-rate check before voice; 20 lines exceed 3.2 wps (EN max 4.4) | Only fit check (Gate D vo_fit) requires paid ElevenLabs wav first | Paid voice generation may be wasted
- [Gap 4] Two clocks: retention rules/check_pack use pixel frames (70.8s), pack_validator/edit use editorial seconds (70.0s) | Time-window rules (re-hook 25-35s, cold open) off by handle frames | Rules misaligned
- [Gap 5] Story gate checks self-graded by writer; no comparison with SOURCE.md | Only SRC-01 ties source_sha256, semantic fidelity not automated | Reviewer pass needed
- [Gap 6] story.json missing style_pack; writer uses deva_neon, check_pack fails P1 | check_pack expects style_pack | Check failure

ORDER-PROBLEMS:
- Voice generation (paid ElevenLabs) ran before speech-rate check (SPEECH-01) | should wait for speech-rate validation
- Writer gates (stage 1,2,3e1,5e1) ran and passed before H3 timing/seam checks (fit_lattice, H3-01) | should wait for H3 validator rule and deterministic lattice fit
- pack_to_spec (Gate B) ran on writer V4 output before

## research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md part 1/1
PROBLEMS:
- [§3 "The cue sheet... was built on the v3 lengths"] Cue sheet outdated | Generated against superseded v3 timeline (70.0 s) instead of frozen v4 timeline (72.833 s) | Not stated
- [§3 "White-outs moved with the timeline only if they sit after an extended cut: recompute them"] White-outs potentially misaligned | Not recomputed after shot-end extensions added in v4 editorial timeline | Not stated
- [§2 "Result for the voice: every line... now plays at natural speed 1.00 (v3 had up to 1.12)"] Voice speedup artifacts in v3 | v3 timeline too short for natural voice duration, required timeline extension | Not stated

ORDER-PROBLEMS:
- Cue sheet generation (score/ep1/cue_sheet.json) ran before editorial timeline freeze (gate M1) | Should wait for frozen `editorial_by_lang.json` (v4) and `vo_tracks_report.json`
- White-outs computation ran before editorial timeline freeze | Should wait for frozen `editorial_by_lang.json` with final shot extensions

ARCH-CHANGES:
- Add gate M1 as explicit dependency: `gate_d_bridge.py write_bgm_manifest` (cue sheet) must read frozen `editorial_by_lang.json` and `vo_tracks_report.json`; fail if versions mismatch.
- Move white-outs recomputation into `director/editorial_by_lang.py --write` so it emits updated white-out list atomically with timeline freeze.
- Contract: music session receives only v4 artifact bundle (editorial_by_lang.json, vo_tracks_report.json, regenerated cue_sheet.json, video masters); v3 artifacts archived/removed from music scope.

## CHECKLIST_ARCHITECTURE_2026-11-07.md part 1/1
PROBLEMS:
- none in this slice

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- none in this slice

## STATUS.md part 1/2
PROBLEMS:
- [Kaliya pack defects before Gate A] reels 2-5 short (60.0/47.6/51.1/55.6 s vs 65-75 s target); CHAR-INDRA/BRAHMA/NARADA/SARASVATI and PROP-KALI-KAMLI used by shots but missing from bible; PROP-KANSA suspicious | owner has not answered; pack not approved | not stated
- [Not built: Step 9 runner, Gate D assembly runner, live author run, any real render] pipeline cannot complete end-to-end | owner rule: no Colab calls; ElevenLabs needs owner go | not stated
- [Owner inputs that code cannot supply] approved plates (one per place/story), braj_earth grade numbers for HOOK/BUILD/DROP/OUTRO, LUT approval (~3 stills/act), story/caption/hook text per language, ElevenLabs voice files per language | code cannot generate these; require owner action | not stated
- [Caption widths measured with Pillow basic layout] Devanagari conjunct widths slightly over-estimated; line breaks may differ from real libass render | no libraqm in Pillow build | not stated
- [ElevenLabs alignment shape] written from public documentation, unverified against live response | no live API call made yet | not stated
- [F1 counting rounds odd transitions up] 8 alternating frames = 4 flashes | confirmed by owner 2026-11-07 | not stated
- [P1 missing story.json = FAIL] | confirmed by owner 2026-11-07 | not stated
- [Wizard rejected-stage does not auto re-open after re-run] decide again works | UI leftover | not stated
- [Typed pack name reverts on poll] | UI leftover | not stated
- [app.js message bar success class] | UI leftover | not stated
- [PLACE_TEXT_OVERRIDES in build_jobs is Kaliya-only] | hardcoded for one story | not stated
- [Open images: LEAP-02A/02B water still pale; KRISHNA_ACTION_POSES bottom row broken] | reference images defective | not stated
- [No render has been run] gate limits (G1/G2 dE 6, G3 dE 8, static 3.5/4.0 s) cannot be tuned | waiting for first approved render | not stated
- [gates.sat_avg_ceiling is null] `ANIME_RELEASE=1 python -m pytest core` fails | saturation-ceiling calibration not done | not stated

ORDER-PROBLEMS:
- [Kaliya pack] render planned (LEAP-01..05 with sing8) before pack defects fixed (reels short, missing bible entries) | render should wait for Gate A approval with fixed pack
- [Voice files] ElevenLabs voice files needed per shot for post.py voice mix, but ElevenLabs use needs owner go and not built | voice files should be ready before render/post, but owner go not given
- [Caption text] caption text and hook words needed for caption engine, but story not written yet (needs owner go for v2.3 writer) | captions should wait for story and caption text
- [Grade numbers] braj_earth grade numbers needed for HOOK/BUILD/DROP/OUTRO, but not supplied | grading should wait for approved plates or grade numbers
- [LUT approval] LUT approval needed (~3 stills/act), but not done | colour grading should wait for LUT approval
- [Reference frames/plates] owner-approved reference frames and plates needed for saturation-ceiling calibration, but not done | calibration should wait for approved plates and reference frames

ARCH-CHANGES:
- [One caption engine] Gate D's private caption builder deleted; now calls shared engine (`core/caption_cues.py`, `core/captions.py`, `core/caption_export.py`) via `h3.gate_d_audio.build_captions` | eliminates duplicate caption logic
- [Voice mixing in post.py] replaces Gate D's mux for final reel; Gate D stays as pre-render gate | single voice mix point, clear separation of concerns
- [Loudness standard] one source of truth in `core/core.json` `delivery.audio` (-16 LUFS, -1 dBTP); Gate D's -14 LUFS profile removed; post.py, voice mix, h3/assemble_reel.py, Gate D post-render check all read it | unified loudness target across pipeline
- [Audio plan frozen] music removed; H3 generates all SFX in video+audio pass; post.py keeps H3 audio as SFX bed ducked under voice; background music is owner's separate step | fixed audio architecture, no separate SFX library
- [UI pipeline wizard] enforces order: Story -> Analysis -> Gate A -> Images -> Gate B -> Read-out -> Gate C (typed START) -> Render -> Gate D -> Export | gated workflow prevents out-of-order execution
- [Caption engine components] `core/caption_cues.py` (cue model, validator, spoken-script reader, hook policy), `core/captions.py` (ASS burn), `core/caption_export.py` (SRT/WebVTT serializer) | modular, testable caption pipeline
- [Voice file contract] per-language voice file `<vo-dir>/<lang>/<shot_id>.wav` required for every shot with narration/dialogue; missing = refusal naming the file, never fallback to H3 audio | explicit contract between voice generation and post mixing
- [Saturation-ceiling calibration] `tools/measure_plate.py` on plates, `tools/calibrate_sat_ceiling.py FILES --write` on reference frames; `ANIME_RELEASE=1 python -m pytest core` must pass (fails while `gates.sat_avg_ceiling` null) | gate enforces calibration before release
- [Writer v2.3] story and shots written via model call (needs owner go) | formalizes story creation as a gated step
- [Gate D caption tests] moved to `h3/tests/test_gate_d_captions.py` | tests co-located with gate logic

## STATUS.md part 2/2
PROBLEMS:
- none in this slice

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- none in this slice

## research/AUDIO_PLAN_FROZEN_2026-11-06.md part 1/1
PROBLEMS:
- [Frozen decision 5] Loudness varies up to 14 dB between clips | Independent clip generation yields different integrated loudness levels | Cost not stated
- [Frozen decision 6] Audio drift can appear at later clips (e.g., clip 4) | Model inconsistency over sequence | Cost not stated
- [Rejected: Vocal tools] Vocal tools cannot separate effects from music | Tool limitation | Cost not stated
- [Frozen decision 1] Music consistency impossible across independently generated clips | No shared audio state between renders | Cost: music removed, owner adds separately (owner effort)
- [Frozen decision 2] Linter warns on negations in prompts | Prompting rules prohibit negations | Cost not stated
- [Frozen decision 5] Dynamic loudnorm second pass unreliable on 5-second clips | Short clip duration breaks loudness-range logic | Cost not stated
- [Frozen decision 6] Music or vocals may leak into generated clips | Model generation inconsistency | Cost: re-render affected clips if owner agrees

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- Add registry `sound_beds` mapping location IDs to fixed sound-bed phrases (≤12 words, consistent casing/punctuation)
- Modify compiler to emit soundscape as "Sound effects only: <bed> <effects>" per shot
- Add linter rule SD-03 to verify soundscape starts with "Sound effects only:" and includes location's bed when defined
- In `assemble_reel.py`, implement `loudness_plan(measured)`: measure integrated loudness per clip (ffmpeg ebur128), compute linear gain to -16 LUFS, apply true-peak limiter at -1.5 dB (`volume=<gain>dB,alimiter=limit=0.84`)
- Define audio processing chain: gain adjustment → 5 ms fades (160 samples at 32 kHz) at every cut
- Write measured loudness values to `loudness.json` in build folder for audit
- Retain model-generated audio in final join (no separate audio render)
- Integrate audio QA into normal clip QA: listen to every rendered clip (not just first)
- Establish leakage remediation: update shared template (prefix or bed phrase) for affected location and re-render only those clips with owner approval; never patch single shots

## research/VOICE_SYSTEM_DESIGN_2026-11-09.md part 1/1
PROBLEMS:
- [§2] No Hindi voices in ElevenLabs account | account only has English premade and Marathi professional voices | must use shared library (free, 10 slots)
- [§4 D1] Quality for Marathi/Hindi and sacred names untested on this account | model quality unknown for target languages | risk of regeneration if quality poor
- [§4 D4] 8 Hindi lines fail words-per-second check (too fast for slots) | text too dense for timing windows | may need text shortening before generation
- [§4 D2] Account slot limit 10 for added library voices | shared library limited to 10 slots on Starter plan | constrains voice count (18 voices needed for 6 speakers × 3 languages)
- [§5] Regeneration triggers identified: wrong text, wrong voice, wrong model, mispronounced names, line too long, changed setting, crash mid-run, duplicate call | various | credits wasted

ORDER-PROBLEMS:
- none in this slice (design proposes correct order S1–S11: audio pipeline before video)

ARCH-CHANGES:
- [§3] Add `director/voice_library.py` to fetch/normalize voices with preview_urls (free API calls)
- [§3] Add `<story pack>/voices_cast.json` as owner-filled voice map after preview review
- [§3] Add `director/voice_cast.py` with jobs (dry), run (paid, `--allow-paid --cap`), measured, export, freeze — replicating Granth's job key, ledger, reuse, ffprobe, manifest
- [§3] Add pre-flight checks gate before any spend: cast completeness, language verification, text checks, credit cap
- [§1.3] Job key = sha256(language|voice_id|model|settings|text) for immutable caching/reuse
- [§1.4] Credit ledger: append-only, file-locked, reserves estimate before call, settles from API header, refuses past cap or open reservation
- [§1.5] Spend gate: `jobs` free, `run` requires `--allow-paid` and cap
- [§1.6] Measure gate: ffprobe every accepted clip, implausible duration stops run, measured duration feeds timing plan
- [§1.7] Freeze file: sha256 of plan, measured file, script text, manifest; voices NOT VALIDATED until owner listens
- [§4 D11] Enforce order: S1 library+previews → S2 cast+lint → S3 code+tests → S4 jobs dry → S5 test run (360 credits) → S6 full run → S7 measure+fit+wavs → S8 freeze

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 1/4
PROBLEMS:
- [Gap 1] Tempo map changed tempo at 41 s (neither hard cut nor act change) | invalid tempo change placement | —
- [Gap 2] Re-hook at 26 s outside retention window (31.5–42.0 s) | incorrect timing | —
- [Gap 3] Live API cannot automate song tempo or change time signature | API limitation | workaround: clock mode at 60 BPM, notes at absolute seconds
- [Gap 4] Arrangement locators are read-only | API limitation | workaround: MARKERS MIDI track with named clips per shot
- [Gap 5] Live API has no audio export | API limitation | workaround: owner export or MCP real-time recording; render trimmed to 3,360,000 samples
- [Gap 6] Gate D supports BGM but `post.py` and `render_controller` pass `bgm=None` | not wired | code change needed in build step 10
- [Gap 7] H3 effects overlap planned hits (bell at 0–0.8 s, 43.0–43.5 s, 48–49 s) | not coordinated | score must avoid same band at same moment
- [Gap 8] Plan rounded first white-out to 43.1 s vs actual 43.083 s (frame 1034) | rounding error | frame-exact timing required
- [Gap 9] 60.0 s white-out and end sting fall under speech | not checked against voice windows | low-hit rule: sub/low drum only under voice
- [Gap 10] Shiva's reveal at 48 s sits inside drum-and-bass act | act/timing mismatch | 0.4 s drop-out + half-time theme required
- [Gap 11] Live imports reference video as .mov only | format limitation | picture reference must be exported as .mov
- [Gap 12] Whether Serum macros follow clip automation not verified | untested | open item: confirm in Live before first build
- [Gap 13] Hybrid-cinematic or electronic style not chosen | undecided | must choose at gate M0
- [Gap 14] Phones roll off below ~200 Hz and play mono when held upright | hardware limitation | mono bass, mid harmonic on every bass note, mono check required
- [Gap 15] MCP tool names unknown (`D:\ableton` not on GitHub) | local-only tooling | adapter written after connection check (build step 1)
- [Gap 16] `PROJECT_LOG.md` lives on PC, not reachable | local file | log lines handed to paste manually
- [Gap 17] `story_plan.json` says 68 s, shots add up to 70.0 s | duration mismatch | score follows shots (70.0 s) unless overridden
- [Gap 18] Cue sheet v1 reads voice windows from pack, not rendered voice | using planned not actual timings | Gate D presence check catches drift; v2 can read rendered timings
- [Gap 19] Drums, chants, vocal horns need real recordings | licensing | own recordings or cleared packs only; never film/song samples

ORDER-PROBLEMS:
- Cue sheet (Score S1) reads voice windows from `shots.json` pack before voices are rendered (actual voice timing only available after render) | should wait for rendered voice timings or accept drift caught at Gate D
- `post.py` and `render_controller` call Gate D with `bgm=None` before BGM manifest is wired | should wait for Score S4 output and manifest injection (build step 10)
- Score S3 (Ableton build) drives MCP before adapter is written (adapter written at build step 1 after connection check) | adapter must exist before Score S3 runs

ARCH-CHANGES:
- Add **Score** stage after clip render and before Gate D (four sub-stages: S1 cue sheet, S2 spotting+plan @ gate M1, S3 Ableton build, S4 render+check @ gate M2)
- Add `score/cue_sheet.py` → `audio/score/cue_sheet.json` (pure script, 32 tests, no model/network)
- Add `score/plan_check.py` as enforced build step (skill forbids weakening rules to pass)
- Add gates **M0** (music bible), **M1** (plan + stock-sound MIDI audition), **M2** (Gate D preview with picture/effects/voice)
- Wire BGM manifest in `director/post.py` and `render_controller`: read `story.json` `"bgm": {"enabled": true, "manifest": ...}` instead of `bgm=None`
- Define `audio/bgm_manifest.json` contract: `track_id, path, license_type, bpm, lufs` (empty list = no BGM)
- Export reference video for Live as `.mov`
- Save approved plans in `score_examples/`; new emotion templates → music bible for future reels
- Write thin MCP adapter after connection check (build step 1) to map local tool names
- Cue sheet v2: read rendered voice timings (not pack) for frame-exact voice windows

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 2/4
PROBLEMS:
- [old 60/120 tempo map] tempo changed at 41 s (not a hard cut or act change), breaking its own rule; 120 BPM suited neither techno nor drum-and-bass | root cause: tempo change at non-act-change cut; wrong BPM for target genres | cost: map replaced, rework implied
- [old re-hook at 26 s] re-hook placed at 26 s, outside retention window (31.5–42.0 s from core.json) | root cause: re-hook not aligned to act change / retention window | cost: moved to 34.0 s in new plan
- [pre-JSON-first workflow] musical decisions made in Ableton; failed MCP calls, crashed Live sets, or changed presets lost compositions; steps not re-runnable | root cause: decisions made in DAW instead of serialized JSON first | cost: lost compositions, irreproducible steps (stated as motivation for JSON-first rule)

ORDER-PROBLEMS:
- Ableton touched before musical decisions written to JSON and tested (JSON-first rule created to stop this: "Ableton is the place the decisions are played, not the place they are made")

ARCH-CHANGES:
- Replace old tempo map with new 60/128/176/60 map where actual BPM changes only at act changes; felt tempo and density carry emotional shifts inside acts
- Move re-hook to 34.0 s (act change) inside retention window (31.5–42.0 s)
- Enforce JSON-first rule: every musical decision written to JSON file and tested before Ableton is touched (components 1–5 produce JSON; component 6 only consumes via MCP)
- Add owner gates: M0 (music_bible.json approval), M1 (score_plan.json approval via plan_check.py)
- Clock-mode workaround: run Live set at 60 BPM (1 beat = 1 s); note writer places notes at absolute seconds from plan's tempo map; tempo-synced devices set to free time (ms/Hz)
- Componentized pipeline with pure-Python builders (1–4, 7–8) and only two tool adapters (5 Serum, 6 Ableton/MCP); each stage emits a versioned file contract (music_bible.json → cue_sheet → score_plan.json → notes/*.json + .mid → presets/ → Live set → checks → bgm_manifest.json)
- Render + check stage (component 7) verifies length = reel length to sample, no clipping, voice-window level, hit alignment, Gate D presence

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 3/4
PROBLEMS:
- [Serum parameter problem] Filter cutoff and other Serum params not exposed to Ableton (only 37/127 verified contracts; cutoff missing) | Ableton Configure mode limitation | Automation of raw Serum knobs impossible; workaround via Macro routing required
- [Als XML injection] Injecting Serum state into .als XML causes reopen failure "Unknown Compound Stream Type" | XML serialization of plugin state unsupported | Lost project files; must avoid
- [Fabricated render tool] `render_to_file` tool does not exist (found fabricated in probes) | False assumption in earlier planning | Cannot automate offline render; must use real-time routes
- [No offline export] Ableton API lacks offline bounce | API limitation | Render takes 1 min (owner) or 75 s + setup (MCP record) per 70 s reel
- [Missing first-test pack] Kaliya Mardan has no committed pack on any branch | Pack not prepared | Cannot use as first test target; must use Kalika Puran Reel 1 SHOT-001–003

ORDER-PROBLEMS:
- None in this slice (the slice describes the intended scoring pipeline order: voice time_range known → score planned to gaps → render → Gate D mix; no step is documented as running before its dependency)

ARCH-CHANGES:
- Add Macro routing contract: NL-to-Serum generator must write every preset with Macros 1–4 pre-routed (1=brightness, 2=motion, 3=width/detune, 4=space) so Ableton only automates 4 macros + volume per track
- Add fallback synth stage: on Serum load failure, auto-load Ableton Wavetable/Drift (all params MCP-visible), log in build_log.json, never silent
- Add preset bible gate: generate preset briefs once per story → store in presets/ → list in bible → reuse every reel (consistency via reuse, not regeneration)
- Add three owner gates as mandatory sequence: M0 (bible approval) → M1 (spotting plan + MIDI audition) → M2 (final listen with Gate D preview); automatic checks (length, peaks, cuts, hits, voice windows, presence, silence, continuity) must pass before M2
- Add Gate D contract change: post.py passes manifest track (not None) to enable score mixing with ducking ratio 6
- Add file handoff contract: repo keeps cue_sheet.json, score_plan.json, notes/*.json, preset briefs, manifest; Google Drive gets WAVs and .als (Rule 14)
- Add first-test definition: Kalika Puran Reel 1 SHOT-001–003 (0–18 s) as mandatory smoke test covering reveal, expression-beat, suspense, hard cut, act change before full 70 s build

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 4/4
PROBLEMS:
- [reel length mismatch] story_plan.json says Reel 1 68.0s but 10 shots sum to 70.0s; score follows shots (70.0) unless owner overrides | conflicting duration sources | not stated
- [audio decision conflict] main frozen plan (2026-11-06) says music removed; v4 handoff (2026-11-07) says one optional BGM track; this plan assumes 11-07 rule | two authoritative docs disagree | not stated
- [Live API gap] Live API cannot write locators, tempo, time signature (web check 2026-11-09); plan uses clock mode + MARKERS track workaround | API limitation forces non-standard mode | not stated
- [MCP connection unverified] Step 1 unchecked: Claude Code cannot list extended MCP tools from D:\ableton or NL-to-Serum interface; adapters unwritten | PC not linked / MCP not pushed | not stated
- [NL-to-Serum tool unidentified] Owner has not named tool folder/repo or output format (.SerumPreset vs Live state) | missing tool contract | not stated
- [MCP capabilities unconfirmed] Clip automation envelopes exposure and Serum Macros 1-4 response unconfirmed | unknown if build step 7 can work | not stated
- [Style decisions pending] Modern style, D minor, character themes, Indian colour all await gate M0 | M0 gate blocks step 3 | not stated
- [Gate M0 unchecked] Step 3 (music_bible.json + motif auditions) blocked on owner gate M0 | dependency on owner | not stated
- [Gate M1 unchecked] Step 4 (score_plan.json) blocked on owner gate M1 | dependency on owner | not stated
- [Gate M2 unchecked] Step 8 (Gate D preview with real clips + voice) blocked on owner gate M2 | dependency on owner | not stated

ORDER-PROBLEMS:
- [music composition before voice timing] Steps 3-7 (music_bible, score_plan, notes, presets, ableton_build) compose music to fixed shot lengths (70s) before step 8 preview with real voice clips; voice windows checked in step 5 but voice audio not yet generated/approved | video/shot timing drives music instead of voice driving both | -
- [shot lengths fixed before voice approval] Shot durations (sum 70s) treated as immutable input to score; voice generation/approval happens later in pipeline (step 8 preview) | shot table spec finalized without voice length contract | -
- [story_plan vs shots out of sync] story_plan.json (68s) and shot table (70s) disagree before any audio gate; both treated as valid in different steps | no reconciliation gate between story and shot planning | -

ARCH-CHANGES:
- Add mandatory "Voice Lock" gate before shot lengths finalize: voice clips generated, approved, durations frozen → only then shot table and score_plan allowed to proceed
- Move music composition (steps 3-7) after Voice Lock gate; score_plan.json must consume voice durations as hard constraints, not shot durations
- Add automated CI check: story_plan.json reel_seconds == sum(shot_durations) == sum(voice_durations) with tolerance; fail build on mismatch
- Resolve audio decision to single source: deprecate 2026-11-06 "music removed" rule or 2026-11-07 "optional BGM" rule; record decision in core.json
- Make Step 1 (MCP connection + adapter validation) an explicit gate with automated test; block steps 6,7 until gate passes
- Make M0 (style bible) a hard file gate: music_bible.json cannot be written until owner signs off on style JSON schema
- Add "contract file" handoff: voice_windows.json (generated at Voice Lock) → consumed by cue_sheet.py, score_plan.py, write_notes.py as immutable timing contract
