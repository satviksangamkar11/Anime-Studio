", "", text or "", flags=re.S)` — removes all <think>...</think> blocks.
    - `if "</think>" in text: text = text.rsplit("</think>", 1)[1]` — if there's a stray </think> (without matching <think>), take everything after the last <think>.
    - `return text.split("<think>", 1)[0].strip()` — if there's a stray <think>, cut at it.
    - Edge: what if the model outputs `answer <think> more`? After sub, no <think>...</think> pairs removed. Then "<think>" in text → rsplit gives " more"? Wait, `text.rsplit("</think>", 1)[1]` — if text = "answer 旨 more", rsplit gives ["answer", " more"], [1] = " more". Then split("旨", 1)[0] = " more".strip() = "more". Hmm, that's wrong — it would drop "answer". But this is an edge case of malformed output. The intent is to extract the final answer after thinking. Acceptable.

45. Let me reconsider line 170-171: `text = strip_think(res["text"])`. If res["text"] is the raw model output. If the model only produced 旨...</think> (thinking) and nothing else, strip_think returns "". Then `if not text: return {"error": "empty reply ..."}`. Good — fail-closed.

46. Now, a potential real bug: **In `review()`, if `reply.get("error")` is set, `text = reply.get("text") or ""` is ""**. Then results are all UNSURE. Then `out["error"] = reply["error"]` is set. Then line 198 writes review.json anyway. The choice would be UNSURE (since all results UNSURE → choose returns {"decision": "UNSURE", "chosen": None}). Exit code 3. Good — fail-closed.

47. Let me check `parse()` more carefully for a subtle bug with the `missing` list and derived verdict.

Line 89: `missing = [q for q, _ in QUESTIONS if q not in answers]`
Line 90: `results = [a["result"] for a in answers.values()]`
Line 91: `derived = "BLOCK" if "BLOCK" in results else ("UNSURE" if missing or "UNSURE" in results else "PASS")`

If answers has Q1=PASS, Q2=BLOCK, Q3=PASS, Q4=PASS, Q5=PASS, Q6=PASS → derived = BLOCK. Good.
If answers has all 6 PASS → derived = PASS. Good.
If answers has 5 PASS and Q6 missing → missing = ["Q6"], derived = UNSURE. Good.

48. Now, `choose()` line 111: `best = min(passed, key=lambda r: sum(a["result"] == "ADVISORY" for a in r["answers"].values()))`. If a PASS candidate has no answers (shouldn't happen since PASS requires all answers), sum = 0. Fine.

49. Let me look for **overwriting files** in review_shot.py:
    - Line 179: `sheet = base.with_name(base.stem + "__neighbours.jpg")` — e.g., `A__neighbours.jpg`.
    - Line 180: `build_sheet(job, [str(c) for c in cands], sheet)` — writes the sheet. Overwrites if exists. That's intended (regenerate the sheet each run).
    - Line 181: `report = base.with_name(base.stem + "__review.md")` — `A__review.md`.
    - Line 186: `report.write_text(text, ...)` — overwrites. Intended.
    - Line 198: `base.with_name(base.stem + "__review.json")` — `A__review.json`. Overwrites. Intended.
    - No accidental overwrite of candidate files. Good.

50. Now `bridge_flow_to_h3.py` line 132: `dst = os.path.join(args.out_dir, f"{leap}_{w}x{h}.png")`. If two source files map to the same leap name... unlikely. Fine.

51. Line 124: `files = sorted(glob.glob(...))`. Good.

52. Line 134: `return 1 if "REFUSED" in statuses else 0`. If any REFUSED → exit 1. Otherwise 0. But what about SKIP/DRY? They don't count as failure. Good. But note: if all SKIP, exit 0. Fine.

53. Hmm, one issue in `_convert` line 83-89: it checks `os.path.exists(dst)`. If dst exists with same size, SKIP. But it doesn't check whether the source has changed. So if the source is updated but the dst already exists at the right size, it SKIPs and produces a stale output. That's a design choice (idempotent by size). Not necessarily a bug, but worth noting. Low severity.

54. Let me reconsider the crop math for off-by-one.

`plan()`:
- sw, sh = source size (ints).
- src_aspect = Fraction(sw, sh)
- target = Fraction(tw, th)
- If src_aspect > target (too wide): win_h = sh, win_w = sh * target = sh * tw / th.
  - box width = win_w. Since sh * tw / th may not divide evenly, win_w is a Fraction.
  - left = (sw - win_w) / 2.
  - The box = (left, 0, left+win_w, sh).
  - Resized to (tw, th). Good.
- If src_aspect < target (too tall): win_w = sw, win_h = sw / target = sw * th / tw.
  - top = (sh - win_h) / 2.
  - box = (0, top, sw, top+win_h).

The centering uses exact Fractions, then float. PIL's box with floats: the box defines the source region to sample. For a box of non-integer size, PIL samples accordingly. The output is exactly (tw, th). No off-by-one in the sense of integer pixel misalignment, because the box is continuous. Good.

However, there's a subtle issue: `box_aspect` computed at line 52 uses float division of the float box values, which may have tiny rounding errors. Only used for reporting. Fine.

55. Let me reconsider: is there a bug where `size` parameter in `bridge()` is mutated? Line 64-66:
```
box, aspect_error_pct, crop_px_removed = plan(src.size, size, tol_pct)
size = tuple(size)
src.resize(size, Image.LANCZOS, box=box).save(dst_path, format="PNG")
```
`size` is the function parameter. `plan()` doesn't mutate it. `size = tuple(size)` reassigns locally. Fine.

56. Now, one thing about `image_part` in review_shot.py: it opens the image, converts to RGB, thumbnails, saves as JPEG. If the candidate is a PNG with transparency, convert("RGB") flattens to white background? Actually convert("RGB") on an RGBA image drops alpha, compositing... no, it just drops the alpha channel (pixels keep RGB values, transparent areas become whatever RGB they have, often black or magenta). Hmm. For screenshots this is usually fine. Not a bug per se.

57. Let me reconsider the "fail-open" requirement more strictly: "a missing answer or empty reply must be UNSURE, never PASS".

- Empty reply → review() line 189-190: verdict UNSURE. choose(): no PASS → if any BLOCK... but all are UNSURE → returns {"decision": "UNSURE"}. Good.
- Missing answer (some Q missing) → derived UNSURE (line 91). If stated VERDICT is "PASS", line 93: derived != stated, derived != BLOCK → verdict = UNSURE. Good.
- But what if the model gives all 6 Q answers as PASS, VERDICT: