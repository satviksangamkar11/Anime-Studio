"""Validated append to a shot progress file (one JSON object per line, UTF-8). Keeps statuses and the decider consistent.

  from progress_log import append
  append("<adhyay>/shots_progress.jsonl", {"shot_id": "LEAP-01A", "status": "DONE", "flow_title": "LEAP-01A__v01", "time": "...",
                                            "decided_by": "claude", "edit_id": "<36-char id>", "notes": "..."})
"""
import json
from pathlib import Path

STATUSES = ("DONE", "NEEDS_REVIEW", "FAILED", "FINAL", "GENERATED", "BLOCKED", "NOTE")
DECIDERS = ("owner", "claude", "haiku")
REQUIRED = ("shot_id", "status", "flow_title", "time", "decided_by")
NEEDS_EDIT_ID = ("DONE", "FINAL")


def check(line) -> None:
    if not isinstance(line, dict):
        raise ValueError("progress line must be a dict")
    missing = [k for k in REQUIRED if not line.get(k)]
    if missing:
        raise ValueError(f"missing required key(s): {', '.join(missing)}")
    if line["status"] not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}, got {line['status']!r}")
    if line["decided_by"] not in DECIDERS:
        raise ValueError(f"decided_by must be owner, claude or haiku, got {line['decided_by']!r}")
    if line["status"] in NEEDS_EDIT_ID and not line.get("edit_id"):
        raise ValueError(f"{line['status']} needs edit_id (the 36-character tile id)")


def append(path, line: dict) -> None:
    check(line)
    with open(Path(path), "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
