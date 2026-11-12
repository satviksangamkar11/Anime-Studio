# Change plan from the Opus calibration review (2026-11-12)

Source: `research/OPUS_CALIBRATION_REVIEW_2026-11-12.md` (53 KB, read completely). Nothing in the system is changed yet. Every item below is a change or an addition; an item marked OD needs an owner decision, $ needs a paid canary (Colab / ElevenLabs go), FREE can be built now with the free tools.
Labels: M = measured, Q = quoted from a creator prompt, I = inferred, R = recommended.

## 0. How to read the "proven reels use a different model" point (owner question)
The owner's argument: the creators' tool (Seedance-class) and MiniMax H3 are both video generators, and our own settings were invented by us, so the proven reels' strategy is probably better than ours.
Judgement after the review:
- **Where the owner is right:** every number we invented (cut rate, reel length, blocking caps, prompt length, beat snap, caption words) had no evidence behind it. The 32 reels are the only real evidence we have, so they replace guesses wherever they measure the same thing. These are model-independent and are adopted now: reel length (batch 1 median 30.1 s), variable shot length with one long centrepiece, hook patterns, one motivated camera move, quasi-static camera with the subject doing the work, anticipation to action to settle, short sound hits on the impact, no dead silence, delivery loudness -14 LUFS.
- **Where care is needed:** the samples are a selected, successful sample from ONE model class. Seedance works from a start image or references, has native audio, a 15 s window and no end frame; H3 in our setup is FL2VA with start AND end keyframes. So three things do not transfer automatically: the roughly 200-word prompt length, the single 15 s take, and the absence of an end frame. Those are tested with a cheap A/B canary (E1) before they become linter rules. The speed caps are a different case: the proven median (0.138 fh/s) is not a measure of character travel speed, so they are loosened or tightened only after canary E4.
- **Net:** adopt the model-independent proven patterns now; gate the three model-specific ones behind E1/E2/E4; keep our own strengths (locked timeline, A/B keyframes, blocking sheets, gates) because nothing in the sample contradicts them.

## 1. Corrections to the two guides (so no wrong number gets built in)
- [ ] G-01 Reel 1 does NOT cut too often: batch-1 multi-cut reels have a median shot of 5.1 s (M). Reel 1 was too uniform (all about 7 s) and too long (72.8 s vs batch-1 median 30.1 s). The fix is variable shot length plus one long centrepiece, not fewer cuts.
- [ ] G-02 The 32 reels are two populations: batch 1 (16 full-bleed reels) and batch 2 (16 prompt-showcase reels with the video in a sub-window, letterbox median 0.147). Use batch 1 for editing numbers; re-measure batch 2 inside its video box (E0b).
- [ ] G-03 Wrong attributions in Gemini: LRA 12.2 belongs to Dd6h9xAy_sS (not DeBiEEsszx-, which is 2.6); +1.8 dBTP belongs to Dc00aP-ypy_; Dd1OhelBa2y cut-on-beat is 0.125 (chance 0.224), not 50%; subject p95 on DZrSotPhi2v is 0.391, not 0.289.
- [ ] G-04 Rejected Gemini items: camera speeds in fh/s inside prompts (below the noise floor, models do not read fh/s); SSIM_1s >= 0.50 gate (fails 3 of 6 verified single takes); LRA 4-5.5 target (single takes run 8-12 LU; keep core lra 11); subject-speed gate 0.08-0.28 (flat-colour cel reads slow); "low histogram correlation = identity drift" (a metric artefact of whip pans); captions at y 62-68% "clearing the bottom 35%" (self-contradictory).
- [ ] G-05 Our own summary errors: change 1 reason wrong (see G-01), change 3 rests on a non-translation metric, change 5 (LRA) contradicted, change 9 ignores rule 51 and the core.json conflict, change 11 numbers partly contradicted.
- [ ] G-06 Speech: no reel has narration. Max speech 2.06 s per reel; of 6 whisper hits 3 are real one-word calls and 3 are hallucinations. The sample cannot judge narrated reels, so it gives no reason to drop the 3-language voice (product decision stays with the owner).
- [ ] G-07 Prompt-length figures reconciled: video part median 198-200 words (n=22-23), whole pasted prompt 324 words, first-frame image prompt median 79 words (n=16). Use these definitions from now on.
- [ ] G-08 Frame rate: 12 of 16 batch-1 reels are 30 fps and 4 are 24 fps; we stay 24 fps.
- [ ] G-09 What the AI-filmmaking frameworks add: the 8-block image prompt (yes, as plain sentences), the I2V rule "the image defines subject, style, composition; spend the words on motion" (yes, strongly), one motivated camera move per shot (yes), shot-size/angle/lens matrix (yes as writer defaults), animatic and motion-test stages with one variable at a time (yes). NOT applicable: Flow slash commands (/establishingshot ...) become literal text in Nano Banana and trip tag hygiene in H3; Veo/Flow video commands (extend, jump-to) belong to another tool, our equivalent is last-frame chaining.

