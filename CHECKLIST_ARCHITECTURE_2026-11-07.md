# CHECKLIST - finish the architecture (owner order 2026-11-07)

Stories are OUT OF SCOPE for now (Kaliya fixes, Mahadev 4th reel). Captions and fonts: owner supplies later.
Tick `[x]` only when done AND verified. After each box, append a row to PROJECT_LOG.md.
Suites to stay green: director 603, h3 385, ui 178, flow 116 (counts grow).

## 0. Done earlier
- [x] Mouth fields required (MO-01)
- [x] BGM optional, default none (2-stem mix)
- [x] Easy-script words whitelisted
- [x] SX-01 now needs a sound cue in all 7 action sentences
- [x] Project log, handoff section 13, memory notes

## 1. English voice option (agent EV: Haiku, high effort, researching + building)
- [x] 1.1 Research note research/EN_H3_VOICE_CONSISTENCY_2026-11-07.md (verified vs unverified; Option A)
- [x] 1.2 `voice_engine` per language (defaults en/hi/mr = elevenlabs; en = h3 is the off-by-default second render)
- [x] 1.3 Character voice anchor + stable speaker-id map (same voice every shot and reel)
- [x] 1.4 H3 linter/compiler/router allow speech in en-h3 only; locks stay for hi/mr/en-elevenlabs
- [x] 1.5 Gate D handles en-h3 (voice from H3 audio) and hi/mr ElevenLabs
- [x] 1.6 Writer + validator carry voice_engine (reviewed by Super VL batches 1-3, fixes applied)
- [x] 1.7 Tests for every new rule; all 4 suites green
- [x] 1.8 EV report triaged; files read and reviewed (Super VL b4-b6 findings fixed or rejected, see PROJECT_LOG)

## 2. Close remaining code gaps (Haiku, medium effort)
- [x] 2.1 h3/SPEC.md refresh (old dialogue block, mode_to_video_shift_map)
- [x] 2.2 retry_policy wired into write_pack.call_path
- [x] 2.3 run_registry event field output_languages / voice_engine
- [x] 2.4 voice .wav manifest
- [x] 2.5 contract: V4 pack -> H3 converter (V4H3) + derive/author step (H3A); live author run needs free-model go
- [x] 2.6 leftover old speech code check in h3_director.py
- [x] 2.7 h3/render_controller.py wiring: router, linter, asset manifest hashes, Gate D mix, Step 9, loudness
- [x] 2.8 suites green

## 3. Review round 1 (Nemotron 3.5 Super VL via OpenRouter + Dots, in parallel; free models only)
- [x] 3.1 Review agents A-F, S1, S2, EV and section 2 changes
- [x] 3.2 Triage every finding against the code (reviewers give false positives)
- [x] 3.3 Fix real findings, re-run suites

## 4. UI audit
- [x] 4.1 Re-read research/UI_AUDIT_AND_UPDATE_PLAN_2026-11-07.md against the code as it is now
- [x] 4.2 List UI changes: language checkboxes + All, voice engine choice for English, BGM on/off, Continue button, scoped approvals, validator report, YouTube link box, Gate D per-language panel, Step 9 + fallback rung + 4 human choices, ops panel, runs and documents
- [x] 4.3 Endpoint contract frozen before coding

## 5. UI update (disjoint files)
- [x] 5.1 U1 ui/server.py + ui/pipeline.py
- [x] 5.2 U2 ui/static/pipeline.js + app.js
- [x] 5.3 U3 ui/static/style.css + index.html + ui/test_static.py (phone width, focus)
- [x] 5.4 ui tests green

## 6. Review round 2 (UI) 
- [x] 6.1 Nemotron Super VL + Dots on UI files
- [x] 6.2 Triage and fix
- [x] 6.3 Browser check of the UI (built-in browser)

## 7. Wrap up
- [x] 7.1 All four suites green
- [x] 7.2 secret scan (tools/secret_scan.py) clean (11-07: 18 files clean; regex scan of 81 V4 + 67 universal files clean)
- [x] 7.3 STATUS.md, README, HANDOFF ledger, PROJECT_LOG, memory updated (11-07 close-out)
- [x] 7.4 Ask owner before any push (owner approved 11-07; pushed d5804ba and 80252ec; later commits 674bcda, 9f7392c NOT pushed)

## 8. Waiting on the owner (do not start)
- [ ] Captions text (owner will provide); fonts DONE 11-07 (4 OFL families in universal styles/fonts)
- [ ] Paid ElevenLabs use (needs go)
- [ ] Stories: Kaliya defects, Mahadev 4th reel

## 9. Caption components (from the owner's caption research + Super VL/Dots review; reviews in research/CAPTION_REVIEW_*_2026-11-07.md). Owner supplies fonts/captions later: build only the code parts, no downloads
- [x] 9.1 SRT + WebVTT sidecar export per language (from the same cues) (built on universal-v1.1: core/caption_export.py to_srt/to_vtt/write_sidecars; post.py writes them)
- [x] 9.2 Safe zone: bottom margin 896 (35%), top 360 (14%), sides 160; per-platform templates built (core.json safe_zone_templates, build_ass template=, post.py --platform)
- [x] 9.3 Font glyph-coverage QA with fontTools (माझं कुठे ॲप क्ष ज्ञ ळ ऱ) (built on universal-v1.1: core/caption_text.py check_font_coverage with an own cmap reader; build_ass FAILs a missing glyph)
- [x] 9.4 Hook-word emphasis style (built on universal-v1.1: cue emphasis and look.hook.emphasis in core/captions.py)
- [x] 9.5 Real font measurement + grapheme wrapping + max 2 lines + explicit line breaks (replace len*46 px) (built on universal-v1.1: caption_text.clusters/wrap_lines/fit_text, used when a fonts dir is given; Pillow basic layout, documented approximation)
- [x] 9.6 Caption contact sheet / reference-frame QA (plan only, no ffmpeg run) (built on universal-v1.1: caption_export.contact_sheet_plan (argv only), frame_hash, compare_frames)
- [x] 9.7 ElevenLabs word alignment into karaoke timing with phrase fallback (plan; needs owner go for API) (built on universal-v1.1: caption_export.words_from_elevenlabs (parser only, no API) + karaoke_text with phrase fallback; live use needs the owner's go)
- [x] 9.8 Mixed-script Latin fallback; preflight check that ffmpeg has libass+HarfBuzz (built on universal-v1.1: caption_text.fallback_markup + caption_export.ffmpeg_preflight (run by post.py))
- DECIDED 2026-11-07: captions inside the Instagram Reels + YouTube Shorts safe zone (bottom 896 px).

## 10. QUEUED (owner: do NOT start until existing work is finished): colour / attention-retention audit
- [x] 10.1 Read research/COLOUR_ATTENTION_RETENTION_AUDIT_2026-11-07.md (decided and built: docs/COLOUR_AUDIT_DECISIONS.md on universal-v1.1) and decide what enters the pipeline (owner asked 2026-11-07 to include it, after the current work)

## 11. Round-2 review (owner rule 5: review again after fixes)
- [x] 11.1 Super VL round 2 r1-r5 done + Dots r1-r2 (r6-r8 pending)
- [x] 11.2 Triage + fix: W1-W5 done (see research/TRIAGE_R3..R6)
- [x] 11.3 Rounds 3, 4, 5, 5B, 6 done; round 5B found 0 real defects, round 6 found 1 low (fixed); loop stopped
- [x] 11.4 Suites green (h3 594, director 658, ui 253, flow 116), secret scan clean, pushed d5804ba
