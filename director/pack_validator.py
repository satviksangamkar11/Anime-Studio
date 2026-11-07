"""H3 V4 pack validator (contract: research/H3_V4_CONTRACT_2026-11-07.md, spec: research/OWNER_MASTER_PROMPT_V4_2026-11-07.txt).

API
  validate_stage(stage, data, bible=None, *, output_languages=None, lang_check=None) -> Report
      stage: story (stage 1) | bible (stage 2) | shots (stage 3: Step 5.5 self-check and the ML-* checks
      for *_by_lang rows; output_languages=None skips the language-set check; lang_check is an optional hook)
  self_check(shots, bible, reel_range=STUDIO_REEL_RANGE) -> Report
      the six Step 5.5 checks (S55-1..S55-6) plus REEL-01 for the reel range
  repair_loop(stage, produce, repair, max_retries=MAX_REPAIR_RETRIES, *, bible=None,
              output_languages=None, lang_check=None) -> (data, Report)
  validate_pack(pack_dir, legacy=False, *, output_languages=None, lang_check=None) -> Report
      reads files only, writes nothing; output_languages is read from stage_1*.json when not given
  duration_bucket(seconds) -> bucket name
Report = {"ok": bool, "errors": [{"code", "where", "message"}], "warnings": [...], "stats": {...}}
CLI: python director/pack_validator.py <pack_dir> [--legacy] [--json]   exit 0 ok, 1 errors, 2 usage

Conventions: a rule that the owner's spec leaves open is pinned here as a constant with a comment
(DENSITY_WINDOW, REHOOK_*, TIME_TOL, MOUTH_STATES, PEOPLE_WORDS, STYLE_*). Negative mentions
(for example "no 3D") are rejected too, because the text is what the model reads.
Legacy mode (old-format packs): ids, durations, lattice, <= 3 characters and reel range are errors;
every V4 column problem is reported as a warning.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from h3.shot_table_spec import (  # noqa: E402  (repo root is put on sys.path above)
    AUDIO_TRACK_KEYS,
    CAPTION,
    DENSITY_HOOKS,
    DURATION_BUCKETS,
    EXIT_RELEASE_SHOTS,
    FPS,
    HOOKS,
    LATTICE_N_MAX,
    LATTICE_N_MIN,
    LIGHTING_KEYS,
    MAX_CHARS_PER_SHOT,
    MAX_REPAIR_RETRIES,
    MAX_SHOT_SEC,
    MODES,
    PER_SECOND_KEYS,
    REFERENCE_ANCHOR_KEYS,
    SPEECH_LANGS,
    STORY_GATE_CHECKS,
    STRONG_HOOKS,
    STUDIO_REEL_RANGE,
    lattice,
    snap_seconds,
)
from h3 import voice_engine as ve  # noqa: E402  (voice rules shared with the H3 linter)
from h3.voice_engine import (  # noqa: E402
    anchor_problems,
    engine_for,
    speaker_map_problems,
    voice_engine_problems,
    voice_map_problems,
)

DENSITY_WINDOW = 3                    # "at least 1 of every 3 consecutive shots" (contract; not in shot_table_spec)
REHOOK_REEL_MIN_SEC = 45.0            # a re-hook is required on reels this long or longer
REHOOK_WINDOW_SEC = (25.0, 35.0)      # reading of "~30 s": a strong hook must start inside this window
TIME_TOL = 0.05                       # seconds, for per-second contiguity and the end of coverage
MOUTH_STATES = ("closed", "open_non_verbal_breath")
BIBLE_SECTIONS = ("characters", "environments", "props")
BIBLE_PREFIX = {"characters": "CHAR-", "environments": "ENV-", "props": "PROP-"}
PROMPT_KEYS = ("prompt", "card_prompt", "sheet_prompt")
# ponytail: word list, not an NLP check. Catches the obvious people/figure nouns in an ENV prompt.
PEOPLE_WORDS = re.compile(
    r"\b(?:characters?|people|persons?|crowds?|figures?|silhouettes?|hands?(?![-\w])|faces?|men|women|man|woman"
    r"|children|child|devotees?|villagers?|sages?|rishis?|humans?)\b",
    re.I,
)
STYLE_FORBIDDEN = [re.compile(p, re.I) for p in (r"\b3d\b", r"pixar", r"\bc4d\b", r"octane", r"cg\s+render",
                                                   r"neon\s+plastic", r"uniform\s+vector\s+lines?")]
STYLE_REQUIRED = (re.compile(r"hand[- ]drawn", re.I), re.compile(r"cel[- ]shad", re.I))
ROW_FIELDS = ("id", "episode", "route", "lattice_n", "pixel_frames", "latent_slots", "editorial_duration_sec",
              "continuity_handoff", "reference_anchors", "hook_type", "is_opening_0_2s_hook", "is_closing_hook",
              "deliberate_flip_marker", "per_second_directives", "audio_and_dialogue_track")
_STAGE_NAMES = {"story": "story", "stage_1": "story", "1": "story",
                "bible": "bible", "stage_2": "bible", "2": "bible",
                "shots": "shots", "shot_table": "shots", "stage_3": "shots", "3": "shots",
                "5": "passthrough", "stage_5": "passthrough", "captions": "passthrough"}   # 5: no V4 rule here
_RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*s?\s*$")


# ---------- small helpers ----------

def _e(errs, code, where, message):
    errs.append({"code": code, "where": where, "message": message})


def _rep(errs, warns, stats):
    return {"ok": not errs, "errors": errs, "warnings": warns, "stats": stats}


def _absorb(errs, warns, stats, rep):
    errs.extend(rep["errors"])
    warns.extend(rep["warnings"])
    stats.update(rep["stats"])


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _nonempty_str(x):
    return isinstance(x, str) and x.strip() != ""


def _d(x):
    return x if isinstance(x, dict) else {}


def _l(x):
    return x if isinstance(x, list) else []


def _side(text):
    """'left' or 'right' when the text names exactly one side, else None."""
    if not isinstance(text, str):
        return None
    t = text.lower()
    has_l, has_r = bool(re.search(r"\bleft\b", t)), bool(re.search(r"\bright\b", t))
    if has_l != has_r:
        return "left" if has_l else "right"
    return None


def _range(v):
    """(start, end) from "1.2-1.6s" or [1.2, 1.6]; None when malformed or empty."""
    if isinstance(v, str):
        m = _RANGE_RE.match(v)
        if not m:
            return None
        a, b = float(m.group(1)), float(m.group(2))
    elif isinstance(v, (list, tuple)) and len(v) == 2 and all(_is_num(x) for x in v):
        a, b = float(v[0]), float(v[1])
    else:
        return None
    return (a, b) if a < b else None


def duration_bucket(seconds):
    """Official duration bucket for a total in seconds ("custom" when none fits)."""
    for name, rng in DURATION_BUCKETS.items():
        if rng and rng[0] <= seconds <= rng[1]:
            return name
    return "custom"


def _bible_ids(bible):
    ids = set()
    for sec in BIBLE_SECTIONS:
        v = _d(bible).get(sec)
        if isinstance(v, dict):
            ids |= {k for k in v if isinstance(k, str)}
        elif isinstance(v, list):
            ids |= {x["id"] for x in v if isinstance(x, dict) and _nonempty_str(x.get("id"))}
    return ids


def _bible_entry(bible, sec, id_):
    v = _d(bible).get(sec)
    if not isinstance(id_, str):
        return None
    if isinstance(v, dict):
        return v.get(id_)
    for x in _l(v):
        if isinstance(x, dict) and x.get("id") == id_:
            return x
    return None


def _dur(r, legacy=False):
    if not isinstance(r, dict):
        return None
    e = r.get("editorial_duration_sec")
    if _is_num(e):
        return float(e)
    if legacy and _is_num(r.get("seconds")):
        return float(r["seconds"])
    return None


def _episodes(shots):
    eps = {}
    for i, r in enumerate(shots):
        if isinstance(r, dict):
            key = r.get("episode")
            eps.setdefault(key if isinstance(key, (int, str)) else None, []).append((i, r))
    return eps


def _characters(r):
    ids = {c["id"] for c in _l(r.get("cast")) if isinstance(c, dict) and _nonempty_str(c.get("id"))}
    ids |= {c["id"] for c in _l(_d(r.get("reference_anchors")).get("character_positions"))
            if isinstance(c, dict) and _nonempty_str(c.get("id"))}
    return ids


def _referenced_ids(r):
    ids = _characters(r)
    ids |= {p["id"] for p in _l(r.get("props")) if isinstance(p, dict) and _nonempty_str(p.get("id"))}
    ids |= {e["id"] for e in _l(_d(r.get("reference_anchors")).get("exited_character_status"))
            if isinstance(e, dict) and _nonempty_str(e.get("id"))}
    if _nonempty_str(r.get("set")):
        ids.add(r["set"])
    return ids


def _positions(r):
    out = {}
    for c in _l(_d(r.get("reference_anchors")).get("character_positions")):
        if isinstance(c, dict) and _nonempty_str(c.get("id")):
            out[c["id"]] = (_side(c.get("screen")), _side(c.get("facing")))
    return out


def _lighting_side(r):
    return _side(_d(_d(r.get("reference_anchors")).get("lighting_baseline")).get("key"))


# ---------- structure (V4 columns) ----------

def _check_continuity(r, w, errs):
    c = r.get("continuity_handoff")
    if not isinstance(c, dict):
        return _e(errs, "CONT-01", f"{w}.continuity_handoff", "must be an object: incoming, outgoing, loop_seam")
    for k in ("incoming", "outgoing"):
        if not _nonempty_str(c.get(k)):
            _e(errs, "CONT-01", f"{w}.continuity_handoff.{k}", "missing handoff text")
    if "loop_seam" not in c or (c["loop_seam"] is not None and not _nonempty_str(c["loop_seam"])):
        _e(errs, "CONT-01", f"{w}.continuity_handoff.loop_seam", "must be text or null")


def _check_anchors(r, w, errs):
    a = r.get("reference_anchors")
    if not isinstance(a, dict):
        return _e(errs, "ANCH-01", f"{w}.reference_anchors", "must be an object with the 4 sub-fields")
    for k in REFERENCE_ANCHOR_KEYS:
        if k not in a:
            _e(errs, "ANCH-01", f"{w}.reference_anchors.{k}", "missing sub-field")
    fl = a.get("fixed_landmarks")
    if "fixed_landmarks" in a and not (isinstance(fl, list) and fl and all(_nonempty_str(x) for x in fl)):
        _e(errs, "ANCH-01", f"{w}.reference_anchors.fixed_landmarks", "must be a non-empty list of strings")
    cp = a.get("character_positions")
    if "character_positions" in a and not (isinstance(cp, list) and all(
            isinstance(x, dict) and _nonempty_str(x.get("id")) and _nonempty_str(x.get("screen"))
            and _nonempty_str(x.get("depth")) for x in cp)):
        _e(errs, "ANCH-01", f"{w}.reference_anchors.character_positions", "each needs id, screen, depth")
    ecs = a.get("exited_character_status")
    if "exited_character_status" in a and not (isinstance(ecs, list) and all(
            isinstance(x, dict) and _nonempty_str(x.get("id")) and "left_after_shot" in x
            and isinstance(x.get("off_stage_shots"), int) and not isinstance(x.get("off_stage_shots"), bool)
            and isinstance(x.get("released"), bool) for x in ecs)):
        _e(errs, "ANCH-01", f"{w}.reference_anchors.exited_character_status",
           "each needs id, left_after_shot, off_stage_shots (int), released (bool)")
    lb = a.get("lighting_baseline")
    if "lighting_baseline" in a:
        if not isinstance(lb, dict):
            _e(errs, "ANCH-02", f"{w}.reference_anchors.lighting_baseline", "must be an object")
        else:
            for k in LIGHTING_KEYS:
                if k not in lb:
                    _e(errs, "ANCH-02", f"{w}.reference_anchors.lighting_baseline.{k}", "missing lighting key")


def _check_audio(r, w, errs):
    t = r.get("audio_and_dialogue_track")
    if not isinstance(t, dict):
        return _e(errs, "AUD-01", f"{w}.audio_and_dialogue_track", "must be an object with the 4 sub-fields")
    for k in AUDIO_TRACK_KEYS:
        if k not in t:
            _e(errs, "AUD-01", f"{w}.audio_and_dialogue_track.{k}", "missing sub-field")
    n = t.get("narration")
    if n is not None and not (isinstance(n, dict) and _nonempty_str(n.get("text"))
                              and n.get("language") in SPEECH_LANGS and _range(n.get("time_range"))):
        _e(errs, "AUD-02", f"{w}.audio_and_dialogue_track.narration",
           f"needs text, language in {SPEECH_LANGS}, time_range [start, end], or null")
    dl = t.get("dialogue")
    if "dialogue" in t:
        if not isinstance(dl, list):
            _e(errs, "AUD-03", f"{w}.audio_and_dialogue_track.dialogue", "must be a list")
        else:
            for j, x in enumerate(dl):
                tr = x.get("time_range") if isinstance(x, dict) else None
                if not (isinstance(x, dict) and _nonempty_str(x.get("speaker")) and _nonempty_str(x.get("text"))
                        and _nonempty_str(x.get("tone")) and (tr == [] or _range(tr))):
                    _e(errs, "AUD-03", f"{w}.audio_and_dialogue_track.dialogue[{j}]",
                       "needs speaker, text, tone and time_range ([] if none)")
    sfx = t.get("sfx_cues")
    if "sfx_cues" in t:
        if not (isinstance(sfx, list) and sfx):
            _e(errs, "AUD-04", f"{w}.audio_and_dialogue_track.sfx_cues", "mandatory in pure-Foley mode: non-empty list")
        else:
            for j, x in enumerate(sfx):
                if not (isinstance(x, dict) and _range(x.get("time_range")) and _nonempty_str(x.get("sfx_key"))
                        and _nonempty_str(x.get("description"))):
                    _e(errs, "AUD-04", f"{w}.audio_and_dialogue_track.sfx_cues[{j}]",
                       "needs time_range (e.g. '1.2-1.6s'), sfx_key, description")
    pn = t.get("performance_notes")
    if "performance_notes" in t:
        if not isinstance(pn, dict) or not _nonempty_str(pn.get("text")):
            _e(errs, "AUD-05", f"{w}.audio_and_dialogue_track.performance_notes", "needs text and the mouth fields")
        else:
            if pn.get("narrator_mouth_closed") is not True:
                _e(errs, "AUD-05", f"{w}.audio_and_dialogue_track.performance_notes.narrator_mouth_closed", "must be true")
            ms = pn.get("mouth_state")
            if not isinstance(ms, dict) or not ms:
                _e(errs, "AUD-05", f"{w}.audio_and_dialogue_track.performance_notes.mouth_state", "needs a per-second map")
            else:
                for sec, v in ms.items():
                    if v not in MOUTH_STATES:
                        _e(errs, "AUD-05", f"{w}.audio_and_dialogue_track.performance_notes.mouth_state.{sec}",
                           f"{v!r} is not one of {MOUTH_STATES}")


def _check_rows(rows, errs):
    """Column completeness of every row (stage 3 structure). Ids, lattice, timing and hooks are self_check's job."""
    seen = {}
    for i, r in enumerate(rows):
        w = f"shots[{i}]"
        if not isinstance(r, dict):
            _e(errs, "ROW-01", w, "shot row must be an object")
            continue
        for k in ROW_FIELDS:
            if k not in r:
                _e(errs, "ROW-02", f"{w}.{k}", f"missing V4 field {k}")
        sid = r.get("id")
        if "id" in r and not _nonempty_str(sid):
            _e(errs, "ROW-02", f"{w}.id", "id must be a non-empty string")
        elif _nonempty_str(sid):
            if sid in seen:
                _e(errs, "ROW-03", w, f"duplicate id {sid} (also shots[{seen[sid]}])")
            seen.setdefault(sid, i)
        if "route" in r and r["route"] not in MODES:
            _e(errs, "ROW-04", f"{w}.route", f"{r['route']!r} is not one of {MODES}")
        if "continuity_handoff" in r:
            _check_continuity(r, w, errs)
        if "reference_anchors" in r:
            _check_anchors(r, w, errs)
        if "hook_type" in r and r["hook_type"] not in HOOKS:
            _e(errs, "HOOK-01", f"{w}.hook_type", f"{r['hook_type']!r} is not one of {HOOKS}")
        for k in ("is_opening_0_2s_hook", "is_closing_hook"):
            if k in r and not isinstance(r[k], bool):
                _e(errs, "HOOK-02", f"{w}.{k}", "must be true or false")
        if "deliberate_flip_marker" in r and r["deliberate_flip_marker"] is not None \
                and not _nonempty_str(r["deliberate_flip_marker"]):
            _e(errs, "ROW-02", f"{w}.deliberate_flip_marker", "must be text or null")
        if "audio_and_dialogue_track" in r:
            _check_audio(r, w, errs)


