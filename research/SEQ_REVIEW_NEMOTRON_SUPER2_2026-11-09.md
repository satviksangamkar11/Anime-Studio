# Nemotron Super merged report

# Anime-Reel Pipeline Review: Merged Report

## 1. PROBLEMS (deduplicated by stage, most expensive first)

**Story / Writer**
- **[C10, P5]** Single Claude subscription for all heavy writer work; reviewers run together on one OpenRouter key with huge slices. Root cause: no per-app `CLAUDE_CONFIG_DIR`/budget watch; no reviewer concurrency control. Cost: work blocked for days (weekly limit hit); hours of review time (empty answers, thought traces, 429s).
- **[C9, PROJECT_LOG 11-08 13:57]** Full-answer repair rewrite instead of targeted fix; Opus rewrote 3e1 as 11 shots, failed validators, originals restored. Root cause: no repair-scope limit; over-broad model edits. Cost: one Opus call + failed stage + redo.
- **[PROJECT_LOG 11-08 06:24, 06:37]** Writer CLI on personal Pro account with exhausted weekly limit; `429 usage_limit_reached`; no Opus call until Nov 12. Root cause: wrong stored login, no separate app-account config. Cost: writer stopped for days.
- **[Q6, V9, W19, PROJECT_LOG 11-08 12:10]** Voice windows sized to whole/rendered clip, not editorial cut; 14 of 54 lines over cut up to 1.46 s; false “54 of 54 fit”; 20 lines >3.2 w/s; pixel vs editorial seconds mismatch (70.8 vs 70.0). Root cause: audio sized before editorial timing plan; no speech-rate gate; clip length estimated from text. Cost: rework after clips exist; 19 of 32 batch-1 clips over slot (up to 2.6x).
- **[Q3, Q4, W9]** H3 prompt compiler glues text without language check; duplicates, glued clauses, curly apostrophes, jargon; no negative/“only these characters” constraint; converter emits “with <cue>” glue. Root cause: no compiler quality gate; glue not fixed at source. Cost: lower clip quality every shot; cobras/extra figures.
- **[Q11, W7, PROJECT_LOG 11-08 20:30, 19:50]** No independent story-fidelity check vs `SOURCE.md`; writer self-grades; Yajna invented; Kali garland beads instead of skulls; keyframes contradict script. Root cause: source fact checked after prop/env creation. Cost: regen of CHAR-KALI, SHOT-003, affected shots.
- **[Rule 34]** Generic official mouth sentences ambiguous/contradictory with several people on screen. Root cause: ambiguous compiler output. Cost: still open (owner decision).
- **[Rule 19, PROJECT_LOG 11-07 22:51]** Off-style bible reaches Stage 2; BIBLE-06 validator regex rejects “plain neutral grey backdrop.” Root cause: no pre-gate style enforcement. Cost: repair call; stage 2 did not advance.
- **[Rule 39, PROJECT_LOG 11-08 14:49]** Older `approval_sheet.csv` used as text baseline instead of `shots.json`; old pre-fix text fails SPEECH-01 on 43 of 54 lines. Root cause: wrong source of truth. Cost: 8 lines regressed; pack rebuilt.
- **[PROJECT_LOG 11-08 12:10]** `pack_to_spec` refuses V4 shots missing set/cast/props/keyframes; `v4_to_h3` lint (73 errors) not run before writer validator; story gates self-graded. Root cause: no pre-pack validation gate. Cost: audit gaps; downstream blocked.
- **[Rule 20, 30, P1, W14, PROJECT_LOG 11-08 00:32/02:18/02:23/02:40/02:41]** Heredoc scripted edits inserted real line breaks/backspace/control chars into strings (HEX regex, SyntaxError, stray correction note, `retention_rules.py` R2/R5 inverted). Root cause: heredoc for backslash text instead of Edit tool; no `ast.parse` gate. Cost: parse failed until fixed; every V4 row failed; four slips on 11-09.
- **[PROJECT_LOG 11-08 01:07, 01:16]** CLI result keeps only text after last tool call (answer began mid-JSON); `v4_to_h3` reads `stage_1_raw.json` envelope, not `story_plan.json`; route=Ref2VA → `run_kaggle` ValueError. Root cause: CLI turn truncation; wrong source file; route enum mismatch. Cost: writer stopped during repair; Kaggle build fails.

