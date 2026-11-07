"""ASS caption builder (WP8 part 2). Standard library plus style_pack helpers.

Builds the .ass text only. Never runs ffmpeg, never reads font files, never raises on junk input.
Output is deterministic: the same input gives byte-identical text.
"""
import math
import re

from core.style_pack import _linear, _rgb_from, l_star

# Documented caption constants (A19). The owner may change them here.
FILL_HEX = "#FFFFFF"         # caption fill
OUTLINE_HEX = "#000000"      # caption outline
MIN_OUTLINE_DELTA_L = 40.0   # outline vs fill DeltaL* below this gives a WARN
# Tune values (OPEN_QUESTIONS): default size, outline formula, wrap estimate.
BASE_PX_1080 = 34            # default caption size at 1080 wide, never below min_px_at_1080w
OUTLINE_FRAC = 0.08          # outline width = ceil(size * OUTLINE_FRAC) px
CHAR_WIDTH_FRAC = 0.6        # wrap estimate: average glyph width as a fraction of size
# Pack defaults when typography.lockup omits a key (spec A3: DEVA values).
DEFAULT_LATIN_FRAC = 0.4
DEFAULT_LATIN_OPACITY = 0.7
DEFAULT_GAP_1080 = 16
REF_WIDTH = 1080
FALLBACK_HEIGHT = 1920       # used only when the width or height given is junk
DEVA_LANGS = ("hi", "mr")
_DEVA_CHAR = re.compile("[ऀ-ॿ]")


class _Junk(Exception):
    """Input that cannot produce captions. Becomes one FAIL entry and a minimal ASS file."""


def _entry(level, message):
    return {"rule": "CAP", "level": level, "shot": None, "episode": None, "message": message}


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def ass_time(seconds):
    """H:MM:SS.cc (centiseconds, rounded). Junk input gives 0:00:00.00."""
    try:
        cs = int(math.floor(float(seconds) * 100 + 0.5))
    except (TypeError, ValueError, OverflowError):
        cs = 0
    cs = max(cs, 0)
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _rel_lum(hex_or_rgb):
    r, g, b = (_linear(v) for v in _rgb_from(hex_or_rgb))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a, hex_b):
    """WCAG 2.x contrast ratio, 1.0 to 21.0."""
    la, lb = _rel_lum(hex_a), _rel_lum(hex_b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def wrap_estimate(text, size):
    """Estimated width in px of the longest line of text at the given font size."""
    try:
        longest = max(len(line) for line in str(text).split("\n"))
        return int(round(CHAR_WIDTH_FRAC * float(size) * longest))
    except (TypeError, ValueError):
        return 0


def _ass_colour(hex_or_rgb):
    r, g, b = _rgb_from(hex_or_rgb)
    return f"&H00{b:02X}{g:02X}{r:02X}"


def _family(value):
    if not isinstance(value, str):
        return None
    s = re.sub(r"[,{}\\\r\n]", " ", value).strip()
    return s or None


def _escape(text):
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\\", "")
    s = s.replace("{", "(").replace("}", ")")
    return s.replace("\n", "\\N")


def _has_deva(text):
    return _DEVA_CHAR.search(text) is not None


def _opt(mapping, key, default, lo, hi, entries):
    """Optional numeric lockup value; invalid or missing gives the default (WARN if invalid)."""
    if key not in mapping or mapping[key] is None:
        return default
    v = mapping[key]
    if _is_num(v) and lo <= v <= hi:
        return v
    entries.append(_entry("WARN", f"typography.lockup.{key} is invalid; default {default} used"))
    return default


def _dims(width, height):
    ok = all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in (width, height))
    if not ok:
        raise _Junk(f"width and height must be positive integers, got {width!r} x {height!r}")
    return width, height


def _document(width, height, margin, lead, sub, dialogues):
    """lead / sub are (family, size, outline) tuples."""
    lead_family, lead_size, lead_outline = lead
    sub_family, sub_size, sub_outline = sub
    fill, outline = _ass_colour(FILL_HEX), _ass_colour(OUTLINE_HEX)
    style_fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
                 "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
                 "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")

    def style(name, family, size, out_w):
        return (f"Style: {name},{family},{size},{fill},&H000000FF,{outline},&H00000000,"
                f"0,0,0,0,100,100,0,0,1,{out_w},0,5,{margin},{margin},0,1")

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        style_fmt,
        style("Lead", lead_family, lead_size, lead_outline),
        style("Sub", sub_family, sub_size, sub_outline),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    lines.extend(dialogues)
    return "\n".join(lines) + "\n"


def _minimal(width, height):
    w, h = (width, height) if _dims_ok(width, height) else (REF_WIDTH, FALLBACK_HEIGHT)
    size = math.ceil(BASE_PX_1080 * w / REF_WIDTH)
    outline = math.ceil(round(size * OUTLINE_FRAC, 9))
    return _document(w, h, 0, ("", size, outline), ("", size, outline), [])