## 2. Findings in our own system (found by the review, not by the reels)
- [ ] S-01 core.json `safe_zone_frac.reels` bottom 0.35 and `caption_band` [0.50, 0.65] contradict rule 51 (`\pos(510,1290)` = 67.2%, bottom limit y 1420 = 74%). One source needed. (OD, see D-02)
- [ ] S-02 `script_pacing` re-hooks at a fixed 25-35 s; core.json says `rehook_window_frac` [0.45, 0.60]. Use core.
- [ ] S-03 `script_pacing` fixed 60-75 s window; make the target per story.
- [ ] S-04 `keyframe_jobs` builds picture A from raw coordinates ("Krishna at (0.5,0.6), scale 0.5"), which Nano Banana cannot use; rewrite as sentences.
- [ ] S-05 MO-01 requires the phrase "while his lips remain completely closed", which the approved per-person mouth sentence never emits; MO-01 must change.
- [ ] S-06 The MASTER_PROMPT section c2 example sheet has `"arms": "down"`, which BLK-S16 rejects (must be an integer >= 2). Fix the brief example.
- [ ] S-07 Rule 50(6) already mutes most H3 SFX, so sound words in the video prompt mainly steer visual timing; the sound sentence must follow cue time.
- [ ] S-08 Three-language length: hi/mr lines run longer than en at MAX_TEMPO 1.0; add a per-shot check max(en,hi,mr) <= edit seconds.
- [ ] S-09 A narrated benchmark set is missing; every number about narration is untested.

## 3. Decisions (OD) with the recommended answer
- [ ] D-01 D1 = option B (W-07): sound cues leave the action sentences and go to `overall_soundscape` in time order; `SX_MIN_STAGE_CUES` 7 -> 0; new check SX-02 (every blocking cue head noun appears in the soundscape in t order); duplicate-sentence guard becomes a compile error; mouth sentence per person (D2) with MO-01 rewritten; blocking files load from `<pack>/blocking/SHOT-NNN.json` via `blocking.load_reel`. Matches the owner's earlier answer 2 (cues out of the action sentences).
- [ ] D-02 X-16 / rule 51: keep caption position (centre y 1290 = 67.2%, card bottom <= 1420 = 74%, x 90-930). Split two margins: TEXT-SAFE for captions, SUBJECT-SAFE (top 14%, bottom 35%) for faces/key action: no face, mouth or key action of a captioned shot below y 0.62 (new lint L15). Words: en <= 4, hi/mr <= 3 and <= 18 characters; `max_words 6` only for title/hook cards. Amendment D text (below, section 10) is ready for blot.md. NOTE: this reinterprets the owner's 35% figure, so the owner must confirm.
- [ ] D-03 D4 = (a) hard end: render SOFT_SE/KFI as hard SE; do NOT build W-10 for reel 2. Re-open W-10 only if the reel-2 canary shows TAIL_SNAP on more than 1 of 3 SE clips after trimming, or a needed hold cannot be trimmed.
- [x] D-04 Reel length: NOT FIXED (owner 2026-11-12). The 32 reels are tutorial/prompt-showcase shorts, not story videos; we amplify the story, so each reel's length follows its story. The 30-45 s recommendation is withdrawn. What stays: variable shot lengths and one long centrepiece when the story has one (P-02), and the within-reel pacing rules.
- [ ] D-05 Voice-over (OD, product): keep the 3-language narration; add the optional writer field `voice_rest:[t0,t1]` for 2-4 s voice-free windows at the climax; test with E6.
- [ ] D-06 Hook rule (OD): `HOOK_WINDOW_S` 3.0 -> 2.0 with exemption when shot 1 `hook_type = scale_tableau`; `none` refused for shot 1.
- [ ] D-07 Route S (start-only) for chain continuations and open-ended reveals needs the owner's `SHOT_MODE_S_ALLOW` approval and canary E3.

