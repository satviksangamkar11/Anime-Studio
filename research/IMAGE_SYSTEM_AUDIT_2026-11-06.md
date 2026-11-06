# Audit: the automated image system (Flow + Haiku agents: generate, validate, download), 2026-11-06

Scope: Anime Studio copy (`anime_studio/flow/`, `flow/scripts/`) as used for the 18 Kaliya Mardan images, plus the Granth spec it follows (`granthstudio/docs/pilot/FLOW_IMAGE_SYSTEM.md`, read only). Read-only audit: no Flow, no model calls, nothing edited. Evidence = files and logs on disk; "not checked" is stated where I did not look.

## 1. What works (verified)
- **Download and filing:** 18 of 18 queued, 18 filed, 0 pending. Every filed image has the right 2K size (2752x1536 sheets, 1536x2752 keyframes). Filing is by EXACT tile title, so a near-miss title is ignored; duplicate bytes are refused. `flow/scripts` tests: 9 passed.
- **Queue and log:** `download_queue.jsonl` (24 lines, 18 latest) and `flow_log.jsonl` (19 lines) agree; every log line has the real job prompt hash (`prompt_source: jobs v2`) and the chips. All 18 queue URLs point at the anime project (an old Granth-URL bug was fixed).
- **Review step:** 44 Codex reviews ran, 0 errors and 0 missing answers: the parser is fail-closed as designed.
- **Watermark:** LaMa removal on all 18 with tests (separate audit not needed).

## 2. Findings, worst first

**F1 (high) Provenance does not match the pixels.** Every image is filed as `v01` and the log says "candidate, not accepted", with the ORIGINAL job prompt hash. But many finals are later edits or regenerations: LEAP-01A/01B dark-water edit, LEAP-03A bansuri edit, LEAP-02B Pro edit, LEAP-03B/04A/04B/05A/05B Pro regenerations (progress notes say so; the log does not). The log therefore cannot reproduce an image, and nothing ever records "owner accepted". Mixed models (queue: 13 x "2.1 x2", 4 x "Pro x2", 1 "Pro") break the "one model only" rule of the spec; the exceptions were owner orders but are only in free-text notes.

**F2 (high) No automatic check that the filed pixels are the APPROVED picture.** The identity master was once filed from the wrong Flow history tile (the unedited look); only a human eye caught it (re-filed, old copy in `final/_superseded`). The filer checks size, duplicate bytes and title, nothing else. A tile history mix-up will happen again.

**F3 (medium) The Haiku layer is not what decides, and the record hides it.** Progress file (48 lines): DONE 24, NEEDS_REVIEW 17, FINAL 5, NOTE 1, BLOCKED 1. FINAL, NOTE and BLOCKED are hand-added; the spec only has DONE/NEEDS_REVIEW/FAILED. No line says WHO decided (no agent or decided_by field); 8 lines have no edit id, 7 no attempts, 10 no codex verdict. Notes show the coordinator (Claude) and owner made the final calls ("coordinator overruled Luna", "owner approved", "coordinator freeze"). The spec says "Haiku decides". Agents also stalled on the usage limit this run (K4/K5, relaunched): there is no heartbeat or resume rule in the files.

**F4 (medium) The reviewer is a strict advisor, not a gate, and its settings drifted.** 44 reviews: choice PASS 7, BLOCK 33, UNSURE 4 (per candidate: BLOCK 63, PASS 11, UNSURE 8). Two models in one run: gpt-6-luna 34 reviews, gpt-6.1-sol 10 (code says Luna by an owner request of 2026-11-05; memory and the spec say Sol medium), so verdicts are not comparable. The review prompt still carries Granth-only wording (Q3 lists "house, door, step, road, well, trough"; a ban on the word "Maharaj"), which is noise for Krishna shots.

**F5 (medium) Orientation and set-consistency are not checked.** The filer accepts either size for any image, so a landscape image filed as a keyframe passes; the builder has no aspect field (RUN_NOTES: the agent must set it by hand). The pale LEAP-02A/02B water got through every gate and is still open: no automatic colour or palette check against the water plate or sibling shots.

**F6 (medium) `final/` holds five variants of every image side by side:** `.png` (with the watermark), `__2K_source.jpg`, `__clean.png`, `__lama.png`, `__final.png` (plus backup folders). Only HANDOFF says "use `__final`". Anything that globs `LEAP-*.png` gets the watermarked one. The watermark step is also not in the filer or the log: the clean file's hash is never recorded.

**F7 (medium) Hidden dependence on the frozen Granth project.** `file_flow_download.py` line 50 reads `granthstudio/canon/drafts/A1_image_catalog_v2_DRAFT.json` on EVERY filing; if that file moves or is renamed, all filing crashes. The anime tests also read it. Paths (Downloads, project id, root) are hard-coded in several scripts.

**F8 (low) Code hygiene in the filer:** validation uses `assert` (skipped under `python -O`, tracebacks instead of messages); `collect` sets `FLOW_MAX_AGE_S` to 7 days, which switches off the "this is the download you just made" guard, leaving only title and duplicate checks; `save_dl.py` silently overwrites a same-named file. Tests do not cover: missing catalog, age check, overwrite refusal, re-file, non-JPEG, orientation.

**F9 (low) The 2K download itself is manual and fragile:** the browser pane drops downloads; the working method (in-page blob hook, decode with `save_dl.py`, owner clicks Save in the spec) lives in HANDOFF text, not in a script. The spec still says "Claude clicks 2K, owner clicks Save".

## 3. Not checked
Haiku agent transcripts (whether each agent attached exactly the job's chips and used the right model chip every time); the Flow site itself; whether LEAP-0xB neighbour sheets were built from the final or the interim picture.

## 4. Recommended fixes (smallest first; none done yet)
1. Filer: drop the Granth catalog read (prompt hash only from the jobs file); replace `assert` with clear refusals; extend tests (about 15 lines each).
2. Log: add `lineage` (edit/regen chain, final model, final prompt or edit sentence), `decided_by` (owner / claude / haiku) and an append-only `accepted` record with the date when the owner approves; one fixed status list (DONE, NEEDS_REVIEW, FAILED, FINAL).
3. Fingerprint: at queue time save a small thumbnail hash (dHash) of the approved zoom picture; at filing refuse if the download's hash differs beyond a threshold (catches the wrong-tile case).
4. Aspect: pass the job's aspect to the filer; refuse the wrong orientation.
5. Folder: move non-final variants into `final/_variants/`, keep only `__final.png` and the 2K source in `final/`; log the clean file's hash.
6. Reviewer: one model for a whole series (decide Sol or Luna); strip Granth wording from the anime review prompt; record that the reviewer only advises.
7. Optional set check: mean water colour of each LEAP frame against the water plate, flag a big gap (would have caught 02A/02B).
