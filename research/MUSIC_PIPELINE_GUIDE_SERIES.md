# Music pipeline guide for a series (Kalika Puran and later stories)

Status: written 2026-11-09 by agent GUIDE (Haiku, medium). Facts come from the files named in section 8.
Use this to score reel 2, 3 and so on of the same series. Read `blot.md` rules 43-47 first.

---

## 1. What the music stage is

1. Music only. Background music (BGM). No sound effects, no voice. The clips' own SFX and the voice are final.
2. It runs after the picture and the voice are final. The picture is the shared timeline (rule 47).
3. One score for all languages. One video, three audio tracks (en, hi, mr). The same music file goes under all three.
4. A series reel is a phone reel of about 70 s (reel 1: 10 shots, 72.833 s). It is not a film. Every theme is a short motif.
5. Owner gates: M0 = the bible (only when the bible changes). M1 = plan + audition. M2 = final listen.
6. Nothing is committed or pushed without the owner's go.

---

## 2. Architecture, start to end

Inputs:
- `shots.json` (picture rows of the pack)
- `editorial_by_lang.json` (shared timeline, one length per shot)
- `vo_tracks_report.json` (REAL speech timing per language)
- `music_bible.json` (style, themes, roles, presets; reused every reel)
- `core.json` (retention windows)

```
shots.json + editorial_by_lang.json + vo_tracks_report.json + music_bible.json + core.json
   |
   v
cue_sheet.py ............ cue sheet (cuts, acts, tempo candidates, voice gaps, retention)
   |
   v
score_plan.json ......... written by hand (style first; section 4 rules)
   |
   v
plan_check.py ........... must print ok (0 errors)
   |
   v
M1 owner gate ........... plan table + audition (Ableton built-in sounds)
   |
   v
note_writer.py .......... exact notes per role, markers, type-1 .mid (clock mode)
   |
   v
ableton_build.py ........ JSON recipe of Ableton MCP calls + Serum briefs
   |
   v
Ableton Live 12 ......... clock mode 60 BPM, one MIDI track per role, one clip per role
   |                      duplicated to the arrangement; owner exports WAV
   v
stem .wav (48 kHz, 24-bit, exact length)
   |
   v
gate_d_bridge.py ........ checks the stem, writes bgm_manifest.json
   |
   v
build_final_reel.py ..... BGM slot (currently None) -> final_reel1_vN (Gate D checks)
   |
   v
Gate D checks ........... music 15 to 21.5 dB under voice; mono-safe bass; length
   |
   v
final reels ............. en, hi, mr + phone copies
```

---

## 3. Series rules (same every episode)

- [ ] The bible is REUSED, never replaced: home key, sonic logo, MAIN theme, character themes, transforms, presets.
- [ ] A new character gets a NEW theme, added to the bible at M0 of that episode (and only then).
- [ ] The sonic logo (LOGO_VOCAL_HORN at 0.0 s) and the end sting are on every reel.
- [ ] Themes TRANSFORM on return (tempo, mode, instrument). Never repeat a theme plainly.
- [ ] Approved plans are copied to `stories/<slug>/score_examples/` as reference for the next reel (SKILL step 9).
- [ ] Any new emotion template is added to the bible after approval.
- [ ] Style follows `research/STYLE_STUDY_Anirudh_Sai_2026-11-09.md` (it wins on style).
- [ ] Original music only. No sample of a film or song (see section 6).

---

## 4. Per-reel run checklist

Replace `<slug>` with the story (kalika_puran_bhag1), `<pack>` with the pack folder
(pack_opus_high_20261108_v4_deva), `<n>` with the episode number, and `<EP>` with
`stories/<slug>/<pack>/score/ep<n>`. Run from `D:/aai work/anime_studio_merge`.

### 4.1 Cue sheet
- [ ] Run the cue sheet with the shared timeline and the REAL speech report:

