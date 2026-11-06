# Anime Studio — Colour & Attention-Retention Audit

Nov 7, 2026 · @Sangeeta

## Verdict

The research is a usable primer on colour theory, but it is not ready to drive the studio. It contains about 20 factual errors, several made-up claims, broken citation tags and no source list. It also never covers attention retention, even though that was one of the two goals.

The bigger issue is fit. The doc is written for feature-film pipelines (ACES, Rec.2020, DCI cinema, Dolby Vision). Our pipeline is different: Flow stills plus MiniMax H3 clips, all 8-bit display-referred video, delivered as 9:16 SDR shorts watched on phones. Most of its post-production advice does not apply to that, and the steps that do apply are missing.

**What to keep:** hue, value and saturation basics; simultaneous contrast; colour scripts; the warm/cool and value-contrast guidance; colour-blind rules; Rec.709 as the delivery target.

**What to fix:** the errors in the fact-check table below. Two high-severity examples: a "bullet train" in *Princess Mononoke*, and ISO 3664 described as D65 for print.

**What to add:** a colour script that the code enforces, automatic colour-drift checks on images and clips, a real grade-and-encode stage in `post.py`, and an attention-retention layer (hook, cadence, captions, loop, analytics). Sections 4 and 5 specify these against the repo's own files.

## Fact-check of the research doc

I checked 24 claims. 6 are fabricated or unsourced, 12 are wrong or garbled, and 4 need a caveat, and 2 are correct. Severity measures how much harm the claim does if the studio acts on it.

| # | Claim in the doc | Problem | Fix | Severity |
| --- | --- | --- | --- | --- |
| 1 | *Princess Mononoke* "mixes lush greens with the crimson bullet train and red wolf masks" | The film has no train. It is set in the Muromachi era. | Delete the line. San's mask and the forest greens are real, so keep those. | High |
| 2 | Monitors calibrated to "ISO 3664:2009 D65 for print" | ISO 3664 uses **D50** for viewing prints. D65 is its condition for monitors only. | Use D65 / Rec.709 for screens. Print viewing is not needed for this studio. | High |
| 3 | DC's Batman grade: shadows at H=192°, highlights at H=28°, "ΔE 42 separation" | No source is given and the numbers look invented. It is also live action, not animation. | Delete. Use teal/orange only as a generic example. | High |
| 4 | Pixar colourists "align grading to Rec.2020 primaries and measure ΔE across P3 gamut" | No source. | Delete. | High |
| 5 | "In a USC study, frames with blue-orange splits altered viewers' emotional arousal measurably" | No citation, and none found. | Delete, or find the paper first. | High |
| 6 | "Pixar's teams have noted" their colour is used "very coherently and effectively in terms of physiological visual perception" | The quote comes from an academic study of Pixar colour scripts (Color Culture and Science Journal), not from Pixar. | Credit the study. | Medium |
| 7 | "Many animation teams test… even neuroimaging" | No source. | Delete. | Medium |
| 8 | DaVinci Qualifier isolates reds "by opponent-channel tests"; Hering theory "utilised" by the Qualifier | Resolve's qualifier works in HSL, RGB, luma or 3D keys, not opponent channels. | Say "HSL qualifier". | Medium |
| 9 | Nuke *ColorLookup* "can apply 3D LUTs" | ColorLookup is a curves node. 3D LUTs go through OCIOFileTransform or Vectorfield. | Correct the node names. | Medium |
| 10 | Blender: "Filmic (ACES-inspired)"; Principled BSDF "has hue/sat inputs" | AgX replaced Filmic as the default in 4.0. Blender 5.0 added ACES 1.3/2.0 views and ACEScg / Linear Rec.2020 working spaces. Principled BSDF has no hue/sat inputs (that is a separate Hue/Saturation/Value node). | Update to Blender 5.x facts. | Medium |
| 11 | "Frame&Focal… 15:1 for text legibility" | WCAG asks for 4.5:1 (AA) and 7:1 (AAA). 15:1 has no basis. | Use 4.5:1 minimum and 7:1 for captions. | Medium |
| 12 | "Dolby Vision ODT for HDR / cinema" | ODT is an ACES term. Dolby Vision uses its own mapping and trims. | Remove. We deliver SDR only. | Low |
| 13 | Complementary "red–cyan" next to triadic "R–Y–B" | Mixes the RGB wheel with the painter's RYB wheel. | Pick one wheel. Use RGB/HSV, because that is how the code measures hue. | Medium |
| 14 | Disney heroes wear "warm, pure hues", then Cinderella in "blues and silvers" | Contradicts itself. | Say "pure, saturated, light-valued hues". | Low |
| 15 | Yasuda quote "Color has a meaning, and it makes the film more easily understood" | The quote is real (LA Times, 2009). But in the same interview she said colours have no fixed meaning and she picks what fits each character. | Keep the quote and add that nuance. | Low |
| 16 | Yasuda used "one main shade and two accent colours" | Not found in any source. | Mark as unverified, or delete. | Low |
| 17 | "Screenwriter Bogdan Sandu" | He writes design blogs. He is not a screenwriter or a colour authority. | Drop the attribution. | Low |
| 18 | Vice quote, "Framethrower.ai extracted Coraline's teal-black palette", "Emag LUTs", "GMG Color Plugin" | Unverified tool names and claims. GMG is a print-proofing vendor. | Remove anything not checked. | Low |
| 19 | Leftover tags `[13†embed_image]`, `[31†L312-L319]`, `[0†]`, `[1†]`; two figure captions with no figure; a "Sources" paragraph with no sources | The tags are broken output from the AI tool that wrote the doc. | Rebuild the source list from real links. | High (traceability) |
| 20 | "Pixar pioneered the colour script" | Pixar made colour scripts famous through Ralph Eggleston, but Disney colour keys came earlier. | Say "popularised". | Low |
| 21 | "About 1 in 12 men are red-green colourblind" | About 8% is the figure for men of European descent. Indian studies range from about 1.5% to 15% by community, with 6.4% among rural male students. | Plan for roughly 1 in 16 Indian men, and design for colour blindness anyway. | Low |
| 22 | "ΔE=1 is a just-noticeable difference" | Roughly right for ΔE2000. With ΔE76 the usual figure is about 2.3. | Name the formula: use ΔE2000 in code. | Low |
| 23 | Rec.709 covers about 36% and Rec.2020 about 75% of visible colours | Correct (CIE xy area). | Keep. | — |
| 24 | Cone peaks around 564, 534 and 420 nm; simultaneous contrast; Inside Out colour coding; Coraline's grey real world | Correct. | Keep. | — |

