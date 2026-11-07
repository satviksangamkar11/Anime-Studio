"""Caption cue layer of the one shared caption engine (owner brief 2026-11-07, Work Items 1 and 3).

The engine is core/captions.py (ASS burn list), core/caption_export.py (SRT, WebVTT, karaoke, preflight),
core/caption_text.py (clusters, wrapping, fonts) and this module, which owns:
  * the cue model: {"t0": s, "t1": s, "text": str, "kind": "spoken" | "hook"} on the reel clock;
  * the spoken-script reader (the V4 audio_and_dialogue_track: captions_by_lang wins, else narration and dialogue text);
  * the script validator: Devanagari forbidden in English cues, required in Hindi and Marathi cues. It lives here and
    nowhere else; post.py and Gate D both call it;
  * the hook policy: the hook caption stays on frame 1 even when a spoken script exists (window until the first spoken
    cue, shortened by an explicit hook duration; text burned once when it equals the first spoken line).
Standard library only. Never raises on junk cues; readers raise ValueError on a malformed time_range.
"""
import math
import re

KIND_SPOKEN = "spoken"
KIND_HOOK = "hook"
LANGUAGES = ("en", "hi", "mr")
RULE = "CAP-CUE"

_RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*s?\s*$")
_DEVA = re.compile("[ऀ-ॿ]")
_LATIN = re.compile("[A-Za-z]")


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _entry(level, message):
    return {"rule": RULE, "level": level, "shot": None, "episode": None, "message": message}


def parse_time_range(value):
    """[s, e] list, or a "1.2-1.6s" / "1.2–1.6s" string -> (s, e). ValueError when malformed or not e > s."""
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(_is_num(v) for v in value):
        s, e = float(value[0]), float(value[1])
    elif isinstance(value, str) and _RANGE_RE.match(value):
        m = _RANGE_RE.match(value)
        s, e = float(m.group(1)), float(m.group(2))
    else:
        raise ValueError(f"bad time_range {value!r}")
    if e <= s:
        raise ValueError(f"time_range must have end > start: {value!r}")
    return s, e


def lang_track(trk, lang):
    """(narration, dialogue) of one shot for one language. Shots with *_by_lang maps use them. Single-language shots
    keep the old fields and serve only their narration language (dialogue is taken as that language)."""
    if trk.get("narration_by_lang") is not None or trk.get("dialogue_by_lang") is not None:
        nbl, dbl = trk.get("narration_by_lang"), trk.get("dialogue_by_lang")
        nbl = nbl if isinstance(nbl, dict) else {}
        dbl = dbl if isinstance(dbl, dict) else {}
        return nbl.get(lang), dbl.get(lang) or []
    narr = trk.get("narration")
    if isinstance(narr, dict) and narr.get("language") == lang:
        return narr, trk.get("dialogue") or []
    return None, []


def spoken_cues(shots, offsets, lang):
    """Spoken-script cues on the reel clock. captions_by_lang[lang] wins when given ({"text", "time_range"}, or plain text
    on the narration time). Otherwise the narration and dialogue text of that language is captioned."""
    cues = []
    for shot, t0 in zip(shots, offsets):
        if not isinstance(shot, dict):
            raise ValueError("shot must be an object")
        trk = shot.get("audio_and_dialogue_track")
        if trk is None:
            continue
        if not isinstance(trk, dict):
            raise ValueError("audio_and_dialogue_track must be an object")
        narr, dia = lang_track(trk, lang)
        if narr is not None and not isinstance(narr, dict):
            raise ValueError("narration must be an object")
        if not isinstance(dia, list) or not all(isinstance(d, dict) for d in dia):
            raise ValueError("dialogue must be a list of objects")
        cbl = trk.get("captions_by_lang")
        if cbl is not None and not isinstance(cbl, dict):
            raise ValueError("captions_by_lang must be an object")
        cap = cbl.get(lang) if cbl else None
        items = []
        if isinstance(cap, dict):
            items.append((cap.get("text"), cap.get("time_range") or (narr or {}).get("time_range")))
        elif isinstance(cap, str) and narr:
            items.append((cap, narr.get("time_range")))
        else:
            items.append(((narr or {}).get("text"), (narr or {}).get("time_range")))
            items += [(d.get("text"), d.get("time_range")) for d in dia]
        for text, rng in items:
            if str(text or "").strip() and rng:
                s, e = parse_time_range(rng)
                cues.append({"t0": s + t0, "t1": e + t0, "text": text, "kind": KIND_SPOKEN})
    return cues