# ---------- multilingual rows (owner addendum 2026-11-07: en / hi / mr, one, two or all) ----------
# Codes: ML-01 malformed *_by_lang, ML-02 unknown language code, ML-03 missing language or key,
# ML-04 primary narration language not in output_languages, ML-05 time ranges differ across languages,
# ML-06 narration beyond the shot's editorial duration, ML-07 caption card over CAPTION max_words,
# ML-08 flagged by the caller's lang_check hook (agent F's validator plugs in there; not imported here).
BY_LANG_KEYS = ("narration_by_lang", "dialogue_by_lang", "captions_by_lang")


def _by_lang(r, key):
    """*_by_lang may sit inside audio_and_dialogue_track or on the row itself; the track wins."""
    track = _d(r.get("audio_and_dialogue_track"))
    if track.get(key) is not None:
        return track[key]
    return r.get(key)


def _range_key(rng):
    return (round(rng[0], 3), round(rng[1], 3))


def _hook_flags(res):
    """lang_check may return None (pass), a list of flags, or {"ok": bool, "flags": [...]}."""
    if res is None:
        return []
    if isinstance(res, dict):
        flags = [str(f) for f in _l(res.get("flags"))]
        if res.get("ok") is False and not flags:
            flags = ["flagged"]
        return flags if (res.get("ok") is False or flags) else []
    if isinstance(res, (list, tuple)):
        return [str(f) for f in res]
    return [str(res)]


