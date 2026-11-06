# Pasted "Master Claude Code Implementation Handoff v3.2" vs what is verified (2026-11-06)

The owner pasted a v3.2 handoff and a Python file (`Master End-to-End Pipeline v3.2`) and said: use Haiku xhigh agents to close the works mentioned. I did NOT run the pasted file (it is only in the chat); its own claims ("56 gates pass") are unverified. Below: what was adopted, what was changed, what was NOT adopted and why. Owner decides the "not adopted" items.

## Adopted (built by Haiku xhigh agents in `flow/scripts/`)
| Handoff item | Where | Notes |
|---|---|---|
| Close the 9 audit gaps (F1-F9) | `file_flow_download.py`, `download_queue.py`, `fingerprint.py`, `progress_log.py`, `tidy_final.py` | dHash fingerprint, lineage/decided_by/accepted record, orientation check, no Granth read, `final/_intermediates/` tidy (dry-run first) |
| Reviewer = NVIDIA Nemotron Omni via NIM, one multimodal call per x2 submit, temperature 0, seed 108 | `review_shot.py` | Model ids are checked live before trusting them; reviewer stays advisory |
| Sub-pixel Lanczos bridge Flow 2K -> exact video aspect | `bridge_flow_to_h3.py` | generic (864x1536 or 768x1344), no stretch |

## Adapted
- Workspace: the handoff says `D:\aai work\animestudio\`; the real repo is `D:\aai work\anime_studio\` (no folder `animestudio` exists). Used the real one. Nothing imports Granth code.
- Flow project name `ANIME_STUDIO__KALIYA_MARDAN__ADHYAY_01`: the UUID `6a7ab793-...` matches; the name is not recorded anywhere in our files (unverified; check in Flow).

## NOT adopted (conflicts with verified facts or approved decisions; owner to decide)
1. **Chip and file renaming.** The handoff renames assets (`ENV-KADAMBA-BANK-DAWN`, `SHEET-KRISHNA-TURNAROUND`, `STYLE-KALIYA-V1`, `LEAP-02B__final.png`, `ZZZ_OLD__` quarantine). The real Flow assets are `CHAR-KRISHNA`, `ENV_KADAMBA_BANK_DAWN__v01`, `ENV_WATER_SURFACE_HIGH__v01`, `STYLE_CHIP_SHEET__v01`, finals `<TITLE>__candidate_v01__final.png`. Renaming means editing tiles in Flow and every job/log file; no benefit proven. Kept current names (old tiles are already `OLD-0xX-v01`).
2. **LEAP-05A "reuse LEAP-04B" (zero submit).** Contradicts the approved set: LEAP-05A is a separate owner-approved image (Pro generation, splash crown + first ripples, no Krishna). Kept as is.
3. **The shot story.** The handoff's ledger is a cliff-gorge crossing (west brink to east ledge, ends on the east ledge). The real storyboard (DIRECTION.md, the 10 approved keyframes) is Krishna leaping from the kadamba branch into the poisoned Kaliya pool (04 dive, 05 splash). The ledger would not match the 18 finals.
4. **Character wording.** "radiant slate-blue skin", ivory uttariya scarf: the approved identity master is lighter cloud-blue skin (sampled base #AFCCEA) with bansuri in sash; do not overwrite the bible.
5. **Video half (Part 2).** It describes a ComfyUI graph (`MiniMaxH3CheckpointLoader`, etc. - node names unverified) and Singularity **FL2VA**. What we verified: Wan2GP headless on Colab; Singularity v2 + Pika-Labs Turbo runs **Ref2VA only** (`check_turbo` refuses FL2VA); owner-chosen arm C = Ref2VA `sing8`, 768x1344, 124 frames; the pasted `mode_to_lora_map` maps FL2VA to the ref2va LoRA, which is wrong. Not built.
6. **Resolution 864x1536 (exact 9:16).** Sensible for a 9:16 reel, but arm C was tested at 768x1344 (4:7) only. 864x1536 costs about 28% more compute per clip; untested on sing8. Needs one test clip before locking.
7. **Banning every negative word** (no/not/without) in prompts: not applied; it would also reject valid existing prompts. Positive anatomy wording is already our practice.
8. **Reviewer as "Haiku decides / Sonnet full-res gate":** kept the owner rule instead: Claude checks at full resolution, owner approves.

## Still open (owner)
- Pick: keep current names (recommended) or rename to the handoff scheme.
- Test one sing8 clip at 864x1536 before choosing it over 768x1344.
- If the video part should follow the handoff, provide the real ComfyUI workflow; otherwise the Wan2GP/Ref2VA route stays.
