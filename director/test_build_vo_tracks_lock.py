"""W-04: build_vo_tracks reads the editorial length of each shot from the timeline lock (frames / fps * retime)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_vo_tracks


def lock():
    return {"fps": 24, "shots": [
        {"id": "SHOT-001", "start_frame": 0, "edit_frames": 120},
        {"id": "SHOT-002", "start_frame": 120, "edit_frames": 96, "retime": {"hi": 1.04}}]}


def test_editorial_from_lock_plain():
    assert build_vo_tracks.editorial_from_lock(lock(), "SHOT-001", "en") == pytest.approx(5.0)


def test_editorial_from_lock_ignores_retime_the_picture_clock_is_never_retimed():
    # W-04: the cut uses the unretimed lock frames; a retime here would be a second clock
    assert build_vo_tracks.editorial_from_lock(lock(), "SHOT-002", "hi") == pytest.approx(4.0)
    assert build_vo_tracks.editorial_from_lock(lock(), "SHOT-002", "en") == pytest.approx(4.0)


def test_unknown_shot_raises():
    with pytest.raises((KeyError, ValueError)):
        build_vo_tracks.editorial_from_lock(lock(), "SHOT-009", "en")


def test_apply_lock_overwrites_editorial_of_rows():
    rows = [{"id": "SHOT-001", "editorial_duration_sec": 9.9}, {"id": "SHOT-002", "editorial_duration_sec": 9.9}]
    out = build_vo_tracks.apply_lock(rows, lock(), "hi")
    assert [round(r["editorial_duration_sec"], 3) for r in out] == [5.0, 4.0]
    assert rows[0]["editorial_duration_sec"] == 9.9          # input rows untouched


def test_apply_lock_refuses_a_row_missing_from_the_lock():
    with pytest.raises((KeyError, ValueError)):
        build_vo_tracks.apply_lock([{"id": "SHOT-777", "editorial_duration_sec": 3.0}], lock(), "en")


def test_main_accepts_lock_flag(tmp_path, monkeypatch):
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(lock()), encoding="utf-8")
    seen = {}

    def fake_build(pack, raw, out, langs, lock=None):
        seen["lock"] = lock
        return [], []
    monkeypatch.setattr(build_vo_tracks, "build", fake_build)
    out = tmp_path / "o"
    out.mkdir()
    rc = build_vo_tracks.main(["--pack", "p", "--raw", "r", "--out", str(out), "--lock", str(path)])
    assert rc == 0 and seen["lock"] == str(path)