## 4. Setting changes (exact)
Order: do the high-confidence ones now; the rest behind their canary.
- [ ] T-01 script_pacing: re-hook from `core.retention.rehook_window_frac` [0.45, 0.60] of total when total >= 36 s (high). 
- [ ] T-02 script_pacing: length window comes from the story (`story.json reel_target_s`, optional); NO fixed recommended length. The current 60-75 s window becomes a per-story default that the writer may override; warn only when a reel is far outside what its own beat count needs.
- [ ] T-03 script_hook: `HOOK_WINDOW_S` 2.0 with the `scale_tableau` exemption; first voiced word at 0.3-1.0 s (audio_edge lead-in) (med / low).
- [ ] T-04 timeline lock: `snap` default false; align hits to the picture in Ableton (impact +-1 frame) (low-med).
- [ ] T-05 timeline lock: allow `edit_frames` < `pixel_frames` down to 60 frames (2.5 s edit from a 107-frame render) (med).
- [ ] T-06 gate_d / core.delivery.audio: keep -14 LUFS, true peak -1.0, `lra` 11; ADD NO_SILENCE (no span > 0.3 s below -50 dBFS = fail) and LRA warn > 11 (high / med).
- [ ] T-07 clip_qa: FLICKER_LIMIT stays 0.1 until 3 accepted reel-2 clips give a distribution, then clip p95 + 20%; ADD within-clip HSV histogram correlation (first frame vs every frame, 16x8): warn < 0.60, fail < 0.40 on uncut clips; ADD SSIM_1s warn < 0.20 only (no pass gate) (med).
- [ ] T-08 clip_gates: keep `end_frame_pass` (ssim .82 / lpips .18 / cos .88) for SE; skip for route S.
- [ ] T-09 blocking_lint (behind canary E4, R5: do not tighten before it): MAX_SPEED_H walk 0.5 -> 0.35 (0.35-0.5 only with `pace:"fast"`, warn); SLOW_SPEED_H 0.25 -> 0.15; POSE_CHANGE_MIN_SEC 1.0 -> 1.5 (sit/stand) plus `POSE_CHANGE_SLOW_SEC` 2.0 (kneel/lie, lie/stand); TURN_90_MIN_SEC 1.0 -> 1.5; TURN_180_MIN_SEC 2.0 -> 3.0; MAX_MOVING 3 -> 2 articulated movers (kind `crowd` exempt); CONT_TOL 0.05 kept plus facing and pose equality on `cut_to_next:"match"`. All low confidence except MAX_MOVING (med).
- [ ] T-10 h3 profiles / linter (ONLY if E1 passes): `min_imd_body_chars` 600 -> 900, `max_imd_body_chars` 4000 -> 2600, new PR-09 warn when motion words (stages + cadence + camera) < 120 or > 300. TG-01 stays (no range labels); beats are written as single time points ("At second 3,").
- [ ] T-11 core.json: `safe_zone_templates.reels` = {top 0.13, bottom 0.26, right 0.139, caption_band [0.62, 0.74], subject_safe_bottom 0.35, subject_safe_top 0.14}; shorts caption_band [0.62, 0.74], bottom 0.26; `captions` = {max_words {en 4, hi 3, mr 3}, max_chars_deva 18, title_card_max_words 6}.
- [ ] T-12 schema_and_linter: `SX_MIN_STAGE_CUES` 7 -> 0 and remove the stage check (lines ~874-876); add SX-02; MO-01 per-person form ("<name> keeps their lips completely closed" / "<name> speaks with moving lips"); `MOUTH_LOCK_SENTENCE` only for zero-cast shots; delete the breath exception.