One idea in the doc works against our delivery: "grade in Rec.2020 and let automated mapping shrink to smaller gamuts." H3 and Flow only produce 8-bit Rec.709/sRGB pixels, and YouTube Shorts and Reels play SDR on phones. A wide-gamut working space adds conversion steps without adding any colour. Section 4 replaces this with a Rec.709 display-referred pipeline.

## Repo audit: what Anime-Studio already has

The repo is strong on colour *intent* and has nothing for colour *enforcement* or retention. The style bible sets hex values for every cloth, skin and place. But nothing checks that a picture or clip actually matches them, `post.py` has not been built, and no code measures the hook or the pacing. I read `main` at its latest commit (shallow clone), as of this date.

| Area | What exists (file) | Gap |
| --- | --- | --- |
| Palette | `director/style/kaliya_mardan.json`: earth, water, miasma, cloth, divine-light hex values; rim-light and shading rules | Marked "design targets, not measured". No per-place value or saturation range, so the bible cannot be used to test a frame. |
| Colour script | `MASTER_PROMPT_v2.2.md` (b)8 asks for "one hex key per episode phase" | The bible schema has no `colour_script` field, and `shot_schema.py` has no colour fields (only `light`). The rule exists only in the prompt. |
| Image QA | `flow/scripts/review_shot.py` Q1–Q5 (people, style, frame) | No palette or value check. Your own audit (`IMAGE_SYSTEM_AUDIT_2026-11-06.md`, F5) found the pale LEAP-02A/02B water got past every gate. |
| Clip QA | `director/visual_qa.py`: 9 criteria; `clip_tools.py`: frame sheet and loudness | No measured colour, flicker or shot-to-shot drift. `light_motivated` is the only criterion about light. |
| Assembly | `h3/assemble_reel.py`: trim, concat, LUFS gain, 5 ms fades | Writes no `-c:v`, `-pix_fmt` or BT.709 tags. ffmpeg then uses its own defaults, and players may read an untagged file as BT.601, which shifts hues. There is no grade step. |
| Post | `post.py` is listed in `STATUS.md` but not built. The Opus review (2026-11-04) lists "LUT grade" and "captions" as its jobs | Nothing to grade, caption or encode for delivery yet. |
| Upscale | Plans name Real-ESRGAN / Real-CUGAN / SeedVR2 / H3 2K | No colour check after upscale. Upscalers can shift saturation and crush gradients. |
| Retention | Gate 5 caption rule (6–7 words, never repeat the spoken line); cliffhanger plus closing question; 9:16 safe zones; 65–75 s episodes | No hook rule for the first seconds, no cadence check, no loop design, no analytics loop. `retention_analysis` in `h3_director.py` is H3's identity-keeping field, **not** viewer retention. |
| Timing data | `h3` schema has `master_reel_window_sec` per shot | This is exactly the key needed to map a retention-graph dip back to a shot id. Nothing uses it yet. |

