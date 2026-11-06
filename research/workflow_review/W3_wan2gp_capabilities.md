# W3: What the Wan2GP headless runner can do for MiniMax H3 and Pika H3 Flex

Reviewer: W3. Date: 2026-11-05.

Source: read-only Wan2GP checkout at commit bd1ff59. Root folder below is shortened to `wan2gp/`, which means `D:\aai work\kaggle_h3_test\wan2gp_src\`.
Short names: `H` = `wan2gp/models/minimax_h3/minimax_h3_handler.py`, `P` = `wan2gp/models/minimax_h3/pipeline.py`, `W` = `wan2gp/wgp.py`, `A` = `wan2gp/shared/attention.py`.
Runner under review: `python wgp.py --process <settings.json> --output-dir <dir> --profile 5 --verbose 2` (`D:\aai work\anime_studio\director\run_kaggle.py`).

Nothing was run, installed or downloaded. Every line number in this file was re-read in this pass. "Not found in code" means no match in the checkout.

## Headline findings

1. Pika H3 Flex is a single-phase, fixed-schedule route. The code rejects it with two phases, custom sigmas, step skipping, or the PDD, PTD, VDN, VEDA and FastH3 models (`P:825-832`, `H:1007-1014`, `H:673`).
2. Wan2GP's two-phase path (half-size phase 1, learned latent upscaler, Euler phase 2) is the nearest equivalent to the ComfyUI SelfLift two-stage sampler. It cannot be combined with Pika in Wan2GP.
3. `sol` attention does not run on the T4 (SM 7.5) or the A100 (SM 8.0). Validation accepts the override, and the run then fails at the first forward pass (`W:12322-12343`, `shared/sol_attn/interface.py:11,14-26`).
4. H3 forces bf16 in its model definition (`H:677`, `W:3323-3325`). `--fp16` has no effect on H3.
5. The runner's `--profile 5` only sets a default. A `memory_profile=N` entry in a settings file's `overrides` wins (`W:3681-3685`, `W:4204-4205`, `W:7560`).
6. The director writes `settings_version` 2.73 (`h3_director.py:298`), but the current version is 2.82 (`W:208`). H3 migrations below 2.75 and 2.74 then run on its settings (`H:1374-1377`). The Pika keys are not affected, but the director should write 2.82.
7. The director's `720x1280` option renders as `704x1280` (`W:7607-7609`, `h3_director.py:37`). The 32-pixel floor is applied silently.

---

## 1. Capability table

| Feature | Supported | Exact keys / values | file:line |
|---|---|---|---|
| Model families, FL2VA and Ref2VA, full and pruned | Yes | model_type `minimax_h3_fl2va`, `minimax_h3_fl2va_pruned`, `minimax_h3_ref2va`, `minimax_h3_ref2va_pruned` | `H:55-58`; `defaults/minimax_h3_fl2va.json`, `defaults/minimax_h3_ref2va.json` |
| Other H3 variants | Yes, per defaults | `minimax_h3_control` (and `_pruned`), `minimax_h3_fl2va_pdd`, `minimax_h3_ref2va_pdd`, `minimax_h3_ref2va_ptd_refasymopd`, `minimax_h3_vdn` (and `_pruned`), `minimax_h3_fasth3_omni` (and `_nvfp4`), `minimax_h3_image`, `minimax_h3_tts_ref2va_pruned`, `minimax_h3_singularity_v2` (and `_pruned`), `viggle_animate` | `H:59-62`, `H:659-660`; `defaults/minimax_h3_*.json` |
| Singularity V2 | Yes, finetune | architecture `minimax_h3_ref2va`; URL `Minimax-h3_Singularity_ref2va_v2_int8_convrot.safetensors`; 33B full and 20B pruned | `defaults/minimax_h3_singularity_v2.json:2-9` |
| Pika H3 Flex, FL2VA and Ref2VA | Yes, fixed rules | `sample_solver` "pika_renoise"; `num_inference_steps` 6; `flow_shift` 12; `guidance_phases` 1; `guidance_scale` 1; `custom_sigmas` ""; `skip_steps_cache_type` ""; `activated_loras` `pika_h3_flex_fl2va_6step_v1_bf16.safetensors` or `pika_h3_flex_ref2va_6step_v1_bf16.safetensors`; `loras_multipliers` "1.0" | `pika.py:10-12`; `P:825-832`; `H:673`; `H:1007-1014`; `profiles/minimax_h3_fl2va/Pika H3 Flex FL2VA 6 Steps.json:2-14` |
| Pika on other models | No | Rejected for `pdd`, `ptd`, `vdn`, `veda`, `fasth3` | `H:1009-1010` |
| Euler sampler | Yes | `sample_solver` "euler" | `H:758`; `P:823` |
| RES Multistep | Yes | "res_multistep" | `H:758` |
| Ralston 2S | Yes, UI label says about 2x slower | "ralston_2s" | `H:758` |
| ER-SDE | Implemented, hidden from UI | "er_sde" accepted by pipeline; not in the UI sampler list. Whether settings validation accepts it was not traced. | `P:823`, `P:1317-1365`; absent from `H:758` |
| Two-phase generation | Yes, not with Pika | `guidance_phases` 2; `num_inference_steps` (phase 1, default 20); `num_inference_steps2` (phase 2, default 3); `switch_threshold` (UI range 0.7-1.0, default 0.9035) | `H:694-697`, `H:725-733`, `H:1447-1451`; `P:927-928` |
| Phase-1 canvas | Yes | round(target / 2 / 32) * 32, minimum 32 | `P:927-928` |
| Latent upscaler between phases | Yes | scale factor = mean of the H and W ratios; file `minimax_h3/minimax_h3_latent_upscaler_3d_bf16.safetensors` | `P:1518-1523`; `minimax_h3_main.py:34-35`; `P:47` (`H3_TWO_PHASE_SCALE` 2.0) |
| Phase-2 sampler | Fixed Euler | `H3_PHASE_2_SAMPLE_SOLVER` "euler"; `H3_PHASE_2_SIGMAS` (0.9035, 0.6316, 0.3158, 0.0) defined | `P:48-49` |
| Automatic Turbo LoRA in phase 2 | Yes, two-phase only | `activated_loras` Turbo entry with `loras_multipliers` "0;1"; code key `minimax_h3_lora_turbo` = `minimax_h3_lightx2v_fl2v_turbo_4step_alpha16_v0.1.safetensors` | `P:441-467`; `H:41-42`, `H:798` |
| Ref2VA Turbo in phase 2 | Not automatic, quirk | Phase 2 always reads the FL2V key, including for Ref2VA. The REF key `minimax_h3_ref_lora_turbo` is used only by the face refiner. | `P:467`; `H:43-44`, `H:799`; `postprocessing/h3_face_refiner/wgp_bridge.py:137-160` |
| Custom sigmas per phase | Yes, non-fixed models only | `custom_sigmas` "slot1;slot2"; each slot a comma list of values in [0, 1), strictly descending; trailing 0 dropped; slot length sets `num_inference_steps` and `num_inference_steps2`; `switch_threshold` checked against the first value of slot 2 | `W:1093-1120`, `W:1215-1241`; `H:699`; `P:1239-1241` |
| Custom sigma starting at 1.0 | No | Values must be below 1 | `W:1111` |
| Custom phase-1 sigmas | Used as given | No flow shift applied; terminal 0 appended | `P:1239-1241` |
| Default schedule | Yes | linspace(1, 0, steps + 1), shifted by `flow_shift` for video; shift 3.0 for audio | `P:1227-1236` |
| Regenerate 2K LoRA | Yes, via preset | `open_h3_regenerate_2k_lora.safetensors`; `loras_multipliers` "0;1"; `switch_threshold` 0.909375; `custom_sigmas` "; 0.909375, 0.8571428571428571, 0.6666666666666666" | `constants.py:2`; `profiles/minimax_h3_presets/H3 Regenerate 2K 2 Phases.json`; `P:1532-1538`; `P:51` |
| Phase-2 spatial tiling | Yes | "~" in `video_prompt_type` or `guidance_phases` "2~"; 4 tiles; overlap ratio 0.25; alignment 32; `resolution_budget_tiled` 3840x2176 | `P:52-55`, `P:923`, `P:1595`; `W:1216`; `H:698-701` |
| Audio refinement extra phase | Yes | `custom_settings` `audio_refinement`: "none" or "enabled" (6 steps, denoise 0.5) | `H:713-724`; `constants.py:4-5`; `P:1765-1766` |
| Mask denoising mode | Yes | `custom_settings` mask mode: Grouped Rows (default) or Shared Timestep | `H:702-712` |
| Frame counts | Yes | `frames_minimum` 107, `frames_steps` 17, `frames_offset` 5 (valid lengths 107 + 17k) | `H:689-691` |
| Sliding windows, FL2VA and Ref2VA | Yes | `window_min` 124, `window_max` 481, `window_default` 362, `window_step` 17, overlap 1-120 step 17, default 18 | `H:840-842`, `H:918-921` |
| Sliding windows, Control | Yes | `window_max` 362 | `H:646` |
| Reference images, Ref2VA | Yes, max 9 | `image_prompt_type` letters T, S, E, V, L allowed; `image_ref_choices` "KI" (first image is subject), "I", "FI" (inject frames); `image_refs_relative_size` 50-400 | `H:844`, `H:846-854`, `H:860`, `H:1154` |
| Reference videos, Ref2VA | Yes, max 3 | each at least 2 s; `reference_video_max_frames` 362 (15 s); `reference_video_max_size` (768, 1344); guide choices "V-U", "V+-U", "V+*-U", "V1-U", "GV", "VU" | `H:861-880`, `H:1156`, `H:1168` |
| Reference audio | Yes, max 3 | each at least 2 s; `audio_reference_max_total_duration` 15 | `H:881-884`, `H:1064`, `H:1228` |
| Mixed reference files | Max 12 | across images, videos and audio | `H:1235` |
| Control video (ControlNet-Union) | Yes | `model_type` `minimax_h3_control` or `_pruned`; `control_net_weight_name` "Control"; `guidance_phases` locked to 1 | `H:627-658` |
| Spatial outpainting | Control: yes. FL2VA and Ref2VA: only with Grouped Rows | `video_guide_outpainting`; `outpainting_quantize_margins` 32 | `H:935-937`, `H:1081-1082`, `H:1098-1099` |
| Background removal of references | Yes | `remove_background_images_ref` (0 = off) | `W:7603`, `W:8524-8532`; `H:1464` |
| Video VAE choice | Yes | Video VAE system config: BF16 (`MiniMax-H3-video_vae_fp16.safetensors`), FP8 mixed, INT8 ConvRot decoder, LightVAE Lite BF16, LightVAE Lite INT8 ConvRot. Settings key for this choice not traced. | `H:815-824`; `minimax_h3_main.py:27-31` |
| In-model X2 spatial VAE upsampling | Yes | value "h3_vae*2"; scales 1.0, 1.5, 2.0 | `vae_upsampler.py:10-14`, `vae_upsampler.py:34-36`; `H:794-795` |
| Text encoder choice | Yes | Qwen3-VL-32B INT8 or BF16 layer 50; GGUF Q2_K and Q4_K_M; NVFP4 AWQ file; distilled 4B for P-H3-Image | `H:36-40`, `H:45-54`, `H:812-813` |
| NVFP4 text encoder | Code path present; needs FP4 hardware | FP4 only on RTX 50xx (sm120+) | `H:40`, `H:48`; `docs/INSTALLATION.md:320` |
| Attention: sdpa, auto, flash, xformers | Depends on install | `flash` added if `flash_attn` present; `xformers` if present | `A:276-283`, `A:296-300`; `docs/INSTALLATION.md:239` (flash needs RTX 30XX+) |
| Attention: sage (SageAttention 1) | Needs package, SM 7.0+, Triton | `attention_mode` "sage"; masks only on the Turing (SM 7.5) kernel; head dims 64 and 128 on pre-8.0 | `A:284-285`, `A:319-321`; `shared/sage1_core.py:60-95`; `docs/INSTALLATION.md:170-182` |
| Attention: sage2 (SageAttention 2.x) | Needs 2.x package, SM 8.0+ on all GPUs, Triton | `attention_mode` "sage2"; default pick order sage2, sage, sdpa | `A:286-287`, `A:313-315`, `A:334-338`; `shared/sage2_core.py:89-95` |
| Attention: sage3 | SM 10.0+ and Triton | "sage3" | `A:291-292`, `A:309-311` |
| Attention: sol (overrides only) | SM 8.6, 8.9, 9.0, 10.0, 12.0, 12.1; Triton; bf16 Q/K/V | override `attention_mode='sol'`; start tau from `attention_sparsity` (default 1.3); end tau 0.8; minimum 8192 tokens | `A:35-38`; `shared/sol_attn/interface.py:11,14-26`; `H:748`, `H:752-757`, `H:1455`; `P:46`; `sol_attention.py:14,32-39` |
| Attention: veda, vsa | SM 8.0+ with Triton, not HIP; H3 model-specific | `veda` only on veda model defs; `vsa` on FastH3 | `A:39-45`; `H:668-672`, `H:744-746`, `H:751` |
| Attention: vdn | VDN models only | "vdn" | `H:742`, `H:751` |
| Attention from the CLI | Limited | `--attention` accepts only auto, sdpa, sage, sage2, flash, xformers; sol, veda and sage3 only through overrides | `W:3673-3679`; `shared/cli_args.py:82` |
| Per-generation overrides | Yes | string such as `attention_mode='sol', memory_profile=4`; keys `memory_profile`, `compilation`, `attention_mode`, `transformer_quantization`, `text_encoder_quantization` | `shared/utils/generation_overrides.py:3,7,22`; `W:12332-12343` |
| Memory profiles | Yes | `--profile` 0-5 (docs: 4 recommended, 5 fail-safe); overrides `memory_profile=N` override the `--profile` default | `docs/CLI.md:192-208`; `W:3681-3685`, `W:4204-4205`, `W:7560`, `W:7632` |
| Transformer quantization | Yes | int8 (default, "Scaled Int8 (recommended)"), fp8, bf16 | `W:3687` |
| Compilation | Yes | disabled, cudagraph, transformer; `--compile` sets transformer; H3 records transformer CUDA graphs unless veda or fasth3 | `W:3689-3692`; `H:679` |
| dtype | Fixed bf16 for H3 | model definition `dtype` "bf16" overrides `--fp16` and `--bf16` | `H:677`; `W:3320-3326`, `W:3667-3670` |
| Turing BF16 convolutions | Yes | `scaled_fp16` installs FP16 tensor-core route for BF16 convs on Turing | `W:4291` |
| Frame rate | Fixed | `fps` 24 | `H:685`; `P:815-819` |
| Output size alignment | Yes, floor to 32 | `block_size` 32 and `vae_block_size` 32; width and height floored to the block size | `H:692-693`; `W:7607-7609`; `shared/resolutions.py:204-207` |
| Resolution budgets | Not enforced on headless runs | `resolution_budget` 2048x2048; `resolution_budget_tiled` 3840x2176. Headless validation checks only dimension limits and lock; the budget range is checked only for API and agent tasks. | `H:700-701`; `shared/resolutions.py:505-512`, `shared/resolutions.py:530-537`; `W:1138-1141`, `W:9739-9743` |
| Headless run | Yes | `python wgp.py --process <settings.json>`; `--output-dir`; `--profile`; `--verbose`; `--dry-run` validates the queue and exits | `W:15147-15230` |
| Settings file | JSON with `model_type`, `settings_version`, runtime keys | current `settings_version` 2.82; migrations below 2.75 and 2.74 | `W:208`; `W:3349-3353`; `H:1374-1377` |
| Step-skip caches | Spectrum and First Block Cache offered; off for Pika | `spectrum_cache`, `first_block_cache` true; First Block thresholds 0.06-0.14; `skip_steps_cache_type` "" turns skipping off. Non-empty token values not traced. | `H:63-66`, `H:736-740`; `H:1013-1014`; `P:831-832` |
| Pika Turbo stacking | Never | auto Turbo applies only to two-phase | `P:444-445` |
| Generation-level upscalers | Yes | Lanczos; SeedVR2 (3B, 7B); FlashVSR; H3 Face Refiner | `postprocessing/lanczos/wgp_bridge.py:40-60`; `postprocessing/seedvr2/wgp_bridge.py:103-125`; `postprocessing/flashvsr/wgp_bridge.py`; `postprocessing/h3_face_refiner/wgp_bridge.py:137-160` |
| Temporal interpolation | Yes, generic | RIFE | `postprocessing/rife/inference.py` (not H3-specific) |
| Color correction between windows | Not for H3 | only `sliding_window_color_correction_strength`, shown only with its flag; implemented in the Wan model only | `shared/extra_settings.py:564`; `models/wan/any2video.py:1852-1876` |
| Motion amplitude | Wan only | `motion_amplitude` | `models/wan/wan_handler.py:378` |
| TTS voice clone | Yes, model family | `minimax_h3_tts_ref2va_pruned` | `H:59`, `H:659-660` |

---

## 2. ComfyUI quality and speed parts, and how Wan2GP reproduces them

ComfyUI references are from `D:\aai work\anime_studio\research\four_videos_2026-11-04\INDIAN_ANIME_STUDIO_ARCHITECTURE_GUIDE.md`, sections (b) and (c).

| ComfyUI part | Wan2GP route | Reproducible? | How, and caveats |
|---|---|---|---|
| Pika LoRA at strength 1 (LoraLoaderModelOnly) | `activated_loras` Pika file, `loras_multipliers` "1.0" | Yes | File names differ: the guide's `pika_h3_flex_fl2va_v1_bf16.safetensors` vs Wan2GP's `pika_h3_flex_fl2va_6step_v1_bf16.safetensors`. Whether the weights match was not traced. |
| Euler sampler, CFG 1 | `sample_solver` "euler", `guidance_scale` 1 | Yes | `H:758` |
| LCM sampler (fixed template) | Not found in code | No | No LCM in the H3 sampler list (`H:758`). `shared/utils/lcm_scheduler.py` exists for other models. Use `pika_renoise` for Pika. |
| ManualSigmas 1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0 (6 steps) | `custom_sigmas` on non-Pika, non-fixed models | Partial | The leading 1.0 is rejected (`W:1111`). Writing "0.972973,0.923077,0.8,0.571429,0.333333" gives 5 steps with the same tail, but the first step (1.0 to 0.973) is dropped. Not tested. Pika requires empty `custom_sigmas` (`H:1013-1014`). |
| BasicScheduler "simple", 6 steps (SelfLift templates) | `num_inference_steps` 6 with the default schedule | Approximate | Default schedule is linspace(1, 0, 7) shifted by `flow_shift` (`P:1227-1236`), not the ComfyUI "simple" curve. Pika uses its own fixed schedule (`P:1237-1238`). |
| SelfLift two-stage sampler (low-res, latent upscale, continue) | Two-phase: `guidance_phases` 2 | Partial, similar design but not the same node | Phase 1 at half size (`P:927-928`); learned 3D latent upscaler (`P:1518-1523`); Euler phase 2 with `switch_threshold` (`P:48-49`, `H:725-733`). The 4x speed in the guide is the speaker's RTX 4090 result, not a Wan2GP measurement. Cannot be combined with Pika (`P:827`). |
| Split-sigma high and low (6+6 or 8+8) | Two-phase with `custom_sigmas` "slot1;slot2" | Yes, non-Pika only | `W:1093-1120`, `W:1215-1241`; `H:699`. Steps set by slot length; `switch_threshold` checked against the first value of slot 2. Time not measured. |
| Latent upscale to 1080p, preferred over Regen 2K | Two-phase with target size = requested canvas | Yes, two-phase only | `P:1518-1523`. Advisory budgets are not enforced headless (`W:9739-9743`). Memory at 1080p not measured. |
| NVIDIA Regen 2K node | Preset "H3 Regenerate 2K 2 Phases" | Yes, via preset | Same LoRA file name. The guide's speaker found Regen blurrier than latent upscale, so the latent route stays the default. Activation at `P:1532-1538`. |
| ffmpeg lanczos (fallback upscale) | Lanczos postprocessing | Yes | `postprocessing/lanczos/wgp_bridge.py:40-60` |
| SageAttention patch (MiniMaxH3MemoryEfficientSageAttentionPatch) | `sage` or `sage2` attention modes | Partial | Needs the sageattention package, which `requirements.txt` does not pin. The node patch itself is not reproduced; attention is chosen by mode (`A:276-300`). |
| sol-attn BlockSparseAttention (1.3, 0.2, 1, "", 12288, 256, "exact_kv_and_rows") | Override `attention_mode='sol'` with `attention_sparsity` | Partial, Ampere and newer only | Wan2GP uses start tau from `attention_sparsity` (default 1.3, `H:1455`), end tau 0.8 (`P:46`) and an 8192-token minimum (`sol_attention.py:14`). The ComfyUI 12288/256 values are not mapped. Not on T4 (`interface.py:11`). Incompatible with grouped masked denoising (`sol_attention.py:35-36`). |
| SolVAE (minimax_h3_sol_vae) | Not found in code | No | Video VAE options are BF16, FP8 mixed, INT8 ConvRot and LightVAE (`H:815-824`). |
| Smaller video VAE | Video VAE system config: FP8 mixed, INT8 ConvRot decoder, LightVAE Lite | Yes, as a choice | `H:815-824`. Quality and speed impact not measured. |
| Molmo2 text encoder | Not found in code | No | No match in `models/minimax_h3` or `wgp.py`. |
| NVFP4 text encoder | Variant exists (`nvfp4_awq`) | Only on FP4 hardware | `H:40`, `H:48`; `docs/INSTALLATION.md:320`. Not on T4. |
| Motion Speed Dials | Not found in code | No | No match in `models/minimax_h3` or `wgp.py`. |
| D-RoPE | Not found in code | No | No match in `models/minimax_h3` or `wgp.py`. |
| Chroma sampling "auto" | Not found in code | No | No match in `models/minimax_h3` or `wgp.py`. |
| Structured prompt (subject_definitions, summary, retention_analysis) | Prompt text only | Yes | Plain text, no node needed. Prompt guidance at `H:772`. |
| Shorter clip for iteration (6 s) | `video_length` 107 (minimum) | Yes | 107 frames is about 4.5 s at 24 fps (`H:689-691`, `H:685`). |
| Pika 8-step LoRA for far faces | Not found in code | No | Wan2GP's Pika profiles are 6-step only. H3 has 8-step Turbo profiles for FL2V and Ref2V (`profiles/minimax_h3_fl2va/Turbo Lightx2v FL2V 8 Steps v1.1 768p.json`), but no Pika 8-step file. |
| Single LoRA, no realism LoRA | `activated_loras` with one entry | Yes | Configuration only. |

---

## 3. What is impossible in Wan2GP for these routes

- Pika H3 Flex with two phases, custom sigmas, step skipping, or on the PDD, PTD, VDN, VEDA and FastH3 models. Evidence: `P:825-832`, `H:673`, `H:1007-1014`.
- Pika with a custom 6-step ManualSigmas list. Pika uses its own fixed schedule (`P:1237-1238`), and custom sigmas are rejected for Pika (`H:1013-1014`).
- A 6-step ManualSigmas list that starts at 1.0 on a non-Pika model. The parser rejects a start of 1.0 (`W:1111`). Only a 5-step tail approximation is possible.
- The LCM sampler. No LCM option for H3 (`H:758`).
- `sol` attention on the T4 (SM 7.5) and the A100 (SM 8.0). Gate: `A:37`, `shared/sol_attn/interface.py:11`. Validation accepts the override (`W:12325-12343`), so the failure appears only at the first forward pass (`sol_attention.py:37-39`, `interface.py:14-20`).
- sage2 on the T4. It needs SM 8.0+ on every GPU (`shared/sage2_core.py:89-95`, `A:313-315`).
- sage3 on any GPU below SM 10.0 (`A:309-311`).
- veda and vsa on the T4 (`A:39-45`, `H:744-746`).
- An fp16 H3 transformer. The dtype is fixed to bf16 (`H:677`, `W:3323-3325`), so `--fp16` does nothing for H3. On the T4 the mitigation is the Turing BF16 path (`W:4291`).
- NVFP4 text encoder on the T4 or any non-Blackwell card (`docs/INSTALLATION.md:320`).
- SolVAE, Molmo2, Motion Speed Dials, D-RoPE, Chroma sampling, color correction and motion amplitude for H3. Not found in code.
- The ComfyUI `SelfLiftH3Sampler` node. Wan2GP has its own two-phase path, which is a different algorithm.
- Automatic REF Turbo LoRA for Ref2VA phase 2. The code always selects the FL2V file (`P:467`, `H:798-799`). Adding the REF file by hand is possible in principle but was not verified.
- Budget enforcement on headless runs. Not impossible, but a gotcha: `--process` does not enforce the 2048x2048 budget (`W:9739-9743`).

---

## 4. Recommended settings JSON

No quality benchmark exists anywhere in the checkout. The choices below follow the pipeline design and the recorded runs in the guide. They should be checked against the run logs before production.

### 4a. Ampere and newer (SM 8.0+, for example RTX 3090 or 4090, L4, A10G, A100): best quality

Two-phase route with the H3 default phase-2 Turbo. Pika is excluded here by design (`P:827`).

```json
{
  "model_type": "minimax_h3_fl2va",
  "settings_version": 2.82,
  "prompt": "<shot prompt>",
  "image_start": "<start frame path>",
  "image_end": "<end frame path>",
  "image_mode": 0,
  "image_prompt_type": "SE",
  "video_prompt_type": "",
  "audio_prompt_type": "",
  "video_length": 124,
  "resolution": "832x480",
  "seed": 42,
  "guidance_phases": 2,
  "guidance_scale": 1,
  "num_inference_steps": 20,
  "num_inference_steps2": 3,
  "switch_threshold": 0.9035,
  "sample_solver": "euler",
  "flow_shift": 12,
  "custom_sigmas": "",
  "skip_steps_cache_type": "",
  "activated_loras": ["https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/minimax_h3_lightx2v_fl2v_turbo_4step_alpha16_v0.1.safetensors"],
  "loras_multipliers": "0;1",
  "custom_settings": {"audio_refinement": "none"},
  "overrides": "memory_profile=4"
}
```

Notes for 4a:
- 124 frames is about 5.2 s at 24 fps and is a valid length (`H:689-691`).
- Phase 1 renders at 416x256 for an 832x480 target (`P:927-928`); phase 2 renders at the requested 832x480.
- For more detail, use `1280x704` (16:9) or `704x1280` (9:16). Add "~" to `video_prompt_type` to tile phase 2 (`P:923`). VRAM and time were not measured.
- Attention is left at its default. With `sageattention` 2.x installed, the default picks sage2; otherwise sage, then sdpa (`A:334-338`). Do not use sol for quality: the H3 label says a higher start tau means sparser and faster, and lower means more faithful (`H:753`).
- Use `memory_profile=4` where VRAM allows. The runner's `--profile 5` is then ignored for this job (`W:4204-4205`).

### 4b. T4 (SM 7.5, Kaggle): proven baseline

The only route in the code with a recorded T4 run is the Pika 6-step single-phase path at 832x480 (`D:\aai work\anime_studio\research\four_videos_2026-11-04\INDIAN_ANIME_STUDIO_ARCHITECTURE_GUIDE.md:162`). The director uses the pruned model, and this JSON matches it.

```json
{
  "model_type": "minimax_h3_fl2va_pruned",
  "settings_version": 2.82,
  "prompt": "<shot prompt>",
  "image_start": "<start frame path>",
  "image_end": "<end frame path>",
  "image_mode": 0,
  "image_prompt_type": "SE",
  "video_prompt_type": "",
  "audio_prompt_type": "",
  "video_length": 124,
  "resolution": "832x480",
  "seed": 42,
  "sample_solver": "pika_renoise",
  "num_inference_steps": 6,
  "guidance_phases": 1,
  "guidance_scale": 1,
  "flow_shift": 12,
  "custom_sigmas": "",
  "skip_steps_cache_type": "",
  "activated_loras": ["https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/pika_h3_flex_fl2va_6step_v1_bf16.safetensors"],
  "loras_multipliers": "1.0",
  "custom_settings": {"audio_refinement": "none"},
  "overrides": "memory_profile=5"
}
```

Notes for 4b:
- Keep the runner's `--profile 5`. The `memory_profile=5` override matches it.
- Do not set `--fp16` or `--bf16`. H3 is bf16 regardless (`H:677`).
- Attention: leave at default. On a T4, sage2, sol, veda, vsa and sage3 are not available. sage (SageAttention 1) runs only if the package is installed, which `requirements.txt` does not do (`A:284-285`, `A:319-321`). Expect sdpa.
- The 33B full model on the T4 is not measured. Portrait `704x1280` is also untested on the T4, and VRAM was not measured.
- A two-phase test on the T4 is possible with the "H3 Original 2 Phases" preset, but it cannot use Pika. Untested.

---

## 5. Items for the director and runner

1. Write `settings_version` 2.82, not 2.73 (`h3_director.py:298`). This avoids migrations that reset `switch_threshold` and `attention_sparsity` (`H:1374-1377`). The Pika keys are not affected.
2. The director's `720x1280` choice renders at `704x1280` (`W:7607-7609`). Downstream size assumptions should use 704.
3. A `memory_profile` override in a settings file beats the runner's `--profile 5` (`W:4204-4205`). Put the profile in one place only.
4. The `--attention` CLI cannot select sol, veda, vsa or sage3 (`W:3673-3679`). Use the overrides string for those.

## 6. Open items not settled by the code

- Settings key for the Video VAE choice (`H:815-824`) was not traced.
- ER-SDE: whether settings validation accepts it was not traced (`P:823`, `H:758`).
- Skip-cache token values for Spectrum and First Block were not traced.
- Whether the guide's Pika LoRA file equals Wan2GP's 6-step file was not traced.
- Effect of starting at 0.973 instead of 1.0 for the ComfyUI schedule was not measured.
- All quality and speed statements here are design-based. None were measured in this checkout.
