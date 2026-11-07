"""Cube LUT maths and the per-shot match LUT (WP8). Standard library only, pure functions.

Grade order (grade_fn): exposure (linear gain 2**EV), contrast (around 0.5), saturation
(around Rec.709 luma), temp (R and B), shadow lift or crush (below 0.25, smooth falloff).

NOT applied in the LUT: highlight, bloom_pct, vignette_pct. Bloom and vignette are ffmpeg
filters in post.py, and the spec gives no LUT formula for highlight. They are ignored here.

Shot match (shot_match_fn): offsets the pixel's Lab by the clamped clip-to-reference offset,
weighted by 4*Y*(1-Y) so pure black and pure white stay pinned. srgb_to_lab only accepts
integer RGB, so the pixel is quantised to 0..255 for the forward conversion.
"""
import math
from pathlib import Path

from core.style_pack import _WHITE as _D65, srgb_to_lab

_XYZ_TO_LINEAR = (
    (3.2404542, -1.5371385, -0.4985314),
    (-0.9692660, 1.8760108, 0.0415560),
    (0.0556434, -0.2040259, 1.0572252),
)
_LUMA = (0.2126, 0.7152, 0.0722)  # Rec.709 weights
_DELTA = 6.0 / 29.0


def _clip01(v):
    return float(min(1.0, max(0.0, float(v))))


def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055


def _lab_finv(t):
    return t ** 3 if t > _DELTA else 3 * _DELTA * _DELTA * (t - 4.0 / 29.0)


def lab_to_srgb(lab):
    """CIELAB (D65) to sRGB floats in 0..1, clipped. Inverse of style_pack.srgb_to_lab."""
    L, a, b = (float(v) for v in lab)
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    X = _D65[0] * _lab_finv(fx)
    Y = _D65[1] * _lab_finv(fy)
    Z = _D65[2] * _lab_finv(fz)
    lin = [m[0] * X + m[1] * Y + m[2] * Z for m in _XYZ_TO_LINEAR]
    return tuple(_clip01(_linear_to_srgb(c)) for c in lin)


def identity_fn(r, g, b):
    return (r, g, b)


def _num(grade, key):
    v = grade.get(key, 0)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def grade_fn(grade):
    """Callable(r, g, b) -> (r, g, b), floats 0..1. Missing keys are no-ops."""
    g_ = grade if isinstance(grade, dict) else {}
    ev = _num(g_, "exposure")
    contrast = _num(g_, "contrast")
    sat = _num(g_, "saturation")
    temp = _num(g_, "temp")
    shadow = _num(g_, "shadow_lift") + _num(g_, "shadow_crush")
    gain = 2.0 ** ev

    def fn(r, g, b):
        rgb = [_clip01(r), _clip01(g), _clip01(b)]
        if ev:
            rgb = [_clip01(_linear_to_srgb(_srgb_to_linear(x) * gain)) for x in rgb]
        if contrast:
            rgb = [_clip01(0.5 + (x - 0.5) * (1 + contrast / 100.0)) for x in rgb]
        if sat:
            y = sum(w * x for w, x in zip(_LUMA, rgb))
            rgb = [_clip01(y + (x - y) * (1 + sat / 100.0)) for x in rgb]
        if temp:
            rgb = [_clip01(rgb[0] * (1 + temp / 200.0)), rgb[1], _clip01(rgb[2] * (1 - temp / 200.0))]
        if shadow:
            out = []
            for x in rgb:
                if x < 0.25:
                    x = _clip01(x + (shadow / 400.0) * (1 - x / 0.25) ** 2)
                out.append(x)
            rgb = out
        return tuple(rgb)

    return fn


