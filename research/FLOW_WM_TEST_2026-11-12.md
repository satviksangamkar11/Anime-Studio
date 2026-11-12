# Flow image + watermark remover test, 2026-11-12

Project: FLOW_WM_TEST_2026-11-12 (Flow id 5300f101-2624-41be-b4c8-71e9cb378ca7), new, nothing else touched.
Model: Nano Banana 2.1, x2, 9:16 portrait, Thinking High (default), 0 credits shown.
Generations: 4 submits (one per prompt), each x2 = 8 tiles in Flow. Downloaded: first tile of each submit (4 files).
Raw files: `flow/generated/_flow_wm_test_2026-11-12/raw/` (git-ignored). Cleaned copies: `.../clean/`. Crops: `.../crops/`.
Remover: `director/watermark_auto.py`, run on copies in `.../copies/` (originals untouched).

| # | Prompt (short) | Raw bytes | Clean bytes | Pixels | Sparkle (bottom-right) | Stamps before / after | Method | Verified | Status | Look at 4x crop |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | flute boy standing, sunrise | 653945 | 1033958 | 1536x2752 | x1397 y2613, 51 px, score 0.933 | 1 / 0 | remove_sparkle | true | clean | Star gone. Faint soft smear on one dark grass stroke. Small at normal size. |
| G2 | flute boy seated | 723614 | 1179928 | 1536x2752 | x1397 y2613, 51 px, score 0.936 | 1 / 0 | remove_sparkle | true | clean | Star gone. Patch on flat sand-brown background, almost invisible. |
| G3 | empty river-bank plate | 872860 | 1511574 | 1536x2752 | x1397 y2613, 51 px, score 0.661 | 1 / 0 | remove_sparkle | true | clean | Star gone, but a clear grey-yellow blurred patch (~70 px) where ink lines were erased. Visible smudge. |
| G4 | old sage under banyan | 1173613 | 2139641 | 1536x2752 | x1397 y2613, 51 px, score 0.921 | 1 / 0 | remove_sparkle | true | clean | Star gone. Dark smear where one vertical ink stroke was lost. Visible at zoom. |

Notes
- LaMa fallback was never needed (remove_sparkle passed the stamp check on all 4).
- The stamp sits 88 px from the right and bottom edges on all four (same Flow watermark position).
- G3 matched at score 0.661, below the normal THR 0.7. It was accepted through the small-star anchor rule (ANCHOR_THR 0.5, the anchor sits near the stamp position).
- Clean files were written as JPEG by cv2 (default quality). Sizes grew 1.6x to 1.8x. Finals in the repo are PNG; a PNG output is needed before any final use.
- Download method: javascript anchor-click hook plus URL.createObjectURL hook; the first download attempt on a page did nothing, the second worked. Decoded with a small script (no browser save).

## Conclusion
- The remover does what its check measures: the Flow star is gone on 4 of 4 real Flow 2K finals (0 stamps left), and every file passes `verified`.
- The check does not measure the fill. The fill is visible as a smudge on G3 (clear) and G4 (visible). G1 and G2 are close to clean.
- Good enough on flat or soft backgrounds (G1, G2). Not good enough on finals with ink lines through the corner (G3, G4) without a visual look.
- Threshold advice: do not lower THR (0.7). Route any stamp with score below about 0.8, or any stamp that sits on ink lines, to LaMa and compare the two results by eye before picking one. Keep a human or Claude look at every corner crop before a final is accepted. Add a smudge metric to the check if the remover is used unattended.

## Rerun with the proven system (M-21, 11-12)
Tool: `director/watermark_auto.py` aligned to IMAGE_SYSTEM_FULL.md section 13: LaMa from the ORIGINAL first, `lama_on_clean` second, alpha-only only with `--allow-alpha-only`; PNG master `<name>__final.png`; variant in `_sparkle_check/`; `watermark_log.jsonl` with the lama_inpaint fields plus stamps_before/after, min_stamp_score, needs_review; missing weights raise `WeightsMissingError`. 17 tests pass.
Run on COPIES (`copies2/`), originals in `raw/` untouched. Output `final2/`, crops (raw | old alpha | new LaMa, 480 px, viewed at full size) in `crops2/`.

| # | Method | Stamps before/after | Min score | needs_review | Look at crop |
|---|---|---|---|---|---|
| G1 | lama | 1 / 0 | 0.933 | false | Clean. Ink lines continue through the corner; old faint smear gone. |
| G2 | lama | 1 / 0 | 0.936 | false | Clean. Flat brown ground, no patch visible. |
| G3 | lama | 1 / 0 | 0.661 | true (marginal) | The grey-yellow blurred patch is GONE; grass strokes are redrawn. A very faint light diagonal ghost of the star remains near the top-left of the old position: visible only at 4x zoom. Owner should glance at it. |
| G4 | lama | 1 / 0 | 0.921 | false | The dark smear is GONE. One vertical ink stroke is replaced by faint hatching (not identical to the original stroke) but no smudge. |

Honest verdict: G3 and G4 smudges are gone with LaMa-from-original; the fill is invented texture, so G3 keeps a faint trace and G4 loses one stroke's weight. The check still only counts stamps, not fill quality, so the needs_review flag plus a human look stays required. LaMa weights live at `D:/aai work/anime_studio/flow/lama_weights/big-lama.pt` (not in this worktree; lama_inpaint.WEIGHTS resolves it).
