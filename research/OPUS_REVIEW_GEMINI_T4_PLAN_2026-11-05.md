# Opus review of the Gemini T4 video plan (2026-11-05)

Input: `research/GEMINI_T4_VIDEO_PLAN_2026-11-05.md` (unverified). Read-only review. Web-checked on 2026-11-05. No GPU runs, no downloads, no paid calls.
Labels: CONFIRMED (source says it), CONTRADICTED (source says otherwise), NOT FOUND (no source; may be invented). All timings and costs for GPUs we have not run are ESTIMATES.

## CORRECTION 2026-11-05 (Claude: every Gemini link was fetched; the Hugging Face file lists were read)
This review called many items NOT FOUND / CONTRADICTED. Fetching the pages shows that was largely WRONG. What exists:
- `WAS/Minimax-h3_Singularity_v2_pruned` (112,847 downloads) holds `Minimax-h3_Singularity_ref2va_v2_pruned_int8_convrot_r2.safetensors` EXACTLY as Gemini said (#2). `WarmBloodAban/Minimax-h3_Singularity` has 1,058,924 downloads and 961 likes.
- `Abiray/Minimax-h3-Singularity-V2-Pruned-GGUF` holds Singularity Q3_K_M / Q4_K_M / Q5_K_M / Q6_K (#3).
- `Pika-Labs/Pika-H3-Flex-Turbo-LoRA` (56,494 downloads): 2-step draft, 4-step, and `pika_h3_flex_turbo_8step_hd_ref2va.safetensors`. Its card says the 4-step Ref2VA file is "the Singularity combo file" and that 8-step HD "also transfers to Singularity" (author's own demo videos). Settings on the card: LoraLoaderModelOnly 1.0, CFG 1, euler/lcm/res_multistep, simple scheduler, Ref2VA shift 12 video / 3 audio. Author H200 timing: 8-step HD 70 s vs official 6-step 60 s per 5 s clip.
- #17 hirokazu gist exists, but its 36.6 s/step is an fp16 run whose latents were NaN (broken); the working bf16 path is ~235 s/step at 736x416. 342 s, 517 s and 94.3 s are NOT in it. The T4 timing table stays unusable.
- #26 PDD-baked repo (28,842 downloads), #27 hybrid b30-49 (created 2026-10-30), #28 kitsune node (53 stars) exist. #29 Rung-Omega exists but is a promotional page (0 downloads, donation links): its 8.92x claim is unverified.
- Wan2GP (our runner) ALREADY ships `defaults/minimax_h3_singularity_v2_pruned.json` (model type minimax_h3_singularity_v2_pruned) and conversion maps so LoRAs load on Singularity V2. No finetune work is needed.
Still UNVERIFIED: that Wan2GP loads the Pika-Labs ComfyUI-format Turbo LoRA; any anime result; any independent identity test. Lesson: a reviewer's "not found" is not proof of invention; check the source before saying either.
The "Verdict" below was written before this correction; read it with the correction applied.

## 1. Verdict in 5 lines
1. Gemini mixes real items (Singularity v2, the Pika Turbo 8-step HD LoRA, FastH3 Omni, Open-H3-Regenerate-2K, the licence text, the Sage 1.0.6 patch) with invented ones (Rung-Omega/TheoremFlow, "hirokazu" T4 gist timings, a Singularity "int8_convrot_r2" build, a "b30-49" hybrid, a "PDD baked" checkpoint, the Viggle LoRA-loss claim).
2. Its whole T4 timing table rests on sources we cannot find. Do not use it. Our own number (5.17 s clip in 8 m 50 s on Kaggle T4) is the only proven T4 figure.
3. If we pay, a T4 is the wrong GPU. Colab now offers G4 = RTX PRO 6000 Blackwell 96 GB at about 8.7 units/h (about $0.87/h). It runs H3 in bf16/int8 with no offload; a Colab user ran H3 there (15 s, 1344x768, 8 steps, 7 m 55 s).
4. "Resolution does not matter, we upscale later" is only half true: a face that is 50 px wide at 480x832 loses identity, and an upscaler cannot bring it back. On G4 we can afford to generate at 768x1344 (Pika's native 768p class), which helps identity more than any LoRA trick.
5. Best plan: keep the proven Wan2GP + Pika H3 Flex 6-step route, move it to Colab G4, generate 9:16 at 768x1344, and A/B Singularity v2 + Pika Turbo 8-step HD as the challenger in T0. Kaggle T4 stays as the free fallback.

## 2. Claim check table
| # | Gemini claim | Status | Source |
|---|---|---|---|
| 1 | Singularity v2 (WarmBloodAban) exists; Ref2VA; merge of ref + fl + b25-49, then fine-tuned; distant-face restoration, less skin gloss, audio-ref fix | CONFIRMED | https://comfyui-wiki.com/en/news/2026-10-22-h3-singularity-v2 |
| 2 | Repo "WAS/Minimax-h3_Singularity_v2_pruned", file `..._pruned_int8_convrot_r2` 19.53 GiB, 26.1 dB PSNR, "13.0B AdaLN params dropped" | CONTRADICTED / NOT FOUND. Real file: `Minimax-h3_Singularity_ref2va_v2_pruned_int8.safetensors` 19.6 GB in WarmBloodAban repo; no r2/PSNR info | same as #1 |
| 3 | "Abiray Singularity V2 Pruned GGUF Q4_K_M 11.56 GB" | NOT FOUND. Abiray Q4_K_M 11.6 GB is stock H3, not Singularity; Abiray's Singularity v2 release is INT8/W4A8 safetensors | https://huggingface.co/Abiray/MiniMax-H3-Pruned-GGUF , https://alphasignal.ai/news/abiray-shrinks-minimax-h3-singularity-v2-from-34-gb-to-12-5-gb |
| 4 | Pika-H3-Flex-Turbo-LoRA: 2/4/8-step files, `pika_h3_flex_turbo_8step_hd_ref2va` 3.9 GB, Flex s=0.6 (0.5 for 2/4), exact rank concat, lite r32 0.31 GB | CONFIRMED. Repo owner unclear (akhaliq per wiki; sekkit copy says "duplicated from Pika-Labs") | https://comfyui-wiki.com/en/news/2026-11-02-pika-h3-flex-turbo , https://huggingface.co/sekkit/Pika-H3-Flex-Turbo-LoRA |
| 5 | 8-step HD on Singularity v2 = "HDR faces + Pika obedience in one pass" | PARTLY. Uploader's own claim that it "transfers"; the uploader's recommended Singularity pair is the 4-step Ref2VA file. No independent test | same as #4 |
| 6 | Use the 4-step lite_r32 at 6 steps if tight | CONTRADICTED. Card: step counts are not interchangeable; 4-step files are tuned for exactly 4; 8-step HD best at 6-8 | same as #4 |
| 7 | Turbo settings: CFG 1, euler + simple, strength 1.0; Ref2VA shift 12 / audio 3 | CONFIRMED (note: FL2VA turbo file uses shift 6, Gemini omits this) | same as #4 |
| 8 | Never stack a turbo LoRA on the official Pika Flex adapter | CONFIRMED | https://docs.comfy.org/tutorials/video/pika/pika-h3-flex |
| 9 | Official Pika sigmas 1.0 ... 0.0 (7 values), 6 steps, CFG 1 | CONFIRMED (docs: at least 7 sigma values, keep strength 1.0) | same as #8 |
| 10 | Stock LoraLoaderModelOnly drops 27-63% of LoRA updates (Viggle COMFYUI.md) | NOT FOUND; the turbo card itself says load with LoraLoaderModelOnly | #4 sources |
| 11 | SamplerCustomAdvanced, not KSampler, for Singularity (ComfyUI issue #15250) | Advice CONFIRMED by our own Source 6 (aiseek); issue number NOT FOUND | `research_transcripts/NOTES_RUN_BIG_VIDEO_MODELS.md` Source 6 |
| 12 | Sage 1.0.6 on sm_75 needs 67,584 B shared memory > 65,536; patch `num_stages=3 if head_dim==64 else 1` | CONFIRMED | https://ai-muninn.com/en/blog/solh3-two-stage-on-2080ti |
| 13 | "Patched Sage cuts step time 16.8% on Turing" | CONTRADICTED in detail. 16.8% was UNPATCHED 1.0.6 (with fallbacks) vs SDPA on a modded 22 GB 2080 Ti with 128 GB RAM; a kernel-modified build was slower (176 s vs 133 s). Not a T4 | https://ai-muninn.com/zh-TW/blog/minimax-h3-on-modded-2080ti-22gb |
| 14 | sol-attn silently falls back to dense on Turing (bf16 only) | CONFIRMED | #12 source |
| 15 | Veda sparse needs sm_80 and ~88 KiB smem | NOT FOUND (not checked deeply) | - |
| 16 | T4: FP16 + INT8 tensor cores, no BF16/FP8; 65 TFLOPS FP16, 130 TOPS INT8, 320 GB/s | CONFIRMED (NVIDIA spec) | https://www.nvidia.com/en-us/data-center/tesla-t4/ |
| 17 | "hirokazu Colab T4 Gist" measured 36.6 s/step (Q4_K_M 736x416), 235/342/517 s/step bf16 emulation, 94 s VAE | NOT FOUND. The only Colab H3 gist found recommends A100 40 GB and warns T4/L4 may run out of RAM/VRAM | https://gist.github.com/safa-dayo/057bcf801828e149f0d9077b63b7aa6b |
| 18 | "17.04 s/step at 864x480 on 2080 Ti" and "NVFP4 DiT 2.68x slower than Q4_K_M on T4" (ai-muninn Part 12) | NOT FOUND in the ai-muninn pages fetched | #12, #13 sources |
| 19 | Whole T4 timing table (3.2-18.8 min per clip) and "36-42 GPU-h per film" | UNSUPPORTED estimate built on #17/#18. Our measured T4 figure: 8 m 50 s per 5.17 s clip (Pika 6-step, Wan2GP) | HANDOFF / PLAN_v4 |
| 20 | Licence: Applicable Territory = world minus EU, UK, Korea, US; under US$20M revenue; no MAU cap | CONFIRMED (§I.3, §I.5, §IV.1) | https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE |
| 21 | §V.4: no use/display of Outputs outside the Applicable Territory | CONFIRMED. Global YouTube release is a real problem | same |
| 22 | §IV.2 show "MiniMax H3" on commercial product UI; §III.3 "Powered by" encouraged; Exhibit A requires AI-generated disclosure | CONFIRMED (Exhibit A item 12). Outputs are NOT Model Derivatives (§I.11) | same |
| 23 | Pika Flex and Singularity are Model Derivatives under the H3 licence | CONFIRMED for Pika Turbo (card says so); Singularity licence tag not stated on the wiki | #4, #1 |
| 24 | Global commercial licence via Comfy Org | CONFIRMED; from US$5,000/month; Comfy Cloud subscriptions include commercial rights for what you generate there | https://comfy.org/minimax/license.md , https://comfyui-wiki.com/es/news/2026-08-30-comfy-minimax-license |
| 25 | FastH3 Omni 8-step, up to 12 refs, single-file INT8 ConvRot for ComfyUI | CONFIRMED (22.2 GB INT8 ConvRot default; FP8, NVFP4 builds; 124/243/362 frames). Start/end frames not mentioned. Docs: FastH3 trades some motion/audio fidelity for speed | https://comfyui-wiki.com/en/news/2026-10-20-fasth3-omni , https://docs.comfy.org/tutorials/video/minimax/minimax-h3-fastvideo.md |
| 26 | "Alibaba PAI PDD 8-step baked into a pruned INT8 file (aptech0081)" | NOT FOUND. Official PDD is a LoRA + head bank applied by a custom node (8 steps; 4/6 allowed) | https://comfyui-wiki.com/en/news/2026-08-26-minimax-h3-pdd-acc-lora |
| 27 | `hyukudan/Pika-H3-Flex-Hybrid-b30-49` and `minimax_h3_hybrid_fl2va_ref2va_b30-49` | NOT FOUND. A b25-49 hybrid exists (FL base + Ref AdaLN blocks 25-49; loader has a configurable range) | https://comfy.icu/node/JR_H3_HybridLoader , https://civitai.com/models/3032822 |
| 28 | `kitsune123150/minimax-h3-hybrid-cond` node (first_frame, last_frame, refs) | NOT FOUND | - |
| 29 | Rung-Omega 4-trit base-243 checkpoint + TheoremFlow-Ω 8.92x speed-up | NOT FOUND. Looks invented | - |
| 30 | Open-H3-Regenerate-2K (NVIDIA) | CONFIRMED: open refiner LoRA, 768p draft to 2K/4K in 3 steps (NVlabs Sana). "24-layer StreamRender VAE" NOT FOUND | https://comfyui-wiki.com/en/news/2026-10-27-open-h3-regenerate-2k |
| 31 | ComfyUI-MiniMaxH3-Context-Loop v0.7.3 chains scenes | CONFIRMED it exists; "60+ clips, 12-frame de-dup, crash-safe" NOT FOUND. Gemini also claims to have read "your Drive" guide: unverified | https://www.runcomfy.com/comfyui-nodes/ComfyUI-MiniMaxH3-Context-Loop |
| 32 | Pika Flex Elo 1293 vs base H3 1277 | CONFIRMED (1277 single source) | https://alphasignal.ai/news/pika-drops-h3-flex-an-open-video-model-generating-audio-1-8x-faster , https://wavespeed.ai/blog/minimax-h3/pika-h3-flex-explained/ |
| 33 | "The AI Brief 8-test benchmark: 6-step Pika lost 2-6 to 20-step H3" | NOT FOUND | - |
| 34 | No published identity (ArcFace) scores for Pika or Singularity | CONFIRMED by absence; we must measure ourselves | - |
| 35 | 6-section Ref2VA prompt (subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music); max 9 images / 3 videos / 3 audio | CONFIRMED | #8 source |
| 36 | "Never put <Picture N> in detailed_description or the clip morphs into the sheet" | NOT FOUND (docs have no such warning). Cheap to obey anyway | #8 source |
| 37 | Split the 3-panel sheet into 3 separate refs; `ref_image_size` match vs max (2048 px short edge) | match/max CONFIRMED (max = better identity, several times the cost). Split advice is a plausible inference, not sourced; our Source 6 used ONE 3-panel image and warns more refs = up to 3x slower | #25 source; NOTES Source 6 |
| 38 | 124 frames = 5.17 s at 24 fps | CONFIRMED | #25 source |
| 39 | Larryvrh turbo: v4 for most work, v1 for heavy 4-step motion | CONFIRMED | https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo |
| 40 | Colab Pro+ T4 has ~51 GB host RAM; cu130 needed for s8xs8 | NOT VERIFIED; the Turing reference stack that works is torch 2.6 + cu124 | #12 source |

Pattern: Gemini attaches a precise date and repo to every line, including the invented ones. Treat every "[Verified Fact]" tag in that file as meaningless.

## 3. GPU / platform comparison with costs
Colab price basis: $10 = 100 compute units (pay-as-you-go), no bulk discount. Pro $9.99/month = 100 units. Pro+ $49.99/month = 500 units (some sources say 600; check in the logged-in UI). Pro+ adds background execution up to 24 h. GPU type is never guaranteed. Rates from https://mccormickml.com/2024/04/23/colab-gpus-features-and-pricing/ (measured 2026-03-10) and https://gpuperhour.com/blog/google-colab-alternatives . India price in INR: check the signup page while logged in.

| Option | VRAM / precision | Units/h | $/h | Time per 5 s clip | $ per clip | 15-min film (180 shots x 3 takes = 540 renders) |
|---|---|---|---|---|---|---|
| Kaggle T4 x2 (free, now) | 2 x 16 GB; FP16/INT8 only, no BF16/FP8; model must be pruned and offloaded | free, ~30 GPU-h/week | 0 | 8 m 50 s at 480x832, MEASURED | 0 | ~80 h = ~3 weeks of quota; 768p not realistic |
| Colab T4 | same card; host RAM small unless High-RAM | 1.19 | ~0.12 | ~9-10 min (same as Kaggle) | ~$0.02 | ~$10 (~95 units), ~85 h. No quality gain over Kaggle |
| Colab L4 | 22.5 GB, Ada: BF16 + FP8 native | 1.71 | ~0.17 | EST 3-5 min at 480x832 (pruned int8 still needed; 22.5 GB is tight) | ~$0.01 | EST ~$7, ~40 h. Cheapest, but still VRAM-limited |
| Colab A100 40 / 80 GB | BF16, no FP8 | 5.4 / 7.5 | 0.54 / 0.75 | EST 2-3 min | ~$0.02-0.04 | EST $15-25. Beaten by G4 on price and VRAM |
| **Colab G4 = RTX PRO 6000 Blackwell 96 GB** | BF16, INT8, FP8, NVFP4 all native; ~176 GiB host RAM; whole model fits, no offload | 8.71 | ~0.87 | EST 1.5-3 min at 480x832; EST 4-6 min at 768x1344 (8-step) | ~$0.03 (480p) / ~$0.07 (768p) | EST ~$25 (480p, ~260 units) or ~$45 (768p, ~450 units) incl. ~15 min setup per session |
| Colab H100 | 80 GB | not verified (one report ~$1.86/h) | ? | - | - | Skip until a rate is visible |

Evidence for the G4 estimate: a Colab G4 user ran H3 pruned INT8 base, 1344x768, 362 frames (15 s): 20-step 18 m 54 s, 8-step turbo 7 m 55 s, peak 54 GiB, PyTorch 2.11 + cu130 preinstalled (https://www.besthub.dev/articles/running-minimax-h3-on-96gb-rtx-pro-6000-via-gemini-pro-bcd6f38f505c). Another RTX PRO 6000 test: 864x480, 192 frames, 182 s with Sage (https://acecloud.ai/blog/minimax-h3-gpu-requirements/). Our 5 s clip has ~3x fewer frames, so per-clip time drops a lot; the numbers above are scaled guesses until T0 measures them.

Answer to "if we pay, is a T4 still right?": No. Paying for a T4 buys nothing over free Kaggle. The money should buy the G4: about 4-6x faster than T4, full precision (no fp16 overflow, no quantisation loss), and enough VRAM for 768p generation and for `ref_image_size = max`. A full film costs roughly one Pro+ month. Note Google AI Pro (Gemini Pro) subscribers get about 200 Colab units per month; check if the owner already has it.

Session costs to plan for: weights are ~40-60 GB and must be re-downloaded every Colab session unless kept on Google Drive (needs a paid Drive plan). Batch many shots per session.

## 4. Best plan + fallback (exact settings)
**Best plan (provisional; T0 decides between A and B)**
- Platform: Colab, pay-as-you-go units or Pro+; runtime G4 (RTX PRO 6000 96 GB). Same `director/` pipeline, Wan2GP headless (no ComfyUI switch).
- Model A (default, proven settings): MiniMax H3 Ref2VA (`minimax_h3_ref2va_pruned`, or the bf16 base if Wan2GP offers it on 96 GB) + official `pika_h3_flex_ref2va_6step_v1_bf16`, strength 1.0. Sampler `pika_renoise`, 6 steps, CFG 1, flow shift 12, one phase, no step-skipping cache, no extra turbo LoRA (exactly what `h3_director.py` already enforces).
- Model B (challenger): Singularity v2 Ref2VA (`Minimax-h3_Singularity_ref2va_v2_pruned_int8.safetensors` 19.6 GB, or `_v2_bf16` 61.7 GB on G4) + `pika_h3_flex_turbo_8step_hd_ref2va.safetensors` strength 1.0, 8 steps, euler + simple, CFG 1, shift 12 video / 3 audio. Needs a Wan2GP finetune entry and a director change (see 6).
- Resolution: 9:16 at 768x1344 (Pika native 768p class), 124 frames (5.17 s at 24 fps). Upscale later (Open-H3-Regenerate-2K or NVIDIA VSR), refiner strength low so the face does not change.
- Wiring: Ref2VA with start + end keyframe (our 1536x2752 LEAP frames) + identity refs. Refs: KRISHNA_IDENTITY_MASTER face crop as `<Picture 1>`, a full-body front crop as `<Picture 2>` (cropped from the 16:9 sheets, labels removed). Bind pictures to `<Subject 1>` in `subject_definitions` and `retention_analysis`; use only `<Subject 1>` in `detailed_description`. `ref_image_size` = match first; try max only if the face still drifts.
- Prompt: short camera/action lines with time codes; name what must be kept (face, hair, peacock feather, costume colours); avoid long skin descriptions.

**Fallback**: Kaggle T4 x2 (free), Model A exactly as today at 480x832 (proven, 8 m 50 s per clip). Use it for drafts and when Colab has no G4. Do not try Gemini's T4 tricks (Sage patch, GGUF, cu130) inside the main pipeline; they are untested and Wan2GP already works.

## 5. T0 test list (one Colab G4 session, about 1-1.5 h, about $1-1.5)
Base shot LEAP-03 (crouch -> launch) from DIRECTION.md, same start/end keyframes, same prompt, seeds 42 and 123 for every variant (8 clips).
| Variant | What | Why |
|---|---|---|
| V1 | Ref2VA, Model A (Pika 6-step), 480x832 | parity with the Kaggle clip; measures G4 speed |
| V2 | Ref2VA, Model A, 768x1344 | does higher generation resolution keep the child's face? |
| V3 | Ref2VA, Model B (Singularity v2 + Pika Turbo 8-step HD), 768x1344 | quality challenger |
| V4 | FL2VA, start + end only, Pika 6-step, 768x1344 | the existing FL route at the new resolution |
Record per clip: wall time (load / sample / decode), peak VRAM, units used. Judge (owner, full clip, full res): same Krishna in first, middle and last second; costume and feather; readable leap; artefacts (hands, feet, flicker); prompt obedience. Use `clip_tools.py qa`. Pick the winner; if V3 does not clearly beat V2, stay on Model A.

## 6. Risks and open questions
- Pipeline lock: `director/h3_director.py` (lines 34-40, 233-252) only allows the two Wan2GP Pika presets, `pika_renoise`, 6 steps, shift 12. Model B needs a new preset, a Wan2GP finetune JSON for Singularity v2, and support for the merged turbo LoRA in Wan2GP. Wan2GP support for that LoRA is NOT verified.
- Gemini's plan is ComfyUI-only (SamplerCustomAdvanced, BasicGuider, custom nodes). Switching to ComfyUI means a rewrite of the render step. Not needed for T0.
- `run_kaggle.py` is Kaggle-only. Colab needs its own runner (Colab MCP or a notebook) and a way to fetch only the .mp4s. Small job, but real.
- Vertical 9:16: no source shows Pika or Singularity tested in 9:16. Our Kaggle clip proves 480x832 works; 768x1344 is untested.
- Ref2VA + start/end frames together: our plan relies on Wan2GP accepting both; Singularity v2's card does not mention keyframes. V3 tests this.
- Our identity sheets are 16:9 composites with labels; at `match` size the face gets tiny. Crop them before T0.
- G4 availability on Colab is not guaranteed; units expire; sessions must re-download ~40-60 GB.
- Licence: CONFIRMED that outputs may not be used or displayed in the US/EU/UK/Korea. A global YouTube release needs geo-blocking, a Comfy/MiniMax commercial licence (from $5,000/month), or Comfy Cloud generation. Credits should show "MiniMax H3" and the film must be disclosed as AI-generated. Owner decision, still open.
- Open question: is the owner's Gemini/Google AI Pro plan (200 units/month) already active? If yes, T0 on G4 costs nothing extra.
