"""Caption export helpers (B9b): SRT/WebVTT sidecars, karaoke timing, ElevenLabs alignment parsing,
contact-sheet plan, frame hashing and ffmpeg preflight.

Standard library + Pillow. Never raises on junk input (returns entries instead).
Never calls a network, a model, ElevenLabs or ffmpeg render. The only subprocess is the
`ffmpeg -buildconf` query in ffmpeg_preflight. contact_sheet_plan only returns argv lists.
"""
import hashlib
import math
import os
import re
import statistics                       # ponytail: stdlib median, no numpy
import subprocess

from PIL import Image

from core.captions import _escape       # reuse the ASS escaper from captions.py

LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]+)?$")
CARD_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
STEM_BAD = ("/", "\\")
ASS_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")  # filter-safe basename (no ':' ',' quotes)
RULE = "CAP-EXPORT"


def _entry(rule, level, message):
    return {"rule": rule, "level": level, "shot": None, "episode": None, "message": message}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _ms(sec):
    """Milliseconds, rounded half up. Negative or junk -> 0."""
    if not _num(sec) or sec < 0:
        return 0
    return int(math.floor(sec * 1000 + 0.5))


def srt_time(sec):
    ms = _ms(sec)
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_time(sec):
    return srt_time(sec).replace(",", ".")


# ---- SRT / WebVTT -------------------------------------------------------

def _clean_cues(cues, entries):
    """Valid cues sorted by t0, each as (t0, t1, body_lines). One WARN per skipped cue."""
    if not isinstance(cues, list):
        entries.append(_entry(RULE, "WARN", "cues is not a list; treated as empty"))
        return []
    valid = []
    for idx, cue in enumerate(cues):
        if not isinstance(cue, dict):
            entries.append(_entry(RULE, "WARN", f"cue {idx} skipped: not an object"))
            continue
        t0, t1, text = cue.get("t0"), cue.get("t1"), cue.get("text")
        if not (_num(t0) and _num(t1)):
            entries.append(_entry(RULE, "WARN", f"cue {idx} skipped: t0 and t1 must be finite numbers"))
            continue
        if t1 <= t0:
            entries.append(_entry(RULE, "WARN", f"cue {idx} skipped: needs t1 > t0"))
            continue
        if not isinstance(text, str) or not text.strip():
            entries.append(_entry(RULE, "WARN", f"cue {idx} skipped: empty text"))
            continue
        lines = [ln.strip() for ln in text.replace("\r", "\n").split("\n") if ln.strip()]
        latin = cue.get("latin")
        if latin is not None and not isinstance(latin, str):
            entries.append(_entry(RULE, "WARN", f"cue {idx}: latin line ignored (not a string)"))
        elif isinstance(latin, str) and latin.strip():
            lines += [ln.strip() for ln in latin.replace("\r", "\n").split("\n") if ln.strip()]
        valid.append((float(t0), float(t1), lines))
    valid.sort(key=lambda c: (c[0], c[1]))
    return valid


def to_srt(cues):
    entries = []
    blocks = []
    for n, (t0, t1, lines) in enumerate(_clean_cues(cues, entries), start=1):
        blocks.append(f"{n}\n{srt_time(t0)} --> {srt_time(t1)}\n" + "\n".join(lines) + "\n\n")
    return "".join(blocks), entries


def to_vtt(cues):
    entries = []
    out = ["WEBVTT\n\n"]
    for t0, t1, lines in _clean_cues(cues, entries):
        body = "\n".join(lines).replace("&", "&amp;").replace("<", "&lt;")
        out.append(f"{vtt_time(t0)} --> {vtt_time(t1)}\n{body}\n\n")
    return "".join(out), entries


