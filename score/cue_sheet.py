"""Score stage S1: the cue sheet of one reel, on the reel clock.

Pure: never calls a model, never runs ffmpeg, never touches Ableton, never raises on bad input (it reports).
Input: the writer's V4 pack rows (stories/<slug>/<pack>/shots.json), the same rows core/timeline.py reads.
Output: one dict (and, from the CLI, cue_sheet.json) that the score planner, the note writer and the checks read.

Reel clock and cuts come from core.timeline.build_episodes (editorial frames at 24 fps), so the score uses the exact
clock the edit uses. Everything else is read from the pack row columns:
  hook_type, is_opening_0_2s_hook, is_closing_hook, purpose, deliberate_flip_marker ("HARD CUT ..." = hard cut in),
  look.act / phase / palette_id / focal / hold_purpose / impact_frames, per_second_directives (t0, t1, action, audio_cue),
  audio_and_dialogue_track: narration_by_lang / dialogue_by_lang (or narration / dialogue), sfx_cues,
  continuity_handoff (incoming, outgoing, loop_seam).
Shot-relative seconds become reel seconds by adding the shot start (start_frame / fps).

Reel-level fields: cuts (with hard_cut and act_change), act segments, voice windows per language and their union,
voice gaps (where music may speak), voice coverage, the retention re-hook window and end-hook window from core.json,
the exact sample count at 48 kHz, and tempo candidates per act segment (solve_tempo).

Report shape matches h3/gate_d_audio.py: {"ok", "errors": [{"code", "where", "message"}], "warnings": [...], "stats": {}}.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.style_pack import load_core  # noqa: E402
from core.timeline import FPS, build_episodes  # noqa: E402

SCHEMA_VERSION = 1
SAMPLE_RATE = 48000
LANGS = ("en", "hi", "mr")
HARD_CUT_PREFIX = "HARD CUT"
MIN_GAP_S = 0.3                    # a voice gap shorter than this is not a usable music window
SUBDIVISION = 2                    # cuts are aligned to 8th notes
# Genre tempo ranges, from production guides checked on the web 2026-11-09. The sources are listed in the owner's
# Claude doc "Anirudh and Sai Abhyankkar Style Study" (https://claude.ai/artifact/GA43TUfaKAxzBJRD1cDFiP), not in this repo. Guides put melodic techno at about 120-130 and drum and bass at 170-176.
# Hypnotic techno examples found were 131-135; the range starts at 128 on purpose so one BUILD tempo can serve both
# techno styles. These are search ranges for the solver, not rules: the bible and the plan pick the final tempo.
DEFAULT_TEMPO_RANGES = {
    "ambient": (56.0, 72.0),
    "cinematic": (70.0, 110.0),
    "melodic_techno": (122.0, 130.0),
    "hypnotic_techno": (128.0, 135.0),
    "drum_and_bass": (170.0, 176.0),
}
# Typical tempo per genre: the tie-break after the offset (closer to this first). Genres without one sort by bpm.
DEFAULT_TEMPO_TYPICAL = {"ambient": 60.0, "melodic_techno": 128.0, "hypnotic_techno": 128.0, "drum_and_bass": 176.0}
_RANGE_TEXT = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s?\s*$")
_VO_LINE_ID = re.compile(r"-(N|D\d+)$")          # SHOT-003-N, SHOT-003-D2 (vo_tracks_report line ids)


# ---------------------------------------------------------------- small helpers

def _err(code, where, message):
    return {"code": code, "where": where, "message": message}


def _report(errors, warnings=(), stats=None):
    return {"ok": not errors, "errors": list(errors), "warnings": list(warnings), "stats": dict(stats or {})}


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _str(x):
    return x if isinstance(x, str) else ""


def _r(x, nd=3):
    return round(float(x), nd)


def _list(x):
    """x when it is a list, else [] (a malformed column never raises)."""
    return x if isinstance(x, list) else []


def parse_range(value):
    """(start, end) seconds from [a, b] or "a-bs"; None when malformed or end < start."""
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(_is_num(v) for v in value):
        a, b = float(value[0]), float(value[1])
    elif isinstance(value, str) and _RANGE_TEXT.match(value):
        m = _RANGE_TEXT.match(value)
        a, b = float(m.group(1)), float(m.group(2))
    else:
        return None
    return (a, b) if b >= a >= 0 else None


def merge_windows(windows):
    """Union of (start, end) windows, sorted, touching windows joined."""
    out = []
    for s, e in sorted(windows):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(a, b) for a, b in out]


def gaps_between(windows, total, min_len=MIN_GAP_S):
    """Free spans of [0, total] not covered by windows, at least min_len long."""
    gaps, t = [], 0.0
    for s, e in merge_windows(windows):
        if s - t >= min_len:
            gaps.append((t, s))
        t = max(t, e)
    if total - t >= min_len:
        gaps.append((t, total))
    return gaps


# ---------------------------------------------------------------- tempo solver

def cut_offsets(times, start, bpm, subdivision=SUBDIVISION):
    """Offset (seconds) of each time from the nearest grid line of a grid that starts at `start` at `bpm`."""
    step = 60.0 / bpm / subdivision
    return [abs((t - start) - round((t - start) / step) * step) for t in times]


def solve_tempo(times, start, lo, hi, *, tolerance_s=1.0 / FPS, subdivision=SUBDIVISION, step=1.0):
    """BPM values in [lo, hi] (stepping by `step`) whose grid from `start` puts every time within tolerance_s of an
    8th note. Sorted by worst offset, then by distance from the range centre. Each item: {"bpm", "max_offset_ms"}."""
    if not (_is_num(lo) and _is_num(hi) and lo > 0 and hi >= lo and _is_num(step) and step > 0):
        return []
    centre = (lo + hi) / 2
    out, bpm = [], float(lo)
    while bpm <= hi + 1e-9:
        worst = max(cut_offsets(times, start, bpm, subdivision), default=0.0)
        if worst <= tolerance_s + 1e-9:
            out.append({"bpm": _r(bpm, 2), "max_offset_ms": _r(worst * 1000, 1)})
        bpm += step
    return sorted(out, key=lambda c: (c["max_offset_ms"], abs(c["bpm"] - centre)))


# ---------------------------------------------------------------- per-shot readers (pack row columns)

def _raw_items(raw):
    """{lang: [(kind, speaker, item)]}: narration first, then dialogue in file order; empty text dropped."""
    trk = raw.get("audio_and_dialogue_track") if isinstance(raw.get("audio_and_dialogue_track"), dict) else {}
    narr_by = trk.get("narration_by_lang") if isinstance(trk.get("narration_by_lang"), dict) else None
    dia_by = trk.get("dialogue_by_lang") if isinstance(trk.get("dialogue_by_lang"), dict) else None
    # each field falls back on its own plain column, so per-language narration never hides plain dialogue
    narr = trk.get("narration")
    lang = _str(narr.get("language")) if isinstance(narr, dict) else ""
    if narr_by is None:
        narr_by = {lang or "xx": narr} if isinstance(narr, dict) else {}
    if dia_by is None:
        dia_by = {}
        for d in _list(trk.get("dialogue")):
            if isinstance(d, dict):
                dia_by.setdefault(_str(d.get("language")) or lang or "xx", []).append(d)
    out = {}
    for lang in sorted(set(narr_by or {}) | set(dia_by or {})):
        items = []
        n = (narr_by or {}).get(lang)
        if isinstance(n, dict) and _str(n.get("text")).strip():
            items.append(("narration", "NARRATOR", n))
        for d in _list((dia_by or {}).get(lang)):
            if isinstance(d, dict) and _str(d.get("text")).strip():
                items.append(("dialogue", _str(d.get("speaker")) or "UNKNOWN", d))
        out[lang] = items
    return out


def _voice_lines(raw, length_s, where, warnings, windows=None):
    """{lang: [{"kind", "speaker", "start", "end", "text"}]} shot-relative, from *_by_lang or the plain fields."""
    out = {}
    for lang, items in _raw_items(raw).items():
        lines = []
        for kind, speaker, item in items:
            rng = parse_range(item.get("time_range"))
            if rng is None:
                warnings.append(_err("VOICE_RANGE_BAD", f"{where} {lang}", f"{kind} time_range unreadable: {item.get('time_range')!r}"))
                continue
            s, e = rng
            if e > length_s + 1e-6 or s >= length_s:
                warnings.append(_err("VOICE_OUTSIDE_SHOT", f"{where} {lang}",
                                     f"{kind} {s:g}-{e:g}s runs past the shot end {length_s:g}s; clipped"))
                e = min(e, length_s)
                if s >= e:
                    continue
            lines.append({"kind": kind, "speaker": speaker, "start": s, "end": e, "text": _str(item.get("text"))})
        lines.sort(key=lambda x: x["start"])
        if windows:  # real audio windows (blot RULE 39): keys SHOT-nnn-N.<lang> and SHOT-nnn-D<k>.<lang>
            k = 0
            for ln in lines:
                if ln["kind"] == "narration":
                    key = f"{where}-N.{lang}"
                else:
                    k += 1
                    key = f"{where}-D{k}.{lang}"
                w = windows.get(key)
                if isinstance(w, dict) and _is_num(w.get("start_s")) and _is_num(w.get("window_s")):
                    ln["scripted_end"] = ln["end"]
                    ln["start"] = float(w["start_s"])
                    ln["end"] = min(float(w["start_s"]) + float(w["window_s"]), length_s)
                    ln["from_audio_window"] = True
        out[lang] = sorted(lines, key=lambda x: x["start"])
    return out


def _sfx_cues(raw, length_s, where, warnings):
    trk = raw.get("audio_and_dialogue_track") if isinstance(raw.get("audio_and_dialogue_track"), dict) else {}
    out = []
    for c in _list(trk.get("sfx_cues")):
        if not isinstance(c, dict):
            continue
        rng = parse_range(c.get("time_range"))
        if rng is None or rng[0] >= length_s:
            warnings.append(_err("SFX_RANGE_BAD", where, f"sfx time_range unreadable or past the shot: {c.get('time_range')!r}"))
            continue
        out.append({"start": rng[0], "end": min(rng[1], length_s), "key": _str(c.get("sfx_key")),
                    "description": _str(c.get("description"))})
    return out


def _per_second(raw, length_s):
    out = []
    for d in _list(raw.get("per_second_directives")):
        if isinstance(d, dict) and _is_num(d.get("t0")) and _is_num(d.get("t1")) and d["t0"] < length_s:
            out.append({"t0": float(d["t0"]), "t1": min(float(d["t1"]), length_s),
                        "action": _str(d.get("action_pose_expression")), "audio_cue": _str(d.get("audio_cue"))})
    return out


def _shift(items, t0, keys):
    return [{**it, **{k: _r(t0 + it[k]) for k in keys if k in it}} for it in items]


# ---------------------------------------------------------------- VO reports (real speech positions)

def _index_vo_reports(vo_reports, warnings):
    """{(shot, lang): row} from {lang: [rows]} (vo_tracks_report.json). A row without shot or lines is ignored, with a warning."""
    out = {}
    for lang, rows in vo_reports.items():
        for row in _list(rows):
            if not isinstance(row, dict) or not _str(row.get("shot")) or not isinstance(row.get("lines"), list):
                warnings.append(_err("VO_REPORT_BAD_ROW", str(lang), f"row ignored, no shot or lines: {str(row)[:80]}"))
                continue
            out[(row["shot"], str(lang))] = row
    return out


def _vo_row_lines(row, raw, lang, sid, length_s, fps, errors, warnings):
    """Real speech lines of one shot and language, shot-relative (the caller shifts them to the reel clock).
    Speaker and text come from the scripted line with the same id: N = narration, Dn = n-th dialogue line."""
    ed = raw.get("editorial_duration_sec")
    ed = float(ed) if _is_num(ed) else length_s
    row_ed = row.get("editorial")
    if not _is_num(row_ed) or abs(row_ed - ed) > 1.0 / fps + 1e-6:
        errors.append(_err("VO_REPORT_EDITORIAL_MISMATCH", sid, f"{lang} report editorial {row_ed!r} vs shot {ed:g} s; "
                           "more than one frame apart"))
    scripted = {}
    k = 0
    for kind, speaker, item in _raw_items(raw).get(lang, []):
        if kind == "narration":
            scripted["N"] = (speaker, item)
        else:
            k += 1
            scripted[f"D{k}"] = (speaker, item)
    lines = []
    for ln in row["lines"]:
        if not isinstance(ln, dict) or not _is_num(ln.get("start")) or not _is_num(ln.get("end")) \
                or ln["start"] < 0 or ln["end"] < ln["start"]:
            warnings.append(_err("VO_REPORT_BAD_LINE", sid, f"{lang} line unreadable: {str(ln)[:80]}"))
            continue
        s, e = float(ln["start"]), float(ln["end"])
        if e > length_s + 1e-6:
            errors.append(_err("VO_REPORT_OVERFLOW", sid, f"{lang} line {ln.get('id')} ends at {e:g} s, past the shot end "
                               f"{length_s:g} s"))
        m = _VO_LINE_ID.search(str(ln.get("id") or ""))
        key = m.group(1) if m else None
        hit = scripted.get(key) if key else None
        lines.append({"kind": "narration" if key == "N" else "dialogue",
                      "speaker": hit[0] if hit else "unknown", "start": s, "end": e,
                      "text": _str(hit[1].get("text")) if hit else "", "id": ln.get("id")})
    return sorted(lines, key=lambda x: x["start"])


# ---------------------------------------------------------------- editorial lengths (v4 shared timeline)

def _shift_time_range(item, s):
    rng = parse_range(item.get("time_range")) if isinstance(item, dict) else None
    if rng is not None:
        item["time_range"] = [_r(rng[0] + s), _r(rng[1] + s)]


def _shift_shot(raw, s):
    """Copy of a pack row with every shot-relative time moved by s seconds (an extension at the start of the shot)."""
    raw = copy.deepcopy(raw)
    look = raw.get("look")
    if isinstance(look, dict):
        for imp in _list(look.get("impact_frames")):
            if isinstance(imp, dict) and _is_num(imp.get("at_s")):
                imp["at_s"] = _r(imp["at_s"] + s)
    for d in _list(raw.get("per_second_directives")):
        if isinstance(d, dict) and _is_num(d.get("t0")) and _is_num(d.get("t1")):
            d["t0"], d["t1"] = _r(d["t0"] + s), _r(d["t1"] + s)
    trk = raw.get("audio_and_dialogue_track")
    if isinstance(trk, dict):
        for c in _list(trk.get("sfx_cues")):
            _shift_time_range(c, s)
        for key in ("narration", "dialogue", "narration_by_lang", "dialogue_by_lang"):
            val = trk.get(key)
            if isinstance(val, dict) and key.endswith("_by_lang"):
                items = [x for v in val.values() for x in (v if isinstance(v, list) else [v])]
            elif isinstance(val, dict):
                items = [val]
            else:
                items = _list(val)
            for it in items:
                _shift_time_range(it, s)
    return raw


def _shift_row(row, s):
    """A VO report row with its line times moved by s seconds (same shift as the shot)."""
    if not s:
        return row
    lines = []
    for ln in row["lines"]:
        if isinstance(ln, dict) and _is_num(ln.get("start")) and _is_num(ln.get("end")):
            ln = {**ln, "start": _r(ln["start"] + s), "end": _r(ln["end"] + s)}
        lines.append(ln)
    return {**row, "lines": lines}


def apply_editorial(shots, editorial, fps=FPS):
    """Apply editorial_by_lang.json (v4 shared timeline). Returns (shots, shifts, errors, warnings), shifts = {shot id: s}.
    plan[].new_editorial_sec becomes the shot's editorial_duration_sec. An extension with at "start" moves the shot's own
    internal times (impacts, beats, sfx, scripted voice) by the extended seconds; at "end" changes nothing inside the shot."""
    errors, warnings, shifts = [], [], {}
    if not isinstance(editorial, dict) or not isinstance(editorial.get("plan"), list):
        return shots, shifts, [_err("EDITORIAL_SHAPE", "editorial", "expected editorial_by_lang.json with a plan list")], warnings
    if editorial.get("shared_timeline") is not True:
        errors.append(_err("EDITORIAL_NOT_SHARED", "editorial", "shared_timeline is not true; the music needs one timeline "
                           "for every language"))
    plan = {str(p["shot"]): p for p in editorial["plan"] if isinstance(p, dict) and _str(p.get("shot"))}
    by_lang = editorial.get("by_lang") if isinstance(editorial.get("by_lang"), dict) else {}
    for sid, p in plan.items():  # every language must carry the same extension as the shared plan
        seen = {(v.get("extend_frames"), v.get("at")) for per in by_lang.values()
                if isinstance(per, dict) and isinstance(per.get(sid), dict) for v in [per[sid]]}
        if seen and seen != {(p.get("extend_frames"), p.get("at"))}:
            errors.append(_err("EDITORIAL_NOT_SHARED", sid, f"per-language extensions {sorted(map(str, seen))} differ "
                               f"from the shared plan {(p.get('extend_frames'), p.get('at'))}"))
    out, present = [], set()
    for sh in shots:
        sid = sh.get("id") if isinstance(sh, dict) else None
        p = plan.get(sid)
        if p is None:
            if isinstance(sh, dict):
                errors.append(_err("EDITORIAL_SHOT_MISSING", str(sid), "shot has no entry in the editorial plan"))
            out.append(sh)
            continue
        present.add(sid)
        new, at, ext = p.get("new_editorial_sec"), p.get("at"), p.get("extend_frames")
        if not _is_num(new) or new <= 0 or at not in ("start", "end") or not isinstance(ext, int) or ext < 0:
            errors.append(_err("EDITORIAL_BAD_VALUE", sid, f"plan row unreadable: new_editorial_sec={new!r}, at={at!r}, "
                               f"extend_frames={ext!r}"))
            out.append(sh)
            continue
        sh = copy.deepcopy(sh)
        sh["editorial_duration_sec"] = new
        if at == "start" and ext:
            shifts[sid] = ext / fps
            sh = _shift_shot(sh, ext / fps)
        out.append(sh)
    for sid in plan:
        if sid not in present:
            warnings.append(_err("EDITORIAL_SHOT_EXTRA", sid, "plan row has no shot in this pack; ignored"))
    return out, shifts, errors, warnings


# ---------------------------------------------------------------- the cue sheet

def build_cue_sheet(shots, *, episode=None, fps=FPS, core=None, voice_windows=None, vo_reports=None, editorial=None):
    """Return (sheet, report). sheet is None when the reel cannot be built. Never raises.
    voice_windows: optional FINAL_TEXT_v2.json dict; its start_s/window_s replace the scripted time_range.
    vo_reports: optional {lang: [rows]} from vo_tracks_report.json; the real speech lines replace both the scripted
    range and the voice_windows for that shot and language (precedence: vo_reports > voice_windows > scripted)."""
    voice_windows = voice_windows if isinstance(voice_windows, dict) else None
    errors, warnings = [], []
    shifts = {}
    if editorial is not None and isinstance(shots, list):
        shots, shifts, ed_errors, ed_warnings = apply_editorial(shots, editorial, fps)
        errors += ed_errors
        warnings += ed_warnings
        if ed_errors:
            return None, _report(errors, warnings)
    vo_index = None
    if isinstance(vo_reports, dict):
        vo_index = _index_vo_reports(vo_reports, warnings)
        vo_langs = {str(l) for l in vo_reports}
    try:
        core = core if isinstance(core, dict) else load_core()
    except Exception as exc:  # the cue sheet still builds; retention windows are then missing
        warnings.append(_err("CORE_UNREADABLE", "core.json", f"{type(exc).__name__}: {exc}"))
        core = {}
    if not isinstance(shots, list):
        return None, _report([_err("INPUT_SHAPE", "shots", "expected the pack's shots.json list")])
    episodes, problems = build_episodes(shots, fps)
    for p in problems:
        errors.append(_err("TIMELINE_" + p.get("rule", "P0"), str(p.get("shot") or p.get("episode") or "timeline"), p.get("message", "")))
    if errors:  # a dropped shot shortens the reel clock: a score built on it would drift against the video
        return None, _report(errors, warnings)
    if not episodes:
        return None, _report([_err("NO_EPISODE", "shots", "no episode could be built")], warnings)
    if episode is None:
        if len(episodes) != 1:
            keys = [e["key"] for e in episodes]
            return None, _report(errors + [_err("EPISODE_AMBIGUOUS", "shots", f"several episodes {keys}; pass episode=")], warnings)
        ep = episodes[0]
    else:
        match = [e for e in episodes if str(e["key"]) == str(episode)]
        if not match:
            return None, _report(errors + [_err("EPISODE_NOT_FOUND", str(episode), f"episodes present: {[e['key'] for e in episodes]}")], warnings)
        ep = match[0]

    total_frames = ep["total_frames"]
    total_s = total_frames / fps
    shot_rows, langs_seen = [], set()
    for view in ep["shots"]:
        raw = view["raw"] if isinstance(view.get("raw"), dict) else {}
        look = view.get("look") if isinstance(view.get("look"), dict) else {}
        sid = view["id"]
        t0 = view["start_frame"] / fps
        length_s = view["frames"] / fps
        voice = _voice_lines(raw, length_s, sid, warnings, voice_windows)
        if vo_index is not None:
            for lang in sorted(vo_langs | set(voice)):
                row = vo_index.get((sid, lang))
                if row is None:  # the scripted or audio-window range stays for this shot and language
                    warnings.append(_err("VO_REPORT_MISSING", sid, f"no {lang} row in the VO report; "
                                         "scripted or audio-window range kept"))
                    continue
                voice[lang] = _vo_row_lines(_shift_row(row, shifts.get(sid, 0)), raw, lang, sid, length_s, fps,
                                            errors, warnings)
        langs_seen |= set(voice)
        flip = _str(raw.get("deliberate_flip_marker"))
        handoff = raw.get("continuity_handoff") if isinstance(raw.get("continuity_handoff"), dict) else {}
        impacts = []
        for i in view.get("impacts") or []:
            if not (t0 - 1e-9 <= i["at_s"] < t0 + length_s - 1e-9):
                # an error, not a warning: a picture-locked hit must never vanish from the sheet silently
                errors.append(_err("IMPACT_OUTSIDE_SHOT", sid, f"impact at {i['at_s']:g}s is outside the shot "
                                   f"{t0:g}-{t0 + length_s:g}s; fix look.impact_frames in the pack"))
                continue
            impacts.append({"at_s": _r(i["at_s"]), "at_frame": i["at_frame"], "type": i["type"], "frames": i["frames"]})
        shot_rows.append({
            "id": sid, "index": view["index"],
            "start_frame": view["start_frame"], "frames": view["frames"],
            "start_s": _r(t0), "end_s": _r(t0 + length_s), "duration_s": _r(length_s),
            "hook_type": _str(raw.get("hook_type")) or None,
            "opening_hook": raw.get("is_opening_0_2s_hook") is True,
            "closing_hook": raw.get("is_closing_hook") is True,
            "purpose": _str(raw.get("purpose")),
            "act": _str(look.get("act")) or None, "phase": _str(look.get("phase")) or None,
            "palette_id": _str(look.get("palette_id")) or None, "focal": _str(look.get("focal")) or None,
            "hold_purpose": _str(look.get("hold_purpose")) or None,
            "hard_cut_in": flip.upper().startswith(HARD_CUT_PREFIX),
            "flip_marker": flip or None,
            "cast_ids": list(view.get("cast_ids") or []),
            "impacts": impacts,
            "beats": _shift(_per_second(raw, length_s), t0, ("t0", "t1")),
            "sfx": _shift(_sfx_cues(raw, length_s, sid, warnings), t0, ("start", "end")),
            "voice": {lang: _shift(lines, t0, ("start", "end", "scripted_end")) for lang, lines in voice.items()},
            "continuity": {"incoming": _str(handoff.get("incoming")), "outgoing": _str(handoff.get("outgoing")),
                           "loop_seam": handoff.get("loop_seam")},
        })
        if not shot_rows[-1]["hook_type"]:
            warnings.append(_err("HOOK_TYPE_MISSING", sid, "no hook_type; the planner will treat the shot as neutral"))
        if not shot_rows[-1]["act"]:
            warnings.append(_err("ACT_MISSING", sid, "no look.act; act segments and act-change cuts are less exact"))

    # cuts between shots
    cuts = []
    for prev, nxt in zip(shot_rows, shot_rows[1:]):
        cuts.append({"at_s": nxt["start_s"], "at_frame": nxt["start_frame"], "from": prev["id"], "to": nxt["id"],
                     "hard_cut": nxt["hard_cut_in"], "act_change": prev["act"] != nxt["act"],
                     "palette_change": prev["palette_id"] != nxt["palette_id"]})

    # act segments (contiguous shots with the same act)
    acts = []
    for row in shot_rows:
        if acts and acts[-1]["act"] == row["act"]:
            acts[-1]["end_s"] = row["end_s"]
            acts[-1]["end_frame"] = row["start_frame"] + row["frames"]
            acts[-1]["shots"].append(row["id"])
        else:
            acts.append({"act": row["act"], "start_s": row["start_s"], "start_frame": row["start_frame"],
                         "end_s": row["end_s"], "end_frame": row["start_frame"] + row["frames"], "shots": [row["id"]]})

    # voice windows per language, their agreement, the union and the free gaps
    per_lang = {}
    for lang in sorted(langs_seen):
        wins = [(l["start"], l["end"]) for row in shot_rows for l in row["voice"].get(lang, [])]
        per_lang[lang] = [(_r(a), _r(b)) for a, b in merge_windows(wins)]
    reference = per_lang.get("en") or (next(iter(per_lang.values())) if per_lang else [])
    differ = sorted(l for l, w in per_lang.items() if w != reference)
    if differ:
        warnings.append(_err("VOICE_WINDOWS_DIFFER", "voice", f"languages {differ} have different speech windows from "
                             f"{'en' if 'en' in per_lang else 'the first language'}; one score must leave room for all of them"))
    union = merge_windows([w for wins in per_lang.values() for w in wins])
    coverage = sum(b - a for a, b in union) / total_s if total_s else 0.0
    gaps = gaps_between(union, total_s)
    for row in shot_rows:  # an impact under speech may only get a low hit (SKILL.md rule 2); the checker reads this
        for imp in row["impacts"]:
            imp["in_voice"] = any(a <= imp["at_s"] < b for a, b in union)

    # retention windows (core.json)
    ret = core.get("retention") if isinstance(core.get("retention"), dict) else {}
    frac = ret.get("rehook_window_frac")
    rehook = [_r(frac[0] * total_s), _r(frac[1] * total_s)] if (isinstance(frac, list) and len(frac) == 2
                                                               and all(_is_num(v) for v in frac)) else None
    end_hook = [_r(total_s - ret["end_hook_s"]), _r(total_s)] if _is_num(ret.get("end_hook_s")) else None
    if rehook is None or end_hook is None:
        warnings.append(_err("RETENTION_WINDOWS_MISSING", "core.json", "rehook_window_frac or end_hook_s missing"))

    # tempo candidates per act segment: every interior cut and the segment end must sit on an 8th note
    tempo = []
    tol = 1.0 / fps
    for seg in acts:
        # cuts inside the act must sit on its 8th-note grid; the act END is not a cut (the next act starts its own grid,
        # the plan puts a 0.4 s drop-out before it), so an off-grid end is a warning, not a dropped candidate
        times = [c["at_frame"] / fps for c in cuts if seg["start_frame"] < c["at_frame"] < seg["end_frame"]]
        start = seg["start_frame"] / fps
        cands = {}
        for name, (lo, hi) in DEFAULT_TEMPO_RANGES.items():  # every candidate within tolerance, no cap
            typ = DEFAULT_TEMPO_TYPICAL.get(name)
            cands[name] = sorted(solve_tempo(times, start, lo, hi, tolerance_s=tol),
                                 key=lambda c: (c["max_offset_ms"], abs(c["bpm"] - typ) if typ else c["bpm"]))
        end_t = seg["end_frame"] / fps
        off_end = sorted({c["bpm"] for lst in cands.values() for c in lst
                          if max(cut_offsets([end_t], start, c["bpm"]), default=0.0) > tol + 1e-9})
        if off_end:
            warnings.append(_err("ACT_END_OFF_GRID", f"{seg['act']} {seg['start_s']:g}-{seg['end_s']:g}s",
                                 f"act end at {seg['end_s']:g} s is off the 8th grid for bpm {off_end}; kept, the next "
                                 "act starts its own grid"))
        tempo.append({"act": seg["act"], "start_s": seg["start_s"], "end_s": seg["end_s"], "candidates": cands})

    samples_exact = total_frames * SAMPLE_RATE / fps
    sheet = {
        "schema_version": SCHEMA_VERSION,
        "episode": ep["key"], "fps": fps, "sample_rate": SAMPLE_RATE,
        "total_frames": total_frames, "total_s": _r(total_s), "total_samples": int(round(samples_exact)),
        "languages": sorted(langs_seen),
        "shots": shot_rows, "cuts": cuts, "acts": acts,
        "voice": {"per_language": {l: [list(w) for w in ws] for l, ws in per_lang.items()},
                  "union": [[_r(a), _r(b)] for a, b in union], "coverage": _r(coverage),
                  "gaps": [[_r(a), _r(b)] for a, b in gaps]},
        "retention": {"rehook_window_s": rehook, "end_hook_window_s": end_hook,
                      "first_motion_s": ret.get("first_motion_s"),
                      # the end sting's bright attack goes after the last word; before it, low hits only (rule 2)
                      "last_voice_end_s": _r(union[-1][1]) if union else None,
                      # last SCRIPTED word (audio windows are permission, not speech): the end sting may follow it
                      "last_speech_end_s": _r(max((l.get("scripted_end", l["end"]) for r in shot_rows
                                                   for ls in r["voice"].values() for l in ls), default=0.0)) or None},
        "tempo_candidates": tempo,
        "tempo_tolerance_ms": _r(1000.0 / fps, 1),
    }
    if abs(samples_exact - round(samples_exact)) > 1e-9:
        warnings.append(_err("SAMPLES_NOT_WHOLE", "reel", f"{total_frames} frames at {fps} fps is not a whole number of samples"))
    stats = {"shots": len(shot_rows), "cuts": len(cuts), "hard_cuts": sum(c["hard_cut"] for c in cuts),
             "acts": len(acts), "total_s": sheet["total_s"], "voice_coverage": sheet["voice"]["coverage"],
             "voice_gaps": len(gaps), "impacts": sum(len(r["impacts"]) for r in shot_rows)}
    if errors:  # a sheet is only ever handed on when every check passed
        return None, _report(errors, warnings, stats)
    return sheet, _report(errors, warnings, stats)


def write_cue_sheet(sheet, report, path):
    """Write cue_sheet.json (the sheet plus its report under "checks"). Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({**sheet, "checks": report}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m score.cue_sheet",
                                description="Build the score cue sheet of one reel from a pack's shots.json. Writes one JSON file.")
    p.add_argument("--shots", required=True, help="stories/<slug>/<pack>/shots.json")
    p.add_argument("--episode", help="episode number or id (needed when the pack has several)")
    p.add_argument("--voice-windows", help="voices/<pack>/FINAL_TEXT_v2.json: real audio windows replace the scripted time_range")
    p.add_argument("--vo-report", action="append", default=[],
                   help="voices/<pack>/vo_<lang>/vo_tracks_report.json; repeat once per language (lang is read from the rows). "
                        "Real speech positions: they replace --voice-windows and the scripted ranges")
    p.add_argument("--editorial", help="stories/<slug>/<pack>/editorial_by_lang.json: shot lengths of the v4 shared timeline")
    p.add_argument("--out", required=True, help="output path, e.g. stories/<slug>/<pack>/score/ep1/cue_sheet.json")
    a = p.parse_args(argv)
    try:
        shots = json.loads(Path(a.shots).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {a.shots}: {exc}", file=sys.stderr)
        return 2
    ed = None
    if a.editorial:
        try:
            ed = json.loads(Path(a.editorial).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"cannot read {a.editorial}: {exc}", file=sys.stderr)
            return 2
    vw = None
    if a.voice_windows:
        try:
            vw = json.loads(Path(a.voice_windows).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"cannot read {a.voice_windows}: {exc}", file=sys.stderr)
            return 2
    vo = None
    if a.vo_report:
        vo = {}
        for path in a.vo_report:
            try:
                rows = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                print(f"cannot read {path}: {exc}", file=sys.stderr)
                return 2
            if not isinstance(rows, list):
                print(f"{path}: expected a JSON list of rows", file=sys.stderr)
                return 2
            for row in rows:
                lang = _str(row.get("lang")) if isinstance(row, dict) else ""
                if not lang:
                    print(f"{path}: a row has no lang", file=sys.stderr)
                    return 2
                vo.setdefault(lang, []).append(row)
    sheet, report = build_cue_sheet(shots, episode=a.episode, voice_windows=vw, vo_reports=vo, editorial=ed)
    for e in report["errors"]:
        print(f"ERROR {e['code']} {e['where']}: {e['message']}", file=sys.stderr)
    for w in report["warnings"]:
        print(f"warn  {w['code']} {w['where']}: {w['message']}", file=sys.stderr)
    if sheet is None or not report["ok"]:
        return 1
    out = write_cue_sheet(sheet, report, a.out)
    s = report["stats"]
    print(f"{out}: {s['shots']} shots, {s['total_s']} s, {s['cuts']} cuts ({s['hard_cuts']} hard), "
          f"{s['acts']} acts, voice {s['voice_coverage']:.0%}, {s['voice_gaps']} gaps, {s['impacts']} impacts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
