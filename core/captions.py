"""ASS caption builder (WP8 part 2). Standard library plus style_pack helpers.

Builds the .ass text only. Never runs ffmpeg, never reads font files, never raises on junk input.
Output is deterministic: the same input gives byte-identical text.
"""
import math
import re

from pathlib import Path

from core import caption_text as _ct
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
EMPHASIS_HEX = "#FFD84D"     # hook-word emphasis and the sung part of a karaoke line (9.4, 9.7); tune value
EMPHASIS_SCALE = 112         # percent size of an emphasised word
MAX_LINES = 2                # measured wrapping limit (research: max 2 lines)
_EM_OPEN, _EM_CLOSE = "\ue000", "\ue001"   # private-use markers around an emphasised word, replaced by ASS tags
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
        emph = cue.get("emphasis")
        emph = [w.strip() for w in emph if isinstance(w, str) and w.strip()] if isinstance(emph, list) else []
        words = cue.get("words") if isinstance(cue.get("words"), list) and cue.get("words") else None
        valid.append({"index": idx, "t0": float(t0), "t1": float(t1),
                      "text": text.strip(), "latin": latin, "emphasis": emph, "words": words})
    valid.sort(key=lambda c: (c["t0"], c["t1"], c["index"]))
    return valid


def _cards(cues, max_words):
    """Splits cues of more than max_words words (and without aligned words) into balanced cards, times shared by word count."""
    if not (isinstance(max_words, int) and not isinstance(max_words, bool) and max_words > 0):
        return cues
    out = []
    for c in cues:
        words = c["text"].split()
        if c["words"] or len(words) <= max_words:
            out.append(c)
            continue
        n = math.ceil(len(words) / max_words)
        size = math.ceil(len(words) / n)
        done = 0
        for k, i in enumerate(range(0, len(words), size)):
            chunk = words[i:i + size]
            s = c["t0"] + (c["t1"] - c["t0"]) * done / len(words)
            done += len(chunk)
            e = c["t0"] + (c["t1"] - c["t0"]) * done / len(words)
            out.append(dict(c, t0=s, t1=e, text=" ".join(chunk), latin=c["latin"] if k == 0 else None))
    return out


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _find_font(font_dir, family):
    """Font file in font_dir whose normalised name starts with the family name (the way rule P10 matches); the shortest
    file name wins, which is the regular or variable file. None when there is no font_dir, no family or no match."""
    if not font_dir or not family:
        return None
    try:
        files = [f for f in Path(font_dir).iterdir() if f.is_file() and f.suffix.lower() in (".ttf", ".otf")]
    except OSError:
        return None
    want = re.sub(r"\s+", "", family.lower())
    hits = [f for f in files if re.sub(r"[\s_\-]", "", f.name.lower()).startswith(want)]
    return str(sorted(hits, key=lambda f: (len(f.name), f.name))[0]) if hits else None


_PUNCT = ".,!?;:'\"()\u2026\u0964"


def _mark_emphasis(line, words):
    """Wraps each token of `line` that equals an emphasis word (punctuation ignored, case-insensitive) in private markers."""
    if not words:
        return line
    wanted = {w.strip(_PUNCT).lower() for w in words}
    return " ".join(_EM_OPEN + t + _EM_CLOSE if t.strip(_PUNCT) and t.strip(_PUNCT).lower() in wanted else t
                    for t in line.split(" "))


def _emphasis_tags(text):
    on = "{\\1c" + _ass_colour(EMPHASIS_HEX) + "&\\fscx%d\\fscy%d}" % (EMPHASIS_SCALE, EMPHASIS_SCALE)
    off = "{\\1c" + _ass_colour(FILL_HEX) + "&\\fscx100\\fscy100}"
    return text.replace(_EM_OPEN, on).replace(_EM_CLOSE, off)


def _line_markup(line, dev, lat):
    """One caption line as ASS text. A line that mixes Devanagari and Latin gets explicit font overrides per script run (9.8)."""
    scripts = [sc for sc, _ in _ct.script_runs(line) if sc != "other"]
    if dev and lat and "deva" in scripts and "latin" in scripts:
        primary = dev if scripts[0] == "deva" else lat
        return "{\\fn%s}%s" % (primary, _ct.fallback_markup(line, dev, lat))
    return _escape(line)


