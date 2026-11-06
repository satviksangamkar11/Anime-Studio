# W2: new4 workflow review for anime generation quality

- Reviewer: W2. Date: 2026-11-05. Read-only. No downloads, GPU runs, paid calls, or secret files. Only this file was written.
- Scope: 10 JSON files. PGP4Hrir6hk x7 and 5sC-FjwGqmQ x3. Each file was parsed node by node: node types, stored widget values with their widget names, the link graph, and subgraph definitions. Context read: guide Sources 9-10 and sections (b)-(e); OPUS_REVIEW_GEMINI_T4_PLAN section 2; `anime_studio/director/h3_director.py` lines 25-45 and 250-300.
- Tags: **JSON** = read from the file. **GUIDE** = the guide, its transcript timestamps, or team docs (OPUS review, LOW_VRAM plan). I did not verify these. **INFER** = my reasoning. "Not stated" = absent from the JSON and the guide.
- Codes: W1 PGP fl2va base; W2 PGP fl2va 2stage_sampling; W3 PGP fl2va sol_attn; W4 PGP fl2va sol_attn_solvae; W5 PGP ref2va base; W6 PGP ref2va 2stage_latentupscale; W7 PGP ref2va sol_atten; W8 5sC t2v; W9 5sC fl2va; W10 5sC ref2va.
- A widget linked to another node takes the linked value at run time (INFER: standard ComfyUI). Effective values below follow the links. Stored values are shown where they differ.

---

## 1. Per-workflow settings

### 1A. Settings, all 10 files

