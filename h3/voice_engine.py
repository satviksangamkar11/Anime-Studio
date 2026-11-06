"""Voice engine rules per output language (owner decision 2026-11-07; research/EN_H3_VOICE_CONSISTENCY_2026-11-07.md).

FINAL owner decision (2026-11-07, Option A, render once): ONE shared pure-Foley H3 render serves every selected language.
Defaults en = hi = mr = "elevenlabs": the voices are ElevenLabs, added after render and Step 9 QC, never called by code.
"h3" is an OFF-BY-DEFAULT switch for en only: it means a SECOND English H3 render (speech in its prompt). It breaks the
render-once rule and adds H3 cost. hi and mr can never be "h3".

ElevenLabs consistency by construction: bible `voice_map` = {character or "NARRATOR": {"en": id, "hi": id, "mr": id}}, one
fixed voice id per character per language, reused in every shot and reel (VM-*).

English H3 consistency (official: stable (Sx) id per speaker across shots, base-en s4.4; <Audio N> voice timbre reference
bound to a speaker, ref-en s2.4): every speaking character has ONE voice anchor = the audio of its FIRST APPROVED H3 clip
(extracted, no ElevenLabs call), plus a fixed voice description sentence, reused as <Audio N> in later Ref2VA shots.
UNVERIFIED: that a re-extracted anchor gives the same timbre in later renders (no official rule; W4 transcript notes say a
reference can change the speaker when an extension adds a new speaker: research/workflow_review/W4_transcript_tips.md).

Pure functions, no I/O. Returns (code, message) lists; callers decide the severity.
"""
from __future__ import annotations

import re

VOICE_ENGINES = ("elevenlabs", "h3")
VOICE_LANGS = ("en", "hi", "mr")
DEFAULT_VOICE_ENGINE = {"en": "elevenlabs", "hi": "elevenlabs", "mr": "elevenlabs"}  # owner 2026-11-07 final (Option A)
H3_SPEECH_LANGS = ("en",)
NARRATOR = "NARRATOR"           # voice_map key of the off-screen narrator
ANCHOR_SOURCE = "first_approved_h3_clip"
SPEAKER_ID_RE = re.compile(r"^S\d+$")
ANCHOR_SEC = (2.0, 15.0)        # official Ref2VA audio clip length (README: each clip 2-15 s)
ANCHOR_TOTAL_SEC = 15.0         # official total audio length per Ref2VA prompt
ANCHOR_MAX_PER_SHOT = 3         # official Ref2VA audio clip count
ANCHOR_DESC_MAX_CHARS = 200


def engine_for(engines, lang):
    """The engine of one language: the given setting, else the default. Never raises."""
    return (engines or {}).get(lang) or DEFAULT_VOICE_ENGINE.get(lang)


def is_h3_voice(engines, lang="en"):
    return engine_for(engines, lang) == "h3"


def parse_overrides(text):
    """CLI form 'en=elevenlabs,hi=elevenlabs' -> {lang: engine}. Raises ValueError (VE-02) on a bad pair."""
    out = {}
    for part in [p.strip() for p in str(text or "").split(",") if p.strip()]:
        if "=" not in part:
            raise ValueError(f"VE-02 voice engine pair must be lang=engine, got {part!r}")
        lang, engine = (x.strip().lower() for x in part.split("=", 1))
        if lang not in VOICE_LANGS or engine not in VOICE_ENGINES:
            raise ValueError(f"VE-02 unknown voice setting {part!r} (langs {VOICE_LANGS}, engines {VOICE_ENGINES})")
        out[lang] = engine
    return out


def resolve_engines(output_languages, overrides=None):
    """voice_engine dict for the selected languages: defaults, then overrides. Keys outside the selection are dropped."""
    langs = list(output_languages or VOICE_LANGS)
    merged = {**DEFAULT_VOICE_ENGINE, **(overrides or {})}
    return {lang: merged[lang] for lang in langs if lang in merged}


def voice_engine_problems(engines, output_languages=None):
    """(errors, warnings) for a stage-1 voice_engine dict. VE-01 h3 for hi/mr, VE-02 bad key or value,
    VE-03 setting for a language not selected, VE-04 (warning) en=h3 is chosen: it breaks the render-once rule."""
    errs, warns = [], []
    if not isinstance(engines, dict):
        return [("VE-02", "voice_engine must be an object of language -> engine")], warns
    for lang, eng in engines.items():
        if lang not in VOICE_LANGS:
            errs.append(("VE-02", f"voice_engine language {lang!r} is not one of {VOICE_LANGS}"))
            continue
        if eng not in VOICE_ENGINES:
            errs.append(("VE-02", f"voice_engine {lang}={eng!r} is not one of {VOICE_ENGINES}"))
            continue
        if eng == "h3" and lang not in H3_SPEECH_LANGS:
            errs.append(("VE-01", f"H3 speech is English only: {lang} must use elevenlabs"))
        if output_languages is not None and lang not in output_languages:
            errs.append(("VE-03", f"voice_engine sets {lang} but the story does not output {lang}"))
    if engine_for(engines, "en") == "h3":
        warns.append(("VE-04", "en=h3 breaks the render-once rule: English gets a second H3 render with speech; adds H3 cost"))
    return errs, warns


