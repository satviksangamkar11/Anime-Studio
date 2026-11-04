# Independent review: Indian-mythology anime studio pipeline (2026-11-04)

Reviewer: Claude (Opus), read-only. I made no model, Kaggle or network calls, except web search and fetch to check claims.
Read: repo `D:\aai work\anime_studio` (director, pack_nemotron_v1, research), Kaggle result `D:\aai work\kaggle_h3_test\results_v1`, Wan2GP source at `bd1ff59` (`D:\aai work\kaggle_h3_test\wan2gp_src`), the research notes, and the two audit summaries.

---

## 0. Verdict (short)

**Keep MiniMax H3 + Pika 6-step on Wan2GP as the video engine, but the studio is not yet "proven".** The one Kaggle result is a low-motion, flat-comic shot from another project (a seated man raising his head; `results_v1/frames/A_first_mid_last.png`). It was not an anime cel shot, not a Kaliya shot, and not an action shot. Everything about anime motion on a T4 is still untested.

Five real problems matter more than any of the parameter experiments in audit 2:

1. **The compiler throws direction away.** In the Nemotron pack, 22 of 26 shots are `fl2va` *with* `refs` and `subjects`. FL2VA never receives those identity references: `h3_director.settings_for` adds `image_refs` only for ref2va (`h3_director.py:108-109`), and Wan2GP says FL2VA is not for character references (`minimax_h3_handler.py:93`). `style_bible.py` and `acting_library.py` have no caller outside their tests (grep). So the Indian visual language the audits asked for exists on paper and never reaches a prompt.
2. **Every shot pays for one extra 17-frame step.** The brief lists the grid as "4.5, 5.2, 5.9, 6.6" (`MASTER_PROMPT_v2.2.md:26`). The true grid is 4.46, 5.17, 5.88, 6.58 s (107/124/141/158 frames). Every value the writer copies rounds UP one step: 5.2 s gives 141 frames, not 124. The pack renders 3836 frames where 3394 were meant, which wastes about 13% of all GPU time.
3. **The runner reloads the models for every shot.** `run_kaggle.py:47-50` starts one `wgp.py --process` per shot. Wan2GP accepts a JSON *list* of settings as a single queue with one model load (`wgp.py:2261-2271`).
4. **The pack misses its own brief.** The owner asked for 65/65/70/70/75 s episodes (`SOURCE.md:6`). The pack has 31.9/27.4/28.1/27.4/27.4 s: 142 s of 345 s (41%). It is also full of directions a 24 fps diffusion model cannot follow ("1f anticipation, 1f impact, 3f follow-through", hex colours, "12f on 2s"), and many shots stack 3-5 actions (SHOT-08, 10, 15, 17, 18, 24).
5. **Licence.** The MiniMax H3 Community License (which also covers the Pika adapters, `PIKA_NOTICE`) excludes the EU, UK, South Korea and US. The licence page also says Outputs may not be used or *displayed* outside the Applicable Territory, and machine-generated content must be disclosed. A global YouTube or Instagram release is therefore a licence question before it is a quality question. Neither audit raises it.

Both audits are directionally right: audit 1 on what is missing, audit 2 on how to test. Audit 2's order of experiments is wrong, though. Throughput and routing must be settled before resolution, steps or VAE. The cheapest big quality lever is not a model setting. It is anime post-production that we control exactly: timing on 2s/3s, holds, impact frames, 2.5D parallax done in post, a grade, and mouth flaps. H3 then has to do less.

---

