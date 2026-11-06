"""Expand ONE base shot into T0 variants (plan v4.3, phase 2).
  python t0_variants.py shot.json out.json style_project          -> 4 variants: FL and REF, each at seeds 42 and 123 (Pika baseline)
  python t0_variants.py shot.json out.json style_project --arms   -> 8 clips: arms A-D at seeds 42 and 123 (DECISION, RETHINK addendum)
    A  Ref2VA, H3 pruned, official Pika 6-step          (route pika6)
    B  Ref2VA, Singularity v2 pruned, Pika Turbo 4-step (route sing4)
    C  Ref2VA, Singularity v2 pruned, Pika Turbo 8-step (route sing8)
    D  FL2VA, H3 FL2VA pruned, official Pika 6-step, start and end only (route pika6)
The variants share start and end keyframes, render_frames, action, camera, sound, cast, set and props. Any base id, mode, seed, refs,
subjects, sampler, route or LoRA override is dropped. REF and arms A-C have one or two identity refs and their subject lines (ref2va);
FL and D have no refs. Every variant is built through settings_for with the style bible before anything is written. An existing output
file is never overwritten, and out must differ from the input."""
import json
import sys
from pathlib import Path

import style_bible
from h3_director import settings_for

SEEDS = (42, 123)
ARMS = {"A": ("ref2va", "pika6"), "B": ("ref2va", "sing4"), "C": ("ref2va", "sing8"), "D": ("fl2va", "pika6")}   # arm: (mode, route)
DROP = ("id", "mode", "seed", "refs", "subjects", "sampler", "route")


def _check_base(base):
    if not isinstance(base, dict):
        raise ValueError("t0_variants takes ONE base shot (a JSON object)")
    if not (base.get("start") and base.get("end")):
        raise ValueError("the T0 base shot needs both start and end keyframes (every variant shares them)")
    refs = base.get("refs") or []
    if not 1 <= len(refs) <= 2 or not base.get("subjects"):   # reviewers W1/W2/W4: face crop + full-body crop, at most 2
        raise ValueError("the T0 base shot needs one or two identity refs and its subject line(s) for the ref2va variants")
    return refs


def _shared(base):
    return {k: v for k, v in base.items() if k not in DROP and "lora" not in k.lower()}


def _identity(s, base, refs):
    """ref2va variants get the refs and subject lines; fl2va variants get neither (fl2va takes start and end only)."""
    if s["mode"] == "ref2va":
        s.update(refs=list(refs), subjects=list(base["subjects"]))
    return s


def _checked(out, bible):
    for s in out:   # every variant is built before anything is written
        settings_for(s, bible, require_bible=True)
    return out


def expand(base, bible):
    refs = _check_base(base)
    out = []
    for family in ("FL", "REF"):
        mode = "fl2va" if family == "FL" else "ref2va"
        for seed in SEEDS:
            out.append(_identity(dict(_shared(base), id=f"SHOT-T0-{family}-S{seed}", seed=seed, mode=mode), base, refs))
    return _checked(out, bible)


def expand_arms(base, bible):
    refs = _check_base(base)
    out = []
    for arm, (mode, route) in ARMS.items():
        for seed in SEEDS:
            out.append(_identity(dict(_shared(base), id=f"SHOT-T0-{arm}-S{seed}", seed=seed, mode=mode, route=route), base, refs))
    return _checked(out, bible)


def main(shot_path, out_path, style, arms=False):
    src, dst = Path(shot_path), Path(out_path)
    if src.resolve() == dst.resolve():
        raise ValueError("output and input must be different files")
    if dst.exists():
        raise ValueError(f"{dst} exists: refusing to overwrite it")
    base = json.loads(src.read_text(encoding="utf-8"))
    bible = style_bible.load(style)
    variants = expand_arms(base, bible) if arms else expand(base, bible)
    dst.write_text(json.dumps(variants, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--arms"]
    if len(args) != 3:
        sys.exit("usage: python t0_variants.py shot.json out.json style_project [--arms]")
    main(*args, arms="--arms" in sys.argv[1:])
