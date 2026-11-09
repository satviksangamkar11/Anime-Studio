# Nemotron Super slice reviews

## blot.md rules part 1/4
**PROBLEMS**
- R1: log lines skipped → context lost when session/account changes | root cause: skipping lines | cost: context lost
- R4: Colab calls happening despite ban | root cause: not stated | cost: not stated
- R5: review round not followed by second review of fixes | root cause: not stated | cost: not stated
- R6: prompts sent to agents without prior review | root cause: not stated | cost: not stated
- R7: colour work running in parallel with coder owning style.css/index.html | root cause: not stated | cost: not stated
- R8: endless review rounds | root cause: not stated | cost: not stated
- R9: UI not tested at 375/1280px in both languages before done | root cause: not stated | cost: high defect
- R11: renders and Opus calls happening despite ban | root cause: not stated | cost: not stated
- R12: Dots reviewer too slow | root cause: Dots is slow | cost: slow reviews
- R13: stories without explicit style pack | root cause: not stated | cost: not stated
- R14: C: nearly full, D: only a few GB free; Google Drive not yet reachable (no connector, no desktop drive letter) | root cause: heavy outputs on local disk + no Drive connector | cost: disk full; heavy outputs wait or use D: only with owner OK
- R15: agents stalled (Haiku xhigh stalled twice on 2700-line pipeline.js) | root cause: Haiku xhigh on big UI files | cost: replace agent (use Sonnet high)
- R16: web context missing for story accuracy | root cause: not stated | cost: not stated
- R17: blot.md copies in worktrees go stale | root cause: not synced on rule change | cost: stale copies
- R18: hidden "More" folds / hash-only links / hover content hiding needed facts from 60-year-old user | root cause: not stated | cost: not stated
- R19: off-style bible passes without repair | root cause: style only named, not enforced | cost: fails and gets repair call
- R20: two control-character slips (real newline inside a string; backspace inside a regex) after script edits | root cause: python heredoc edits | cost: file parse failures
- R21: flow packet missing items → `ui/test_packet_and_roots.py` fails | root cause: not stated | cost: test fails
- R22: non-Kaliya stories not working end to end | root cause: not stated | cost: not stated

**ORDER-PROBLEMS**
- none in this slice

**ARCH-CHANGES**
- R1: add `PROJECT_LOG.md` — append-only "LIVE LOG" (one line per step, blot.md format) + overwriteable "NOW" block (≤8 lines); new session reads NOW first, then last 20 LIVE LOG lines, then checklist
- R2: add `CHECKLIST_ARCHITECTURE_2026-11-07.md` — tick `[x]` only when step done AND verified; log each tick
- R3: agent brief contract — must append blot.md-format log lines after every step, owns named files, never commits/pushes
- R6: gate before dispatch — Super VL + Xing (free) review every prompt/instruction file, triage, fix, re-review (R5), only then send; prompts saved as `research/_prompt_*.md`
- R8: review cap — one pass + one check of fixes; round with no HIGH finding ends review
- R12: reviewer contract — Nemotron 3.5 Super VL + Xing (OpenRouter free), runner `research/_run_uifinal_reviews.py xing|supervl`; Dots dropped
- R13: `core/core.json` key `default_style_pack` = `deva_neon`; writer/new story.json/UI read from there; UI style chooser in step 1 + `GET /api/styles`, `POST /api/story/<slug>/style`
- R14: heavy outputs → Google Drive; `flow_outputs`/render outputs point there; local only as fallback; never upload `secrets/`
- R15: agent stall gate — no log line for 20 min = stalled, replace (Sonnet high for big UI files); brief demands log line every 5 min
- R16: `write_pack.py --web` on for every model; Claude uses live WebSearch/WebFetch; free models get per-story `WEB_NOTES.md` (Haiku, low effort, web search); SOURCE stays authority
- R17: blot.md synced in same step as rule change (both copies: `anime_studio` and `anime_studio_merge`)
- R19: gate STYLE-01/STYLE-02 (`style_pack_errors`) before image work; writer receives whole style pack via `style_rules()`; `MASTER_PROMPT_v2.3.md` rule 8 defers; `_look_rules` with test for new style pack fields
- R20: post-scripted-edit check — file parses + no control chars (`grep -c $'\x08\x0c'`, `ast.parse`, `node --check`); prefer Edit tool for code with escapes
- R21: story folder contract — `flow_outputs/anime_<slug>` (`server.flow_root`); packet carries project link, aspect, edit base, neighbours, safety stops, fix loop, reviewer commands, queue, progress, phase-2 2K download; `ui/test_packet_and_roots.py` gate
- R22: gate — any story other than Kaliya must work end to end
- R9/R18: UI contract — English + Marathi only; v2 colour guide wins; controls MOVED, never hidden; done only after browser test at 375/1280px both languages + cold test `research/UI_COLD_TEST_*.md` with no high defect

## blot.md rules part 2/4
### PROBLEMS
* **RULE 23:** Kalika stage 2 lost its first part of a long answer | plain json result kept only the last turn of

## blot.md rules part 3/4
PROBLEMS:
- Rule 37: Disk C: reached 0 GB free | root cause: insufficient disk space | cost: commands began to fail, cleanup freed 1.30 GB.
- Rule 38: Audio fit estimation failed; 19 of 32 clips over slot, up to 2.6x | root cause: relying on words-per-second instead of measurement | cost: needed to measure seconds per character and adjust text or tempo.
- Rule 39: Voice windows sized to whole clip wrong for 14 of 54 lines | root cause: incorrect basis (clip length vs editorial length) | cost: rewrote 8 lines and regenerated.
- Rule 40: Render S009 failed 3x | root cause: not checking URLs before paid session; download issues like HTTP 504 | cost: failed renders, wasted resources.

ORDER-PROBLEMS:
- Render started before audio was generated and measured (Rule 37) | what ran too early: render | should have waited for: audio generation and

## blot.md rules part 4/4
PROBLEMS:
* **RULE 46 Amendment / Rule 42**: FINAL_TEXT_v2.json windows were used as speech windows, but they are permission windows only (wrong for 14 of 54 lines) | Root cause: confusion between permission windows and actual speech windows | Cost: required correcting the score to read real speech from `vo_tracks_report.json` and rebuilding into `final_reel1_v4`.
* **RULE 48**: Stock-synth sketches and default Ableton patches were sent to the owner | Root cause: using default/stock patches instead of produced, royalty-free samples | Cost: owner rejection ("sounds shit"), requiring rework with owner library samples.
* **RULE 48 (5)**: An agent reported the target value as the measurement instead of verifying levels from written files | Root cause: reporting target values instead of actual measurements | Cost: potential mix errors and wasted verification steps.
* **RULE 49 (3)**: The chroma key estimator is blind below 65 Hz | Root cause: frequency limitation of the estimator | Cost: bass falls back to 808/sub one-shots pitched to the nearest D with |shift| <= 5 st.