| Setting | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Role | fl2va, first frame only | fl2va, first frame only | fl2va + Sage/sol-attn | as W3 + SolVAE | ref2va, 1 ref | ref2va, 1 ref + SelfLift | ref2va, 1 ref + Sage/sol-attn | T2V (first/last unwired) | fl2va, first AND last | ref2va, 2 refs |
| Image inputs | LoadImage titled "Last frame (Picture 2)" feeds **first_frame**; last_frame unwired | same as W1 | same as W1 | same as W1 | ref_image_0 | ref_image_0 | ref_image_0 | none | first_frame ("ref_popart_woman.png", also to GetImageSize); last_frame ("lastP_spin_jump_hole.png") | ref_image_0 "ref_pilot_profile.png"; ref_image_1 "ref_subject_station.png" |
| UNET widget | minimax_h3_fl2va_int8_convrot | same | same | same | minimax_h3_ref2va_pruned_int8_convrot | minimax_h3_ref2va_int8_convrot | minimax_h3_ref2va_int8_convrot | minimax_h3_fl2va_pruned_int8_convrot (subgraph) | minimax_h3_fl2va_pruned_int8_convrot (subgraph) | minimax_h3_ref2va_pruned_int8_convrot |
| UNET file the node links to (JSON) | fl2va_pruned_int8_convrot: **MISMATCH** | **MISMATCH** | **MISMATCH** | **MISMATCH** | match | ref2va_pruned: **MISMATCH** | **MISMATCH** | match | match | match |
| Pika LoRA, strength, loader | pika_h3_flex_fl2va_v1_bf16, 1.0, model-only | same | same | same | pika_h3_flex_ref2va_v1_bf16, 1.0, model-only | pika_h3_flex_ref2va_comfy_bf16, 1.0 (link name ref2va_v1: **MISMATCH**) | ref2va_comfy_bf16, 1.0 (**MISMATCH**) | fl2va_v1_bf16, 1.0 | fl2va_v1_bf16, 1.0 | ref2va_v1_bf16, 1.0 |
| VAE: video / audio | int8_convrot / fp32 | same | same | video slot = minimax_h3_sol_vae_int8_convrot (note lists video VAE: **MISMATCH**) / fp32 | int8_convrot / fp32 | same | same | same | same | same |
| Text encoder | qwen3vl_32b_minimax_h3_nvfp4_awq (CLIPLoader type "minimax", device "default") | same | same | same | same | same | same | same | same | same |
| Sampler | LCM (KSamplerSelect) + SamplerCustomAdvanced + BasicGuider | **Euler** -> SelfLiftH3Sampler (no CustomAdvanced, no BasicGuider) | LCM + CustomAdvanced + BasicGuider | LCM + CustomAdvanced + BasicGuider | LCM + CustomAdvanced + BasicGuider | **Euler** -> SelfLiftH3Sampler | LCM + CustomAdvanced + BasicGuider | LCM + CustomAdvanced + BasicGuider (subgraph) | same | same |
| Scheduler / sigmas | ManualSigmas "1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0" | **BasicScheduler "beta", 6 steps, denoise 1**. ManualSigmas node present, output unconnected | ManualSigmas (same list) | ManualSigmas (same list) | ManualSigmas (same list) | **BasicScheduler "simple", 6 steps, denoise 1** | ManualSigmas (same list) | ManualSigmas (same list) | ManualSigmas (same list) | ManualSigmas (same list) |
| Steps | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| CFG | none (BasicGuider has no CFG input) | SelfLift cfg = 1 | none | none | none | SelfLift cfg = 1 | none | none | none | none |
| Negative conditioning | none | ConditioningZeroOut(positive) -> SelfLift negative | none | none | none | ConditioningZeroOut(positive) -> SelfLift negative | none | none | none | none |
| Flow shift (shift node) | not stated (no ModelSampling node in any file) | not stated | not stated | not stated | not stated | not stated | not stated | not stated | not stated | not stated |
| Resolution (effective) | 16:9 selector, 1.0 MP, multiple 32 -> **1376x768** (saved run metadata shows 1376x768) | 16:9, 1.0 MP -> 1376x768 | 16:9, 1.0 MP -> 1376x768 | same as W3 | 16:9, 0.98 MP, multiple 32 -> 1344x768 | 16:9, 0.98 MP -> 1344x768 | 16:9, 0.98 MP -> 1344x768 | 16:9, 0.98 MP, multiple 16 -> 1344x768 | first-frame size rounded to multiple of 32 (frame size not stated); stored top-level 1344x768 | 16:9, 0.98 MP -> 1344x768 |
| Stored MiniMax width/height/length (overridden by links) | 864x1536, 73 | 864x1536, 73 | 864x1536, 73 | 864x1536, 73 | 1344x768, 124 | 1344x768, 124 | 1344x768, 124 | 1344x768, 73 (inside subgraph) | 864x1536, 73 (inside subgraph) | 1344x768, 124 |
| Frames (effective) | 124 (5.17 s) | 124 (5.17 s) | 124 (5.17 s) | 124 (5.17 s) | **243 (10.13 s)**; prompt says "12-second" | **243 (10.13 s)**; prompt says "ten-second" (matches) | 124 (5.17 s); prompt says "10-second" | 124 (5.17 s) | 124 (5.17 s) | 124 (5.17 s); prompt says "five-second" |
| FPS | 24 | 24 | 24 | 24 | 24 | 24 | 24 | 24 | 24 | 24 |
| Seed (control) | 107368156123956 (randomize) | **42 (fixed)** | 206068906131171 (randomize) | 435266142647354 (randomize) | 640427569954067 (randomize) | 642210584697734 (randomize) | 269322708690364 (randomize) | 914757319624586 (top-level) | 915756813683825 (top-level) | 261662374822964 (randomize) |
| Two-stage / SelfLift | none | **yes (1C)** | none | none | none | **yes (1C)** | none | none | none | none |
| Attention / memory nodes, in order | none | MiniMaxH3MemoryEfficientSageAttentionPatch -> BlockSparseAttention "sol-attn" -> SelfLift and scheduler | Sage -> BlockSparse sol-attn -> BasicGuider | as W3 | none | Sage -> BlockSparse sol-attn -> SelfLift and scheduler | Sage -> BlockSparse sol-attn -> BasicGuider | none | none | none |
| ref_image_size | n/a | n/a | n/a | n/a | "match" | "match" | "match" | n/a | n/a | "match" |
| Prompt (chars; style words) | 1,172 chars; "For the target video ... <Picture 1> (from [Shot 1]) ... realistic cooking shot" | same text | same text | same text | 5,273 chars; structured; "Photorealistic live-action"; "12-second" | 3,433 chars; structured; "Photorealistic live-action"; "ten-second" | 3,056 chars; structured; "16:9 cinematic"; "10-second"; "<Picture 1> is a character reference, not the opening frame" | 2,314 chars; "Stylized 3D animation, Pixar-inspired cartoon rendering"; cook scene | 2,529 chars; "How the reference pictures align ... Picture 1 at 0.00 s, Picture 2 at 5.17 s"; "Editorial pop-art photography ... flat printed card" | 5,082 chars; structured; "Refined retro-futurist cinematography"; "five-second" |
| Output node | VHS_VideoCombine (h264, crf 19, yuv420p, metadata saved) | same | same | same | same | same | same | SaveVideo + CreateVideo 24 fps | same as W8 | SaveVideo + CreateVideo 24 fps |