**Keyframe Images**
- **[Rule 31, Q5, W7]** Start/end keyframe inconsistency: SHOT-002 loses two arms; SHOT-008 set morphs (Brahma standing vs seated); Shiva hair flickers; 8A made without script check; Brahma seated not rising; missing sages/Shiva. Root cause: A/B generated separately as options, not start/end pair; keyframes reviewed alone, not against per-second script. Cost: re-render ~2 units per shot; full redo of 8A + re-render.
- **[Rule 32, Q1]** Full compiled prompt not read before GPU; sound notes named drawable creatures; “serpents hiss” drawn as cobras; black cobras in SHOT-008. Root cause: only blank lines and one word checked; video model draws every noun. Cost: wasted re-render; second re-render ~1.2 units / ~30 min.
- **[F1, F2, F3, Q2, W8]** Keyframes accepted from small thumbnails/reviewer verdicts; A and B not defined as start/end in packet/UI; clip judged from 16 frames; picture reviewer claims trusted without full-size verification. Root cause: no full-size side-by-side pair review; advisory reviewer not verified. Cost: full-size defects (letters in sparks, cropped sages, wrong crowns); wrong all-clear to owner.
- **[F4, F5, PROJECT_LOG 11-08 18:58–19:49]** 5–8 submits per image; stale/duplicated tile names; exact-name picker rule missing; renames not persisting; chip selection before sheet renames saved; picker shows 0 rows; row click closes without attaching; tile rename failed twice; reviewer BLOCK A/B; Kamadeva solid red hands/feet; ENV-MARKANDEYA-ASHRAM missing kusha mats/smoke. Root cause: picker UI unreliable across resolutions; capture overflow/CORS; bible `sheet_prompt` wrong; env details missing. Cost: shots blocked, not submitted; remaining jobs not started; regen required.

**Video Render**
- **[Rule 28, C3, C4]** First live render burned 13 min with nothing running; 19.7 MB `run.py` never reached VM; `colab exec -f` hung above ~7 MB; size fix guessed untested (11.3 MB same hang). Root cause: no script-size check under ~12 MB; no proof `/content/out` exists within 180s. Cost: 13 min burned units; 1.68 units; 0.57 units.
- **[C1, C7]** Clips fetched only at run end; local folder never created; six finished clips lost; `FILES.txt` split on spaces with spaces in names. Root cause: no per-shot `fetch_ready`/folder-before-use gate; runner path-parsing bug. Cost: full G4 session plus second session; extra billed minutes.
- **[C2, C5]** A100 re-render no HF token/retry/unproven GPU; owner’s T4 mistaken for team G4; no session-ownership rule. Root cause: model download 429/hang; session ownership confusion. Cost: A100 session, 0 clips; G4 terminated 2 min into install; ~0.3–0.9 units.
- **[C6]** Full batch before H3 prompt tested on GPU; blank line read as second generation request. Root cause: no single-shot canary (`--ids SHOT-001`). Cost: ~0.9 units, 15 min.
- **[Rule 30, W10, W18]** Wan2GP refused blank-line prompt rc=1 in 10 s; `chumpy-0.71` HTTP 504 failed 3 paid sessions; three failures hid behind each other. Root cause: no prompt sanitization; external URLs not curl-tested before paid session; no real-VM proof. Cost: failed generation; 0.58 units, 3 sessions, ~25 min.
- **[Rule 30, W16, W17]** Unnamed T4 costs 1.15 units/h, CLI cannot stop it; failed `colab new` left unnamed G4 billing 10 units/h; runner looped after ALL DONE, G4 billed 10 units/h for ~10 min. Root cause: session ownership confusion; no VM record in CLI state; no stop condition on `RESULT.json` ALL DONE. Cost: 1.15 units/h; ~1.16 units + 25 min; ~1.67 units.
- **[Rule 31]** Phone/remote viewers cannot receive files over 30 MiB; must create `_small.mp4` (~3 MB). Root cause: recipient file size limit. Cost: delivery rework.
- **[Rule 31]** Runner ends with error but session kept; manual colab session check required. Root cause: runner behavior. Cost: orphan billing.
- **[Rule 40, PROJECT_LOG 11-08 14:54]** Render S009 failed 3x (no pre-flight URL check, `chumpy-0.71` HTTP 504); `h3_author.py --live` SHOT-001 failed 5 rounds (lint before Gate B; boundary PNGs only exist after Gate B). Root cause: no curl pre-flight; author lint ran before Gate B. Cost: 3 failed sessions; shots 2–10 blocked.

