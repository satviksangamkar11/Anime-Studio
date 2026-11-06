# V1: "I Built an Unlimited Anime Pipeline in RunningHub (MiniMax H3)" (The AI Brief), analysed for Anime Studio

- Video: JndCXtuU7-I, The AI Brief, uploaded 2026-09-17, 771 s (12:51). Channel is sponsored by RunningHub ([01:19]).
- Analyst: V1. Date: 2026-11-05. Read-only; no web, no downloads, no paid calls, no secrets read.

## 0. Sources, conventions, limits

- Read in full: the transcript (Whisper, `[mm:ss]`), `info.txt` (title, description, chapters), `ctxloop_readme.md` (Context Loop 0.7.3), and the metadata fields in `info.json` (duration, chapters).
- Also read: the two workflow JSONs in the same folder, `MiniMax-H3-Context-Loop-NEW.json` and `MiniMax-H3-Context-Loop.json`. Their node titles and widget values come from the pack's example graphs (a courier demo and a Doom paratrooper demo). They are NOT the Akio/Elder graph of the video, and the folder does not record where they came from. Cited as JSON-NEW and JSON-OLD.
- Our files (cited as OUR): HANDOFF_2026-11-05, DECISION_best_workflow_2026-11-05, DIRECTION.md, `director/h3_director.py`, `shot_schema.py`, `style_bible.py`, `style/kaliya_mardan.json`, MASTER_PROMPT_v2.1.md, PLAN_v3 and PLAN_v4 (v4.3 in force), the OPUS review, the four_videos architecture guide, and workflow_review W1-W4.
- Limits:
  - No video file is in the folder, so I did not see the finished anime. Every visual claim is the creator's word.
  - The Gumroad LLM playbook and the RunningHub graph were not available and were not fetched.
  - None of the creator's quality claims are measured.
  - Whisper errors: the lead character is "Akio" at [02:07] and [02:14], "Q" at [04:44], and "Accio" in tags from [04:48] on. I treat these as one character (MY INFERENCE). "Sea Dance 2.5" at [11:38] appears as "#Seedance2.5" in the description.
- "Not stated" means the source does not say. "MY INFERENCE" marks my reasoning.

## Bottom line

1. The video is a ComfyUI version of the stack we already run. A chat LLM writes the cast, character sheets, location tags, a shared prompt, and per-scene prompts with durations. A node graph then generates one scene at a time behind a review gate, and an Assemble node joins the clips. He uses reference images only. No start/end keyframes appear in the transcript.
2. It exposes three gaps for us:
   - The voice path. He attaches a tagged voice clip per character. Our ElevenLabs plan is a kept-soundtrack or mouth-edit route, and the dialogue test is no longer in the adopted plan (PLAN_v4 v4.3).
   - Multi-angle location sheets, which we do not make.
   - Scene-to-scene chaining. MASTER_PROMPT line 12 asks for it, but the Flow keyframe plan does not do it.
3. Nothing in the video is anime-specific. Identity, location and voice consistency are all asserted, not measured.
4. Worth taking now: the shared-prefix-plus-tags structure (we already have it in code), a dialogue and voice field in the shot JSON (we lack it), and the pack's audio-fit rules for an ElevenLabs line (1/24 s start offset, pad or cut to the scene).
5. Document problems found while checking:
   - MASTER_PROMPT line 26 says durations are "rounded up" to the grid. The code rounds to the nearest legal count.
   - DIRECTION's LEAP-NN shot names fail the director's id rule.
   - The DECISION Audio row conflicts with PLAN_v3 and the OPUS review.

## 1. The pipeline, from script to finished anime (his method)

