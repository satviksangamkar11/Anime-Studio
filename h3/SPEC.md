# h3/: H3 (MiniMax H3, Route C "sing8") compiler, linter, render gate, Gate D audio plan

Status 2026-11-07. Pre-render and planning only in this folder: no Flow, no Colab, no GPU, no ffmpeg run, no ElevenLabs
call, no network. The engine reads any story/episode JSON; no story is hardcoded and no live Flow chip name changes.
Python 3.14, stdlib + Pillow. Tests: `cd "D:\aai work\anime_studio"`, then `python -m pytest -q -p no:cacheprovider h3`.

## 1. Design (owner option A, final 2026-11-07)
- The video is rendered ONCE: one shared pure-Foley H3 render. H3 makes diegetic sound effects only (SFX/Foley), frame
  synced. The narrator's mouth stays closed in every shot. H3 carries no speech.
- Voices for en, hi and mr are ElevenLabs VO files added AFTER the render and after Step 9 QC. They are supplied by the
  owner as `audio/vo/<lang>/<shot_id>.wav`. The code never calls ElevenLabs.
- One final reel per selected language (`export/<reel>_<lang>.mp4`), all from the same video and the same SFX stem.
- Background music is off by default. Optional: one continuous licensed track from `audio/bgm_manifest.json`.
- Consistency of a voice across shots and reels: the bible `voice_map` (fixed voice id per character per language;
  `NARRATOR` for the off-screen narrator).
- OPTIONAL English H3 voice switch (`voice_engine.en = "h3"`), OFF by default. It is a second English render with
  H3's built-in voice. Only en can use it; hi and mr never use H3 speech. The details (anchors, speaker map, audio
  reference rules) belong to EV: see `h3/voice_engine.py` and `research/EN_H3_VOICE_CONSISTENCY_2026-11-07.md`.
  Turning it on adds a second H3 render and cost. The plan says so in a warning.

## 2. Story file (input JSON)
```
{ "registry": { "execution_profile": {...}, "style_lock": {...}, "characters": {id: {"short_disambiguator": str}},
                "voice_engine": {optional, see 8}, "voice_map": {optional, see 8} },
  "episodes": [ { "episode_id": "EP_01", "asset_root": "<dir with the picture paths>", "shots": [ <shot>, ... ],
                  "episode_plan": {optional} } ] }
```
Output languages (`output_languages`, a subset of en/hi/mr in priority order) are set by the writer on story.json;
the plan reads them from the story, else uses `["en"]`.

## 3. Execution profile
Profile files: `h3/profiles/sing8_864x1536.json`, `sing8_768x1344.json` (`registry.execution_profile`). A story may
override it.
- `model_sampling_av`: `video_shift` = `{"keyframe": 6.0, "ref2va": 12.0}` and `audio_shift` = 3.0. These are
  profile parameters: `h3/router.video_shift_for(profile, route)` picks 12.0 for Ref2VA and 6.0 for every other mode.
  Old `mode_to_video_shift_map` text is removed.
- `fps` 24, `aspect_ratio` "9:16", `base_resolution` [864,1536] (or [768,1344]); both divisible by 32.
- `valid_lattice_n_range` [6,20]; `max_total_prompt_chars` and the LEN-01 limit of 7000 characters.
- `style_lock`: `mandatory_prefix`, `banned_style_tokens`, optional `banned_negative_words_regex` (prose matches are warnings).

## 4. Shot row (V4 contract)
The full V4 row is in `research/H3_V4_CONTRACT_2026-11-07.md`. Columns: id, episode, route (one of the 5 modes),
lattice_n, pixel_frames, latent_slots, editorial_duration_sec, continuity_handoff, reference_anchors, hook_type,
is_opening_0_2s_hook, is_closing_hook, deliberate_flip_marker, per_second_directives, and
`audio_and_dialogue_track` = narration (+ `narration_by_lang`), dialogue, sfx_cues, performance_notes
(`narrator_mouth_closed: true`, `mouth_state` per second: "closed" or "open_non_verbal_breath").
The H3 linter and compiler still read the older shot layout (timing_and_lattice, fl2va_keyframes, sound_plan,
dialogue_and_lip_lock). The V4 row is accepted by the director validator; the H3 side of V4 is not converted yet
(see the GAP in section 11).