def write_cube(path, fn, size=33, title=""):
    """Write a 3D .cube (red fastest, LF, UTF-8, 6 decimals). Same input gives the same bytes."""
    if size < 2:
        raise ValueError("LUT size must be at least 2")
    step = size - 1
    lines = []
    if title:
        lines.append(f'TITLE "{title}"')
    lines += [f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                out = fn(r / step, g / step, b / step)
                lines.append(" ".join(f"{_clip01(v):.6f}" for v in out))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(str(target), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def parse_cube(path):
    """Read a 3D .cube. Raises ValueError on a malformed file."""
    with open(str(path), encoding="utf-8") as fh:
        text = fh.read()
    title = ""
    size = None
    table = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line[0].isalpha():
            key, _, rest = line.partition(" ")
            key = key.upper()
            if key == "TITLE":
                t = rest.strip()
                title = t[1:-1] if len(t) >= 2 and t[0] == '"' and t[-1] == '"' else t
            elif key == "LUT_3D_SIZE":
                size = int(rest.split()[0])
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"bad cube row: {line!r}")
        table.append(tuple(float(x) for x in parts))
    if size is None:
        raise ValueError("cube has no LUT_3D_SIZE")
    if len(table) != size ** 3:
        raise ValueError(f"cube has {len(table)} rows, expected {size ** 3}")
    return {"title": title, "size": size, "table": table}


def apply_cube(table, size, rgb):
    """Trilinear lookup in a parsed 3D table (red fastest)."""
    if size < 2:
        raise ValueError("LUT size must be at least 2")
    cells = []
    for x in rgb:
        p = _clip01(x) * (size - 1)
        i0 = min(int(p), size - 2)
        cells.append((i0, p - i0))
    (ir, fr), (ig, fg), (ib, fb) = cells
    out = [0.0, 0.0, 0.0]
    for db in (0, 1):
        for dg in (0, 1):
            for dr in (0, 1):
                w = ((fr if dr else 1 - fr) * (fg if dg else 1 - fg) * (fb if db else 1 - fb))
                v = table[(ir + dr) + size * (ig + dg) + size * size * (ib + db)]
                for c in range(3):
                    out[c] += w * v[c]
    return tuple(out)


def shot_match_offset(clip_mean_lab, reference_lab, clamp_de):
    """Lab vector from the clip mean to the reference, length limited to clamp_de. Zero if no reference."""
    if reference_lab is None:
        return (0.0, 0.0, 0.0)
    d = [float(r) - float(c) for c, r in zip(clip_mean_lab, reference_lab)]
    norm = math.sqrt(sum(x * x for x in d))
    if norm <= clamp_de or norm == 0:
        return tuple(d)
    k = clamp_de / norm
    return tuple(x * k for x in d)


def shot_match_fn(offset):
    """Callable(r, g, b) that adds offset * 4*Y*(1-Y) in Lab (black and white stay pinned)."""
    off = tuple(float(v) for v in offset)
    if all(v == 0 for v in off):
        return identity_fn

    def fn(r, g, b):
        r, g, b = _clip01(r), _clip01(g), _clip01(b)
        y = sum(w * _srgb_to_linear(x) for w, x in zip(_LUMA, (r, g, b)))
        w = 4.0 * y * (1.0 - y)
        if w <= 0:
            return (r, g, b)
        ints = tuple(int(round(x * 255)) for x in (r, g, b))
        L, a, bb = srgb_to_lab(ints)
        return lab_to_srgb((L + off[0] * w, a + off[1] * w, bb + off[2] * w))

    return fn


def combine(*fns):
    """One callable applying fns in the order given."""
    def fn(r, g, b):
        for f in fns:
            r, g, b = f(r, g, b)
        return (r, g, b)
    return fn


def write_shot_lut(path, act_fn, offset, size=33, title="shot match (generated)"):
    write_cube(path, combine(shot_match_fn(offset), act_fn), size=size, title=title)


def act_reference_lab(pack, act):
    """Lab of the act's phase key, or None when the act, phase or key is absent or null."""
    try:
        phase_id = pack["acts"][act]["phase"]
        phases = pack["colour_script"]["phases"]
    except (KeyError, TypeError):
        return None
    if not isinstance(phases, list):
        return None
    for ph in phases:
        if isinstance(ph, dict) and ph.get("id") == phase_id:
            key = ph.get("key")
            if not isinstance(key, str):
                return None
            try:
                return srgb_to_lab(key)
            except ValueError:
                return None
    return None
