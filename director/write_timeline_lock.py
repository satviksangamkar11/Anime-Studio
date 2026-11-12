"""Write the versioned timeline lock for one pack: every shot's length, beat grid and H3 handles, in one file.

  python write_timeline_lock.py --pack <pack dir> --wav-root <.../wav_export/wav> --manifest <manifest.json> \
      --out-dir <lock dir> [--langs en,hi,mr] [--acts acts.json] [--blocking-dir <dir>]

Reads <pack>/shots.json (rows with audio_and_dialogue_track, optional bpm, snap, cue) and the line WAVs
<wav-root>/<lang>/<line id>.<lang>.wav. Writes timeline_lock_vN.params.json, timeline_lock_vN.json (never overwritten)
and, from v2 on, timeline_lock_vN.diff.json (edit_frames changes against the previous version).
--blocking-dir is either a folder of blocking/1 sheets (<SHOT-ID>.json, one per shot row, each validated by
director/blocking.load_sheet) or, for backward compatibility, a folder with blocking.json
({shot id: {bpm, snap, cue, min_seconds}}), which wins when present. Sheet derivation: sheet_entry().
No model call, no network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import blocking as blocking_sheets  # noqa: E402
import build_vo_tracks as bvt  # noqa: E402
import timeline_lock_core as core  # noqa: E402
import timeline_lock_io as lio  # noqa: E402

LATTICE_NAME = "v4_to_h3.fit_lattice"
EXEMPT_BPM = (None, 60)  # groove-free: a non-snapped shot at these tempos never needs a grid


def wav_name(line_id, lang):
    return f"{line_id}.{lang}.wav"


def _cue_value(row, acts):
    return acts[row["id"]] if acts is not None else row.get("cue")


def plan_lock(rows, wav_seconds_fn, langs, acts, min_seconds, edit_seconds=None, preset=None):
    """Lock rows for one reel. Pure apart from the WAV reads through wav_seconds_fn(lang, line_id).

    rows: [{id, audio_and_dialogue_track, bpm?, snap?, cue?}] in reel order.
    acts: None or {shot id: act name}. An act is a run of shots with the same act name
    (no acts: the same cue, else the same bpm).
    min_seconds: {shot id: seconds}; a shot with no voice line needs one. Any rule break raises SystemExit.
    edit_seconds: {shot id: writer's edit seconds}. For a voiced shot, max over langs of the voice seconds at
    MAX_TEMPO 1.0 must fit inside it (M-16), else SystemExit names the shot and the language.
    """
    if not isinstance(rows, list) or not rows:
        raise SystemExit("reel has no shots")
    if len(rows) == 1:
        raise SystemExit("one-shot reel unsupported")
    min_seconds = min_seconds or {}

    labels = []
    for row in rows:
        sid = row["id"]
        if acts is not None and sid not in acts:
            raise SystemExit(f"{sid}: missing from acts")
        if acts is not None:
            labels.append(acts[sid])
        else:
            labels.append(row.get("cue") if row.get("cue") is not None else row.get("bpm"))
        if row.get("snap", False) and row.get("bpm") is None:
            raise SystemExit(f"{sid}: snap needs a bpm")

    for i, row in enumerate(rows[:-1]):
        if not row.get("snap", False) and row.get("bpm") not in EXEMPT_BPM and labels[i + 1] == labels[i]:
            raise SystemExit(f"{row['id']}: non-snap shot at {row.get('bpm')} BPM is not the last shot of its act")

    voice = {}
    for row in rows:
        sid = row["id"]
        per_lang = {}
        for lang in langs:
            lines = [{"id": lid, "start": start, "natural": wav_seconds_fn(lang, lid)}
                     for lid, start in bvt.scripted_lines(row, lang)]
            if lines:
                per_lang[lang] = bvt.needed_sec(lines, 1.0)
        if not per_lang and sid not in min_seconds:
            raise SystemExit(f"{sid}: silent shot needs blocking min_seconds")
        if per_lang and edit_seconds and sid in edit_seconds:
            worst = max(per_lang, key=lambda k: per_lang[k])
            if per_lang[worst] > edit_seconds[sid] + 1e-9:
                raise SystemExit(
                    f"{sid}: {worst} voice needs {per_lang[worst]:.2f} s at tempo {bvt.MAX_TEMPO} but the edit is "
                    f"{edit_seconds[sid]:.2f} s: shorten the {worst} line or raise the writer seconds")
        if per_lang:
            voice[sid] = per_lang

    act_names, act_no = [], 0
    for i, row in enumerate(rows):
        if i > 0 and labels[i] != labels[i - 1]:  # an act is a run of one cue (or one bpm); a non-snap shot does not end it
            act_no += 1
        act_names.append(f"act{act_no}")

    plan_in = []
    for row, act in zip(rows, act_names):
        snap = bool(row.get("snap", False))
        plan_in.append({
            "id": row["id"],
            "bpm": row.get("bpm") if snap else None,
            "snap": snap,
            "cue": act,
            "min_seconds": min_seconds.get(row["id"]),
        })
    try:
        planned = core.plan_shots(plan_in, voice, margin_frames=0, fps=core.FPS, preset=preset)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    by_id = {row["id"]: row for row in rows}
    lock_rows = []
    for p in planned:
        src = by_id[p["id"]]
        lock_rows.append({
            "id": p["id"],
            "edit_frames": p["edit_frames"],
            "start_frame": p["start_frame"],
            "method": p["method"],
            "beats": p["beats"],
            "error_ms": p["error_ms"],
            "spare": p["spare"],
            "lattice_n": p["lattice_n"],
            "pixel_frames": p["pixel_frames"],
            "trim_in_frame": p["trim_in_frame"],
            "trim_out_frame": p["trim_out_frame"],
            # the trims fix the handles: head = trim_in, tail = pixel - trim_out (matches _plan_handles in every branch)
            "head_handle_frames": p["trim_in_frame"],
            "tail_handle_frames": p["pixel_frames"] - p["trim_out_frame"],
            "incoming_seam_type": p["incoming_seam"],
            "outgoing_seam_type": p["outgoing_seam"],
            "end_frame_position": p["end_frame_position"],
            "bpm": src.get("bpm"),
            "snap": bool(src.get("snap", False)),
            "cue": _cue_value(src, acts),
            "act_start_frame": p["act_start_frame"],
        })
        for key in ("voice_rest", "silence_ok"):        # M-34: shot-relative [t0, t1] from the blocking sheet, if it has one
            if src.get(key) is not None:
                lock_rows[-1][key] = src[key]
    return lock_rows


def wav_paths(rows, langs, wav_root):
    """Every line WAV the plan reads, in row order (each one is an input of the lock)."""
    out = []
    for row in rows:
        for lang in langs:
            for line_id, _start in bvt.scripted_lines(row, lang):
                out.append(Path(wav_root) / lang / wav_name(line_id, lang))
    return out


def _versions_latest(out_dir):
    found = lio._versions(out_dir)
    return found[-1][1] if found else None


def write_version(out_dir, lock_rows, inputs, params):
    """Write the next timeline_lock_vN.json with its params file and diff. Never overwrites a version."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    previous = _versions_latest(out)
    target = lio.next_lock_path(out)
    if target.exists():
        raise SystemExit(f"{target.name} already exists, refusing to overwrite")
    n = int(target.stem.rsplit("v", 1)[1])

    params_path = out / f"timeline_lock_v{n}.params.json"
    params_path.write_text(json.dumps(params, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    lock = lio.write_lock(target, lock_rows, list(inputs) + [params_path], params)

    if previous is not None:
        changes = [{"id": c["id"], "old": c["old"], "new": c["new"]}
                   for c in lio.diff_locks(lio.load_lock(previous), lock) if c["field"] == "edit_frames"]
        diff_path = out / f"timeline_lock_v{n}.diff.json"
        diff_path.write_text(json.dumps(changes, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def sheet_entry(sheet, row, langs):
    """Lock fields of one shot from its blocking/1 sheet.

    bpm, snap, cue: the sheet's own keys when it carries them, else None, False, None (blocking/1 has none today).
    min_seconds: the sheet's writer_seconds for a silent shot only (no scripted line in any language). A voiced
    shot takes its length from the voice, so it gets no min_seconds.
    """
    entry = {"bpm": sheet.get("bpm"), "snap": sheet.get("snap", False), "cue": sheet.get("cue")}
    if not any(bvt.scripted_lines(row, lang) for lang in langs):
        entry["min_seconds"] = sheet["writer_seconds"]
    entry.update({k: sheet[k] for k in ("voice_rest", "silence_ok") if sheet.get(k) is not None})
    return entry


def _sheet_rows(block_dir, rows, langs, min_seconds, edit_seconds=None):
    """Overlay each row with its sheet. Every row needs <SHOT-ID>.json in block_dir; a bad sheet is refused.
    edit_seconds (optional dict) gets each shot's writer_seconds, the edit length plan_lock checks voice against."""
    if not block_dir.is_dir():
        raise SystemExit(f"missing blocking dir: {block_dir}")
    out, files = [], []
    for row in rows:
        path = block_dir / f"{row['id']}.json"
        if not path.is_file():
            raise SystemExit(f"{row['id']}: no blocking sheet at {path}")
        try:
            sheet = blocking_sheets.load_sheet(str(path))
        except ValueError as exc:
            problems = exc.args[0] if exc.args and isinstance(exc.args[0], list) else [str(exc)]
            raise SystemExit("; ".join(str(p) for p in problems)) from exc
        files.append(path)
        if edit_seconds is not None:
            edit_seconds[row["id"]] = sheet["writer_seconds"]
        out.append(_overlay(row, sheet_entry(sheet, row, langs), min_seconds))
    return out, files


def _overlay(row, entry, min_seconds):
    row = dict(row)
    for key in ("bpm", "snap", "cue", "voice_rest", "silence_ok"):
        if key in entry:
            row[key] = entry[key]
    if "min_seconds" in entry:
        min_seconds[row["id"]] = entry["min_seconds"]
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--wav-root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--langs", default="en,hi,mr")
    ap.add_argument("--acts")
    ap.add_argument("--blocking-dir")
    ap.add_argument("--preset", choices=sorted(core.PIKA_PRESETS), help="render preset for the pixel plan (pika: 124-frame floor)")
    a = ap.parse_args(argv)

    langs = [x for x in a.langs.split(",") if x]
    shots_file = Path(a.pack) / "shots.json"
    manifest = Path(a.manifest)
    for needed in (shots_file, manifest):
        if not needed.is_file():
            raise SystemExit(f"missing input: {needed}")
    rows = json.loads(shots_file.read_text(encoding="utf-8"))
    inputs = [shots_file, manifest]

    acts = None
    if a.acts:
        acts_file = Path(a.acts)
        acts = json.loads(acts_file.read_text(encoding="utf-8"))
        inputs.append(acts_file)

    min_seconds = {}
    edit_seconds = {}
    if a.blocking_dir:
        block_dir = Path(a.blocking_dir)
        legacy = block_dir / "blocking.json"
        if legacy.is_file():
            block = json.loads(legacy.read_text(encoding="utf-8"))
            inputs.append(legacy)
            rows = [_overlay(row, block.get(row["id"], {}), min_seconds) for row in rows]
        else:
            rows, sheet_files = _sheet_rows(block_dir, rows, langs, min_seconds, edit_seconds)
            inputs.extend(sheet_files)

    wav_root = Path(a.wav_root)
    wavs = wav_paths(rows, langs, wav_root)
    for wav in wavs:
        if not wav.is_file():
            raise SystemExit(f"missing WAV: {wav}")
    inputs.extend(wavs)

    def wav_fn(lang, line_id):
        return bvt.wav_seconds(wav_root / lang / wav_name(line_id, lang))

    lock_rows = plan_lock(rows, wav_fn, langs, acts, min_seconds, edit_seconds, a.preset)
    params = {"margin_frames": 0, "tail": bvt.TAIL, "gap": bvt.GAP, "tempo": 1.0, "fps": core.FPS,
              "langs": langs, "lattice": LATTICE_NAME}
    if a.preset:                                        # only recorded when set, so default locks keep their hash
        params["preset"] = a.preset
    target = write_version(a.out_dir, lock_rows, inputs, params)
    print(f"wrote {target} ({len(lock_rows)} shots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
