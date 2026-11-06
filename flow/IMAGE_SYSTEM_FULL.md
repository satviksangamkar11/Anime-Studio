# Anime Studio image system, written down in full (2026-11-06)

What it is: the automated pipeline that turns a shot spec into final 2K pictures through Google Flow (Nano Banana), with Haiku agents doing the Flow clicks, an NVIDIA Nemotron image reviewer (14-key scheduler) and Claude reviewing, and scripts filing the results. This is the Anime Studio (Kaliya Mardan) version of the Granth "Flow image system v2". It is the system that made the 18 Leap images. Companion files: `RUN_NOTES.md` (run log with exact commands), `../research/IMAGE_SYSTEM_AUDIT_2026-11-06.md` (what is weak), `../HANDOFF_2026-11-05.md` (2K download method, tile ids).
Granth sources (read-only, frozen, never edit `D:\aai work\granthstudio\`): `docs/pilot/FLOW_IMAGE_SYSTEM.md` (the spec), `FLOW_RUNBOOK.md` (click details), `IMAGE_PROMPT_RULES.md`, `scripts/flow/build_jobs_v2.py`.

## 1. Owner rules that bind the system
- One model: Nano Banana 2.1, count x2, no fallback. Exceptions only by owner order, per shot (this run: Nano Banana Pro for LEAP-02B edit, 03B, 04B, 05A, 05B).
- Always x2 per submit; always download at **2K Upscaled** (never 1K, never 4K).
- **RULE (owner 2026-11-06): the Flow generation and download work runs on Haiku at effort LOW** (agents that operate Flow: attach, submit, open, rename, queue, download). Build and code-review agents are a separate job and keep their own effort. Haiku agents operate Flow; one agent per scene, each in its OWN browser tab; Haiku AND the NVIDIA reviewer review, **no downloads while generating** (phase 1), one download pass at the end (phase 2) after the owner's OK.
- Claude checks every kept picture at FULL resolution, then freezes or fixes ("check yourself, freeze or fix, close fast"). Owner approves the set.
- Image reviewer (changed 2026-11-06, owner): NVIDIA Nemotron through the existing 14-key `animation_research_tool/nvidia_scheduler.py` (10 calls per key per 60 s), one call per submit for both x2 images, advisory only. Primary model `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (found live, accepts images). Documented fallback: `nvidia/nemotron-3.5-super-vl-120b-a12b`, used only on a model-not-found 404/400. Code and system reviews use the free Dots model (`flow/scripts/dots_review.py`).
- Never delete anything in Flow; never click Upgrade/Share/Trash; stop on sign-in, CAPTCHA, payment or terms pages; credits shown must stay 0. The owner signs in; nobody types a password.
- Flow project (anime): `6a7ab793-d05f-476d-91a2-aaeb00c234a0` (never the Granth project). No flow-mcp.

## 2. The parts
| Part | Where | Does |
|---|---|---|
| Series data | `flow/flow_series_kaliya.json` | characters with strict sentences, places, ONE style chip, model settings, outputs root. Built from `director/style/kaliya_mardan.json` |
| Shot spec | `flow/A_KM_image_spec_*.json` | per shot: id, method (generate or edit), characters, place, action, light, aspect sentence, base_edit_id |
| Job file | `flow/A_KM_flow_jobs_*.json` (built) | per job: prompt, prompt_sha256, chips in order, previous/next shot, sheets, attempt_cap 8, neighbour chips and sentence, model |
| Job builder | Granth `scripts/flow/build_jobs_v2.py` (called with `--series` pointing at the anime series file) | refuses forbidden words, refuses an edit job without base_edit_id, warns about unaccepted sheets |
| Agents | Haiku, effort LOW (owner rule 2026-11-06), in the Claude built-in browser | attach chips, paste prompt, submit, open tiles, screenshot, rename, queue, progress line |
| Neighbour sheet | `flow/scripts/neighbour_sheet.py` | one JPEG: PREVIOUS / candidate A / candidate B / NEXT on top, reference sheets below |
| Image review (NVIDIA) | `flow/scripts/review_shot.py` | six questions Q1-Q6 per candidate, verdict PASS/BLOCK/UNSURE, FIX none/edit/regenerate, EDIT_INSTRUCTION, REGEN_SENTENCE; fail closed; writes `<A>__review.json/.md` |
| Queue | `flow/scripts/download_queue.py` | `add` (queue a kept tile by edit id), `status`, `collect` (file every saved 2K by exact title) |
| Filer | `flow/scripts/file_flow_download.py` | checks complete JPEG, 2752x1536 or 1536x2752, no overwrite, no duplicate bytes; writes png + `flow_log.jsonl` |
| Download helper | `flow/scripts/save_dl.py` | decodes a download captured as base64 in a browser-tool result into Downloads |
| Watermark | `flow/scripts/lama_inpaint.py`, `remove_sparkle.py` (+ tests), weights `flow/lama_weights/big-lama.pt` | removes the Flow sparkle (LaMa) from the 18 finals |
| Video refs | `flow/scripts/make_refs.py` | cuts face / front / back crops of Krishna for the video Ref2VA step |
| Outputs | `D:\aai work\flow_outputs\anime_kaliya\adhyay_01\` | `references/` (sheets), `shots/` (candidates, reviews, neighbour sheets), `final/`, `refs_video/`, `download_queue.jsonl`, `flow_log.jsonl`, `shots_progress.jsonl` |

## 3. Order of work for a new set (what was done for Kaliya Mardan)
1. **Data first.** Style bible (`director/style/kaliya_mardan.json`) -> series file (strict character sentence, places, style chip). Owner approves.
2. **Reference sheets, in order, each accepted before the next:** KRISHNA_IDENTITY_MASTER (then name it `CHAR-KRISHNA` in Flow: later jobs attach it by that name) -> KRISHNA_TURNAROUND, ACTING_SHEET, ACTION_POSES, COSTUME_DETAIL -> STYLE_CHIP_SHEET -> place plates (ENV_KADAMBA_BANK_DAWN, ENV_WATER_SURFACE_HIGH). Accepted sheets: set `accepted: true` and the chip name in the series file; the chip name must equal the exact Flow asset name.
3. **Keyframes A (START frames, `generate`, 9:16)**, then **keyframes B (END frames)** as NEW generations with the A tile attached as a chip (`@LEAP-0xA__v01`), not as Flow edits (a Flow edit replaces the tile picture).
4. **Phase 1 per job** (section 4), **Phase 2 download** (section 5), **watermark removal**, **video refs**.

## 4. Phase 1: make and review (no downloads)
Per job, the agent re-reads its job entry first.
1. Look once: read previous/next shot files and the job's sheets; write one line on what the new picture continues from and cuts into.
2. Check settings: model chip = series `model.name`, count x2, aspect set per job (16:9 sheets and plates, 9:16 keyframes; the builder has no aspect field, it is only in the prompt text), credits 0. After any PC restart Flow resets the chip: fix it first.
3. Attach chips with the `@` method: type `@`, wait ~3 s, click the menu search box, type the exact name, attach ONLY if exactly one matching row shows. Chips = exactly the job's `chips` in order (characters, place, props, ONE style chip). Screenshot the chip names before submit.
4. Paste the job prompt exactly (an edit job: open `.../edit/<base_edit_id>` and type the edit instruction instead; never type into "What do you want to change?" by mistake). Submit once, wait ~60 s; if no tile, reload and look before resubmitting.
5. Open each of the two new tiles (click twice until the URL has `/edit/`), note both edit ids, zoom on the picture; the zoom image is the candidate file. No download.
6. NVIDIA review (both images, one call): `python flow/scripts/review_shot.py --jobs <jobs> --shot <ID> --candidate <A> <B>`. Neighbour sheet: `neighbour_sheet.py` (no model call). Exit code 0 PASS, 1 BLOCK, 3 UNSURE.
7. Haiku review of the same sheet (Q1 people, Q2 action and gaze, Q3 place and props, Q4 continuity with previous and next, Q5 style and framing, Q6 nothing invented). A PASS belongs to one exact image version.
8. Decide:
   - PASS on one and agreed -> keep.
   - Both bad -> fix loop: **edit first** (one local defect: type "Change only <defect>. Keep everything else exactly the same: <pose, props, background, style>."), a second edit once with a sharper sentence plus accepted-neighbour chips, **regenerate** when identity, age, framing or pose is wrong (job prompt + the latest REGEN_SENTENCE, replaced not stacked; neighbour chips from the second regeneration on). Drop a neighbour chip when the job changes a position or light from that neighbour.
   - Stuck rule: same question fails for the same reason twice -> `NEEDS_REVIEW` with the reason. Safety stop: 8 submits or edits per shot. UNSURE or reviewer/agent disagreement -> `NEEDS_REVIEW`.
9. Keep: rename the tile to the job's `flow_title` (the FIRST "Editable text" on the edit page), then queue: `python flow/scripts/download_queue.py add --root "D:\aai work\flow_outputs\anime_kaliya" --adhyay 1 --shot <ID> --version v01 --edit-id <36-char id> --jobs <jobs> --model "Nano Banana 2.1 x2"`.
10. Append one line to `shots_progress.jsonl`: `{shot_id, status, flow_title, edit_id, attempts, decided_by, reviewer, haiku, time, notes}` (validated by `progress_log.py`; statuses DONE, NEEDS_REVIEW, FAILED, FINAL, GENERATED, BLOCKED, NOTE`. DONE only when both reviews pass.
11. Claude then checks each kept picture beside its neighbours at full size (the owner sees a contact sheet and exceptions).
Several agents share one project: new tiles of the others appear at the top; identify YOUR tiles by edit id and title, check the picture matches your shot, pass your own `tabId` on every browser call, append-only files. Old tiles you replace get renamed `OLD-0xX-v01` so the `@` picker stays unique.

## 5. Phase 2: download pass (only after the owner's OK)
1. `python flow/scripts/download_queue.py status --root ... --adhyay 1` lists PENDING tiles with their edit URLs.
2. For each: open the edit URL, menu (three dots) -> Download media -> **2K Upscaled** (the first attempt after a page load often does nothing: repeat once). After an edit, download immediately while the edited picture is on screen and rename afterwards (renaming first downloads the OLD image).
3. The built-in browser pane does NOT save downloads. Working method: in `javascript_tool` hook `HTMLAnchorElement.prototype.click` so the download is fetched into `window.__dl` as a data URL named `<title>_<hash>_2K.jpg`; return it; the result is saved as a text file; decode with `python flow/scripts/save_dl.py <result files>` into `C:\Users\Satvik\Downloads`.
4. `python flow/scripts/download_queue.py collect --root ... --adhyay 1 --downloads "C:\Users\Satvik\Downloads"` files every saved image by EXACT title into `adhyay_01\final\` (never by time), checks size and duplicates, logs the real prompt hash, chips and model. Repeat until 0 pending. Exit 0 only when nothing is pending.

## 6. After filing
- **Watermark:** `lama_inpaint.py` (LaMa) on every final; LEAP-04A/04B used a LaMa-on-alpha hybrid. The master per image stays in `final/`: **`<TITLE>__candidate_v01__final.png` (use this one)**. The other variants were moved by `tidy_final.py --apply` (2026-11-06) into `final/_intermediates/`: `<TITLE>__candidate_v01.png` (original, WATERMARKED), `__2K_source.jpg`, `__clean.png`, `__lama.png`. The watermarked originals are also backed up in `final/_original_with_watermark/`. The scripts read inputs from `_original_with_watermark` (fallback `_intermediates`, then `final/`) and never overwrite a file without `--overwrite`. The review prompt tells the reviewer to ignore the sparkle.
- **Video references:** `make_refs.py` -> `refs_video/CHAR-KRISHNA__ref_{face,front,back}.png`. Do not use the KRISHNA_ACTION_POSES sheet (broken bottom row).
- Final set (18): 10 keyframes LEAP-01A..05B at 1536x2752 and 8 sheets/plates at 2752x1536.

## 7. Files and naming
- Tile title = job `flow_title` = `<SHOT_ID>__v01`; filed as `<SHOT_ID>__candidate_v01(.png | __2K_source.jpg)`.
- `download_queue.jsonl` (append-only; latest line per shot+version wins) -> `flow_log.jsonl` (one line per filing: sha256 of jpg and png, pixel size, model shown, chips, prompt hash, edit id, notes). An item is FILED when the log has the same image id + version.
- Review outputs next to the candidate: `__neighbours.jpg`, `__review.md`, `__review.json`.

## 8. Failure modes met and the rule that answers each
| Seen | Rule |
|---|---|
| Wrong or extra chip; a neighbour attached by mistake | Attach only the job's chips; one exact search row; screenshot the chip list before submit |
| Flow resets model/count after a restart | Check the chip before the first job and after any restart |
| Silent no-submit | Wait ~60 s, reload and read the newest tiles before submitting again |
| "Failed ... not charged" card beside a result | Open the tile with an image, ignore the card |
| Safety filter blocked a word | Forbidden words are refused when jobs are built |
| Wrong tile opened from a search with several rows | Identify by edit id; check header title and picture before renaming |
| Edit downloaded the old image | Download before renaming; the filer refuses identical bytes |
| Flat toes (LEAP-02B, four 2.1 tries) | Edit on a spare tile with Nano Banana Pro (owner exception) |
| Water too pale / not matching the plate (LEAP-02A/02B still open) | Edit with the water plate attached (done for 01A, 01B, 03A) |
| Identity master filed from the wrong history tile | Select the approved version in Flow, re-download, re-file, move the wrong file to `_superseded` |
| Agent stalled on the usage limit | Relaunch with its saved brief; Usage limit in Flow: STOP and report, never switch model |
| Neighbour chip pulls the old layout | Drop that chip when the job changes position or light |
| Browser pane drops downloads | In-page blob hook + `save_dl.py` (section 5.3) |

## 9. Known weak points (audit 2026-11-06; F1-F3, F5, F7, F8 now fixed in the scripts, see below)
Provenance records the first prompt not the later edits; nothing checks that the filed pixels are the approved picture; progress statuses and "who decided" are not recorded; reviewer model drifted and is very strict (33 of 44 reviews BLOCK); orientation and colour consistency are not checked automatically; five variants per image sit in `final/`; the filer reads a Granth catalog file on every filing. Details and fixes: `../research/IMAGE_SYSTEM_AUDIT_2026-11-06.md`.

## 10. For a new set (checklist)
- [ ] Style bible + series data written, owner approved
- [ ] Sheets generated, accepted in order, chips named exactly in Flow, series file updated
- [ ] Spec written (aspect in each prompt), jobs built (no warnings except expected)
- [ ] Settings checked (model, x2, aspect, credits 0)
- [ ] Phase 1 per job: attach, submit, open, review x2, decide, rename, queue, progress line
- [ ] Claude full-size check of every kept picture; owner approves the set
- [ ] Owner OK -> phase 2 download + collect until 0 pending
- [ ] Watermark removal; keep only `__final.png` as the working file; refs cut for video

## 11. Changes made after the audit (2026-11-06, built by Haiku xhigh agents, reviewed by Dots; 60 tests pass)
- Filer: no Granth read; explicit REFUSED errors; orientation per job (`--aspect`); picture fingerprint (`--approved-image`, dHash, hamming > 14 refuses; threshold tested on synthetic pictures only); lineage and decided_by in the log; `download_queue.py accept` writes `accepted.jsonl`; sub-folder cannot leave the chapter.
- New: `fingerprint.py`, `progress_log.py`, `tidy_final.py` (applied 2026-11-06: 72 variant files moved to `final/_intermediates/`, sha256 checked; `lama_inpaint.py` and `remove_sparkle.py` now use the sub-folders, see section 6), `bridge_flow_to_h3.py` (exact-aspect crop + one Lanczos resize), `dots_review.py`.
- Reviewer: `review_shot.py` uses the NVIDIA scheduler (see section 1). Not yet run on a real 2K candidate.

## 12. Calibration on real art (2026-11-06)
- **Tidy applied:** `final/` root holds only the 18 `__final.png`; 72 variants moved to `final/_intermediates/` (sha256 of all moved files unchanged); queue status 18 filed, 0 pending. `lama_inpaint.py` and `remove_sparkle.py` read the watermarked input from `final/_original_with_watermark/` and write intermediates to `final/_intermediates/`; they no longer replace an existing output without `--overwrite`.
- **Picture fingerprint (dHash, 64 bit), 3 real finals:** same picture after downscale or screenshot-like crop+JPEG = distance 0 to 11; different shots 18 to 42; the A and B frames of ONE shot 2 to 15 (so it cannot tell A from B of the same shot). Threshold 14 stays: it refuses a picture from another shot; telling A from B is left to the exact title and edit id.
- **Reviewer on real art:** first run gave UNSURE (the model copied the literal `<candidate A>` placeholder). Fixed: the prompt asks for plain letters and all six answers in the final reply, `parse()` accepts `<A>`, `**A**` and `candidate A` forms, and the raw reply (with thinking) is saved as `<A>__raw.txt`. Second run on LEAP-03A: the right image A = PASS on Q1-Q6, a deliberately wrong image (LEAP-05B, no Krishna) B = BLOCK on Q1-Q6, with `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` on key 1, one try. One pair only: treat the reviewer as advisory.
- **Bridge:** `keyframes_h3/` holds the 10 Leap frames at 864x1536 (21.3 px trimmed top and bottom).

## 13. Sparkle (Flow watermark) removal: methods and record (2026-11-06)
Three methods exist, newest last: (1) `remove_sparkle.py` alpha inversion (undoes the translucent stamp; leaves faint residue on some images) -> `__clean.png`; (2) `lama_inpaint.py` LaMa (`big-lama.pt`, deep-learning inpainting of the stamp region from the ORIGINAL) -> `__lama.png`; (3) **`lama_on_clean`**: LaMa on the alpha-cleaned image with a smaller mask around the residue (the newest, hybrid method). `lama_inpaint.py` writes all variants and review sheets in `final/_sparkle_check3/`; the person checking (Claude, then owner) picks one per image in a `choices.json` and `finalize` writes the master `__final.png`. Result for the 18 finals: 16 = `lama`, LEAP-04A and LEAP-04B = `lama_on_clean` (alpha residue was faint). The chosen method is now recorded per master in `<chapter>/watermark_log.jsonl` (method, verdict, sha256; written by `finalize`, existing 18 backfilled). Choosing the method is still a visual decision, not automatic.
