"""Index the owner's royalty-free sample libraries (read only) for the reel score.

Pure: scans folders, reads WAV/AIFF headers with soundfile, parses BPM, key and category from file and folder
names. Never writes into a library folder. CLI:
    python -m score.sample_index [--out research/sample_index_reel_libs.json] [--root DIR ...]

index_roots(roots) -> list of entries {path, pack, name, bpm, key, categories, seconds, channels, sr}
  bpm: float or None (from "128", "128bpm", "_128_" in the file or folder name, range 50-200).
  key: e.g. "D min", "F# maj", or None (only a letter with an explicit min/maj/m suffix counts, so bare letters
       such as "A" in "A Kick" never match).
  categories: list of category words found in path segments (drum loop, kick, bass loop, chord, arp, ...).
Titles containing words ("Hooks With Lyrics", "vocal chant" with lyrics) are excluded by LYRIC_WORDS.
"""
import argparse
import json
import os
import re
import sys

import soundfile as sf

from score.key_estimate import detect_file

TONAL = {"bass_loop", "chord_loop", "arp", "lead", "pad", "flute", "sitar", "brass", "strings", "piano",
         "vocal_chant", "vocal_world", "adlib", "texture", "riser", "instrument", "war_horn", "sub_drop"}

DEFAULT_ROOTS = [
    "D:/Sounds of KSHMR Vol 4 Complete Edition",
    "D:/Producion class/Dharma Studio - Sounds of KSHMR Vol.5 Complete Edition",
    "D:/Producion class/Indian Perc.-BAGAL BACHHA 100 BPM",
    "D:/Producion class/Production Music Live - Melodic House - Afterglow/PML - Melodic House - Sample Pack",
    "D:/Producion class/Production Music Live - Afro House Sound Pack Vol.4/PML - Afro House - Sample Pack",
    "D:/Producion class/Splice Sounds - Chords of KSHMR (WAV MIDI)",
]
AUDIO_EXT = (".wav", ".aif", ".aiff")

# Never used: folders or files with lyrics or words (all 3 languages share one score), and film or song material.
EXCLUDE_WORDS = ("hooks with lyrics", "lyric", "lyrics", "with vox", "vocal phrase", "word")

# category -> path words that select it (checked on lowercase path segments, joined with spaces)
CATEGORY_WORDS = [
    ("kick", ["kick"]),
    ("snare", ["snare", "clap"]),
    ("hat", ["hat", "hihat", "hi-hat"]),
    ("perc", ["perc", "percussion", "tom", "shaker", "conga", "bongo"]),
    ("drum_loop", ["drum loop", "drumloop", "drum loops", "breakbeat", "break"]),
    ("drum_oneshot", ["drum", "drums"]),
    ("bass_loop", ["bass loop", "bassloop", "bass"]),
    ("chord_loop", ["chord", "chords", "progression"]),
    ("arp", ["arp", "arpeggio", "sequence"]),
    ("lead", ["lead", "melody", "pluck"]),
    ("pad", ["pad", "pads", "atmosphere"]),
    ("flute", ["flute", "bansuri"]),
    ("sitar", ["sitar"]),
    ("brass", ["brass", "trumpet", "horn section"]),
    ("strings", ["string", "strings", "violin", "cello"]),
    ("piano", ["piano", "keys"]),
    ("vocal_chant", ["chant", "chants", "hum", "hums", "chop", "chops"]),
    ("vocal_world", ["world vocal", "world vocals", "vocals"]),
    ("adlib", ["adlib", "adlibs"]),
    ("impact", ["impact", "impacts"]),
    ("sub_drop", ["sub drop", "subdrop", "sub drops"]),
    ("riser", ["riser", "risers", "sweep", "sweeps", "uplifter"]),
    ("war_horn", ["war horn", "war horns", "horn", "alarm", "alarms"]),
    ("texture", ["texture", "textures", "ambience", "ambient", "fx", "noise"]),
    ("instrument", ["instrument", "instruments"]),
]

