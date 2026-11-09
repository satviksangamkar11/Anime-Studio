# Nemotron Super slice reviews

## blot.md rules part 1/4
PROBLEMS:
- [Rule 1] Skipped PROJECT_LOG line | not logged before next step | context lost when session/account changes
- [Rule 10] Worktree copies of PROJECT_LOG.md/blot.md | copies are stale and never written
- [Rule 12] Dots reviewer | slow | slow
- [Rule 20] Scripted edits via python heredoc | control characters slipped in (newline in string, backspace in regex) | two slips on 11-07/11-08
- [Rule 15] Haiku xhigh coder on 2700-line pipeline.js | stalled twice | stall
- [Rule 14] Google Drive unreachable | heavy outputs wait; C: nearly full, D: limited | heavy outputs wait; disk pressure
- [Rule 19] Off-style bible reaches Stage 2 | no pre-gate style enforcement | repair call
- [Rule 21] Flow agent packet missing items | ui/test_packet_and_roots.py fails | test failure

ORDER-PROBLEMS:
- [Rule 7] Colour work before T3/T4 verification | should wait for T3/T4 verified; not in parallel with style.css/index.html coder
- [Rule 19] Image work before bible swatch check | should wait for STYLE-01/STYLE-02 gate and swatch check
- [Rule 13] Assay UI review before style chooser built | should wait for style chooser built and simplification verified
- [Rule 6] Agent prompt/instruction sent before review | should wait for Super VL + Xing review
- [Rule 21] Flow agent starts before packet complete | should wait for ui/test_packet_and_roots.py pass
- [Rule 5] Second review before fixes | should wait for fixes after first review

ARCH-CHANGES:
- Log gate: block next step until PROJECT_LOG line is appended (Rule 1)
- Single log path: prohibit worktree copies of PROJECT_LOG.md/blot.md; use only D:\aai work\anime_studio\PROJECT_LOG.md (Rule 10)
- Reviewer swap: use Nemotron Super VL + Xing only; drop Dots (Rule 12)
- Script-edit gate: ast.parse/node --check/grep control characters after every python heredoc edit (Rule 20)
- Stall watchdog: replace agent after 20 min silence; require log line every 5 min (Rule 15)
- Drive routing: mount Google Drive; point flow_outputs/render outputs there; move heavy files off D: (Rule 14)
- Style gate: Stage 2 blocked by STYLE-01/STYLE-02 style_pack_errors; bible swatch check before image work; new look fields in _look_rules with test (Rule 19)
- Packet gate: flow agent cannot start until ui/test_packet_and_roots.py passes (Rule 21)
- UI done gate: browser test at 375 and 1280 px in both languages + independent cold test before UI task done (Rule 9)
- Instruction review gate: Super VL + Xing review agent prompts/instructions before sending (Rule 6/12)