Shared facts, all 10 (JSON):
- Text encoder in all 10 is `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`.
- Pika adapter is always LoraLoaderModelOnly (no CLIP LoRA).
- No split-sigma node, no chunk-FF node, no ModelSampling/shift node, no negative prompt text (no CLIPTextEncode).
- Audio decode path exists in all 10 (VAEDecodeAudio or CreateVideo audio input).
- All 10 are 16:9. No file sets a 9:16 selector value.

### 1B. Model files named in the JSON notes

| File | Size (from note) | Used by |
|---|---|---|
| minimax_h3_video_vae_int8_convrot.safetensors | 2.62 GB | all |
| minimax_h3_audio_vae_fp32.safetensors | 577.2 MB | all |
| minimax_h3_fl2va_pruned_int8_convrot.safetensors | 19.53 GB | W1-W4, W8, W9 |
| minimax_h3_ref2va_pruned_int8_convrot.safetensors | 19.53 GB | W5, W10 (note); W6, W7 use a non-pruned widget name |
| qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors | 14.61 GB | all |
| pika_h3_flex_fl2va_v1_bf16.safetensors | not stated | W1-W4, W8, W9 |
| pika_h3_flex_ref2va_v1_bf16.safetensors | not stated | W5, W10 (note); W6, W7 use _comfy_bf16 |
| minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors | not stated; in no note | W2, W6 |
| minimax_h3_sol_vae_int8_convrot.safetensors | not stated; in no note | W4 |

- Listed weights sum to about 37.3 GB before the LoRA (INFER arithmetic: 19.53 + 14.61 + 2.62 + 0.58).
- T4 16 GB (INFER: standard spec). L4 22.5 GB (OPUS table). G4 96 GB (OPUS table). None of the three holds the full listed set without offload, except G4 (INFER).

### 1C. SelfLift two-stage: exact settings (W2 and W6)