## 5. Routing: 5 modes (`h3/router.py`)
`route_shot(shot)` returns one of T2VA, I2VA, L2VA, FL2VA, Ref2VA:
- any audio reference -> Ref2VA (the only mode with documented audio refs);
- reference cards and no boundary pair -> Ref2VA;
- both boundary frames -> FL2VA; start only -> I2VA; end only -> L2VA; none -> T2VA.
`ref2va_limit_problems(shot)`: at most 9 image refs (RF-01) and 3 video refs (RF-02); 0 audio refs in pure-Foley mode (AU-01).

## 6. Prompt locks and lint codes (`h3/schema_and_linter.py`, `h3/compile_h3_sing8.py`)
The compiler refuses speech in the source (`refuse_speech_in_source`). The linter reports these codes:
- Speech (SL): SL-01 speaker id such as `(S1)`; SL-02 `[Language]` tag; SL-03 `<d>...</d>` wrapper; SL-04 speech in the source.
- Audio (AU-01): `<Audio N>` tags. Tags (TG-01): Flow chips (@CHAR-*, SHEET-*, ENV-*, STYLE-*) or bracket storyboard tags.
- Text (TX-01): unrequested on-screen text in double quotes.
- Length (LEN-01): prompt over 7000 characters.
- Mouth (MO-01): `narrator_mouth_closed` must be true and `mouth_state` must be present; the closed-lips lock sentence is always emitted.
- Sound (SX-01): every action sentence of the 7 stages needs a sound cue (`SX_MIN_STAGE_CUES = 7`); the soundscape is 1-4 English sentences.
- Refs (RF-*) and workflow (WF-*) codes as in section 5 and 9.
In pure-Foley mode the prompt carries no speaker id, no dialogue tag and no `<Audio N>`. `non_diegetic_music` is `N/A` on every shot.

## 7. Compiled prompt
One prompt per shot. FL2VA shots use the 4-part layout; Ref2VA shots use the 6-section layout
(`REF2VA_SECTIONS`: subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape,
non_diegetic_music). Every free-text field goes through `sanitize_single_line` before it is built and before it is checked.
Dialogue and speech blocks are NOT part of the H3 prompt any more.

## 8. Voices and Gate D (`h3/voice_engine.py`, `h3/voice_manifest.py`, `h3/gate_d_audio.py`)
- `voice_engine` per language: default `{"en": "elevenlabs", "hi": "elevenlabs", "mr": "elevenlabs"}`. The only other
  allowed value is "h3" for en (section 1). Owner-set, stored in the registry.
- `voice_map`: `{"CHAR-x" | "NARRATOR": {"en": id, "hi": id, "mr": id}}`, checked by `voice_map_problems` (VM-*).
- Wav manifest (`h3/voice_manifest.py`): per language and shot: path `audio/vo/<lang>/<shot_id>.wav`, sha256, duration
  (stdlib wave), voice ids (narrator and speakers from voice_map), VO-fit result (wav <= editorial - 0.10 s,
  `VO_OVERFLOW_ERROR`), `VO_MISSING` when narration exists but the wav does not. A changed shot text makes its entry stale.
  CLI: `python -m h3.voice_manifest --vo-root <dir> --shots <json> --lang en,hi [--voice-map <json>] [--out <json>]`.
- Gate D (`plan_language_outputs`): one plan per language: VO stem, 3-stem mix (SFX, VO, optional BGM), `.ass` captions
  (6 words per card, font per language), mux with burned-in captions, `loudnorm` master at the pipeline loudness standard (core/core.json delivery.audio: -16 LUFS, loudnorm TP -1.3 dB, ceiling -1 dBTP).
  Dead-air, hook and closing checks run per language. Nothing runs ffmpeg; the plan is argv and text only.
- Post-AAC loudness check: `check_post_aac_loudness` on the exported mp4 (-16 +-0.5 LUFS, true peak <= -1 dBTP; read from core/core.json).
- Easy language: every spoken line and caption is easy English, Hindi or Marathi (`director/simple_language.py`).

## 9. Render, QC and fallback
- Asset manifest (`h3/asset_manifest.py`): each clip is keyed by five hashes: bible (whole registry), shot row,
  start frame, end frame, model id (`h3-singularity-v2`). A stale hash, a missing clip, an orphan clip, an unlogged
  model switch or an unresolved `placeholder: missing clip` blocks assembly.
- Resolution ladder (`render_plan`): pass 1 at 864x1536 (Seedance 1080x1920); pass 2 at 1440x2560 only for approved clips.
- Fallback ladder (`h3/fallback_policy.py`): failure 1 = regenerate with the Reference Anchors prefix; failure 2 =
  shorten to <= 6.0 s, split rows, re-run self_check; failure 3 = switch to Seedance 2.0 (logged in the manifest);
  failure 4 = human gate with `HUMAN_CHOICES`. Rung 4 never re-renders.