**Voices / Audio**
- **[V9, W19, PROJECT_LOG 11-08 12:10]** 19 of 32 batch-1 clips overran slot (up to 2.6x); real slow voices 1.7–2.4 w/s vs 3.2 rule on paper; windows sized to rendered clip (6.6–10.1 s) not editorial (5–8 s); 14 of 54 lines past cut up to 1.46 s; false “54 of 54 fit”; no pre-voice speech-rate check (20 lines >3.2 w/s). Root cause: clip length estimated from text; audio sized before assembler editorial plan; Gate D not run first. Cost: 14 lines over cut; rework after clips exist.
- **[Rule 39, PROJECT_LOG 11-08 14:49]** Older `approval_sheet.csv` used as baseline instead of `shots.json`; old text fails SPEECH-01 on 43 of 54 lines. Root cause: wrong source of truth. Cost: 8 lines regressed.
- **[V10]** Promised speed + shorter text would fix length before testing; speed 1.15 gave same length (4.08 → 4.16 s). Root cause: knob not tested on one cheap clip first. Cost: wasted calls/sends.
- **[V4, V5]** ElevenLabs previews were WAV named `.mp3`; preview URL treated as pronunciation/speed/names test. Root cause: header not checked with `ffprobe`; preview is voice demo, not our names. Cost: phone showed silent.
- **[V6]** Five blockers found only at pre-flight (shared-library voices, slot limits, model/language mismatch, double-cost voices, w/s over limit, untested hard names). Root cause: no free pre-flight before first paid call. Cost: cost not stated.
- **[V2, V3]** Wrong claim no Hindi voice (Granth not searched); new `voice_library.py` instead of copying Granth code. Root cause: no voice-library lookup; `source/a1_eleven.py` not copied first. Cost: cost not stated.
- **[V8]** C: reached 1 MB free during long job. Root cause: no free-space pre-check. Cost: cost not stated.
- **[PROJECT_LOG 11-07 01:47]** Voices after render; no voice clips supplied. Root cause: audio scheduled after video. Cost: shared Foley render ran before voices.

**Music**
- **[Rule 46 amendment]** Music scored against `FINAL_TEXT_v2.json` permission windows instead of real speech. Root cause: permission windows treated as actual speech timing. Cost: 14 of 54 lines wrong.
- **[Rule 31]** No music score exists; Doseedo research stopped on owner’s word; nothing installed/called. Root cause: missing music score. Cost: missing music score.
- **[Rule 47]** Music gate M1 can run before shared timeline locked. Root cause: no `editorial_by_lang.json` freeze before M1. Cost: re-communication to music session.

**SFX / Mix**
- **[Rule 49 (8)]** H3 model SFX as loud as voice (gaps -18.6 dBFS vs voice -18.4); no voice > hits > music priority; no per-shot SFX study. Root cause: no priority hierarchy. Cost: reel sounds jumbled.
- **[Rule 50 (3)]** r1-r3 renders wasted; muting VOICE fader to measure bus removes sidechain key. Root cause: no separate voice-only render. Cost: r1-r3 wasted.
- **[Q1]** Sound notes named drawable creatures; video model drew them (black cobras). Root cause: prompt carried sound notes naming drawable things. Cost: second re-render ~1.2 units / ~30 min.
- **[W1]** Sparkle batch tool found no inputs, exited 0, printed nothing; misread as tool fault. Root cause: batch tool does not print input count or fail on zero. Cost: cost not stated.

**Captions**
- **[Rule 51]** Devanagari conjuncts broken (ब्रह्मा → बरहमा) in v4-v7. Root cause: simple shaping instead of complex shaping. Cost: broken text in v4-v7.
- **[Rule 46]** libass silently drew system font; ASS family name not set to font ID 1 “Mukta ExtraBold”; plain “Mukta” used. Root cause: wrong font family ID. Cost: wrong font rendered silently.
- **[PROJECT_LOG 11-07 03:02, 03:48]** Caption/cc files requested, none found; W1 FAIL `test_stage_1_data_carries_the_selected_languages` after gate merge (LANG-03/caption-check merge affected stages 1–3). Root cause: no caption files supplied; caption-check merged before stage 5 gate. Cost: cost not stated.