| Field | W2 (fl2va) | W6 (ref2va) | Reading |
|---|---|---|---|
| Node | SelfLiftH3Sampler | SelfLiftH3Sampler | JSON type |
| seed / control | 42 / fixed | 642210584697734 / randomize | JSON |
| cfg | 1 | 1 | JSON. With cfg 1 the negative should have no effect (INFER) |
| transition_step | 3 | 3 | JSON. Latent upscale after step 3 of 6 (INFER from name) |
| lowres_scale | 0.5 | 0.4 | JSON value. Meaning not stated; INFER: stage-1 size factor |
| rho | 0 | 0 | JSON name; meaning not stated |
| w_min / w_max | 0.5 / 1 | 0.5 / 1 | JSON names; meaning not stated |
| upscaler_model | minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors | same | JSON. Not in any note |
| highres_tiling | false | false | JSON. INFER: no tiling at high res, so a higher peak VRAM |
| upscaler_unload | true | true | JSON. INFER: unloads the upscaler after use |
| sampler | KSamplerSelect euler | KSamplerSelect euler | JSON. The GUIDE quotes "only accepts the Euler sampler" |
| sigmas | BasicScheduler beta, 6, denoise 1 | BasicScheduler simple, 6, denoise 1 | JSON. The two files differ |
| model_hires | not connected | not connected | JSON. INFER: the same MiniMax model runs both passes |
| model path | UNET -> LoRA -> Sage -> BlockSparse sol-attn -> SelfLift + scheduler | same | JSON |
| VAE | video VAE int8 | video VAE int8 | JSON |
| effective target | 1376x768, 124 frames | 1344x768, 243 frames | JSON |

- Cost (GUIDE, Source 10 [06:59-07:48], RTX 4090): 29 s for 5 s with SelfLift, against about 50 s for Sage + sol-attn. The transcript does not isolate SelfLift. Not verified.
- Identity (GUIDE): "face consistency strong" is claimed for the whole speed path. No source has a SelfLift-only identity test.
- Cel look: no source tests it. W6 is "Photorealistic live-action" and W2 is "realistic cooking shot". The upscaler's training data is not stated. INFER: the upscaler adds detail in steps 4-6 at full resolution, which is where line shimmer and texture drift would show on flat colour.
- Flicker (GUIDE, Source 10 [07:05-07:30]): "Simple" removes opening-frame flicker. Only W6 uses Simple. W2 uses beta. Not tested in any JSON.
- Team doc conflict: the LOW_VRAM plan says "finish 2 steps at low denoise (0.3-0.4)". The JSON has the switch at step 3 of 6 with denoise 1. The plan misdescribes the JSON.
- Runner: these are ComfyUI nodes. Wan2GP support is not stated (GUIDE open question 1).
- Verdict: test only, behind the gate in scorecard S5.

### 1D. Faults inside the JSON files (will break or mislead if copied as-is)

1. Widget names differ from the linked model names: W1-W4 UNET; W6-W7 UNET and LoRA; W4 VAE (sol VAE, but the note lists the video VAE). INFER: these will fail to load unless renamed.
2. W1-W4 label "Last frame (Picture 2)" feeds first_frame. last_frame is unwired, so the "fl2va" set is first-frame-only.
3. Duration vs prompt: W5 prompt says 12 s, duration node is 10 s (243 frames). W7 prompt says 10 s, duration node is 5 s (124 frames), but its shot timing runs to about 10 s.
4. Stored widget values differ from what runs: W1-W4 store 864x1536 and 73 frames; W5-W6 store 124 frames vs effective 243; ImageResizeKJv2 stores 512x512. Anyone reading the file sees the wrong size.
5. W2 ManualSigmas node is present but unconnected (dead node).
6. Model notes are incomplete: the latent upscaler (W2, W6), the sol VAE (W4), and the ref2va "comfy" LoRA (W6, W7) are not listed.

### 1E. Where the JSON contradicts the guide or team docs

