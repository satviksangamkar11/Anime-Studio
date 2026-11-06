

**A. CONFLICTS**  
1. **Font choice** – research recommends Mukta (best overall) with Anek for emphasis; our code uses Noto Sans Devanagari as primary for hi/mr (`gate_d_audio.py:37-45`). The owner explicitly chose Noto in the master prompt, so the owner is probably right. Risk: if Noto lacks proper Marathi conjuncts (ळ, Edition), but the owner supplies the font and can change it later.  
2. **Safe‑area numbers** – research gives Meta Reels ads guidance for 1080×1920 (top 269, bottom 672, sides 65) while our 1440×2560 canvas uses MarginL=160, MarginR=160, MarginV=467, top y=360 (`gate_d_audio.py:496-516`, `assets/fonts/README.md:15-16`). The owner’s numbers are explicit and for a different resolution; owner is probably right. Risk: our bottom margin (18 % unsafe) is less conservative than the research’s 35 %, possibly covering UI elements – but the owner may have tested it.  
3. **Wrapping** – research says use grapheme‑aware measurement, max 2 lines. Our `_estimate_lines` uses a fixed 46 px per character and no max‑line enforcement (`gate_d_audio.py:454-457`, `split_cards` at 423-430). Research is probably right. Risk: captions may overflow or wrap to 3+ lines, hurting readability.  
4. **Word‑timing source** – research recommends forced‑alignment (WhisperX/whisper‑timestamped); we divide shot time ranges equally among words (`gate_d_audio.py:423-451`). The owner decided to use shot ranges + ElevenLabs wav lengths for now. Research is probably right for accuracy, but we follow the owner. Risk: captions may not sync with speech; acceptable for the current phase.  
5. **SRT/VTT export** – research says ship separate UTF‑8 SRT/WebVTT for YouTube. Our code only builds burned‑in `.ass` (`gate_d_audio.py:519-544`). Research is probably right. Risk: no separate subtitle files for YouTube, only burned‑in captions.  
6. **Grapheme handling** – research says use `Intl.Segmenter`; we use Python `len`/`split` (`gate_d_audio.py:423-430`). Research is probably right. Risk: conjuncts like र्क may be split incorrectly, but impact is low if text is pre‑segmented into words.

**B. BUGS or gaps**  
- **Medium** – `_estimate_lines` uses an average glyph advance (46 px) without real font metrics, so the line‑count estimate and caption placement can be wrong (`gate_d_audio.py:454-457`). Fix: measure actual widths with Pillow + libraqm or fontTools.  
- **Medium** – `build_cards` divides cue time equally among words, producing inaccurate karaoke `\k` timing (`gate_d_audio.py:423-451`). Fix: integrate ElevenLabs word‑level alignment or use wav length to distribute time non‑uniformly.  
- **Medium** – No max‑2‑line enforcement; a 6‑word card can wrap to 3+ lines, violating the research’s guidance and hurting readability (`gate_d_audio.py:423-430`, `place_card` at 468-480). Fix: after wrapping, check line count and re‑split or adjust font size.  
- **Low** – No per‑line font fallback for mixed Devanagari‑Latin text; libass may substitute fonts poorly (`gate_d_audio.py:495-516`, `build_ass` at 519-536). Fix: detect Latin runs and insert `\fn` switches to the Latin font.  
- **Low** – Missing SRT/WebVTT export (`gate_d_audio.py:519-544`). Fix: add a function to write SRT/VTT from the cue list.  
- **Low** – No QA contact sheet / reference‑frame extraction to visually verify caption placement. Fix: use ffmpeg to grab frames at cue midpoints and montage them.  
- **Low** – The ffmpeg build must support libass/HarfBuzz for correct Devanagari shaping; this is not checked in code (`gate_d_audio.py:566-569`). Fix: document the requirement and add a CI check.

**C. REEL COMPONENTS we can implement now (no Remotion)**  
1. **Active‑word karaoke highlight** – Already present via `\k` tags, but timing is equal‑division. Needs real word timings for accuracy. Effort: M. Value: engaging captions. Affects all languages.  
2. **Safe‑area templates per platform** – Parameterise margins for Reels/YouTube/Shorts. Effort: S. Value: captions fit each platform’s UI. Affects all.  
3. **Grapheme‑aware wrapping + max‑2‑line fit** – Use Pillow + libraqm to measure, wrap, and enforce 2 lines. Effort: M. Value: no overflow, clean layout. Affects all.  
4. **Per‑language font selection with Latin fallback** – Inline `\fn` switches for mixed scripts. Effort: M. Value: correct rendering of English words inside Devanagari captions. Affects hi/mr.  
5. **SRT/WebVTT sidecar export** – Convert cues to SRT/VTT. Effort: S. Value: YouTube subtitle support. Affects all.  
6. **Caption contact sheet / reference‑frame QA** – Extract frames with captions, montage for visual check. Effort: S. Value: verify placement and readability. Affects all.  
7. **Hook‑word emphasis** – Style the first word with a distinct colour/animation. Effort: S. Value: draws attention to the hook. Affects all.  
8. **Timing from ElevenLabs alignment** – Parse word‑level timing from the ElevenLabs API response. Effort: M (depends on API). Value: accurate sync. Affects all.  
9. **Confidence‑based fallback to phrase timing** – If word confidence is low, use phrase timing. Effort: S. Value: robustness. Affects all.

**D. WHAT NOT TO ADOPT**  
- **Remotion Captions Kit** – immature, untested on Marathi; adds a heavy dependency. We already have a working ffmpeg/libass pipeline.  
- **WhisperX for Marathi alignment** – no default Marathi aligner exists; benchmark first before trusting.  
- **Mukta as primary font** – the owner chose Noto; switching now risks breaking the pipeline.  
- **Research’s safe‑area numbers for 1080×1920** – our canvas is 1440×2560; direct adoption would misplace captions.  
- **Intl.Segmenter in Python** – not available in standard Python; we can achieve grapheme awareness with regex/fontTools instead of adopting a JS‑only tool.

**E. ORDERED PLAN (smallest first)**  
1. Add SRT/VTT export (S effort, high value).  
2. Create safe‑area templates per platform (S effort, ensures correct placement).  
3. Implement grapheme‑aware wrapping with Pillow + libraqm (M effort, prevents overflow).  
4. Add per‑line font fallback for mixed scripts (M effort, better rendering).  
5. Build caption contact sheet QA (S effort, visual verification).  
6. Add hook‑word emphasis (S effort, engagement).  
7. Upgrade word timing to use ElevenLabs alignment (M effort, accuracy).  
8. Implement confidence‑based fallback logic (S effort, robustness).

FINAL:
- The biggest immediate win is adding SRT/VTT export and platform‑specific safe‑area templates – both are small efforts with high value.
- The current wrapping and line‑estimation logic is the most dangerous defect; it can cause captions to overflow or be placed incorrectly.
- Word timing will remain approximate until ElevenLabs alignment data is available; the equal‑division approach is a known limitation.
- The owner’s font and margin choices override the research; we should not “fix” them without explicit approval.
- All caption components should be built in Python + ffmpeg/libass to stay within the owner’s “no Remotion today” rule.