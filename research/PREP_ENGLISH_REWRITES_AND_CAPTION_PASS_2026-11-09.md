# PREPARED FOR OWNER APPROVAL (2026-11-09): English line rewrites + the caption pass
Nothing here is applied. No ElevenLabs call, no Colab call, no download was made to prepare it.

## PART A. English voice lines (check result first)
Offline speech recognition on the 18 raw English clips, the 10 packed per-shot tracks and the FINISHED mixed reel: every word of every line is present, each line sits inside its own shot and ends before the cut. The audio is NOT cut.
What reads badly is the wording (fragments and literal translations from Hindi). Only 3 of the 18 lines need a change; the rest are fine and stay.

| Line | Now | Proposed | Why |
|---|---|---|---|
| SHOT-005 N | Then another came from his mind, golden yellow. | Then another was born of his mind, golden. | "another" what? "born" ties it to the daughter just born; 42 chars (was 47), fits |
| SHOT-007 D1 (Kama) | Let's see if it's true. | Let me test those words. | says what is tested; 24 chars (was 23) |
| SHOT-007 N | He aimed at Brahma's own court. Every mind slipped. | He aimed at Brahma's own court. Every mind wavered. | "mind slipped" is a literal copy of the Hindi idiom (मन डोला) and means nothing in English |
Cost if approved: about 3 lines x 15 to 25 credits (ElevenLabs), then the same three tools already built: regenerate only these, `build_vo_tracks.py`, `build_final_reel.py` (shot 7 packing is at tempo 1.12 now, the new text stays inside the 1.15 limit: checked by arithmetic, to be measured after generation).
Kept as they are (read fine): 001 N, 002 N, 003 (all three), 004 N, 005 D1, 006 D1 and N, 008 (both), 009 (both), 010 (both).

## PART B. The caption pass
### B1. What you already specified (sources)
1. Owner master prompt V4, section 5 (research/OWNER_MASTER_PROMPT_V4_2026-11-07.txt): captions are SUBTITLES of the speech; .ass via libass/HarfBuzz; bundled OFL font NotoSansDevanagari-Bold; at most 6 words per card; high-contrast ACTIVE-word highlight; symmetric margins MarginL = MarginR = 160, Alignment 2; no content above y = 360; never cover character faces; 1440 x 2560 play resolution.
2. Decided 2026-11-07 (CHECKLIST 9, core/shot_table_spec CAPTION): inside the Instagram Reels + YouTube Shorts safe zone, bottom margin 896 px (35 percent), top 360, sides 160; core.json safe_zone_templates: reels caption band 0.50 to 0.65, shorts 0.52 to 0.68, youtube 0.80 to 0.92.
3. Your pasted font research (research/CAPTION_FONTS_RESEARCH_2026-11-07.md, marked "not yet verified"): Reels = Mukta ExtraBold or Anek Bold, max 2 lines, word-level timing, ACTIVE word yellow / others white, dark outline or shadow; YouTube long form = phrase timing, Mukta/Hind Medium-SemiBold, separate SRT/VTT; Shorts = Reels style, karaoke used selectively. Final recommendation there: Mukta + Anek + Noto fallback.
4. Built already in the repo (CHECKLIST 9.1 to 9.8): SRT/VTT sidecars, glyph-coverage QA (माझं कुठे ॲप क्ष ज्ञ ळ ऱ), hook-word emphasis, real font measurement + grapheme wrapping + max 2 lines, contact sheet QA, word-timing parser with phrase fallback, ffmpeg libass preflight.
5. Fonts on disk: Inter (Latin), Noto Sans Devanagari VARIABLE, Rajdhani (Medium/SemiBold/Bold), Yatra One. NOT on disk: Mukta, Anek Devanagari (would need a download, only with your OK).

### B2. What the current reels do against that (measured on kalika_reel1_*.mp4 / .ass)
| Rule | Current | Verdict |
|---|---|---|
| Captions are subtitles of the speech | only 10 writer-made TITLE CARDS (one per shot, 2 to 4 s each); the spoken words are not captioned at all | FAILS: this is why English cards read like cut fragments ("Struck by his own creation") |
| Size | engine default 34 px at 1080 wide (about 24 px glyph on the 768 px reel): too small for a phone | FAILS legibility (typical Reels text is about 55 to 65 px at 1080) |
| Weight | the Devanagari font is the VARIABLE file; libass shows it at Regular weight (thin) | FAILS "Bold" |
| Active-word highlight | cards use a progressive karaoke fill, not word-by-word timing from the voice | PARTIAL |
| Never cover faces | no face boxes are given, text sits on Kali's face at 1.5 s | FAILS |
| Safe zone | bottom margin 896, sides 160, nothing above 360 | OK |
| Fonts | Noto Sans Devanagari / Inter fallback style; Mukta/Anek not used | differs from the research |
| Sidecars | SRT/VTT code exists, not produced in this build | MISSING |
| Language texts | same 10 cards translated en/hi/mr; Hindi and Marathi read natural, English cards are fragments | English worst |

### B3. Plan (backend only, no UI), in order
1. Caption text source: the SPOKEN lines of each language, exactly as in shots.json, split into cards of at most 6 words, 2 lines max (the engine already does this). Word timing from the real voice tracks (the packed per-shot WAVs we have) with the local offline recogniser for English and phrase fallback for Hindi/Marathi (no aligner for mr, per your research); no API call.
2. Style from the Reels template: Alignment 2, MarginL/R 160, band 0.50 to 0.65, size about 60 px at 1080 (owner to confirm), bold, outline about 8 percent, ACTIVE word yellow and the rest white (per the research), colours checked for contrast by the engine.
3. Face avoidance: get face boxes from the keyframes (or per-shot detection) and pass them to the engine, which already raises a caption that would cover a face.
4. Bold Devanagari: use a STATIC bold file (generate NotoSansDevanagari-Bold.ttf from the variable font with fontTools: a local instancer, no download) or Mukta/Anek if you approve the download.
5. Outputs per language: burned reel (Instagram/Shorts) + .srt + .vtt (YouTube), contact sheet of 12 frames per language for your review on a phone.
6. Keep the 10 title cards only if you want them as a separate on-screen title style (see question 1).
7. Tests: size floor, bold weight present, no face overlap, words per card, glyph coverage, sidecars equal to the cues. All offline.

### B4. Questions (only what is missing)
1. Content: should the captions be the spoken words (as the master prompt says), with the 10 title cards removed? Or both (spoken words at the bottom, the 10 cards as a separate title style at the top)? If you supply your own caption text, where is it?
2. Font: master prompt says Noto Sans Devanagari Bold; the research says Mukta ExtraBold / Anek Bold. Final choice? (Mukta/Anek need a download, I will not do it without your OK.)
3. Size: is about 60 px at 1080 wide right for Instagram + Shorts, or another number?
4. Colours: active word yellow and the rest white with a dark outline (research), or your story palette (deva_neon: Rani Pink / Tiger Amber)? Exact hex if you have one.
5. Position: use the Reels band 0.50 to 0.65 for both Instagram and Shorts, or two separate files (Reels and Shorts bands differ by 2 percent)?
6. English wording: approve the 3 line rewrites in Part A (about 60 credits) or leave the English voice as it is.
