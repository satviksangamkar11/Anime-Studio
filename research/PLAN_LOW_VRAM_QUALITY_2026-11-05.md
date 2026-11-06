# Low-VRAM, high-quality, fast generation plan (2026-11-05)

Owner goal: do NOT load the full model; use settings that keep generation quality while using less VRAM, so clips are faster and Colab units last longer. Output resolution can be low; we upscale later.
Built only from our evidence: `research_transcripts/NOTES_RUN_BIG_VIDEO_MODELS.md` (Sources 1-11), `INDIAN_ANIME_STUDIO_ARCHITECTURE_GUIDE.md`, `research/OPUS_REVIEW_GEMINI_T4_PLAN_2026-11-05.md` (web-checked), our Kaggle run (STATUS.md). Gemini's T4 timings are NOT used (not found / likely invented).

## What actually saves time and units (ranked by evidence)
| Lever | Gain | Quality cost | Evidence | Works on |
|---|---|---|---|---|
| Pika H3 Flex 6-step LoRA (CFG 1, shift 12) instead of 20-40 steps | ~3x (30 min -> 11.5 min per clip on 16 GB) | small: slightly softer faces | Source 2 (measured by him), our run 8m50s | any GPU (proven T4 Wan2GP) |
| Pruned INT8 checkpoint (~21 GB) instead of full bf16 (66 GB) | fits a 22-24 GB GPU, no heavy offload | small (int8; pruning removes redundant weights) | Source 1, Opus #2 (real file 19.6 GB) | L4 / A100 / G4; T4 with Wan2GP offload |
| Text encoder (Qwen3-VL-32B) as GGUF Q2/Q4 in system RAM, encode once per prompt | frees 15-25 GB VRAM | small (encoder runs once) | Sources 4, 1 | all |
| Two-stage: generate at ~0.5-0.6 MP, latent-upscale, finish 2 steps at low denoise (0.3-0.4) | ~4x on 4090 (125 s -> 29 s per 5 s) | low if refiner strength is low (high strength changes the face) | Source 10 (one source, RTX 4090), Source 5 | ComfyUI (SelfLift / latent upscaler). Wan2GP has a "two-phase" option (Source 3, user claim, untested) |
| SageAttention / sol-attn | ~2.5x on 4090 (125 s -> 50 s) | none reported | Source 10 | Ampere or newer only (L4, A100, G4). NOT T4 |
| Lower base resolution (0.6-0.7 MP vs 1.5 MP) | ~2x | face gets small -> identity loss on wide shots | Source 6 | all |
| Fewer refs (one 3-panel sheet, not 3 images) | up to 3x faster at high res | none if the sheet is clear | Source 6 | all |
| One session, many shots (load models once) | saves the 15-30 min download/load per session | none | Kaggle run 16m54s incl. downloads vs 8m50s gen | all |
Avoid: stacking a second turbo LoRA on Pika (breaks output), caching tricks (EasyCache/Spectrum) with few-step LoRAs (eye/finger drift), KSampler for Singularity (loses identity), NVFP4 files on non-Blackwell GPUs.

## Recommended setup (to confirm in T0)
- Model: MiniMax H3 pruned INT8 (Ref2VA for identity, FL2VA for exact start/end frames), never the full 66 GB.
- Speed LoRA: Pika H3 Flex 6-step, strength 1.0, CFG 1, shift 12 (video) / 3 (audio). No second turbo LoRA.
- Text encoder: GGUF Q4 (Q2 if RAM is tight) on CPU RAM; encode once.
- Sampling: two-stage. Stage 1 at 9:16 ~544x960 (0.52 MP), 6 steps. Stage 2 latent upscale to 768x1344, 2 steps, denoise 0.3-0.4, refiner LoRA low strength so the face does not change.
- Attention: Sage (L4/A100/G4 only).
- Refs: one clean 3-panel Krishna sheet (face close-up + front + back, no text) as Picture 1; start/end keyframes as conditioning.
- Session: load once, render all 5 leap shots x 3 takes in one session.

## GPU choice for unit cost
Colab per-hour unit rates must be read in the Colab "Resources" panel after purchase (2024 rates: L4 ~1.7, A100 ~5.4-7.5, G4 ~8.7 units/h). Cheapest per clip is likely the L4 (24 GB Ada, fp8 + Sage) with the pruned INT8 setup; the G4 is fastest. Nothing is measured on either yet.
T0 therefore measures cost per clip, not just quality: same shot (LEAP-03), same seed, on L4 and on G4 (if unlocked).

## Open risks
- Wan2GP (our runner) may not support the two-stage latent upscale; that path may need ComfyUI on Colab.
- Two-stage speed number is from one 4090 test; T4 cannot use Sage.
- Pro plan may not unlock G4 (Colab hint says "Google AI Ultra" for premium GPUs).