_BPM_RES = [
    re.compile(r"(?<![0-9])(\d{2,3}(?:\.\d)?)\s*bpm", re.IGNORECASE),
    re.compile(r"(?:^|(?<=[\s_\-(\[]))(\d{2,3})(?=[\s_\-.,)\]]|$)"),
]
_KEY_RE = re.compile(
    r"(?<![A-Za-z])([A-G])([#b]?)[ _\-]?(min|minor|maj|major|m)(?![A-Za-z])",
    re.IGNORECASE,
)


_ROOT_RE = re.compile(r"\(([A-Ga-g])([#b]?)\)")


def parse_bpm(text):
    """First plausible tempo in a name, or None. The bpm-suffixed form wins over a bare number."""
    m = _BPM_RES[0].search(text)
    if m and 50 <= float(m.group(1)) <= 200:
        return float(m.group(1))
    for m in _BPM_RES[1].finditer(text):
        v = float(m.group(1))
        if 50 <= v <= 200:
            return v
    return None


def parse_key(text):
    """'D min', 'F# maj' from names like 'Dm', 'F#m', 'D minor', 'Bb major'. Bare letters are never keys."""
    m = _KEY_RE.search(text)
    if not m:
        m2 = _ROOT_RE.search(text)  # packs write "(D)", "(F#)": root only, mode unknown
        return f"{m2.group(1).upper()}{m2.group(2)} root" if m2 else None
    root, acc, qual = m.group(1).upper(), m.group(2), m.group(3).lower()
    mode = "min" if qual in ("min", "minor", "m") else "maj"
    return f"{root}{acc} {mode}"


def categorize(rel_parts):
    """Category words found in the path segments (lowercase, joined)."""
    text = " ".join(p.lower() for p in rel_parts)
    found = []
    for cat, words in CATEGORY_WORDS:
        for w in words:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text):
                found.append(cat)
                break
    return found


def _excluded(rel_parts):
    text = " ".join(p.lower() for p in rel_parts)
    return any(w in text for w in EXCLUDE_WORDS)


def index_roots(roots, probe=sf.info):
    entries = []
    for root in roots:
        root = os.path.normpath(root)
        if not os.path.isdir(root):
            continue
        pack = os.path.basename(root)
        for dirpath, _dirs, files in os.walk(root):
            for fn in sorted(files):
                if not fn.lower().endswith(AUDIO_EXT):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root).split(os.sep)
                if _excluded(rel):
                    continue
                folders = rel[:-1]
                name_text = " ".join(rel)
                bpm = parse_bpm(fn) or parse_bpm(" ".join(folders))
                key = parse_key(fn) or parse_key(" ".join(folders))
                try:
                    info = probe(full)
                    seconds = round(info.frames / float(info.samplerate), 4)
                    channels, sr = info.channels, info.samplerate
                except Exception:
                    continue  # unreadable file: skip, never fail the scan
                entries.append({
                    "path": full.replace("\\", "/"),
                    "pack": pack,
                    "name": fn,
                    "bpm": bpm,
                    "key": key,
                    "categories": categorize(rel),
                    "seconds": seconds,
                    "channels": channels,
                    "sr": sr,
                    "_text": name_text,
                })
    for e in entries:
        e.pop("_text", None)
    return entries


def measure_tonal(entries, max_s=30.0):
    """Add detected_key / detected_confidence to every tonal entry (measured, never trusted from the name)."""
    for e in entries:
        if not (TONAL & set(e["categories"])) or e["seconds"] < 0.5:
            continue
        try:
            d = detect_file(e["path"], max_s=max_s)
        except Exception:
            continue
        e["detected_key"] = d["key"]
        e["detected_confidence"] = d["confidence"]
    return entries


def write_index(roots, out_path, measure=True):
    entries = index_roots(roots)
    if measure:
        measure_tonal(entries)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"schema_version": 1, "roots": roots, "count": len(entries), "entries": entries}, f,
                  ensure_ascii=False, indent=1)
    return entries


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="research/sample_index_reel_libs.json")
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--no-measure", action="store_true", help="skip the chroma key measurement")
    args = ap.parse_args(argv)
    roots = args.root or DEFAULT_ROOTS
    entries = write_index(roots, args.out, measure=not args.no_measure)
    print(f"indexed {len(entries)} files -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