```
python -m score.cue_sheet --shots stories/<slug>/<pack>/shots.json --episode <n> --editorial stories/<slug>/<pack>/editorial_by_lang.json --vo-report <path to vo_tracks_report.json> --out stories/<slug>/<pack>/score/ep<n>/cue_sheet.json
```

- [ ] `--vo-report` can repeat (it is "append"). Pass one per language if the report is split.
- [ ] Do NOT use `--voice-windows` (FINAL_TEXT windows are permission only, rule 42).
- [ ] Stop on any error. Read every warning and report them to the owner.
- [ ] Check `total_s` in the cue sheet equals the picture length (reel 1: 72.833).
- [ ] Check `voice.coverage`, `voice.gaps`, `retention.rehook_window_s`, `retention.end_hook_window_s`.

### 4.2 Plan (write `score_plan.json`, no notes yet)
- [ ] Open `.claude/skills/score-reel/SKILL.md` section "score_plan.json (v1)" and copy its shape.
- [ ] Give every section a `why` in one plain sentence.
- [ ] Motifs only in voice gaps that are FREE in all languages (use `voice.union`).
- [ ] Hits land on impact frames (within 1 frame = 41.7 ms). Read the frame-exact times from the cue sheet.
- [ ] Any hit under voice is a LOW hit: `"band": "low"`, sub, kick, low drum or low brass below 250 Hz.
- [ ] Every hit and every god theme entry has a drop-out of 0.4 s (never more than 0.45 s).
- [ ] Only ONE elevation (`peak_at_s`) per reel. It is the loudest attack.
- [ ] A god theme (SHIVA, KALI, BRAHMA) enters in half feel after a drop-out. Never a drop.
- [ ] Re-hook (`rehook_at_s`) sits inside `retention.rehook_window_s`.
- [ ] The end sting sits after the last word (`at_s` >= `retention.last_speech_end_s`), tail 0.45 s or less.
- [ ] Sonic logo event at `at_s` 0.0.
- [ ] Tempo changes only at act changes. BPM must be in `tempo_candidates` for that act.
- [ ] Genre colour may change at a shot boundary inside an act only if the BPM stays the same (rule 45).
- [ ] Every cut has a plan transition (none, theme_handover, bed_continues, reverse_swell_to_cut, swell_to_cut, key_colour_on_downbeat, act_change).
- [ ] Plan covers exactly 0 to `total_s`.
- [ ] Busy roles (see bible `track_roles`) are gated in voice windows (`"voice_gated": true` on the section).

### 4.3 Plan check
- [ ] Run and fix every error. Never weaken a rule to pass.

```
python -m score.plan_check --plan <EP>/score_plan.json --cue-sheet <EP>/cue_sheet.json --bible stories/<slug>/music_bible.json
```

- [ ] Exit 0 = ok. Exit 1 = errors. Exit 2 = unreadable file.

### 4.4 Note writer (no CLI in the module; call the Python API)
- [ ] Run from the repo root:

```
python -c "import json; from score.note_writer import write_notes, write_midi; p=json.load(open('<EP>/score_plan.json')); c=json.load(open('<EP>/cue_sheet.json')); b=json.load(open('stories/<slug>/music_bible.json')); r=write_notes(p,c,b); print(r['ok'], r['errors'][:3], len(r['warnings'])); m=write_midi(r['tracks'],'<EP>/notes.mid',r['markers']); print(m['ok'], m['notes'])"
```

- [ ] Same input gives the same output (no random).
- [ ] Read every warning (for example HIT_FORCED_LOW). Report them.

### 4.5 Audition (M1 listening)
- [ ] Stock sounds are timing checks only. The owner rejected them as the M1 sound (2026-11-09).

```
python -m score.audition <EP>/audition --plan <EP>/score_plan.json --cue-sheet <EP>/cue_sheet.json --reel <reel mp4> --out-prefix <name>
```

- [ ] Add `--phone` for a 540 px phone copy.

