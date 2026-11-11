"""Voice file naming, header validation, and slot-length helpers."""

from __future__ import annotations

import math
from pathlib import Path

LANGS = ("en", "hi", "mr")


WINDOWS_RESERVED = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{i}" for i in range(1, 10)]
    + [f"lpt{i}" for i in range(1, 10)]
)


def wav_name(line_id: str, lang: str) -> str:
    """Return the canonical voice file name for a line id and language.

    The line id is a line id such as "SHOT-001-N".
    """
    if lang not in LANGS:
        raise ValueError(f"unsupported language: {lang!r}")
    if not line_id:
        raise ValueError("line_id must not be empty")
    if "/" in line_id or "\\" in line_id or ".." in line_id or ":" in line_id:
        raise ValueError(f"line_id must not be path-like: {line_id!r}")
    if line_id[-1] in ". ":
        raise ValueError(f"line_id must not end with '.' or space: {line_id!r}")
    if any(ord(ch) < 32 for ch in line_id):
        raise ValueError(f"line_id must not contain control characters: {line_id!r}")
    stem = line_id.split(".", 1)[0].rstrip(" ").casefold()
    if stem in WINDOWS_RESERVED:
        raise ValueError(f"line_id uses a Windows reserved name: {line_id!r}")
    if any(ch in "<>|?*\"" for ch in line_id):
        raise ValueError("line_id must not contain Windows-illegal characters: " + repr(line_id))
    return f"{line_id}.{lang}.wav"


def sniff_audio(path) -> str:
    """Sniff the first 12 bytes of *path* and return 'wav' or 'mp3'."""
    p = Path(path)
    with p.open("rb") as f:
        data = f.read(12)
    if len(data) < 12:
        raise ValueError(f"file too short to sniff: {p}")
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:3] == b"ID3":
        return "mp3"
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    raise ValueError(f"unrecognized audio format: {p}")


def require_wav(path) -> Path:
    """Return *path* as a Path only if it has a .wav name and WAV content."""
    p = Path(path)
    name = p.name
    if not name.lower().endswith(".wav"):
        raise ValueError(
            f"file {name!r} does not have a .wav extension"
        )
    kind = sniff_audio(p)
    if kind != "wav":
        raise ValueError(
            f"file {name!r} has a .wav extension but content looks like mp3"
        )
    return p


def slot_seconds(seconds_by_lang: dict) -> float:
    """Return the maximum slot length across languages."""
    if not seconds_by_lang:
        raise ValueError("seconds_by_lang must not be empty")
    best = None
    for lang, value in seconds_by_lang.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"non-numeric slot length for {lang!r}: {value!r}")
        if not math.isfinite(value):
            raise ValueError(f"non-finite slot length for {lang!r}: {value!r}")
        if value < 0:
            raise ValueError(f"negative slot length for {lang!r}: {value!r}")
        if best is None or value > best:
            best = value
    return float(best)


def find_voice(folder, shot_id: str, lang: str) -> Path:
    """Return folder / lang / wav_name(shot_id, lang) if it exists."""
    expected = Path(folder) / lang / wav_name(shot_id, lang)
    if not expected.is_file():
        raise FileNotFoundError(
            f"voice file not found: {expected}"
        )
    return expected


def plan_names(shot_ids: list, langs=LANGS) -> list:
    """Return every (shot_id, lang, file name) triple in stable order."""
    folded = [s.casefold() for s in shot_ids]
    if len(folded) != len(set(folded)):
        raise ValueError("shot_ids contains duplicates")
    triples = []
    for shot_id in shot_ids:
        for lang in langs:
            triples.append((shot_id, lang, wav_name(shot_id, lang)))
    return triples