**Assembly / QC**
- **[Rule 12, P5]** Dots reviewer slow; Nemotron/Xing/OpenRouter reviewers run together with huge slices → empty answers, thought traces, 429s. Root cause: slow reviewer; no concurrency/budget control. Cost: slow; hours of review time.
- **[Rule 21]** Flow agent packet missing items; `ui/test_packet_and_roots.py` fails. Root cause: packet missing items. Cost: test failure.
- **[Q2, Q7, Q8]** Clip judged from 16 frames; wrong “all clear”; `aac` audio never listened to/measured; wrong state reported from agent reports before looking. Root cause: no automatic frame scan; no audio measurement; trusted agent text. Cost: wrong all-clear to owner; unknown audio; wrong state reported.
- **[W5]** Old renders (shots 7, 9 from 11-08 keyframes) sent as newest without source keyframes. Root cause: no keyframe provenance metadata. Cost: cost not stated.
- **[W6]** Two code trees drifted; compile mixed them; fix lost. Root cause: no single live tree synced before fix. Cost: fix is lost.
- **[W20]** Gate D retention failures (86% vs 90% coverage, 27 vs 38 words, dead air to 1.5 s) risked silent waiver. Root cause: findings treated as build issues or waived without owner record. Cost: risk, none stated.
- **[PROJECT_LOG 11-07 04:57–04:59, 08:28]** Core suite collection blocked by missing modules (`test_pack_rules`, `test_cvd`, `test_lut`, `test_make_lut`, `test_timeline`, `retention_report`); stray `cat` hung 120s. Root cause: other workers’ files missing; shell hang. Cost: 3×60s wait; 60s wait; 120s hang.
- **[PROJECT_LOG 11-08 01:09–01:17]** Audit gaps: queue/review lack story arg; `pack_to_spec` outputs_root lacks `anime_` prefix; `read_images` wrong root; `api.review` hardcodes Kaliya; `download_queue` collect→‘final’; palette gate not wired; bridge pattern missing `--pattern`; wizard sends `shots.json` to `h3_prepare` with no convert step; export G12 not built; `bible_to_sheet_jobs` not in COMMANDS; `images_dir` never set; Gate B counts sheets; `playable()` 4.5–6.5 s; `run_kaggle` KeyError ‘mode’; `style_bible.load(deva_neon)` FileNotFound; no `asset_manifest`/`fallback_history`; post vs gate_d output paths differ; `findJobsFile` SHOT-001 vs jobs SHOT-001A; `packet()` 1..60 cap; old bible schema; identical chip names; route=Ref2VA ValueError; `v4_to_h3` reads `stage_1_raw` not `story_plan.json`. Root cause: API/template/path mismatches, missing convert step, schema migration gaps, ID/cap gaps, naming collisions. Cost: pack routing broken; wrong assets served; H3 pipeline blocked; post/QC/export outputs missing; Kaggle build fails.

