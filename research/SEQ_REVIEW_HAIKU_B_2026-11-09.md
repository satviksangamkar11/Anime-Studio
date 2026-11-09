# Sequence review B: code-level timing data flow (Haiku B, 2026-11-09)

Scope: read only. No model, API, paid or Colab call. Files read: director/build_final_reel.py, director/build_vo_tracks.py, director/editorial_by_lang.py, director/voice_cast.py, h3/render_controller.py, h3/v4_to_h3.py (timing parts), h3/gate_d_audio.py (grep), h3/assemble_reel.py (grep), h3/compile_h3_sing8.py (grep), the pack editorial_by_lang.json, research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md, research/VOICE_SYSTEM_DESIGN_2026-11-09.md, blot.md rules 27-51.

Notes on the inputs:
- director/build_h3_batch.py and director/run_colab_batch.py do NOT exist in anime_studio_merge. They exist only in D:/aai work/anime_studio/director/. Rule 27 names them as the render path, so the render path lives in a second code tree. Their timing facts below come from the anime_studio copies (grep only, not fully read).
- research/FINAL_TEXT_v2.json is not in the merge tree. The key format used below (`<line>.<lang>` with `window_s`) is taken from voice_cast.load_slots, not checked against the file.
- blot.md rules are numbered by heading, not by line. Rules 27-51 are at blot.md lines 108-183.

---

## 1. TIMING CHAIN (one shot, in the order the code actually runs)

Example shot: any SHOT-nnn. The same chain applies to every row.

| # | Stage (file:function) | Input | What it decides for the shot | Written to |
|---|---|---|---|---|
| 1 | Writer, pack shots.json (v4 pack) | writer output | `editorial_duration_sec` (length, e.g. SHOT-003 = 7.0 s); `per_second_directives` (t0/t1 in editorial seconds); `audio_and_dialogue_track.*.time_range` (scripted speech window, start = the mouth-sync time) | `stories/.../pack_opus_high_20261108_v4_deva/shots.json` |
| 2 | h3/v4_to_h3.py:fit_lattice | editorial_duration_sec | Picks `lattice_n` and `pixel_frames` (the frames the model generates) so the cut has legal handles (head 8..35, tail 24..47). This is the hard ceiling for every later length change. | story rows `timing_and_lattice` (pixel_frames, latent_slots) |
| 3 | h3/v4_to_h3.py:_plan_handles, _timing_inputs | pixel_frames, ed = round(e_sec*24) | `trim_in_frame`, `trim_out_frame`, head/tail handles; `editorial_frames` | story `timing_and_lattice` |
| 4 | h3/v4_to_h3.py:_shot, _stages (line 144), _mouth (line 169) | ti (trim_in), ed, directives | Maps each second of directive and each mouth state to clip frames (`a = t0*24 + ti`). The 7 motion sentences and mouth text are baked here. | story `h3_fields` / prompt text |
| 5 | h3/compile_h3_sing8.py:compile_fl2va_prompt | story shot | The compiled prompt, using the stage text from step 4 | prompt.txt |
| 6 | director/build_h3_batch.py:legacy_rows (anime_studio copy, line 133-141) | `pixel_frames`, prompt | `render_frames = pixel_frames`; blank lines collapsed here, not in the compiler | batch rows |
| 7 | director/run_colab_batch.py (anime_studio copy) + GPU | batch rows | Clip frame count = pixel_frames. Fixed at render time. | clip.mp4 (SHOT-nnn/) |
| 8 | director/voice_cast.py:run (ElevenLabs, paid) | pack shots.json text, voices_cast.json | One mp3 per line and language, natural length. No timing applied. | mp3/<lang>/..., eleven_manifest.json |
| 9 | director/voice_cast.py:export_wavs + load_slots (line 297, 269) | mp3, slot = SCRIPTED time_range width (or FINAL_TEXT window) | Trims edge silence, atempo to fit the SLOT (not the editorial length) | wav/<lang>/<id>.wav, fit_report.json |
| 10 | director/editorial_by_lang.py:plan (line 104) | raw natural voice wavs (`<raw>/<lang>/<id>.<lang>.wav`), beats (BPM), spare frames from pixel_frames - trim_out | Extends editorial_frames at the END of the shot (last shot at the START only), by whole beats for BPM shots, capped by spare frames | pack editorial_by_lang.json |
| 11 | director/editorial_by_lang.py:apply_rows (44), apply_shots (52) | file + original rows / H3 shots | New editorial_duration_sec, trim_out_frame (or trim_in at start), master_reel windows, in COPIES | in memory only |
| 12 | director/build_vo_tracks.py:build (79) -> pack_shot (31) | apply_rows(rows) | One wav per shot per language of EXACTLY the new editorial length. Lines at scripted start (+GAP 0.12 s); one atempo up to MAX_TEMPO 1.15, the smallest that ends each line TAIL 0.10 s before the cut | `vo/<lang>/SHOT-nnn.wav`, vo_tracks_report.json (line start/end) |
| 13 | director/build_final_reel.py:main (261-265) | file + story | Re-applies apply_rows and apply_shots; checks pack row ids equal H3 shot ids | in memory |
| 14 | build_final_reel.py:assemble_video (41) | h3_shots (extended trims), clips | Clip frame check (`probe_frames >= trim_out_frame`); ffmpeg trims each clip to trim_in..trim_out and concatenates | kalika_reel1_video.mp4 |
| 15 | build_final_reel.py:mux_argv (64) + h3/gate_d_audio.py:plan_language_outputs | editorial sums, VO files | Mix offsets = cumulative editorial; VO_OVERFLOW check (gate_d_audio ~line 196-208) | export/<reel>_<lang>.mp4 |
| 16 | build_final_reel.py:spoken_cues_real (153) + caption_ass (181) | vo_tracks_report line start/end (from step 12) | Caption cards; each word's time is a letter-proportional share of the LINE window. No audio alignment. | captions .ass |
| 17 | HANDOFF section 2 (manual) | editorial lengths | Music beat grid (60/BPM) per shot; the cue sheet was built on the v3 lengths (handoff section 3) | score/ep1/cue_sheet.json |

