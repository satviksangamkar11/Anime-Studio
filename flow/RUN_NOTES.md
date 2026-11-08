# Kaliya Mardan, Phase 1A: Flow run notes

> Update 2026-11-06: the image reviewer is now NVIDIA (`flow/scripts/review_shot.py` through the 14-key NvidiaScheduler, primary `nvidia/nemotron-3.5-super-vl-120b-a12b` since 2026-11-08, fallback omni); the Codex mentions below are history.

Scope: the reference sheets and plates now (8 jobs). The 10 keyframes wait for accepted sheets. Granth's system v2 is used unchanged; nothing under `D:\aai work\granthstudio\` was edited.

## Files
- Series: `D:\aai work\anime_studio\flow\flow_series_kaliya.json`
- Stage 1 spec (sheets and plates): `D:\aai work\anime_studio\flow\A_KM_image_spec_phase1a.json`
- Stage 1 jobs (built, 8 jobs): `D:\aai work\anime_studio\flow\A_KM_flow_jobs_phase1a.json`
- Stage 2 spec (10 keyframes, not built): `D:\aai work\anime_studio\flow\A_KM_image_spec_phase1a_keyframes.json`
- Progress file (agents append one line per shot): `D:\aai work\flow_outputs\anime_kaliya\adhyay_01\shots_progress.jsonl`
- Output chapter folder: `D:\aai work\flow_outputs\anime_kaliya\adhyay_01\` (the builder names the chapter by the adhyay number, so use `adhyay_01`)

## Before the first job (owner)
1. Create the anime project in Flow and put its id in `flow_series_kaliya.json` -> `flow_project` (it is a placeholder; the Granth project must not be used). Project URL placeholder: `https://flow.google.com/project/<ANIME-PROJECT-ID>`.
2. Model chip = `Nano Banana 2.1`, count `x2`, aspect per job (below), credits shown 0. Check after any restart.
3. Sheets first, in this order, each accepted before the next: KRISHNA_IDENTITY_MASTER (then name it `CHAR-KRISHNA` in Flow, because every later job attaches it by that name), KRISHNA_TURNAROUND, KRISHNA_ACTING_SHEET, KRISHNA_ACTION_POSES, KRISHNA_COSTUME_DETAIL, STYLE_CHIP_SHEET, then the plates ENV_KADAMBA_BANK_DAWN (name `ENV-KADAMBA-BANK`) and ENV_WATER_SURFACE_HIGH (name `ENV-KALIYA-DAH-POISONED`).
4. Accepted sheets: set `accepted: true` for `CHAR-KRISHNA` in the series file. Set `style.chip` to the exact Flow name of the accepted STYLE_CHIP_SHEET only after it is accepted (it is null now, so no style image is attached).

## Aspect per job (the builder has no aspect field)
The aspect is written into each job prompt ("Landscape 16:9 frame" / "Portrait 9:16 frame") and must also be set on the Flow chip by the agent:
| Job | Aspect |
|---|---|
| KRISHNA_IDENTITY_MASTER, KRISHNA_TURNAROUND, KRISHNA_ACTING_SHEET, KRISHNA_ACTION_POSES, KRISHNA_COSTUME_DETAIL, STYLE_CHIP_SHEET | 16:9 |
| ENV_KADAMBA_BANK_DAWN, ENV_WATER_SURFACE_HIGH | 16:9 |
| LEAP-01A..LEAP-05B (stage 2) | 9:16 |

## Stage 1 jobs (8)
`KRISHNA_IDENTITY_MASTER__v01`, `KRISHNA_TURNAROUND__v01`, `KRISHNA_ACTING_SHEET__v01`, `KRISHNA_ACTION_POSES__v01`, `KRISHNA_COSTUME_DETAIL__v01`, `STYLE_CHIP_SHEET__v01`, `ENV_KADAMBA_BANK_DAWN__v01`, `ENV_WATER_SURFACE_HIGH__v01`.
- Each job: `method` generate, `attempt_cap` 8, x2 per submit.
- The identity master's job lists `CHAR-KRISHNA` as a chip, but that asset does not exist yet. Attach nothing for that one job; the chip is for the later sheets.
- The `sheets` field of the identity master lists its own output file. Do not read it as a reference.
- The job file warns `unaccepted sheet` for CHAR-KRISHNA until it is accepted; that warning is expected.

## Review and download commands (anime paths)
Scripts in Granth are called read-only from here; their outputs go to the anime folders.

