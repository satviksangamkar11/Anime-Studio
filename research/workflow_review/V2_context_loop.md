# V2 - MiniMax H3 Context Loop: what it does and what we can use

Date: 2026-11-05. Analyst: video analyst V2. Read-only. This file is the only output. No web, no downloads, no workflow runs, no paid calls, no secret files opened.

Video: "MiniMax H3 Context Loop Explained: Generate Long Videos with Scene Continuity in ComfyUI", AiNinja94, uploaded 2026-09-13, 12:11 (video id eSDey7wAK60).

## 0. Inputs, gaps and caveats

- **Caption gap:** the transcript has no captions between [00:09] and [02:04]. Anything said in that window is unknown here. The description (eSDey7wAK60_description.txt) has no settings and only a summary of the stages.
- **Pack version:** ctxloop_readme.md describes pack 0.7.3 (README line 15). Both JSON files are older: the NEW file's nodes carry commit 2b4c7d3; the OLD file's nodes carry version 0.3.10 and legacy commit fa21821. The README therefore describes nodes that are newer than the JSON (see 2.5). License: GPL-3.0 (README line 266).
- **Widget names are not in the JSON.** ComfyUI stores widget values by position only. Names are given here only where the transcript or README states them. Other values are shown as positional and labelled "name not stored".
- **Node code is not on disk.** Behaviour comes from node titles, wiring, the video and the README. Anything else is marked MY INFERENCE.
- **Both JSON files are "Ref2V Basic" examples**, not T2V. NEW node 31 says so ("0.6 RELEASE - Ref2V Basic"); OLD node 1977 says "REF2V BASIC - QUICK START". NEW node 21 still uses the output prefix "t2v_normal" (a leftover name).
- The folder also holds JndCXtuU7-I_* files from another video. Not used.

Source keys: [mm:ss] = transcript timestamp. N<id> = NEW JSON node id. O<id> = OLD JSON node id. README L<n> = ctxloop_readme.md line. h3_director.py L<n>. W3 / W4 = workflow_review notes. DECISION, HANDOFF, DIRECTION = pipeline docs.

Scripted parse outputs (scratchpad): NEW_dump.txt, OLD_dump.txt, plan_summary.txt.

---

## 1. How Context Loop keeps continuity (plain English)

One scene is generated per loop. The next scene does not start from a picture. It starts from a **latent continuation state** left by the previous scene (picture and, optionally, sound). The model regenerates a short overlap at the start of the new scene, that overlap is decoded, and then the **Trim** node cuts it off. Each scene is saved and must be approved in a **Review** gate before the next one starts.

One loop, NEW wiring (node ids):

1. **Loop Start (N7)** starts or resumes the run at `start_clip` (widget 1). The value goes up when a scene is approved [08:03-08:20]. Scene range blank = all scenes (README L91).
2. **Current Scene (N8)** reads the state and outputs prompt, seed, length, width, height, steps (N8 slots 4-9 to N11, N10, N15) [05:47-05:58].
3. **Reference Conditioning (N11)** takes the two reference pictures (N26 -> ref_image_0, N27 -> ref_image_1) plus the prompt. The same two pictures are fed to every scene (OLD note O1958: "Both connected pictures remain active in every scene"; the NEW wiring is the same) [05:58-06:03].
4. **Apply Scene Context (N12)** is used from the second scene on [06:03-06:14]. It takes the state (N8 -> N12), the conditioning and the reference latent (N11), and the video VAE (N4). Outputs: conditioning -> BasicGuider N14; latent -> SamplerCustomAdvanced N16; `trim_frames` -> Trim N19. Audio VAE, model, drift_sigmas and lip_sync_voice inputs are not wired.
5. **Sampling:** BasicGuider N14 -> SamplerCustomAdvanced N16 (one scene per loop). The sigma schedule comes from BasicScheduler N15 [06:20-06:31].
6. **Decode:** VAEDecode N17 (video VAE N4) and VAEDecodeAudio N18 (audio VAE N5) [06:31-06:37].
7. **Trim Carried Overlap (N19)** removes the carried frames from images and audio. It also keeps an `images_with_overlap` output for the blend copy [07:22-07:32]. Outputs: images -> Save N20 and Loop End N23; audio -> Save and Review; images_with_overlap -> Save.
8. **Save Segment + Checkpoint (N20)** writes the scene, the checkpoint and metadata [07:42; 09:50-10:00; 11:02-11:18].
9. **Review Candidates (N28)** plays the scene. Options: approve and continue, retry with a new seed or prompt, reroll, approve and stop [07:42-08:03; README L84-85].
10. **Loop End (N23)** either advances to the next scene or emits the manifest for Assemble N21 [08:20-08:24].

**What is carried**

