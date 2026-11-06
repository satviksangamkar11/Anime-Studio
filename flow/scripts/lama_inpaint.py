"""LaMa inpainting for the Flow corner sparkle, always starting from the ORIGINAL watermarked PNG.

Per image: the stamp mask comes from remove_sparkle (every star it finds, dilated). The bottom-right
CROP x CROP window goes through LaMa (big-lama.pt, a TorchScript file, loaded with torch.jit.load
only). The LaMa output is blended back into a copy of the image with a feathered edge, inside the
window only. Two variants per image: 'lama' (original + mask) and 'lama_on_clean' (alpha-cleaned
image + smaller mask around the residue). finalize() writes the chosen one as __final.png.

Layout (after tidy_final.py): the watermarked input is read from final/_original_with_watermark (fallback:
final/_intermediates, then final/); __lama.png goes to final/_intermediates; the master __final.png goes to final/.
Nothing is overwritten unless --overwrite is given (checked before any work starts).

Usage:
  python lama_inpaint.py [final_dir]                     process every image, write variants and sheets
  python lama_inpaint.py finalize final_dir choices.json  choices: {title: {"method", "verdict"}}; also logs each master to <chapter>/watermark_log.jsonl
  python lama_inpaint.py backfill final_dir               one-time: log the methods already in _sparkle_check3/report.json
  options: --originals NAME --intermediates NAME --overwrite
"""
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import remove_sparkle as rs  # noqa: E402  (templates, find_stars, stamp_mask, read_rgb)

WEIGHTS = Path("D:/aai work/anime_studio/flow/lama_weights/big-lama.pt")
CROP = 640          # LaMa window, bottom-right corner, multiple of 8
DILATE = 10         # px the stamp mask grows over the soft edge and halo
RESIDUE_DILATE = 4  # px, smaller mask for LaMa on the alpha-cleaned image
FEATHER = 4.0       # blend sigma; the transition is about 6-10 px wide
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_model(path=WEIGHTS):
    return torch.jit.load(str(path), map_location=DEVICE).eval()


def stamps_of(rgb, thr):
    """(hh, y, x) of each stamp, window coordinates (bottom-right BOX x BOX)."""
    return [(hh, y, x) for _, hh, y, x in rs.find_stars(rgb, thr)]


def sparkle_mask(rgb, thr, dilate=DILATE):
    """Full-size uint8 mask of all stamps, grown by `dilate` px. Zero outside the corner window."""
    h, w = rgb.shape[:2]
    m = np.zeros((h, w), np.uint8)
    m[h - rs.BOX:, w - rs.BOX:] = rs.stamp_mask((rs.BOX, rs.BOX), stamps_of(rgb, thr))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate + 1, 2 * dilate + 1))
    return cv2.dilate(m, k)


def lama_blend(rgb, mask, model):
    """rgb with LaMa filling `mask` inside the bottom-right CROP window. Nothing outside the window changes."""
    h, w = rgb.shape[:2]
    y0, x0 = h - CROP, w - CROP
    assert not mask[:y0].any() and not mask[:, :x0].any(), "mask reaches outside the LaMa window"
    img = rgb[y0:, x0:]
    hole = mask[y0:, x0:] > 0
    x = torch.from_numpy(img.astype(np.float32) / 255).permute(2, 0, 1)[None].to(DEVICE)
    m = torch.from_numpy(hole.astype(np.float32))[None, None].to(DEVICE)
    with torch.inference_mode():
        y = model(x, m)[0].clamp(0, 1).permute(1, 2, 0).cpu().numpy() * 255
    assert y.shape[:2] == img.shape[:2], f"model returned {y.shape}, expected {img.shape}"
    a = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), FEATHER)[..., None]
    a[a < 0.01] = 0
    out = rgb.copy()
    out[y0:, x0:] = np.clip(np.round(img * (1 - a) + y * a), 0, 255).astype(np.uint8)
    return out


def changed_outside(before, after):
    """Pixels that differ outside the LaMa window (must be 0)."""
    h, w = before.shape[:2]
    diff = np.any(before != after, axis=2)
    diff[h - CROP:, w - CROP:] = False
    return int(diff.sum())


def write_rgb(path, rgb):
    assert cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)), f"write failed: {path}"


def big_star_centre(rgb, stamps):
    """Full-image (x, y) centre of the largest stamp."""
    h, w = rgb.shape[:2]
    hh, y, x = max(stamps)
    n = 2 * hh + 3
    return w - rs.BOX + x + n // 2, h - rs.BOX + y + n // 2


