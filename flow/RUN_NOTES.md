# Kaliya Mardan, Phase 1A: Flow run notes

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
