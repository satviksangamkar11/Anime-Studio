# OPEN QUESTIONS

## Closed 2026-11-07 (owner: "close everything that is open"; decisions taken with the recommended defaults, the owner may reopen any of them)

- Q1 CLOSED. Kaliya stays on braj_earth; DEVA-NEON is for new deity reels. The pipeline is universal: a story picks its pack in story.json.
- Q2 CLOSED. The dL* 55 law stays a WARN (never a FAIL) and the owner-supplied hex values are not changed. Hanuman, Karna, Durga and Shiva keep their WARNs in lint_pack as accepted findings; a scene must separate the hero from the background (G1, G2 and the focal_reads criterion measure it).
- Q3 CLOSED. braj_earth keeps min_dL_focal_vs_bg = null. lint_pack prints LINT-DL-UNSET as a WARN by design: Krishna's cloud-blue skin sits close to the dawn haze, so the scene separates him, not the palette. Set a number only after the first approved plates are measured.
- Q4 CLOSED. The auto-tagged neon colours (list below) are accepted as they are.
- Q5 CLOSED, DONE. write_pack.py staged mode now defaults to MASTER_PROMPT v2.3 (v2.2 stays selectable with --prompt-version v2.2).
- Q6 CLOSED. No BPM sound-sync layer: the audio plan is frozen (H3 audio kept, no music). core.json sound_sync.enabled stays false.
- Q7 CLOSED as a rule. The thresholds (G1/G2 dE 6, G3 dE 8, static 3.5/4.0 s) stay as starting values in core.json. Tune them after the first approved renders; tools/calibrate_sat_ceiling.py turns gates.sat_avg_ceiling into a measured number and the ANIME_RELEASE=1 test fails while it is null.
- Q8 CLOSED as a rule. The 65-75 s episode target stays. A 45-60 s cut is compared once analytics exist (core/retention_report.py reads them).

## Auto-tagged neon colours (confirm, Q4)

Tagged `neon: true` by tools/convert_deva_bible.py (role text contains glow, energy, vfx, burn, afterimage, trail, kill-mark or kill mark):

- shiva_neelkanth: Neel Cyan (throat glow, energy VFX); Trialokya Saffron (third-eye burn only)
- karna_surya: Arrow Energy (astra trails)
- durga_kali_shakti: Rani Pink (signature energy); Tongue Red (kill-mark VFX)
- narasimha_twilight: Feral Amber (mane, eye glow); Dusk Purple (VFX, afterimage)
- hanuman_vayu: none

## Palettes under the dL* law (Q2)

Output of `python tools/lint_pack.py deva_neon` (min_dL_focal_vs_bg = 55):

- hanuman_vayu: Dawn Vermilion vs Sky Teal, dL* 13.4 (WARN)
- karna_surya: Molten Gold vs Dusk Clay, dL* 36.0 (WARN; pair comes from focal_hints only)
- durga_kali_shakti: Rani Pink vs Midnight Indigo, dL* 46.1 (WARN; pair comes from focal_hints only)
- shiva_neelkanth: Vibhuti Ash vs Himalaya Mist, dL* 39.2 (WARN; extra, found by the role-keyword rule, not in the spec's expected list)
- narasimha_twilight: no role-keyword pair; the focal_hints pair Feral Amber vs Shadow Violet is checked and passes

braj_earth: no gap check (min_dL_focal_vs_bg is null; owner to set, Q3).

## Decisions taken without the owner

- DEVA phase mapping: PH-HOOK (play) to HOOK, PH-BUILD (play) to BUILD, PH-DROP (threat) to DROP (act role peak), PH-OUTRO (release) to OUTRO. Acts are derived by code from these phases.
- DEVA luma/sat per act use the spec 3.2 example values; lut paths follow `luts/deva_neon/<ACT>.cube`.
- DEVA grade `temp` is stored as a number: "warm+6" -> 6, "cool-4" -> -4, "+2" -> 2.
- braj_earth usage_pct is 0 for every colour (not measured by the bible).
- braj_earth has no grade block: the Kaliya bible has no grade numbers, so acts carry no grade.
- braj_earth palettes come from the bible: skin tones from skin.treatment hex codes, hair, costume (cloth, shade, border, accent), jewellery, and environment day/night/composition hex codes. Colour names come from the word before each hex, with a numbered fallback.
- braj_earth environments list is empty, so G1 is skipped with a WARN until the owner measures plates (A24).
- focal_hints (per DEVA palette, used only by lint_pack): the spec's role-keyword rule cannot produce the Karna and Durga gaps, so the hero/background pairs are given explicitly. Pairs: shiva Vibhuti Ash / Mahakal Void; hanuman Dawn Vermilion / Sky Teal; karna Molten Gold / Dusk Clay; durga Rani Pink / Midnight Indigo; narasimha Feral Amber / Shadow Violet.
- Accent limit: accent_max_per_episode = 1 on every braj_earth palette (A4: divine-light gold once per episode). DEVA palettes have no accent limit.
- DEVA frame_law values are read from the art_bible (min_dL_hero_vs_bg 55, neon_dominant_per_shot 1, pure_white 8 percent as 0.08, area_split 70/20/10).
- lint_pack prints one WARN with rule LINT-DL-UNSET when min_dL_focal_vs_bg is null.
