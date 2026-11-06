# OPEN QUESTIONS

## Owner questions

- Q1 Should Kaliya stay on braj_earth (recommended), with DEVA-NEON for new deity reels only?
- Q2 The DEVA palettes that fail dL* 55 (Hanuman, Karna, Durga): change their hex values, or lower the law for those packs?
- Q3 braj_earth min_dL_focal_vs_bg: what value? (Krishna skin vs dawn haze is only about 2, so the scene, not the palette, must separate him.)
- Q4 Confirm the auto-tagged neon: true colour list (see the next section).
- Q5 Switch write_pack.py's default to v2.3?
- Q6 Build the BPM sound-sync layer for owner-supplied music, or leave it off?
- Q7 Tune thresholds after the LEAP-01..05 render: G1/G2 dE 6, G3 dE 8, static 3.5/4.0 s.
- Q8 Test a 45-60 s episode cut against 65-75 s once analytics exist?

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
