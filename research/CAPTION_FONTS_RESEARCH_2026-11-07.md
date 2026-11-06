# Caption + font research (owner-supplied, 2026-11-07; condensed copy, facts kept, links and sample JSON dropped)
Source: owner's pasted report "Hindi, Marathi and English caption fonts for Instagram Reels and YouTube" (research date 7 Nov 2026). Not yet verified by us. Treat as input, check before adopting.

## 1. Font shortlist (all OFL 1.1 unless a licence file says otherwise; keep notices when bundling)
- Mukta: best overall, humanist, Devanagari+Latin, 7 weights (use 400-800). Primary caption font.
- Anek Devanagari: variable weight and width axes (8 weights x 5 widths); kinetic/emphasis, hooks.
- Noto Sans Devanagari: fallback + QA reference for Devanagari rendering.
- Baloo 2: rounded, 5 weights; comedy/UGC. Hind: 5 weights, restrained, long YouTube subtitles.
- Others to test: Biryani (7 weights), Kalam (Light/Regular/Bold, handwritten), Yatra One (single weight, titles), Sarpanch (6 weights Regular-Black, wide, headlines only). Do not use single-weight display fonts as main caption family.
- Pairings: Hindi/Marathi educational = Mukta + Anek; comedy = Baloo 2 + Anek (Hindi) or Yatra One (Marathi); documentary = Hind + Mukta; cinematic = Mukta + Yatra One titles; motivational = Mukta + Sarpanch/Anek.
- Caveat: test real font files and the shaping engine with माझं, कुठे, ॲप, र्क, क्ष, ज्ञ, and Marathi ळ, ऱ.

## 2. Platform design
- Reels: 1080x1920, Mukta ExtraBold or Anek Bold, max 2 lines, word-level timing, active word yellow / others white, dark outline or shadow, keep above the lower UI controls.
- YouTube long form: phrase-level timing, Mukta/Hind Medium-SemiBold, 1-2 lines, subtle outline/background, no constant bouncing; ship separate UTF-8 SRT/WebVTT (SRT has no styling, VTT limited).
- Shorts: Reels style as base, karaoke highlight used selectively, avoid the Shorts buttons/description overlay.
- YouTube auto captions support Hindi and Marathi but need checking.
- Safe area: the proposed x=72, maxWidth=936, bottom=1500 is NOT an official Meta spec. Meta Reels ADS guidance: about 14% top, 35% bottom, 6% each side = on 1080x1920: top 269, bottom 672, left/right 65, usable 950x979 px. Ads guidance only; organic Reels differ; use configurable safe-area templates and real-device previews.

## 3. Repositories reviewed (snapshot 7 Nov 2026)
- R1 Remotion Skills (official agent skills; `npx skills add remotion-dev/skills`, `npx remotion skills add`): safest foundation.
- R2 Remotion Captions Kit (MIT, v0.2.0, 5 commits, 8 stars): KaraokeFill, KineticSlam, PillKaraoke, WeightShift, NeonGlow, EditorialEmphasis, sentence-aware pagination. Immature: fork/vendor and pin, test Hindi/Marathi yourself.
- R3 WhisperX (BSD-2): transcription + forced alignment + diarization. Default Hindi aligner theainerd/Wav2Vec2-large-xlsr-hindi exists; NO default Marathi (mr) aligner found.
- R4 whisper-timestamped (MIT): word timestamps via DTW on cross-attention + confidence; no language-specific aligner needed. Benchmark both on the same recorded Hindi/Marathi samples.
- R5 Capite (MIT, 27 styles, faster-whisper, exports MP4/SRT/VTT/ASS), R6 Captioneer (MIT, 14 styles, @remotion/captions format): compare R2 vs R6 on one Devanagari corpus; neither proven on Marathi.
- R7 word-highlight example (MIT-0), R8 FFmpeg skill (42 tools, FFmpeg >= 6.1), R9 Claude Remotion skill (MIT), R10a/b ASS karaoke templates (CC0 / MIT): references only.
- Forced alignment matches supplied text to audio; it does not correct a wrong transcript. Fix the transcript before trusting word timings.

## 4. Rendering architecture proposed
Audio/video -> WhisperX / whisper-timestamped (word timestamps + confidence) -> Python caption prep (sentences, proofreading, timing) -> caption-engine JSON (fonts, pages, themes, timings, safe area, language, confidence, fallback phrase timing) -> Remotion/Chromium (Devanagari shaping, animation, layout) -> FFmpeg (encode, mux, subtitle packaging) -> Instagram MP4 burned in; YouTube MP4 + separate SRT/VTT.
- HarfBuzz does the Indic shaping. Pillow CAN do Devanagari if built with libraqm (HarfBuzz+FriBiDi). FFmpeg drawtext CAN shape with a HarfBuzz/FriBiDi build. They are still not preferred for animation/word highlight; Remotion preferred for layout and animation.
- Wrapping: do not use text.length. Use Intl.Segmenter graphemes + real pixel measurement of the loaded font in Chromium + max 2 lines + per-platform safe area + fallback when a page cannot fit.

## 5. QA acceptance (refined)
Devanagari shaping: zero broken matras/conjuncts/missing glyphs. Marathi forms ळ ॲ ऱ correct. Mixed scripts: no baseline shift or unexpected font substitution. Wrapping: no grapheme splits, max 2 lines. Safe area: all caption boxes inside the template. Word timing: measure vs manually annotated recordings, report median and 90th percentile error. Page transitions: no old+new captions at once. Fallback: missing glyph or low timing confidence logs a fallback. Determinism: compare fixed reference PNG frames (MP4 hashes are not reliable across encoders). Long sentences: no overflow, configurable minimum page duration. Preview: contact sheet with one image per page.

## 6. Workflow and licences
- Remotion project, `@remotion/captions`, `@remotion/fonts`, bundle fonts locally (public/fonts/...), do not download Google Fonts at render time.
- CLI should expose: target (Reels burned-in animated / YouTube clean subtitles / Shorts animated), language, font family+weight, position + safe-area template, word vs phrase timing; always export .srt and .vtt for YouTube.
- Licences: OFL fonts ok to bundle, not to sell alone. Remotion free for individuals and companies up to 3 employees, paid above (check current terms). FFmpeg LGPL/GPL depends on build. WhisperX BSD-2, whisper-timestamped MIT.
- Final recommendation: fonts Mukta + Anek + Noto fallback; WhisperX for Hindi, Marathi alignment benchmarked separately; Remotion + React animation; FFmpeg final encode; exports Instagram MP4, YouTube MP4 + SRT + VTT; fixed Hindi/Marathi/mixed test corpus with reference-frame comparison. Build two presets first: KaraokeFill (Reels) and Cinematic (YouTube); test on real phones.
