"""W-05b: the cue sheet reads the timeline lock (frames, bpm/snap/cue/act copied, VO reports required, stale lock exit 2).

Offline. Uses the Kalika pack shots (repo fixture) and synthetic locks written with timeline_lock_io.write_lock.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from director.timeline_lock_io import write_lock  # noqa: E402
from score import cue_sheet  # noqa: E402

KALIKA = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "shots.json"


def pack2():
    return json.loads(KALIKA.read_text(encoding="utf-8"))[:2]


def _shot(sid, start, n, bpm=128, snap=True, cue="c1", act_start=0):
    pixel = max(n, 107)
    pixel += (5 - pixel) % 17
    return {"id": sid, "start_frame": start, "edit_frames": n, "pixel_frames": pixel, "trim_in_frame": 0,
            "trim_out_frame": n, "end_frame_position": n - 1, "error_ms": 0.0, "bpm": bpm, "snap": snap,
            "cue": cue, "act_start_frame": act_start}


def lock2(bpm2=128, snap2=False):
    shots = [_shot("SHOT-001", 0, 79), _shot("SHOT-002", 79, 72, bpm=bpm2, snap=snap2)]
    return {"version": 2, "fps": 24, "total_frames": 151, "total_seconds": round(151 / 24, 6), "shots": shots}


def vo_rows2():
    return [{"shot": "SHOT-001", "lang": "en", "editorial": 79 / 24, "tempo": 1.0, "file": "", "lines": []},
            {"shot": "SHOT-002", "lang": "en", "editorial": 72 / 24, "tempo": 1.0, "file": "", "lines": []}]


def test_lock_sets_frames():
    sheet, report = cue_sheet.build_locked_cue_sheet(pack2(), lock2(), vo_rows2())
    assert sheet is not None and report["errors"] == [], report
    assert [s["frames"] for s in sheet["shots"]] == [79, 72]
    assert sheet["total_frames"] == 151
    assert sheet["shots"][1]["start_frame"] == 79


def test_lock_requires_vo_reports():
    for vo in (None, []):
        sheet, report = cue_sheet.build_locked_cue_sheet(pack2(), lock2(), vo)
        assert sheet is None
        assert [e["code"] for e in report["errors"]] == ["NO_VO_REPORT"]


def test_lock_frames_mismatch_blocks_the_sheet(monkeypatch):
    real = cue_sheet.build_episodes

    def shifted(shots, fps):
        episodes, problems = real(shots, fps)
        episodes[0]["shots"][0]["frames"] += 1          # core.timeline disagrees with the lock by one frame
        return episodes, problems
    monkeypatch.setattr(cue_sheet, "build_episodes", shifted)
    sheet, report = cue_sheet.build_locked_cue_sheet(pack2(), lock2(), vo_rows2())
    assert sheet is None
    assert [e["code"] for e in report["errors"]] == ["LOCK_FRAMES_MISMATCH"]


def test_lock_bpm_snap_cue_and_act_on_rows():
    sheet, _ = cue_sheet.build_locked_cue_sheet(pack2(), lock2(), vo_rows2())
    second = sheet["shots"][1]
    assert second["bpm"] == 128 and second["snap"] is False      # a non-snap shot still carries its bpm
    assert sheet["shots"][0]["cue"] == "c1" and sheet["shots"][0]["act_start_frame"] == 0
    assert second["cue"] == "c1" and second["act_start_frame"] == 0


def test_lock_shot_missing_from_lock_is_an_error():
    lock = lock2()
    lock["shots"] = lock["shots"][:1]
    lock["total_frames"], lock["total_seconds"] = 79, round(79 / 24, 6)
    sheet, report = cue_sheet.build_locked_cue_sheet(pack2(), lock, vo_rows2())
    assert sheet is None and any(e["code"] == "LOCK_SHOT_MISSING" for e in report["errors"])


def _inputs(tmp_path):
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps(pack2(), ensure_ascii=False), encoding="utf-8")
    vo = tmp_path / "vo.json"
    vo.write_text(json.dumps([{**r, "lang": "en"} for r in vo_rows2()]), encoding="utf-8")
    lock = tmp_path / "timeline_lock_v1.json"
    write_lock(lock, lock2()["shots"], [str(shots)], {"tempo": 1.0})
    return shots, vo, lock


def test_main_missing_lock_exit_2(tmp_path, capsys):
    shots, vo, _ = _inputs(tmp_path)
    rc = cue_sheet.main(["--shots", str(shots), "--vo-report", str(vo), "--lock", str(tmp_path / "none.json"),
                         "--out", str(tmp_path / "cue.json")])
    assert rc == 2


def test_main_stale_lock_exit_2(tmp_path, capsys):
    shots, vo, lock = _inputs(tmp_path)
    shots.write_text("[]", encoding="utf-8")                  # an input changed after the lock
    rc = cue_sheet.main(["--shots", str(shots), "--vo-report", str(vo), "--lock", str(lock),
                         "--out", str(tmp_path / "cue.json")])
    assert rc == 2


def test_main_fresh_lock_writes_the_sheet(tmp_path):
    shots, vo, lock = _inputs(tmp_path)
    out = tmp_path / "cue.json"
    rc = cue_sheet.main(["--shots", str(shots), "--vo-report", str(vo), "--lock", str(lock), "--out", str(out)])
    assert rc == 0 and json.loads(out.read_text(encoding="utf-8"))["total_frames"] == 151