**Contradictions inside the repo** (fix these first, because they cause colour drift):

- `palette.skin_range` says "Krishna is cloud-dark indigo-grey", but `CHAR-KRISHNA.skin` says soft cloud-blue `#AFCCEA` and lists dark indigo-grey under `forbidden`. A model reading the bible gets both instructions.
- `MASTER_PROMPT_v2.2` (a)2 gives child Krishna 5–6 heads, while the bible and the approved master say 4.5.
- `STATUS.md` still says `post.py` will "drop H3 audio", but the 2026-11-06 owner decision is to keep it.

**Hook risk in the current cut:** `milestone_leap/DIRECTION.md` opens LEAP-01 (0–3 s) with a locked-off medium close-up of the face settling. That is a slow opening for a feed where people decide to stay or swipe in the first second or two.

## Colour system spec

One rule runs through it: **colour is decided once, in the bible, and measured at every stage after that.** Prompts describe the colour, gates measure it, and post corrects small drift. Post never invents a look.

&#91;embedded content: colour pipeline · 4 automatic gates\]

G1 catches a drifted still before it becomes a clip. G2 catches flicker and drift in each clip. G3 and G4 check cuts and readability on the finished episode.

### 4.1 Colour space: Rec.709 display-referred, end to end

- Inputs are already 8-bit sRGB/Rec.709: Flow stills, H3 clips and upscaler output. Keep all work in that space. Do not use ACES or Rec.2020. They add conversions without adding colour.
- Process at 16-bit internally (`format=gbrp16le` or `rgb48le` in ffmpeg). Go back to 8-bit only at the encode, with dithering, so dark gradients like the poisoned water and dawn haze do not band.
- Deliver H.264, `yuv420p`, limited (tv) range, tagged BT.709 on all three tags. Make the RGB→YUV matrix explicit too, so ffmpeg cannot fall back to BT.601:

```bash
ffmpeg -i graded_rgb.mov \
  -vf "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p" \
  -c:v libx264 -crf 16 -pix_fmt yuv420p \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
  -c:a aac -b:a 192k -movflags +faststart episode_01.mp4
```

- Review on one D65 / Rec.709 monitor, then on two phones at full brightness before upload (one OLED, one budget LCD). Most viewers will watch on a phone.

### 4.2 Bible additions (`director/style/kaliya_mardan.json` + `style_bible.py`)

Add a `colour_script` block. The code reads it and the gates test against it:

