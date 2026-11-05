"""Continuity sheet for one candidate image (universal Flow image system, 2026-11-01).

  python scripts/flow/neighbour_sheet.py --jobs canon/drafts/A1_flow_jobs_v2.json --shot SH_S2_09 --candidate <png> --out <jpg>

Top row: PREVIOUS shot | CANDIDATE | NEXT shot (the film order from the job), each labelled with its Flow title.
Bottom row: the reference sheets of every visible character and the place sheet. A missing neighbour is a grey 'none' box.
Read by the Haiku agent and by the Codex reviewer (review_shot.py) to judge the cut in and out of the shot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, PAD, LABEL, REF_H = 960, 540, 16, 34, 300


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _tile(path: str | None, label: str, w: int, h: int, border: tuple | None = None) -> Image.Image:
    tile = Image.new("RGB", (w, h + LABEL), (40, 40, 40))
    if path and Path(path).is_file():
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((w, h))
            tile.paste(im, ((w - im.width) // 2, LABEL + (h - im.height) // 2))
    else:
        ImageDraw.Draw(tile).text((w // 2 - 30, LABEL + h // 2), "none", fill=(160, 160, 160), font=_font(28))
    d = ImageDraw.Draw(tile)
    d.text((8, 4), label, fill=(255, 255, 255), font=_font(24))
    if border:
        d.rectangle([0, 0, w - 1, h + LABEL - 1], outline=border, width=6)
    return tile


def build_sheet(job: dict, candidates, out: Path) -> Path:
    """Top row PREVIOUS | CANDIDATE A [| CANDIDATE B] | NEXT (both images of an x2 submit on one sheet), bottom row the reference sheets.
    A candidate may be a 2K file or a browser screenshot of the Flow tile (no download needed for review)."""
    cands = [candidates] if isinstance(candidates, (str, Path)) else list(candidates)
    w, h = (W, H) if len(cands) == 1 else (720, 405)
    prev, nxt = job.get("previous_shot") or {}, job.get("next_shot") or {}
    top = [_tile(prev.get("file"), f"PREVIOUS  {prev.get('flow_title', '-')}", w, h)]
    top += [_tile(str(c), f"CANDIDATE {'AB'[k]}  {Path(c).stem[:28]}", w, h, border=(230, 160, 20)) for k, c in enumerate(cands)]
    top += [_tile(nxt.get("file"), f"NEXT  {nxt.get('flow_title', '-')}", w, h)]
    refs = [_tile(p, f"REF  {Path(p).stem[:34]}", int(REF_H * 1.6), REF_H) for p in job.get("sheets", [])]
    width = len(top) * w + (len(top) + 1) * PAD
    height = PAD + h + LABEL + PAD + ((REF_H + LABEL + PAD) if refs else 0)
    sheet = Image.new("RGB", (width, height), (18, 18, 18))
    for k, t in enumerate(top):
        sheet.paste(t, (PAD + k * (w + PAD), PAD))
    x = PAD
    for t in refs:
        if x + t.width > width - PAD:
            break
        sheet.paste(t, (x, PAD + h + LABEL + PAD))
        x += t.width + PAD
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=Path, required=True)
    ap.add_argument("--shot", required=True)
    ap.add_argument("--candidate", required=True, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    job = next((j for j in json.loads(a.jobs.read_text(encoding="utf-8")) if j["shot_id"] == a.shot), None)
    if job is None:
        print("REFUSED: shot not in the job file")
        return 2
    if not all(Path(c).is_file() for c in a.candidate):
        print("REFUSED: candidate file missing")
        return 2
    print("sheet ->", build_sheet(job, a.candidate, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