## 5. Image prompt changes (Flow / Nano Banana 2.1)
- [ ] I-01 Start picture A = eight plain sentences, no labels, no slash commands, no coordinates, <= 110 words (creator median 79): (1) style anchor from the style pack + STYLE chip, (2) shot size + angle + perspective words (no mm numbers: "85mm" pulls toward photoreal in flat cel), (3) composition from blocking x/y/scale via the mapping table, (4) subject: bible name + pose + facing + expression + hands + prop state, (5) space: only the plate landmarks needed, (6) light direction + palette, (7) continuity from the previous shot's end, (8) frame law "Vertical 9:16 frame. Faces stay in the upper two thirds."
- [ ] I-02 Coordinate-to-words mapping (code): x <0.33 left third / <=0.67 centre / else right third; y <0.40 high / <0.62 mid-height / else low; scale >=0.80 filling most of the frame height / 0.45-0.80 full figure about half / 0.20-0.45 a small full figure / <0.20 a tiny figure; facing left/right -> screen-left/right, camera -> facing the viewer, away -> seen from behind.
- [ ] I-03 One short exclusion sentence at the end ("No text, no logo, no extra people, no halo."), at most 4 nouns from the bible's forbidden list. Leave out: costume re-description (the character chip carries it), camera motion, mm numbers, film/show names, any count you cannot see.
- [ ] I-04 Picture B = a NEW generation with the `<SHOT>-A final` tile as first chip (not a Flow in-place edit): "Same picture, same framing, same light, same background. Change only: 1) ... 2) ... 3) ..." from `blocking.change_list`; MAX 3 changes. Rules enforced by lint and the keyframe gate: same framing and angle; no screen-side flip (x crossing 0.5 needs an L10 turn record and a >= 3 s shot); key light side unchanged unless the beat is an emissive ignition; prop count and identity unchanged; facing change at most 90 degrees per 1.5 s. Empty-plate and reveal shots: no B (route S, or B = A plus one atmospheric change). Rename `method:"edit"` / `base_edit_id` in keyframe_jobs to `generate_with_chip`.
- [ ] I-05 Reference sheets BEFORE any keyframe, one accepted before the next: CHAR identity master (front, neutral grey, locked hexes), CHAR turnaround (front, 3/4, side, back), CHAR expressions (6 heads), LOCATION plates (per location and key light), PROP sheets (with a grey human outline for scale), STYLE chip (line weight, cel shadow, swatches), and a CONTINUITY sheet generated by code from the blocking sheets (screen direction, eyeline pairs, prop states, end state of each shot).
- [ ] I-06 Worked examples (A, B, empty plate in the Kalika Puran style) are in Opus section 4.4; reuse them as test fixtures.

## 6. Video prompt changes (MiniMax H3 FL2VA through our compiler)
- [ ] V-01 Template order (kept): [Shot 1] style prefix + "preserving the exact character design ..."; stages 1-5 time-anchored; cadence clause; ONE camera sentence; cast line; mouth sentence; stages 6-7 (tail, deduped).
- [ ] V-02 Stages start with a SINGLE time point ("At second 0," "At second 2.5," "By second 6,"), never a range (TG-01). Each stage = ONE subject verb + ONE physical reaction (cloth, water, dust, hair). Anticipation stage before the primary action. Holds name the stillness ("<name> does not move.").
- [ ] V-03 Camera sentence: exactly one move from the vocabulary table (section 8) + its motivation, or "The camera stays locked." Shake only as "a short shake at second N" when `camera.shake` is set.
- [ ] V-04 Do not repeat from the images: costume, colours, faces, background objects. Exception: a prop that must keep its shape (<= 6 words).
- [ ] V-05 Soundscape (D1 = B): "Sound effects only: <bed>. First <cue>; then <cue>; finally <cue>." at most 4 sentences, cues in t order, `non_diegetic_music: N/A`.
- [ ] V-06 Length: body 900-2600 characters, 120-300 motion words, but only after E1; until then keep 600-4000. Shorter shots use the low end, 10-14 s shots the high end.
- [ ] V-07 Linter fit: no quotes (TX-01), no chips, no arrows, no `[shot:` tags, no ranges, ASCII soundscape, no blank line.
- [ ] V-08 Five worked examples (slow scale reveal, character action with lip movement, chained second clip with CURRENT CHARACTER STATE, crowd, close-up emotional) are in Opus section 5.2; use them as the golden compile fixtures.

