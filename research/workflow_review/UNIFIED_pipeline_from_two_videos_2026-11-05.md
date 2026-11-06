# Unified pipeline: what the two videos add to the anime studio (2026-11-05)

Sources: V1 `JndCXtuU7-I` (The AI Brief, "Unlimited Anime Pipeline", 12:51, transcribed locally with Whisper) and V2 `eSDey7wAK60` (AiNinja94, "MiniMax H3 Context Loop Explained") with its two workflow JSONs (32-node NEW, 48-node OLD). Full analyses: `V1_unlimited_anime_pipeline.md`, `V2_context_loop.md`. Both are Haiku-xhigh reports; Claude re-checked the code claims marked CHECKED. Everything else is the agents' reading of the sources, unmeasured by us.

Limits: V1's own workflow (RunningHub / Gumroad) is not available, so it is reconstructed from speech. V2's transcript has no captions from 00:09 to 02:04. The two JSONs we hold are example graphs (courier / Doom demos), not an anime graph. The Context Loop node pack is GPL-3.0: reimplement ideas, never copy its code.

## The one-line answer
Both videos are ComfyUI pipelines. Our Wan2GP + director + ffmpeg pipeline already has their core (shared style prefix, two refs per character, one-shot-at-a-time rendering, Pika 6-step). What we should take is the **orchestration layer**: shot-list generation by an LLM, a join rule between shots, a per-run manifest, recovery/assembly in post, and an owner gate. We should NOT take their sampler/LoRA/latent-carry parts.

## What we use, adapt, and skip
| Aspect | From | Decision | Plugs into |
|---|---|---|---|
| Shared prompt prefix on every shot | V1, V2 | Already in code; add a validator that the prefix is identical across a project | `style_bible`, `h3_director.body_for`, `shot_schema` |
| One character sheet, 2 refs (face + body) | V1, V2 | Already adopted (DECISION) | `make_refs.py`, `refs_video/` |
| LLM writes the blueprint (cast, shots, durations) | V1 | Adapt: the writer emits our shot JSON with `render_frames` and bible ids, never free durations | MASTER gates, `shot_schema.validate_shots` |
| Chain policy "Cut" | V2 | YES: the leap is 5 hard cuts, each from its own Flow keyframes | director default |
| Chain policy "Guide" (carry ~22 motion frames) | V2 | ADAPT, test only: use the last frame of shot N as the start keyframe of N+1 for continuous-action shots | director `join` field, runner, `clip_tools last_frame` |
| Latent overlap carry (Apply Scene Context) | V2 | NO: ComfyUI latent state, not reproducible in Wan2GP | - |
| Trim carried overlap / de-dup frame at a join | V2 | ADAPT: `edit_start` + `edit_frames`, dropped in ffmpeg | director, `post.py` |
| Crossfade 12 frames | V2 | Optional, off by default | `post.py` (xfade) |
| Save segment + checkpoint + manifest | V2 | ADAPT: `manifest.json` per run (settings hash, mp4 hash, last frame, seconds, VRAM) | `run_kaggle.finish()` |
| Resume from scene N / regenerate one scene | V2 | ADAPT: `--ids` from the first unfinished shot using the saved last-frame PNG | runner |
| Review gate per scene (approve / retry / reroll) | V2 | ADAPT: owner OK between chained shots; `clip_tools qa` first; `visual_qa` triage only | runner `--fetch` flow |
| Final assembly + recovery from saved files | V2 | YES: `post.py` concat in manifest order, assemble-only mode | `post.py` (not built) |
| Multi-voice per character (voice clip per tag) | V1 | ADAPT the registry idea only: a `voices` map in the style bible for ElevenLabs; H3 speech is untested | style bible, post |
| Per-scene audio fit (1/24 s start, pad or cut) | V1 | YES as the spec for ElevenLabs line length | shot JSON `dialogue` field (later), post |
| Location grid as extra reference | V1 | LATER: test an environment plate as a 3rd ref on a non-identity shot | T1 test |
| Tags as prompt handles | V1 | Already our `<Subject k>` / `<Picture N>` | `h3_director` |
| Euler + simple, 20 steps, LightX2V turbo, Sage, NVFP4 TE | V1, V2 | NO: our single Pika adapter, `pika_renoise`, 6 steps; Sage/NVFP4 not for T4 | DECISION |
| Reference-video guidance (Wan2GP V-U) | V2 | TEST ONLY if last-frame chaining fails on a continuous shot | director (new optional field) |
| RunningHub / Gumroad / Seedance | V1 | NO (hosted, paid, licence) | - |

## Rules for the leap reel (from both videos)
1. Five keyframe-driven hard cuts. No chaining across any LEAP join (03->04 apex cut, 04->05 contact cut, W4 tip 10).
2. H3 audio dropped (`-an` on H3 clips); ElevenLabs/SFX in post.
3. Same style+KEEP prefix on all five shots; same two refs on shots with Krishna.

## Verified by Claude in the code (CHECKED)
- `SHOT_ID` in `h3_director.py:58` accepts only `SHOT-NN[A]`, so `LEAP-03` is rejected. Map LEAP-0N -> SHOT-0N (keep the LEAP name as a label).
- The writer brief said durations are "rounded up"; the code rounds to the NEAREST legal count. Brief fixed (`MASTER_PROMPT_v2.1.md` line 26).
- `frames_for_shot` validates `edit_frames` but does not say which end is kept (agents' claim; consistent with the code read earlier).

## Code changes proposed (none made yet; each is small)
1. `join` field per shot: `cut` (default) or `chain` (start = previous shot's last frame). Runner extracts the PNG after the previous shot finishes.
2. `edit_start` next to `edit_frames` (which frames post keeps).
3. Validator: prompt prefix identical across a project; LEAP-NN accepted as scene label while ids stay SHOT-NN.
4. `manifest.json` written by the runner.
5. `post.py`: concat in manifest order, apply `edit_start`/`edit_frames`, drop H3 audio, map our audio, assemble-only recovery mode.
6. Later: `dialogue` list in shot JSON + `voices` map in the style bible, only after a Wan2GP audio check (what `audio_prompt_type` A/AS do on H3) and one dialogue test (~0.5 GPU-h).

## Open tests (need the owner's go, GPU)
- T0 (LEAP-03, 4 clips) as already planned.
- T0-chain: render one shot from the LEAP-03 winner's last frame; measure frame-0 match, face match, motion jump, colour drift.
- Dialogue test: one close-up, one Hindi ElevenLabs line, H3 kept soundtrack vs Flow mouth edit.
- Environment plate as 3rd reference; single 3-panel sheet vs two crops.
