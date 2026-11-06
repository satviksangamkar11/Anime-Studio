# PROJECT LOG - Anime Studio (append only; rules in blot.md)

## NOW (overwrite after every agent finish or checklist tick; max 8 lines)
- Item: checklist 1-7 done except push + docs wrap (7.2-7.4); captions/fonts/colour/stories set aside by owner.
- Open: 2.5 contract test (pack_to_spec reads legacy pack only; no V4-to-H3 converter). Retry wiring into write_pack is NOT mine.
- Green suites (2026-11-07 02:00): director 622, h3 441 (1 skip = 2.5 gap), ui 178, flow 116.
- Blockers: none in my files. No render, no model call, no commit, no push.
- Next: owner gives next task. Queued (not started): colour/attention audit (checklist 10), caption items (section 9), live author run + ElevenLabs need owner go.

Purpose: one line per step so a new session or Claude account loses no context.
Read with: `HANDOFF_2026-11-07.md` (rules, ledger, section 13 = latest owner decisions), `research/H3_V4_CONTRACT_2026-11-07.md`, `research/OWNER_MASTER_PROMPT_V4_2026-11-07.txt`.
Every new step: append a row. Never edit old rows; add a correcting row instead.

Columns: time (IST) | who (me = Claude in this session, or agent id) | model + effort | provider (NVIDIA scheduler / OpenRouter / none) | files | what and result

Rules for entries: write "unknown" where the fact is not recorded; do not guess. "none" provider = local work, no model call.

## A. Before this session (reconstructed from HANDOFF + file times; agents ran under ANOTHER Claude account)