def _compare_timing(w, key, seqs, errs):
    """Every language of one *_by_lang block must carry the same time ranges, in the same order."""
    if len({tuple(s) for s in seqs.values()}) > 1:
        _e(errs, "ML-05", f"{w}.{key}", f"time ranges differ across languages: {sorted(seqs)}")


def _card_seqs(w, key, by, errs, check_words=False):
    seqs = {}
    for lang, lst in by.items():
        if not isinstance(lst, list):
            _e(errs, "ML-01", f"{w}.{key}.{lang}", "must be a list of cards")
            continue
        seq = []
        for j, x in enumerate(lst):
            where = f"{w}.{key}.{lang}[{j}]"
            if not isinstance(x, dict) or not _nonempty_str(x.get("text")):
                _e(errs, "ML-01", where, "needs text")
                seq.append("invalid")
                continue
            tr = x.get("time_range")
            rng = None if tr == [] else _range(tr)
            if tr == []:
                seq.append("none")
            elif rng is None:
                _e(errs, "ML-01", f"{where}.time_range", "needs [start, end] with start < end")
                seq.append("invalid")
            else:
                seq.append(_range_key(rng))
            if check_words and len(x["text"].split()) > CAPTION["max_words"]:
                _e(errs, "ML-07", where, f"{len(x['text'].split())} words in one card (max {CAPTION['max_words']})")
        seqs[lang] = seq
    return seqs