def _dims_ok(width, height):
    return all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in (width, height))


def _validate_core(core):
    if not isinstance(core, dict) or not isinstance(core.get("safe_zone_frac"), dict) \
            or not isinstance(core.get("retention"), dict):
        raise _Junk("core must hold safe_zone_frac and retention objects")
    sz, ret = core["safe_zone_frac"], core["retention"]
    band = sz.get("caption_band")
    if not (isinstance(band, list) and len(band) == 2 and all(_is_num(x) for x in band)
            and 0 <= band[0] < band[1] <= 1):
        raise _Junk("core.safe_zone_frac.caption_band must be [top, bottom] fractions")
    if not (_is_num(sz.get("right")) and 0 <= sz["right"] < 1):
        raise _Junk("core.safe_zone_frac.right must be a fraction from 0 to 1")
    if not (_is_num(ret.get("caption_min_on_screen_s")) and ret["caption_min_on_screen_s"] >= 0):
        raise _Junk("core.retention.caption_min_on_screen_s must be a number >= 0")
    if not (_is_num(ret.get("caption_min_contrast")) and ret["caption_min_contrast"] > 0):
        raise _Junk("core.retention.caption_min_contrast must be a positive number")
    return band, sz["right"], float(ret["caption_min_on_screen_s"]), ret["caption_min_contrast"]


def _clean_cues(cues, entries):
    valid = []
    for idx, cue in enumerate(cues):
        if not isinstance(cue, dict):
            entries.append(_entry("WARN", f"cue {idx} skipped: not an object"))
            continue
        t0, t1 = cue.get("t0"), cue.get("t1")
        if not (_is_num(t0) and _is_num(t1)):
            entries.append(_entry("WARN", f"cue {idx} skipped: t0 and t1 must be numbers"))
            continue
        if t0 < 0 or t1 <= t0:
            entries.append(_entry("WARN", f"cue {idx} skipped: needs 0 <= t0 < t1"))
            continue
        text = cue.get("text")
        if not isinstance(text, str) or not text.strip():
            entries.append(_entry("WARN", f"cue {idx} skipped: empty text"))
            continue
        latin = cue.get("latin")
        if latin is not None and not isinstance(latin, str):
            entries.append(_entry("WARN", f"cue {idx}: latin line ignored (not a string)"))
            latin = None
        latin = latin.strip() if isinstance(latin, str) and latin.strip() else None
        valid.append({"index": idx, "t0": float(t0), "t1": float(t1),
                      "text": text.strip(), "latin": latin})
    valid.sort(key=lambda c: (c["t0"], c["t1"], c["index"]))
    return valid


