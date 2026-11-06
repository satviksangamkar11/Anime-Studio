"""Writes a measured plate into a style pack's environments list (G1, A24).
usage: python tools/measure_plate.py PNG ENV_ID --pack PACK_ID [--region name:x0,y0,x1,y1 ...] [--sibling PLATE_ID] [--styles-dir DIR]
Sets environments[ENV_ID].measured = {L, a, b, luma}; each --region sets regions[].box and regions[].measured {L, a, b}.
With --sibling PLATE_ID the plate's Lab goes to sibling_measured[PLATE_ID] and the id joins accepted_siblings (no duplicates);
an environment that already has measured values keeps them. Exit 2 when the PNG or the pack is missing.
Run only on owner-approved plates, and never commit images. Prints one summary line."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flow" / "scripts"))
from palette_check import measure  # noqa: E402
from core.style_pack import load_pack  # noqa: E402


def refuse(reason):
    print(f"REFUSED: {reason}", file=sys.stderr)
    return 2


def parse_region(text):
    name, sep, coords = text.partition(":")
    parts = coords.split(",")
    if not sep or not name.strip() or len(parts) != 4:
        raise ValueError(f"--region must be name:x0,y0,x1,y1, got {text!r}")
    try:
        box = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"--region coordinates must be numbers, got {text!r}")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError(f"--region box must be fractions 0..1 with x0<x1 and y0<y1, got {text!r}")
    return name.strip(), box


def _lab(m):
    return {"L": m["L"], "a": m["a"], "b": m["b"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measure an owner-approved plate into a style pack environment.")
    ap.add_argument("png")
    ap.add_argument("env_id")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--region", action="append", default=[])
    ap.add_argument("--sibling", default=None)
    ap.add_argument("--styles-dir", default=None)
    a = ap.parse_args(argv)

    png = Path(a.png)
    if not png.is_file():
        return refuse(f"PNG not found: {png.name}")
    styles = Path(a.styles_dir) if a.styles_dir else ROOT / "styles"
    if not (styles / f"{a.pack}.json").is_file():
        return refuse(f"style pack not found: {a.pack}.json in {styles}")
    try:
        pack = load_pack(a.pack, styles)
        regions = [parse_region(r) for r in a.region]
    except ValueError as exc:
        return refuse(str(exc))
    try:
        m = measure(png, regions=[{"name": n, "box": b} for n, b in regions])
    except Exception as exc:
        return refuse(f"cannot read PNG {png.name}: {type(exc).__name__}: {exc}")

    envs = pack.get("environments")
    if envs is None:
        envs = pack["environments"] = []
    if not isinstance(envs, list):
        return refuse("environments must be a list in the style pack")
    env = next((e for e in envs if isinstance(e, dict) and e.get("id") == a.env_id), None)
    if env is None:
        env = {"id": a.env_id}
        envs.append(env)
    env.setdefault("accepted_siblings", [])
    set_base = not (a.sibling and "measured" in env)
    if set_base:
        env["measured"] = dict(_lab(m), luma=m["luma"])
        if regions:
            regs = env.get("regions")
            if not isinstance(regs, list):
                regs = env["regions"] = []
            for name, box in regions:
                reg = next((r for r in regs if isinstance(r, dict) and r.get("name") == name), None)
                if reg is None:
                    reg = {"name": name}
                    regs.append(reg)
                reg["box"] = box
                reg["measured"] = _lab(m["regions"][name])
    if a.sibling:
        sib = env.get("sibling_measured")
        if not isinstance(sib, dict):
            sib = env["sibling_measured"] = {}
        sib[a.sibling] = _lab(m)
        acc = env["accepted_siblings"]
        if not isinstance(acc, list):
            return refuse("accepted_siblings must be a list in the style pack")
        if a.sibling not in acc:
            acc.append(a.sibling)

    with open(styles / f"{a.pack}.json", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(pack, indent=2, ensure_ascii=False) + "\n")
    mode = f"sibling {a.sibling}" if a.sibling else "base"
    print(f"measured {a.env_id} in {a.pack} ({mode}): L={m['L']:.2f} a={m['a']:.2f} b={m['b']:.2f} "
          f"luma={m['luma']:.3f} regions={len(regions)} base_updated={set_base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