| # | Stage | Tool / node (his name) | What he does | Settings and files | Source |
|---|---|---|---|---|---|
| 1 | Brief | ChatGPT + a "markdown guide" (the Gumroad "LLM Master Prompt Playbook") | Input: how many characters, the premise, the visual style. Demo: one-minute anime short, a conversation about the future of AI between a young boy and an old man. | Guide file type: markdown. | [01:31]-[01:53]; desc lines 12-13 |
| 2 | Casting | ChatGPT | Two characters, "Akio" and "Elder": personalities, ages, roles. | Text | [02:02]-[02:07] |
| 3 | Character sheets | ChatGPT built-in image generation | One sheet per character, Akio first, then Elder. He chose ChatGPT because its image generation "saves us from switching tools later". | Image; size and format not stated | [01:33]-[01:37]; [02:10]-[02:20] |
| 4 | Location reference | ChatGPT image | "a grid of images showing the same setting from different angles". ChatGPT also returns a tag (example: "rooftop"). | One grid image per location | [02:27]-[02:38]; [05:16]-[05:20] |
| 5 | Voice profiles | ElevenLabs ("11 Labs") | "generate unique voice profiles". He says "I've already extracted mine". | Audio clip per character; format not stated | [03:36]-[03:42] |
| 6 | Script and prompts | ChatGPT | A shared prompt (a prefix on every scene), then Scene 1 to Scene 4 prompts with a duration each. Also: total length, dialogue progression, ending, and tagging instructions. The shared prompt is "perfectly structured for the Minimax H3 model". | Text blocks | [02:43]-[03:31] |
| 7 | Workflow | RunningHub cloud ComfyUI, "Launch on Cloud" | Three groups: casting, locations, voices. Ctrl-B to unbypass the character, tag, and audio nodes. | RunningHub workflow, not available to us | [04:11]-[04:40] |
| 8 | Load cast | Image nodes plus tag nodes | One image per character, tagged ("Accio", "Elder"). Purpose: "easier for both us and the model to identify the character later". | Two images | [04:42]-[04:57] |
| 9 | Load location | Image node plus tag node | Location grid plus tag "rooftop". "your location is locked in" (claim). | One location shown | [05:03]-[05:24] |
| 10 | Load voices | Two audio nodes plus tag nodes | Tags "Accio Voice" and "Elder Voice". | Audio clips | [05:26]-[05:47] |
| 11 | Speed and attention | Sage Attention (on, cloud); bypass toggles for LoRA, Turbo LoRA, Comfy Kitchen Attention, Model Sampling | "Just unbypass the ones that suit your hardware." Weaker local GPU needs these. | Not stated which were on | [06:25]-[06:46] |
| 12 | Prompt slots | Prompting node | Paste the shared prompt, then Scene 1, Scene 2, and so on into their slots. | Text | [06:47]-[07:00] |
| 13 | Durations | Per-scene seconds | Seconds per scene must "exactly match the timing ChatGPT outlined". He calls this the step "most people miss". | Seconds | [07:02]-[07:08] |
| 14 | Prompt check | Scene Prompt Editor | All tags shown. Hover a character tag to see its sheet; hover an audio tag to preview the clip. | | [07:11]-[07:35] |
| 15 | Sampler | Sampler and scheduler | Euler; Simple. | Steps not stated | [07:37]-[07:41] |
| 16 | Resume | Loop Start Resume | Start Clip defaults to 1. Set it to 3 to skip Scenes 1 and 2. | Integer | [07:43]-[07:58] |
| 17 | Live check | Model Preview Override | Real-time preview. Stop and fix the prompt or "enhancements" if something is off. | | [08:01]-[08:19]; [09:24]-[09:31] |
| 18 | Review gate | Review Gate | Pauses after each scene. Options: Enable or Disable, Toggle Notification Sounds. Approve, retry with a different seed, or stop. | | [08:21]-[08:48] |
| 19 | Batch mode | Review Gate, Enabled = False | "Set Enabled to False". The run then goes through all scenes and delivers one video. | | [08:48]-[09:03] |
| 20 | Run | Run button, side task list | | | [09:12]-[09:19] |
| 21 | Save per scene | Save Segment | Shows each scene result. Approve; the next scene is then built "automatically". | Video per scene | [09:36]-[10:03] |
| 22 | Assembly | Assembly node | Joins all clips into one result. | Output format not stated (pack README: MP4) | [10:37]-[10:42] |
| 23 | Bonus | Sea Dance 2.5 (RunningHub) | A character reference sheet plus a long prompt gave "a seamless 30 second clip". | | [11:31]-[11:56] |

Not stated in the video: sampler steps, CFG, resolution, frame counts, seconds per scene, GPU, time per scene, number of scenes in the final cut, audio mix, music, SFX, captions, export format.

How "unlimited" works in the pack (not shown in the video): the README says that to extend a running Plan, you append scenes before approving its last scene. With Loop Start's scene range blank, Approve and continue finishes the current run, then queues the updated workflow at the first appended scene, using the saved checkpoint. The transcript never explains the word "unlimited". MY INFERENCE: this is the likely mechanism behind the claim.

## 2. Multi-reference character lock

- Reference count and images:
  - One image per character, two characters ([04:42]-[04:57]). The transcript says "character sheet" in the singular, so one sheet per character is the likely case. Whether that sheet holds several views is not stated (MY INFERENCE: it does).
  - One location image ([05:11]-[05:16]).
  - One voice clip per character ([05:37]-[05:47]).
  - The pack's two-picture Ref2VA note says "Both connected pictures remain active in every scene" (JSON-OLD node 1958; the basic Ref2V note at node 1977 says the same). Whether his refs stay active in every scene is not stated.
