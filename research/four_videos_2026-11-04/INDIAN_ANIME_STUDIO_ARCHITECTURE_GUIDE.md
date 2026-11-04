# Indian anime studio: architecture and optimization guide (sources 8-11)

Built 2026-11-04 from four YouTube videos on Pika H3 Flex (a MiniMax H3 fine-tune run in ComfyUI). Transcripts are local Whisper (small.en), timestamped [mm:ss]. Where a value is not spoken or shown in the JSON, it is marked "not stated".

Scope notes:
- Workflow JSON files were downloaded only from GitHub and docs.comfy.org (allowed hosts). Patreon, RunningHub and Dropbox links were not downloaded (see section (a)).
- Not done: 720p downloads and frame pulls for on-screen settings. On-screen values come from the downloaded workflow JSON where a JSON exists. Anything shown only on screen in 8xuxQP_M-h0 or stRsg-wNQds is "not stated".
- Whisper errors are visible in the transcripts (for example "post-train of the H3 bass" for "base", and an outro at 5sC [13:34] that reads as hallucinated). Treat exact words with care.

---

## (a) The four videos

| # | Video id | Title | Channel | Date | Length |
|---|---|---|---|---|---|
| 8 | 8xuxQP_M-h0 | Pika H3 Flex Makes MiniMax H3 Look BETTER?! | smallzero | 2026-11-02 | 6:10 |
| 9 | 5sC-FjwGqmQ | MiniMax H3 - Pika H3 Flex + Nvidia Regen 2K Upscale ComfyUI Walkthrough | Benji's AI Playground | 2026-11-02 | 13:55 |
| 10 | PGP4Hrir6hk | Master Pika H3 Flex: 5s Hd video in 30s Fast Renders & Insane character consistency | Veteran AI | 2026-11-03 | 11:53 |
| 11 | stRsg-wNQds | MiniMax H3 Just Got WAY FASTER! New Molmo2 Text Encoder + Motion Tests | Ok Todd AI | 2026-11-04 | 19:43 |

Full descriptions are in the appendix at the end of this file.

