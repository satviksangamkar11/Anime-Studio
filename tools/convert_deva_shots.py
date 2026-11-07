"""DEVA shots template -> shots with a `look` block (flat mode, WP4 part 4).

  python tools/convert_deva_shots.py IN.json [--out OUT.json] [--pack deva_neon] [--styles-dir DIR]
  convert(shots, pack) -> shots      (pack = the dict from core.style_pack.load_pack)

Moves top-level palette_id, grade, hook_type, impact_frames and vfx_tokens into `look`.
grade -> look.act, hook_type -> look.hook (first shot of an episode only), impact names -> at_s seconds,
vfx tokens -> {color, role}. Every other key is kept. Input is not mutated. Output: indent 2, UTF-8, LF.
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from core.style_pack import load_pack  # noqa: E402

HOOK_CAPTION_PLACEHOLDER = "<hook caption>"   # the owner or writer supplies the real caption
TOKEN_ROLE_ALIASES = {"core": "energy"}      # token suffix -> role; any other suffix word is its own role
_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s\b")
_THIRD_EYE = re.compile(r"third[\s_-]*eye", re.I)


def _words(text):
    return [w for w in re.split(r"[^a-z0-9]+", str(text).lower()) if w]


def _neon_colour(token, pal):
    """Name of the first neon colour whose name shares a word with the token, else None."""
    tw = set(_words(token))
    for name, colour in (pal.get("colors") or {}).items():
        if isinstance(colour, dict) and colour.get("neon") is True and tw & set(_words(name)):
            return name
    return None


def _token_role(token, colour, pal, action):
    suffix = _words(token)[-1]
    role = TOKEN_ROLE_ALIASES.get(suffix, suffix)
    for law in pal.get("special_laws") or []:
        if not isinstance(law, dict) or law.get("color") != colour:
            continue
        only = law.get("only_roles") or []
        if suffix == "burn" and "third_eye" in only and _THIRD_EYE.search(action):
            role = "third_eye"
    return role


def _impact_seconds(name, action, seconds):
    """End of the a-b s range whose text holds the most name words (prefix match); ties go to the first range.
    No range matches: middle of the shot."""
    name_words = _words(name)
    best, best_score = None, 0
    parts = [p for p in str(action).split(";")]
    for part in parts:
        m = _RANGE.search(part)
        if not m:
            continue
        part_words = _words(part[m.end():])
        score = sum(1 for w in name_words if any(t.startswith(w) for t in part_words))
        if score > best_score:
            best, best_score = float(m.group(2)), score
    if best is not None:
        return best
    return round(float(seconds) / 2.0, 3) if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else 0.0


def _convert_shot(shot, pack, first_in_episode):
    out = copy.deepcopy(shot)
    notes = []
    pal_id = out.pop("palette_id", None)
    grade = out.pop("grade", None)
    hook_type = out.pop("hook_type", None)
    impacts = out.pop("impact_frames", None) or []
    tokens = out.pop("vfx_tokens", None) or []
    pal = (pack.get("palettes") or {}).get(pal_id) or {}
    acts = pack.get("acts") or {}
    act_phase = (acts.get(grade) or {}).get("phase") if isinstance(grade, str) else None
    action = out.get("action") if isinstance(out.get("action"), str) else ""

    look = {"palette_id": pal_id, "act": grade, "phase": act_phase,
            "focal": (pal.get("characters") or [None])[0], "focal_value": "lightest"}
    if hook_type is not None:
        if first_in_episode:
            look["hook"] = {"type": hook_type, "caption": HOOK_CAPTION_PLACEHOLDER}
            notes.append(f"hook caption is {HOOK_CAPTION_PLACEHOLDER} (placeholder; the owner or writer supplies it)")
        else:
            notes.append(f"hook_type {hook_type!r} dropped: look.hook is allowed on the first shot only")

    look["impact_frames"] = []
    for imp in impacts:
        if not isinstance(imp, dict):
            notes.append(f"impact entry {imp!r} is not an object; dropped")
            continue
        at_s = _impact_seconds(imp.get("at", ""), action, out.get("seconds"))
        look["impact_frames"].append({"at_s": at_s, "type": imp.get("type"), "frames": imp.get("frames")})

    look["vfx"] = []
    for token in tokens:
        colour = _neon_colour(token, pal) if isinstance(token, str) and _words(token) else None
        if colour is None:
            notes.append(f"vfx token {token!r} matches no neon colour of the palette; dropped")
            continue
        look["vfx"].append({"color": colour, "role": _token_role(token, colour, pal, action)})

    look["accent_use"] = False
    look["hold_purpose"] = None
    out["look"] = look
    if notes:
        out["converter_notes"] = notes
    return out


def convert(shots, pack):
    """Return a new list of shots with the look block. Non-dict items pass through unchanged."""
    seen = set()
    result = []
    for shot in shots:
        if not isinstance(shot, dict):
            result.append(copy.deepcopy(shot))
            continue
        ep = shot.get("episode")
        key = json.dumps(ep, sort_keys=True)
        first = key not in seen
        seen.add(key)
        result.append(_convert_shot(shot, pack, first))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert a DEVA shots template to shots with a look block (flat mode).")
    ap.add_argument("inp")
    ap.add_argument("--out", default=None, help="output file (default: print to stdout)")
    ap.add_argument("--pack", default="deva_neon")
    ap.add_argument("--styles-dir", default=None)
    a = ap.parse_args(argv)
    try:
        shots = json.loads(Path(a.inp).read_text(encoding="utf-8"))
        if not isinstance(shots, list):
            raise ValueError("input must be a JSON list of shots")
        pack = load_pack(a.pack, a.styles_dir)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(convert(shots, pack), indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_bytes(text.encode("utf-8"))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
