"""G1 image palette gate (WP5): compares a keyframe's mean Lab with the environment's measured Lab (A24).
Usage: python palette_check.py IMAGE PACK_ID ENV_ID [--aspect 9:16|16:9] [--styles-dir DIR]   (exit 1 on FAIL)
Pillow + the style-pack colour maths in core/style_pack.py. Junk input gives a FAIL entry, never a traceback."""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.style_pack import delta_e_2000, load_core, load_pack, srgb_to_lab  # noqa: E402

ASPECTS = {"9:16": "portrait", "16:9": "landscape"}
SAMPLE_LONG_SIDE = 256   # downscale before sampling
GRID = 64                # coarse sample grid: at most 64x64 pixels


def _entry(level, message):
    return {"rule": "G1", "level": level, "shot": None, "episode": None, "message": message}


def _load(img):
    if isinstance(img, Image.Image):
        return img
    with Image.open(img) as im:
        return im.copy()


def _mean_lab(im):
    """Mean CIELAB of the pixels in an image: averages the Lab of at most GRID x GRID samples."""
    im.thumbnail((SAMPLE_LONG_SIDE, SAMPLE_LONG_SIDE), Image.Resampling.BOX)
    im.thumbnail((GRID, GRID), Image.Resampling.BOX)
    w, h = im.size
    px = im.load()
    sums = [0.0, 0.0, 0.0]
    luma = 0.0
    n = 0
    for y in range(h):
        for x in range(w):
            L, a, b = srgb_to_lab(px[x, y])
            sums[0] += L
            sums[1] += a
            sums[2] += b
            # relative luminance Y from L* (inverse of the CIE lightness formula)
            luma += ((L + 16) / 116) ** 3 if L > 8 else L / 903.3
            n += 1
    return {"L": sums[0] / n, "a": sums[1] / n, "b": sums[2] / n, "luma": luma / n}


def measure(img, regions=None):
    """Whole-frame and per-region mean Lab (+ luma 0..1). img: PIL image or path. regions: [{"name", "box": [x0,y0,x1,y1] fractions}]."""
    base = _load(img).convert("RGB")
    w, h = base.size
    whole = _mean_lab(base.copy())
    out = {k: round(whole[k], 4) for k in ("L", "a", "b", "luma")}
    out["regions"] = {}
    for reg in regions or []:
        x0, y0, x1, y1 = (float(v) for v in reg["box"])
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError(f"region {reg.get('name')!r} box must be fractions with x0<x1 and y0<y1")
        box = (round(x0 * w), round(y0 * h), max(round(x1 * w), round(x0 * w) + 1), max(round(y1 * h), round(y0 * h) + 1))
        lab = _mean_lab(base.crop(box))
        out["regions"][reg["name"]] = {k: round(lab[k], 4) for k in ("L", "a", "b")}
    return out


def _lab(d):
    if not isinstance(d, dict):
        raise ValueError("measured Lab must be an object")
    vals = []
    for k in ("L", "a", "b"):
        v = d.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v != v or abs(v) == float("inf"):
            raise ValueError(f"measured Lab {k} is not a finite number: {v!r}")
        vals.append(float(v))
    return tuple(vals)


def _check(img, env, core, aspect):
    if env is None:
        return [_entry("WARN", "G1 skipped: no measured Lab for this environment")]
    if not isinstance(env, dict):
        return [_entry("FAIL", f"G1: environment must be an object, got {type(env).__name__}")]
    env_id = env.get("id", "?")
    im = _load(img)
    out = []
    if aspect is not None:
        if aspect not in ASPECTS:
            return [_entry("FAIL", f"G1: aspect must be 9:16 or 16:9, got {aspect!r}")]
        w, h = im.size
        ok = h > w if aspect == "9:16" else w > h
        if not ok:
            out.append(_entry("FAIL", f"G1 FAIL: wrong orientation: aspect {aspect} needs {ASPECTS[aspect]}, got {w}x{h}"))
    measured = env.get("measured")
    if not measured:
        out.append(_entry("WARN", f"G1 skipped: no measured Lab for this environment ({env_id})"))
        return out
    limit = core["gates"]["g1_de2000_max"]
    target = _lab(measured)
    regions = env.get("regions") or []
    if not isinstance(regions, list):
        return out + [_entry("FAIL", f"G1: regions must be a list in environment {env_id}")]
    got = measure(im, regions=[r for r in regions if isinstance(r, dict) and "box" in r and "name" in r])
    d = delta_e_2000(_lab(got), target)
    if d > limit:
        out.append(_entry("FAIL", f"G1 FAIL: {env_id} whole frame dE2000 {d:.2f} > {limit} "
                                  f"(keyframe L={got['L']:.2f} a={got['a']:.2f} b={got['b']:.2f}, "
                                  f"measured L={target[0]:.2f} a={target[1]:.2f} b={target[2]:.2f})"))
    sib_measured = env.get("sibling_measured") or {}
    no_value = []
    for pid in env.get("accepted_siblings") or []:
        if pid not in sib_measured:
            no_value.append(str(pid))
            continue
        ds = delta_e_2000(_lab(got), _lab(sib_measured[pid]))
        if ds > limit:
            out.append(_entry("FAIL", f"G1 FAIL: {env_id} vs accepted sibling {pid} dE2000 {ds:.2f} > {limit}"))
    if no_value:
        out.append(_entry("WARN", f"G1 skipped for siblings without a measured Lab in {env_id}: {', '.join(no_value)}"))
    for r in regions:
        if not (isinstance(r, dict) and isinstance(r.get("measured"), dict) and r.get("name") in got["regions"]):
            continue
        dr = delta_e_2000(_lab(got["regions"][r["name"]]), _lab(r["measured"]))
        if dr > limit:
            out.append(_entry("FAIL", f"G1 FAIL: {env_id} region '{r['name']}' dE2000 {dr:.2f} > {limit}"))
    return out


def check_keyframe(img, env, core=None, aspect=None):
    """G1 entries for a keyframe (PIL image or path) against an environment record. Never raises."""
    try:
        return _check(img, env, core or load_core(), aspect)
    except Exception as exc:  # junk input must never raise a traceback
        return [_entry("FAIL", f"G1 could not check this image: {type(exc).__name__}: {exc}")]


def check_download(png_path, pack_id, env_id, aspect=None, styles_dir=None):
    """Loads the pack, finds the environment and runs check_keyframe. png_path may be a path or an open PIL image."""
    entries = []
    try:
        pack = load_pack(pack_id, styles_dir)
    except ValueError as exc:
        entries.append(_entry("WARN", f"G1 skipped: {exc}"))
    else:
        envs = pack.get("environments")
        envs = envs if isinstance(envs, list) else []
        env = next((e for e in envs if isinstance(e, dict) and e.get("id") == env_id), None)
        if env is None:
            entries.append(_entry("WARN", f"G1 skipped: environment {env_id} is not in pack {pack_id}"))
        else:
            entries = check_keyframe(png_path, env, aspect=aspect)
    return {"fail": any(e["level"] == "FAIL" for e in entries), "entries": entries}


def main(argv=None):
    ap = argparse.ArgumentParser(description="G1 palette gate for one keyframe.")
    ap.add_argument("image")
    ap.add_argument("pack_id")
    ap.add_argument("env_id")
    ap.add_argument("--aspect", default=None)
    ap.add_argument("--styles-dir", default=None)
    a = ap.parse_args(argv)
    res = check_download(a.image, a.pack_id, a.env_id, aspect=a.aspect, styles_dir=a.styles_dir)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 1 if res["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
