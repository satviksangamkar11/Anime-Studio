"""Caption text helpers: grapheme clusters, script runs, glyph coverage, measured wrapping.

Widths come from PIL ImageFont.getlength. Pillow may lack libraqm/harfbuzz (see
shaping_engine()); then widths are "basic layout" (no GSUB/GPOS shaping), an
approximation that can differ from the real rendered width of Devanagari clusters.

Nothing here raises on junk input: functions return a neutral value or an entry list.
"""
import struct
import unicodedata
from pathlib import Path

from PIL import ImageFont, features

CORPUS = ["माझं", "कुठे", "ॲप", "र्क", "क्ष", "ज्ञ", "ळ", "ऱ"]

_VIRAMAS = {0x094D, 0x09CD, 0x0A4D, 0x0ACD, 0x0B4D, 0x0BCD, 0x0C4D, 0x0CCD, 0x0D4D}
_ZWJ = "‍"
_ZWNJ = "‌"
_IGNORED = {" ", "\n", "\r", "\t", _ZWJ, _ZWNJ}
_MARK_CATS = {"Mn", "Mc", "Me"}
_NEEDS = "needs "
_WORD_WIDE = "word wider than the line, split between clusters"

# ponytail: unbounded cache, fine for a handful of fonts x sizes per run.
_FONT_CACHE = {}


def _entry(rule, level, message):
    return {"rule": rule, "level": level, "shot": None, "episode": None, "message": message}


def _extends(ch):
    cp = ord(ch)
    if unicodedata.category(ch) in _MARK_CATS:
        return True
    if ch in (_ZWJ, _ZWNJ):
        return True
    return 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF


def _joins(prev, ch):
    if _extends(ch) or prev == _ZWJ:
        return True
    if ord(prev) in _VIRAMAS and unicodedata.category(ch).startswith("L"):
        return True
    return prev == "\r" and ch == "\n"


def clusters(text):
    """Grapheme-like clusters using unicodedata only. Joined output equals the input."""
    if not isinstance(text, str):
        return []
    out = []
    cur = ""
    prev = ""
    for ch in text:
        if cur and _joins(prev, ch):
            cur += ch
        else:
            if cur:
                out.append(cur)
            cur = ch
        prev = ch
    if cur:
        out.append(cur)
    return out


def script_of(ch):
    """'deva', 'latin' or 'other' for one character."""
    if not isinstance(ch, str) or len(ch) != 1:
        return "other"
    cp = ord(ch)
    if 0x0900 <= cp <= 0x097F or 0xA8E0 <= cp <= 0xA8FF:
        return "deva"
    if ch.isalpha() and unicodedata.name(ch, "").startswith("LATIN"):
        return "latin"
    return "other"


def _cluster_script(cluster):
    for ch in cluster:
        s = script_of(ch)
        if s != "other":
            return s
    return "other"


def script_runs(text):
    """[(script, substring)]. 'other' clusters join the previous run (the next run at the start)."""
    if not isinstance(text, str):
        return []
    runs = []
    pending = ""
    for c in clusters(text):
        s = _cluster_script(c)
        if s == "other":
            if runs:
                runs[-1][1] += c
            else:
                pending += c
            continue
        if runs and runs[-1][0] == s:
            runs[-1][1] += c
        else:
            runs.append([s, pending + c])
            pending = ""
    if pending:
        runs.append(["other", pending])
    return [(s, sub) for s, sub in runs]


# ---------- cmap ----------

def _parse_subtable(data, off):
    fmt = struct.unpack_from(">H", data, off)[0]
    out = set()
    if fmt == 4:
        seg2 = struct.unpack_from(">H", data, off + 6)[0]
        segs = seg2 // 2
        ends_off = off + 14
        starts_off = ends_off + seg2 + 2
        deltas_off = starts_off + seg2
        ranges_off = deltas_off + seg2
        ends = struct.unpack_from(f">{segs}H", data, ends_off)
        starts = struct.unpack_from(f">{segs}H", data, starts_off)
        deltas = struct.unpack_from(f">{segs}h", data, deltas_off)
        ranges = struct.unpack_from(f">{segs}H", data, ranges_off)
        for i in range(segs):
            s, e, d, r = starts[i], ends[i], deltas[i], ranges[i]
            for c in range(s, e + 1):
                if c == 0xFFFF:
                    continue
                if r == 0:
                    g = (c + d) & 0xFFFF
                else:
                    addr = ranges_off + 2 * i + r + 2 * (c - s)
                    g = struct.unpack_from(">H", data, addr)[0]
                    if g:
                        g = (g + d) & 0xFFFF
                if g:
                    out.add(c)
        return out
    if fmt == 12:
        n = struct.unpack_from(">I", data, off + 12)[0]
        for g in range(n):
            s, e, _ = struct.unpack_from(">III", data, off + 16 + 12 * g)
            out.update(range(s, min(e, 0x10FFFF) + 1))
        return out
    return set()


