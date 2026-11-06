"""Checks progress_log.append: statuses, decider, edit_id rule, UTF-8 append-only lines."""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import progress_log as pl  # noqa: E402

GOOD = {"shot_id": "LEAP-01A", "status": "DONE", "flow_title": "LEAP-01A__v01", "time": "2026-11-06T10:00:00+05:30",
        "decided_by": "claude", "edit_id": "34ba531b-b5c7-43fa-82a5-7b7746b57016", "notes": "कृष्ण"}


def test_valid_lines_appended_as_utf8_json(tmp_path):
    p = tmp_path / "shots_progress.jsonl"
    pl.append(p, GOOD)
    pl.append(p, {k: v for k, v in GOOD.items() if k != "edit_id"} | {"status": "NOTE"})
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0]) == GOOD and "कृष्ण" in lines[0]


@pytest.mark.parametrize("status", ["NEEDS_REVIEW", "FAILED", "GENERATED", "BLOCKED"])
def test_statuses_without_edit_id_are_fine(tmp_path, status):
    pl.append(tmp_path / "p.jsonl", {k: v for k, v in GOOD.items() if k != "edit_id"} | {"status": status, "decided_by": "haiku"})
    assert (tmp_path / "p.jsonl").is_file()


@pytest.mark.parametrize("change, msg", [
    ({"status": "MAYBE"}, "status"),
    ({"decided_by": "robot"}, "decided_by"),
    ({"status": "FINAL", "edit_id": ""}, "edit_id"),
    ({"status": "DONE", "edit_id": ""}, "edit_id"),
    ({"shot_id": ""}, "shot_id"),
])
def test_bad_line_refused_and_nothing_written(tmp_path, change, msg):
    p = tmp_path / "p.jsonl"
    with pytest.raises(ValueError, match=msg):
        pl.append(p, GOOD | change)
    assert not p.exists()


def test_missing_key_refused(tmp_path):
    bad = {k: v for k, v in GOOD.items() if k != "flow_title"}
    with pytest.raises(ValueError, match="flow_title"):
        pl.append(tmp_path / "p.jsonl", bad)