## 7. Shot planning and camera planning
- [ ] P-01 (length not fixed, see D-04) Reel premise line + 4-beat arc (Hook 0-2 s, Setup, Escalation, Payoff last 5 s); writer brief adds `premise` and per-shot `arc_beat`.
- [ ] P-02 Variable shot lengths: at least one shot <= 4.4 s (trimmed impact) and ONE centrepiece >= 10 s per reel >= 25 s; anti-metronome lint: no two consecutive shots within +-0.5 s of each other's length.
- [ ] P-03 Cut on new information or impact; hold while one subject keeps changing; prefer one long take over two cuts when subject and place are the same. 2-4 sub-beats per shot, each >= 1.5 s (anticipation, hold).
- [ ] P-04 Hook patterns `hook_type`: kinetic (motion/impact before 2.0 s), scale_tableau (frame 0 shows extreme scale contrast), voice_call (one named call before 2.0 s).
- [ ] P-05 Camera: enum `camera.move` (null/locked, push_in, pull_back, pan_left/right <= 60 degrees, tilt_up/down along a leading line, track_left/right at pace <= walk, orbit_left/right only when all cast hold or do not move (L12), crane_up/down, handheld_drift with no other move, shake {t, dur 0.3-1.5} impact only on body_action/seam). Writer default angle/lens by emotion: awe/scale low or ground angle wide; dread high angle wide with negative space; intimacy/grief eye level close tele; resolve/triumph low angle medium; calm/devotion eye level centred normal.
- [ ] P-06 blocking/1.1 (additive and optional; 1.0 sheets must still load): `emotion`, `composition`, `route`, `beats[]` {t,label,action,physics,primary} (lint L14: 2-4 beats, ascending, gaps >= 1.5 s, exactly one primary, t < seconds), `chain_from` (L17: previous `cut_to_next` == "match", depth <= 2), `voice_rest`, `hook_type` (L16 required on shot 1), `camera.angle/lens/motivation/shake` (BLK-S06 enums, L11: mode fixed <=> move null, motivation required when move set, L13 shake inside the shot), `cast[].hold`, `cast[].expression` (BLK-S16 from the bible list), `cast[].pace` + `fast`, `sound_cues[].kind` (hit/bed, SX-02), computed `caption_safe` (L15). The full example sheet is in Opus section 6.3. Rich-shot `beats` move into blocking (single source, rule 57).
- [ ] P-07 MASTER_PROMPT v2.4: fix the c2 example (`arms` integer), add the new fields, premise + arc, camera vocabulary table, beats moved to blocking.