def _karaoke_body(cue, font_file, size, text_w, entries):
    """ASS karaoke text for a cue that carries aligned words, or None when the timing falls back to phrase mode (9.7)."""
    from core import caption_export as cx   # lazy: caption_export imports this module
    ass, mode, kents = cx.karaoke_text(cue["words"], line_t0=cue["t0"], line_t1=cue["end"])
    if mode == "synthetic" and all(isinstance(w, str) for w in cue["words"]):
        kents = [e for e in kents if "synthetic equal split" not in e["message"]]   # asked for with karaoke=True
    entries.extend(kents)
    if mode == "phrase":
        return None
    texts = [w.get("text", "") if isinstance(w, dict) else str(w) for w in cue["words"]]
    if font_file:
        lines, wents = _ct.wrap_lines(" ".join(texts), font_file, size, text_w, MAX_LINES)
        entries.extend(wents)
        pieces = re.findall(r"\{\\k\d+\}[^{]*", ass)
        if len(pieces) == len(texts) and sum(len(ln.split(" ")) for ln in lines) == len(texts):
            out, i = [], 0
            for ln in lines:
                n = len(ln.split(" "))
                out.append("".join(pieces[i:i + n]).rstrip())
                i += n
            return "\\N".join(out)
    return ass


def _build(cues, pack, core, width, height, language, entries, font_dir=None, template=None, face_boxes=(),
           karaoke=False, require_fonts=False):
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
    if template is not None:   # per-platform safe area (9.2): replaces the caption band and the right margin only
        tpl = core.get("safe_zone_templates", {}).get(template) if isinstance(core.get("safe_zone_templates"), dict) else None
        try:
            band, right = _validate_core(dict(core, safe_zone_frac=tpl))[:2]
        except _Junk:
            entries.append(_entry("WARN", f"safe-zone template {template!r} is missing or invalid; using the default safe zone"))

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
    latin_raised = None
    if latin_size < min_latin:
        latin_size = min_latin
        latin_raised = f"latin line raised to the minimum size ({min_latin} px)"
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
    cap_cfg = core.get("captions") if isinstance(core.get("captions"), dict) else {}
    cues = _cards(cues, cap_cfg.get("max_words"))
    sz_top = core["safe_zone_frac"].get("top")
    top_forbidden = sz_top * H if _is_num(sz_top) else None
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

    dev_family, lat_family = _family(typo.get("subtitle_devanagari")), _family(typo.get("subtitle_latin"))
    min_size = math.ceil(min_px * W / REF_WIDTH)
    outline_lead = math.ceil(round(lead_size * OUTLINE_FRAC, 9))
    outline_sub = math.ceil(round(latin_size * OUTLINE_FRAC, 9))
    dialogues = []
    missing_fonts = set()
    face_step = max(1, round(H * 40 / 2560))
    for cue in cues:
        want_deva = _has_deva(cue["text"]) or lang in DEVA_LANGS
        family = pick(want_deva)
        has_latin = cue["latin"] is not None
        if has_latin and latin_raised:   # only a caption that has a latin line cares about the latin size
            entries.append(_entry("WARN", latin_raised))
            latin_raised = None
        lead_file = _find_font(font_dir, family)
        if require_fonts and not lead_file and family not in missing_fonts:
            missing_fonts.add(family)
            entries.append({"rule": "CAP-FONT", "level": "FAIL", "shot": None, "episode": None,
                            "message": f"font file for family {family!r} not found in {font_dir}; this code never downloads fonts"})
        words = cue["words"] if cue["words"] else (cue["text"].split() if karaoke else None)
        kcue = dict(cue, words=words) if words else cue
        size_tag, k_tags, body = "", "", None
        if words:
            body = _karaoke_body(kcue, lead_file, lead_size, text_w, entries)
            if body is not None:
                k_tags = "\\1c" + _ass_colour(EMPHASIS_HEX) + "&\\2c" + _ass_colour(FILL_HEX) + "&"
        if body is None:
            if lead_file:   # measured wrapping with the real font file: explicit line breaks, at most MAX_LINES lines
                lines, size_used, wents = _ct.fit_text(cue["text"], lead_file, lead_size, text_w, MAX_LINES,
                                                       min_size_px=min_size)
                entries.extend(wents)
                if size_used != lead_size:
                    size_tag = "\\fs%d" % size_used
                gl = _ct.glyph_coverage(lead_file, cue["text"])
                if not gl["ok"]:
                    entries.append({"rule": "CAP-GLYPH", "level": "FAIL", "shot": None, "episode": None,
                                    "message": f"cue {cue['index']}: glyph(s) {''.join(gl['missing'])!r} missing from "
                                               f"{Path(lead_file).name}"})
            else:
                lines = [cue["text"]]
                if wrap_estimate(cue["text"], lead_size) > text_w:
                    entries.append(_entry("WARN", f"cue {cue['index']}: text too long for one line at "
                                                  f"{lead_size} px; ASS wraps it"))
            body = "\\N".join(_emphasis_tags(_line_markup(_mark_emphasis(ln, cue["emphasis"]), dev_family, lat_family))
                              for ln in lines)
        nlines = body.count("\\N") + 1
        block_h = nlines * lead_size                      # one line: exactly the old single-line numbers
        lead_y = mid
        latin_y = None
        bottom = lead_y + block_h / 2
        if has_latin:
            latin_y = bottom + gap + latin_size / 2
            bottom = latin_y + latin_size / 2
        shift = bottom - band_bot
        if shift > 0:
            lead_y -= shift
            if latin_y is not None:
                latin_y -= shift
            entries.append(_entry("WARN", "caption pair shifted up to stay inside the caption band"))
        top = lead_y - block_h / 2
        bottom = (latin_y + latin_size / 2) if latin_y is not None else lead_y + block_h / 2
        if face_boxes and any(_overlaps((margin, top, W - margin, bottom), f) for f in face_boxes):
            lo = top_forbidden if top_forbidden is not None else band_top
            ny, nl = lead_y, latin_y
            while any(_overlaps((margin, ny - block_h / 2, W - margin,
                                 (nl + latin_size / 2) if nl is not None else ny + block_h / 2), f) for f in face_boxes):
                ny -= face_step
                nl = nl - face_step if nl is not None else None
                if ny - block_h / 2 < lo:
                    entries.append(_entry("WARN", f"caption at {cue['t0']:.2f}s covers a face and has no clear spot; kept in place"))
                    break
            else:
                lead_y, latin_y = ny, nl
                top = lead_y - block_h / 2
        if top_forbidden is not None and top < top_forbidden - 1e-6:
            entries.append({"rule": "CAP-GEOMETRY", "level": "FAIL", "shot": None, "episode": None,
                            "message": f"cue {cue['index']}: caption top y={top:.0f} is inside the forbidden top zone "
                                       f"(y < {top_forbidden:.0f})"})
        elif top < band_top:
            entries.append(_entry("WARN", "caption is taller than the caption band"))
        if has_latin and wrap_estimate(cue["latin"], latin_size) > text_w:
            entries.append(_entry("WARN", f"cue {cue['index']}: latin line too long for one line; "
                                          "ASS wraps it"))
        t0s, t1s = ass_time(cue["t0"]), ass_time(cue["end"])
        override = f"\\fn{family}" if family != lead_family else ""
        lead_tags = f"\\an5\\pos({x},{round(lead_y)}){override}{size_tag}{k_tags}"
        dialogues.append(f"Dialogue: 0,{t0s},{t1s},Lead,,0,0,0,,{{{lead_tags}}}{body}")
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


