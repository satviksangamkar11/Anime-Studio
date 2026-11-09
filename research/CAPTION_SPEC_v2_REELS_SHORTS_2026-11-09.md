# Caption spec v2: Instagram Reels + YouTube Shorts (owner, 2026-11-09)

Owner: captions are small, sit on faces, look bad; Hindi/Marathi letters are broken. Study Reels/Shorts and define properly.

## Bugs found in v7 (measured on frames)
1. Devanagari conjuncts broken (ब्रह्मा shows as बरहमा): the burn used libass simple shaping. Fix: burn with the `ass` filter and `shaping=complex` (tested: ब्रह्मा क्या शक्ति render correctly with Mukta ExtraBold).
2. Captions over faces (Kali's mouth, shots 1-2), because they sit at the middle band (0.50-0.65).
3. Too small: about 3.4% of the frame width, on a 768x1344 export.
4. Off centre: `\pos(640, ...)` on PlayResX 1440 (centre is 720).
5. Yellow highlight (#FFD400) disappears on the gold court scenes.
6. A stray punctuation card piece ("began, .").

## Platform facts (sources: reap.video safe zones guide, admanage.ai Reels safe zone, adaptlypost 2026 guide, opus.pro caption design, blitzcutai caption styles)
- Canvas 1080x1920 (9:16) for both.
- UI covers: top ~250 px (username/music), bottom ~500 px safe margin (caption, CTA, description; long captions push higher), right ~150 px (like/comment/share rail). Keep text inside x 90-930, y 250-1420.
- Style that wins watch time: bold sans, white with a thick black outline, 2-5 words per card, word-by-word highlight in ONE accent colour, max 2 lines, lower-centre third, never over the subject's face.

## The spec (reference canvas 1080x1920)
- Export video at 1080x1920 (lanczos upscale of the 768x1344 picture) and burn captions at that size, so text is sharp.
- ASS: PlayResX 1080, PlayResY 1920, WrapStyle 2, burned with `ass=<file>:fontsdir=styles/fonts:shaping=complex`.
- Font: Mukta ExtraBold (Devanagari + Latin, family name "Mukta ExtraBold"); size 84 (en), 80 (hi, mr); outline 7 px black; shadow 3 px black at about 60% opacity; no box.
- Cards: en 1-4 words, hi/mr 1-3 words (and at most 18 characters); one line preferred, two lines max, max text width 840 px, balanced wrap, never split a name; no card that is only punctuation; strip stray " ." leftovers.
- Position: `\an5\pos(510,1290)` (x 510 = centre shifted 30 px left of 540 to clear the right button rail; y 1290 = 67%, lower third, inside the safe zone, below faces in every reel-1 shot).
- Active word: green #3CFF4E (readable on purple, blue and gold scenes) with a 108% scale pop (`\fscx108\fscy108`) on that word only; other words white.
- Timing: unchanged (one event per spoken word, from the real voice timing).
- Sidecars SRT/VTT follow the new card splits.

## Acceptance (checked on real frames, not on the .ass text)
- Contact sheet per language: every caption fully inside x 90-930, y 250-1420; none crosses a face.
- Zoomed crop of ब्रह्मा / दक्ष / क्या in hi and mr: conjuncts joined.
- Cap height at least 5% of frame width (54 px of 1080).