def _lang_texts(found, primary, track, output_languages):
    """(lang, text, where) for every text the lang_check hook should see."""
    out = []
    if found:
        for lang, e in _d(found.get("narration_by_lang")).items():
            if isinstance(e, dict) and _nonempty_str(e.get("text")):
                out.append((lang, e["text"], f"narration_by_lang.{lang}"))
        for key in ("dialogue_by_lang", "captions_by_lang"):
            for lang, lst in _d(found.get(key)).items():
                for j, x in enumerate(_l(lst)):
                    if isinstance(x, dict) and _nonempty_str(x.get("text")):
                        out.append((lang, x["text"], f"{key}.{lang}[{j}]"))
        return out
    lang = primary.get("language") if primary else (
        output_languages[0] if output_languages and len(output_languages) == 1 else None)
    if primary and _nonempty_str(primary.get("text")):
        out.append((lang, primary["text"], "narration"))
    for j, x in enumerate(_l(track.get("dialogue"))):
        if isinstance(x, dict) and _nonempty_str(x.get("text")):
            out.append((lang, x["text"], f"dialogue[{j}]"))
    return out


def _check_languages(rows, output_languages, lang_check, errs):
    """Every language of every multilingual row, with its own timing; single-language rows keep the old checks."""
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        w = f"shots[{i}]"
        track = _d(r.get("audio_and_dialogue_track"))
        primary = track.get("narration") if isinstance(track.get("narration"), dict) else None
        editorial = _dur(r)
        found = {k: _by_lang(r, k) for k in BY_LANG_KEYS if _by_lang(r, k) is not None}
        prng = _range(primary.get("time_range")) if primary else None
        if prng and editorial is not None and prng[1] > editorial + TIME_TOL:   # single-language rows too
            _e(errs, "ML-06", f"{w}.audio_and_dialogue_track.narration.time_range",
               f"narration ends at {prng[1]} s, shot is {editorial} s")
        for k, by in found.items():
            if not isinstance(by, dict):
                _e(errs, "ML-01", f"{w}.{k}", "must be an object keyed by language code")
                continue
            for lang in by:
                if lang not in SPEECH_LANGS:
                    _e(errs, "ML-02", f"{w}.{k}.{lang}", f"unknown language code {lang!r}; use one of {SPEECH_LANGS}")
        if found:
            for k in BY_LANG_KEYS:
                if k not in found:
                    _e(errs, "ML-03", f"{w}.{k}", "multilingual row is missing this key")
            if output_languages is not None:
                for k, by in found.items():
                    for lang in (output_languages if isinstance(by, dict) else ()):
                        if lang not in by:
                            _e(errs, "ML-03", f"{w}.{k}.{lang}", f"no {lang} text for this shot")
        elif output_languages is not None and len(output_languages) > 1:
            _e(errs, "ML-03", w, f"story has output_languages {output_languages} but this row has no *_by_lang text")
        if primary and output_languages is not None and primary.get("language") not in output_languages:
            _e(errs, "ML-04", f"{w}.audio_and_dialogue_track.narration.language",
               f"primary language {primary.get('language')!r} is not in output_languages {output_languages}")
        nb = found.get("narration_by_lang")
        if isinstance(nb, dict):
            seqs = {}
            for lang, e in nb.items():
                rng = _range(e.get("time_range")) if isinstance(e, dict) else None
                if not (isinstance(e, dict) and _nonempty_str(e.get("text")) and rng):
                    _e(errs, "ML-01", f"{w}.narration_by_lang.{lang}", "needs text and time_range [start, end]")
                    seqs[lang] = ["invalid"]
                    continue
                if e.get("language") not in (None, lang):      # the block's key is the language; a wrong label is copied into the flat mirror
                    _e(errs, "ML-01", f"{w}.narration_by_lang.{lang}.language", f"language {e.get('language')!r} does not match key {lang!r}")
                seqs[lang] = [_range_key(rng)]
                if editorial is not None and rng[1] > editorial + TIME_TOL:
                    _e(errs, "ML-06", f"{w}.narration_by_lang.{lang}.time_range",
                       f"{lang} narration ends at {rng[1]} s, shot is {editorial} s")
            if primary and _range(primary.get("time_range")):
                seqs["primary"] = [_range_key(_range(primary["time_range"]))]
            _compare_timing(w, "narration_by_lang", seqs, errs)
        if isinstance(found.get("dialogue_by_lang"), dict):
            _compare_timing(w, "dialogue_by_lang",
                            _card_seqs(w, "dialogue_by_lang", found["dialogue_by_lang"], errs), errs)
        if isinstance(found.get("captions_by_lang"), dict):
            _compare_timing(w, "captions_by_lang",
                            _card_seqs(w, "captions_by_lang", found["captions_by_lang"], errs, check_words=True), errs)
        if lang_check is not None:
            for lang, text, where in _lang_texts(found, primary, track, output_languages):
                flags = _hook_flags(lang_check(text, lang))
                if flags:
                    _e(errs, "ML-08", f"{w}.{where}", f"language check flagged {lang}: {'; '.join(flags)}")


# ---------- Step 5.5 self-check (S55-1..S55-6) ----------

def _s55_1(eps, errs):
    for ep, items in eps.items():
        rows = [r for _, r in items]
        hooks = [r.get("hook_type") for r in rows]
        for k in range(len(rows) - DENSITY_WINDOW + 1):
            if not any(h in DENSITY_HOOKS for h in hooks[k:k + DENSITY_WINDOW]):
                ids = [rows[k + j].get("id") for j in range(DENSITY_WINDOW)]
                _e(errs, "S55-1", f"shots[{items[k][0]}]",
                   f"episode {ep}: {ids} has no reveal/reversal/callback (1 of every {DENSITY_WINDOW} needed)")
        if rows:
            first, last = items[0], items[-1]
            if first[1].get("is_opening_0_2s_hook") is not True or first[1].get("hook_type") not in STRONG_HOOKS:
                _e(errs, "S55-1", f"shots[{first[0]}]",
                   f"episode {ep}: opening shot must set is_opening_0_2s_hook and use one of {STRONG_HOOKS}")
            if last[1].get("is_closing_hook") is not True or last[1].get("hook_type") not in STRONG_HOOKS:
                _e(errs, "S55-1", f"shots[{last[0]}]",
                   f"episode {ep}: closing shot must set is_closing_hook and use one of {STRONG_HOOKS}")
        total = sum(_dur(r) or 0.0 for r in rows)
        if total >= REHOOK_REEL_MIN_SEC:
            lo, hi = REHOOK_WINDOW_SEC
            t, found = 0.0, False
            for r in rows:
                if lo <= t <= hi and r.get("hook_type") in STRONG_HOOKS:
                    found = True
                t += _dur(r) or 0.0
            if not found:
                _e(errs, "S55-1", f"episode {ep}",
                   f"reel of {round(total, 1)} s needs a strong re-hook starting {lo}-{hi} s in")