- Step 9 QC (`h3/step9_qc.py` `final_qc`): SFX alignment to sfx_cues (tolerance 0.25 s, a parameter), visual
  continuity, closing payoff, no storyboard labels on screen. It fails closed: a missing or failing measurer is a failed check.

## 10. Ordered pipeline plan (`h3/pipeline_contract.py`, `render_controller.plan_pipeline`)
`plan_pipeline(story, groups, out_root, *, languages=None, render_results=None, qc_measurers=None)` is a DRY RUN. It
never renders, calls no backend and writes no file. Steps in order, each with status `ready`, `blocked` or `pending`
and a list of reasons:
1. lint: linter, profile and paths. 2. route: route per shot, Ref2VA limits. 3. prompt: compile per shot.
4. manifest: hashes current, no missing or placeholder clips. 5. fallback: no shot waiting at the human gate.
6. render: successful render for every shot (pending until `render_results` is given). 7. step9_qc: final QC (runs after render).
8. gate_d: Gate D plan for every selected language. 9. assembly: ready only when steps 1-8 are all ready.
10. loudness: post-AAC check (pending until the mp4 exists; it never blocks assembly).
`build_plan(results)` and `assembly_allowed(steps)` are pure. The UI reads the list.

## 11. Known gaps (do not hide)
- No converter from a V4 pack (shot rows + bible) to an H3 story (registry + episodes). `flow/scripts/pack_to_spec.py`
  reads the legacy Flow pack and writes the Flow image spec. `h3/tests/test_pack_to_spec_contract.py` pins this.
- The H3 linter still reads the older dialogue and timing layout beside the V4 row. Converting the linter to the V4
  layout is open.
- Ref2VA reference_images node input is unverified against a real ComfyUI.
- Caption placement uses a character-width estimate, not libass measurement. The caption font files are not bundled.

## 12. Public API (fixed names)
- `h3/schema_and_linter.py`: `sanitize_single_line`, `lint_story(story)`, `lint_profile`, `resolve_keyframes`,
  `read_png_dimensions_on_disk`, `picture_path_problem`, `voice_mode`.
- `h3/router.py`: `route_shot`, `ref2va_limit_problems`, `ref2va_limits_ok`, `video_shift_for`, `workflow_mode`.
- `h3/compile_h3_sing8.py`: `compile_fl2va_prompt(shot, registry)`, `compile_comfyui_workflow(...)`, `compile_episode(...)`.
- `h3/assemble_reel.py`: `build_ffmpeg_assembly_plan`, `write_assembly_script`. Never runs ffmpeg.
- `h3/render_controller.py`: `prepare`, `plan_pipeline`, `main`, `register_backend`. The only backend is `none`.
- `h3/fallback_policy.py`: `next_action`, `record_attempt`, `load_history`. `h3/asset_manifest.py`: `blocking_problems`,
  `render_plan`, `load_manifest`. `h3/step9_qc.py`: `final_qc`.
- `h3/gate_d_audio.py`: `plan_language_outputs`, `vo_fit_check`, `check_post_aac_loudness`. `h3/voice_manifest.py`: `build_manifest`, `stale_entries`.

## 13. CLI and tools
- Controller: `python -m h3.render_controller --story-file STORY.json --scope shots --ids A,B` (also `--scope reel --episode EP`,
  `--scope all`), `--dry-run`, `--allow-partial`, `--second-pass`, `--out-dir`. Exit 0 clean; 1 blocked, bad scope or
  bad story; 2 refused usage; 3 execute gates passed, no backend started. Writes per episode: readiness.json and,
  when clean, prompt.txt, workflow.json, filter.txt, assemble.cmd. Every workflow carries `_unverified_node_classes: true`.
- E2E sample: `python -m h3.e2e_sample --offline` (built-in valid story, no model call). The live mode is separate and
  uses only the approved text model through the scheduler. The sample's shots carry explicit `narrator_mouth_closed: true`
  and per-second `mouth_state`.
- Voice manifest: `python -m h3.voice_manifest ...` (section 8).

## 14. Tests
`python -m pytest -q -p no:cacheprovider h3` (h3 suite). Tests are offline and use synthetic fixtures (`h3/tests/synth.py`).
New with this refresh: `test_render_controller_wiring.py`, `test_voice_manifest.py`, `test_pack_to_spec_contract.py`.