def write_sidecars(cues_by_lang, out_dir, stem):
    entries = []
    if not isinstance(cues_by_lang, dict):
        return [], [_entry(RULE, "FAIL", "cues_by_lang must be a dict")]
    if not isinstance(stem, str) or not stem or any(c in stem for c in STEM_BAD):
        return [], [_entry(RULE, "FAIL", f"bad sidecar stem {stem!r}")]
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        return [], [_entry(RULE, "FAIL", f"cannot create {out_dir}: {exc}")]
    paths = []
    for lang, cues in cues_by_lang.items():
        if not isinstance(lang, str) or not LANG_RE.match(lang):
            entries.append(_entry(RULE, "WARN", f"language key {lang!r} is invalid; skipped"))
            continue
        srt, e1 = to_srt(cues)
        vtt, e2 = to_vtt(cues)
        entries += e1 + e2
        for ext, body in (("srt", srt), ("vtt", vtt)):
            path = os.path.join(out_dir, f"{stem}.{lang}.{ext}")
            try:
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(body)
            except OSError as exc:
                entries.append(_entry(RULE, "FAIL", f"cannot write {path}: {exc}"))
                continue
            paths.append(path)
    return sorted(paths), entries


# ---- ElevenLabs alignment -----------------------------------------------

_KEYS = ("characters", "character_start_times_seconds", "character_end_times_seconds")


def words_from_elevenlabs(alignment_doc):
    """Group characters into words on whitespace. The API gives no confidence, so conf = 1.0."""
    fail = lambda msg: ([], [_entry("CAP-ALIGN", "FAIL", msg)])  # noqa: E731
    doc = alignment_doc
    if isinstance(doc, dict) and "characters" not in doc:
        for key in ("alignment", "normalized_alignment"):
            if isinstance(doc.get(key), dict):
                doc = doc[key]
                break
    if not isinstance(doc, dict) or any(k not in doc for k in _KEYS):
        return fail("alignment document is missing characters or time lists")
    chars = doc["characters"]
    starts = doc["character_start_times_seconds"]
    ends = doc["character_end_times_seconds"]
    if not (isinstance(chars, list) and isinstance(starts, list) and isinstance(ends, list)):
        return fail("alignment fields must be lists")
    if not (len(chars) == len(starts) == len(ends)):
        return fail(f"alignment list lengths differ: {len(chars)}, {len(starts)}, {len(ends)}")
    if not all(_num(v) for v in starts + ends):
        return fail("alignment times must be finite numbers")
    if not all(isinstance(c, str) for c in chars):
        return fail("alignment characters must be strings")
    words, cur = [], None
    for ch, t0, t1 in zip(chars, starts, ends):
        for c in ch:
            if c.isspace():
                if cur is not None:
                    words.append(cur)
                    cur = None
            else:
                if cur is None:
                    cur = {"text": "", "t0": float(t0), "t1": float(t1), "conf": 1.0}
                cur["text"] += c
                cur["t1"] = float(t1)
    if cur is not None:
        words.append(cur)
    return words, []


# ---- karaoke ------------------------------------------------------------

def _cs_rel(seconds, start):
    return int(math.floor((seconds - start) * 100 + 0.5))


def _timed_body(texts, bounds):
    """bounds: cumulative centisecond boundaries, len(texts)+1 values."""
    parts = []
    for i, text in enumerate(texts):
        parts.append("{\\k%d}%s" % (bounds[i + 1] - bounds[i], _escape(text)))
    return " ".join(parts)


def _first_problem(words, min_conf, min_word_s):
    prev_t1 = None
    for w in words:
        if not isinstance(w, dict):
            return "missing timing"
        t0, t1 = w.get("t0"), w.get("t1")
        if not (_num(t0) and _num(t1)) or t1 <= t0:
            return "missing timing"
        if prev_t1 is not None and t0 < prev_t1 - 0.001:
            return "non-monotonic timing"
        conf = w.get("conf", 1.0)
        if not _num(conf) or conf < min_conf:
            return "low confidence"
        if t1 - t0 < min_word_s:
            return "word shorter than min_word_s"
        prev_t1 = t1
    return None


