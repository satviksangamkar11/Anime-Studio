# W-08: does input_video_strength survive to the end frame? (Wan2GP pin bd1ff59)

Source: `D:\aai work\kaggle_h3_test\wan2gp_src`, read only. Pin check: `.git/HEAD` is `ref: refs/heads/main`, and `.git/refs/heads/main` = `bd1ff5903cbc18b46c3cce3b75bd140870b536a2` (the pin in `director/run_kaggle.py:23`). The card's "HEAD equals the hash" is true only after resolving the symbolic ref. Enforced by `director/test_wan2gp_pin_trace.py::test_pin_matches`.
Test: `director/test_wan2gp_pin_trace.py` (17 tests, all pass; source-dependent ones skip with a reason when the folder is missing).

## Proven by the pinned source (file:line)

1. **Our side drops it first.** `director/h3_director.py:310` `settings_for` builds a fixed dict (347-356). The key set has no `input_video_strength` and no `image_end_frame_position`. Any strength on a row is lost here. Test: `test_settings_for_drops_strength`, `test_our_settings_key_set_is_fixed`.
2. **The CLI path pops it.** `--process` at `wgp.py:15199` (`_parse_settings_json`, def 2248), then `validate_task` at 15223 (def 9662). Inside it, `clean_settings(model_type, inputs)` at 9734 (def 1987) calls module `fix_settings` at 1993. That dispatches to the handler at `wgp.py:3500` (def 3349). The handler's `fix_settings` (`models/minimax_h3/minimax_h3_handler.py:1359-1360`, class `family_handler` at 546) runs `ui_defaults.pop("input_video_strength", None)`. `update_default_settings` (1415-1416) does the same.
   - Card correction: the card cites 1993 as the handler call. 1993 is the module-level call, and the handler pop is reached through 3500.
3. **The H3 model_def has no strength entry.** The only two mentions of `input_video_strength` in the handler are the two pops (1360, 1416). So the setting has no label.
4. **Strength is forced to 1.0.** `wgp.py:940-945` `input_video_strength_visible` is True only when the model_def label is non-empty and the image prompt type has S, V, L or E (or an injected frame). H3 has no label, so it is False. `validate_settings` (def 1123) reads `inputs.get("input_video_strength", 1.0)` at 1297, then sets `input_video_strength = 1.0` at 1510-1511 when not visible. `validate_task` applies the result at 9744 (call) and 9747 (`inputs.update`).
5. **Strength reaches generate as 1.0.** `generate_media` (def 7380) passes it on at `wgp.py:8788`.
6. **The pipeline can soften the end, but nothing sets it.** `models/minimax_h3/pipeline.py:787` default `input_video_strength=1.0`. Line 967 sets `soft_anchor_timestep` below `VISUAL_COND_TIMESTEP`. Lines 1010, 1012, 1014 and 1016 apply it to the end image and injected frames. This is the only place a soft end exists in the pin.
7. **End position is computed, not a setting.** `wgp.py:8262` `tail_trim_frames = discard_last_frames + automatic_trim_last_frames`. Line 8317 `end_image_before_discard = model_def["end_image_before_discarded_frames"] and window_no < total_windows`. Line 8318 `image_end_frame_position = current_video_length - (automatic_trim_last_frames if end_image_before_discard else tail_trim_frames) - 1`, only when the model_def sets `image_end_frame_position`. The H3 model_def sets it at handler:767, and `end_image_before_discarded_frames` at handler:765.
   - Correction to the card: the card says `video_length - tail_trim - 1` for all windows. The code uses `automatic_trim_last_frames` for non-final windows (8317-8318). The formula equals the card's only for the final window.
   - No input reads it: `inputs.get("image_end_frame_position"` occurs 0 times in `wgp.py`.
8. **Settings-save pop is not on the generation path.** `prepare_inputs_dict` (def 10474) pops the key at 10516-10517, only when `target == "settings"`. It is a save/serialise step.

## Not proven

- No run. This is a source trace. It does not show what the model does with a soft anchor, nor the visual result.
- Whether the frame at 8318 is the cut point for our handle plan. The formula is proven; the "end of the tail handle" reading in the card is an inference from that formula, not checked against the trim logic beyond 8262-8318.
- The Gradio UI path (load settings, `fix_settings` at 11189 and 3542) is not traced in full. The test covers the `--process` path.
- Other Wan2GP commits. The result is for bd1ff59 only.

## Consequence for the wiring cards

- **Hard fact:** on this pin, SOFT_SE and KFI (input strength below 1.0) render as a hard SE. Putting the key in the task JSON does nothing, because the handler pop (1360) runs before validation, and validation forces 1.0 (1511).
- **W-09 (build_h3_batch rows):** the refusal `"<sid>: route <r> needs input_video_strength <v>, which Wan2GP bd1ff59 drops"` matches this trace. Under D4 (a) the soft routes become hard SE, as the card says. Test shape: `test_soft_se_refused_until_d4`.
- **W-10 (soft end by VM handler patch) is conditional on D4 = b.** The card's patch removes both pops (1360, 1416) and adds a label after line 767. Both changes are needed. The label makes `input_video_strength_visible` True for an E image prompt (940-945), which skips the forcing at 1510-1511. Removing only the pops is not enough. The strength then reaches the pipeline soft anchor (967, 1010-1016). This is still unproven on the model, so it needs the paid one-shot A/B canary the owner must approve. The end position stays a separate item: no setting places B at the cut (8318 decides it), so W-10 point 4 holds.
- **Owner decision D4:** (a) recommended now: soft routes render as hard SE on bd1ff59. (b) only after this note is read: the handler patch above plus the canary. (c) move the pin, which this trace does not evaluate.

## Reproduce

`python -m pytest director/test_wan2gp_pin_trace.py -q` from `D:\aai work\anime_studio_merge`. Read-only on the source folder.
