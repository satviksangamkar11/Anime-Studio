"""Exact centred crop + resize of a Flow keyframe to a video-model size.

bridge() takes the largest centred window of the SOURCE with the TARGET aspect
(exact Fractions) and resamples only that window to the target size in one
Lanczos pass (Image.resize box=...). Sources whose aspect is off by more than
tol_pct are refused; target sides must be multiples of 32.

  bridge_flow_to_h3.py --src IN.png --out OUT.png [--size 864x1536]
  bridge_flow_to_h3.py --final-dir DIR --out-dir DIR [--size 864x1536] [--dry-run]
"""
import argparse
import glob
import json
import os
import sys
from fractions import Fraction

from PIL import Image

PATTERN = "LEAP-*__candidate_v01__final.png"
DEFAULT_SIZE = (864, 1536)
DEFAULT_TOL_PCT = 3.0


def parse_size(text):
    try:
        w, h = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"size must look like 864x1536, got {text!r}")
    return w, h


def plan(src_size, size, tol_pct=DEFAULT_TOL_PCT):
    """Return (box, aspect_error_pct, crop_px_removed) for src_size -> size, or raise ValueError."""
    tw, th = size
    if tw % 32 or th % 32:
        raise ValueError(f"target {tw}x{th} must have both sides divisible by 32")
    sw, sh = src_size
    src_aspect = Fraction(sw, sh)
    target = Fraction(tw, th)
    off_pct = abs(src_aspect - target) / target * 100
    if off_pct > Fraction(str(tol_pct)):
        raise ValueError(f"source {sw}x{sh} aspect is {float(off_pct):.2f}% off {tw}x{th} (limit {tol_pct}%)")
    if src_aspect > target:  # too wide: keep full height, trim left and right
        win_h = Fraction(sh)
        win_w = win_h * target
    else:  # too tall: keep full width, trim top and bottom
        win_w = Fraction(sw)
        win_h = win_w / target
    left = (sw - win_w) / 2
    top = (sh - win_h) / 2
    box = tuple(float(v) for v in (left, top, left + win_w, top + win_h))
    box_aspect = (box[2] - box[0]) / (box[3] - box[1])
    aspect_error_pct = abs(box_aspect / float(target) - 1) * 100
    crop_px_removed = round(float((sw - win_w) + (sh - win_h)), 3)  # source px trimmed on the cropped axis
    return box, aspect_error_pct, crop_px_removed


def bridge(src_path, dst_path, size=DEFAULT_SIZE, tol_pct=DEFAULT_TOL_PCT):
    """Write src_path cropped+resized to size as PNG at dst_path; return a report dict."""
    if os.path.abspath(src_path) == os.path.abspath(dst_path):
        raise ValueError("dst must not be the source file")
    with Image.open(src_path) as im:
        src = im.convert("RGB")
    box, aspect_error_pct, crop_px_removed = plan(src.size, size, tol_pct)
    size = tuple(size)
    src.resize(size, Image.LANCZOS, box=box).save(dst_path, format="PNG")
    with Image.open(dst_path) as chk:
        if chk.size != size:
            raise RuntimeError(f"wrote {chk.size} to {dst_path}, expected {size}")
    return {"src": src_path, "dst": dst_path, "src_size": src.size, "box": box,
            "size": size, "aspect_error_pct": aspect_error_pct, "crop_px_removed": crop_px_removed}


def _box_text(box):
    return "(" + ", ".join(f"{v:.3f}" for v in box) + ")"


def _convert(src, dst, size, tol_pct, dry_run, records=None):
    """Handle one source. Prints one line and returns OK, SKIP, DRY or REFUSED.
    records (a list) turns printing off and collects one dict per source instead (--json, G9)."""
    label = os.path.basename(src).split("__")[0]
    w, h = size
    rec = {"label": label, "status": None, "src": src, "dst": dst, "src_size": None, "box": None, "removed_px": None, "reason": None}
    if records is not None:
        records.append(rec)

    def say(line):
        if records is None:
            print(line)

    try:
        if os.path.exists(dst):
            with Image.open(dst) as im:
                existing = im.size
            if existing == (w, h):
                rec["status"] = "SKIP"
                say(f"SKIP     {label} -> {dst} (already {w}x{h})")
                return "SKIP"
            raise ValueError(f"{dst} exists as {existing[0]}x{existing[1]}; not overwriting")
        with Image.open(src) as im:
            src_size = im.size
        rec["src_size"] = list(src_size)
        box, _, removed = plan(src_size, size, tol_pct)
        rec["box"], rec["removed_px"] = [float(v) for v in box], removed
        if dry_run:
            rec["status"] = "DRY"
            say(f"DRY-RUN  {label} {src_size[0]}x{src_size[1]} -> {dst} box={_box_text(box)} removed={removed}px")
            return "DRY"
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        r = bridge(src, dst, size, tol_pct)
    except (ValueError, OSError) as e:
        rec["status"], rec["reason"] = "REFUSED", str(e)
        say(f"REFUSED  {label}: {e}")
        return "REFUSED"
    rec["status"] = "OK"
    say(f"OK       {label} {r['src_size'][0]}x{r['src_size'][1]} -> {dst} "
        f"box={_box_text(r['box'])} removed={r['crop_px_removed']}px")
    return "OK"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exact centred crop + resize of Flow keyframes.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--src", help="one source PNG")
    mode.add_argument("--final-dir", help="folder holding LEAP-*__candidate_v01__final.png files")
    ap.add_argument("--out", help="output PNG (with --src)")
    ap.add_argument("--out-dir", help="output folder (with --final-dir)")
    ap.add_argument("--size", type=parse_size, default=DEFAULT_SIZE, help="WxH, default 864x1536")
    ap.add_argument("--dry-run", action="store_true", help="print what would be written; write nothing")
    ap.add_argument("--json", action="store_true", help="print one JSON list of records (status, box, removed_px, reason) and nothing else")
    ap.add_argument("--pattern", default=PATTERN, help="file pattern inside --final-dir (default: %(default)s)")
    args = ap.parse_args(argv)
    records = [] if args.json else None

    if args.src:
        if not args.out:
            ap.error("--src needs --out")
        statuses = [_convert(args.src, args.out, args.size, DEFAULT_TOL_PCT, args.dry_run, records)]
    else:
        if not args.out_dir:
            ap.error("--final-dir needs --out-dir")
        files = sorted(glob.glob(os.path.join(args.final_dir, args.pattern)))
        if not files:
            if args.json:
                print("[]")
            else:
                print(f"NO FILES matching {args.pattern} in {args.final_dir}")
            return 1
        w, h = args.size
        statuses = []
        for f in files:
            leap = os.path.basename(f).split("__")[0]
            dst = os.path.join(args.out_dir, f"{leap}_{w}x{h}.png")
            statuses.append(_convert(f, dst, args.size, DEFAULT_TOL_PCT, args.dry_run, records))
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=1))
    return 1 if "REFUSED" in statuses else 0


if __name__ == "__main__":
    sys.exit(main())