def build_ass(cues, pack, core, width, height, language="hi", font_dir=None, template=None, face_boxes=(),
              karaoke=False, require_fonts=False):
    """Return (ass_text, entries). Never raises; junk input gives a FAIL entry and a minimal ASS.
    font_dir: folder with the font files; when given, text is wrapped by measuring the real font (at most 2 lines, explicit
    line breaks, shrink down to the minimum size) and every glyph is checked. template: key of core.safe_zone_templates
    (reels, shorts, youtube) replacing the caption band and the right margin.
    A cue may carry `emphasis` (list of words drawn larger in the emphasis colour) and `words` (aligned words for karaoke;
    low confidence or bad timing falls back to the plain line).
    Cues longer than core.captions.max_words words are split into balanced cards (times shared by word count).
    face_boxes: (x0, y0, x1, y1) in render pixels; a caption that would cover one is raised until it clears it (down to
    the forbidden top zone) or kept with a WARN. karaoke=True: cues without aligned words get an equal split per word
    (the Gate D look). require_fonts=True: a family whose font file is not in font_dir is a FAIL (Gate D); a caption box
    that reaches into the forbidden top zone (core.safe_zone_frac.top) is a FAIL entry, CAP-GEOMETRY."""
    entries = []
    try:
        text = _build(cues, pack, core, width, height, language, entries, font_dir, template, face_boxes, karaoke,
                      require_fonts)
        return text, _dedupe(entries)
    except _Junk as exc:
        return _minimal(width, height), [_entry("FAIL", f"captions not built: {exc}")]
    except Exception as exc:  # safety net: junk input must never raise
        return _minimal(width, height), [
            _entry("FAIL", f"captions not built: {type(exc).__name__}: {exc}")]