### Source 8: 8xuxQP_M-h0 (smallzero, 6:10)
- What it shows: ComfyUI's free "Pika H3 Flex reference to video" template (also text-to-video and first/last-frame variants). Tested on an RTX 5090 with BF16 files. Image-to-video on an AI-influencer image, then text-to-video of a Toyota Chaser in a parking garage.
- Workflow steps:
  1. Update ComfyUI so the template appears (speaker: "maybe a day old or so") [01:17-01:24].
  2. Install the Pika H3 Flex LoRA plus the usual MiniMax H3 files. "It's really just this Laura, the Pica H3 Fleck that you install" [02:04-02:11].
  3. Open the template; it contains an example prompt. Paste it into ChatGPT with the reference image and the motion idea, and ask for a new prompt in the same structure [02:39-02:59].
  4. Use BF16 (speaker's choice). The template asks for INT8, which he calls "a little bit faster ... but probably a little bit less quality" [03:35-03:48].
  5. Output is set to 16:9 even for a 1:1 input image [03:56-04:00]. Length 5 s [04:01].
  6. Enable chroma sampling. "It was off by default. I selected auto" [04:05-04:10].
  7. Run. Time: "about three or four minutes" for the 5 s clip [04:36].
  8. Text-to-video: same process with a JDM prompt from ChatGPT; expected "maybe two to three minutes" [05:13-05:24].
- Models and files: MiniMax H3 base (BF16 used by speaker, file names "not stated"), Pika H3 Flex LoRA (name "not stated" in the video; the template JSON uses pika_h3_flex_ref2va_v1_bf16.safetensors).
- Settings: 16:9, 5 s, BF16, chroma sampling "auto". Resolution "a little bit low" [04:21-04:23]. Other sampler values: not stated.
- Prompts (exact, as spoken): "we want to do a video of this woman posing for flash photography shoot in front of the car. So like a JDM style photo shoot." [03:03-03:09]. "let's take this girl, let's try some movement. So she'll do a photo shoot and squat and then give the peace sign." [03:16-03:22]. Full ChatGPT output: not stated.
- Character consistency: no sheet used. The speaker suggests adding "a facial reference photo, so something super up close" to lock identity [04:44-04:51]. Not tested.
- Opinion: "I actually prefer some of the results to standard MiniMax H3" is not said; he asks viewers instead [02:28-02:32]. Quality "not perfect, need some refinement" [04:19].

### Source 9: 5sC-FjwGqmQ (Benji's AI Playground, 13:55)
- What it shows: Pika H3 Flex Turbo LoRA (2/4/8-step files) against the LightX2V 4-step turbo LoRA, same prompts; split-sigma high-action pass; latent upscale to 1080p versus NVIDIA Regen 2K.
- Workflow steps:
  1. Download the Comfy-format Pika LoRA (BF16, 3.9 GB files) into the LoRA folder [02:23-02:46]. "I load it into the LoRa models folder" [02:40-02:46].
  2. Use the normal MiniMax H3 setup for everything else [02:46-02:53].
  3. Outfit try-on test: one reference image with several garments, short prompt, 15 s clip [03:00-03:26]. Two reference slots are wired by default, one used [03:13-03:20].
  4. Compare two routes at 8 steps each, same prompt, side by side. "Both routes are set to eight steps" [03:54-04:01, 04:28-04:35]. Basic sampler: "I keep the sampler as basic as possible" [04:15-04:18].
  5. Face consistency with two characters from an earlier video. Pika: fingers move oddly; LightX2V: better talking hands [07:13-07:25].
  6. High-action scene, Singularity Reference-to-Video V2 base [08:27-08:34]. Split sigmas: high-sigma half does the first 6 steps, Pika low-sigma half does 6 steps; 12 total, 50/50 [09:18-09:58]. Can go to 8+8 = 16 [10:04-10:10].
  7. Output: 0.8 MP, 24 fps, 15 s [10:17-10:26].
  8. Upscale: 480p first pass, then latent upscale to 1.5 MP [11:01-11:24]. Comparison: latent upscale to 2.0 MP (1080p) versus NVIDIA Regen 2K three-step [12:18-12:44]. Preference: "Latent upscale to 1080p, then another upscaler to 2K or 4K only if I need it" [13:10-13:16].
- Models and files: Pika H3 Flex Turbo LoRA (2/4/8 step) from the akhaliq repo on Hugging Face, Comfy-format BF16 from Comfy-Org/MiniMax-H3 loras, base WarmBloodAban/Minimax-h3_Singularity (named in description). Upscale LoRA stack and NVIDIA Regen node: not stated in detail.
- Settings stated: 8 steps for comparison; split 6+6 (total 12) for high action; output 0.8 MP 24 fps 15 s; upscale 1.5 MP and 2.0 MP. Sampler names and CFG: not stated. Sigmas for the 2-stage: not stated beyond the split.
- Prompts: no prompt text is quoted in the video. The long 15 s fight prompt is described only ("a longer text prompt that describes all 15 seconds", [08:34-08:43]). Text not stated.
- Character consistency: two characters from a previous video, one has a different face and outfit. Result: "both video loras stay pretty close on character-style consistency" [06:28-06:34]. Pika better on far and mid-range faces (no pixelation) [07:32-08:03].
- Key claim: "you do not stack another Turbo LoRa on top of it in the Comfy UI workflow" [01:50-01:56]. Pika is "distilled ... from 50 steps down to 6" [00:06-00:11]. Base weights "around 210 gigabytes" [01:17-01:21]. Up to 12 images, video clips or voice samples as references [00:30-00:36]. Audio in the same pass [00:17-00:23]. Licence: MiniMax community [00:47-00:54].

### Source 10: PGP4Hrir6hk (Veteran AI, 11:53)
- What it shows: a speed path from the official Pika H3 Flex workflow to about 30 s per 5 s clip on an RTX 4090, plus character-consistency tests. Built on RunningHub, also in ComfyUI.
- Workflow steps (times on RTX 4090):
  1. Baseline FL2VA: LCM sampler, 6 steps defined with manual sigmas, Pika FL2VA LoRA at strength 1, 5 s, 16:9, 1.0 MP target. Output 1376x768 [02:15-03:08]. About 125 s per run [03:13-03:27].
  2. Add the SageAttention patch for H3 and sparse attention set to "sol-attn" [04:08-04:23]. Time about 50 s [04:23-04:29].
  3. Replace the VAE with the experimental SolVAE from the Comfy repo [04:38-04:46]. Update ComfyUI first: "An older version may produce decoding errors" [04:52-04:58]. Time about 47 s [05:00-05:06]. Loses the rotating exhaust-fan detail [05:12-05:18].
  4. Reference-to-video: same acceleration nodes; sword-dance test 5 s in about 45 s [05:44-05:56].
  5. Two-stage sampling: replace the sampler with the SelfLift progressive sampler (sample at lower resolution, upscale the latent, continue). "This node only accepts the Euler sampler" [06:59-07:05]. Scheduler changed from manual sigmas to Simple, keeping 6 steps [07:05-07:12]. Time 29 s for 5 s; 61 s for 10 s [07:30-07:48].
- Models and files: minimax_h3_sol_vae_int8_convrot.safetensors (SolVAE), Pika FL2VA and REF2VA LoRAs, minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors (SelfLift, from the JSON). Text encoder: qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors (from the JSON; this is an NVFP4 file, see (d)).
- Settings (from the downloaded JSON, two-stage ref2va): Euler, BasicScheduler "simple", 6 steps, SelfLift upscaler as above, sol-attn BlockSparseAttention (1.3, 0.2, 1, "exact_kv_and_rows"), 16:9 at 0.98 MP.
- Prompt format (quoted from the downloaded JSON, template node "subject_definitions"): "<Subject 1> is the single character defined exclusively by <Picture 1>. All views in the character sheet depict the same individual. The picture supplies character identity and design only, not the target composition or action." The same node has "summary" and "retention_analysis" fields, where each subject is labelled "fully_preserved" or "partially_preserved". Official ref2va references: ref_pilot_profile.png and ref_subject_station.png.
- Character consistency: "We supplied a character sheet, then generated a completely different scene" [00:20-00:27]. Face kept close after hair and pose changes [00:27-00:33, 08:51-09:10]. Six-panel storyboard, rooftop dance, multi-cut, identity kept [09:42-10:20].
- Fast-action limit: normal pace fine. "In the second prompt, I explicitly ask for fast continuous punches." Hair and body edges go soft [10:57-11:23].
- Prompts spoken: the cooking prompt and the sword-dance prompt are not quoted. Text not stated.

### Source 11: stRsg-wNQds (Ok Todd AI, 19:43)
- What it shows: Molmo2 as a smaller text encoder, a smaller H3 VAE, Motion Speed Dials, and D-RoPE. Runs on a 16 GB card (speaker's "16-gigabyte card"; he also says "40 series" [02:39] and the description names a 4070 Ti Super 16 GB).
- Workflow steps:
  1. Install Molmo2 (custom node) and its text encoder. Known error: "value error, this config is already used by a Transformers model" [05:20-05:24]. Fix: edit the Molmo2 model file, remove three spaces at the end, around line 1764 [06:44-07:23]. Exact file name: not stated (heard as "modeling MOMO2py").
  2. Connect Molmo2 to the existing workflow, bypassing a clip node that the other author made [07:36-07:59].
  3. Swap in the smaller MiniMax H3 VAE from the Comfy-Org repo [08:19-08:49].
  4. Keep the realism LoRA on, although the speaker dislikes it: "It messes up the motion for me so much" [03:50-03:54].
  5. Two-stage split: steps 10, split at 8 (8 high, 2 low) [18:41-18:52]. Slower but better quality.
  6. Sampler: Euler with Simple. A commenter suggested LCM with Beta; he says "I didn't like it" [13:26-13:45].
- Models and files: Molmo2 text encoder (Alissonerdx/Molmo2-8B-Minimax-H3, about 9 GB per speaker, vs about 26 GB for the INT8 Qwen encoder he used before [02:37-02:53]). New H3 VAE from Comfy-Org (size: "a lot smaller", figure not stated).
- Speed (16 GB card, low resolution): 6 s clip in "two and a half minutes" [04:12-04:18]. 15 s clip at 1088x608 "only taking five minutes" [03:14-03:21]. The 15 s clip "only took me about six minutes" [17:57]. Before the Molmo2 change, the same 6 s clip took "three and a half minutes or four minutes" [04:58-05:03].
- Motion Speed Dials (custom node, matlowai/ComfyUI-Dials): range from -2 ("barely moving") through base 0 ("normal") to 2 ("ultra fast") [08:50-09:07]. Tests: -0.5 almost no motion [14:33-14:47]; 1 "running is good" [14:56-15:12]; 2 "zoomies ... basically worthless" [16:41-16:47].
- D-RoPE (from AI Ninja's workflow, a de-roping section): "it's messing up the faces" [01:51-01:54]. Body motion improves, faces change [15:15-16:06]. The speaker rated one clip "95% there" but the face changed [16:01-16:06].
- Prompts: none quoted. The song lyric line used as a lip-sync test: "All the words I left unspoken, didn't scare me anymore." [11:08-11:09]. Result: one clip matched lyrics, two went garbled [11:55-12:08].
- Character consistency: not a method in this video. Speaker says "I'm not there yet, 80% there" [02:20-02:24].

---

## Links and workflows (per video)

### Source 8: 8xuxQP_M-h0
- Workflow: ComfyUI built-in template (Pika H3 Flex reference-to-video; text-to-video; first/last frame). No external link in the description. Downloaded: none directly. The same template JSONs are in workflows_new4\5sC-FjwGqmQ\ (video_pika_h3_flex_ref2va.json and video_pika_h3_flex_t2v.json, from the Comfy-Org templates repo). These should match what the speaker used; not verified against his copy.
- Model: none linked.
- Tool: none linked.
- Tutorial: none linked.
- Other: smallzero.io (community), skool.com/small-zero-ai-5861 (community), x.com/Smallzero (social).

### Source 9: 5sC-FjwGqmQ
- Workflow:
  - Patreon post 174179682 (freebie workflow). **Gated**. Not downloaded.
  - docs.comfy.org/tutorials/video/pika/pika-h3-flex (tutorial + templates). Downloaded the three official template JSONs from GitHub (Comfy-Org/workflow_templates): video_pika_h3_flex_fl2va.json, video_pika_h3_flex_ref2va.json, video_pika_h3_flex_t2v.json. These are in workflows_new4\5sC-FjwGqmQ\.
- Model:
  - huggingface.co/Pika-Labs/Pika-H3-Flex (official adapters; full base about 210 GB per speaker). Not downloaded (too large, not needed).
  - huggingface.co/akhaliq/Pika-H3-Flex-Turbo-LoRA (2/4/8 step LoRA, used in the video). Not downloaded (model weights).
  - huggingface.co/Comfy-Org/MiniMax-H3/tree/main/loras (Comfy-format BF16 LoRAs). Not downloaded.
  - huggingface.co/WarmBloodAban/Minimax-h3_Singularity (base model used). Not downloaded.
- Tool: github.com/benjiyaya/Calliope ("Local-first Agentic Idea-to-video Studio"). Code; not downloaded.
- Tutorial: docs.comfy.org (above).
- Other: patreon.com/c/aifuturetech (channel support), utm-tagged Patreon link.

### Source 10: PGP4Hrir6hk
- Workflow:
  - GitHub amao2001/ganloss-latent-space, folder "workflow/2026-11-03 pika h3 flex". **Downloaded 7 JSON files** to workflows_new4\PGP4Hrir6hk\: video_pika_h3_flex_fl2va.json, _fl2va_2stage_sampling.json, _fl2va_sol_attn.json, _fl2va_sol_attn_solvae.json, _ref2va.json (source name had a trailing space), _ref2va_2stage_latentupscale.json, _ref2va_sol_atten.json.
  - Six RunningHub posts (fl2va, ref2va, fl2va_sol_attn, ref2va_sol_atten, fl2va_2stage_sampling, ref2va_2stage_latentupscale). **Gated / platform**: RunningHub account and invite-code links. Not downloaded.
- Model:
  - huggingface.co/Comfy-Org/MiniMax-H3/tree/main/lora. Not downloaded.
  - huggingface.co/Pika-Labs/Pika-H3-Flex. Not downloaded.
- Tool: RunningHub (online ComfyUI host, "1,000 free compute points" on signup via referral link). Not used. Paid compute points are outside our no-paid rule.
- Tutorial: docs.comfy.org/tutorials/video/pika/pika-h3-flex (official).
- Other: RunningHub referral/invite links (not used).

### Source 11: stRsg-wNQds
- Workflow:
  - Dropbox direct download, Ep49-Deno_MiniMax_H3_R2V_Turbo_8plus2.json (includes motion-dial node and D-RoPE section). **Not downloaded**: Dropbox is outside the allowed hosts (HF / GitHub / docs.comfy.org). Owner can approve it.
  - AI Ninja's workflow (referenced in the speaker's description of the D-RoPE section; the NOTES file lists AI Ninja as source 5). Not re-downloaded here.
- Model:
  - huggingface.co/Alissonerdx/Molmo2-8B-Minimax-H3 (Molmo2 text encoder). Not downloaded (text-encoder weights).
  - huggingface.co/Comfy-Org/MiniMax-H3 (new smaller H3 VAE referenced in the video). Not downloaded.
- Tool:
  - github.com/alisson-anjos/ComfyUI-Molmo2-H3 (custom node). Code; not downloaded.
  - github.com/matlowai/ComfyUI-Dials (motion speed dials custom node). Code; not downloaded.
- Tutorial: the speaker's YouTube chapters only (in the description). No external tutorial.
- Other: about 9 Amazon affiliate links (monitor, mouse, desk, GPU, etc.). Not relevant to us; not followed.

### Summary of downloads
- Downloaded (allowed hosts only): 7 files from GitHub (PGP4Hrir6hk); 3 files from GitHub Comfy-Org/workflow_templates (5sC-FjwGqmQ). Total 10 JSON.
- Gated: Patreon 174179682 (source 9). RunningHub posts (source 10). Need login or invite.
- Not downloaded, need owner approval: Dropbox workflow (source 11). Civitai and Google Drive: none linked in these four videos.

---

## Workflow node summaries (from the downloaded JSON)

All files use the same ComfyUI node set: MiniMaxH3ImageToVideo (FL2VA) or MiniMaxH3ReferenceToVideo (REF2VA), SamplerCustomAdvanced with BasicGuider, KSamplerSelect, ManualSigmas or BasicScheduler, LoraLoaderModelOnly (Pika LoRA, strength 1), VAE loaders, VHS_VideoCombine or SaveVideo. The Comfy-Org template base files use these names:
- UNET: minimax_h3_fl2va_int8_convrot.safetensors, or minimax_h3_ref2va_int8_convrot.safetensors, or minimax_h3_ref2va_pruned_int8_convrot.safetensors.
- Text encoder: qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors (CLIPLoader, type "minimax"). NVFP4 needs a Blackwell-class card (see (d)).
- Video VAE: minimax_h3_video_vae_int8_convrot.safetensors (2.62 GB per the template note). Sol variant: minimax_h3_sol_vae_int8_convrot.safetensors.
- Audio VAE: minimax_h3_audio_vae_fp32.safetensors (577.2 MB per the template note).
- Pika LoRAs: pika_h3_flex_fl2va_v1_bf16.safetensors and pika_h3_flex_ref2va_v1_bf16.safetensors (strength 1). The PGP JSON also uses pika_h3_flex_ref2va_comfy_bf16.safetensors.
- Sampler: LCM (fixed template) or Euler (two-stage SelfLift). CFG: 1 (BasicGuider). Schedulers: ManualSigmas 1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0 (6 steps) in the official templates; BasicScheduler "simple" (6 steps) in the SelfLift templates.
- Shift: not stated in the JSON node list (no separate shift node found).
- Frames: 5 s in the FL2VA variants (per the speaker, [02:55-03:03] in PGP); 16:9; ResolutionSelector 0.98 MP (ref2va template) or 1.0 MP (FL2VA template per speaker). 480p-class base.
- Attention: MiniMaxH3MemoryEfficientSageAttentionPatch and BlockSparseAttention "sol-attn" (1.3, 0.2, 1, "", 12288, 256, "exact_kv_and_rows", false) in the acceleration JSONs.
- SelfLiftH3Sampler: seed mode "fixed" or "randomize", 1, 3, 0.4 or 0.5, 0, 0.5, 1, latent upscaler file, false, true (values per the JSON; names are not labelled in the JSON).
- Prompts in the ref2va templates: PrimitiveStringMultiline "subject_definitions", "summary", "retention_analysis" (see PGP section above).

---

## (b) Recommended architecture, mapped onto our stack

Stack from the brief: Google Flow (Nano Banana) for character sheets and keyframes; our watermark remover; MiniMax H3 + Pika H3 Flex 6-step LoRA in Wan2GP on Kaggle T4 (proven: 5 s at 832x480, 8m50s, 3.3 GB VRAM peak, --profile 5; Veda attention not supported on T4); Wan 2.2 fallback; ElevenLabs; ffmpeg.

| Stage | Have | Add / change | Source support |
|---|---|---|---|
| 1. Story and shot list | Nothing in the stack. | Shot list written by hand or with the owner's own chat LLM (no paid API). Keep each shot as: subject, action, camera, duration. | 8xuxQP [02:39-02:59] (ChatGPT turns template into prompt). |
| 2. Character sheets | Google Flow (Nano Banana) plus watermark remover. | One sheet per character with several views: front, back, full body, face close-up. Use a 3-panel layout (face + full front + back). Keep the sheet for every character; two characters side by side in one image rather than two references (speed). | aiseek (NOTES source 6); PGP [00:20-00:27]; 5sC [06:08-06:14] (two characters from a previous video). |
| 3. Keyframes / start and end frames | Google Flow for keyframes; FL2VA plan A. | Generate start and end frames from approved images. Use the subject_definitions / retention format for prompts (see PGP JSON). | PGP JSON ref2va template; 8xuxQP [01:47-01:49] (two images hybridise into a scene). |
| 4. Video (base) | Wan2GP on Kaggle T4, Pika 6-step LoRA, 832x480 5 s, about 8m50s. | Test Ref2VA vs FL2VA side by side on one shot. Keep one turbo LoRA only (Pika). Add the 8-step Pika route for shots with far faces (5sC). | 5sC [01:50-01:56] (no second turbo LoRA); 5sC [07:32-08:03] (fewer pixelated far faces). |
| 5. Two-stage / high-action | Not in Wan2GP as far as we know. | Test a split-sigma (high/low) run and a two-stage (low-res then latent upscale) run for high-action shots only. | 5sC [09:18-10:10]; PGP [06:23-07:12]. Wan2GP support: not stated. |
| 6. Upscale | Only watermark remover; ffmpeg. | Start with ffmpeg lanczos scale (free, no GPU). Add the H3 latent upscaler (fp16 file) only if a ComfyUI or Wan2GP path is found. Skip Topaz (paid). | 5sC [12:18-13:17] (latent upscale to 1080p preferred over Regen 2K). |
| 7. Voice and sound | ElevenLabs voices. | Keep ElevenLabs as the voice source. Use the H3 audio VAE only for SFX/ambience if tested. Pin the video to a frozen ElevenLabs line for talking shots (lip-sync from H3 is weak). | Mickmumpitz (NOTES source 7) [pin to a voice line]; stRsg [10:59-12:08] (lip-sync hit or miss); 5sC [00:17-00:23] (audio in same pass). |
| 8. Edit | ffmpeg. | Add a grading pass and scene assembly in ffmpeg. No new tool. | n/a |

Add list (what is missing in our stack): a story/shot-list step; the upscale path (ffmpeg fallback first); a face-reference crop for identity lock (untested); and a test of whether Wan2GP can run the SelfLift two-stage sampler.

---

## (c) Optimization list

Expected gains are the figures the speakers reported on their own cards (RTX 4090, 5090, 16 GB card). They do not transfer to T4 without a test.

| # | Change | Expected gain (reported) | Source and timestamp | Fits our T4? |
|---|---|---|---|---|
| 1 | Two-stage SelfLift sampler (low-res, latent upscale, continue), Euler, 6 steps | 5 s: 125 s to 29 s on 4090 (about 4x). 10 s: 61 s. | PGP [06:23-07:48] | Unknown: needs a Wan2GP or ComfyUI path. Test. |
| 2 | SageAttention patch + sol-attn sparse attention | 125 s to 50 s on 4090 (about 2.5x). | PGP [04:08-04:29] | Unknown: Sage kernels may not run on T4 (Turing). Test. |
| 3 | SolVAE (minimax_h3_sol_vae) | 50 s to 47 s (about 6%). Lost fan detail. | PGP [04:38-05:18] | Unknown. Gain is small; skip unless quality is fine. |
| 4 | Scheduler: Simple instead of manual sigmas in two-stage | Removes start-of-clip flicker. No time figure. | PGP [07:05-07:30] | Yes (scheduler choice only). |
| 5 | Euler sampler (only option for the SelfLift node) | Required by the node. No time figure. | PGP [06:59-07:05] | Yes. |
| 6 | Smaller H3 video VAE (new Comfy VAE) | "smaller ... makes it run faster" on 16 GB. Figure not stated. | stRsg [08:19-08:49] | Likely yes (VRAM); test. |
| 7 | Molmo2 text encoder (about 9 GB) instead of INT8 Qwen (about 26 GB) | 6 s at low res: 2.5 min on 16 GB (vs about 3.5-4 min before for same clip). | stRsg [02:37-02:55], [04:12-04:18], [04:58-05:03] | Unknown: needs a custom node and a Transformers version fix. Test. |
| 8 | Pika LoRA only; do not stack another turbo LoRA | Avoids broken output (speaker). | 5sC [00:47-00:54], [01:50-01:56] | Yes (already our setup). |
| 9 | Split-sigma high/low for high-action shots (6+6, or 8+8) | Better action detail; time roughly doubles (not stated). | 5sC [09:18-10:10] | Yes if the pass is available; test time. |
| 10 | Latent upscale to 1080p, not NVIDIA Regen 2K | Speaker prefers the result; Regen 2K "goes blurish". Time not stated. | 5sC [12:18-13:16] | Yes (ffmpeg fallback needed). |
| 11 | Pika 8-step LoRA for far and mid shots (face clarity) | Fewer pixelated faces than LightX2V 4-step. Quality, not speed. | 5sC [07:32-08:03] | Yes. |
| 12 | Keep action at normal pace; avoid "fast continuous" prompts | Avoids soft hair/body edges. Quality. | PGP [10:57-11:23] | Yes (prompt rule). |
| 13 | Motion dial 0 to 1 (not 2); avoid D-RoPE on character shots | Dial 2 "basically worthless"; D-RoPE changes faces. | stRsg [14:33-16:47] | Dial needs its custom node (ComfyUI); not in Wan2GP. |
| 14 | Skip the realism LoRA (speaker dislikes it) | Speaker says it "messes up the motion". | stRsg [03:50-03:54] | Yes. |
| 15 | Structured prompt format (subject_definitions, summary, retention_analysis) | Consistency; no figure. | PGP JSON ref2va template (node 138) | Yes (text only). |
| 16 | Chroma sampling set to auto (off by default) | "works out pretty well" (speaker). Quality. | 8xuxQP [04:05-04:10] | Unclear: the setting is not clearly described on screen. |
| 17 | Shorter clip (6 s instead of 15 s) for iteration, then long render | Iteration time. Speaker: 6 s in 2.5 min vs 15 s in about 6 min. | stRsg [04:12-04:18], [17:57] | Yes. |

---

## (d) What does NOT fit a Kaggle T4 or our no-paid rule

- NVFP4 text encoder (qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors): used by every Comfy-Org template JSON. Needs a Blackwell-class card. Not on T4. Our Wan2GP run uses its own encoder path (as proven).
- Pika-H3-Flex full base (about 210 GB per speaker [01:17-01:21]): too large for Kaggle disk. Use only the LoRA.
- Sage and sol-attn kernels (PGP): Sage targets Ampere and newer as far as known; sol-attn not checked on T4. Treat as "does not fit until tested".
- SolVAE: experimental per speaker [04:44-04:46]; untested on T4.
- Molmo2 text encoder path: needs a ComfyUI custom node and a Transformers version fix ([05:20-07:23]). Runs on 16 GB in ComfyUI; not on our Wan2GP path.
- Motion Speed Dials and D-RoPE: custom ComfyUI nodes; no Wan2GP equivalent known.
- NVIDIA Regen 2K (5sC): the NVIDIA node is not described in detail; the speaker found it blurrier than latent upscale. Skip.
- Topaz Video AI (5sC [13:04-13:08]): paid. Not allowed under the no-paid rule. Use ffmpeg instead.
- RunningHub (PGP): paid compute points after the free grant; invite-based. Not allowed.
- Patreon workflows (5sC, 8xuxQP's source freebie): gated. Not downloaded.
- Licence: "Minimax community licence" (5sC [00:47-00:54]). Earlier NOTES list excluded countries (EU, UK, South Korea, US). India not excluded per NOTES, but verify the licence text before any commercial use.
- Real-time speed claims (30 s per 5 s clip): measured on RTX 4090/5090. Our T4 is much slower; expect the 8m50s proven baseline, not these numbers.

---

## (e) Open questions

1. Does Wan2GP (our runner) support the SelfLift two-stage sampler or the latent upscaler file? If not, do we run ComfyUI on Kaggle instead (only if T4 + Sage/sol-attn work)?
2. Does SageAttention or sol-attn run on Kaggle T4 (sm75)? One smoke test answers it.
3. Is the Molmo2 encoder usable with Wan2GP? It is 9 GB against our current encoder size.
4. What does "Chroma sampling" do in the Pika template? It is not described on screen.
5. Does Pika Flex with 6 steps keep faces on T4 at 832x480 (our baseline)? The NOTES plan says yes for FL2VA; no face test is on record.
6. Are the 8xuxQP and 5sC Patreon workflows worth the owner's manual download? Probably only the Dropbox JSON (source 11) is useful; approve if wanted.
7. Licence: check the MiniMax community licence text for India and commercial output before any release (NOTES item 1).
8. The 5sC transcript ends with text that looks hallucinated [13:34-13:53]; treat its last lines as unreliable.

---

## Comparison table across the four videos

| Topic | 8xuxQP (smallzero) | 5sC (Benji) | PGP (Veteran AI) | stRsg (Ok Todd) |
|---|---|---|---|---|
| Main claim | Pika H3 Flex quick local video, sometimes preferred over H3. | Pika LoRA vs LightX2V: better far faces; LightX2V better for talking hands. | Speed path: 125 s to 29 s for 5 s on 4090; face consistency strong. | Molmo2 encoder + VAE = faster on 16 GB; dials; D-RoPE fixes motion but not faces. |
| Turbo / speed LoRA | Pika LoRA only. | Pika 2/4/8 vs LightX2V 4-step; never stack. | Pika FL2VA/REF2VA at 6 steps. | Pika LoRA + realism LoRA (dislikes it). |
| Sampler | Not stated (template defaults). | "basic" sampler; split sigma 6+6 for action. | LCM with manual sigmas (base); Euler + Simple (two-stage). | Euler + Simple (LCM + Beta worse for him). |
| Steps | Not stated. | 8 (compare); 12 split (action); 16 (8+8). | 6 (base and two-stage). | 6 (speed run); 10 with split 8 (quality). |
| Resolution | 16:9 for a 1:1 input; "a little bit low". | 0.8 MP base; 1.5 MP latent upscale; 2.0 MP option. | 1376x768 (about 1.0 MP target). | 1088x608 (15 s run). |
| Upscale | Not covered. | Latent upscale to 1080p preferred over NVIDIA Regen 2K. Topaz for 2K/4K (paid). | Not covered. | Not covered. |
| Character consistency | Not tested; suggests a face close-up reference. | Two-character test: consistent; Pika better at distance. | Sheet + 6-panel storyboard: strong. | Faces change with D-RoPE; not solved. |
| Fast action | Not tested. | Single pass poor; split sigma helps. | Fast continuous punches soften edges. | Fight scenes poor; dial 2 unusable. |
| Audio / lip sync | "It's got soundscape" [01:40]. | Audio in same pass; talking fingers odd. | Not covered. | Lip-sync to lyrics: 1 of 3 good. |
| Prompt method | ChatGPT rewrites the template example from a reference image. | Long prompt for action; short for test. | Structured fields (subject_definitions etc.) in the JSON. | Short prompt in tests; no quoted text. |

Where they agree:
- Pika LoRA works alone; do not stack another turbo LoRA (8xuxQP, 5sC).
- Character identity is better with Pika than with plain turbo LoRA at distance (5sC, PGP).
- Normal motion pace is safer than fast action (PGP, 5sC, stRsg).

Where they contradict:
- Upscale: 5sC prefers latent upscale over NVIDIA Regen 2K; no other video tests Regen.
- Sampler: PGP says Euler + Simple; stRsg says LCM + Beta was worse for him; a commenter suggested LCM + Beta. Official template uses LCM + manual sigmas.
- Speed of one clip: 8xuxQP says 3-4 min (5090, 5 s); PGP says 30 s (4090, 5 s, two-stage). Different methods; not comparable.
- Face: PGP says faces hold; stRsg says D-RoPE changes faces. Not a contradiction on the same method, but a warning.

---

## Appendix: full descriptions (verbatim from the info files, line 1 excluded)

### Source 8: 8xuxQP_M-h0

```text
Today we're testing **Pika H3 Flex inside ComfyUI**, a new AI video workflow that uses the MiniMax H3 video model alongside a custom LoRA.

I actually stumbled across this workflow while browsing ComfyUI and figured I'd give it a try. I hadn't done much research beforehand, but after playing with it, I've gotten some surprisingly good results.

And you know me, I had to test it with AI influencers and JDM cars.

For this video, we're looking at both **image-to-video and text-to-video generation**, using a free workflow available directly inside ComfyUI.

I started with some AI influencer images I previously generated using MOSS Image SFT, then used Pika H3 Flex to animate them into JDM-inspired photography scenes.

The results are pretty cool, especially considering we're running this locally.

**In this video, I'm testing:**

- Pika H3 Flex with MiniMax H3
- Image-to-video using MOSS Image references
- JDM car meets and automotive photography
- AI influencer motion and pose consistency
- Squatting, posing, and hand gestures
- Text-to-video without reference images
- Toyota Chaser generation inside a parking garage
- Prompt creation using ChatGPT
- BF16 vs INT8 model options
- Chroma sampling settings in ComfyUI

One thing I really like is how simple the workflow is to get started with.

If you're on an updated version of ComfyUI, you should be able to find the **Pika H3 Flex reference-to-video workflow** in the workflow templates. There's also a text-to-video version and a first-frame/last-frame option.

You'll need the Pika H3 Flex LoRA and the corresponding MiniMax H3 model files.

For my testing, I'm using the BF16 version rather than INT8, mainly because I already had it installed and I'm running everything on my RTX 5090.

I'm also using ChatGPT to help structure prompts based on the workflow's example format. I simply give it a reference image, explain the motion I want, and let it create a suitable prompt.

For one of the tests, I have an AI influencer posing in front of a JDM car, squatting down, and giving a peace sign.

The model actually follows the motion surprisingly well.

It's not perfect, and the resolution could definitely be higher, but for a quick local generation, I'm pretty happy with the result.

Then we switch over to text-to-video and generate a Toyota Chaser scene inside a parking garage.

The car details are probably my favorite part of that test.

Overall, **I think Pika H3 Flex has a lot of potential**, and from these initial generations, I actually prefer some of the results to standard MiniMax H3.

Of course, this is just an early test, and I'd love to hear whether you agree.

Have you tried Pika H3 Flex? Are you getting better results with INT8 or BF16? And have you experimented with multiple reference images or first-frame/last-frame generation?

Let me know in the comments, and if you've got any interesting ComfyUI workflows you'd like me to cover, send them my way!

**Join the SmallZero community:** https://smallzero.io

Thanks for watching!

#ComfyUI #PikaH3Flex #MiniMaxH3 #AIVideo #SmallZero

Join our community: https://smallzero.io
Skool: https://www.skool.com/small-zero-ai-5861/ 
Twitter: https://x.com/Smallzero

####

Disclaimer:

The content on this channel is provided for educational and informational purposes only. While I strive to share accurate and up-to-date information about artificial intelligence tools, software, and workflows, I am not responsible for how you choose to use this information.

0:00 Testing Pika H3 Flex in ComfyUI
0:32 MOSS Image Influencer & JDM Video Results
1:04 Where to Find the Free ComfyUI Workflow
1:26 Text-to-Video & Reference-to-Video Features
1:59 Installing the H3 Flex LoRA & First Results
2:38 Creating Better Prompts With ChatGPT
3:09 AI Influencer Motion Test & BF16 Settings
4:01 Chroma Sampling & Image-to-Video Results
4:57 Switching to Text-to-Video
5:28 Toyota Chaser Generation & Final Thoughts
```

### Source 9: 5sC-FjwGqmQ

```text
Pika H3 Flex in ComfyUI: I run Pika's fine-tune of MiniMax H3 side by side with the LightX2V turbo LoRA on identical prompts, then push the winner through split sigma sampling and a 2K latent upscale.

Pika post-trained MiniMax H3 on their own footage and shipped it as LoRA adapters that load on the H3 base you already run in ComfyUI. In this video I test the Pika H3 Flex Turbo LoRA (2, 4 and 8 step files) against the LightX2V turbo LoRA we usually use: same prompts, same step counts, side by side. Then I take the high action scenes through a split sigma pipeline and finish everything with a latent upscale pass to 1080p.

This one is for anyone already running MiniMax H3 in ComfyUI who wants to know whether a fine-tune is worth the download, and for reference-to-video users who care about face consistency at distance. No new architecture, no new install: the adapters drop into your existing models folder.

Why it matters: distilled H3 runs went from twenty-plus steps to a handful, but not every fine-tune wins everywhere. In my tests Pika keeps faces readable in far and mid shots where the usual turbo LoRA pixelates, while the old turbo still owns talking-hand motion. I show both failures and both wins, plus the upscale LoRA stack that stopped fighting the Pika adapter.

Resources:
- Freebie workflow attached in the description: https://www.patreon.com/aifuturetech/posts/174179682?utm_source=youtube&utm_medium=video&utm_campaign=202611
- Pika H3 Flex (official adapters): https://huggingface.co/Pika-Labs/Pika-H3-Flex
- Pika H3 Flex Turbo LoRA (2/4/8 step): https://huggingface.co/akhaliq/Pika-H3-Flex-Turbo-LoRA
- ComfyUI tutorial and template workflows: https://docs.comfy.org/tutorials/video/pika/pika-h3-flex
- Comfy-format BF16 LoRAs: https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/loras
- MiniMax H3 Singularity V2 (base used in this video): https://huggingface.co/WarmBloodAban/Minimax-h3_Singularity


Chapter : 
00:00 - Introduction to Pika H3 Flex
00:59 - Hugging Face models & setup
02:56 - Reference image outfit test
03:43 - Pika H3 Flex vs Light X2V comparison
05:54 - Face consistency & dialogue test
08:13 - High-action scenes & split sigma sampling
10:57 - Upscaling: Latent upscale vs Nvidia Regen 2K
13:17 - Final sample showcase & conclusion

Calliope - Local-first Agentic Idea-to-video Studio 
https://github.com/benjiyaya/Calliope

If You Like tutorial like this, You Can Support Our Work In Patreon:
https://www.patreon.com/c/aifuturetech

#PikaH3Flex #MiniMaxH3 #ComfyUI #AIVideo #TurboLoRA
```

### Source 10: PGP4Hrir6hk

```text
Can you really render a 10-second MiniMax H3 video at 1.0 Megapixels in just 60 seconds on an RTX 4090? 🚀 Pika just dropped Pika H3 Flex, delivering an unprecedented balance between blazing generation speed and hyper-accurate character consistency!
In this tutorial, we modify the official baseline workflow step-by-step—adding SageAttention, Sol-Attn, Kijai’s experimental Sol VAE, and the SelfLift Progressive Sampler—to smash render times from 125s down to just 30s for a 5-second clip! More importantly, we test whether Pika H3 Flex finally solves the dreaded "generic plastic AI face" problem across multiple complex scenarios.
🔥 Speed Benchmarks in this Video (RTX 4090):
• ⏱️ Official Baseline: ~125s (5s clip)
• ⚡ Stage 1 (Sage + Sol-Attn): ~50s
• 🚀 Stage 2 (+ Sol VAE): ~47s
• 🏎️ Stage 3 (SelfLift 2-Stage Sampling): ~29s (5s clip) / ~61s (10s clip)
🔥 What you'll master in this tutorial:
• 🧠 The Pika H3 Flex Architecture: Exploring the FL2VA (I2V / First-Last Frame) and Ref2VA (Ref-to-Video) LoRAs.
• 👤 Flawless Character Likeness: Locking specific facial bone structures and hairstyles across completely new scenes and outfits.
• 🥊 Dynamic Action & Combat: Stress testing boxing combos, rapid punching, and hair physics.
• 🎬 6-Panel Storyboard Test: Converting a 6-grid dance storyboard into a continuous, multi-camera sequence with zero character drift.
• ⚙️ The SelfLift Anti-Flicker Fix: Why switching from manual sigmas to Euler + Simple eliminates opening frame flickering.

#runninghub #PikaH3Flex #PikaAI #MiniMaxH3 #ComfyUI #AIVideo #SpeedUpAI #CharacterConsistency #SelfLift #SolAttn #SageAttention #AIFilmmaking #GenerativeAI #RunningHub #AITutorial #VideoGeneration

------------------------------------------------------------------------------------------------------------------------
resource
https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/lora
https://huggingface.co/Pika-Labs/Pika-H3-Flex
https://docs.comfy.org/tutorials/video/pika/pika-h3-flex

1：pika_h3_flex_fl2va
https://www.runninghub.ai/zh-cn/post/2117085837866684418/?inviteCode=kol02-rh021

2：pika_h3_flex_ref2va
https://www.runninghub.ai/zh-cn/post/2117153481216139265/?inviteCode=kol02-rh021

3：pika_h3_flex_fl2va_sol_attn
https://www.runninghub.ai/zh-cn/post/2117088501236826113/?inviteCode=kol02-rh021

4：pika_h3_flex_ref2va_sol_atten
https://www.runninghub.ai/zh-cn/post/2117094885589688322/?inviteCode=kol02-rh021

5：pika_h3_flex_fl2va_2stage_sampling
https://www.runninghub.ai/zh-cn/post/2117151265058050049/?inviteCode=kol02-rh021

6：pika_h3_flex_ref2va_2stage_latentupscale
https://www.runninghub.ai/zh-cn/post/2117100808910524418/?inviteCode=kol02-rh021


RunningHub Fan Benefit: Sign up and get 1,000 free compute points.
https://www.runninghub.ai/?utm_source=kol02-RH021

workflow and prompt engineering download：
https://github.com/amao2001/ganloss-latent-space/tree/main/workflow/2026-11-03%20pika%20h3%20flex

------------------------------------------------------------------------------------------------------------------------
```

### Source 11: stRsg-wNQds

```text
MiniMax H3 speed is significantly improved with the new Molmo2 text encoder. I test these motion updates to optimize your workflow.

This video walks through the latest updates to the MiniMax H3 model, focusing on how the integration of the Molmo2 text encoder impacts generation speed and overall responsiveness. I demonstrate the practical differences by running several motion tests, comparing the new encoder performance against previous versions to see where the gains are most noticeable.

Free workflow:  https://www.dropbox.com/scl/fi/hkojsgteneyrtfkrupn8c/Ep49-Deno_MiniMax_H3_R2V_Turbo_8plus2.json?rlkey=ati3s3c94905qtgorig0zpxi1&st=pi291aqs&dl=1

That workflow also includes the custom node for motion speed dials as well as the De-Rope section to the far right.

Molmo2 HuggingFace repo:  https://huggingface.co/Alissonerdx/Molmo2-8B-Minimax-H3
and Github:
https://github.com/alisson-anjos/ComfyUI-Molmo2-H3

Motion Speed Dials Custom Node:  https://github.com/matlowai/ComfyUI-Dials

__________________________________________________________________
Time Stamps

0:00 - 2:21 - Introducing Molmo2, Motion Dials, and D-RoPE Tests
2:22 - 3:34 - Molmo2 vs My Previous Text Encoder: Size and Speed
3:35 - 5:08 - Speed Test: A Six-Second Video in Two and a Half Minutes
5:09 - 6:35 - Troubleshooting the Molmo2 Installation Error
6:36 - 7:34 - Fixing the Python File Indentation
7:35 - 8:18 - Connecting Molmo2 to the Existing Workflow
8:19 - 8:49 - Switching to the Smaller MiniMax H3 VAE
8:50 - 9:47 - How Motion Dials Control Movement Speed
9:48 - 10:58 - Cartoon Test: Clean Motion and Consistent Characters
10:59 - 12:49 - Singing Tests: Matching Lyrics, Audio, and Lip Sync
12:50 - 13:52 - Realistic Skin and Sampler Comparisons
13:53 - 15:15 - Running Tests: Comparing Motion Dial Settings
15:16 - 16:06 - D-RoPE: Better Motion, but Changed Faces
16:07 - 17:46 - Sword Fight Tests: Motion Speed, Blur, and D-RoPE
17:47 - 18:33 - Fifteen-Second Talking Head Test and Skin Quality
18:34 - 19:40 - Updated Step Settings, Downloads, and Final Thoughts
__________________________________________________________________

Some of my must have computer tools:
Logitech MX Master 4 Mouse - https://link.amazon/B05yEOQV3
Apple Airpods Pro 3 Headphones - https://link.amazon/B00sML41Z
Nvidia Graphics Card 4070 TI Super 16gb Vram - https://link.amazon/B0gCGmjPm
Samsung 4K M7 Smart Monitor - https://link.amazon/B0egSfFaE
Wolfbox Compressed Air Electronic Duster - https://link.amazon/B0cerJd5t
FlexiSpot 72x30 Adjustable Standing Desk - https://link.amazon/B05QhWRDA
FlexiKing Office Chair - https://link.amazon/B0fGxJpZ7
Apple Ipad Pro with Lidar Scanner - https://link.amazon/B0cbqNcH0
Apple Pencil Pro - https://link.amazon/B0gx54RwT
```