**Tooling / Process**
- **[Rule 1, 24, P3]** Skipped/missed `PROJECT_LOG` lines; log lines written for steps that did not happen. Root cause: not logged before next step; wrong state believed. Cost: context lost on session/account change; backfill required.
- **[Rule 10]** Worktree copies of `PROJECT_LOG.md`/`blot.md` stale, never written. Root cause: copies not single path. Cost: stale context.
- **[Rule 26]** Agent without `tabId` renamed whole Flow project. Root cause: missing `tabId`. Cost: cost not stated.
- **[Rule 23, C8]** Long Claude answer truncated; CLI kept only last turn; Opus JSON kept only last turn; first 90% lost. Root cause: `join_stream` not concatenating all turns. Cost: 2.62 USD; no new answer saved.
- **[F6–F9]** No tab discipline; agents on wrong tabs/closed active tabs (~9-tab cap blocked download agents; project renamed); coordinate clicks without screenshot/reference (2K download null captures 20+ min); agents launched without sign-in check (signed out; false done/blocked); Edit IDs from partial notes. Root cause: no `tabId`/sign-in/screenshot discipline. Cost: 20+ min null captures; false done lines.
- **[F10]** Watermark threshold tuned on dark images; ghost star baked in. Root cause: no native-size corner crop check. Cost: no sparkle in 4 of 20; baked-in ghost star.
- **[P2]** Shell wrapper hid failing Gate D tests; bad push `ce74e37`. Root cause: wrapper hid failure. Cost: bad push to fix.
- **[P6]** Pipeline hard-wired to first story; no per-story folders/dry run; 44 HIGH gaps found late. Root cause: no per-story onboarding/dry run. Cost: two full audits, closed late.
- **[P7, P8]** Authoring before render-controller SX-01 dry run; full 10-shot batch before one-shot real test. Root cause: no dry-run/canary gate. Cost: authoring ran twice; 4 failed starts.
- **[P9, P10]** Agent briefs/reports trusted without file/log verification; mid-task owner rule changes not acted on. Root cause: no verification gate. Cost: repeated reruns; wasted calls/sends.
- **[W15]** HF token exposed in chat history/tool call. Root cause: secret not saved to `secrets/` once, stdin only. Cost: security risk.
- **[W13]** Known gaps parked before reel 1 (HF token, chumpy wheel, model caching, one code tree, converter glue, mouth sentence, OpenRouter key). Root cause: intentional deferral per owner order. Cost: none stated.
- **[PROJECT_LOG 11-07 17:59–22:56]** Write blocked by worktree path guard; script escape failure; file not written; Python REPL hung; stray `cat` waited on stdin; coders stopped by user; partial uncommitted edits; `write_pack.py` story arg must be `SOURCE.md` path not slug; UI step-2 validation bug; UI usability; reviewer swap OpenRouter ID pending; style ambiguity fixed vs per-story; style picker missing. Root cause: path guard; bad escapes; malformed commands; validation state bug; missing feature. Cost: reviewer runs failed; rewrite + re-run; hung process; cancelled work; blocked flow.

## 2. ORDER PROBLEMS (step ran before its dependency)

