# DECISION: where do the H3-only shot fields come from? (owner asked "what is the proven way", 2026-11-07)

## Evidence from the repo (git log 2026-11-04..07, files read)
1. h3/e2e_sample.py (commit 55df3d2, 2026-11-06): the H3 story JSON is NOT written by the story writer. A separate step gives a model a FIXED timing/seam blueprint, the model writes the content, `lint_story` checks it and the exact lint messages go back for up to 4 repair rounds. That is the only authoring pattern in the repo for these fields (offline path tested; the live free-model run was a sample, not a production run).
2. director/h3_director.py (builds the Wan2GP settings per shot; the production renders were run on COLAB, e.g. the T0 clips via director/t0_pack/run_t0_parallel.py and colab_batches/; docs also record one early Kaggle T4 test on 2026-11-04, owner corrected: all real renders were Colab) consumes plain shot rows (id, mode, seconds, start/end frames, refs, subjects, action, camera, sound). It needs none of the pose/seam fields. Those fields belong to the newer h3/ ComfyUI sing8 engine only.
3. The owner's V4 spec (OWNER_MASTER_PROMPT_V4) asks the writer for the 6-column shot table and says nothing about pose vectors, biomechanical tags, cadence windows or handles. The official MiniMax skill also keeps shot table (story step) and per-shot prompt (render step) as separate steps.
4. h3/schema_and_linter.py seam rules (CN-02..CN-06): static seams (CHAINED / INTER_REEL) need trim_out == pixel_frames and handles 0; DYNAMIC seams need head handle in [8,35] and tail handle in [24,47]. So the V4 "trimmed editorial duration" (Col 1) is DERIVABLE: editorial == pixel_frames means static; editorial < pixel_frames means a dynamic cut whose handles add up to pixel_frames - editorial.

## Options weighed
- Writer emits all H3 fields: bloats stage 3 for 50+ shots on free models, mixes story work with engine internals, each rewrite of a shot would force a rewrite of engine fields. Rejected.
- Converter fills defaults (zero pose vectors etc.): invents data the linter then trusts; a wrong pose vector breaks cut-on-action matching silently. Rejected.
- CHOSEN (three tiers): 
  1. DERIVE (deterministic, no invention): trim/handles/seam types from editorial vs pixel_frames and shot position; location_id from fixed_landmarks ENV id; props_present from ids already in the row; story_beat from the row's own purpose/continuity text; boundary frames from the Flow keyframes folder.
  2. AUTHOR (model, per shot, after Gate A and after images exist, before render): pose vectors, biomechanical tags, cadence windows, shot scale, screen direction, camera axis, horizon, emotional objective. Free models only (Super VL on OpenRouter or Nemotron Ultra via the 14-key scheduler), exactly the e2e_sample loop: fixed blueprint in the prompt, lint, max 4 repair rounds, result cached per shot by hash so any upstream edit invalidates it (asset manifest rule).
  3. REPORT: anything still missing is a precise problem, never a silent default; Gate C does not open while problems remain.
- Writer stays unchanged.

## Not decided here / owner
No live model call is made by this change (tests inject a fake caller). Running the author step for real needs the free-model go as usual. No Colab, no render.
