"""Automatic Flow-watermark (corner sparkle) removal for 2K images: LaMa from the original first, lama_on_clean second, a measured check.

process(image) never touches the original file. A PNG master <name>__final.png is written into out_dir (variants in _sparkle_check/), and one
JSON line goes to watermark_log.jsonl. status "clean" = the check passed; "needs_manual" = it did not (no __final file,
no success claimed). Alpha-only removal runs only with allow_alpha_only. The LaMa model and torch load lazily.

Check (sparkle_left): the same stamp detector that remove_sparkle uses (template match, THR 0.7, tuned on real Flow
finals) must find NO stamp in the corner window after cleaning. Image too small for the window: unverified.
(A brightness/edge box-vs-control test was tried first; a strong sparkle hides the art texture inside it, so the
edge energy went DOWN. Rejected.)

CLI: python director/watermark_auto.py PATH [--out DIR] [--record FILE]   (PATH = one image or a folder)
     python director/watermark_auto.py --calibrate CLEAN_DIR DIRTY_DIR   (reports stamp counts only, sets nothing)
"""
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

FLOW_SCRIPTS = Path(__file__).resolve().parents[1] / "flow" / "scripts"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
RECORD_NAME = "watermark_log.jsonl"
MARGINAL_SCORE = 0.8                 # stamp match below this = marginal: a human looks at the crop
WEIGHTS_NAME = "big-lama.pt"
_LAMA = {}                            # cached LaMa model, filled on first fallback only


class WatermarkInputError(ValueError):
    """Empty, unreadable or non-image input: refused before any work."""


class WeightsMissingError(RuntimeError):
    """LaMa weights missing: refused, never a silent fall back to the smudging alpha-only method."""


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


def _lama_model():
    lama = _flow_module("lama_inpaint")
    if not Path(lama.WEIGHTS).is_file():
        raise WeightsMissingError(f"LaMa weights not found: {lama.WEIGHTS} (use --allow-alpha-only to accept the smudging method)")
    if "model" not in _LAMA:
        _LAMA["model"] = lama.load_model()
    return lama, _LAMA["model"]


def _lama_method(rgb):
    """Proven default: LaMa fills the stamp window of the ORIGINAL."""
    lama = _flow_module("lama_inpaint")
    rs = _flow_module("remove_sparkle")
    if not lama.stamps_of(rgb, rs.THR):
        return rgb.copy()
    lama, model = _lama_model()
    return lama.lama_blend(rgb, lama.sparkle_mask(rgb, rs.THR), model)


def _lama_on_clean_method(rgb):
    """Hybrid: LaMa on the alpha-cleaned image with the small residue mask (for faint alpha residue)."""
    lama = _flow_module("lama_inpaint")
    rs = _flow_module("remove_sparkle")
    if not lama.stamps_of(rgb, rs.THR):
        return rgb.copy()
    lama, model = _lama_model()
    return lama.lama_blend(_remove_sparkle_method(rgb), lama.sparkle_mask(rgb, rs.THR, lama.RESIDUE_DILATE), model)


def _min_score(rgb):
    rs = _flow_module("remove_sparkle")
    scores = [st[0] for st in rs.find_stars(rgb, rs.THR)]
    return min(scores) if scores else None


def _append_record(record_path, rec):
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with open(record_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + chr(10))


def _write_png(path, rgb):
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)), f"write failed: {path}"


def process(image_path, out_dir, *, lama=None, lama_on_clean=None, alpha_only=None, allow_alpha_only=False,
            record_path=None):
    """Clean one image (proven system, IMAGE_SYSTEM_FULL.md section 13). Candidates, each verified by sparkle_left == 0:
    lama (from the ORIGINAL) -> lama_on_clean -> alpha_only (only with allow_alpha_only). The master is a PNG
    <name>__final.png in out_dir; every verified variant is kept in out_dir/_sparkle_check/. The original is never touched.
    needs_review is true when the method was not plain lama or the stamp match was marginal (score < MARGINAL_SCORE)."""
    src = Path(image_path)
    rgb = load_rgb(src)                                   # refuses before any work
    out_dir = Path(out_dir)
    dst = out_dir / f"{src.stem}__final.png"
    if dst.resolve() == src.resolve():
        raise WatermarkInputError(f"output would overwrite the original: {src}")
    steps = [("lama", lama or _lama_method), ("lama_on_clean", lama_on_clean or _lama_on_clean_method)]
    if allow_alpha_only:
        steps.append(("alpha_only", alpha_only or _remove_sparkle_method))
    before = sha256_file(src)
    stamps_before = sparkle_left(rgb)
    score = _min_score(rgb)
    method, cand, stamps_left, errors = None, None, None, []
    for name, fn in steps:
        try:
            out = fn(rgb)
        except WeightsMissingError:
            if not allow_alpha_only:
                raise                                     # never a silent fall back to the smudging method
            errors.append(f"{name}: LaMa weights missing")
            continue
        except Exception as exc:                          # a failing method is a failed check, not a crash
            errors.append(f"{name}: {exc}")
            continue
        left = sparkle_left(out)
        if left == 0:
            _write_png(out_dir / "_sparkle_check" / f"{src.stem}__{name}.png", out)
            method, cand, stamps_left = name, out, 0
            break
        else:
            stamps_left = left
            errors.append(f"{name}: stamps left {left}")
    verified = cand is not None
    after = None
    if verified:
        _write_png(dst, cand)
        after = sha256_file(dst)
    marginal = score is not None and score < MARGINAL_SCORE
    rec = {"time": datetime.datetime.now().astimezone().isoformat(), "title": src.stem, "method": method,
           "verdict": "auto_verified" if verified else "needs_manual", "final_sha256": after,
           "weights": Path(WEIGHTS_NAME).name, "backfilled": False,
           "path": str(src), "clean_path": str(dst) if verified else None, "sha256_before": before, "sha256_after": after,
           "verified": verified, "status": "clean" if verified else "needs_manual",
           "stamps_before": stamps_before, "stamps_after": stamps_left, "stamps_left": stamps_left, "min_stamp_score": score,
           "needs_review": (not verified) or method != "lama" or marginal, "errors": errors}
    _append_record(Path(record_path) if record_path else out_dir / RECORD_NAME, rec)
    return rec


def process_folder(folder, out_dir, *, record_path=None, **kw):
    """Clean every image in folder (skips *__final.* files). Returns counts; refused inputs are counted, not raised."""
    counts = {"total": 0, "clean": 0, "needs_manual": 0, "refused": 0}
    for p in sorted(Path(folder).iterdir()):
        if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES or p.stem.endswith("__final"):
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
    ap.add_argument("--allow-alpha-only", action="store_true",
                    help="allow plain alpha inversion as a last resort (leaves smudges; default off)")
    ap.add_argument("--calibrate", nargs=2, metavar=("CLEAN_DIR", "DIRTY_DIR"),
                    help="report stamp counts for known-clean and known-dirty folders; changes nothing")
    a = ap.parse_args(argv)
    if a.calibrate:
        print(json.dumps(calibrate(*a.calibrate), ensure_ascii=False, indent=1))
        return
    if a.path is None:
        ap.error("give PATH, or --calibrate CLEAN_DIR DIRTY_DIR")
    if a.path.is_dir():
        print(process_folder(a.path, a.out or a.path, record_path=a.record, allow_alpha_only=a.allow_alpha_only))
    else:
        print(json.dumps(process(a.path, a.out or a.path.parent, record_path=a.record,
                                     allow_alpha_only=a.allow_alpha_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