def karaoke_text(words, min_conf=0.6, min_word_s=0.04, line_t0=None, line_t1=None):
    entries = []
    has_line = _num(line_t0) and _num(line_t1) and line_t1 > line_t0
    if not isinstance(words, list) or not words:
        entries.append(_entry("CAP-ALIGN", "WARN", "karaoke fell back to phrase mode: missing timing"))
        return "", "phrase", entries
    if all(isinstance(w, str) for w in words):
        if not has_line:
            entries.append(_entry("CAP-ALIGN", "WARN", "karaoke fell back to phrase mode: missing timing"))
            return " ".join(_escape(w) for w in words), "phrase", entries
        entries.append(_entry("CAP-ALIGN", "WARN", "karaoke synthetic equal split (no word timing)"))
        dur = line_t1 - line_t0
        bounds = [0] + [round(i * dur * 100 / len(words)) for i in range(1, len(words))]
        bounds.append(round(dur * 100))
        return _timed_body(words, bounds), "synthetic", entries
    reason = _first_problem(words, min_conf, min_word_s)
    texts = [str(w.get("text", "")) for w in words if isinstance(w, dict)]
    if reason is not None:
        entries.append(_entry("CAP-ALIGN", "WARN", f"karaoke fell back to phrase mode: {reason}"))
        return " ".join(_escape(t) for t in texts if t), "phrase", entries
    start = line_t0 if has_line else words[0]["t0"]
    end = line_t1 if has_line else words[-1]["t1"]
    bounds = [0]
    for w in words[1:]:
        bounds.append(max(bounds[-1], _cs_rel(w["t0"], start)))
    bounds.append(max(bounds[-1], _cs_rel(end, start)))
    return _timed_body(texts, bounds), "word", entries


# ---- timing stats -------------------------------------------------------

def timing_error_stats(predicted, truth):
    errors = []
    if isinstance(predicted, list) and isinstance(truth, list):
        for p, t in zip(predicted, truth):
            if isinstance(p, dict) and isinstance(t, dict) and _num(p.get("t0")) and _num(t.get("t0")):
                errors.append(abs(p["t0"] - t["t0"]))
    if not errors:
        return {"n": 0, "median_s": None, "p90_s": None, "max_s": None}
    errors.sort()
    rank = max(1, math.ceil(0.9 * len(errors)))
    return {
        "n": len(errors),
        "median_s": round(statistics.median(errors), 6),
        "p90_s": round(errors[rank - 1], 6),
        "max_s": round(errors[-1], 6),
    }


# ---- contact sheet plan (plan only) -------------------------------------

