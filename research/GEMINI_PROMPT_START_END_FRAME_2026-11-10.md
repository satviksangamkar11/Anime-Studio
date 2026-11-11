# Research brief for Gemini: start-frame / end-frame consistency in an AI anime video pipeline

You are a research partner. Research on your own, with sources, and propose a better way to storyboard and generate shots so the video does not morph. Separate VERIFIED facts (with links or repo file names) from SPECULATION. Do not invent model features, node names or parameters; if you cannot verify something, say so.

## 1. What we are making
Short vertical devotional-anime reels (Indian mythology, flat-colour cel look, "Deva Neon" style pack): 9:16, 24 fps, 60-75 s, about 10 shots per reel, each shot 6-9 s. Three languages (English, Hindi, Marathi) share ONE picture timeline. Budget is small: rented Colab GPU units, free or cheap models, one person supervising. Each shot is one video clip, then clips are cut, voiced, scored and captioned.

## 2. The pipeline and the models (facts from our repo)
- Keyframes (still images): made in Google Flow (Nano Banana 2.1; Nano Banana Pro for rework edits). Per shot we make keyframe A (start) and keyframe B (end), from character sheets, place plates and reference crops.
- Video: MiniMax H3 run through Wan2GP (headless, not ComfyUI) on a Colab G4 (RTX PRO 6000 Blackwell, about 98 GB). Reel 1 used the first/last-frame route "FL2VA" (`minimax_h3_fl2va_pruned` + official Pika H3 Flex 6-step LoRA, `pika_renoise`, 6 steps, shift 12), 768x1344, 24 fps. Clip length must be `17n+5` frames (158, 175, 209, 243 seen). Alternative route we tested: Singularity v2 pruned + Pika-Labs Turbo 8-step HD LoRA with Ref2VA (face + full-body reference images), euler, CFG 1.
- Prompt: one structured text prompt per shot with a 7-stage action timeline; one blank line inside a prompt makes Wan2GP see a second request and fail.
- Order of work (locked): script -> voices -> timeline (every shot's length fixed from measured voice length) -> shot keyframes -> render. So A and B must be designed for a KNOWN duration.

## 3. The problem statement
The model treats keyframe B as a hard lock. Our own review of Wan2GP's code (`minimax_h3_handler.py`, about line 117) quotes: each window "lands exactly on its end image. When the action has drifted away from that picture, the last few frames jump to it." If A and B disagree in set, pose, props, camera or scale, or the action cannot physically reach B in the shot's time, the clip morphs, pops or invents things. Consistency between two independently generated stills is very hard to reach, and we pay for every failed render (about 1-2 Colab units per shot, 10 units per GPU hour).

## 4. Evidence: what actually went wrong (reel 1, a real production reel)
| # | Shot | What happened | Root cause as we understand it |
|---|---|---|---|
| 1 | SHOT-008 (Brahma, Shiva, Kamadeva on an assembly throne) | Keyframe A: Brahma STANDING in front of a flat throne. Keyframe B: Brahma SEATED on a raised stepped dais. The script says seated for the whole shot. The video morphed the set between the two (flat throne becomes dais), and Shiva's hair flickered. | A and B were generated as two separate images; nobody compared them to each other or to the script. Re-render needed (about 1.2 units each). |
| 2 | SHOT-002 | The character lost two arms in the middle of the clip; the A/B arm counts disagree. | Arm count differs between the two stills; the model reconciles it mid-clip. |
| 3 | SHOT-007 and SHOT-009 | Keyframes missed required people (Daksha and sages reacting; Shiva present) and the pose list disagreed with the script (script: Brahma rises; both new stills show him seated; 007A already shows the full bow draw although the script starts the draw). | Keyframes were approved without checking them against the per-second script or the scripture. |
| 4 | SHOT-001 keyframe 1A | Letters appeared inside sparks; asking the image model for "one eye open, one closed" produced a wink. | Image model behaviour; fixed by a rule, not by the pipeline. |
| 5 | SHOT-008 re-render | The sound note "serpents hiss" made the video model draw two cobras behind Brahma from frame 48 to the end. | The video model draws every noun it reads, including nouns in sound notes. |
| 6 | Hair / props / background | Flicker and small identity drift even when A and B agree. | Typical H3 behaviour; partly reduced by Ref2VA references. |
| 7 | Our T0 test (LEAP-03, 8 clips, 768x1344, 124 frames) | Arm A (Ref2VA + Pika 6-step): scene and identity held. Arm B (Singularity + Turbo 4-step): FAILED on both seeds, the scene cut to a village/lake view at frames 60-90. Arm C (Singularity + Turbo 8-step HD): held, crisper hands. Arm D (first/last-frame): held scene and identity, slightly looser pose. | When A and B were designed together as one consistent pair, FL2VA behaved. Failures came from inconsistent pairs or the wrong LoRA/schedule. |

## 5. What we already do or decided (so you do not repeat it)
- B is made as an EDIT of A (single reference image, short exact change list, Nano Banana Pro), never as an independent generation. Every kept picture is checked at full size by a human; the AI picture reviewer is advisory and was wrong at least once.
- Clip is rendered with spare "handles" (about 8-35 frames at the head, 24-47 at the tail) and the pop is trimmed away.
- Never chain the next shot from the previous clip's real last frame, except match-on-action cuts (our review: drift and softening compound over many shots).
- Shot types routed differently: first/last frame (one action between two known poses), first/last + a middle keyframe for arcs or leaps over about 1.5 s (planned, NOT implemented), Ref2VA for identity-critical close-ups, and no-GPU "POST" routes (holds, pans, parallax, reactions) for shots where consistency is too costly.
- Not implemented yet: an automatic end-frame similarity check (SSIM/LPIPS/embedding) between the clip's last kept frame and keyframe B; the middle-keyframe option.

## 6. Unverified claims we received (please verify or refute, with sources)
- Wan2GP / MiniMax H3 can run START-FRAME-ONLY ("image_prompt_type" `S` with no end image) on our checkpoint without a quality loss; our code can write `S` or `SE`, but we have never rendered start-only.
- An "end strength" of about 0.5-0.65 ("pin then flip") softens the end lock. We found this only in an outside document, never in our files or in Wan2GP; we do not know if our route has any such strength control.
- ComfyUI node names mentioned by others (MiniMax director / keyframe nodes) apply to ComfyUI, not to our Wan2GP setup.
- Whether Wan 2.x FLF2V, VACE, or other first-last-frame / multi-keyframe models do better than H3 for flat-colour anime.

## 7. Constraints
Free or very cheap; Colab G4 units are limited; one human reviewer; Windows PC; no re-rendering of finished reels; Hindi/Marathi/English voices fixed before pictures; characters must stay on model (sacred figures, correct iconography); flat colour, ink outlines, no photoreal.

## 8. Repositories to read (read the code, do not guess)
- OUR REPO (public): https://github.com/satviksangamkar11/Anime-Studio . Branches: `merge-v4-universal-2026-11-07` (main working line, newest), `v4-architecture-2026-11-07` (has the batch builder and Colab runner), `universal-v1.1`, `main`.
- In it, read: `director/h3_director.py` (builds the Wan2GP settings per shot; line ~346 builds `image_prompt_type` "S"/"E"/"SE" from start/end presence), `h3/compile_h3_sing8.py` (prompt compiler, FL2VA and Ref2VA), `h3/shot_table_spec.py` (lattice, handles, seams), `h3/v4_to_h3.py` (timing, lattice fit, mouth and sound cues), `director/build_h3_batch.py` and `director/run_colab_batch.py` (branch `v4-architecture-2026-11-07`: the batch that was really run on Colab), `research/OPUS_INDEPENDENT_REVIEW_2026-11-04.md` (the review that found the end-frame lock), `research/workflow_review/DECISION_best_workflow_2026-11-05.md` and `W3_wan2gp_capabilities.md` (the T0 test and the Wan2GP capability notes), `MISTAKES_AND_LESSONS.md` (cost of every failure, F2/F4/Q1-Q5/W7 are the keyframe items), `blot.md` rules 25, 31-34, 52 (keyframe rules, clip check method, order of work), `research/SEQ_MERGED_REPORT_2026-11-09.md` and `PLAN_REVIEW_TRIAGE_2026-11-10.md` (latest reviews).
- Wan2GP (upstream, the video runner): https://github.com/deepbeepmeep/Wan2GP . Read the MiniMax H3 model code (`models/minimax_h3/`, handler and pipeline), the model definitions and settings (`image_prompt_type`, `image_start`, `image_end`, `video_prompt_type`), and its docs for what start-only, first/last and multi-keyframe input really do.
- Also look for: MiniMax H3 / Pika H3 Flex / Singularity docs and model cards, Wan 2.x first-last-frame (FLF2V) and VACE code, and any open-source keyframe-interpolation or multi-keyframe video conditioning projects.

## 9. What we want you to research and deliver
1. WHY the inconsistency happens on both sides: (a) image generation/edit (how to get two stills of the same set, characters and camera that differ ONLY in the intended change), (b) the video model's end-frame lock (what it really does, which settings change it).
2. NEW STORYBOARDING METHODS that avoid the problem, with evidence: for example one source image plus controlled edits; inpainting only the changing region; pose/depth/line-art conditioned edits; multi-keyframe or keyframe-at-frame-index conditioning; start-frame-only plus a strong prompt; short chained segments with correction; character LoRA or reference-based generation; video extension / continuation; storyboarding in a 3D or 2.5D layout (layers, parallax, held backgrounds with animated characters); motion-comic hybrids; anything else you find that works for anime.
3. A decision tree: for each shot type (single acting beat, big body action, camera move, crowd, dialogue close-up, seam into the next shot), which method to use and why, with cost per try.
4. Automatic checks we can add before paying for a render and after it (set consistency, character count, arm/hand count, pose difference between A and B, end-frame match, flicker), with the cheapest tools that work on Windows.
5. A cheap experiment plan on ONE shot (our SHOT-008 case above): arms to compare, what to measure, how many tries, expected Colab units, and a clear pass/fail rule.
6. A short list of repositories, papers and docs you actually read, with links. Mark each claim VERIFIED (you read the source) or UNVERIFIED.

Answer in English. Be concrete and skeptical; prefer a smaller proven method over a clever unproven one.