## blot.md rules part 2/4
PROBLEMS:
- [Rule 23] Kalika stage 2 lost its first part of a long Claude answer | CLI continued in a second turn and plain json kept only the last turn | 2.62 USD
- [Rule 24] Missed PROJECT_LOG.md line after a step | step completed without writing the log line in the same step | backfill required
- [Rule 26] Agent acting without tabId renamed the whole Flow project | missing tabId on agent action | cost not stated
- [Rule 28] First live render attempt burned units for 13 minutes with nothing running | 19.7 MB run.py never reached VM; colab exec -f hung; /content had no out/ or Wan2GP | 13 minutes of burned units
- [Rule 30] Wan2GP refused prompt with blank line, rc=1 in 10 s | blank line inside prompt read as second generation request | failed generation
- [Rule 30] colab exec -f hangs on this PC above about 7 MB | file size limit for local exec | hang
- [Rule 30] Rule 20 slipped 4 times on 2026-11-09 | python heredocs used for code with backslash escapes instead of Edit tool | cost not stated
- [Rule 30] Unnamed T4 in colab sessions costs 1.15 units/h and CLI cannot stop it | session ownership confusion (owner's browser notebook) | 1.15 units/h
- [Rule 31] SHOT-002 loses two arms mid-way; SHOT-008 set morphs (Brahma standing vs seated) and Shiva's hair flickers | start/end keyframe inconsistency | re-render about 2 units per shot
- [Rule 31] Phone/remote viewers cannot receive files over 30 MiB | recipient file size limit | must create _small.mp4 (~3 MB)
- [Rule 31] fetch() splits FILES.txt on spaces while clip names contain spaces | runner bug parsing paths | workaround: read one path per line
- [Rule 31] Runner ends with error but session is kept | runner behavior | must manually check colab sessions and stop it
- [Rule 31] No music score exists yet | Doseedo research stopped on owner's word; nothing installed or called | missing music score
- [Rule 32] SHOT-008 re-render had duplicated last sentence, glued clause, "at seconds 7", and "serpents hiss" drawn as cobras | full compiled prompt not read before GPU start; only blank lines and one word checked | wasted re-render; incorrect visual elements
- [Rule 34] Generic official mouth sentences ambiguous with several people on screen and slightly contradictory | ambiguous/contradictory compiler output | still open (owner decision)

ORDER-PROBLEMS:
- [Rule 32] GPU re-render of SHOT-008 ran before full compiled prompt of every shot was read and before all reviewers read prompt + shot script + run.py | should have waited for preflight review and owner go
- [Rule 31] Render of SHOT-008 and SHOT-002 ran before start/end keyframe consistency was confirmed | should have waited for keyframe A/B consistency gate
- [Rule 28] First live render --go ran with 19.7 MB run.py before confirming script size under ~12 MB and before proving run.py reached VM | should have waited for size check and VM start proof
- [Rule 30] Render submitted with blank lines in prompts before build_h3_batch validation | should have waited for prompt sanitization (single line breaks only)
- [Rule 23] Next Claude stage consumed result before checking num_turns and parse | should have waited for turn-count and parse validation

ARCH-CHANGES:
- Add a pre-render keyframe consistency gate: A/B keyframe pair must pass a consistency check (set, character, props, posture) and emit keyframe_contract.json before build_h3_batch submits shots.
- Add a mandatory pre--go preflight gate: run.py, settings, and every compiled prompt must be reviewed by all reviewers (Super VL, Xing, Nemotron Super) and owner go recorded in preflight_signoff.json before Colab session starts.
- Add a prompt compiler gate that rejects blank lines and ambiguous/contradictory mouth clauses, emitting a validated .compiled_prompt artifact per shot before render submission.
- Add a Claude turn-integrity gate: join_stream must concatenate all turns into one saved artifact; num_turns and parse check must pass before the next stage consumes the result.
- Add an audio-lock stage before video render: voices/music/sound mix completed and per-shot audio length locked in audio_lock.json so render builds to audio length (no editorial timeline repair).
- Add a runner teardown hook: on error or fetch failure, auto-stop the Colab session and check colab sessions for orphans; never leave a session kept after error.

## blot.md rules part 3/4
PROBLEMS:
- [RULE 37] C: reached 0 GB free, commands began to fail | Claude temp folder filled system drive | commands began to fail
- [RULE 38] Batch 1: 19 of 32 clips over slot, up to 2.6x | clip length estimated from text instead of measured audio | 19 clips over slot
- [RULE 39] Rule 39 voice windows sized to whole clip wrong for 14 of 54 lines | windows matched clip length, not editorial cut | 14 of 54 lines wrong
- [RULE 39] Older approval_sheet csv used as text baseline instead of shots.json | wrong source of truth for text changes | 8 lines regressed
- [RULE 40] Render S009 failed 3x | session started without pre-flight URL check (chumpy-0.71 HTTP 504) | 3 failed sessions
- [RULE 36] Voice system design only, nothing built | design not implemented | nothing built, no credits spent

ORDER-PROBLEMS:
- [RULE 39 → RULE 42] Voice windows sized to whole clip before editorial_duration_sec fixed | should have waited for: editorial cut length / Gate D slot length
- [RULE 42] Video/clip built before voices measured and frozen | should have waited for: real mp3 seconds vs each slot, then video built to audio length
- [RULE 40] Paid Colab session / blind retry before curl pre-flight of external downloads | should have waited for: all URLs return 200, errors logged to timeline.txt
- [RULE 43] Ableton write or commit/push before owner gates | should have waited for: M1 gate and owner approval

ARCH-CHANGES:
- Add audio-fit gate before video/mix: voice stage outputs fit_report.json and per-shot windows from FINAL_TEXT_v2.json; Gate D blocks mix unless real mp3 seconds fit each editorial slot (VO_OVERFLOW_ERROR)
- Add editorial-lock stage before voice generation: editorial_duration_sec is authoritative input; voice windows derived from cut length, not whole clip length
- Add pre-flight stage before any paid Colab session: curl all pinned external URLs from PC, block on non-200, write errors to timeline.txt
- Add disk-space guard on C: / mandatory D: redirect for heavy output before commands or sessions
- Enforce shots.json as sole text baseline in voice_cast.py export; block regeneration unless baseline is shots.json
- Add code/CI gate: no Ableton write before M1; no commit/push without owner approval

## blot.md rules part 4/4
PROBLEMS:
- [Rule 46 amendment] Music scored against FINAL_TEXT_v2.json permission windows instead of real speech | permission windows treated as actual speech timing | 14 of 54 lines wrong.
- [Rule 46] libass silently drew a system font | ASS family name not set to the font file's own family ID 1 ("Mukta ExtraBold"); plain "Mukta" used | wrong font rendered silently.
- [Rule 49 (8)] H3 model SFX as loud as voice (gaps -18.6 dBFS vs voice -18.4) | no voice > hits > music priority; no per-shot SFX study | reel sounds jumbled.
- [Rule 50 (3)] r1-r3 renders wasted | muting the VOICE fader to measure the bus also removes the sidechain key | r1-r3 wasted.
- [Rule 51] Devanagari conjuncts broken (ब्रह्मा shown as बरहमा) in v4-v7 | caption burn used simple shaping instead of complex shaping | broken text in v4-v7.
- [Rule 48] Ableton export via computer use denied once on 11-09 | access dialog requires owner approval | export blocked once.

ORDER-PROBLEMS:
- [Rule 46 amendment] Music scoring ran before real speech timing was available | should wait for vo_tracks_report.json (line start/end from shot start).
- [Rule 47] Music gate M1 can run before the shared timeline is locked | should wait for editorial_by_lang.json freeze.
- [Rule 50 (3)] Bus measurement ran by muting the VOICE fader, removing the sidechain key | should wait for a separate voice-only render.
- [Rule 51] Caption burn ran with simple shaping before complex shaping was required | should wait for `shaping=complex` and real-frame verification.
- [Rule 49 (6)] Export/render can run before Session clips are cleared and Back to Arrangement | Session clips override the arrangement until cleared.

ARCH-CHANGES:
- Add a voice-timing gate: vo_tracks_report.json must be produced and validated before score/sound_select.py; hand real speech windows from voice build to music scoring.
- Add a timeline-freeze gate: editorial_by_lang.json must be frozen and published before music gate M1; later changes are re-communicated to the music session.
- Add a split-measurement stage: generate a voice-only render and a mix render; compute music/SFX/voice levels from both instead of muting the VOICE fader.
- Add a caption burn gate: enforce `ass=...:shaping=complex` in build_final_reel.py and require contact-sheet + conjunct crop on real frames before final render.
- Add an Ableton export gate: require manual Session clip deletion, "Back to Arrangement", and owner approval of the computer-use access dialog before any render.
- Add a font-family validation stage: check ASS name ID 1 equals "Mukta ExtraBold" before burn; reject plain "Mukta".

## MISTAKES_AND_LESSONS part 1/3
PROBLEMS:
- [C1] Clips fetched only at run end; local folder never created; download untested | six finished clips lost | full G4 session plus second session
- [C2] A100 re-render with no HF token, no retry, unproven GPU | model download 429 and hang | an A100 session, 0 clips
- [C3] 19.7 MB script sent to GPU with no start proof and unknown size limit | run never reached GPU; G4 billed 13 min | 1.68 units
- [C4] Size fix guessed, untested | same hang with 11.3 MB script | 0.57 units
- [C5] Owner’s T4 notebook mistaken for team G4; no session-ownership rule | G4 terminated 2 min into install; local exec hung | about 0.3–0.9 units
- [C6] Full batch run before H3 prompt tested on GPU | blank line read as second generation request | about 0.9 units, 15 minutes
- [C7] FILES.txt split on spaces with real names containing spaces | failed fetch left session billing | extra billed minutes on finished job
- [C8] Opus CLI `--output-format json` kept only last turn | first 90% of answer lost | 2.62 USD
- [C9] Repair prompt allowed full-answer rewrite | 3e1 stage rewritten as 11 shots, failed validators | one Opus call, failed stage
- [C10] All heavy writer work on one subscription, no budget watch | Claude weekly limit hit mid-project | blocked work for days
- [F1] Keyframes accepted from reviewer verdicts and small thumbnails | full-size defects: letters in sparks, cropped sages, wrong crowns
- [F2] A and B generated separately as options instead of start/end pair | frames disagree; video must invent the change
- [F3] A/B not defined as start and end in packet or UI | long misunderstanding with owner
- [F4] Repeated long-prompt regenerations instead of single reference change list | 5–8 submits per image
- [F5] Stale/duplicated tile names in @ picker; silent partial renames | agents stopped or picked wrong tile
- [F6] No tab discipline; agents acted on wrong tabs or closed active tabs | ~9-tab cap blocked download agents; project renamed
- [F7] Coordinate clicks without screenshot/reference | 2K download null captures 20+ min
- [F8] Agents launched without sign-in check | project signed out; agents reported done/blocked falsely
- [F9] Edit IDs from partial notes used instead of prompt/title match | agent lost time searching gallery
- [F10] Watermark threshold tuned on dark images; edits copied ghost star | no sparkle detected in 4 of 20; baked-in ghost star
- [F11] GPU noted from plan not run log | A100 vs G4 mismatch caused argument
- [P1] Heredocs converted `\n` to real line breaks | broken files caught late | wasted rounds
- [P2] Shell wrapper hid failing Gate D tests | bad push ce74e37 | bad push to fix
- [P3] Log lines written for steps that did not happen | wrong state believed
- [P4] Process kill by command-line pattern matched own shell | exit 255; session left running once | lost minutes
- [P5] Nemotron/Xing/OpenRouter reviewers run together with huge slices | empty answers, thought traces, 429s | hours of review time
- [P6] Pipeline hard-wired to first story; no per-story folders or dry run | 44 HIGH gaps found late | two full audits, closed late
- [P7] Authoring ran before render controller checked SX-01 sound cues | 6 of 10 shots not ready | authoring ran twice
- [P8] Full 10-shot batch before one-shot real test | dry run only prints commands | 4 failed starts
- [P9] Agent briefs/reports trusted without file/log verification | sign-in blocks, wrong tab, false done lines | repeated reruns
- [P10] Mid-task owner rule changes not acted on immediately | wasted calls and sends | wasted calls and sends

ORDER-PROBLEMS:
- [C1] VM stop ran before per-shot clip fetch succeeded | should have waited for: `fetch_ready` per shot and folder created before use
- [C2] A100 re-render ran before GPU/model-download test | should have waited for: proven G4 test and HF token/retry
- [C3] GPU billing ran before script-start proof | should have waited for: 180s proof that `/content/out` exists
- [C6] Full batch ran before H3 prompt layout tested on GPU | should have waited for: single-shot prompt test
- [P6] New-story pipeline ran before end-to-end dry run | should have waited for: per-story dry run
- [P7] Authoring ran before render-controller sound-cue check | should have waited for: `render_controller --dry-run` right after writer
- [P8] Full 10-shot batch ran before one-shot real test | should have waited for: `--ids SHOT-001` run and clip inspection
- [F2] B keyframe generated before/without A as edit reference | should have waited for: A start frame, then B as edit of A

ARCH-CHANGES:
- Add per-shot `fetch_ready` stage with folder-before-use gate (R29): clip saved to PC the minute shot ends; gate before VM teardown.
- Add GPU pre-flight gate (R28/R30): prove `/content/out` within 180s and test model download before billing; no unproven GPU switch.
- Add prompt validation/canary stage before batch (C6/P8): collapse blank lines; run one shot (`--ids SHOT-001`) and inspect clip before full batch.
- Add render-controller dry-run gate between writer and authoring (P7): `render_controller --dry-run` after writer to validate SX-01 before authoring.
- Add per-story onboarding stage (P6): dedicated folders plus one end-to-end dry run for every new story.
- Add keyframe pair contract (N4/F2): B produced as edit of A; side-by-side pair review; enumerated allowed changes.
- Add writer output contract (R23/C8): stream-json + `join_stream`; verify `num_turns` before handoff to next stage.
- Add fetch manifest contract (C7): one path per line in `FILES.txt`; mandatory session check after run.
- Add agent verification gate (P9): agent "done" accepted only after checking file, gallery, or log.

## MISTAKES_AND_LESSONS part 2/3
PROBLEMS:
- [Q1] Sound notes named drawable creatures and the video model drew them (black cobras in SHOT-008) | prompt carried sound notes naming drawable things; video model draws every noun | second re-render (~1.2 units, ~30 min) and owner's trust
- [Q2] Clip judged from 16 frames; wrong "all clear" given to owner | no automatic frame check; human glance at sparse sample | wrong all-clear to owner
- [Q3] Compiled H3 prompt has grammar/content defects (glued clause, duplicate sentence, broken breath sentence, pronoun clashes, repeated boilerplate, curly apostrophes, literal jargon) | compiler glues text without a language check | unknown, probably lower clip quality in every shot
- [Q4] Visual prompt lacks negative/no-extra constraint, allowing cobras and extra figures | H3 layout has no negative or "only these characters" line | cobras, possible extra figures
- [Q5] Keyframe 8A made without checking against script (Brahma seated all shot) | keyframes reviewed alone, not against shot's script lines | one full redo of 8A plus a re-render
- [Q6] 8 Hindi lines run 3.3–3.6 words/s in slots allowing 3.2; script not checked for speaking speed before render | writer sets time windows and text separately; nothing measures voice | rework of script after clips exist
- [Q7] Audio track (aac) in every clip never listened to or measured | only frames were checked | unknown; may contain speech-like noise, music or silence
- [Q8] Wrong state reported to owner from agent reports before looking | trusted agent text | wrong state reported
- [Q9] Owner's words guessed (CNET, "E100", "dataset the render", "Hyde haikyu") and acted on | no habit of confirming unclear order before costly action | wasted turns
- [Q10] Rule recorded without being asked (Flow wording rule) then removed | preference recorded as a rule | a few minutes and noise
- [Q11] Story-fidelity not checked; script not compared with SOURCE.md; writer grades itself | no independent check | risk of wrong story beats in production
- [Q12] Marathi/Hindi quality checked only by one person; easy-language checker not run on final lines; hard names may be mispronounced | no native review step, no pronunciation test | risk of poor audio
- [V1] Edit logged as done when Write was blocked by worktree path guard | file not checked with ls/read before logging as written | cost not stated
- [V2] Wrong claim to owner that account has no Hindi voice | saved Granth library not searched before denying voice type | cost not stated
- [V3] New voice_library.py started instead of copying Granth code with minimal change | source/a1_eleven.py not copied first | cost not stated
- [V4] ElevenLabs preview files were WAV data named .mp3; phone showed silent | header not checked with ffprobe before sending | cost not stated
- [V5] Preview URL treated as a test of pronunciation, speed, and names | preview is voice's own demo, not Hindi/Marathi and never our names | cost not stated
- [V6] Five blockers found only at pre-flight (shared-library voices, slot limits, model/language mismatch, double-cost rate voices, w/s over limit, untested hard names) | no free pre-flight before first paid call | cost not stated
- [V7] SHOT-007 and SHOT-009 rendered missing required figures (Daksha/sages, Shiva) | staging checked against scripture after render instead of before keyframes | cost not stated
- [V8] C: volume reached 1 MB free during long job | free space not checked before long jobs | cost not stated
- [V9] 19 of 32 batch-1 clips overran slot (up to 2.6x); 3.2 w/s rule passed on paper but real slow voices ran 1.7–2.4 w/s | no real line per voice measured against slot before batch | 19 of 32 batch-1 clips overran slot
- [V10] Promised speed + shorter text would fix length before testing; voice_settings speed 1.15 gave same length (4.08 → 4.16 s) | knob not tested on one cheap clip before promising | cost not stated
- [W1] Sparkle batch tool found no inputs, exited 0, printed nothing; misread as tool fault | batch tool does not print input count or fail on zero | cost not stated
- [W2] python -I raised ModuleNotFoundError for cv2, scipy, torch in AppData Roaming | -I used for own tools instead of untrusted data only | cost not stated
- [W3] Detector missed faint big ghost star; alpha-clean and lama_on_clean left scratches | corner crop at native size not checked for every variant; both stamp positions not forced | cost not stated
- [W4] Reviewer key expired unseen; OpenRouter returned 401 only when review ran | reviewer key not checked with tiny call before review round | cost not stated
- [W5] Old renders (shots 7 and 9 from 11-08 keyframes) sent as newest without stating source keyframes | clip sent before confirming keyframe provenance | cost not stated

ORDER-PROBLEMS:
- [Q6] Video clips rendered before voice script speaking speed was checked against slot; should have waited for voice-length fit (audio first).
- [Q5] Keyframe 8A produced before checking against script position/pose list; should have waited for script check.
- [V7] SHOT-007 and SHOT-009 rendered before source/staging check for omitted details; should have waited for scripture check before keyframes.
- [V9] Full paid batch-1 run started before generating one real line per voice and measuring seconds against slot; should have waited for real voice fit test.
- [Q1] SHOT-008 re-rendered before sound cues were linted for drawable nouns; sound-note lint should precede visual prompt/render.
- [Q3] Clips rendered before prompt compiler grammar/duplicate check; prompt quality gate should precede render.
- [Q4] Clips rendered before negative/"only these characters" constraint added to prompt; constraint should precede render.
- [Q7] Video clips accepted before measuring the aac audio track; audio measurement should precede clip acceptance.
- [W5] Clips of shots 7 and 9 sent/reported before confirming they were made from current keyframes; should have waited for keyframe provenance verification.

ARCH-CHANGES:
- Add a sound-cue lint stage between writer and video prompt compiler that rejects drawable nouns in sound notes.
- Add an automatic frame-scan gate (vision model over every 4th frame, comparing characters/creatures/objects to shot script) after render and before human sign-off.
- Add a prompt quality gate in the compiler (grammar, duplicate, jargon, boilerplate check) before any render.
- Add a fixed negative constraint line ("only these characters, no creatures, no extra objects") to the prompt compiler output.
- Add a keyframe-to-script verification stage (position and pose list) after keyframe creation and before render.
- Add a voice-length fit loop in the writer stage: measure real or estimated voice length per language and loop until the line fits the slot, before render.
- Add an audio measurement stage (ffmpeg level/silence/speech detector on every clip) after render and before clip acceptance.
- Add an independent story-fidelity pass comparing the script to SOURCE.md before keyframes/render.
- Add a pronunciation test stage for hard names with chosen voices before full voice generation, plus a native listener check.
- Add a file-write verification gate (ls/read result before logging an edit as done) in the project log.
- Add a voice-library lookup stage before claiming a voice type does not exist.
- Add a copy-from-source stage (Granth canon/a1_eleven.py) instead of rewriting voice code.
- Add an audio header validation/transcode stage (ffprobe format_name, re-encode libmp3lame 128k mono) before sending audio.
- Add a free pre-flight gate (account, slots, per-voice verified languages/model, rate, words per second per slot) before the first paid voice call.
- Add a source/staging check stage comparing each shot's script to source before keyframes are made.
- Add a disk free-space pre-check gate on C: before long jobs.
- Add a per-voice real-line fit test (one hardest slot, measure seconds against slot) before any full paid batch run.
- Add a knob validation stage (test quality/speed setting on one cheap clip and measure before promising).
- Add a batch-tool contract: print input count and fail on zero inputs.
- Add a reviewer key pre-check gate (tiny call before review round, with NVIDIA fallback).
- Add keyframe provenance metadata to clip delivery/reporting: state which keyframes the clip was made from before sending or reporting.

## MISTAKES_AND_LESSONS part 3/3
PROBLEMS:
- [W6] Two code trees drifted and a compile mixed them | no single live tree synced before code/prompt fix | fix is lost
- [W7] Keyframes contradict shot script (Brahma seated not rising; missing sages/Shiva; 007A full draw vs script start) | pictures approved without checking per-second script directives | none stated
- [W8] Picture reviewer gave wrong claims (two attendants, Sandhya facing Kamadeva vs three sages, facing viewer) | advisory reviewer trusted without full-size verification | none stated
- [W9] Converter emits "with <cue>" glue in every shot prompt ("with a veil snaps") | glue not fixed once at source with test in live tree | none stated
- [W10] Paid render sessions failed because chumpy-0.71 download returned HTTP 504 | external download URLs not tested before paid session | 0.58 units, 3 sessions, about 25 minutes
- [W11] First setup failure showed only "exit 1" | setup.log not downloaded; only timeline.txt and gpu.csv fetched | none stated
- [W12] Blind pip retries after 504 repeated the failure | retry run before cause was confirmed | none stated
- [W13] Known gaps (HF token, chumpy wheel, model caching, one code tree, converter glue, mouth sentence, OpenRouter key) parked before reel 1 | intentional deferral per owner order | none stated
- [W14] Escaped newline in test heredoc became a real line break | heredoc used for backslash text instead of Edit tool | none stated
- [W15] Hugging Face token exposed in chat history and a tool call | secret not saved to secrets/ once, not sent via stdin only | none stated
- [W16] Failed 'colab new' left unnamed G4 session billing 10 units/hour; CLI could not stop it | CLI state file had no VM record; no immediate session/usage check after failure | about 1.16 units and 25 minutes of attention
- [W17] Runner looped timeline.txt downloads after ALL DONE; G4 billed 10 units/hour for ~10 minutes | no stop condition when RESULT.json says ALL DONE and clips are home | 10 units/hour until manual stop (~10 min)
- [W18] Three failures hid behind each other (chumpy 504, colab new drop, upload websocket drop) | steps not proven on the real VM before paid attempts | none stated
- [W19] Voice windows sized to rendered clip (6.6–10.1 s) not editorial length (5–8 s); 14 of 54 lines ran past cut up to 1.46 s; false "54 of 54 fit" report | audio sized before assembler's editorial timing plan; Gate D not run first | 14 of 54 lines over cut; false fit report
- [W20] Gate D script-level retention failures (86% vs 90% coverage, 27 vs 38 words, dead air to 1.5 s) risked silent waiver | findings about script treated as build issues or waived without owner record | none stated

ORDER-PROBLEMS:
- [W6] Code/prompt fix ran before live-tree decision/sync | should wait for one canonical tree and sync
- [W7] Keyframes produced before shot-script verification | should wait for per-second script check and picture approval
- [W9] Shot prompts generated with converter glue still present | should wait for converter fix at source with test
- [W10] Paid render session started before download URL tests | should wait for curl check of every external URL from this PC
- [W11] Session stopped before setup.log was fetched | should wait to fetch log (or write tail to timeline.txt) before stopping
- [W12] Retry attempted before cause diagnosis | should wait for free cause finding after a failed paid start
- [W16] No session/usage check immediately after failed 'colab new' | should check 'colab sessions' and 'colab usage' at once
- [W17] Runner kept running after ALL DONE and clips home | should stop at once once RESULT.json says ALL DONE
- [W18] Paid setup attempts run before real-VM proof of each step | should wait for free URL/sed/hash checks on the real VM
- [W19] Audio windows sized before editorial timing plan from assembler | should wait for timing_and_lattice.trim_in/out and editorial_duration_sec; run Gate D before declaring fit

ARCH-CHANGES:
- [W6] Merge anime_studio and anime_studio_merge into one live tree; add a pre-fix sync gate so no code or prompt change runs until trees are unified
- [W7] Add a keyframe-vs-script gate before image approval requiring per-second directives as input contract
- [W8] Add full-size picture-claim verification stage; reviewer output is advisory only and must be checked at full size (F1, Q8)
- [W9] Remove "with <cue>" glue once in v4_to_h3.py with an automated test in the live tree; make converter output a contract that forbids cue glue
- [W10] Add a free pre-paid gate: curl every external download URL (requirements, model files, git clone) from this PC before any paid session
- [W11] Make setup.log a required runner artifact: fetch it (or write its tail into timeline.txt) before the session is allowed to stop
- [W12] Add a diagnosis stage between failed start and retry; no retry gate until cause is found
- [W14] Add an ast.parse gate for test files; require Edit tool for any text containing backslashes
- [W15] Add a secrets architecture: save to secrets/ once, never echo, inject via stdin only; owner writes the secret file themselves
- [W16] Add a post-'colab new' reconciliation stage: runner/waiter must check 'colab sessions' and 'colab usage' immediately after any failure; CLI state file must record VMs or a watchdog must terminate stray G4s
- [W17] Add an automated stop gate: when RESULT.json says ALL DONE and all clips are home, fetch logs once and stop the session immediately
- [W18] Add a real-VM prove-it stage with free checks (URL, sed requirements line, wheel hash) before any paid attempt
- [W19] Add a timing contract: build_vo_tracks.py must consume the assembler's editorial plan (trim_in/out, editorial_duration_sec) before sizing audio; Gate D vo_fit_check must pass before any "fit" report
- [W20] Add a gate-waiver contract: Gate D findings are written into the report; waivers only by owner order, listed by code, never silent

## PROJECT_LOG decisions/fails/owner lines part 1/12
PROBLEMS:
- [11-07 01:47 OWNER PROJECT_LOG.md] Voices after render; no voice clips supplied | audio stage scheduled after video render | cost not stated
- [11-07 02:00 GAP CHECKLIST_ARCHITECTURE_2026-11-07.md] Checklist 2.5 open: V4-to-H3 converter missing | converter not built | cost not stated
- [11-07 03:02 OWNER research/COLOUR_ATTENTION_RETENTION_AUDIT_2026-11-07.md] Caption/cc files requested; none found | no caption/cc files supplied | cost not stated
- [11-07 03:48 W1 FAIL director/test_writer_v4.py] test_stage_1_data_carries_the_selected_languages fails after gate merge | LANG-03 writer fallback / caption-check merge | cost not stated
- [11-07 04:16 DECISION usage limit reached] Usage limit reached; work stopped | usage limit exceeded | cost: pending UI/server/pipeline fixes blocked
- [11-07 04:57 B1 FAIL core suite] Core collection blocked by test_pack_rules.py and test_cvd.py | missing modules in other workers' files | cost: 3x60s wait
- [11-07 04:57 B4a FAIL core suite] Collection errors in test_lut.py, test_make_lut.py, test_cvd.py, test_pack_rules.py | other workers' files | cost not stated
- [11-07 04:57 B5 FAIL core suite] Collection errors in test_pack_rules.py and test_timeline.py | core modules missing, other worker | cost: 60s wait
- [11-07 04:59 B8b FAIL core/tests/test_retention_report.py] ImportError: retention_report missing | other agent's file missing | cost not stated
- [11-07 08:25 A25 FAIL core/tests/test_convert_deva_h3.py] 15 linter errors remain (KF-02 x8, SD-01 x2, CM-01 x1, PR-05 x4) | template/registry content | cost: no commit
- [11-07 08:28 T-DIR FAIL shell] Stray cat hung 120s; task stopped | shell command hang | cost: 120s hang, task stopped

ORDER-PROBLEMS:
- [11-07 01:47 / 01:52 / 01:53 OWNER/EV] Shared Foley video render ran before ElevenLabs voices for en/hi/mr | should have waited for voice audio, voice_map, and approved H3 anchor clip before render
- [11-07 03:48 W1 DECISION director/write_pack.py] Writer caption checks merged before stage 5 (affected stages 1-3) | should wait for stage 5 gate/validator passthrough
- [11-07 04:16 DECISION usage limit reached] server.py record_spend not gated on _start success | should wait for _start to succeed before recording spend

ARCH-CHANGES:
- Add an audio-first gate: voice generation/approval (voice_map + anchor + audio-length manifest) must complete and hand a contract file to render before the video stage is enabled; render rejects missing audio.
- Move voice_engine/audio stage ahead of shared Foley render in pipeline order; pass voice length per shot to render.
- Gate server.py record_spend to run only after _start succeeds (post-start hook).
- Add pre-collection/pre-merge gate: worker test files must not break core suite collection; missing modules fail fast before blocking other workers.
- Add V4-to-H3 converter stage to close checklist 2.5 before downstream H3 work.

## PROJECT_LOG decisions/fails/owner lines part 2/12
PROBLEMS
- [probe_r4/probe_d.py call_path] unmocked call_path hit NVIDIA endpoint with fake model (HTTP 404, no paid) | probes did not mock calls
- [gate_d_audio.py:803] Gate D audio raises before TIME-01 | gate raises before TIME-01 checkpoint
- [schema_and_linter.py:504] bool frames pass TM-02 with zero probe errors | schema/linter accepts bool frames
- [write_pack.py:237] check gets envelope JSON | check receives envelope JSON
- [pack_validator.py:844] unhashable language | unhashable language value
- [h3/gate_d_audio.py] r3 test pins PLAN-01 for captions_by_lang string; guard reverted | test pin mismatched existing error entry
- [push ce74e37] shipped with 2 failing Gate D tests (captions_by_lang string, string narration) | wrapper hid failure; cue-layer hardening coerced malformed blocks silently
- [ui/static/pipeline.js] Gate A Approve enabled while stale-server banner says restart first | UI does not block approve on stale server
- [ui/static/app.js] showSection(video) calls loadColab (Colab CLI), blot RULE 4 forbids | video section invokes forbidden Colab CLI
- [ui/static/app.js] Images Shots tab shows [object Object] in Q1-Q6 cells | fillReview String of object
- [ui/static/style.css] 8 selectors target removed #wiz-panels | dead CSS selectors
- [http://127.0.0.1:8765] phone Advanced toggle click did not expand (advancedOpen=false after click) | possible mis-target on Runs row
- [core/tests/test_caption_text.py] collection error blocks full core run after wait | test collection error | blocks full core run
- [research/_r4_dots.out] dots attempt 1 empty | token budget
- [TRIAGE_R4_BF] item7 used-after-start design | used-after-start design
- [TRIAGE_R4_BF] 4e voice_engine not editable | voice_engine not editable

ORDER-PROBLEMS
- [gate_d_audio.py:803] Gate D audio ran too early | should have waited for TIME-01 checkpoint
- [gate_d step keys from own writer] Gate D ran too early | should have waited for writer step-keys manifest
- [record_spend order] record_spend ran too early | should have waited for correct predecessor step
- [push ce74e37] push/deploy ran too early | should have waited for Gate D tests to pass
- [ui/static/pipeline.js] Gate A Approve ran too early | should have waited for server restart / stale banner to clear
- [TRIAGE_R4_BF item7] used-after-start design ran too early | should have waited for proper initialization sequence

ARCH-CHANGES
- Add a TIME-01 gate that Gate D audio must pass before running
- Add a writer-to-Gate D contract: writer emits a step-keys manifest that Gate D consumes; block Gate D until it exists
- Add a CI/push gate that blocks deployment when Gate D tests fail; remove the failure-hiding wrapper
- Add a UI gate: disable Gate A Approve until server restart is confirmed and the stale banner clears
- Remove or guard the Colab CLI call in the video section; add a Colab-readiness stage before the video section opens (per RULE 4)
- Make core.json the single loudness contract for post.py and Gate D; remove Gate D's own -14 target
- Require probes to mock calls before any endpoint hit; add a pre-flight mock gate
- Add a test-collection gate that blocks full core runs when caption tests fail to collect

## PROJECT_LOG decisions/fails/owner lines part 3/12
PROBLEMS:
- [17:59 FAIL] research/UI_PARALLEL_DISPATCH_2026-11-07.md | Write blocked by worktree path guard; file missing; both reviewer runs failed with 110 chars | path guard blocked Write / wrong path | reviewer runs failed, rewrite + re-run required.
- [18:47 FAIL] research/_prompt_colour_research.md | 'applied fixes' log line wrong; edit script failed (backslash escapes), no change made | script escape failure | incorrect log, no change made.
- [19:07 OWNER] Satvik_Loop_V4_Universal_Pipeline_Decision_Brief.docx | owner attached docx with no text | empty attachment | content missing.
- [19:08 OWNER] brief docx | wrong doc for UI but used for pipeline production | wrong document selected | missing-content check and report needed.
- [19:11 OWNER] colour guide v1 | v1 pasted again with no text; implementation waits for T3/T4 verify + CV review of v2 | no text; blocked on verify/review | implementation stalled.
- [19:12 FAIL] research/COLOUR_V2_REVIEW_HAIKU_2026-11-07.md | file NOT written; worktree path guard blocked Write; report in handback text only | path guard blocked Write | file missing, report not persisted.
- [19:13 OWNER] close the pipeline | owner asks why pipeline can't be closed; needs proper close on colour palette + UI development docs | pipeline not closed | close blocked.
- [19:27 FAIL] ui/static | key-check command launched Python REPL by mistake (hung, background bmp71oyjb) | command error | hung process, stopped, redo as script.
- [19:27 FAIL] ui | background pytest left no output and no process | pytest background failure | no output, rerun with scratchpad file.
- [19:48 FAIL] ui/static/tokens.css | git ignores via .gitignore '*token*' line 6; not changed | .gitignore pattern | not changed; lead must negate or force-add.
- [20:20 FAIL] write_pack.py | story argument must be SOURCE.md path, not slug | wrong argument type | retry with SOURCE.md path.
- [21:00 OWNER] UI bug | 'Save the languages first (step 1).' always shows at step 2 (story finished, languages none ticked) | validation state bug | step-2 flow blocked.
- [21:04 OWNER] UI feels complicated/mixed/jumbled | owner wants independent agent to interact with site and find real cracks | UI usability | independent review needed.
- [21:35 OWNER] gaps first | complete gaps (log, blot, reviews, coders) before installing Assay | gaps exist | Assay install blocked.
- [21:36 OWNER] reviewer swap | Xing in place of Dots; verifying OpenRouter id | reviewer change | ID verification pending.
- [21:41 OWNER] youtube link | link sent with no text; probing captions read-only to check if source video | no context | source-video status unknown.
- [21:44 OWNER] style question | fixed style for all stories vs per-story not explained | ambiguity | explanation needed.
- [21:46 OWNER] style | fix Deva Neon style for every story from now | style needs global fix | restyle pending.
- [21:46 OWNER] style picker | backend + frontend style chooser missing | feature gap | not built.
- [21:52 FAIL] shell | stray 'cat >> /dev/null' waited on stdin and hung | malformed command | hung, stopped.
- [21:56 FAIL] coderW coderE | both stopped by user around Assay interruption; cannot resume; work cancelled; partial uncommitted edits remain | user stop during Assay | cancelled work, uncommitted edits, relaunch blocked.
- [22:05 OWNER] focus | only Kalika Puran, not Ashtavakra | scope change | Ashtavakra work affected.
- [22:07 OWNER] Kalika writer | Claude Opus high for Kalika (rule 11 exception); stopping Nemotron Kalika run | model/run switch | Nemotron stopped, Opus run needed.

ORDER-PROBLEMS:
- [17:59] reviewer runs (supervl, dots) ran before research/UI_PARALLEL_DISPATCH_2026-11-07.md existed | should wait for successful Write/file existence.
- [19:20] test_static endpoint check fails until ui/PLAN.md section 4 gets the required row | test should wait for PLAN.md row edit (lead request, not yet done).
- [21:23] agent finishes occurred without overwriting NOW block / merge-tree blot.md (stale since 20:25; rule: overwrite after every agent finish) | blot update should follow every agent finish immediately.
- [22:01] Ashtavakra + Kalika writers started in parallel before owner narrowed focus to Kalika only (22:05) | Ashtavakra writing should wait for focus decision.
- [22:07] Nemotron Kalika run was active before owner chose Claude Opus high (rule 11 exception) | model decision should precede writer dispatch.

ARCH-CHANGES:
- Add a file-existence/write-success gate before dispatching reviewers or consumers; artifact contract handed between stages (stops 17:59, 19:12).
- Make blot/NOW-block overwrite an automated post-agent hook/gate instead of manual upkeep (stops stale blot since 20:25).
- Gate test_static on ui/PLAN.md section 4 row presence; plan row as contract prerequisite before endpoint tests.
- Add a focus/scope gate before launching parallel writers; owner focus decision recorded/committed first (stops 22:01/22:05 rework).
- Add a model-selection gate before writer runs; record owner model choice and stop conflicting runs first (stops 22:07 Nemotron stoppage).
- Merge coder S into W2 (frontend) and E2 (backend) as decided at 22:01 to reduce stage handoffs.
- Enforce write_pack.py argument validation at stage entry: require SOURCE.md path, reject slugs.
- Fix UI step-2 validation gate: 'Save languages first' must not fire when story is finished and no languages are ticked.

## PROJECT_LOG decisions/fails/owner lines part 4/12
PROBLEMS:
- [11-07 22:26] No Google Drive connector visible in session | connector not enabled/present | heavy-file storage blocked
- [11-07 22:38] coderW2/coderE2 stalled and no longer exist | agents disappeared; no log/file change since 22:04/22:05 | pipeline work stalled
- [11-07 22:51] Kalika stage 2 failed after BIBLE-06 repair | validator regex rejects 'plain neutral grey backdrop' | stage 2 did not advance to stage 3
- [11-07 23:03] director/write_pack.py syntax error | scripted edit wrote real line breaks inside strings | parse failed until fixed
- [11-07 23:06] npm view assay-ui 404 | package not on npm / identity unknown | install blocked
- [11-07 23:10] No visible UI way to choose/continue unfinished stories | UI design gap | Assay paused
- [11-07 23:24] project/gate via HTTP 403 | page-origin guard blocks HTTP | gate dispatch failed
- [11-07 23:29] assay run 1: server served only / (404) for /index.html | server routing gap | not a real pass
- [11-07 23:34] assay venv lacked Pillow | dependency missing | /api/images errors
- [11-07 23:41] assay run 2 crashed printing Marathi to cp1252 console | console encoding cp1252 | no report from ~160 cases
- [11-07 23:56] Kalika v3_web writer stopped at stage 3e4 | S55-6 Virini screen left->right SHOT-040->041 unmarked | stage stopped
- [11-08 00:32] director/write_pack.py backspace char in HEX regex | scripted edit wrote control char | regex broken until fixed
- [11-08 01:07] Kalika v4 stage 2 answer began mid-JSON | CLI 'result' keeps only text after last tool call with web tools | writer stopped during repair call
- [11-08 02:18] director/test_writer_v4.py:496 SyntaxError | real newlines in a string (rule 20 slip) | test parse failed
- [11-08 02:23] Kalika v4_deva stage 2 old file ends with stray correction note | file contamination | PARSE fail under new code
- [11-08 02:40] core/timeline.py escape slip (newline in string) | scripted edit | caught by assert; nothing broken
- [11-08 02:41] core/retention_rules.py R2/R5 inverted | code + tests inverted vs COLOUR_AUDIT.md spec | every V4 row failed
- [auditB 11-08 01:09] queue_add/queue_accept/neighbour/review lack story arg; pack_to_spec outputs_root lacks anime_ prefix | API/template gap | pack routing broken
- [auditB 11-08 01:10] read_images uses story_links root not flow_root; api.review hardcodes Kaliya; sheet job title vs chip mismatch | path/config mismatch | wrong assets served
- [auditB 11-08 01:10] download_queue.py collect->'final' for sheets; palette gate not wired | incomplete wiring | sheet collection/palette gate broken
- [auditB 11-08 01:11] bridge_flow_to_h3.py PATTERN LEAP-*; server.py b_bridge no --pattern | missing arg | bridge pattern fails
- [auditC 11-08 01:11] wizard Prepare sends shots.json to h3_prepare; b_h3 refuses it; no convert step writes H3 story; export G12 not built | interface mismatch / missing convert step | H3 pipeline blocked
- [auditB 11-08 01:11] bible_to_sheet_jobs.py not in COMMANDS; pack_to_spec outputs_root flow_outputs/<slug> no anime_ | command/template gap | sheet jobs not registered
- [auditC 11-08 01:13] converter shot lacks metadata.look/audio_and_dialogue_track; nothing writes episode.json/<sid>/clip.mp4/step9_qc.json; images_dir/results_dir never set by wizard | data contract gap | post/QC/export outputs missing
- [auditB 11-08 01:14] images_dir never set by wizard (only API); Gate B counts *__final.png incl sheets | wizard/API gap | Gate B count wrong
- [auditC 11-08 01:14] playable() 4.5-6.5s; run_kaggle.build KeyError 'mode' on V4 rows; style_bible.load(deva_neon) FileNotFound; nothing writes asset_manifest/fallback_history; post vs gate_d output paths differ | schema/path gaps | T0/Kaggle/build broken
- [auditB 11-08 01:15] findJobsFile ids SHOT-001 vs jobs SHOT-001A; server.py packet() 1..60 cap; queue_add/accept/review/neighbour no story arg | ID/cap/API gap | job lookup/packet truncated
- [auditB 11-08 01:15] pack_to_spec/bible_to_sheet_jobs written for old bible schema; V4 bible has style_lock/card_prompt, no age/heads/layers | schema migration gap | V4 bible incompatible
- [auditC 11-08 01:16] writer V4 rows route=Ref2VA -> run_kaggle ValueError; v4_to_h3._source reads only stage_1*.json envelope; story_plan.json unread | route enum mismatch / wrong source file | Kaggle build fails; H3 source wrong
- [auditB 11-08 01:17] STYLE_CHIP_SHEET__v01 identical chip name for every story; build_spec/jobs cannot rebuild after accepted flags (no overwrite) | naming collision / immutable flags | pack rebuild blocked

ORDER-PROBLEMS:
- [11-08 01:11 auditC] h3_prepare received shots.json from wizard Prepare | should have waited for a convert step to write an H3 story first
- [11-08 01:13 auditC] post/_shot_facts expected metadata.look/audio_and_dialogue_track | should have waited for converter to write those fields and for episode.json/<sid>/clip.mp4/step9_qc.json
- [11-08 01:16 auditC] v4_to_h3._source read stage_1_raw.json CLI envelope | should have waited for/read story_plan.json
- [11-08 02:35 OWNER] writer restart considered before gap fixes | should have waited for gaps fixed and reviews closed
- [11-08 02:37 DECISION] Opus/writer run proceeded before gap fixes/reviews closed | should wait until gap fixes and reviewer sign-off are complete

ARCH-CHANGES:
- Add a Drive-connector presence gate before any heavy-file render/storage step
- Add a backdrop validator/gate (BIBLE-06) before stage 2 to reject invalid descriptions early
- Add a convert/write step between wizard Prepare and h3_prepare that emits an H3 story; block b_h3 from raw shots.json
- Add a converter-to-post data contract/gate: metadata.look, audio_and_dialogue_track, episode.json, <sid>/clip.mp4, step9_qc.json must exist before post/QC
- Make v4_to_h3 read story_plan.json (not CLI envelope stage_1_raw.json) via a defined file handoff
- Require story arg on queue_add/queue_accept/neighbour/review; enforce pack_to_spec outputs_root anime_ prefix
- Add schema adapter so pack_to_spec/bible_to_sheet_jobs accept V4 bible (style_lock, card_prompt)
- Unique style chip names per story; allow overwrite/rebuild after accepted flags
- Add route normalization/validation before run_kaggle so Ref2VA is mapped/rejected early
- Add lint/gate blocking scripted edits that insert newlines/control chars into strings (rule 20 automation)
- Set PYTHONIOENCODING=utf-8 at assay venv startup
- Add pipeline order gate: writer/Opus restart only after gap fixes and reviewer sign-off are closed

## PROJECT_LOG decisions/fails/owner lines part 5/12
PROBLEMS:
- [11-08 03:03 gapfix R1 xing] HTTP 429 after 5 retries | both reviewers on one OpenRouter key simultaneously | 5 retries failed, delay.
- [11-08 06:23 Kalika writer stage 2] parse_bible needs block last but answer had trailing note | model output format mismatch | no new answer saved; repair exit 1.
- [11-08 06:24 Kalika writer stage 2 repair retry] claude API 429 usage_limit_reached | weekly limit hit on writer's stored login | no Opus call until Nov 12 15:30 IST; writer stopped.
- [11-08 06:37 Kalika writer 429 root cause] writer CLI authenticated to wrong Claude account | stored login is personal Pro account with exhausted weekly limit, not app account | blocked until owner browser login; needs separate CLAUDE_CONFIG_DIR.
- [11-08 10:33 Kalika writer run _10] ML-08 false positives | language rules wrong (aai valid Marathi listed as Hindi leak; ne Hindi ergative in MR_ONLY) | run failed after repair.
- [11-08 10:37 reel 1 redo] P6 prompt gap | writer never told pack impact budget | redo of 3e1+5e1.
- [11-08 10:37 Kalika writer run _12] refuse_finished guard blocked call | PACK.md exists = pack finished | no model call, nothing spent.
- [11-08 12:10 audit reel 1 gaps] pack_to_spec refuses V4 shots | V4 shots lack set/cast/props/keyframes | audit gap.
- [11-08 12:10 audit reel 1 gaps] v4_to_h3 lint 73 errors not run by writer validator | non-authored timing errors (dynamic split, MO-03, MO-01 7th second, SX-01 5/7) | audit gap.
- [11-08 12:10 audit reel 1 gaps] no pre-voice speech-rate check | 20 lines >3.2 wps | audit gap.
- [11-08 12:10 audit reel 1 gaps] pixel-frame vs editorial seconds mismatch | 70.8 vs 70.0 | audit gap.
- [11-08 12:10 audit reel 1 gaps] story gates self-graded, no source fidelity check | audit gap.
- [11-08 13:57 Kalika reel 1 writer rerun] Opus repair rewrote 3e1 as 11 shots | over-broad repair instead of targeted rewrite | ML-01/STIFF-01 errors, stage failed, originals restored.
- [11-08 14:49 Kalika reel 1] pasted retention script fails SPEECH-01 on 43 of 54 lines + malformed mr line in shot 7 | old pre-fix text used | pack rebuilt, 0 model calls.
- [11-08 14:54 h3/h3_author.py --live] SHOT-001 failed 5 rounds | author lint counts missing boundary PNGs (KF-06, PR-00 route T2VA) that only exist after Gate B | shots 2-10 blocked.
- [11-08 18:15 agentC-sheets sheet_jobs.json] prompt/job aspect mismatch | prompts say 9:16 vertical but job aspect is 16:9 | stopped before submit, nothing submitted.
- [11-08 18:19 agentB-sheets CHAR-SANDHYA] wrong image captured | capture from hidden strip image | recapture needed, wrong files set aside.
- [11-08 18:20 agentB-sheets CHAR-SANDHYA] wrong tile captured | plain Sandhya sheet instead of tile f962 four-armed | recapture via elementFromPoint, first A/B files set aside.
- [11-08 18:21 agentA-flow-sheets MARKANDEYA] B has garbled label text and invented labels | sheet generation quality | B not kept.
- [11-08 18:29 agentB-sheets CHAR-SHIVA] submit left no tile | prompt box showed 'Prompt must be provided' | no Shiva tile, resubmit needed.
- [11-08 20:20 me khadga shape] CHAR-KALI v01 sword was plain scimitar | prop reference not in bible/sheet prompt before sheet generation | regenerate CHAR-KALI v02 after PROP-KHADGA accepted.
- [11-08 22:10 me reel 1 sheets accepted] Kali tile rename did not save | rename didn't persist (stayed 'Character sheet displaying deity') | 3 rename-only agents started.
- [11-08 18:58 keyframe-agent-B shots_progress.jsonl] SHOT-005A stopped before submit | chip name collisions, ENV_BRAHMA_SABHA and STYLE_CHIP_SHEET not found | not submitted.
- [11-08 18:58 keyframeC SHOT-008A,008B] chip CHAR-SHIVA matches 2 rows | duplicate rows (CHAR-SHIVA + OLD-CHAR-SHIVA-B) | not submitted.
- [11-08 18:59 keyframeC SHOT-008A..010B] picker substring search matches OLD- rows | exact-name rule not implemented | all 6 jobs blocked, nothing submitted.
- [11-08 23:20 me picker rule] 0 rows for ENV_BRAHMA_SABHA__v01, STYLE_CHIP_SHEET__v01 | renames likely did not save | keyframe agent B stopped at 005A.
- [11-08 18:59 flow-keyframe-agentA SHOT-004A] picker shows no rows | exact-name match only, tile not found | BLOCKED pending picker.

ORDER-PROBLEMS:
- [11-08 14:54 h3/h3_author.py --live] author lint ran before Gate B | needed boundary PNGs (KF-06, PR-00 route T2VA) that only exist after Gate B.
- [11-08 12:10 audit reel 1 gaps] pack_to_spec ran before V4 shots had set/cast/props/keyframes | needed those fields to accept shots.
- [11-08 12:10 audit reel 1 gaps] v4_to_h3 lint did not run before writer validator/downstream | needed non-authored timing checks (dynamic split, MO-03, MO-01 7th second, SX-01 5/7).
- [11-08 12:10 audit reel 1 gaps] no pre-voice speech-rate check | needed before voice/audio; 20 lines >3.2 wps.
- [11-08 18:58 keyframe-agent-B / 18:59 keyframeC] keyframe chip selection ran before sheet renames saved | needed ENV_BRAHMA_SABHA__v01, STYLE_CHIP_SHEET__v01 and deduplicated CHAR rows.
- [11-08 18:59 flow-keyframe-agentA SHOT-004A] keyframe picker queried before exact-name tile existed | needed CHAR-BRAHMA row saved.

ARCH-CHANGES:
- Add a pre-pack validation gate: pack_to_spec accepts shots only after set/cast/props/keyframes exist, or add a V4 normalization stage to populate them first.
- Move v4_to_h3 lint (non-authored timing: dynamic split, MO-03, MO-01 7th second, SX-01 5/7) into the writer validator or a pre-voice gate so it blocks downstream until clean.
- Add a pre-voice speech-rate gate (≤3.2 wps) before voice/audio production.
- Add a source-fidelity gate for story gates; stop self-grading.
- Enforce Gate B before h3_author.py lint: author lint runs after Gate B emits boundary PNGs, or skips image-dependent codes until Gate B passes.
- Add a persisted chip registry with exact-name-only lookup and a mandatory rename-verify stage that completes before keyframe agents query chips.
- Run writer CLI with a separate CLAUDE_CONFIG_DIR logged in as the app account, not the personal Pro account.
- Add pack impact budget to the writer prompt contract.
- Add aspect-ratio validation in sheet_jobs submit (prompt aspect must match job/brief aspect).
- Add a versioned pack or reopenable finished pack so refuse_finished guard doesn't block legitimate repairs.

## PROJECT_LOG decisions/fails/owner lines part 6/12
PROBLEMS:
- [11-08 19:00 keyframeC FAIL SHOT-008A] ENV_BRAHMA_SABHA__v01 picker shows 0 rows under exact-name rule | asset picker not returning rows for named env | shot blocked, not submitted, no renames
- [11-08 19:02 flow-keyframe-agentA FAIL SHOT-004A] @CHAR-BRAHMA at 1280x900 yields no picker rows | resolution/tab picker empty | shot blocked again
- [11-08 19:03 flow-keyframe-agentA FAIL SHOT-004A] picker row click closes menu without attaching chip | UI add-to-prompt flow unreliable | no submit, stopped
- [11-08 19:03 keyframeC FAIL SHOT-008A] 1280x900 picker is a different panel; row click closes without attaching | resolution-dependent picker UI | chip step unreliable, no submit, viewport reset
- [11-08 19:04 keyframe-agent-B FAIL shots_progress.jsonl] SHOT-005A chip attach incomplete in wide picker | chip attach not completed | nothing submitted; 005B-007B not started
- [11-08 19:05 flow-keyframe-agentA DECISION SHOT-001A] post-process paused; tile not captured/reviewed/renamed | post-process incomplete before tab switch | tile not captured/reviewed/renamed; remaining jobs not started
- [11-08 19:05 flow-keyframe-agentA FAIL SHOT-001A] JS data URL capture overflowed tool output (~262k chars) | capture method too large for tool | no files written; no review/rename; remaining jobs not started
- [11-08 19:06 flow-keyframe-agentA FAIL SHOT-001A] img src fetch fails CORS; canvas tainted | cross-origin fetch blocks capture | no file written; 001A review/rename not done; stopping
- [11-08 19:07 keyframeC FAIL SHOT-008A] second @ after a chip stays literal; picker won't reopen | chip-then-@ picker flow broken | blocked on chip 2; draft cleared
- [11-08 19:09 keyframeC FAIL SHOT-008A] chip 2 still literal after ref click; aspect must be re-set | picker state not persistent | no submit
- [11-08 19:09 flow-keyframe-agentA DECISION SHOT-001A] tile A rename failed twice; title still 'Goddess opening ...' | rename method not persisting | tile A not renamed; stopped per retry-once rule
- [11-08 19:19 keyframeC FAIL SHOT-008A] reviewer BLOCK A and B (advisory) | reviewer quality block | both need regenerate; not kept
- [11-08 19:27 keyframeC FAIL SHOT-008B] reviewer BLOCK A and B | reviewer quality block | not kept; NEEDS_REVIEW
- [11-08 19:40 me DECISION owner] Kamadeva sheet has solid red hands/feet + thin prop details | bible sheet_prompt/description wrong | CHAR-KAMADEVA-v02 added; shots 5,6,7,9,10 to be redone
- [11-08 19:40 AGENT-D DECISION ENV-MARKANDEYA-ASHRAM-v02] plate A BLOCK: no kusha mats, smoke off kunda | env details missing/incorrect | A blocked, no rename
- [11-08 19:45 flow-keyframe-agentA FAIL SHOT-002A] regen1 A and B BLOCK on Q2 (palm/gaze) | generation quality issue | not kept; regen2 started
- [11-08 20:30 me DECISION owner] Yajna invented as 'ring of fire stones' in ashram plate; SOURCE reel 1 has no yajna scene | source fact checked after prop/env creation | PROP-YAJNA-KUNDA and ENV-YAJNA-GROUND rewritten; shot 3 regenerated
- [11-08 19:50 me DECISION owner] Kali garland was beads instead of skulls; severed-head garland replaced | bible/pack deviated from source | Bible/PACK/shots/PROP-AKSHARA-MALA updated; affected shots need redo
- [11-08 19:44 flow-keyframe-agentA FAIL ENV_MARKANDEYA_ASHRAM] new tile rename failed twice; title still 'Sacred fire pit at...' | rename method not persisting | CHAR-KALI-v03 and SHOT-003A/B not started
- [11-08 19:49 H1 FAIL monitor bwiel7e68] monitor exited early; ps grep matched nothing | monitoring process died | review monitoring gap; re-armed on pid
- [11-08 19:52 H3 FAIL review_shot.py v03] background task exited code 1 | review script failure | no result from automated review
- [11-08 19:59 H1 FAIL review_shot.py CHAR-KALI-v03] background run exit 1, no result | review script failure | coordinator fell back to manual visual check
- [11-08 20:00 H1 FAIL d012df26 rename] title still CHAR-KALI after 2 tries | rename method not persisting | extra tab-22 opened/closed; rename incomplete
- [11-08 20:00 H3 FAIL tab-22] tab closed by something after submit click | UI/session instability | submit status unknown
- [11-08 20:03 H2 DECISION SHOT-003A] r1 review BLOCK both (mala not held) | prop not held in generation | regen required
- [11-08 20:02 H2 DECISION SHOT-010B] no 010B tiles found in gallery (32 tiles, none with Push-in prompt) | gallery/query missing expected tiles | resubmitting 010B

ORDER-PROBLEMS:
- SHOT-005A, 005B, 006A, 006B (and 007, 009, 010 Kamadeva shots) ran with old CHAR-KAMADEVA before CHAR-KAMADEVA-v02 sheet fix | should have waited for approved CHAR-KAMADEVA-v02 chip
- ENV-MARKANDEYA-ASHRAM plate with invented 'ring of fire stones' ran before source fact check (reel 1 has no yajna scene) | should have waited for source-verified Vedic altar definition
- SHOT-001A/B, 002A/B ran before CHAR-KALI v03 acceptance (skull garland confirmed) | should have waited for accepted CHAR-KALI v03
- CHAR-KALI-v03 and SHOT-003A/B expected to start before ENV_MARKANDEYA_ASHRAM__v01 rename verified | should have waited for verified rename/post-process
- SHOT-005B-007B expected to start before SHOT-005A chip attach completed | should have waited for chip attach completion

ARCH-CHANGES:
- Add a source-fact gate before bible/pack/shot generation: source reel facts (yajna scene, Kali garland, Kamadeva description) verified and signed off; a source-fact contract file handed to bible/pack stage.
- Add an asset-approval gate: CHAR/ENV/PROP versions (e.g., CHAR-KAMADEVA-v02, CHAR-KALI-v03, ENV_MARKANDEYA_ASHRAM__v01) must be APPROVED and renamed before any shot referencing them is dispatched; shot job carries referenced asset version ID.
- Replace unreliable UI picker chip attach with a deterministic asset-binding stage: exact-name rule returns chip ID; row selection inserts chip into prompt (not close menu); bind assets via API before submit.
- Add a post-process verification gate: capture, review, and rename must complete (file written, title verified after reload) before downstream jobs launch; progress line cannot advance to DONE without rename verification.
- Make review_shot.py synchronous or add non-zero exit handling: no background review run may exit code 1 without a result; coordinator fallback only after logged review failure.

## PROJECT_LOG decisions/fails/owner lines part 7/12
PROBLEMS:
- [11-08 20:16 R1/R2/R3 FAIL] Flow pane signed out; project URL redirects to /about, Sign in link present | lost authentication in built-in pane | all jobs stopped (7A/9A rename, 9B, 2A, 2B); no submit, rename, or download; agents idle pending owner sign-in.
- [11-08 20:37 R1 FAIL] review_shot.py cp1252 UnicodeEncodeError printing Devanagari reason | script defaults to cp1252 instead of UTF-8 | rerun with PYTHONIOENCODING=utf-8 required for 001A B.
- [11-08 21:13 R5 FAIL] gallery title SHOT-001A__v01 is on edit 1f1d26c1, not log id 8aa727e3 | title/id aliasing or stale URL mapping | agent must check 8aa727e3 directly before any rename.
- [11-08 21:15 R5 FAIL] click (250,667) opened tile a1019a88 (RETIRED-SHOT-006B-D), not composer; text typed into its edit box | UI coordinate/tile-target mismatch | no submit; page abandoned without touching tile.
- [11-08 21:19 R5 FAIL] edit route always opens a200e328 for tile B click (dup titles); tile B thumb fetch s1600 failed decode | duplicate titles and broken thumbnail fetch | tile B judged only from gallery zoom; cannot open at full size.
- [11-08 21:22 me DECISION] SHOT-001A a200e328 rejected on owner's second look (wink look, crown dominates, not eye close-up) | quality re-evaluation after prior acceptance | R5 resumed with new sentence; 3 submits left; unique title (1f1d26c1) still to verify.

ORDER-PROBLEMS:
- [11-08 20:16 R1/R2/R3] Flow submit/rename/download ran before Flow sign-in | should have waited for owner sign-in in the pane.
- [11-08 21:13–21:22 R5/me] SHOT-001A rename and 2K download actions ran before verifying unique gallery title (1f1d26c1 alias of 8aa727e3?) | should have waited for title-uniqueness verification.
- [11-08 21:19 R5] SHOT-001A tile B visual judgment ran before correct tile/full-size view was available (thumb decode failed; edit route opens wrong tile) | should have waited for resolved tile and full-size asset.

ARCH-CHANGES:
- Add a sign-in gate at the Flow coordinator: agents receive a signed-in session contract before any submit, rename, or download stage runs.
- Add a title-uniqueness / canonical tile-ID resolution stage before rename and 2K download: gallery service must hand a verified unique title and image ID to the agent as a precondition.
- Add a UTF-8 output contract to the review stage (review_shot.py runs with PYTHONIOENCODING=utf-8) so Devanagari reasons do not crash encoding.
- Add a full-size asset availability gate before visual review: agent must hold a decoded full-size or verified thumbnail before judging a tile.

## PROJECT_LOG decisions/fails/owner lines part 8/12
PROBLEMS:
- [11-08 21:42–21:55] 2K download agents D1–D4/L1–L4 failed: tab cap reached (9 flow tabs); 2K clicks produced no capture (window.__dl null, no network download, no blob). | Root cause: browser tab/pane gate and download hook not capturing. | Cost: 0 of 20 filed initially; only 10 of 20 filed; 009A, 010A, 010B, 003A left open; shots reassigned to L1/L3.
- [11-08 22:30] h3_author --live --opus failed: Claude weekly usage limit (429) for opus and sonnet, resets Nov 12 15:30. | Root cause: model quota exhausted. | Cost: fell back to free NVIDIA scheduler; nothing written by failed run.
- [11-08 22:41] h3_author Ultra run stopped after authoring shots 1–5 only. | Root cause: run stopped before completion. | Cost: incomplete authoring (shots 6–10 not done in that run).
- [11-08 23:21] Render pre-check not met: dry run 4/10 shots ready (SX-01 errors in 3,4,5,8,9,10); controller says no GPU backend wired. | Root cause: gaps unfixed; backend absent. | Cost: render could not start.
- [11-09 00:16] render kalika_reel1 failed: run.py 19.7 MB never started on VM (/content has no out/ or Wan2GP after 13 min; kernel idle); local colab exec stuck sending. | Root cause: embed too large (19.7 MB vs 7 MB that worked); VM output dir/backend missing; local exec stuck. | Cost: ~2 units spent; render delayed; rebuilt 11.3 MB batch not started until later.
- [11-08 21:31] SHOT-006B: 4 submits used (cap); owner edit order not run; needs 5th submit. | Root cause: submit cap reached before owner-directed edit. | Cost: extra submit required; v05 kept as NEEDS_REVIEW.
- [11-08 21:34] SHOT-006A: submit 4 of 4 (last allowed) still not clear PASS. | Root cause: submit cap reached before acceptable edit. | Cost: cap extended to 6 total.

ORDER-PROBLEMS:
- [11-08 22:06] Gate B approval and boundary-frame start ran while 2K downloads incomplete (only 10/20 filed; 009A, 010A, 010B open). | Too early: approval/start of boundary frames. | Should wait for: 2K download completion / 20/20 filed.
- [11-08 23:20–23:21] Render start ordered before cross-check confirmed readiness; dry run showed 4/10 shots ready and no GPU backend wired. | Too early: render start order. | Should wait for: gap fixes and GPU backend wiring.
- [11-09 00:01] Render launch confirmed (G4) before rebuilt batch verified/started; 00:16 run failed because VM environment not ready. | Too early: render launch. | Should wait for: environment fix and pre-flight verification.

ARCH-CHANGES:
- Add a download-completion gate/manifest: download stage emits a filed manifest (20/20 receipts) that Gate B and boundary-frame stage verify before approval/start.
- Add a render pre-flight gate: controller checks GPU backend wired, /content/out and Wan2GP present, and all shots ready before run.py may launch; fail fast without spending units.
- Add an artifact size contract: run.py/embed bundle checked against a max size before VM submit, with auto-shrink (JPEG q90 4:2:0) as a pre-submit stage.
- Add a submit-cap reservation: owner-directed edit submits reserved/checked before the order is issued so the edit is not blocked by the cap.
- Replace browser-tab download automation with a non-tab download method to remove tab-cap dependency.

## PROJECT_LOG decisions/fails/owner lines part 9/12
PROBLEMS:
• [11-09 01:10 FAIL] G4 render session terminated ~2 min after pip install began; local runner/exec killed; no clips | likely stopped by owner in Colab Manage while closing extra notebook (not proven) | no clips; browser T4 still running 1.15/h; balance 185.30
• [11-09 01:12 OWNER] Render attempt 4 stopped; no clips rendered | owner stop after switching to A100 | no clips rendered
• [11-09 01:22 FAIL] All 10 shots rc=1 in 10 s | blank line in H3 prompt made wgp parse into 2 generation requests (T0 used single newlines only) | ~0.9 units spent (184.86)
• [11-09 02:29 OWNER] New 8A (tile 9b95bb2f) 2K download blocked and held | owner: Flow is dumb; wants simple words, proper reference image, small changes; RULE 32 blotted | 8A held; waiting owner decision
• [11-09 02:50 FAIL] SHOT-008 re-render v2 drew cobras behind Brahma from frame ~48 to end | prompt sound cues ('serpents hiss softly', 'serpents shift with a faint dry hiss') read by model as visual direction; only 16 frames reviewed | re-render rejected ('shit')
• [11-09 03:01 OWNER] Render v2 started before reading full compiled prompt/run.py | prompt read only after start | render stopped; defects found (duplicate last sentence, 'with the wind drops', 'at seconds 7', pronouns)
• [11-09 04:03 DECISION] en NARRATOR voice ID not in our account (GET /v1/voices/<id> not found); Hindi not verified; no Hindi sample | voice must be added to account (uses a slot) before any run | awaiting
• [11-09 05:12 FAIL] Browser tab-17 opened wrong tile edit page (SHOT-001A__v01) | misclick at (250,667); nothing submitted | no edits; none stated
• [11-09 05:21 FAIL] SHOT-007A rename 8746c61d → SHOT-007A__v02 not saved after 2 tries | rename save failure | SHOT-007B not started; title still 'Archer aiming bow with sages'
• [11-09 05:22 FAIL] Rename 56530241 → RETIRED-SHOT-007A__v02-x not saved | rename save failure | title stays 'Archer aiming bow in heaven'
• [11-09 05:30 DECISION] SHOT-007B tile e7562f52 shows Sandhya with 3 arms (needs 4); both tiles wrong | visual generation mismatch | one more edit required

ORDER-PROBLEMS:
• SHOT-008 video render (batch kalika_shot008 on G4, 11-09 02:34) ran before voice generation go (11-09 02:42) | should have waited for audio/voices first
• Voice generation (11-09 02:42) ran before en NARRATOR and other voice IDs were added to the account (11-09 04:03: must be added before any run; awaiting) | should have waited for voice account registration
• SHOT-008 re-render v2 (11-09 02:34–02:50) ran before shots.json audio_cue fix removed serpent words | should have waited for prompt/audio_cue correction
• Render v2 (11-09 03:01) started before full compiled prompt/run.py was read and defects fixed | should have waited for prompt review/fix
• Render attempt 5 (11-09 01:22) ran before build_h3_batch blank-line collapse/raise fix | should have waited for prompt sanitization

ARCH-CHANGES:
• Add an audio-lock gate before any GPU video render: a stage that issues a per-shot audio manifest (voice IDs + lengths) and blocks render start until the manifest exists and is approved; video build consumes audio length.
• Add a pre-render prompt gate: full compiled prompt and run.py must be read/reviewed and lint-clean (no blank lines, no stray audio cues) before the GPU session may start.
• Add a voice-account registration contract: voices_cast.json must mark each voice ID as added to the account before the audio generation stage runs; generation reads from that contract.
• Add a sound-cue validation stage between script authoring and video render (or separate audio cues from visual prompts) so prompt sound cues cannot generate unintended visuals unreviewed.
• Add a render readiness review gate: reviewer sign-off on prompt/script must be recorded before render start.

## PROJECT_LOG decisions/fails/owner lines part 10/12
PROBLEMS:
- [11-09 05:43 FAIL C: drive] C: drive 0 GB free; command stdout failed once | no free space on C: | work redirected to D:/aai work/tmp_fit; owner must free C: (rule 37)
- [11-09 05:54 FAIL voice_add.py remove] deletion of 10 KP- voices from ElevenLabs blocked | permission classifier blocks delete | not retried; owner OK needed to free slots for 6 remaining cast voices
- [11-09 10:36 FAIL OpenRouter] HTTP 401 API key expired | key file loop_p0/secrets/openrouter_paid_key.txt expired | not renewed; fallback NVIDIA Super VL; save step assumed dict but envelope returns str (fixed)
- [11-09 10:56 FAIL render S009 attempt 1] pip install exit 1 in 0.5 s: GitHub HTTP 504 on chumpy wheel | external transient 504; script retry only covers HF 429 | no clip rendered; session stopped
- [11-09 11:05 FAIL render S009 attempt 2] pip install failed 4 times even with retry | persistent chumpy wheel unreachable; runner did not download setup.log | error text lost; session stopped; balance −0.44 units; no clip
- [11-09 11:10 FAIL render S009 attempt 3] HTTP 504 Gateway Time-out on chumpy release URL | release file unreachable from PC and server; external | 3 attempts stopped; no clip
- [11-09 11:47 FAIL render S009 attempt 4] colab new died with ConnectionError; orphan unnamed G4 session left billing | remote end closed connection; sessions.json empty so colab stop cannot find it | balance 175.67 → 175.34 and falling; browser not signed in to Google
- [11-09 11:58 FAIL render S009 attempt 5] colab new died with ConnectionError before setup | remote end closed connection without response | no units spent; wheel/pip path untested
- [11-09 12:02 FAIL render S009 attempt 6] upload_00.py died: WebSocketConnectionClosedException | socket already closed | runner stopped session; balance 174.51 (no visible loss)
- [11-09 12:34 FAIL render S007 attempt 1] colab new ColabRequestError: G4 assign Service Unavailable after ~10 min | no G4 accelerator free | nothing spent; guard ran
- [11-09 11:34 FAIL test file edit] escaped newline became real line break in test_run_colab_batch.py | heredoc escaping issue | P1, 9th occurrence; caught by ast.parse
- [11-09 12:53 FAIL score/gate_d_bridge.py] NaN/inf float stem passes checks; anti-phase f32 misses BASS_NOT_MONO; presence_levels raises on nan win_s | gate checks miss edge cases | GBR findings
- [11-09 12:54 FAIL score/plan_check.py] KeyError on missing rehook_at_s/peak_at_s | missing keys not handled | CHECK_CRASH; fixed with .get and explicit PEAK
- [11-09 13:08 DECISION captions] captions use engine default style (34 px at 1080 w, plain fallback, 10 title cards) not owner Instagram/YouTube Shorts spec | captions produced before owner spec located/applied | not touched now; to be redone in dedicated pass; current final reels keep default captions

ORDER-PROBLEMS:
- [11-09 10:56–12:02 render S009 attempts 1–6] video render ran before voice text v3 / locked editorial length (decision at 12:47) | should wait for voice text v3 and per-shot editorial length
- [11-09 12:34 render S007 attempt 1] video render ran before voice text v3 / locked editorial length (decision at 12:47) | should wait for voice text v3 and per-shot editorial length

ARCH-CHANGES:
- Add an audio/voice-lock gate before render: render CLI requires a voice manifest and locked per-shot editorial-length JSON; no --go until voice exists and matches picture length
- Make the Colab runner download and preserve setup.log/full pip error text as an artifact before stopping any session
- Add a pre-flight external dependency/URL availability check (rule 40) for wheels such as chumpy before pip install, with cached fallback or skip
- Add session-ID tracking/reaper so orphan unnamed Colab sessions can be stopped and billing halted even when sessions.json is empty
- Add a dedicated captions conformance gate after mix that validates against the owner's Instagram/YouTube Shorts spec before final release
- Add a C: drive free-space guard (rule 37) or default tmp to D: before any command that writes stdout/logs
- Add an ElevenLabs voice-slot pre-approval/owner-OK step before bulk deletion to unblock the voice pipeline

## PROJECT_LOG decisions/fails/owner lines part 11/12
PROBLEMS:
- [11-09 13:13 DECISION study finding] Recipe lacks readbacks after mutations; only get_session_info readbacks exist | missing readback steps in Ableton recipe | mutations unverified
- [11-09 13:13 DECISION study not finished] Built modules + bible not audited against README 400-end, serum-mcp docs, core modules | study incomplete | audit pending
- [11-09 13:40 FAIL style study GA43TUfaKAxzBJRD1cDFiP] Style study inaccessible: docs access denied, artifact not found, no local copy | access/availability failure | owner must share or paste it; blocks style audit
- [11-09 13:40 DECISION music_bible SHIVA] SHIVA theme D2-D3 all <200 Hz silent on phones at peak | low-frequency direction error (rule 11) | silent on phones
- [11-09 13:33 FAIL score/tests/test_note_writer.py] Partners test fails (no partner notes) | test red before implementation / missing partner notes | C29 red
- [11-09 13:50 DECISION music_bible.json vs study] 11 direction errors between music_bible.json and study | bible/study mismatch | 2 rule conflicts escalated to owner
- [11-09 13:59 DECISION NW4 triage] Voice 34.3-40.2 conflicts with music event at 34.0 | music event placed against unfrozen voice timing | rehook required
- [11-09 14:02 DECISION NW4 r2 triage] SANDHYA 4/4 notes dropped; 34.0 DnB kick merged into club tail; 0.4 s drop-out at 33.6 missing | open triage items | round 3 required
- [11-09 14:03 DECISION PCR2 triage] Items 3, 6, 9 rejected | timing/rule conflicts (last word 69.846 vs sting 69.85; rule 8 fast-act only) | PC2 fixes required
- [11-09 14:05 DECISION NW4 r3 triage] SANDHYA 4th note (hang B4) lost | missing note in arrangement | feel quad required
- [11-09 14:08 DECISION NW4 r4 triage] KAMADEVA hook 3/5 cut | timing constraint (all before 30.2) | feel quad required
- [11-09 14:12 DECISION PCR2 re-check triage] R-1 rejected: note_writer drops high brass under voice though bible allows low brass/horn | vocabulary/rule mismatch between bible and note_writer | test_c28 / PC2 fixes
- [11-09 14:12 DECISION PCR2 re-check triage] R-2 rejected: handover/swell are audible changes | audible transitions not permitted | PC2 fixes
- [11-09 14:12 DECISION PCR2 re-check triage] R-4 rejected: writer truncates by design | design truncation | PC2 fixes
- [11-09 14:14 FAIL research/_probe_nwr3_reel.py] Probe cannot import pytest under python -I | fixture module imports pytest; isolated mode blocks it | rerun without -I required
- [11-09 14:18 DECISION NWR3 findings] HIGH: piano under speech; Shiva reveal drums. MED: bpm hang; end sting low; fixture omits mapped motifs; 11 s hard cut no swell | review findings | rework required
- [11-09 14:19 DECISION NWR3 triage] Item 12 rejected: DnB enters 34.0 + MAIN 40.25 both in window | overlapping music events in same window | owner sees at M0
- [11-09 14:29 FAIL NW4 r6 + PC2 r3 agents] Work stopped on Claude Code session restart | process exit, not code error | 15 failed, 331 passed left in red stage
- [11-09 14:43 DECISION NWR3 re-check] NWR3-7 not fixed; new R-1 curse swallowed, R-2 merge velocity leak, R-3 theme velocity flat 100, R-4 stale docs | unresolved/regressed issues | rework required
- [11-09 14:44 DECISION NWR3 re-check] 2 items not resolved | re-check verdicts | remaining rework
- [11-09 14:54 FIX blot.md] Caption rule 45 collided with music session RULE 45; plan_check.py cites rule 45 = music | parallel sessions sharing one rule namespace | rule renumbered 45->46; fix required in blot/handoff/memory
- [11-09 15:10 FAIL final_reel1_v4 first build] Gate D VO_OVERFLOW_ERROR shots 5/7/8 all langs | padded VO file = editorial-0.10 exactly; frame-based editorial (8.2917) rounds up one sample | gate failure; not speech
- [11-09 15:22 FAIL score/tests/test_audition.py] test_cli_builds_three_files failed after live regenerate | live regenerate broke build | investigating
- [11-09 15:35 FAIL score/note_writer.py] write_notes rejects plan_check transitions theme_handover, key_colour_on_downbeat | vocabulary clash between plan_check and note_writer | forced swells on 5 soft cuts (style fault); workaround flagged
- [11-09 16:30 FAIL score/sound_select.py] Selection run crashed on zero centroid (silent sample) | no guard for silent samples | crash; rerun required
- [11-09 16:31 FAIL score/sound_select.py] Relax logic applied to modern layers (S5 groove/bass shown as Indian relaxed) | wrong layer scope for relax logic | rerun required
- [11-09 16:33 FAIL score/sound_select.py] 4 empty slots (S5-groove, S5-bass, S6-bed, S7-bass) | cap 30 consumed by clipped/key-failing files; noisy 6 s snippet key re-measure | empty slots; rerun required
- [11-09 16:46 DECISION SMP2 round 2 triage] S3 has no audible Indian layer | missing Indian layer in S3 | round 3 fixes required
- [11-09 16:54 FAIL v3 build] S3 indian stem -53 dBFS (<-40); windows 14-15 at -30.7/-27.1 | level imbalance | v3 build fail; level_db fix required
- [11-09 16:58 FAIL v3 rebuild 2] Outro bed window 67.4-70.4 s at -26.0; bed -37.8 dBFS | insufficient S8-bed level_db | rebuild fail; level_db 12->18 required

ORDER-PROBLEMS:
- [11-09 15:10 FAIL final_reel1_v4] Editorial/frame timing (8.2917 s) fixed and VO padded to it before VO length was locked | should have waited for final audio/VO length, then built editorial to audio
- [11-09 15:20 DECISION score/cue_sheet.py] Shots and VO rows built before editorial extensions applied | should have applied new_editorial_sec to shots and shifted VO rows before build_episodes
- [11-09 13:59 DECISION NW4 triage] Music event at 34.0 placed against voice 34.3-40.2 | should have waited for voice lock/final timing
- [11-09 14:03 DECISION PCR2 triage] Sting at 69.85 placed 0.004 s after real last word 69.846 | should have waited for final voice last-word timestamp
- [11-09 14:19 DECISION NWR3 triage] DnB (34.0) and MAIN (40.25) scheduled in same window without voice-window separation | should have waited for voice/window boundaries before placing music events
- [11-09 14:54 FIX blot.md] Music session added RULE 45 while caption rule 45 was being edited | should have waited for rule-namespace lock or used domain-separated rule IDs

ARCH-CHANGES:
- Add a readback step after every mutation in the Ableton recipe (currently only get_session_info readbacks exist).
- Add an audio-lock gate: final VO/music length must be frozen before editorial timeline or video build; editorial/video built to audio length, not VO padded to editorial.
- Make editorial a pre-build transform: apply new_editorial_sec to shots and shift raw shot times + VO rows atomically before build_episodes, with a gate that VO length <= shot length minus epsilon.
- Replace shared flat rule namespace with domain-scoped/versioned rule IDs (e.g., caption rule 46 vs music rule 45) so parallel sessions cannot collide.
- Merge plan_check and note_writer cut-transition vocabularies into one shared contract/module so note_writer accepts all plan_check transitions.
- Persist test/CI state across Claude Code sessions so a restart does not abandon work in the red (tests-first) stage.
- Add sample validation guard (non-silent, stable chroma key) before slot assignment in sound_select; measure key beyond cap and auto-remove stale snippets.
- Require a local copy of the style study in the repo; gate builds on style study present and audited.

## PROJECT_LOG decisions/fails/owner lines part 12/12
PROBLEMS:
- [SMP2] restore stems | wrong copy path used; stems/ removed then restored from backup | stems/ deleted, restore required
- [ABL2] track 5 KP drone slot 1 | create_clip blocked: slot occupied; no delete-session-clip or clear-notes tool | nothing written, clip not deleted
- [SFX1] score/sfx_study.py | onset clicks 56 ms early (log-flux + 2048 frames) | test failure; rework to linear flux 512 frames
- [MIX1 v6 round 1 triage] voice over SFX+music below target; true peak above limit | voice-priority ducker missing/insufficient | round 1 failed; round 2 required
- [EQ1] noduck pre at -2.7 LUFS clipped; no clash cuts (SUSTAIN 0.25 too high) | raw stems without global gain first; permissive clash threshold | clipping; missed clashes
- [me] why not built in Ableton | mix built outside Ableton, not brought back for mixing | Ableton export access denied; MCP cannot write arrangement/automation/render | owner anger; Ableton-native mix proposed as rework
- [me] render naming | r1-r4 renders overwritten in place | no versioning | r1-r4 settings/results lost
- [me] FIX: research/_run_seq_review_nv.py | heredoc edit failed (backslash, rule 20); stray dots run killed by PID | edit error; process kill; redo required
- [me] Nemotron Super run 1 | 17/32 slices empty, synthesis empty | max_tokens too low; thinking consumed 6000 tokens | empty output; rerun as SUPER2 required

ORDER-PROBLEMS:
- [EQ1] loudness/clipping check ran before global gain applied to noduck | should wait for v5 global gain first
- [ABL2] create_clip ran before slot was cleared | should wait for delete-session-clip / clear-notes or slot availability
- [MIX1] voice-over-SFX+music levels checked before voice-priority ducker applied | should wait for final ducker stage (ducker last, round 2)
- [me] code mixing/render ran before Ableton-native mix | should wait for Ableton arrangement/render access or return stems to Ableton for mixing

ARCH-CHANGES:
- Add path-confirmation + backup-verification gate before any stem delete/restore (SMP2).
- Add delete-session-clip / clear-notes tool or slot-clear precondition to Ableton clip creation (ABL2).
- Add onset-parameter test gate (flux type + frame size vs click offset) before score/sfx_study.py acceptance (SFX1).
- Insert global gain-staging stage before loudness/clipping checks; enforce SUSTAIN clash threshold as measurement contract (EQ1).
- Make voice-priority ducker a mandatory final mix gate after music/SFX and before true-peak limiting, with loudness contracts (MIX1).
- Enforce immutable render naming (rN, never overwrite) via render manifest (render naming).
- Require Ableton-native mix or return-to-Abelton stage before final export; provision Ableton export/automation/render access (Ableton).
- Add max_tokens / non-empty-output validation gate before accepting Nemotron synthesis (Nemotron).
- Add Devanagari spelling/localization validation gate for FINAL_TEXT_v2.json before captions/video (spelling).
- Add source aspect-ratio validation (4:7 vs 9:16) at video/caption intake before scale/crop (CAP2).

## docs/PIPELINE_AUDIT_2026-11-07.md part 1/2
PROBLEMS:
- [Verdict 1] Branches `v4-architecture-2026-11-07` and `universal-v1.1` never merged; 4 conflicted files / 8 hunks; no single checkout runs the whole path | parallel development | whole path blocked until merge
- [Verdict 3] V4 holes: Step 9 QC runner, Gate D assembly runner, live author run not built; pre-render controller has no GPU backend wired | not built / not wired | V4 incomplete as runnable path
- [Verdict 4] No production render; only T0 test (8 clips, Colab); `post.py` only on synthetic clips | no production render run | no real video validated
- [Verdict 5] No story through finished pipeline; Kaliya pack missing in new form; old T0 shots lack `look` block, 8 of 8 fail P2 | missing `look` block | 8/8 P2 failures
- [Verdict 6] Two caption engines: `core/captions.py` (universal) and `h3/gate_d_audio.py` (V4) | duplicate implementations across branches | divergence at merge
- [Verdict 7] Style packs unmeasured: no Lab plate values, no LUT file, `braj_earth` no grade numbers, `gates.sat_avg_ceiling` null, gate limits untuned | calibration tools not run on real plates | untuned starting gate values
- [Verdict 8] Dots unreliable on long inputs (empty answers); some batches Super VL only | reviewer limitation | incomplete reviewer coverage
- [Stage 5] Flow image generation is a manual browser step, not code | not automated | manual pipeline step
- [Stage 7] Pre-render controller prepare-only; no GPU backend wired | backend missing | controller cannot trigger render
- [Stage 8] Render not part of controller; T0 only, no production render | separated from controller | no production render path
- [Stage 10] Step 9 QC runner not built | missing runner | final review gate not executable
- [Stage 11] Audio plan assembly runner not built; ElevenLabs needs go | missing runner / external approval | audio assembly not runnable
- [Stage 12] Assembly plans only; never runs ffmpeg | not executed | no actual assembly run
- [Stage 13] Post never run on real clips | synthetic tests only | unvalidated on real footage
- [Stage 14] No analytics file exists | no output file generated | no retention data
- [Stage 15] UI not verified for merged `rules` list from universal `check_pack` | branches not merged | unverified post-merge display

ORDER-PROBLEMS:
- [Stage 8 vs Stage 11/12] T0 render ran before Audio plan / Assembly fixed voice length | should have waited for Audio plan (stage 11) and Assembly (stage 12) duration contract
- [Stage 8 vs Stage 7] T0 render ran outside pre-render controller (Colab) | should have waited for GPU backend wired into controller (stage 7)

ARCH-CHANGES:
- Add a merge gate requiring the two branches to be merged and one checkout to run the full path before any production story enters.
- Insert an Audio-First gate before Render: approved voice manifest + duration contract must be handed to Render; Render blocked without it.
- Wire a GPU backend into the pre-render controller (stage 7) or move Render inside it so no render runs outside the controller.
- Build missing runners as gated stages: Step 9 QC runner, Gate D assembly runner, live author run.
- Make Assembly (stage 12) execute ffmpeg against the audio/video contract instead of emitting plans only.
- Unify `core/captions.py` and `h3/gate_d_audio.py` into one caption service with a shared `.ass` contract between Audio plan and Post.
- Add a style-pack measurement gate: `measure_plate.py`, `make_lut.py`, `calibrate_sat_ceiling.py` must run on real plates and `gates.sat_avg_ceiling` must be non-null before style-pack use.
- Automate Flow image generation or add a gate requiring code-built image jobs (remove manual browser step).

## docs/PIPELINE_AUDIT_2026-11-07.md part 2/2
PROBLEMS:
- [Table row 1] 3 suite failures (flow +2, ui +1) are real-pack tests needing a local untracked pack folder | pack folder absent/untracked | tests fail
- [Table row 2] check_pack on old T0 shots: 8 P2 FAIL (no look block), 1 R1 FAIL, 8 R6 FAIL (5.17 s static gaps) | real content problems of old shots | not stated
- [Table row 3] DEVA template + Shiva story: P5 FAILs on SHOT-02 | known P5 failures | not stated
- [Table row 7] No images, clips, keys under granthstudio; only fonts staged | assets not staged | not stated
- [5] Universal suite: 3 known data-dependent failures, 1 release gate skipped | data-dependent / intentional | tests fail or skip
- [6.1] Branches not merged (4 conflicts, 8 hunks) | branch divergence | not stated
- [6.2] No production render or real post.py run | not executed | limits G1/G2 dE 6, G3 dE 8, static 3.5/4.0 s not tuned; LUTs unchecked on real frames
- [6.3] Style packs unmeasured: no measured plate values (G1 skipped), no styles/luts, post.py falls back to pack grade numbers, braj_earth has no grade numbers (Kaliya ungraded), gates.sat_avg_ceiling null (G2 provisional 181.02) | measurement not run against approved plates/reference frames | Kaliya would export ungraded; provisional values with warnings
- [6.4] V4 runners not built: Step 9 QC runner, Gate D assembly runner, live author run | not built | not stated
- [6.5] Render backend not wired into controller | not wired | not stated
- [6.6] ElevenLabs parser/karaoke path unverified against live API | API shape from public docs only | live use requires approval; risk unverified
- [6.7] Story work not started: writer run, caption text/hook words, Kaliya defects, Mahadev fourth reel | not started by instruction | not stated
- [6.8] Manual checks spec 6.4 not done: LUT approval on 3 stills/act, D65 + two phone review, caption placement vs overlays, DEVA publish gate | not done | not stated
- [7.1] Caption widths use Pillow basic layout, no libraqm; Devanagari conjunct widths over-estimated | missing libraqm | line breaks may differ from real render
- [7.2] Caption size defaults (34 px @1080, outline 8%) and safe zones are tune values | defaults not finalized | not stated
- [7.3] Reviewer tools unreliable: Dots empty on long inputs, Super VL cites unseen code | tool limitations | every finding hand-checked
- [7.4] Automatic log hook not seen firing | needs new session | not stated
- [7.5] V4 branch STATUS.md stale (older suite counts) | not updated | misleading docs
- [7.6] Two review claims rejected as by design (karaoke gap handling, caption centre shift) | by design | documented in TRIAGE_R7

ORDER-PROBLEMS:
none in this slice

ARCH-CHANGES:
- [6.1] Merge branches; replace Gate D caption code with core/captions.py + caption_export.py; wire universal gates into UI (one caption engine)
- [6.3] Add required pre-export measurement/calibration stage (measure_plate, make_lut, calibrate_sat_ceiling) with approved plates and reference frames; create styles/luts; post.py must not fall back to unmeasured grade numbers
- [6.4] Add the three V4 runners: Step 9 QC runner, Gate D assembly runner, live author run
- [6.5] Wire render backend into the controller
- [8.2] Enforce stage order/gate: writer run, caption text and hook words, and approved plates must complete before first render; calibrate_sat_ceiling and limit tuning after render
- [7.1] Integrate libraqm/proper shaping for Devanagari caption widths instead of Pillow basic layout

## docs/AUDIT_2026-11-08_REEL1.md part 1/1
PROBLEMS:
- [Gap 1] pack_to_spec refuses writer V4 shots ("unsafe set id None"); Gate B image prompts cannot be built from new writer output | pack_to_spec reads shot.set, shot.cast, shot.props and shot.keyframes, which V4 rows lack | cost not stated
- [Gap 2] Reel passes all writer gates but is unrenderable; 73 H3 lint errors on reel 1 | H3A author step has not run (13 authored fields missing per shot); writer validator never runs H3 timing/seam checks; editorial length vs lattice handles mismatch; missing mouth states and sound cues | ~20-30% more GPU time per clip (pixel frames grow 192→243 for an 8 s shot) due to H3 head/tail spare frames
- [Gap 3] No speech-rate check before voice; 20 lines above 3.2 words/s (EN SHOT-003 4.4); Gate D vo_fit needs paid ElevenLabs wav first | fit check deferred until after real voice generation | cost not stated
- [Gap 4] Retention rules/check_pack measure pixel frames (70.8 s) while pack_validator/edit use editorial seconds (70.0 s); time-window rules off by handle frames | two clocks (pixel frames vs editorial seconds) used inconsistently | cost not stated
- [Gap 5] Story gate checks self-graded by writer with its own evidence; nothing compares script with SOURCE.md | no automated source-fidelity comparison | cost not stated
- [Gap 6] story.json with no style_pack; writer uses deva_neon; check_pack fails P1 | missing/default style_pack not enforced between writer and check_pack | cost not stated

ORDER-PROBLEMS:
- H3 conversion/lint (v4_to_h3 + linter) ran before H3A author step supplied 13 authored fields per shot | should have waited for H3A authoring
- Writer gate passed before H3 timing/seam checks (lattice handles, mouth states, sound cues, H3-01) | should have waited for H3 timing/seam validation
- Voice generation/Gate D vo_fit proceeded before speech-rate check (SPEECH-01) | should have waited for words-per-second validation per language

ARCH-CHANGES:
- Add V4→spec contract/adapter (_v4_view) between writer output and pack_to_spec so Gate B image prompts can be built from V4 rows
- Add H3A authoring stage before H3 conversion/lint; add H3-01 timing/seam rule to writer gate so writing cannot pass before legal handles, mouth states, and sound cues
- Add SPEECH-01 pre-voice gate (words per second per language) before paid ElevenLabs generation/Gate D vo_fit; lock audio length before video build
- Unify timebase: editorial length in check_pack and core/timeline; pixel frames only for render allocation; hand off single timebase contract/file between stages
- Add SRC-01 source-fidelity gate comparing story.json source_sha256 to SOURCE.md before writer gate closes
- Add style_pack presence/default gate in write_pack/check_pack before pack validation

## research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md part 1/1
PROBLEMS:
- [cue_sheet.json / score/ep1/cue_sheet.json] Music cue sheet was built on v3 lengths (70.0 s) instead of v4 (72.833 s). | Root cause: score/ was not updated when the shared timeline advanced to v4; cues were planned against superseded picture length. | Cost not stated.
- [v3 voices / table note] Voices were time-stretched up to 1.12× to fit a pre-locked picture. | Root cause: video/clips were rendered before real voice lengths were known; picture was fixed first. | Cost not stated.
- [White-outs section] White-outs only move if after an extended cut; otherwise must be recomputed as "shot N + X". | Root cause: white-out timing was not systematically rebased to the v4 shared timeline. | Cost not stated.
- [build_mix_filter / "the None is the BGM slot"] BGM slot is None in the final mix filter. | Root cause: background music is not wired into the merge; music lives outside the build. | Cost not stated.
- [Disk D note] About 3 GB free; one build is about 470 MB. | Root cause: large build outputs on limited disk. | Cost not stated.

ORDER-PROBLEMS:
- [Video/clip render / v3 picture] Video clips and picture were rendered before real voice lengths were known. | Should have waited for: voice tracks/timings (vo_v4, vo_tracks_report.json) so picture could be built to audio length.
- [Cue sheet] Music cue sheet was built before the v4 timeline was frozen. | Should have waited for: editorial_by_lang.json frozen at gate M1 and final v4 shot lengths.
- [White-outs] White-outs were placed/moved against the old timeline. | Should have waited for: final v4 extensions (shot N + X) before positioning white-outs.

ARCH-CHANGES:
- Add a gate: voice tracks (build_vo_tracks.py → vo_v4 + vo_tracks_report.json) and the shared timeline (editorial_by_lang.json) must be locked before any clip/video render or editorial frame extension; prevents picture-before-audio.
- Make editorial_by_lang.json a versioned contract: cue_sheet.json, white-outs, and music manifests must declare dependency on its version/hash and auto-regenerate when it changes; prevents stale v3 cues.
- Make BGM a required input to build_final_reel.py: replace the `None` slot with a mandatory manifest/music file from score/gate_d_bridge.py write_bgm_manifest, validated by h3/gate_d_audio.py, so no final reel is muxed without a music decision.
- Move editorial timeline generation ahead of clip rendering: compute shot lengths from voice first via editorial_by_lang.py, then render clips to those lengths, removing the separate post-render repair step and superseded versions.

## CHECKLIST_ARCHITECTURE_2026-11-07.md part 1/1
PROBLEMS:
- [2.1] h3/SPEC.md retains old dialogue block and mode_to_video_shift_map | spec not refreshed after dialogue/mode changes
- [2.6] leftover old speech code in h3_director.py | obsolete speech code not removed after voice-engine changes
- [3.2] Nemotron/Dots review agents return false positives | automated review noise
- [11.3] round 6 found 1 low defect | not stated

ORDER-PROBLEMS:
none in this slice

ARCH-CHANGES:
- Add Gate D audio-mix gate before video render/Step 9 (1.5, 2.7) so voice audio is locked before picture is built to its length
- Freeze endpoint contract before coding (4.3) as a gate between UI and pipeline implementation
- Require voice .wav manifest (2.4) and V4H3 → H3A converter/author contract (2.5) as a file handed from voice stage to video/author stage
- Run ffmpeg libass+HarfBuzz preflight (9.8) before caption burn-in in post.py
- Enforce per-language voice_engine locks in H3 linter/compiler/router (1.4) so only the approved audio render can proceed

## STATUS.md part 1/2
PROBLEMS:
- [voice rule] Per-language `<vo-dir>/<lang>/<shot_id>.wav` required for narration/dialogue; missing = refusal, never H3 fallback | Owner-supplied ElevenLabs voice files not provided (code cannot supply) | Shot refusal / pipeline halt
- [POST-UNGRADED] Act with no LUT file or grade numbers warns POST-UNGRADED; `colour_report.json` carries `graded: false` | Missing approved plates / grade numbers / LUT approval (owner inputs) | Ungraded export warning
- [sat ceiling] `gates.sat_avg_ceiling` is null; `ANIME_RELEASE=1 pytest core` fails | No approved reference frames/plates measured; no first approved render | Release gate blocked
- [Kaliya pack] Reels 2–5 short (60.0/47.6/51.1/55.6 s vs 65–75 s target); CHAR-INDRA/BRAHMA/NARADA/SARASVATI and PROP-KALI-KAMLI missing from bible; PROP-KANSA suspicious | Incomplete pack/bible; owner has not answered | Gate A plan not approved
- [caption width] Pillow basic layout (no libraqm) over-estimates Devanagari conjunct widths; line breaks may differ from libass | No Pillow build with raqm | Caption timing/position inaccuracy
- [ElevenLabs alignment] Alignment shape from public docs only, unverified against live response | No live ElevenLabs call (awaiting owner's go) | Karaoke/phrase fallback may mismatch real API
- [render_controller gap] `render_controller` does not pass `loudness` to assembly plan; needs measured clips | Wiring not implemented | Assembly plan lacks loudness data
- [UI leftovers] Rejected-stage wizard does not auto re-open after re-run; typed pack name reverts on poll; `app.js` message bar success class; `PLACE_TEXT_OVERRIDES` Kaliya-only | Unresolved UI bugs | Authoring errors / job misconfiguration
- [no render] No real render run; Step 9 runner, Gate D assembly runner, live author run not built | Not built / awaiting owner inputs | Pipeline unverified end-to-end
- [P1 story.json] Missing `story.json` = FAIL | No story file supplied yet | Pipeline cannot start

ORDER-PROBLEMS:
- [render_controller → assembly plan] Assembly plan runs before loudness is available | Should wait for measured clips / loudness values from render_controller

ARCH-CHANGES:
- Add an audio-lock gate before Render in the UI wizard: validate per-shot voice files and mix the voice branch (`build_voice_branch`) first; hand audio length to render as a contract file so video is built to audio length.
- Insert a loudness measurement stage between clip render and assembly: `render_controller` emits measured loudness (`loudness.json`) and `h3/assemble_reel.py` consumes it before assembly.
- Make Gate D a pre-render audio gate requiring voice files and `core.json` `delivery.audio` loudness target before Gate C/Render proceeds.
- Add a pipeline-entry gate: `story.json` must exist and pass P1 before writer/image steps run.
- Replace POST-UNGRADED warning with a hard colour gate: approved plates, LUT, and grade numbers must be delivered before `post.py` colour export.
- Add libraqm/Pillow build or a libass-compatible caption width contract so Devanagari cue widths match real render.

## STATUS.md part 2/2
- [Unverified: Met Museum reference (HTTP 429)] Met Museum reference returns HTTP 429 | external rate limit / blocked source | cost not stated
- [Unverified: MiniMax H3 licence text] MiniMax H3 licence text unverified | legal usage uncertainty | cost not stated
- [Unverified: sthayi bhava names from general knowledge] sthayi bhava names sourced from general knowledge | potential acting-terminology inaccuracy | cost not stated
- [Unverified: all palette hex values are design targets] palette hex values are design targets only | visual style not finalized | cost not stated
- [Loop system: untouched; old-base branch uncommitted] loop system untouched; `owner-free-review-opus-low-2026-11-04` branch in loop_p0 uncommitted | deferred decision / branch divergence risk | cost not stated
- [Granth Studio / Gajanan Maharaj: paused] Granth Studio / Gajanan Maharaj paused | blocked production track | cost not stated

none in this slice

- Add reference-families stage (identity, turnaround/pose, acting per character) before keyframe/shot generation; gate blocks keyframes until references approved
- Add controlled-batch/render-manifest gate before visual QA; frame review cannot run without Kaggle batch
- Add Opus-review gate before prompt upgrades merge into MASTER_PROMPT_v2.2.md
- Enforce `check_pack.py` as hard gate on `<id>.direction.json` before `write_pack.py --staged` execution
- Merge, close, or discard uncommitted `loop_p0` branch to stop untouched loop system diverging

## research/AUDIO_PLAN_FROZEN_2026-11-06.md part 1/1
- [Frozen decision 1] Independently generated clips cannot share one score | no shared audio state between renders | music removed; owner overlays music on finished reel (audio costs nothing beyond video render per decision 7)
- [Frozen decision 5] Clip loudness varies up to 14 dB between T0 clips | different render arms/clips measured at different integrated LUFS (-23.7 to -10.2) | gain-match required before join
- [Frozen decision 5] Dynamic loudnorm second pass unreliable on 5 s clips | loudness-range logic unstable on short audio; changes dynamics differently per clip | not used; plain linear gain + limiter instead
- [Frozen decision 6] Drift can appear at clip 4 | QA on only the first clip misses later clips | every clip must be QA'd (normal clip QA, free)
- [Rejected review item] Vocal tools do not separate effects from music | no source separation capability | prevention in prompt plus QA, not post separation
- [Nemotron proposal not adopted] Negations in soundscape wording ("No music, no score...") violate model prompting rules | linter warns on negations | positive wording required

- [Frozen decision 5] Join before gain-match | gain-match every clip before the join | join should wait for per-clip loudness measurement and linear gain
- [Frozen decision 5] Fades before gain | 5 ms fades applied after gain at every cut | fades should wait for gain
- [Code changes C8] Soundscape compiled before sound_beds | compiler inserts location bed into soundscape | compiler should wait for registry sound_beds
- [Frozen decision 6] Separate audio test render instead of real-clip QA | QA on real clips as part of normal clip QA | separate test should not replace or precede real-clip QA

- Add `sound_beds` registry stage (location id → phrase ≤12 words, fixed casing/punctuation) before soundscape compilation
- Add `loudness_plan(measured)` stage in `assemble_reel.py` (pure gain to -16 LUFS, limiter at -1.5 dB) as a gate before the join; write `loudness.json`
- Enforce audio chain order in code: gain → 5 ms fades → join
- Add linter SD-03 gate after compilation (soundscape starts with "Sound effects only:" and location bed)
- Remove separate audio test render stage; QA every real clip during normal clip QA
- Add template-change-and-re-render gate for leaks; never patch single shots

## research/VOICE_SYSTEM_DESIGN_2026-11-09.md part 1/1
PROBLEMS:
- [bible.json voice_map] placeholder voice IDs (`placeholder-NARRATOR-hi`) instead of resolved ElevenLabs IDs | voice map not filled with real account voices | cost not stated
- [ElevenLabs account] no Hindi voice in the account | account holds only English premade and Marathi professional voices; Hindi voices exist only in shared library, not added | cost not stated
- [h3/voice_engine.py / h3/voice_manifest.py] voice rules and wav manifest defined but nothing calls ElevenLabs | voice engine not wired to the paid API | cost not stated
- [Gate D / vo_fit] `vo_fit` checks generated wav length against the slot after audio exists | slot length validated against audio rather than audio built to a pre-frozen slot | cost not stated

ORDER-PROBLEMS:
- none in this slice

ARCH-CHANGES:
- Add a pre-paid cast gate in `director/voice_cast.py`: reject `--allow-paid` unless `voices_cast.json` resolves every speaker × language in `shots.json`, passes lint, and estimate is within cap
- Add a freeze-file gate to Gate D (`h3/gate_d_audio.py`): refuse to mix wavs unless the freeze file exists and owner has listened/validated voices
- Add a mandatory hard-name pronunciation test stage before S6 full run: test candidate spellings for hard names first and store results in the manifest
- Make the timing slot derive from measured audio duration: freeze the slot from ffprobe-measured clip length before video lock or mix, so `vo_fit` compares against an audio-first window

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 1/4
PROBLEMS:
- [Cross-check #6] post.py and render_controller pass bgm=None instead of wiring story.json BGM manifest | BGM not wired in build step 10 | cost not stated
- [Cross-check #17] story_plan.json says 68 s, shots add to 70.0 s | Duration mismatch between story plan and shots | cost not stated
- [Cross-check #18] Cue sheet v1 reads voice windows from pack, not rendered voice | Score built before rendered voice timings exist | cost not stated
- [Cross-check #1] Tempo changed at 41 s, not at act change/hard cut | Invalid tempo placement | cost not stated
- [Cross-check #2] Re-hook at 26 s outside retention window 31.5–42.0 s | Retention timing violation | cost not stated
- [Cross-check #7] H3 effects overlap planned hits (bell 0–0.8 s, 43.0–43.5 s, 48–49 s) | Score fills same band at same moment as effects | cost not stated
- [Cross-check #8] First white-out rounded to 43.1 s | Rounding instead of frame-exact time | cost not stated
- [Cross-check #9] 60.0 s white-out and end sting fall under speech | Music hits under voice | cost not stated
- [Cross-check #10] Shiva's reveal at 48 s inside drum and bass act | Drop placed on divine reveal | cost not stated
- [Cross-check #11] Live imports reference video as .mov only | Picture reference format mismatch | cost not stated
- [Cross-check #12] Serum macros following clip automation not verified | Unverified integration | cost not stated
- [Cross-check #13] Hybrid-cinematic or electronic style not chosen | Style decision deferred | cost not stated
- [Cross-check #14] Phones roll off below ~200 Hz and play mono upright | Playback constraint | cost not stated
- [Cross-check #15] MCP tool names unknown (D:\ableton not on GitHub) | Adapter not written | cost not stated
- [Cross-check #16] PROJECT_LOG.md on PC, unreachable | Log inaccessible | cost not stated
- [Cross-check #19] Drums, chants, vocal horns need real recordings | Uncleared/unsourced assets | cost not stated
- [Table: Where BGM enters] Plan proposed new ableton_serum_director.py + 3-stem mix, but repo already has h3/gate_d_audio.py taking one BGM track | Architecture based on incorrect repo state | cost not stated
- [Table: BGM manifest] Plan said bpm 120, lufs -18; repo needs track_id, path, license_type, bpm, lufs; empty list = no BGM | Manifest schema mismatch | cost not stated
- [Table: Loudness] Plan said -14 LUFS; core/core.json target -16 LUFS, true peak -1.5 dB, AAC 192k | Loudness target mismatch | cost not stated
- [Table: Hold-Burst-Hold spans] Plan referenced stage_frame_spans in shots.json; only in H3 shot JSON after convert_deva_shots.py | Data source mismatch | cost not stated
- [Table: Colour acts] Plan said PH-DAWN-PLAY, PH-POISON; field is look.act / look.phase + look.palette_id | Field name mismatch | cost not stated
- [Table: Extended Ableton MCP] Plan said in ableton-claude-final; Rule 31 says D:\ableton, not in GitHub | Tool location unverified | cost not stated
- [Table: NL to Serum preset] Plan said Celian-mrc/serum-mcp; existing tool maps only 7 of 127 parameters and is a tutorial project | Preset generator inadequate | cost not stated

ORDER-PROBLEMS:
- [Cross-check #18] Score S2/S3 built from pack voice windows before rendered voice timings exist | Should wait for rendered voice windows
- [Pipeline Gate D / Cross-check #6] Gate D mix runs with bgm=None instead of reading story.json BGM manifest | BGM manifest must be wired before mix

ARCH-CHANGES:
- Add Score stage (S1 cue sheet, S2 plan, S3 Ableton build, S4 render/check vs picture) between Gate A and Gate D, with owner gates M0/M1/M2
- Add contract: `audio/bgm_manifest.json` (track_id, path, license_type, bpm, lufs; empty = no BGM) from story.json/UI set_bgm to Gate D; post.py/render_controller must read it instead of passing bgm=None
- Add contract: `cue_sheet.json` frame-exact reel clock from Score S1 to S2/S3/S4; v2 must read rendered voice windows, not pack windows
- Add gate: `score/plan_check.py` enforces the 12 skill rules in code; no weakening a rule to pass
- Add stage: export picture reference as .mov before Score S3 Ableton build
- Merge/use existing: route BGM through existing `h3/gate_d_audio.py` single continuous track + sidechain ducking instead of new `ableton_serum_director.py` + 3-stem mix
- Add adapter stage: thin Claude Code adapter for local MCP at `D:\ableton` after connection check (build step 1)
- Add gate/contract: loudness -16 LUFS, true peak -1.5 dB, AAC 192k per core/core.json at Gate D

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 2/4
**PROBLEMS**
- [Architecture rule] Musical decisions made in Ableton before JSON lock | Ableton used as composition environment instead of playback/render | Failed MCP call, crashed Live set, or changed preset loses the composition.
- [Old 60/120 tempo map] Tempo changed at 41 s on a non-act cut | BPM/genre changed outside act change | Broke the act-change-only tempo rule.
- [Re-hook timing] Re-hook at 26 s | Placed outside retention window (31.5–42.0 s) | Outside retention window.
- [Voice comes first] Music composed without voice-gap priority | Score not built around 83% narration/dialogue coverage | not stated.

**ORDER-PROBLEMS**
- [Architecture rule] Ableton builder (step 6) run before JSON decisions (steps 1–4) written and tested | Should wait for `music_bible.json`, cue sheet, `score_plan.json`, and `notes/*.json` | Lost composition on MCP crash/Live crash/preset change.
- [Voice comes first] Music spotting/placement before voice gaps locked | Should wait for voice-window/gap data so themes and hits land in gaps | not stated.

**ARCH-CHANGES**
- Hard gate: block `ableton_build.py` until `score_plan.json` passes `plan_check.py` and `notes/*.json` exist; Ableton becomes render-only, never composition.
- Add voice-gap manifest stage before spotting planner (step 3); planner consumes locked voice windows.
- Enforce file contract: `shots.json` → cue sheet → `score_plan.json` so planner cannot run without cue sheet.

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 3/4
PROBLEMS:
- [Rule 9] Sample packs with Content ID claims or melodies resembling known themes used | `license_type: "original"` not enforced | Content ID claims
- [Serum parameter problem] Raw Serum filter cutoff not automatable in Ableton | cutoff not among 37 verified Configure-mode contracts | macros must be used instead
- [.als XML injection] Serum state injected into `.als` XML | unsupported `.als` modification | reopen failed with "Unknown Compound Stream Type"
- [render_to_file] Reliance on Ableton render API/tool | `render_to_file` fabricated; no offline export in API | no automated render route
- [MCP conflict] Installing CanArslanDev/ableton-live-mcp | two Remote Scripts compete for control surface | control surface conflict
- [PySceneDetect] Shot detection run on footage | `shots.json` already gives frame-accurate cuts | detection could only add error
- [faster-whisper] Voice transcription run | voice `time_range` already in pack for en/hi/mr | unnecessary transcription
- [D:\CinescopeAI workspace] Separate workspace created | breaks `shots.json` single source of truth (Rule 22) | pipeline not story-agnostic
- [post.py] `None` passed to Gate D instead of manifest track | manifest track not wired into Gate D | score not handed to mix
- [Serum load failure] Serum preset fails to load | preset/load issue | fallback to Wavetable/Drift logged
- [Ableton API] Tempo/time-signature changes attempted in Live | API cannot write them | note writer must apply tempo map
- [Ableton API] Arrangement locators written via API | locators read-only from API | MARKERS MIDI track used instead
- [check_score.py] Raw render differs by > one frame (42 ms) | length tolerance | file refused before trimming
- [Kaliya Mardan] No committed pack on any branch | pack uncommitted | cannot be first test reel

ORDER-PROBLEMS:
- Score notes written before checking all three language voice time windows | Rule 11: planner must check en/hi/mr gaps before writing notes | voice gaps won't hold across languages
- Gate D mix runs before manifest track is passed | post.py previously passed `None` | score absent from Gate D mix
- Automation envelopes created before confirming Serum macros respond in Live | confirmation required once in Live before first build | macros may not drive Serum
- Live set run before `get_session_info` connection check | connection must be verified first | set may fail to run
- M2 final listen before automatic `check_score.py` checks pass | all checks must pass before M2 | unchecked score reaches owner gate

ARCH-CHANGES:
- Add `get_session_info` connection check as a hard gate before opening/running the Live set
- Add voice time-range/gaps contract (en/hi/mr) that planner must read before writing notes; block build if missing
- Add Serum Macro 1-4 response confirmation in Live as a pre-build gate before automation envelopes are written
- Make `post.py` require the manifest track path as a required input to Gate D instead of accepting `None`
- Add license/copyright check stage before preset/score composition: verify `license_type: "original"` and no Content ID resemblance
- Add `check_score.py` automatic gate after render: all checks (length, peaks, cuts, hits, voice windows, presence, silence, continuity) must pass before M2
- Add preset manifest validation before build: every preset must exist in `presets/` and match bible; log fallback if Serum load fails

## research/SCORING_SYSTEM_PLAN_2026-11-09.md part 4/4
PROBLEMS:
- [Open item: Reel length] `story_plan.json` Reel 1 `reel_seconds` 68.0 vs 10 shots summing to 70.0 s; score follows shots (70.0) unless owner says otherwise | story length inconsistent with shot-table sum; no single authoritative reel length
- [Open item: Audio decision] main frozen plan (2026-11-06) says music removed; v4 handoff (2026-11-07) says one optional BGM track; plan assumes 11-07 | contradictory music rules across plan versions not reconciled
- [Step 1] Adapters cannot be written: real MCP tool names from `D:\ableton` and the NL-to-Serum tool interface/output are unknown (PC not linked or MCP not pushed; tool folder/repo unnamed) | missing real tool-name and preset-output contract
- [Open item: Live/Serum] Live API cannot write locators, tempo or time signature; clock-mode + MARKERS workaround depends on unconfirmed MCP clip-automation envelopes and Serum Macros 1–4 response | platform API limitation plus unverified dependency

ORDER-PROBLEMS:
none in this slice

ARCH-CHANGES:
- Add a length-reconciliation gate before scoring: story `reel_seconds` must equal the shot-table sum (one authoritative length) and `score_plan.json` must follow it
- Add a single audio-rule manifest/gate resolving the 11-06 (music removed) vs 11-07 (optional BGM) contradiction before the score build proceeds
- Add an interface-contract gate for step 1: publish the MCP tool manifest (`D:\ableton` real names) and NL-to-Serum output spec (folder/repo + `.SerumPreset` or Live state) before adapters are written
- Add a capability gate before steps 6–7 confirming MCP exposes clip automation envelopes and Serum Macros 1–4 respond to them