### 4.6 Ableton build recipe
- [ ] Build the recipe JSON (checks the tool names against the owner's server).

```
python -m score.ableton_build --notes <EP>/notes.json --plan <EP>/score_plan.json --bible stories/<slug>/music_bible.json --out-dir <EP>/ableton
```

- [ ] Use the owner's AbletonMCP tools only. Read before you mutate; read back after.
- [ ] Clock mode: `set_tempo` 60. One beat = one second.
- [ ] One MIDI track per role. Real presets from the Ableton browser, not init patches.
- [ ] One clip per role (length = reel seconds), duplicated to the arrangement.
- [ ] MARKERS track: one empty, named clip per shot.
- [ ] Anything the server cannot do is written as MANUAL in the build log (for example automation points).

### 4.7 Export and stem
- [ ] Owner exports the WAV: 48 kHz, 24-bit, exact length (cue `total_samples`). No export tool exists in the MCP.
- [ ] Trim to `total_samples`. Never use mp3 for the final stem.

### 4.8 Gate D bridge
- [ ] Run the bridge. Exit 0 = all checks passed and the manifest is written.

```
python -m score.gate_d_bridge --cue-sheet <EP>/cue_sheet.json --stem <stem.wav> --voice <voice mix.wav> --out-manifest <manifest.json> --bpm 128
```

- [ ] Checks: 48 kHz, 24-bit or float, stereo, length within 2000 samples, bass mono under 200 Hz (side at most -20 dB), mono fold loss at most 3 dB, not silent.
- [ ] Presence: music 15 to 21.5 dB under the voice (median).

### 4.9 Build the reel with the score
- [ ] `director/build_final_reel.py` has a BGM slot (currently `None`). The manifest goes there.
- [ ] Check the build script's own help for the exact flag name before the run (not verified in this guide).
- [ ] Output = a new version folder (reel 1 next = `final_reel1_v5`). Never overwrite a finished version.
- [ ] Gate D checks pass on all three languages.

### 4.10 Owner gates
- [ ] M0 (bible): ONLY when the bible changes. Owner decides.
- [ ] M1 (plan + audition): owner approves the plan table and the Ableton audition before any final build.
- [ ] M2 (final listen): owner listens to the finished reel with picture and voice.

---

## 5. Timing facts

- The shared timeline (`editorial_by_lang.json`): each shot = the LARGEST need of all languages.
- Extra frames go at the END of a shot (last shot: at the START).
- Whole-beat rounding only inside BUILD and DROP non-final shots with a groove (reel 1: shots 3 and 4 at 128 BPM; shots 6, 7 and 8 at 176 BPM).
- Act-final shots and 60 BPM acts are NOT rounded. An act end off the grid is fine.
- Voice speed-up in the editorial step is at most 1.03x. The audio builder may use one atempo per shot up to 1.15 (rule 42).
- Reel 1 v4 shot lengths (s): 6, 5.375, 7.458, 8, 8.292, 7, 7.667, 9.042, 8, 6. Total 72.833 s = 1748 frames.
- Clock mode: 60 BPM, 1 beat = 1 s, so beat numbers equal seconds in Ableton.
- Frame = 1/24 s = 41.7 ms at 24 fps. The frame lock tolerance is one frame.
- Residual misses at the beat-rounded cuts are up to about 19 ms (reel 1). The music absorbs them.
- Shot timings move if a shot is extended. Recompute white-outs as "shot N + X".

---

## 6. Monetisation and copyright

- [ ] Original music only. Never a sample of a film or song recording (Coolie drew a claim for a sample).
- [ ] Ableton library samples and built-in instruments are fine. A fitting library vocal may replace a stand-in (rule 45 amendment).
- [ ] Use the library sound as a sound, never as an SFX (rule 45).
- [ ] Keep a `sample_log.json` per reel: every library item used, its track role, and its time.
- [ ] Never register the score with a distributor's Content ID system.
- [ ] One video with three language audio tracks (en, hi, mr). One score, one picture.
- [ ] Captions stay as they are (rule 46). Music does not change them.

---

## 7. Known limits and lessons

- The Ableton MCP has NO audio export tool. The owner exports, or the computer-use tool is granted for it.
- The Ableton MCP has no automation write. Automation points are written as MANUAL steps and logged.
- Presets must be real browser presets, not init patches. Reel 1 round 1 used init patches; round 2 replaces them.
- Stock-synth auditions are for timing checks only. The owner rejected them as the M1 sound (2026-11-09): build with built-in Ableton instruments and samples.
- The M1 gate was sent before the build; the owner then ordered the Ableton build first. Keep the order: build, then M1.
- Agents can be stopped by an app restart. Log one line per step so a restart does not lose work.
- Reviews: Haiku MEDIUM coders, Haiku HIGH reviewer, different agents. One re-review after fixes (rule 8). Stop when a round has no HIGH finding.
- Agents never commit, push, touch `ui/`, or call Colab, Flow, Opus or paid APIs.
- Read the tool output yourself. Do not trust an agent report.
- Never edit scripted code that has backslashes with a python heredoc (rule 20). Use the Edit tool.

---

## 8. Where things are (paths)

| What | Path |
| --- | --- |
| Skill (the spec) | `anime_studio_merge/.claude/skills/score-reel/SKILL.md` |
| Standing rules | `anime_studio_merge/blot.md` (rules 43-47) |
| Style study | `anime_studio_merge/research/STYLE_STUDY_Anirudh_Sai_2026-11-09.md` |
| Scoring system plan | `anime_studio_merge/research/SCORING_SYSTEM_PLAN_2026-11-09.md` |
| Bible style fix spec | `anime_studio_merge/research/BIBLE_STYLE_FIX_SPEC_2026-11-09.md` |
| Music needs from video | `anime_studio_merge/research/MUSIC_NEEDS_FROM_VIDEO_2026-11-09.md` |
| Handoff reel 1 to music | `anime_studio_merge/research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md` |
| Strict build checklist | `anime_studio_merge/research/SCORE_BUILD_CHECKLIST_STRICT_2026-11-09.md` |
| Ableton build log reel 1 | `anime_studio_merge/research/ABLETON_BUILD_LOG_REEL1_2026-11-09.md` |
| Music bible (story) | `anime_studio_merge/stories/kalika_puran_bhag1/music_bible.json` |
| Reel 1 score folder | `anime_studio_merge/stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/score/ep1/` |
| Reel 1 gate tables | `.../score/ep1/M0_table.md`, `.../score/ep1/M1_table.md` |
| Cue sheet / plan (reel 1) | `.../score/ep1/cue_sheet.json`, `.../score/ep1/score_plan.json` |
| Shared timeline | `anime_studio_merge/stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/editorial_by_lang.json` |
| Real speech report (v4) | `D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva/vo_v4/vo_tracks_report.json` |
| Final reels v4 (no music) | `D:/aai work/flow_outputs/anime_kalika_puran_bhag1/final_reel1_v4/export/` |
| Score code | `anime_studio_merge/score/` (cue_sheet.py, plan_check.py, note_writer.py, audition.py, ableton_build.py, gate_d_bridge.py) |
| Reel builder (BGM slot) | `anime_studio_merge/director/build_final_reel.py` |
| Project log (append only) | `D:/aai work/anime_studio/PROJECT_LOG.md` |

Log line for every step (run exactly, no backticks inside the text):

```
echo "$(date +%m-%d\ %H:%M) | <agent id> | <TYPE> | <files> | <result>" >> "D:/aai work/anime_studio/PROJECT_LOG.md"
```

TYPE: CMD, EDIT, TEST, DECISION, FAIL, AGENT-START, AGENT-DONE, REVIEW-START, REVIEW-DONE, OWNER.

AGENT-DONE