def _s55_2(shots, errs):
    for i, r in enumerate(shots):
        if not isinstance(r, dict):
            continue
        w = f"shots[{i}]"
        e = _dur(r)
        if e is None or not 0 < e <= MAX_SHOT_SEC:
            _e(errs, "S55-2", f"{w}.editorial_duration_sec", f"must be > 0 and <= {MAX_SHOT_SEC} s")
        n = r.get("lattice_n")
        if not (isinstance(n, int) and not isinstance(n, bool) and LATTICE_N_MIN <= n <= LATTICE_N_MAX):
            _e(errs, "S55-2", f"{w}.lattice_n", f"must be an int {LATTICE_N_MIN}..{LATTICE_N_MAX}")
            continue
        L = lattice(n)
        if r.get("pixel_frames") != L["pixel_frames"]:
            _e(errs, "S55-2", f"{w}.pixel_frames", f"must be {L['pixel_frames']} (5 + 17n) for n={n}")
        if r.get("latent_slots") != L["latent_slots"]:
            _e(errs, "S55-2", f"{w}.latent_slots", f"must be {L['latent_slots']} (5n + 2) for n={n}")
        pf = r.get("pixel_frames")
        if e is not None and _is_num(pf) and e > pf / FPS + 1e-9:
            _e(errs, "S55-2", f"{w}.editorial_duration_sec", "trimmed duration is longer than the rendered frames")


def _s55_3(shots, errs):
    for i, r in enumerate(shots):
        if isinstance(r, dict):
            ids = _characters(r)
            if len(ids) > MAX_CHARS_PER_SHOT:
                _e(errs, "S55-3", f"shots[{i}]",
                   f"{len(ids)} significant characters (max {MAX_CHARS_PER_SHOT}): {sorted(ids)}")


def _s55_4(shots, bible, errs):
    for i, r in enumerate(shots):
        if not isinstance(r, dict):
            continue
        w = f"shots[{i}].reference_anchors"
        a = _d(r.get("reference_anchors"))
        fl = {x.lower() for x in _l(a.get("fixed_landmarks")) if isinstance(x, str)}
        env = _bible_entry(bible, "environments", r.get("set")) if isinstance(bible, dict) else None
        for x in _l(_d(env).get("continuity_landmarks")):
            if _nonempty_str(x) and x.lower() not in fl:
                _e(errs, "S55-4", f"{w}.fixed_landmarks", f"does not inherit ENV landmark {x!r} from {r.get('set')}")
        lb = _d(a.get("lighting_baseline"))
        for k in ("key", "fill", "rim"):
            if not _nonempty_str(lb.get(k)):
                _e(errs, "S55-4", f"{w}.lighting_baseline.{k}", "lighting is not inherited (empty)")
        for x in _l(a.get("exited_character_status")):
            if isinstance(x, dict) and x.get("released") is True:
                off = x.get("off_stage_shots")
                if not (isinstance(off, int) and not isinstance(off, bool) and off >= EXIT_RELEASE_SHOTS):
                    _e(errs, "S55-4", f"{w}.exited_character_status",
                       f"{x.get('id')} released after {off} off-stage shots; release needs {EXIT_RELEASE_SHOTS} consecutive")


def _s55_5(shots, errs):
    for i, r in enumerate(shots):
        if not isinstance(r, dict):
            continue
        w = f"shots[{i}].per_second_directives"
        e = _dur(r)
        ps = r.get("per_second_directives")
        if not (isinstance(ps, list) and ps):
            _e(errs, "S55-5", w, "needs per-second brackets from 0.00 s")
            continue
        prev_end = 0.0
        for j, b in enumerate(ps):
            bw = f"{w}[{j}]"
            if not (isinstance(b, dict) and _is_num(b.get("t0")) and _is_num(b.get("t1"))):
                _e(errs, "S55-5", bw, "bracket needs numeric t0 and t1")
                continue
            t0, t1 = float(b["t0"]), float(b["t1"])
            if abs(t0 - prev_end) > TIME_TOL:
                _e(errs, "S55-5", bw, f"starts at {t0} after {round(prev_end, 2)} (gap or overlap)")
            if t1 <= t0:
                _e(errs, "S55-5", bw, "timestamps must strictly increase")
            for k in PER_SECOND_KEYS:
                if not _nonempty_str(b.get(k)):
                    _e(errs, "S55-5", f"{bw}.{k}", "required element missing")
            prev_end = t1
        if e is not None and abs(prev_end - e) > TIME_TOL:
            _e(errs, "S55-5", w, f"coverage ends at {round(prev_end, 2)} s, shot is {e} s")


def _s55_6(shots, bible, errs, warns):
    bible_ids = _bible_ids(bible) if isinstance(bible, dict) else None
    if bible_ids is None:
        warns.append({"code": "S55-6", "where": "bible", "message": "no bible supplied: id references not checked"})
    for i, r in enumerate(shots):
        if isinstance(r, dict) and bible_ids is not None:
            for x in sorted(_referenced_ids(r) - bible_ids):
                _e(errs, "S55-6", f"shots[{i}]", f"referenced id {x} is not in the bible")
    for i in range(1, len(shots)):
        prev, cur = shots[i - 1], shots[i]
        if not (isinstance(prev, dict) and isinstance(cur, dict)) or prev.get("episode") != cur.get("episode"):
            continue
        pp, cp = _positions(prev), _positions(cur)
        flips = []
        for cid in sorted(set(pp) & set(cp)):
            for label, a, b in (("screen", pp[cid][0], cp[cid][0]), ("facing", pp[cid][1], cp[cid][1])):
                if a and b and a != b:
                    flips.append(f"{cid} {label} {a}->{b}")
        la, lb = _lighting_side(prev), _lighting_side(cur)
        if la and lb and la != lb:
            flips.append(f"lighting {la}->{lb}")
        if flips and not _nonempty_str(cur.get("deliberate_flip_marker")):
            _e(errs, "S55-6", f"shots[{i}].deliberate_flip_marker",
               f"unmarked flip from {prev.get('id')} to {cur.get('id')}: {'; '.join(flips)}")


