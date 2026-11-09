# Handoff: reel 1 is finished WITHOUT music -> music producer session (updated 2026-11-09 15:15, v4)

Picture, voices, SFX and captions of Kalika Puran reel 1 are FINAL. Only the background score is missing.
Do not re-render video, regenerate voices or change captions (owner: no regeneration, no Colab). Music scope = blot RULE 43/44/45.

## 1. Final reels (no music) = the picture to score against: v4
- Masters: `D:/aai work/flow_outputs/anime_kalika_puran_bhag1/final_reel1_v4/export/kalika_reel1_{en,hi,mr}.mp4`
  (72.833 s = 1748 frames at 24 fps, SAME picture in all three, voice + clip SFX ducked under voice, burned captions, about -16 LUFS / <= -1 dBTP)
- Picture with the clips' own SFX, no voice, no captions: `.../final_reel1_v4/kalika_reel1_video.mp4`
- Build report: `.../final_reel1_v4/kalika_reel1_build_report.json`. Phone copies (listening only): `.../final_reel1_v4/phone/`
- v3 (70.0 s), v2, v1, draft are SUPERSEDED.

## 2. Shared timeline (your spec, applied): `stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/editorial_by_lang.json`
FROZEN for gate M1. Same values for en/hi/mr. If it ever changes, this file and the music session are told.

| Shot | v3 s | extra frames | new frames | new s | start frame | start s | rounding |
|---|---|---|---|---|---|---|---|
| 001 | 6 | 0 | 144 | 6.0000 | 0 | 0.0000 | none (60 BPM) |
| 002 | 5 | +9 (end) | 129 | 5.3750 | 144 | 6.0000 | none (last of act) |
| 003 | 7 | +11 (end) | 179 | 7.4583 | 273 | 11.3750 | 1 beat @128 = 0.46875 s -> 11 fr = 0.4583 s (-10.4 ms) |
| 004 | 8 | 0 | 192 | 8.0000 | 452 | 18.8333 | fits |
| 005 | 8 | +7 (end) | 199 | 8.2917 | 644 | 26.8333 | none (last of act) |
| 006 | 7 | 0 | 168 | 7.0000 | 843 | 35.1250 | fits |
| 007 | 7 | +16 (end) | 184 | 7.6667 | 1011 | 42.1250 | 2 beats @176 = 0.6818 s -> 16 fr = 0.6667 s (-15.2 ms) |
| 008 | 8 | +25 (end) | 217 | 9.0417 | 1195 | 49.7917 | 3 beats @176 = 1.0227 s -> 25 fr = 1.0417 s (+19.0 ms) |
| 009 | 8 | 0 | 192 | 8.0000 | 1412 | 58.8333 | none (last of act) |
| 010 | 6 | 0 at START | 144 | 6.0000 | 1604 | 66.8333 | none; shot 10 head extension = 0 frames |
Total 1748 frames = 72.833 s. Every extension is at the END of its shot, so the picture from each shot's start to its old cut is
unchanged: an event at "shot N + X s" with X < old length stays on the same frame. Beat rounding is exact to the nearest frame only
(24 fps); the residuals above (max 19 ms) are what the music must absorb at those three cuts.
Result for the voice: every line of every language now plays at natural speed 1.00 (v3 had up to 1.12).

## 3. Timing data
- REAL voice timings (all languages, one file): `D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva/vo_v4/vo_tracks_report.json`
  (per shot, per language: line start/end in s from the shot start). Per-shot voice wavs: `.../vo_v4/{en,hi,mr}/SHOT-nnn.wav`.
  Use these, not FINAL_TEXT_v2.json windows (RULE 42), and not the old vo/ or vo_{lang}/ folders (v3 lengths).
- Captions word timing: `.../final_reel1_v4/captions/kalika_reel1.{lang}.srt/.vtt`.
- The cue sheet in `pack.../score/ep1/cue_sheet.json` was built on the v3 lengths: re-run your cue sheet on the v4 lengths (I did not touch score/).
- White-outs moved with the timeline only if they sit after an extended cut: recompute them as "shot N + X".

## 4. Where the music plugs in (code, anime_studio_merge)
`director/build_final_reel.py`, `mux_argv`: `gd.build_mix_filter(sfx, "vo_full", None, t)`: the `None` is the BGM slot. Manifest format
`{"tracks": [{track_id, path, license_type, bpm, lufs}]}` (h3/gate_d_audio.py validate/read_bgm_manifest), written by
`score/gate_d_bridge.py write_bgm_manifest`. Same music file for all three languages. Then rerun section 6 into final_reel1_v5.
Each audio track ends 0.07-0.09 s after the picture (encoder padding, silence).

## 5. Rules
`anime_studio/blot.md` RULES 39, 42, 43, 44, 45 (music style), 46 (captions), 47 (shared per-language timeline). Log: `D:/aai work/anime_studio/PROJECT_LOG.md` (NOW block first).

## 6. Rebuild commands (local, no Colab, no paid call)
```
cd "D:/aai work/anime_studio_merge"
F="D:/aai work/flow_outputs/anime_kalika_puran_bhag1"; V="$F/voices/pack_opus_high_20261108_v4_deva"
python director/build_vo_tracks.py --pack stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva --raw "$V/wav_raw/wav" --out "$V/vo_v4" --langs en,hi,mr
python director/build_final_reel.py --pack stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva --story "$F/rework79/h3_story_rework79.json" --clips "$F/rework79/clips_draft.json" --vo "$V/vo_v4" --out "$F/final_reel1_v5"
```
Re-plan the lengths (only if voice or picture change): `python director/editorial_by_lang.py ... --beats SHOT-003:128,SHOT-004:128,SHOT-006:176,SHOT-007:176,SHOT-008:176 --write` (see its docstring).
Disk D: about 3 GB free; one build is about 470 MB.

## 7. Code tree
Branch `merge-v4-universal-2026-11-07` (worktree `D:/aai work/anime_studio_merge`), NOTHING committed. New/changed for v4:
director/editorial_by_lang.py (+ test, 5 tests), build_vo_tracks.py (reads the file, <raw>/<lang>/, ms-floored track end),
build_final_reel.py (reads the file, combined voice report, loudness limiter margin). director suite 830 pass. Commit only with the owner's OK.
