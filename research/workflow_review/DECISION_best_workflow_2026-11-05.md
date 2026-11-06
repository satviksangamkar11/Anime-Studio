# Best workflow for anime generation quality: decision (2026-11-05)

Inputs: W1 (Nov-04 ComfyUI workflows), W2 (new4 workflows incl. SelfLift), W3 (Wan2GP code at bd1ff59), W4 (all transcripts), plus Claude's own checks in the Wan2GP source. Every quality claim below is design-based; T0 measures it.

## Chosen: Wan2GP + MiniMax H3 pruned + Pika H3 Flex 6-step (no ComfyUI switch)
| Part | Setting | Why (evidence) |
|---|---|---|
| Speed LoRA | One Pika H3 Flex adapter at 1.0, nothing stacked | W1, W2, W4 agree; stacking breaks output |
| Schedule | Wan2GP `pika_renoise`, 6 steps, shift 12, one phase | Checked: `models/minimax_h3/pika.py` builds the official upstream schedule (knots 1, .75, .5, .25, .1, .04, 0 at shift 12). Same as the official ComfyUI ManualSigmas (W2 arithmetic). Wan2GP refuses any other steps/phases for Pika (`pipeline.py:825-832`) |
| Resolution | 9:16 at 768x1344 (~1 MP) for identity shots; 544x960 for wide shots if units are short | All official workflows run at 1.0-1.06 MP (W2); 480x832 is 0.4 MP. H3 sizes must be multiples of 32 (`vae_block_size`) |
| Keyframes | Start + end frame with the exact time anchor sentence (Picture 1 at 0.00 s, Picture 2 at the end) | W1, W2; already what `h3_director.py` writes for FL2VA |
| Identity | Ref2VA with 2 refs of one character: face crop + full-body front crop (no labels), `<Picture N>` only in subject_definitions/retention; `ref_image_size` match | W1, W2, W4 (T3, T4). Refs cut by `flow/scripts/make_refs.py` into `adhyay_01/refs_video/` |
| Prompt wording | Cel style stated (flat colour, ink outlines); no "photorealistic/realistic/Pixar 3D" words | W2: 4 of 10 sample prompts carry photoreal wording |
| Caching / step skipping | Off | W4 (face drift); Wan2GP refuses it with Pika anyway |
| Audio | H3 sound ignored; sound in post | W4 tip 10, DIRECTION |
| GPU memory | `--profile 5` on T4; a lower profile on a bigger Colab GPU | W3: the settings file's memory_profile override wins over the flag |

## Not adopted (and why)
- **Two-stage / SelfLift with Pika:** impossible in Wan2GP (Pika is single-phase, no custom sigmas). ComfyUI-only, untested on anime, and the downloaded JSONs have wrong file names (W2). Revisit only if T0 at 768x1344 is too slow.
- **Non-Pika two-phase "quality" recipe (20 + 3 steps, H3 Turbo LoRA):** about 4x the steps of Pika, so many more units; W3 design-only. Keep as a later quality arm, not T0.
- **Singularity v2:** its edge is realistic skin; we are cel-shaded.
- **Sage / sol attention:** sol fails below SM 8.6 (T4, A100); sage needs an extra package. Not needed for T0.
- **Motion dials, D-RoPE, LCM, SolVAE, Molmo2:** not in Wan2GP (W3).
- **KRISHNA_ACTION_POSES sheet as a ref:** its bottom row is broken.

## T0 (one shot, LEAP-03, 4 clips)
Base shot fields: `resolution: 768x1344`, start/end = final LEAP-03A/03B, refs = `refs_video/CHAR-KRISHNA__ref_face.png` + `__ref_front.png`, subject "<Subject 1> is Bala Krishna, face in <Picture 1>, full body in <Picture 2>." `t0_variants.py` makes FL and REF at seeds 42 and 123. Measure: time and units per clip, peak VRAM, face match to the sheet, line flicker, colour drift.

## Code changed today (309 tests pass)
- `director/h3_director.py`: per-shot `resolution` (480x832, 544x960, 704x1280, 768x1344 for 9:16); settings_version 2.82; one subject may name 2 pictures (face + body).
- `director/t0_variants.py`: 1-2 refs.
- `director/run_kaggle.py`: `--target colab` (run.py + run.ipynb, /content paths) and `--profile N`.
- `flow/scripts/make_refs.py`: cuts face / front / back refs from the identity master.

## RETHINK addendum (2026-11-05, after fetching Gemini's links and the repos)
Two of my earlier calls were wrong and are reversed:
1. **Singularity v2 is NOT only about realistic skin.** Wan2GP's own README says it gives "clearer fast action, sharper distant faces and less glossy skin". Our leap has fast action (LEAP-03/04) and small faces in wide shots (03, 04, 05): it fits. It is built into Wan2GP (`minimax_h3_singularity_v2_pruned`, 1M+ downloads upstream).
2. **The Pika-Labs Turbo LoRAs are normal LoRAs (euler, simple, CFG 1), not `pika_renoise`.** So Wan2GP's "Pika is single-phase" limits (no custom sigmas, no two-phase, no 3D latent upscaler) do NOT apply to this route. Two-stage refinement becomes possible again.
Still true: the T4 timing table is unusable; Gemini's "Verified Fact" tags prove nothing; no anime or identity test exists anywhere.