```json
"colour_script": {
  "phases": [
    {"id": "PH-DAWN-PLAY",  "key": "#E9C98F", "accent": "#E8B531", "temp": "warm",
     "luma_mean": [0.45, 0.65], "sat_mean": [0.25, 0.45], "lut": "luts/ph_dawn_play.cube"},
    {"id": "PH-POISON",     "key": "#1F3A3E", "accent": "#5B3E6B", "temp": "cool",
     "luma_mean": [0.15, 0.35], "sat_mean": [0.10, 0.25], "lut": "luts/ph_poison.cube"},
    {"id": "PH-PURIFIED",   "key": "#6FA7B0", "accent": "#F6D27A", "temp": "neutral-warm",
     "luma_mean": [0.45, 0.70], "sat_mean": [0.30, 0.50], "lut": "luts/ph_purified.cube"}
  ],
  "hero_contrast": {"pair": ["pitambara_gold", "violet_fume"], "note": "near-complementary; reserve for hooks and climaxes"},
  "limits": {"shot_drift_de2000": 6, "cut_jump_de2000": 8, "flicker_luma_step": 0.04}
}
```

The ranges and limits above are starting values. Tune them on LEAP-01..05 before you lock them. Also add `measured` (mean Lab and luma) to each environment, taken from its owner-approved plate. That turns "design target" hex values into a reference you can test against. Finally, delete the stale `skin_range` sentence about indigo-grey.

### 4.3 Shot contract additions (`director/shot_schema.py`, `MASTER_PROMPT_v2.2.md` (c))

```json
"colour": {"phase": "PH-POISON", "focal": "CHAR-KRISHNA", "focal_value": "lightest", "accent_use": false}
```

`phase` must exist in the bible. `focal_value` is `lightest` or `darkest`: the focal subject must be the extreme value in the frame, because the eye goes to the strongest contrast first. `accent_use` caps the gold divine-light bloom at once per episode (the bible already says this, and the linter would now enforce it).

### 4.4 Automatic gates (all CPU, no paid calls)

| Gate | Where | Measures | Fails when |
| --- | --- | --- | --- |
| G1 Image palette | new `flow/scripts/palette_check.py`, run by the filer | Mean Lab of the frame (or of a box over the water or sky) vs the place's `measured` value and vs sibling shots | ΔE2000 above `shot_drift_de2000`. This would have caught the pale LEAP-02A/02B water. |
| G2 Clip stability | `director/clip_tools.py` (ffmpeg `signalstats`: YAVG, SATAVG, HUEMED per frame) | Frame-to-frame luma steps; first-vs-last-frame drift; drift from the phase range | Luma step above `flicker_luma_step`; mean outside the phase's `luma_mean` / `sat_mean`; drift above the limit |
| G3 Cut match | `h3/assemble_reel.py` (new `colour_seams` beside `seam_transitions`) | Last 6 frames of shot N vs first 6 of shot N+1, within one phase | Jump above `cut_jump_de2000`, unless the cut is a planned phase change |
| G4 Read test | `director/visual_qa.py`: add `colour_script_match` and `focal_reads` | Vision or human check on a 270 px-wide thumbnail and on a deuteranopia simulation of the same frame | The focal subject does not read first at that size, or it vanishes under the simulation |

### 4.5 Grade order in `post.py`

1. **Upscale** the accepted clip first (Real-CUGAN / Real-ESRGAN anime / SeedVR2). After upscaling, run G2 again, because upscalers shift saturation.
2. **Shot match**: apply a small per-shot correction toward the phase reference (offset and gain on the Lab mean, clamped to ±3 ΔE). It nudges the shot and never makes a new look. Anything bigger is sent back to regenerate.
3. **Phase LUT** with `lut3d=luts/<phase>.cube`. Build one LUT per phase, by hand in Resolve or from the bible's key and accent. Keep each subtle, because the bible's palette is already the look.
4. **Grain and dither**: light grain (`noise=alls=2:allf=t`) on the dark phases, then dither down to 8-bit.
5. **Captions** (section 5), drawn after the grade so their colour stays exact.
6. **Encode** with the 4.1 command, then run G2 on the final file and save `colour_report.json` next to `loudness.json`.

### 4.6 Indian colour meaning for this project

White is the colour of mourning in Hindu custom, so keep white-dominant frames away from joyful beats. Saffron and gold read as sacred, red and sindoor as auspicious, and Krishna's blue as divine. Use these as the bible already does, through cloth and light, never as a glow. Western palette rules from the research (for example, villains in purple) do not carry over automatically: Kaliya's obsidian and violet fume work because of the story, not because of a Disney convention.

## Attention-retention system spec