Summary of which stage FIRST decides a shot's length: step 1 (writer's editorial_duration_sec), then fixed for render by step 2 (pixel_frames). After step 2 the frame budget is fixed for good, because the clip is rendered at pixel_frames.

---

## 2. REPAIRS (a later stage had to change an earlier length)

R1. Lattice re-pick (fit_lattice, v4_to_h3.py:302). The writer's smallest lattice left 4..14 spare frames that could never form a legal handle plan. The code re-picks n and pixel_frames before render. This is the correct repair (before render). It shows the length is decided in two places (writer and lattice).

R2. Voice longer than the shot (owner example). The video was rendered first, at pixel_frames chosen from the v3 writer length. Voice came later.
- build_vo_tracks.pack_shot (line 31) repairs by atempo up to 1.15. Beyond that it raises and the shot is reported, not fixed.
- RULE 38 and RULE 42: 8 lines were rewritten shorter and REGENERATED by paid ElevenLabs calls. The "no regeneration" intent (RULE 35, owner) was broken for those 8 lines.
- RULE 39: the audio window was sized to the whole clip and was wrong for 14 of 54 lines (RULE 42). The windows file FINAL_TEXT_v2.json is still read by voice_cast.load_slots (line 280) for export.

R3. editorial_by_lang extends shots AFTER the clips and the voice wavs exist (the shared timeline, RULE 47).
- It adds frames the clip already has (spare = pixel_frames - trim_out_frame). The picture is not re-rendered. The clip spare tail was rendered but never shown; this is a silent post-render decision.
- For the LAST shot it moves trim_in ("at start", apply_shots line 60). The prompt mouth and stage timing (v4_to_h3._stages line 150, _mouth line 179) were compiled with the ORIGINAL ti. After the change, every stage and mouth state in the last shot is off by the new head frames. Shot 10 had 0 frames, so this has not fired yet. It is a latent error.
- The extension at END of a shot changes the clip's last seconds, which the prompt sentences were written for at the old editorial length (the stage of 7 sentences covers pixel_frames, so the prompt is not wrong, but the editorial cut now shows frames the motion stage was not authored to end on). Not verified visually.

