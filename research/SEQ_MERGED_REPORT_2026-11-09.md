# Merged sequence and architecture report (2026-11-09)

Reviewers: Haiku A (logs/rules), Haiku B (code timing chain), Codex gpt-6-luna (read-only), Nemotron 3 Ultra, Nemotron Super (run 2, 16000 tokens), Dots (OpenRouter :free, spend 0). Raw reports: `SEQ_REVIEW_*_2026-11-09.md` in this folder. Weight: Haiku B and Codex (read the code) > Haiku A and Ultra (read logs) > Super2 > Dots (6 of 32 slices failed, lists trivial test noise). Super run 1 failed 17/32 slices (token starvation), not used.

## 1. Root cause (all reviewers agree)
The picture was fixed before the sound. 11-07 01:52 "render once, ElevenLabs after render" -> render 11-09 01:34 -> voices approved 02:42, first paid batch 05:27 -> every later repair (RULE 38, 42, 47, editorial_by_lang, cue-sheet rebuild, 8 rewritten lines, 3 caption rebuilds) is a symptom. Voice is paid but its text is free to fix early; the render is the fixed, expensive budget, so audio must decide length, not the render.

## 2. Corrected sequence (cross-checked; where reviewers disagreed, the resolution is marked)
| # | Stage | Writes (contract) | Gate before next |
|---|---|---|---|
| 0 | Source lock + style pack | SOURCE.md hash, `source_check.json` (names/events per shot vs source, reviewer pass) | fidelity pass, STYLE-01/02 |
| 1 | Writer text (no times) | `shots.json` text only, per-second directives | easy-language, staging list per shot checked vs source |
| 2 | Voice pre-flight + pilot | account slots/languages/rate OK, one real line per voice + hard names, measured s/char | owner hears hard names |
| 3 | Text freeze + FULL voice run (once, cap) | `FINAL_TEXT.json` hash, per-line natural mp3 durations (`vo_tracks_report.json`) | text hash fixed, no regeneration after |
| 4 | **Timeline contract** (new `timing_contract.json`) | per shot integer frames at 24 fps = max over languages of MEASURED natural line + margin, rounded to exact beat/bar frames for music acts, plus head/tail handles H3 needs, input sha256 | every language fits at 1.00x, handles legal, hash frozen |
| 5 | Keyframes A/B | B is an edit of A, staging checked vs script before approval | full-size pair review |
| 6 | H3 author + lint + prompt compile | prompts carry contract hash; lint with image codes AFTER step 5 | compiled prompts read in full, sound-cue noun ban, no dup/glue |
| 7 | Free render pre-flight | URL curl, script size, blank-line check, reviewers' pass file | all green, one-shot proof (SHOT-001) |
| 8 | Render + clip QA | clip frame count == contract frames; clips saved per shot | frame scan + A/B end match |
| 9 | Assembly -> score -> SFX/voice mix (Ableton) -> captions -> delivery | all read the contract; stale hash = refuse | contact sheet on real frames, measured levels |

Disagreements resolved:
- Haiku A put a frozen timeline BEFORE the full voice run (from a pilot). Wrong: frames must come from measured real durations (Haiku B, Codex). Pilot only prevents rewrites; the full run precedes the contract.
- Super2 put music and SFX scoring before keyframes and used -14 LUFS. Wrong: model SFX exist only after the render (Codex), and the owner standard is -16 LUFS in `core.json`.
- Ultra gave the voice step an "anchor clip from the first approved H3 clip" (circular) and a 16:9 aspect (reel is 768x1344, 9:16). Both dropped.
- Music tempo: choose the beat grid in step 4 so cut lengths are exact bars (Haiku B: 45 frames per 4 beats at 128 BPM, 90 per 11 beats at 176) instead of rounding to the nearest frame afterwards.

## 3. Architectural changes, merged and ranked
1. One `timing_contract.json` written once (new `director/timing_contract.py`), read by H3 lattice, voice-track build, Gate D, mux, captions, music cue sheet. Replaces `editorial_by_lang.json` end-extension, the time_range from the writer, the 70.0/70.8/72.833 duplicate clocks and three tempo limits (1.03/1.15/1.15).
2. Hash gates in code: a stage refuses to start if the upstream contract hash differs; cue sheet, stems, captions go stale on a changed hash.
3. Measure speech before text is final (pilot) and delete the SPEECH-01 w/s estimate once measured values exist.
4. One free pre-flight command before every paid call (URLs, voice slots, keys valid, script size, blank lines, prompt lint, one-shot plan).
5. Sound/staging/prompt lint before authoring (creature-noun ban in audio cues, compiled-prompt duplicate/glue check, per-shot "who is on screen" vs source).
6. Runner: stop session on ALL DONE, setup log into status file, `colab sessions` check at exit, one-shot proof required before batch.
7. Music/mix order: style study before bible; Ableton the only final mix; SFX policy (script hits only, beds 22 dB under voice) set before the render prompts.
8. One caption engine, one loudness source (`core.json`), one code tree (build_h3_batch.py and run_colab_batch.py exist only in `anime_studio`, not in the merge tree).
9. Automated frame scan as first clip QA gate; human looks only at flagged frames.

## 4. Shortest fix per problem (from Haiku A section 7 and Haiku B "SHORTEST FIX", checked against code)
Delete first: the "at start" branch in `editorial_by_lang.apply_shots`; frame rounding in `plan_shot` (use exact bar lengths); in-place atempo in `voice_cast.export_wavs`; `MAX_SPEEDUP`; `CAPTION_FIXES` as a silent override (add caption == TTS text check); the raw-shots pass in `render_controller._gate_d_result` (two Gate D verdicts today: 70.0 s vs 72.833 s); Gate D's own loudness target; the V4 caption writer.
Rename/move: `voice_cast` export writes `<id>.wav` but `build_vo_tracks` reads `<id>.<lang>.wav` (fix once); move blank-line collapse into `compile_fl2va_prompt`; `voice_cast.load_slots` still uses scripted windows (rule 42 basis).
Build, smallest: timing_contract writer + readers; keyframe_review field that prepare requires; preflight.json that `--go` requires.
Reel 1 needs no re-render or re-voice: build the contract offline from the existing voice report, clips and `editorial_by_lang.json`, then verify all consumers read it.

## 5. Facts to fix in the docs (found by cross-check)
- blot RULE 41 (re-render shot 7) conflicts with the 11-09 13:01 log decision (shot 7 kept).
- Caption rule appears as 46 and 51; VOICE_SYSTEM_DESIGN says nothing generated (stale); merge-tree PROJECT_LOG NOW block is stale (canonical log is `anime_studio/PROJECT_LOG.md`).
- Voice file naming mismatch (O8, Haiku B). Haiku B runtime effects are inferred from code, no test was run.

## 6. Limits
Dots and Super run 1 were incomplete. "Shortest fix" was added to Haiku A and B in flight; Codex, Ultra, Super and Dots ran before the instruction, so their reports have no per-problem fix column (the merge above supplies it from Haiku A/B). No code was changed in this review.