def _parse_cmap(data):
    if data[:4] == b"ttcf":
        return set()
    num_tables = struct.unpack_from(">H", data, 4)[0]
    cmap_off = None
    for i in range(num_tables):
        tag, _, off, _ = struct.unpack_from(">4sIII", data, 12 + 16 * i)
        if tag == b"cmap":
            cmap_off = off
            break
    if cmap_off is None:
        return set()
    n = struct.unpack_from(">H", data, cmap_off + 2)[0]
    subs = []
    for i in range(n):
        pid, eid, off = struct.unpack_from(">HHI", data, cmap_off + 4 + 8 * i)
        subs.append((pid, eid, cmap_off + off))
    order = ([s for s in subs if s[:2] == (3, 10)]
             + [s for s in subs if s[:2] == (3, 1)]
             + [s for s in subs if s[0] == 0])
    for _, _, off in order:
        try:
            found = _parse_subtable(data, off)
        except Exception:
            found = set()
        if found:
            return found
    return set()


def read_cmap(font_path):
    """Set of codepoints in the font's cmap (formats 4 and 12). Empty set on any problem."""
    try:
        return _parse_cmap(Path(font_path).read_bytes())
    except Exception:
        return set()


def _missing(cmap, text):
    return sorted({ch for ch in text if ch not in _IGNORED and ord(ch) not in cmap})


def glyph_coverage(font_path, text):
    """{"ok": bool, "missing": sorted chars not in the font's cmap} (space/newline/ZWJ/ZWNJ ignored)."""
    if not isinstance(text, str):
        text = ""
    missing = _missing(read_cmap(font_path), text)
    return {"ok": not missing, "missing": missing}


def check_font_coverage(font_path, corpus=CORPUS):
    """One CAP-GLYPH FAIL entry per corpus char the font lacks; empty list when covered."""
    name = Path(str(font_path)).name
    cmap = read_cmap(font_path)
    if not cmap:
        return [_entry("CAP-GLYPH", "FAIL", f"cannot read cmap of font {name}")]
    if not isinstance(corpus, (list, tuple)):
        corpus = []
    text = " ".join(str(x) for x in corpus)
    return [_entry("CAP-GLYPH", "FAIL", f"glyph {ch!r} (U+{ord(ch):04X}) missing from {name}")
            for ch in _missing(cmap, text)]


# ---------- measuring and wrapping ----------

def shaping_engine():
    try:
        return "raqm" if features.check("raqm") else "basic"
    except Exception:
        return "basic"


def _font(font_path, size_px):
    key = (str(font_path), size_px)
    if key not in _FONT_CACHE:
        try:
            _FONT_CACHE[key] = ImageFont.truetype(str(font_path), size_px)
        except Exception:
            _FONT_CACHE[key] = None
    return _FONT_CACHE[key]


def measure(font_path, size_px, text):
    """Pixel width of text. Falls back to len*0.6*size only when the font cannot load."""
    if not isinstance(text, str) or not text:
        return 0.0
    font = _font(font_path, size_px)
    try:
        if font is None:
            return len(text) * 0.6 * size_px
        return float(font.getlength(text))
    except Exception:
        return 0.0


def _limit(max_lines):
    try:
        return int(max_lines)
    except Exception:
        return 2


def _break_word(word, width, max_w):
    pieces = []
    cur = ""
    for c in clusters(word):
        cand = cur + c
        if cur and width(cand) > max_w:
            pieces.append(cur)
            cur = c
        else:
            cur = cand
    if cur:
        pieces.append(cur)
    return pieces