def _reel(shots, reel_range, errs, stats, legacy=False):
    lo, hi = reel_range
    out = {}
    for ep, items in _episodes(shots).items():
        total = sum(_dur(r, legacy) or 0.0 for _, r in items)
        out[str(ep)] = {"shots": len(items), "seconds": round(total, 3), "bucket": duration_bucket(total)}
        if not lo <= total <= hi:
            _e(errs, "REEL-01", f"episode {ep}", f"reel total {round(total, 2)} s is outside the preset {lo}-{hi} s")
    stats["episodes"] = out


def self_check(shots, bible, reel_range=STUDIO_REEL_RANGE):
    """The six Step 5.5 checks (S55-1..S55-6) over a V4 shot table, plus the reel range (REEL-01)."""
    errs, warns, stats = [], [], {}
    if not isinstance(shots, list):
        _e(errs, "SHOT-00", "shots", "shot table must be a list of rows")
        return _rep(errs, warns, stats)
    _s55_1(_episodes(shots), errs)
    _s55_2(shots, errs)
    _s55_3(shots, errs)
    _s55_4(shots, bible, errs)
    _s55_5(shots, errs)
    _s55_6(shots, bible, errs, warns)
    _reel(shots, reel_range, errs, stats)
    stats["shots"] = len(shots)
    return _rep(errs, warns, stats)


# ---------- stages ----------

def _validate_story(data):
    errs, warns, stats = [], [], {}
    if not isinstance(data, dict):
        _e(errs, "STAGE-01", "story", "story data must be an object")
        return _rep(errs, warns, stats)
    if "output_languages" in data:
        ol = data["output_languages"]
        if not (isinstance(ol, list) and ol and all(x in SPEECH_LANGS for x in ol) and len(set(ol)) == len(ol)):
            _e(errs, "STORY-04", "output_languages", f"must be a non-empty, non-repeating subset of {SPEECH_LANGS}")
        elif "output_language" in data and data["output_language"] != ol[0]:
            _e(errs, "STORY-04", "output_language", "must equal output_languages[0] (the primary)")
    if "voice_engine" in data:
        e, w = voice_engine_problems(data["voice_engine"], data.get("output_languages"))
        errs.extend({"code": c, "where": "voice_engine", "message": m} for c, m in e)
        warns.extend({"code": c, "where": "voice_engine", "message": m} for c, m in w)
    gate = data.get("story_gate_checks")
    if not isinstance(gate, dict):
        _e(errs, "STORY-01", "story_gate_checks", "missing story_gate_checks object")
        gate = {}
    for name in STORY_GATE_CHECKS:
        c = gate.get(name)
        if not isinstance(c, dict) or "pass" not in c:
            _e(errs, "STORY-01", f"story_gate_checks.{name}", "missing gate check (needs pass and evidence)")
            continue
        if c["pass"] is not True:
            _e(errs, "STORY-02", f"story_gate_checks.{name}.pass", "gate check must pass (true)")
        if not _nonempty_str(c.get("evidence")):
            _e(errs, "STORY-03", f"story_gate_checks.{name}.evidence", "evidence must be non-empty")
    return _rep(errs, warns, stats)


def _collect_strings(node, path, out):
    if isinstance(node, str):
        out.append((path, node))
    elif isinstance(node, dict):
        for k, v in node.items():
            _collect_strings(v, f"{path}.{k}", out)
    elif isinstance(node, list):
        for j, v in enumerate(node):
            _collect_strings(v, f"{path}[{j}]", out)
    return out


def _style_fields(node, path="bible", out=None):
    """Every string under a style/prompt/line/shading key, at any depth."""
    out = [] if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            key = str(k).lower()
            if "style" in key or "prompt" in key or key in ("line", "shading"):
                _collect_strings(v, f"{path}.{k}", out)
            else:
                _style_fields(v, f"{path}.{k}", out)
    elif isinstance(node, list):
        for j, v in enumerate(node):
            _style_fields(v, f"{path}[{j}]", out)
    return out


def _prompt(entry):
    for k in PROMPT_KEYS:
        if _nonempty_str(entry.get(k)):
            return entry[k]
    return ""


def _validate_bible(data):
    errs, warns, stats = [], [], {}
    if not isinstance(data, dict):
        _e(errs, "STAGE-01", "bible", "bible data must be an object")
        return _rep(errs, warns, stats)
    for sec in BIBLE_SECTIONS:
        v = data.get(sec)
        if not isinstance(v, dict):
            _e(errs, "BIBLE-01", sec, "canonical layout: must be an object keyed by id")
            continue
        for id_, entry in v.items():
            w = f"{sec}.{id_}"
            if not str(id_).startswith(BIBLE_PREFIX[sec]):
                _e(errs, "BIBLE-02", w, f"id must start with {BIBLE_PREFIX[sec]}")
            if not isinstance(entry, dict):
                _e(errs, "BIBLE-02", w, "entry must be an object")
                continue
            p = _prompt(entry)
            if sec == "environments":
                if not p:
                    _e(errs, "BIBLE-03", w, "ENV needs an environment-only card prompt")
                elif PEOPLE_WORDS.search(p):
                    _e(errs, "BIBLE-04", w, f"ENV prompt names people or figures: {PEOPLE_WORDS.search(p).group(0)!r}")
                lm = entry.get("continuity_landmarks")
                if not (isinstance(lm, list) and lm and all(_nonempty_str(x) for x in lm)):
                    _e(errs, "BIBLE-05", f"{w}.continuity_landmarks", "ENV needs a non-empty list of landmarks")
            if sec == "characters":
                if not p:
                    _e(errs, "BIBLE-06", w, "CHAR needs a 16:9 labeled sheet prompt")
                else:
                    if not re.search(r"16\s*:\s*9", p):
                        _e(errs, "BIBLE-06", w, "CHAR sheet must be 16:9")
                    if not re.search(r"label", p, re.I):
                        _e(errs, "BIBLE-06", w, "CHAR sheet must be labeled")
                    if not re.search(r"plain\s+neutral\s+(?:backdrop|background)", p, re.I):
                        _e(errs, "BIBLE-06", w, "CHAR sheet must sit on a plain neutral backdrop")
    if "voice_map" in data:  # ElevenLabs voice ids per character and language (shape here; per-language presence in shots)
        for code, msg in voice_map_problems(data["voice_map"], data.get("characters"), None):
            _e(errs, code, "voice_map", msg)
    if "voice_speaker_map" in data:  # English H3 speech only (voice_engine en=h3): one speaker map for the whole reel
        smap, chars = data["voice_speaker_map"], data.get("characters")
        chars = chars if isinstance(chars, dict) else {}
        for code, msg in speaker_map_problems(smap, chars):
            _e(errs, code, "voice_speaker_map", msg)
        for sid, cid in (smap.items() if isinstance(smap, dict) else ()):
            if cid in chars:
                anchor = chars[cid].get("voice_anchor") if isinstance(chars[cid], dict) else None
                if anchor is None:
                    _e(errs, "VA-01", f"characters.{cid}.voice_anchor", f"{sid} speaks but the character has no voice anchor")
                for code, msg in anchor_problems(anchor) if anchor is not None else ():
                    _e(errs, code, f"characters.{cid}.voice_anchor", msg)
    style = _style_fields(data)
    for path, s in style:
        for rx in STYLE_FORBIDDEN:
            if rx.search(s):
                _e(errs, "BIBLE-07", path, f"style lock forbids {rx.search(s).group(0)!r} (2D hand-drawn anime only)")
    joined = " ".join(s for _, s in style)
    for rx, label in zip(STYLE_REQUIRED, ("hand-drawn", "cel-shaded")):
        if not rx.search(joined):
            _e(errs, "BIBLE-08", "bible", f"style lock must state '{label}' 2D anime wording")
    stats["style_fields"] = len(style)
    return _rep(errs, warns, stats)


