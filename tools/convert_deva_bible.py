"""Convert the DEVA-NEON art_bible.json into styles/deva_neon.json (WP2).

Usage: python tools/convert_deva_bible.py ART_BIBLE.json [--out PATH]
Deterministic: same input gives byte-identical output. No hex value is changed.
The DEVA zip folder is an input path only; it is never copied into the repo.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK_ID = "deva_neon"
NEON_WORDS = ("glow", "energy", "vfx", "burn", "afterimage", "trail", "kill-mark", "kill mark")

PALETTE_CHARS = {
    "shiva_neelkanth": ["CHAR-SHIVA"],
    "hanuman_vayu": ["CHAR-HANUMAN"],
    "karna_surya": ["CHAR-KARNA"],
    "durga_kali_shakti": ["CHAR-DURGA", "CHAR-KALI"],
    "narasimha_twilight": ["CHAR-NARASIMHA"],
}
SPECIAL_LAWS = {
    "shiva_neelkanth": [{"id": "SHIVA-EYE", "color": "Trialokya Saffron", "only_roles": ["third_eye"]}],
    "karna_surya": [{"id": "KARNA-TRAGIC", "tag": "tragic", "only_impact_types": ["black_out"]}],
    "durga_kali_shakti": [{"id": "DURGA-TRAILS", "role": "weapon_trail", "max_vfx": 3}],
    "narasimha_twilight": [{"id": "NARASIMHA-TIME", "reveal_impact": {"type": "black_out", "frames": 3}}],
}
FOCAL_HINTS = {
    "shiva_neelkanth": {"hero": "Vibhuti Ash", "bg": "Mahakal Void"},
    "hanuman_vayu": {"hero": "Dawn Vermilion", "bg": "Sky Teal"},
    "karna_surya": {"hero": "Molten Gold", "bg": "Dusk Clay"},
    "durga_kali_shakti": {"hero": "Rani Pink", "bg": "Midnight Indigo"},
    "narasimha_twilight": {"hero": "Feral Amber", "bg": "Shadow Violet"},
}
PRESERVED = ("devanagari", "hook_primary", "hook_alt", "impact", "grades", "respect_guardrail", "trail_rule")
TYPE_MAX_FRAMES = {"white_out": 2, "black_out": 3, "inverted": 2, "alpha_sil": 2, "chroma_split": 2}
# Spec 3.2 luma/sat per act (the DEVA example values). Phase id -> act.
ACT_PLAN = [("HOOK", "PH-HOOK", "hook", "play", [0.30, 0.55], [0.35, 0.60]),
            ("BUILD", "PH-BUILD", "build", "play", [0.20, 0.45], [0.20, 0.40]),
            ("DROP", "PH-DROP", "peak", "threat", [0.25, 0.55], [0.40, 0.70]),
            ("OUTRO", "PH-OUTRO", "outro", "release", [0.15, 0.40], [0.15, 0.35])]


def _temp(value):
    """'warm+6' -> 6, 'cool-4' -> -4, '+2' -> 2 (numbers pass through)."""
    if isinstance(value, (int, float)):
        return value
    return int(re.search(r"[+-]?\d+", value).group())


def _grade(grade):
    out = {}
    for key, value in grade.items():
        if key == "act":
            continue
        out[key] = _temp(value) if key == "temp" else value
    return out


def _colours(pal):
    out = {}
    for name, c in pal["colors"].items():
        role = c["role"]
        out[name] = {"hex": c["hex"], "role": role, "usage_pct": c["usage"],
                     "neon": any(word in role.lower() for word in NEON_WORDS)}
    return out


def build(art):
    fl = art.get("frame_law", {})
    phases, acts = [], {}
    for act, phase_id, act_role, phase_role, luma, sat in ACT_PLAN:
        phases.append({"id": phase_id, "role": phase_role, "key": None, "accent": None,
                       "luma_mean": list(luma), "sat_mean": list(sat), "lut": f"luts/deva_neon/{act}.cube"})
        ph = phases[-1]
        acts[act] = {"role": act_role, "phase": phase_id, "lut": ph["lut"],
                     "luma_mean": list(luma), "sat_mean": list(sat)}
        if act in art.get("grades", {}):
            acts[act]["grade"] = _grade(art["grades"][act])
    palettes = {}
    for name, pal in art["palettes"].items():
        entry = {
            "characters": PALETTE_CHARS.get(name, []),
            "time_lock": ({"keywords": ["sandhya", "twilight", "dusk"], "note": pal["time_lock"]}
                          if pal.get("time_lock") else None),
            "colors": _colours(pal),
            "special_laws": SPECIAL_LAWS.get(name, []),
        }
        for key in PRESERVED:
            if key in pal:
                entry[key] = pal[key]
        if name in FOCAL_HINTS:
            entry["focal_hints"] = dict(FOCAL_HINTS[name])
        palettes[name] = entry
    return {
        "pack_id": PACK_ID,
        "version": "1.2",
        "status": "draft",
        "source": {"art_bible": art.get("art_bible"), "version": art.get("version")},
        "colour_script": {"phases": phases},
        "acts": acts,
        "palettes": palettes,
        "frame_law": {
            "min_dL_focal_vs_bg": fl.get("min_dL_hero_vs_bg", 55),
            "max_neon_hues_per_shot": fl.get("neon_dominant_per_shot", 1),
            "pure_white_area_cap_frac": fl.get("pure_white_area_cap_pct", 8) / 100,
            "area_split": [fl.get("environment_pct", 70), fl.get("character_pct", 20),
                           fl.get("ignition_pct", 10)],
        },
        "impact": {"allowed_types": list(art.get("impact", {}).get("types", [])),
                   "type_max_frames": dict(TYPE_MAX_FRAMES)},
        "typography": {"display": "Rajdhani", "sacred": "Yatra One", "subtitle_latin": "Inter",
                       "subtitle_devanagari": "Noto Sans Devanagari", "min_px_at_1080w": 22,
                       "font_dir": "styles/fonts",
                       "lockup": {"leader": "devanagari", "latin_size_frac": 0.4,
                                  "latin_opacity": 0.7, "gap_px_1080": 16}},
        "prompt_forbidden_words": [],
        "guardrails": ["no gore-shock framing of the goddess"],
        "sound_sync": {"enabled": False, "events": list(art.get("sound_sync", {}).get("events", []))},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="DEVA art_bible.json -> styles/deva_neon.json")
    ap.add_argument("art_bible")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else ROOT / "styles" / f"{PACK_ID}.json"
    art = json.loads(Path(args.art_bible).read_text(encoding="utf-8"))
    text = json.dumps(build(art), indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
