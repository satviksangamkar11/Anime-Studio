"""Simple-language validator for Hindi, Marathi and English (owner rule: everyday spoken language, not literary words).

Tier 1: whitelist of sacred / Puranic nouns and names (data/simple_language_sacred.json). Never flagged.
        English also whitelists Latin-transliterated names (data/simple_language_en.json).
Tier 2: stiff literary words with a simple replacement (data/simple_language_{hi,mr,en}.json, key stiff_words),
        and words of the other language leaking into hi/mr text (key leaks).
English: SEN-01 sentence over 18 words, SCRIPT-01 Devanagari in an en text.
Hindi/Marathi: SCRIPT-02 Latin-only text (names allowed).
detect_marathi() tells Marathi from Hindi (letter U+0933 and Marathi postpositions vs Hindi markers).
check_shot_texts() walks V4 shot rows: narration, dialogue, captions, and the per-language blocks
narration_by_lang / dialogue_by_lang / captions_by_lang (each key gets the tier of that language).
Word lists are starter lists; the owner extends them. Offline only: no network, no model call.

CLI: python director/simple_language.py <shots.json> [--lang hi|mr|en]
Exit: 0 clean, 1 flags found, 2 input or data-file error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:  # lets `import asr_transcribe` work when run as a script or from pytest
    sys.path.insert(0, str(_HERE))
from asr_transcribe import DEV_WORD, HI_MARK, MR_MARK  # reused: same Devanagari word regex and whisper marker sets

DATA_DIR = _HERE / "data"
SACRED_FILE = "simple_language_sacred.json"
LANGS = ("hi", "mr", "en")
CAPTION_MAX_WORDS = 6
EN_MAX_SENTENCE_WORDS = 18
MIN_POINTS = 2          # marker points needed before a language is named
RATIO = 2               # winner must have at least this many times the other side's points
LETTER_LLA = "ळ"   # ळ, Marathi-only letter
_DEV = "ऀ-ॣ०-ॿ"
_NOT_DEV_BEFORE = "(?<![" + _DEV + "])"
_NOT_DEV_AFTER = "(?![" + _DEV + "])"
_SEP = re.compile(r"[\s।॥.,;:!?\"'“”‘’()\[\]{}\-–—/|…]+")
_EN_TOKEN = re.compile(r"[A-Za-z]+")
_EN_COUNT = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")
_LANG_ALIASES = {"hi": "hi", "hindi": "hi", "mr": "mr", "marathi": "mr", "en": "en", "english": "en"}

# Detection markers (token-level). MR_MARK / HI_MARK come from asr_transcribe.
MR_ONLY = {"ला", "ने", "चा", "ची", "चे", "मध्ये", "साठी", "पासून", "होते", "होती", "होता", "आहेत", "आहोत", "मला", "माझ्या"}
HI_ONLY = {"है", "हैं", "नहीं", "में", "से", "को", "थे", "थी", "था"}
HI_WEAK = {"का", "की", "के"}  # Hindi possessives, but also Marathi words (का = why, की = or/that): half point


class SimpleLanguageDataError(Exception):
    """A word-list file is missing, unreadable, not JSON, or has the wrong shape."""


@dataclass(frozen=True)
class WordLists:
    lang: str
    whitelist: frozenset
    phrase_res: tuple
    stiff: dict
    leaks: dict
    status: str


def _norm(text) -> str:
    if text is None:
        return ""
    t = unicodedata.normalize("NFC", str(text))
    return t.replace("‌", "").replace("‍", "")


def _has_deva(t: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in t)


def word_count(text) -> int:
    """Words for the caption cap: whitespace/punctuation separated, digits count (१८७८ / 1878 = 2)."""
    return sum(1 for p in _SEP.split(_norm(text))
               if p and any(c.isalnum() or unicodedata.category(c).startswith("M") for c in p))


def detect_marathi(text) -> dict:
    """Return {language: 'mr'|'hi'|'unknown', score: -1..1 (+ = Marathi), evidence: {...}}."""
    t = _norm(text)
    toks = DEV_WORD.findall(t)
    mr_hits = [w for w in toks if w in MR_ONLY or w in MR_MARK]
    hi_hits = [w for w in toks if w in HI_ONLY or w in HI_MARK]
    weak = [w for w in toks if w in HI_WEAK]
    lla = t.count(LETTER_LLA)
    mr_pts = len(mr_hits) + 3 * lla
    hi_pts = len(hi_hits) + 0.5 * len(weak)
    total = mr_pts + hi_pts
    score = round((mr_pts - hi_pts) / total, 3) if total else 0.0
    if mr_pts >= MIN_POINTS and mr_pts >= RATIO * hi_pts:
        language = "mr"
    elif hi_pts >= MIN_POINTS and hi_pts >= RATIO * mr_pts:
        language = "hi"
    else:
        language = "unknown"
    evidence = {"mr_points": mr_pts, "hi_points": hi_pts, "mr_tokens": mr_hits,
                "hi_tokens": hi_hits + weak, "letter_lla": lla}
    return {"language": language, "score": score, "evidence": evidence}


def _read_json(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise SimpleLanguageDataError(f"word list missing: {path}") from e
    except OSError as e:
        raise SimpleLanguageDataError(f"cannot read word list {path}: {e}") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SimpleLanguageDataError(f"word list is not valid JSON: {path} (line {e.lineno}: {e.msg})") from e
    if not isinstance(data, dict):
        raise SimpleLanguageDataError(f"word list must be a JSON object: {path}")
    return data


def _whitelist(data: dict, path: Path) -> set:
    wl = data.get("whitelist")
    if isinstance(wl, dict):
        groups = list(wl.values())
    elif isinstance(wl, list):
        groups = [wl]
    else:
        raise SimpleLanguageDataError(f"'whitelist' must be a dict of lists (or a list) in {path}")
    out = set()
    for group in groups:
        if not isinstance(group, list) or not all(isinstance(w, str) for w in group):
            raise SimpleLanguageDataError(f"every whitelist group must be a list of strings in {path}")
        out.update(_norm(w).strip() for w in group if w.strip())
    return out


def _mapping(data: dict, key: str, path: Path, fold: bool = False) -> dict:
    m = data.get(key)
    if not isinstance(m, dict):
        raise SimpleLanguageDataError(f"'{key}' must be a JSON object in {path}")
    out = {}
    for k, v in m.items():
        k2 = _norm(k).strip()
        if fold:
            k2 = k2.lower()
        if not k2 or not isinstance(v, str) or not v.strip():
            raise SimpleLanguageDataError(f"'{key}' entries need a word and a non-empty string in {path}: {k!r}")
        if " " in k2:
            raise SimpleLanguageDataError(f"'{key}' keys must be single words (no spaces) in {path}: {k!r}")
        out[k2] = v.strip()
    return out


def _phrase_re(p: str, en: bool):
    if en:
        return re.compile(r"(?<![A-Za-z])" + re.escape(p) + r"(?![A-Za-z])", re.IGNORECASE)
    return re.compile(_NOT_DEV_BEFORE + re.escape(p) + _NOT_DEV_AFTER)


@lru_cache(maxsize=32)
def _load(lang: str, data_dir: str) -> WordLists:
    base = Path(data_dir)
    sacred_path = base / SACRED_FILE
    lang_path = base / f"simple_language_{lang}.json"
    sacred = _read_json(sacred_path)
    lang_data = _read_json(lang_path)
    wl = _whitelist(sacred, sacred_path)
    if "whitelist" in lang_data:  # per-language names (the English file carries Latin-transliterated names)
        wl |= _whitelist(lang_data, lang_path)
    en = lang == "en"
    if en:
        wl = {w.lower() for w in wl}
    phrases = sorted((w for w in wl if " " in w), key=len, reverse=True)
    return WordLists(lang=lang, whitelist=frozenset(wl),
                     phrase_res=tuple(_phrase_re(p, en) for p in phrases),
                     stiff=_mapping(lang_data, "stiff_words", lang_path, fold=en),
                     leaks={} if en else _mapping(lang_data, "leaks", lang_path),
                     status=str(lang_data.get("_status", "")))


def load_lists(lang: str, data_dir=None) -> WordLists:
    """Load and cache the word lists for hi, mr or en. Raises SimpleLanguageDataError with the file path."""
    if lang not in LANGS:
        raise ValueError(f"word lists exist for hi, mr and en only, got {lang!r}")
    return _load(lang, str(Path(data_dir) if data_dir else DATA_DIR))


def _flag(where, word, reason, suggestion, code) -> dict:
    return {"where": where, "word": word, "reason": reason, "suggestion": suggestion, "code": code}


def _mask(text: str, phrase_res) -> str:
    for pat in phrase_res:  # whitelisted phrases are blanked first, so their words cannot trip tier 2
        text = pat.sub(lambda m: " " * len(m.group(0)), text)
    return text


def _check_en(t: str, data_dir=None) -> list:
    """English tier: wrong script, stiff/legalese words, over-long sentences."""
    lists = load_lists("en", data_dir)
    flags = []
    if _has_deva(t):
        dev = DEV_WORD.findall(t)
        flags.append(_flag(None, dev[0] if dev else None, "SCRIPT-01: Devanagari text labelled en (wrong script)",
                           "label it hi or mr, or write this line in English", "SCRIPT-01"))
    masked = _mask(t, lists.phrase_res)
    seen = set()
    for w in _EN_TOKEN.findall(masked):
        lw = w.lower()
        if lw in lists.whitelist or lw in seen:
            continue
        seen.add(lw)
        if lw in lists.stiff:
            flags.append(_flag(None, w, "STIFF-01: legalese or literary word, use plain English",
                               lists.stiff[lw], "STIFF-01"))
    for sent in _SENT_SPLIT.split(t):
        n = len(_EN_COUNT.findall(sent))
        if n > EN_MAX_SENTENCE_WORDS:
            flags.append(_flag(None, None, f"SEN-01: sentence has {n} words (max {EN_MAX_SENTENCE_WORDS})",
                               "split it into two sentences", "SEN-01"))
    return flags


def _script_latin_flag(t: str, lang: str, data_dir) -> list:
    """hi/mr text with no Devanagari at all: flag it unless every Latin word is a whitelisted name."""
    names = load_lists("en", data_dir).whitelist
    for w in _EN_TOKEN.findall(t):
        if w.lower() not in names:
            return [_flag(None, w, f"SCRIPT-02: Latin-script text labelled {lang} (names are allowed)",
                          "write it in Devanagari", "SCRIPT-02")]
    return []


def check_text(text, lang, data_dir=None) -> dict:
    """Check one string. lang: hi | mr | en. Returns {ok, flags, language_detected, notes}."""
    if lang not in LANGS:
        raise ValueError(f"lang must be one of hi, mr, en; got {lang!r}")
    t = _norm(text)
    if not t.strip():
        detected = "unknown"
    elif not _has_deva(t):
        detected = "en"
    else:
        detected = detect_marathi(t)["language"]
    if lang == "en":
        flags = _check_en(t, data_dir)
        return {"ok": not flags, "flags": flags, "language_detected": detected,
                "notes": ["lang=en: SCRIPT-01, STIFF-01, SEN-01"]}
    flags = [] if _has_deva(t) or not t.strip() else _script_latin_flag(t, lang, data_dir)
    lists = load_lists(lang, data_dir)
    masked = _mask(t, lists.phrase_res)
    other = "Hindi" if lang == "mr" else "Marathi"
    seen = set()
    for w in DEV_WORD.findall(masked):
        if w in lists.whitelist or w in seen:
            continue
        seen.add(w)
        if w in lists.stiff:
            flags.append(_flag(None, w, "STIFF-01: literary word, use everyday speech", lists.stiff[w], "STIFF-01"))
        elif w in lists.leaks:
            flags.append(_flag(None, w, f"LEAK-01: {other} word in {lang} text", lists.leaks[w], "LEAK-01"))
    notes = [f"detected={detected}"]
    if {lang, detected} == {"hi", "mr"}:
        flags.append(_flag(None, None, f"LANG-01: text looks like {detected} but is labelled {lang}",
                           f"check the label; if the text is {detected}, run with lang={detected}", "LANG-01"))
    return {"ok": not flags, "flags": flags, "language_detected": detected, "notes": notes}


def _lang_code(v):
    if not isinstance(v, str):
        return None
    return _LANG_ALIASES.get(v.strip().lower())


def _item(where, text, lang, fallback, data_dir, caption=False):
    """Check one text. Returns (language used or None, flags, notes)."""
    t = _norm(text)
    if not t.strip():
        return None, [], []
    flags, notes = [], []
    if caption:
        n = word_count(t)
        if n > CAPTION_MAX_WORDS:
            flags.append(_flag(where, None, f"CAP-01: caption has {n} words (max {CAPTION_MAX_WORDS})",
                               "split into two cards", "CAP-01"))
    if lang is None:
        lang = fallback
    if lang is None:
        lang = "en" if not _has_deva(t) else detect_marathi(t)["language"]
        if lang == "unknown":
            notes.append(f"{where}: language unknown, word check skipped")
            return None, flags, notes
    flags += [{**f, "where": where} for f in check_text(t, lang, data_dir)["flags"]]
    return lang, flags, notes


def _lang_key_flag(where, raw):
    return _flag(where, None, f"LANG-02: unknown language key {raw!r} (use en, hi or mr)", "use en, hi or mr", "LANG-02")


def _lang_block(holder: dict, name: str) -> list:
    """Items of <name>_by_lang in one dict: [(where, text, raw_language_key)]."""
    block = holder.get(f"{name}_by_lang")
    if not isinstance(block, dict):
        return []
    out = []
    for k, v in block.items():
        if isinstance(v, list):
            for j, item in enumerate(v):
                text = item.get("text") if isinstance(item, dict) else item
                out.append((f"{name}_by_lang.{k}[{j}].text", text, k))
        else:
            text = v.get("text") if isinstance(v, dict) else v
            out.append((f"{name}_by_lang.{k}.text", text, k))
    return out


def _captions(node, path="") -> list:
    """(where, text, language, strict) for every caption under node. strict = from captions_by_lang."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else str(k)
            if k == "caption":
                if isinstance(v, dict):
                    out.append((p, v.get("text"), v.get("language"), False))
                else:
                    out.append((p, v, None, False))
            elif k == "captions" and isinstance(v, list):
                for j, c in enumerate(v):
                    if isinstance(c, dict):
                        out.append((f"{p}[{j}]", c.get("text"), c.get("language"), False))
                    else:
                        out.append((f"{p}[{j}]", c, None, False))
            elif k == "captions_by_lang" and isinstance(v, dict):
                for lk, lv in v.items():
                    if isinstance(lv, list):
                        for j, c in enumerate(lv):
                            out.append((f"{p}.{lk}[{j}]", c.get("text") if isinstance(c, dict) else c, lk, True))
                    else:
                        out.append((f"{p}.{lk}", lv.get("text") if isinstance(lv, dict) else lv, lk, True))
            else:
                out.extend(_captions(v, p))
    elif isinstance(node, list):
        for j, v in enumerate(node):
            out.extend(_captions(v, f"{path}[{j}]"))
    return out