def _build(cues, pack, core, width, height, language, entries):
    if not isinstance(cues, list):
        raise _Junk("cues must be a list")
    width, height = _dims(width, height)
    if not isinstance(pack, dict) or not isinstance(pack.get("typography"), dict):
        raise _Junk("pack must be an object with a typography object")
    typo = pack["typography"]
    min_px = typo.get("min_px_at_1080w")
    if not _is_num(min_px):
        raise _Junk("typography.min_px_at_1080w must be a number")
    band, right, min_on, min_contrast = _validate_core(core)

    lang = language.strip().lower() if isinstance(language, str) else ""
    W, H = width, height

    # Sizes (A3): never below min_px_at_1080w scaled to the render width.
    lead_size = math.ceil(max(min_px, BASE_PX_1080) * W / REF_WIDTH)
    lockup = typo.get("lockup") if isinstance(typo.get("lockup"), dict) else {}
    frac = _opt(lockup, "latin_size_frac", DEFAULT_LATIN_FRAC, 0, 1, entries)
    opacity = _opt(lockup, "latin_opacity", DEFAULT_LATIN_OPACITY, 0, 1, entries)
    gap = _opt(lockup, "gap_px_1080", DEFAULT_GAP_1080, 0, 10000, entries) * W / REF_WIDTH
    latin_size = round(frac * lead_size)
    min_latin = math.ceil(min_px * W / REF_WIDTH)
    if latin_size < min_latin:
        latin_size = min_latin
        entries.append(_entry("WARN", f"latin line raised to the minimum size ({min_latin} px)"))
    alpha = math.floor((1 - opacity) * 255 + 0.5)

    margin = round(right * W)
    text_w = W - 2 * margin
    band_top, band_bot = band[0] * H, band[1] * H
    mid = (band[0] + band[1]) / 2 * H
    x = round((W - right * W) / 2)

    # Font families. Lead = Devanagari when the language or any cue calls for it.
    def pick(want_deva):
        dev = _family(typo.get("subtitle_devanagari"))
        lat = _family(typo.get("subtitle_latin"))
        primary, other, pname, oname = ((dev, lat, "subtitle_devanagari", "subtitle_latin")
                                        if want_deva else
                                        (lat, dev, "subtitle_latin", "subtitle_devanagari"))
        if primary:
            return primary
        if other:
            entries.append(_entry("WARN", f"typography.{pname} is empty; using {oname} as the font"))
            return other
        entries.append(_entry("WARN", "no usable subtitle font family in typography"))
        return ""

    cues = _clean_cues(cues, entries)
    doc_deva = lang in DEVA_LANGS or any(_has_deva(c["text"]) for c in cues)
    lead_family = pick(doc_deva)
    sub_family = pick(False)

    # Shortest on-screen time (retention) with the overlap guard.
    for i, cue in enumerate(cues):
        cue["end"] = cue["t1"]
        if cue["t1"] - cue["t0"] < min_on - 1e-9:
            new_end = cue["t0"] + min_on
            nxt = cues[i + 1] if i + 1 < len(cues) else None
            if nxt is not None and new_end > nxt["t0"] + 1e-9:
                entries.append(_entry("WARN", f"cue {cue['index']}: shorter than {min_on:g} s "
                                              "on screen and would overlap the next cue; kept"))
            else:
                cue["end"] = new_end

    outline_lead = math.ceil(round(lead_size * OUTLINE_FRAC, 9))
    outline_sub = math.ceil(round(latin_size * OUTLINE_FRAC, 9))
    dialogues = []
    for cue in cues:
        want_deva = _has_deva(cue["text"]) or lang in DEVA_LANGS
        family = pick(want_deva)
        has_latin = cue["latin"] is not None
        lead_y = mid
        latin_y = None
        if has_latin:
            latin_y = lead_y + lead_size / 2 + gap + latin_size / 2
            bottom = latin_y + latin_size / 2
        else:
            bottom = lead_y + lead_size / 2
        shift = bottom - band_bot
        if shift > 0:
            lead_y -= shift
            if latin_y is not None:
                latin_y -= shift
            entries.append(_entry("WARN", "caption pair shifted up to stay inside the caption band"))
        if lead_y - lead_size / 2 < band_top:
            entries.append(_entry("WARN", "caption is taller than the caption band"))
        if wrap_estimate(cue["text"], lead_size) > text_w:
            entries.append(_entry("WARN", f"cue {cue['index']}: text too long for one line at "
                                          f"{lead_size} px; ASS wraps it"))
        if has_latin and wrap_estimate(cue["latin"], latin_size) > text_w:
            entries.append(_entry("WARN", f"cue {cue['index']}: latin line too long for one line; "
                                          "ASS wraps it"))
        t0s, t1s = ass_time(cue["t0"]), ass_time(cue["end"])
        override = f"\\fn{family}" if family != lead_family else ""
        lead_tags = f"\\an5\\pos({x},{round(lead_y)}){override}"
        dialogues.append(f"Dialogue: 0,{t0s},{t1s},Lead,,0,0,0,,{{{lead_tags}}}{_escape(cue['text'])}")
        if has_latin:
            latin_tags = f"\\an5\\pos({x},{round(latin_y)})\\alpha&H{alpha:02X}&"
            dialogues.append(f"Dialogue: 0,{t0s},{t1s},Sub,,0,0,0,,{{{latin_tags}}}"
                             f"{_escape(cue['latin'])}")

    ratio = contrast_ratio(FILL_HEX, OUTLINE_HEX)
    if ratio < min_contrast:
        entries.append(_entry("WARN", f"caption fill vs outline contrast {ratio:.2f} is below "
                                      f"{min_contrast:g}"))
    delta = abs(l_star(FILL_HEX) - l_star(OUTLINE_HEX))
    if delta < MIN_OUTLINE_DELTA_L:
        entries.append(_entry("WARN", f"caption outline vs fill DeltaL* {delta:.1f} is below "
                                      f"{MIN_OUTLINE_DELTA_L:g}"))

    return _document(W, H, margin,
                     (lead_family, lead_size, outline_lead),
                     (sub_family, latin_size, outline_sub),
                     dialogues)


def _dedupe(entries):
    seen, out = set(), []
    for e in entries:
        key = (e["level"], e["message"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def build_ass(cues, pack, core, width, height, language="hi"):
    """Return (ass_text, entries). Never raises; junk input gives a FAIL entry and a minimal ASS."""
    entries = []
    try:
        text = _build(cues, pack, core, width, height, language, entries)
        return text, _dedupe(entries)
    except _Junk as exc:
        return _minimal(width, height), [_entry("FAIL", f"captions not built: {exc}")]
    except Exception as exc:  # safety net: junk input must never raise
        return _minimal(width, height), [
            _entry("FAIL", f"captions not built: {type(exc).__name__}: {exc}")]
