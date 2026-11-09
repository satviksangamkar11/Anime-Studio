## 1. Problems by stage

- **Script and voice readiness — root cause: text windows were treated as evidence that speech would fit.** The 2026-11-08 audit found 20 lines above its words-per-second limit; later measurements showed that words per second still failed to predict real delivery speed. The lessons report says **19 of 32** measured clips exceeded their slots, by up to **2.6×**. Cost: late script edits, timing work, and unusable voice takes. See [MISTAKES_AND_LESSONS.md](</D:/aai work/anime_studio_merge/MISTAKES_AND_LESSONS.md>) (Q6, V9, W19) and [AUDIT_2026-11-08_REEL1.md](</D:/aai work/anime_studio_merge/docs/AUDIT_2026-11-08_REEL1.md>).

- **Video timing and editorial — root cause: clips were rendered before final voice timing was known.** Reel 1 needed per-shot editorial extensions after the renders. The handoff records **70.0 → 72.833 seconds** and extensions of up to 25 frames. They used spare clip frames, preserving the old shot content, but leave little room for future timing changes. Cost: extra planning and a constrained edit; if voice needs exceed available frames, the choices become speed-up, text changes, or another render. See [HANDOFF_REEL1_TO_MUSIC_2026-11-09.md](</D:/aai work/anime_studio_merge/research/HANDOFF_REEL1_TO_MUSIC_2026-11-09.md>) and [editorial_by_lang.py](</D:/aai work/anime_studio_merge/director/editorial_by_lang.py>).

- **Voice fitting — root cause: several timing sources coexist.** `voice_cast.py` can fit to scripted or `FINAL_TEXT_v2.json` windows; `build_vo_tracks.py` packs lines into the shot’s editorial duration; the final reel builder reads `editorial_by_lang.json`. Those are different timing contracts. Cost: a clip can pass one fit check and overflow the actual cut. The lessons document reports exactly this earlier: **14 of 54** lines exceeded the cut by up to **1.46 seconds** because windows were sized to rendered-clip length. See [voice_cast.py](</D:/aai work/anime_studio_merge/director/voice_cast.py>), [build_vo_tracks.py](</D:/aai work/anime_studio_merge/director/build_vo_tracks.py>) and [MISTAKES_AND_LESSONS.md](</D:/aai work/anime_studio_merge/MISTAKES_AND_LESSONS.md>) (W19).

- **Assembly, captions, and music — root cause: downstream assets depend on the final shared timeline.** Captions and music cues must use the measured voice timings and final cut lengths. The handoff says the v3 cue sheet must be rebuilt for v4, while the v4 captions already use measured voice timings. Cost: stale cues or captions if either is built from the earlier timeline. See the Reel 1 handoff and [build_final_reel.py](</D:/aai work/anime_studio_merge/director/build_final_reel.py>).

- **Readiness gates — root cause: checks were split across writer, H3, voice, and render stages.** The earlier audit found that writer checks could pass while H3 timing/seam checks still made a reel unrenderable. Fixes reduced the Reel 1 timing/seam/mouth/sound lint errors from 73 to 0, but the old audit also notes unbuilt live QC and render integration. Cost: late blockers and expensive work reaching an incomplete gate. See [AUDIT_2026-11-08_REEL1.md](</D:/aai work/anime_studio_merge/docs/AUDIT_2026-11-08_REEL1.md>) and [PIPELINE_AUDIT_2026-11-07.md](</D:/aai work/anime_studio_merge/docs/PIPELINE_AUDIT_2026-11-07.md>).

## 2. Order problems

- **Video render ran before final measured dialogue duration.** That forced editorial extensions to be planned afterward from whatever spare frames the rendered clips had.
- **Voice-slot checks ran against scripted or clip durations before the assembler’s editorial cut was authoritative.** The lessons explicitly record both the clip-versus-cut mismatch and the later measured overruns.
- **Music cueing followed a timeline change without rebuilding the cue sheet.** The handoff calls out that its cue sheet still used v3 lengths.
- **Final assembly must follow all three locked inputs:** final editorial timeline, accepted voice tracks, and final clips. Captions and score cues should follow that same timeline.

## 3. Recommended stage sequence

| Stage | Handoff contract | Gate before next stage |
|---|---|---|
| Story and script | `SOURCE.md` → versioned pack with final per-language lines, speakers, and text hashes | Independent source-fidelity review; language and speaking-rate checks; H3 timing/lint checks |
| Voice casting and generation | Cast file + accepted raw voice clips + measured-duration manifest | Every speaker/language resolved; clips decode; owner approves listening/pronunciation; all takes have stable IDs and hashes |
| Timeline planning | Measured voice manifest + clip frame capacity + beat choices → one shared `editorial_by_lang.json` | All languages fit the same frame timeline; each extension fits available head/tail frames; no unresolved speed-up or overflow |
| H3 preparation and video render | H3 story carrying that timeline, plus keyframes and prompts | Pre-render lint and prompt gates pass; rendered clip frame counts cover final trim windows; rendered clip manifest matches source/timeline hashes |
| Voice-track build and assembly | Per-shot VO tracks + final clips + timing manifest → language reels | Gate D fit, SFX/VO mix, caption timing and final loudness/QC pass |
| Music and delivery | Final shared timeline + final video-only picture + cue sheet + score manifest | Cues align to locked frame positions; licensing/format and final playback checks pass |

This puts dialogue audio before video timing. Any model-generated SFX remain a video-stage output, so their QA follows the render.

## 4. Architectural changes, ranked

1. **Make one versioned timeline manifest authoritative.** Include frame rate, per-shot editorial in/out frames, measured VO line windows, spare-frame limits, language set, and hashes of script, voices, keyframes, and clips. Make every stage consume it; reject stale inputs.
2. **Move measured-voice planning before render.** Render readiness should require an approved measured-duration manifest and a feasible timeline. Stop with a clear blocker if any language cannot fit the available frames.
3. **Unify voice fit calculations.** Replace independent `voice_cast`, `build_vo_tracks`, and Gate D slot interpretations with one fit report based on the assembler’s final cut windows. Report natural-speed fit, permitted tempo, and hard overflow in the same units.
4. **Make gates dependency-aware.** The H3 controller currently orders lint/render/QC/Gate D, but that list does not encode the prerequisite that dialogue durations and editorial timing must be frozen before video allocation.
5. **Bind downstream assets to timeline hashes.** Caption files and music cue sheets should refuse to build—or be marked stale—when their source timeline hash differs from the reel’s.

## 5. Likely missed

- **The docs and log disagree about what is current.** The Nov. 7 audit describes a pipeline with no production render; the Nov. 9 handoff says Reel 1 v4 is finished and only music remains. The voice-system design says nothing has been generated yet, which conflicts with that handoff’s completed voice tracks. Treat the dated handoff as the Reel 1 status source and reconcile the other documents before using them as run instructions.
- **The merge workspace log is stale.** Its `NOW` block is dated Nov. 7 and the available log tail has no Nov. 9 Reel 1 entries, so it cannot establish the latest execution order. I did not append the requested review entry because you specified read-only.
- **Requested path mismatch:** `director/build_h3_batch.py` is absent from this merge workspace, so I could not review it here. This audit covers the named render controller instead.

**First fix:** make measured voice durations and the shared editorial timeline prerequisites for rendering, then enforce those prerequisites with hashes and fail-closed gates.