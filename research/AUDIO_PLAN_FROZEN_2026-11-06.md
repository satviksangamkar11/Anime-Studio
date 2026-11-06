# Audio plan, FROZEN 2026-11-06 (owner approved the direction; Nemotron Ultra reviewed; Claude corrected the review)

Owner rules: all sound comes from the video model (no ElevenLabs, no SFX library, no paid audio); NO separate audio test render while rendering; clips carry sound effects only, no vocals (dialogue is acceptable: the owner removes vocals with his own tools); the sound must be consistent; background score kept only if it can be made consistent, otherwise removed (the owner adds the music separately). Everything else in the pipeline is frozen.

## Frozen decisions
1. **Music: removed.** Independently generated clips cannot share one score (reviewer and logic agree: no shared audio state between renders). Every shot says `non_diegetic_music: N/A` (the official section stays, with that value). The owner lays his own music over the finished reel.
2. **Sound effects: from the model, written per shot** in `overall_soundscape`, in POSITIVE wording (the H3 prompt rules avoid negations): the soundscape starts with the fixed words "Sound effects only:" and then lists the concrete effects (steps, cloth, wind, water, splash, impact). Nemotron proposed "No music, no score..." wording; NOT adopted because negations are against the model's prompting rules (our linter warns on them).
3. **Consistency of effects: one fixed sound-bed phrase per location** (registry field `sound_beds`: location id -> phrase of 12 words or fewer, same casing and punctuation), placed right after "Sound effects only:" in every shot of that location. Limit (reviewer, accepted): the bed is statistically similar, never sample-identical between clips; fine for effects.
4. **Dialogue: allowed as is.** If a vocal appears the owner removes it with his tool. The prompt keeps the mouth/lip rule as in SPEC.
5. **Loudness: gain-match every clip before the join.** Measured on our T0 clips (local ffmpeg ebur128, no render): arm A -23.7 and -21.1 LUFS, arm C -24.3 and -23.2, arm D (start/end frames only) -12.3 and -10.2: up to 14 dB apart between clips, so matching is required. Method (corrected from the review): measure integrated loudness per clip (ffmpeg loudnorm pass 1 or ebur128), then apply a plain linear gain to reach -16 LUFS with a true-peak limiter at -1.5 dB (`volume=<gain>dB,alimiter=limit=0.84`); NOT the dynamic `loudnorm` second pass (the clips are only 5 s: its loudness-range logic is unreliable on such short audio and it can change dynamics differently per clip). The 5 ms fades (160 samples at the clips' 32 kHz) are applied AFTER the gain, at every cut. The measured values are written to `loudness.json` in the build folder for audit.
6. **QA without a separate test:** the audio is listened to on the REAL clips as part of the normal clip QA (free): every clip, not only the first (reviewer point accepted: drift can appear at clip 4). If music or vocals leak in, change the shared template once (the "Sound effects only:" prefix or the bed phrase) for the affected location and re-render only those clips if the owner agrees; never patch single shots.
7. **Cost:** audio costs nothing beyond the video render.

## Rejected from the review (reason)
- "Request 5.20 s renders for fade handles": clip length is fixed by the frame lattice (17n+5 frames); 5 ms fades need no handle.
- "Compliance rises from 60% to over 95%": no source, not used.
- "Dialogue ducking sentence obeyed about 70%": no source, not used; the owner removes vocals in post anyway.
- Vocal tools do not separate effects from music (reviewer, accepted): so prevention in the prompt plus QA is the plan, not post separation.

## What changes in the code (task C8, Dots codes it, Haiku reviews)
Registry `sound_beds`; compiler puts "Sound effects only: <bed> <effects>" in the soundscape; linter SD-03 (soundscape starts with "Sound effects only:" and with the location's bed when one is defined) next to SD-01/SD-02; `assemble_reel.py`: `loudness_plan(measured)` (pure gain computation, target -16 LUFS, limiter), the audio chain gain -> 5 ms fades, `loudness.json` writer; tests. The model audio is kept in the join.