## 8. Consistency strategy (all items)
- [ ] C-01 Reference bible accepted before keyframes (I-05).
- [ ] C-02 A/B discipline (I-04). Keyframe gate: background SSIM (masked outside cast boxes) >= 0.80, palette DeltaE2000 <= 6 (core g1), cast count equal.
- [ ] C-03 Last-frame chaining: A(N+1) = the last KEPT decoded frame of accepted clip N after trim (not B(N)); PNG at render resolution 768x1344, never regenerated in Flow; chain depth <= 2 then re-anchor to a fresh Flow keyframe; gate: frame 0 of N+1 vs that PNG SSIM >= 0.90; prompt header "CURRENT CHARACTER STATE ... Continue directly from this exact frame with no reset"; max 2 chained clips (reel 29 used 2).
- [ ] C-04 Identity gates per clip: face cosine vs CHAR master >= 0.88 on first, middle, last frame; within-clip hist corr warn < 0.60 / fail < 0.40; SSIM_1s warn < 0.20; NEW_CLASS after frame 12 (exists); TAIL_SNAP trim (exists); `end_frame_pass` for SE only.
- [ ] C-05 Palette/line locks: style-pack palette ids only; g1 DeltaE <= 6 vs the plate; g3 cut jump DeltaE <= 8 between neighbours; STYLE chip attached to every A job.
- [ ] C-06 Settings lock: `add_settings_sha` hashes {Wan2GP pin bd1ff59, profile sha, steps, cfg, sampler, seed, resolution, prompt sha, A/B sha}; any change = a new `render_version`; seed fixed per shot and changed only in pass 5.
- [ ] C-07 Drift iteration order, one variable per pass, logged: 1 simplify action (one primary, add holds) -> 2 remove camera move -> 3 move B closer to A -> 4 split the shot or chain -> 5 new seed -> 6 route change SE -> S. Stop after 3 renders of one shot and escalate (about 0.6 compute units each, inferred).

## 9. Sound, voice and assembly (additional items)
- [ ] A-01 Ableton cue sheet rows {shot, t_frame, kind hit/bed/rest, source cue text, voice_rest}; hits on the impact frame +-1 frame; a 2 s riser before the primary beat; no silence > 0.3 s (continuous bed); delivery -14 LUFS / -1 dBTP.
- [ ] A-02 voice_manifest.<lang>.json (schema voice_manifest/1) is the only source of spoken text for captions; row id `<SHOT-NNN>-<N|Dk>.<lang>`, NFC text, text_sha256, wav, wav_sha256, seconds, speaker; any hash mismatch stops the build; caption text differs from spoken text only by an approved `caption_diff` with the same word count. Needs an end-to-end test (voice_cast fake TTS -> manifest -> spoken_cues_real; a mutated wav raises SystemExit).
- [ ] A-03 Burn with `ass=...:fontsdir=styles/fonts:shaping=complex` after the 768x1344 -> 1080x1920 crop/scale; real-frame check: contact sheet per language plus a conjunct crop (ब्रह्मा, क्या, दक्ष); export a clean no-caption master per language.
- [ ] A-04 Text-card QA: any caption or title card frame passes a Devanagari conjunct OCR check and sits inside the text-safe box.
- [ ] A-05 Animatic gate (missing from both guides as code): A/B stills + the voice lock + guide track -> a 24 fps MP4 per language; the owner watches it before any Colab go.

## 10. Draft text for blot.md (append-only; owner to confirm)
> **AMENDMENT D: RULE 51 (captions, owner 2026-11-12).**
> (1) Two margins, one source (core/core.json): TEXT-SAFE for burned captions is x 90-930, y 250-1420 on 1080x1920 (top 13%, bottom 26%, right 14%); captions sit at `\an5\pos(510,1290)`, the bottom line fixed for 2-line cards. SUBJECT-SAFE for keyframes is top 14%, bottom 35%: no face, mouth or key action of a captioned shot below y 0.62 (blocking lint L15).
> (2) Card words: en <= 4 (two balanced lines max), hi/mr <= 3 words and <= 18 characters; title/hook cards <= 6 words. core.json `captions.max_words` 6 applies to title cards only.
> (3) Spoken text for captions comes only from `voice_manifest.<lang>.json` (schema voice_manifest/1). Row id `<SHOT-NNN>-<N|Dk>.<lang>`, NFC text, text_sha256, wav, wav_sha256, seconds, speaker. Any hash mismatch stops the build. Caption text differs from spoken text only by an approved `caption_diff` with the same word count.
> (4) Burn with `ass=...:fontsdir=styles/fonts:shaping=complex` after the 768x1344 to 1080x1920 crop/scale. Check on real frames: contact sheet per language plus a conjunct crop (ब्रह्मा, क्या, दक्ष).
> (5) Also export a clean (no-caption) master per language.

