# Colour research (corrected)

This is the corrected version of the colour research (spec A11). It is built from `_inputs\COLOUR_AUDIT.md` (7 Nov 2026). It keeps only claims that have a source or can be worked out from a standard. Every unsourced claim is removed, and the list is at the end.

The pipeline makes 8-bit, Rec.709, SDR video for phones. Everything below is about that.

## What to use

- **Delivery space is Rec.709, display-referred, 8-bit SDR.** Flow stills, H3 clips and upscaler output are already 8-bit sRGB/Rec.709. Do not use ACES or Rec.2020; they add conversions and no colour. Source: the audit's keep list ("Rec.709 as the delivery target") and the FFmpeg colorspace notes it cites (`trac.ffmpeg.org/wiki/colorspace?version=45`).
- **Work at 16-bit inside the pipeline and go back to 8-bit only at encode, with dithering.** This stops dark gradients from banding. Source: the audit's section 4.1 plan. It is a method choice, not a measured result.
- **Encode H.264, `yuv420p`, limited (tv) range, tagged BT.709 on all three tags, with the matrix set explicitly.** This stops players from reading the file as BT.601, which shifts hues. Source: FFmpeg colorspace notes (as above).
- **Judge colour difference with CIEDE2000 (dE2000) in code.** Name the formula; do not write "dE" alone. Source: the CIEDE2000 standard. The code implements it in `core/style_pack.py` (`delta_e_2000`).
- **Pick one hue wheel: RGB/HSV.** Do not mix the RGB wheel with the painter's RYB wheel. The code measures hue in RGB/HSV. Source: the audit's fact-check item 13.
- **Hue, value and saturation basics, simultaneous contrast, colour scripts, and warm/cool and value-contrast guidance** are kept as general colour theory. The audit lists them as correct. Only the parts with sources above are used as rules.
- **Colour-blind design.** Design for colour blindness in every frame. Red-green colour blindness is common enough in India that the sheet has a deuteranopia panel (see the Indian figures below). Source: the two studies in the next section.
- **Contrast for captions: at least 4.5:1 (WCAG AA), and 7:1 (WCAG AAA) for captions.** Source: WCAG contrast standard. The audit did not check the ratios against the WCAG text, and neither did this file (no network). Treat them as the standard values to check against.
- **Blender 5.0 facts.** Blender 5.0 added ACES 1.3/2.0 views and ACEScg and Linear Rec.2020 working spaces. Sources: VideoHelp Blender version history (`videohelp.com/software/Blender/version-history`) and It's FOSS (`itsfoss.com/news/blender-5-0-release/`), both as cited by the audit. The old "Filmic" wording is wrong for 5.x.
- **ISO 3664 uses D50 for viewing prints. D65 is its monitor condition.** Use D65 / Rec.709 for screens. Print viewing is not needed for this studio. Source: ISO 3664:2009 viewing conditions summary (`yujiintl.com/?p=1218`), as cited by the audit.

## Sourced facts used as background

- **Michiyo Yasuda (Studio Ghibli colour designer).** She said colour has a meaning and helps the film be understood (LA Times, 2009, quoted on Wikipedia: `en.wikipedia.org/wiki/Michiyo_Yasuda`). In the same interview she said colours do not have a fixed meaning and that she picks what suits each character (Kotaku: `kotaku.com/1787741281`). Use both.
- **Pixar colour scripts.** The "physiological visual perception" wording comes from an academic study of Pixar colour scripts, not from Pixar. Credit the study: "PIXAR's Colorscripts: Chromatic Analyses of Four Films", Color Culture and Science Journal (`jcolore.gruppodelcolore.it/ojs/index.php/CCSJ/article/view/294`). Say Pixar "popularised" colour scripts; Ralph Eggleston is the name the audit gives for that work.
- **Red-green colour blindness in India.** Studies range from about 1.5% to 15% by community. Rural male students show about 6.4% (PMC: `pmc.ncbi.nlm.nih.gov/articles/PMC4645753`, rural school students; IJPH Manipur study: `ijph.tums.ac.ir/index.php/ijph/article/view/4765`). Plan for roughly 1 in 16 Indian men as a planning figure, and design for colour blindness anyway.
- **Rec.709 and Rec.2020 coverage of visible colours.** Rec.709 covers about 36% and Rec.2020 about 75% of visible colours (CIE 1931 xy area). This follows from the chart, so it counts as derivable.
- **Retention numbers (not colour).** See `docs/RESEARCH_SOURCES.md` for the only numbers the pipeline may cite.

