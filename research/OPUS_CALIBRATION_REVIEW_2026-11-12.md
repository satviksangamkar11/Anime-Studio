# Opus calibration review: 32 proven reels vs our system (2026-11-12)

Read-only review (Opus, owner-authorised). No code or existing file changed. Labels: **MEASURED** (our validated measure_reels output, `reanalysis/measure/*.json`), **QUOTED** (creator prompt text, `reanalysis/prompts/*.json`, OCR), **INFERRED** (reasoning, model or Gemini judgement), **RECOMMENDED** (my proposal). Reel ids are Instagram ids; Gemini's #numbers are given where it used them.

---

## 0. The eight findings that matter most

1. **The 32 reels are not one population.** Batch 2 (16 reels) are prompt-showcase/tutorial reels: the video sits in a sub-window with prompt cards (letterbox median 0.147). Strict cut detection misses their in-window cuts, and camera motion is pinned to 0. Every all-32 median for cuts, shot length and camera is biased. **Use batch 1 (full-bleed, 16 reels) for editing numbers.**
2. **Our 7 s cut rate is NOT too fast.** Batch 1 multi-cut reels (12 reels with 2 or more cuts) have a median shot of **5.1 s** (MEASURED: 2.53, 3.63, 3.90, 4.68, 4.70, 4.95, 5.30, 6.02, 6.30, 6.90, 6.98, 9.60). Reel 1 is too **uniform** and too **long** (72.8 s against a batch 1 median of 30.1 s). It does not cut too often. Both guides got this wrong ("cut 2x too often").
3. **The creators wrote for a different model class.** Every reel that names a model names Seedance 2.0/2.5 (QUOTED: DY2AvnNTNdP, DYPUg_KPU8u, DYR1DWJvftu, Dego7pnB6Gs). Those prompts are 15 s, start-image or reference driven (`@image1`, "Animate forward from this exact image"), with native audio and **no end frame**. We run H3 FL2VA with two keyframes, so motion is already bounded by A and B. Their prompt length transfers only partly. It is a hypothesis for a canary test, not a rule.
4. **Our linter would refuse the creators' format.** TG-01 (`TIMING_LABEL_RE`, schema_and_linter.py:104) bans `0-3s` ranges. Gemini's template (`[0.0s–3.5s]`) fails PR-00/TG-01. Single time points ("At second 3, ...") pass the regex today, so time-coded beats are possible without changing the linter.
5. **No reel in the 32 has narration.** Maximum speech is 2.06 s per reel (MEASURED). Of the 6 whisper hits, 3 are real one-word calls (VASUKI! at 2.03 s, Погнали! at 1.07 s, a sampled intro at 2.16 s) and 3 are typical whisper hallucinations ("Субтитры субтитров Н.Новик", "you", "You"). The sample holds spectacle reels only. It **cannot judge narrated katha reels**, so it gives no reason to drop our 3-language voice. That is a product decision, and we need a narrated benchmark set.
6. **Gemini's QA gates would fail proven footage.** SSIM_1s ≥ 0.50 would fail 3 of 6 verified single takes (DZwJE4_hMuG 0.234, DZua04Yh0f0 0.353, De5vZ9QhJBm 0.454). LRA 4-5.5 is contradicted by 7 single takes with LRA 8.3-12.2. Only the within-take histogram correlation ≥ 0.60 holds on verified uncut takes (min 0.629, n=6).
7. **The blocking speed caps from "subject median 0.138 fh/s" are a category error.** That number is the median of a 90th-percentile flow magnitude over frames. It is not centroid translation, and the method notes say it under-reports flat-colour footage. It bounds sustained motion loosely and cannot set MAX_SPEED_H. A small tightening is reasonable. Calibration still needs our own canary.
8. **Two contradictions inside our own system** show up before any new rule is needed:
   - core.json `safe_zone_frac.reels` = bottom 0.35 and `caption_band` [0.50, 0.65], but rule 51 places captions at `\pos(510,1290)` (67.2 %) with a bottom limit of y 1420 (74 %).
   - script_pacing re-hooks at a fixed 25-35 s, but core.json says `rehook_window_frac` [0.45, 0.60].

   Also, keyframe_jobs builds picture A from raw coordinates ("Krishna at (0.5,0.6), scale 0.5"), which Nano Banana cannot use.

---

## 1. Review of the two guides

### 1.1 Gemini claims checked against our data