- Voice/audio after video render: shared Foley render ran before ElevenLabs voices [Rule 1 / PROJECT_LOG 11-07 01:47].
- Writer caption checks merged before stage 5 gate (affected stages 1–3) [PROJECT_LOG 11-07 03:48].
- `record_spend` before `_start` success [PROJECT_LOG 11-07 04:16].
- Colour work before T3/T4 verification [Rule 7].
- Image work before bible swatch check / STYLE-01/STYLE-02 gate [Rule 19].
- Assay UI review before style chooser built [Rule 13].
- Agent prompt/instruction sent before Super VL + Xing review [Rule 6].
- Flow agent starts before packet complete / `ui/test_packet_and_roots.py` pass [Rule 21].
- Second review before fixes [Rule 5].
- GPU re-render of SHOT-008 before full compiled prompt of every shot read and reviewers read prompt + shot script + `run.py` [Rule 32].
- Render of SHOT-008 and SHOT-002 before start/end keyframe consistency confirmed [Rule 31].
- First live render `--go` with 19.7 MB `run.py` before size check under ~12 MB and VM start proof [Rule 28 / C3].
- Render submitted with blank lines in prompts before `build_h3_batch` validation [Rule 30].
- Next Claude stage consumed result before checking `num_turns` and parse [Rule 23 / C8].
- Voice windows sized to whole clip before `editorial_duration_sec` fixed / Gate D slot length [Rule 39 → 42].
- Video/clip built before voices measured and frozen [Rule 42].
- Paid Colab session / blind retry before curl pre-flight of external URLs [Rule 40 / W10].
- Ableton write or commit/push before owner gates / M1 [Rule 43].
- Gate D audio ran before TIME-01 checkpoint [PROJECT_LOG part 2].
- Gate D ran before writer step-keys manifest [PROJECT_LOG part 2].
- `record_spend` ran before correct predecessor step [PROJECT_LOG part 2].
- Push/deploy ran before Gate D tests passed (`ce74e37`) [PROJECT_LOG part 2].
- Gate A Approve ran before server restart / stale banner cleared [PROJECT_LOG part 2].
- Used-after-start design ran before proper initialization sequence (TRIAGE_R4_BF item7) [PROJECT_LOG part 2].
- Reviewer runs before `research/UI_PARALLEL_DISPATCH_2026-11-07.md` existed [PROJECT_LOG 11-07 17:59].
- `test_static` before `ui/PLAN.md` section 4 row [PROJECT_LOG 11-07 19:20].
- Ashtavakra + Kalika writers in parallel before owner narrowed focus to Kalika [PROJECT_LOG 11-07 22:01].
- Nemotron Kalika run active before owner chose Claude Opus high [PROJECT_LOG 11-07 22:07].
- `h3_prepare` received `shots.json` before convert step wrote H3 story [PROJECT_LOG 11-08 01:11 auditC].
- `post/_shot_facts` expected `metadata.look`/`audio_and_dialogue_track` before converter wrote them [PROJECT_LOG 11-08 01:13 auditC].
- `v4_to_h3._source` read `stage_1_raw.json` before `story_plan.json` [PROJECT_LOG 11-08 01:16 auditC].
- Writer restart considered/proceeded before gap fixes and reviews closed [PROJECT_LOG 11-08 02:35/02:37].
- Author lint ran before Gate B [PROJECT_LOG 11-08 14:54].
- `pack_to_spec` ran before V4 shots had set/cast/props/keyframes [PROJECT_LOG 11-08 12:10].
- `v4_to_h3` lint did not run before writer validator/downstream [PROJECT_LOG 11-08 12:10].
- No pre-voice speech-rate check before voice/audio [PROJECT_LOG 11-08 12:10].
- Keyframe chip selection before sheet renames saved / exact-name tile existed [PROJECT_LOG 11-08 18:58–18:59].
- Music scoring before real speech timing / `vo_tracks_report.json` [Rule 46 amendment].
- Music gate M1 before `editorial_by_lang.json` freeze [Rule 47].
- Bus measurement by muting VOICE fader before separate voice-only render [Rule 50 (3)].
- Caption burn with simple shaping before complex shaping required [Rule 51].
- Export/render before Session clips cleared and Back to Arrangement [Rule 49 (6)].
- Video clips rendered before voice script speaking speed checked against slot [Q6].
- Keyframe 8A before script position/pose check [Q5].
- SHOT-007/009 rendered before source/staging check [V7].
- Full paid batch-1 before one real line per voice measured against slot [V9].
- SHOT-008 re-rendered before sound cues linted for drawable nouns [Q1].
- Clips rendered before prompt compiler grammar/duplicate check [Q3].
- Clips rendered before negative/“only these characters” constraint [Q4].
- Video clips accepted before measuring `aac` audio track [Q7].
- Code/prompt fix before live-tree decision/sync [W6].
- Keyframes before shot-script verification [W7].
- Shot prompts generated with converter glue still present [W9].
- Paid render session before download URL tests [W10].
- Session stopped before `setup.log` fetched [W11].
- Retry before cause diagnosis [W12].
- No session/usage check after failed `colab new` [W16].
- Runner kept running after ALL DONE [W17].
- Paid setup attempts before real-VM proof of each step [W18].
- Audio windows sized before editorial timing plan from assembler [W19].
- VM stop before per-shot clip fetch succeeded [C1].
- A100 re-render before GPU/model-download test [C2].
- GPU billing before script-start proof [C3].
- Full batch before H3 prompt layout tested on GPU [C6].
- New-story pipeline before end-to-end dry run [P6].
- Authoring before render-controller sound-cue check [P7].
- Full 10-shot batch before one-shot real test [P8].
- B keyframe generated before/without A as edit reference [F2].

## 3. THE CORRECT SEQUENCE

Audio-first is justified because render must build to locked audio length (no editorial timeline repair), and music/SFX scoring depends on real speech windows.

