A. CONFLICTS (implementation vs. research)

1. Font choice — research names Mukta as the primary Devanagari+Latin caption font, Anek for emphasis/hooks, and Noto Sans Devanagari only as fallback/QA reference (research:5-10). Our code locks NotoSansDevanagari-Bold.ttf for hi/mr and NotoSans-Bold.ttf for en (h3/gate_d_audio.py:37-45, h3/gate_d_audio.py:412-420, assets/fonts/README.md:6-9). Who is probably right: the owner decision stands for now (fonts are specified, nothing is downloaded); the research is unverified input and not a mandate to change code today. Risk if we do nothing: if Mukta shapes Devanagari+Latin mixes better, captions are suboptimal but not broken; switching later means a font swap plus re-QA.

2. Safe-area numbers — research: Meta ads guidance on 1080x1920 is top 269 / bottom 672 / sides 65 (14% / 35% / 6%), explicitly not an official Meta spec, and it urges configurable templates plus real-device previews (research:18). Ours: 1440x2560 with MarginL=160, MarginR=160, MarginV=467, nothing above y=360, hardcoded via CAPTION (imported at h3/gate_d_audio.py:21) and used at h3/gate_d_audio.py:46-49, 512-513, 471-480. Scaled, our top ≈360 matches 269·4/3, but our bottom margin (467) is far smaller than 672·4/3≈896 and our sides (160) exceed 65·4/3≈87. Who is probably right: research on making safe areas configurable per platform; owner numbers are the current spec. Risk if we do nothing: captions may collide with Reels/Shorts bottom UI and description overlays on organic feeds; one template fits no platform perfectly.

3. Wrapping / line estimation — research: never use text.length; use grapheme segmentation plus real pixel measurement of the loaded font, max 2 lines, with a fallback when a page cannot fit (research:32). Ours: split_cards splits on whitespace (h3/gate_d_audio.py:425); _estimate_lines measures sum(len(w)+1) * 46 px (h3/gate_d_audio.py:454-457); WrapStyle: 0 with no explicit line breaks, so libass wraps freely (h3/gate_d_audio.py:513, 533-535). Who is probably right: research. Risk if we do nothing: Devanagari words are mis-measured; libass may wrap to 3+ lines while we placed for 2, overflowing the safe area or covering faces.

4. Grapheme handling — research: zero broken matras/conjuncts; test माझं, कुठे, ॲप, र्क, क्ष, ज्ञ and Marathi ळ, ऱ (research:11, 35). Ours: Python str.split() and len() operate on codepoints; no grapheme segmentation, no glyph-coverage check (h3/gate_d_audio.py:425, 456, 412-420). Who is probably right: research. Risk if we do nothing: conjuncts/matras can be mis-measured or mis-wrapped; Marathi-specific glyphs may render as tofu if the bundled font lacks them (unverified).

5. Word timing source — research: forced alignment (WhisperX for Hindi; Marathi has no default aligner, benchmark separately; whisper-timestamped as alternative), validated against manual annotations, with confidence-based phrase fallback (research:23-27, 35). Ours: timings come from shot time ranges and ElevenLabs wav lengths; build_cards divides each card equally across words for \k (h3/gate_d_audio.py:443-450); Whisper is only a fallback for transcribing source videos (director/asr_transcribe.py:1). Owner decision: this is today's approach. Who is probably right: research for karaoke accuracy; owner for current scope (no ASR in the render path). Risk if we do nothing: \k highlight may be perceptually off-sync; no confidence fallback; Marathi alignment maturity unproven if we later add ASR timing.

6. SRT/VTT export — research: always ship UTF-8 SRT + WebVTT sidecars for YouTube (research:15, 40). Ours: only burned .ass; no SRT/VTT writers exist in h3/gate_d_audio.py. Who is probably right: research. Risk if we do nothing: YouTube uploads have no caption sidecar (accessibility/SEO); no clean subtitle track.

7. Mixed-script / Latin fallback inside one line — research: mixed scripts must not cause baseline shift or unexpected font substitution (research:35). Ours: one font per language, single style (h3/gate_d_audio.py:41-45, 511). A hi/mr line containing English words (or vice versa) is rendered with one font; libass fallback behavior with fontsdir is unverified. Who is probably right: research. Risk if we do nothing: mixed-script captions may substitute glyphs or shift baselines silently.

