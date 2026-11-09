# What the music needs from the video/edit session (music session, 2026-11-09)

1. ONE shared timeline for en/hi/mr (one YouTube video with 3 audio tracks; one score). Each shot length = the LARGEST need of the three languages.
2. Rounding of each shot's extra time:
   - whole beats only for shots 3, 4 (BUILD, 128 BPM: 1 beat = 0.469 s) and 6, 7, 8 (DROP, 176 BPM: 1 beat = 0.341 s);
   - no rounding for act-final shots 2, 5, 9, 10 and for the 60 BPM acts (the next act starts a new tempo grid);
   - capped by each clip's spare footage; voice speed-up at most 1.03x.
3. File: editorial_by_lang.json (same values for all languages under the shared policy). Missing file = build exactly as v3.
4. Freeze that file before music gate M1. If it changes after M1, tell the music session (re-run, no re-compose).
5. Shot 10 extra frames go at its START: tell the music session the exact frame count.
6. Music plugs into build_final_reel.py BGM slot (gd.build_mix_filter(sfx, "vo_full", None, t) -> manifest from score/gate_d_bridge.py). Same music file for all three languages.
7. Do not edit anything under score/, the music bible or .claude/skills/score-reel/. Blot RULE 45 = music style decisions; caption rule = RULE 46.