1. **Story & Source Lock** — Input: `SOURCE.md`. Contract out: `shots.json` (sole text baseline) + pack impact budget. Gate: independent story-fidelity pass vs `SOURCE.md`; owner sign-off. (Removes self-grading, wrong beats.)
2. **Style & Bible Gate** — Input: style bible. Contract out: `style_pack_errors`, swatch check STYLE-01/STYLE-02, `_look_rules`. Gate: style enforcement before Stage 2; bible swatch check before any image work. (Removes off-style bible in Stage 2.)
3. **Voice Library & Pre-flight** — Input: Granth canon `a1_eleven.py`. Contract out: `voice_map`, `voice_library.py`. Gate: voice-library lookup before denying a voice type; free pre-flight (account, slots, languages/model, rate, w/s per slot); pronunciation test for hard names. (Removes wrong “no Hindi voice” claims, rewrite-instead-of-copy, paid-call blockers.)
4. **Editorial Lock** — Input: `shots.json`. Contract out: `editorial_by_lang.json` (frozen), `editorial_duration_sec`, `trim_in`/`out`. Gate: freeze published before music M1 and voice generation; later changes re-communicated. (Removes music before timeline lock, voice windows vs whole clip.)
5. **Voice Generation & Audio Lock** — Input: editorial plan. Contract out: real mp3 per shot, `vo_tracks_report.json` (line start/end from shot start), `fit_report.json`, `audio_lock.json`. Gate: Gate D `vo_fit_check` (real mp3 seconds fit each slot, `VO_OVERFLOW_ERROR`), speech-rate ≤3.2 w/s, `ffprobe` header validation, `ffmpeg` level/silence/speech measurement. Render rejects missing audio. (Removes 14 of 54 lines over cut, false fit reports, voices after render.)
6. **Music & SFX Scoring** — Input: `vo_tracks_report.json`, frozen `editorial_by_lang.json`. Contract out: score + per-shot SFX study. Gate: M1 after timeline freeze; voice > hits > music priority; split measurement (voice-only render + mix render), never muting the VOICE fader. (Removes SFX as loud as voice, jumbled reel.)
7. **Keyframe Pair (A/B)** — Input: per-second script directives. Contract out: `keyframe_contract.json` (A = start, B = edit of A, side-by-side pair, enumerated allowed changes). Gate: keyframe-vs-script verification; full-size review; picker exact-name + rename-verify complete before keyframe agents query chips. (Removes set morphs, missing figures, ~2 units/shot re-renders.)
8. **Visual Prompt Compiler** — Input: `keyframe_contract.json`, script. Contract out: validated `.compiled_prompt` per shot. Gate: grammar/duplicate/jargon/boilerplate check; negative/“only these characters” constraint; sound-cue lint rejects drawable nouns; blank-line rejection. (Removes cobras, glued clauses, lower clip quality.)
9. **Video Render Canary & Batch** — Input: `.compiled_prompt`, `audio_lock.json`. Contract out: clips + `_small.mp4`. Gate: single-shot canary (`--ids SHOT-001`) and clip inspection before batch; `run.py` under ~12 MB and `/content/out` proof within 180s; curl pre-flight of all external URLs; `preflight_signoff.json` by all reviewers + owner go before Colab starts. (Removes burned units, hung VMs, blank-line refusals, failed sessions.)
10. **Assembly & QC** — Input: clips, audio, captions. Contract out: assembly. Gate: automatic frame scan (every 4th frame vs script); audio measurement (`ffmpeg`); caption burn gate (`ass=...:shaping=complex`, contact sheet + conjunct crop on real frames); font-family validation (ASS name ID 1 = “Mukta ExtraBold”); keyframe provenance metadata on delivery; Gate D retention findings recorded, waivers only by owner order listed by code, never silent. (Removes wrong all-clear, broken conjuncts, wrong silent font, silent waivers.)
11. **Captions / CC** — Input: `shots.json`, voice timing. Contract out: caption/cc files. Gate: complex shaping, font validation, real-frame verification. (Removes missing caption files, broken Devanagari.)
12. **Mix & Export** — Input: voice, music, SFX. Contract out: final reel. Gate: Ableton export (Session clips cleared, “Back to Arrangement”, owner approval of computer-use access dialog); loudness contract `core.json` (-14 LUFS); final render built to locked audio length. (Removes export blocked, Session clips overriding arrangement, r1-r3 wasted.)
13. **Delivery & Log** — Input: final reel, `_small.mp4`. Contract out: delivery + appended `PROJECT_LOG` line. Gate: log gate (block next step until `PROJECT_LOG` line appended); single log path only (`D:\aai work\anime_studio\PROJECT_LOG.md`); per-shot `fetch_ready` (clip saved to PC before VM teardown); runner teardown hook (auto-stop Colab on error, check orphans, stop at ALL DONE). (Removes context lost, stale log copies, orphan billing, lost clips.)

## 4. ARCHITECTURAL CHANGES (ranked)

