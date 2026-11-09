"""Per-language editorial lengths (music session decisions, 2026-11-09): the file `<pack>/editorial_by_lang.json`.

ONE shared timeline: every language gets the same values (one video, 3 audio tracks, one score). A shot grows only by frames the clip
already has (spare tail; the last shot may only grow at its START); nothing is regenerated. Missing file = the v3 build, unchanged.

  {"fps": 24, "by_lang": {"en": {"SHOT-005": {"extend_frames": 12, "at": "end"}, ...}, "hi": {...same...}, "mr": {...same...}}}

Plan (writes the file): for each shot, the largest need of all languages = the length at which the voice plays at natural speed and ends
TAIL s before the cut; extra time rounded UP to whole beats for the shots given in --beats (BPM), not rounded for the others; capped by the
clip's spare frames; when rounding up does not fit, round DOWN and accept a voice speed-up of at most 1.03 (else reported).

  python editorial_by_lang.py --pack <pack> --story <h3_story.json> --raw <root with <lang>/<line>.<lang>.wav> --langs en,hi,mr
         --beats SHOT-003:128,SHOT-004:128,SHOT-006:176,SHOT-007:176,SHOT-008:176 [--write]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_vo_tracks import TAIL, pack_shot, scripted_lines, wav_seconds  # noqa: E402

FILE = "editorial_by_lang.json"
MAX_SPEEDUP = 1.03


def load(pack):
    """The shared per-shot extensions {shot: (frames, at)}, or {} when the file is missing. Languages must agree (one timeline)."""
    p = Path(pack) / FILE
    if not p.is_file():
        return {}
    doc = json.loads(p.read_text(encoding="utf-8"))
    langs = list(doc["by_lang"].values())
    if any(x != langs[0] for x in langs):
        raise ValueError(f"{p}: languages differ; only one shared timeline is supported")
    return {s: (int(v["extend_frames"]), v.get("at", "end")) for s, v in langs[0].items() if int(v["extend_frames"])}


def apply_rows(rows, ext, fps=24):
    out = copy.deepcopy(rows)
    for r in out:
        if r["id"] in ext:
            r["editorial_duration_sec"] = round(float(r["editorial_duration_sec"]) + ext[r["id"]][0] / fps, 4)
    return out


def apply_shots(h3_shots, ext):
    """New trim window, editorial length and master-reel windows of the H3 shots (copies)."""
    out, cum = copy.deepcopy(h3_shots), 0
    for s in out:
        t = s["timing_and_lattice"]
        n, at = ext.get(s["shot_id"], (0, "end"))
        fps = t["fps"]
        if at == "start":
            if n > t["trim_in_frame"]:
                raise ValueError(f"{s['shot_id']}: needs {n} head frames, clip has {t['trim_in_frame']}")
            t["trim_in_frame"] -= n
        else:
            if t["trim_out_frame"] + n > t["pixel_frames"]:
                raise ValueError(f"{s['shot_id']}: needs {n} tail frames, clip has {t['pixel_frames'] - t['trim_out_frame']}")
            t["trim_out_frame"] += n
        t["editorial_frames"] = t["trim_out_frame"] - t["trim_in_frame"]
        t["editorial_duration_sec"] = round(t["editorial_frames"] / fps, 4)
        t["trim_in_sec"], t["trim_out_sec"] = round(t["trim_in_frame"] / fps, 4), round(t["trim_out_frame"] / fps, 4)
        t["master_reel_frame_window"] = [cum, cum + t["editorial_frames"]]
        t["master_reel_window_sec"] = [round(cum / fps, 4), round((cum + t["editorial_frames"]) / fps, 4)]
        cum += t["editorial_frames"]
    return out


def needed_sec(lines, tempo):
    """Shot length at which these lines, packed at exactly `tempo`, end TAIL s before the cut."""
    sped = [dict(x, natural=x["natural"] / tempo) for x in lines]
    _, placed = pack_shot(sped, 1e9, max_tempo=1.0)
    return max(p["end"] for p in placed) + TAIL


def plan_shot(need1, need_max, editorial, spare, fps, beat=None):
    """Frames to add. need1 = length for natural speed, need_max = length at MAX_SPEEDUP. Returns (frames, note)."""
    raw = need1 - editorial
    if raw <= 1e-9:
        return 0, "fits at natural speed"
    if beat:
        frames = round(math.ceil(raw / beat - 1e-9) * beat * fps)
        if frames <= spare:
            return frames, f"rounded up to {round(frames / fps / beat)} beat(s)"
        frames = int(math.floor(spare / fps / beat) * beat * fps)
        note = f"rounded down to {round(frames / fps / beat)} beat(s) (spare {spare} fr)"
    else:
        frames = math.ceil(raw * fps - 1e-9)
        if frames <= spare:
            return frames, "natural speed, not rounded"
        frames, note = spare, f"all spare frames ({spare})"
    if editorial + frames / fps + 1e-9 < need_max:
        note += f"; VOICE STILL ABOVE {MAX_SPEEDUP}x"
    return frames, note


def plan(rows, h3_shots, raw_root, langs, beats_bpm):
    shots = {s["shot_id"]: s["timing_and_lattice"] for s in h3_shots}
    out, report = {}, []
    for i, r in enumerate(rows):
        sid, t = r["id"], shots[r["id"]]
        fps, ed = t["fps"], float(r["editorial_duration_sec"])
        last = i == len(rows) - 1
        need1 = need_max = 0.0
        for lg in langs:
            sl = scripted_lines(r, lg)
            if sl:
                lines = [{"id": k, "start": s, "natural": wav_seconds(Path(raw_root) / lg / f"{k}.{lg}.wav")} for k, s in sl]
                need1, need_max = max(need1, needed_sec(lines, 1.0)), max(need_max, needed_sec(lines, MAX_SPEEDUP))
        tail = t["pixel_frames"] - t["trim_out_frame"]
        # the last shot grows only at its START (owner/music rule); voice keeps its picture sync there, so a head extension gives the
        # voice no room: the last shot is planned with no spare when its tail is empty
        spare = tail if not last or tail else 0
        bpm = beats_bpm.get(sid)
        frames, note = plan_shot(need1, need_max, ed, spare, fps, 60.0 / bpm if bpm else None)
        at = "start" if last and not tail else "end"
        out[sid] = {"extend_frames": frames, "at": at}
        report.append({"shot": sid, "editorial_sec": ed, "need_natural_sec": round(need1, 3), "need_1.03_sec": round(need_max, 3),
                       "spare_frames": spare, "bpm": bpm, "extend_frames": frames, "extend_sec": round(frames / fps, 4),
                       "new_editorial_sec": round(ed + frames / fps, 4), "at": at, "note": note})
    return out, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--story", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--langs", default="en,hi,mr")
    ap.add_argument("--beats", default="")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    rows = json.loads((Path(a.pack) / "shots.json").read_text(encoding="utf-8"))
    h3 = json.loads(Path(a.story).read_text(encoding="utf-8"))["episodes"][0]["shots"]
    beats = {k: float(v) for k, v in (x.split(":") for x in a.beats.split(",") if x)}
    langs = a.langs.split(",")
    shared, report = plan(rows, h3, a.raw, langs, beats)
    for x in report:
        print(json.dumps(x, ensure_ascii=False))
    total = sum(float(r["editorial_duration_sec"]) for r in rows) + sum(v["extend_frames"] for v in shared.values()) / 24
    print(f"total {total:.3f} s")
    if a.write:
        doc = {"fps": 24, "shared_timeline": True, "beats_bpm": beats, "max_voice_speedup": MAX_SPEEDUP, "plan": report,
               "by_lang": {lg: shared for lg in langs}}
        (Path(a.pack) / FILE).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        print("written", Path(a.pack) / FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