## MISTAKES_AND_LESSONS part 1/3
PROBLEMS:
- C1: results folder did not exist, final download failed, six clips lost | clips fetched only at end, local folder never created, download step not tested | a full G4 session of rendering, a second A100 session
- C2: A100 re-render failed with HTTP 429 and hang | no HF token, no retry, unproven GPU chosen | an A100 session, 0 clips
- C3: run.py was 19.7 MB, `colab exec -f` hung, script never reached GPU | no proof script started, script size limit unknown | 1.68 units, G4 billed for 13 minutes
- C4: same hang with 11.3 MB script | size fix was a guess, not tested | 0.57 units
- C5: G4 session terminated 2 minutes into install | owner's browser notebook looked like ours, no clear session rule | about 0.3 to 0.9 units
- C6: every shot failed in 10 seconds (rc=1) due to blank line in prompt | prompt layout never run on GPU before full batch | about 0.9 units, 15 minutes
- C7: forgotten or looping runner, fetch split `FILES.txt` on spaces, session not stopped | untested with real file names | extra billed minutes
- C8: Opus writer stage 2 lost first 90% of answer | CLI `result` kept only last turn | 2.62 USD
- C9: Opus "repair" rewrote stage as 11 shots and failed | repair prompt let model rewrite whole answers | one Opus call, failed stage
- C10: Claude weekly limit hit during Opus stages | all heavy writer work on one subscription, no budget watch | blocked work for days
- F1: keyframes accepted from reviewer verdicts and thumbnails, defects at full size | reviewer is advisory, small captures hide defects | many hours, about 150 Flow submits
- F2: A and B keyframes made as separate generations, disagree | A/B treated as "pick the better" instead of start and end frame | video has to invent the change
- F3: long misunderstanding about A and B being options vs. start/end frame | not explained in packet and UI | rework rounds
- F4: regenerating images with long prompts repeatedly | no rule for reworks | 5 submits for 1A, 8 for 6A/6B
- F5: chip rules: `@` picker listed old tiles next to exact name, agents picked wrong one | duplicated and stale names, UI quirks | agents stopped or picked wrong tile
- F6: browser tabs: pane cap of 9 tabs, agents left tabs open, one agent renamed whole project | no tab discipline | three download agents could not start
- F7: 2K download: four Haiku agents got null captures for 20+ minutes due to wrong click coordinates | coordinate clicks without screenshot | hours of review time
- F8: Flow project signed out in pane, agents started/stopped without owner knowledge | no sign-in check before launching agents | agents reported "done" or "blocked" falsely
- F9: edit ids in notes did not match gallery, agent lost time | ids copied from partial notes | agent lost time searching
- F10: watermark detector found no sparkle in 4 of 20 images, 6A had ghost star | threshold tuned on dark images, edits copy watermark | rework needed
- F11: wrong GPU named in memory (A100 vs. G4), owner and I argued | memory written from plans, not run log | fixed the note
- P1: Python heredocs turned `\n` into real line breaks (at least 8 times) | use of heredocs for code with backslashes | broken files caught late, wasted rounds
- P2: shell wrapper hid 2 failing Gate D tests, push went out | tests not read through wrapper | bad push to fix
- P3: log lines for steps that did not happen (e.g., "applied fixes" after failed script) | correction not treated as new FIX line | wrong state believed
- P4: killing processes by command-line pattern matched own shell, command exited 255 | kill by PID not found first | lost minutes, session left running
- P5: reviewers: Nemotron Super spent tokens thinking, Xing returned thought traces, OpenRouter hit 429 when run together | slices too large for Nemotron, reviewers run together | hours of review time
- P6: pipeline built around first story (Kaliya): hard-wired folders, patterns, style chip, no GPU path for V4 rows | no per-story customization | two audits found 44 HIGH gaps, closed late
- P7: sound-cue rule SX-01 showed up in render controller after authoring, 6 of 10 shots "not ready" | authoring ran before sound-cue rule applied | authoring ran twice (stale fields)
- P8: "dry run" only prints commands, never tested real chain on one shot before full batch | dry run not a real test | 4 failed starts
- P9: agent briefs and reports trusted too much (sign-in blocks, wrong tab, "done" lines) | not verified against file, gallery, or log | repeated reruns
- P10: owner rules arrived mid-task (send each clip, then don't; Haiku low then high; etc.), I did not stop first | not stopping first on "stop" | wasted calls and sends

ORDER-PROBLEMS:
- F2: A and B keyframes were generated as separate generations instead of B being an edit of A | B should have waited for A to be completed and then edited
- P7: authoring ran before the sound-cue rule SX-01 was applied in the render controller | authoring should have waited for sound-cue rules to be integrated

ARCH-CHANGES:
- Add a stage to save each clip to the PC immediately after its shot ends (R29 from C1)
- Add a gate to prove the script started within 180 seconds of `--go` and check `/content/out` exists (R28 from C3)
- Add a retry mechanism for HTTP 429 errors and stick to proven GPU (G4) without switching unless tested (R30 from C2)
- Merge sound-cue rule application into the authoring stage or add a gate before authoring to ensure rules are applied (from P7)
- Add a one-shot real test (`--ids SHOT-001`) before the full batch run (from P8)
- Implement per-story folders and customization to avoid hard-wiring (from P6)
- Use exact-title rule for tiles, rename then reload, and retire first to avoid chip picker issues (from F5)
- Enforce tab discipline with `tabId` on every action and close tabs of finished agents only (from F6)
- Add a sign-in check before launching agents and have them report stops immediately (from F8)
- Apply rules like streaming JSON with `join_stream` for Opus CLI to avoid losing content (R23 from C8)
- Use the Edit tool for code with backslashes and run `ast.parse` after scripted edits to avoid heredoc issues (R20, R30 from P1)
- Check Claude limit before heavy stages and use free models for authoring and review (from C10)

## MISTAKES_AND_LESSONS part 2/3
PROBLEMS:
- [Q1] Sound notes naming drawable things ("serpents hiss softly") caused cobras to appear in video | prompt carried sound notes with nouns; video model draws every noun it reads | second re-render (~1.2 units, ~30 min) and owner's trust
- [Q2] Judged clip from 16 frames and gave wrong "all clear" | no automatic frame check; human glance at sparse sample | wrong "all clear" given to owner
- [Q3] Compiled H3 prompt had grammar defects, duplicate sentences, broken sentences, pronoun clashes, boilerplate repetition, curly apostrophes, jargon | compiler glues text pieces without a language check | unknown, probably lower clip quality in every shot
- [Q4] Visual prompt had no negative/"only these characters" line despite Flow job prompt having one | H3 layout lacks negative or "only these characters" line | cobras, possible extra figures
- [Q5] Keyframe 8A made without checking against script (Brahma seated all shot) | keyframes reviewed alone, not against shot's own script lines | one full redo of 8A plus a re-render
- [Q6] Voice script never checked for speaking speed before render; 8 Hindi lines ran 3.3–3.6 w/s in slots allowing 3.2 | writer sets time windows and text separately; nothing measures voice | rework of script after clips exist
- [Q7] Never listened to or measured the audio track the video model made | only frames were checked | unknown: may contain speech-like noise, music or silence
- [Q8] Reported "second Flow tile could not be opened" and "Brahma is seated" from agent reports without looking | trusted agent text | wrong state reported
- [Q9] Owner's words guessed more than once (CNET, "E100", "dataset the render", "Hyde haikyu") and acted on guesses | no habit of confirming unclear order before costly action | wasted turns
- [Q10] Rules recorded without being asked (Flow wording rule) then removed | recorded a preference as a rule | a few minutes and noise
- [Q11] Story-fidelity not checked against SOURCE.md; writer grades itself | no independent check | risk of wrong story beats in production
- [Q12] Marathi/Hindi quality checked only by me; no automatic easy-language checker run on final lines; names like मन्मथ, कंदर्प may be mispronounced | no native review step, no pronunciation test | risk of poor audio
- [V1] Logged an edit that never happened (Write of director/voice_library.py blocked by worktree path guard, but log said "EDIT ... done") | did not check with ls (or read result) before logging file as written | (no cost stated)
- [V2] Wrong claim that account has no Hindi voice; saved Granth library shows eight male voices verified for both Hindi and Marathi | did not search saved library before saying voice type does not exist | (no cost stated)
- [V3] Rewrote voice_library.py instead of copying existing code that could be reused | did not copy source/a1_eleven.py first | (no cost stated)
- [V4] Several ElevenLabs preview files were WAV data named .mp3 (RIFF header); phone player shows as silent | wrong header; phone player shows RIFF as silent | (no cost stated)
- [V5] Preview_url is the voice's own demo clip, usually not Hindi/Marathi and never our names; says nothing about pronunciation, speed, or sacred names | preview is not a test | (no cost stated)
- [V6] Pre-flight found five blockers before any credit was spent: 16 of 18 cast voices not in account (Starter has 10 slots); Hindi Victor/Frederick/Edward verified for hi only on eleven_multilingual_v2 not eleven_v4; rate 2.0 voices may cost double; 9 Hindi lines ran 3.24–3.57 w/s against 3.2 limit; hard names untested | did not run free pre-flight before first paid call | (would have cost credits on failed calls)
- [V7] Staging not checked against scripture until after render; SHOT-007 should show Daksha/sages reacting, SHOT-009 should show Shiva present when Kama shoots Brahma; both rendered clips lack them | no check before keyframes | both rendered clips lack required characters
- [V8] C: volume holding Claude's temp folder reached 1 MB free | did not check free space before long jobs | (no cost stated)
- [V9] Words-per-second rule (3.2 w/s) passed on paper but real clips from slow dramatic voices ran 1.7–2.4 w/s; 19 of 32 batch-1 clips overran their slot (up to 2.6x) | did not generate one real line per voice and measure before full paid run | 19 overrunning clips
- [V10] ElevenLabs voice_settings speed 1.15 returned clips of same length (4.08 → 4.16 s); told owner speed + shorter text would solve it before testing | setting not proven until result measured | (no cost stated, but wrong advice given)
- [W1] Sparkle tools only read files named *__candidate_v01.png; v02 images matched nothing; earlier run "wrote nothing, rc=0" misread as tool fault | batch tool finds no input, exits 0, prints nothing | misread as tool fault
- [W2] python -I hides user site-packages (cv2, scipy, torch live in AppData Roaming); raised ModuleNotFoundError | -I flag hides user site-packages | ModuleNotFoundError for cv2, scipy, torch
- [W3] Automatic detector misses faint big ghost star (inherited from F10); alpha-clean and lama_on_clean variants leave scratches on dark cloth and gold steps | detector limitation; only LaMa with both stamp positions forced worked | scratches on dark cloth and gold steps
- [W4] Reviewer key expired unseen; OpenRouter returned 401 only when review ran | did not check each reviewer key with tiny call before review round | (no cost stated)
- [W5] Called old renders (from keyframes 11-08 20:31 and 20:38) "the newest" and sent them while new keyframes existed | did not state which keyframes a clip was made from before sending | sent without saying until owner asked

ORDER-PROBLEMS:
- [Owner concern] Video rendered before voices → voices should be completed first, then video built to the audio length (extra "editorial timeline" repair step was needed)
- [Q6] Voice script speaking-speed check ran after render → voice testing and fitting should happen before video render
- [V7] Staging checked against scripture after render → staging/script check must happen before keyframes are made
- [V9] Full paid voice run started before measuring one real line per voice → voice speed/length measurement must happen before full paid batch
- [W5] Old renders sent as "newest" without verifying keyframe version → keyframe version verification must happen before sending or reporting a clip

ARCH-CHANGES:
- [Q1] Sound notes must never name a drawable thing; describe sound as sound only ("a soft dry rustle"); add a lint on the cues
- [Q2] Add an automatic frame scan: a vision model over every 4th frame that lists characters, creatures, objects, arm counts and compares them with the shot script; human check is the second line, not the first
- [Q3] Add a prompt compiler with grammar and duplicate check; one fixed boilerplate; no repeated sentence; no jargon in the visual part; a prompt quality gate before any render
- [Q4] Add "only these characters, no creatures, no extra objects" sentence to the compiler's visual part
- [Q5] Check each keyframe against the script's position and pose list before using it
- [Q6] Writer measures real or estimated voice length per language and loops until the line fits the slot
- [Q7] Measure level, silence and speech with ffmpeg and a speech detector on every clip; decide keep or replace
- [Q8] Verify against the picture before reporting state from agent reports
- [Q9] Confirm in one line when an order is unclear and the action costs units or sends data
- [Q10] Record rules only when the owner says so
- [Q11] Add an independent story-fidelity pass against SOURCE.md for every reel
- [Q12] Add a short pronunciation test of hard names with the chosen voices before generating everything; add a native listener check
- [V1] Check with ls (or read the result) before logging a file as written; a correction is a new FIX line
- [V2] Search the saved voice library BEFORE saying a voice type does not exist
- [V3] Copy source/a1_eleven.py first (job key, ledger, reuse, ffprobe, measured, export); change only plan loading, languages and paths
- [V4] Check header (ID3/mp3) with ffprobe format_name before sending audio; re-encode to a real mp3 (libmp3lame 128k mono)
- [V5] Test with actual names and text, not preview_url
- [V6] Always run the free pre-flight (account, slots, per-voice verified languages and model, rate, words per second per slot) before the first paid call
- [V7] Check each shot's script against the source for omitted details BEFORE keyframes are made; say what the picture must show
- [V8] Check free space on C: before long jobs; never delete the owner's files without telling them
- [V9] Before a full paid run, generate ONE real line per voice (the hardest slot) and measure seconds against the slot; set voice speed and text length from that measurement
- [V10] Test any quality/speed knob on one cheap clip and measure before promising it as the fix
- [W1] A batch tool must print how many inputs it found and fail on zero
- [W2] Use -I for untrusted data only; plain python for our own tools
- [W3] For watermark/ghost removal: LaMa with both stamp positions forced (small 24 at 161,161; big 48 at 56,56); always look at the corner crop at native size for every variant; verify no change outside the window
- [W4] Check each reviewer key with a tiny call before a review round; fall back to NVIDIA and say so
- [W5] Before sending or reporting a clip, state which keyframes it was made from

## MISTAKES_AND_LESSONS part 3/3
PROBLEMS:
- W6: Two code trees have drifted | no decision on live tree and sync before code fixes | none
- W7: Keyframes made without checking shot script | check not done before approval | none
- W8: Picture reviewer advisory and partly wrong | not verified at full size | none
- W9: "with <cue>" glue still in converter | not fixed at source with test | none
- W10: Free URL check not done before paid sessions | no test of external downloads from this PC | 0.58 units, 3 sessions, 25 minutes
- W11: Runner lost error text | only

## PROJECT_LOG decisions/fails/owner lines part 1/12
PROBLEMS:
- [11-07 01:47 owner line] Voices generated after video render, causing length mismatch; no voice clips supplied | Root cause: Pipeline steps ordered with video render before voice generation | Cost: Not stated
- [11-07 03:48 W1 FAIL] test_stage_1_data_carries_the_selected_languages fails after gate merge | Root cause: LANG-03 from writer fallback | Cost: Not stated
- [11-07 04:57 B1 FAIL] Core suite collection blocked by other workers' test files | Root cause: Missing modules from other workers | Cost: Not stated
- [11-07 04:57 B4a FAIL] Core suite collection errors in test_lut.py, test_make_lut.py, test_cvd.py, test_pack_rules.py | Root cause: Other workers' files missing modules | Cost: Not stated
- [11-07 04:57 B5 FAIL] Core suite collection errors after 60s wait | Root cause: Core modules missing from other worker | Cost: Not stated
- [11-07 04:59 B8a FAIL] ImportError in test_retention_report.py | Root cause: retention_report module missing from other agent's file | Cost: Not stated
- [11-07 08:25 A25 FAIL] Linter 15 ERRORs in test_convert_deva_h3.py | Root cause: Template/registry content issues (KF-02, SD-01, CM-01, PR-05) | Cost: Not stated

ORDER-PROBLEMS:
- Video render ran before voice generation; it should have waited for voices to be completed.

ARCH-CHANGES:
- none in this slice

## PROJECT_LOG decisions/fails/owner lines part 2/12
PROBLEMS:
- [11-07 08:39] dots attempt 1 empty (token budget) | root cause: token budget exceeded | cost: retry at 48000
- [11-07 08:49] unmocked call_path hit NVIDIA endpoint with fake model (HTTP 404, no paid) | root cause: probes not mocking calls | cost: no paid, but fixed by mocking
- [11-07 10:33] r3 test pins PLAN-01 for captions_by_lang string; reverted that guard | root cause: guard reverted | cost: already an error entry
- [11-07 12:57] one transient failure in first final run (581 pass, 1 fail) | root cause: transient, not reproduced | cost: total now 590 pass
- [11-07 13:20] collection error blocks full core run after wait | root cause: not mine, reported under REQUESTS | cost: blocks full core run
- [11-07 13:20] correction: last AGENT-DONE said 325; actual core run excluding caption_text = 331 pass, 1 skip | root cause: misreporting | cost: incorrect pass count reported
- [11-07 16:12] previous push ce74e37 went out with 2 failing Gate D tests; my wrapper hid the failure | root cause: cue-layer hardening coerced malformed blocks silently | cost: fixed by raising clear ValueErrors; h3+core 1033 pass
- [11-07 17:03] 8 selectors target removed #wiz-panels (dead CSS) | root cause: dead CSS | cost: not a visible fault
- [11-07 17:04] Gate A Approve enabled while stale-server banner says restart first | root cause: safety gap | cost: not stated
- [11-07 17:05] Images Shots tab shows [object Object] in Q1-Q6 cells | root cause: fillReview String of object | cost: not stated
- [11-07 17:07] phone Advanced toggle click did not expand | root cause: mis-target on a Runs row | cost: not stated

ORDER-PROBLEMS: none in this slice

ARCH-CHANGES:
- probes now mock calls to avoid unmocked endpoints (from 11-07 08:49)
- raise clear ValueErrors instead of silent coercion to prevent hidden failures (from 11-07 16:12)

## PROJECT_LOG decisions/fails/owner lines part 3/12
PROBLEMS:
- [11-07 17:59] Write blocked by worktree path guard | root cause: worktree path guard | cost: both reviewer runs failed
- [11-07 18:47] Edit script failed due to backslash escapes | root cause: backslash escapes in script | cost: no change made
- [11-07 19:12] File not written due to worktree path guard | root cause: worktree path guard | cost: report delivered in handback text instead
- [11-07 19:27] Key-check command started Python REPL by mistake | root cause: command error | cost: hung, stopped, redoing as script
- [11-07 19:27] First background pytest left no output and no process | root cause: not stated | cost: rerunning with output to scratchpad
- [11-07 19:48] tokens.css ignored by .gitignore | root cause: .gitignore pattern '*token*' | cost: not changed, lead must add negation or force-add
- [11-07 20:20] write_pack.py story argument must be SOURCE.md path | root cause: wrong argument type | cost: retrying with correct path
- [11-07 21:00] UI bug: error 'Save the languages first' always shows at step 2 | root cause: not stated | cost: not stated
- [11-07 21:52] Stray 'cat >> /dev/null' command hung on stdin | root cause: stray command | cost: stopped, nothing else lost
- [11-07 21:56] coderW and coderE stopped by user, cannot be resumed | root cause: user interruption during Assay | cost: work cancelled, partial uncommitted edits remain

ORDER-PROBLEMS: none in this slice

ARCH-CHANGES:
- Use relative paths from V4 tree to avoid worktree path guard blocks (from 11-07 17:59 fix)
- Add .gitignore negation pattern or force-add for tokens.css (from 11-07 19:48)
- Enforce SOURCE.md path argument for write_pack.py or fix script to accept slug (from 11-07 20:20)
- Merge coder S into W2 (frontend) and E2 (backend) to save a stage (from 11-07 22:01)
- Add review gate: reviewers must approve before sending prompts/instructions to coders (from 11-07 17:56)
- Add final review pass by free Super VL+Dots before agent dispatch (from 11-07 18:55)

## PROJECT_LOG decisions/fails/owner lines part 4/12
FAILED after 3 tries: ERR 'choices'

## PROJECT_LOG decisions/fails/owner lines part 5/12
FAILED after 3 tries: EMPTY None

## PROJECT_LOG decisions/fails/owner lines part 6/12
FAILED after 3 tries: EMPTY None

## PROJECT_LOG decisions/fails/owner lines part 7/12
PROBLEMS:
*   `[11-08 20:16 / R1, R2, R3] Flow pane signed out / redirect to /about` | Owner was not signed in to Google Flow in the pane | Stopped all jobs (0/4 done), wasted turns.
*   `[11-08 20:37 / R1] review_shot.py cp1252 UnicodeEncodeError` | Printing Devanagari characters without UTF-8 encoding | Required rerun with `PYTHONIOENCODING=utf-8`.
*   `[11-08 21:13 / R5] Gallery title alias (SHOT-001A__v01 on edit 1f1d26c1 vs 8aa727e3)` | Stale/alias title mapping in gallery | Required manual verification of keeper tile before renaming.
*   `[11-08 21:15 / R5] Misclick on (250,667) opened retired tile a1019a88` | Incorrect coordinates or stale DOM state | Typed text into retired tile's edit box (no submit, wasted actions).
*   `[11-08 21:19 / R5] Tile B thumb fetch with s1600 failed decode` | Image fetch/decode failure | Forced visual judgment from gallery zoom instead of full-size inspection.
*   `[11-08 21:22 / me] SHOT-001A a200e328 rejected (wink, crown dominates)` | Visual defect (wink look, crown too large, not eye close-up) | Required regenerating the shot (3 submits left).

ORDER-PROBLEMS:
*   `[11-08 20:16 / R1, R2, R3] Flow jobs launched before owner sign-in was completed` | Ran too early: agents attempted to run jobs on a signed-out project | Should have waited for owner to sign in to Flow in the pane first.
*   `[11-08 21:13 / R5] Renaming/clicking tiles before verifying unique title mapping` | Ran too early: attempted rename and clicks before resolving the `1f1d26c1` vs `8aa727e3` alias | Should have waited for title uniqueness verification.

ARCH-CHANGES:
*   `[11-08 20:17 / me] Owner Sign-in Gate` | Add a mandatory owner authentication/sign-in gate in the Flow pane before launching any project agents.
*   `[11-08 20:37 / R1] Encoding Configuration Gate` | Set `PYTHONIOENCODING=utf-8` environment variable globally for the review scripts to prevent UnicodeEncodeError.
*   `[11-08 21:21 / me] Title Uniqueness Verification Contract` | Add a pre-phase-2 (pre-download) gate to verify unique gallery titles and resolve aliases before 2K download and watermarking.
*   `[11-08 21:25 / me] Model Routing and Cost Control Gate` | Restrict reworks to Nano Banana PRO while keeping standard shots on 2.1, with a hard-stop gate on any payment/upgrade prompt (logging model + credit cost).

## PROJECT_LOG decisions/fails/owner lines part 8/12
PROBLEMS:
- [11-08 21:42] D3/L1/L4 tab cap reached (9 flow tabs) | root cause: too many open tabs | cost: 0 shots downloaded, stopped
- [11-08 21:44] L2 SHOT-004A download failed (window.__dl null) | root cause: no file captured | cost: no file
- [11-08 21:45] L2 SHOT-003B download failed (no blob) | root cause: no download request in network log | cost: stopped
- [11-08 21:46] L4 SHOT-009A download failed (no capture in 20s) | root cause: hook state? | cost: moving on
- [11-08 21:48] L2 all 5 shots failed (capture null each time) | root cause: window.__dl null | cost: 10 of 20 filed, shots moved
- [11-08 21:48-21:55] L1/L3 multiple shots failed (no capture after multiple tries) | root cause: recipe issues, no capture | cost: shots not filed, retry later
- [11-08 22:30] h3_author failed (Claude weekly usage limit 429) | root cause: usage limit | cost: nothing written, fell back to free model
- [11-08 23:21] Render dry run: only 4/10 shots ready, SX-01 errors, no GPU backend wired | root cause: not all shots ready, GPU not wired | cost: render not started
- [11-09 00:16] Render failed (run.py 19.7 MB never started, kernel idle) | root cause: file too large? local exec stuck | cost: ~2 units spent, need to shrink
- [11-08 23:20-23:37] Render started before cross-check and fixes | root cause: premature start | cost: wasted units, needed to stop and fix

ORDER-PROBLEMS:
- Render started at 11-08 23:20 before cross-check and fixes were done (dry run showed only 4/10 shots ready, GPU not wired). It should have waited for all shots ready and GPU wired.

ARCH-CHANGES:
- Add a gate that requires all keyframes downloaded and GPU backend wired before starting render.
- Enforce a review pass (R1, R2, Super VL) before render start.

## PROJECT_LOG decisions/fails/owner lines part 9/12
PROBLEMS:
- [11-09 01:10] Render session terminated prematurely | owner closed extra notebook | no clips, balance 185.30, browser T4 still running
- [11-09 01:22] Prompt parsing error due to blank line | blank line in H3 prompt | ~0.9 units spent (184.86)
- [11-09 02:50] Visual defect: snakes appearing | sound cues in prompt | re-render needed
- [11-09 03:01] Render started without reading script | didn't read script | stopped render, runner killed, defects found
- [11-09 05:12] Incorrect click opened wrong tile | click mistake | no edits
- [11-09 05:21] Rename not saved | rename failure | none
- [11-09 05:22] Rename not saved | rename failure | none
- [11-09 05:30] Download failure | window.__dl null | none

ORDER-PROBLEMS:
- Video rendering ran before voice generation (render attempts 3-6, SHOT-008 re-renders) | should have waited for voice generation and audio sync
- Render started before full script review (03:01) | should have waited for script review

## PROJECT_LOG decisions/fails/owner lines part 10/12
FAILED after 3 tries: EMPTY None

## PROJECT_LOG decisions/fails/owner lines part 11/12
PROBLEMS:
- [11-09 13:40] music_bible SHIVA theme D2-D3 all <200 Hz = silent on phones at peak | low notes below phone playback range | octave-up doubling fix applied
- [11-09 13:33] test_note_writer.py C29 red before impl: partners test fails (no partner notes) | incomplete implementation | test failed
- [11-09 15:10] final_reel1_v4 Gate D VO_OVERFLOW_ERROR shots 5/7/8 all langs: padded VO file = editorial-0.10 exactly, frame-based editorial rounds up one sample | frame rounding vs sample-accurate padding mismatch | extra editorial step needed
- [11-09 15:35] note_writer rejects plan_check transitions theme_handover, key_colour_on_downbeat: vocabulary clash | cut vocabulary differs between plan_check and note_writer | forced swells on 5 soft cuts (style fault)
- [11-09 16:30] sound_select.py crashed on zero centroid (silent sample) in zone_score | no guard for silent samples | crash
- [11-09 16:33] 4 empty slots (S5-groove, S5-bass, S6-bed, S7-bass): cap 30 consumed by clipped/key-failing files; 6 s snippet key re-measure noisy on bass | key measurement too short/aggressive on bass | empty slots
- [11-09 16:54] v3 build S3 indian stem -53 dBFS (<-40) and windows 14-15 at -30.7/-27.1 (riding clamp +12) | per-slot level not adjustable | out-of-spec audio
- [11-09 16:58] v3 rebuild 2: S8-bed outro bed -37.8 dBFS, window still -26.0 | level fix insufficient | out-of-spec audio

ORDER-PROBLEMS:
- [11-09 13:40] style study GA43TUfaKAxzBJRD1cDFiP attempted before owner uploaded it (Docs read=access deny, Artifact read=not found) | music_bible direction errors found while working without the study | 11 direction errors had to be corrected after the fact
- [11-09 13:33] test_note_writer.py C29 red before impl: partners test fails | test written before implementation existed | test failure
- [11-09 15:10] final_reel1_v4 built before editorial timing applied (new_editorial_sec) | video built with wrong shot lengths | VO_OVERFLOW_ERROR on build
- [11-09 16:30/16:33] sound_select.py first full run before guards added (zero centroid crash, relax logic on wrong layers) | selection ran with unvalidated code | crashes, wrong results, empty slots

ARCH-CHANGES:
- Add readback after each mutation (recipe currently has only get_session_info readbacks) — per Ableton CLAUDE.md rules 4/6/8/10/11/12
- Add guard for zero centroid in zone_score (silent sample crash)
- Restrict relax logic to Indian-required layers only (not modern layers)
- Measure key beyond cap up to 300 until 12 scored (instead of 6 s snippet at cap 30)
- Add per-slot level_db control via SLOT_LEVEL_DB (S3 +15, S8-bed +12→18)
- Apply plan new_editorial_sec to shots before build_episodes (editorial timing must precede video build)
- One shared cut vocabulary for plan_check and note_writer (currently differ: theme_handover, key_colour_on_downbeat vs accepted set)
- Add key measurement (chroma) for every tonal sample with D minor/F major only, shift <= 3 st else reject, re-measure stems, key report in sample_log
- One shared timeline en/hi/mr with each shot = largest need, whole beats for 3,4 (128) and 6,7,8 (176), capped by spare frames, voice <= 1.03x

## PROJECT_LOG decisions/fails/owner lines part 12/12
PROBLEMS:
- [SMP2 FAIL] Problem: restore stems failed due to wrong path. Root cause: first copy used wrong path. Cost: stems/ removed then restored from backup.
- [ABL2 FAIL] Problem: create_clip refused because clip slot already has a clip. Root cause: no delete-session-clip or clear-notes tool exists. Cost: nothing written, no arrangement clip deleted.
- [SFX1 FAIL] Problem: onset test failed, clicks 56 ms early. Root cause: log-flux + 2048 frames. Cost: fixed with linear flux, 512 frames; tests passed.
- [EQ1 FAIL] Problem: no sustained clashes detected, no cuts made. Root cause: SUSTAIN threshold 0.25 too high. Cost: noduck pre at -2.7 LUFS clipped.
- [OWNER 18:00] Problem: code outside Ableton led to mixing issues. Root cause: MCP cannot write in Ableton, owner rejected stock MIDI. Cost: mistake not bringing back to Ableton for mixing.
- [OWNER 18:40] Problem: Devanagari spelling not checked properly. Root cause: not specified. Cost: not stated.

ORDER-PROBLEMS: none in this slice

ARCH-CHANGES:
- [OWNER 18:00] Proposed Ableton-native mix, moving the mixing stage to Ableton.
- [OWNER 18:20] Changed render naming convention to preserve each render instead of overwriting (from r5 on).
- [DECISION 23:04] Added second pass for reviewers on reports as a gate.

## docs/PIPELINE_AUDIT_2026-11-07.md part 1/2
PROBLEMS:
- [1] Two branches never merged | root cause: never merged | cost: no single checkout runs the whole path
- [3a] Step 9 QC runner not built | root cause: not implemented | cost: not stated
- [3b] Gate D assembly runner not built | root cause: not implemented | cost: not stated
- [3c] Live author run not built | root cause: not implemented | cost: not stated
- [3d] Pre-render controller has no GPU backend wired | root cause: not wired | cost: not stated
- [4] Nothing rendered for production | root cause: not part of controller; T0 test only | cost: not stated
- [5] No story gone through finished pipeline | root cause: Kaliya pack doesn't exist; old shots fail P2 | cost: not stated
- [6] Two caption engines exist | root cause: not unified | cost: must be unified at merge
- [7] Style packs structurally complete but not measured | root cause: no measured Lab value, no LUT file, etc. | cost: not stated
- [8] Dots unreliable on long inputs | root cause: unreliable | cost: some batches covered by Super VL only

ORDER-PROBLEMS:
none in this slice

ARCH-CHANGES:
- Merge branches v4-architecture-2026-11-07 and universal-v1.1 to resolve conflicts and enable a single pipeline checkout.
- Build the Step 9 QC runner as a mandatory gate after assembly.
- Build the Gate D assembly runner to handle audio plan integration before video rendering.
- Implement the live author run for end-to-end pipeline validation.
- Wire the GPU backend to the pre-render controller for production rendering.
- Unify the two caption engines into a single module to avoid duplication.
- Measure and populate style pack values (e.g., Lab values, LUT files) for all packs.
- Add a length check for Dots inputs or default to Super VL for long inputs to ensure reliable reviews.

## docs/PIPELINE_AUDIT_2026-11-07.md part 2/2
PROBLEMS:
- [6.1] Merge not done: 4 conflicts, 8 hunks | root cause: separate branches developed independently | cost: after merge, need to run all suites, wire gates, replace caption code.
- [6.2] No production render or real post.py run | root cause: not started | cost: limits (G1/G2 dE 6, G3 dE 8, static 3.5/4.0 s) not tuned, LUTs unchecked on real frames.
- [6.3] Style packs unmeasured | root cause: no approved plates or reference frames for tools like measure_plate, make_lut, calibrate_sat_ceiling | cost: G1 skipped with warning, no LUT files (post.py falls back to pack grade numbers), braj_earth has no grade numbers (ungraded export), G2 uses provisional 181.02 with warning.
- [6.4] V4 runners not built (Step 9 QC runner, Gate D assembly runner, live author run) | root cause: functions exist but not implemented as runners | cost: pipeline stages incomplete.
- [6.5] Render backend not wired into controller | root cause: incomplete integration | cost: rendering may not function properly.
- [6.6] Paid ElevenLads parser and karaoke path exist but API shape unverified | root cause: based on public documentation, not tested | cost: any live use risks failure.
- [6.7] Story work not started (writer run, caption text, hook words, Kaliya defects, Mahadev fourth reel) | root cause: by instruction | cost: production delayed.
- [6.8] Manual checks from spec 6.4 not done | root cause: not performed | cost: LUTs not approved on 3 stills per act, episodes not reviewed on D65 monitor and phones, caption placement unchecked against platform overlays, DEVA publish gate not run.
- [7] Caption widths over-estimated for Devanagari conjuncts | root cause: Pillow basic layout used (no libraqm) | cost: line breaks may differ from real render.
- [7] Caption size defaults (34 px at 1080 wide, outline 8%) and safe zones are tune values | root cause: not calibrated | cost: may not fit platform requirements.
- [7] Free reviewers: Dots returns empty answers on long inputs; Super VL occasionally cites unseen code | root cause: tool limitations | cost: findings may be incomplete or incorrect (checked by hand).
- [7] Automatic log hook not firing in this session | root cause: needs new session | cost: logging unreliable.
- [7] Stale docs on V4 branch (STATUS.md shows older suite counts) | root cause: not updated | cost: misinformation.

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- [8.1] Merge the two branches: resolves conflicts, unifies caption engine (replace Gate D's code with core/captions.py and caption_export.py) | stops recurrence of code duplication and integration issues.
- [8.2] Build the three V4 runners (Step 9 QC runner, Gate D assembly runner, live author run) | completes pipeline stages for automated execution.
- [8.2] Wire the controller to the render backend | ensures rendering is integrated and controllable.
- [8.2] Approve plates for measure_plate, make_lut, calibrate_sat_ceiling | enables measurement of style packs and LUT creation, preventing ungraded exports and warnings.
- [8.2] Run first render of one episode before limit tuning | ensures limits are based on real data.

## docs/AUDIT_2026-11-08_REEL1.md part 1/1
PROBLEMS:
- Gap 1: pack_to_spec refuses V4 shots ("unsafe set id None") | root cause: V4 rows lack shot.set, shot.cast, shot.props, shot.keyframes | cost: not stated
- Gap 2: H3 prep has 73 lint errors (missing authored fields, timing/seam issues) | root cause: H3 author step not run; writer validator misses H3 checks | cost: 20-30% more GPU time per clip due to increased pixel frames
- Gap 3: No speech-rate check before voice (e.g., English SHOT-003 at 4.4 wps) | root cause: only fit check (Gate D vo_fit) requires real wav, forcing paid voice first | cost: not stated
- Gap 4: Retention rules measure on pixel frames (70.8 s) vs editorial seconds (70.0 s) | root cause: two clocks (pixel frames vs editorial length) | cost: rules off by handle frames
- Gap 5: Story gate checks self-graded by writer with no SOURCE.md comparison | root cause: no automated source fidelity validation | cost: not stated
- Gap 6: story.json missing style_pack; check_pack fails P1 (loud) | root cause: writer uses deva_neon without recording default pack | cost: not stated

ORDER-PROBLEMS:
- Speech-rate check (SPEECH-01) should run before voice step, but it was omitted; voice recording proceeded without the check, risking length mismatches.

ARCH-CHANGES:
- Modified pack_to_spec.py to derive image prompts from V4 data (reference_anchors, landmarks, etc.) instead of expecting missing fields.
- Added fit_lattice algorithm in h3/v4_to_h3.py and H3-01 validator rule in pack_validator.py to enforce H3 timing/seam checks before renderability.
- Introduced SPEECH-01 speech-rate gate in pack_validator.py and writer_prompts.py to run before voice step.
- Unified clock to editorial seconds in check_pack.py and core/timeline.py for consistent rule application.
- Added SRC-01 source fidelity check in pack_validator.py to tie story.json to SOURCE.md.
- Ensured story.json records style_pack and check_pack uses the same default in write_pack.py and check_pack.py.

## research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md part 1/1
PROBLEMS:
- [Owner's concern] Video rendered before voices were finalized, causing length mismatch | wrong order: video before audio | extra editorial repair step, voice speed up to 1.12x
- [Cue sheet] Built on v3 lengths instead of v4 | timeline changed from v3 to v4 but cue sheet not updated | music sync issues
- [White-outs] Not recomputed after timeline extensions | placed before final timeline | potential visual misalignment

ORDER-PROBLEMS:
- Video render ran before voice lengths were known | should have waited for voice timings
- Cue sheet creation ran before v4 timeline was frozen | should have waited for final editorial timeline
- White-out placement ran before timeline extensions were known | should have waited for final shot extensions

ARCH-CHANGES:
- Added editorial_by_lang.py to generate a shared frozen timeline JSON (gate M1) before voice/video production
- Added build_vo_tracks.py to produce voice wavs that exactly match the timeline lengths
- Added build_final_reel.py that consumes the timeline and voice report, ensuring video is built to audio length (audio-first)
- Handoff document (this slice) acts as a contract: music producer must re-run cue sheet on v4 lengths and cannot re-render video

## CHECKLIST_ARCHITECTURE_2026-11-07.md part 1/1
PROBLEMS: none in this slice
ORDER-PROBLEMS: none in this slice
ARCH-CHANGES: none in this slice

## STATUS.md part 1/2
FAILED after 3 tries: EMPTY None

## STATUS.md part 2/2
PROBLEMS: none in this slice
ORDER-PROBLEMS: none in this slice
ARCH-CHANGES: none in this slice

## research/AUDIO_PLAN_FROZEN_2026-11-06.md part 1/1
PROBLEMS:
* **Loudness mismatch (up to 14 dB apart)** | Measured differences between clips (e.g., arm A -23.7/-21.1 LUFS, arm D -12.3/-10.2 LUFS) require gain matching before the join. | Root cause: independently generated clips have inconsistent volume levels. | Cost: requires a measurement and linear gain adjustment step (`loudness_plan`) targeting -16 LUFS with a limiter.
* **Inability to share a consistent score** | Independently generated clips cannot share one background score. | Root cause: no shared audio state between renders. | Cost: background music is removed from generation entirely; the owner adds music separately over the finished reel.
* **Audio/vocal drift leakage** | Model drift (such as unwanted music or vocals leaking in) can appear in later clips (e.g., clip 4). | Root cause: variance in model generation across multiple clips. | Cost: requires listening to and QA-checking *every* clip, not just the first; re-rendering affected clips if the owner agrees.
* **Prompt negation warnings** | Proposed negative prompt phrasings (e.g., "No music, no score...") trigger linter warnings. | Root cause: the model's prompting rules avoid negations. | Cost: prompts must use positive wording starting with "Sound effects only:".

ORDER-PROBLEMS:
* none in this slice

ARCH-CHANGES:
* Added a registry `sound_beds` mapping location IDs to a fixed 12-word-or-fewer sound phrase to ensure effect consistency.
* Updated the compiler to inject the location-specific sound bed and effects directly after the "Sound effects only:" prefix in the soundscape.
* Added a new linter rule `SD-03` (next to `SD-01`/`SD-02`) to validate that the soundscape starts with "Sound effects only:" and includes the location's bed when defined.
* Modified `assemble_reel.py` to include a `loudness_plan(measured)` step (pure gain computation targeting -16 LUFS with a true-peak limiter at -1.5 dB), apply 5 ms fades after the gain at every cut, and write measured values to `loudness.json` in the build folder.
* Changed the QA process to perform audio checks on the REAL clips for *every* clip (not just the first) as part of the normal clip QA workflow.
* Established a rule to modify the shared location template (and re-render all clips in that location) rather than patching individual shots when audio issues occur.

## research/VOICE_SYSTEM_DESIGN_2026-11-09.md part 1/1
FAILED after 3 tries: EMPTY None

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 1/4
PROBLEMS:
- [gap 1] Tempo map changed at 41 s, which is neither a hard cut nor an act change | Tempo changes only at act changes; cue sheet solves valid BPMs per act (BUILD 128, DROP 176) | cost not stated
- [gap 2] Re-hook at 26 s was outside the retention window (31.5 to 42.0 s) | Re-hook placed at wrong time; retention window not respected | cost not stated
- [gap 3] Live's API cannot automate song tempo or change time signature | API limitation | cost not stated
- [gap 4] Arrangement locators are read-only | API limitation | cost not stated
- [gap 5] API has no audio export | API limitation | cost not stated
- [gap 6] Gate D supports BGM, but post.py and render_controller pass bgm=None | Wiring not done; manifest not connected | cost not stated
- [gap 7] H3 effects overlap planned hits (bell at 0–0.8 s, 43.0–43.5 s, 48–49 s) | Cue sheet did not list every effect; score filled same band at same moment | cost not stated
- [gap 8] Plan rounded first white-out to 43.1 s | Non-frame-exact timing used | cost not stated
- [gap 9] 60.0 s white-out and end sting fall under speech | Low-hit rule missing; sub/low drum not restricted under voice | cost not stated
- [gap 10] Shiva's reveal at 48 s sits inside drum and bass act | No drop-out on divine reveal; 0.4 s drop-out needed | cost not stated
- [gap 11] Live imports reference video as .mov only | Format limitation | cost not stated
- [gap 12] Whether Serum macros follow clip automation is unverified | Not confirmed before first build | cost not stated
- [gap 13] Hybrid-cinematic or electronic style not chosen | Music bible states style; choice deferred to gate M0 | cost not stated
- [gap 14] Phones roll off below ~200 Hz and play mono when held upright | Phone audio hardware limitation | cost not stated
- [gap 15] MCP tool names unknown (D:\ableton not linked to chat) | PC not linked; adapter written after connection check | cost not stated
- [gap 16] PROJECT_LOG.md lives on PC, unreachable from here | Local file | cost not stated
- [gap 17] story_plan.json says 68 s, shots add up to 70.0 s | Duration mismatch between plan and shots | cost not stated
- [gap 18] Cue sheet v1 reads voice windows from pack, not from rendered voice | Voice not yet rendered when cue sheet was built | cost not stated
- [gap 19] Drums, chants, vocal horns need real recordings | Sample quality requirement; no cleared pack used | cost not stated

ORDER-PROBLEMS:
- [gap 18] Cue sheet v1 read voice windows from the pack (pre-render) before the rendered voice existed; it should have waited for rendered voice timings for v2.
- [gap 17] Score duration followed story_plan.json (68 s) before shots were finalized; it should have waited for the locked shot clock (70.0 s).

ARCH-CHANGES:
- Add a new **Score** stage with four steps (S1 cue sheet, S2 spotting/plan, S3 Ableton build, S4 render + check) inserted between Gate A and Gate D.
- Wire BGM manifest into build step 10 so post.py and render_controller read story.json `"bgm": {"enabled": true, "manifest": ...}` instead of passing `bgm=None`.
- Replace arrangement locators with a **MARKERS MIDI track** (one named clip per shot) because locators are read-only.
- Use **clock mode** (60 BPM, notes at absolute seconds, synced effects in free time) instead of automating song tempo or time signature.
- Build a **cue sheet** (`score/cue_sheet.py`) that lists every effect, hit, voice window, and valid tempo per act, frame-exact, and refuse to build on a shorter or wrong reel clock.
- Apply a **low-hit rule**: sub and low drum only under voice; flag `in_voice` and last word time (69.8 s).
- Add a **0.4 s drop-out** before divine reveals (e.g. Shiva at 48 s) so they never land inside a drum-and-bass act.
- Export picture reference as **.mov** for Live import.
- Verify **Serum macros follow clip automation** before the first build (open item).
- Choose style from the **music bible** at gate M0.
- Use **mono bass**, a **mid harmonic** on every bass note, and a **mono check** for phone playback.
- Write the **adapter** after the connection check (build step 1).
- Follow **shots (70.0 s)** for score duration, not story_plan.json (68 s).
- For cue sheet v2, read voice windows from the **rendered voice** timings, not the pack.
- Use **real recordings** (or cleared packs only) for drums, chants, and vocal horns; never a sample of a film or song.

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 2/4
PROBLEMS:
- Old 60/120 tempo map: 120 BPM suited neither the techno nor the drum & bass experiment; tempo changed at 41 s, a cut that is neither a hard cut nor an act change, breaking its own rule; the re-hook at 26 s fell outside the retention window (31.5–42.0 s).
- (Implied by contrast) Composition was lost when an MCP call failed, a Live set crashed, or a preset changed — because decisions lived only in Ableton.

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- JSON-first rule: every musical decision is written to a JSON file and tested before Ableton is touched. Ableton becomes the playback engine, not the composition tool.
- Separation of planning from execution: cue sheet builder (`score/cue_sheet.py`), spotting planner (Claude Code + `SKILL.md` + `score/plan_check.py`), and note writer (`write_notes.py`) run before the Ableton builder (`ableton_build.py`), which is now a thin adapter over MCP.
- Render + check (`check_score.py`) runs after Ableton build, validating length, clipping, voice-window levels, hit alignment, and gate D presence — a dedicated gate stage before the manifest is written.

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 3/4
**PROBLEMS:**
- [Serum parameter problem] Ableton only sees 127 Serum parameters from Configure mode; filter cutoff was not among the 37 verified contracts → cannot automate raw Serum knobs | root: Ableton's limited Serum parameter exposure | cost: must route Macros 1-4 inside Serum instead of automating raw knobs
- [XML injection] Injecting Serum state into `.als` XML caused "Unknown Compound Stream Type" on reopen | root: unsupported injection method | cost: project file corruption, reload failure
- [Render tool] `render_to_file` was fabricated; no MCP render tool exists | root: tool never existed | cost: must use owner export (~1 min) or real-time MCP record (~75 s+ for drafts)
- [Connection check] Running the set without `get_session_info` first | root: not verifying connection before build | cost: potential build failure

**ORDER-PROBLEMS:** none in this slice

**ARCH-CHANGES:**
- [Serum macro routing] NL-to-Serum generator writes each preset with Macros 1-4 pre-routed inside Serum (1=brightness, 2=motion, 3=width/detune, 4=space); Ableton automates only 4 macros + track volume. Same 5 controls on every preset, every reel.
- [Preset brief system] One text brief per track role per palette, generated once per story, stored in `presets/`, listed in the bible, reused every reel. Consistency from reuse, not regeneration.
- [Fallback path] If Serum load fails, fall back to Ableton's Wavetable or Drift on that track, logged in `build_log.json`, never silent.
- [Dual render routes] Route A (owner export, default, ~1 min) and Route B (MCP record, ~75 s+, for drafts while owner is away) because Ableton has no offline export.
- [check_score.py gate] Automatic checks (length, peaks, cuts, hits, voice windows, presence, silence, continuity) must all pass before M2 final listen.
- [Manifest hand-off] `post.py` passes the manifest track instead of `None` to Gate D; Gate D mixes voice, H3 effects, score (ducked ratio 6) and runs `check_music_presence`.
- [Drive delivery] WAVs and `.als` go to Google Drive, not public repo; repo keeps `cue_sheet.json`, `score_plan.json`, `notes/*.json`, preset briefs, manifest.
- [Owner gates] M0 (music bible, once per story), M1 (spotting plan, per reel), M2 (final listen, per reel) — each a listen or read, never a technical approval.
- [Pre-build verification] Confirm Serum macros respond to automation in Live before the first build.

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 4/4
PROBLEMS:
- none in this slice

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- none in this slice
