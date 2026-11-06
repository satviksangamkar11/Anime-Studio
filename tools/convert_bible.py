"""Convert director/style/<name>.json (Kaliya bible) into styles/braj_earth.json (WP2).

Usage: python tools/convert_bible.py kaliya_mardan [--out PATH]
Deterministic: same input gives byte-identical output (LF, ensure_ascii=False, fixed key order).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK_ID = "braj_earth"
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
A9_LINE = "avoid white-dominant frames on joyful beats (white = mourning in Hindu custom)"

# Spec 3.2 + WP2 + A14, verbatim numbers. role added per A23.
PHASES = [
    {"id": "PH-DAWN-PLAY", "role": "play", "key": "#E9C98F", "accent": "#E8B531", "temp": "warm",
     "luma_mean": [0.45, 0.65], "sat_mean": [0.25, 0.45], "lut": "luts/ph_dawn_play.cube"},
    {"id": "PH-POISON", "role": "threat", "key": "#1F3A3E", "accent": "#5B3E6B", "temp": "cool",
     "luma_mean": [0.15, 0.35], "sat_mean": [0.10, 0.25], "lut": "luts/ph_poison.cube"},
    {"id": "PH-PURIFIED", "role": "release", "key": "#6FA7B0", "accent": "#F6D27A", "temp": "neutral-warm",
     "luma_mean": [0.45, 0.70], "sat_mean": [0.30, 0.50], "lut": "luts/ph_purified.cube"},
]
HERO_CONTRAST = {"pair": ["pitambara_gold", "violet_fume"],
                 "note": "near-complementary; reserve for hooks and climaxes"}
LIMITS = {"shot_drift_de2000": 6, "cut_jump_de2000": 8, "flicker_luma_step": 0.04}
# (act, phase id, act role). A23: acts are derived from phases, never typed.
ACT_PLAN = [("HOOK", "PH-DAWN-PLAY", "hook"), ("BUILD", "PH-DAWN-PLAY", "build"),
            ("DROP", "PH-POISON", "peak"), ("OUTRO", "PH-PURIFIED", "outro")]
LOCKUP = {"leader": "devanagari", "latin_size_frac": 0.4, "latin_opacity": 0.7, "gap_px_1080": 16}


STOP_WORDS = {"in", "and", "on", "at", "the", "of", "with", "to", "a", "an", "or", "from", "for",
              "over", "under", "by", "is", "its", "from", "behind", "under"}


def _label_before(text, pos):
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", text[:pos])]
    words = [w for w in words if w not in STOP_WORDS and len(w) >= 3]
    return words[-1] if words else ""


def _hex_labels(text, prefix):
    """(name, hex) for each hex in text; name = word before the hex (fallback 'tone N')."""
    out = []
    for n, m in enumerate(HEX_RE.finditer(text), start=1):
        label = _label_before(text, m.start())
        if not label or label == prefix:
            label = f"tone {n}"
        out.append((f"{prefix} {label}".strip(), m.group(0)))
    return out


def _noun(piece):
    seg = re.sub(r"\(.*?\)", "", piece)
    seg = re.split(r",|:|\s(?:tied|with|in|as|over|on|and|of|for|at|from)\s", seg)[0]
    words = re.findall(r"[A-Za-z]+", seg)
    return words[-1].lower() if words else "cloth"


class _Palette:
    def __init__(self):
        self.colors = {}
        self.seen_hex = set()

    def add(self, name, hex_, role):
        if not hex_ or not HEX_RE.fullmatch(hex_) or hex_.upper() in self.seen_hex:
            return
        self.seen_hex.add(hex_.upper())
        base, name_, i = name, name, 2
        while name_ in self.colors:
            name_, i = f"{base} {i}", i + 1
        self.colors[name_] = {"hex": hex_, "role": role, "usage_pct": 0, "neon": False}


def _character_palette(char):
    pal = _Palette()
    for name, hex_ in _hex_labels(char.get("skin", {}).get("treatment", ""), "skin"):
        pal.add(name, hex_, "skin")
    pal.add("hair base", char.get("hair", {}).get("base_colour"), "hair")
    for item in char.get("costume", []):
        noun = _noun(item.get("piece", ""))
        pal.add(noun, item.get("colour_hex"), "cloth")
        pal.add(f"{noun} shade", item.get("shade_hex"), "cloth")
        pal.add(f"{noun} border", item.get("border_hex"), "ornament")
        pal.add(f"{noun} accent", item.get("accent_hex"), "ornament")
    for item in char.get("jewellery", []):
        pal.add(_noun(item.get("piece", "")), item.get("colour_hex"), "ornament")
    return pal.colors


def _environment_palette(env):
    pal = _Palette()
    texts = [env.get("day_key", ""), env.get("night_key", "")]
    texts += list(env.get("composition", {}).values())
    for text in texts:
        for name, hex_ in _hex_labels(text, ""):
            pal.add(name, hex_, "environment")
    return pal.colors


def _palette_id(item_id):
    return item_id.lower().replace("-", "_")


def build(bible):
    phases = [dict(p) for p in PHASES]
    by_id = {p["id"]: p for p in phases}
    acts = {}
    for act, phase_id, role in ACT_PLAN:
        ph = by_id[phase_id]
        acts[act] = {"role": role, "phase": phase_id, "lut": ph["lut"],
                     "luma_mean": list(ph["luma_mean"]), "sat_mean": list(ph["sat_mean"])}
    palettes = {}
    for char in bible["characters"]:
        palettes[_palette_id(char["id"])] = {
            "characters": [char["id"]], "time_lock": None, "colors": _character_palette(char),
            "special_laws": [], "accent_max_per_episode": 1}
    for env in bible["environments"]:
        palettes[_palette_id(env["id"])] = {
            "characters": [], "time_lock": None, "colors": _environment_palette(env),
            "special_laws": [], "accent_max_per_episode": 1}
    restrictions = list(bible["iconography"]["restrictions"])
    return {
        "pack_id": PACK_ID,
        "version": "1.2",
        "status": "draft",
        "source_status": bible["status"],
        "source": {"project": bible["project"], "version": bible["version"]},
        "references": bible.get("references", []),
        "colour_script": {"phases": phases, "hero_contrast": dict(HERO_CONTRAST), "limits": dict(LIMITS)},
        "acts": acts,
        "palettes": palettes,
        "frame_law": {"min_dL_focal_vs_bg": None, "max_neon_hues_per_shot": 0,
                      "pure_white_area_cap_frac": 0.08},
        "impact": {"allowed_types": [], "type_max_frames": {}},
        "typography": {"display": None, "sacred": None, "subtitle_latin": "Inter",
                       "subtitle_devanagari": "Noto Sans Devanagari", "min_px_at_1080w": 22,
                       "font_dir": "styles/fonts", "lockup": dict(LOCKUP)},
        "environments": [],
        "prompt_forbidden_words": ["neon", "glow aura", "halo"],
        "guardrails": restrictions + [A9_LINE],
        "sound_sync": {"enabled": False},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Kaliya bible -> styles/braj_earth.json")
    ap.add_argument("name")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if not NAME_RE.match(args.name):
        print(f"bad bible name: {args.name!r}", file=sys.stderr)
        return 2
    src = ROOT / "director" / "style" / f"{args.name}.json"
    out = Path(args.out) if args.out else ROOT / "styles" / f"{PACK_ID}.json"
    bible = json.loads(src.read_text(encoding="utf-8"))
    text = json.dumps(build(bible), indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