def _new_result(sid) -> dict:
    return {"shot": sid, "flags": [], "notes": [], "by_language": {}}


def _add(res: dict, lang, flags, notes) -> None:
    if lang is None and not flags and not notes:  # empty text: nothing was checked
        return
    res["flags"].extend(flags)
    res["notes"].extend(notes)
    res["by_language"].setdefault(lang or "unknown", []).extend(flags)


def _finish(res: dict) -> dict:
    by = {k: {"ok": not v, "flags": v} for k, v in res["by_language"].items()}
    return {"shot": res["shot"], "ok": not res["flags"], "flags": res["flags"], "notes": res["notes"],
            "by_language": by}


def check_shot_texts(shots, default_lang=None, data_dir=None) -> list:
    """Walk V4 shot rows. Returns one result per row:
    {shot, ok, flags, notes, by_language: {lang: {ok, flags}}}.

    Each text is checked with the tier of its language: the key of a *_by_lang block, else the field's own
    language, else the story's output language (output_language / output_languages[0] of the file), else
    default_lang, else auto-detection. A *_by_lang block is authoritative for its field: the primary copy
    of that field is not checked a second time."""
    default = _lang_code(default_lang) if default_lang is not None else None
    if default_lang is not None and default is None:
        raise ValueError(f"default_lang must be hi, mr or en; got {default_lang!r}")
    story_lang = None
    if isinstance(shots, dict):
        story_lang = _lang_code(shots.get("output_language") or shots.get("language"))
        if story_lang is None and isinstance(shots.get("output_languages"), list):
            story_lang = next((c for c in map(_lang_code, shots["output_languages"]) if c), None)
    fallback = story_lang or default
    rows = shots.get("shots") if isinstance(shots, dict) else shots
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise TypeError("shots must be a list of shot rows (or an object with a 'shots' list)")
    results = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            res = _new_result(i)
            _add(res, None, [_flag(f"row[{i}]", None, "ROW-01: shot row is not an object", "fix the JSON", "ROW-01")], [])
            results.append(_finish(res))
            continue
        res = _new_result(row.get("id", i))
        aat = row.get("audio_and_dialogue_track")
        aat = aat if isinstance(aat, dict) else {}
        holders = (aat, row)

        # narration: primary copy, unless a narration_by_lang block is present
        nar = aat.get("narration")
        nar_lang = _lang_code(nar.get("language")) if isinstance(nar, dict) else None
        nar_block = [it for h in holders for it in _lang_block(h, "narration")]
        if isinstance(nar, dict) and not nar_block:
            lg, f, n = _item("narration.text", nar.get("text"), nar_lang, fallback, data_dir)
            _add(res, lg, f, n)
        for where, text, raw in nar_block:
            lang = _lang_code(raw)
            if lang is None:
                _add(res, None, [_lang_key_flag(where, raw)], [])
                continue
            lg, f, n = _item(where, text, lang, fallback, data_dir)
            _add(res, lg, f, n)

        # dialogue: same rule as narration
        dia = aat.get("dialogue")
        dia_block = [it for h in holders for it in _lang_block(h, "dialogue")]
        if isinstance(dia, list) and not dia_block:
            for j, d in enumerate(dia):
                if isinstance(d, dict):
                    hint = _lang_code(d.get("language")) or nar_lang
                    lg, f, n = _item(f"dialogue[{j}].text", d.get("text"), hint, fallback, data_dir)
                    _add(res, lg, f, n)
        for where, text, raw in dia_block:
            lang = _lang_code(raw)
            if lang is None:
                _add(res, None, [_lang_key_flag(where, raw)], [])
                continue
            lg, f, n = _item(where, text, lang, fallback, data_dir)
            _add(res, lg, f, n)

        # captions: primary caption fields, unless a captions_by_lang block is present (then strict only)
        caps = _captions(row)
        has_cap_block = any(s for _, _, _, s in caps)
        for where, text, hint, strict in caps:
            if strict:
                lang = _lang_code(hint)
                if lang is None:
                    _add(res, None, [_lang_key_flag(where, hint)], [])
                    continue
            elif has_cap_block:
                continue
            else:
                lang = _lang_code(hint)
            lg, f, n = _item(where, text, lang, fallback, data_dir, caption=True)
            _add(res, lg, f, n)
        results.append(_finish(res))
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Simple-language check for V4 shot rows (hi, mr, en).")
    ap.add_argument("shots", help="shots.json (a list of shot rows, or an object with a 'shots' list)")
    ap.add_argument("--lang", choices=["hi", "mr", "en"], default=None,
                    help="language for texts that carry none (a story's output_language wins over this)")
    args = ap.parse_args(argv)
    try:
        data = json.loads(Path(args.shots).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"simple_language: cannot read shots file {args.shots}: {e}", file=sys.stderr)
        return 2
    try:
        results = check_shot_texts(data, default_lang=args.lang)
    except (SimpleLanguageDataError, TypeError, ValueError) as e:
        print(f"simple_language: {e}", file=sys.stderr)
        return 2
    total = sum(len(r["flags"]) for r in results)
    print(f"simple_language: {len(results)} shot rows checked, {total} flags")
    for r in results:
        for f in r["flags"]:
            word = f" '{f['word']}'" if f["word"] else ""
            print(f"  shot {r['shot']} {f['where']}:{word} [{f['code']}] {f['reason']} -> {f['suggestion']}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