1. GUIDE (workflow node summaries): "All files use the same ComfyUI node set: ... SamplerCustomAdvanced with BasicGuider." **JSON contradicts this** for W2 and W6, which use SelfLiftH3Sampler with BasicScheduler and no CustomAdvanced or BasicGuider.
2. GUIDE (SelfLift line): "names are not labelled in the JSON." **JSON contradicts this.** The widget names are in each node's inputs (seed, cfg, transition_step, lowres_scale, rho, w_min, w_max, upscaler_model, highres_tiling, upscaler_unload).
3. GUIDE (Source 10 step 5 and table (c) row 4): "Scheduler changed from manual sigmas to Simple." **Partly contradicted.** W2 (fl2va two-stage) uses beta. Simple appears only in W6 (ref2va).
4. GUIDE (Source 10 prompt format): "Official ref2va references: ref_pilot_profile.png and ref_subject_station.png." These files appear only in the 5sC ref2va template (W10). The PGP ref2va files use other images. Attribution error.
5. GUIDE (Source 10 "Baseline FL2VA") and (b) row 3 ("Generate start and end frames", with "FL2VA plan A" citing the PGP JSON): **the PGP fl2va files wire only the first frame and cannot take an end frame.** Only W9 wires both keyframes.
6. GUIDE (workflow list): UNET given as one name per variant. The downloadable names carry "pruned" for both fl2va and ref2va, and the widget names do not. The guide does not flag this.
7. GUIDE (node summary): "Frames: 5 s in the FL2VA variants." Correct for W1-W4, W8, W9. The ref2va base and latent-upscale files (W5, W6) are 243 frames (10 s), which the guide does not mention.
8. GUIDE (d): "NVFP4 ... needs a Blackwell-class card. Not on T4." The LOW_VRAM plan cites a Comfy-Org commit saying pre-Blackwell cards run it with software dequantisation (memory saver). This is a conflict between team docs. Not resolved here. The JSON does not settle it.
9. GUIDE (d): "Sage targets Ampere and newer as far as known." OPUS #12 says Sage 1.0.6 runs on sm_75 only after a kernel patch. Partly consistent.
10. GUIDE (workflow node summaries, Shift line): "Shift: not stated." Agreed. But the manual sigmas equal a shift-12 warp (INFER, verified arithmetic in 2C).
11. LOW_VRAM plan: "Two-stage ... finish 2 steps at low denoise (0.3-0.4)." **JSON contradicts this** (switch at step 3 of 6, denoise 1).
12. OPUS #7: "FL2VA turbo file uses shift 6." Not in our JSON set. Not checkable here.

### 1F. Runner (`h3_director.py`) against the JSON

- Default 9:16 size is 480x832 (0.40 MP). JSON runs are about 1.0 MP. The runner's per-shot options for 9:16 include 768x1344 (1.03 MP) and 720x1280 (0.92 MP).
- Frame rule: FRAMES_MIN 107, STEP 17, MAX 362. The JSON rule (17k+5) also allows 73 (3.04 s) and 90 (3.75 s). **The runner blocks both**, and our shots are 3-5 s.
- Preset LoRA "pika_h3_flex_fl2va_6step_v1_bf16" / "pika_h3_flex_ref2va_6step_v1_bf16". JSON uses "..._v1_bf16" (no "6step"). Whether the weights are the same: not stated.
- Preset UNET "minimax_h3_fl2va_pruned" (no quant suffix). JSON uses "_pruned_int8_convrot". Runner quantisation: not stated.
- Sampler "pika_renoise", 6 steps, guidance 1, flow_shift 12, custom_sigmas "". The validator requires custom_sigmas to be empty, so the JSON's sigma list is never sent. How Wan2GP's pika_renoise grid compares to the JSON list: not stated.
- The runner's validator matches the JSON structure (ref2va needs refs and subjects; fl2va takes start or end only).

---

## 2. Part scorecard

Ratings are my judgement. Numbers come from JSON or GUIDE where tagged. Platform order: L4 / A100 / G4 (Blackwell, OPUS) / T4.

