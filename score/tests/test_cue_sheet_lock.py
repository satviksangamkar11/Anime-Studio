"""W-05: the cue sheet takes shot lengths from the timeline lock (edit_frames / fps), one clock for picture, voice and music."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from score import cue_sheet


def lock():
    return {"fps": 24, "shots": [
        {"id": "SHOT-001", "start_frame": 0, "edit_frames": 120},
        {"id": "SHOT-002", "start_frame": 120, "edit_frames": 96}]}


def test_apply_lock_sets_editorial_seconds_from_frames():
    shots = [{"id": "SHOT-001", "editorial_duration_sec": 9.0}, {"id": "SHOT-002", "editorial_duration_sec": 9.0}]
    out, errors = cue_sheet.apply_lock(shots, lock())
    assert errors == []
    assert [s["editorial_duration_sec"] for s in out] == [5.0, 4.0]
    assert shots[0]["editorial_duration_sec"] == 9.0            # input untouched


def test_apply_lock_reports_a_shot_missing_from_the_lock():
    out, errors = cue_sheet.apply_lock([{"id": "SHOT-009", "editorial_duration_sec": 3.0}], lock())
    assert [e["where"] for e in errors if e["code"] == "LOCK_SHOT_MISSING"] == ["SHOT-009"]


def test_apply_lock_reports_a_lock_shot_missing_from_the_pack():
    out, errors = cue_sheet.apply_lock([{"id": "SHOT-001", "editorial_duration_sec": 3.0}], lock())
    assert [e["code"] for e in errors] == ["LOCK_SHOT_EXTRA"] and errors[0]["where"] == "SHOT-002"


def test_apply_lock_refuses_a_bad_lock():
    out, errors = cue_sheet.apply_lock([{"id": "SHOT-001"}], {"shots": "x"})
    assert [e["code"] for e in errors] == ["LOCK_SHAPE"]


def test_build_cue_sheet_stops_on_lock_errors():
    sheet, report = cue_sheet.build_cue_sheet([{"id": "SHOT-777", "editorial_duration_sec": 3.0}], timeline_lock=lock())
    assert sheet is None and not report["ok"]
    assert any(e["code"] == "LOCK_SHOT_MISSING" for e in report["errors"])


def test_main_refuses_editorial_flag_after_w12(tmp_path, capsys):
    """W-12: --editorial is removed from the CLI; argparse refuses it (exit 2) even next to a valid --lock."""
    shots = tmp_path / "s.json"
    shots.write_text("[]", encoding="utf-8")
    lk = tmp_path / "l.json"
    lk.write_text(json.dumps(lock()), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        cue_sheet.main(["--shots", str(shots), "--lock", str(lk), "--editorial", str(lk), "--out", str(tmp_path / "o.json")])
    assert exc.value.code == 2