def contact_sheet_plan(ass_path, cards, width, height, out_dir, fontsdir=None,
                       bg="#202020", ffmpeg="ffmpeg"):
    """Return (plans, entries). Nothing is executed. Each plan: {id, png, argv, cwd}."""
    entries = []
    if not (isinstance(width, int) and isinstance(height, int)
            and not isinstance(width, bool) and width > 0 and height > 0):
        return [], [_entry(RULE, "FAIL", "contact sheet width and height must be positive integers")]
    ass_name = os.path.basename(str(ass_path))
    if not ASS_NAME_RE.match(ass_name):
        return [], [_entry(RULE, "FAIL", f"ass file name {ass_name!r} is not filter-safe")]
    font_name = None
    if fontsdir:
        font_name = os.path.basename(os.path.normpath(str(fontsdir)))
        if not ASS_NAME_RE.match(font_name):
            return [], [_entry(RULE, "FAIL", f"fonts dir name {font_name!r} is not filter-safe")]
    if not isinstance(cards, list):
        return [], [_entry(RULE, "FAIL", "cards must be a list")]
    colour = str(bg)[1:] if str(bg).startswith("#") else str(bg)
    vf = f"subtitles={ass_name}" + (f":fontsdir={font_name}" if font_name else "")
    cwd = os.path.dirname(os.path.abspath(str(ass_path)))
    if fontsdir and os.path.dirname(os.path.abspath(str(fontsdir))) != cwd:
        entries.append(_entry(RULE, "WARN", "fonts dir is not next to the ass file: the relative fontsdir name will not resolve"))
    plans, seen = [], set()
    for idx, card in enumerate(cards):
        if not isinstance(card, dict):
            entries.append(_entry(RULE, "WARN", f"card {idx} skipped: not an object"))
            continue
        cid, t = card.get("id"), card.get("t")
        if not isinstance(cid, str) or not CARD_ID_RE.match(cid):
            entries.append(_entry(RULE, "WARN", f"card {idx} skipped: bad id {cid!r}"))
            continue
        if cid in seen:
            entries.append(_entry(RULE, "WARN", f"card {cid!r} skipped: duplicate id"))
            continue
        if not _num(t) or t < 0:
            entries.append(_entry(RULE, "WARN", f"card {cid!r} skipped: t must be a number >= 0"))
            continue
        seen.add(cid)
        png = os.path.join(os.path.abspath(str(out_dir)), f"{cid}.png")   # absolute: ffmpeg runs with cwd = the ass folder
        argv = [ffmpeg, "-hide_banner", "-y", "-f", "lavfi", "-i",
                f"color=c={colour}:s={width}x{height}:r=24:d={t + 1}",
                "-vf", vf]
        argv += ["-ss", f"{t:.3f}", "-frames:v", "1", png]
        plans.append({"id": cid, "png": png, "argv": argv, "cwd": cwd})
    return plans, entries


# ---- frame hash / QA ----------------------------------------------------

def frame_hash(png_path):
    try:
        with Image.open(png_path) as im:
            rgb = im.convert("RGB")
            h = hashlib.sha256(f"{rgb.width}x{rgb.height}".encode())
            h.update(rgb.tobytes())
            return h.hexdigest()
    except Exception:  # unreadable file or not an image
        return None


def compare_frames(png_path, reference_hash):
    got = frame_hash(png_path)
    if got is None:
        return [_entry("CAP-QA", "FAIL", "caption frame is unreadable")]
    if got == reference_hash:
        return []
    return [_entry("CAP-QA", "FAIL", "caption frame differs from the reference")]


# ---- ffmpeg preflight ---------------------------------------------------

def preflight_from_buildconf(text):
    text = text if isinstance(text, str) else ""
    entries = []
    if "--enable-libass" not in text:
        entries.append(_entry("CAP-PREFLIGHT", "FAIL", "ffmpeg lacks --enable-libass (subtitles filter)"))
    if "--enable-libharfbuzz" not in text:
        entries.append(_entry("CAP-PREFLIGHT", "FAIL", "ffmpeg lacks --enable-libharfbuzz (Devanagari shaping)"))
    if "--enable-libfribidi" not in text:
        entries.append(_entry("CAP-PREFLIGHT", "WARN", "ffmpeg lacks --enable-libfribidi"))
    if "--enable-fontconfig" not in text:
        entries.append(_entry("CAP-PREFLIGHT", "WARN", "ffmpeg lacks --enable-fontconfig"))
    return entries


def ffmpeg_preflight(ffmpeg="ffmpeg", timeout=20):
    try:
        proc = subprocess.run([ffmpeg, "-hide_banner", "-buildconf"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return [_entry("CAP-PREFLIGHT", "FAIL", f"ffmpeg -buildconf timed out after {timeout} s")]
    except (OSError, ValueError) as exc:
        return [_entry("CAP-PREFLIGHT", "FAIL", f"ffmpeg not runnable: {exc}")]
    if proc.returncode != 0:
        return [_entry("CAP-PREFLIGHT", "FAIL", f"ffmpeg -buildconf exited {proc.returncode}")]
    return preflight_from_buildconf((proc.stdout or "") + (proc.stderr or ""))