def _wrap_para(para, width, max_w, entries):
    words = [w for w in para.split(" ") if w]
    if not words:
        return [""]
    lines = []
    cur = ""
    for w in words:
        cand = w if not cur else cur + " " + w
        if width(cand) <= max_w:
            cur = cand
            continue
        if cur:
            lines.append(cur)
            cur = ""
        if width(w) <= max_w:
            cur = w
            continue
        pieces = _break_word(w, width, max_w)
        entries.append(_entry("CAP-WRAP", "WARN", _WORD_WIDE))
        lines.extend(pieces[:-1])
        cur = pieces[-1]
    lines.append(cur)
    return lines


def wrap_lines(text, font_path, size_px, max_width_px, max_lines=2):
    """Greedy wrap by measured width. Never splits inside a cluster. Returns (lines, entries)."""
    entries = []
    if not isinstance(text, str) or text == "":
        return [], entries
    try:
        max_w = float(max_width_px)
    except Exception:
        max_w = 0.0
    if not max_w > 0:
        return [], [_entry("CAP-WRAP", "FAIL", "invalid max width")]
    if _font(font_path, size_px) is None:
        entries.append(_entry("CAP-WRAP", "WARN", "font could not load, widths estimated"))

    def width(s):
        return measure(font_path, size_px, s)

    lines = []
    for para in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        lines.extend(_wrap_para(para, width, max_w, entries))
    limit = _limit(max_lines)
    if len(lines) > limit:
        entries.append(_entry("CAP-WRAP", "WARN", f"needs {len(lines)} lines, limit {limit}"))
    return lines, entries


def fit_text(text, font_path, size_px, max_width_px, max_lines=2, min_size_px=None):
    """Shrink in 2 px steps (ending at min_size_px) until wrap_lines fits max_lines.

    Returns (lines, size_used, entries). If nothing fits, returns the smallest-size result
    plus a CAP-WRAP FAIL entry.
    """
    if not isinstance(text, str) or text == "":
        return [], size_px, []
    try:
        floor = size_px if min_size_px is None else min_size_px
        sizes = [size_px]
        s = size_px
        while s - 2 >= floor:
            s -= 2
            sizes.append(s)
        if floor < size_px and sizes[-1] != floor:
            sizes.append(floor)
        limit = _limit(max_lines)
        lines, size, entries = [], size_px, []
        for size in sizes:
            lines, entries = wrap_lines(text, font_path, size, max_width_px, limit)
            if len(lines) <= limit:
                return lines, size, entries
        kept = [e for e in entries if not e["message"].startswith(_NEEDS)]
        kept.append(_entry("CAP-WRAP", "FAIL",
                           f"does not fit in {limit} lines at the minimum size"))
        return lines, size, kept
    except Exception:
        return [], size_px, [_entry("CAP-WRAP", "FAIL", "invalid fit parameters")]


def ass_lines(lines):
    """Join with the ASS line break (backslash + capital N)."""
    if not isinstance(lines, (list, tuple)):
        return ""
    return "\\N".join(str(x) for x in lines)


# ---------- mixed-script font fallback ----------

def _esc(text):
    # same rules as core.captions._escape
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\\", "")
    s = s.replace("{", "(").replace("}", ")")
    return s.replace("\n", "\\N")


def _fallback_build(text, deva_family, latin_family):
    if not isinstance(text, str) or text == "":
        return "", []
    runs = script_runs(text)
    if not runs:
        return "", []
    fams = {"deva": deva_family, "latin": latin_family}
    primary = runs[0][0]
    if primary == "other":
        return _esc(text), []
    primary_fam = fams[primary]
    missing = []
    parts = []
    for script, sub in runs:
        if script == "other" or script == primary:
            parts.append(_esc(sub))
            continue
        fam = fams[script]
        if not fam:
            if script not in missing:
                missing.append(script)
            parts.append(_esc(sub))
            continue
        close = "{\\fn" + _esc(str(primary_fam)) + "}" if primary_fam else "{\\fn}"
        parts.append("{\\fn" + _esc(str(fam)) + "}" + _esc(sub) + close)
    entries = []
    if missing:
        entries.append(_entry("CAP-TEXT", "WARN",
                              f"no font family for {', '.join(missing)}; "
                              "mixed-script run kept in the line font"))
    return "".join(parts), entries


def fallback_markup(text, deva_family, latin_family):
    """Text with ASS \\fn overrides on the other-script runs. Single-script text has no tags."""
    return _fallback_build(text, deva_family, latin_family)[0]


def fallback_markup_entries(text, deva_family, latin_family):
    """WARN CAP-TEXT when a needed script family is None/empty (no override emitted)."""
    return _fallback_build(text, deva_family, latin_family)[1]
