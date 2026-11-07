"""Lint a style pack for focal-vs-background L* gaps (WP2).

Usage: python tools/lint_pack.py <pack_id> [--styles-dir DIR]
Prints a JSON list of entries. Exit 0 when there is no FAIL (WARN only), 1 on FAIL.
Entries: {"rule", "level", "palette", "hero", "bg", "gap", "message"}.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.style_pack import l_star, load_pack, validate_pack  # noqa: E402

HERO_WORDS = ("hero", "body", "skin")
BG_WORDS = ("sky", "night", "void", "fog", "background")


def _fail(message, palette=None):
    return {"rule": "P0", "level": "FAIL", "palette": palette, "hero": None, "bg": None,
            "gap": None, "message": message}


def _pairs(colors, hint):
    heroes = [n for n, c in colors.items() if any(w in c["role"].lower() for w in HERO_WORDS)]
    bgs = [n for n, c in colors.items() if any(w in c["role"].lower() for w in BG_WORDS)]
    pairs = [(h, b) for h in heroes for b in bgs if h != b]
    if hint:
        pairs.append((hint.get("hero"), hint.get("bg")))
    out = []
    for pair in pairs:
        if pair not in out:
            out.append(pair)
    return out


def lint_pack(pack_id, styles_dir=None):
    try:
        pack = load_pack(pack_id, styles_dir)
    except ValueError as exc:
        return [_fail(str(exc))]
    errors = validate_pack(pack)
    if errors:
        return [_fail(e) for e in errors]
    min_dl = pack["frame_law"].get("min_dL_focal_vs_bg")
    if min_dl is None:
        return [{"rule": "LINT-DL-UNSET", "level": "WARN", "palette": None, "hero": None, "bg": None,
                 "gap": None, "message": "no min_dL_focal_vs_bg set"}]
    out = []
    for pname, pal in pack["palettes"].items():
        colors = pal["colors"]
        for hero, bg in _pairs(colors, pal.get("focal_hints")):
            if hero not in colors or bg not in colors:
                out.append(_fail(f"focal_hints names not in palette: {hero!r} / {bg!r}", pname))
                continue
            gap = abs(l_star(colors[hero]["hex"]) - l_star(colors[bg]["hex"]))
            if gap < min_dl:
                out.append({"rule": "LINT-DL", "level": "WARN", "palette": pname, "hero": hero,
                            "bg": bg, "gap": round(gap, 1),
                            "message": f"{hero} vs {bg}: dL* {gap:.1f} is below min_dL_focal_vs_bg {min_dl}"})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint focal-vs-background dL* gaps in a style pack")
    ap.add_argument("pack_id")
    ap.add_argument("--styles-dir", default=None)
    args = ap.parse_args(argv)
    entries = lint_pack(args.pack_id, args.styles_dir)
    print(json.dumps(entries, indent=2))
    return 1 if any(e["level"] == "FAIL" for e in entries) else 0


if __name__ == "__main__":
    sys.exit(main())