- Review (one Codex call for both x2 images; this is a model call and runs only in the Flow session, not now):
  `C:\Python314\python.exe "D:\aai work\granthstudio\scripts\flow\review_shot.py" --jobs "D:\aai work\anime_studio\flow\A_KM_flow_jobs_phase1a.json" --shot <SHOT_ID> --candidate <A.png> <B.png>`
  It works on the anime files because the job file is passed in. It writes `<candidate>__review.json` next to the candidate, so the candidates must sit in `...\adhyay_01\shots\`.
- Neighbour sheet (no model call):
  `C:\Python314\python.exe "D:\aai work\granthstudio\scripts\flow\neighbour_sheet.py" --jobs "D:\aai work\anime_studio\flow\A_KM_flow_jobs_phase1a.json" --shot <SHOT_ID> --candidate <A.png> <B.png> --out "D:\aai work\flow_outputs\anime_kaliya\adhyay_01\shots\<SHOT_ID>__neighbours.jpg"`
- Queue a kept tile (writes only into the anime chapter folder):
  `C:\Python314\python.exe "D:\aai work\granthstudio\scripts\flow\download_queue.py" add --root "D:\aai work\flow_outputs\anime_kaliya" --adhyay 1 --shot <SHOT_ID> --version v01 --edit-id <36-char id> --jobs "D:\aai work\anime_studio\flow\A_KM_flow_jobs_phase1a.json" --model "Nano Banana 2.1 x2"`
  Caveat: the `url` field it writes is Granth's project URL (hard-coded). Use the edit id; the URL in the queue is not reliable for anime.
- Status (read-only, anime folder):
  `C:\Python314\python.exe "D:\aai work\granthstudio\scripts\flow\download_queue.py" status --root "D:\aai work\flow_outputs\anime_kaliya" --adhyay 1`

## Blocked: do not run until fixed
- `download_queue.py collect` cannot point at the anime folder. It calls `file_flow_download.py`, which hard-codes `D:\aai work\flow_outputs\adhyay_<NN>`. Running it would file anime images into Granth's Adhyay 1 folder. The anime filer needs its own copy (outside Granth) before phase 2. Phase 2 (2K downloads and filing) is not started; it also needs the owner's OK.
- `status` shows nothing as FILED for anime until a filer writes `flow_log.jsonl` into the anime chapter folder.

## Builder notes (differences from the brief)
- `method` is `generate` for the no-reference sheets. The builder accepts only `generate` and `edit`; `new` is refused.
- The keyframes are NOT built. The `edit` jobs need a `base_edit_id` (the Flow edit id of the accepted A tile), and the builder refuses a spec with an empty one. Stage 2 holds the 10 keyframes with `PENDING-LEAP-0xA` placeholders; replace them after the A tile is accepted, then rebuild. A trial build of stage 2 went to scratch only (no output kept).
- `ENV-KALIYA-DAH-POISONED` was added as a place (the water-surface plate and LEAP-04/05 use it). It is not in the checklist; it is the bible's poisoned-pool environment.
- Props: `PROP-KALI-KAMLI` and `PROP-MOR-MUKUT` share the costume detail sheet as their chip. Only PROP-KALI-KAMLI is used in stage 2 keyframes.
- The style entry has `chip: null` and its own sheet slot (`style.chip_sheet`).
- The forbidden-word list is Granth's, unchanged. The builder found no hits in the job file.

## Next
Owner approves the identity master, then the other sheets and plates. Then build stage 2 (after replacing the placeholders) and run the Flow agents per the Granth brief, with these paths.

## Rebuild 2: approved Krishna identity master (2026-11-05)
Owner approved `KRISHNA_IDENTITY_MASTER__v01__edit2_candA.png`. Changes:
- Job file: `D:\aai work\anime_studio\flow\A_KM_flow_jobs_sheets2.json` (4 jobs: KRISHNA_TURNAROUND, KRISHNA_ACTING_SHEET, KRISHNA_ACTION_POSES, KRISHNA_COSTUME_DETAIL; all `__v01`, generate, x2, cap 8). Spec: `A_KM_image_spec_sheets2.json`. Built with `granthstudio\scripts\flow\build_jobs_v2.py --series` pointing at `flow_series_kaliya.json`. Each job chips: `CHAR-KRISHNA`, then `STYLE_CHIP_SHEET__v01`. No props or place chips. No unaccepted-sheet warning.
- Series: CHAR-KRISHNA sentence rewritten to the approved look; sheet `references\CHAR-KRISHNA__identity_master.png` (copy of the approved image); accepted true.
- Style: chip `STYLE_CHIP_SHEET__v01` (sheet `references\STYLE_CHIP_SHEET.png`), accepted true.
- Place ENV-KADAMBA-BANK: chip `ENV_KADAMBA_BANK_DAWN__v01`, sheet `references\ENV-KADAMBA-BANK.png`, accepted true.
- Place ENV-KALIYA-DAH-POISONED: sheet `references\ENV-KALIYA-DAH-POISONED.png` (a copy of ENV_WATER_SURFACE_HIGH__v01__candB), accepted FALSE. The owner has not picked A or B yet; swap the sheet once chosen.
- Director bible `director\style\kaliya_mardan.json` CHAR-KRISHNA: lighter cloud-blue skin (sampled base #AFCCEA, light #B3D1F7, shadow #7990B9), playful eyes, pearls, U-tilak, bansuri (PROP-FLUTE attached), dark indigo-grey / no tilak / missing pearls or flute added to forbidden drift. Director tests: 306 passed.
- Not run: no Flow, no browser, no model calls, no network. Nothing under `granthstudio\` edited. Nothing committed.

Open points:
- RESOLVED 2026-11-05: the owner approved the bansuri rule. Krishna keeps the bansuri tucked in his sash in every scene (leap and underwater included); in hand only when a shot says so. Director bible and series sentence updated.
- Chip names for the two places and the style chip must match the exact Flow asset names when uploaded. ENV-KADAMBA-BANK's chip name changed to `ENV_KADAMBA_BANK_DAWN__v01`.
- The earlier phase1a KRISHNA_TURNAROUND, ACTING, ACTION_POSES and COSTUME_DETAIL jobs in `A_KM_flow_jobs_phase1a.json` are superseded by the sheets2 file. Do not run them.

## Keyframes A (START frames of the leap), built 2026-11-05
Owner approvals the same day: DIRECTION.md (status APPROVED), water plate B, the bansuri rule. Not run: no Flow, no browser, no model calls, no network. Nothing committed; nothing under `granthstudio\` edited (its `build_jobs_v2.py` was only run).
- Spec: `D:\aai work\anime_studio\flow\A_KM_image_spec_keyframesA.json`
- Jobs (built, 5 jobs, all `generate`, x2, cap 8): `D:\aai work\anime_studio\flow\A_KM_flow_jobs_keyframesA.json`
- Build command: `C:\Python314\python.exe "D:\aai work\granthstudio\scripts\flow\build_jobs_v2.py" --adhyay 1 --spec "D:\aai work\anime_studio\flow\A_KM_image_spec_keyframesA.json" --out "D:\aai work\anime_studio\flow\A_KM_flow_jobs_keyframesA.json" --series "D:\aai work\anime_studio\flow\flow_series_kaliya.json"`
- Aspect: 9:16 portrait for all five (stated in each prompt: "Portrait 9:16 frame"). The agent must set the 9:16 aspect on the Flow chip for each job.
- Chips (in order):
  - LEAP-01A__v01: CHAR-KRISHNA, ENV_KADAMBA_BANK_DAWN__v01, STYLE_CHIP_SHEET__v01
  - LEAP-02A__v01: CHAR-KRISHNA, ENV_KADAMBA_BANK_DAWN__v01, STYLE_CHIP_SHEET__v01
  - LEAP-03A__v01: CHAR-KRISHNA, ENV_KADAMBA_BANK_DAWN__v01, STYLE_CHIP_SHEET__v01
  - LEAP-04A__v01: CHAR-KRISHNA, ENV_WATER_SURFACE_HIGH__v01, STYLE_CHIP_SHEET__v01
  - LEAP-05A__v01: ENV_WATER_SURFACE_HIGH__v01, STYLE_CHIP_SHEET__v01 (no Krishna)
- Props: none attached as chips. The Kali Kamli is already in the strict CHAR-KRISHNA sentence, so the costume sheet is not a chip here.
- Water tile: Flow edit `3822feb6-7345-47ad-907c-c65fa19086e3` (candB) is accepted. Before LEAP-04A runs, rename it to `ENV_WATER_SURFACE_HIGH__v01` in Flow and queue it with `download_queue.py add` (the file is `ENV_WATER_SURFACE_HIGH__v01__candB.png`, and `references\ENV-KALIYA-DAH-POISONED.png` is a copy of it).
- Series: ENV-KALIYA-DAH-POISONED is accepted with chip `ENV_WATER_SURFACE_HIGH__v01`.
- END frames (LEAP-0xB, edits): `D:\aai work\anime_studio\flow\A_KM_image_spec_keyframesB_pending.json`. Not built. Each needs its A tile's Flow edit id to replace `PENDING-LEAP-0xA`. LEAP-05B has no Krishna.
- Superseded: `A_KM_image_spec_phase1a_keyframes.json` (the old 10-keyframe stage-2 spec) and its unbuilt jobs. Do not build it; use the two specs above.
- Open point: DIRECTION.md says "5.5 heads" in its cast line; the approved identity master and the series sentence say about 4.5 heads. The keyframe prompts use 4.5 heads. Owner to confirm, then fix DIRECTION.md.

## Phase 2 (anime filer)
Anime copies of the download queue and filer live in `D:\aai work\anime_studio\flow\scripts\` (copied from Granth; Granth is not edited). They use the anime project URL (`6a7ab793-d05f-476d-91a2-aaeb00c234a0`), root `D:\aai work\flow_outputs\anime_kaliya`, and file the 2K download into `adhyay_01\final\` by exact tile title. The 2K check accepts 2752x1536 and 1536x2752. Duplicate bytes are refused.
- Tests (tmp folders only, no Flow, no network): `cd "D:\aai work\anime_studio\flow\scripts"` then `C:\Python314\python.exe -m pytest -q -p no:cacheprovider`
- Queue a kept tile (use the anime copy, so the URL is the anime project): `C:\Python314\python.exe "D:\aai work\anime_studio\flow\scripts\download_queue.py" add --root "D:\aai work\flow_outputs\anime_kaliya" --adhyay 1 --shot <SHOT_ID> --version v01 --edit-id <36-char id> --jobs "<jobs file>" --model "Nano Banana 2.1 x2"`
- Status (read-only): `C:\Python314\python.exe "D:\aai work\anime_studio\flow\scripts\download_queue.py" status --root "D:\aai work\flow_outputs\anime_kaliya" --adhyay 1`
- Collect (files every PENDING item whose exact-title 2K is in Downloads): `C:\Python314\python.exe "D:\aai work\anime_studio\flow\scripts\download_queue.py" collect --root "D:\aai work\flow_outputs\anime_kaliya" --adhyay 1 --downloads "C:\Users\Satvik\Downloads"`
- Exit code of status and collect is 0 only when nothing is pending. Owner OK is still needed before the download pass runs.

## Keyframes B (END frames), 2026-11-05
- Made as NEW generations with the A tile attached as chip @LEAP-0xA__v01 (never Flow edits of A tiles).
- Kept: LEAP-01B 25ebfc1b, LEAP-03B f9d684f2 and LEAP-04B 22550c87 (coordinator overruled Luna: wide-shot sash/flute; head-first dive from above shows feet up), LEAP-05B e2a147b6.
- LEAP-02B: 4 Nano Banana 2.1 generations drew flat toes. Fix = Flow edit on a spare 02B candidate tile. Owner order: use Nano Banana Pro for the 02B fix (exception to the one-model rule, this shot only). Kept: Pro edit on spare tile e3e487da (front-foot toes curled over the bark), coordinator-checked by zoom; Luna not run (no capture). All 5 B frames queued.
- Owner review round (2026-11-05 evening): LEAP-01A (candB) and LEAP-01B (try3_candA) edited to DARK poisoned water (Nano Banana 2.1 edit, water plate attached; same tile ids) - owner FINAL. LEAP-03: A = candA_edit1 (bce62f79) + dark water, B regenerated with Nano Banana Pro. LEAP-04A = candC2 + fix, 04B regenerated from it (Pro); LEAP-05B regenerated with the river extended (Pro).
- Final ids: 03A bce62f79 (+ bansuri tucked by a 2.1 edit), 03B 5294210f, 04A 00cfdd7c (C2 + fix), 04B 009554a2 (Pro candA; candB grew while falling away from the camera), 05A 033c928f (Pro, matches 05B camera), 05B 30cb1c15. Old tiles renamed OLD-0xX-v01 so the @ picker stays unique (never reuse a "LEAP-..." prefix for old tiles).
- Phase 2 DONE 2026-11-05: all 18 downloaded at 2K and filed (status 0 pending, 18 filed). The browser pane drops downloads; method in HANDOFF_2026-11-05.md ("How the 2K download works").
- Queue: the 5 LEAP-0xA entries had Granth's project URL; replaced with the anime project id (backup in session scratchpad).
