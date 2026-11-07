# Research sources: verified numbers only

This file lists the only numbers the pipeline may cite. Each one comes from a source named in the repo inputs (`_inputs\`). Nothing here was re-checked against the web: the writing task had no network access. The status column says what the inputs claim and nothing more.

Status legend:
- **Listed as verified**: the input file says the number was checked against its source.
- **Source named, not re-opened**: the input names the source but says nothing about checking it.
- **Spec rule**: the number is a rule written in the spec, not a research claim.

## Verified numbers

| Claim | Number | Source (as named in the inputs) | Listed in | Status |
| --- | --- | --- | --- | --- |
| Reels share of Instagram time | 50% | Meta Q1 2024 earnings call, via Loopex. Loopex link as the digest gives it: `loopexdigital.com/blog/instagram-reels-statistics` | `deva_zip/research/RESEARCH_DIGEST.md` section 2 | Listed as verified. The Loopex page is the Q1 2026 edition; the 50% figure is attributed to Meta Q1 2024. Not re-opened. |
| Opening caption window (the "Opus 1.5 s hook") | 1.5 s | Opus, "The Ideal Instagram Reels Length & Format for Retention", `opus.pro/blog/ideal-instagram-reels-length` (as the digest gives it) | `deva_zip/research/RESEARCH_DIGEST.md` section 1 | Listed as verified. Not re-opened. The digest uses it as `retention_targets.hook_window_s`. |
| Shorts length limit | 3 minutes | YouTube Help: three-minute Shorts, `support.google.com/youtube/answer/15424877?hl=en` | `_inputs\COLOUR_AUDIT.md` section Sources (and section 5.5 step 4) | Source named, not re-opened. |
| General flashes per second | 3 or fewer | Ofcom flashing-images guidance and the Harding FPA test (no URL given in the inputs) | `deva_zip/research/RESEARCH_DIGEST.md` section 3; `_inputs\SPEC_v1.2.txt` lines 143-144 | Listed as verified in the digest. The inputs name no URL, so none is given here. |
| Flash definition | WCAG "general flash" definition | `_inputs\SPEC_v1.2.txt` lines 143-144 (the flash values follow the WCAG general-flash definition, the machine-checkable form of the Ofcom/ITU rule) | spec | Spec rule. The definition text is not in the inputs. |
| Flash check scope | Screening check, not a certified test | `_inputs\SPEC_v1.2.txt` line 474: "F1 is a screening check based on the WCAG definition. It is not a certified Harding test." | spec | Spec rule. Stated in the F1 report header. |

## Unverified - not used by any rule

Every other statistic in `deva_zip/research/RESEARCH_DIGEST.md` is listed here, one per bullet. No rule, gate or report uses these numbers. Each one needs a source before anyone cites it.

- Keep/drop decision horizon: under 2 s (digest section 1, `decide_window_s: 2.0`).
- First-3-seconds drop-off: 40% of the audience lost when the hook is not front-loaded (digest section 1).
- Static-shot danger zone: 4.0 s with no held frame (digest section 1, `max_static_s: 4.0`).
- Healthy retention band: 60-80% for 7-15 s reels (digest section 1, "pilot-reel retro benchmark").
- Viral probability lift: +72% when a storytelling hook or jump cut lands inside 3 s (digest section 2).
- Engagement lift from cut rhythm: +32% with one cut every 3-5 s (digest section 2, `cut_rhythm_s: [3, 5]`).
- Non-follower views: 55% of views, so the reel must read with no context (digest section 2).
- Instagram users in India: 414 million (digest section 2).
- Audience aged 18-34: 62% (digest section 2).
- Finish-rate lift with captions: +80% (digest section 2).
- Pure-white frame area cap: 8% outside impact frames (digest section 3, `pure_white_area_cap_pct: 8`). The spec calls the cap a pack design choice, not an Ofcom rule (spec near line 456).
- Impact budget: at most 4 impact frames per 30 s, minimum gap 500 ms, impact run at most 4 frames (digest section 3). These are validator and config values, not sourced statistics.
- Frame law: environment 70%, character 20%, ignition (neon) 10% (digest section 4). A design rule, not a measured statistic.
- Separation metric: hero vs background dL* of at least 55, accent vs background dL* of at least 40 (digest section 4).
- Thumbnail test: 3 seconds, the frame must read at 100% and at 30% zoom (digest section 4).
- Working tempo: 140-160 BPM, reference 150 BPM = 0.4 s per beat = 9.6 frames at 24 fps (digest section 5). Sound-sync is config only (`enabled: false`), so no code uses it.
- Narasimha reveal: 3-frame black-out (digest section 6).
- Colour values such as saffron #FF9E1B, cyan #27E0FC and the base palette hexes (digest sections 4 and 6). These are style-pack values, not statistics. They belong in the style pack, not in this file.
