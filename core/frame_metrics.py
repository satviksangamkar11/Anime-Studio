"""Per-frame metrics (WP6): ffmpeg signalstats parsing, frame extraction and Pillow grid / region stats.
Colour maths comes from core.style_pack (never re-implemented here). Standard library + Pillow only."""
import math
import re
import subprocess
from pathlib import Path

from PIL import Image

from core.style_pack import l_star, srgb_to_lab

_FRAME_RE = re.compile(r"^frame:(\d+)\s+pts:\S+\s+pts_time:(\S+)")
_STAT_RE = re.compile(r"^lavfi\.signalstats\.(YAVG|SATAVG|HUEMED)=(\S+)$")
_SAMPLE_SIDE = 64  # coarse subsample used by region and Lab stats


def _tail(text, n=800):
    text = (text or "").strip()
    return text[-n:] if len(text) > n else text


def per_frame_stats(clip):
    """[{frame, pts_time, YAVG, SATAVG, HUEMED}] for every frame, from ffmpeg signalstats."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(clip), "-vf", "signalstats,metadata=print:file=-",
           "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RuntimeError(f"ffmpeg could not run: {exc}") from exc
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on {Path(clip).name}: {_tail(r.stderr)}")
    stats, cur = [], None
    for line in r.stdout.splitlines():
        line = line.strip()
        m = _FRAME_RE.match(line)
        if m:
            if cur is not None and "YAVG" in cur:
                stats.append(cur)
            try:
                pts = float(m.group(2))
            except ValueError:
                pts = float("nan")
            cur = {"frame": int(m.group(1)), "pts_time": pts}
            continue
        m = _STAT_RE.match(line)
        if m and cur is not None:
            cur[m.group(1)] = float(m.group(2))
    if cur is not None and "YAVG" in cur:
        stats.append(cur)
    return stats


def extract_frames(clip, out_dir, scale=0.5, every=1, start=0, count=None):
    """PNG frames at `scale` of the original size, every Nth frame from `start`.
    Returns [(frame_index, Path)] in frame order."""
    if every < 1 or start < 0 or (count is not None and count < 1) or scale <= 0:
        raise ValueError("extract_frames: every>=1, start>=0, count>=1 or None, scale>0")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    before = set(out.glob("frame_*.png"))
    select = f"select='gte(n\\,{start})*not(mod(n-{start}\\,{every}))',scale=iw*{scale}:ih*{scale}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vf", select, "-fps_mode", "passthrough"]
    if count is not None:
        cmd += ["-frames:v", str(count)]
    cmd += ["-start_number", "0", str(out / "frame_%06d.png")]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed on {Path(clip).name}: {_tail(r.stderr)}")
    new = sorted(set(out.glob("frame_*.png")) - before)
    return [(start + k * every, p) for k, p in enumerate(new)]


# ---- Pillow helpers ----
def _rgb(img):
    return img.convert("RGB")


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


_LIN = [_lin(v) for v in range(256)]


def _luma(rgb):
    r, g, b = rgb
    return 0.2126 * _LIN[r] + 0.7152 * _LIN[g] + 0.0722 * _LIN[b]


def _share_red(rgb):
    r, g, b = rgb
    s = r + g + b
    return r / s if s else 0.0


def _cell_means(img, n, fn):
    """n*n row-major cell means of fn(pixel). Every cell gets at least one pixel, so tiny frames work."""
    img = _rgb(img)
    w, h = img.size
    px = img.load()
    vals = [[fn(px[x, y]) for x in range(w)] for y in range(h)]
    out = []
    for r in range(n):
        y0 = r * h // n
        y1 = min(h, max(y0 + 1, -((-(r + 1) * h) // n)))
        for c in range(n):
            x0 = c * w // n
            x1 = min(w, max(x0 + 1, -((-(c + 1) * w) // n)))
            total = 0.0
            count = 0
            for y in range(y0, y1):
                row = vals[y]
                for x in range(x0, x1):
                    total += row[x]
                    count += 1
            out.append(total / count if count else 0.0)
    return out


def grid_luma(img, n=8):
    """n*n cell means of relative luminance Y (WCAG: linear sRGB, 0.2126R+0.7152G+0.0722B)."""
    return _cell_means(img, n, _luma)


def grid_red_share(img, n=8):
    """n*n cell means of R/(R+G+B); 0 where the pixel sum is 0."""
    return _cell_means(img, n, _share_red)


def white_share(img, thr=250):
    """Share of pixels with R, G and B all >= thr."""
    img = _rgb(img)
    w, h = img.size
    px = img.load()
    total = w * h
    if not total:
        return 0.0
    return sum(1 for y in range(h) for x in range(w)
               if min(px[x, y]) >= thr) / total


def _box_px(size, box_frac):
    try:
        x0f, y0f, x1f, y1f = (float(v) for v in box_frac)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"box must be four fractions: {box_frac!r}") from exc
    if not (0 <= x0f < x1f <= 1 and 0 <= y0f < y1f <= 1):
        raise ValueError(f"box must satisfy 0<=x0<x1<=1 and 0<=y0<y1<=1: {box_frac!r}")
    w, h = size
    x0 = min(math.floor(x0f * w), w - 1)
    y0 = min(math.floor(y0f * h), h - 1)
    x1 = min(w, max(x0 + 1, math.ceil(x1f * w)))
    y1 = min(h, max(y0 + 1, math.ceil(y1f * h)))
    return x0, y0, x1, y1


def _samples(img, box=None):
    """Coarse subsample (at most 64x64 steps) of the image, or of the pixel box (x0, y0, x1, y1)."""
    img = _rgb(img)
    w, h = img.size
    px = img.load()
    if box is None:
        box = (0, 0, w, h)
    x0, y0, x1, y1 = box
    sx = max(1, -((-(x1 - x0)) // _SAMPLE_SIDE))
    sy = max(1, -((-(y1 - y0)) // _SAMPLE_SIDE))
    return [px[x, y] for y in range(y0, y1, sy) for x in range(x0, x1, sx)]


def region_lstar(img, box_frac):
    """Mean L* inside box_frac = [x0, y0, x1, y1] (fractions 0..1)."""
    px = _samples(img, _box_px(_rgb(img).size, box_frac))
    return sum(l_star(p) for p in px) / len(px)


def outside_region_lstar(img, box_frac):
    """Mean L* of the sampled pixels outside box_frac; None when nothing lies outside the box."""
    img = _rgb(img)
    x0, y0, x1, y1 = _box_px(img.size, box_frac)
    w, h = img.size
    px = img.load()
    sx = max(1, -((-w) // _SAMPLE_SIDE))
    sy = max(1, -((-h) // _SAMPLE_SIDE))
    vals = [l_star(px[x, y]) for y in range(0, h, sy) for x in range(0, w, sx)
            if not (x0 <= x < x1 and y0 <= y < y1)]
    return sum(vals) / len(vals) if vals else None


def mean_lab(img):
    """Mean (L, a, b) of the sampled pixels (D65 CIELAB)."""
    labs = [srgb_to_lab(p) for p in _samples(img)]
    n = len(labs)
    return tuple(sum(lab[i] for lab in labs) / n for i in range(3))
