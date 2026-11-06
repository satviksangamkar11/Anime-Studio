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
- [ ] 1.6 Writer + validator carry voice_engine (writer and stage 2 done; left open for the review round)
- [x] 1.7 Tests for every new rule; all 4 suites green
- [ ] 1.8 Triage the agent's report; check its files myself

## 2. Close remaining code gaps (Haiku, medium effort)
- [x] 2.1 h3/SPEC.md refresh (old dialogue block, mode_to_video_shift_map)
- [ ] 2.2 retry_policy wired into write_pack
- [x] 2.3 run_registry event field output_languages / voice_engine
- [x] 2.4 voice .wav manifest
- [ ] 2.5 contract tests pack_to_spec <-> H3 compile (V4H3 agent building the V4->H3 converter)
- [x] 2.6 leftover old speech code check in h3_director.py
- [x] 2.7 h3/render_controller.py wiring: router, linter, asset manifest hashes, Gate D mix, Step 9, loudness
- [ ] 2.8 suites green

## 3. Review round 1 (Nemotron 3.5 Super VL via OpenRouter + Dots, in parallel; free models only)
- [ ] 3.1 Review agents A-F, S1, S2, EV and section 2 changes
- [ ] 3.2 Triage every finding against the code (reviewers give false positives)
- [ ] 3.3 Fix real findings, re-run suites

## 4. UI audit
- [ ] 4.1 Re-read research/UI_AUDIT_AND_UPDATE_PLAN_2026-11-07.md against the code as it is now
- [ ] 4.2 List UI changes: language checkboxes + All, voice engine choice for English, BGM on/off, Continue button, scoped approvals, validator report, YouTube link box, Gate D per-language panel, Step 9 + fallback rung + 4 human choices, ops panel, runs and documents
- [ ] 4.3 Endpoint contract frozen before coding

## 5. UI update (disjoint files)
- [ ] 5.1 U1 ui/server.py + ui/pipeline.py
- [ ] 5.2 U2 ui/static/pipeline.js + app.js
- [ ] 5.3 U3 ui/static/style.css + index.html + ui/test_static.py (phone width, focus)
- [ ] 5.4 ui tests green

## 6. Review round 2 (UI) 
- [ ] 6.1 Nemotron Super VL + Dots on UI files
- [ ] 6.2 Triage and fix
- [ ] 6.3 Browser check of the UI (built-in browser)

## 7. Wrap up
- [ ] 7.1 All four suites green
- [ ] 7.2 secret scan (tools/secret_scan.py) clean
- [ ] 7.3 STATUS.md, README, HANDOFF ledger, PROJECT_LOG, memory updated
- [ ] 7.4 Ask owner before any push

## 8. Waiting on the owner (do not start)
- [ ] Captions and fonts (owner will provide)
- [ ] Paid ElevenLabs use (needs go)
- [ ] Stories: Kaliya defects, Mahadev 4th reel

## 9. Caption components (from the owner's caption research + Super VL/Dots review; reviews in research/CAPTION_REVIEW_*_2026-11-07.md). Owner supplies fonts/captions later: build only the code parts, no downloads
- [ ] 9.1 SRT + WebVTT sidecar export per language (from the same cues)
- [x] 9.2 Safe zone: bottom margin 896 (35%), top 360 (14%), sides 160; per-platform templates still to build
- [ ] 9.3 Font glyph-coverage QA with fontTools (माझं कुठे ॲप क्ष ज्ञ ळ ऱ)
- [ ] 9.4 Hook-word emphasis style
- [ ] 9.5 Real font measurement + grapheme wrapping + max 2 lines + explicit line breaks (replace len*46 px)
- [ ] 9.6 Caption contact sheet / reference-frame QA (plan only, no ffmpeg run)
- [ ] 9.7 ElevenLabs word alignment into karaoke timing with phrase fallback (plan; needs owner go for API)
- [ ] 9.8 Mixed-script Latin fallback; preflight check that ffmpeg has libass+HarfBuzz
- DECIDED 2026-11-07: captions inside the Instagram Reels + YouTube Shorts safe zone (bottom 896 px).
