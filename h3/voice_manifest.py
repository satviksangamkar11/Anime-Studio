"""Voice .wav manifest per language (audio/vo/<lang>/<shot_id>.wav). Pure functions plus a small CLI.

No ElevenLabs call: the owner supplies the wav files; this only reads them (stdlib wave via gate_d_audio) and
records sha256, duration, voice ids and the VO-fit result. A text change after the wav was made marks it stale.
CLI: python -m h3.voice_manifest --vo-root <dir> --shots <shots.json> --lang en,hi [--voice-map <json>] [--out <json>]
"""
import argparse
import hashlib
import json
import os
import sys

from h3.gate_d_audio import vo_fit_check, wav_duration_sec
from h3.voice_engine import NARRATOR

MANIFEST_SCHEMA = 1
LANGS = ("en", "hi", "mr")


def shot_id(shot):
    return shot.get("id") or shot.get("shot_id")


def narration_text(shot, lang):
    """Narration text of a shot in one language (*_by_lang first, else the single narration in that language)."""
    trk = shot.get("audio_and_dialogue_track") or {}
    by_lang = trk.get("narration_by_lang") or {}
    if isinstance(by_lang.get(lang), dict):
        return str(by_lang[lang].get("text") or "")
    narr = trk.get("narration") or {}
    return str(narr.get("text") or "") if narr.get("language") == lang else ""


def text_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wav_rel_path(lang, sid):
    return f"audio/vo/{lang}/{sid}.wav"


def voice_ids_for(shot, lang, voice_map):
    """{"narrator": id or None, "speakers": {character: id}} for one shot in one language."""
    vm = voice_map or {}
    trk = shot.get("audio_and_dialogue_track") or {}
    speakers = {}
    for d in trk.get("dialogue") or []:
        ch = d.get("speaker") if isinstance(d, dict) else None
        if ch and ch in vm and isinstance(vm[ch], dict) and vm[ch].get(lang):
            speakers[ch] = vm[ch][lang]
    narr = (vm.get(NARRATOR) or {}).get(lang) if isinstance(vm.get(NARRATOR), dict) else None
    return {"narrator": narr or None, "speakers": speakers}


def build_entry(vo_root, shot, lang, voice_map=None):
    """One manifest entry. Missing or unreadable wav: exists False, no duration (vo_fit_check reports it)."""
    sid = shot_id(shot)
    rel = wav_rel_path(lang, sid)
    path = os.path.join(vo_root, rel)
    entry = {"shot_id": sid, "lang": lang, "path": rel, "exists": os.path.isfile(path),
             "text_sha256": text_sha256(narration_text(shot, lang)),
             "editorial_duration_sec": shot.get("editorial_duration_sec"),
             "voice_ids": voice_ids_for(shot, lang, voice_map), "sha256": None, "duration_sec": None}
    if entry["exists"]:
        with open(path, "rb") as f:
            entry["sha256"] = hashlib.sha256(f.read()).hexdigest()
        try:
            entry["duration_sec"] = round(wav_duration_sec(path), 3)
        except Exception:  # not a readable PCM wav: the fit check reports VO_UNREADABLE
            entry["duration_sec"] = None
    return entry


def build_manifest(vo_root, shots, languages, voice_map=None):
    """{"schema", "languages", "entries": [...], "fit": {"ok", "errors", ...}}. Fit runs per language on the wavs
    that exist; a shot with narration in that language and no wav is a VO_MISSING error."""
    entries, fit_items, errors = [], [], []
    for lang in languages:
        for shot in shots:
            if not narration_text(shot, lang).strip():
                continue  # this shot has no narration in this language: no wav needed
            e = build_entry(vo_root, shot, lang, voice_map)
            entries.append(e)
            if e["exists"]:
                fit_items.append({"shot_id": e["shot_id"], "wav_path": os.path.join(vo_root, e["path"]),
                                  "editorial_duration_sec": e["editorial_duration_sec"]})
            else:
                errors.append({"code": "VO_MISSING", "where": f"{lang}/{e['shot_id']}", "message": f"no {e['path']}"})
    fit = vo_fit_check(fit_items)
    return {"schema": MANIFEST_SCHEMA, "languages": list(languages), "entries": entries,
            "fit": {"ok": fit["ok"] and not errors, "errors": errors + fit["errors"], "stats": fit["stats"]}}


def stale_entries(manifest, shots):
    """Entries whose shot text changed after the wav was made (text_sha256 differs). Returns [(lang, shot_id)]."""
    by_id = {shot_id(s): s for s in shots}
    out = []
    for e in manifest.get("entries", []):
        shot = by_id.get(e["shot_id"])
        if shot is None:
            out.append((e["lang"], e["shot_id"]))
        elif text_sha256(narration_text(shot, e["lang"])) != e["text_sha256"]:
            out.append((e["lang"], e["shot_id"]))
    return out


def _cli(argv=None):
    ap = argparse.ArgumentParser(prog="python -m h3.voice_manifest", description="Voice wav manifest (no model call).")
    ap.add_argument("--vo-root", required=True, help="folder that holds audio/vo/<lang>/<shot_id>.wav")
    ap.add_argument("--shots", required=True, help="shots JSON: a list of shot rows, or {'shots': [...]}")
    ap.add_argument("--lang", required=True, help="comma-separated languages, e.g. en,hi")
    ap.add_argument("--voice-map", help="JSON object: the bible voice_map")
    ap.add_argument("--out", help="write the manifest JSON here")
    args = ap.parse_args(argv)
    langs = [x.strip() for x in args.lang.split(",") if x.strip()]
    if not langs or any(x not in LANGS for x in langs) or len(set(langs)) != len(langs):
        print(f"ERROR: --lang must be a unique subset of {LANGS}")
        return 2
    with open(args.shots, encoding="utf-8") as f:
        doc = json.load(f)
    shots = doc["shots"] if isinstance(doc, dict) else doc
    vmap = None
    if args.voice_map:
        with open(args.voice_map, encoding="utf-8") as f:
            vmap = json.load(f)
    man = build_manifest(args.vo_root, shots, langs, vmap)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(man, f, indent=2, ensure_ascii=False)
    print(f"entries={len(man['entries'])} fit_ok={man['fit']['ok']} errors={len(man['fit']['errors'])}")
    for err in man["fit"]["errors"]:
        print(f"  ! {err['code']} {err['where']}: {err['message']}")
    return 0 if man["fit"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
