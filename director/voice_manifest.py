"""D-VOICE: the voice manifest binds the text that was voiced to the exported wav, so the captions are built from the same text.

One file per language: <voices dir>/voice_manifest.<lang>.json =
  {"schema": "voice_manifest/1", "lang": "hi", "source_text_sha256": "...",
   "rows": [{"id": "<line>.<lang>", "text", "text_sha256", "wav", "wav_sha256", "seconds", "speaker"}]}
  text_sha256   = sha256 of the NFC-normalised UTF-8 text.
  wav_sha256    = sha256 of the wav file bytes; wav is a path relative to the manifest folder.
  source_text_sha256 = sha256 of the JSON list of [id, text_sha256] pairs sorted by id (binds the row set).
Any change to a text, a wav or a row makes the loader refuse. Stdlib only."""
from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from pathlib import Path

SCHEMA = "voice_manifest/1"
TOP_KEYS = {"schema", "lang", "rows", "source_text_sha256"}
ROW_KEYS = {"id", "text", "text_sha256", "wav", "wav_sha256", "seconds", "speaker"}


class VoiceManifestError(ValueError):
    """Any refusal. The message names the file, row or field."""


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def text_sha256(text: str) -> str:
    return hashlib.sha256(nfc(text).encode("utf-8")).hexdigest()


def file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_sha256(rows: list) -> str:
    pairs = sorted([r["id"], r["text_sha256"]] for r in rows)
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False).encode("utf-8")).hexdigest()


def manifest_path(folder, lang: str) -> Path:
    return Path(folder) / f"voice_manifest.{lang}.json"


def _rel(wav: Path, folder: Path) -> str:
    try:
        return os.path.relpath(wav, folder).replace("\\", "/")
    except ValueError:                                   # another drive: keep the absolute path
        return str(wav).replace("\\", "/")


def write_manifest(folder, lang: str, rows: list) -> Path:
    """rows: dicts {id, text, wav (path of the exported wav), seconds, speaker}. Writes the manifest into folder
    (temp file, then replace) and returns its path. The text stored is the NFC text that was hashed."""
    folder = Path(folder)
    out = []
    for r in sorted(rows, key=lambda x: x["id"]):
        wav = Path(r["wav"])
        out.append({"id": r["id"], "text": nfc(r["text"]), "text_sha256": text_sha256(r["text"]),
                    "wav": _rel(wav, folder), "wav_sha256": file_sha256(wav),
                    "seconds": round(float(r["seconds"]), 3), "speaker": r["speaker"]})
    man = {"schema": SCHEMA, "lang": lang, "rows": out, "source_text_sha256": source_sha256(out)}
    path = manifest_path(folder, lang)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_voice_manifest(path, lang: str | None = None, check_files: bool = True) -> list:
    """Returns the rows of one manifest after every check: schema, fields, language, text hashes, wav hashes, row set.
    lang=None skips the language check (the rows still must carry their own language suffix)."""
    path = Path(path)
    try:
        man = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VoiceManifestError(f"{path}: not readable JSON: {exc}") from None
    if not isinstance(man, dict):
        raise VoiceManifestError(f"{path}: not a JSON object")
    if man.get("schema") != SCHEMA:
        raise VoiceManifestError(f"{path}: unknown schema {man.get('schema')!r} (want {SCHEMA})")
    if set(man) != TOP_KEYS:
        raise VoiceManifestError(f"{path}: missing fields {sorted(TOP_KEYS - set(man))} or unknown fields {sorted(set(man) - TOP_KEYS)}")
    mlang = man["lang"]
    if lang is not None and mlang != lang:
        raise VoiceManifestError(f"{path}: wrong lang: manifest is {mlang}, the build needs {lang}")
    if not isinstance(man["rows"], list):
        raise VoiceManifestError(f"{path}: rows is not a list")
    folder = path.parent
    seen = set()
    for r in man["rows"]:
        if not isinstance(r, dict):
            raise VoiceManifestError(f"{path}: a row is not an object")
        rid = r.get("id", "?")
        if set(r) != ROW_KEYS:
            raise VoiceManifestError(f"{rid}: missing fields {sorted(ROW_KEYS - set(r))} or unknown fields {sorted(set(r) - ROW_KEYS)}")
        if rid in seen:
            raise VoiceManifestError(f"{rid}: duplicate id in the voice manifest")
        seen.add(rid)
        if not rid.endswith("." + mlang):
            raise VoiceManifestError(f"{rid}: wrong lang, the row is not {mlang}")
        if not isinstance(r["text"], str) or not r["text"].strip():
            raise VoiceManifestError(f"{rid}: empty text")
        if text_sha256(r["text"]) != r["text_sha256"]:
            raise VoiceManifestError(f"{rid}: text_sha256 does not match its text (the text changed after it was voiced)")
        if not isinstance(r["seconds"], (int, float)) or isinstance(r["seconds"], bool) or r["seconds"] <= 0:
            raise VoiceManifestError(f"{rid}: seconds must be a positive number")
        if check_files:
            wav = folder / r["wav"]
            if not wav.is_file():
                raise VoiceManifestError(f"{rid}: wav missing: {wav}")
            if file_sha256(wav) != r["wav_sha256"]:
                raise VoiceManifestError(f"{rid}: wav_sha256 does not match the wav file (the audio changed after it was voiced)")
    if source_sha256(man["rows"]) != man["source_text_sha256"]:
        raise VoiceManifestError(f"{path}: source_text_sha256 does not match the rows")
    return man["rows"]


def require_row(rows: list, line_id: str) -> dict:
    """The row of one line id ('<line>.<lang>'); a missing row is a refusal, never a silent skip."""
    for r in rows:
        if r["id"] == line_id:
            return r
    raise VoiceManifestError(f"{line_id}: no row in the voice manifest")
