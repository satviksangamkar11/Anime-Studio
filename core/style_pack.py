"""Style-pack loading, schema validation and colour maths (WP1). Standard library only."""
import json
import math
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CORE_PATH = _HERE / "core.json"
_STYLES_DIR = _HERE.parent / "styles"

ACT_ROLES = ("hook", "build", "peak", "outro", "neutral")
PHASE_ROLES = ("play", "threat", "release")
PACK_STATUS = ("draft", "owner_approved")

_HEX_HASH = re.compile(r"^#[0-9A-Fa-f]{6}$")
_HEX_BARE = re.compile(r"^[0-9A-Fa-f]{6}$")


# ---- loading ----
def load_core():
    return json.loads(_CORE_PATH.read_text(encoding="utf-8"))


def default_pack_id():
    """The style pack a story gets when its story.json names none (owner 2026-11-07: Deva Neon for every story)."""
    value = load_core().get("default_style_pack")
    return value if isinstance(value, str) and value else "deva_neon"


def pack_for_story(story, styles_dir=None):
    """The pack id a story uses: its own story['style_pack'] when that pack exists, else the default."""
    own = story.get("style_pack") if isinstance(story, dict) else None
    base = Path(styles_dir) if styles_dir is not None else _STYLES_DIR
    if isinstance(own, str) and own and not re.search(r"[\/]|\.\.", own) and (base / f"{own}.json").is_file():
        return own
    return default_pack_id()


def list_packs(styles_dir=None):
    """Every style pack on disk as plain data for the UI: id, status, whether it has grade numbers or LUT files, act names."""
    base = Path(styles_dir) if styles_dir is not None else _STYLES_DIR
    out = []
    for path in sorted(base.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("pack_id") != path.stem:
            continue
        acts = data.get("acts") if isinstance(data.get("acts"), dict) else {}
        out.append({
            "id": path.stem, "status": data.get("status") if isinstance(data.get("status"), str) else "draft",
            "acts": list(acts), "has_grade_numbers": all(isinstance(a, dict) and isinstance(a.get("grade"), dict) for a in acts.values()) and bool(acts),
            "default": path.stem == default_pack_id()})
    return out


def load_pack(pack_id, styles_dir=None):
    if not isinstance(pack_id, str) or not pack_id or re.search(r"[\\/]|\.\.", pack_id):
        raise ValueError(f"bad pack id: {pack_id!r}")
    base = Path(styles_dir) if styles_dir is not None else _STYLES_DIR
    path = base / f"{pack_id}.json"
    if not path.is_file():
        raise ValueError(f"style pack not found: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"style pack {path.name} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"style pack {path.name} must be a JSON object")
    return data


# ---- colour maths (sRGB D65 -> CIELAB, CIEDE2000) ----
_M = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)
_WHITE = (0.95047, 1.0, 1.08883)


def _rgb_from(value):
    if isinstance(value, str):
        s = value[1:] if value.startswith("#") else value
        if not _HEX_BARE.match(s):
            raise ValueError(f"not a hex colour: {value!r}")
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    if (isinstance(value, (tuple, list)) and len(value) == 3
            and all(type(v) is int and 0 <= v <= 255 for v in value)):
        return tuple(value)
    raise ValueError(f"not a colour: {value!r}")


def _linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lab_f(t):
    return t ** (1.0 / 3.0) if t > (6.0 / 29.0) ** 3 else t / (3 * (6.0 / 29.0) ** 2) + 4.0 / 29.0


def srgb_to_lab(hex_or_rgb):
    r, g, b = (_linear(v) for v in _rgb_from(hex_or_rgb))
    x, y, z = (m[0] * r + m[1] * g + m[2] * b for m in _M)
    fx, fy, fz = _lab_f(x / _WHITE[0]), _lab_f(y / _WHITE[1]), _lab_f(z / _WHITE[2])
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def l_star(hex_or_rgb):
    return srgb_to_lab(hex_or_rgb)[0]


def _hue(b, a):
    if a == 0 and b == 0:
        return 0.0
    h = math.degrees(math.atan2(b, a))
    return h + 360 if h < 0 else h


