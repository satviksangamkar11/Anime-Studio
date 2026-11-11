"""Automatic Flow-watermark (corner sparkle) removal for 2K images: remove_sparkle first, LaMa second, a measured check.

process(image) never touches the original file. A cleaned copy is written as <name>_clean<ext> into out_dir, and one
JSON line goes to watermark_log.jsonl. status "clean" = the check passed; "needs_manual" = it did not (no _clean file,
no success claimed). The LaMa model and torch are loaded only when the fallback runs, never at import time.

Check (sparkle_left): the same stamp detector that remove_sparkle uses (template match, THR 0.7, tuned on real Flow
finals) must find NO stamp in the corner window after cleaning. Image too small for the window: unverified.
(A brightness/edge box-vs-control test was tried first; a strong sparkle hides the art texture inside it, so the
edge energy went DOWN. Rejected.)

CLI: python director/watermark_auto.py PATH [--out DIR] [--record FILE]   (PATH = one image or a folder)
     python director/watermark_auto.py --calibrate CLEAN_DIR DIRTY_DIR   (reports stamp counts only, sets nothing)
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

FLOW_SCRIPTS = Path(__file__).resolve().parents[1] / "flow" / "scripts"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
RECORD_NAME = "watermark_log.jsonl"
_LAMA = {}                            # cached LaMa model, filled on first fallback only


class WatermarkInputError(ValueError):
    """Empty, unreadable or non-image input: refused before any work."""


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rgb(path):
    path = Path(path)
    if not path.is_file():
        raise WatermarkInputError(f"not a file: {path}")
    if path.stat().st_size == 0:
        raise WatermarkInputError(f"empty file: {path}")
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise WatermarkInputError(f"unreadable or not an image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _flow_module(name):
    if str(FLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(FLOW_SCRIPTS))
    return __import__(name)


def sparkle_left(rgb):
    """Number of Flow sparkle stamps still found in the corner (0 = clean). None if the image is too small to check."""
    rs = _flow_module("remove_sparkle")
    h, w = rgb.shape[:2]
    if h < rs.CROP or w < rs.CROP:
        return None
    return len(rs.find_stars(rgb, rs.THR))


def _remove_sparkle_method(rgb):
    rs = _flow_module("remove_sparkle")
    stamps = rs.find_stars(rgb, rs.THR)
    if not stamps:
        return rgb.copy()
    clean, _, _ = rs.process_group([("img", rgb, stamps)])["img"]
    return clean


def _lama_method(rgb):
    lama = _flow_module("lama_inpaint")
    rs = _flow_module("remove_sparkle")
    if not lama.stamps_of(rgb, rs.THR):
        return rgb.copy()
    if "model" not in _LAMA:
        _LAMA["model"] = lama.load_model()
    return lama.lama_blend(rgb, lama.sparkle_mask(rgb, rs.THR), _LAMA["model"])


def _append_record(record_path, rec):
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with open(record_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def process(image_path, out_dir, *, first=None, fallback=None, record_path=None):
    """Clean one image. first/fallback: rgb -> rgb callables (default remove_sparkle, then LaMa). Returns the record."""
    src = Path(image_path)
    rgb = load_rgb(src)                                   # refuses before any work
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{src.stem}_clean{src.suffix}"
    if dst.resolve() == src.resolve():
        raise WatermarkInputError(f"output would overwrite the original: {src}")
    before = sha256_file(src)
    steps = [("remove_sparkle", first or _remove_sparkle_method), ("lama", fallback or _lama_method)]
    method, cand, stamps_left, errors = None, None, None, []
    for name, fn in steps:
        try:
            out = fn(rgb)
        except Exception as exc:                          # a failing method is a failed check, not a crash
            errors.append(f"{name}: {exc}")
            continue
        left = sparkle_left(out)
        if left == 0:
            method, cand, stamps_left = name, out, 0
            break
        stamps_left = left
        errors.append(f"{name}: stamps left {left}")
    verified = cand is not None
    after = None
    if verified:
        if np.array_equal(cand, rgb):
            shutil.copyfile(src, dst)                     # already clean: keep the bytes, not a re-encode
        else:
            assert cv2.imwrite(str(dst), cv2.cvtColor(cand, cv2.COLOR_RGB2BGR)), f"write failed: {dst}"
        after = sha256_file(dst)
    rec = {"path": str(src), "clean_path": str(dst) if verified else None, "sha256_before": before,
           "sha256_after": after, "method": method, "verified": verified,
           "status": "clean" if verified else "needs_manual", "stamps_left": stamps_left, "errors": errors}
    _append_record(Path(record_path) if record_path else out_dir / RECORD_NAME, rec)
    return rec


def process_folder(folder, out_dir, *, record_path=None, **kw):
    """Clean every image in folder (skips *_clean.* files). Returns counts; refused inputs are counted, not raised."""
    counts = {"total": 0, "clean": 0, "needs_manual": 0, "refused": 0}
    for p in sorted(Path(folder).iterdir()):
        if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES or p.stem.endswith("_clean"):
            continue
        counts["total"] += 1
        try:
            rec = process(p, out_dir, record_path=record_path, **kw)
        except WatermarkInputError as exc:
            counts["refused"] += 1
            print(f"refused: {exc}")
            continue
        counts[rec["status"]] += 1
    return counts


def calibrate(clean_dir, dirty_dir):
    """Report the stamp count sparkle_left sees on folders of KNOWN-clean and KNOWN-dirty images.

    Reporting only: it sets no threshold and claims no calibration. The check is not calibrated on real Flow finals
    until someone runs this on real labelled folders and reads the numbers. Unreadable files are listed with an error.
    """
    report = {}
    for label, folder in (("clean", clean_dir), ("dirty", dirty_dir)):
        rows = []
        for p in sorted(Path(folder).iterdir()):
            if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            try:
                rows.append({"path": str(p), "stamps": sparkle_left(load_rgb(p))})
            except WatermarkInputError as exc:
                rows.append({"path": str(p), "error": str(exc)})
        report[label] = rows
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path, nargs="?", help="one image, or a folder of images")
    ap.add_argument("--out", type=Path, default=None, help="output folder (default: the input folder)")
    ap.add_argument("--record", type=Path, default=None, help=f"record file (default: <out>/{RECORD_NAME})")
    ap.add_argument("--calibrate", nargs=2, metavar=("CLEAN_DIR", "DIRTY_DIR"),
                    help="report stamp counts for known-clean and known-dirty folders; changes nothing")
    a = ap.parse_args(argv)
    if a.calibrate:
        print(json.dumps(calibrate(*a.calibrate), ensure_ascii=False, indent=1))
        return
    if a.path is None:
        ap.error("give PATH, or --calibrate CLEAN_DIR DIRTY_DIR")
    if a.path.is_dir():
        print(process_folder(a.path, a.out or a.path, record_path=a.record))
    else:
        print(json.dumps(process(a.path, a.out or a.path.parent, record_path=a.record), ensure_ascii=False))


if __name__ == "__main__":
    main()