| # | Gemini claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Median duration 20.97 s; batch 1 30.12, batch 2 15.16; 3 reels > 35 s | CONFIRMED | MEASURE_SUMMARY row "duration"; DeoWrqdhI0b 54.0, DdxwQdRB3PS 59.2, DeBiEEsszx- 70.3 |
| 2 | -14.0 LUFS median, range -16.6..-12.7 | CONFIRMED | two methods agree within 0.053 LU |
| 3 | "LRA max 12.2 on #13 DeBiEEsszx-" | CONTRADICTED | DeBiEEsszx- LRA 2.6. The 12.2 is Dd6h9xAy_sS. |
| 4 | "+1.8 dBTP on #09, +1.2 on #15" | CONTRADICTED | DetwqtpBcgp +0.2, Dd1OhelBa2y -0.2. The +1.8 is Dc00aP-ypy_. |
| 5 | Cut-on-beat ±1 f = 0.20 vs chance 0.175 | CONFIRMED (low confidence) | 17 reels; tempo estimators disagree on most of batch 1 |
| 6 | "#15 Dd1OhelBa2y 50 % of cuts on beat" | CONTRADICTED | measured 0.125 (chance 0.224) |
| 7 | 29 of 32 no speech; only 3 real voices | CONFIRMED in substance | 6 whisper hits, 3 hallucination-type (see §0.5). "0 of 32 narration" is MEASURED. |
| 8 | Reel 1 cuts "2x more often" than the proven reels | CONTRADICTED | Uses the all-32 median 0.605/10 s, which batch 2 biases (Gemini admits this in its own §1.2 #2). Batch 1: 1.0/10 s; multi-cut batch 1 median shot 5.1 s. |
| 9 | DdxwQdRB3PS: 4 early cuts, then a 20.04 s hold 19.13-39.17 s | CONFIRMED (strict cuts) | cuts at 9.1, 12.167, 15.1, 19.133, 39.167, but 10 sensitive-only cuts exist, so the "hold" may hide soft transitions |
| 10 | DfhVkywhsin holds 0-20.8 s | CONFIRMED (strict) | cuts [20.8, 25.167]; 9 sensitive-only cuts, so same caveat |
| 11 | Camera shake 0.000-0.003 before, 0.015-0.028 fh/s at the roar (DZrSotPhi2v) | UNVERIFIABLE | flow noise floor about 0.013-0.017 fh/s at 360p; 0.0227 at second 13 is within 2x noise |
| 12 | Camera speeds to write in prompts (0.003 fh/s dolly) | REJECT | below measurement noise; models do not read fh/s |
| 13 | subj p95 0.289 on #01 | MISQUOTED | 0.289 is the second-11 motion peak; subject_p95 is 0.391 |
| 14 | Pose/turn 2-3 s | QUOTED, not measured | DZrSotPhi2v: "Even a slight rotation takes two seconds" (for a colossal dragon head, not a human) |
| 15 | 81 % of reels have 1-2 moving figures | INFERRED (MODEL) | no figure counter ran |
| 16 | Batch 1 low take hist-corr = drift from missing reference locks | CONTRADICTED interpretation | hist corr is computed per take between strict cuts; batch 1 "takes" include whip-pans and camera moves, and batch 2 has fewer detected takes. This is a metric artifact, not evidence about identity drift. |
| 17 | Video prompt median 198 words | CONFIRMED (with a definition) | `prompts/*.json`, `video_prompt_words`, n=22: median 200.5, range 25-342. Gemini added reel 29 OCR (n=23), which gives 198. |
| 18 | "324 words" (our earlier figure) | RECONCILED | COVERAGE.md "prompt" column = whole quoted prompt (image + references + headings + video), n=28 non-empty: median (319+329)/2 = 324. Image-prompt median 79 (n=16). 198 ≈ video part only; 324 ≈ full paste. |
| 19 | Time-coded prompts in 16 of 32 | ROUGHLY CONFIRMED | 12 of 24 extracted JSON are `time_coded`, more from OCR |
| 20 | Hooks: 15 kinetic / 10 scale tableau / 7 weak | PARTLY | 15 reels have a measured hook time (median 1.8 s, batch 1 0.9 s). The 10/7 split is MODEL judgement. |
| 21 | Captions at y 62-68 % "clearing the bottom 35 %" | SELF-CONTRADICTORY | 62-68 % from top lies inside the bottom 35 % band (which starts at 65 %) |
| 22 | QA: SSIM_1s ≥ 0.50 action / 0.68 hold | CONTRADICTED | 3 of 6 verified single takes are below 0.50 |
| 23 | QA: take hist corr ≥ 0.60 | SUPPORTED for uncut clips only | verified single takes: 0.629-0.99 |
| 24 | Subject-speed gate 0.08-0.28 fh/s | REJECT for our style | the flat-fill limit (MEASURE_SUMMARY validation) makes cel footage read slow, so the gate would false-fail |
| 25 | Silence: 0 reels with > 0.3 s at -50 dB | CONFIRMED | MEASURED |

### 1.2 Our own summary (gemini_results/SUMMARY_AND_PROPOSED_CHANGES.md): errors and omissions
- **"Its numbers match our measured files"**: mostly, but items 3, 4, 6 and 13 above are wrong reel attributions.
- **Change 1 (25-32 s, 3-5 cuts)**: the length is supported by batch 1 (median 30.1 s). The stated reason ("cut every 7 s is wrong") is not: proven multi-cut reels cut every ~5 s, non-uniformly (2.5-20 s). The real fix is variable shot length plus one long centrepiece. 15 s single takes are partly a tool limit (Seedance window = 15 s; 8 reels are exactly 14.8-15.2 s).
- **Change 2**: omits that TG-01 bans range labels and that the reference prompts are Seedance, not H3 FL2VA. The 80-word image prompt is fine (MEASURED median 79).
- **Change 3**: the speed caps rest on a metric that does not measure translation (§0.7).
- **Change 5**: LRA 4-5.5 is contradicted by the single takes. core.json `lra: 11` is already a better ceiling.
- **Change 6**: "29 vs 6" is not a conflict (see §0.5). The real omission is that the sample has no narrated reels.
- **Change 9**: ignores that rule 51 already places captions at 67 %, and that core.json disagrees with rule 51.
- **Change 11**: its QA numbers are partly contradicted (items 22-24).
- **Missing from both guides:**
  - frame rate: 12 of 16 batch 1 reels are 30 fps and 4 are 24 fps; we stay 24, fine
  - keyframe_jobs coordinate prompts
  - script_pacing's fixed 60-75 s window and the fixed 25-35 s re-hook
  - MO-01 rejecting the approved per-person mouth sentence (D2)
  - rule 50(6) already mutes most H3 SFX, so sound words in the prompt mainly steer visual timing
  - three-language length differences (hi/mr lines run longer than en at MAX_TEMPO 1.0)
  - the need for a narrated benchmark set

### 1.3 What the AI-filmmaking frameworks add, and what applies to H3 + Wan2GP + Nano Banana
The framework documents themselves are not in our folder. This is judged from Gemini Part D, which carries them.

| Framework item | What the 32 reels cannot show | Applies to us? |
|---|---|---|
| 8-block image prompt (intent, frame, optics, subject+blocking, space, light/materials, continuity) | A shared vocabulary and ordering | **YES for Nano Banana A frames** (§4). Lens mm becomes perspective words in flat cel, because "85mm" pulls toward photoreal. |
| I2V vs T2V rule: "image already defines subject, style, composition; spend words on motion" | Why long prompts help | **YES, strongly, for H3 FL2VA**: A and B fix appearance. Our compile already repeats the style prefix plus "preserving the exact character design"; drop further appearance text from stages. |
| One motivated camera move per shot; conflicting camera instructions break the background | | **YES**. Already in MASTER_PROMPT (b)5; enforce via a camera.move enum (§6). |
| Shot-size / angle / composition / lens matrix | Emotion-to-angle mapping | **YES as writer defaults** (§6.3), not as hard lint. |
| Google Flow slash commands (`/establishingshot`, `/lowlight`, ...) | | **NO** for our prompts. They are Flow/Veo video UI presets. Typed into a Nano Banana text prompt they become literal text, and in H3 they trip TG-01-style tag hygiene. Use the plain-English equivalent. |
| 10-stage workflow: animatic, motion test, one variable at a time | | **YES**: animatic gate and iteration order (§7, §9). |
| Veo/Flow video commands (extend, jump-to, scene builder) | | **NO** (another tool). Our equivalent is last-frame chaining (§2c). |

---

## 2. The three open cards

### 2a. W-07 / D1: SX-01 sound cues, duplicate guard, mouth sentence, blocking location
**DECISION: D1 = B.** Move cues out of the action sentences into `overall_soundscape`; set `SX_MIN_STAGE_CUES = 0`; add one coverage rule (SX-02).

Reasoning:
1. The owner's 2026-11-11 answer #2 already says "move sound cues out of action sentences into the soundscape (SX-01 amended)". B is that.
2. The ", with <cue>" glue makes broken sentences (W9/Q3: "Sati lifts the veil, with a veil snaps"). Option A only swaps the separator, and 7 cues still crowd 7 short sentences.
3. H3's official format has a dedicated `overall_soundscape` line. The creators inline sound only because Seedance has no such field (QUOTED: DZrSotPhi2v "Blizzard howls around its body"). The one creator who separates audio (Dc00aP-ypy_) uses an "Audio:" block.
4. Rule 50(6) keeps only short script-cue hits from model audio anyway. Sound words matter for sync, so the order in the soundscape must follow cue time.

Exact change:
- **v4_to_h3.py:164**: `sentence = "; ".join(x for x in actions if x)`. Delete the SX vocabulary problem at lines 166-168. Pass the stage cues to `_soundscape(track, sid, problems, extra=stage_cues)`. Cues are sorted by `t`, deduplicated case-insensitively, and packed into 1-4 sentences of the form "First <cue>; then <cue>; finally <cue>." (no digit ranges).
- **schema_and_linter.py:112**: `SX_MIN_STAGE_CUES = 0`. Remove the stage check at 874-876.
- **NEW SX-02**: every `blocking.sound_cues[].text` head noun appears in the compiled `overall_soundscape`, in `t` order.
- **Duplicate-sentence guard** (deferred xfail in W-07): at the end of `_fl2va`/`compile_fl2va_prompt`, raise `ValueError(f"{sid}: duplicate sentence")` if `prompt_hygiene.find_duplicate_sentences(body)` is non-empty, and likewise for `find_cue_glue(body)`. Keep `_tail` dedupe.
- **Mouth (D2, owner-approved 2026-11-11 #3)**:
  - Replace `_mouth_lock` with `prompt_hygiene.mouth_sentence(on_screen_names, speaking_names)` from the blocking cast (`speaks`).
  - Delete the breath exception (v4_to_h3.py:189-190).
  - **MO-01 must change**: today it requires `"while his lips remain completely closed"`, which `mouth_sentence` never emits. New MO-01: for each silent on-screen name the body contains `"<name> keep(s) their lips (completely )?closed"`; for each speaker, `"<name> speaks with moving lips"`. `MOUTH_LOCK_SENTENCE` stays only for zero-cast shots.
- **Where blocking files live**: `<pack>/blocking/SHOT-NNN.json`, written by write_pack_glue.py:123-135. `blocking.load_sheet` enforces file name = shot_id. Use `blocking.load_reel(os.path.join(pack, "blocking"), shot_ids)`; no new loader. `convert_pack(..., blocking=load_reel(...))`.

Tests (h3/tests/test_prompt_wiring.py):
- `test_glue_gone` and `test_duplicate_sentence_refused`: flip from xfail(strict) to pass.
- `test_sx02_all_cues_in_soundscape_in_order`
- `test_sx_min_zero_no_stage_error`
- `test_soundscape_max_4_sentences_with_7_cues`
- `test_mouth_two_people_one_speaker` (expects "Sati speaks with moving lips; Shiva keeps their lips completely closed")
- `test_mo01_accepts_mouth_sentence`
- `test_no_breath_exception`
- `test_blocking_loaded_from_pack_folder`
- Acceptance: `python -m pytest h3/tests -q`, with zero `", with "` in v4_to_h3.py.

### 2b. X-16: captions, rule 51 text, voice manifest, placement
Status: blot already carries "AMENDMENT A: RULE 51" (caption_text/caption_diff_approved, crop before ASS). Two things remain open: (1) core.json and rule 51 disagree, and (2) the voice manifest is built (`director/voice_manifest.py`, schema `voice_manifest/1`) but the voice_cast to manifest to build_final_reel chain has no end-to-end test.

Placement evidence:
- The proven reels give **no caption evidence**: batch 1 has no story captions (12 of 16, MODEL/OCR); batch 2 shows prompt cards.
- The 14 %/35 % margins are Meta's ad safe-zone figures (the bottom 35 % includes the ad CTA). Rule 51 used organic Reels/Shorts UI figures (top 250 px = 13 %, bottom 500 px = 26 %) and was checked on reel 1 frames.

**DECISION (owner to confirm the text): keep rule 51 placement; split "subject safe" from "text safe".**
- Captions: centre y 1290 (67.2 %), card bottom ≤ 1420 (74 %), x 90-930.
- Faces and key action stay above y 0.62 in every keyframe, so captions never cover a face. This is what the 35 % bottom margin actually protects.
- Words: en ≤ 4, hi/mr ≤ 3 and ≤ 18 characters, as in rule 51. `max_words 6` survives only for title and hook cards.

Draft text for blot.md (append-only):
> **AMENDMENT D: RULE 51 (captions, owner 2026-11-12).**
> (1) Two margins, one source (core/core.json): TEXT-SAFE for burned captions is x 90-930, y 250-1420 on 1080x1920 (top 13 %, bottom 26 %, right 14 %); captions sit at `\an5\pos(510,1290)`, the bottom line fixed for 2-line cards. SUBJECT-SAFE for keyframes is top 14 %, bottom 35 %: no face, mouth or key action of a captioned shot below y 0.62 (blocking lint L15).
> (2) Card words: en ≤ 4 (two balanced lines max), hi/mr ≤ 3 words and ≤ 18 characters; title/hook cards ≤ 6 words. core.json `captions.max_words` 6 applies to title cards only.
> (3) Spoken text for captions comes only from `voice_manifest.<lang>.json` (schema voice_manifest/1). Row id `<SHOT-NNN>-<N|Dk>.<lang>`, NFC text, text_sha256, wav, wav_sha256, seconds, speaker. Any hash mismatch stops the build. Caption text differs from spoken text only by an approved `caption_diff` with the same word count.
> (4) Burn with `ass=...:fontsdir=styles/fonts:shaping=complex` after the 768x1344 to 1080x1920 crop/scale. Check on real frames: contact sheet per language plus a conjunct crop (ब्रह्मा, क्या, दक्ष).
> (5) Also export a clean (no-caption) master per language.

Code to match:
- core.json `safe_zone_templates.reels` = `{"top":0.13,"bottom":0.26,"right":0.139,"caption_band":[0.62,0.74],"subject_safe_bottom":0.35,"subject_safe_top":0.14}`
- shorts: caption_band [0.62, 0.74], bottom 0.26
- `captions` = `{"max_words":{"en":4,"hi":3,"mr":3},"max_chars_deva":18,"title_card_max_words":6}`

Tests:
- `test_core_caption_band_matches_rule51_pos` (1290/1920 inside the band)
- `test_caption_word_caps_per_lang`
- `test_e2e_voice_manifest_to_captions`: voice_cast export_wavs (fake TTS) writes manifest, then spoken_cues_real reads it; a mutated wav raises SystemExit.
- `test_clean_master_written`

### 2c. W-10 / D4: soft end
**DECISION: D4 = (a). Render SOFT_SE/KFI as hard SE on bd1ff59. Do not build W-10 for reel 2.**

Reasoning:
1. **No proven reel uses an end-frame anchor.** QUOTED: 0 of 24 extracted prompts give an end frame. Their anchors are the start image ("Animate forward from this exact image": DZrSotPhi2v, DZwJE4_hMuG) and, for long takes, the **last decoded frame of the previous clip** (DZP6jIHyvg2 OCR: "Use uploaded last frame as the first frame reference ... Continue directly from the previous 10-second clip ... No reset ... no cuts"). Its seam held: within-take hist corr 0.966-0.983 (MEASURED).
2. **The soft end fixes a symptom we already handle.** `clip_gates.tail_spike` plus `suggest_trim_out` catch the snap to B. The soft end is unproven on the model (trace note: "not proven"), it needs a VM source patch, and it needs a paid canary.
3. **Our real end-frame risk is B quality.** Reel 1's shot 8 failed on A/B disagreement. An edit-of-A discipline (§4.2) addresses that at zero GPU cost.

What changes instead (all RECOMMENDED):
- **Route S (start-only) for chain continuations and for open-ended reveals** where B cannot be drawn honestly. This needs the owner's `SHOT_MODE_S_ALLOW` approval and a canary (E3).
- **Chaining**: `A_{N+1}` = the **last kept decoded frame of accepted clip N, after trim** (not `B_N`). Save it as PNG at render resolution 768x1344; never re-generate it in Flow. Chain depth ≤ 2 clips, then re-anchor to a fresh Flow keyframe so colour drift cannot accumulate. Reel 29 used 2.
- **Re-open W-10 only if** the reel 2 canary shows TAIL_SNAP on more than 1 of 3 SE clips after trimming, or a needed hold cannot be trimmed.

Test: `test_soft_se_refused_until_d4` stays.

---

## 3. Exact setting changes

Columns: file and symbol, current value, new value, evidence, M/I (measured or inferred), confidence.

| File : symbol | Now | New | Evidence | M/I | Conf |
|---|---|---|---|---|---|
| director/blocking_lint.py : MAX_SPEED_H (walk) | 0.5 | **0.35**; 0.35-0.5 allowed only with `pace:"fast"` (new, warn) | subject median ≤ 0.26 in all 32 (upper bound on sustained motion); Haiku note: a medium-full walk is about 0.45 | I | low; canary E4 |
| blocking_lint : SLOW_SPEED_H | 0.25 | **0.15** | median subject 0.138 | I | low |
| blocking_lint : POSE_CHANGE_MIN_SEC | 1.0 | **1.5** (sit/stand); add `POSE_CHANGE_SLOW_SEC = 2.0` for kneel/lie and lie/stand pairs | QUOTED 2-3 s pacing; Haiku research | I | low |
| blocking_lint : TURN_90_MIN_SEC | 1.0 | **1.5** | QUOTED "slight rotation takes two seconds" (giant creature) | I | low |
| blocking_lint : TURN_180_MIN_SEC | 2.0 | **3.0** | creator beats are 2-3 s; 180° is two such beats | I | low |
| blocking_lint : MAX_MOVING | 3 | **2** articulated movers (kind `crowd` exempt: crowd is texture) | MODEL: 26/32 with 1-2 figures; reel 1 V7 multi-figure failures | I | med |
| blocking_lint : CONT_TOL | 0.05 | keep 0.05 **plus** facing and pose equality on cut_to_next="match" | no data | I | low |
| v4_to_h3 lattice 17n+5, 107..345 | same | keep; allow **edit length 2.5-4.4 s** by trimming a 107-frame render (lock `edit_frames` < `pixel_frames`) | batch 1 multi-cut shots: 25 % below about 4 s | M | med |
| write_timeline_lock : snap default | per-shot optional | **default `snap:false`**; align hits to picture in Ableton (impact ±1 f) | on-beat 0.20 vs chance 0.175 | M | low-med |
| script_pacing.py : length warn | 60-75 s | **target per story (`story.json reel_target_s`), warn outside 25-75**; recommended 30-45 s narrated | batch 1 median 30.1, 3/32 > 35 s | M | med; owner |
| script_pacing : re-hook window | fixed 25-35 s when total ≥ 36 | `core.retention.rehook_window_frac` [0.45, 0.60] of total, when total ≥ 36 | internal contradiction | — | high |
| script_pacing : dead air in shot | gap > 1.5 s | keep (ma holds are allowed but filled by bed) | 0/32 silences | M | med |
| script_hook.py : HOOK_WINDOW_S | 3.0 | **2.0** for the visual hook event; exempt when shot 1 `hook_type:"scale_tableau"` | hook median 1.8 s (n=15), batch 1 0.9 s | M | med |
| script_hook : MAX_FIRST_LINE_WORDS | en 8, hi 6, mr 6 | keep; first voiced word at **0.3-1.0 s** (audio_edge lead-in) | proven calls at 1.07-2.03 s | M (n=3) | low |
| clip_qa.py : FLICKER_LIMIT | 0.1 placeholder | keep 0.1 until 3 accepted reel-2 clips give a distribution, then the clip p95 + 20 % | none | I | low |
| clip_qa : NEW within-clip hist corr (first frame vs every frame, HSV 16x8) | — | **warn < 0.60, fail < 0.40** on uncut clips | verified single takes 0.629-0.99 | M (n=6) | med |
| clip_qa : NEW SSIM_1s | — | **warn < 0.20** only (morph/scene jump); no pass gate | proven single takes 0.234-0.87 | M | med |
| clip_gates.end_frame_pass | ssim .82 / lpips .18 / cos .88 | keep for SE; skip for S route | — | — | — |
| h3/gate_d_audio + core.delivery.audio | -14 LUFS, tp -1.0, lra 11 | keep; **add NO_SILENCE**: no span > 0.3 s below -50 dBFS (fail); LRA warn > 11 | 0/32 silences; LRA up to 12.2 | M | high/med |
| core.json safe zones / captions | see §2b | see §2b | §2b | — | owner |
| h3 profiles : min_imd_body_chars | 600 | **900** | creator video prompt median 200 words ≈ 1200 chars | M (other model) | low; E1 first |
| h3 profiles : max_imd_body_chars | 4000 | **2600** (≈ 400 words) | creator max 342 words ≈ 2100 chars | M | med |
| schema_and_linter : NEW PR-09 | — | warn if the motion words (stages + cadence + camera) are < 120 or > 300 | same | I | low |
| schema_and_linter : SX_MIN_STAGE_CUES | 7 | **0** + SX-02 (§2a) | owner #2 | — | high |
| schema_and_linter : MO-01 | fixed phrase | per-person form (§2a) | owner #3 | — | high |
| schema_and_linter : TG-01 TIMING_LABEL_RE | bans ranges | **keep**; write single points "At second 3," | linter fact | — | high |

---

## 4. Image prompt changes (Flow / Nano Banana 2.1)

### 4.1 Start picture A: schema (≤ 110 words; measured creator median 79, range 29-312)
Order matters: Nano Banana weights early words more (INFERRED). Fields 1-8 are emitted as plain sentences with **no labels, no slash commands, no coordinates**.

| # | Field | Source (who writes) | Budget |
|---|---|---|---|
| 1 | Style anchor sentence (from style pack `mandatory_prefix`) plus the attached STYLE chip | code | 12-18 w |
| 2 | Shot size + angle + perspective words (from `camera.framing`, `camera.angle`, `camera.lens`) | code | 6-10 w |
| 3 | Composition: where each figure sits, converted from blocking x, y, scale (table below) | code | 8-15 w |
| 4 | Subject: bible name + pose + facing + expression + hands + prop state (start pose) | writer (`intent`, expression) + code (pose) | 20-35 w |
| 5 | Space: only the plate landmarks this shot needs | writer | 8-15 w |
| 6 | Light: key direction + palette words (from `light.key_dir`, `palette_id`) | code | 8-12 w |
| 7 | Continuity: what carries from the previous shot (prop in hand, wet cloth, time of day) | code from shot N-1 end | 5-12 w |
| 8 | Frame law: "Vertical 9:16 frame. Faces stay in the upper two thirds." | code | 9 w |

Blocking-to-words mapping (code):
- x: < 0.33 → "in the left third"; 0.33-0.67 → "in the centre"; > 0.67 → "in the right third"
- y: < 0.40 → "high in the frame"; 0.40-0.62 → "at mid-height"; > 0.62 → "low in the frame"
- scale: ≥ 0.80 → "filling most of the frame height"; 0.45-0.80 → "full figure about half the frame height"; 0.20-0.45 → "a small full figure"; < 0.20 → "a tiny figure"
- facing: left/right → "facing screen-left/right"; camera → "facing the viewer"; away → "seen from behind"

Negatives: Nano Banana has no negative field. Put at most one short exclusion sentence at the end: "No text, no logo, no extra people, no halo." Exclusions come from the bible's forbidden list; at most 4 nouns.

**Put in**: names from the bible, one expression, pose, the one prop state, light direction.
**Leave out**: costume re-description (the character chip carries it), camera motion (a still has none), lens numbers in mm (perspective words instead), film or show names, any count you cannot see.

### 4.2 End picture B = edit of A
- Method: NEW generation with the `<SHOT>-A final` tile attached as the first chip (IMAGE_SYSTEM_FULL §3.3). Do not use a Flow in-place edit. keyframe_jobs' `method:"edit"` / `base_edit_id` must be renamed to match.
- Text = `"Same picture, same framing, same light. Change only: 1) ... 2) ..."`, from `blocking.change_list(sheet)` (B-08 fixed). **Max 3 changes.**
- Hard rules, enforced by lint and the keyframe gate:
  - same camera framing and angle (an orbit or push shot keeps A's framing; B shows the end framing only if `camera.move` changes framing, and then needs a mid keyframe)
  - no screen-side flip (x crossing 0.5 needs an L10 turn record and a ≥ 3 s shot)
  - key light side unchanged unless the beat is an emissive ignition
  - prop count and identity unchanged
  - for a facing change, at most 90° per 1.5 s of shot
- **Empty-plate and reveal shots: no B.** Use route S, or B = A plus a single atmospheric change.

### 4.3 Reference sheets (before any keyframe; one accepted before the next)
| Sheet | Content | Prompt core |
|---|---|---|
| CHAR identity master | front full body, neutral grey ground, locked hexes | "Character sheet of <name>: full body front view, standing neutral, on plain mid-grey background, flat cel colours, ink outline. Skin #..., dhoti #..., ..." |
| CHAR turnaround | front, 3/4, side, back in one row | "Same character, four views in one row: front, three-quarter, side, back, same scale, same lighting." |
| CHAR expressions | 6 heads: calm, resolve, awe, grief, anger, joy | used by close-ups |
| LOCATION plate(s) | empty plate per location and key light | §4.4 example |
| PROP | each recurring prop beside a human silhouette for scale | "<prop>, three views, next to a plain grey human outline for scale" |
| STYLE chip | one frame showing line weight, cel shadow, palette swatches | one per style pack |
| CONTINUITY sheet (NEW, code-made, no generation) | per scene: screen direction arrow, eyeline pairs, prop states, end state of each shot | built from blocking sheets; a JPEG for the reviewer |

### 4.4 Worked examples (Kalika Puran style pack: flat cel, ink outline)

**A (SHOT-012, Krishna on the river bank, medium, start of a kneel-to-stand):**
> Flat cel animation frame with clean variable-weight ink outlines, hard two-tone cel shadows and flat painted background bands. Medium shot at eye level, gentle wide-angle perspective. Krishna kneels in the left third, full figure about half the frame height, low in the frame, facing screen-right. Blue skin, yellow dhoti, peacock feather in his hair; calm, resolved eyes looking across the river, right hand resting on his knee, flute tucked in his sash. Green river bank with tall reeds; the slow dark Yamuna in the right two thirds; far bank as a pale flat band. Soft morning sun from screen-left, warm rim on his shoulder; palette morning gold and river teal. Same wet hem as the previous shot. Vertical 9:16 frame. Faces stay in the upper two thirds. No text, no logo, no extra people, no halo.

(about 105 words)

**B (edit of A, chip = SHOT-012-A final):**
> Same picture, same framing, same light, same background. Change only: 1) Krishna now stands upright in the same spot, still facing screen-right, full figure about three-quarters of the frame height. 2) His right hand lifts the flute to chest height. 3) The reeds beside him bend slightly to the right in the wind.

