# Blender camera and motion for H3 / Wan2GP, plus news (research as of 2026-11-05)

Status labels: VERIFIED = read in a primary source during this research. UNVERIFIED = stated by a secondary source or not checked; do not build on it without a test.

## 0. Ground truth checks
- The Wan2GP repo now lives at https://github.com/deepbeepmeep/WanGP (the old name redirects). Newest commit: **bd1ff59, Nov 4, 2026, "showrunner, taomate face refiner"** (VERIFIED: https://github.com/deepbeepmeep/WanGP/commits/main). No commits newer than bd1ff59 were visible at check time.
- The docs/CHANGELOG.md file stops at **26 Aug 2026** (v12.643), so it is not maintained. Use the README and commit list for recent changes (VERIFIED: https://github.com/deepbeepmeep/WanGP/blob/main/docs/CHANGELOG.md).
- H3 ControlNet-Union 2.0 (pose, depth, edge, shape, recolour controls on FL2VA 33B and pruned 20B) is in the README under **29 Sep 2026, WanGP v13.141** (VERIFIED: https://github.com/deepbeepmeep/WanGP/blob/main/README.md). It is therefore not new in bd1ff59; it dates from late September.
- MiniMax H3 licence, read from the primary file (VERIFIED: https://huggingface.co/MiniMaxAI/MiniMax-H3/raw/main/LICENSE, dated Aug 2, 2026):
  - Commercial use above US$20M yearly revenue needs written authorisation (api@minimax.io). Section IV.1.
  - "MiniMax H3" must appear prominently in a commercial UI. Section IV.2.
  - **The Applicable Territory is worldwide EXCEPT the EU, UK, Republic of Korea and US.** Use of the works *and their Outputs* outside that territory is not authorised. Sections I.5, V.4; Exhibit A.
  - Outputs may not be used to improve other AI models, and "Model Derivatives" (including distilled or synthetic-data models) are covered. Section V.3.
  - **Legal read needed before any global YouTube release.** This is a flag, not legal advice.

## 1. Camera control methods (Section 1 of checklist)

| Name | What it does | Works with H3 / Wan 2.2? | T4-feasible? | Licence | Link | Date |
|---|---|---|---|---|---|---|
| H3 camera-movement LoRAs (community, e.g. "Yunjing", 360-orbit, third-person) | Text-free camera moves learned by a LoRA | Yes, H3 (FL2VA / Ref2VA variants must match the LoRA) | UNVERIFIED on T4; the LoRA sits on the H3 base, so the same memory limits apply | Not stated on sources checked | https://x.com/SD_Tutorial/status/2089389656689570115 ; https://huggingface.co/pablodawson/MiniMax-H3-360-Orbit-LoRA | Aug to Oct 2026 (secondary sources) |
| Wan2GP "Fun Control-Camera 1.3B" and "Uni3C 14B" | Start image + camera path | **Wan 2.1 base, not H3 or Wan 2.2.** Listed as WanGP v18.00 | UNVERIFIED on T4 (Uni3C reports 46-54 GB per GPU on H20s) | Uni3C code Apache-2.0; ReCamMaster MIT | https://github.com/deepbeepmeep/WanGP/blob/main/README.md (heading 11 Oct 2026); https://github.com/alibaba-damo-academy/Uni3C | Oct 11, 2026 (WanGP), Uni3C latest code news Aug 2025 |
| Wan2.2-Fun-14B Control-Camera (Alibaba PAI) | Camera lens control on Wan 2.2 I2V-style model | Wan 2.2 (Fun family), not H3 | Model is about 64 GB of weights; T4 UNVERIFIED | Apache-2.0 for the Fun family (inferred; the Control-Camera card was not read) | https://huggingface.co/alibaba-pai/Wan2.2-Fun-A14B-Control-Camera | Last PAI update seen Dec 11, 2025 |
| SCoPE (Tencent ARC) | Camera-ray positional encoding on Wan2.2-I2V-A14B, 81 frames, no separate control branch | Wan 2.2 I2V-A14B, not H3 | UNVERIFIED; needs CUDA GPU, Python 3.11, PyTorch 2.9.1; bundle about 67 GB | Apache-2.0 (VERIFIED from its page) | https://comfyui-wiki.com/en/news/2026-08-12-scope-camera-control-wan2-2 | Page updated Aug 12, 2026; original release date UNVERIFIED |
| ReCamMaster (KwaiVGI) | Re-renders an input video along a new camera path | Wan 2.1 1.3B base | UNVERIFIED | MIT (VERIFIED) | https://github.com/KwaiVGI/ReCamMaster | Last dated update 15 Apr 2025 |
| Uni3C (Alibaba DAMO) | Camera plus human-motion control via 3D-enhanced PCD controller (0.95B) | Wan 2.1 14B, not Wan 2.2 or H3 | Reported 46-54 GB per GPU on H20s, so no | Apache-2.0 code; weights at huggingface.co/ewrfcas/Uni3C (VERIFIED) | https://github.com/alibaba-damo-academy/Uni3C | Weights news 22 May 2025 |
| CameraCtrl, MotionCtrl, CamCo | Earlier camera encoders | Not checked against H3 or Wan 2.2 | UNVERIFIED | UNVERIFIED | ReCamMaster paper credits CameraCtrl: https://arxiv.org/html/2503.11647v2 | Older (2024-25) |
| Prompt-only camera words | "dolly, orbit, crane" in text on base Wan 2.2 | Wan 2.2 base; H3 by our own test (weak) | Yes | Model licence | https://help.scenario.com/articles/9790083883-wan-2-2-the-essentials | Undated |
| Blender-driven depth video into H3 Control | Camera move is baked into the depth video (dolly, orbit) | **Yes, H3 ControlNet-Union 2.0 in WanGP** | Our own run is the proof, not yet done for depth-with-moving-camera | Model licence (H3 terms above) | https://github.com/deepbeepmeep/WanGP/blob/main/README.md (29 Sep 2026) | Sep 29, 2026 |

Notes:
- No public H3 native camera-trajectory input was found. The H3 camera options are LoRAs (community) or a control video.
- Camera-from-depth is the only camera route that uses an H3 feature we already have.

## 2. Blender to AI video bridges (Section 2)

| Name | What it does | Works with H3 / Wan2GP? | T4-feasible? | Licence | Link | Date |
|---|---|---|---|---|---|---|
| toyxyz Blender ControlNet rig | Rigged mannequin that renders depth, normal, segmentation and lineart passes in one render; OpenPose attach addon | Pose/depth images can feed a control video; not tested with H3 | Yes (Blender only) | Gumroad, licence not checked | https://toyxyz.gumroad.com/l/ciojz | Undated (update notes); older SD-era |
| openpose_attach addon (toyxyz) | Snaps a separate OpenPose rig onto a character rig | Blender only | Yes | Gumroad | same as above | Undated |
| toyxyz AnimateDiff camera export | Converts Blender camera motion to CameraCtrl pose (needs ComfyUI-AnimateDiff-Evolved) | No (AnimateDiff, SD era) | n/a | Free | from search result, no URL check | 2023-era; UNVERIFIED for 2026 |
| Blender depth export add-on (PLAN8VR/Depth_Map) | One-click normalised Z-pass depth PNG; needs a camera | Yes as a depth source for H3 Control | Yes | Not checked | https://www.github.com/PLAN8VR/Depth_Map | Undated; treat as old |
| ComfyUI-BlenderAI-node (AIGODLIKE) | Runs ComfyUI inside Blender; camera and depth nodes | ComfyUI only, not Wan2GP | Depends | Not checked | https://www.github.com/AIGODLIKE/ComfyUI-BlenderAI-node | Undated |
| Blender-to-ComfyUI Wan VACE workflow (RunComfy) | Depth, outline or pose passes from Blender drive Wan VACE | Wan VACE, not H3 directly | Not checked | Not checked | https://www.runcomfy.com/comfyui-workflows/blender-to-comfyui-ai-renderer-2-0-workflow-cinematic-video-output | Undated |
| Blender to H3 Ref2VA blocking (Seedance blog) | Blender playblast sets camera timing and blocking, then Ref2VA | H3 Ref2VA (ComfyUI workflow) | UNVERIFIED | Not checked | https://www.seedance.tv/blog/minimax-h3-blender-animation-to-realistic-video | Undated |
| Mixamo, Rigify (Pierre Schiller ControlNet rig) | Rigged character for pose | Yes (pose) | Yes | Commercial; Mixamo terms | https://superhivemarket.com/products/controlnet-posable-rig | Undated; Blender 3.5+ |
| Freestyle lineart to ControlNet | Not found as a documented 2026 method | UNVERIFIED | n/a | n/a | n/a | n/a |
| Grease Pencil anime layouts | Not searched in depth | UNVERIFIED | n/a | n/a | n/a | n/a |

Gaps: no single 2026 add-on exports depth, normal, pose, lineart and a camera path to Wan2GP. The workable route is Blender passes plus manual export.

## 3. Anime-specific (Section 3)

| Name | What it does | Works with H3 / Wan 2.2? | T4-feasible? | Licence | Link | Date |
|---|---|---|---|---|---|---|
| AniSora V3.x (bilibili) | Anime I2V on Wan 2.2 (V3.2: 8 steps) | Wan 2.2 base | UNVERIFIED on T4 | Apache-2.0 for V3 (VERIFIED from summary) | https://github.com/bilibili/Index-anisora | Latest official update seen 31 Oct 2025; no 2026 update found |
| Anime Style [WAN 2.2 I2V] LoRA (Civitai) | Anime look on Wan 2.2 I2V | Wan 2.2 I2V (not H3) | UNVERIFIED | Civitai terms | https://civitai.com/models/2222779/anime-style-wan-22-i2v | Update 10 Aug 2026 (secondary) |
| Switch to Anime Style [WAN 2.2 I2V] | Converts realistic start frames to anime | Wan 2.2 I2V | UNVERIFIED | Non-commercial only | https://civitai.com/models/2243780/switch-to-anime-style-wan-22-i2v | Undated |
| ToonComposer | In-betweening plus colourisation in one DiT pass | Not tested | UNVERIFIED | Code not public as of ICLR 2026 listing | https://arxiv.org/html/2508.10881v1 | ICLR 2026 |
| ToonCrafter | Cartoon interpolation (2024) | No | Likely yes | Not checked | https://arxiv.org/html/2405.17933v1 | 2024 (no 2026 successor found) |
| Video2X (Real-CUGAN / Real-ESRGAN / Anime4K) | Anime video upscale, frame by frame | n/a (post) | Yes (CPU and GPU) | GPL | https://vanceai.com/video-upscaler/video2x-review/ | 2026 review (secondary) |
| Real-CUGAN | Anime upscaler 2x to 4x, developer says ~2.2x faster than Real-ESRGAN on V100 | n/a | Yes | Not checked | https://www.besthub.dev/articles/real-cugan-an-open-source-ai-super-resolution-model-for-anime-video-upscaling-f07cf940bf3d | Undated |
| WanGP "H3 Face Refiner" (v12.643) | Face refinement for H3 | H3 | UNVERIFIED on T4 | Model | https://github.com/deepbeepmeep/WanGP/blob/main/docs/CHANGELOG.md | 26 Aug 2026 |

Notes: no 2026 anime video model that clearly beats H3 for our look was found. Nothing new for anime LoRAs on H3 beyond the H3 camera LoRAs above.

## 4. Wan2GP changes after bd1ff59 (Section 4)
- Since bd1ff59 (Nov 4, 2026), **no commits**. bd1ff59 is the newest commit visible.
- H3-related commits since Oct 28, 2026 (VERIFIED from commit list: https://github.com/deepbeepmeep/WanGP/commits/main):

| Date | Commit | Message | H3 relevance |
|---|---|---|---|
| Oct 29, 2026 | d951836 / 563c714 | "added H3 Pika & Singularity" | Diff only bumps version string in wgp.py; the H3 Pika support is UNVERIFIED beyond the title |
| Oct 29, 2026 | 9cb2bcd | "fix h3 detection typr" | Bug fix |
| Oct 29, 2026 | 2efcb44 | "fix regenerate 2k" | Regeneration fix (not checked for H3) |
| Oct 30, 2026 | a504252 | "H3 regenerate audio fix" | H3 audio regenerate |
| Oct 21, 2026 | dee6635 | "added FastH3 Omni, LTX2 VAE turing optimization" | Before the window; "turing" optimisation may matter for T4 (not verified) |
| Oct 26, 2026 | 2dca0c4 / 97845dc | "tuned mmgp mixed VRAM/CPU processing" | Memory tuning, applies to all models |
| Nov 3, 2026 | a288819 | "3D update" (49 files) | Adds models/minimax_h3 folder and Speridlabs Idol (TripoSplat) Gaussian splat; no VRAM stated |
| Nov 3, 2026 | e9c7506 | "added 3D Idol Gaussian" | Gaussian splat from one image (VERIFIED from a288819 summary) |
| Nov 4, 2026 | bd1ff59 | "showrunner, taomate face refiner" | Pinned commit |

- No T4-specific fix for H3 is visible in commit titles. Veda / Sol attention issue is still open for us.
- The changelog (last entry 26 Aug) lists H3 PDD 8-step LoRA acceleration (v12.645) for FL2VA and Ref2VA. Useful for the T1 test (lower steps).
- Gaussian splat (Idol): could be a camera route (orbit a 3D splat from one keyframe). Not tested; UNVERIFIED on T4.

## 5. News since 2026-10-28 (Section 5)
- **Pika H3 Flex**, released Oct 29, 2026 (API Club), in the Pika app Nov 2 (VERIFIED via comfyui-wiki and secondary blogs: https://comfyui-wiki.com/en/news/2026-10-29-pika-h3-flex). Six-step distilled H3 with FL2VA and Ref2VA LoRA adapters; inherits the H3 licence; VRAM and licence not stated on the page. Our plan already uses it.
- **Singularity** is a community merged fine-tune of H3 variants (not a LoRA), dated Sep 7, 2026, Apache-2.0 on its HF page per a secondary source (https://comfyui-wiki.com/zh/news/2026-09-07-h3-singularity). Before our window; UNVERIFIED on T4.
- **Lightx2v H3 Turbo LoRA v1.0** (8 and 4 step, 768p): Aug 11, 2026 (https://comfyui-wiki.com/news/2026-08-11-minimax-h3-turbo-lightx2v-v1). Before our window, but relevant to step count.
- **Hyperflow / NVIDIA H3 variant**: not found. UNVERIFIED that they exist.
- **New open video models fitting 16 GB**: Kandinsky 6.0 Video, published Oct 6, 2026 under MIT (secondary: https://pinggy.io/blog/best_video_generation_ai_models/ and linked blog); 29B Pro and 3B Lite; **VRAM UNVERIFIED**. The 3B Lite may fit a T4; the Pro will not. Check the model card before use.
- **H3 licence**: no update after Aug 2, 2026 found; the H3 Community License text is the one to use (see section 0).

## 6. Ranked recommendation: Blender camera and motion for our stack

Ranking (best first):
1. **Blender layout as driving video, into H3 Control (depth or pose), with start and end keyframes from Flow.** Uses a feature WanGP already has (H3 ControlNet-Union 2.0, Sep 29, 2026). Camera is exact from the Blender camera. Motion comes from a mannequin rig (toyxyz-style passes). Cheapest to test; no new model download.
2. **Phone "follow acting" video into H3 Control (pose)** for choreography and gestures. Same pipeline; different driver.
3. **H3 camera-movement LoRA** (community) for a single shot's camera move when Blender is too slow. Test only after 1. Licence and variant match apply.
4. **Uni3C or Fun Control-Camera (Wan 2.1) in WanGP** as a side branch for a locked camera move on a still. Not H3; use only if the H3 route fails and the shot is a plain move. Output would need a different look check.
5. **SCoPE (Wan 2.2)**: camera-ray method, Apache-2.0, but about 67 GB bundle and T4 UNVERIFIED. Park.
6. **Gaussian splat (Speridlabs Idol in WanGP)**: a possible orbit source from one keyframe. Test only if an orbit shot is needed.

What to test first (order):
- **C1 (Blender depth into H3 Control, moving camera):** a 5 s Blender dolly-in or orbit on a plain mannequin scene, rendered as depth; run H3 Control FL2VA with the Flow keyframe. Question: does H3 follow the camera move from depth alone? Compare with a static-camera depth run. Cost about 1 GPU-h. Pair with T1 in plan_v3 (Control on T4).
- **C2 (pose from the same rig):** the same mannequin as pose; compare with depth for body motion. Cost about 0.5 GPU-h.
- **C3 (H3 camera LoRA on one still):** one orbit LoRA run only if C1 fails. Cost about 0.5 GPU-h.

Blocking points: H3 licence territory (section 0) must be read before global distribution. T4 feasibility for H3 Control at our settings is still the unknown from plan_v3 T1.

## 7. What could not be verified
- CameraCtrl, MotionCtrl, CamCo: not checked against H3 or Wan 2.2.
- T4 VRAM for any camera model except what sources state.
- Freestyle-to-ControlNet lineart export: no method found.
- Kandinsky 6.0 Video VRAM and licence on the model card: not read.
- Hyperflow and an NVIDIA H3 variant: not found.
- WanGP H3 Pika code path (commit d951836): only the title and a version bump were visible.
- Wan2GP changelog after Aug 26, 2026: not maintained; recent changes taken from commit titles only.