def _check_voice(rows, bible, engines, output_languages, errs, warns):
    """Voice rules per selected language (engines=None skips them: no voice setting given).
    elevenlabs (default, all languages): every dialogue line of that language has a speaker with a voice_map entry for
    that language (VM-01); English/Hindi/Marathi narration needs voice_map.NARRATOR for that language (VM-01); a shot's
    voice_id, when written, must equal the bible voice_map (VM-02): one voice id per character, every shot and reel.
    h3 (English only, optional): each English line's speaker is in voice_speaker_map (VA-01), the character has a voice
    anchor (VA-01) and the line carries the anchor's voice description verbatim (VA-02). VE-05: English narration on h3
    has no H3 voice path yet (owner decision)."""
    if engines is None:
        return
    vm = _d(bible).get("voice_map")
    vm = vm if isinstance(vm, dict) else {}
    smap, chars = _d(bible).get("voice_speaker_map"), _d(bible).get("characters")
    smap = smap if isinstance(smap, dict) else {}
    chars = chars if isinstance(chars, dict) else {}
    langs = list(output_languages or [])
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        w = str(r.get("id", f"row {i}"))
        track = _d(r.get("audio_and_dialogue_track"))
        narr = track.get("narration")
        primary = narr.get("language") if isinstance(narr, dict) else (langs[0] if langs else None)
        if isinstance(narr, dict) and isinstance(narr.get("language"), str) and narr["language"] and engine_for(engines, narr["language"]) == "elevenlabs":
            if not _d(vm.get(ve.NARRATOR)).get(narr["language"]):
                _e(errs, "VM-01", f"{w}.narration", f"no voice_map.{ve.NARRATOR} voice id for {narr['language']}")
        for lang in _d(_by_lang(r, "narration_by_lang")):   # multilingual narration: each ElevenLabs language needs its narrator voice
            if engine_for(engines, lang) == "elevenlabs" and not _d(vm.get(ve.NARRATOR)).get(lang):
                _e(errs, "VM-01", f"{w}.narration_by_lang.{lang}", f"no voice_map.{ve.NARRATOR} voice id for {lang}")
        if isinstance(narr, dict) and narr.get("language") == "en" and engine_for(engines, "en") == "h3":
            warns.append({"code": "VE-05", "where": f"{w}.narration",
                          "message": "English narration on h3 has no H3 voice path yet: needs an owner decision"})
        for lang in langs:
            lines = [(f"{w}.dialogue[{j}]", x) for j, x in enumerate(_l(track.get("dialogue")) if primary == lang else [])]
            by = _d(_by_lang(r, "dialogue_by_lang")).get(lang)
            lines += [(f"{w}.dialogue_by_lang.{lang}[{j}]", x) for j, x in enumerate(_l(by))]
            if engine_for(engines, lang) == "elevenlabs":
                for where, x in lines:
                    if not isinstance(x, dict):
                        continue
                    entry = _d(vm.get(x.get("speaker")))
                    if not str(entry.get(lang) or "").strip():
                        _e(errs, "VM-01", where, f"speaker {x.get('speaker')!r} has no voice_map id for {lang}")
                    elif "voice_id" in x and x["voice_id"] != entry.get(lang):
                        _e(errs, "VM-02", where, "voice_id must equal the bible voice_map id (same voice every shot)")
            elif lang == "en" and engine_for(engines, "en") == "h3":
                for where, x in lines:
                    if not isinstance(x, dict):
                        continue
                    cid = smap.get(x.get("speaker"))
                    if cid is None:
                        _e(errs, "VA-01", where, f"speaker {x.get('speaker')!r} has no entry in voice_speaker_map")
                        continue
                    anchor = _d(chars.get(cid)).get("voice_anchor")
                    if not anchor:
                        _e(errs, "VA-01", where, f"{cid} speaks English but has no voice anchor")
                        continue
                    if x.get("voice_description") != anchor.get("voice_description"):
                        _e(errs, "VA-02", where, "voice_description must equal the character's anchor sentence verbatim (same in every shot)")


def validate_stage(stage, data, bible=None, *, output_languages=None, lang_check=None, voice_engines=None):
    """output_languages: the story's selected languages (None = do not check the language set).
    lang_check(text, lang) -> None | list of flags | {"ok", "flags"}: optional hook for the language-quality validator.
    voice_engines: the story's voice_engine dict; None skips the English H3 voice checks (VA-*)."""
    kind = _STAGE_NAMES.get(str(stage).strip().lower())
    if kind is None:
        return _rep([{"code": "STAGE-00", "where": "stage", "message": f"unknown stage {stage!r}"}], [], {})
    if kind == "story":
        return _validate_story(data)
    if kind == "bible":
        return _validate_bible(data)
    if kind == "passthrough":
        return _rep([], [{"code": "STAGE-02", "where": "stage", "message":
                          f"stage {stage!r} has no pack_validator rule; its own gate checks it"}], {})
    rows = data.get("shots") if isinstance(data, dict) else data
    errs, warns, stats = [], [], {}
    if not isinstance(rows, list):
        _e(errs, "SHOT-00", "shots", "shot table must be a list of rows (or {'shots': [...]})")
        return _rep(errs, warns, stats)
    _check_rows(rows, errs)
    _check_languages(rows, output_languages, lang_check, errs)
    _check_voice(rows, bible, voice_engines, output_languages, errs, warns)
    sc = self_check(rows, bible)
    _absorb(errs, warns, stats, sc)
    return _rep(errs, warns, stats)