**Empty plate (PLATE-yamuna-bank-morning):**
> Flat cel animation background painting with clean ink outlines and flat colour bands, no characters. Vertical 9:16 frame, eye-level wide view of a green river bank with tall reeds in the lower third, the slow dark Yamuna across the middle, the far bank as a pale flat band and a high pale sky. A kadamba tree on the left edge. Soft morning sun from screen-left. Palette morning gold and river teal. Leave the lower middle open for a figure. No people, no animals, no text, no logo.

---

## 5. Video prompt changes (MiniMax H3 FL2VA through our compiler)

### 5.1 Template (the body = `integrated_multimodal_description`, one line, no blank lines)
Order as compiled by `_fl2va` (kept), with new content rules:
1. `[Shot 1] <style prefix>, preserving the exact character design, color palette, lighting, and environment in Picture 1 and Picture 2.` (code; unchanged)
2. **Stages 1-5, time-anchored**: each stage sentence starts with a **single time point**, "At second 0," / "At second 2.5," / "By second 6,". Never a range (TG-01). Each stage has ONE subject verb plus ONE physical reaction (cloth, water, dust, hair). Anticipation stages must precede the primary action. Holds name their stillness: "<name> does not move."
3. Cadence clause (code)
4. **Camera sentence**: exactly one move from the §6.2 vocabulary plus its motivation, or "The camera stays locked." Shake only as "a short shake at second N" when `camera.shake` is set.
5. Cast line (code): "Only X and Y appear in this shot; no extra figures or creatures appear."
6. Mouth sentence (D2, code)
7. Stages 6-7 (tail, deduped)