8. Languages — research: en/hi/mr supported, but no default Marathi WhisperX aligner (research:23). Ours: LANGUAGES = ("en","hi","mr") (h3/gate_d_audio.py:774). No conflict on support; conflict is alignment maturity for mr if ASR timing is ever added. Risk if we do nothing: Marathi word timings would be less reliable than Hindi under a future alignment path.

B. BUGS / GAPS IN CAPTION CODE (severity, file:line, why, one-line fix)

- high — h3/gate_d_audio.py:513, 533-535, 454-457 — WrapStyle: 0 and no explicit \N breaks let libass wrap with the real font, while placement uses a fixed 46 px/char estimate, so cards can wrap to more lines than estimated and overflow the safe area or cover faces. Fix: pre-wrap every card with real font pixel measurement, insert explicit \N line breaks, and place from the measured line count.
- high — h3/gate_d_audio.py:425, 456 — split_cards/_estimate_lines use Python str.split() and len() (codepoints), not graphemes; Devanagari conjuncts/matras (क्ष, ज्ञ, Marathi ळ/ऱ) are mis-measured and can be mis-wrapped. Fix: segment by grapheme clusters and measure each word's pixel width with the loaded font instead of len(w)*CAPTION_CHAR_PX.
- high — h3/gate_d_audio.py:566-569, 359 — burned captions depend on ffmpeg/libass HarfBuzz shaping for Devanagari; we never verify the ffmpeg build has libass with HarfBuzz/FriBiDi, so hi/mr could render broken matras silently. Fix: add a preflight QA render of a Devanagari test .ass and pixel-check the output (shaping correctness unverified).
- medium — h3/gate_d_audio.py:412-420 — ensure_font checks file existence only, not glyph coverage for माझं, कुठे, ॲप, क्ष, ज्ञ, ळ, ऱ; missing glyphs would render as tofu. Fix: glyph-coverage QA with fontTools against the test corpus (font coverage unverified).
- medium — h3/gate_d_audio.py:41-45, 511 — one font per language with no in-line fallback; mixed-script lines risk unexpected substitution/baseline shift because libass gets a single Fontname. Fix: validate script-language match at caption time and/or declare a fallback font chain (libass fallback behavior with fontsdir unverified).
- medium — h3/gate_d_audio.py:443-450 — build_cards divides each card equally across words for \k, so karaoke timing is synthetic, not aligned to spoken word boundaries; no confidence-based phrase fallback. Fix: use ElevenLabs word alignment when available, else phrase-level timing with a low-confidence flag.
- medium — h3/gate_d_audio.py (no srt/vtt functions) — no SRT/WebVTT sidecar export per language, so YouTube gets burned-in captions only. Fix: add SRT and VTT writers from the same cues.
- low — h3/gate_d_audio.py:447, 460-461 — CAPTION_LINE_PX=110 is decoupled from the 84 px font and real font metrics, so vertical placement/face-avoidance can be off by a line. Fix: derive line height from font metrics (actual metrics unverified).
- low — h3/gate_d_audio.py:476-480, 531-532 — place_card gives up and build_ass hard-raises when no clear spot exists, instead of falling back (shrink/split/reposition) as research requires when a page cannot fit. Fix: implement a fallback path rather than raising on overflow.

C. REEL COMPONENTS IMPLEMENTABLE NOW (no Remotion; ASS/libass + ffmpeg + Python)