R4. Beat rounding repairs the length to a beat grid, but it cannot be exact (editorial_by_lang.plan_shot, line 83-91).
- At 128 BPM one beat = 11.25 frames at 24 fps. The code rounds to frames: `round(ceil(raw/beat)*beat*fps)`. For SHOT-003 it outputs 11 frames = 0.4583 s, which is LESS than one beat. The docstring and the note "rounded up to 1 beat(s)" are wrong by 10.4 ms per shot.
- The residuals (max 19 ms, handoff table) accumulate in the absolute timeline. The start of each later shot is no longer on the beat grid (shot 3 starts at 11.375 s = 24.27 beats).
- Exact integers exist: at 128 BPM 4 beats = 45 frames; at 176 BPM 11 beats = 90 frames. The code does not use them.

R5. Second tempo fit on the same voice (voice_cast.export_wavs line 305-311 and build_vo_tracks.build line 91-99).
- export_wavs fits to the scripted slot and writes the fitted wav in place of the natural one.
- editorial_by_lang.plan (line 115) reads the natural length from the `<raw>/<lang>/` wav. If someone points it at the export output (already atempo'd), the need is UNDER-estimated and the extension is too short. If someone points build_vo_tracks at export output, it measures the fitted length and fits again. The contract does not say which wavs are natural.

R6. Captions repaired after the voice changed (build_final_reel.CAPTION_FIXES line 95, applied line 168-170).
- The hi caption fixes (SHOT-003-D1 ब्याहीं, SHOT-010-D1 ग़लती) change the TEXT after the voice mp3s were made. The voice still says the old text. The code comment says "voice files NOT changed". Caption and speech now differ on those two lines.

R7. Gate D in the render controller uses the unextended timeline (h3/render_controller.py:_gate_d_result, lines 537-564).
- It passes `ep["shots"]` raw to plan_language_outputs, with no apply_shots / apply_rows. build_final_reel passes the extended rows. So the same reel gets two Gate D verdicts with different lengths (70.0 s vs 72.833 s for reel 1). Nothing compares them.

R8. Three different tempo limits for three planners.
- build_vo_tracks.MAX_TEMPO = 1.15 (pack), voice_cast.MAX_TEMPO = 1.15 (wav fit), editorial_by_lang.MAX_SPEEDUP = 1.03 (plan warns only). The plan extends the shot to satisfy 1.00 (natural, need1) and only warns at 1.03. The pack then uses up to 1.15. The lengths are therefore chosen for a speed the packer does not need, and the two numbers are not tied together.

---

## 3. PROPOSED ORDER AND CONTRACT

### 3.1 Why audio first for LENGTH
- The hard budget is the render (pixel_frames). Its cost is GPU units and it cannot be extended after the clip exists. The voice is paid per character and cannot be changed without a new paid call. The text is free to change before the voice is made.
- So the length must be decided from (a) frozen text, (b) MEASURED natural voice durations, and only then (c) the lattice and render. Video-first forces the voice to fit whatever the clip gave, which is the reel 1 failure (R2, R3, R5).
- For reel 1 the voices are already made (54 clips, RULE 39). So the contract can be built now from the measured mp3 and the render can still be chosen after it, if the lattice is chosen after the contract. Rendered clips already exist, so for reel 1 the contract must be checked against pixel_frames (a gate), not re-chosen.

### 3.2 The single timing contract: `timing_contract.json` (per story pack, one file for all languages)

Written by ONE stage. Read by every later stage. Each stage checks its inputs' sha256 against the contract before it runs.

Fields per shot (integers where possible, frames at 24 fps):
- `shot_id`, `start_frame` (cumulative), `editorial_frames` (integer, the cut length), `pixel_frames` (lattice, >= editorial_frames + handles; set AFTER the contract), `trim_in_frame`, `trim_out_frame`.
- `bpm` (or null) and `beat_frames` (exact: 60*24/bpm must give an integer count of frames per bar; otherwise the bar is rejected at contract time, not rounded).
- `lines`: [{id, lang, start_s, natural_s, placed_start_s, placed_end_s, tempo}] per language; `tempo` is always 1.00 or the single packing value up to MAX_TEMPO; the natural_s is the MEASURED mp3 duration, never a fitted one.
- `speech_budget_frames` = editorial_frames - TAIL frames (per language, max over languages).
- `inputs`: sha256 of shots.json (text fields), of each measured natural clip (per line, per language), and the BPM table.

Top level: `contract_sha256`, `fps`, `shared_timeline: true`, `max_tempo`, `tail_s`, `gap_s`.

### 3.3 Stages and what they read and write

| Order | Stage | Writes | Reads | Gate |
|---|---|---|---|---|
| S0 | Text freeze (writer + caption fixes) | shots.json text, CAPTION text source | writer output | text hash stored; caption text == TTS text (prep_text) per line, checked |
| S1 | Voice generation (voice_cast run, paid) | mp3 per line, eleven_manifest.json (natural) | S0 text, voices_cast.json | job key includes text hash (already in voice_cast) |
| S2 | Measure natural durations (voice_cast measured) | measured natural seconds | mp3 | ffprobe; no atempo |
| S3 | TIMING CONTRACT (new director/timing_contract.py) | timing_contract.json | S0 text hashes, S2 measured naturals, BPM table, spare frames | sha256 of inputs; integer frames; bar-exact beats; lines fit at <= MAX_TEMPO |
| S4 | Lattice (v4_to_h3.fit_lattice reads contract) | pixel_frames, latent_slots, trim frames | S3 editorial_frames | pixel_frames >= editorial_frames + legal handles, or STOP |
| S5 | Prompt compile (compile_h3_sing8) | prompt.txt | S4 story | the compiled prompt carries contract_sha256 in its header; no blank line in the compiler itself |
| S6 | Render (build_h3_batch, run_colab_batch) | clip.mp4 | S5 prompt, S4 pixel_frames | clip frames == pixel_frames (ffprobe) before the clip is "home" |
| S7 | Voice wav build (build_vo_tracks reads contract) | vo/<lang>/<id>.wav of exactly editorial length | S3 lines, natural wavs | atempo recorded in contract; no re-fit |
| S8 | Reel assembly + Gate D + mux (build_final_reel) | video, export mp4 | S3 editorial, S4 trims, S7 wavs | the same contract sha in build report; Gate D in render_controller uses the same contract |
| S9 | Captions (build_final_reel) | .ass/.srt/.vtt | S7 report (line starts from S3) | words aligned (optional ASR check, asr_transcribe.py exists) |
| S10 | Music (score) | cue sheet, BGM manifest | S3 bar grid (absolute frames) | cue sheet sha in contract; music mix re-checks Gate D |

Contract rules: a stage that finds a different contract sha in its input stops. No stage writes a length. Only S3 writes editorial_frames. Only S4 writes pixel_frames. Only S7 writes wavs.

### 3.4 Concrete rules for the contract
- Editorial frames are integers. A shot's length is `editorial_frames / 24`. The beat rule applies only if an exact bar exists (128 BPM: bars of 45 frames; 176 BPM: 11-beat units of 90 frames; 60 BPM: 24 frames per beat). Otherwise the shot is NOT on the grid, and the music must follow the picture, not the other way round.
- The extension is allowed only from the shot's own spare frames and is recorded per shot.
- Speed-up limit: ONE constant (MAX_TEMPO = 1.15). The plan must use the same constant as the packer. The 1.03 plan threshold is removed.

---

## 4. OTHER ORDER PROBLEMS

O1. Music vs SFX vs voice mix (build_final_reel.mux_argv line 78-79, gate_d_audio BGM checks). The BGM slot is None, so Gate D BGM presence checks never run. Music is added later with ffmpeg amix (rule 49 step 7) or in Ableton (rule 50). The loudness correction (correct_loudness, line 228) runs on the export without music. Music added after that changes the loudness, so the correction must be run again. Proposal: the music stage takes the contract and the mux is one function with the BGM manifest passed in.

O2. Model SFX are the same loudness as voice (rule 49 item 8). The mix priority (voice > key hits > music) is decided in code nowhere in build_final_reel: the SFX stem is a plain split of the clip audio (build_sfx_split_filter, line 78). Rule 50 says SFX should be cut to script-cue hits. That selection is not in the build path, so the mix cannot be reproduced from code.

O3. Keyframe vs script checks (render_controller._picture_rows line 208-227). The only keyframe check is PNG dimensions and presence. Content (SHOT-008: standing in A, seated in B; rule 31) is checked only by eye after the render. The keyframe content check must be a gate BEFORE compile (S5) and before the paid GPU start (S6). Rule 32 asks for it in the owner's order, but no code enforces it.

O4. Prompt compile vs render (compile_h3_sing8 vs build_h3_batch.legacy_rows). The compiler can emit blank lines (rule 30). build_h3_batch collapses them after compile and raises if one remains. The compile tests therefore never see the bad text. Proposal: collapse in compile_fl2va_prompt so the compiled text is single-line, and keep the batch check.

O5. Captions vs voice text (build_final_reel.spoken_cues_real line 153-178; voice_cast.prep_text). The caption source is the raw shot text; the TTS source is prep_text(text), which rewrites "।" to ", ", removes quote marks, and appends "." . The two can differ silently. Captions use the line window from the voice report and split words by letter count (no alignment). asr_transcribe.py exists and is not used for caption timing.

O6. Editorial file has no input hash. editorial_by_lang.json (plan written by --write) records beats and plan rows but not the sha256 of the raw voice wavs or shots.json it used. A voice re-export silently makes it stale. build_vo_tracks and build_final_reel read it without checking.

O7. voice_cast.load_slots uses the SCRIPTED speaking window (line 275-279) as the fit slot. Rule 42 says the correct basis is the editorial length. The export's fit_report therefore flags lines against the wrong slot, and its atempo writes fitted wavs that build_vo_tracks would not need. This is the superseded RULE 39 basis still live in code.

O8. File-name contract mismatch between voice_cast and build_vo_tracks. voice_cast.export_wavs writes `wav/<lang>/<id>.wav` (line 304). build_vo_tracks.render_shot and build read `<raw>/<lang>/<id>.<lang>.wav` (line 67, 85, 91). So the voice_cast output cannot be fed to build_vo_tracks without a rename. The handoff command uses `$V/wav_raw/wav` from the older pipeline, so the two routes have never been run together in this code tree (not verified by running).

O9. The writer's time_range (speaking window) feeds gate_d_audio coverage and dead-air checks (gate_d_audio lines 75-79, 158) while build_vo_tracks uses the same start. Start is consistent, but the end is not used by the packer. Any change to speech window end in the writer is ignored by the voice build.

O10. Render controller manifest hash (asset_manifest.hash_shot_row, render_controller._current_hashes line 489-492) hashes the raw story row. A change to editorial_by_lang does not invalidate any clip, which is correct for the clips (they are not re-rendered), but the editorial length change is also not visible to any clip-level gate. The contract sha would fix both.

O11. Two code trees. build_h3_batch.py and run_colab_batch.py are not in anime_studio_merge (only in anime_studio). The render path that rule 27 names therefore has no copy in the tree that holds build_final_reel and the voice code. This is the same "one code tree" gap listed in rule 41.

O12. Last-shot head extension moves the prompt timing (R3). Shot 10 has 0 frames now, so no live error. Guard: refuse "at start" unless the contract says the prompt was compiled after the change.

---

## 5. CODE CHANGES NEEDED

C1. NEW director/timing_contract.py (one writer of editorial_frames and placed lines). Replaces the planning part of director/editorial_by_lang.py: plan (line 104), plan_shot (83), needed_sec (76). It reads the natural (measured, unfitted) wavs and the shot rows; writes timing_contract.json with the sha256 inputs. Integer frames; exact bar check for BPM shots.

C2. director/editorial_by_lang.py: keep only as a reader of the contract, or delete `load` (line 32), `apply_rows` (44), `apply_shots` (52) and make callers read the contract. Remove MAX_SPEEDUP (line 29); use build_vo_tracks.MAX_TEMPO.

C3. h3/v4_to_h3.py:fit_lattice (302) and _timing_inputs (210): read editorial frames from the contract, not row.editorial_duration_sec. Add a check that pixel_frames >= contract editorial_frames + handles.

C4. h3/v4_to_h3.py:_stages (144) and _mouth (169): keep as is, but record the contract sha in the story so the prompt can be proven to match the shot's final trim.

C5. h3/compile_h3_sing8.compile_fl2va_prompt: collapse blank lines in the compiler; add contract_sha256 to the prompt header. build_h3_batch.legacy_rows (anime_studio, line 136-138): keep the check, remove the collapse once the compiler does it.

C6. director/build_vo_tracks.py:build (79-101): read the contract (line placement, editorial) instead of editorial_by_lang.load. Keep pack_shot; read MAX_TEMPO from the contract. Write contract sha into vo_tracks_report.json.

C7. director/voice_cast.py:load_slots (269-283): the slot = contract speech budget (editorial - TAIL), not the scripted time_range or FINAL_TEXT window. Remove the FINAL_TEXT_v2 window path (superseded by rule 42). export_wavs (297): write `<id>.<lang>.wav` (fix O8); write the fitted wavs to a SEPARATE folder and record the tempo in the contract; never feed fitted wavs to the plan.

C8. director/build_final_reel.py:main (261-265): replace apply_rows/apply_shots with the contract; check contract sha against vo_tracks_report.json. mux_argv (64): read BGM manifest (currently None). spoken_cues_real (153): use contract line starts. CAPTION_FIXES (95): move the fixed text into the TTS source and require a voice regeneration gate, or stop applying it (the voices are not to be regenerated, so the caption must be checked against the spoken text instead; add a check that caption text == prep_text(TTS text) per line, failing on the two known lines).

C9. h3/render_controller.py:_gate_d_result (537-564): pass the contract-applied shots (same as build_final_reel), so there is one Gate D verdict per reel.

C10. h3/render_controller.py:_picture_rows / prepare (208, 285): add a keyframe content gate that refuses to write executables until a review record exists for each keyframe (reviewer sha + "full size checked" flag), before compile.

C11. h3/gate_d_audio.py:_editorial_len (650) and same_timing_problems (712): read the contract editorial length only.

C12. Music (score/): the bar grid must come from the contract (absolute frames). Re-run the cue sheet after S3 for reel 1 (handoff says it is built on v3 lengths).

C13. Tests to add (offline, no model): contract sha mismatch stops each stage; exact-bar check rejects 128 BPM with 11 frames per beat; build_vo_tracks rejects a fitted wav as input; export filename == build_vo_tracks filename; render_controller and build_final_reel Gate D give the same verdict on the same contract.

C14. Blot rules to update after the change: 42 (single basis = contract), 47 (editorial_by_lang becomes the contract), 38 (measured on natural clips only).

---

## SHORTEST FIX

Order of each fix: delete or reuse first, then the smallest build, then how to verify it is closed.

Repairs (section 2)
- R1 (lattice re-pick): keep fit_lattice. Close it by making it read the contract's editorial_frames (C3). Verify: a shot whose contract length does not fit its pixel_frames stops with an error.
- R2 (voice longer than shot, regenerated lines): no code change to reuse; close it by the S0 text gate (text is measured before any paid call). Verify: every line passes the seconds-per-character check before voice_cast run; no regeneration log entries after the contract exists.
- R3 (post-render extension, last-shot head move): delete the "at start" branch in apply_shots (editorial_by_lang.py:60). Extend only at END, from spare frames, and write the extension into the contract before lattice. Verify: the contract sha in the prompt header equals the one in the final build report.
- R4 (beat rounding is 11 frames, not a beat): delete the frame-rounding formula in plan_shot (editorial_by_lang.py:89). Use exact bar lengths only (128 BPM: 45 frames per 4 beats; 176 BPM: 90 frames per 11 beats; 60 BPM: 24 per beat). Reject any other BPM at contract time. Verify: a unit test asserts 128 BPM shots are multiples of 45 frames.
- R5 (second tempo fit / natural vs fitted wav confusion): delete the in-place atempo in export_wavs (voice_cast.py:305-311). Write fitted wavs to a separate folder and record tempo in the contract. Verify: the contract's natural_s equals ffprobe of the raw mp3 for every line.
- R6 (caption text differs from spoken text): delete CAPTION_FIXES (build_final_reel.py:95) as a silent override. Replace with a check that caption text == prep_text(TTS text) per line; the two known lines fail until the owner decides. Verify: the check runs in the build and reports those two lines.
- R7 (two Gate D verdicts): delete the raw ep["shots"] pass in render_controller._gate_d_result (line 555). Reuse the contract-applied shots from build_final_reel. Verify: render_controller and build_final_reel report the same BLOCK/WAIVED lists for reel 1.
- R8 (three tempo limits): delete MAX_SPEEDUP = 1.03 (editorial_by_lang.py:29) and its warn logic. Reuse build_vo_tracks.MAX_TEMPO = 1.15 everywhere. Verify: grep finds one definition of the limit.

Other order problems (section 4)
- O1 (music added after loudness): reuse build_final_reel.mux_argv; pass the BGM manifest into it (replace the None at line 78) and run correct_loudness once, after the mux with music. Verify: BGM_PRESENCE check runs (not skipped) in the build report.
- O2 (SFX as loud as voice, no mix priority in code): delete nothing; add one SFX-cue filter step before build_sfx_split_filter (line 78) that keeps only script-cue hits, with the rule-50 levels as constants. Verify: the SFX stem level in gaps is logged in the build report and within the rule-50 target.
- O3 (keyframe content not checked before GPU): reuse the existing render_controller prepare gate. Add one required field per shot, "keyframe_review": {sha256, full_size_checked: true}, and refuse to write prompt.txt without it. Verify: removing the field makes prepare exit 1.
- O4 (blank line collapsed in batch, not compiler): move the one-line collapse from build_h3_batch.legacy_rows into compile_fl2va_prompt, delete the batch copy after tests pass. Verify: compile tests assert no blank line in the compiled text.
- O5 (captions vs TTS text, word timing by letters): reuse core/ asr_transcribe.py only as an optional check, not in the build path. Shortest: the text equality check from R6. Verify: captions text equals TTS text per line.
- O6 (editorial file has no input hash): delete editorial_by_lang.json as a separate input once the contract exists; until then add sha256 of the raw wavs and shots.json to the file. Verify: changing one wav byte makes build_vo_tracks refuse.
- O7 (slot uses scripted window, RULE 39 basis): delete load_slots window path (voice_cast.py:275-283) and FINAL_TEXT window read. Slot = contract speech budget. Verify: fit_report slot equals editorial minus TAIL for every line.
- O8 (filename mismatch voice_cast vs build_vo_tracks): delete the `.wav` name in export_wavs (voice_cast.py:304); write `<id>.<lang>.wav`. Verify: build_vo_tracks.build finds every file the export wrote (one run, offline, on the existing reel 1 mp3s).
- O9 (writer speech window end ignored): delete nothing; the contract records the scripted end and the packer uses it as the minimum. Verify: a test with a longer scripted end moves the placed line.
- O10 (manifest hash blind to editorial change): add contract_sha256 to the clip manifest entry (asset_manifest.hash_shot_row input). Verify: changing the contract makes _current_hashes report the clip stale.
- O11 (two code trees): delete the anime_studio copies of build_h3_batch.py and run_colab_batch.py once merge carries them, or sync one copy by a single command; one tree is the only fix. Verify: the file hashes match across the two trees (or one tree is removed).
- O12 (last-shot head move): covered by the R3 deletion of the "at start" branch. Verify: the test in R3.

Code changes (section 5)
- C1 to C14 are the build for the fixes above. Smallest build order: C1 (contract writer), then C3 and C6 and C7 readers, then C8 and C9 consumers, then C5 and C10 gates, then C12 music re-run, then C13 tests. Verify all at once by one offline run of the contract and build_final_reel on the existing reel 1 files, with no paid call and no render.

Verification status: this is a read-only code review. Nothing was run, no test was executed, no file except this report was written. Claims about runtime effects (for example the 10.4 ms beat error and the O8 mismatch) come from reading the code and the handoff numbers, not from running the scripts.

PROJECT_LOG lines written by this agent: start, reads, and the final line below.