1. **Log gate + single log path** — Block next step until `PROJECT_LOG` line appended; prohibit worktree copies; use only `D:\aai work\anime_studio\PROJECT_LOG.md`. Removes: [Rule 1, 10, 24, P3] context lost, stale copies, backfill, wrong state.
2. **Audio-first pipeline + audio-lock gate** — Voice generation/approval before render; `audio_lock.json` contract; render rejects missing audio. Removes: [Rule 39→42, W19, PROJECT_LOG 11-07 01:47] voices after render, rework after clips, 14 lines over cut.
3. **Pre-render preflight gate** — `run.py` size <12 MB, `/content/out` proof within 180s, curl all external URLs, prompt sanitization (no blank lines), single-shot canary, `preflight_signoff.json`. Removes: [Rule 28, 30, 40, C3, C6, W10, W18] burned units, hung VMs, failed sessions, blank-line refusals.
4. **Keyframe pair contract + keyframe-vs-script gate** — A/B as start/end pair; `keyframe_contract.json`; per-second script check; full-size review. Removes: [Rule 31, F2, Q5, W7] set morphs, missing figures, re-renders ~2 units/shot.
5. **Prompt compiler quality gate** — Grammar/duplicate/jargon check; negative/“only these characters”; sound-cue lint for drawable nouns; blank-line rejection. Removes: [Q3, Q4, W9, Rule 32] cobras, glued clauses, lower clip quality.
6. **Gate D `vo_fit_check` + editorial lock** — `fit_report.json`, real mp3 seconds vs slots, speech-rate ≤3.2 w/s, `shots.json` sole baseline. Removes: [Rule 39, 42, W19, PROJECT_LOG 11-08 12:10] 19 of 32 clips over slot, false fit reports.
7. **Voice-timing gate for music** — `vo_tracks_report.json` before scoring; `editorial_by_lang.json` freeze before M1. Removes: [Rule 46 amendment, 47] music scored against permission windows, 14 lines wrong.
8. **Split measurement + loudness contract** — Voice-only render + mix render; voice > hits > music priority; `core.json` single loudness contract; never mute VOICE fader. Removes: [Rule 49 (8), 50 (3)] SFX as loud as voice, r1-r3 wasted, jumbled reel.
9. **Caption burn gate** — `shaping=complex`; ASS name ID 1 = “Mukta ExtraBold”; contact sheet + conjunct crop on real frames. Removes: [Rule 46, 51] broken conjuncts, wrong silent font.
10. **Ableton export gate** — Session clips cleared, “Back to Arrangement”, owner approval of access dialog. Removes: [Rule 48, Rule 49 (6)] export blocked, Session clips overriding arrangement.
11. **Runner teardown + session ownership** — Auto-stop Colab on error, check orphans, stop at ALL DONE, CLI state records VMs/watchdog terminates stray G4s. Removes: [Rule 30, 31, W16, W17] unnamed T4 billing 1.15 units/h, orphan sessions, runner looping after ALL DONE.
12. **Script-edit gate** — `ast.parse`/node `--check`/grep control characters after every heredoc; Edit tool for backslash text. Removes: [Rule 20, 30, P1, W14] control characters in strings, broken files, four slips on 11-09.
13. **Reviewer swap + instruction review gate** — Nemotron Super VL + Xing only; drop Dots; review agent prompts/instructions before sending; no huge slices together. Removes: [Rule 6, 12, P5] slow reviews, empty answers, 429s, hours of review time.
14. **Drive routing + disk guard** — Mount Google Drive; point `flow_outputs`/render there; move heavy files off D:; disk-space guard on C: before long jobs. Removes: [Rule 14, V8] heavy outputs wait, C: full, commands fail.
15. **Packet + UI gates** — Flow agent waits for `ui/test_packet_and_roots.py` pass; browser test at 375 and 1280 px in both languages + independent cold test before UI done; disable Gate A Approve until server restart confirmed. Removes: [Rule 21, Rule 9, PROJECT_LOG part 2] packet missing items, UI test failures, premature approve.
16. **One live tree + sync gate** — Merge `anime_studio` and `anime_studio_merge`; pre-fix sync gate. Removes: [W6] drifted code trees, lost fixes.
17. **Secrets architecture** — Save to `secrets/` once, never echo, inject via stdin only; owner writes the file. Removes: [W15] HF token exposure.
18. **Per-story onboarding + dry run** — Dedicated folders plus end-to-end dry run for every new story. Removes: [P6] 44 HIGH gaps found late, two full audits.
19. **Gate D waiver contract** — Findings written to report; waivers only by owner order, listed by code, never silent. Removes: [W20] silent waivers of retention failures.
20. **Stall watchdog** — Replace agent after 20 min silence; require log line every 5 min. Removes: [Rule 15] stalled coder on 2700-line `pipeline.js`.