- How refs are named in the prompt:
  - The tags are the handles. The Scene Prompt Editor shows all of them ([07:15]-[07:18]).
  - The prompt-side syntax is not shown.
  - The README says: "Valid prompt `@tags` again see the connected Tagged registry". So the pack's tags are `@tag` names in prompt text. MY INFERENCE: his tag nodes are that Tagged registry.
  - The pack's basic example uses native labels "<Picture 1>" and "<Picture 2>" (JSON-OLD node 1977).
- What he warns about: nothing on references. His stated reason is "easier for both us and the model to identify the character later" ([04:48]-[04:51]). His actual warnings cover durations ([07:02]-[07:08]), weaker local GPUs ([06:33]-[06:35]), and stopping early on inconsistencies ([08:04]-[08:12]).
- Keyframes: no start or end frame appears anywhere in the transcript. The method is references plus prompt (Ref2V).
- Claim, unmeasured: "It pulled the same reference characters I defined" ([11:22]-[11:24]).
- OUR: the DECISION uses two references of one character (face crop and full-body front crop) cut by `flow/scripts/make_refs.py` from the 3-panel identity master. The `<Picture N>` labels appear only in subject_definitions and retention_analysis. `style_bible.flow_sheet_prompt()` already asks Flow for one image with three panels (face close-up, full front, back). So his sheet is the same idea as ours. The difference is that he uses the sheet whole (MY INFERENCE), while we cut it into two references.
- The pack's two-picture Ref2VA example uses Picture 1 as a style and viewpoint reference for the subject, and Picture 2 as an environment reference (JSON-OLD node 1991, "TWO GLOBAL PIC").
- MASTER_PROMPT line 32 says "two characters together go side by side in ONE reference picture". That is a per-shot choice we have not tested.

## 3. Multi-location scenes

- How the location is set: a ChatGPT grid of the same setting from several angles ([02:27]-[02:33]). Stated purpose: "ensuring the background stays coherent throughout the animation" ([02:36]-[02:38]). The LLM's tag ("rooftop") goes on the location's tag node ([05:16]-[05:22]).
- How it stays consistent: the grid is a reference picture, like a character sheet, and the tag names it in the prompt. The prompt syntax is not shown.
- Claim: "Notice how it used the exact location from my character sheet?" ([11:18]-[11:21]). He says "character sheet", but the location was a grid (MY INFERENCE: a slip).
- What is shown: one location only ("rooftop"). No scene changes location in the transcript. The description's "Multi-location scenes" chapter ([desc] 5:00-7:00) shows only the loading of a single location image. So the multi-location claim is not demonstrated.
- OUR: environment plates are made in Flow (ENV-KADAMBA-BANK, ENV_WATER_SURFACE_HIGH, per HANDOFF and DIRECTION). In `h3_director.py`, the shot's `set` enters only as text (`identity_text()` calls `style_bible.prompt_block()`), not as a picture. Environment consistency therefore comes from the Flow keyframes (FL2VA start and end) and the text. REF2VA has no environment picture.
- Addition to consider: an environment plate as a third picture, following the pack's two-picture example, where Picture 2 is the environment. The Wan2GP limit on reference count is not verified in our notes, so check the pinned code before testing it.
- Adapt later: the multi-angle grid. Our MASTER Gate 2 asks for a single empty plate. A turnaround-style environment sheet is an option only if a later scene needs several angles.

## 4. Multi-voice consistency

- What he says:
  - Each character gets an ElevenLabs voice profile ([03:36]-[03:42]).
  - Each is loaded into its own audio node and tagged "Accio Voice" and "Elder Voice" ([05:37]-[05:47]).
  - Hovering the audio tag previews the clip ([07:30]-[07:33]).
  - A sample plays at [05:49]-[06:17]. It is a narration line ("On the edge of a forgotten forest...") and the transcript does not say which character it is.
  - Claim: "matched the specific voice tones I tagged for each one" ([11:25]-[11:27]).
- Generated or recorded: not stated.
  - The LLM's breakdown includes "dialogue progression" ([03:23]-[03:25]), so the speech text is probably in the scene prompts (MY INFERENCE).
  - The voice clip most likely conditions the timbre of what the model generates (MY INFERENCE).
  - Lip-sync is not shown or mentioned.
  - The pack's own graphs (JSON-NEW and JSON-OLD) have no audio loader node, only VAEDecodeAudio. So his audio nodes come from a graph we do not have.
