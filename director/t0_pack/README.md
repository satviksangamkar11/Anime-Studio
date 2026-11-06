# T0 pack: LEAP-03, four arms x two seeds

Built 2026-11-05. Nothing has run on Colab or Kaggle yet: no GPU, no paid call, no model download.
Plan: `research/workflow_review/DECISION_best_workflow_2026-11-05.md` (RETHINK addendum, the 4 arms).

## The 8 clips

All: 9:16, 768x1344, 124 frames (5.17 s), start = LEAP-03A, end = LEAP-03B, CFG 1, flow shift 12, one phase, seeds 42 and 123.

| Clip id (x2 seeds) | Arm | Mode / route | Model (Wan2GP) | Speed LoRA | Sampler, steps | Identity |
|---|---|---|---|---|---|---|
| SHOT-T0-A-S42, -S123 | A, baseline | ref2va / pika6 | H3 Ref2VA pruned | official Pika 6-step | pika_renoise, 6 | face + front refs, keyframes |
| SHOT-T0-B-S42, -S123 | B | ref2va / sing4 | Singularity v2 pruned | Pika-Labs Turbo 4-step | euler, 4 | face + front refs, keyframes |
| SHOT-T0-C-S42, -S123 | C | ref2va / sing8 | Singularity v2 pruned | Pika-Labs Turbo 8-step HD | euler, 8 | face + front refs, keyframes |
| SHOT-T0-D-S42, -S123 | D | fl2va / pika6 | H3 FL2VA pruned | official Pika 6-step | pika_renoise, 6 | keyframes only (no refs) |

## What each arm answers

- **A vs B:** does Singularity v2 beat the proven H3 Ref2VA on the same refs and keyframes? The DECISION note quotes the Wan2GP README: "clearer fast action, sharper distant faces and less glossy skin". The LEAP-03 wide shot has small faces, so this is the test.
- **B vs C:** does the 8-step HD Turbo beat the 4-step Turbo enough to pay for twice the steps?
- **A vs D:** do identity refs add anything to start and end keyframes, or do the keyframes already hold the face?
- **Seed 42 vs 123:** a difference between clips with the same arm is seed noise, so no conclusion from one seed.

## Files in this folder

- `t0_base_shot.json`: the base shot (id SHOT-03, LEAP-03 action and camera from `milestone_leap/DIRECTION.md`, style and identity from `style/kaliya_mardan.json`).
- `keyframes/`: copies of the four named PNGs. Originals untouched: `LEAP-03A__candidate_v01.png`, `LEAP-03B__candidate_v01.png` (final, 1536x2752), `CHAR-KRISHNA__ref_face.png`, `CHAR-KRISHNA__ref_front.png`.
- `t0_shots.json`: the 8 expanded shots, from `python ..\t0_variants.py t0_base_shot.json t0_shots.json kaliya_mardan --arms`.
- `../colab_batches/t0/run.py` and `run.ipynb`: the batch, from `python ..\run_kaggle.py t0_shots.json keyframes t0 --target colab --style kaliya_mardan --profile 5` (run in this folder). Embedded images total about 5.2 MB raw, about 7.1 MB in the script, under the 20 MB cap.
- `run_t0_colab.py`: the Colab wrapper (dry run by default).
- `results/`: created by the wrapper on a real run.

## How to run

1. **Dry run first (safe, prints only):** `cd D:\aai work\anime_studio\director\t0_pack` then `python run_t0_colab.py`.
2. **Real run (spends compute units):** the Colab CLI README says **Linux and macOS only**. On Windows the first command is expected to fail. From Linux or macOS: `python run_t0_colab.py --go --gpu G4`. The wrapper runs `colab usage`, `colab new`, `colab exec` of run.py (timeout 6 h), a list step, downloads only the .mp4 files plus `timeline.txt`, `RESULT.json` and `gpu.csv`, and `colab stop` in a finally block. It does not retry.
3. **Score:** `python ..\clip_tools.py qa results\SHOT-T0-A-S42\<file>.mp4 results\qa` writes the first/middle/last sheet and a JSON (frames, fps, loudness).
4. **Manual fallback without the CLI:** upload `colab_batches\t0\run.ipynb` to Colab, pick the GPU, Run all. Clips land in `/content/out`.

## Cost and time (estimates, not measured)

- Compute: one session. The research notes estimate about 1 to 1.5 h and about $1 to 1.5 for one G4 session (`research/OPUS_REVIEW_GEMINI_T4_PLAN_2026-11-05.md`, section 5). A 2024 figure gives G4 about 8.7 units/h (`research/PLAN_LOW_VRAM_QUALITY_2026-11-05.md`). Check the balance with `colab usage` before and after.
- Downloads: 40 to 60 GB of weights per new session (research note). The Kaggle run measured 49 GB in about 7 min (`run_kaggle.py` docstring, Kaggle not Colab).
- Per clip: the only measured number is 8 min 50 s for one 480x832 clip on a Kaggle T4 with Pika 6-step (research note). 768x1344 has about 2.6 times the pixels, and arms B and C change the model. Per-clip time is unknown until T0 runs.
- The 6 h exec timeout is a cap I chose, not measured.