## Fact-check fixes from the audit

The audit checked 24 claims from the old research doc. These are the corrections it made. Each one is applied in this file.

1. Delete the "bullet train" in *Princess Mononoke*. The film has no train. Keep the mask and forest greens.
2. ISO 3664 is D50 for prints and D65 for monitors. Not D65 for print.
3. Delete the DC Batman grade numbers. No source, and the film is live action.
4. Delete the Pixar Rec.2020 and P3 grading claim. No source.
5. Delete the USC blue-orange arousal study. No citation was found.
6. Credit the CCSJ study for the "physiological visual perception" wording.
7. Delete the neuroimaging claim. No source.
8. DaVinci Qualifier works in HSL, RGB, luma or 3D keys. Say "HSL qualifier".
9. Nuke ColorLookup is a curves node. 3D LUTs go through OCIOFileTransform or Vectorfield.
10. Update Blender facts to 5.x (see "What to use").
11. Caption contrast is 4.5:1 (AA) minimum and 7:1 (AAA) for captions. "15:1" has no basis.
12. Remove Dolby Vision ODT. The pipeline delivers SDR only.
13. Use RGB/HSV, not RYB (see "What to use").
14. Disney heroes: say "pure, saturated, light-valued hues". The "warm" wording contradicted the later blues.
15. Keep the Yasuda quote and add her point that colours have no fixed meaning.
16. Yasuda's "one main shade and two accent colours" is not found in any source. Deleted.
17. Drop the "screenwriter" label for Bogdan Sandu. He writes design blogs.
18. Remove unverified tool names and claims (Framethrower.ai, Emag LUTs, GMG). GMG is a print-proofing vendor.
19. Broken citation tags and the empty "Sources" paragraph are removed. The source list is rebuilt from the links above.
20. "Pixar pioneered the colour script" becomes "popularised" (see Pixar above).
21. Colour blindness: about 8% for men of European descent is not used. The Indian figures are above.
22. dE 1 as a just-noticeable difference is for dE2000. The dE76 figure of about 2.3 is removed (no source).
23. Rec.709 / Rec.2020 coverage is correct and kept (see above).
24. Cone peak wavelengths and the film and Inside Out examples: kept by the audit as correct, but no citation is in the inputs. Removed from this file until one is added.

## Removed: no source in the inputs

The audit says these were not checked against a source. They are removed from this file. Add a citation before using any of them.

- Nuke and Resolve node behaviour (other than items 8 and 9 above).
- The dE JND figures, including dE76 of about 2.3.
- The Hindu custom of white for mourning. The studio's bible may still use it through cloth and light, but this file does not state it as a fact.
- The libass Devanagari shaping claim. The plan to test ASS/libass against `drawtext` on Devanagari stays in the audit (section 5.4) as a test step, not a fact.
- Cone peak wavelengths (see item 24).
- The upscaler saturation and gradient claims. Plan step only: re-run G2 after upscaling (audit section 4.5).

## Starting values, not standards

The audit gives these as starting values to tune on the LEAP-01..05 clips, not as standards: the colour-drift limits (dE2000 6 for a shot and 8 for a cut), the flicker luma step of 0.04, the cadence limit of 3.5 s without a change, and the 45-60% re-hook band. Tune them before you lock them. Do not cite them as research.
