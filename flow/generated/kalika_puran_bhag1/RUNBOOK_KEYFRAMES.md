# RUNBOOK: reel 1 keyframes (Haiku, effort LOW). Follow exactly. Proven by Claude 2026-11-08.

Rules: own tab (tabs_create), pane at its normal size (do NOT resize to 1280), project https://flow.google.com/project/9d936443-27e4-4192-a040-a72aa77f086f ONLY. Never download via the Flow menu, delete, Upgrade or Share. Stop on sign-in/CAPTCHA/payment/terms. Settings bar must show Nano Banana 2.1, the PORTRAIT icon (9:16) and x2. Do not stop to ask questions; report once at the end with a table.

## A. Submit one job (use browser_batch; max 25 actions per batch; use YOUR tabId)
Batch 1 (start): [navigate project URL] [wait 6] [left_click (250,667)] then, per chip, these 7 actions:
 1 type "@"   2 wait 3   3 left_click (280,117)   4 type "<search text>"   5 wait 2
 6 javascript_tool (action javascript_exec) with text:
   const n='<EXACT CHIP NAME>'; const els=[...document.querySelectorAll('*')].filter(e=>e.children.length==0&&e.textContent.trim()===n); const e=els[els.length-1]; e? (e.click(),'clicked '+els.length):'NOT FOUND'
 7 wait 2
 Expect "clicked 1". If "NOT FOUND": stop this job and report. Put at most 2 chips in batch 1 and the rest in batch 2 (same 7 actions each).
Last batch: [after the last chip] [computer type: the job's prompt text EXACTLY from flow/generated/kalika_puran_bhag1/kalika_puran_bhag1_flow_jobs.json (field prompt), plus, on a retry, the reviewer's REGEN_SENTENCE appended at the end] [screenshot scale 0.5: the thumbnails above the box must equal the number of chips] [left_click (452,725) = submit arrow] [wait 4] [screenshot scale 0.4: tiles show a percentage].
Chips and search texts: the job's `chips` field, in order; search text = chip name (for CHAR-... names the full name, for ENV_ names the name without the __v01 suffix is fine, but the javascript click uses the EXACT full title).
After submit, the NEW tiles appear at the top of the gallery and take ~60 s.

## B. Verify + capture the two new tiles (no guessing from gallery order)
In javascript_tool on the gallery page run the loop that opens the tile, reads the info panel and fetches the image. Simplest: open the gallery, click the first tile (find the first image tile), then on its /edit/<id> page: click the button with aria-label "Show asset info" and get_page_text: it lists the CHIP NAMES used and then the exact PROMPT. Both must match the job (no OLD-/RETIRED- chip; the prompt equals the job prompt + optional regen sentence), otherwise discard the tile and resubmit. Capture: on the /edit/<id> page run
   await new Promise(r=>setTimeout(r,4000)); const im=[...document.images].find(i=>i.naturalWidth==768&&i.naturalHeight==1376); const b=await (await fetch(im.currentSrc)).blob(); const data=await new Promise(res=>{const fr=new FileReader(); fr.onload=()=>res(fr.result); fr.readAsDataURL(b)}); JSON.stringify({name:"<SHOT_ID>__v01_<A|B>_<first 12 hex of the edit id without dashes>_2K.jpg", data})
 The tool says the result is too long and prints a saved .txt path. Then in Bash: python flow/scripts/save_dl.py "<that .txt path>" (writes the jpg to C:\Users\Satvik\Downloads) and PIL-convert to PNG: D:\aai work\flow_outputs\anime_kalika_puran_bhag1\adhyay_01\shots\<SHOT_ID>__v01_A.png and _B.png. Go back with navigate to the other tile of the pair (the second tile is the next one in the gallery; its edit id differs).

## C. Review (strict) and decide
python flow/scripts/review_shot.py --jobs flow/generated/kalika_puran_bhag1/kalika_puran_bhag1_flow_jobs.json --shot <SHOT_ID> --candidate <A.png> <B.png>   (8 questions, 2 passes, takes ~3-4 min, run it with run_in_background and read the output file; do not start a second copy). Also look at both pictures yourself (Read tool on the PNG) with the same strictness: count people, arms, hands, fingers, text/glyphs in the picture, colours against the sheets, props named in the prompt.
 PASS on one tile (reviewer PASS and you agree) -> KEEP it. Otherwise regenerate (go to A) with the reviewer's REGEN_SENTENCE appended to the prompt; after the second failure on the same question, add a stronger sentence yourself (for a head count: "exactly six sages, clearly separated, all six visible"). Safety stop: 6 submits per job, then report NEEDS_REVIEW with the best candidate.
## D. Keep = rename
Open the kept tile's /edit/<id>, click the title (first "Editable text"), select all, type <SHOT_ID>__v01, press Enter or click the check/Done editing button, WAIT 4 s, RELOAD, re-read the title; retry once. Name the other tile RETIRED-<SHOT_ID>-x (ignore if it fails). Append one line to D:\aai work\flow_outputs\anime_kalika_puran_bhag1\adhyay_01\shots_progress.jsonl (status DONE / NEEDS_REVIEW, edit id, attempts, reviewer verdict, your verdict, time).

## RATIOS (owner 2026-11-08: always keep the ratios in mind)
Keyframes are 9:16 PORTRAIT (768x1376). Reference sheets and place plates are 16:9 LANDSCAPE (1376x768). Before every submit: the settings bar icon must be the portrait one (keyframe) or the landscape one (sheet); after every reload the aspect can reset, so check again. The tile's picture must be 768x1376 for a keyframe (the capture snippet already looks for exactly 768x1376; if it finds nothing, the aspect was wrong: regenerate). review_shot.py now blocks any candidate with the wrong shape automatically (RATIO BLOCK).

## RENAME THAT WORKS (Claude, 2026-11-08; the earlier Enter-key method did not save)
On the tile's /edit/<id> page (wait 5 s after load): left_click the title in the header at about (160,45) so it becomes an INPUT (verify with javascript: document.activeElement.tagName == "INPUT" and its aria-label "Editable text"); key ctrl+a; type the new name; then `find` "Done editing" and left_click that button (do NOT rely on Enter); wait 5 s; navigate to the same /edit/<id> URL again, wait 5 s and verify with javascript_tool: document.querySelector('input[aria-label="Editable text"]').value must equal the new name. If not, repeat once.