| # | Part | Quality for our anime | VRAM / time | Cel-look risk | L4 / A100 / G4 / T4 | Verdict |
|---|---|---|---|---|---|---|
| S1 | Pika H3 Flex adapter: one, model-only, strength 1.0 | High. Used in all 10 (JSON). Identity claims are GUIDE only | Low: loader only. Size not stated | Medium (INFER): training footage style not stated | yes / yes / yes / yes (INFER: same weights as runner not confirmed) | **KEEP.** Never stack a second turbo LoRA (GUIDE; OPUS #8 confirmed) |
| S2 | 6-step ManualSigmas list (= shift-12 warp of t = 1, .75, .5, .25, .1, .04, 0) | Medium: the grid the adapter runs with in the JSON (INFER on the shift match) | None: 6 steps, same as runner | Low | yes / yes / yes / yes | **TEST.** One A/B against the runner default on one anime shot. Runner validator blocks custom sigmas |
| S3 | LCM + BasicGuider, CFG 1, no negative | Baseline for 8 of 10 files | Lowest: no CFG pass | Low | yes / yes / yes / yes | **KEEP** (matches runner CFG 1) |
| S4 | Euler + BasicScheduler 6 steps (beta or simple) | Not tested. Flicker claim is GUIDE only | Same steps as LCM | Medium: flicker claim untested on flat colour | yes / yes / yes / yes | **TEST**, only together with S5 |
| S5 | SelfLift two-stage latent upscale (1C) | Possible gain: detail in steps 4-6 at full res. Identity and cel unknown | Two passes at two sizes plus upscaler (size not stated). GUIDE: 29 s vs 50 s on 4090, not isolated | **HIGH** (INFER): upscaler adds detail on flat colour; no test exists | ComfyUI only in our files; Wan2GP not stated / untested / untested / fp16 upscaler loads on Turing (INFER), untested | **TEST ONLY**, behind the gate in section 3 note |
| S6 | Sage patch (MiniMaxH3MemoryEfficientSageAttentionPatch) | Not stated: no quality figure in any source | GUIDE: part of 125 s -> 50 s with sol-attn. VRAM effect not stated | Not stated | yes (Ampere+: GUIDE, OPUS) / yes / yes / **no stock**: sm_75 shared-memory limit needs a kernel patch (OPUS #12, third-party blog) | **TEST** on L4/A100/G4 only |
| S7 | BlockSparse sol-attn (tau 1.3, start 0.2, end 1, min_tokens 12288, extra 256, exact_kv_and_rows) | Risk: softer edges. GUIDE reports soft hair and body edges on fast-action prompts, not isolated to sol-attn | GUIDE: part of 2.5x. On T4 it falls back to dense (OPUS #14): no gain | **HIGH** for line work (INFER) | not stated / not stated / not stated / no gain (dense fallback) | **AVOID on T4.** TEST on A100/G4 with a line-sharpness A/B |
| S8 | SolVAE (minimax_h3_sol_vae_int8_convrot) | Negative: GUIDE says the rotating fan detail is lost; "experimental" | GUIDE: 50 s -> 47 s (about 6%) | **HIGH**: thin outlines and fine line detail (INFER) | not stated / not stated / not stated / untested (GUIDE) | **AVOID** |
| S9 | Video VAE int8_convrot (2.62 GB) | Baseline decode. No loss figure | 2.62 GB | Low-medium (INFER) | yes all; T4 has INT8 tensor cores (OPUS #16) | **KEEP** |
| S10 | Audio VAE fp32 + audio decode | None for silent frames. Lip-sync weak (GUIDE) | 577.2 MB + decode time | None | yes all | **DROP for silent shots.** Test removing; keep if the ref node refuses without audio_vae (not stated) |
| S11 | UNET pruned int8_convrot (19.53 GB) | Official int8 build. Quantisation loss not stated | 19.53 GB; L4 and T4 need offload (INFER) | Low | yes / yes / yes / INT8 path yes (OPUS #16); speed untested | **KEEP**, using the pruned name the JSON links |
| S12 | Text encoder qwen3vl_32b NVFP4 AWQ (14.61 GB) | Not stated. No encoder A/B in our sources | 14.61 GB; encodes once per prompt (LOW_VRAM plan) | Low | L4/A100: no native FP4 (INFER); G4: native (GUIDE, OPUS); T4: software fallback per team doc, speed untested | **KEEP on G4.** Time-test on the others. Runner uses its own encoder path (GUIDE); whether it is NVFP4 is not stated |
| S13 | Structured prompt (subject_definitions, summary, retention_analysis, detailed_description, [Shot N] with seconds, soundscape, music) | High for obedience (JSON structure) | Text only (INFER) | Medium if copied: 4 of 10 prompts use photoreal, realistic or photographic wording (W1, W5, W6, W9); W7 says 16:9; W8 says 3D Pixar | yes all | **ADOPT the structure.** Rewrite the style words |
| S14 | Retention labels and reference-role sentences | High for identity (JSON). Labels: fully_preserved, partially_preserved, attribute_transfer, weak_reference | None | Low | yes all | **ADOPT.** Include "<Picture N> is a character reference, not the opening frame" (W7) and "do not reproduce the character-sheet background, labels, grid" (W6) |
| S15 | 1 reference vs 2 references | High for identity and props (JSON) | Each ref adds conditioning (INFER). GUIDE: 3 refs up to 3x slower (NOTES Source 6, not checked) | Medium: a realistic reference pulls toward realism | yes all | **ADOPT**: one cel character sheet per character, at most one extra prop or location ref per shot |
| S16 | ref_image_size "match" vs "max" | "max" may raise identity (OPUS claim, not verified) | "max" is several times the cost (OPUS) | Low | G4 feasible (OPUS); T4 not practical (INFER) | **TEST on G4 only** |
| S17 | FL2V with first AND last keyframe (W9) vs first only (W1-W4) | High: two anchors. W9 prompt ties Picture 1 to 0.00 s and Picture 2 to 5.17 s (JSON) | One more image (small) | Low | yes all | **ADOPT** |
| S18 | ImageResizeKJv2 crop, center, divisible 32 (W1-W4) | Loss: crops a 9:16 keyframe to a 16:9 target (INFER) | CPU resize, negligible | High for framing (INFER) | yes all | **AVOID** for 9:16 keyframes. Use a matching generation aspect or pad |
| S19 | Generation size: ~1.0 MP (JSON) vs runner 480x832 (0.40 MP) | High (INFER and OPUS point 4). All official JSON runs are about 1.0-1.06 MP | 768x1344 is about 2.6x the pixels of 480x832. Time and VRAM rise (INFER); not measured | Low | G4 yes / A100 yes / L4 tight (INFER) / T4 VRAM untested | **TEST on T4, then ADOPT** for hero shots using the 768x1344 option |
| S20 | Frame rule 17k+5 (73, 90, 107, 124, 243) | None | 73 = 3.04 s and 90 = 3.75 s: cheaper | None | yes all | **TEST**: runner FRAMES_MIN 107 blocks 73 and 90. Model acceptance at 73/90 untested |
| S21 | Fixed seed per shot (W2 is the only fixed-seed file) | Reproducible re-renders (INFER) | None | None | yes all | **ADOPT** a fixed seed per shot |
| S22 | ConditioningZeroOut negative (W2, W6) | None at cfg 1 (INFER) | None | None | yes all | **SKIP** |

Not in any of the 10 files, so not scored: split sigmas, chunk FF, shift node, negative prompt text.

---

## 3. Top 5 parts to adopt for anime, and why

1. **One Pika H3 Flex adapter at strength 1.0, model-only loader, no second turbo LoRA (S1, S3).** Every file uses this. The team sources say stacking breaks output. Confirm our 6step adapter file is the same weights as the JSON's `pika_h3_flex_fl2va_v1_bf16` (names differ; not stated).
2. **Wire both keyframes for fl2va, and copy the timing anchor from W9 (S17).** Our film has start and end keyframes. W9 is the only JSON that wires both. Its sentence "Picture 1 aligns with the 0.00-second mark ... Picture 2 aligns with the 5.17-second mark" tells the model which image is which end. Do not use the W1-W4 wiring for end frames, and do not crop keyframes (S18).
3. **Structured identity prompt with retention labels and one cel character sheet per character (S13, S14, S15).** It is the only identity mechanism the JSON exposes. Before use, strip "photorealistic", "realistic", "photographic", "16:9" and "Pixar 3D" from the template text (4 of 10 prompts have photoreal words), and state the cel style in the prompt (flat colour, black outlines). The cel wording is my choice (INFER).
4. **Generate near 1 MP for identity-critical shots, with a fixed seed per shot (S19, S21).** All official JSON runs are 1.0-1.06 MP. Our default 480x832 is 0.40 MP, and the runner already has a 768x1344 per-shot option. Pixel count drives face detail (INFER, supported by OPUS point 4). Measure VRAM and time on T4 first, and prefer G4 for hero shots.
5. **Test the JSON's 6-step sigma grid against the runner default (S2).** The JSON values equal sigma = 12t/(1+11t) at t = 1, 0.75, 0.5, 0.25, 0.1, 0.04, 0 (INFER; arithmetic checked). The runner sends `custom_sigmas ""` with flow_shift 12, and its validator rejects custom sigmas, so we do not know whether our grid matches the adapter's. One A/B on one anime shot settles it. Whether Wan2GP accepts a custom sigma list for pika_renoise is not stated.

**Why SelfLift is not in the top 5.** Its exact settings are clear (1C). No source tests identity or cel look. Its flicker claim conflicts with the JSON scheduler split, and it needs a ComfyUI path. It stays in the test queue (S5) behind a gate: same keyframe and seed, 3 anime shots, SelfLift vs LCM + ManualSigmas. Measure line-edge shimmer across frames, colour drift on flat fixed regions, face match to the character sheet, wall-clock time, and peak VRAM. Adopt only if all four are at least equal.

---

## 4. Parts to avoid

1. **SolVAE (S8).** Fine-line detail loss is reported, the gain is about 6%, and its VAE name does not match the note.
2. **sol-attn BlockSparse on T4 (S7).** It falls back to dense (OPUS #14), so there is no speed gain. Edge softening is a risk on any GPU until tested.
3. **Stock SageAttention on T4 (S6).** Sage 1.0.6 exceeds the sm_75 shared-memory limit unless patched (OPUS #12).
4. **Crop-mode keyframe resize (S18).** It crops 9:16 keyframes to 16:9.
5. **Template style words in our prompts (S13).** "Photorealistic", "realistic", "photographic", "16:9", and "Pixar-inspired 3D" pull the output away from cel style or the 9:16 frame.
6. **The PGP "fl2va" set as an end-frame setup (W1-W4).** Only the first frame is wired.
7. **Copying W3, W4, W6 or W7 as-is (1D).** Their UNET, LoRA and VAE names do not match the notes. INFER: they will fail to load until renamed.
8. **SelfLift in production before the gate (S5).** No source tests identity or cel look. The flicker claim conflicts with the JSON scheduler split.
9. **NVFP4 text encoder for speed on L4, A100 or T4 (S12).** No native FP4 on those cards (INFER). Speed is untested.
10. **Audio decode on silent shots (S10).** Adds 577 MB and decode time for no benefit.
11. **ref_image_size "max" on T4 (S16).** The cost is several times higher (OPUS). Use on G4 only.

---

## 5. Not verified, and tests needed

- Speed numbers, identity claims and the anti-flicker claim come from GUIDE transcripts. I did not check them.
- Wan2GP support for SelfLift, custom sigma lists, sol-attn and Sage is not stated. Each needs a one-shot test.
- The upscaler file size, and the meaning of lowres_scale, rho, w_min and w_max, are not stated.
- The NVFP4 software-fallback claim (team doc citing a Comfy-Org commit) is not checked.
- I ran no GPU tests. All tests above need a run on a GPU.