`overall_soundscape` (D1 = B): "Sound effects only: <bed>. First <cue>; then <cue>; finally <cue>." at most 4 sentences, cues in t order. `non_diegetic_music: N/A`.

What not to repeat from the images: costume, colours, faces, background objects already visible. Exception: a prop that must keep its shape gets ≤ 6 words ("the flute stays one straight piece").

Length: body 900-2600 chars; motion words 120-300 (PR-05 / PR-09). Why: the creators' motion text is about 200 words for 15 s with no end frame (MEASURED, other model). Our A/B bounds the motion, so the lower end suffices for 4.5-7 s shots and the upper end for 10-14 s shots. Unproven on H3 (E1).

Fit with linter: no quotes (TX-01), no chips, no `->` arrows, no `[shot:` tags, no ranges, ASCII soundscape, no blank line. Every example below follows that.

### 5.2 Worked examples (body text after the fixed prefix; soundscape line given separately)

**(1) Slow scale reveal, 12.0 s, route S or SE with a near-identical B, `camera.move = pull_back`:**
> At second 0, the great serpent Kaliya lies coiled in the black water, completely still, only mist sliding over its hoods. At second 3, its seven nearest hoods rise one after another, water sheeting off each hood in thin curtains. At second 6, the central hood turns slowly toward the tiny figure of Krishna on the bank; the turn takes two full seconds. At second 9, ripples run outward in wide rings and the reeds on the bank lean away. Slow holds between the movements. The camera pulls back slowly to reveal the full height of the serpent against the pale sky, because the audience must feel its size. Only Kaliya and Krishna appear in this shot; no extra figures or creatures appear. Krishna keeps their lips completely closed. By second 11, the serpent holds still, hoods spread, eyes on Krishna, who does not move.
>
> soundscape: Sound effects only: low river wind. First water pours off the hoods; then a deep rumble rises from the water; finally the reeds hiss in the wind.