def sheet(path, panels, centre):
    """Panels side by side: 100x100 px around the big star, enlarged 4x to 400x400, labelled."""
    cx, cy = centre
    tiles = []
    for label, img in panels:
        tile = cv2.resize(img[cy - 50:cy + 50, cx - 50:cx + 50], (400, 400), interpolation=cv2.INTER_CUBIC)
        tile = np.ascontiguousarray(tile)
        cv2.putText(tile, label, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        tiles.append(np.pad(tile, ((0, 0), (0, 8), (0, 0))))
    write_rgb(path, np.hstack(tiles))


def process(final, model=None, originals=rs.ORIGINALS, intermediates=rs.INTERMEDIATES, overwrite=False):
    """Reads the original from final/<originals>/ (fallback: intermediates, then final/) and the alpha-cleaned image from
    final/<intermediates>/. Writes __lama.png to final/<intermediates>/ and the sheets and report to final/_sparkle_check3/."""
    out_dir = final / "_sparkle_check3"
    inter = final / intermediates
    inputs = rs.input_titles(final, originals, intermediates)
    rs.check_free([p for t in inputs for p in (inter / f"{t}__candidate_v01__lama.png", out_dir / f"{t}__lama_on_clean.png",
                                              out_dir / f"{t}__sheet.png")], overwrite)
    missing = [t for t in inputs if not (inter / f"{t}__candidate_v01__clean.png").is_file()]
    if missing:
        raise FileNotFoundError(f"no __clean.png in {inter} for: {missing}")
    out_dir.mkdir(exist_ok=True)
    inter.mkdir(exist_ok=True)
    if model is None:
        model = load_model()
    report = {}
    for title, src in inputs.items():
        orig = rs.read_rgb(src)
        clean = rs.read_rgb(inter / f"{title}__candidate_v01__clean.png")
        thr = rs.THR_FOR.get(title, rs.THR)
        stamps = stamps_of(orig, thr)
        assert stamps, f"{title}: no stamp found"
        lama = lama_blend(orig, sparkle_mask(orig, thr), model)
        lama_clean = lama_blend(clean, sparkle_mask(orig, thr, RESIDUE_DILATE), model)
        write_rgb(inter / f"{title}__candidate_v01__lama.png", lama)
        write_rgb(out_dir / f"{title}__lama_on_clean.png", lama_clean)
        sheet(out_dir / f"{title}__sheet.png",
              [("before", orig), ("clean(alpha)", clean), ("lama", lama), ("lama_on_clean", lama_clean)],
              big_star_centre(orig, stamps))
        report[title] = {"stamps": stamps,
                         "changed_outside_window": {"lama": changed_outside(orig, lama),
                                                    "lama_on_clean": changed_outside(orig, lama_clean)}}
        print(title, stamps, report[title]["changed_outside_window"])
    (out_dir / "report.json").write_text(json.dumps(report, indent=1))


def log_watermark(final, title, method, verdict, backfilled=False):
    """Append-only record of HOW each master was made (method lama | lama_on_clean | clean, the owner/Claude verdict, sha256 of the master): <chapter>/watermark_log.jsonl."""
    master = final / f"{title}__candidate_v01__final.png"
    rec = {"time": datetime.datetime.now().astimezone().isoformat(), "title": title, "method": method, "verdict": verdict,
           "final_sha256": hashlib.sha256(master.read_bytes()).hexdigest(), "weights": WEIGHTS.name, "backfilled": backfilled}
    with open(final.parent / "watermark_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def backfill(final):
    """One-time: log the method already recorded in _sparkle_check3/report.json for masters that have no log line yet."""
    report = json.loads((final / "_sparkle_check3" / "report.json").read_text())
    log = final.parent / "watermark_log.jsonl"
    seen = {json.loads(l)["title"] for l in log.read_text(encoding="utf-8").splitlines() if l.strip()} if log.is_file() else set()
    n = 0
    for title, v in report.items():
        if title not in seen and v.get("method") and (final / f"{title}__candidate_v01__final.png").is_file():
            log_watermark(final, title, v["method"], v.get("verdict"), backfilled=True)
            n += 1
    return n


def finalize(final, choices_path, originals=rs.ORIGINALS, intermediates=rs.INTERMEDIATES, overwrite=False):
    """Writes the chosen picture of each title as the master final/<T>__candidate_v01__final.png (the only file this writes)."""
    out_dir = final / "_sparkle_check3"
    inter = final / intermediates
    report = json.loads((out_dir / "report.json").read_text())
    choices = json.loads(Path(choices_path).read_text())
    srcs = {title: {"clean": inter / f"{title}__candidate_v01__clean.png",
                    "lama": inter / f"{title}__candidate_v01__lama.png",
                    "lama_on_clean": out_dir / f"{title}__lama_on_clean.png"}[c["method"]]
            for title, c in choices.items()}
    rs.check_free([final / f"{t}__candidate_v01__final.png" for t in choices], overwrite)
    missing = [str(p) for p in srcs.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"missing source picture(s): {missing}")
    for title, c in choices.items():
        rgb = rs.read_rgb(srcs[title])
        write_rgb(final / f"{title}__candidate_v01__final.png", rgb)
        orig = rs.read_rgb(rs.find_input(final, f"{title}__candidate_v01.png", originals, intermediates))
        report[title].update(method=c["method"], verdict=c["verdict"],
                             changed_outside_window=changed_outside(orig, rgb))
        log_watermark(final, title, c["method"], c["verdict"])
    (out_dir / "report.json").write_text(json.dumps(report, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("args", nargs="*", metavar="ARG", help="[final_dir], or: finalize final_dir choices.json")
    ap.add_argument("--originals", default=rs.ORIGINALS, help="sub-folder of final/ with the watermarked originals (default %(default)s)")
    ap.add_argument("--intermediates", default=rs.INTERMEDIATES, help="sub-folder of final/ for __clean.png and __lama.png (default %(default)s)")
    ap.add_argument("--overwrite", action="store_true", help="replace files that already exist (default: refuse)")
    a = ap.parse_args(argv)
    if a.args[:1] == ["backfill"]:
        if len(a.args) != 2:
            ap.error("backfill needs final_dir")
        print("logged", backfill(Path(a.args[1])), "masters")
    elif a.args[:1] == ["finalize"]:
        if len(a.args) != 3:
            ap.error("finalize needs final_dir and choices.json")
        finalize(Path(a.args[1]), a.args[2], a.originals, a.intermediates, a.overwrite)
    else:
        if len(a.args) > 1:
            ap.error("process takes at most one final_dir")
        process(Path(a.args[0]) if a.args else rs.FINAL, None, a.originals, a.intermediates, a.overwrite)


if __name__ == "__main__":
    main()