## 1. Fact check of the audits' claims

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | H3 prompts support `retention_analysis` | **TRUE, Ref2VA only** | It is the 3rd of H3's six Ref2VA sections (subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music): `models/minimax_h3/prompt_enhancer.py:111,284,290`. The Wan2GP default Ref2VA prompt uses it: `defaults/minimax_h3_ref2va_pruned.json` (prompt). The Comfy PGP Ref2VA JSON has the same field (guide line 67). It is H3 syntax, not Pika-specific: Pika says to use the existing H3 controls (`minimax_h3_handler.py:299`). Our compiler omits it (`h3_director.py:82-83`). |
| 2 | FL2VA picture-to-time alignment line | **TRUE** | "When an image fixes a point on the output timeline, put its alignment instruction before these fields" (`prompt_enhancer.py:49-53`). Example: `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` (`:90`, `:275`). The end image aligns to the exact end time, and injected frames align at their own times (`:54`, `:310`). Our FL2VA prompt has no alignment line (`h3_director.py:79-80`). The proven run had none either (`settings_A_tutorial_pika_fl2va.json`) and still kept identity, but that shot barely moved. |
| 3 | Native 768p is supported | **TRUE (documented), speed on T4 UNVERIFIED** | Pika: "Start with 480p or 768p and a 5-15 second clip" (`minimax_h3_handler.py:299`, `:304`). Wan2GP ships 768p Lightx2v profiles (`profiles/minimax_h3_fl2va/Turbo Lightx2v FL2V 8 Steps v1.1 768p.json`). The Comfy Pika templates run at 1344x768 (`MiniMaxH3ReferenceToVideo [.., 1344, 768, 124, ..]`). Wan2GP's 9:16 preset list has `720x1280`, not 768x1344 (`shared/resolutions.py` 720p block), so a 768x1344 string is a custom value to verify. |
| 4 | Up to 9 image references | **TRUE** | "Limits: 9 reference images (injected frames not counted) ... At most 12 uploaded reference files" (`minimax_h3_handler.py:128`, `:137`, `:142`). Note: start/end images take Picture numbers before the references (`:186`). Our compiler does not renumber for that (see section 2). |
| 5 | Our Wan2GP settings keys are right | **TRUE (they ran), with gaps** | The keys match the shipped Pika profile (`profiles/minimax_h3_fl2va/Pika H3 Flex FL2VA 6 Steps.json`): `pika_renoise`, 6 steps, `flow_shift` 12, `guidance_phases` 1, `custom_settings.audio_refinement none`. The run returned rc=0 and an mp4 (`timeline.txt:13-14`). The profile's `merge_loras` key is UI-only (`wgp.py:11138-11144`). Missing keys we need: `audio_prompt_type: "A"` + `audio_guide` (soundtrack kept, `minimax_h3_handler.py:77,107`); `video_prompt_type: "KFI"` + `image_refs` + `frames_positions` for FL2VA mid-shot keys (`:928`, `wgp.py:1458-1467`); `config` for the text encoder or low-RAM choice (`docs/FINETUNES.md:104`, `minimax_h3_handler.py:527-542`). |
| 6 | run_kaggle.py embeds references as JPEG | **TRUE** | `run_kaggle.py:4` docstring; `jpeg_b64` saves quality 95 with long side 1376 (`:56-60`); `.with_suffix(".jpg")` (`:72`). The whole image blob is limited to 20 MB inside the script (`:20`, `:86-87`), which also caps batch size. JPEG ringing on flat cel colour and ink lines is exactly the wrong artefact to feed a VAE encoder. |
| 7 | The two-stage JSONs have a scheduler mismatch | **TRUE** | Single-stage Pika templates: `KSamplerSelect lcm` + `ManualSigmas 1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0` (PGP `video_pika_h3_flex_ref2va.json` nodes 123/147; 5sC ref2va the same). Two-stage: `SelfLiftH3Sampler` takes `KSamplerSelect euler` + `BasicScheduler beta 6` (fl2va_2stage node 194) or `simple 6` (ref2va_2stage node 157). In fl2va_2stage, the Pika `ManualSigmas` node 169 is still present but **not connected** to the sampler. The two-stage graphs also use `BlockSparseAttention sol-attn` and `minimax_h3_latent_upscaler_3d_conv_v1_fp16`. |
| 8 | Sol/Sage/Veda speed-ups help on T4 | **FALSE for sol and Veda; Sage UNVERIFIED** | Sol-Attn needs BF16, Triton 3.6+ and SM86/89/90/100/120/121 (`minimax_h3_handler.py:321`). T4 is SM75. Veda: "not installed or supported on your system" (`wgp_B_comment_singularity_veda.log:174`). Sage on Turing: not checked. |
| 9 | "Molmo2" smaller text encoder | **Comfy-only; Wan2GP has its own equivalent** | Wan2GP offers "Distilled Qwen3-VL-4B: about 5 GB instead of 27 GB and about half the encoding time", plus GGUF Q4/Q2 (`README.md:114`, `minimax_h3_handler.py:45-54,331`). Caveat in the source: it "may follow reference images ... less closely". It is selected via the `config` setting. |
| 10 | Two-stage is not in Wan2GP (our guide, (b) row 5) | **FALSE** | Wan2GP has "Two Phases" with the H3 latent upscaler (`minimax_h3_handler.py:258-272`), and the upscaler is already downloaded and loaded (`ckpts_A...txt:63`, wgp log "latent_upscaler"). It also has an X2 VAE decoder (`vae_upsampler.py:12-18`). Pika itself has no released phase-2 stage (`:299`, `:307`), so phase 2 would fall back to the Lightx2v Turbo (`:274-276`). |
| 11 | T4 has no bf16/fp8 tensor cores | **TRUE** | Log: "Switching to FP16 models when possible as GPU architecture doesn't support optimed BF16 Kernels" (`wgp_A...log`). Turing has FP16/INT8 tensor cores and no BF16/FP8. |
| 12 | Denoising is GPU-bound, not transfer-bound | **TRUE (new finding)** | `gpu.csv`: GPU0 at 98-100% utilisation with about 2.5 GB used through the six steps (16:26-16:34). GPU1 stayed at 0% and 3 MiB the whole run. Preloading more weights into VRAM will not speed up a step. Only fewer tokens, fewer steps or a second GPU will. |
| 13 | Kaggle T4 x2 burns quota at the same rate as one GPU | **UNVERIFIED (likely)** | No official statement found. Third-party pages say quota is counted by session time ([aimultiple](https://aimultiple.com/free-cloud-gpu), [gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits)). Check the quota meter during the E0 run. |
| 14 | H3 licence territory | **TRUE, needs legal reading** | The [HF LICENSE](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE) (fetched and summarised, not read in full) excludes the EU, UK, Korea and US (§I.5). It bars use or display of Outputs outside the territory (§V.4). It requires written authorization above US$20M revenue (§IV.1) and disclosure of machine-generated content (Exh. A 12). The Pika adapters fall under the same licence (`PIKA_NOTICE`). |

---

## 2. Where I agree, where I disagree, what both audits miss

### Agree
- **Audit 1** is right that there was no Indian visual language, no animation direction and no visual acceptance. v2.2 adds these on paper: `MASTER_PROMPT_v2.2.md` sections (a)/(b), the `style/kaliya_mardan.json` bible (11 characters, physics per costume piece, references) and `acting_library.py`. But nothing consumes them yet (section 0, problem 1), and the only pack was written with v2.1.
- **Audit 2**: keep H3 + Pika as the baseline. Build a locked reference family per character. Route shots. Use the alignment line and retention_analysis. Send PNG. Use a weighted acceptance score with hard rejects. Record render manifests.

### Disagree / correct
- **Experiment order.** Audit 2 puts 1-vs-2 refs, FL2VA-vs-Ref2VA and 480-vs-768 first, and leaves throughput out. Throughput sets every budget, so it comes first: single queue, distilled text encoder, whether two workers fit in RAM. Then routing, because FL2VA cannot use refs at all, so "FL2VA vs Ref2VA" is really "do we need sheets in the generation at all". Molmo2 and motion dials should be dropped: both are ComfyUI-only, and Wan2GP has a distilled text encoder instead. "6-step vs 8-step HD" is the Lightx2v 768p LoRA, a different accelerator. Test it only if 720p is chosen.
- **16-render first batch (4 scenes x 2 configs x 2 seeds).** The size is right, the design is not. Audit 2's 4 scenes are not tied to the shot types the series needs. Use probe shots that cover the series' risk types: identity close-up acting, body action, creature/water FX and a dialogue close-up. Change one variable per pair.
- **New modules** (`quality_experiments.py`, `reference_registry.py`, `shot_router.py`). Three new modules are not needed. A route is one shot field plus a small function in `h3_director.py`. The reference registry is a `refs` block per character in the existing bible JSON, with paths and sha256. Experiments are a JSON list of setting overrides that `run_kaggle.py` already knows how to queue. Fewer files, same capability.
- **Weights.** Identity 30 / motion 25 / style 15 / acting 15 / cinematography 10 / stability 5 is reasonable. But stability (flicker, melting line art, camera drift) should be an **automatic gate before any human looks**, not 5 points. And "end-frame reached" or "continuity" needs its own score, because FL2VA can pop onto the end image (below).
- **"End keyframes are targets, not locks"** (`MASTER_PROMPT_v2.2.md:30`, `h3_director.py:9`) is wrong for a single window. Wan2GP says each window "lands exactly on its end image. When the action has drifted away from that picture, the last few frames jump to it" (`minimax_h3_handler.py:117`). Rule instead: the end frame must be physically reachable in the clip's time. Render roughly 0.3 s longer than the edit needs and trim the pop.
- **"The next shot starts from the real last frame"** (MASTER_PROMPT failure 2, `clip_tools.last_frame`). This compounds VAE softening and identity drift over 26 shots. Use the real last frame only for match-on-action cuts inside one scene. Otherwise start from the approved Flow keyframe made against the reference family.
- **"Backgrounds are held plates; the model animates only characters"** (`MASTER_PROMPT_v2.2.md:52`). H3 regenerates every pixel. A held background is only possible through compositing (matte the character, put it over the plate). The brief promises something the engine cannot do.

### Missed by both audits
1. **Two T4s.** GPU1 sat idle. Two H3 workers (`CUDA_VISIBLE_DEVICES=0` and `1`, each with half the queue) depend on host RAM: the transformer is 19.6 GiB and the INT8 text encoder 22.7 GiB mapped from file (wgp log "Weights of 'transformer' ... 19.61 GiB", "'text_encoder' ... 22.71 GiB"). During denoising, "used" RAM was only about 6 GB with 26 GB available (`ram_used_avail_mb.txt` 16:26-16:34), so the weights live mostly in shared page cache. Two workers reading the same files *may* fit if the 27 GB text encoder is replaced by the distilled 4B (about 5 GB) and the starts are staggered. This must be measured (E0). If it fails, use GPU1 for small jobs: upscaling, matting, depth, interpolation-free post.
2. **Session overhead and caching.** Measured: pip 224 s (`timeline.txt:8`), about 4 min of downloads for 49 GB (ckpts timestamps 16:19-16:23), about 2 min encoding the prompt (wgp log `[0/6] Denoising | 2m 10s`), 8m50s denoising, about 1m07s VAE decode. Downloads are fast, so a 49 GB Kaggle dataset copy of the weights is not worth it (it would also need a 49 GB upload). A small dataset of pip wheels (saves about 3 min per session) is. The real waste is per-shot model reloads (fix: one queue). The HF `.metadata` files in `ckpts/.cache` already record commit/etag, which makes a cheap manifest (no 49 GB hashing).
3. **12 h sessions.** Fill batches to at most about 10.5 h of renders. Write each mp4 straight to `/kaggle/working/out` (already done), so a timeout keeps finished clips.
4. **Weekly budget per series and across people.** See section 3. Each extra account is a different person: they run `run_kaggle.py --push` from their own machine with their own `kaggle.json`, on a batch the owner assigns. Results come back via a dataset or notebook output they share. `KAGGLE_USER` is hardcoded (`run_kaggle.py:21`) and must become the runner's own user.
5. **H3 audio vs ElevenLabs, and lip sync.** H3 always generates audio. FL2VA and Ref2VA can instead *keep a supplied soundtrack* and drive the mouth from it: `audio_prompt_type "A"` + `audio_guide`, with "speaking with natural lip movements synchronized" and **no `<d>` words** (`minimax_h3_handler.py:77,107,111`; `prompt_enhancer.py:68-74`). The pack writes Hindi lines and the compiler ignores them. For anime, the cheaper and more on-style answer for close-ups is deterministic mouth flaps (kuchi-paku): 3 mouth drawings made as Flow edits of the keyframe, switched on 3s from the ElevenLabs loudness envelope.
6. **Frame interpolation is the wrong direction.** H3 gives smooth 24 fps "AI-float". Anime is drawn on 2s/3s with holds. Post should *decimate* per beat from an exposure sheet: on 3s for acting, 2s for action, 1s only for sakuga bursts, plus freeze holds. That is free, deterministic, and makes AI motion read as animation. Use RIFE only for camera moves over a still plate, if ever.
7. **Camera drift (about 10% on "static").** Ask for static and fix it in post: stabilise static shots (ffmpeg vidstab). Do pans, pushes and parallax as 2.5D compositing over held layers, not inside H3.
8. **Colour grading and the colour script.** One LUT per episode phase (poisoned, purified, gold), plus matching each clip's colours back to its approved keyframe to remove drift. Deterministic, CPU-only.
9. **FL2VA mid-shot keys (genga) are supported.** Mode `KFI` + `frames_positions` (numeric frame) puts a breakdown pose at an exact time (`minimax_h3_handler.py:928`, `shared/prompt_enhancer/images.py:76-96`). This is the anime pipeline: key animator → inbetweener. Neither audit uses it. (`one_image_ref_only: True` at `:939` may limit FL2VA to one injected key. Ref2VA `FI` allows more.)
10. **Ref2VA also takes start and end images** (`minimax_h3_handler.py:186`). Picture 1 is the start, Picture 2 the end, then the sheets. "FL2VA vs Ref2VA" is the wrong framing; the real candidate is "Ref2VA with start + end + one sheet".
11. **Licence and terms.** MiniMax territory and display limits (section 1, #14). AI disclosure is required. ElevenLabs commercial terms depend on plan (verify the owner's tier). Removing Flow's visible watermark may conflict with Google's terms (UNVERIFIED: read before release). The WanGP Community License covers the runner (`minimax_h3_handler.py:1`).
12. **The pack does not meet its own target, and the checker does not catch it.** `check_pack.py` reports episode seconds but never compares them with the target. The writer does not know that a big share of anime screen time is holds, pans over still art and reaction stills, which need no H3 at all.

---

## 3. Throughput math (Kaliya pack)

**Measured base (480x832-class, 124 frames, Pika 6 steps, profile 5, one T4):** prompt encode about 2.2 min, denoise 6 x 88 s = 8.8 min, VAE decode about 1.1 min. That is 12.1 min per render once the models are loaded. Cold start per session: pip 3.7 min + download about 4.5 min + load about 1.5 min ≈ 10 min.

**Scaling assumptions (UNVERIFIED until E0 and E2):**
- Step time ∝ frames^1.1, because attention grows faster than linear.
- 720x1280 has 2.31x the pixels and 768x1344 has 2.58x. With roughly 35% of step time in attention, I estimate 3.3x and 3.8x per step.
- Decode scales with pixels and frames.

**Pack as written:** 26 shots, 3836 frames, average 147.5 frames, so the length factor is 1.19^1.1 ≈ 1.21.

| Config | Min per render | x2.5 tries (65 renders) | x3 tries (78 renders) |
|---|---|---|---|
| 480p, grid bug kept (3836 fr) | 2.2 + 10.6 + 1.3 ≈ **14.1** | 15.3 h | 18.3 h |
| 480p, grid fixed (3394 fr, avg 130.5) | ≈ **12.8** | 13.9 h | 16.6 h |
| 480p + X2 VAE decode on every try (+~3.5 min, est.) | ≈ 16.3 | 17.7 h | 21.2 h |
| 720x1280 native | 2.2 + 35 + 3.0 ≈ **40** | 43 h | 52 h |
| 768x1344 native | 2.2 + 40 + 3.4 ≈ **46** | 50 h | 60 h |

Add about 10 min per session for the cold start: 2 sessions at 480p, 5-6 at 720p. Two workers, if E0 passes: wall time roughly halves, and quota roughly halves if T4 x2 is metered per session (item 13).

**The brief's real target (345 s, 5 episodes)**, assuming about 55% of screen time is H3 and about 45% is deterministic post (holds, 2.5D pans over plates, reaction stills, title cards, mouth flaps): about 190 s of H3 ≈ 34 clips at about 5.6 s ≈ 85 renders at 2.5 tries.
- 480p (grid fixed): 85 x 12.8 min ≈ **18 GPU-h** + 4 sessions x 10 min ≈ **19 h**.
- 720p for everything: 85 x 40 min ≈ **57 h**.
- Hybrid (recommended): 480p tries for all shots (18 h), then 720p re-renders of the accepted ~8 hero close-ups at 1.5 tries (12 renders x 40 min ≈ 8 h). Total **≈ 27 h**.

**Fitting the weekly limit (30 GPU-h per account, one account per person):**
- Hybrid series ≈ 27 h + experiments ≈ 8 h = 35 h. That is **one owner-account plus about 5 h of a second person's account**, or one account over two weeks.
- All-720p ≈ 57 h + 8 h ≈ 65 h: **two people's accounts for a full week, plus part of a third**, or about 2.2 weeks of one account.
- Rule: one batch = one person's account = one session of at most 10.5 h. The owner keeps `batches/ledger.csv` with columns batch, assigned_to (a person), status, renders, GPU-h. No one ever pushes from another person's account.

---

## 4. A better end-to-end plan

### Principle
The writer directs. The reference family locks identity. H3 animates **only** what needs real motion. Everything that is timing, camera on still art, compositing or grade is deterministic post that we control exactly. "Anime" comes from timing and layout as much as from drawing style.

### Stages

| # | Stage | Tool | Output |
|---|---|---|---|
| 1 | Story → staged pack | `write_pack.py --staged` with v2.2. Gate 1-2 on Claude CLI (opus); Gates 3-4 per episode on Claude CLI, with Nemotron 3 Ultra (NVIDIA free) as a second opinion. OpenRouter free only for re-writes. | `bible.json`, `shots.json` (rich), PACK.md |
| 2 | Human edit pass (owner, 1 h per episode) | `check_pack.py` (extended) | canon class per beat; one action per shot; route chosen |
| 3 | Reference family per character | Google Flow (Nano Banana) + watermark remover, saved as **PNG** | identity master (3-panel), turnaround (front / 3-4 / side / back), acting master (6 bhava faces), mouth set (closed / mid / open); env plates empty; prop sheets |
| 4 | Keyframes per shot | Flow edits of the identity master, never fresh pictures | Frame_A; breakdown key (optional, at time t); Frame_B as an EDIT of A; layered plates for 2.5D shots (BG empty plate, character on flat ground) |
| 5 | Video | Kaggle, Wan2GP, H3 + Pika 6, 480p, one queue per GPU | try clips + manifest |
| 6 | Auto gates | `clip_tools.py` (CPU, local) | 12-frame motion sheet; camera drift; flicker / line-melt score; end-frame SSIM |
| 7 | Human acceptance | `visual_qa.py --via manual` (+ free vision model as a second reader on identity only) | accept log |
| 8 | Deterministic post | ffmpeg + Python (`post.py`) | exposure-sheet holds (1s/2s/3s, freezes), impact-frame inserts, stabilise, 2.5D parallax from layers, mouth flaps, LUT grade, upscale (X2 VAE or Real-ESRGAN anime), captions |
| 9 | Sound | ElevenLabs (lines, SFX, music) + H3 SFX where good | final mix, dialogue first; H3 soundtrack-kept for full-body speaking shots |
| 10 | Edit and deliver | ffmpeg concat + loudness normalisation | episode mp4 + AI disclosure + NOTICE |

### Shot routes (the director picks one per shot)

| Route | When | Kaggle cost |
|---|---|---|
| `H3-FL` (FL2VA S+E) | one body action between two known poses, no sheet needed | 1 render per try |
| `H3-FL-KEY` (FL2VA S + breakdown at t + E, `KFI`) | arcs, leaps, any motion over about 1.5 s (genga + inbetween) | same |
| `H3-REF` (Ref2VA S+E + 1 sheet, retention_analysis) | identity-critical close-ups, or a character not in the start frame | same, slower with each ref |
| `H3-TALK` (FL2VA/Ref2VA + `audio_prompt_type A`) | visible full-body or mid-shot speaking | same |
| `POST-2.5D` | establishing frames, pans, pushes, divine-vision stills, crowd reactions | 0 GPU (CPU compositing) |
| `POST-HOLD` / `POST-LIPFLAP` | ma beats, reactions, close-up dialogue | 0 GPU |

### What the director must output per shot (additions to the rich contract)
- `route` (above), and `keys`: list of `{t, image, pose}`. `t` = 0 / mid / end; mid is required for motion over 1.5 s.
- `seconds` **on the true grid** (4.46 / 5.17 / 5.88 / 6.58 / 7.29) plus `edit_seconds` (≤ seconds - 0.3).
- `exposure`: list of `{t:[a,b], on:1|2|3|"hold"}` plus `impact_frames: [{t, image}]`. All frame-level timing lives here and **never** in the H3 prompt.
- `camera_in_model` (static / one simple move) vs `camera_post` (pan / push / shake over layers, with parallax factors per layer).
- `audio`: `{dialogue_ids, soundtrack_kept: bool, h3_sfx_keep: bool}`.
- `grade`: LUT id from the colour script.
- `accept`: which items matter most (for example "identity close-up: identity ≥ 4/5").

### Acceptance (two tiers)
1. **Automatic gates (cheap, local, no model):**
   - camera drift on static shots: global shift above about 2% of width → stabilise, or reject if not fixable
   - flicker / line-melt: frame-to-frame edge-density variance over a threshold → reject
   - end-frame SSIM against Frame_B
   - duration and frame count
2. **Human review** of the motion sheet + the clip at 0.5x speed, scored 1-5. Weights: identity 30, motion 25, acting 15, style 15, cinematography / continuity 15. Any canon, anatomy or identity break = reject. Accept at ≥ 3.5 weighted with no item below 3. A free vision model (NVIDIA / OpenRouter) is a second reader for identity and costume only, with the sheet shown next to the frames. It never judges motion.
3. Log every render (settings, seed, manifest, gate results, score, reviewer) to `stories/<s>/accept_log.csv`.

### Kaggle layout
- One session = one assigned batch = one person's account. GPU0 runs H3 worker A. After E0: GPU1 runs H3 worker B if RAM allows; otherwise GPU1 runs post GPU jobs (Real-ESRGAN anime, matting, depth for 2.5D).
- Settings: one JSON list per worker. `"config": "distilled_4b"` if E0 shows no prompt loss, else `int8`. PNG inputs via a private dataset shared by the owner (`dataset_sources`), not base64.

### The first two weeks (concrete)

**Week 1: infrastructure + routing. About 9 GPU-h, owner's account only.**
- **Day 1 (no GPU).** P0 code fixes (section 5). The owner makes reference families in Flow for Krishna, Shridama and Kaliya (identity, turnaround, acting 6 faces, mouth set), plus 2 env plates (`ENV-KADAMBA-BANK`, `ENV-KALIYA-DAH-POISONED`), all PNG.
- **Day 2 (no GPU).** Re-run Gates 3-4 for **Ep2 only** with v2.2, target 65 s, routes, true grid and exposure sheets. Hand-edit. Pick 6 probe shots that cover the risk types:
  - SHOT-07 walk (body, on 2s)
  - SHOT-09 Shridama anger to terror (acting close-up)
  - SHOT-10 split into 10a arm slap and 10b climb
  - SHOT-11 dive + splash (FX, needs a breakdown key)
  - SHOT-13 Kaliya rears (creature; pulled from Ep3)
  - SHOT-15 Balarama calls down (dialogue)
- **Day 2-3 (no GPU).** Flow keyframes for the 6 probes: A, B and one breakdown key each. Watermark removed, PNG.
- **Day 3: E0 (about 1.5 GPU-h).** One session, 2 short clips:
  - (a) a single queue of 2 tasks: confirm one model load
  - (b) `int8` vs `distilled_4b` text encoder: encode time, RAM, same seed and prompt
  - (c) two workers on GPU0 and GPU1, started 3 min apart: s/step, RAM, OOM
  - Read the quota meter (is T4 x2 metered as one GPU?)
- **Day 4-5: B1 routing batch (about 6 GPU-h at 480p, one session).** 6 probes x 2 seeds x 2 routes = 24 renders. Routes: `H3-FL` vs `H3-FL-KEY` for action shots, `H3-FL` vs `H3-REF` for identity shots, `H3-TALK` vs mute + post lip-flap for SHOT-15.
- **Day 5-6 (no GPU).** Build `post.py` (exposure holds, stabilise, LUT, impact insert, layer parallax, lip-flap) and the gates in `clip_tools.py`. Score B1 with the two-tier acceptance.
- **Day 7.** Decision memo: a route per shot type, 2 workers or 1, text encoder choice. Freeze the defaults in `h3_director.py`.

**Week 2: resolution + one finished episode. About 14 GPU-h, owner's account; a second person's account only if E0 shows a gain.**
- **Day 8: B2 (about 3 GPU-h).** On 3 accepted B1 shots: 480p + X2 VAE decode vs 720x1280 native vs 480p + Real-ESRGAN animevideo-v3 (GPU1 or local CPU). Judge line art at phone size. Pick the hero-shot rule.
- **Day 9-11: B3 (about 8-9 GPU-h).** Render all H3 shots of Ep2 (about 11-12 shots x 2.5 tries ≈ 30 renders at 480p). The remaining seconds are `POST-*` routes.
- **Day 11-13 (no GPU).** ElevenLabs lines (Hindi / Braj) and SFX. Post assembly with holds, parallax, grade and captions. Final mix.
- **Day 14.** Ep2 at 65 s with the accept log and render manifests. Review against the brief. Then assign Ep1/Ep3 batches across people's accounts.

---

## 5. Concrete repo changes (ranked)

### P0 (before the next Kaggle run)
1. `director/h3_director.py`: `frames_for` treats a value within 0.05 s above a grid point as that point (5.2 → 124, not 141). This saves about 13% GPU.
2. `director/MASTER_PROMPT_v2.2.md` (+ v2.1): correct the grid to 4.46/5.17/5.88/6.58/7.29 s, and replace "end keyframes are targets, not locks" with "FL2VA lands exactly on the end image; make it reachable; edit trims the last 0.3 s".
3. `director/h3_director.py`: FL2VA prompt gets the alignment lines (start at 0.00 s, end at exact end time, injected keys at their times) before `integrated_multimodal_description`.
4. `director/h3_director.py`: refuse `fl2va` with `refs`/`subjects`, or route it to ref2va. For ref2va, renumber `<Picture N>` after start/end images and emit `retention_analysis` (fully_preserved per subject).
5. `director/h3_director.py`: put `style_bible.prompt_block()` for every cast/set id into the prompt body (identity and costume text). Today the bible never reaches H3.
6. `director/h3_director.py`: dialogue shots → `audio_prompt_type "A"` + `audio_guide` + lip-sync wording, no `<d>`. Non-dialogue shots get "no speech" in the soundscape.
7. `director/run_kaggle.py`: write ONE settings JSON list per worker and call `wgp.py --process` once (`wgp.py:2261`). Optional `--workers 2` splits the list by `CUDA_VISIBLE_DEVICES`.
8. `director/run_kaggle.py`: PNG inputs through a private Kaggle dataset (`dataset_sources`). Drop JPEG and the 20 MB base64 limit.
9. `director/run_kaggle.py`: `--user` read from the runner's own `kaggle.json`, replacing hardcoded `KAGGLE_USER`. Write `manifest.json`: Wan2GP commit, ckpt `.metadata` etags, LoRA URL, settings, seeds, input sha256, phase timings.
10. `director/check_pack.py`: fail on episode seconds below target minus one clip; flag frame-level timings (`\d+f\b`), hex colours and more than one primary action in video prompt text; flag `fl2va` with refs.

### P1 (week 1-2)
11. `director/post.py` (new, the only new module): exposure-sheet holds, impact-frame insert, vidstab, LUT grade, layer parallax (ffmpeg overlay / zoompan per layer), mouth flaps from the audio envelope.
12. `director/clip_tools.py`: 12-frame motion sheet, camera-drift measure (vidstabdetect transforms), edge-flicker score, end-frame SSIM vs Frame_B.
13. `director/visual_qa.py`: 1-5 weighted rubric with hard rejects and auto-gate results. Show the reference sheet beside the frames. Append to `accept_log.csv`.
14. `director/shot_schema.py`: add `route`, `keys[{t,image,pose}]`, `edit_seconds`, `exposure`, `camera_post`, `audio.soundtrack_kept`, `grade`. Validate that mid keys exist for motion over 1.5 s.
15. `director/h3_director.py`: `KFI` + `image_refs` + `frames_positions` for `H3-FL-KEY`; `config` (text encoder / lower_ram) passed through from the shot or batch.
16. `director/style/kaliya_mardan.json`: per-character `refs` block (identity, turnaround, acting, mouth set: path + sha256). This replaces a separate `reference_registry.py`.
17. `director/experiments/E0.json`, `B1.json`: lists of setting overrides queued by `run_kaggle.py`. This replaces `quality_experiments.py`.
18. `batches/ledger.csv` + README section: batch → person → account → status → GPU-h (one person per account).
19. `MASTER_PROMPT_v2.2.md`: add the route table, POST routes, exposure sheet, and "frame-level timing never in the video prompt".

### P2 (after Ep2 ships)
20. `run_kaggle.py`: pip wheel cache dataset (saves about 3 min per session).
21. ControlNet-Union (pose/depth from a Blender or hand-drawn layout) for choreography shots. It is a separate checkpoint, so test cost first.
22. Two-phase (latent upscaler) vs X2 VAE for hero shots, if B2 shows that 720p native is too slow.
23. A 12 fps generation experiment (Wan2GP allows another frame rate, `minimax_h3_handler.py:198`), to check whether on-2s motion can be had at half the compute.
24. `LICENSE_NOTES.md`: MiniMax territory and disclosure, Pika under the MiniMax licence, ElevenLabs plan, Flow watermark terms. Owner or legal sign-off before the first public upload.

Sources: [MiniMax H3 LICENSE](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE), [aimultiple free GPU](https://aimultiple.com/free-cloud-gpu), [gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits).