| Component | What it needs | Effort | Viewer value | Languages |
|---|---|---|---|---|
| Active-word karaoke highlight (\k tags) | Word timestamps; existing skeleton in build_cards/build_ass (h3/gate_d_audio.py:433-451, 519-536) | M | Read-along highlight aids comprehension | en, hi, mr |
| Safe-area templates per platform | Template JSON (Reels/Shorts/YouTube) + parameterize place_card (h3/gate_d_audio.py:468-480); keep 160/160/467/y>=360 as the Reels template | S | Captions clear platform UI and face zones | en, hi, mr |
| Grapheme-aware wrapping + max-2-line fit with font measurement | Grapheme segmentation + Pillow (libraqm if available, else fontTools) measuring the actual TTF | L | No broken Devanagari wraps; fits safe area | hi, mr critical; en too |
| Per-language font selection with Latin fallback inside one line | Font-pair config + per-run script detection; libass fallback behavior unverified | M | Correct glyphs for Hinglish-ish lines | hi, mr |
| SRT/WebVTT sidecar export per language | Writers for .srt and .vtt from the same cues | S | YouTube caption track; accessibility/SEO | en, hi, mr |
| Caption contact sheet / reference-frame QA | ffmpeg argv to render one frame per card per language; compare to reference PNG hashes (MP4 hashes unreliable per research:35) | M | Catches broken shaping/overflow before publish | hi, mr critical |
| Hook-word emphasis | Hook-word list + emphasis style (size/color/Anek variant) | S | Hook salience | en, hi, mr |
| Timing from ElevenLabs alignment instead of Whisper | ElevenLabs word-alignment output (availability unverified) | M | Accurate karaoke sync | en, hi, mr |
| Confidence-based fallback to phrase timing | Confidence scores from alignment | S/M | Avoids wrong highlight when alignment is poor | en, hi, mr |

D. WHAT NOT TO ADOPT (and why)

- Remotion/Chromium (research R1/R2): owner locked "no Remotion today" and the code never downloads or renders; R2 is immature (5 commits, 8 stars; research:22). The research claim that Remotion is preferred for layout/animation (research:31) is unverified and conflicts with our ASS/libass + ffmpeg path. Do not adopt.
- WhisperX (research R3): no default Marathi aligner, and forced alignment does not correct a wrong transcript (research:27). Not in our render path; owner permits Whisper only as a fallback for transcribing source videos. Do not trust as a timing source yet; benchmark on Hindi/Marathi samples first if ever adopted.
- whisper-timestamped (research R4): unbenchmarked for our hi/mr samples. Do not adopt without a same-sample benchmark.
- SRT/VTT as the Reels caption master: SRT has no styling and VTT is limited (research:15). Burned .ass remains the Reels master; sidecars are supplementary for YouTube only.
- Single-weight display fonts (e.g., Yatra One) as the main caption family (research:9). Do not adopt.
- YouTube auto captions for hi/mr without QA (research:17). Do not trust.
- Runtime Google Fonts downloads (research:38): violates the owner rule that the code never downloads anything.

E. ORDERED PLAN (8 steps, smallest first)

1. Add SRT and WebVTT exporters from existing cues (S).
2. Parameterize safe-area templates (Reels/Shorts/YouTube); keep 160/160/467/y>=360 as the Reels template (S).
3. Glyph-coverage QA of bundled fonts vs माझं, कुठे, ॲप, क्ष, ज्ञ, ळ, ऱ with fontTools (S).
4. Add a hook-word emphasis style variant (S).
5. Replace len()*46 px estimation with grapheme segmentation + real font measurement (Pillow; libraqm if present, else fontTools), explicit \N wrapping, max 2 lines (M).
6. Add contact-sheet / reference-frame QA argv: burn one frame per card per language, compare to reference PNG hashes (M).
7. Wire ElevenLabs word alignment into \k with confidence-based phrase fallback (L).
8. Mixed-script Latin fallback run selection + font-pairing review (Mukta/Anek vs locked Noto only if the owner reopens the font decision) (L).

FINAL:
- The owner's font (Noto) and safe-area (160/160/467, y>=360) calls stand; the research is unverified input, not a reason to change code today.
- Real defects to fix first: codepoint-based wrapping/measurement, unverified libass HarfBuzz shaping for Devanagari, no glyph-coverage check, no SRT/VTT export, and synthetic equal-split \k timing.
- Do not add Remotion or WhisperX; both outrun or violate current owner constraints.
- ffmpeg/libass Devanagari shaping is the biggest silent-risk item; QA it before burning hi/mr reels.
- Execution order: sidecars → templates → glyph QA → emphasis → measured wrapping → contact-sheet QA → alignment \k → font-pairing review.