On Shorts, the swipe decision happens in the first second or two, and YouTube treats "viewed vs swiped away" as the main hook metric. So retention has to be designed into the pack and checked by code, just like colour. YouTube publishes no official benchmarks, so compare each episode against the channel's own earlier episodes, not against figures from blogs.

### 5.1 Retention rules (new `director/retention_lint.py`, run by `check_pack.py`)

| Rule | Check | Why |
| --- | --- | --- |
| R1 Cold open | Episode frame 1 shows the protagonist **and** the stake (the danger or question). No fade from black, title card or logo. | Frame one is both the thumbnail and the hook. |
| R2 Motion by 0.5 s | The first shot's first beat is a camera move or a primary action, not a hold. A post push of 3–5% counts. | A still first second looks like a paused video. |
| R3 Face change by 1.0 s | An expression change lands inside the first second. This fits the brief's own "face before body" rule. | Faces stop the scroll. |
| R4 Hook caption from frame 1 | At most 6 words, a question or a stake, and different from the spoken line (already a Gate 5 rule). | Many viewers watch muted. |
| R5 No ma in 0–3 s | Hold beats (`hold: true`) are banned in the first 3 s. After that, keep the existing ma budget. | Stillness pays off only once the viewer has decided to stay. |
| R6 Change cadence | No window longer than 3.5 s without a change event (a cut, a camera move, an expression shift, a caption, or a sound hit), except declared ma holds that state their purpose. | This is a creator rule of thumb, not a YouTube rule. Tune it from your analytics. |
| R7 Mid-episode re-hook | A colour-phase change or a reveal lands at 45–60% of the runtime. | That is where retention graphs usually sag. It reuses the colour script. |
| R8 Earned end + loop | The last 2 s are the cliffhanger, plus the closing question caption (already in the brief). The last frame's colour and shape lead back into frame 1. | Shorts loop automatically, so a clean loop adds replays. |
| R9 Sound from frame 0 | The H3 soundscape bed is present at 0.0 s, with no silent lead-in. | Silence reads as a dead clip. |

### 5.2 Applying it to the milestone leap (`stories/kaliya_mardan/milestone_leap/DIRECTION.md`)

The current LEAP-01 opens on a 3 s locked-off close-up while play leaves the face. That breaks R2 and R5. Two fixes, smallest first:

1. Keep LEAP-01, but start the slow 3% push at frame 0 instead of as a late post move. Land the eyes locking onto the water by 0.8 s, and put a hook caption on frame 1 (for example, "Why would he leap into poison?").
2. Cold-open on a 1 s cut of LEAP-04's high angle (the child above the violet-black water, gold against violet), then cut back to LEAP-01. This uses the hero contrast pair exactly where it earns attention.

### 5.3 Colour as an attention tool

- The eye goes to the highest value contrast first, so the focal subject owns the extreme value (`colour.focal_value`, 4.3).
- Keep one saturated accent per frame. The gold-against-violet pair is near-complementary, so save it for hooks and climaxes, or it stops working.
- Each phase change in the colour script is also a re-hook (R7). Plan it at the story turn, not just for looks.

### 5.4 Captions on a phone

- The brief puts captions in "the lower third", but the Shorts and Reels UI (title, buttons) covers the bottom band and the right edge. Put captions in the band just above it, and check against each platform's safe-zone overlay before you lock the template.
- Contrast at least 7:1 (WCAG AAA), using an outline or a soft box. Hold on screen for at least about 1.2 s.
- Burn captions with ASS subtitles through libass (ffmpeg `subtitles=`), which shapes Devanagari correctly. ffmpeg's `drawtext` may not join Hindi conjuncts properly. Test both before you choose.

### 5.5 Analytics feedback loop (new `director/retention_report.py`)

1. After each upload, copy from YouTube Studio: viewed vs swiped away, average percentage viewed, and the timestamps of retention-graph dips. Save them to `stories/<slug>/analytics/<episode>.json`.
2. The script maps each dip to a shot id using `master_reel_window_sec`, which is already in the h3 schema.
3. Feed the list of dip shots into the next pack's Gate 3/4 as notes. A dip on a ma hold means shorten it. A dip at a cut means check G3's colour jump.
4. The 65–75 s episodes fit Shorts' 3-minute limit. Once you have a baseline, A/B test one 45–60 s cut, because a shorter cut can raise percentage viewed.