## Scoring sheet (one row per clip; the owner judges the full clip at full resolution)

| Clip | Arm | Seed | Face match to sheet (1-5) | Line flicker (none / some / heavy) | Colour drift (1-5) | Launch motion (1-5) | Wall time (s) | Units | Peak VRAM (MB) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|

- Face match: first, middle and last second against `CHAR-KRISHNA__ref_face.png` (full size, not a thumbnail).
- Line flicker: ink outlines shimmer or jump between frames.
- Colour drift: flat cel colours against LEAP-03A/B (palette rule in the style file).
- Launch motion: does the crouch become a deliberate arc, with the branch rebound and the cloth trailing a beat behind?
- Wall time: `timeline.txt` (START and END lines per clip). Units: `colab usage` before and after the run. Peak VRAM: `gpu.csv`.

## Open question: does Wan2GP load the Turbo LoRA on Singularity?

**Answer from the code (not verified on a run, the LoRA file was not downloaded):** probably yes, if the LoRA's AdaLN input is full width (2688). It is refused with a clear error if the LoRA is pruned (width 8 or 64) and has no source tag. Either way the failure is loud, not silent.

Findings (Wan2GP at commit bd1ff59, `D:\aai work\kaggle_h3_test\wan2gp_src`):

1. **Routing:** `wgp.py:3070-3076` maps the finetune to its architecture, `minimax_h3_ref2va_pruned`. The loader gets that name (`wgp.py:4157`, `wgp.py:7776`).
2. **Key names:** `models/minimax_h3/transformer.py:504-531` converts ComfyUI, Kohya and diffusers names; fused qkv is split at `transformer.py:605-610`; the generic mapper is `shared/utils/lora_mapping.py:77-135`. Unknown keys are left for the loader to reject (`transformer.py:515`).
3. **AdaLN width:** `transformer.py:578-587` calls `convert_adaln_loras` (`models/minimax_h3/lora_affine.py:104-153`). Singularity's map `lora_affine_maps/singularity_v2_rank8.sft` is not the canonical `ref2va_rank8.sft` (the tables differ), so a pruned LoRA with no source tag is refused at `lora_affine.py:148-150`. A full-width (2688) LoRA converts through the Singularity map. The log line at `transformer.py:584-587` says which case ran ("from full AdaLN width 2688" or "pruned AdaLN width N").
4. **Samplers and schedule:** `pipeline.py:823` accepts euler, er_sde, res_multistep, ralston_2s and pika_renoise. The euler schedule is linspace(1, 0, steps+1) shifted by `flow_shift` (`pipeline.py:1228-1235`). The audio shift is fixed at 3.0 (`pipeline.py:1236`), not a setting. There is no separate scheduler key: "simple" is this default with `custom_sigmas` empty.
5. **Automatic Turbo:** the H3 LightX2V Turbo is added only for phase 2 (`pipeline.py:444-447`, `461-467`), so the one-phase arms do not pick it up.
6. **Guards:** `minimax_h3_handler.py:1003-1021` checks Pika only. For the Turbo files, `check_combo` in `h3_director.py` is the only guard.

**Not verified:** the Turbo file's key names and AdaLN width. The answer is in the VM log `wgp_SHOT-T0-B-S42.log` (the converted line, or the refusal at `lora_affine.py:150`). The wrapper does not download the wgp logs (the spec says mp4 plus three files). To get them, add `wgp_*.log` to the list in `run_t0_colab.py`.

**Fallback if Wan2GP refuses:** run arms B and C in ComfyUI on the same GPU, as the DECISION note says (full bf16 Singularity fits a 96 GB G4). Not built here: ComfyUI needs its own render step (OPUS review, section 6).

## Risks

- **Windows:** the Colab CLI is documented for Linux and macOS only. Run the real batch from Linux, macOS or WSL (WSL not tested here).
- **Aspect:** the LEAP frames are 1536x2752 (0.558) and the target is 768x1344 (0.571). Check the first frame of each clip for crop or stretch.
- **Keyframe size:** `run_kaggle.py` caps embedded images at 1376 px on the long side, so the LEAP frames reach the batch at 768x1376.
- **Logs:** only the mp4 and three log files come back (see the open question).
- **Licence:** the research notes say outputs may not be used or shown in the US, EU, UK or Korea. T0 is internal testing; the owner handles the licence (HANDOFF).
- **Tests:** 337 pass (`C:\Python314\python.exe -m pytest -q -p no:cacheprovider` in `director\`).

## Result (2026-11-06)
All 8 clips rendered. B fails (scene break), A, C, D good. Owner chose arm C (`sing8`) for the Leap reel; see research/workflow_review/DECISION_best_workflow_2026-11-05.md. Comparison sheets: `cmp/`.