def script_problems(cues, language):
    """The script validator: messages for cue texts in the wrong script for the output language (first three only).
    English cues must not contain Devanagari; Hindi and Marathi cues that contain Latin letters must contain Devanagari."""
    out = []
    for c in cues:
        text = c.get("text") if isinstance(c, dict) else None
        if not isinstance(text, str) or not text.strip():
            continue
        if language == "en" and _DEVA.search(text):
            out.append(f"English reel: caption {text[:30]!r} contains Devanagari")
        elif language in ("hi", "mr") and _LATIN.search(text) and not _DEVA.search(text):
            out.append(f"{language} reel: caption {text[:30]!r} has no Devanagari")
    return out[:3]


def _same(a, b):
    return " ".join(str(a).split()).casefold() == " ".join(str(b).split()).casefold()


def build_cue_list(spoken, hook_text, *, hook_end=None, hook_duration=None):
    """-> (cues, entries): the cue list that is burned and written to SRT and WebVTT.

    spoken: spoken cues (any order). hook_text: the hook caption (None or empty = none). hook_end: where the hook ends when
    there is no spoken script (today's behaviour: the end of the first shot). hook_duration: explicit hook length in
    seconds from the pack (the shorter of it and the window wins).
    Rule 1: the hook runs from frame 1 to the start of the first spoken cue. Rule 3: when the hook text equals the first
    spoken cue's text it is not added; the spoken cue is burned once. Rule 4: otherwise the hook is the first cue (kind
    hook), so the SRT and WebVTT carry what is burned. With no spoken script the hook is burned alone."""
    entries = []
    good = [c for c in spoken if isinstance(c, dict) and _is_num(c.get("t0")) and _is_num(c.get("t1")) and isinstance(c.get("text"), str)]
    if len(good) != len(spoken):
        entries.append(_entry("WARN", f"{len(spoken) - len(good)} malformed spoken cue(s) skipped (need numeric t0, t1 and a text)"))
    spoken = sorted((dict(c) for c in good), key=lambda c: (c["t0"], c["t1"]))
    hook_text = hook_text.strip() if isinstance(hook_text, str) else ""
    if not hook_text:
        return spoken, entries
    if not spoken:
        end = hook_end if _is_num(hook_end) and hook_end > 0 else None
        if end is None:
            entries.append(_entry("WARN", "hook caption has no end time: not burned"))
            return spoken, entries
        if _is_num(hook_duration) and hook_duration > 0:
            end = min(end, float(hook_duration))
        return [{"t0": 0.0, "t1": float(end), "text": hook_text, "kind": KIND_HOOK}], entries
    first = spoken[0]
    if _same(hook_text, first["text"]):
        return spoken, entries
    window = first["t0"]
    if _is_num(hook_duration) and hook_duration > 0:
        window = min(window, float(hook_duration))
    if window <= 1e-6:
        entries.append(_entry("WARN", "the first spoken cue starts at frame 1: the hook caption has no window and is not burned"))
        return spoken, entries
    return [{"t0": 0.0, "t1": float(window), "text": hook_text, "kind": KIND_HOOK}] + spoken, entries


def hook_of(shot, language=None):
    """(text, duration_s) of a shot's hook caption: metadata.look.hook {caption, caption_by_lang, duration_s}.
    caption_by_lang[language] wins over caption, so a reel in each language gets a hook in its own script.
    (None, None) when absent."""
    meta = shot.get("metadata") if isinstance(shot, dict) else None
    look = meta.get("look") if isinstance(meta, dict) else None
    hook = look.get("hook") if isinstance(look, dict) else None
    if not isinstance(hook, dict):
        return None, None
    by_lang = hook.get("caption_by_lang")
    text = by_lang.get(language) if isinstance(by_lang, dict) and language else None
    if not isinstance(text, str):
        text = hook.get("caption")
    dur = hook.get("duration_s")
    return (text if isinstance(text, str) else None), (dur if _is_num(dur) else None)