**(2) Character action with lip movement, 6.6 s, two people, Yashoda speaks (voice slot 1.2-3.8 s):**
> At second 0, Yashoda stands in the centre facing screen-left, hand on her pallu, brows drawn together. At second 1, she steps half a pace toward Krishna, her sari hem swinging and settling a beat late. At second 1.2, she speaks with moving lips while pointing at the broken pot; her lips stop moving by second 3.8. At second 4, Krishna lowers his eyes and his shoulders drop. Expression first, then the body. The camera stays locked, because the argument is between the two of them. Only Yashoda and Krishna appear in this shot; no extra figures or creatures appear. Yashoda speaks with moving lips; Krishna keeps their lips completely closed. By second 6, Yashoda holds her pointing hand still and Krishna looks up at her.
>
> soundscape: Sound effects only: quiet courtyard. First a footstep on packed earth; then the clay shards click under her foot.

Risk: H3 lip motion is untested (MOUTH research A8). Canary E5.

**(3) Continuous chain, second clip, 8.0 s, Picture 1 = last kept frame of SHOT-013 (no B, route S):**
> CURRENT CHARACTER STATE: Krishna is mid-leap above the river, body arched forward, yellow dhoti trailing behind him, both arms reaching down toward the water, facing screen-right. Continue directly from this exact frame with no reset of pose, light or framing and no cut. At second 0, his arc continues downward at the same speed. At second 1.5, his hands break the surface and a white sheet of water rises in a crown. At second 3, his body disappears under the water and the crown falls back in heavy drops. At second 5, rings spread across the dark water. The camera tilts down to follow his fall, because the dive leads the eye into the river. Only Krishna appears in this shot; no extra figures or creatures appear. Krishna keeps their lips completely closed. By second 7, the water calms into slow rings.
>
> soundscape: Sound effects only: river wind. First a deep splash; then heavy drops fall back; finally the water laps the bank.