- The pack's rules for a per-scene dialogue file (README, "Dialogue audio for one scene"):
  - Pick an audio file from the Project Asset Carousel; this turns Lip-sync on for that scene only.
  - The audio start position is snapped to 1/24 s.
  - Short audio is padded with silence; longer audio is cut to the scene length.
  - "Generated output uses the dialogue once."
  - These are the best spec we have for fitting an ElevenLabs line to a shot.
- OUR plan, with status:
  - ElevenLabs makes the spoken line (Hindi). H3 keeps that audio as the soundtrack and moves the lips (PLAN_v3 line 37: audio_prompt_type "A" for FL2VA, "AS" for Ref2VA). Or Flow mouth-shape edits, masked to the mouth, when the head is still (PLAN_v4 amendment 5). Or post-production mouth flaps.
  - Non-dialogue shots: H3 sound ignored, sound in post (DECISION).
  - `h3_director.py` sets `"audio_prompt_type": ""` (line 304). The OPUS change 6 (dialogue shots get audio_prompt_type "A" plus audio_guide) is not implemented.
  - PLAN_v4 v4.3, the adopted order, has no dialogue row. The old step 5, "Dialogue: H3 soundtrack vs masked mouth shapes, ~0.5 h", was dropped when v4.3 replaced the order (PLAN_v4 line 34).
  - The four_videos guide (row 7) says: "Pin the video to a frozen ElevenLabs line for talking shots (lip-sync from H3 is weak)."
  - Licence: ElevenLabs commercial terms depend on the plan tier, which is unverified (OPUS line 71). No voice cloning for deities (MASTER line 22).

| Question | His method (as stated) | Our plan |
|---|---|---|
| Who makes the speech | Not stated. Probably H3, from the scene text (MY INFERENCE) | ElevenLabs, exact text |
| How the voice carries across shots | One tagged audio clip per character, sent with every shot (MY INFERENCE from the tags) | One ElevenLabs voice per character. Not yet in the style bible: no voice field exists |
| Lips | Not shown | H3 kept-soundtrack mode (weak per the guide) or masked Flow mouth edits when the head is still |
| Evidence | One claim, no measurement | None yet; the dialogue test is not in v4.3 |
| Voice rule for real persons and deities | Not stated | No cloning for deities (MASTER line 22) |

- Verdict: keep ElevenLabs as the one voice source. Borrow the tag-per-character registry and the preview. Do not copy a voice clone for Krishna or any deity. Speech generated by H3 is an untested alternative only.

## 5. The LLM master prompt

- His LLM (ChatGPT plus the Gumroad markdown playbook, which we do not have):
  - Input: number of characters, script premise, visual style ([01:39]-[01:46]).
  - Output, in the order shown: cast with personality, age and role ([01:56]-[02:07]); character sheet prompts ([02:10]-[02:14]); location grid prompt and tag ([02:27]-[02:33]; [05:16]-[05:20]); shared prompt for H3 ([03:04]-[03:12]); a prompt and duration for each scene ([03:18]-[03:21]); a breakdown with total length, dialogue progression and ending ([03:23]-[03:25]); tagging guidance ([03:28]-[03:30]).
  - The layout of the output text is not shown.
- Ours, MASTER_PROMPT_v2.1.md: five gates (story autopsy, art bible, shot ledger, generation prompts, sound and QA), then a final ```json shots``` contract. The contract has id, episode, mode, seconds, aspect, start, end, refs, subjects, style, world, action, camera, sound. The writer must emit valid JSON.
  - Strengths: stricter than his. One primary action and one camera move per clip. End keyframes are edits of the start keyframe. Model limits are stated.
  - Gaps against his flow:
    - Gate 5's dialogue table is not linked to any shot field.
    - The shot JSON has no tag or cast ids, and no durations in frames.
    - Line 26 says durations are "rounded up to that grid". The code does not do that (see section 8, C9).
    - Line 12 says the next shot "starts from the real last frame of the accepted clip". That conflicts with per-shot Flow keyframes (see section 8, C3).
- Proposed shot-list template. It keeps our contract and adds the parts of his flow that we lack. Keys marked NEW are not in `h3_director.py` today.

```json
{
  "project": "kaliya_mardan",
  "prompt_prefix": "<one style line plus the KEEP sentence from the bible; identical in every shot>",
  "voices": {"CHAR-KRISHNA": "<designed ElevenLabs voice id>"},
  "shots": [
    {
      "id": "SHOT-03",
      "scene_label": "LEAP-03",
      "mode": "fl2va",
      "render_frames": "<107 + 17k, max 362>",
      "edit_frames": "<1 to render_frames>",
      "aspect": "9:16",
      "start": "keyframes/<file>.png",
      "end": "keyframes/<file>.png",
      "refs": [],
      "subjects": [],
      "set": "ENV-<id>",
      "cast": ["CHAR-<id>"],
      "style": "<one line, no film or show names>",
      "world": "<place, time of day, light>",
      "action": "<time-coded, one primary action>",
      "camera": "<one move>",
      "sound": "<soundscape, no speech>",
      "dialogue": [
        {"speaker": "CHAR-<id>", "text": "<line>", "audio": "audio/<file>.wav", "start_s": 0.0, "fit": "pad_silence or cut_to_scene"}
      ]
    }
  ]
}
```

