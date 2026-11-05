# Milestone scene: Krishna's kadamba leap (16 s) — DIRECTION LOCK (Phase 0, for owner approval)

Status: DRAFT (written 2026-11-05 by Claude from SOURCE.md EVENT-006, the style bible and the acting library). Approve or change it, then it becomes the locked direction for Phase 1A art and T0.

Canon: ŚB 10.16.6 (CANON) — Krishna tightens his waist-cloth, climbs the kadamba, slaps his arms like a wrestler and leaps into the poisoned pool; Shridama's cry is KATHAVACHAK_VARIATION. This scene covers the climb's END: Krishna already on the high branch; tightening and arm-slap are in the shot before (not in this test).

Cast and assets (ids from `director/style/kaliya_mardan.json`): CHAR-KRISHNA (5.5 heads; flat cloud-dark indigo-grey skin; golden pitambara #E8B531; black Kali Kamli as a tight wrestler's sash; curls + one peacock feather), PROP-KALI-KAMLI, PROP-MOR-MUKUT (feather only), ENV-KADAMBA-BANK (dawn, low sun screen left, black ash bank, leaning kadamba, dark violet-green water). Shridama is off screen (voice only).

## Shots (editorial time; each H3 render is 107 frames = 4.46 s, trimmed to the edit)
| Shot | Edit time | What the audience sees (mute-first) | Bhava / acting progression | Camera | Route | Fallback |
|---|---|---|---|---|---|---|
| LEAP-01 | 0.0–3.0 s | medium close-up on the high branch: Krishna looks down at the dark water; the play leaves his face and resolve arrives | courage: eyes lift and lock on the water -> brows level -> mouth closes to a firm line -> chin level -> breath in and held | locked off in generation; a slow 3% push added in post | H3-REF (identity-critical close-up) | H3-FL |
| LEAP-02 | 3.0–6.0 s | insert: bare foot grips the bark, toes curl; hand closes on the branch; knees start to bend | hands take a grip; weight sinks | locked off | H3-FL | POST-STATIC with two held drawings |
| LEAP-03 | 6.0–10.0 s | wide side view: deep crouch -> launch; body arcs out over the bank, arms forward; the branch flexes up and rebounds; sash and curls trail | full body: drops into the crouch, then launches; cloth follows 0.4 s after the body | locked off (the arc must read against a still frame) | H3-FL with key poses (crouch start, mid-air end) | **H3-CONTROL from a Blender proxy layout of the arc** |
| LEAP-04 | 10.0–13.0 s | high angle looking down: Krishna falls head-first toward the dark water, small in frame, the surface rising | stillness of a committed dive; only cloth and hair move | locked off in generation; tilt-down follow added in post | H3-FL | POST-CAMERA over a held drawing + motion blur |
| LEAP-05 | 13.0–16.0 s | the dark surface breaks: a tall sheet of violet-black water rises where he entered; then it hangs and falls | — | locked off | H3-FL (water plate) + POST-FX | composited splash elements |

## Editorial timing (lock 4)
- 13.0 s: 2-frame impact flash (black and gold) on entry, then 0.5 s of near silence (ma), then the splash sound.
- Exposure: Krishna's acting on 2s in LEAP-01 and LEAP-02 (post holds); LEAP-03 and LEAP-04 on 1s (fluid action); water on 1s.
- Cuts: LEAP-02 -> LEAP-03 is a match on the crouch; LEAP-03 -> LEAP-04 cuts on the apex of the arc; LEAP-04 -> LEAP-05 cuts on contact.

## Sound
Dawn wind, leaves, a branch creak on the grip (LEAP-02), the branch rebound (LEAP-03), wind rush (LEAP-04), the impact silence and the splash (LEAP-05). Off-screen, Shridama (ElevenLabs): "नहीं-नहीं लाला, यहाँ मत कूदियो!" starting at 6.2 s over LEAP-03. Music: a low tanpura drone that cuts out at 13.0 s.

## Flow assets this needs (Phase 1A, owner)
1. Krishna reference family: IDENTITY_MASTER, TURNAROUND (front, 3/4, side, back), ACTING_SHEET (neutral, resolve, mischief, smile), ACTION_POSES (grip, crouch, launch, mid-air arc, head-first dive), COSTUME_DETAIL (pitambara folds, Kali Kamli knot, feather).
2. ENV-KADAMBA-BANK plate at dawn (empty), plus a high-angle water-surface plate.
3. Keyframes (each made FROM the references): LEAP-01 A (looking out, relaxed) / B (eyes locked on water, firm mouth); LEAP-02 A (foot flat, hand open) / B (toes curled, hand tight, knees bending); LEAP-03 A (deep crouch on the branch) / B (mid-air, arched, arms forward, branch flexed); LEAP-04 A (head-first, upper frame) / B (just above the surface); LEAP-05 A (dark surface, silhouette entering) / B (tall water sheet, no Krishna). B frames are Flow EDITS of their A frames.

## Acceptance (from plan v4.3)
Same Krishna before, during and after; the leap reads as deliberate physical motion; nothing hidden by VFX; full-clip review, not three frames; owner approves the finished 16 s with sound.