| Time | Who | Model / effort | Provider | Files | What / result |
|---|---|---|---|---|---|
| 11-06 13:38-23:53 | earlier sessions | see notes | NVIDIA scheduler + OpenRouter free | flow/scripts/*, h3/*, ui/*, director/*, stories/* | Flow image tools, H3 prompt engine, UI wizard gates A-D, run registry, Whisper fallback, 4 story packs (Kaliya, Ashtavakra, Mahadev, Upanishad Ganga). Committed 11-06 23:21 as 4 commits (5240377, 55df3d2, 359dccf, 8b1119a). Older UI coders were Haiku; reviewers Nemotron + Dots. |
| 11-07 00:26 | owner | - | - | research/OWNER_MASTER_PROMPT_V4_2026-11-07.txt | Owner V4 master prompt (pure-Foley H3, 6-column table, Step 5.5, router, Gate D, Step 9). |
| 11-07 00:27-00:45 | agent A | coder, effort not recorded (handoff: Haiku high class) | none for the code (tests local) | director/pack_validator.py, test_pack_validator.py | Pack validator, 63 tests, language codes ML-*/STORY-04. |
| same | agent B | same | none | director/write_pack.py, writer_prompts.py, test_writer_v4.py | V4 writer, one repair retry, --out-lang en,hi,mr. Writer model itself = Super VL via OpenRouter (rule: free writer). |
| same | agent C | same | none | h3/router.py, compile_h3_sing8.py, schema_and_linter.py, profiles/ | 5-mode router, Ref2VA compile, locks, 7000 char limit. |
| same | agent D | same | none | h3/fallback_policy.py, asset_manifest.py, step9_qc.py | 4-rung fallback, hashes, Step 9 QC. |
| same | agent E | same | none | h3/gate_d_audio.py + tests | Gate D mix, captions .ass, per-language reels. |
| same | agent F | same | none | director/simple_language.py, data/*.json | Easy en/hi/mr validator. |
| same | agent S1 | same | none | director/story_state.py, story_links.py, run_registry.py, backfill_registry.py | Resume state, registry fields. |
| same | agent S2 | same | none | tools/secret_scan.py, .githooks/pre-push, director/retry_policy.py, ops_checks.py, docs/RUNBOOK_failures.md | Ops safety. |
| same | agent U0 | read-only auditor | none | research/UI_AUDIT_AND_UPDATE_PLAN_2026-11-07.md | UI audit and endpoint contract. |
| 11-07 00:35 | gap review | Nemotron 3.5 Super VL | OpenRouter free | research/GAP_REVIEW_SUPER_VL_2026-11-07.md | Gap list; accepted/rejected in HANDOFF 9b. |

## B. This session (me, Claude Sonnet 5.5, no sub-agents spawned, no paid or model API call made)

| Time | Model / effort | Provider | Files | What / result |
|---|---|---|---|---|
| 01:18 | me, low | none | whole anime_studio tree | Listed 251 files changed since 11-06 12:30; git log shows 4 commits, rest uncommitted. |
| 01:20 | me | none | OWNER_MASTER_PROMPT_V4, H3_V4_CONTRACT | Read the owner spec to answer agent questions (fallback ladder, router, flip marker, hooks all match the spec). |
| 01:21 | me | none | pack_validator.py, 2 shots.json | Found the 4-character shots: Mahadev SHOT-18/30/34, Upanishad SHOT-037. |
| 01:23 | me | none | director h3 ui flow/scripts tests | Baseline: h3 384, ui 178, flow 116 pass; director 1 file failing. |
| 01:25 | me | none | director/test_backfill_registry.py | S1 made backfill preview-by-default; added `--apply` to the tests (the no-change test stays preview). director 603 pass. |
| 01:30 | me | none | h3/schema_and_linter.py, tests/synth.py, e2e_sample.py, tests/test_prompt_locks.py | MO-01 now REQUIRES narrator_mouth_closed true + per-second mouth_state (spec says enforce). Fixtures updated. h3 384 pass. |
| 01:32 | me | none | director/data/simple_language_sacred.json | Whitelisted owner words श्रेष्ठ, संपूर्ण, निर्माण (group owner_easy_script). |
| 01:35 | me | none | h3/gate_d_audio.py, tests/test_gate_d_audio.py | Background music optional (default none): build_mix_filter bgm_input=None gives a 2-stem graph; _bgm_track(None) ok; plan skips the BGM input. +1 test, h3 385 pass. plan_language_outputs with no BGM not run end to end. |
| 01:38 | me | none | Mahadev shots.json, Upanishad shots.json (+ .bak_pre_charcap backups) | Removed CHAR-SITA from SHOT-18/30/34 and CHAR-JANAK from SHOT-037 (first tried Bandi, wrong: beats look at Bandi; restored from backup). Both packs 0 errors in `pack_validator --legacy`. |
| 01:40 | me | none | HANDOFF_2026-11-07.md section 13, memory project_v4_owner_decisions_late.md | Recorded owner decisions. Suites: director 603, h3 385, ui 178, flow 116. |
| 01:45 | me | none | PROJECT_LOG.md (this file) | Created this log. |

## C. Owner decisions (short; full text HANDOFF section 13)
- Mouth fields required. hi/mr voices = ElevenLabs. English = H3 inbuilt voices with fixed voices, option to use ElevenLabs. BGM default none, optional single continuous track. All spoken text easy en/hi/mr. 1, 2 or 3 language reels per story.
- Rules still in force: no Haiku/paid Claude for loops, reviews = Nemotron 3.5 Super VL (OpenRouter free) + Dots (OpenRouter), NVIDIA 14-key scheduler at most 10 calls/key/min, no push to GitHub without owner's go, ElevenLabs paid use needs owner's go, answer in English, no Colab spend without go.

## D. Open / next (in order)
1. English voice-engine option per language (en default H3, hi/mr ElevenLabs; Audio refs only for English; mouth lock relaxed for English H3 speech). NOT BUILT.
2. UI: U1 ui/server.py + ui/pipeline.py, U2 ui/static/pipeline.js + app.js, U3 style.css + index.html + test_static.py (disjoint files, contract in UI_AUDIT_AND_UPDATE_PLAN). NOT STARTED. Plus h3/render_controller.py wiring, h3/SPEC.md refresh, retry_policy into write_pack.
3. Nemotron Super VL + Dots reviews of agents A-F, S1, S2; triage; fix.
4. STATUS.md/README update, then ask owner before push (run tools/secret_scan.py first).
5. Kaliya pack defects (short reels 2-5, missing devas, PROP-KANSA, PROP-KALI-KAMLI) still open; Mahadev 4th reel and fonts download need owner's go.

## E. Useful commands
- Suites: `cd director|h3|ui|flow/scripts && python -m pytest -q -p no:cacheprovider`
- Validate a pack: `python director/pack_validator.py <pack_dir> [--legacy] [--json]`
- Backfill registry: `python director/backfill_registry.py [--apply] [--only slug]`
- Dots review: `python flow/scripts/dots_review.py --prompt ... FILES --out report.md`
| 01:55 | me | none | h3/schema_and_linter.py, tests/synth.py, e2e_sample.py, tests/test_prompt_locks.py | Owner: more sound effects is better, so SX-01 now needs a cue in all 7 action sentences (was 4). Fixtures and e2e sample text got cues. h3 385 pass. Writer prompts (director/writer_prompts.py) may still say 4 of 7: check. |
| 02:05 | me | none | CHECKLIST_ARCHITECTURE_2026-11-07.md | Owner asked for a proper checklist; written (sections 0-8). Agent EV launched (Haiku high, background) for English H3 voice research + build; interpreted owner's 'Haikyuu Duo' as Haiku high and 'Haikyuu Medium' as Haiku medium. Stories out of scope. |

## LIVE LOG (blot.md format: MM-DD HH:MM | WHO | TYPE | WHERE | RESULT)
11-07 02:05 | me | DECISION | CHECKLIST_ARCHITECTURE_2026-11-07.md | checklist written; stories out of scope
11-07 02:06 | EV(haiku,high) | AGENT-START | h3/*,director/{write_pack,writer_prompts,pack_validator,simple_language}.py | English H3 voice option research+build
11-07 02:12 | me | EDIT | blot.md,CLAUDE.md,PROJECT_LOG.md | log-every-step rule + NOW block created
11-07 01:42 | me | FIX | PROJECT_LOG.md | the 02:05, 02:06 and 02:12 times above are wrong; real clock is about 01:35-01:41
11-07 01:43 | EV(haiku,high) | EDIT | research/EN_H3_VOICE_CONSISTENCY_2026-11-07.md | research note written: official speaker/d/Audio rules verified from raw repo; owner ban on Audio in Ref2VA refuted; 4 owner questions
11-07 01:55 | EV(haiku,high) | EDIT | h3/voice_engine.py | new pure rules: engines VE-01..04, anchors VA-03, speaker map SP-01..03, Audio refs VA-05/06
11-07 01:57 | EV(haiku,high) | EDIT | director/pack_validator.py | voice_engine in stage 1, speaker map + anchors in bible, VA-01/02 English lines in shots (engines=None skips)
11-07 02:01 | EV(haiku,high) | EDIT | h3/router.py,h3/schema_and_linter.py | en-h3 voice mode: audio refs route Ref2VA, voice_mode(reg), english speech/mouth/anchor checks (VA-*, VE-06, SL-01..03 in voice)
11-07 02:04 | EV(haiku,high) | EDIT | h3/compile_h3_sing8.py | en-h3 speech sentences, Audio timbre subjects, mouth lock only when silent
11-07 02:08 | EV(haiku,high) | EDIT | h3/gate_d_audio.py | en-h3 mix: H3 clip audio is the one stem (vo_input None), no VO files, per-language video dict, voice_engines kwarg
11-07 01:47 | me | OWNER | PROJECT_LOG.md | owner: same video for en/hi/mr, 3 reels; voices after render; no voice clips supplied; allow Audio in en-h3
11-07 01:47 | me | DECISION | agent EV | sent redesign: default elevenlabs on shared foley video, voice_map per char/lang, en-h3 optional 2nd render, anchor=first approved H3 clip
11-07 01:48 | EV(haiku,high) | OWNER | PROJECT_LOG,research/EN_H3_VOICE_CONSISTENCY_2026-11-07.md | coordinator change: default elevenlabs for all langs (shared Foley video), en-h3 optional 2nd render, voice_map + anchor from first approved H3 clip
11-07 01:49 | me | FIX | agent EV | my last design msg was wrong; correct defaults: en=h3, hi/mr=elevenlabs; en-h3 own render, hi/mr share foley render; correction sent
11-07 01:49 | EV(haiku,high) | OWNER | h3/voice_engine.py | CORRECTION: defaults en=h3, hi=elevenlabs, mr=elevenlabs (replaces 'all elevenlabs'); en-h3 = one extra H3 render
11-07 01:50 | EV(haiku,high) | EDIT | h3/voice_engine.py,h3/schema_and_linter.py,h3/gate_d_audio.py,director/pack_validator.py | voice_map VM-*, pending anchors VA-08, VA-07 source exemption, per-lang video, en-h3 warning
11-07 01:50 | EV(haiku,high) | TEST | h3 | h3 424 pass (was 385): test_voice_engine.py, test_voice_gate_d.py
11-07 01:51 | me | OWNER | PROJECT_LOG.md | owner: render video ONCE total, use H3 for what it can do; options sent (A foley+11labs all, B english-baked+separation, C two renders); awaiting pick
11-07 01:52 | me | OWNER | agent EV | owner chose option A: render once (shared foley), ElevenLabs for en/hi/mr after render; en-h3 kept as off-by-default 2nd-render switch; sent to EV
11-07 01:53 | EV(haiku,high) | OWNER | h3/voice_engine.py | FINAL OPTION A: one shared Foley render; defaults en,hi,mr=elevenlabs; en=h3 off-by-default second render; hi/mr never h3
11-07 01:54 | me | AGENT-START | GAP(haiku,medium): h3/render_controller.py,SPEC.md,voice_manifest.py,run_registry.py | owner: finish pipeline code, NO render; wiring+voice manifest+contract tests+SPEC refresh
11-07 01:55 | GAP(haiku,medium) | EDIT | h3/pipeline_contract.py | new ordered pipeline plan (build_plan, assembly_allowed); smoke ok
11-07 01:55 | GAP(haiku,medium) | CMD | h3/tests/test_pack_to_spec_contract.py,h3/e2e_sample.py | read only: e2e narrator_mouth_closed+mouth_state already present (task 1 verify)
11-07 01:55 | EV | EDIT | h3/tests/test_voice_gate_d.py | removed NUL bytes in _wav, added missing import wave
11-07 01:56 | EV | TEST | h3/tests/test_voice_gate_d.py | 9 pass
11-07 01:56 | EV | TEST | h3/tests | h3 428 pass (was 385)
11-07 01:56 | EV | TEST | director | director 612 pass
11-07 01:56 | me | OWNER | research/CAPTION_FONTS_RESEARCH_2026-11-07.md | owner pasted caption/font research; wants Super VL + Dots to review our files vs it and say which Reel components to implement
11-07 01:56 | GAP(haiku,medium) | EDIT | h3/render_controller.py | imports added for plan_pipeline (pending function body)
11-07 01:56 | GAP(haiku,medium) | EDIT | h3/render_controller.py | plan_pipeline + gate helpers added (dry run, no render)
11-07 01:57 | EV | TEST | ui, flow/scripts | ui 178 pass, flow 116 pass
11-07 01:57 | GAP(haiku,medium) | TEST | h3/tests/test_render_controller_wiring.py | 5 passed in 0.19s
11-07 01:57 | EV | EDIT | research/EN_H3_VOICE_CONSISTENCY_2026-11-07.md | Option A: render once, en=elevenlabs default, en-h3 second render
11-07 01:57 | GAP(haiku,medium) | EDIT | h3/voice_manifest.py | wav manifest per lang: sha256, duration, voice ids, VO fit reuse, stale text check, CLI
11-07 01:57 | me | REVIEW-START | research/_run_caption_reviews.py | Dots + Super VL (OpenRouter free) on caption research vs gate_d_audio/fonts/simple_language/asr; outputs research/CAPTION_REVIEW_*_2026-11-07.md
11-07 01:57 | GAP(haiku,medium) | TEST | h3/tests/test_voice_manifest.py | 6 passed in 0.08s (tightened 2 weak asserts)
11-07 01:58 | EV | EDIT | director/writer_prompts.py,director/write_pack.py | stage2 voice_map (+en=h3 speaker map/anchor); stale en=h3 defaults fixed to en=elevenlabs
11-07 01:58 | GAP(haiku,medium) | GAP | h3/tests/test_pack_to_spec_contract.py | pack_to_spec reads legacy pack only, no V4-to-H3 converter; H3 half skipped with reason; 2 pass 1 skip
11-07 01:58 | EV | TEST | director/writer_prompts.py | stage2 example bible validates ok (en=h3 + placeholders)
11-07 01:58 | EV | DECISION | director/simple_language.py | no change: check_shot_texts already flags English dialogue SEN-01 for any engine
11-07 01:59 | GAP(haiku,medium) | EDIT | h3/SPEC.md | rewritten: option A, 5-mode router, lock codes, shift params, pipeline plan, en-h3 switch; dialogue block removed
11-07 01:59 | EV | EDIT | HANDOFF_2026-11-07.md,CHECKLIST_ARCHITECTURE_2026-11-07.md,PROJECT_LOG.md | ledger row EV added; checklist 1.1-1.5,1.7 ticked; NOW overwritten
11-07 01:59 | GAP(haiku,medium) | CMD | h3/*.py,director/h3_director.py | speech sweep: no dead code in my files; compile_h3_sing8 _speech_sentences live only for en-h3 (EV file, reported)
11-07 01:59 | EV | REVIEW-DONE | h3/gate_d_audio.py,h3/voice_engine.py,director/write_pack.py | self-triage: planning and timing code read, suites green; 1.8 left open until review round
11-07 01:59 | GAP(haiku,medium) | EDIT | director/run_registry.py | EVENT_FIELDS +output_languages,+voice_engine (optional, validated); SCHEMA_VERSION stays 1 (optional fields)
11-07 01:59 | GAP(haiku,medium) | TEST | director/test_run_registry_langs.py | 30 passed in 0.22s
11-07 02:00 | me | FIX | PROJECT_LOG.md | audit: I had not logged these earlier steps; added below. EV rows 02:01-02:08 carry wrong clock (real about 01:44-01:48)
11-07 02:00 | me | EDIT | research/CAPTION_FONTS_RESEARCH_2026-11-07.md,research/_caption_review_prompt.txt,research/_run_caption_reviews.py | saved owner caption research (condensed), review prompt, runner script
11-07 02:00 | me | REVIEW-DONE | research/CAPTION_REVIEW_DOTS_2026-11-07.md,CAPTION_REVIEW_SUPERVL_2026-11-07.md | both OpenRouter free reviews written (7.3 KB and 12.4 KB); not yet triaged
11-07 02:00 | EV(haiku,high) | AGENT-DONE | h3/voice_engine.py,gate_d_audio.py,writer files | option A built; director 612, h3 428, ui 178, flow 116 pass; checklist 1.6 and 1.8 left open for review
11-07 02:00 | me | OWNER | me | owner asked if every step is logged: audited log, gaps fixed, rule restated to agents
11-07 02:00 | me | EDIT | CHECKLIST_ARCHITECTURE_2026-11-07.md | added section 9 caption components from the two reviews; open owner question on bottom margin 467 vs 35% guidance
11-07 02:00 | me | EDIT | PROJECT_LOG.md | NOW block refreshed
11-07 02:00 | GAP(haiku,medium) | TEST | director,h3,ui,flow/scripts | director 622, h3 441 (1 skip, EV tests included), ui 178, flow 116 all green
11-07 02:00 | GAP(haiku,medium) | DECISION | CHECKLIST_ARCHITECTURE_2026-11-07.md | ticked 2.1 2.3 2.4 2.6 2.7; 2.5 left open (V4-to-H3 converter missing)
11-07 02:00 | GAP(haiku,medium) | EDIT | PROJECT_LOG.md,HANDOFF_2026-11-07.md | NOW block overwritten; GAP row added to handoff section 9 ledger
11-07 02:01 | GAP(haiku,medium) | AGENT-DONE | h3/render_controller.py,pipeline_contract.py,voice_manifest.py,SPEC.md,run_registry.py | wiring done, 2.5 contract open (no V4->H3 converter); reported director 622,h3 441+1 skip
11-07 02:02 | me | OWNER | h3/gate_d_audio.py | owner: captions inside the Instagram and YouTube Shorts safe zone -> enlarge bottom margin
11-07 02:03 | me | EDIT | h3/shot_table_spec.py,tests/test_gate_d_audio.py,assets/fonts/README.md | caption margin_v 467->896 (35% = Reels+Shorts safe zone), top 360, sides 160 kept; test face box moved
11-07 02:03 | me | REVIEW-START | research/_run_arch_reviews.py | round-1 review of agents A-F,EV,GAP,S1,S2 files: Dots + Super VL (OpenRouter free), 6 batches each -> research/ARCH_REVIEW_*_2026-11-07.md
11-07 02:03 | me | AGENT-START | V4H3(haiku,medium): h3/v4_to_h3.py + tests | converter V4 pack -> H3 story (gap from GAP agent, checklist 2.5)
11-07 02:07 | supervl | REVIEW-DONE | batch b1_validator_writer | 3918 chars
11-07 02:07 | V4H3(haiku,medium) | CMD | blot.md,CLAUDE.md,PROJECT_LOG.md,CHECKLIST,HANDOFF,SPEC,contract,linter,synth read | required docs read; FL2VA-only H3 needs pose/seam/cadence fields V4 lacks
11-07 02:08 | V4H3(haiku,medium) | EDIT | h3/v4_to_h3.py | converter written (convert_pack, CLI); not yet run
11-07 02:09 | V4H3(haiku,medium) | TEST | h3/tests/test_v4_to_h3.py,h3/v4_to_h3.py | 32 new tests; 1 fixture fix (cadence end 175); run again
11-07 02:10 | supervl | REVIEW-DONE | batch b2_write_pack_lang | 4188 chars
11-07 02:11 | V4H3(haiku,medium) | TEST | h3/tests/test_pack_to_spec_contract.py,h3/tests/test_v4_to_h3.py | contract skip replaced by convert->lint; 33 pass
11-07 02:13 | V4H3(haiku,medium) | EDIT | HANDOFF_2026-11-07.md | ledger row V4H3 added (section 9)
11-07 02:13 | V4H3(haiku,medium) | TEST | h3,director,ui,flow/scripts | h3 474 pass, director 622, ui 178, flow 116; CLI smoke exit 0
11-07 02:13 | supervl | REVIEW-DONE | batch b3_state_ops | 2214 chars
11-07 02:13 | V4H3 | AGENT-DONE | h3/v4_to_h3.py,tests | converter built, h3 474 pass; real V4 packs report missing h3_fields (seam types, pose vectors, handles, boundary png): owner/integrator decision
11-07 02:14 | dots | REVIEW-DONE | batch b1_validator_writer | 6186 chars
11-07 02:14 | me | EDIT | director/pack_validator.py,write_pack.py,story_state.py,run_registry.py | fixed 9 Super VL batch1-3 findings (ML-06 single-lang, tone, bool, screen/depth, id/episode/key/URLError guards, resume IndexError, h3 en-only); director 622 pass; skipped: ML-03 all-keys rule (by design), 999 cap (not real)
11-07 02:24 | me | EDIT | PROJECT_LOG.md,CHECKLIST_ARCHITECTURE_2026-11-07.md | NOW refreshed; ticked 2.1 2.3 2.4 2.7
11-07 02:25 | me | OWNER | git | owner: push everything done to the git repo and give the link (push go given)
11-07 02:25 | me | CMD | git | secret_scan clean (101 files); committed caf6fa1 on branch v4-architecture-2026-11-07 (101 files); pushed to origin; stories/* stay ignored (public repo)
11-07 02:25 | me | OWNER | all agents | owner: do NOT make any Colab calls (none made so far; briefs already forbid it)
11-07 02:27 | supervl | REVIEW-DONE | batch b4_h3_linter | 4032 chars
11-07 02:27 | dots | REVIEW-DONE | batch b2_write_pack_lang | 8680 chars
11-07 02:28 | me | OWNER | h3_fields decision | owner: research git history 3-5 days + repos for the proven way, conclude, fix, no quality shortcuts
11-07 02:29 | me | DECISION | research/DECISION_H3_FIELDS_2026-11-07.md | h3_fields: derive deterministic tier + separate model-authoring step with lint/repair (e2e_sample pattern) + report; writer unchanged; handles derivable from editorial vs pixel_frames
11-07 02:29 | me | AGENT-START | H3A(haiku,medium): h3/h3_author.py,v4_to_h3.py,tests | implements DECISION_H3_FIELDS: derive tier + author step + wiring; no live call
11-07 02:29 | H3A(haiku,medium) | CMD | blot.md,CLAUDE.md,PROJECT_LOG.md,research/DECISION_H3_FIELDS_2026-11-07.md,h3/v4_to_h3.py read | required docs read; derive+author spec in hand
11-07 02:32 | me | FIX | research/DECISION_H3_FIELDS_2026-11-07.md | owner: all renders were on Colab, not Kaggle; doc corrected (STATUS.md/h3_director docstring still mention one early Kaggle T4 test, not edited)
11-07 02:34 | supervl | REVIEW-DONE | batch b5_gate_d | 3743 chars
11-07 02:35 | H3A(haiku,medium) | DECISION | h3/v4_to_h3.py | cut plan: ed<pf=dynamic both sides, ed==pf=static; first-in-reel incoming INTER, last outgoing INTER; CHAINED picture_1 = prev picture_2; authored fields cached per shot with hash
11-07 02:36 | H3A(haiku,medium) | EDIT | h3/v4_to_h3.py | tier1 derive_fields, group_rows, plan_handles, merge_h3, authored cache read wired into convert_pack
11-07 02:36 | supervl | REVIEW-DONE | batch b6_controller | 2621 chars
11-07 02:37 | H3A(haiku,medium) | EDIT | h3/h3_author.py | tier2 prompt, parse, check+repair loop (max 4), save cache, author_pack, scheduler_caller (lazy), CLI dry-run/live gate
11-07 02:38 | H3A(haiku,medium) | EDIT | h3/tests/test_h3_author.py | new tests written (derive, prompt, parse, loop, cache, round trip, CLI gate)
11-07 02:38 | H3A(haiku,medium) | TEST | h3/tests/test_h3_author.py,h3/tests/test_v4_to_h3.py | 61 pass (author+converter)
11-07 02:39 | H3A(haiku,medium) | TEST | h3,ui,flow/scripts,director | h3 503 pass, ui 178, flow 116, director 622
11-07 02:40 | H3A(haiku,medium) | EDIT | HANDOFF_2026-11-07.md | ledger row H3A added (section 9), judgment calls + findings listed
11-07 02:40 | H3A(haiku,medium) | AGENT-DONE | h3/h3_author.py,h3/v4_to_h3.py,h3/tests/test_h3_author.py | tier1+tier2+cache+CLI built; h3 503 pass; no model call, no commit
11-07 02:40 | H3A | AGENT-DONE | h3/h3_author.py,v4_to_h3.py,tests | derive+author step built, h3 503 pass; live run needs free-model go; INTER_REEL rule unconfirmed
11-07 02:41 | me | EDIT | h3/schema_and_linter.py,compile_h3_sing8.py | Super VL b4: fixed missing asset_root crash (EP-AR), episode not found, profile KeyError; rejected SL-04 (speech refusal is by design), fps=0/profile-types/path-traversal (trusted internal inputs)
11-07 02:43 | me | EDIT | h3/gate_d_audio.py,render_controller.py,tests | Super VL b5-b6: per-language PLAN-01 guard + TIME-01 on bad range, empty BGM tracks ok, reel id sanitized, plan default hi; rejected asset_root confine/float fps (trusted); suites ok
11-07 02:44 | me | DECISION | research/UI_CONTRACT_ADDENDUM_2026-11-07.md | UI contract addendum: resolved blockers, owner decisions adopted (recommended), new features k-o (voice engine, voice map, BGM toggle, author panel, safe-zone chip)
11-07 02:44 | me | AGENT-START | U1(haiku,medium) ui/server.py,pipeline.py,tests | UI backend per audit 4a + addendum k-o
11-07 02:44 | me | AGENT-START | U2(haiku,medium) ui/static/pipeline.js,app.js | UI front end features a-o
11-07 02:44 | me | AGENT-START | U3(haiku,medium) ui/static/style.css,index.html,test_static.py | UI design pass + static tests
11-07 02:44 | U2(haiku,medium) | CMD | blot.md,CLAUDE.md,PROJECT_LOG.md,research/UI_*_2026-11-07.md | contract docs read
11-07 02:45 | U1(haiku,medium) | AGENT-START | ui/server.py,ui/pipeline.py,ui/test_*.py | read blot, CLAUDE, log, plan 1-4a, addendum; starting code read
11-07 02:46 | U3(haiku,medium) | EDIT | research/UI_CONTRACT_ADDENDUM_2026-11-07.md | U3 element ids section appended (ids for U2)
11-07 02:47 | U3(haiku,medium) | EDIT | ui/static/index.html | header chips, job bar, wiz-panels containers, labels bound, copy fixes L1 L4 L5 L6 M13 M19 M21
11-07 02:47 | U2(haiku,medium) | CMD | ui/static/pipeline.js,app.js,test_static.py,server.py | read current JS, pinned test strings noted
11-07 02:48 | U3(haiku,medium) | EDIT | ui/static/style.css | visual pass 3j: tokens light/dark, 44px, focus-visible 3px, stacked tables, 900/760 breakpoints, reduced motion, toast removed
11-07 02:49 | U1(haiku,medium) | DECISION | ui/pipeline.py | scope = project pointer (409 if story/pack differ); legacy approvals w/o story ignored; ROUTE_IMAGES map for expected images
11-07 02:49 | U1(haiku,medium) | CMD | director,h3,ui | read module contracts (story_state, links, validator, ops_checks, voice_engine, render_controller, h3_author, registry); baseline ui 178 pass
11-07 02:49 | dots | REVIEW-DONE | batch b3_state_ops | 7323 chars
11-07 02:49 | U3(haiku,medium) | FIX | ui/static/style.css | red-fg token + dark ok/blue/grey darkened for white-text contrast
11-07 02:49 | U2(haiku,medium) | EDIT | ui/static/pipeline.js | rewritten: story/langs/voices/bgm/link/validator/render/author/ops/gate D/export scoped
11-07 02:49 | U2(haiku,medium) | TEST | ui/static/pipeline.js | node --check
11-07 02:49 | U1(haiku,medium) | EDIT | ui/pipeline.py | rewritten: scoped approvals, validator, h3 plan bridge, render status, voice map; not yet tested
11-07 02:50 | U2(haiku,medium) | EDIT | ui/static/app.js | 403 text only for Host/Origin/X-UI; port via location.host; export scoped by project; one poller hidden-aware
11-07 02:50 | U2(haiku,medium) | TEST | ui/test_static.py | 17 pass, 1 fail: index.html placeholder https URL (U3 file)
11-07 02:50 | U2(haiku,medium) | EDIT | HANDOFF_2026-11-07.md | ledger row U2 added (section 9), DONE-UNVERIFIED
11-07 02:51 | U1(haiku,medium) | TEST | ui/test_pipeline.py | 44 pass after scoping gate records (sc/ag helpers)
11-07 02:51 | U2 | AGENT-DONE | ui/static/pipeline.js,app.js | features a-o built, node --check ok, test_static 17 pass 1 fail (index.html youtube placeholder, U3 file); relies on U1 routes not yet present; shapes forwarded to U1
11-07 02:51 | me | DECISION | U1 | forwarded U2's assumed response shapes + h3_author whitelist + run_allowed to U1
11-07 02:51 | U1(haiku,medium) | OWNER | ui/server.py | integrator: match U2 shapes (full pack path on pack/validate/voices/author; gate_d.languages rows vo/captions/final/checks; prepare_ready; h3_author dry-run cmd)
11-07 02:51 | U1(haiku,medium) | EDIT | ui/server.py | header constants added (LEGACY_STORY, LANGS, DISK_PATHS, STARTED, SERVER_MTIME0)
11-07 02:51 | U3(haiku,medium) | TEST | ui/test_static.py | 17 U3 tests added; addendum endpoints counted in pipeline.js endpoint check
11-07 02:51 | U1(haiku,medium) | EDIT | ui/server.py | job verified flag, job table reload, spend lock on unverified, cumulative total cap, kill tree
11-07 02:52 | me | EDIT | director/write_pack.py,test_retry_policy.py | shared retry policy wired into call_path (nvidia/openrouter): 429/5xx/timeout/empty retried 15-180s max 5; budget/fatal stop; ModelRefused carries kind; +2 tests; director 624 expected
11-07 02:52 | U3(haiku,medium) | TEST | ui | full ui suite 194 pass (static 34), was 178 baseline
11-07 02:52 | U3(haiku,medium) | FIX | ui/test_static.py | U3 test count is 16 not 17 (log correction); addendum endpoints counted in pipeline.js check
11-07 02:52 | U3(haiku,medium) | DECISION | HANDOFF_2026-11-07.md | ledger row U3 added (section 9), DONE-UNVERIFIED; gaps: L2 keyboard stepper, .gitignore check, browser check
11-07 02:52 | U3(haiku,medium) | AGENT-DONE | ui/static/style.css,index.html,ui/test_static.py | U3 done: ui 194 pass; DONE-UNVERIFIED
11-07 02:54 | U1(haiku,medium) | EDIT | ui/server.py | write_pack out_lang required + --out-lang argv
11-07 02:54 | U1(haiku,medium) | EDIT | ui/server.py | h3 prepare refuses shots.json and maps reel->EP_NN; style/profile args; yt_transcript + h3_author dry-run commands; colab_run verified
11-07 02:56 | U1(haiku,medium) | EDIT | ui/server.py | U1 methods inserted (version, ops, state, languages, voices, bgm, pack voices, validator, render, author dry-run, link); status/stories/save/project/images edited
11-07 02:57 | U1(haiku,medium) | EDIT | ui/server.py | export story+pack scoped, packet scoped, file endpoint redact and runs block, V4 read_pack, spend re-check + ledger, yt result, bind message
11-07 02:57 | U1(haiku,medium) | FIX | ui/server.py | previous EDIT line was written before the patch script succeeded; patch2 applied OK on retry
11-07 02:57 | U1(haiku,medium) | EDIT | ui/pipeline.py,ui/server.py | render status in U2 shape (gate_d.languages vo/captions/final/checks, prepare_ready); dispatch routes for all new endpoints
11-07 03:00 | U1(haiku,medium) | TEST | ui/test_ui.py | ui suite 195 pass; only test_static u3 id test fails (U3 file, not mine)
11-07 03:00 | dots | REVIEW-DONE | batch b4_h3_linter | 4245 chars
11-07 03:01 | U1(haiku,medium) | TEST | ui/test_u1_routes.py | new file 26 pass (gates, validator, languages, voices, bgm, author dry-run, ledger cap, jobs reload)
11-07 03:02 | U1(haiku,medium) | EDIT | HANDOFF_2026-11-07.md | U1 ledger row added (section 9)
11-07 03:02 | me | OWNER | research/COLOUR_ATTENTION_RETENTION_AUDIT_2026-11-07.md | owner supplied colour audit, wants it in pipeline BUT not now: finish existing work first. Saved to repo, queued, NOT started. Owner asked if caption/cc files were given: none found
11-07 03:02 | U1(haiku,medium) | EDIT | research/UI_CONTRACT_ADDENDUM_2026-11-07.md | U1 deviations section appended (16 items)
11-07 03:02 | U1(haiku,medium) | AGENT-DONE | ui/server.py,ui/pipeline.py,ui/test_ui.py,ui/test_pipeline.py,ui/test_registry.py,ui/test_u1_routes.py | ui 221 pass (+1 U3 test_static WIP), director 624, h3 504, flow 116; no commit
11-07 03:03 | U1 | AGENT-DONE | ui/server.py,pipeline.py,tests | UI backend done, ui 221 pass + 1 fail (static id 'li'); live author run not built (run_allowed false)
11-07 03:04 | me | FIX | research/UI_CONTRACT_ADDENDUM_2026-11-07.md | removed backticked li from a note (static id test parsed it as an id); all four suites run
11-07 03:05 | me | REVIEW-START | research/_run_ui_reviews.py | UI review round: Super VL + Dots (OpenRouter free) on ui/server.py,pipeline.py,pipeline.js,app.js,index.html,style.css -> research/UI_REVIEW_*_2026-11-07.md
11-07 03:05 | dots | REVIEW-DONE | batch b5_gate_d | 5511 chars
11-07 03:06 | me | CMD | ui/server.py | stopped stale UI server (pid 21208 from 11-06) and started the new build on 127.0.0.1:8765 for the browser check
11-07 03:13 | supervl | REVIEW-DONE | batch u1_server | 4265 chars
11-07 03:15 | dots | REVIEW-DONE | batch u1_server | 3740 chars
11-07 03:16 | dots | REVIEW-DONE | batch b6_controller | 6070 chars
11-07 03:17 | me | TEST | UI in built-in browser (phone 490px + desktop 1280px) | found+fixed: duplicate static panels (every id twice), next-step key/text mismatch ([object Object]), header chips, validate POST path, label layout, sticky header on phone, stepper wrap; validator run ok (Upanishad pack: no errors); ui 223 pass
11-07 03:17 | supervl | REVIEW-DONE | batch u2_pipeline_js | 5252 chars
11-07 03:19 | me | EDIT | STATUS.md,README.md,HANDOFF_2026-11-07.md,CHECKLIST,PROJECT_LOG.md | wrap-up docs updated; Dots+Super VL triaged: fixed free-model guard (empty pricing), answer_text JSON error, Marathi detect, per-language AttributeError, UI fetch timeout; suites director 624 h3 504 ui 223 flow 116; secret scan clean
