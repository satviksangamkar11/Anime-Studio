# Opus final review: crack register, new cracks, Reel 2 start (2026-11-12)

Read-only review by Opus (owner-ordered, internet on). No code was edited and nothing was run on Colab, ElevenLabs or Flow. This file is the only output.
Labels:
- **VERIFIED** = read on the page or in the local file named.
- **INFERRED** = my reasoning, or a search snippet whose page did not render.
- **UNKNOWN** = not found.

All web pages were accessed on 2026-11-12. Code references are `file:symbol` in `D:\aai work\anime_studio_merge`. The Wan2GP pin is the local copy `D:\aai work\kaggle_h3_test\wan2gp_src` (bd1ff59).

Sources used (short ids):

| id | Source | Status |
|---|---|---|
| U1 | https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md | VERIFIED (fetched) |
| U2 | https://platform.minimax.io/docs/guides/video-generation | VERIFIED (fetched) |
| U3 | Wan2GP pin bd1ff59: `models/minimax_h3/minimax_h3_handler.py` lines 73-131 and 291-306, `prompt_enhancer.py` (FL2VA_PROMPT_INFOS, FL2VA_IMAGE_SYSTEM_PROMPT), `shared/deepy/settings/gen_video/Pika H3 Flex FL2VA Pruned 6 Steps.json` (upstream: https://github.com/deepbeepmeep/Wan2GP/tree/bd1ff59) | VERIFIED (local read) |
| U4 | https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana (published 2026-03-06) | VERIFIED |
| U5 | https://blog.google/products/gemini/prompting-tips-nano-banana-pro/ | INFERRED (search snippet only) |
| U6 | https://elevenlabs.io/docs/overview/models | VERIFIED |
| U7 | https://elevenlabs.io/docs/api-reference/text-to-speech/convert | VERIFIED |
| U8 | https://elevenlabs.io/docs/best-practices/prompting/controls | VERIFIED |
| U9 | local `ffmpeg 8.1.1 -h filter=silencedetect` | VERIFIED |
| U10 | https://tech.ebu.ch/docs/tech/tech3341.pdf (EBU R128 gating) | INFERRED (search summary; the -70 LUFS gate is widely cited) |
| U11 | Netflix SilenceInspector pages (https://partnerhelp.netflixstudios.com/hc/en-us/articles/216754737, .../216194858) | INFERRED (the pages need JavaScript and did not render; figures come from the search snippet) |
| U12 | https://en.wikipedia.org/wiki/Dead_air | INFERRED (search snippet) |
| U13 | https://support.google.com/youtube/answer/2734698 (YouTube subtitle formats) | VERIFIED |
| U14 | https://partnerhelp.netflixstudios.com/hc/en-us/articles/215600497 (Netflix pt-BR timed-text guide: 42 characters per line, 2 lines) | VERIFIED for pt-BR only |

---

## 0. The ten findings that matter most

1. **The silence check measures the wrong audio.** `director/build_final_reel.py:main` calls `master_audio_check(video, ...)` on `<reel>_video.mp4` before any voice or music is mixed. That file is the concatenated H3 clip audio. The per-language export, which is the real master (Ableton mix or ffmpeg mux), is never silence-checked. Section E fixes this.
2. **The S prompt uses the FL2VA alignment line.** `h3/compile_h3_sing8.py:_fl2va(start_only=True)` writes "How the reference pictures align ... Picture 1 ... aligns with the 0.00-second mark". The official first-frame line is different: "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced." (U1 and U3, VERIFIED). S is now the default route, so fix this before the first S clip.
3. **Route S has no identity gate.** `director/clip_qa.py:features` computes "cosine" as a raw-pixel cosine against keyframe B, and route S skips it (`_end_result`). Nothing checks face identity at all: the change plan's C-04 (face embedding ≥ 0.88) was never built. Identity drift is the one known open risk of start-only (Luna P3, INFERRED). Today only hist-corr (palette) watches it.
4. **The Pika preset recommends 124-362 frames; our lattice allows 107.** U3 (VERIFIED): "Start at 480p/768p and 124–362 frames at 24 fps." `h3/shot_table_spec.py:LATTICE_N_MIN = 6` gives 107 frames. Reel 1 never rendered below 158. Make 124 (n = 7) the floor for route pika6. The 80-frame trimmed edit still fits.
5. **ElevenLabs gets no `language_code`, and Hindi and Marathi share Devanagari.** `director/voice_cast.py:run` posts only text, model_id and voice_settings. The API's `language_code` "enforce[s] a language for the model and text normalization" (U7, VERIFIED). It works for v3/v4 but not multilingual_v2. Marathi exists only on the v3/v4 family (U6, VERIFIED). Without the code, Marathi lines may be read with Hindi rules (INFERRED).
6. **`voice_rest` has two clocks.** `director/story_shape.py` reads it as reel seconds. `score/cue_sheet.py:_rest_window` and `director/blocking.py` (BLK-S21) read it as shot seconds. The silence exemption and the Ableton rest rows would land in different places.
7. **The Ableton handoff has no cue rows.** `score/cue_sheet.py:cue_rows` (M-15) has no caller outside tests, so `cue_sheet.json` does not contain the rows. The cue sheet also takes sound cues from pack `per_second_directives`, not from blocking `sound_cues` (rule 57 single source).
8. **blot.md still says the opposite of today's decisions.** M-22 was stopped, so nothing from 11-12 was appended. Three rules now contradict the code:
   - Rule 27: "SX-01: all 7 action sentences ... carry a sound word" (now D1 = B).
   - Rule 52(5): "S ... only after the owner-approved SHOT-008 A/B test" (now the S default).
   - Rule 54(12): "start-only mode S stays off" (now the S default).

   Every agent reads blot first, so an agent can "fix" the code back.
9. **There are two SRT writers, and the YouTube upload has no clean video.**
   - `build_final_reel` writes `captions/<reel>.<lang>.srt`. Timing is correct (voice report plus lock offsets), but the file is unversioned and is written before the export exists.
   - `post.py` writes a second SRT from writer time ranges.
   - M-10 (clean no-caption master) was cancelled with HOLD-3. A YouTube upload of the burned video plus an SRT shows captions twice when CC is on.
10. **Post-fetch QA fails open.** `run_colab_batch.main` without `--qa-plan` prints "POST-FETCH QA NOT RUN" and returns 0 after a paid render.

---

## A. Crack register (my earlier review + the change plan, verified against the code)

Verdict key:
- **DONE** = built and solves the crack.
- **DONE-weak** = built, but does not fully solve it.
- **PARTIAL**, **NOT BUILT**, **HELD**, **CANCELLED** (owner).

| id | Crack | Solution given | Built where (verified) | Verdict |
|---|---|---|---|---|
| G-01..G-09 | Wrong numbers and attributions in the two guides | Record the corrections in docs | Nothing in blot.md/HANDOFF (M-22 stopped) | NOT BUILT (docs only; low risk because no code uses them) |
| S-01 | core.json caption band vs rule 51 | Split text-safe and subject-safe | M-10 cancelled; core.json still has `caption_band [0.50,0.65]` | CANCELLED (owner). Residual: core.json still contradicts rule 51. Nothing in the reel path reads it except `post.py --platform`, so mark it "not used by build_final_reel" (G item 20) |
| S-02/T-01 | Re-hook fixed at 25-35 s | Core fraction [0.45, 0.60] | `script_pacing.py`, `pack_validator.py:REHOOK_WINDOW_FRAC`, `writer_prompts.py` (M-07, M-25) | DONE |
| S-03/T-02 | Fixed 60-75 s length | Per-story `reel_target_s` | `script_pacing.py`, `story_shape.py` | DONE |
| S-04/I-01..03 | A prompt from raw coordinates | 8 plain sentences, words mapping, ≤ 110 words | `keyframe_jobs.py` (M-06) | DONE-weak. Continuity, space and palette sentences have no input (M-06 note 4). `EXCLUSION` is a fixed negative sentence, while Google says "Describe what you want, not what you don't want" (U4, VERIFIED) |
| S-05/T-12 | MO-01 fixed phrase | Per-person mouth sentence | `h3/prompt_hygiene.py:mouth_sentence`, `compile_h3_sing8.py:_mouth_sentence`, linter MO-01 | DONE |
| S-06 | Brief example `arms:"down"` | Fix the example | `director/MASTER_PROMPT_v2.4.md` (M-05) | DONE. v2.4 is not the default: `write_pack --prompt-version` default stays v2.3, so Reel 2 must pass `v2.4` explicitly |
| S-07/D-01 | Cue glue ", with" | Cues to soundscape, SX-02, guards | `schema_and_linter.py:SX_MIN_STAGE_CUES = 0`, SX-02; 0 hits of `", with "` in `v4_to_h3.py`; `compile_fl2va_prompt` raises on glue and duplicates | DONE |
| S-08 | hi/mr longer than en | max(en, hi, mr) ≤ edit seconds | BLK-S13 in `blocking.py` (M-16) | DONE (mr path untested, M-16 note) |
| S-09 | No narrated benchmark | E0 | HOLD-4 (reel-analysis system frozen) | HELD |
| D-02 | Caption split / Amendment D | — | — | CANCELLED (owner 12:40) |
| D-03 | Soft end W-10 | Hard end (D4 = a) | `build_h3_batch.legacy_rows` refuses strength ≠ 1.0 | DONE (and S makes it moot) |
| D-04 | Reel length | Not fixed | — | WITHDRAWN (owner) |
| D-05 | Voice-free climax windows | `voice_rest` field | blocking 1.1, `story_shape` SHAPE-10, `cue_sheet` | DONE-weak: two clocks (finding 6) |
| D-06/T-03 | Hook window | 2.0 s, scale_tableau exempt, first word 0.3-1.0 s | `script_hook.py:HOOK_WINDOW_S = 2.0`, `VOICE_START_MIN_S/MAX_S` | DONE |
| D-07 | Route S | Build S; default S (owner 11:40) | `h3/shot_mode.py:s_allowed` (on unless `=0`), `build_h3_batch.legacy_rows` default "S", `compile_fl2va_prompt(start_only)` | DONE-weak: wrong alignment line (finding 2); no identity gate (finding 3) |
| T-04 | Beat snap default | snap false | Lock (M-12) | DONE |
| T-05 | 2.5 s edits | 60-frame edits | MO-03 blocks them; 80-frame floor; strict xfail kept | DONE as decided (owner: 80 frames) |
| T-06 | No silence rule | NO_SILENCE 0.3 s / -50 dBFS fail | `h3/gate_d_audio.py:check_no_silence`, called by `build_final_reel.master_audio_check` | DONE-weak. Wrong signal (finding 1) and rule too strict for intentional quiet. Redesign in section E |
| T-07 | QA metrics | hist corr warn 0.60 / fail 0.40, SSIM_1s warn 0.20, chain 0.90 | `clip_qa.py:HIST_WARN/HIST_FAIL/SSIM_1S_WARN/CHAIN_SSIM_MIN` | DONE |
| T-08 | End check for S | Skip for S | `clip_qa._end_result` | DONE |
| T-09 | Blocking knobs | After E4 | `blocking_lint.py` constants unchanged (0.5/0.25/1.0/2.0/1.0/0.05/3) | HELD (HOLD-1) |
| T-10/V-06 | Prompt length 900/2600 | After E1 | Profiles `min_imd_body_chars` 450 (interim), max 4000 | HELD. 450 is an interim number of ours; neither guide gives a length (U1, VERIFIED) |
| T-11 | core.json keys | — | — | CANCELLED |
| I-04 | B = edit of A | `generate_with_chip`, ≤ 3 changes | `keyframe_jobs.py`, `flow/scripts/build_jobs.py` (M-06b), `prop_changes` (M-30) | DONE (now only for SE overrides) |
| I-05/C-01 | Reference sheets before keyframes | Sheet jobs + continuity sheet | `bible_to_sheet_jobs.py --section-4-3` (opt-in), `continuity_sheet.py` | PARTIAL: opt-in flag and default not flipped; not wired into the UI wizard |
| I-06/V-08 | Golden fixtures | Opus examples | `h3/tests/test_opus_examples.py` (M-03) | DONE |
| V-01..V-05 | Prompt template | Time points, one camera sentence, holds, soundscape | `v4_to_h3._stages` (`SEQ_LEADS`; `time_points` false in both profiles), CM-05/06 | DONE (time points OFF by owner). Not mechanically checked: "no costume/colour/face repetition" (writing rule only) |
| V-07 | Linter fit | TX-01, TG-01, no blank line | `compile_fl2va_prompt` blank-line raise; `build_h3_batch` collapse | DONE |
| P-01/P-03/P-07 | Premise, arc, brief | story fields, v2.4 brief | `story_shape.py` SHAPE-01..10, MASTER_PROMPT v2.4 | PARTIAL: the UI/story writer does not write the new story fields yet (M-23 note) |
| P-02 | Variable lengths / centrepiece | L18/L19 + SHAPE rules | `blocking_lint.py` L18/L19, `story_shape` | DONE (double coverage by design) |
| P-04..P-06 | hook_type, camera enum, blocking 1.1 | Fields + lint L11-L17 | `blocking.py:_CAMERA_11_MOVES`, BLK-S21, `blocking_lint` L11-L17 | DONE. `cast.expression` is free string (no bible list) |
| C-02 | Keyframe gate | bg SSIM ≥ 0.80, ΔE ≤ 6, cast parity | `keyframe_gate.py` (M-24) | DONE (uncalibrated) |
| C-03 | Last-frame chaining | chain_step, depth ≤ 2, SSIM ≥ 0.90 | `director/chain_step.py:MAX_CHAIN_DEPTH = 2`, `clip_qa.chain_check` | DONE (8x8 block SSIM approximation) |
| C-04 | Identity gates per clip | Face cosine ≥ 0.88 first/mid/last | Not present. `clip_qa.features` "cosine" is a pixel cosine vs B, and is skipped for S | **NOT BUILT** (finding 3) |
| C-05 | Palette/line locks | STYLE chip on every A | `keyframe_jobs` | DONE |
| C-06 | Settings lock | render_version hashes pin/profile/settings/seed/A/B bytes | `build_h3_batch.add_settings_sha` (key bytes, S hashes A only), `shot_seed` | DONE (M-33 code present; its suite run was still running at 12:45) |
| C-07 | Drift order, 3-render stop | `render_allowed`, `DRIFT_ORDER`, history | `h3/render_controller.py`, `run_colab_batch.render_gate/record_fetched` | DONE |
| A-01 | Ableton cue rows | `cue_rows` | `score/cue_sheet.py:cue_rows` | DONE-weak: no caller writes them to `cue_sheet.json` (finding 7) |
| A-02 | Voice manifest e2e | Test | `director/test_voice_manifest_e2e.py`; `build_final_reel.spoken_cues_real` checks the hash | DONE |
| A-03 | Burn after crop; clean master | — | Burn: `DELIVERY_VF` before ASS (DONE). Clean master: cancelled with M-10 | PARTIAL (see B-05) |
| A-04 | Text-card QA | OCR conjunct check | `director/text_card_qa.py` (takes OCR output; no OCR run) | PARTIAL (no caller) |
| A-05 | Animatic gate | Tool | `tools/animatic.py` | DONE (not in any runbook step) |
| M-26/M-28/M-29 | QA wiring | post_fetch_qa, qa_plan, seed | `post_fetch_qa.py`, `qa_plan.py`, `run_colab_batch --qa-plan` | DONE-weak: fails open without `--qa-plan` (finding 10); review producer model id is an ASSUMPTION (M-29) |
| E0-E6 | Canaries | — | HOLD-4/5. E3 replaced by "owner checks the first real S clip" | HELD |
| HOLD-1..7 | — | — | as listed in the checklist | HELD except HOLD-3 (cancelled) |

---

## B. New cracks (ranked; each with the exact fix)

| # | Sev | Crack (evidence) | Exact fix (file : symbol : rule) | Test name |
|---|---|---|---|---|
| B-01 | **P0** | Silence check runs on clip audio before the mix. The real per-language master is never checked (`build_final_reel.main` lines 615-618 vs 661-682) | Replace with section E. Run it on (1) each `--mix` WAV in `intake`, and (2) each export after `correct_loudness`, decoded. Demote the pre-mix call to an info-only `CLIP_AUDIO_QUIET` warning | `test_silence_checked_on_final_export`, `test_premix_quiet_is_warning_only` |
| B-02 | **P0** | S alignment line is the FL2VA form (`compile_h3_sing8._fl2va` start_only header) | header = `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` Body start = `[Shot 1] Continue directly from <Picture 1>, preserving <style prefix>, its subject, clothes, composition, light and setting.` Keep a single newline (rule 30(2); U3 asks for a blank line, which Wan2GP's PG mode reads as a 2nd prompt) | `test_s_header_is_official_i2va_line`, `test_s_prompt_has_no_picture_2`, `test_fl2va_golden_unchanged` |
| B-03 | **P0** | blot.md rules 27, 52(5), 54(12) contradict D1 = B and the S default; no 11-12 decisions recorded | Append (never rewrite) "RULE 59: OWNER DECISIONS 2026-11-12": D1 = B; S default and SE override; time points off; captions per rule 51 (Instagram burned, YouTube SRT); silence rule per section E; MO-03 + 80 frames; reel length per story; HOLD list. Both blot copies identical (`cmp`) | `tools/test_blot_copies_identical` (exists?) + grep check "RULE 59" |
| B-04 | P1 | No identity gate for S (`clip_qa.features`, `_end_result`) | Add `identity_check(frames, char_master_crops)`. Use the free NVIDIA vision reviewer already used by M-29 to answer per sampled frame (0, mid, last kept): "same character as reference? yes/no + reason". Fail on any "no" at the last kept frame. Until a face-embedding model is chosen, record it as REVIEW, not a number. Owner eye stays mandatory on the first S clip | `test_s_route_runs_identity_check`, `test_identity_no_fails_clip` |
| B-05 | P1 | No clean video for the YouTube SRT upload: `build_final_mux_argv(burn_captions=True)` is hard-coded; M-10 cancelled | Owner decision D-1 (below). Recommended: build_final_reel writes `<reel>_<lang>_rN_clean.mp4` (same mix, no ASS) next to the burned export. No change to caption position | `test_clean_export_has_no_subtitle_filter` |
| B-06 | P1 | SRT unversioned and written before the export (`cx.write_sidecars(..., out/"captions", a.reel)`) | After `correct_loudness` succeeds, write `<export stem>.srt` (e.g. `reel2_hi_r3.srt`) next to the export; report `srt_path` + sha256. Keep plain UTF-8 without BOM and `HH:MM:SS,mmm` (U13, VERIFIED) | `test_srt_named_like_export`, `test_srt_not_written_when_export_fails` |
| B-07 | P1 | SRT cues are the 3-4-word karaoke cards (`word_cues`): fine for burned captions, choppy on YouTube | SRT mode `line`: one cue per spoken line, split at sentence ends, ≤ 42 chars per line, ≤ 2 lines, ≥ 1.0 s on screen. Use the same voice-report times; Devanagari is counted in code points. 42/2 is the Netflix pt-BR figure (U14, VERIFIED for pt-BR; INFERRED for hi/mr) | `test_srt_line_mode_max_42_chars_2_lines`, `test_srt_times_equal_voice_report` |
| B-08 | P1 | Two SRT writers (`post.py` sidecars from writer time ranges vs `build_final_reel`) | `post.py`: default `--no-sidecars` for reels and print "SRT comes from build_final_reel". Or delete the sidecar step (YAGNI) | `test_post_writes_no_sidecar_by_default` |
| B-09 | P1 | `language_code` missing; mixed models per language (`voices_cast.json _models.hi` = multilingual_v2 for 3 voices) | `voice_cast.build_jobs`: add `language_code` = lang when the model starts with `eleven_v3`/`eleven_v4` (not multilingual_v2, U7); include it in the job key. Add `seed` = int(sha256(line id)[:8], 16) (U7: best effort). Send explicit `voice_settings` {stability 0.5, similarity_boost 0.75, style 0, use_speaker_boost true} = API defaults (U7) so the key cannot drift with library defaults. Prefer one model per language (eleven_v4 for en/hi/mr, U6) unless the owner keeps a voice for its sound | `test_job_has_language_code_v4`, `test_no_language_code_for_multilingual_v2`, `test_seed_in_job_key` |
| B-10 | P1 | `voice_rest` two clocks | One rule: `voice_rest` is **shot-relative seconds** in the blocking sheet (rule 57 single source). `story_shape` SHAPE-10 converts with lock offsets; `cue_sheet` reads the blocking sheet. The silence rule exempts the converted reel window | `test_voice_rest_same_reel_window_in_story_shape_cue_sheet_silence` |
| B-11 | P1 | Ableton handoff lacks cue rows; cues read from pack, not blocking | `cue_sheet.main`: write `cue_rows(sheet)` into `cue_sheet.json["cue_rows"]` and `cue_rows.csv` (frame, timecode, kind, source, voice_rest). Take hits from blocking `sound_cues` (kind hit) when sheets exist | `test_cli_writes_cue_rows`, `test_cue_rows_from_blocking_sound_cues` |
| B-12 | P1 | Post-fetch QA fails open (`run_colab_batch.main` "POST-FETCH QA NOT RUN", rc 0) | `--go` requires `--qa-plan`, or `--no-qa I_ACCEPT` written to the history. Exit 3 when QA is not run | `test_go_without_qa_plan_refused` |
| B-13 | P1 | Lattice floor 107 < Pika's 124 (U3) | `build_h3_batch.legacy_rows`: route pika6 refuses `pixel_frames < 124` unless `--allow-107`; writer brief says the minimum render is 124 frames (5.17 s); edit ≥ 80 frames is unchanged | `test_pika6_refuses_107` |
| B-14 | P2 | Speaker shots: "X speaks with moving lips" without `<d>` text and without soundtrack mode. U3: outside Soundtrack-Kept mode, include the exact words in `<d>`. With ElevenLabs narration the model invents mouth timing | Rule: narrated lines stay off-screen voiceover (official phrase "says in an off-screen voiceover ... lips remain completely closed", U1). On-screen speaking only for short dialogue shots. Soundtrack mode (`audio_prompt_type "A"` + `audio_guide`, U3) syncs one language only, so test it once (owner decision D-4) | `test_narration_shot_uses_offscreen_lip_sentence` |
| B-15 | P2 | `scene_cut` uses SSIM to keyframe A (`clip_qa.features sim_to_a`). On S clips with a camera move or big action, similarity to A falls by design, which can flag false cuts and switch the hist check off | For route S, run `scene_cut` on frame-to-frame SSIM (lag 1), not similarity to A | `test_s_route_scene_cut_uses_neighbour_ssim` |
| B-16 | P2 | `EXCLUSION` is negative ("No text, no logo, no extra people, no halo."); Google: positive framing (U4) | Replace with "The frame shows only <cast names>, on <plate>." Keep "no text" only if the first Reel 2 A frames show lettering | `test_a_prompt_positive_cast_sentence` |
| B-17 | P2 | S keyframes still wait for the lock (rule 52(3) reason = B must be reachable) | For S shots, A keyframes may be made in parallel with the voice work (no end pose). The lock only sets the render length. Owner decision D-3 | n/a (doc) |
| B-18 | P2 | Colab CLI 9d45981 "reject unknown --gpu values"; our `--gpu G4` was proven on 11-05 only | Owner runs `colab new --help` (no session) and confirms G4 is listed; update `COLAB_CLI_REFERENCE.md` (`colab console` → `colab ssh`) | manual |
| B-19 | P2 | ElevenLabs output mp3 (`mp3_44100_128`). MP3 encoder priming can shift measured starts by a few tens of ms (INFERRED) | If the plan is Pro tier, use `wav_44100` / `pcm_44100` (U7: "requires ... Pro tier or above"). Else keep mp3 and measure from the decoded WAV (already done by `probe_seconds`) | `test_output_format_from_config` |
| B-20 | P3 | `window_levels_db` pure-Python loop (7 M samples per minute of stereo 48 kHz) | Use numpy (already a dependency) in the new silence module | perf assert < 2 s for 75 s |

Not cracks (checked, fine):
- SRT timing comes from `vo_tracks_report` + lock offsets.
- Text is NFC (`voice_manifest.nfc`, `caption_fields`).
- The voice ledger reuses accepted clips by job key (resume-safe).
- `run_colab_batch` stops the session on every path except "clips still on the VM".
- `add_settings_sha` hashes keyframe bytes.
- `correct_loudness` hits -14 LUFS / -1 dBTP.

---

## C. Open questions answered

| # | Question (source) | Answer + evidence | Settled by owner? |
|---|---|---|---|
| Q1 | S or SE default (Luna P3: keep SE) | S default stays. The pinned Wan2GP handler states FL2VA works "from text, a first frame, a last frame, or both" (U3 line 295, VERIFIED), so S through the Pika FL2VA adapter is a documented path. This closes M-02's "I2VA LoRA reuse UNVERIFIED" for the Wan2GP route. Gate: owner looks at the first S clip | YES (11:40) |
| Q2 | "At second N" time points (M-03, Luna P2) | OFF. U1 uses timestamps only for later shot cuts and connectors like "as / while / followed by / toward the end" (VERIFIED). Current `SEQ_LEADS` matches | YES |
| Q3 | Prompt length 600/450/900-2600 (M-01b, Luna P2) | Keep 450-4000 as a sanity band only. No length rule in U1 (VERIFIED); API cap 7,000 chars (U2, VERIFIED); Ref2VA enhancer aims at 350-500 words for detailed_description (U3, VERIFIED, Ref2VA only) | partly (HOLD-2 stays) |
| Q4 | Caption band (Luna P4, HOLD-3) | Not changed. Rule 51 stays | YES (12:40) |
| Q5 | Silence fail vs warn (Luna P5) | Section E: fail only on dropout / digital silence / dead air > 1 s; quiet spans warn | Owner gave the frame; design here |
| Q6 | 60-frame edits (Luna Q3, M-12 xfail) | Keep the 80-frame floor; allow 60-79 only when MO-03 passes (impact span intact and tail handle valid). With S there is no end snap, so a later card may shrink `TAIL_HANDLE` for S shots (saves render frames). Wait for the first S clips | YES (MO-03 + 80) |
| Q7 | Organic vs paid caption templates (Luna Q1) | Moot: one organic template (rule 51) | YES |
| Q8 | Tag intentional dramatic silence? (Luna Q2) | Yes: `silence_ok:[t0,t1]` on the blocking sheet, shot-relative, max 2.0 s, used only by the silence rule (E) | Recommend |
| Q9 | Drop the rich-shot copy of beats (M-05 open) | Keep both until one live v2.4 writer run passes; then drop the rich copy (rule 57) | Later |
| Q10 | Flip `--section-4-3` default (M-19) | Flip it on for Reel 2: identity master + turnaround + expressions + STYLE chip before any keyframe (C-01). Cost is Flow time only | Owner go (Flow) |
| Q11 | Review producer model id (M-29 ASSUMPTION) | Must be checked against the NVIDIA catalogue with a free call before relying on it. UNKNOWN until then | Open (free check) |
| Q12 | Wan2GP pin move (UPSTREAM 13 commits) | Do not move. The HyperFlow changes touch `pipeline.py`; diffs were truncated (UPSTREAM §5) | Recommend |
| Q13 | Opus as story writer vs rule 56(1) (Amendment C) | Owner to confirm per job. Reel 2 writer: use the free `super-vl` writer (rule 56) with `--prompt-version v2.4 --web`; Opus only on an explicit go | Open |
| Q14 | F-15 story → N reels planner | `write_pack` stage 1 already plans episodes (`story_plan.json` has 6 episodes). Reel 2 = episode 2, "Spring Cannot Move Him" | Deferred by owner; enough for Reel 2 |
| Q15 | F-20 per-language picture retime | Option A (one master timeline, dial ±6 %) built (S-01b). Nothing needed for Reel 2 | YES |
| Q16 | Key rotation, hooksPath, min-free-gb, Drive move, G3 watermark glance | Owner chores; none blocks the Reel 2 script or voice | Open (owner) |
| Q17 | chumpy wheel commit (HANDOFF §7) | Keep it vendored by absolute path with sha check (`build_h3_batch.WHEEL_SHA256`); do not commit binaries | Recommend |
| Q18 | Lip motion for H3 (rule 34 open, E5) | See B-14. For narrated reels, close the mouths and keep speech as voiceover | Owner D-4 |

---

## D. Exact instructions from the internet (and where our defaults differ)

### D1. MiniMax H3 prompt (U1 HF guide; U2 platform; U3 pinned Wan2GP help)

| Topic | Official (status) | Ours | Change |
|---|---|---|---|
| Fields | 3 fields: `integrated_multimodal_description`, `overall_soundscape`, `non_diegetic_music` (U1, U3, VERIFIED) | Same | none |
| First-frame (S) alignment | "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced." (U1, U3, VERIFIED) | FL2VA-style line | **B-02** |
| First+last (SE) alignment | "How the reference pictures align ... Picture 1 (from Shot 1) aligns with the 0.00-second mark ...; Picture 2 ... the S.SS-second mark" (U1, VERIFIED) | Same | none |
| Blank line before fields | U3 enhancer asks for one blank line (VERIFIED) | Single newline (rule 30(2): Wan2GP PG mode reads a blank line as a second prompt) | keep ours, deliberately |
| Actions in one shot | `[Shot 1]` has no timestamp; timestamps only for later cuts; connectors such as "as", "while", "followed by", "toward the end" (U1, VERIFIED) | time_points false, SEQ_LEADS | none |
| I2V body order | First-frame anchor → action onset → continuous development → result (U1, VERIFIED); example opens "Continue directly from <Picture 1>, preserving its subject, clothes, composition ..." (U3, VERIFIED) | 7 stages in that order | B-02 body opener |
| SE | "generally favors a single shot"; describe the path toward the last frame (U1, VERIFIED) | single shot | none |
| Camera | Natural English: type + amplitude + speed only when meaningful, e.g. "pushes in with small amplitude at slow speed" (U1, VERIFIED). The API page uses bracket tags `[pan]` (U2, VERIFIED), but that is the hosted API and conflicts with U1 for the structured prompt | Natural English | keep; never bracket tags (TG-01) |
| Soundscape | 1-4 sentences; ambience, action and non-verbal sounds; no dialogue (U1, VERIFIED) | ≤ 4 sentences, cues in t order | none |
| Music | 1-3 sentences or `N/A` (U1, VERIFIED) | N/A (score is added in Ableton) | none |
| Voiceover lips | "says in an off-screen voiceover" + "lips remain completely closed" (U1, VERIFIED) | `OFFSCREEN_LIP` exists; per-person mouth sentence | B-14 |
| Speech | `<d>[Language] words</d>`; without Soundtrack-Kept the exact words belong in `<d>` (U3, VERIFIED) | No `<d>` (voice is ElevenLabs) | B-14 |
| Length | No length rule (U1, VERIFIED); API max 7,000 chars (U2, VERIFIED) | 450-4000 | none |
| Duration | 4-15 s per window; designed for 24 fps (U3, VERIFIED); API 4-15 s integer (U2, VERIFIED) | 107-345 frames at 24 fps | B-13 floor 124 for Pika |

### D2. Wan2GP H3 settings (pinned preset "Pika H3 Flex FL2VA Pruned 6 Steps", U3, VERIFIED)

| Setting | Pinned preset | Ours (`h3_director.settings_for`) | Change |
|---|---|---|---|
| model_type | minimax_h3_fl2va_pruned | same | none |
| LoRA | pika_h3_flex_fl2va_6step_v1_bf16, multiplier 1.0 | same | none |
| sampler / steps / flow_shift | pika_renoise / 6 / 12 | same | none |
| guidance | guidance_scale 1, 1 phase, custom_sigmas "" | same | none |
| skip steps | "" (off required) | same | none |
| audio_refinement | none | none | none |
| sliding_window_size | 362 | 362 (`FRAMES_MAX`) | none (our max 345 = one window) |
| video_length | example 124; help "124–362 frames at 24 fps", "480p or 768p", "5–15 second clip" | 107-345 | **floor 124** (B-13) |
| resolution | example 832x480; 768p allowed | 768x1344 | none |
| image_prompt_type | "S", "E" or "SE" (U3 lines 87-93: start only / end only / both) | S default, SE override | none |
| seed | per settings file | `shot_seed(shot id, seed_version)` | none |
| Soundtrack mode | `audio_prompt_type "A"` + `audio_guide`: video follows the soundtrack, lip-sync wording "speaking with natural lip movements synchronized", no spoken words in the prompt, "exact lip sync is not guaranteed" (U3, VERIFIED) | not used | experiment only (D-4) |
| End-image snap | "each window lands exactly on its end image ... the last few frames jump to it" (U3, VERIFIED) | S avoids it; SE keeps tail trim | none |

### D3. Nano Banana / Flow images (U4 VERIFIED; U5 INFERRED)

| Official | Ours | Change |
|---|---|---|
| Narrative sentences, not keyword lists (U4) | 8 plain sentences | none |
| "start a prompt with a strong verb" (U4) | starts with the style noun phrase | INFERRED small gain: prefix "Draw" / "Create a flat cel animation frame: ..."; test on 2 A frames |
| Positive framing: "Describe what you want, not what you don't want" (U4) | `EXCLUSION` negative sentence | B-16 |
| Edits: "focus on what is changing and what is staying the same"; "Be explicit about what to keep exactly the same" (U4) | B text "Same picture ... Change only: 1) 2) 3)" | none (matches) |
| Up to 14 reference images (U4) | char chip + STYLE chip + plate (+ A for B) | none |
| 9:16, 1K/2K/4K (U4) | 2K download (memory rule) | none |
| Model names: Nano Banana 2 = Gemini 3.1 Flash Image; Nano Banana Pro = Gemini 3 Pro Image (U4) | "Nano Banana 2.1" in our docs | **UNKNOWN**: "2.1" is not named on the official guide. Record the model label exactly as Flow shows it |
| Consistency "may vary" across edits (U5, INFERRED) | reference sheets + keyframe gate | flip `--section-4-3` (Q10) |

### D4. ElevenLabs narration en / hi / mr (U6, U7, U8 VERIFIED)

| Topic | Official | Ours (`voice_cast.py`, `voices_cast.json`) | Change |
|---|---|---|---|
| Model | Hindi on v4, v4_turbo, v3, multilingual_v2, flash_v2_5; **Marathi only on v4/v4_turbo/v3/v3_conversational** (U6) | default `eleven_v4`; 3 hi voices on multilingual_v2 | Keep v4 for all; multilingual_v2 only by owner ear choice; never for mr |
| `language_code` | ISO 639-1, enforces language and normalisation; ignored if unsupported; "not supported for multilingual_v2" (U7) | not sent | **B-09** |
| voice_settings | stability default 0.5, similarity_boost 0.75, style 0 (non-zero costs latency), use_speaker_boost true, speed 1.0 (U7); speed range 0.7-1.2 (U8) | `SETTINGS = {}` (voice defaults); `_line_speed` 1.15 | Send explicit defaults (B-09); keep per-line speed ≤ 1.2 |
| seed | 0..4294967295, "best effort ... Determinism is not guaranteed" (U7) | not sent | add (B-09) |
| Pauses | v3 and v4 do not support SSML `<break>`; use punctuation, ellipses, structure (U8) | lock measures natural durations | writer brief: no `<break>` tags |
| Sanskrit names | Pronunciation dictionaries (phoneme or alias), up to 3 locators per request (U7); phoneme tags only on `eleven_flash_v2`; v4 takes IPA in slashes; alias works without phoneme support (U8) | none | One alias dictionary per language (en first: Daksha, Kamadeva, Markandeya, Brahma, Kalika, Himavan). Spoken text changes only through the dictionary, never the caption text (caption_fields keeps captions) |
| Normalisation | `apply_text_normalization` auto/on/off (U7); "enabled by default for all TTS models" (U8) | default | Writer spells out numbers in words in hi/mr (INFERRED: normalisation quality for hi/mr is undocumented) |
| Output | mp3 default; WAV/PCM 44.1 kHz needs Pro tier (U7) | mp3_44100_128 | B-19 |
| v3 with clones | "PVCs are not fully optimized for Eleven v3"; v4 recommended for PVC/library voices (U8) | v4 | none |

---

## E. The silence rule (final design)

### E1. Evidence

| Fact | Status |
|---|---|
| ffmpeg `silencedetect` defaults: noise 0.001 (= -60 dB), duration 2 s (U9) | VERIFIED |
| EBU R128 / BS.1770 loudness ignores blocks below -70 LUFS (absolute gate) (U10) | INFERRED (search summary) |
| Netflix SilenceInspector: silence = -80 dBFS or lower; a dropout across all channels flagged; max single silent block 15 s; first/last 60 s ignored (U11) | INFERRED (page did not render) |
| Radio "dead air" = no programme for "more than a few seconds"; silence alarms on that order (U12) | INFERRED |
| The 32 proven reels: 0 spans > 0.3 s below -50 dBFS (our measurement) | VERIFIED (OPUS calibration §1.1 #25) |
| Short-form platform rule for silence | UNKNOWN (no platform document found; Luna P5 found loudness pages only) |

Conclusion: no standard fails a mix for 0.3 s of quiet. Standards fail digital silence, dropouts and long dead air. Our 0.3 s / -50 dBFS figure describes how the proven reels sound; it is a style target (warning), not a defect test.

### E2. What is measured

| Signal | Check | Why |
|---|---|---|
| **Final per-language export** (decoded from the AAC mp4 after `correct_loudness`, PCM16 48 kHz stereo) | all codes below | This is what the viewer hears |
| Ableton mix WAV at `intake` (`--mix`) | same codes (early stop, before muxing) | Cheaper failure |
| Assembled H3 clip audio (`<reel>_video.mp4`) | `CLIP_AUDIO_QUIET` warning only | Model SFX are muted/ducked later (rule 50(6)); a quiet clip is not a defect |
| Stems / per-clip model audio | none here (clip QA keeps `bed_db`) | — |

### E3. Rule text (for blot RULE 59(4))

> NO_SILENCE v2 (owner 2026-11-12). Measured on the final per-language master and on the Ableton mix WAV. Windows: 10 ms for dropouts, 50 ms RMS for quiet.
> 1. **DIGITAL_SILENCE (fail, never waivable):** sample peak ≤ -90 dBFS on all channels for ≥ 50 ms, anywhere after 0.05 s and before end - 0.05 s.
> 2. **DROPOUT (fail, never waivable):** the 10 ms level is ≥ -40 dBFS, then falls below -70 dBFS within 20 ms, stays below -70 dBFS for 20 ms to 1.0 s, and returns to ≥ -40 dBFS. This is a cut-out, not a fade.
> 3. **CHANNEL_DROP (fail, never waivable):** one channel ≤ -90 dBFS peak for ≥ 0.5 s while the other channel's RMS is ≥ -50 dBFS.
> 4. **DEAD_AIR (fail, waivable):** 50 ms RMS below -60 dBFS for more than 1.0 s. Inside an owner-tagged `silence_ok` window it may last up to 2.0 s.
> 5. **QUIET (warning):** 50 ms RMS below -50 dBFS for more than 0.3 s. No warning inside `voice_rest` or `silence_ok` windows, the first 0.10 s, or the last 0.50 s (tail fade).
> 6. **HEAD (warning):** RMS reaches -50 dBFS within the first 0.10 s, so the hook never opens on silence. First voiced word stays at 0.3-1.0 s (rule from `script_hook`).
>
> Windows (`voice_rest`, `silence_ok`) are shot-relative on the blocking sheet and converted to reel time with the lock offsets (B-10).

### E4. Constants (new module `h3/silence_rule.py`, replaces `gate_d_audio.check_no_silence` callers)

```
DIGITAL_PEAK_DBFS = -90.0;  DIGITAL_MIN_S = 0.05;  EDGE_IGNORE_S = 0.05
DROPOUT_PRE_DBFS = -40.0;   DROPOUT_FLOOR_DBFS = -70.0;  DROPOUT_FALL_S = 0.02;  DROPOUT_MIN_S = 0.02;  DROPOUT_MAX_S = 1.0
CHANNEL_DROP_MIN_S = 0.5;   CHANNEL_OTHER_MIN_DBFS = -50.0
DEAD_AIR_DBFS = -60.0;      DEAD_AIR_MAX_S = 1.0;  SILENCE_OK_MAX_S = 2.0
QUIET_DBFS = -50.0;         QUIET_MAX_S = 0.3;     HEAD_IGNORE_S = 0.10;  TAIL_IGNORE_S = 0.50
RMS_WINDOW_S = 0.05;        PEAK_WINDOW_S = 0.01
CRITICAL (add to director/waivers.py CRITICAL_CODES): DIGITAL_SILENCE, DROPOUT, CHANNEL_DROP
```

### E5. Where it runs

| Step | Change |
|---|---|
| `build_final_reel.intake` | run on the `--mix` WAV; any fail → SystemExit naming the code and time |
| `build_final_reel.main` after `correct_loudness` | decode the export with `master_wav_argv(export, wav)`, run the rule, store the result in `report.languages[lg].silence`. A fail marks the language BLOCKED (export kept, renamed `_REJECTED`) |
| `build_final_reel.main` lines 616-618 | replace the blocking call with a `CLIP_AUDIO_QUIET` warning |
| `gate_d_audio.check_no_silence` | keep as a thin wrapper that returns QUIET as a warning (old callers) |

### E6. Tests (synthetic WAVs, numpy)

| Test | Expect |
|---|---|
| `test_digital_silence_60ms_fails` | 60 ms of zeros mid-file → DIGITAL_SILENCE |
| `test_digital_silence_40ms_passes` | 40 ms → no fail |
| `test_dropout_cut_fails_fade_passes` | -20 dBFS → zeros in 1 ms for 100 ms fails; a 2 s linear fade to -65 dBFS passes |
| `test_channel_drop_fails` | L zeros 0.6 s, R -30 dBFS → CHANNEL_DROP |
| `test_quiet_bed_minus55_is_warning_only` | 2 s at -55 dBFS RMS → QUIET warning, no fail |
| `test_dead_air_1_2s_minus65_fails` | DEAD_AIR fail |
| `test_silence_ok_window_allows_1_8s` | tagged window → pass |
| `test_voice_rest_exempts_quiet_warning` | no QUIET inside the converted window |
| `test_tail_fade_exempt` | last 0.5 s fade → no warning |
| `test_head_silence_warns` | first 0.2 s silent → HEAD warning |
| `test_critical_codes_not_waivable` | waiver for DROPOUT refused |
| `test_runs_on_export_not_premix` | build_final_reel calls it on the export path (mock subprocess) |

---

## F. Start of Reel 2 (least spend)

**Story:** `stories/kalika_puran_bhag1`, episode 2 "Spring Cannot Move Him" (`pack_opus_high_20261108_v4_deva/story_plan.json` episodes[1]; rule 53(2)). The length follows the story (D-04).

Steps marked **[GO-…]** need the owner's explicit go in the same turn. Everything else is free.

| # | Step | Command / output | Owner |
|---|---|---|---|
| 0 | Land P0 cards B-01, B-02, B-03 (+ B-09, B-12, B-13 before any paid step) | G items 1-6 | approve the cards |
| 1 | Writer, free model, v2.4 brief | `python director/write_pack.py stories/kalika_puran_bhag1/story.json stories/kalika_puran_bhag1/pack_reel2_v24 --writer super-vl --web --staged --prompt-version v2.4 --episodes 2` → shots.json + blocking/SHOT-NNN.json + story fields (premise, arc_beat, hook_type, voice_rest) | — |
| 2 | Free gates | `script_inspect` PASS (hook 2.0 s, first word band 0.3-1.0 s, pacing), `story_shape` (SHAPE-01..10), `blocking.validate` + `blocking_lint` (L11-L19), `source_check`, `writer_gate`. Max 2 repair rounds, then escalate | — |
| 3 | **Owner approval 1: script text** in en/hi/mr + shot list + routes (S default, SE only where an exact end pose is needed) | read PACK.md | **approve** |
| 4 | Voice preflight (free): `voice_cast preflight` checks each voice is verified for language+model; owner listens to free preview samples | voices_cast.json for reel 2 | **approve voices by ear** |
| 5 | **[GO-ElevenLabs] pilot**: 1 narrator line + 1 dialogue line × 3 languages (6 clips) with language_code, seed, explicit settings, alias dictionary | `voice_cast run --allow-paid --cap <small>` | **go** |
| 6 | Owner listens; text freeze; fix names in the alias dictionary | — | **approve** |
| 7 | **[GO-ElevenLabs] full voice** (resume-safe by job key) → export_wavs → voice_manifest.<lang>.json | — | **go** |
| 8 | Timeline lock (measured durations, 17n+5, pika6 floor 124 frames) → shot_router routes.json | `write_timeline_lock`, `shot_router` | — |
| 9 | Ableton cue sheet from the lock (cue rows, B-11); music style work can start now (rule 52(3)) | `score/cue_sheet.py` | — |
| 10 | **[GO-Flow] reference sheets** (`--section-4-3`): identity master, turnaround, expressions, plates, STYLE chip; one accepted before the next; watermark_auto LaMa-first; full-size check | Flow agents (Haiku HIGH, own tab) | **go + accept each** |
| 11 | **[GO-Flow] keyframes A** (S shots: A only; SE overrides: A then B via generate_with_chip); keyframe_gate; full-size owner check | — | **go + accept** |
| 12 | Animatic (free): A stills + voice + guide track per language | `tools/animatic.py` | **watch and approve** |
| 13 | Compile + lint all shots; read every compiled prompt in full (rule 32); reviewers Super VL + Xing on prompt + run.py (rule 28(3)) | `build_h3_batch ... --ids <first shot>` dry run, `run_colab_batch` dry run | — |
| 14 | **[GO-Colab] first S clip only** (one shot, G4, proof within 3 min, clip saved at once, session stopped, `colab sessions` + `colab usage` checked) | `run_colab_batch BATCH --results ... --go --gpu G4 --qa-plan ...` | **go** |
| 15 | First-clip checks (table F1) + owner looks at the clip | post_fetch_qa + rule 33 contact sheet | **accept / reject** |
| 16 | **[GO-Colab] batch** of the remaining shots (only after 15 passes) | same | **go** |
| 17 | Post-fetch QA per clip; reworks per drift order (max 3 renders per shot) | — | accept waivers |
| 18 | Ableton score + mix per language (rule 50) → `build_final_reel --mix` → silence rule v2 + loudness → burned export + SRT (+ clean export if D-1 = yes) | — | **approve the final cut** |

Which shot goes first: a typical **acting shot**, chosen for these properties:
- 1 character with a clear face, medium framing, locked camera
- one primary action plus one physical reaction, no speech
- render 124-175 frames
- not the scale-tableau hook, which is the easiest case for S and would prove little

It tests identity hold, which is the S risk.

### F1. First S clip: pass/fail checks

| # | Check | Pass | Tool / who |
|---|---|---|---|
| 1 | File home within the run, size > 50 KB, 768x1344, 24 fps, frames = pixel_frames, audio stream present | all true | `fetch_ready`, ffprobe |
| 2 | Session stopped; `colab sessions` shows none of ours; units used | ≤ about 1.5 units (INFERRED: setup 2 min + model download 7 min + 0.75 s/frame × ~150 frames, rule 30(5)) | owner reads `colab usage` |
| 3 | Frame 0 vs keyframe A (768x1344) | block SSIM ≥ 0.90 | `chain_step.ssim` on frame 0 vs A |
| 4 | Identity at mid and last kept frame vs A / identity master | same character (owner eye, full-size crops at 6-8 points, rule 33) | owner (+ B-04 reviewer when built) |
| 5 | Within-clip histogram correlation | ≥ 0.60 (warn 0.40-0.60, fail < 0.40) | `clip_qa.hist_check` |
| 6 | SSIM_1s | ≥ 0.20 (else morph warning) | `clip_qa.ssim_1s_check` |
| 7 | New objects / creatures after frame 12; arm count; cast count | none / correct / equal to sheet | review JSON + owner |
| 8 | Flicker | ≤ 0.10 (placeholder; record the value) | `clip_qa` |
| 9 | Tail spike (no end snap expected for S) | not flagged | `clip_gates.tail_spike` |
| 10 | Action completes inside the lock trim window; primary beat visible before `trim_out` | yes (owner eye vs blocking beats) | owner |
| 11 | Mouth: silent cast lips closed the whole clip | yes | owner |
| 12 | Style: flat cel and ink line kept, no photoreal drift; palette stays the plate's | yes (owner); ΔE2000 ≤ 6 vs plate if g1 is run | owner / keyframe gate g1 |
| 13 | Model audio | present, no speech-like mumble louder than the bed (it is muted later anyway) | informational |

### F2. If the first clip fails (one variable per pass, log each; C-07)

1. Check the prompt first. Wrong alignment line or a blank line means a code fix, no new render until it is fixed.
2. Simplify the action (one primary, add "<name> does not move").
3. Remove the camera move.
4. Shorter render (124 frames) or split the shot.
5. New seed (`--seed-version 2`).
6. Route change S → SE for that shot only (needs a B keyframe: Flow go).

Stop after 3 renders of the shot (`render_allowed`) and escalate to the owner.

If identity drift is the failure on 2 of 3 tries, use SE for all shots with faces and keep S for empty-plate, reveal and chain shots. This is the fallback default.

---

## G. Next implementation checklist (coder agents, Sonnet medium; max 25)

| id | Title | Files | Acceptance |
|---|---|---|---|
| G1 | Silence rule v2 module | new `h3/silence_rule.py`, `h3/gate_d_audio.py` (wrapper), `director/waivers.py` CRITICAL_CODES | E6 tests 1-11 pass; numpy; 75 s stereo in < 2 s |
| G2 | Run the silence rule on the real master | `director/build_final_reel.py` (`intake`, `main`, `master_audio_check` → warning) | `test_runs_on_export_not_premix`, `test_premix_quiet_is_warning_only`, `test_silence_fail_blocks_language` |
| G3 | Official I2VA alignment line for S | `h3/compile_h3_sing8.py:_fl2va` | `test_s_header_is_official_i2va_line`, `test_s_prompt_has_no_picture_2`, FL2VA golden unchanged, h3 suite green |
| G4 | blot RULE 59 (11-12 decisions) + stale-rule notes 27/52(5)/54(12) | `blot.md` (both copies), `HANDOFF_2026-11-10.md` addendum 15 | both copies identical (`cmp`); grep finds "RULE 59"; no old line edited |
| G5 | ElevenLabs request: language_code, seed, explicit settings | `director/voice_cast.py:build_jobs`, `run` | `test_job_has_language_code_v4`, `test_no_language_code_for_multilingual_v2`, `test_seed_in_job_key`, `test_settings_explicit_defaults` |
| G6 | Pronunciation alias dictionary support | `director/voice_cast.py` (`pronunciation_dictionary_locators`, ≤ 3), new `stories/<slug>/pronunciation_<lang>.json` | `test_locators_max_3`, `test_locator_ids_in_job_key`; caption text unchanged |
| G7 | Pika floor 124 frames | `director/build_h3_batch.py:legacy_rows`, `director/timeline_lock_core.py` (route-aware min n = 7 for pika6) | `test_pika6_refuses_107`, `test_lock_picks_124_for_short_shot`, M-12 tests still pass |
| G8 | Post-fetch QA fails closed | `director/run_colab_batch.py:main` | `test_go_without_qa_plan_refused`, `test_no_qa_flag_recorded_in_history` |
| G9 | Identity check for S clips | `director/clip_qa.py` (new `identity_check`), `director/qa_plan.py` (identity master path) | `test_s_route_runs_identity_check`, `test_identity_no_fails_clip`, stub when no key |
| G10 | Scene-cut on neighbour SSIM for S | `director/clip_qa.py:qa_shot` | `test_s_route_scene_cut_uses_neighbour_ssim`; SE behaviour unchanged |
| G11 | One clock for voice_rest (+ silence_ok field) | `director/blocking.py` (BLK-S21 shot-relative, add `silence_ok`), `director/story_shape.py` SHAPE-10, `score/cue_sheet.py` | `test_voice_rest_same_reel_window_in_story_shape_cue_sheet_silence`, `test_silence_ok_max_2s` |
| G12 | Cue rows written for Ableton | `score/cue_sheet.py:main` (+ csv), read blocking `sound_cues` | `test_cli_writes_cue_rows`, `test_cue_rows_from_blocking_sound_cues` |
| G13 | SRT next to the export, versioned, after success | `director/build_final_reel.py` | `test_srt_named_like_export`, `test_srt_not_written_when_export_fails`, UTF-8 no BOM |
| G14 | SRT line mode for YouTube | `director/build_final_reel.py` (new `srt_line_cues`), `core/caption_export.py` unchanged | `test_srt_line_mode_max_42_chars_2_lines`, `test_srt_times_equal_voice_report`, Devanagari fixture (ब्रह्मा) round-trips |
| G15 | Clean (no-caption) export, only if owner D-1 = yes | `director/build_final_reel.py`, `h3/gate_d_audio.build_final_mux_argv` | `test_clean_export_has_no_subtitle_filter`, same audio sha as the burned export |
| G16 | post.py sidecars off for reels | `director/post.py` | `test_post_writes_no_sidecar_by_default` |
| G17 | Narration shots use the official voiceover lip sentence | `h3/compile_h3_sing8.py`, `h3/prompt_hygiene.py` | `test_narration_shot_uses_offscreen_lip_sentence`; MO-01 still passes |
| G18 | Positive cast sentence in A prompts | `director/keyframe_jobs.py:EXCLUSION` | `test_a_prompt_positive_cast_sentence`; ≤ 110 words |
| G19 | Flip `--section-4-3` default on | `flow/scripts/bible_to_sheet_jobs.py` | `test_section_43_default_on`; old flag still accepted |
| G20 | core.json caption keys marked "post.py only" | `core/core.json` (comment key `_caption_note`), `director/post.py` doc | `test_build_final_reel_does_not_read_core_caption_band` |
| G21 | ElevenLabs output format from config | `director/voice_cast.py` | `test_output_format_from_config`; default mp3 unchanged |
| G22 | Text-card QA wired into build_final_reel (OCR input optional) | `director/build_final_reel.py`, `director/text_card_qa.py` | `test_text_card_qa_runs_when_ocr_given` |
| G23 | Animatic step in the runbook + UI wizard button | `ui/` wizard, `tools/animatic.py` | wizard e2e test shows the animatic step before the Colab go |
| G24 | Story writer writes premise/arc/hook/voice_rest fields | `director/write_pack.py`, `director/writer_prompts.py` (v2.4) | `test_v24_pack_has_story_fields`; story_shape passes on the fixture |
| G25 | COLAB_CLI_REFERENCE refresh (`colab ssh`; G4 accepted) | `research/COLAB_CLI_REFERENCE.md` | doc mentions no `colab console`; owner confirms `colab new --help` lists G4 |

## Decisions needed from the owner
- **D-1:** Does the YouTube upload get a clean (no burned captions) export plus the SRT? Recommended: yes (G15).
- **D-2:** Silence rule v2 as written in section E (fail only on digital silence, dropout, channel drop, dead air > 1 s; 0.3 s quiet = warning). Recommended: yes.
- **D-3:** Start S-shot A keyframes in parallel with the voice work (rule 52(3) amended for S). Recommended: yes.
- **D-4:** Narrated lines as off-screen voiceover with closed mouths; on-screen speaking only in short dialogue shots. Optionally test Soundtrack-Kept lip sync once (one language only). Recommended: voiceover; no test now.
- **D-5:** Reel 2 writer = free super-vl with v2.4 (no Opus). Recommended: yes.

```json
[
 {"id":"G1","title":"Silence rule v2 module","files":["h3/silence_rule.py","h3/gate_d_audio.py","director/waivers.py"],"acceptance":"E6 tests 1-11 pass; numpy; 75 s stereo checked in under 2 s"},
 {"id":"G2","title":"Run the silence rule on the real master","files":["director/build_final_reel.py"],"acceptance":"test_runs_on_export_not_premix, test_premix_quiet_is_warning_only, test_silence_fail_blocks_language pass"},
 {"id":"G3","title":"Official I2VA alignment line for route S","files":["h3/compile_h3_sing8.py"],"acceptance":"test_s_header_is_official_i2va_line, test_s_prompt_has_no_picture_2 pass; FL2VA golden unchanged; h3 suite green"},
 {"id":"G4","title":"blot RULE 59 with the 2026-11-12 decisions","files":["blot.md (both copies)","HANDOFF_2026-11-10.md"],"acceptance":"copies identical (cmp); RULE 59 present; no old line edited"},
 {"id":"G5","title":"ElevenLabs language_code, seed, explicit settings","files":["director/voice_cast.py"],"acceptance":"test_job_has_language_code_v4, test_no_language_code_for_multilingual_v2, test_seed_in_job_key, test_settings_explicit_defaults pass"},
 {"id":"G6","title":"Pronunciation alias dictionaries","files":["director/voice_cast.py","stories/<slug>/pronunciation_<lang>.json"],"acceptance":"test_locators_max_3, test_locator_ids_in_job_key pass; caption text unchanged"},
 {"id":"G7","title":"Pika render floor 124 frames","files":["director/build_h3_batch.py","director/timeline_lock_core.py"],"acceptance":"test_pika6_refuses_107, test_lock_picks_124_for_short_shot pass; M-12 tests pass"},
 {"id":"G8","title":"Post-fetch QA fails closed","files":["director/run_colab_batch.py"],"acceptance":"test_go_without_qa_plan_refused, test_no_qa_flag_recorded_in_history pass"},
 {"id":"G9","title":"Identity check for S clips","files":["director/clip_qa.py","director/qa_plan.py"],"acceptance":"test_s_route_runs_identity_check, test_identity_no_fails_clip pass; deterministic stub without key"},
 {"id":"G10","title":"Scene-cut on neighbour SSIM for route S","files":["director/clip_qa.py"],"acceptance":"test_s_route_scene_cut_uses_neighbour_ssim passes; SE unchanged"},
 {"id":"G11","title":"One clock for voice_rest, add silence_ok","files":["director/blocking.py","director/story_shape.py","score/cue_sheet.py"],"acceptance":"test_voice_rest_same_reel_window_in_story_shape_cue_sheet_silence, test_silence_ok_max_2s pass"},
 {"id":"G12","title":"Cue rows written for Ableton","files":["score/cue_sheet.py"],"acceptance":"test_cli_writes_cue_rows, test_cue_rows_from_blocking_sound_cues pass"},
 {"id":"G13","title":"SRT next to the export, versioned, after success","files":["director/build_final_reel.py"],"acceptance":"test_srt_named_like_export, test_srt_not_written_when_export_fails pass; UTF-8 without BOM"},
 {"id":"G14","title":"SRT line mode for YouTube","files":["director/build_final_reel.py"],"acceptance":"test_srt_line_mode_max_42_chars_2_lines, test_srt_times_equal_voice_report pass; Devanagari fixture round-trips"},
 {"id":"G15","title":"Clean no-caption export (if owner D-1 yes)","files":["director/build_final_reel.py","h3/gate_d_audio.py"],"acceptance":"test_clean_export_has_no_subtitle_filter passes; audio sha equals the burned export"},
 {"id":"G16","title":"post.py sidecars off for reels","files":["director/post.py"],"acceptance":"test_post_writes_no_sidecar_by_default passes"},
 {"id":"G17","title":"Official voiceover lip sentence for narration shots","files":["h3/compile_h3_sing8.py","h3/prompt_hygiene.py"],"acceptance":"test_narration_shot_uses_offscreen_lip_sentence passes; MO-01 passes"},
 {"id":"G18","title":"Positive cast sentence in A prompts","files":["director/keyframe_jobs.py"],"acceptance":"test_a_prompt_positive_cast_sentence passes; prompt at most 110 words"},
 {"id":"G19","title":"Reference sheets section 4.3 on by default","files":["flow/scripts/bible_to_sheet_jobs.py"],"acceptance":"test_section_43_default_on passes; old flag accepted"},
 {"id":"G20","title":"Mark core.json caption keys as post.py only","files":["core/core.json","director/post.py"],"acceptance":"test_build_final_reel_does_not_read_core_caption_band passes"},
 {"id":"G21","title":"ElevenLabs output format from config","files":["director/voice_cast.py"],"acceptance":"test_output_format_from_config passes; default mp3 unchanged"},
 {"id":"G22","title":"Text-card QA wired into the build","files":["director/build_final_reel.py","director/text_card_qa.py"],"acceptance":"test_text_card_qa_runs_when_ocr_given passes"},
 {"id":"G23","title":"Animatic step in runbook and UI wizard","files":["ui/","tools/animatic.py"],"acceptance":"wizard e2e test shows the animatic step before the Colab go"},
 {"id":"G24","title":"Writer emits premise/arc/hook/voice_rest","files":["director/write_pack.py","director/writer_prompts.py"],"acceptance":"test_v24_pack_has_story_fields passes; story_shape passes on the fixture"},
 {"id":"G25","title":"Colab CLI reference refresh","files":["research/COLAB_CLI_REFERENCE.md"],"acceptance":"no colab console left; owner confirms G4 in colab new --help"}
]
```