def voice_map_problems(voice_map, characters, langs):
    """[(code, message)] for the bible voice_map {"CHAR-x" | "NARRATOR": {"en": id, "hi": id, "mr": id}}.
    VM-03 bad shape or key, VM-01 a key without a non-empty voice id for every selected language. Placeholder names are
    allowed (any non-empty string): the owner supplies the real ElevenLabs ids later."""
    if not isinstance(voice_map, dict):
        return [("VM-03", "voice_map must be an object keyed by character id (or NARRATOR)")]
    out = []
    for key, by_lang in voice_map.items():
        if key != NARRATOR and not (isinstance(key, str) and key.startswith("CHAR-") and key in (characters or {})):
            out.append(("VM-03", f"voice_map key {key!r} must be NARRATOR or a character id of the bible"))
            continue
        if not isinstance(by_lang, dict):
            out.append(("VM-03", f"voice_map.{key} must be an object of language -> voice id"))
            continue
        for lang in langs or ():
            vid = by_lang.get(lang)
            if not (isinstance(vid, str) and vid.strip()):
                out.append(("VM-01", f"voice_map.{key} has no voice id for {lang}"))
    return out


def anchor_problems(anchor):
    """[(code, message)] for one character's voice anchor. VA-03 on bad or missing fields.
    Form A (extracted): audio = path, duration_sec in 2-15 s. Form B (pending): audio = null and clip_shot_id names the
    first approved H3 clip the audio is extracted from (source = first_approved_h3_clip)."""
    if not isinstance(anchor, dict):
        return [("VA-03", "voice_anchor must be an object: audio, duration_sec, voice_description")]
    out = []
    if anchor.get("audio") is None and anchor.get("source") == ANCHOR_SOURCE:
        # pending: the first approved clip is not rendered yet; clip_shot_id may be null until it is known (VA-08 in the
        # linter until the audio is extracted)
        if anchor.get("clip_shot_id") not in (None, "") and not isinstance(anchor.get("clip_shot_id"), str):
            out.append(("VA-03", "voice_anchor.clip_shot_id must be a shot id or null"))
    else:
        if not (isinstance(anchor.get("audio"), str) and anchor["audio"].strip()):
            out.append(("VA-03", "voice_anchor.audio must be a non-empty path, or null with source and clip_shot_id"))
        d = anchor.get("duration_sec")
        if not (isinstance(d, (int, float)) and not isinstance(d, bool) and ANCHOR_SEC[0] <= d <= ANCHOR_SEC[1]):
            out.append(("VA-03", f"voice_anchor.duration_sec must be a number in {ANCHOR_SEC[0]}-{ANCHOR_SEC[1]} s"))
    desc = anchor.get("voice_description")
    if not (isinstance(desc, str) and desc.strip()):
        out.append(("VA-03", "voice_anchor.voice_description must be a non-empty sentence"))
    elif len(desc) > ANCHOR_DESC_MAX_CHARS or re.search(r"[<>\"]", desc):
        out.append(("VA-03", f"voice_anchor.voice_description must be plain text, <= {ANCHOR_DESC_MAX_CHARS} characters"))
    return out


def speaker_map_problems(smap, characters):
    """[(code, message)] for the story speaker map {"S1": "CHAR-..."}. SP-01 bad id, SP-02 unknown character,
    SP-03 one character under two speaker ids (the same voice would be two speakers)."""
    if not isinstance(smap, dict):
        return [("SP-01", "voice_speaker_map must be an object of speaker id -> character id")]
    out, seen = [], {}
    for sid, cid in smap.items():
        if not (isinstance(sid, str) and SPEAKER_ID_RE.match(sid)):
            out.append(("SP-01", f"speaker id {sid!r} must look like S1, S2, ..."))
            continue
        if not (isinstance(characters, dict) and cid in characters):
            out.append(("SP-02", f"{sid} maps to {cid!r}, which is not a character of the bible"))
            continue
        if cid in seen:
            out.append(("SP-03", f"{cid} is mapped by both {seen[cid]} and {sid}"))
        seen.setdefault(cid, sid)
    return out


def anchored_speakers(smap, characters, speaker_ids):
    """[(speaker_id, character_id, anchor)] for the given speaker ids in the given order (VA-01 when unmapped/no anchor)."""
    out = []
    for sid in speaker_ids:
        cid = (smap or {}).get(sid)
        anchor = ((characters or {}).get(cid) or {}).get("voice_anchor") if cid else None
        out.append((sid, cid, anchor))
    return out


def audio_ref_problems(anchors):
    """[(code, message)] for the <Audio N> references of one Ref2VA shot: VA-05 count over the official limit,
    VA-06 total length over the official limit. anchors: the voice_anchor dicts used by the shot."""
    out = []
    if len(anchors) > ANCHOR_MAX_PER_SHOT:
        out.append(("VA-05", f"{len(anchors)} voice anchors in one shot, Ref2VA allows {ANCHOR_MAX_PER_SHOT}"))
    total = sum(float(a.get("duration_sec") or 0) for a in anchors if isinstance(a, dict))
    if total > ANCHOR_TOTAL_SEC + 1e-9:
        out.append(("VA-06", f"voice anchors total {total:.2f} s, Ref2VA allows {ANCHOR_TOTAL_SEC:g} s"))
    return out
