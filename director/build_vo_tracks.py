"""Build the per-shot voice tracks the Gate D plan expects: <vo_dir>/<lang>/<SHOT-nnn>.wav, one file per shot with speech, exactly the
shot's EDITORIAL length (the reel cuts every shot at editorial_duration_sec, the clip tail is trimmed away), mono 44.1 kHz 16-bit.

Every line of a shot is placed at its scripted start (a dialogue line keeps the mouth-sync time); a line that would overlap the one before
starts GAP seconds after it. The voice stays at natural speed (no atempo). The shot length is the timeline lock's (edit_frames / fps);
if the lines do not end TAIL seconds before that cut, the shot is reported as a problem (the text must be shortened), never sped up or cut.
The lock is verified before anything is rendered. The accepted mp3/wav files are never modified. Never calls ElevenLabs or any model.

  python build_vo_tracks.py --pack <pack dir> --raw <dir with <line>.<lang>.wav, edge silence trimmed> --out <vo_dir> --lock <timeline_lock_vN.json> [--langs en,hi,mr]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import timeline_lock_io

GAP = 0.12
TAIL = 0.10
MAX_TEMPO = 1.0   # no speed-up: the voice stays at natural speed, the lock sizes the shot


def editorial_from_lock(lock, shot_id, lang=None):
    """Editorial duration in seconds of a shot: lock frames / fps. The picture clock is never retimed, so lang is not used."""
    return timeline_lock_io.frames_for(lock, shot_id) / lock.get("fps", 24)


def apply_lock(rows, lock, lang):
    """New list of row copies (dict(row)) with editorial_duration_sec overridden from the lock. Missing shot id raises."""
    out = []
    for row in rows:
        r = dict(row)
        r["editorial_duration_sec"] = editorial_from_lock(lock, r["id"], lang)
        out.append(r)
    return out


def wav_seconds(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def needed_sec(lines, tempo):
    """Shot length at which these lines, packed at exactly `tempo`, end TAIL s before the cut (moved from the reel-1 module, W-12)."""
    sped = [dict(x, natural=x["natural"] / tempo) for x in lines]
    _, placed = pack_shot(sped, 1e9, max_tempo=1.0)
    return max(p["end"] for p in placed) + TAIL


def pack_shot(lines, editorial, gap=GAP, tail=TAIL, max_tempo=MAX_TEMPO):
    """lines = [{"id", "start", "natural"}] (scripted start and natural length in seconds). Returns (tempo, [{"id", "start", "length", "end"}]).
    Raises ValueError when no tempo up to max_tempo makes every line end before editorial - tail."""
    order = sorted(lines, key=lambda x: x["start"])
    limit = editorial - tail
    t = 1.0
    while t <= max_tempo + 1e-9:
        cur, placed = None, []
        for ln in order:
            s = ln["start"] if cur is None else max(ln["start"], cur + gap)
            length = ln["natural"] / t
            placed.append({"id": ln["id"], "start": round(s, 3), "length": round(length, 3), "end": round(s + length, 3)})
            cur = s + length
        if cur <= limit + 1e-9:   # a lock length can equal the need exactly
            return round(t, 2), placed
        t += 0.01
    raise ValueError(f"does not fit: needs more than tempo {max_tempo} ({sum(x['natural'] for x in order):.2f} s of speech in {editorial:.1f} s)")


def scripted_lines(row, lang):
    """[(line id, start)] of one pack row in one language: narration and every dialogue line."""
    a = row["audio_and_dialogue_track"]
    out = []
    n = (a.get("narration_by_lang") or {}).get(lang) or {}
    if n.get("text"):
        out.append((f"{row['id']}-N", float(n["time_range"][0])))
    for k, d in enumerate((a.get("dialogue_by_lang") or {}).get(lang) or [], 1):
        out.append((f"{row['id']}-D{k}", float(d["time_range"][0])))
    return out


def render_shot(placed, raw_dir, lang, editorial, out_path):
    """One wav of exactly `editorial` seconds: each line delayed to its start at natural speed, mixed (no normalisation)."""
    args = ["ffmpeg", "-y", "-v", "error"]
    chains = []
    for i, p in enumerate(placed):
        args += ["-i", str(Path(raw_dir) / f"{p['id']}.{lang}.wav")]
        ms = int(round(p["start"] * 1000))
        chains.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(placed)))
    # Gate D wants every VO file to end TAIL seconds before the cut (it pads each shot's VO to the cut itself). Floored to the ms: with a
    # frame-based editorial (8.2917 s) the exact value rounds up by a sample and Gate D reported VO_OVERFLOW_ERROR.
    end = math.floor((editorial - TAIL) * 1000) / 1000
    chains.append(f"{mix}amix=inputs={len(placed)}:normalize=0:duration=longest,apad=whole_dur={end:.3f},atrim=0:{end:.3f}[o]")
    args += ["-filter_complex", ";".join(chains), "-map", "[o]", "-ac", "1", "-ar", "44100", "-sample_fmt", "s16", str(out_path)]
    subprocess.run(args, check=True)


def build(pack, raw_dir, out_dir, langs, lock=None):
    if lock is None:
        raise ValueError("--lock is required: shot lengths come only from the timeline lock (the editorial file path is retired)")
    rows = json.loads((Path(pack) / "shots.json").read_text(encoding="utf-8"))
    stored = timeline_lock_io.load_lock(lock)
    timeline_lock_io.verify_lock(lock, stored["inputs"], stored["params"])   # StaleLockError before any render
    report, problems = [], []
    root = raw_dir
    for lang in langs:
        raw_dir = Path(root) / lang if (Path(root) / lang).is_dir() else root    # <raw>/<lang>/ or one flat folder
        for row in rows:
            sl = scripted_lines(row, lang)
            if not sl:
                continue
            try:
                ed = float(apply_lock([row], stored, lang)[0]["editorial_duration_sec"])
            except KeyError:
                problems.append(f"{row['id']}: not in the timeline lock")
                continue
            lines = [{"id": i, "start": s, "natural": wav_seconds(Path(raw_dir) / f"{i}.{lang}.wav")} for i, s in sl]
            try:
                tempo, placed = pack_shot(lines, ed)
            except ValueError as e:
                problems.append(f"{row['id']} {lang}: {e}")
                continue
            dst = Path(out_dir) / lang / f"{row['id']}.wav"
            dst.parent.mkdir(parents=True, exist_ok=True)
            render_shot(placed, raw_dir, lang, ed, dst)
            report.append({"shot": row["id"], "lang": lang, "editorial": ed, "edit_frames": timeline_lock_io.frames_for(stored, row["id"]),
                           "tempo": tempo, "lines": placed, "file": str(dst)})
    return report, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--langs", default="en,hi,mr")
    ap.add_argument("--lock", required=True, help="timeline_lock_vN.json: the only source of shot lengths")
    a = ap.parse_args(argv)
    try:
        report, problems = build(a.pack, a.raw, a.out, a.langs.split(","), lock=a.lock)
    except (OSError, ValueError) as exc:   # missing lock, corrupt lock, StaleLockError (a ValueError): nothing was rendered
        print(f"{a.lock}: {exc}", file=sys.stderr)
        return 2
    Path(a.out, "vo_tracks_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(len(report), "tracks written;", len(problems), "problems")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