def repair_loop(stage, produce, repair, max_retries=MAX_REPAIR_RETRIES, *, bible=None,
                output_languages=None, lang_check=None, voice_engines=None):
    """produce() once; while invalid, repair(errors) at most max_retries times. Returns (last data, last Report)."""
    kw = {"output_languages": output_languages, "lang_check": lang_check, "voice_engines": voice_engines}
    data = produce()
    report = validate_stage(stage, data, bible, **kw)
    for _ in range(max(0, int(max_retries))):
        if report["ok"]:
            break
        data = repair(report["errors"])
        report = validate_stage(stage, data, bible, **kw)
    return data, report


# ---------- legacy (old-format packs) ----------

def _legacy_checks(shots, bible, errs, warns, stats):
    if not isinstance(shots, list):
        _e(errs, "SHOT-00", "shots", "shot table must be a list of rows")
        return
    bible_ids = _bible_ids(bible) if isinstance(bible, dict) else None
    for i, r in enumerate(shots):
        if not isinstance(r, dict):
            continue
        w = f"shots[{i}]"
        render = float(r["seconds"]) if _is_num(r.get("seconds")) else _dur(r, legacy=True)
        if render is None or not 0 < render <= MAX_SHOT_SEC:
            _e(errs, "S55-2", f"{w}.seconds", f"duration must be > 0 and <= {MAX_SHOT_SEC} s")
        else:
            snap = snap_seconds(render)
            if round(render, 1) != round(snap["seconds"], 1):   # old packs write seconds to one decimal
                _e(errs, "S55-2", f"{w}.seconds",
                   f"{render} s is not on the H3 lattice (nearest {snap['seconds']} s, n={snap['n']})")
        ed = _dur(r, legacy=True)
        if ed is not None and not 0 < ed <= MAX_SHOT_SEC:
            _e(errs, "S55-2", f"{w}.editorial_duration_sec", f"must be > 0 and <= {MAX_SHOT_SEC} s")
        ids = _characters(r)
        if len(ids) > MAX_CHARS_PER_SHOT:
            _e(errs, "S55-3", w, f"{len(ids)} significant characters (max {MAX_CHARS_PER_SHOT})")
        if bible_ids is not None:
            for x in sorted(_referenced_ids(r) - bible_ids):
                _e(errs, "S55-6", w, f"referenced id {x} is not in the bible")
    _reel(shots, STUDIO_REEL_RANGE, errs, stats, legacy=True)
    v4 = []
    _check_rows(shots, v4)
    by_code = {}
    for e in v4:
        by_code.setdefault(e["code"], []).append(e)
    for code, items in sorted(by_code.items()):
        first = items[0]
        warns.append({"code": code, "where": "shots", "message":
                      f"legacy: V4 column issue, warning only ({len(items)}x); first at {first['where']}: {first['message']}"})


# ---------- files ----------

def _load(path, errs, code):
    if not path.is_file():
        _e(errs, code, path.name, f"{path.name} is missing")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _e(errs, "PACK-02", path.name, f"{path.name} is not readable JSON ({type(exc).__name__})")
        return None


def _story_file(d):
    """The parsed stage 1 block: story_plan.json (written by a staged run), else stage_1.json; None when neither exists."""
    for name in ("story_plan.json", "stage_1.json"):
        if (d / name).is_file():
            return d / name
    return None


def _peek_output_languages(d):
    """output_languages from the stage 1 block; None when it does not carry them."""
    src = _story_file(d)
    try:
        data = json.loads(src.read_text(encoding="utf-8")) if src else None
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("output_languages"), list):
        return data["output_languages"]
    return None


def _peek_voice_engines(d):
    """voice_engine from the stage 1 block; None when it does not carry one."""
    src = _story_file(d)
    try:
        data = json.loads(src.read_text(encoding="utf-8")) if src else None
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("voice_engine"), dict):
        return data["voice_engine"]
    return None


def validate_pack(pack_dir, legacy=False, *, output_languages=None, lang_check=None, voice_engines=None):
    """Read shots.json and bible.json (plus stage_1*/stage_2* files when present). Writes nothing.
    output_languages=None is read from the stage_1 file when it carries one."""
    d = Path(pack_dir)
    errs, warns = [], []
    stats = {"pack": d.name, "mode": "legacy" if legacy else "v4"}
    shots = _load(d / "shots.json", errs, "PACK-01")
    bible = _load(d / "bible.json", errs, "PACK-01")
    if legacy:
        if shots is not None:
            _legacy_checks(shots, bible, errs, warns, stats)
        return _rep(errs, warns, stats)
    if output_languages is None:
        output_languages = _peek_output_languages(d)
    if shots is not None:
        if voice_engines is None:
            voice_engines = _peek_voice_engines(d)
        _absorb(errs, warns, stats, validate_stage("shots", shots, bible, output_languages=output_languages,
                                                   lang_check=lang_check, voice_engines=voice_engines))
    if bible is not None:
        _absorb(errs, warns, stats, validate_stage("bible", bible))
    story_src = _story_file(d)   # the parsed stage 1 block; the *_raw.json envelopes are model output, never story data
    if story_src is not None:
        data = _load(story_src, errs, "PACK-01")
        if data is not None:
            _absorb(errs, warns, stats, validate_stage("story", data))
    return _rep(errs, warns, stats)


# ---------- CLI ----------

def _print_human(rep):
    print(f"{'OK' if rep['ok'] else 'FAILED'}: {len(rep['errors'])} error(s), {len(rep['warnings'])} warning(s)")
    for e in rep["errors"]:
        print(f"  ERROR {e['code']} {e['where']}: {e['message']}")
    for w in rep["warnings"]:
        print(f"  WARN  {w['code']} {w['where']}: {w['message']}")
    for k, v in rep["stats"].items():
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Validate an H3 V4 pack folder (reads only).")
    ap.add_argument("pack_dir")
    ap.add_argument("--legacy", action="store_true", help="old-format pack: only what it can satisfy; V4 columns as warnings")
    ap.add_argument("--json", action="store_true", help="print the Report as JSON")
    args = ap.parse_args(argv)   # usage errors exit 2
    if not Path(args.pack_dir).is_dir():
        print(f"not a folder: {args.pack_dir}", file=sys.stderr)
        return 2
    rep = validate_pack(args.pack_dir, legacy=args.legacy)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        _print_human(rep)
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
