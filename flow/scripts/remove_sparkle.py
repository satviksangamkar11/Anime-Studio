"""Remove Flow's corner sparkle from anime FINAL images, keeping every original.

The sparkle is one alpha blend, I = (1 - a) J + a C, with C = white. Images of one size in a group share
the same 4-point stamp shape at the same offsets; each stamp has its own strength, and the art J changes.
Per group (10 portrait, 8 landscape), inside the bottom-right BOX x BOX window:
  1. Find the stamps per image (template match).
  2. Background B under the stamps: harmonic (Laplace) interpolation from the ring around them.
     The alpha proxy a = (I - B) / (C - B) is then exact at the stamp edge and approximate inside.
  3. Shape T per size class: median over the group of the proxies, each stamp shifted to its best
     integer position and divided by its strength. One shape, shared by every image of the group.
  4. Strength s per stamp: plateau of the proxy, then matched so the recovered stamp core has the mean
     brightness of the ring just outside it. Overlapping stamps combine as 1 - prod(1 - s T).
  5. Recover J = C + (I - C) / (1 - a). Within RING px of a stamp edge the measured proxy is used.
     Where a is high, 1/(1 - a) would amplify noise, so the low frequencies come from B and only the
     detail of the inversion is kept. The result is feathered back into the original at the edge.
Only pixels inside the window change; the originals are copied byte-identical to
<final>/_original_with_watermark and never overwritten.
Layout (after tidy_final.py): inputs are read from final/_original_with_watermark (fallback: final/_intermediates,
then final/); the cleaned image <T>__candidate_v01__clean.png is written to final/_intermediates.
Existing output files are never replaced unless --overwrite is given (checked before any work starts).
Usage: python remove_sparkle.py [final_dir] [--originals NAME] [--intermediates NAME] [--overwrite]
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

FINAL = Path("D:/aai work/flow_outputs/anime_kaliya/adhyay_01/final")
BOX = 300              # processed window (bottom-right); stamps sit 88 to 245 px in from the edges
CROP = 480             # work area around the corner, gives the median background context
BG_K = 201             # median window for the detector's background, wider than the big star
HALF = (24, 48)        # sparkle half-widths: small (51 px) and big (99 px) template
MARGIN = 3             # the shape keeps 3 px of partial-alpha edge around each astroid
SHIFT = 3              # integer alignment search per stamp (px)
THR = 0.7              # normalised-correlation score that counts as a stamp
ANCHOR_THR = 0.5       # lower bar at the small-star anchor (Flow puts one on every export)
THR_FOR = {"LEAP-02B": 0.55}   # overlapping ghost copy scores 0.60
C_WHITE = 255.0        # colour of the sparkle
AMIN = 0.04            # floor on 1 - a, keeps J finite
RING = 3               # px either side of a stamp edge where the measured alpha is used
DETAIL_SIGMA = 5.0     # blur that separates background from stroke detail where a is high
HIGH_A = (0.7, 0.8)    # alpha range over which the recovered J hands over to background + detail
FEATHER = 0.03         # alpha at which the blend back to the original reaches 100 %
ORIGINALS = "_original_with_watermark"  # sub-folder of final/: watermarked originals, byte-identical backups
INTERMEDIATES = "_intermediates"        # sub-folder of final/: __clean.png and __lama.png


def star_template(a):
    """Filled 4-point astroid, half-width a px, on a (2a+3) square canvas."""
    n = 2 * a + 3
    c = n / 2
    t = np.linspace(0, 2 * np.pi, 720)
    pts = np.stack([c + a * np.cos(t) ** 3, c + a * np.sin(t) ** 3], 1).round().astype(np.int32)
    m = np.zeros((n, n), np.uint8)
    cv2.fillPoly(m, [pts], 1)
    return m


TEMPLATES = {24: star_template(24), 48: star_template(48)}
SMALL = (BOX - 113, BOX - 114)  # small-star centre inside the window (x, y)


def find_stars(rgb, thr):
    """Returns [(score, half_width, y, x)] with (y, x) = template top-left inside the window."""
    h, w = rgb.shape[:2]
    y0, x0 = h - CROP, w - CROP
    gray = np.ascontiguousarray(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)[y0:, x0:])
    bg = cv2.medianBlur(gray, BG_K).astype(np.float32)
    diff = np.clip(gray.astype(np.float32) - bg, 0, 80)
    box = np.ascontiguousarray(diff[CROP - BOX:, CROP - BOX:])
    cands = []
    for a, t in TEMPLATES.items():
        n = t.shape[0]
        r = cv2.matchTemplate(box, t.astype(np.float32), cv2.TM_CCOEFF_NORMED)
        peak = cv2.dilate(r, np.ones((25, 25), np.uint8))
        for y, x in zip(*np.where((r == peak) & (r > ANCHOR_THR))):
            cx, cy = x + n / 2, y + n / 2
            near_small = abs(cx - SMALL[0]) <= 10 and abs(cy - SMALL[1]) <= 10
            if r[y, x] >= (ANCHOR_THR if near_small else thr):
                cands.append((float(r[y, x]), a, int(y), int(x), float(cx), float(cy)))
    cands.sort(reverse=True)
    kept = []
    for c in cands:                                   # one star per place: the strongest match wins
        if all(max(abs(c[4] - k[4]), abs(c[5] - k[5])) > 15 for k in kept):
            kept.append(c)
    return [(s, a, y, x) for s, a, y, x, _, _ in kept]


def size_of(hh):
    return 2 * hh + 3 + 2 * MARGIN


def patch(arr, hh, oy, ox):
    """The square of arr that the shape covers for a stamp whose template starts at (oy, ox)."""
    m = size_of(hh)
    return arr[oy - MARGIN:oy - MARGIN + m, ox - MARGIN:ox - MARGIN + m]


def normalise(med):
    """Scale the shape so its plateau reads 1."""
    return np.clip(med / np.percentile(med[med > 0.5 * med.max()], 95), 0, 1)


def fit_shapes(proxies, placements, iters=3):
    """Shared shape T per size class from the group, plus each stamp's aligned position and strength.

    proxies: per image alpha proxy (window). placements: per image [(hh, oy, ox)]. Returns T, placements, s.
    """
    items = [[i, j, hh, oy, ox] for i, pl in enumerate(placements) for j, (hh, oy, ox) in enumerate(pl)]
    classes = sorted({it[2] for it in items})          # only the size classes this group contains
    T = {hh: normalise(np.median(np.stack([patch(proxies[i], hh, oy, ox) for i, j, h2, oy, ox in items if h2 == hh]), axis=0))
         for hh in classes}
    s = {}
    for _ in range(iters):
        for it in items:
            i, j, hh, oy, ox = it
            best = None
            for dy in range(-SHIFT, SHIFT + 1):
                for dx in range(-SHIFT, SHIFT + 1):
                    p = patch(proxies[i], hh, oy + dy, ox + dx)
                    sc = float(np.sum(p * T[hh]) / max(np.sum(T[hh] ** 2), 1e-9))
                    err = float(np.sum((p - sc * T[hh]) ** 2))
                    if best is None or err < best[0]:
                        best = (err, dy, dx, sc)
            _, dy, dx, sc = best
            it[3] += dy
            it[4] += dx
            s[(i, j)] = sc
        for hh in classes:
            pats = [patch(proxies[i], hh, oy, ox) / s[(i, j)] for i, j, h2, oy, ox in items if h2 == hh and s[(i, j)] > 0.05]
            T[hh] = normalise(np.median(np.stack(pats), axis=0))
    placements = [[] for _ in placements]
    flat = []
    for i, j, hh, oy, ox in items:
        placements[i].append((hh, oy, ox))
        flat.append(s[(i, j)])
    return T, placements, np.array(flat)


def harmonic_background(lum, mask):
    """Laplace interpolation of lum over mask, with the pixels around mask as the fixed boundary."""
    H, W = lum.shape
    idx = -np.ones((H, W), int)
    ys, xs = np.where(mask)
    idx[ys, xs] = np.arange(len(ys))
    rows, cols, vals = [], [], []
    b = np.zeros(len(ys))
    for k, (y, x) in enumerate(zip(ys, xs)):
        rows.append(k)
        cols.append(k)
        vals.append(4.0)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = min(max(y + dy, 0), H - 1), min(max(x + dx, 0), W - 1)
            if idx[yy, xx] >= 0:
                rows.append(k)
                cols.append(idx[yy, xx])
                vals.append(-1.0)
            else:
                b[k] += lum[yy, xx]
    A = sp.csc_matrix((vals, (rows, cols)), shape=(len(ys), len(ys)))
    out = lum.copy()
    out[ys, xs] = spl.spsolve(A, b)
    return out


def stamp_mask(shape, pl):
    """Binary mask of the stamp astroids (no margin) in window coordinates."""
    m = np.zeros(shape, np.uint8)
    for hh, oy, ox in pl:
        n = 2 * hh + 3
        m[oy:oy + n, ox:ox + n] |= TEMPLATES[hh]
    return m


def background_and_proxy(win, pl, C=C_WHITE):
    """Per-channel harmonic background under the stamps, and the alpha proxy (I - B) / (C - B)."""
    mask = cv2.dilate(stamp_mask(win.shape[:2], pl), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) > 0
    B = np.stack([harmonic_background(win[..., c], mask) for c in range(3)], -1)
    lum, bl = win.mean(axis=2), B.mean(axis=2)
    return B, np.clip((lum - bl) / np.maximum(C - bl, 1.0), 0, 1)


def padded_shape(hh, oy, ox, shape, T):
    """The shape T of one stamp on a window-sized canvas (zero elsewhere)."""
    own = np.zeros(shape)
    m = size_of(hh)
    own[oy - MARGIN:oy - MARGIN + m, ox - MARGIN:ox - MARGIN + m] = T[hh]
    return own


def stamp_alpha(pl, s, T, shape):
    """Alpha of the window from all stamps, combined as 1 - prod(1 - s T) so overlaps screen."""
    A = np.ones(shape)
    for k, (hh, oy, ox) in enumerate(pl):
        A *= 1 - s[k] * padded_shape(hh, oy, ox, shape, T)
    return 1 - A


def core_strengths(proxies, placements, T):
    """Strength per stamp from its plateau, where no other stamp overlaps."""
    s = []
    for proxy, pl in zip(proxies, placements):
        shape = proxy.shape
        owns = [padded_shape(hh, oy, ox, shape, T) for hh, oy, ox in pl]
        for j in range(len(pl)):
            other = np.zeros(shape)
            for k in range(len(pl)):
                if k != j:
                    other = np.maximum(other, owns[k])
            core = (owns[j] > 0.9) & (other < 0.02)
            if core.sum() < 50:
                core = owns[j] > 0.9
            s.append(float(np.sum(proxy[core] * owns[j][core]) / np.sum(owns[j][core] ** 2)))
    return np.array(s)


def ring_match(win, pl, s, T, k, B, iters=40):
    """Strength of stamp k that makes its plateau brightness equal the ring just outside it."""
    shape = win.shape[:2]
    own = padded_shape(pl[k][0], pl[k][1], pl[k][2], shape, T)
    other = np.zeros(shape)
    base = np.ones(shape)
    for j, (hh, oy, ox) in enumerate(pl):
        if j != k:
            layer = padded_shape(hh, oy, ox, shape, T)
            other = np.maximum(other, layer)
            base *= 1 - s[j] * layer
    core = (own > 0.9) & (other < 0.02)
    hh, oy, ox = pl[k]
    box = np.zeros(shape, np.uint8)
    m = size_of(hh)
    box[oy - MARGIN:oy - MARGIN + m, ox - MARGIN:ox - MARGIN + m] = 1
    ring = (cv2.dilate(box, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
            - cv2.dilate(box, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))) > 0
    ring &= other < 0.02
    if core.sum() < 50 or ring.sum() < 50:
        return s[k]
    target = B.mean(axis=2)[core].mean()          # harmonic background over the core: no gradient bias

    def core_mean(sk):
        Ac = np.maximum(base * (1 - sk * own), AMIN)
        J = np.clip(C_WHITE + (win - C_WHITE) / Ac[..., None], 0, 255)
        return J.mean(axis=2)[core].mean()

    lo, hi = 0.01, 0.95
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if core_mean(mid) > target:      # recovered core too bright: remove more
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def recover(win, pl, s, T, proxy, B):
    """Clean window and the alpha it was computed from."""
    shape = win.shape[:2]
    a = stamp_alpha(pl, s, T, shape)
    mask = stamp_mask(shape, pl)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * RING + 1, 2 * RING + 1))
    band = (cv2.dilate(mask, k) > 0) & (cv2.erode(mask, k) == 0)
    a = np.where(band, np.clip(proxy, 0, 1), a)
    J = C_WHITE + (win - C_WHITE) / np.maximum(1 - a, AMIN)[..., None]
    Jlow = np.stack([cv2.GaussianBlur(J[..., c], (0, 0), DETAIL_SIGMA) for c in range(3)], -1)
    keep = np.clip((HIGH_A[1] - a) / (HIGH_A[1] - HIGH_A[0]), 0, 1)[..., None]
    fill = B + (J - Jlow) * keep
    u = np.clip((a - HIGH_A[0]) / (HIGH_A[1] - HIGH_A[0]), 0, 1)[..., None]
    J = J * (1 - u) + fill * u
    w = np.clip(a / FEATHER, 0, 1)[..., None]
    out = win * (1 - w) + np.clip(J, 0, 255) * w
    return np.clip(np.round(out), 0, 255).astype(np.uint8), a


def read_rgb(path):
    bgr = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    assert bgr is not None and bgr.ndim == 3 and bgr.shape[2] == 3, f"cannot read RGB: {path}"
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keep_original(src, dst):
    if dst.exists():
        assert sha(dst) == sha(src), f"{dst} exists and differs from the original"
        return
    shutil.copy2(src, dst)
    assert sha(dst) == sha(src), f"copy of {src} is not byte-identical"


def find_input(final, name, originals=ORIGINALS, intermediates=INTERMEDIATES):
    """The first existing copy of `name`: final/<originals>/, then final/<intermediates>/, then final/ (old layout)."""
    for d in (final / originals, final / intermediates, final):
        if (d / name).is_file():
            return d / name
    raise FileNotFoundError(f"{name} not found in {originals}/, {intermediates}/ or final/")


def input_titles(final, originals=ORIGINALS, intermediates=INTERMEDIATES):
    """{title: path of its watermarked <T>__candidate_v01.png}, sorted by title; the first location in find_input order wins."""
    out = {}
    for d in (final / originals, final / intermediates, final):
        if d.is_dir():
            for p in sorted(d.glob("*__candidate_v01.png")):
                out.setdefault(p.name[: -len("__candidate_v01.png")], p)
    return dict(sorted(out.items()))


def check_free(paths, overwrite=False):
    """Refuse, before any work, if an output already exists. Nothing is overwritten silently; --overwrite allows it."""
    taken = [str(p) for p in paths if Path(p).exists()]
    if taken and not overwrite:
        raise FileExistsError("exists, not overwritten (use --overwrite): " + ", ".join(taken))


def process_group(items):
    """items: [(title, rgb, stamps)] of one size. Returns {title: (clean_rgb, alpha, [(half, y, x, strength)])}."""
    windows, placements, proxies, backs = [], [], [], []
    for title, rgb, stamps in items:
        h, w = rgb.shape[:2]
        win = rgb[h - BOX:, w - BOX:].astype(np.float64)
        pl = [(hh, y, x) for _, hh, y, x in stamps]
        B, proxy = background_and_proxy(win, pl)
        windows.append(win)
        placements.append(pl)
        proxies.append(proxy)
        backs.append(B)
    T, placements, _ = fit_shapes(proxies, placements)
    per_image = np.split(core_strengths(proxies, placements, T), np.cumsum([len(pl) for pl in placements])[:-1])
    for _ in range(2):                                   # two passes: overlapping stamps see each other
        for i, (win, pl) in enumerate(zip(windows, placements)):
            sv = per_image[i].copy()
            for k in range(len(pl)):
                sv[k] = ring_match(win, pl, sv, T, k, backs[i])
            per_image[i] = sv
    out = {}
    for i, ((title, rgb, _), win, pl) in enumerate(zip(items, windows, placements)):
        clean_win, a = recover(win, pl, per_image[i], T, proxies[i], backs[i])
        h, w = rgb.shape[:2]
        clean = rgb.copy()
        clean[h - BOX:, w - BOX:] = clean_win
        out[title] = (clean, a, [(hh, oy, ox, round(float(s), 3)) for (hh, oy, ox), s in zip(pl, per_image[i])])
    return out


def run(final, originals=ORIGINALS, intermediates=INTERMEDIATES, overwrite=False):
    backup, inter, report_dir = final / originals, final / intermediates, final / "_sparkle_check2"
    inputs = input_titles(final, originals, intermediates)
    check_free([inter / f"{t}__candidate_v01__clean.png" for t in inputs], overwrite)     # refuse before any work
    backup.mkdir(exist_ok=True)
    inter.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)
    groups = {}
    for title, src in inputs.items():
        for name in (src.name, f"{title}__candidate_v01__2K_source.jpg"):
            keep_original(find_input(final, name, originals, intermediates), backup / name)   # no-op when already in backup
        rgb = read_rgb(src)
        stamps = find_stars(rgb, THR_FOR.get(title, THR))
        if not stamps:
            print(f"{title}: NO STAR FOUND, left unchanged")
            continue
        groups.setdefault(rgb.shape[:2], []).append((title, rgb, stamps))
    report = []
    for items in groups.values():
        result = process_group(items)
        for title, rgb, _ in items:
            clean, a, placed = result[title]
            dst = inter / f"{title}__candidate_v01__clean.png"
            assert cv2.imwrite(str(dst), cv2.cvtColor(clean, cv2.COLOR_RGB2BGR)), f"write failed: {dst}"
            back = read_rgb(dst)
            h, w = rgb.shape[:2]
            mask = np.zeros((h, w), bool)
            mask[h - BOX:, w - BOX:] = a > 0.001
            assert back.shape == rgb.shape and np.array_equal(back[~mask], rgb[~mask]), f"verify failed: {dst}"
            report.append({"title": title, "mask_px": int(mask.sum()),
                           "stamps": [{"half": hh, "y": oy, "x": ox, "strength": s} for hh, oy, ox, s in placed]})
            print(f"{title}: {[(hh, oy, ox, s) for hh, oy, ox, s in placed]}, mask {int(mask.sum())} px")
    (report_dir / "report.json").write_text(json.dumps(report, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("final", nargs="?", type=Path, default=FINAL, help="the chapter's final/ folder (default: the Kaliya adhyay_01 final/)")
    ap.add_argument("--originals", default=ORIGINALS, help="sub-folder of final/ with the watermarked originals (default %(default)s)")
    ap.add_argument("--intermediates", default=INTERMEDIATES, help="sub-folder of final/ for __clean.png (default %(default)s)")
    ap.add_argument("--overwrite", action="store_true", help="replace __clean.png files that already exist (default: refuse)")
    a = ap.parse_args(argv)
    run(a.final, a.originals, a.intermediates, a.overwrite)


if __name__ == "__main__":
    main()