**(4) Crowd / army, 7.3 s, kind `crowd`, `camera.move = push_in`:**
> At second 0, a dense crowd of Braj villagers fills the river bank, the nearest row clearly drawn, the rest fading into soft painted depth. At second 2, the front row raises their hands toward the river together, cloth sleeves sliding down their arms. At second 4, a ripple of movement passes back through the crowd as people lean forward; the back rows stay simple shapes. The camera pushes in slowly toward the front row, because their hope is the subject. Only the villagers appear in this shot; no extra figures or creatures appear. The villagers keep their lips completely closed. By second 7, the crowd holds still, hands raised.
>
> soundscape: Sound effects only: open river air. First many feet shift on the dry grass; then a low murmur of cloth and breath.

No counts. The front row is the only articulated layer.

**(5) Close-up emotional, 5.9 s, `framing = close`, `lens = tele`:**
> At second 0, close on Devaki's face in the centre, eyes lowered, a tear held on her lower lid. At second 1.5, her breath catches and her shoulders rise slightly. At second 3, she lifts her eyes toward the light from screen-left; the tear runs down her cheek. Expression first; the body barely moves. The camera stays locked, because her face carries the moment. Only Devaki appears in this shot; no extra figures or creatures appear. Devaki keeps their lips completely closed. By second 5, she holds her gaze, the tear line catching the light.
>
> soundscape: Sound effects only: a dim stone room. First a soft breath catches; then a lamp flame flutters.

---

## 6. Shot planning and camera planning

### 6.1 Story to shots
- **Reel length**: owner decision. RECOMMENDED target 30-45 s per narrated reel (batch 1 median 30.1 s); story chunks are split into more reels, not longer ones. Keep 60-75 s as an allowed upper class.
- **Premise + 4-beat arc per reel**: premise line (character, goal, obstacle, stakes, payoff), then Hook (0-2 s), Setup, Escalation, Payoff (last 5 s; P2 rule exists). The writer brief adds a `premise` field and an `arc_beat` per shot.
- **Shots vs beats**: one shot = one primary action (exists). Within-shot sub-beats (2-4 per shot, each ≥ 1.5 s) carry anticipation and hold. Shot lengths vary: at least 1 shot ≤ 4.4 s (trimmed impact) and **one centrepiece ≥ 10 s** per reel ≥ 25 s. No two consecutive shots within ±0.5 s of each other's length (anti-metronome lint, P5 NEW).
- **Cut vs hold**: cut on a new piece of information or an impact. Hold while one subject keeps changing (anticipation to action to settle). Prefer one long take over two cuts when the subject and place are the same.
- **Hook patterns (`hook_type`)**: `kinetic` (motion or impact before 2.0 s), `scale_tableau` (frame 0 shows extreme scale contrast; DZrSotPhi2v, DZwJE4_hMuG, De5vZ9QhJBm), `voice_call` (one named call before 2.0 s; DfRx1nLhxH9). `none` is refused for shot 1.
- **Narration**: keep 3-language voice (product). RECOMMENDED: voice-free windows of 2-4 s around the climax impact (score plus SFX carry it), as a writer option `voice_rest:[t0,t1]`. Experiment E6 checks retention against a fully narrated cut.

### 6.2 Camera vocabulary (enum to prompt phrase)
| `camera.move` | Prompt phrase | Use for | Rule |
|---|---|---|---|
| null (`mode: fixed`) | "The camera stays locked" | dialogue, close-ups, most shots | default |
| push_in | "The camera pushes in slowly toward <target>" | pressure, realisation | subject mostly planted |
| pull_back | "The camera pulls back slowly to reveal <what>" | scale, isolation | foreground anchor |
| pan_left/right | "The camera pans slowly to the left/right to <target>" | follow gaze, link two subjects | ≤ 60° |
| tilt_up/down | "The camera tilts up from <a> to <b>" | human to deity, height | along a leading line |
| track_left/right | "The camera tracks beside <name> as <pronoun> walks" | travel | subject pace ≤ walk |
| orbit_left/right | "The camera circles slowly around <name>, who stays still" | divine presence, monument | **all cast moving = false** (L12) |
| crane_up/down | "The camera rises slowly above <scene>" | ending, overview | — |
| handheld_drift | "The camera drifts very slightly, as if held by hand" | tension, POV | no other move |
| `shake: {t, dur ≤ 1.5}` | "a short shake at second N" | impact only | kind body_action; once per shot |

**Angle and lens by emotion** (writer default, overridable): awe/scale → low or ground angle, wide; dread → high angle, wide, negative space; intimacy/grief → eye level, close, tele; resolve/triumph → low angle, medium; calm/devotion → eye level, centred, normal.

### 6.3 New and changed blocking/1 fields (all additive and optional for compatibility; becomes blocking/1.1)
| Field | Type | Allowed | Default | Writer/code | Lint | Example |
|---|---|---|---|---|---|---|
| `camera.move` | str or null | enum §6.2 (today free str) | null | writer | BLK-S06: enum; L11: `mode=fixed` ⇔ move null | "pull_back" |
| `camera.angle` | str | eye_level, low, high, ground, overhead | eye_level | writer | BLK-S06 | "low" |
| `camera.lens` | str | wide, normal, tele | normal | writer | BLK-S06 | "wide" |
| `camera.motivation` | str | ≥ 3 words | — | writer | L11: required when move not null | "audience must feel its size" |
| `camera.shake` | obj or null | {t: num, dur: 0.3-1.5} | null | writer | L13: t+dur ≤ seconds; kind in body_action, seam | {"t":4.1,"dur":1.0} |
| `composition` | str | thirds_left, thirds_right, centred, negative_space, foreground_frame, leading_lines | centred | writer | BLK-S20 | "thirds_left" |
| `beats` | list | [{t: num, label: 1-3 UPPER words, action: str, physics: str, primary: bool}] | — | writer | L14: 2-4 beats, ascending t from 0, gaps ≥ 1.5 s, exactly one primary, t < seconds | see JSON |
| `cast[].hold` | bool | | false | writer | L12: orbit needs all hold or not moving; compile emits "<name> does not move." | true |
| `cast[].expression` | str | from the bible expression list | "neutral" | writer | BLK-S16 | "resolve" |
| `cast[].pace` | str | walk, slow, **fast** (new, warn) | walk | writer | L03 per pace | "slow" |
| `hook_type` | str | kinetic, scale_tableau, voice_call | — | writer | required on shot 1 (L16) | "scale_tableau" |
| `route` | str | SE, S, SE_MID, REF | SE | code (router) from kind, chain_from | S needs SHOT_MODE_S_ALLOW | "S" |
| `chain_from` | str or null | previous SHOT id | null | writer | L17: previous `cut_to_next` == "match"; depth ≤ 2 | "SHOT-013" |
| `sound_cues[].kind` | str | hit, bed | hit | writer | SX-02 | "hit" |
| `voice_rest` | [t0,t1] or null | inside shot | null | writer | no voice line overlaps | [3.0,6.0] |
| `caption_safe` | bool | | computed | code | L15: speaking/close cast y_face ≤ 0.62 | true |
| `emotion` | str | awe, dread, intimacy, grief, resolve, triumph, calm | — | writer | picks angle/lens defaults | "awe" |