- **Picture (video):** a latent continuation of the end of the previous scene. The overlap is **22 frames** in the OLD plan (`context_length` 22; O2016 shots 1-4; O1977 note: "22 motion-context frames"). The NEW plan has no `context_length` value, so it is **not stated** for NEW. Overlap frames are decoded so they can be trimmed and, optionally, blended (images_with_overlap).
- **Sound:** the previous scene's **sampled audio latent**, when generated continuity is on [03:53-04:03]. OLD shots 1-4: `generated_continuity` "on". NEW: the "Generate audio" choice. MY INFERENCE: this travels inside the H3_CHAIN_STATE, because no wire carries audio latent into N12 (its audio_vae input is unwired).
- **Pictures (references):** the two references, every scene (step 3).
- **Prompt:** the NEW scene-2 text says to continue directly from the incoming H3 Motion Context and begin new action only after the carried overlap. The OLD shared prefix says each scene opens with the exact final state of the previous scene and about 2 seconds of small natural movement (O2016 prompt_prefix).
- **Not carried:** the scene noise is fixed per scene (RandomNoise N10 / O1966, control "fixed"; the scene seed comes from N8). MY INFERENCE: no decoded pixels are passed on, only latents and the overlap they regenerate.

**How many frames**

- H3 renders 107 + 17k frames at 24 fps, max 362 (h3_director.py L33-34). 362 frames = 15.08 s. The video's "15-second clip" [02:31] is that maximum.
- Files: NEW shots 243 frames (10.125 s) x 2 (both legal: 107 + 17 x 8). OLD active plan: 294 (12.25 s) + 7 x 362 = 2828 frames = 117.83 s.
- Overlap carried: 22 frames (OLD). The trim value is computed at run time from N12 output 1 (`trim_frames`): not stated. MY INFERENCE: it equals the overlap, so 22 in OLD.
- Crossfade: 12 frames = half a second at 24 fps [10:17-10:22]. OLD active plan: `video_blend_frames` 12 on shots 1-4. NEW: not set (blend_segments empty with defaults [10:05-10:11]).

**Overlap removal (de-duplication at the join)**

- Trim N19 removes the carried overlap at the start of each scene after scene 1 [07:22-07:27]. The position is taken from the NEW prompt wording ("the carried opening overlap ... begin new action only after it"). MY INFERENCE: it is removed from the front of the decoded scene.
- The saved copy for blending keeps a 12-frame cushion at the start of each scene from scene 2 on [10:29-10:40]. Final assembly uses that cushion to dissolve.
- Scene 1 has no overlap and no Context node [06:14].

---

## 2. Settings

### 2.1 NEW - MiniMax-H3-Context-Loop-NEW.json (32 nodes, 9 groups, 54 links)

Groups: 01 PROJECT & SCENES; 02 MODELS & INPUTS; 03 PREPARE SCENE; 04 PREPARE SCENE (group 03 and group 04 share the title); 05 SAMPLE & DECODE; 06 SAVE & REVIEW; 07 REVIEW & CONTINUE; 08 DELIVER; RECOVERY - DISABLED / NO SAMPLING. Muted: N9 and N25 (recovery). All others active.