| Key | Status | Why |
|---|---|---|
| `prompt_prefix` | NEW (the director builds style per shot today) | His shared prompt. The pack's Plan uses the same key (JSON-OLD node 2016). A validator should check it is identical in every shot |
| `voices` | NEW, in the bible | His per-character voice clip. Ours: designed ElevenLabs voice ids |
| `scene_label` | NEW, optional | Keeps DIRECTION's LEAP-NN names. The director's id rule needs SHOT-NN |
| `render_frames`, `edit_frames` | EXISTS | Write frames, not seconds, so the LLM cannot drift from the grid |
| `set`, `cast` | EXISTS in the rich-shot schema | Validated by `validate_shots(bible_ids)` |
| `dialogue` | NEW | Ties Gate 5's dialogue table to shots. Fit rules from the pack's README |

- Writer rules that follow from this:
  - Write frames, not seconds.
  - Use only ids from the bible.
  - Put dialogue in `dialogue`, not in `sound`.
  - Emit valid JSON only.

## 6. Prompt format and structure

- His prompts: no prompt text is shown or quoted in the transcript or the description. Stated: the shared prompt is a prefix on every scene ([02:52]-[02:58]; [06:49]-[06:56]); the output is "perfectly structured for the Minimax H3 model" ([03:09]-[03:12]); scene prompts are "highly detailed" ([07:33]-[07:35]).
- The pack's own example text (JSON, not his):
  - The basic Plan prefix (JSON-OLD node 2016) opens: "Modern cinematic 2D animated feature film style, high-definition cel shading, clean line art, sharp but natural color palettes, detailed environments, expressive character animation, cinematic lighting and physically believable motion."
  - The six-section Ref2VA format (JSON-OLD node 1958): subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music.
  - A character picture is described as "<Picture 1> is the primary visual reference for <Subject 1>..." (JSON-OLD node 1991).
- OUR `h3_director.prompt_for()`:
  - REF2VA uses the same six sections, in the same order: subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music.
  - FL2VA opens with "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.", then `integrated_multimodal_description:`, `overall_soundscape:` and `non_diegetic_music: N/A`.
  - The KEEP sentence: "Keep every face, outfit, prop and background exactly as in the pictures; no new people; no style change; no on-screen text."
- Verdict: our format already matches the pack's six-section structure. Keep it. Do not copy "cinematic lighting and physically believable motion" from the pack prefix. MY INFERENCE: those words push toward light effects and realism. Test with the T0 colour and line checks.

## 7. What works for anime

- His video: nothing anime-specific. No style words and no anime failure fixes are shown or said. W4 reached the same conclusion across seven transcripts ("Anime-specific tips found: 0").
- Generic things he does say:
  - Stop a run when the preview shows an inconsistency ([08:04]-[08:12]).
  - Check durations ([07:02]-[07:08]).
  - Retry with a new seed ([08:43]-[08:47]).
  - Repeat the shared prefix on every scene ([02:52]-[02:58]).