Full example sheet:
```json
{"schema": "blocking/1.1", "shot_id": "SHOT-012", "plate_id": "PLATE-yamuna-bank-morning", "location_id": "LOC-yamuna-bank",
 "kind": "acting", "emotion": "resolve", "composition": "thirds_left", "route": "SE",
 "camera": {"mode": "fixed", "framing": "medium", "move": null, "angle": "eye_level", "lens": "normal",
            "motivation": null, "shake": null},
 "light": {"key_dir": "left", "palette_id": "PAL-morning"},
 "props": [{"id": "P1", "class": "flute", "x": 0.30, "y": 0.62, "visible": ["A", "B"]}],
 "entries": [], "exits": [],
 "sound_cues": [{"t": 1.6, "text": "cloth rustle", "kind": "hit"}, {"t": 0.0, "text": "river wind", "kind": "bed"}],
 "beats": [{"t": 0.0, "label": "STILL", "action": "Krishna kneels, eyes on the river", "physics": "reeds sway", "primary": false},
           {"t": 1.6, "label": "RISE", "action": "Krishna stands up in one smooth push", "physics": "dhoti hem swings and settles", "primary": true},
           {"t": 4.0, "label": "HOLD", "action": "Krishna lifts the flute to chest height", "physics": "wind lifts the peacock feather", "primary": false}],
 "arc_sec": 2.4, "writer_seconds": 5.9, "cut_to_next": "cut", "chain_from": null, "voice_rest": null,
 "hook_type": null, "source_refs": ["L41"],
 "cast": [{"id": "CHAR-KRISHNA", "name": "Krishna", "speaks": false, "arms": 2, "pace": "slow", "hold": false,
           "expression": "resolve", "source_refs": ["L41"],
           "start": {"x": 0.30, "y": 0.70, "scale": 0.50, "facing": "right", "pose": "kneeling", "mouth_moves": false},
           "end":   {"x": 0.30, "y": 0.66, "scale": 0.72, "facing": "right", "pose": "standing", "mouth_moves": false}}]}
```
Diff against today's blocking/1:
- `+emotion +composition +route +beats +chain_from +voice_rest +hook_type`
- `camera: +angle +lens +motivation +shake; move becomes an enum`
- `cast[]: +hold +expression; pace +fast`
- `sound_cues[]: +kind`
- computed `caption_safe`

Also:
- The MASTER_PROMPT (c2) example has `"arms": "down"`, which BLK-S16 rejects (must be int ≥ 2). **Fix the brief example.**
- Rich shot `beats` move to blocking (rule 57, single source). The rich shot keeps purpose, dialogue and layers.

---

## 7. Consistency strategy
1. **Reference bible** (§4.3) accepted before keyframes. A per-scene continuity sheet is generated from blocking.
2. **A/B discipline**: B is a new generation chipped on A final, ≤ 3 listed changes, same framing/light/side. The keyframe gate compares A vs B: background SSIM (masked outside cast boxes) ≥ 0.80, palette ΔE2000 ≤ 6 (core g1), cast count equal.
3. **Last-frame chaining**: the trimmed last kept frame of clip N becomes A of N+1, depth ≤ 2, then re-anchor. Gate: frame-0 of N+1 vs that PNG, SSIM ≥ 0.90.
4. **Identity gates per clip**:
   - face embedding cosine vs the CHAR master ≥ 0.88 (existing min_cosine) on frames 0, middle, last
   - within-clip hist corr warn < 0.60 / fail < 0.40
   - SSIM_1s warn < 0.20
   - NEW_CLASS after frame 12 (exists)
   - TAIL_SNAP trim (exists)
   - end_frame_pass for SE only
5. **Palette / line locks**: style pack palette ids only (v2.3). Gate g1 ΔE2000 ≤ 6 vs the plate. g3 cut jump ΔE ≤ 8 between neighbours. Line weight: the STYLE chip is attached to every A job.
6. **Settings lock**: `build_h3_batch.add_settings_sha` hashes {Wan2GP pin bd1ff59, profile file sha, steps, cfg, sampler, seed, resolution, prompt sha, A/B sha}. A re-render with any hash change is a new `render_version`. The seed is fixed per shot (store it), and changes only in iteration pass 5.
7. **When a clip drifts (one variable per pass, log each)**:
   1. simplify action (one primary, add holds/"does not move")
   2. remove camera move
   3. move B closer to A
   4. split the shot (two shots or chain)
   5. new seed
   6. route change (SE to S)

   Stop after 3 renders of one shot and escalate to the owner. Each render is about 0.6 units (INFERRED).

---

## 8. Per-section before/after examples
| Section | Before | After | Fields touched |
|---|---|---|---|
| Script | 72.8 s, 10 even shots, narration everywhere | 32 s: premise line; hook_type scale_tableau; shots 3.5 / 6.6 / 12.0 / 4.5 / 5.2 s; voice_rest 2-3 s at the climax | story.json reel_target_s; shot arc_beat, hook_type, voice_rest |
| Voice | lines voiced, captions from shots.json text | voice_manifest.<lang>.json binds text→wav sha; first word 0.3-1.0 s | voice_manifest rows; audio_edge lead-in |
| Timeline | snap on beat by default | snap false by default; edit_frames may be < pixel_frames down to 2.5 s | acts.json snap; lock edit_frames |
| Blocking | camera.move free text "slow push" | `move:"push_in", motivation:"pressure on Daksha", lens:"tele"` + beats | §6.3 |
| Keyframes | A prompt "same set, add: Krishna at (0.5,0.6), scale 0.5, facing right, pose kneeling" | §4.4 sentence form; B "Same picture... Change only: 1) 2) 3)" | keyframe_jobs._prompt_from_cast, change_list |
| Video | "Sati lifts the veil, with a veil snaps" ×7 + double mouth sentence | time-pointed stages, one camera sentence, per-person mouth sentence, cues in soundscape | v4_to_h3 _stages/_soundscape, compile _mouth_lock, linter SX/MO |
| QA | flicker 0.1 only | + hist corr warn .60 / fail .40, SSIM_1s warn .20, frame-0 chain check | clip_qa |
| Assembly | captions band in core 0.50-0.65 vs pos 67 % | one source: band [0.62, 0.74], clean master exported | core.json, build_final_reel |
| Sound/Ableton | no cue sheet of impacts | cue sheet rows {shot, t_frame, kind hit/bed/rest, source cue text, voice_rest}; hits on the impact frame ±1 f; 2 s riser before the primary beat; no silence > 0.3 s | cue_sheet (W-05) + score skill |