def delta_e_2000(lab1, lab2):
    """CIEDE2000 with kL = kC = kH = 1 (Sharma, Wu, Dalal 2005)."""
    L1, a1, b1 = (float(v) for v in lab1)
    L2, a2, b2 = (float(v) for v in lab2)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p, h2p = _hue(b1, a1p), _hue(b2, a2p)

    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        if dhp > 180:
            dhp -= 360
        elif dhp < -180:
            dhp += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))

    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2

    T = (1 - 0.17 * math.cos(math.radians(hbp - 30))
         + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6))
         - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    d_theta = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Lsq = (Lbp - 50) ** 2
    SL = 1 + 0.015 * Lsq / math.sqrt(20 + Lsq)
    SC = 1 + 0.045 * Cbp
    SH = 1 + 0.015 * Cbp * T
    RT = -math.sin(math.radians(2 * d_theta)) * Rc
    term = RT * (dCp / SC) * (dHp / SH)
    return math.sqrt(max(0.0, (dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2 + term))


# ---- validation (never raises; returns one string per error) ----
def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def _hex_ok(v):
    return isinstance(v, str) and _HEX_HASH.match(v) is not None


def _range_ok(v):
    return (isinstance(v, list) and len(v) == 2 and all(_is_num(x) and 0 <= x <= 1 for x in v)
            and v[0] <= v[1])


def _lut_ok(v):
    if not isinstance(v, str) or not v.endswith(".cube") or len(v) <= len(".cube"):
        return False
    if v.startswith(("/", "\\")) or ":" in v:
        return False
    return ".." not in re.split(r"[\\/]", v)


def _check_colour_script(cs, errors):
    if not isinstance(cs, dict):
        errors.append("colour_script must be an object")
        return set()
    phases = cs.get("phases")
    if not isinstance(phases, list) or not phases:
        errors.append("colour_script.phases must be a non-empty list")
        return set()
    ids = set()
    for i, ph in enumerate(phases):
        where = f"colour_script.phases[{i}]"
        if not isinstance(ph, dict):
            errors.append(f"{where} must be an object")
            continue
        pid = ph.get("id")
        if not _nonempty_str(pid):
            errors.append(f"{where}.id must be a non-empty string")
        elif pid in ids:
            errors.append(f"{where}.id '{pid}' is duplicated")
        else:
            ids.add(pid)
        if ph.get("role") not in PHASE_ROLES:
            errors.append(f"{where}.role must be one of {', '.join(PHASE_ROLES)}")
        if not _range_ok(ph.get("luma_mean")):
            errors.append(f"{where}.luma_mean must be [lo, hi] with 0 <= lo <= hi <= 1")
        if not _range_ok(ph.get("sat_mean")):
            errors.append(f"{where}.sat_mean must be [lo, hi] with 0 <= lo <= hi <= 1")
        if not _lut_ok(ph.get("lut")):
            errors.append(f"{where}.lut must be a relative .cube path with no '..'")
        for key in ("key", "accent"):
            if ph.get(key) is not None and not _hex_ok(ph.get(key)):
                errors.append(f"{where}.{key} must be #RRGGBB or null")
        if "temp" in ph and not isinstance(ph["temp"], str):
            errors.append(f"{where}.temp must be a string")
    return ids


def _check_acts(acts, phase_ids, errors):
    if not isinstance(acts, dict) or not acts:
        errors.append("acts must be a non-empty object")
        return
    for name, act in acts.items():
        where = f"acts.{name}"
        if not isinstance(act, dict):
            errors.append(f"{where} must be an object")
            continue
        if act.get("role") not in ACT_ROLES:
            errors.append(f"{where}.role must be one of {', '.join(ACT_ROLES)}")
        phase = act.get("phase")
        if not isinstance(phase, str) or phase not in phase_ids:
            errors.append(f"{where}.phase '{phase}' is not a phase in colour_script.phases")
        if not _lut_ok(act.get("lut")):
            errors.append(f"{where}.lut must be a relative .cube path with no '..'")
        if not _range_ok(act.get("luma_mean")):
            errors.append(f"{where}.luma_mean must be [lo, hi] with 0 <= lo <= hi <= 1")
        if not _range_ok(act.get("sat_mean")):
            errors.append(f"{where}.sat_mean must be [lo, hi] with 0 <= lo <= hi <= 1")
        if "grain" in act and not isinstance(act["grain"], bool):
            errors.append(f"{where}.grain must be true or false")
        if "grade" in act:
            grade = act["grade"]
            if not isinstance(grade, dict) or not all(_is_num(v) for v in grade.values()):
                errors.append(f"{where}.grade must be an object of numbers")


def _check_palettes(palettes, errors):
    if not isinstance(palettes, dict) or not palettes:
        errors.append("palettes must be a non-empty object")
        return
    for pname, pal in palettes.items():
        where = f"palettes.{pname}"
        if not isinstance(pal, dict):
            errors.append(f"{where} must be an object")
            continue
        chars = pal.get("characters")
        if not isinstance(chars, list) or not all(isinstance(c, str) for c in chars):
            errors.append(f"{where}.characters must be a list of strings")
        tl = pal.get("time_lock")
        if tl is not None and (not isinstance(tl, dict) or not isinstance(tl.get("keywords"), list)
                               or not all(isinstance(k, str) for k in tl["keywords"])):
            errors.append(f"{where}.time_lock must be null or an object with a keywords list")
        colors = pal.get("colors")
        if not isinstance(colors, dict):
            errors.append(f"{where}.colors must be an object")
            colors = {}
        for cname, c in colors.items():
            cw = f"{where}.colors['{cname}']"
            if not isinstance(c, dict):
                errors.append(f"{cw} must be an object")
                continue
            if not _hex_ok(c.get("hex")):
                errors.append(f"{cw}.hex must be #RRGGBB")
            if not isinstance(c.get("role"), str):
                errors.append(f"{cw}.role must be a string")
            if not _is_num(c.get("usage_pct")):
                errors.append(f"{cw}.usage_pct must be a number")
            if not isinstance(c.get("neon"), bool):
                errors.append(f"{cw}.neon must be true or false")
        laws = pal.get("special_laws", [])
        if not isinstance(laws, list):
            errors.append(f"{where}.special_laws must be a list")
        else:
            for i, law in enumerate(laws):
                if not isinstance(law, dict) or not _nonempty_str(law.get("id")):
                    errors.append(f"{where}.special_laws[{i}] must be an object with a string id")
        if "accent_max_per_episode" in pal:
            v = pal["accent_max_per_episode"]
            if not (_is_int(v) and v >= 0):
                errors.append(f"{where}.accent_max_per_episode must be an integer >= 0")


def _check_frame_law(fl, errors):
    if not isinstance(fl, dict):
        errors.append("frame_law must be an object")
        return
    v = fl.get("max_neon_hues_per_shot")
    if not (_is_int(v) and v >= 0):
        errors.append("frame_law.max_neon_hues_per_shot must be an integer >= 0")
    v = fl.get("min_dL_focal_vs_bg")
    if v is not None and not _is_num(v):
        errors.append("frame_law.min_dL_focal_vs_bg must be a number or null")
    v = fl.get("pure_white_area_cap_frac")
    if not (_is_num(v) and 0 <= v <= 1):
        errors.append("frame_law.pure_white_area_cap_frac must be a number from 0 to 1")
    if "area_split" in fl:
        v = fl["area_split"]
        if not (isinstance(v, list) and len(v) == 3 and all(_is_num(x) for x in v)):
            errors.append("frame_law.area_split must be a list of 3 numbers")


def _check_impact(imp, errors):
    if not isinstance(imp, dict):
        errors.append("impact must be an object")
        return
    allowed = imp.get("allowed_types")
    if not isinstance(allowed, list) or not all(isinstance(t, str) for t in allowed):
        errors.append("impact.allowed_types must be a list of strings")
    tmf = imp.get("type_max_frames")
    if not isinstance(tmf, dict) or not all(_is_int(v) and v >= 0 for v in tmf.values()):
        errors.append("impact.type_max_frames must be an object of integers >= 0")


def _check_typography(t, errors):
    if not isinstance(t, dict):
        errors.append("typography must be an object")
        return
    for key in ("subtitle_latin", "subtitle_devanagari", "font_dir"):
        if not _nonempty_str(t.get(key)):
            errors.append(f"typography.{key} must be a non-empty string")
    if not _is_num(t.get("min_px_at_1080w")):
        errors.append("typography.min_px_at_1080w must be a number")
    for key in ("display", "sacred"):
        if t.get(key) is not None and not isinstance(t.get(key), str):
            errors.append(f"typography.{key} must be a string or null")
    if "lockup" in t and not isinstance(t["lockup"], dict):
        errors.append("typography.lockup must be an object")


def _check_environments(envs, errors):
    if envs is None:
        return
    if not isinstance(envs, list):
        errors.append("environments must be a list")
        return
    for i, env in enumerate(envs):
        where = f"environments[{i}]"
        if not isinstance(env, dict) or not _nonempty_str(env.get("id")):
            errors.append(f"{where} must be an object with a string id")
            continue
        m = env.get("measured")
        if not isinstance(m, dict) or not all(_is_num(m.get(k)) for k in ("L", "a", "b")):
            errors.append(f"{where}.measured must hold numeric L, a and b")


def _check_str_list(pack, key, errors):
    v = pack.get(key)
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        errors.append(f"{key} must be a list of strings")


def _check_pack(pack, errors):
    if not isinstance(pack, dict):
        errors.append(f"pack must be a JSON object, got {type(pack).__name__}")
        return
    if not _nonempty_str(pack.get("pack_id")):
        errors.append("pack_id must be a non-empty string")
    if pack.get("status") not in PACK_STATUS:
        errors.append(f"status must be one of {', '.join(PACK_STATUS)}")
    phase_ids = _check_colour_script(pack.get("colour_script"), errors)
    _check_acts(pack.get("acts"), phase_ids, errors)
    _check_palettes(pack.get("palettes"), errors)
    _check_frame_law(pack.get("frame_law"), errors)
    _check_impact(pack.get("impact"), errors)
    _check_typography(pack.get("typography"), errors)
    _check_environments(pack.get("environments"), errors)
    _check_str_list(pack, "prompt_forbidden_words", errors)
    _check_str_list(pack, "guardrails", errors)


def validate_pack(pack):
    errors = []
    try:
        _check_pack(pack, errors)
    except Exception as exc:  # safety net: junk input must never raise
        errors.append(f"pack could not be checked: {type(exc).__name__}: {exc}")
    return errors
