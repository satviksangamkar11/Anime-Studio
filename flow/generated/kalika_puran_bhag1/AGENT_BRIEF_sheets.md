# Flow agent brief: reel 1 reference sheets (Haiku, effort LOW, built-in browser)

Same system as the proof run: flow/IMAGE_SYSTEM_FULL.md sections 1, 4, 5, 8 bind you. Project: "Anime Kalika Puran R1", id 9d936443-27e4-4192-a040-a72aa77f086f, URL https://flow.google.com/project/9d936443-27e4-4192-a040-a72aa77f086f . Never any other project. Jobs: flow/generated/kalika_puran_bhag1/kalika_puran_bhag1_sheet_jobs.json (find your jobs by shot_id).
Other agents work in the same project at the same time, each in its own tab: open your OWN new tab (tabs_create) and pass your tabId on every browser call. New tiles of the others appear at the top; identify YOUR tiles by edit id and picture. Append-only files.

Rules: stop and report on any sign-in, CAPTCHA, payment or terms page. Never type a password; never click Upgrade/Share/Trash; never delete anything in Flow. Take a screenshot before clicking; resize_window preset desktop first if the pane is narrow. Do not edit repo files.

Per job (one after another):
1. Settings: model chip Nano Banana 2.1, count x2, aspect 16:9, credits 0 (stop if not 0). No chips for sheets.
2. Paste the job prompt exactly (form_input), submit once, wait ~60 s; if no tile, reload and look before resubmitting.
3. Open each of your two new tiles (click until the URL has /edit/), note both edit ids. Capture each displayed picture to disk with javascript_tool (fetch the img src -> data URL) and decode with flow/scripts/save_dl.py (as in the proof run) into D:\aai work\flow_outputs\anime_kalika_puran_bhag1\adhyay_01\shots\<SHOT_ID>__v01_A.png and _B.png (re-encode to PNG). NO use of Flow's download menu.
4. Review: python flow/scripts/review_shot.py --jobs flow/generated/kalika_puran_bhag1/kalika_puran_bhag1_sheet_jobs.json --shot <SHOT_ID> --candidate <A.png> <B.png>  (Super VL, advisory; exit 0 PASS, 1 BLOCK, 3 UNSURE). Also give your own Haiku review of the neighbour sheet (people, action, place/props, style, nothing invented). Check the picture against the prompt yourself too.
5. Decide as in the doc: a tile that PASSES both reviews is kept. If both are bad: edit-first for one local defect, regenerate for identity/layout faults; stuck rule: same question failing for the same reason twice -> NEEDS_REVIEW; safety stop 8 submits/edits per job. UNSURE or disagreement -> NEEDS_REVIEW.
6. Keep = rename the tile to the job's chip_name (the FIRST "Editable text" on the edit page; this is the exact name later keyframe jobs attach by @, so it must be exact and unique; rename any replaced old tile OLD-<name>). Do not queue or download.
7. Append one line per job to D:\aai work\flow_outputs\anime_kalika_puran_bhag1\adhyay_01\shots_progress.jsonl in the progress_log.py format (statuses DONE / NEEDS_REVIEW / FAILED; edit ids, attempts, reviewer verdict, haiku verdict, chip_name used, time).
Final report: per job the status, both edit ids, which tile was kept and renamed, reviewer key lines, anything unexpected.