---

## 9. Checklist (implementation order)
Owner key: [OD] owner decision, [CODE] module, [EXP] experiment, [$] paid canary (Colab/ElevenLabs go needed).

- [ ] 1. [OD] Approve D1=B, D2 wording (MO-01 change), D4=(a). Files: OWNER_DECISIONS, blot rule 58 append. Risk: low. Dep: none.
- [ ] 2. [CODE] W-07 finish: v4_to_h3:164, linter SX_MIN 0 + SX-02, duplicate guard, mouth_sentence + MO-01, blocking.load_reel. Tests §2a. Risk: high (≈40 h3 test files). Dep: 1.
- [ ] 3. [OD] Caption margins split (§2b) + Amendment D text. Dep: none.
- [ ] 4. [CODE] core.json caption/safe-zone keys; build_final_reel reads them; clean master export; e2e voice manifest test. Tests §2b. Risk: med. Dep: 3.
- [ ] 5. [CODE] script_pacing re-hook from core fraction; length window from story.json. Test `test_rehook_uses_core_fraction`, `test_length_window_from_story`. Risk: low.
- [ ] 6. [CODE] script_hook HOOK_WINDOW_S 2.0 + hook_type exemption. Test `test_scale_tableau_exempt`. Risk: low. [OD] on 2.0.
- [ ] 7. [CODE] blocking/1.1 additive fields + BLK-S06/S20 enums + L11-L17 (+ L15 caption-safe). Tests one per code, plus `test_blocking_1_0_sheets_still_load`. Risk: med. Dep: 1.
- [ ] 8. [CODE] MASTER_PROMPT v2.4: c2 example fix (`arms` int), new fields, premise + arc, camera vocab table, beats moved to blocking. Test: brief example sheet passes `blocking.validate`. Risk: low. Dep: 7.
- [ ] 9. [CODE] keyframe_jobs: sentence-form A prompt (§4.1 mapping), B text "Same picture...", method renamed to `generate_with_chip`. Tests `test_a_prompt_has_no_digits_coords`, `test_b_max_3_changes`. Risk: low.
- [ ] 10. [CODE] compile: time-point stage prefixes from `beats[].t` / stage_frame_spans; camera sentence from the enum; "does not move" from hold. Tests `test_stage_time_points_pass_tg01`, `test_one_camera_sentence`. Risk: med. Dep: 2, 7.
- [ ] 11. [CODE] Blocking-lint knobs (§3) **behind the canary**: change constants and log old-test changes (rule 58(5)). Risk: med. Dep: E4.
- [ ] 12. [CODE] clip_qa: hist-corr and SSIM_1s warns, chain frame-0 check. Tests on synthetic clips. Risk: low.
- [ ] 13. [CODE] gate_d NO_SILENCE check. Test with a 0.5 s digital-silence WAV. Risk: low.
- [ ] 14. [CODE] timeline lock: snap default false; edit_frames < pixel_frames down to 60 frames. Test `test_trimmed_short_shot`. Risk: med (F-03 lattice).
- [ ] 15. [CODE] chain step: extract the last kept frame after trim to `<pack>/chain/<SHOT>-last.png`; refuse depth > 2. Test with an ffmpeg testsrc. Risk: low.
- [ ] 16. [EXP] Animatic gate (NEW): A/B stills + the voice lock + guide track → 24 fps MP4 per language, owner watches before any Colab go. Tool: ffmpeg concat + build_vo_tracks. Risk: low. Missing from both guides as code.
- [ ] 17. [EXP][$] Canaries E1-E5 (§10), one G4 session, ≤ 6 clips.
- [ ] 18. [CODE] PR-05 900/2600 + PR-09, **only if E1 passes**. Dep: E1.
- [ ] 19. [OD] Reel length target for reel 2; narrated benchmark set: collect 10 narrated mythology reels and run measure_reels (free).
- [ ] 20. [CODE] Ableton cue sheet fields (§8) in W-05's cue_sheet. Test field presence. Dep: W-05.
- [ ] 21. [CODE] Text-card QA: any caption or title card frame passes a conjunct OCR check (Devanagari) and sits inside the text-safe box. Dep: 4.
- [ ] 22. [CODE] Three-language length check: per shot, max over en/hi/mr voice seconds ≤ edit seconds at MAX_TEMPO 1.0 (else the writer shortens). Exists partly in the lock; add a test with a long hi line.

---

## 10. Experiments (cheapest first) and risks

| # | Experiment | Cost | Pass / fail |
|---|---|---|---|
| E0 | Narrated benchmark: 10 narrated Indian-mythology reels through measure_reels (length, cuts, LUFS, LRA, speech share) | free | gives our real length/cut targets. Fail = fewer than 6 usable reels. |
| E0b | Re-measure batch 2 inside the video sub-window (crop to the video box) for cuts and camera | free | sub-window cuts match OCR/MODEL counts ±1 on ≥ 6 of 8 reels |
| E1 | Same SE shot (A, B, seed fixed), prompt current (~110 motion words, untimed) vs time-pointed 220 words | $ 2 clips | pass if blind owner preference for the long prompt AND within-clip hist corr ≥ 0.60 AND no new TAIL_SNAP; fail = no visible difference (then keep 600-4000) |
| E2 | Two-clip chain from the last kept frame + CURRENT CHARACTER STATE | $ 2 clips | seam frame SSIM ≥ 0.90; hist corr across the seam ≥ 0.60; owner sees no reset |
| E3 | Route S vs SE on a scale-reveal shot | $ 2 clips | S clip keeps identity (face cosine ≥ 0.88 at the last frame) and has no tail snap |
| E4 | Speed/turn: one walk at 0.35 and one at 0.5 fh/s, one 180° turn in 3 s | $ 2-3 clips (can share E1 session) | 0.35 clean and 0.5 smeared, which confirms the caps; both clean → keep 0.5 |
| E5 | Lip movement: two-person shot, one speaker with D2 sentence | $ 1 clip | speaker's mouth moves only inside the slot ±0.3 s; silent person closed |
| E6 | Retention proxy: reel 2 cut A (full narration) vs B (voice_rest at climax) shown to the owner | free after render | owner choice |

**Risks**
- R1: H3 may ignore time points (E1 fail). Then keep the stage structure and its value is ordering only.
- R2: Longer prompts raise morph risk on short shots. Keep 900-char minimum only for ≥ 7 s shots if E1 shows harm on 4.5 s.
- R3: Last-frame chaining carries artefacts forward (depth ≤ 2 mitigates).
- R4: Caption decision (§2b) overrides an owner-stated 35 % margin. Owner must confirm.
- R5: Blocking knobs remain uncalibrated until E4. Don't tighten before it, because frozen tests would change for nothing.
- R6: The W-07 regex coupling breaks many h3 tests. Run the full h3 suite.
- R7: Thin evidence everywhere on pose/turn/movers (no estimator ran). Treat those numbers as starting points.
- R8: The sample bias (Seedance spectacle reels, 15 s tool windows) is the largest single uncertainty in every "proven" number.