- Anime-relevant risks from our own notes (not from this video):
  - Spectrum Cache may change eyes and fingers (W4 g7, T2 [09:16]-[09:37]).
  - Kitchen Attention "makes the result bad when used with distilled models", a creator's claim (W4 d5, T6 [02:13]-[02:22]).
  - A weak reference gives the wrong person (W4 b3, T4 [13:38]-[13:42]).
  - De-Rope may change faces (W4 e7, guide source 11; one creator's claim).
- Our anime rules that already cover this:
  - The style bible's palette, line and shading rules are appended to every shot (`identity_text()`).
  - Each character has a forbidden-drift list.
  - Rim light: "at most one rim-lit figure per shot; never on faces during dialogue or acting beats" (`style/kaliya_mardan.json` line 75). This matters for dialogue shots, so write "no rim light on faces" into any dialogue prompt.
  - DECISION already uses cel-style wording, avoids photoreal words, and keeps caching off.
- Test to add (MY INFERENCE): measure flat colour and line weight on the T0 frames. T0 already measures colour drift and line flicker.

## 8. What contradicts or improves our DECISION

| ID | Topic | Our docs say | His video says | Verdict | Action |
|---|---|---|---|---|---|
| C1 | Audio | DECISION: "H3 sound ignored; sound in post". PLAN_v3 line 37 and OPUS change 6: dialogue shots keep the ElevenLabs line | Voice clips per character | DECISION is ambiguous about dialogue | Rewrite the Audio row: dialogue is a separate, untested route |
| C2 | Dialogue test | PLAN_v4 v4.3 has no dialogue row (old step 5 dropped) | Not applicable | The test that decides the voice route is unscheduled | Re-add it (top action 1) |
| C3 | Continuity | MASTER line 12: next shot starts from the last frame of the accepted clip. DIRECTION and DECISION: per-shot Flow keyframes; LEAP-02 to 03 is a match on the crouch, 03 to 04 and 04 to 05 are cuts | Scenes are chained (README: "Carries visual motion ... between scenes"; "the exact saved checkpoint supplies the next scene's continuity"). The transcript shows approval per scene, not the mechanism | Two rules in our docs disagree | Decide per shot class (top action 4) |
| C4 | Identity source | DECISION: two crops from the 3-panel master (make_refs.py). MASTER line 32: 3-panel sheet, and two characters in ONE picture | One whole sheet per character | Our crop choice is design-based (W1, W2, W4), not measured. The whole-sheet route is his and MASTER's default | Add a control arm if the owner allows extra clips (top action 10) |
| C5 | Environment | DECISION: no environment picture in REF2VA | Location grid as a tagged reference | Improvement candidate, untested | Test after T0 (top action 9) |
| C6 | Steps and LoRA | DECISION: Pika 6-step, pika_renoise, one LoRA at 1.0 | LoRA and Turbo options are for "a weaker GPU" ([06:33]-[06:46]). Steps not stated. Euler and Simple ([07:37]-[07:41]). The pack's example graph: 20 steps, res_multistep, simple (JSON-NEW nodes 3 and 15) | No direct contradiction. He treats LoRA as a hardware compromise; we treat Pika as the default. Do not cite this video as evidence for Pika quality | Keep the 20-step no-LoRA arm as a later quality test, as DECISION says |
| C7 | Attention | DECISION: Sage not needed for T0; sol fails below SM 8.6 on T4 and A100; sage needs an extra package | Sage Attention on cloud ([06:25]-[06:28]) | No contradiction. Quality note from W4 g2 (another creator): T2V quality "noticeably lower", FL "minimal difference" | If speed is the problem, test Sage on FL shots only |
| C8 | Review gate | Batch per model group (PLAN_v4 amendment 6), owner review after | Approve each scene before the next is built ([09:43]-[10:03]), because scenes are chained | Consistent only while we do not chain | If C3 chooses chaining, add a clip-level approve step |
| C9 | Durations | MASTER line 26: "rounded up to that grid". Code: `frames_for()` rounds to the nearest legal count. 5.2 s gives 124 frames (5.17 s), 4.5 s gives 107 frames, 13.0 s gives 311 frames (12.96 s) | Manual check that durations match ([07:02]-[07:08]) | We are ahead of him. The MASTER text is wrong | Fix line 26 and have the writer emit frames (top action 5) |
| C10 | Shot ids | DIRECTION uses LEAP-01 to LEAP-05. `SHOT_ID` (`h3_director.py` line 58) accepts SHOT-NN, SHOT-NNN, SHOT-NNA only. "LEAP-03" fails. "SHOT-03A" passes | Not applicable | Writers will hit a hard error | Map to SHOT-NN and keep LEAP as `scene_label` (top action 6) |
| C11 | Voice | No voice field in the style bible or the shot JSON | Tagged voice per character | Gap | Add `voices` and `dialogue` (top action 7) |
| C12 | Preflight | Our validate_shots and settings_for run before any Kaggle run | Preflight node "checks the plan before the models load" (README) | Consistent | Keep |
| C13 | Shared prefix | Style text is added after the shot body (`identity_text()`), and KEEP is in the body | Shared prompt goes first, on every scene | Same idea. Order effect untested | Add a validator check that the style and KEEP lines match across shots (top action 8) |

## 9. Table: aspect, what he does, can we use it, where it plugs in, risk

| ASPECT | What he does | Can we use it | Where it plugs into our pipeline | Risk |
|---|---|---|---|---|
| LLM writes the whole blueprint | Cast, sheet prompts, location, shared prompt, scene prompts, durations, tags | Adapt | MASTER gates 1 to 4; shot-list template (section 5); `shot_schema.validate_shots` | The LLM writes durations or ids the validator rejects. Make it write frames and bible ids |
| Shared prefix on every shot | Same block on each scene | Yes, already in code | `style_bible` and `h3_director.identity_text()`; add a validator check | Order effect untested |
| One character sheet, tagged | ChatGPT sheet, loaded and tagged | Yes, already in our form | `flow_sheet_prompt()` (3 panels) to `make_refs.py` to `refs_video/` to DECISION identity (two crops) | Whole sheet versus crops not tested |
| Tags as prompt handles | Tag node; hover to preview | Adapt | Our `<Subject k>` and `<Picture N>` labels; a `cast` id list per shot | Wan2GP label syntax not verified here (W4 a1 covers another creator) |
| Location grid, tagged | ChatGPT multi-angle grid | Adapt, later | Flow ENV plate as an optional third picture; `set` text | Reference limit unverified; identity dilution |
| ElevenLabs voice per character | One audio clip per tag | Adapt the registry only | `voices` in the bible; ElevenLabs stays the voice source | Conditioning unverified; voice-cloning rule for deities |
| Dialogue spoken by H3 from scene text | Dialogue progression in the prompts (MY INFERENCE) | No, for now | Would need an H3 speech test; not in our plan | H3 speech quality unknown; the H3 licence excludes outputs in the US, EU, UK and South Korea (PLAN_v4 amendment 3) |
| Per-scene audio file, lip-sync | Pack rules: 1/24 s start, pad or cut to the scene | Yes, as the fit spec for our ElevenLabs lines | `dialogue` in the shot JSON; Wan2GP `audio_prompt_type` A or AS (after the code check); post | H3 lip-sync is weak (guide row 7); W2 S10 also says lip-sync is weak |
| Durations matched by hand | Manual check | No; we compute | `frames_for()` and `render_frames` | None beyond the MASTER text error (C9) |
| Sampler Euler and Simple | Node setting | No. Pika needs pika_renoise at 6 steps (DECISION; W3) | Nothing | A 20-step arm is a later test |
| Sage Attention | Cloud toggle | Not for T0 | Wan2GP run settings (not in the director) | Quality on T2V (W4 g2, another creator) |
| LoRA, Turbo LoRA, Comfy Kitchen, Model Sampling toggles | Bypass per hardware | No. One Pika adapter, never stacked | Wan2GP `activated_loras` holds one entry | Stacking breaks output (W4 d7; guide source 9) |
| Resume from scene N | Loop Start, start clip | Partly (per-shot queue) | Kaggle queue and manifests (PLAN_v4 P0-C) | None |
| Live preview and stop early | Model Preview Override | No. Kaggle runs headless | None. Whether Wan2GP headless gives previews is not verified | Cost of a bad run |
| Review gate per scene (approve, reseed, stop) | Review Gate | Partly. Owner QA plus seed variants | `t0_variants` seeds 42 and 123; `clip_tools.py qa`; owner watches | Only needed if we chain |
| Scene-to-scene chaining | Chain Context, Trim Carried Overlap (pack) | Test only | Would change the keyframe rule (MASTER line 12) | Drift; W4 f10: an extension can change the voice (T3 [10:59]-[11:04]) |
| Assembly node | Joins the clips | Already have it | `post.py` and ffmpeg | None |
| RunningHub hosting, Gumroad pack, Sea Dance 2.5 | Hosted cloud | No | Not applicable | Licence, cost, not ours |

## 10. Top 10 actions, ranked

GPU runs need the owner's go (PLAN_v4 rules).

1. Put the dialogue test back in the queue. One close-up with one Hindi ElevenLabs line. Compare H3 kept-soundtrack (audio_prompt_type "A" or "AS", per mode) with Flow mouth-shape edits. Pass: lips follow the line, face and costume unchanged, no speech from H3, no rim light on faces. Cost about 0.5 GPU-h (PLAN_v3 estimate).
2. Before writing any dialogue code, verify in the pinned Wan2GP code (commit bd1ff59) what audio_prompt_type "A" and "AS" do for MiniMax H3 FL2VA and Ref2VA. Record each finding as VERIFIED, FAILED or UNTESTED. This blocks actions 1 and 7.
3. Rewrite the DECISION Audio row. H3 generated sound is ignored. Dialogue is an open test (action 1). Voice references are not used in the current director. This resolves C1.
4. Decide the continuity rule per shot class and write it into DECISION and MASTER line 12. Identity-critical shots use Flow start and end keyframes. Continuation shots use chaining only after a test. Until then, keep LEAP-03 to 04 and 04 to 05 as cuts, and treat LEAP-02 to 03 as the one match that may need a test (DIRECTION lock 4).
5. Fix MASTER_PROMPT_v2.1.md line 26. It should say the duration is rounded to the nearest legal count (for example 5.2 s gives 124 frames, 5.17 s). Have the writer emit `render_frames` and `edit_frames` directly. Covers C9.
6. Map DIRECTION's LEAP-NN names to SHOT-NN ids in the shot list. `SHOT_ID` rejects LEAP-03. Keep the LEAP name in `scene_label`. Covers C10.
7. Add a `dialogue` list to the shot JSON and a `voices` map to the style bible, with designed ElevenLabs voices only (no cloning for deities). The validator checks that each speaker id is in the bible. The director puts "no rim light on faces" into dialogue prompts. Implement only after action 2.
8. Add a validator check that `prompt_prefix` (style line plus KEEP) is identical across all shots of one project. Cheap, and it guards the shared-prefix idea (C13).
9. After T0, test an environment plate as a third reference on a non-identity shot. Check the Wan2GP reference limit in the pinned code first. Measure identity and costume drift, and whether the kadamba bank stays consistent (C5).
10. If the owner allows two or three extra clips, run a control: one three-panel identity sheet as a single reference against the two crops, same seeds, on one shot (C4).

## Appendix A: node name mapping (video to pack)

| Video name [time] | Pack README name | Pack JSON title (JSON-NEW / JSON-OLD) | Match |
|---|---|---|---|
| Prompting node [06:47] | Plan (Modern) / Plan | "Production Plan" (NEW 24); "REF2V BASIC PLAN" (OLD 2016) | Likely |
| Tag nodes, character, location, voice [04:44]-[05:47] | Tagged registry, tagged references | No tag node in either JSON. The tagged examples are not in our folder | Likely, unverified |
| Audio nodes [05:26] | Per-scene lip-sync audio file from the Carousel | No LoadAudio node in either JSON | Unverified |
| Scene Prompt Editor [07:11] | Scene Prompt Editor | "Scene Prompts" (NEW 6); "SCENE PROMPT EDITOR" (OLD 1993) | Exact |
| Loop Start Resume, Start Clip [07:43] | Loop Start, start_clip | "Loop Start" (NEW 7, value 1); "LOOP START / RESUME" (OLD 1995) | Exact |
| Model Preview Override [08:01] | Not in README | Not in either JSON | Not found |
| Review Gate [08:21] | Review Gate | "Review Candidates" (NEW 28); "REVIEW GATE" (OLD 1996) | Exact (NEW title differs) |
| Save Segment [09:36] | Segment + Checkpoint | "Save Segment + Checkpoint" (NEW 20) | Exact |
| Assembly node [10:37] | Assemble | "Assemble Final Video" (NEW 21) | Exact |
| Sage Attention [06:26] | Not in README | Sage patch nodes (OLD 1986, 1990); NEW uses "pytorch attention" (22) | Present |
| LoRA, Turbo, Comfy Kitchen, Model Sampling bypasses [06:39] | Not in README | LoraLoaderModelOnly (OLD 1985); Comfy Kitchen ModelAttentionBackend, bypassed (OLD 1987); Sigma Shift [12, 3] (NEW 13) | Partly. No "Turbo" node found |
| Sampler Euler, Simple [07:37] | Not in README | KSamplerSelect "res_multistep" (NEW 3); BasicScheduler "simple", 20 steps (NEW 15) | Sampler differs (video: Euler) |
| Generation Profile (not in video) | Two controls: continuity and audio | "Visual continuity", "Generate audio" (NEW 30) | Exists; his setting not shown |

The version of the pack in his video is not stated. The README describes 0.7.3. JSON-OLD carries 0.5-era titles (for example "0.5 PREFLIGHT") and JSON-NEW carries the 0.6 release note. Some names changed between versions.

## Appendix B: discrepancies and checks

- Chapters: the description's "Multi-voice consistency" starts at 7:00 (420 s). The voice nodes appear at [05:26]-[05:47], and 7:00 is where prompt entry starts. "Full walkthrough" at 9:00 matches [09:08]-[09:12]. info.json chapters match the description list.
- Whisper: "Akio" versus "Q" and "Accio"; "Sea Dance" versus "Seedance2.5".
- Teaser lines at [00:22]-[00:26] ("Eyes up, Borne...") and "S-Gen-Re!" at [00:49] are not tied to the Akio and Elder demo. The transcript does not say what they are.
- Title "Unlimited": not explained in the transcript; see section 1.
- Not checked: the Wan2GP code for audio_prompt_type behaviour (only PLAN_v3, W1 and W3 notes exist). This is action 2.
- Not used: the eSDey7wAK60 files and tr.log in the same folder.