| Setting | Value | Node | Note / source |
|---|---|---|---|
| Diffusion model | `minimax_h3_ref2va_pruned_int8_convrot.safetensors`, weight `default` | N1 | Same family as our Wan2GP preset `minimax_h3_ref2va_pruned` (h3_director.py L40-41). |
| Text encoder | `qwen3vl_32b_minimax_h3_int8_convrot.safetensors`, type `minimax`, `default` | N2 | int8 build. |
| Video VAE | `minimax_h3_video_vae_fp16.safetensors` | N4 | Same as OLD. |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` | N5 | Same as OLD. |
| LoRA | none | - | No Pika adapter in this file. |
| Attention | `pytorch attention` (ModelAttentionBackend, active) | N22 | No Sage patch. |
| Sigma shift | 12 and 3 (second name not stored) | N13 | MY INFERENCE: 3 = audio shift (W3 line 45: Wan2GP uses shift 3.0 for audio). |
| Sampler | `res_multistep` | N3 | |
| Scheduler | `simple`, steps 20 (wired from Current Scene output 7), denoise 1 | N15 | Steps are live (link 23). |
| Guider | BasicGuider, no CFG widget | N14 | |
| Noise | RandomNoise, seed from Current Scene, control `fixed` | N10 | Widget 0 unused. |
| Chain policy | Generation Profile: `Visual continuity`, `Generate audio` | N30 | Two controls only (README L160). |
| Plan | Production Plan (MiniMaxH3ChainPlanModern), defaults `steps` 20 | N24 | README calls this "Plan (Modern)" (L161). |
| Shared prompt | none saved in this plan | N24 | OLD has one (O2016 prompt_prefix). |
| Shots | 2: `reference_delivery` 243 frames, seed "6101"; `reference_confirmation` 243 frames, seed "6102"; steps 20 each | N24 | Total 486 frames = 20.25 s. |
| Resolution | 896 x 672 (plan widgets; 4:3; 0.60 MP) | N24 -> N8 -> N11 | Multiples of 32. Not 9:16. |
| Ref image size mode | `match` (name not stored) | N11 | Our DECISION uses `ref_image_size` match. |
| Context length | not stated | N12 | No widget values. |
| Blend (video_blend_frames) | 0 by default | N24 output unwired; N19 | Transcript [10:05-10:11]. |
| Trim | `[0, 24, true, 0]` (names not stored); trim count from N12 | N19 | 24 = fps (MY INFERENCE). |
| Loop start | `[1, "", true]` | N7 | start_clip 1 [11:18-11:32]; scene range blank (README L91). Third value not stated. |
| Preflight | `[1, "", true]` | N29 | Checks before models load (README L83). |
| Loop End | `["off", "recursive_legacy"]` | N23 | Top-level requeue off; recursive execution (README L43-47). |
| Current Scene | `[false]` (name not stored) | N8 | |
| Review gate | `[true, false, 0, false, true, "checkpointed", 1, false]` (names not stored) | N28 | Options from README L84-85. |
| Assemble | `["plan", "t2v_normal_%date:yyyy-MM-dd%", 256, false, "", "plan", "off", "off"]` (names not stored) | N21 | Prefix name is a leftover. |
| Recovery assemble | `t2v_normal_recovered_%date%`, muted | N9 | Muted, as documented. |
| Load saved clips | muted | N25 | Takes plan from N6. |
| References | `h3_v06_courier_greenhouse_arrival.png` (N26), `h3_v06_courier_greenhouse_delivery.png` (N27) | N26, N27 | Both used in every scene. |
| Prompt format | six sections: subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music | N24 | Same six-section format as h3_director.py `prompt_for` (L227-229). |

Prompt caution: the NEW reference-scene text uses the words "photographic rendering". DECISION says no photoreal wording for our cel style. Do not copy it.

### 2.2 OLD - MiniMax-H3-Context-Loop.json (48 nodes, 5 groups, 66 links)

Groups: H3 MODEL STACK; CORE REF2VA + CHECKPOINTED REVIEW; DISABLED RECOVERY PATH; GLOBAL PICTURE REFERENCES - ALL SCENES; WORKFLOW GUIDE. Bypassed: O1987 (ModelAttentionBackend, "comfy kitchen attention") and O2000 (test plan). Recovery nodes O1964 and O1978 are saved **ACTIVE** (see 2.5).

| Setting | Value | Node | Note / source |
|---|---|---|---|
| Diffusion model | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | O1989 | Same as NEW. |
| Text encoder | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, `minimax` | O1982 | NVFP4 build. MY INFERENCE: NVFP4 needs Blackwell-class GPUs, so it probably does not load on our Kaggle T4. Verify before use. |
| Video / audio VAE | `minimax_h3_video_vae_fp16`, `minimax_h3_audio_vae_fp32` | O1983, O1984 | Same as NEW. |
| LoRA | `minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy.safetensors` at 0.8 (LoraLoaderModelOnly) | O1985 | Turbo 4-step adapter, named fl2v, on a ref2va model. W3 line 41 says Wan2GP's own Ref2VA phase 2 also reads the FL2V turbo key, so this may be deliberate. Not verified. |
| Attention | PathchSageAttentionKJ `auto`, false (O1990) -> MiniMaxH3MemoryEfficientSageAttentionPatch (O1986) | O1990, O1986 | Sage patches from kjnodes. Our DECISION says Sage is not needed for T0. |
| Sigma shift | 12 and 3 | O1981 | Same as NEW. |
| Sampler | `euler` | O1992 | Its own note says res_multistep (O1977). |
| Scheduler | `simple`, **6** (widget); steps input **unwired** | O1988 | The plan's 20 steps do not reach the sampler (wiring). |
| Guider | BasicGuider | O1970 | |
| Noise | RandomNoise, control `fixed` | O1966 | |
| Chain policy | Manual Chain Policy (Legacy): `guide`, `generated`, `off`, `on`, false | O1994 | Names not stored. MY INFERENCE from the video's control order [03:01-04:18]: transition Guide, final audio Generated, source reference off, generated continuity on, lock source audio false. Per-shot keys agree (below). |
| Plan | Plan node (MiniMaxH3ChainPlan), active: O2016. Test copy O2000 bypassed. | O2016 | Scene Prompt Editor O1993 reads O2016. |
| Shared prompt | `prompt_prefix`: 13 entries (style, two character-sheet references, continuity rule, speaker IDs) | O2016 | Style line says cel shading and clean line art. |
| Shots (active) | 8: 1 x 294 frames (12.25 s) + 7 x 362 frames (15.08 s); steps 20 per shot; total 2828 frames (117.83 s) | O2016 | Seeds vary; one seed (414030390311599855) is reused on shots 2, 3, 4, 6 and 7. |
| Per-shot continuity keys | shots 1-4: `continuation_mode` "guide", `context_length` 22, `audio_context_length` 22, `source_reference` "off", `generated_continuity` "on", `video_blend_frames` 12; shots 2-4 also `visual_context_source` (the previous shot id) | O2016 | Shots 5-8 have only length, steps and seed. MY INFERENCE: they inherit plan-level values (plan widget "22" and "guide"). |
| Resolution | 736 x 416 (plan widgets; 0.31 MP; 16:9-like) | O2016 | Reference node O1991 has 896 x 672 in its own widgets, but links overwrite them at run time (links 194-196). |
| Plan text values (positional) | `ref2v_basic_T1`, `ref2v-jigen-global-v1`, 22, `video`, `head`, `disabled`, `generated_audio`, 22, 10, 20, 0, 20, 0, `guide` | O2016 | Names not stored. MY INFERENCE: run name, project id, context 22, encode `video`, anchor `head` (same words as W4 f5, from a different video), audio `generated_audio`, plan-level continuation `guide`. |
| Trim | `[0, 24, true, 0]` | O1974 | Same as NEW. |
| Loop start | `[1, "", true]` | O1995 | Same as NEW. |
| Preflight | `[1, "", true]` | O1980 | Same as NEW. |
| Loop End | `["off", "recursive_legacy"]` | O1976 | Same as NEW. |
| Review gate | `[true, false, 0, false, true, "checkpointed", 1, false]` | O1996 | Same as NEW. |
| Assemble (final) | `["plan", "t2v_normal_%date:yyyy-MM-dd%", 256, false, "", "plan", "off", "off"]` | O1997 | Active. |
| Assemble (recovery) | `t2v_normal_recovered_%date%` | O1964 | **Saved ACTIVE** (see 2.5). |
| Load all saved clips (recovery) | | O1978 | **Saved ACTIVE** (see 2.5). |
| References | `Young Courier.png` (O1998 -> ref_image_0), `The Clockmaker.png` (O1999 -> ref_image_1) | O1998, O1999 | Both in every scene. |

### 2.3 Chain policy values and review options (from the video and README)

| Control | Options | Source |
|---|---|---|
| Incoming transition | Cut (fresh start, no carry); Guide (short visual handoff, default, recommended); Hard AV (picture and audio locked more firmly); Soft AV (picture locked, audio blends out) | [02:45-03:28] |
| Final audio | Generated (H3 voices, ambience, music); Source (original soundtrack); None (silent) | [03:32-03:43] |
| Source reference | On / Off: existing audio inspires style without copying | [03:49-03:53] |
| Generated continuity | Carry the previous scene's sampled audio latent | [03:53-04:03] |
| Lock source audio | Keep exact original audio; overrides generated continuity | [04:03-04:18] |
| Lip-sync voice | Option exists; lip-sync not tested by the author | [04:35-04:42] |
| NEW Generation Profile | Two controls: Visual continuity, Generate audio. The other options are in the audio/continuity docs, which are not in our files | N30; README L160, L82 |
| Review gate | Approve & continue; Retry (new seed or prompt); Reroll seed; Approve & stop | [07:42-08:03]; README L84-85 |
| Crossfade (blend) | 12 frames suggested for a half-second dissolve; 0 for hard cuts (blend folder empty) | [10:05-10:22] |

### 2.4 Which workflow is newer and better, and why

**NEW is the newer file.**

- The author says the developer updated the workflows and the "logic remains the same, but the naming convention has been improved" [04:18-04:30].
- OLD nodes are titled "(Legacy)" (O1994) and the plan node is the older MiniMaxH3ChainPlan. NEW uses the Generation Profile and Production Plan (Modern) nodes, which the README lists as current (L160-161).
- NEW is internally consistent: its steps reach the scheduler, its recovery nodes are muted as documented, and its only sampling path is the plain one.
- OLD has at least four internal conflicts (2.5).

**For generation quality (our goal), NEW is the better reference.** It has no turbo LoRA, no Sage patch, a standard sampler (res_multistep) and 20 steps. OLD is a speed build (6-step scheduler, turbo LoRA, Sage). MY INFERENCE: NEW is the quality baseline, but no source measures quality. T0 has to measure it.

**Our pipeline already uses the NEW design choices:** sigma shift 12, the same two VAEs, the same UNET family, and the six-section Ref2VA prompt. We differ on sampler (Pika needs pika_renoise and 6 steps; check_combo in h3_director.py L237-257 refuses anything else), LoRA (one Pika adapter), and audio (ours is in post).

**The pack itself (README 0.7.3) is newer than both files.** It adds Chapter Delivery (L168-170), Pending Review, Plan Studio, Project Asset Carousel, a per-scene dialogue source (L176-196), tagged references (L122-124, L250), and deferred upscale (L120). None of those are in either JSON.

### 2.5 Conflicts inside the files and the video

1. **OLD recovery nodes are saved ACTIVE** (O1964 Assemble, O1978 Load Manifest), but the note O1979 says they are "MUTED by default". If they run as output nodes, they execute with every queue. Check the OLD file in the UI before queueing it. (MY INFERENCE on execution behaviour.)
2. **OLD steps are not wired.** The scheduler (O1988) has steps 6 as a widget, and its steps input has no link. Current Scene O1963's steps output is unconnected. The plan's 20 steps do not reach the sampler. Note O1977 says "20-step sampling with res_multistep", but the sampler is `euler` (O1992).
3. **OLD note O1957 says "two-scene" demonstration.** The active plan O2016 has 8 shots.
4. **Recovery instructions disagree.** Video: "bypass the entire loop" [11:57-12:03] and "disable the output node" [11:41]. README L146-150: unmute the recovery pair and queue its Assemble; no sampler graph needs to run. OLD note O1979: mute the main Assemble, enable both recovery nodes, queue (and it validates SHA-256 checkpoint pairs). Use the README method for the current pack.
5. **NEW prompt contains "photographic rendering"** (see 2.1).
6. **Plan and pack versions.** NEW is pack commit 2b4c7d3; OLD is 0.3.10 with a legacy node. The pack README is 0.7.3. Expect node names and widget order to differ if we ever open these in a newer ComfyUI.

---

## 3. How the long video is assembled, and recovery and resume

**Assembly (normal run)**

1. After the last scene is approved, Loop End N23 emits the manifest (`H3_CHAIN_MANIFEST`) to Assemble N21 [08:20-08:29].
2. Assemble N21 builds the final MP4 from the accepted scenes and returns `video_path` (N21 output has no link). README L86: "The active Assemble node writes the final MP4 after the last scene."
3. Overlaps are removed by Trim per scene (section 1). Dissolves use the blend folder: the copy from scene 2 on has a 12-frame cushion [10:29-10:40]. Optional blend VAE N21 input (unwired) decodes extra frames from the checkpoint for a longer crossfade than was saved [10:44-10:55].
4. Output folder: `ComfyUI/output/h3_chains/<run_name>/` (README L218-219). The run name names the folder [10:00-10:05]. Inside: Segments (each accepted scene), Checkpoint (latent continuation state plus file paths, prompts, seeds, timing), blend_segments [09:50-11:18].

**Resume**

- Start-clip (N7/O1995) = first clip to generate. It goes up on each approval. Resume works after a restart [08:03-08:20].
- The run name is the identity of the run. Keep it to resume; use a new name for a new production (README L214-215). Preflight rejects resume state made with different generation inputs (README L216-217).
- To extend a finished run, add scenes before approving the last one (README L89-92).
- Regenerate one scene: load the checkpoint before it, optionally delete later scenes, and re-run. Later scenes are then based on the new scene [09:25-09:50].

**Recovery (assemble without re-rendering)**

- Use it if every segment is done but the final assembly failed [11:46-11:54].
- Nodes: N25 "Load Saved Clips" (takes the plan from N6, outputs the manifest from saved files) -> N9 "Assemble Final Video" (recovery prefix). Both muted in NEW.
- Steps: keep the plan's run name; disable the main Assemble path; enable the recovery pair; queue (README L146-150; O1979). Each checkpoint pair is checked against its SHA-256 (O1979).
- For an interrupted render (not a finished one): leave recovery muted; set start-clip to the first unfinished scene (O1979).

**Latent upscale.** Not in either JSON. README L120 and L142-148 point to deferred upscale and DeRoPE/upscale example workflows that are not in our files. Not stated.

**External context.** Loop Start N7 and Preflight N29 both have an `external_context` input (type H3_CHAIN_EXTERNAL_CONTEXT). Nothing is wired and the purpose is not documented in our files. Loop End N23 outputs `last_context_frames` and `last_context_latent` (unwired). Names only.

---

## 4. Which parts we can reproduce in Wan2GP + director + ffmpeg (no ComfyUI)

| Part | Reproducible? | How in our pipeline | Limit |
|---|---|---|---|
| One settings file per shot, run in order | YES (already) | h3_director.py `main()` L313-325; run_kaggle.py kernel loop L60-66 (one `wgp.py --process` per shot, in order) | None. |
| Per-scene checkpoint | YES, approximately | Per-shot folder: settings JSON, mp4, last frame PNG (clip_tools.py `last_frame`, L41-44), qa JSON (`qa`, L29-38), plus a manifest (to add) | No latent resume. Resume uses the saved PNG (lossy, one frame). |
| Last frame of shot N as start keyframe of shot N+1 | YES (keyframe, not latent) | h3_director.py `start_of` L141-142 and the start-frame line `ALIGN` L50 (Picture 1 at 0.00 s) | One frame carries pose and look, not motion or velocity. Expect a visible jump on moving shots. |
| Carry ~22 motion frames as latent | NO | ComfyUI state (H3_CHAIN_STATE). W3 lists sliding windows (inside one generation: Wan2GP window 124-481, overlap 1-120, default 18; W3 line 51) and no cross-clip latent carry. | Not available to our director. |
| Wan2GP reference video as previous-clip context | UNTESTED | Wan2GP Ref2VA has "Use One Reference Video" (V-U), up to 3 videos, each at least 2 s, max 362 frames, max size 768x1344 (minimax_h3_handler.py L855-885; W3 line 54). | Exact settings key not yet read. Memory cost and identity risk on T4. |
| Trim of carried overlap (de-duplication) | YES (concept) | `edit_frames` (h3_director.py L122-133) plus ffmpeg. Chain joins drop 0-1 frame at the head. | `edit_frames` does not say which end is kept (see action 3). Post not built (HANDOFF "Not done" 3). |
| Crossfade (12 frames) | YES, in post only | ffmpeg xfade in post.py (to build). Not H3's blend. | Only where DIRECTION asks for a dissolve (none in LEAP). |
| Blend VAE (extra frames from a checkpoint) | NOT NEEDED | Keep full renders (`render_frames`) so the cut point can move without re-rendering. | Renders are 107+ frames; storage. |
| Audio carry (sampled audio latent) | NO | ComfyUI state. Not needed: our sound is in post (DECISION, Audio row; DIRECTION Sound). | None if H3 audio is dropped. |
| Lip-sync / dialogue per scene | NO for now | Untested by the author [04:42]. | Dialogue in post. |
| Review gate that blocks the loop | PARTLY | Owner gate between chained shots: `run_kaggle --fetch` (L145-150), `clip_tools qa`, owner OK, then the next chained shot. visual_qa.py (nine criteria, accept at 14) as triage only. | Not in-loop; batch runs. Owner time. |
| Regenerate one scene | YES | `run_kaggle --ids SHOT-NN` (L122-123) with a new seed. Shots that chain from it must re-run. | Cascade cost. |
| Recovery assemble from manifest | YES | post.py assemble mode reading the manifest (to build). | post.py not yet written. |
| Latent upscale / two-phase / SelfLift | NO with Pika | W3 line 104 and DECISION: Wan2GP two-phase cannot be combined with Pika. | ComfyUI-only otherwise. |
| DeRoPE | NO | W3 line 116: not found in Wan2GP code. | |
| Attention backends (Sage, sol) | NOT NOW | DECISION: sol fails below SM 8.6 (T4 and A100); Sage needs an extra package. | Revisit only if VRAM forces it. |
| Shared style prefix and KEEP line | YES (already) | h3_director.py `body_for` L158-166 (style, world, KEEP). | None. |

---

## 5. Which parts suit our film

Our leap (DIRECTION.md): 5 hard-cut shots, LEAP-01 (0.0-3.0 s) to LEAP-05 (13.0-16.0 s). Each has approved Flow keyframes: A is the start, B is the end. Each H3 render is 107 frames (4.46 s), trimmed to the edit.

**Leap: use keyframes and cuts, no chaining across shots.**

- The cut rules are fixed: LEAP-02 to 03 is a match on the crouch; 03 to 04 cuts on the apex; 04 to 05 cuts on contact; a 2-frame impact flash and 0.5 s of silence at 13.0 s (DIRECTION lines 23-25).
- Carrying the previous shot would carry its pose, its water plate (ENV-KALIYA-DAH-POISONED, candidate B approved, DIRECTION line 6) and its bansuri state. The bansuri rule is per scene: in the sash unless the shot says otherwise (DIRECTION line 7). A carried frame could break that.
- Identity: the keyframes are approved art. Chaining passes a generated frame forward, and drift compounds from hop to hop.
- LEAP-03 (4.0 s) fits one generation: render 107, edit 96 frames. The crouch-to-launch-to-arc action happens inside one shot, so no chaining is needed. The crouch start (03A) already matches the end pose of 02.
- Edit lengths: 3.0 s shots = 72 frames kept of 107; 4.0 s = 96 kept of 107 (24 fps).

**Where chaining helps (other scenes, if any run longer than one window or need one continuous take):**

- A continuous take longer than about 4.5 s with no framing change: chain with the last frame. Hide the join on an action or a hold.
- Continuous cloth or hair motion that must not reset: a frame-chain resets velocity. Add a 0.5-1.0 s hold or settle at the join (MY INFERENCE; test at T0-chain).
- Recovery of a bad scene: regenerate it from its start keyframe, then re-chain the shots after it.

**Where cuts are better:**

- Any location or time change, any framing change (wide to close), any identity-critical close-up, any water or prop state change, and any shot where a prop must be reset.
- Hard cuts are the default. Use Cut for all LEAP joins.

**Note on the OLD sample:** its prompts script several cuts inside one 15-second generation ("[Shot 2] At 00:04.000, the shot cuts to ..."). H3 can render in-clip cuts from prompt text. We should not rely on that for the leap: we control each frame with keyframes, and in-clip cuts in one take are untested (MY INFERENCE).

---

## 6. Table: ASPECT | what it does | can we use it | where it plugs into our pipeline | risk

Plug points: `h3_director.py` (director), `run_kaggle.py` (Kaggle/Colab runner; `build()`, kernel loop L60-66, `finish()` L53-58), `clip_tools.py` (QA and last frame), `visual_qa.py` (triage), `post.py` (not yet built), `check_pack.py` and `dry_run.py` (counts and edit JSON).

| ASPECT | What it does | Use? | Where it plugs in | Risk |
|---|---|---|---|---|
| Chain policy: Cut | New scene, no carry | YES | Director default; the leap's 5 cuts | None. |
| Chain policy: Guide | Carries ~22 motion frames as latent | ADAPT: last frame as start keyframe | Director `start_of` takes `chain_from`; runner writes PNG before the shot runs (clip_tools `last_frame`) | Pose-only carry; velocity resets; identity drift per hop. |
| Hard AV / Soft AV | Audio locked to picture at the join | NO | Post | None if H3 audio is dropped. |
| Final audio: Generated / Source / None | Audio at export | NO | post.py: map our audio, `-an` on H3 clips | H3 audio leaking into the cut. clip_tools qa reports loudness; add a check. |
| Generated continuity (audio latent carry) | Audio continuity across joins | NO | Not needed | None. |
| Source reference | Existing audio as style reference | NO | Not needed | None. |
| Generation Profile (two controls) | Continuity and audio choice | ADAPT: one field `join` (cut or chain) | shot schema (`shot_schema.py` for rich shots) and h3_director | Low. |
| Shared prompt prefix | Prepended to each scene | YES (already) | h3_director `body_for` (style, world, KEEP) | "Photographic" wording creeps in from examples. |
| Plan defaults and per-shot length, steps, seed | Per-scene length, steps, seed | YES (already) | Shot JSON and `settings_for` | None. |
| Preflight | Timing, media, resume checks | YES, extend | `settings_for`, `check_combo`, `check_unique_ids` exist; add chain-source-exists and size checks | Low. |
| Current Scene (prompt, seed, length, size) | Drives one scene | YES (already) | One settings file per shot | None. |
| Two references, every scene | Identity pictures | YES (already) | h3_director refs and subjects; Picture numbering | Keep refs per shot. |
| Apply Scene Context (latent overlap, 22 frames) | The core carry | NO | ComfyUI state only | Losing this is the main gap. Replace with keyframes (leap) and last-frame chaining (other shots). |
| Sampler, scheduler, steps (res_multistep, simple, 20) | Sampling | NO for sampler and steps; yes for shift 12 | h3_director constants. Pika needs pika_renoise and 6 steps. | check_combo refuses a 20-step plan under Pika (h3_director L254-255). |
| Sigma shift 12 (and 3) | Schedule shape | YES (12 already) | h3_director `flow_shift` 12 | None. |
| LoRA stack (LightX2V fl2v turbo, 0.8) | Speed | NO | We use one Pika adapter (h3_director PRESET L39-42) | Stacking breaks output (DECISION). |
| Attention backends (Sage, pytorch) | Speed and memory | NOT NOW | Wan2GP setting | Sol fails on T4; Sage needs a package (DECISION). |
| Trim carried overlap (de-duplication) | Removes overlap at joins | ADAPT | `edit_frames` plus ffmpeg in post.py. Chain joins: drop 0-1 frame. | Which end is kept is undefined today (see action 3); a duplicate frame at the join if not dropped. |
| Crossfade (12 frames, blend copy) | Dissolve at joins | ADAPT, off by default | post.py ffmpeg xfade | Dissolve look untested; none in the leap. |
| Save Segment + Checkpoint | Per-scene take plus resume state | ADAPT | Per-shot folder: settings, mp4, last PNG, qa JSON (`run_kaggle` results, `clip_tools` qa and last). Add manifest. | No latent resume. |
| Review gate (approve, retry, reroll, stop) | Human stop per scene | ADAPT as owner gate between chained shots | `run_kaggle --fetch` then `clip_tools qa` then owner; visual_qa as triage | Owner time; visual_qa is not a substitute for owner review (HANDOFF rule). |
| Loop Start start-clip (resume) | Resume at scene N | ADAPT | `run_kaggle --ids` from the first unfinished shot, with its saved last-frame PNG | Chain order must be kept; a changed setting must invalidate a resume (manifest hash). |
| Loop End manifest (plus last-context outputs) | Accepted-scene list; last frame and latent | ADAPT | `manifest.json` written in `run_kaggle.finish()`; last frame via `clip_tools.last_frame` | None. |
| Final assembly (concat with blend) | MP4 from accepted scenes | YES | post.py ffmpeg concat in manifest order (not yet built) | Mixed sizes or codecs; keep 768x1344 for all shots. |
| Recovery (assemble from saved files, SHA-256 pairs) | Rebuild without rendering | YES | post.py assemble mode plus a SHA-256 in the manifest | Conflicting instructions in the video and README (only one is needed). |
| Regenerate one scene | Redo a scene, then later ones | YES | `run_kaggle --ids` plus new seed | Cascade cost on chained shots. |
| Reference video (Wan2GP V-U) | Previous clip as in-context reference | TEST ONLY | h3_director ref2va branch (new field); exact key from handler L855-885 | Untested; memory on T4; identity drift. |
| Sliding windows (Wan2GP) | One long take in windows | NO for 3-5 s shots | h3_director `frames_for` refuses >362 already | None. |
| Latent upscale, SelfLift, deferred upscale | Higher-resolution pass | NO | Not in these JSON; Wan2GP two-phase cannot combine with Pika | None now. |
| Lip-sync voice; dialogue source per scene | Voice to picture | NO | Not tested | None. |
| Tagged references; reference schedule | Per-scene reference sets | NO for now | Sockets unwired; docs not in our files | None. |
| External context socket | Unknown purpose | NO | ComfyUI only | Unknown. |
| Licence: pack GPL-3.0 (README L266) | Code license | RISK | Do not copy code; reimplement the ideas | GPL terms if code is copied. |
| Licence: H3 model exclusions (HANDOFF) | Model use | RISK | Applies to all H3 output, not only this workflow | Owner is handling it (HANDOFF). |

---

## 7. Top 10 actions, ranked (describe only, nothing edited)

1. **Keep the leap as five keyframe-driven hard cuts. Do not chain across any LEAP join.** No code. Write it into DIRECTION or the director notes so nobody chains 02 to 03 or 04 to 05 by habit. Reason: section 5.

2. **After the owner's go for T0, run one join test (T0-chain).** Take the T0 winner for LEAP-03, extract its last frame (`clip_tools.py last`), and render one 107-frame shot from it as the start keyframe. Measure: pixel difference between frame 0 of the new shot and the last frame of the old one (decides whether to drop 0 or 1 frame); face match to the sheet; motion jump at the join; colour drift. No code change. Decides whether chaining is usable at all.

3. **Define the meaning of `edit_frames` (small director change).** `h3_director.py` `frames_for_shot` (L122-133) validates `edit_frames` but nothing says which end is kept. Add `edit_start` (frames dropped from the head) and keep `edit_frames` as the kept count, with the check `edit_start + edit_frames <= render_frames`. Update `check_pack.py` (L24) and `dry_run.py` (L24) to use it. Tests: `test_preflight.py` L33-38 and `test_review2.py` L152-164 are the templates. Needed before post.py.

4. **Add a `join` field to each shot: `cut` (default) or `chain` (small director change).** In `h3_director.py`: `start_of()` (L141-142) returns the placeholder `<chain_from>_last.png` when `join` is `chain` and no `start` is given, so `settings_for` builds the same FL2VA settings (L290-306). Validate in `shot_schema.py` for rich shots. Do not copy the Context Loop wording "carried overlap" into our prompts; the existing ALIGN line (L50) already says Picture 1 is the 0.00 s start frame.

5. **Make `run_kaggle` extract the chained start frame at run time (runner change).** `build()` embeds every image up front (`__IMAGES__`, L52; docstring L5), so chain shots must be skipped at build time. In the kernel loop (L60-66), after a shot returns "ok", run `clip_tools.last_frame` on its mp4 into the inputs folder as `<id>_last.png`, then rewrite the next chain shot's `image_start` before its `wgp.py` call. Keep shots sequential. Check that ffmpeg is present in the Kaggle image before relying on it (MY INFERENCE: it is not verified).

6. **Write a `manifest.json` per run and save per-shot artefacts for resume.** In `run_kaggle.finish()` (L53-58), record: shot id, join type, settings SHA-256, mp4 path and SHA-256, last-frame PNG, `edit_start`, `edit_frames`, seconds per shot, and peak VRAM if `nvidia-smi` is logged. Resume is then `--ids` from the first unfinished shot (flag exists, L122-123), using the saved last-frame PNG. Covers the T0 measurement list (time, units, VRAM) for free.

7. **Build post.py (not yet written; HANDOFF "Not done" 3).** ffmpeg concat in manifest order, applying each shot's `edit_start` and `edit_frames`. Map our audio explicitly and drop H3 audio (`-an` on the H3 clips). No crossfade by default. Add an assemble-only mode that reads the manifest (this is our recovery path). Needed before the first 16 s film.

8. **Keep the owner gate between chained shots.** Process: `run_kaggle --fetch` (L145-150), then `clip_tools qa` (sheet, duration, loudness), then owner OK, then the next chained shot is rendered. Use visual_qa (nine criteria, accept at 14, L34-64) only as a triage score. Owner approval stays the decision (HANDOFF rule).

9. **Record the NEW workflow's settings as the quality reference, but do not adopt them.** Keep these in notes: res_multistep, 20 steps, no LoRA, pytorch attention, shift 12 (and 3). Do not copy the 20-step sampler or the turbo LoRA into the Pika path; check_combo refuses them (h3_director L237-257). Do not adopt the OLD NVFP4 text encoder on T4 until its loading is checked (MY INFERENCE).

10. **Test Wan2GP reference-video guidance only if action 2 fails on a continuous shot.** First read the exact settings key and the video-guide letters from `minimax_h3_handler.py` L855-885 and `wgp.py` (W3 line 54 gives the limits). Then add an optional `reference_videos` field to the ref2va branch of the director. One test shot, owner go first.

---

## 8. What I did not verify

- No node code was read. Widget names and behaviour are from wiring, the video and the README.
- Whether the first frame of an H3 FL2VA render equals the start image (action 2 measures it).
- Whether the NVFP4 encoder loads on a T4 (inference from the Blackwell requirement; not checked).
- The exact Wan2GP settings key for reference videos (action 10).
- Captions 00:14-02:04 are missing; claims about that window are not included.
- No timing transfers to our hardware: the video's 200 s per 15 s clip is on an RTX 5060 Ti with 736x416 or 896x672 frames. Our frames are 768x1344. T0 measures ours.