## T0 rethought: 4 arms, one shot (LEAP-03), seeds 42 and 123 = 8 clips, on the G4 (or A100/L4 if G4 is locked)
| Arm | Model | Speed LoRA | Sampler / steps | Why |
| --- | --- | --- | --- | --- |
| A (baseline, built) | H3 Ref2VA pruned | official Pika 6-step | pika_renoise, 6 | what we have proven |
| B | Singularity v2 pruned | Pika-Labs Turbo 4-step Ref2VA | euler + simple, 4, CFG 1, shift 12 | author's recommended Singularity combo |
| C | Singularity v2 pruned | Pika-Labs Turbo 8-step HD Ref2VA | euler + simple, 8, CFG 1, shift 12 | max-quality arm |
| D | H3 FL2VA pruned | official Pika 6-step | pika_renoise, 6 | start/end-frame lock without refs |
All at 768x1344 with the two refs (A-C) or keyframes only (D). Score: face match to the sheet, line flicker, colour drift, motion quality of the launch, time and units per clip.
**Open question that decides the runner:** does Wan2GP load the Pika-Labs (ComfyUI-format) Turbo LoRA onto Singularity? If yes, stay on Wan2GP and add presets to `h3_director.py`. If no, run arms B and C in ComfyUI on the same Colab GPU (full bf16 Singularity fits a 96 GB G4).

## T0 RESULT 2026-11-06 (8 clips, LEAP-03, 768x1344, 124 frames; Claude's own full-resolution look, not measured)
- All 6 re-rendered on G4 in one session (no 429 this time, retry code not triggered), all downloaded and checked, session stopped, sessions empty. Cost about 3.0 units (190.93 -> 187.95). Turbo LoRAs confirmed loaded on Singularity (wgp logs: "was loaded in model", AdaLN map singularity_v2_rank8).
- Warm time per clip on G4: A ~105 s, B ~78 s, C ~132 s, D ~92 s (first clip of a session adds model load, B42 took 450 s incl. download).
- **B (Singularity + Turbo 4-step): FAIL on both seeds** - frames 60-90 break the scene (cut to a village/lake view, Krishna half out of frame, different composition). Drop it.
- **A (H3 Ref2VA + official Pika 6-step), C (Singularity + Turbo 8-step HD), D (FL2VA start/end, no refs): all three hold scene, line art, colours and identity** (tilak, pearls, feather, flute, dhoti correct); launch reads well. Differences are small; C looks slightly crisper in hands/flute, D slightly looser pose.
- Recommendation: default **A** (proven, faster than C, uses face/body refs so identity is guaranteed in shots without a clean face in the keyframes); keep **C** as the quality option for hero shots; **D** is fine where keyframes already carry the face. Owner makes the final pick.
- Files: director/t0_pack/results/ (6 clips + logs), results_early/ (A), cmp/ (sheet_S42.jpg, sheet_S123.jpg, crop_ACD.jpg).

## OWNER DECISION 2026-11-06: arm C
Owner chose **arm C** (Singularity v2 pruned + Pika-Labs Turbo 8-step HD LoRA, route `sing8`) for the Leap reel, against my recommendation of A (A default, C for hero shots). Settings are the T0 arm C ones: Ref2VA, subjects name face + front refs, euler + simple, 8 steps, CFG 1, LoRA strength 1.0, shift 12, 768x1344, 124 frames (5.17 s) at 24 fps.
- Plus of C: slightly crisper hands, flute and face; designed for small distant figures and fast action; holds scene, colours, line art and identity (seen on both seeds of LEAP-03).
- Minus of C: ~132 s per clip warm vs ~105 s for A (about 25% more units); extra ~23 GB of downloads (Singularity model + Turbo LoRA) so more exposed to the Hugging Face 429 (retry code now in the runner); tested on ONE shot only.
- Safeguards: render LEAP-01..05 with `sing8`, 3 takes each; check every take at full size for scene breaks like arm B's; if a shot fails, re-render it with `pika6` (A) and note it here. Arm B (`sing4`) is not to be used.

## OWNER DECISION 2026-11-06: sound
The video model (MiniMax H3) generates all sound effects with the clip; we only describe them in `overall_soundscape` per shot. The H3 audio stays in the final edit (post step must not strip it). Background music: owner supplies it separately; prompts carry `non_diegetic_music: N/A`. Linter rules SD-01 (soundscape must describe the effects, music must be N/A) and SD-02 (warning on a placeholder soundscape) enforce this in `h3/`. All other parts of the pipeline are frozen.
