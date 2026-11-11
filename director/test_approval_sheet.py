import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Frozen test gate for card X-11: approval sheet (3 layers) + Gate B record.

import csv
import hashlib
import json

import pytest

import approval_sheet


def _write_keyframe_gate(keyframe_gate_dir, shot_id, payload):
    keyframe_gate_dir.mkdir(parents=True, exist_ok=True)
    path = keyframe_gate_dir / f"{shot_id}.json"
    path.write_text(json.dumps(payload, sort_keys=True))
    return path


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


LOCK = [
    {"id": "shot_01", "edit_frames": 24},
    {"id": "shot_02", "edit_frames": 48},
    {"id": "shot_03", "edit_frames": 72},
]
SHOT_IDS = [shot["id"] for shot in LOCK]

SHEETS = {
    "shot_01": {"voice_start": 0.0, "voice_end": 1.0},
    "shot_02": {"voice_start": 1.0, "voice_end": 2.0},
    "shot_03": {"voice_start": 2.0, "voice_end": 3.0},
}

SOURCE_CHECK = {
    "shot_01": {"refs": ["ref_01"], "verdicts": ["ok"]},
    "shot_02": {"refs": ["ref_02"], "verdicts": ["ok"]},
    "shot_03": {"refs": ["ref_03"], "verdicts": ["ok"]},
}

KEYFRAME_GATES = {
    "shot_01": {"pass": True, "metrics": {"sharpness": 0.9}, "image_paths": ["img/01.png"]},
    "shot_02": {"pass": True, "metrics": {"sharpness": 0.8}, "image_paths": ["img/02.png"]},
    "shot_03": {"pass": True, "metrics": {"sharpness": 0.7}, "image_paths": ["img/03.png"]},
}

ROUTES = {
    "shot_01": "route_A",
    "shot_02": "route_B",
    "shot_03": "route_C",
}


def test_three_layers_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    approval_sheet.build(LOCK, SHEETS, SOURCE_CHECK, KEYFRAME_GATES, ROUTES)

    markdown = Path("approval_sheet.md")
    table = Path("approval_sheet.csv")
    assert markdown.exists(), "build must write approval_sheet.md"
    assert table.exists(), "build must write approval_sheet.csv"

    text = markdown.read_text()
    assert "### Timing" in text
    assert "### Source" in text
    assert "### Staging" in text
    # timing layer: edit frames, seconds, voice range of shot_01
    assert "- edit frames: 24 (1.0 s)" in text
    assert "- voice: 0.0 -> 1.0" in text
    # source layer: refs and verdicts of shot_01
    assert "- refs: ref_01" in text
    assert "- verdicts: ok" in text
    # staging layer: route, keyframe gate result and image path of shot_01
    assert "- route: route_A" in text
    assert "- keyframe gate pass: True" in text
    assert "img/01.png" in text


def test_approve_refused_on_failed_gate(tmp_path):
    keyframe_gate_dir = tmp_path / "keyframe_gates"
    gate_b_path = tmp_path / "gate_b.json"
    gate_b_path.write_text("[]")

    _write_keyframe_gate(keyframe_gate_dir, "shot_02", {"pass": False})

    with pytest.raises(ValueError):
        approval_sheet.approve("shot_02", "owner", gate_b_path)

    assert json.loads(gate_b_path.read_text()) == []


def test_gate_b_stale_after_new_B(tmp_path):
    keyframe_gate_dir = tmp_path / "keyframe_gates"
    gate_b_path = tmp_path / "gate_b.json"
    gate_b_path.write_text("[]")

    first = {"pass": True, "image": "img/01.png", "note": "first"}
    _write_keyframe_gate(keyframe_gate_dir, "shot_01", first)
    first_sha = _sha256_file(keyframe_gate_dir / "shot_01.json")

    approval_sheet.approve("shot_01", "owner", gate_b_path)

    approvals = json.loads(gate_b_path.read_text())
    assert len(approvals) == 1
    record = approvals[0]
    assert record["shot"] == "shot_01"
    assert record["by"] == "owner"
    assert isinstance(record["date"], str) and record["date"]
    assert record["keyframe_gate_sha256"] == first_sha

    second = {"pass": True, "image": "img/01.png", "note": "second"}
    _write_keyframe_gate(keyframe_gate_dir, "shot_01", second)

    problems = approval_sheet.gate_b_ok(gate_b_path, keyframe_gate_dir, ["shot_01"])
    assert problems == ["shot_01: keyframe gate changed after approval (stale), re-approve"]


def test_gate_b_reports_gate_that_no_longer_passes(tmp_path):
    keyframe_gate_dir = tmp_path / "keyframe_gates"
    gate_b_path = tmp_path / "gate_b.json"
    failing = {"pass": False}
    _write_keyframe_gate(keyframe_gate_dir, "shot_01", failing)
    # a hand-made approval whose sha matches the failing gate file
    record = {"shot": "shot_01", "by": "owner", "date": "x",
              "keyframe_gate_sha256": _sha256_file(keyframe_gate_dir / "shot_01.json")}
    gate_b_path.write_text(json.dumps([record]))

    problems = approval_sheet.gate_b_ok(gate_b_path, keyframe_gate_dir, ["shot_01"])
    assert problems == ["shot_01: keyframe gate no longer passes"]


def test_gate_b_flags_record_without_sha(tmp_path):
    keyframe_gate_dir = tmp_path / "keyframe_gates"
    gate_b_path = tmp_path / "gate_b.json"
    _write_keyframe_gate(keyframe_gate_dir, "shot_01", {"pass": True})
    gate_b_path.write_text(json.dumps([{"shot": "shot_01", "by": "owner"}]))

    problems = approval_sheet.gate_b_ok(gate_b_path, keyframe_gate_dir, ["shot_01"])
    assert problems == ["shot_01: approval record missing keyframe_gate_sha256"]


def test_approve_accepts_empty_gate_b_file(tmp_path):
    keyframe_gate_dir = tmp_path / "keyframe_gates"
    gate_b_path = tmp_path / "gate_b.json"
    gate_b_path.write_text("")
    _write_keyframe_gate(keyframe_gate_dir, "shot_01", {"pass": True})

    approval_sheet.approve("shot_01", "owner", gate_b_path)

    approvals = json.loads(gate_b_path.read_text())
    assert [record["shot"] for record in approvals] == ["shot_01"]


def test_csv_row_count_equals_lock_shots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    approval_sheet.build(LOCK, SHEETS, SOURCE_CHECK, KEYFRAME_GATES, ROUTES)

    rows = list(csv.reader(Path("approval_sheet.csv").open()))
    assert len(rows) - 1 == len(LOCK), "one csv row per shot (excluding header)"


def test_csv_seconds_from_lock_frames(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    approval_sheet.build(LOCK, SHEETS, SOURCE_CHECK, KEYFRAME_GATES, ROUTES)

    table = list(csv.DictReader(Path("approval_sheet.csv").open()))
    seconds = {row["shot"]: float(row["seconds"]) for row in table}
    assert seconds == {"shot_01": 1.0, "shot_02": 2.0, "shot_03": 3.0}


def test_approve_refused_when_gate_file_missing(tmp_path):
    gate_b_path = tmp_path / "gate_b.json"
    gate_b_path.write_text("[]")

    with pytest.raises(ValueError):
        approval_sheet.approve("shot_03", "owner", gate_b_path)

    assert json.loads(gate_b_path.read_text()) == []
