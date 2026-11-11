"""Approval sheet (timing / source / staging layers) and the Gate B record (card X-11).

build() writes approval_sheet.md and approval_sheet.csv, one row per lock shot.
approve() appends an owner approval to gate_b.json, only when that shot's keyframe gate passes.
gate_b_ok() reports shots with no approval, or whose keyframe gate changed after approval.

The keyframe gate files are read from keyframe_gate.keyframe_dir(<gate_b dir>), i.e.
<gate_b dir>/keyframe_gates/<SHOT>.json. The gate writes there too, so gate_b.json must sit in the flow root
that the timeline lock names.
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import blocking
import keyframe_gate as kg

FPS = 24
KEYFRAME_DIR_NAME = kg.KEYFRAME_DIR_NAME
CSV_FIELDS = [
    "shot", "edit_frames", "seconds", "voice_start", "voice_end",
    "refs", "verdicts",
    "start_end", "change_list", "route", "gate_pass", "gate_metrics", "image_paths",
]


def _shots(lock):
    return lock["shots"] if isinstance(lock, dict) else list(lock)


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _start_end(sheet):
    parts = []
    for member in sheet.get("cast", []):
        start, end = member.get("start", {}), member.get("end", {})
        parts.append(
            f"{member.get('name', member.get('id'))}: ({start.get('x')},{start.get('y')}) -> "
            f"({end.get('x')},{end.get('y')})"
        )
    return "; ".join(parts)


def _change_list(sheet):
    return blocking.change_list(sheet) if "cast" in sheet else []


def _rows(lock, sheets, source_check, keyframe_gates, routes, vo_report, fps):
    rows = []
    for shot in _shots(lock):
        sid = shot["id"]
        sheet = sheets.get(sid, {})
        voice = (vo_report or {}).get(sid) or sheet
        src = source_check.get(sid, {})
        gate = keyframe_gates.get(sid, {})
        frames = int(shot["edit_frames"])
        rows.append({
            "shot": sid,
            "edit_frames": frames,
            "seconds": round(frames / fps, 3),
            "voice_start": voice.get("voice_start", ""),
            "voice_end": voice.get("voice_end", ""),
            "refs": "; ".join(src.get("refs", [])),
            "verdicts": "; ".join(src.get("verdicts", [])),
            "start_end": _start_end(sheet),
            "change_list": " | ".join(_change_list(sheet)),
            "route": (routes or {}).get(sid, ""),
            "gate_pass": bool(gate.get("pass", False)),
            "gate_metrics": json.dumps(gate.get("metrics", {}), sort_keys=True),
            "image_paths": "; ".join(gate.get("image_paths", [])),
        })
    return rows


def _markdown(rows):
    out = ["# Approval sheet", ""]
    for row in rows:
        out += [
            f"## {row['shot']}",
            "",
            "### Timing",
            f"- edit frames: {row['edit_frames']} ({row['seconds']} s)",
            f"- voice: {row['voice_start']} -> {row['voice_end']}",
            "",
            "### Source",
            f"- refs: {row['refs']}",
            f"- verdicts: {row['verdicts']}",
            "",
            "### Staging",
            f"- start -> end: {row['start_end']}",
            f"- change list: {row['change_list']}",
            f"- route: {row['route']}",
            f"- keyframe gate pass: {row['gate_pass']}",
            f"- keyframe gate metrics: {row['gate_metrics']}",
            f"- images: {row['image_paths']}",
            "",
        ]
    return "\n".join(out) + "\n"


def build(lock, sheets, source_check, keyframe_gates, routes, vo_report=None, out_dir=".", fps=FPS):
    """Write approval_sheet.md and approval_sheet.csv; return the rows written."""
    rows = _rows(lock, sheets, source_check, keyframe_gates, routes, vo_report, fps)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "approval_sheet.md").write_text(_markdown(rows), encoding="utf-8")
    with (out / "approval_sheet.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _keyframe_dir(gate_b_path):
    return kg.keyframe_dir(Path(gate_b_path).parent)


def _load_approvals(gate_b_path):
    path = Path(gate_b_path)
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError(f"{path}: gate_b.json must hold a list of approvals")
    return data


def approve(shot, by, gate_b_path, keyframe_dir=None):
    """Record the owner's approval of one shot. Refuses unless its keyframe gate passes.

    keyframe_dir defaults to the folder the gate writes to, next to gate_b.json (see module docstring).
    """
    gate_file = (Path(keyframe_dir) if keyframe_dir else _keyframe_dir(gate_b_path)) / f"{shot}.json"
    if not gate_file.exists():
        raise ValueError(f"{shot}: no keyframe gate file at {gate_file}")
    gate = json.loads(gate_file.read_text(encoding="utf-8"))
    if gate.get("pass") is not True:
        raise ValueError(f"{shot}: keyframe gate did not pass, approval refused")
    approvals = _load_approvals(gate_b_path)
    record = {
        "shot": shot,
        "by": by,
        "date": datetime.now(timezone.utc).isoformat(),
        "keyframe_gate_sha256": _sha256(gate_file),
    }
    approvals.append(record)
    Path(gate_b_path).write_text(json.dumps(approvals, indent=2, sort_keys=True), encoding="utf-8")
    return record


def gate_b_ok(gate_b, keyframe_gate_dir, shot_ids):
    """Return problems: shots with no approval, a failed gate, or a gate changed since approval."""
    approvals = _load_approvals(gate_b)
    latest = {}
    for record in approvals:
        latest[record["shot"]] = record
    problems = []
    for sid in shot_ids:
        record = latest.get(sid)
        if record is None:
            problems.append(f"{sid}: no owner approval in gate_b.json")
            continue
        gate_file = Path(keyframe_gate_dir) / f"{sid}.json"
        if not gate_file.exists():
            problems.append(f"{sid}: keyframe gate file missing")
            continue
        if "keyframe_gate_sha256" not in record:
            problems.append(f"{sid}: approval record missing keyframe_gate_sha256")
            continue
        if _sha256(gate_file) != record["keyframe_gate_sha256"]:
            problems.append(f"{sid}: keyframe gate changed after approval (stale), re-approve")
            continue
        if json.loads(gate_file.read_text(encoding="utf-8")).get("pass") is not True:
            problems.append(f"{sid}: keyframe gate no longer passes")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Record the owner's Gate B approval of one shot.")
    parser.add_argument("shot")
    parser.add_argument("--by", required=True)
    parser.add_argument("--gate-b", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        record = approve(args.shot, args.by, args.gate_b)
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(f"approved {record['shot']} by {record['by']} at {record['date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