## 11. Experiments (cheapest first)
- [ ] E0 FREE Narrated benchmark: 10 narrated Indian-mythology reels through `measure_reels` (length, cuts, LUFS, LRA, speech share). Pass: >= 6 usable reels. Gives our real narrated length/cut targets.
- [ ] E0b FREE Re-measure batch 2 inside the video sub-window (crop to the video box). Pass: sub-window cuts match OCR/MODEL counts +-1 on >= 6 of 8 reels.
- [ ] E1 $ Same SE shot (A, B, seed fixed): current prompt (~110 motion words, untimed) vs time-pointed 220 words; 2 clips. Pass: blind owner preference for the long prompt AND within-clip hist corr >= 0.60 AND no new TAIL_SNAP. Fail (no visible difference): keep 600-4000.
- [ ] E2 $ Two-clip chain from the last kept frame + CURRENT CHARACTER STATE; 2 clips. Pass: seam SSIM >= 0.90, hist corr across the seam >= 0.60, no visible reset.
- [ ] E3 $ Route S vs SE on a scale-reveal shot; 2 clips. Pass: S keeps identity (face cosine >= 0.88 at the last frame) with no tail snap.
- [ ] E4 $ Speed/turn: one walk at 0.35 and one at 0.5 fh/s, one 180 degree turn in 3 s; 2-3 clips (can share the E1 session). Pass: 0.35 clean and 0.5 smeared confirms the caps; both clean -> keep 0.5.
- [ ] E5 $ Lip movement: two-person shot, one speaker with the D2 sentence; 1 clip. Pass: speaker's mouth moves only inside the slot +-0.3 s, the silent person stays closed.
- [ ] E6 FREE after render: reel 2 cut A (full narration) vs B (voice_rest at the climax) shown to the owner.

## 12. Risks
- R1 H3 may ignore time points (E1 fail): keep the stage structure; value is ordering only.
- R2 Longer prompts raise morph risk on short shots: use the 900-character minimum only for shots >= 7 s if E1 shows harm at 4.5 s.
- R3 Last-frame chaining carries artefacts forward (depth <= 2 mitigates).
- R4 The caption decision overrides an owner-stated 35% margin: owner must confirm.
- R5 Blocking knobs stay uncalibrated until E4: do not tighten before it, because frozen tests would change for nothing.
- R6 The W-07 regex coupling breaks many h3 tests: run the full h3 suite (about 40 test files).
- R7 Thin evidence on pose/turn/movers (no estimator ran): treat those numbers as starting points.
- R8 Sample bias (Seedance spectacle reels, 15 s tool windows) is the largest single uncertainty in every "proven" number.

## 13. Implementation order (Opus checklist 1-22, with the owner's decisions first)
1 OD D-01/D-03 + MO-01 wording (D-04 length is withdrawn) -> 2 W-07 finish (D-01) -> 3 OD caption split -> 4 core.json caption keys + build_final_reel + clean master + e2e voice manifest test -> 5 script_pacing from core -> 6 script_hook 2.0 s -> 7 blocking/1.1 fields + enums + lint L11-L17 -> 8 MASTER_PROMPT v2.4 -> 9 keyframe_jobs sentences -> 10 compiler time points + one camera sentence -> 11 blocking knobs (behind E4) -> 12 clip_qa hist corr / SSIM_1s / chain frame-0 -> 13 gate_d NO_SILENCE -> 14 lock snap default false + short edit_frames -> 15 chain step (last kept frame, depth <= 2) -> 16 animatic gate -> 17 canaries E1-E5 -> 18 PR-05 900/2600 + PR-09 (only if E1 passes) -> 19 narrated benchmark (E0; reel length is per story) -> 20 Ableton cue sheet fields -> 21 text-card QA -> 22 three-language length check.
Items 2, 4-10, 12-15, 20-22 are code that the free tools (Super + reviews) can build and test offline; 11 and 18 wait for canaries; 16 is a small ffmpeg tool; 17 needs the owner's Colab go.

## 14. Open question raised by the owner: start-only (S) versus start+end (SE)
See the answer in the chat of 2026-11-12: per-shot route, canary E3 decides the default; S needs a new compile workflow (compile_h3_sing8 knows only FL2VA and Ref2VA).