## Build order

The order is cheapest first. Everything up to step 7 runs on CPU with no paid calls, so it can be built and tested before the LEAP-01..05 `sing8` render. Each step ends when its tests pass.

- [ ] 1\. Fix the three repo contradictions (Krishna skin line, 4.5 vs 5–6 heads, the `post.py` audio note).
- [ ] 2\. Correct the research doc using the fact-check table, and give it a real source list.
- [ ] 3\. Add `colour_script` and the per-environment `measured` values to the bible schema and `style_bible.py`. Sample `measured` from the owner-approved plates.
- [ ] 4\. Add the `colour` block to `shot_schema.py` and `MASTER_PROMPT_v2.2` (c), and teach `check_pack.py` to check it.
- [ ] 5\. G1 `palette_check.py`, wired into the filer. Test it on LEAP-02A/02B (it must flag them) and on the approved frames (it must pass them).
- [ ] 6\. `retention_lint.py` (R1–R9), run inside `check_pack.py`. Apply 5.2 to `DIRECTION.md`.
- [ ] 7\. Fix `assemble_reel.py`: explicit codec, `yuv420p`, BT.709 tags and the 709 matrix; add G3 `colour_seams`.
- [ ] 8\. G2 in `clip_tools.py` (signalstats), and G4 criteria in `visual_qa.py`.
- [ ] 9\. Build `post.py`: upscale, shot match, phase LUT, grain and dither, ASS captions, encode, `colour_report.json`.
- [ ] 10\. Render LEAP-01..05 (already planned), then run G2, G3 and G4 on the clips and tune the limits.
- [ ] 11\. Upload, fill `analytics/<episode>.json`, run `retention_report.py`, and feed the dip shots into the next pack.

## Sources

Repo: [satviksangamkar11/Anime-Studio](https://github.com/satviksangamkar11/Anime-Studio). I read `STATUS.md`, `director/` (bible, master prompt v2.2, shot schema, visual QA, clip tools), `h3/` (SPEC, assemble\_reel), `flow/` (image-system audit, review\_shot) and `stories/kaliya_mardan/milestone_leap/DIRECTION.md`.

- [Michiyo Yasuda — Wikipedia](https://en.wikipedia.org/wiki/Michiyo_Yasuda) (LA Times 2009 quote)
- [Kotaku: Studio Ghibli Color Designer Michiyo Yasuda Has Died](https://kotaku.com/1787741281) ("colours don't have a specific meaning")
- [PIXAR's Colorscripts: Chromatic Analyses of Four Films (CCSJ)](https://jcolore.gruppodelcolore.it/ojs/index.php/CCSJ/article/view/294) (source of the "physiological visual perception" quote)
- [ISO 3664:2009 viewing conditions summary (Yuji)](https://www.yujiintl.com/?p=1218) (D50 for prints, D65 for monitors)
- [Blender 5.0 colour-management changes (VideoHelp)](https://www.videohelp.com/software/Blender/version-history) and [It's FOSS](https://itsfoss.com/news/blender-5-0-release/)
- [FFmpeg wiki: colorspace](https://trac.ffmpeg.org/wiki/colorspace?version=45)
- [Red-green CVD among rural school students in India (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4645753) and [Manipur study (IJPH)](https://ijph.tums.ac.ir/index.php/ijph/article/view/4765)
- [YouTube Help: three-minute Shorts](https://support.google.com/youtube/answer/15424877?hl=en)
- [1of10: YouTube Shorts analytics](https://1of10.com/blog/youtube-shorts-analytics/) and [Creator Essentials: Viewed vs. Swiped Away](https://www.creatoressentials.com/glossary/viewed-vs-swiped-away/)

Not checked against a source (from general knowledge): the Nuke and Resolve node behaviour, WCAG 4.5:1 / 7:1, the ΔE JND figures, Hindu white-for-mourning custom, and libass Devanagari shaping. Treat the gate limits (ΔE 6 / 8, luma step 0.04) and cadence numbers (3.5 s, 45–60%) as starting values to tune, not standards.
