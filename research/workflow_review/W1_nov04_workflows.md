# W1 review: Pika H3 / MiniMax H3 ComfyUI workflows (2026-11-05)

**Scope.** The six ComfyUI JSON files in `D:\aai work\research_transcripts\workflows_2026-11-04\` on the brief list. Each was read in full with a script (`python -I`) that dumps every node, link, widget, named widget value and subgraph, including subgraph inputs and outputs. Also read: `NOTES_RUN_BIG_VIDEO_MODELS.md` (Sources 1-11), `OPUS_REVIEW_GEMINI_T4_PLAN_2026-11-05.md` section 2, and `h3_director.py` lines 32-41 and 284-296. `jigs10_wan2gp_kaggle.ipynb` is in the same folder but is not on the list, so it was not read.

**Legend.** Every fact carries one tag.
- **[J]** FROM JSON. Node numbers are the JSON node IDs.
- **[N]** FROM NOTES. This includes the OPUS section 2 status, cited as "OPUS #n" (CONFIRMED / CONTRADICTED / NOT FOUND).
- **[I]** MY INFERENCE.
- **not stated** = not in the file or the notes.
- Where a link feeds an input, the linked value is the effective one. The saved widget value is noted when it differs. This is standard ComfyUI behaviour [I].

**Three points that matter most**
1. None of the six files is cel-shaded anime, none is 9:16, and none wires a Ref2VA node to first/last keyframes. Every "adopt" below is a T0 test item for our film, not a proven setting.
2. The notes describe at least three saved graphs wrongly (sigma lists, pass-1 sampler, upscale size). Use the JSON values (section 1b).
3. The parts that transfer best are the official 6-step Pika recipe, the official Ref2VA two-reference wiring, the FL2VA keyframe template with its alignment sentence, and a low-denoise tiled refine as an A/B arm.

---

## 1. Per-workflow settings

### 1a. Settings matrix

Column key: **A** = `ainiinja_FL2VA-Minimax-Pika-2stage.json` · **B** = `ainiinja_Text-To-Video-Minimax-Pika-2stage.json` · **C** = `cgpixel_pika_h3_2k_gdrive.json` · **D** = `comfy_video_pika_h3_flex_fl2va.json` · **E** = `comfy_video_pika_h3_flex_ref2va.json` · **F** = `comfy_video_pika_h3_flex_t2v.json`

| Setting | A: AI Ninja FL2VA | B: AI Ninja T2V | C: CG Pixel 2K | D: Comfy FL2VA | E: Comfy REF2VA | F: Comfy "T2V" |
|---|---|---|---|---|---|---|
| Role | FL2VA, first + last keyframe, 2 passes [J] | FL2VA model, no image input wired, 2 passes [J] | Singularity Ref2VA base, 1 ref, base + tiled refine + decode [J] | FL2VA, first + last keyframe, 1 pass [J] | REF2VA, 2 refs, 1 pass [J] | FL2VA model, no image input wired, 1 pass [J] |
| Main DiT (as saved) | `minimax_h3_fl2va_pruned_int8_convrot.safetensors`, node 174 [J] | same file, node 6 [J] | `Minimax-h3_Singularity_ref2va_v2_Pruned_int8.safetensors`, node 215 [J] (capital P; OPUS lists lowercase, see 1b row 9) | `minimax_h3_fl2va_pruned_int8_convrot.safetensors`, node 127 [J] | `minimax_h3_ref2va_pruned_int8_convrot.safetensors`, node 127 [J] | `minimax_h3_fl2va_pruned_int8_convrot.safetensors`, node 127 [J] |
| Text encoder | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, type minimax, node 176 [J] | same, node 13 [J] | `qwen3vl-32B-MiniMax-H3-Q2_K.gguf` via CLIPLoaderGGUF, node 6688 [J] | same NVFP4 file, node 128 [J] | same NVFP4 file, node 128 [J] | same NVFP4 file, node 128 [J] |
| VAE video / audio | `minimax_h3_video_vae_int8_convrot` / `minimax_h3_audio_vae_fp32`, nodes 186, 187 [J] | same types, nodes 11, 24 [J] | same types, nodes 207, 208 [J] | same types, nodes 119, 120 [J] | same types, nodes 119, 120 [J] | same types, nodes 119, 120 [J] |
| LoRA(s), strength | `pika_h3_flex_fl2va_v1_avg_rank_56_bf16`, 1.0, node 182 [J]. Not the official `v1_bf16` name [I] | same `avg_rank_56` file, 1.0, node 137 [J] | Upscale path stacks 4 LoRAs, all 1.0: `pika_h3_flex_fl2va_v1_bf16` (6714) → `sharp_curve_branches` (6722) → `minimax_h3_lms_v1.0_r64` (6684) → `open_regenerate_2k_refiner_rank_16_bf16` (6686). Base pass uses only the Pika LoRA [J] | `pika_h3_flex_fl2va_v1_bf16`, 1.0, node 134 [J] | `pika_h3_flex_ref2va_v1_bf16`, 1.0, node 145 [J] | `pika_h3_flex_fl2va_v1_bf16`, 1.0, node 134 [J] |
| Pass-1 sampler | KSamplerSelect `er_sde`, node 189 [J] | `er_sde`, node 17 [J] | `euler`, node 211 [J] | `lcm`, node 123 [J] | `lcm`, node 123 [J] | `lcm`, node 123 [J] |
| Pass-1 schedule | BasicScheduler `simple`, 6 steps, denoise 1, node 188 [J] | `simple`, **4 steps**, denoise 1, node 9 [J] | `simple`, 6 steps, denoise 1, node 212 [J] | ManualSigmas `1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0` = 6 steps, node 143 [J] | same list, node 147 [J] | same list, node 143 [J] |
| Guidance | BasicGuider (single conditioning, no negative input), node 190 [J]; CFG-free [I] | BasicGuider, node 16 [J] | BasicGuider 6711 [J]; refine MMH3UltimateUpscale `cfg` 1 (node 6600) [J] | BasicGuider 126 [J] | BasicGuider 126 [J] | BasicGuider 126 [J] |
| Pass-1 size | ResolutionSelector 16:9, 0.4 MP, multiple 8 (node 219). Keyframe resized to it, then width/height rounded to multiples of 32 (nodes 170, 171). Final px **not stated** (about 832-864 x 480 [I]) [J] | 16:9, 0.5 MP, multiple 8 (node 159) [J]; final px not stated [I] | 16:9, 0.6 MP, multiple 32 → **1056x608** (saved VHS metadata) [J] | Size copies the first frame: GetImageSize (149) → round to 32 (150, 151) [J] | 16:9, 0.98 MP, multiple 32 → **1344x768** (per the 0.98 row of the CG Pixel note table) [J] | 16:9, 0.98 MP, multiple 16, then rounded to 32 (nodes 147, 148). Final px not stated [J] |
| Frames / fps | 8 s → **192 frames**, 24 fps (nodes 166, 167, 196) [J] | 8 s → 192 frames (nodes 160, 161), 24 fps [J] | 5 s → **124 frames**, 24 fps (6342, 6344) [J] | 5 s → 124 frames (132, 133), 24 fps [J] | 5 s → 124 frames (131, 132), 24 fps [J] | 5 s → 124 frames (132, 133), 24 fps [J] |
| Conditioning | First frame LoadImage 148, last frame LoadImage 147, both resized to the 0.4 MP size (198, 200) [J] | None wired; EmptyMiniMaxH3LatentAV 80 gives a plain latent [J] | 1 ref (`ref_image_0`), `ref_image_size` match. The reference LoadImage 6681 and resize 6349 are **bypassed (mode 4)** [J] | First = `ref_popart_woman.png` (148), last = `lastP_spin_jump_hole.png` (147) [J] | 2 refs: `ref_image_0` = pilot `ref_pilot_profile.png` (149), `ref_image_1` = station `ref_subject_station.png` (150); `ref_image_size` match [J] | None wired (first_frame, last_frame, prompt are subgraph inputs with no root link) [J] |
| Attention / memory nodes | ModelAttentionBackend "comfy kitchen attention" (177); MiniMaxChunkFeedForward 2 / 4096 (175); ModelPreviewOverrideKJ (183) is preview-only [J][I] | same backend (126) and chunk FF 2 / 4096 (151); preview node 123 [J] | Inside the OPTIMIZATION subgraph, applied to all passes: backend "comfy kitchen attention" (327) → MiniMaxH3SigmaShift `shift_video` 12, `shift_audio` 3 (329) → MiniMaxLowVRAMAttention `head_chunks` 2 (328) → MiniMaxChunkFeedForward 2 / 4096 (326) → VedaSparseAttention (944). easy cleanGpuUsed / clearCacheAll between passes (6586, 6587) [J] | none [J] | none [J] | none [J] |
| Pass-2 type | Latent upscale (LatentUpscaleModelLoader 210 `..._3d_conv_v1_bf16` → MiniMaxH3LatentUpscaleWithModel 211) then refine. Target = pass-1 size **x 1** (subgraph `scale_by` node 212, scale_by = 1). The saved 2560x1440 widget is overridden by links [J] | Latent upscale (138, 139) then refine. Target = pass-1 size **x 2** (ImageScaleBy in subgraph node 167, scale_by 2) [J]; about 4x pixels [I] | MMH3LatentUpscaleWithModelParams 6596 (`minimax_h3_latent_upscaler_3d_bf16`, cuda, bf16) → MMH3UltimateUpscale 6600 tiled refine. Target **2144x1216** (saved VHS metadata; 2.5 MP) [J] | none [J] | none [J] | none [J] |
| Pass-2 LoRA / attention | Refiner LoRA rank 16, 1.0, node 205 [J]; BlockSparseAttention "sol-attn" (206) on the refine model only [J] | Refiner rank 16, 1.0, node 78 [J]; sol-attn (118) on refine model only [J] | Upscale path only: the 4-LoRA stack above [J] | n/a | n/a | n/a |
| Pass-2 sampler, sigmas, steps, denoise | er_sde (189). ManualSigmas `0.909375, 0.857143, 0.666667, 0` = **3 steps, start sigma 0.909** (node 208) [J]. Unused: ManualSigmas `0.7, 0.494118, 0` (209) and BasicScheduler 2-step (214), both with no output link [J] | er_sde (17). ManualSigmas `0.909375, ...` = 3 steps (144) [J]. Unused: `0.7, ...` (150) and BasicScheduler 2-step (140) [J] | `sa_solver` (6590); BasicScheduler `simple`, **6 steps, denoise 0.32** (6594) [J]; cfg 1 [J] | n/a | n/a | n/a |
| Prompt (effective) | Node 220: coffee-to-desert morph with "@Image 1 / @Image 2" tokens, no timeline, 632 chars [J]. Node 197's own text (game-menu, 10 s timeline) is stored but overridden, because its prompt input is linked [J][I] | CLIPTextEncode 125: the same coffee-to-desert text with @Image tokens, but no image input is wired [J]. Unused PrimitiveStringMultiline 153 (juice) and 155 (street photographer) [J] | StringConcatenate 6346: prefix `photorealistic, natural lighting, realistic textures` + delimiter " " + selected CR Text 6716 "samurai" (2494 chars) [J] | `integrated_multimodal_description`, pop-art, preceded by an alignment sentence ("Picture 1 at 0.00 s; Picture 2 at 5.17 s"), 2529 chars [J] | 6 sections: subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music; 5082 chars [J] | `integrated_multimodal_description`, "Stylized 3D animation, Pixar-inspired cartoon rendering with a C4D and Octane look", 2314 chars [J] |
| Seed | 24, fixed (191) [J] | 24, fixed (15) [J] | 44 via SeedNode 6327 (base and refine) [J] | 20261220, randomize (129) [J] | 261662374822964, randomize (129) [J] | 20261220, randomize (129) [J] |
| Outputs | SaveVideo 193 (pass 1), 216 (pass 2) [J] | SaveVideo 146 (pass 1), 113 (pass 2) [J] | VHS 6541 (base, 1056x608), VHS 6606 (refine, 2144x1216) [J] | SaveVideo 92 [J] | SaveVideo 92 [J] | SaveVideo 92 [J] |
| Saved-state traps | Bypassed PrimitiveInt 201, 202 (unused). Note 221: "scale_by = 1.20 gives error" [J] | Prompt with @Image tokens and no image input; two unused prompts [J] | Bypassed reference nodes; 3 unused CR Texts (6712, 6713, 6715); FancyTimerNode `elapsed_time_str` "83:45:551", meaning not stated [J] | none | none | Named "T2V" but its images are not wired [J] |

**Audio.** All six decode audio from the same sampler output (VAEDecodeAudio fed by the sampler), so audio is generated jointly with the video [J][I].

### 1b. Where the notes and the JSON disagree

| # | Notes say | JSON says | Status |
|---|---|---|---|
| 1 | NOTES Src 5: AI Ninja pass 1 is LCM, CFG 1, the 7-value sigma list, shift video 12 / audio 3 | FL2VA file: sampler `er_sde` (189), BasicScheduler `simple` 6 steps (188). No LCM. No shift node in either AI Ninja file. The 7-value list appears only in the official Comfy files (143, 147) | CONTRADICTED [J] |
| 2 | NOTES Src 5: the JSON uses `er_sde` plus the shorter list `0.909375, 0.857143, 0.666667, 0` for pass 1 | That list is pass 2 only (ManualSigmas 208 → refine sampler 213). Pass 1 uses BasicScheduler | MIS-ASSIGNED [J] |
| 3 | NOTES Src 5: pass 2 is 2 steps with sigmas `0.7, 0.494118, 0` | Connected pass 2 is 3 steps starting at 0.909375. The `0.7` list (209) has no output link; the 2-step BasicScheduler (214) is also unconnected | CONTRADICTED [J] |
| 4 | NOTES Src 5: "fp16 file suggested" for the latent upscaler | Node 210 loads the bf16 file. fp16 appears only in a Note (215) | MINOR [J] |
| 5 | NOTES Src 5: upscale to 1440p, about 440 s | File A: target = pass-1 size x 1 (scale_by = 1). The 2560x1440 widget is overridden by links. File B scales x 2 | CONTRADICTED for file A [J] |
| 6 | NOTES Src 5 gives shift 12 / audio 3 for the AI Ninja run | Shift 12/3 is stated only in CG Pixel (node 329, `widgets_values_named`: shift_video 12, shift_audio 3) | UNSUPPORTED for AI Ninja [J] |
| 7 | NOTES Src 4: "Pika Flex LoRA" on the Singularity Ref2VA base | The LoRA is `pika_h3_flex_fl2va_v1_bf16`, the FL2VA variant, on a Ref2VA model. Comfy's own Ref2VA template uses `pika_h3_flex_ref2va_v1_bf16` | SPECIFIED NOW, and the pairing is unusual [J] |
| 8 | NOTES Src 1: SageAttention and EasyCache speed-ups | No Sage or EasyCache node in any of the six. The attention patches present are sol-attn (BlockSparseAttention) and VedaSparse | NOT IN FILES [J] |
| 9 | OPUS #2: the real repo file is `Minimax-h3_Singularity_ref2va_v2_pruned_int8.safetensors` | CG Pixel loads `Minimax-h3_Singularity_ref2va_v2_Pruned_int8.safetensors` (capital P) | NAME MISMATCH [J] vs [N]. On a case-sensitive Linux host (Kaggle) this lookup may fail [I] |
| 10 | NOTES Src 1: pruned about 21 GB | Comfy note: `minimax_h3_fl2va_pruned_int8_convrot` is 19.53 GB | MINOR [J] vs [N] |
| 11 | NOTES (Workflow choice): the ComfyUI JSONs use an NVFP4 encoder that "needs a Blackwell RTX 50 card" | Five of six use the NVFP4 AWQ encoder (14.61 GB, per note). CG Pixel uses Q2_K GGUF. No file says "Blackwell" | PARTLY [J]; the Blackwell claim is [N] only |
| 12 | NOTES Src 6: use SamplerCustomAdvanced, not KSampler | All six use SamplerCustomAdvanced. No KSampler node exists in any of them | CONSISTENT [J]; not A/B tested in the files |
| 13 | NOTES Src 4: two passes, 6 steps, denoise 0.32, 2.5 MP, sharp_curve, LMS, refiner, all strength 1 | Matches [J] (nodes 6594, 6612, 6684, 6686, 6722). Not in the notes: the euler base sampler, sa_solver refine sampler, SeedNode 44, the photorealistic prefix, and the bypassed reference nodes | CONSISTENT, with extras [J] |

### 1c. OPUS section 2 statuses that touch these files

| Claim (OPUS #) | Status | Where it shows in the six files |
|---|---|---|
| #1 Singularity v2 exists, Ref2VA | CONFIRMED | CG Pixel node 215 |
| #2 "int8_convrot_r2" file, PSNR | CONTRADICTED | Not in any of the six. CG Pixel's name differs in case (row 9 above) |
| #4 Pika Flex Turbo 8-step HD LoRA | CONFIRMED | Not used in any of the six |
| #6 "use the 4-step lite at 6 steps" | CONTRADICTED | Not used in any of the six |
| #8 never stack a turbo LoRA on the official Pika LoRA | CONFIRMED | No turbo LoRA in any of the six. CG Pixel stacks four non-turbo LoRAs on the refine path |
| #9 official sigmas 1.0 ... 0.0, 6 steps, CFG 1 | CONFIRMED | Nodes 143 (D, F) and 147 (E), exactly the same list |
| #10 LoraLoaderModelOnly drops 27-63% of updates | NOT FOUND | All six use LoraLoaderModelOnly, including the official templates. Not actionable |
| #11 SamplerCustomAdvanced, not KSampler | Advice CONFIRMED (by aiseek, NOTES Src 6) | All six use SamplerCustomAdvanced |
| #12 Sage 1.0.6 fails on sm_75 shared memory | CONFIRMED | No Sage node in the six, so no action |
| #14 sol-attn silently falls back to dense on Turing, bf16 only | CONFIRMED | sol-attn in A (206) and B (118). Refine pass only |
| #15 VedaSparse needs sm_80, about 88 KiB | NOT FOUND | VedaSparse in C (944) |
| #16 T4 has FP16 and INT8 tensor cores, no BF16 or FP8 | CONFIRMED (NVIDIA spec) | Matters for every bf16 LoRA and the FP8 Veda predictor |
| #17 "hirokazu" T4 timings | NOT FOUND | none |
| #30 Open-H3-Regenerate-2K refiner LoRA | CONFIRMED | A (205), B (78), C (6686) |
| #35 six-section Ref2VA prompt | CONFIRMED | E (138) |
| #36 never put `<Picture N>` in detailed_description | NOT FOUND | E complies anyway: detailed_description uses only `<Subject N>` |
| #37 ref_image_size match vs max | match/max CONFIRMED | E (136) and C (6617) use match |
| #38 124 frames = 5.17 s at 24 fps | CONFIRMED | D, E, F, C (VHS metadata 5.17 s, 124 frames) |

### 1d. Our runner (`h3_director.py`) against the six files

| Setting | Ours | Six files | Read |
|---|---|---|---|
| Resolution | 480x832, 9:16 (line 34) | All six are 16:9. Range 0.4 MP (AI Ninja) to 2.6 MP (CG Pixel refine) | Ours is the low end. 9:16 is not in any file |
| Steps | 6 (line 285) | 6 in D, E, F, C base and refine, A pass 1. 4 in B pass 1 | Match, except B |
| Sampler | `pika_renoise` default (line 285) | LCM (D, E, F), er_sde (A, B), euler (C base), sa_solver (C refine) | Our sampler is in none of the files. Equivalence **not stated** |
| Sigmas | `custom_sigmas: ""` (line 286) | Official 6-value manual list (D, E, F) | Equivalence **not stated**. Test |
| Guidance | `guidance_scale` 1, `guidance_phases` 1 (line 285) | BasicGuider in all six, cfg 1 in C refine | Match in effect [I] |
| Shift | `flow_shift` 12 (line 286) | 12 only in C (`shift_video`). Not stated in the others | Match where stated |
| LoRA names | `pika_h3_flex_fl2va_6step_v1_bf16`, `pika_h3_flex_ref2va_6step_v1_bf16` (lines 36-37) | `pika_h3_flex_fl2va_v1_bf16`, `pika_h3_flex_ref2va_v1_bf16` | Names differ by "6step_". Same file **not stated** |
| Frames | 107 to 362 in steps of 17 (lines 32-33) | 124 for 5 s (D, E, F, C). 192 for 8 s (A, B) | 124 is in our legal set [I] |
| Ref sizing | `image_refs_relative_size` 100 (line 293). No ref-size mode set | `ref_image_size` = match (E, C) | Wan2GP equivalent of "match" **not stated** [I: probably the same idea] |
| Identity text | KEEP constant (line 41) | No negative prompt path in any of the six. C adds "Avoid ..." sentences in the positive prompt | Ours already locks identity. Keep it |
| Audio | `audio_prompt_type` "" and `audio_refinement` none (lines 286, 289) | All six generate audio jointly [J][I] | Our film uses ElevenLabs audio [N]. Not a conflict |
| Attention / memory | None set | ComfyUI nodes in A, B, C | ComfyUI only. Wan2GP equivalent **not stated** |
| Refine pass | None | Three of six (A, B, C) | Ours has none |

---

## 2. Part scorecard

### 2a. Facts used for hardware and cost

- **T4 (Turing).** FP16 and INT8 tensor cores. No BF16 or FP8 tensor cores. [N, OPUS #16 CONFIRMED]
- **L4 (Ada).** BF16 and FP8 native. 22.5 GB. [N, OPUS section 3 table]
- **A100 40/80 GB.** BF16, no FP8. [N, OPUS section 3 table]
- **G4 (RTX PRO 6000 Blackwell, 96 GB).** BF16, INT8, FP8 and NVFP4 native. About 176 GiB host RAM. [N, OPUS section 3 table]
- **sol-attn.** bf16 only. Dense fallback on Turing. [N, OPUS #14 CONFIRMED]
- **VedaSparse hardware needs.** Not stated. [N, OPUS #15 NOT FOUND]
- **NVFP4 encoder.** NOTES says it needs Blackwell [N]. L4 and A100 native NVFP4 **not stated**; [I] not native there.
- **Measured and reported times and VRAM:**
  - Our Kaggle T4, Pika 6-step, Wan2GP, 480x832, one 5.17 s clip: 8 min 50 s [N, via OPUS #19, cites HANDOFF].
  - Jigs10 Wan2GP, 16 GB, 480p, FL2VA: 11.5-16.5 min per 5 s clip. Original H3 about 30 min [N, Src 2].
  - CG Pixel (card not stated): base 0.6 MP about 11 min; base plus 2.5 MP refine about 1 h [N, Src 4].
  - AI Ninja (RTX 5060 Ti 16 GB): base 60-200 s; 1440p upscale about 440 s [N, Src 5]. The saved file does not reach 1440p (1b row 5).
  - aiseek (3060 12 GB): 13 min; 0.7 MP about 2x faster than 1.5 MP [N, Src 6].
  - Mickmumpitz (RTX 5080): H3 high-res re-render about 15 min per shot [N, Src 7].
  - Colab G4 user: 15 s at 1344x768, 362 frames, 8 steps, 7 min 55 s [N, OPUS section 3 evidence].
  - Our 5 s at 768x1344 on G4: 4-6 min. **Estimate only** [N, OPUS EST].
  - Weights from the JSON notes: DiT pruned int8 convrot 19.53 GB; NVFP4 text encoder 14.61 GB; video VAE 2.62 GB; audio VAE 577.2 MB [J].
  - Frames: 124 at 5 s, 192 at 8 s, from the formula in nodes 132, 161, 166 [J].

### 2b. Scorecard

Columns: **Quality** = expected effect on cel-shaded anime. **Risk** = line flicker / realism drift / identity, each H, M, L, or ? (unknown). **L4 / A100 / G4** and **T4** = whether the part has a hardware barrier (Y = no barrier stated).

| # | Part (JSON nodes; source) | Quality for our anime | VRAM / time | Risk L / R / I | L4 / A100 / G4 | T4 | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Official 6-step recipe: Pika Flex LoRA at 1.0 + LCM + 6-value sigmas (134, 143, 145, 147, 123) [J]; OPUS #8, #9 [N] | Model's intended schedule [I]. The LoRA's effect on cel art is untested | 6 model passes, no CFG pass [I] | ? / ? / L [I] | Y [I] | Y. Our 6-step Wan2GP run on T4 is proven [N] | **ADOPT** as baseline arm |
| 2 | BasicGuider, single conditioning, no negative input (126, 190, 207, 6711, 16, 143) [J] | Neutral. No negative path, so "avoid" text is positive text only [I] | One model call per step, the cheapest guidance mode [I] | L / L / L [I] | Y | Y | **KEEP** |
| 3 | Sigma shift 12 video / 3 audio (329, CG Pixel only) [J] | Same value as our `flow_shift` 12 (line 286). Audio shift matters little if audio is ElevenLabs [I] | None [I] | L / L / L | Y | Y | **KEEP 12** |
| 4 | Attention backend "comfy kitchen attention" (177, 126, 327) [J] | not stated | not stated | ? / ? / ? | not stated | not stated | **TEST** by seed-matched pixel diff |
| 5 | MiniMaxChunkFeedForward, chunks 2, threshold 4096 (175, 151, 326) [J] | Expected neutral: chunking is exact math [I] | Lower peak VRAM; small time cost [I] | L / L / L | Y [I] | Y [I] | **ADOPT for VRAM** if we use ComfyUI. Check parity |
| 6 | MiniMaxLowVRAMAttention, head_chunks 2 (328, CG Pixel) [J] | Expected neutral [I] | Lower attention peak; slower [I] | L / L / L | Y [I] | Y [I] | **TEST** only if VRAM-bound |
| 7 | VedaSparseAttention, predictor `minimax_h3_t2va_veda_8nfe_600step_preview_fp8`, sparsity 32 / 32 (944, CG Pixel; applies to base and refine) [J] | Unknown. Sparse attention with a "preview" predictor can soften edges and faces [I] | Claimed about 33% faster; user claim, untested [N, Src 3] | M / ? / M [I] | Predictor is FP8: native on L4 and G4 [N]; A100 not native [N]; Veda's own needs not stated | FP8 not native; no speed claim verified [N] | **AVOID** until A/B |
| 8 | BlockSparseAttention "sol-attn" on the refine pass only (206, 118, AI Ninja) [J] | Unknown. The refine pass decides identity [I] | Claimed sparse, not measured [N] | M / ? / M [I] | not stated | Dense fallback on Turing, no saving [N, OPUS #14] | **AVOID** on T4. TEST on Ampere only if needed |
| 9 | Re-noise refine: start sigma 0.909, 3 steps, size x1 (A) or x2 (B) (208, 144, 212, 167) [J] | Re-noising from 0.909 is near full, so faces and colour can change [I]. Notes say a strong refiner changes identity [N, Src 5]. With x1 there is no size gain [J] | +1 pass; about 440 s for 1440p on a 16 GB card [N] | H / M / H [I] | Y [I] | Y, but slow [I] | **AVOID** as configured |
| 10 | Latent upscale plus tiled refine: denoise 0.32, 6 steps, sa_solver, cfg 1, 0.6 MP to 2.5 MP (6594, 6600, 6596, 6612, 6590) [J] | Likely more face detail at higher pixels [I]. Denoise 0.32 is mid-range; notes give 0.4 as the max [N, Src 4] | Heavy: base about 11 min, plus about 50 min on CG Pixel's card [N] | M / M / M [I] | Y. Upscaler runs bf16 on cuda [J] | Slow or unclear. bf16 has no tensor cores on T4; timings NOT FOUND [N, OPUS #17] | **TEST** as A/B arm. Ampere first. Pika LoRA only |
| 11 | Temporal tile split: chunk 136, overlap 17, anchor 0.999 (6627) [J] | Inactive for 124 frames, because the chunk (136) is longer than the clip [I] | None for 5 s shots [I] | L | Y | Y | **SKIP** for 5 s shots |
| 12 | Spatial tile split: 2x3 tiles of 512, overlap 128 (6692) [J] | Seams possible at tile borders [I] | Lowers peak VRAM [I] | M / L / L [I] | Y | Y | **TEST** only with row 10 |
| 13 | Four-LoRA refine stack: Pika FL2VA, sharp_curve_branches, LMS r64, refiner rank 16, all 1.0 (6714, 6722, 6684, 6686) [J] | No per-LoRA evidence in any file or note. "sharp_curve" suggests edge sharpening [I]: halo or hard-line risk | Three extra LoRA loads; sizes not stated | H / M / M [I] | ? | ? | **AVOID** as a bundle. Test singly |
| 14 | Open-H3-Regenerate-2K refiner LoRA, rank 16, 1.0 (205, 78, 6686) [J] | Refinement detail. OPUS #30 CONFIRMED as a refiner LoRA [N] | Small (about 155 MB, Src 5) [N] | L-M / M / M [I] | Y | Y | **TEST** at lower strength (NOTES says lower it) |
| 15 | Ref2VA, 2 refs, `ref_image_size` match (136, 149, 150) [J] | Strongest identity anchor of the six: one ref per subject [N, Src 1 and 6; I] | Each ref adds tokens. "max" costs several times more [N, OPUS #37] | L / L / L-M [I] | Y | Ref2VA on T4 through Wan2GP is **not proven** in the notes (Src 2 tested FL2VA only) | **ADOPT**, with `match` (not `max`). `max` only as a test if the face drifts |
| 16 | Ref2VA with one ref, input chain bypassed (6617 with 6349, 6681 bypassed, C) [J] | Identity from one ref only [I]. Saved state is broken [J] | Less than two refs [I] | L / L / M [I] | not applicable | not applicable | **AVOID** as saved |
| 17 | FL2VA first + last keyframes with the alignment sentence (148, 147, 140, D) [J] | Strong end-pose control. The first frame sets identity [I]. Our start and end LEAP frames map directly | Low: two images [I] | L / L / L-M [I] | Y | Y. FL2VA on Kaggle T4 is proven [N, Src 2] | **ADOPT** for keyframe shots |
| 18 | Output size copies the first frame, rounded to 32 (149, 150, 151, D) [J] | A 1536x2752 keyframe would set a huge output [I]. Resize first | Scales with pixels [I] | not applicable | not applicable | not applicable | **ADOPT the rule**: resize keyframes first |
| 19 | Prompt structure: six sections (138, E) and `integrated_multimodal_description` with timed beats (140, 6716) [J]; OPUS #35 [N] | Better obedience [I]. No A/B in the files | None | L / L / L [I] | Y | Y | **ADOPT** the structure. Add our own anime style line |
| 20 | Realism wording: prefix "photorealistic, natural lighting, realistic textures" (6346); "Photorealistic cinematic ..." openers (6715, 6716); "Live-action" (6713, unused); "Ultra-photorealistic" (155, unused); "Pixar-inspired ... C4D and Octane" (F, 140) [J] | Pushes toward realism or a 3D render [I] | None | L / H / L [I] | not applicable | not applicable | **AVOID** for cel-shaded anime |
| 21 | NVFP4 AWQ text encoder, Qwen3-VL-32B, 14.61 GB (176, 13, 128) [J] | Prompt quality unknown [I] | 14.61 GB; can sit in system RAM [J, N Src 1] | ? | G4 native [N]. L4 and A100 not native [I] | Blackwell-only per NOTES [N]. Not runnable natively on T4 [I] | Use on G4. T4 needs another encoder: **not stated** |
| 22 | Q2_K GGUF text encoder (6688, C) [J] | Very heavy quantisation. Prompt-obedience risk [I] | Smaller; size not stated | M / ? / M [I] | Y [I] | Y [I] | **AVOID** as default. Test against row 21 |
| 23 | Pruned int8 convrot DiT, 19.53 GB (174, 127, 215) [J] | int8 may lose fine line detail. No bf16 A/B in the files [I] | Smallest DiT here [J] | M / ? / M [I] | Y: INT8 tensor cores on L4 and A100 [I] | INT8 tensor cores exist [N]. Whether the convrot kernel runs on T4 is **not stated** | **TEST** against bf16 on G4 |
| 24 | Video VAE int8 convrot, 2.62 GB; audio VAE fp32, 577 MB (119, 120, 186, 187, 11, 24, 207, 208) [J] | A quantised video VAE can add colour or line error [I] | Small | M / L / L [I] | Y | Y | **TEST** only if banding or flicker appears |
| 25 | Resolution: 0.98 MP 16:9, 1344x768 (115, E) [J]; 0.6 MP base, 1056x608 (6345, C) [J] | More pixels per face help identity [I]; OPUS point 4 agrees [N] | Scales with pixels [I]; G4 768p estimate 4-6 min [N] | L / L / L [I] | G4 yes. L4 tight at 22.5 GB [N] | Not realistic on Kaggle quota [N, OPUS] | **TEST** 768x1344 on G4. 9:16 is untested in these files |
| 26 | Steps: 6 (D, E, F, C) vs 4 (B pass 1, node 9) [J] | 6 steps: faces less refined and background text broken [N, Src 2]. Four steps is weaker [I]. 8-step Turbo is the OPUS challenger [N] | Linear in steps [I] | not applicable | not applicable | not applicable | **KEEP 6**. 8-step Turbo only as its own LoRA, never stacked |
| 27 | Clip length: 124 frames at 5 s (132, 133, 6344) vs 192 frames at 8 s (166, 167, 161) [J] | Longer clips drift more per shot [I] | Linear in frames [I] | not applicable | not applicable | not applicable | **KEEP 5 s** (124 frames) for our 3-5 s shots |
| 28 | Sampler family: er_sde (A, B), euler (C base), sa_solver (C refine), pika_renoise (ours) [J] | No A/B in the files | Same steps, same cost [I] | ? | Y | Y | **TEST** er_sde and euler against `pika_renoise` on the same seed and keyframes |
| 29 | Seeds: fixed 24 (A, B), SeedNode 44 (C), randomize (D, E, F) [J] | None | None | not applicable | not applicable | not applicable | Use fixed seeds (42, 123, per the OPUS T0 plan [N]) |
| 30 | Process traps in saved graphs: bypassed nodes (C 6681, 6349; A 201, 202); prompts stored but unlinked (A 197 vs 220); widget sizes overridden by links (A 197 holds 864x1536, a 9:16 size, but links set 16:9; B 80) [J] | None | None | not applicable | not applicable | not applicable | **Do not copy** the saved graphs as they are. Read the links |

---

## 3. Top 5 parts to adopt for anime

1. **Official Pika H3 Flex 6-step recipe (scorecard row 1).** Pika Flex LoRA at 1.0, LCM sampler, the 6-value manual sigma list (1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0), CFG-free BasicGuider, 124 frames at 24 fps. *Why:* it is the one recipe identical in three files (D node 143, E node 147, F node 143). It matches our 6-step runner and needs no extra passes. *Caveat:* our runner uses `pika_renoise` and its own schedule. Run one A/B on the same seeds and keyframes before switching. Never stack a turbo LoRA on it [N, OPUS #8].

2. **Official Ref2VA identity wiring (row 15).** Two references, one per subject. `ref_image_size` = match. The 6-section prompt, with `<Picture N>` only in subject_definitions and retention_analysis, and `<Subject N>` in detailed_description. *Why:* the cleanest identity wiring in the set, and it fits our character sheets. *Caveats:* crop the sheets to face and full body first; our 16:9 composites shrink the face at match size [N, OPUS section 6]. No file wires Ref2VA with keyframes, so test refs and keyframes separately first. Keep `match`; `max` is a test only.

3. **FL2VA keyframe template with the alignment sentence (row 17, row 18).** First and last frame, plus "Picture 1 aligns with the 0.00-second mark; Picture 2 aligns with the end". *Why:* our approved start and end keyframes fit this template one to one, and the alignment line anchors the end pose. *Must do:* resize each keyframe to the target size before feeding it, because in the Comfy template the output size copies the first frame (rounded to 32) [J][I]. Feeding the 1536x2752 LEAP frame as is would set a 1536x2752 output.

4. **Two-stage low-denoise tiled refine, as an A/B arm (row 10).** Base at 0.6 to 0.98 MP, then latent upscale and tiled refine at denoise 0.32, 6 steps, cfg 1, with the single Pika LoRA only. *Why:* it is the only file that reaches a higher-pixel detail pass with a bounded denoise. The AI Ninja files re-noise from 0.909 instead. Higher pixels help small faces [I]. *Caveats:* drop the four-LoRA stack (row 13); test on Ampere first (the upscaler runs bf16 on cuda); measure identity ourselves, since no published identity scores exist [N, OPUS #34]. Cost is high: about 1 h on CG Pixel's card [N].

5. **Chunked feed-forward and "comfy kitchen attention" for VRAM headroom (rows 4, 5, conditional).** MiniMaxChunkFeedForward (chunks 2, threshold 4096) and the ModelAttentionBackend "comfy kitchen attention". *Why:* present in three of the six files, no quality claim in any note, and the cheapest route to fit a 768x1344 or refine pass on 16 GB [I]. *Caveats:* both are ComfyUI nodes, and Wan2GP equivalents are **not stated**. Run a seed-matched pixel diff against the plain path before use.

---

## 4. Parts to avoid

1. **Realism and 3D wording (row 20).** The CG Pixel prefix "photorealistic, natural lighting, realistic textures", the "Photorealistic cinematic" openers, and the Pixar/C4D wording. Keep our own cel-anime style line and the KEEP constant (line 41).
2. **Re-noise refine from sigma 0.909 (row 9).** It can change faces and colour. A size factor of 1 gives no size gain.
3. **The four-LoRA refine stack (row 13).** `sharp_curve_branches` and LMS have no evidence in any file. Test singly or not at all.
4. **FL2VA Pika LoRA on the Ref2VA Singularity base (CG Pixel).** It is a mismatched adapter for the mode. If we use Ref2VA, use the ref2va LoRA, and test any mix first.
5. **VedaSparse with the "preview" predictor (row 7) and sol-attn on the refine pass (row 8).** sol-attn is bf16-only and falls back to dense on T4. The Veda predictor is FP8, which T4 cannot run natively.
6. **Q2_K GGUF text encoder as default (row 22), and NVFP4 on T4 (row 21).** Both are lossy or unsupported. Test prompt obedience before any use.
7. **Four-step pass 1 and 8-second clips (rows 26, 27).** Fewer steps and longer clips both raise drift risk.
8. **Copying the saved graphs as they are (row 30).** Bypassed reference nodes, stored-but-unlinked prompts, widget sizes overridden by links, and "scale_by 1.20" which errors (AI Ninja note 221).
9. **Stacking a turbo LoRA on the official Pika LoRA.** Not in any of the six. Listed because the Gemini plan proposes it [N, OPUS #8 CONFIRMED].

---

## Open items

- **Not in any file:** 9:16 output, cel-shaded or anime prompts, identity scores, Ref2VA with keyframes, and T4 timings per part.
- **Add to T0:** precision (bf16 vs int8 DiT, and the video VAE), since no file tests it.
- **Ask the owner:** the AI Ninja and CG Pixel saved graphs were captured in a state that does not match the notes. Confirm which graph produced the reported run before quoting its settings.
