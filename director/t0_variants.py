"""Expand ONE base shot into the four T0 variants (plan v4.3, phase 2): FL and REF, each at seeds 42 and 123.
  python t0_variants.py shot.json out.json style_project
The variants share start and end keyframes, render_frames, action, camera, sound, cast, set and props, and the Pika baseline
(any base sampler or LoRA override is dropped). FL variants have no refs or subjects (fl2va takes start and end only); REF variants
have exactly one identity ref and its subject lines (ref2va). Every variant is built through settings_for with the style bible
before anything is written. An existing output file is never overwritten, and out must differ from the input."""
import json
import sys
from pathlib import Path

import style_bible
from h3_director import settings_for

SEEDS = (42, 123)


def expand(base, bible):
    if not isinstance(base, dict):
        raise ValueError("t0_variants takes ONE base shot (a JSON object)")
    if not (base.get("start") and base.get("end")):
        raise ValueError("the T0 base shot needs both start and end keyframes (FL and REF share them)")
    refs = base.get("refs") or []
    if len(refs) != 1 or not base.get("subjects"):
        raise ValueError("the T0 base shot needs exactly one identity ref and its subject line(s) for the REF variants")
    shared = {k: v for k, v in base.items()
              if k not in ("id", "mode", "seed", "refs", "subjects", "sampler") and "lora" not in k.lower()}
    out = []
    for family in ("FL", "REF"):
        for seed in SEEDS:
            s = dict(shared, id=f"SHOT-T0-{family}-S{seed}", seed=seed, mode="fl2va" if family == "FL" else "ref2va")
            if family == "REF":
                s.update(refs=[refs[0]], subjects=list(base["subjects"]))
            out.append(s)
    for s in out:
        settings_for(s, bible, require_bible=True)   # every variant is built before anything is written
    return out


def main(shot_path, out_path, style):
    src, dst = Path(shot_path), Path(out_path)
    if src.resolve() == dst.resolve():
        raise ValueError("output and input must be different files")
    if dst.exists():
        raise ValueError(f"{dst} exists: refusing to overwrite it")
    base = json.loads(src.read_text(encoding="utf-8"))
    bible = style_bible.load(style)
    variants = expand(base, bible)
    dst.write_text(json.dumps(variants, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: python t0_variants.py shot.json out.json style_project")
    main(*sys.argv[1:4])
