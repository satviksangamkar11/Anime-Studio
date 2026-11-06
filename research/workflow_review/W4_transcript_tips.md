# W4 transcript tips: MiniMax H3 / Pika H3 Flex for a 2.5D cel-shaded film

Reviewer W4 | 2026-11-05 | Read-only review. No downloads, no web, no paid calls, no secrets read. Output resolution ignored (we upscale later).
Target: generation quality for the 16 s leap scene (LEAP-01..05, `DIRECTION.md`).

## 1. Bottom line

- **Anime-specific tips found: 0.** None of the 7 transcripts or their 7 descriptions mention anime, cel-shading, flat colour or 2D. Every row below is general (G). Rows tagged `NOTES` or `GUIDE` come from the owner's notes/guide, not from these transcripts, and are unverified.
- **Identity across shots is not measured by any source.** The usable identity tips are workflow-level: two references (face + body), exact reference labels, no caching on face/hand shots, keyframes from one generator family.
- **Every speed number is one creator, one run, on RTX 5060 Ti 16 GB** (each description lists 14400F, 64 GB RAM, RTX 5060 Ti 16 GB). None transfers to Wan2GP on a Kaggle T4 without a test. Most speed tips are ComfyUI nodes; no source states a Wan2GP equivalent.
- **Sources disagree** on the 6-step sigma schedule, on Sage quality, and on whether De-Rope changes faces (section 4).
- Shot budget reference: the owner's own T4 baseline is 5 s at 832x480 in 8m50s (`GUIDE` section b). Our five leap shots are 4.46 s each (107 frames), so roughly 45 min per pass before retries.

## 2. Sources and legend

