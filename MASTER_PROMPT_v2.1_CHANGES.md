# OPUS MASTER PROMPT v2.1: changes to v2.0 for OUR stack (2026-11-04)

Apply these on top of the owner's v2.0 text (5 gates, canon classes, ma, mute-first, FLF keyframes all stay). Anime studio only: Granth Studio /
Gajanan Maharaj stays in its frozen flat-comic style (D-015/D-018) and does not use this prompt.

## Replace the tool stack (Part 2 matrix, Gate 4, Gate 5 step 2-3)
| Step | v2.0 said | v2.1 (what we actually run) |
|---|---|---|
| Reference sheets + keyframes | Midjourney / Flux | **Google Flow (Nano Banana)**, FINAL image system v2, then our watermark remover (`wm_clean_v2.py`) |
| Video | Wan 2.1 FLF / Kling / Runway / Veo / AniSora / ToonCrafter | **MiniMax H3 + Pika H3 Flex 6-step** on Kaggle T4 via Wan2GP headless; fallback Wan 2.2 FLF. No paid video API. |
| Director output | free-text 5-layer prompt | **Wan2GP settings JSON per shot**, made by `director/h3_director.py` from the shot list (proven settings) |
| Upscale | not covered | after acceptance only: Real-ESRGAN anime / RTX Video first; H3 2K refiner tested on one clip |
| Assembly | Remotion | Remotion or ffmpeg; frame holds (on 2s/3s) applied here |

## Rules to add or change
1. **Gate 4 writes H3's format.** FL2VA: `integrated_multimodal_description / overall_soundscape / non_diegetic_music`. Ref2VA: `subject_definitions` (`<Subject 1> is X in <Picture 1>`), `summary`, `detailed_description`. The director script builds this; the agent fills `style, world, action (with time codes), camera, sound`.
2. **Frame_B is a target, not a lock.** The next shot's Frame_A is the **real last frame of the accepted clip** (or H3 continuation), not the separately drawn Frame_B.
3. **Frame_B must be a Flow edit of Frame_A** ("same picture, X changed"), never a fresh image.
4. **Clip length on H3's grid:** 107 + 17k frames at 24 fps (4.5 s, 5.2 s, 5.9 s ... max 15.1 s). Time codes inside the action are allowed.
5. **Anime timing (on 2s/3s) is done in the edit**, not asked of the model (H3 renders 24 fps).
6. **H3 makes sound.** Per shot: keep its SFX or strip it; dialogue/narration come from ElevenLabs. No voice cloning for deities.
7. **No film or show names in Flow/H3 prompts** ("Ramayana 1993", "Solo Leveling"): describe the look (cel-shaded, variable ink lines, hard rim light, volumetric god-rays, multi-plane depth).
8. **Counts models cannot draw:** "101 hoods/tongues" become a fan of 7-9 visible hoods + suggestion (shadows, depth); never ask for exact counts.
9. **Fast sakuga is H3's weak spot:** split fights into short single-impact shots; impact frames, smears and shake added in the edit.
10. **Child proportions:** Bala Krishna (age 7-8) about 5-6 heads tall, not the 7.5-8-head adult rule.
11. **Identity:** 3-panel character sheet per character (face close-up + full body front + back); two characters side by side in ONE reference image (more refs = up to 3x slower); name everything to keep in the prompt.
12. **Repo list is unverified** (several names may not exist): treat as background reading, not as claims.
13. **Vertical 9:16** = Wan2GP resolution `480x832`; Flow keyframes made at 9:16.
14. **Budget:** about 15-20 min per accepted 5 s clip on one T4 (first clip incl. downloads 18m51s); 18 shots x ~3 tries is about 14 GPU-h, inside one account's 30 h/week. Second Kaggle account only run by its owner.
