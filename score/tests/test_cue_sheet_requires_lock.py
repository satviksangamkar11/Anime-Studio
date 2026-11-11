"""X-19: the cue sheet of a reel is built only from a timeline lock (no lock, no sheet; no --editorial CLI path)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from director.timeline_lock_io import write_lock  # noqa: E402
from score import cue_sheet  # noqa: E402

KALIKA = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "shots.json"


def pack3():
    """The first three Kalika shots: 175, 158 and 209 rendered frames, enough for locked lengths 168, 120 and 192."""
    return json.loads(KALIKA.read_text(encoding="utf-8"))[:3]


def pixel_for(n):
    """Smallest pixel_frames >= n that the lock check accepts ((p - 5) % 17 == 0, 107..345)."""
    return n + ((5 - n) % 17)


def lock_shot(sid, start, n):
    return {"id": sid, "start_frame": start, "edit_frames": n, "pixel_frames": pixel_for(n),
            "trim_in_frame": 0, "trim_out_frame": n, "end_frame_position": n - 1, "error_ms": 0.0}


def lock_dict():
    return {"version": 2, "fps": 24, "total_frames": 480, "total_seconds": 20.0, "shots": [
        lock_shot("SHOT-001", 0, 168), lock_shot("SHOT-002", 168, 120), lock_shot("SHOT-003", 288, 192)]}


def vo_rows():
    """{lang: [rows]} as vo_tracks_report.json gives it: one en row per shot with no speech lines."""
    return {"en": [{"shot": sid, "lang": "en", "editorial": n / 24, "tempo": 1.0, "file": "", "lines": []}
                   for sid, n in (("SHOT-001", 168), ("SHOT-002", 120), ("SHOT-003", 192))]}


def write_inputs(tmp_path):
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps(pack3(), ensure_ascii=False), encoding="utf-8")
    vo = tmp_path / "vo.json"
    vo.write_text(json.dumps(vo_rows()["en"]), encoding="utf-8")
    return shots, vo


def test_lengths_from_lock():
    sheet, report = cue_sheet.build_locked_cue_sheet(pack3(), lock_dict(), vo_rows())
    assert sheet is not None and report["errors"] == [], report
    assert sheet["total_frames"] == 480 and sheet["total_s"] == 20.0
    assert [s["duration_s"] for s in sheet["shots"]] == [7.0, 5.0, 8.0]


def test_no_vo_report_is_an_error():
    sheet, report = cue_sheet.build_locked_cue_sheet(pack3(), lock_dict(), [])
    assert sheet is None and [e["code"] for e in report["errors"]] == ["NO_VO_REPORT"]


def test_lock_total_mismatch_is_an_error():
    lock = lock_dict()
    lock["total_frames"] = 481
    sheet, report = cue_sheet.build_locked_cue_sheet(pack3(), lock, vo_rows())
    assert sheet is None and any(e["code"] == "LOCK_MISMATCH" for e in report["errors"])


def test_bpm_snap_copied_and_act_checked():
    lock = lock_dict()
    for row in lock["shots"]:
        row.update({"bpm": 128.0, "snap": "8th"})
    sheet, report = cue_sheet.build_locked_cue_sheet(pack3(), lock, vo_rows())
    assert sheet is not None, report
    assert all(s["bpm"] == 128.0 and s["snap"] == "8th" for s in sheet["shots"])
    lock["shots"][0]["act"] = "not-the-pack-act"
    sheet, report = cue_sheet.build_locked_cue_sheet(pack3(), lock, vo_rows())
    assert sheet is None and any(e["code"] == "ACT_MISMATCH" for e in report["errors"])


def test_no_lock_exit_2(tmp_path, capsys):
    shots, vo = write_inputs(tmp_path)
    rc = cue_sheet.main(["--shots", str(shots), "--vo-report", str(vo), "--out", str(tmp_path / "o.json")])
    assert rc == 2 and "--lock" in capsys.readouterr().err
    assert not (tmp_path / "o.json").exists()


def test_no_vo_report_cli_exit_2(tmp_path, capsys):
    shots, _ = write_inputs(tmp_path)
    lk = tmp_path / "lock"
    lk.mkdir()
    lock_path = lk / "timeline_lock_v1.json"
    wav = tmp_path / "picture.wav"
    wav.write_bytes(b"picture")
    write_lock(lock_path, lock_dict()["shots"], [str(wav)], {"reel": 1})
    rc = cue_sheet.main(["--shots", str(shots), "--lock", str(lock_path), "--out", str(tmp_path / "o.json")])
    assert rc == 2 and "--vo-report" in capsys.readouterr().err


def test_stale_wav_exit_2(tmp_path, capsys):
    shots, vo = write_inputs(tmp_path)
    wav = tmp_path / "picture.wav"
    wav.write_bytes(b"picture")
    lock_path = tmp_path / "timeline_lock_v1.json"
    write_lock(lock_path, lock_dict()["shots"], [str(wav)], {"reel": 1})
    wav.write_bytes(b"picture-changed")          # one input byte-run changed: the lock is stale
    rc = cue_sheet.main(["--shots", str(shots), "--lock", str(lock_path), "--vo-report", str(vo),
                         "--out", str(tmp_path / "o.json")])
    assert rc == 2 and "stale" in capsys.readouterr().err
    assert not (tmp_path / "o.json").exists()


def test_fresh_lock_builds_the_sheet(tmp_path):
    shots, vo = write_inputs(tmp_path)
    wav = tmp_path / "picture.wav"
    wav.write_bytes(b"picture")
    lock_path = tmp_path / "timeline_lock_v1.json"
    write_lock(lock_path, lock_dict()["shots"], [str(wav)], {"reel": 1})
    out = tmp_path / "o.json"
    rc = cue_sheet.main(["--shots", str(shots), "--lock", str(lock_path), "--vo-report", str(vo), "--out", str(out)])
    assert rc == 0 and out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["total_frames"] == 480


def test_cli_has_no_editorial_flag(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cue_sheet.main(["--help"])
    text = capsys.readouterr().out
    assert "--lock" in text and "--editorial" not in text and "--voice-windows" not in text
    shots, vo = write_inputs(tmp_path)
    with pytest.raises(SystemExit) as exc:   # W-12: the flag itself is gone; argparse refuses it
        cue_sheet.main(["--shots", str(shots), "--editorial", str(vo), "--out", str(tmp_path / "o.json")])
    assert exc.value.code == 2