Folder for T1-T7 and D1-D7: `D:\aai work\research_transcripts\aininja94\`. Timestamps `[mm:ss]` are from the `.txt` caption files. The caption `.json` files carry the same text with second-precision starts; I checked all seven and used the `.txt` markers. `D` = that video's `_description.txt` (creator text: claims, not measurements).

| Code | File (`...\aininja94\`) | Topic |
|---|---|---|
| T1 | `20260804_KlINSdYDSe4_MiniMax H3 On RTX 5060 Ti Test, Setup & Speed Boost Guide.txt` | Setup, Sage, Sol-Attn, Easy Cache, Ref2VA labels |
| T2 | `20260813_ykf9axFwmnc_Comfy UI Attention, Caching & Memory Management Nodes - MiniMax H3.txt` | Attention, caching, low-VRAM nodes |
| T3 | `20260819_OS31rr2QfkU_MiniMax H3 in ComfyUI_ Multi-Keyframes, Long Videos & Video Extension.txt` | Keyframes, Motion Context, trim, extension |
| T4 | `20260823_2IxKL3-Igh4_MiniMax H3 Face Swap & Body Swap in Comfy UI _ Complete Workflow.txt` | SAM 3 mask, crop, face/body swap |
| T5 | `20260913_eSDey7wAK60_MiniMax H3 Context Loop Explained — Generate Long Videos with Scene Continuity in Comfy UI.txt` | Context Loop, checkpoints, cut/guide |
| T6 | `20261101_7cog89wVP_A_Pika Just Changed Open Source Video AI! (Pika-H3-Flex + 2K Upscale in ComfyUI).txt` | Pika 6-step, LCM, refiner |
| T7 | `20261102_iA2TOpyY218_Minimax H3 + Pika + ComfyUI Dial (No Training Required!).txt` | Motion dials, dial maker, De-Rope |
| D1-D7 | same names as T1-T7 with `_description.txt` | Creator cheat sheets, repos, hardware |

Secondary files: `NOTES` = `D:\aai work\research_transcripts\NOTES_RUN_BIG_VIDEO_MODELS.md` (its sources 1-11). `GUIDE` = `D:\aai work\research_transcripts\INDIAN_ANIME_STUDIO_ARCHITECTURE_GUIDE.md` (its sources 8 = 8xuxQP, 9 = 5sC, 10 = PGP, 11 = stRsg). Those transcripts are not in this review's scope, so I cite their own timestamps and tag them.

Columns: **Type** G = general, A = anime-specific. **Portable?** CUI = needs a ComfyUI node (Wan2GP equivalent not stated); Setting = a value or wording usable in any runner; Test = needs our own measurement.

Our stack (per `NOTES` and `GUIDE` section b): MiniMax H3 + Pika H3 Flex 6-step LoRA in Wan2GP on a Kaggle T4.

## 3. Tips by group

### (a) Prompts and the Ref2VA prompt structure

| ID | Tip | Exact values or wording | Source | Type | Portable? |
|---|---|---|---|---|---|
| a1 | Copy the reference label exactly as the Ref2VA node prints it. | "Picture-1", "Picture-2", "Audio-1"; "we need to use these exact labels"; labels come from the node code. | T1 [07:52-08:09] | G | CUI (Wan2GP label syntax not stated) |
| a2 | Labels follow connection order; adding an input changes the next label. | A separate audio clip after a reference video becomes "Audio-2"; the reference video is "Video-1". | T1 [09:18-09:53] | G | CUI |
| a3 | Ref2VA prompt = block 1 says what each reference is for; block 2 gives timed beats. | "During the first five seconds, the dinosaur from Picture-1 walks. After five seconds, the dinosaur roars using the sound from Audio-1. Finally, the video ends with the dinosaur lowering its head." Full prompt text not stated. | T1 [08:09-08:29] | G | Setting |
| a4 | Shared prefix on every shot, scene text per shot. | "The prompt entered here is automatically added to the beginning of the prompt for every scene." Shared Prompt = prefix; Scene Prompt = per shot. | T5 [05:01-05:23], [06:37-06:48] | G | CUI node; the idea is portable |
| a5 | Expand a template prompt with an LLM from the images and the motion idea, keeping the template's structure. | Give the reference images "along with a sample prompt to Gemini"; Prompt Director asks for clip count, seconds per clip and context. | T3 [02:58-03:03], [03:43-03:53]; T1 [05:43-05:52] | G | Setting. Our rule: no paid calls |
| a6 | Keep the prompt fixed; change motion with the dial, not extra wording. | "The prompt is kept as it is"; motion from the prompt alone has "a limit". | T7 [00:36-01:03] | G | CUI (dial) |
| a7 | Prompt obedience failure: a later voice was dropped. Changing the prompt fixed it. | "it failed to generate the woman's voice after the man's voice... Later I change the prompt, and tried which worked." | T1 [03:15-03:19] | G | Setting (failure note) |
| a8 | Identity sentence in the prompt (NOTES). | "image 1 is the sole character identity reference. Preserve her exact facial identity, hairstyle, outfit ..., body proportions and appearance throughout the entire video." | NOTES src 6 (aiseek). Not in transcripts | G | Secondary, Test |
| a9 | Name everything that must stay (NOTES). A short look line beats long skin text (NOTES). | "Name everything to keep (else the model may change clothes)"; "long ones give plastic skin". | NOTES src 6 (aiseek) | G | Secondary, Test |
| a10 | Fast-action wording softens hair and body edges (GUIDE). | "I explicitly ask for fast continuous punches. Hair and body edges go soft." | GUIDE 10 (PGP) [10:57-11:23] | G | Secondary |

### (b) References and character sheets

| ID | Tip | Exact values or wording | Source | Type | Portable? |
|---|---|---|---|---|---|
| b1 | Two references per character: face image and body image. | "upload two images of the character. The first is the face image, and the second is the body image." | T3 [09:27-09:39] | G | CUI |
| b2 | Make the reference as a character sheet, remove its background, then stitch and preview. | Sheet made with Flux Klein; "prompt used here is for generating a character sheet"; background-removal model (name not stated) runs first; both images stitched. | T4 [01:30-02:00] | G | Our sheets come from Flow; same role |
| b3 | A weak reference gives the wrong person. Replace the reference first. | "You should use a better quality image then the one I am using"; result: "the old man appeared after the first second". | T4 [13:38-13:42], [13:52-13:57] | G | Failure note |
| b4 | Preview the target frame before a full run: switch off processing nodes and run once. | "Disable these processing nodes and run the workflow to get the first frame." | T4 [12:15-12:38] | G | CUI |
| b5 | Isolate one person with a mask prompt ("Head", "full body"); allow one object. | "Head" prompt; "full body" prompt; max object 0 -> 1; detection_threshold higher = stricter; detect interval 1 (every frame) vs 5. | T4 [04:18-04:30], [11:24-11:28], [12:51-13:21] | G | CUI (SAM 3). Plates only |
| b6 | Two characters in one image beat two references for speed (NOTES). | "More reference images = up to 3x slower at high res: put two characters side by side in ONE image." | NOTES src 6 (aiseek) | G | Secondary, Test |
| b7 | Three-panel sheet: face close-up, full front, back (NOTES). | "Character sheet with 3 panels (face close-up + full body front + back)." | NOTES src 6 (aiseek) | G | Secondary; matches CHAR-KRISHNA sheets |
| b8 | Reference audio gives voice cloning. | "the reference audio workflow is excellent for voice cloning". | T1 [09:47-09:59] | G | Not needed: ElevenLabs line is pinned |

### (c) Start/end keyframes and multi-keyframe

| ID | Tip | Exact values or wording | Source | Type | Portable? |
|---|---|---|---|---|---|
| c1 | Keyframes are placed by frame number. The node reads width, height and frame count from the latent. Up to 32 keyframes. | "frame 62 is in the middle of the video"; "support for up to 32 keyframes"; Index "zero or one; I'll keep it at one"; Crop = how sources fit the latent aspect (value not stated). | T3 [01:07-02:16] | G | CUI (H3 Custom Keyframes; repo not named in caption) |
| c2 | Keep all keyframes in one generator family. A different generator shifts colour. | Flux Klein keyframes: "a difference in the color of the car"; "issue with the color ... due to the image generated by the Flux model". | T3 [02:46-03:17] | G | Setting: our B frames are Flow edits of A |
| c3 | Test at a small size, then step up. | "point 3 pixels" test (140 s); "results look better at point 5 pixels". | T3 [03:04-03:17] | G | Setting; output size otherwise irrelevant |
| c4 | Start and end frames: both, one, or none (text-to-video). | "The conditioning node accepts both images when they are provided. Otherwise, this workflow also works as a text-to-video workflow." | T1 [04:33-04:39] | G | Setting |
| c5 | Mask latent: diffusion acts only on the masked area; the rest comes from the source clip. | "This allows the diffusion process to work on the masked area while using the given image as the condition." | T4 [02:47-03:05] | G | Needs a source clip; not for generated shots |
| c6 | Mask cleanup: min_frames controls flicker; edge_grow raised above the recommended 4 (value not stated). | "min_frames remove unwanted blobs ... it affects the video flicker." | T4 [05:15-06:14] | G | CUI; mask-only |

### (d) Sampler, steps and LoRA

| ID | Tip | Exact values or wording | Source | Type | Portable? |
|---|---|---|---|---|---|
| d1 | Pika-H3-Flex: 6-step distilled LoRA on base or INT8 H3. | "reduces the required sampling steps from the default 20-50 steps down to just 6 steps, cutting generation time by up to 80%"; two files: T2V/I2V and reference-to-video. D6: reduced-rank Kijai LoRAs ~550 MB. | T6 [00:34-01:17]; D6 | G | Setting (in our stack) |
| d2 | Pass-1 cheat sheet from the creator (exact values). | Model H3 base or int8; LoRA "Pika H3 Flex FL2VA (or Ref2VA) at 1.0 Strength"; Sampler LCM; CFG 1.0; custom sigmas (6 steps) 1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0; Sigma shift Video 12.0, Audio 3.0. | D6 (cheat sheet) | G | Setting. **Conflicts: section 4, C1** |
| d3 | Basic Scheduler instead of manual sigmas. Creator reports +8-9% speed. | "I noticed an increment in speed by 8 or 9 percent" (T6 also says the sigmas were removed). | T6 [02:22-02:32] | G | Setting; check quality |
| d4 | Chunk feed-forward node: creator says no noticeable change to the result. | "These nodes work really well without noticeably affecting the final result." | T6 [01:57-02:08] | G | CUI |
| d5 | Kitchen Attention: creator says it makes distilled results "bad", accepted the difference. | "I know this makes the result bad when used with distilled models, but I have compared, the difference is acceptable." | T6 [02:13-02:22] | G | Setting; A/B on face shots |
| d6 | A second turbo LoRA was used with no quality result. Multi-keyframe used a 4-step FL turbo; face swap used an 8-step LoRA with the 4-step as an option. Which file is not named. | "I just wanted to check the difference in quality." (no result given). | T3 [00:46-00:52]; T4 [01:08-01:18] | G | Test |
| d7 | Do not stack a second turbo LoRA on Pika. | "you do not stack another Turbo LoRa on top of it in the Comfy UI workflow." | GUIDE 9 (5sC) [01:50-01:56] | G | Secondary. No transcript stacks Pika |
| d8 | No caching with a turbo LoRA at 6-8 steps. | "I do not recommend using these caching nodes with a Turbo LoRA ... only 6 or 8 sampling steps." | T2 [08:46-09:04] | G | Setting (see g6-g7) |
| d9 | Scheduler change removes opening-frame flicker (claim). | "Euler + Simple eliminates opening frame flickering" (PGP description, quoted in GUIDE). | GUIDE 10 (PGP) [07:05-07:30] | G | Secondary, Test |
| d10 | Refiner pass values from the creator's cheat sheet (only if we use a refiner). | "Steps: 2 steps; Sampler: Euler or er_sde; Manual Sigmas: 0.7, 0.494118, 0.0"; refiner LoRA rank 16 (155 MB). | D6 (pass 2) | G | Setting; identity risk, see h4 |
| d11 | Non-distilled baseline for timing: 20 steps at 12 s per iteration. | "Since there are 20 steps, the time taken to generate a 5-second video is 323 seconds." | T1 [02:05-02:15] | G | Baseline |

### (e) Motion control (dials, De-Rope, split sigmas)

| ID | Tip | Exact values or wording | Source | Type | Portable? |
|---|---|---|---|---|---|
| e1 | Motion dial: a small motion file (~15 KB in T7, ~14 KB in D7) in a custom node. Strength is set in the node. No trigger word. | Dial "point five zero negative" -> "less motion"; a positive value -> "increased noticeably" (positive value not stated). "There is no trigger word." | T7 [01:03-02:02], [02:37-02:42]; D7 | G | CUI (ComfyUI-Dials, matlowai) |
| e2 | Dial range. | D7: "from frozen cinemagraphs (-2.0) to hyper-kinetic sprints (+2.0)". | D7 line 4 | G | CUI |
| e3 | Negative dial removes the action the prompt asks for; 0 = prompt's own motion. | "When the value is negative, the dog does not run even if you prompt for it." | T7 [02:46-02:58] | G | CUI |
| e4 | Build a dial from two opposite prompts. Use a {subject} placeholder and pipes. Average across subjects. Score above 0.6 = good. | "The word subject in curly brackets will be interpolated"; "separated by Pipes"; "averaging across these multiple subjects, individual identities are removed"; "greater than zero point six means it is good". | T7 [04:25-05:36] | G | CUI (dial_maker_h3; D7) |
| e5 | A dial does not replace a character LoRA; stack them. (Description heading only.) | "Why it DOESN'T replace Character LoRAs (and why you should stack them)." | D7 line 8 | G | Heading only; not explained in caption |
| e6 | De-Rope: detects fast motion, slows it briefly, cleans blurred frames. Generation takes longer. | "it detects high speed motion, temporarily slows down and cleans up the blurry frames"; "generation time will be higher". | T7 [06:23-06:42]; D7 (ComfyUI-MAINodes) | G | CUI |
| e7 | De-Rope face effect (claim from another video). | "it's messing up the faces" [01:51-01:54]; "Body motion improves, faces change" [15:15-16:06]. | GUIDE 11 (stRsg). Not in T7 | G | Secondary. **Conflicts with T7 silence (C6)** |
| e8 | Split sigma high/low for action. | 5sC: "high-sigma half does the first 6 steps ... 50/50", "8+8 = 16" [09:18-10:10]. stRsg: 10 steps split 8 high / 2 low, "slower but better quality" [18:41-18:52]. | GUIDE 9 (5sC), GUIDE 11 (stRsg) | G | Secondary, Test (time) |
| e9 | Blender layout video for camera moves in a shot workflow. | "Blender 3D layout video for camera moves." | NOTES src 7 (Mickmumpitz) | G | Secondary. Matches our H3-CONTROL fallback |
| e10 | Second dial file (speech tone). Use case unknown. | "I am still trying to find a better use case for it." | T7 [02:05-02:09], [03:21-03:45] | G | Skip |

### (f) Long video and shot continuity (Context Loop)

| ID | Tip | Exact values or wording | Source | Type | Portable? |
|---|---|---|---|---|---|
| f1 | Transition options between scenes: Cut, Guide, Hard AV, Soft AV. | "Cut ... start the next scene fresh; no visual carry-over." "Guide ... selected by default and recommended for continuation." | T5 [03:01-03:24] | G | CUI node; the meaning is portable |
| f2 | Final audio: Generated / Source / None. Lock source audio overrides generated continuity. | "None - that exports a silent video." "Lock source audio ... overrides the above generated continuity." | T5 [03:32-04:18] | G | Setting. Our sound is in post |
| f3 | Trim the repeated handoff frames at every join. Trim the audio by the same amount. | "Without this node, the final video will have repeated frames, and the audio ... would slowly stop matching the picture." H3 can add "a few milliseconds of extra audio". | T3 [04:44-05:33]; T5 [07:22-07:32] | G | CUI (H3 Motion Context Trim) |
| f4 | Crossfade frames must not exceed trim frames. 12 frames at 24 FPS = half-second dissolve. Hard cuts need 0. | "Crossfade Frames cannot exceed the Trim Frames value"; "12 frames gives you a clean half-second transition." | T3 [06:05-06:11]; T5 [10:17-10:22] | G | Setting |
| f5 | Motion Context memory settings. | context_length (value not stated); encode_mode "video" ("Keep it on video"); anchor_mode "Head"; audio_context_length 0 = match context_length; audio_mode "timeline". | T3 [07:23-08:01] | G | CUI |
| f6 | Checkpoint each scene (latent, prompt, seed, timing). Approve, re-run one scene with a new seed or prompt, resume later. | "The Checkpoint folder saves the latent continuation state ... prompts, seeds, timing"; "change the seed ID or the prompt and try again". | T5 [07:42-08:24], [11:02-11:18] | G | Process: copy the logic in our loop |
| f7 | New Run Name per plan; Start-Clip = 1. | "For every new video generation, make sure you change the Run Name in the Plan node, and set Start-Clip to 1." | T5 [11:18-11:32] | G | Operational |
| f8 | Clip length limit with the INT8 model: 15 s. Above it, "bad results". | "The duration for one clip can be a maximum of 15 seconds. Going above that gave me bad results with the smaller INT8 model." | T3 [04:15-04:21] | G | Our 4.46 s shots are well under |
| f9 | Time reference: 15 s clip ~200 s; 24 s at 0.4 MP = 550 s (INT8); 50 min for the whole video including checks. | "A single 15-second clip took around 200 seconds ... on my RTX 5060 Ti"; "24-second video ... took 550 seconds". | T5 [02:02-02:31]; T3 [04:06-04:15] | G | Budget |
| f10 | Extending a clip with a reference can change the speaker. | "The difference in the boy's voice is because the generated character is different from the one speaking at the end of the original video." | T3 [10:59-11:04] | G | Avoid extension on identity shots |
| f11 | Cut semantics for our planned cuts (our inference, not a source claim). | LEAP-03 to 04 (apex cut) and LEAP-04 to 05 (contact cut) use Cut so motion does not carry over. Test Guide only for the LEAP-02 to 03 crouch match. | DIRECTION.md; T5 [03:01-03:17] | G | Our inference |

### (g) Speed and VRAM

| ID | Tip | Exact values or wording | Source | Type | Portable? |
|---|---|---|---|---|---|
| g1 | Sage Attention: use the H3-specific node. Do not run both Sage nodes together. | "Usually, no. The H3 specific node is the more targeted choice." | T2 [05:14-05:32] | G | CUI |
| g2 | Sage speed and quality, by mode. | T2V 0.4 MP, 5 s, 20 steps: 12 -> 8 s/it, 323 s -> 187 s, "quality noticeably lower". FL: 297 s -> 185 s, "quality difference appears to be minimal". I2V 0.3 MP, 2 s: 72 s -> 41 s, "looks perfectly fine". | T1 [02:05-03:15], [04:44-05:07], [11:34-12:56] | G | CUI; Turing support untested |
| g3 | Sol-Attention (sparse). Dense blocks "0 and 2" and "-1" recommended for H3. Start/End % keep early and late steps dense. Higher Tau = faster and less accurate. Tau Profile sets Tau per block. | "For the Mini Max H3 model, these are the recommended blocks." Start/End and Tau values not stated. | T2 [06:13-07:55]; D2 (kijai ComfyUI-SolAttn_triton) | G | CUI |
| g4 | Sol-Attention speed and audio. | Iteration time "quite noticeable"; quality "doesn't seem to affect"; audio "became slightly worse". | T1 [10:26-11:13] | G | CUI. Audio risk for SFX |
| g5 | Chunk recipe for OOM (Low-VRAM Attention + Chunk FeedForward). | Chunks 1 = none. Start chunks 2 with head_chunks 1. If OOM, raise head_chunks. If GPU ~100%, raise chunks to 4. seq_threshold: leave default. | T2 [12:16-12:56], [13:34-14:34] | G | CUI |
| g6 | Easy Cache: speed, but skips steps. | T1: 53 s vs 72 s, "Easy Cache skipped 7 out of the 20 steps", "skipping steps generally means a loss in quality". T2: reuse threshold 0.1 or 0.15; start 0.2, end 0.9. | T1 [12:09-12:27]; T2 [08:33-08:46] | G | CUI. Not for us (d8) |
| g7 | Spectrum Cache: forecast-based skipping. Docs warn that eyes and fingers may change. | "motion and fast-moving details, small parts like eyes, fingers, may change." | T2 [09:16-09:37]; D2 (xmarre) | G | CUI. Not on identity or hands |
| g8 | Block Cache (T8). residual_diff_threshold: lower = closer to native. max_consecutive_hits default 2 forces a refresh. cache_device CPU saves VRAM. metric_stride 1 = every value, 8 = about every eighth. Use one cache node at a time. | Threshold values not stated. | T2 [09:43-11:26], [12:16-12:20]; D2 (T8) | G | CUI |
| g9 | Time the second run, not the first (model load). | "the first run usually takes longer while the model is being loaded into memory." | T1 [02:57-03:02], [11:58-12:04] | G | Setting |
| g10 | Test cheaply: a frame cap and a skipped start. | "Testing with 97 frames will be much faster"; skip the first 24 frames for the first-frame test. | T4 [11:41-12:03] | G | Setting, preview only |
| g11 | Crop around the subject, process the crop at higher megapixels, paste back with a feathered edge. Costs time and memory. | "Upscale_megapixels improves the result ... it has a significant effect on generation time and memory usage." | T4 [06:25-06:48], [07:35-07:40], [08:11-08:22] | G | CUI. For identity: test a tight face crop |
| g12 | Resolution references. | 0.4 MP default = "864 × 480"; 0.3 MP for quick tests. | T1 [01:40-01:51], [11:34-11:39] | G | Setting. Our 832x480 is the same class |
| g13 | Smaller INT4-mixed model (~15 GB) on Hugging Face. One test: "didn't perform very well". | D1 link: tsolful/Minimax_H3_INT4Mixed (probably the model in T1). | T1 [10:06-10:22]; D1 | G | Quality risk |
| g14 | Speed claims from other sources (not tested): 5 s at 480p = 11.5-16.5 min on a 16 GB GPU (Wan2GP). "veda sparse" ~33% faster (YouTube comment). 125 s -> 29 s on a 4090 with two-stage sampling. | | NOTES src 2 and src 3 (comment); GUIDE 10 (PGP) [03:13-07:48] | G | Secondary, Test. Veda not supported on T4 (GUIDE) |

### (h) Known failure modes and fixes

| ID | Failure | Evidence | Fix | Source | Type |
|---|---|---|---|---|---|
| h1 | Caching changes eyes and fingers. | "small parts like eyes, fingers, may change" | No cache on LEAP-01 or hand shots | T2 [09:32-09:37] | G |
| h2 | Caching with a turbo LoRA at 6-8 steps degrades. | "it can also degrade the result" | No cache on 6-step Pika runs | T2 [08:52-09:04] | G |
| h3 | Sage loses quality in text-to-video. | "the quality is affected, and the difference is quite noticeable" | A/B per shot; mode-dependent | T1 [03:09-03:15] | G |
| h4 | Refiner pass changes identity. | "the strength of the refiner needs to be adjusted. It is affecting the identity." Strength value not stated. | Lower the strength; A/B against the keyframe | T6 [07:30-07:34] | G |
| h5 | Colour drift between keyframes from different sources. | "a difference in the color of the car" | One generator family | T3 [02:46-03:17] | G |
| h6 | Repeated frames and audio drift at joins. | Repeated frames; audio "would slowly stop matching the picture". | Trim node at every join | T3 [04:44-05:33]; T5 [07:22-07:32] | G |
| h7 | Wrong person in a crowd. | "the old man appeared after the first second of the video" | Better reference; skip 9 frames (second try) | T4 [13:52-14:08] | G |
| h8 | Over 15 s per clip on INT8: bad results. | "Going above that gave me bad results" | Keep clips short | T3 [04:15-04:21] | G |
| h9 | High dial -> motion smear. | "characters moving fast may start to smear and blur" | De-Rope (time cost) | T7 [06:23-06:42] | G |
| h10 | Extension with a new speaker changes the voice. | "the generated character is different" | Do not extend identity shots | T3 [10:59-11:04] | G |
| h11 | Unknown which attention node ran. | "Check the program's output to see which attention node is being used." | Log the node per shot | T2 [14:34-14:41] | G |
| h12 | Nightly ComfyUI is unstable; a Manager UI broke after an update. | "nightly builds may include new but unstable updates"; "the Manager interface - turned transparent". | Pin the version; test updates | T7 [02:17-02:27]; T6 [01:28-01:34] | G |
| h13 | Sol-Attention lowers audio quality slightly. | "the audio quality became slightly worse" | Check SFX after any sparse-attention run | T1 [11:08-11:13] | G |
| h14 | Realism drift. Not tested by any transcript. Secondary: a realism LoRA "messes up the motion"; long skin text -> plastic skin. | | Skip realism LoRA; keep skin text short; test | GUIDE 11 (stRsg) [03:50-03:54]; NOTES src 6 | G |
| h15 | Fast action on 6 steps: soft edges, shrinking props, bad hands (secondary). | "Hair and body edges go soft"; "sword shrinks, bad hands". | Normal pace on LEAP-02 and LEAP-03 unless test passes | GUIDE 10 (PGP) [10:57-11:23]; NOTES src 4 | G |

## 4. Contradictions between sources

- **C1. Sigmas and sampler for the 6-step Pika pass (three versions).** D6 says LCM, CFG 1.0, a 7-value manual sigma list, shift 12/3. T6 [02:22-02:32] says the manual sigmas were removed and replaced by Basic Scheduler (+8-9%). NOTES src 5 says the creator's JSON uses er_sde with a different 4-value list (not verified by me). Test which one we use and record it in the decision log.
- **C2. Pika timing.** D6 says "under 60 seconds". T6 says 60 s for the base [00:01-00:05], "one step took around 30 seconds ... around 150 seconds" [02:55-03:07] (six 30 s steps would be ~180 s), and "200 seconds" [05:44-06:00]. Use the 150-200 s range, not the title claim.
- **C3. Sage quality is mode-dependent.** T1: noticeable loss in T2V [02:40-03:15]; "minimal" in FL [04:44-05:07]; "less noticeable" in I2V [12:52-12:56]. One clip per mode. Test per mode.
- **C4. Caching.** T1 uses Easy Cache for 26% speed (53 s vs 72 s) by skipping 7 of 20 steps, and calls that a quality loss. T2 [08:46-09:04] says do not cache with turbo at 6-8 steps. T1 does not name its LoRA or threshold, so its speed figure does not transfer to our 6-step runs. Follow T2.
- **C5. Sol-Attention quality.** T1 [11:01-11:05]: "doesn't seem to affect the video quality." T2 [05:52-05:57]: "a greater possibility of changing the denoising path if the settings are high." Settings-dependent. Test.
- **C6. De-Rope and faces.** T7 gives no face warning [06:23-06:42]. GUIDE 11 (stRsg) says faces change [15:15-16:06]. Treat as a risk until tested.
- **C7. Six steps and faces.** T6 presents 6 steps as good. NOTES src 2 says 6 steps give "less refined faces, broken background text." GUIDE 9 (5sC) [07:32-08:03] says the 8-step file holds far faces better than 4-step. Test 6 vs 8 on LEAP-01.
- **C8. Kitchen Attention.** T6 [02:13-02:22] says it makes distilled results "bad" but acceptable. T4 [01:08-01:18] uses it with an 8-step LoRA and gives no quality claim. Test on face shots.
- **C9. Label spelling.** T1 "Picture-1"; T4 [03:05-03:10] "Picture 1"; NOTES "picture 1". Copy the text the node prints (a1).
- **C10. Chained attention nodes.** T2 [14:34-14:41] describes a fallback chain. T1 [13:18-13:25] found Sage absent from the program output when Sol-Attention ran. Log which node ran (h11).

## 5. Gaps, caption problems and "not stated"

- **Caption gaps.** T5 has no caption from about 00:14 to 02:04 (JSON 9.8 s -> 124.6 s). Any setup in that span is missing. T3 has none from 00:07 to 00:40 (JSON 7.3 s -> 40.0 s).
- **Timing glitch.** T2 repeats timestamp [12:16] (JSON 736.7-736.9 s) in the cache section. Text is readable.
- **ASR errors.** T2 garbled "Mini Max H3 Mem E F Sage Attention Patch" [04:53-05:00]. T7 says "De-Rope" and "D-Read"; the creator says he does not know "D-Read" [06:48-06:52]. The D-RoPE name here comes from D7 and GUIDE.
- **Not stated in any source:** H3 base sampler and CFG (except D6 for Pika); Pika LoRA strength in T6 captions (D6 says 1.0); Easy Cache threshold (T1); Sol-Attention Start/End and Tau (T2); Block Cache threshold (T2); Motion Context context_length (T3); keyframe Crop mode (T3); mask grow values (T4); dial positive test value (T7); the full Ref2VA prompt text (T1 shows only fragments); which H3 keyframe node repo is used (D3 names only the Motion Context repo).
- **Not covered by any source:** cel-shaded or flat-colour style, realism drift measured with numbers, identity across several shots with numbers, Wan2GP-specific settings.
- **Excluded:** Pika's 4K upscaler is a paid cloud API (T6 [03:33-03:45]). RunningHub and Topaz appear in GUIDE and are paid. Licence not reviewed here; NOTES says verify before commercial use.
- **T4 risk:** Sage kernels may not run on Turing (GUIDE section d: "Sage targets Ampere and newer as far as known"). Untested on our T4.

## 6. Top 10 tips for our leap scene (LEAP-01..05)

1. **LEAP-01 (H3-REF).** Use the character's Ref2VA label exactly as the node prints it (T1 [07:52-08:09] uses "Picture-1"; T4 writes "Picture 1", so copy the node). One character per prompt.
2. **LEAP-01.** Give two references from the approved CHAR-KRISHNA sheets: a tight face crop and a full-body image. Reject any weak reference. Sources: T3 [09:27-09:39]; T4 [13:38-13:42].
3. **LEAP-01.** No cache node (Spectrum, Block, Easy). Sage stays off until an A/B on this shot passes. Log which attention node ran. Sources: T2 [09:32-09:37], [08:46-09:04], [14:34-14:41]; T1 [02:40-03:15].
4. **LEAP-01 (test before LEAP-02 to 05).** A/B the 6-step Pika LoRA against the 8-step file on one keyframe; the face-quality evidence conflicts (C7). Sources: T6 [00:34-00:41]; GUIDE 9 (5sC) [07:32-08:03]; NOTES src 2.
5. **LEAP-02, LEAP-03, LEAP-04.** Make all A and B keyframes in one Flow family, with B frames as edits of A (as DIRECTION already says). Source: T3 [02:46-03:17].
6. **LEAP-03.** Place keyframes by frame number with a frame-index keyframe node: crouch at frame 1, apex at a chosen frame of the 107. First confirm Wan2GP has an equivalent; if not, use A and B as start and end frames. Source: T3 [01:07-02:16].
7. **LEAP-03 (LEAP-04 only if the fall reads still).** Use the motion dial for launch power. Test 0, -0.50 and one positive value. Keep dial 0 on LEAP-01, LEAP-02 and LEAP-05. Sources: T7 [01:03-01:33]; D7 (-2.0 to +2.0).
8. **LEAP-03 and LEAP-04.** Use De-Rope only if the arc or the fall smears, and never on a shot with a readable face. It adds generation time. Sources: T7 [06:23-06:42]; GUIDE 11 (stRsg) [15:15-16:06] (secondary, C6).
9. **All shots, starting with LEAP-03.** VRAM recipe: chunks 2 and head_chunks 1; raise head_chunks on OOM; raise chunks to 4 only if the GPU sits near 100%. Source: T2 [14:12-14:34]. T6 [01:57-02:08] reports no visible quality change from chunk feed-forward.
10. **LEAP-03 to 04 (apex cut) and LEAP-04 to 05 (contact cut).** Use Cut (no carry-over) and silent H3 output (final audio None). Sound stays in post, as DIRECTION says. Test Guide only for the LEAP-02 to 03 crouch match. Sources: T5 [03:01-03:17], [03:32-03:43].
