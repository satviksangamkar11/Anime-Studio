"""G12: cue rows for Ableton written by the CLI (cue_sheet.json["cue_rows"] and cue_rows.csv), hits from blocking."""
import csv
import json

from score import cue_sheet as cs


def _sheet():
    shots = [{"id": "SHOT-001", "start_frame": 0, "frames": 96, "start_s": 0.0, "end_s": 4.0, "impacts": [],
              "beats": [], "voice_rest": None},
             {"id": "SHOT-002", "start_frame": 96, "frames": 144, "start_s": 4.0, "end_s": 10.0, "impacts": [],
              "beats": [], "voice_rest": None}]
    return {"fps": 24, "total_s": 10.0, "total_frames": 240, "shots": shots}


BLK = {"SHOT-002": {"shot_id": "SHOT-002", "voice_rest": [1.0, 3.0],
                    "sound_cues": [{"t": 1.5, "text": "conch blast", "kind": "hit"},
                                   {"t": 0.0, "text": "river wind", "kind": "bed"}]}}


def test_cue_rows_from_blocking_sound_cues():
    rows = cs.cue_rows(_sheet(), blocking=BLK)["rows"]
    hits = [r for r in rows if r["kind"] == "hit"]
    assert [(h["shot"], h["t_frame"], h["source"]) for h in hits] == [("SHOT-002", 96 + 36, "conch blast")]
    rest = [r for r in rows if r["kind"] == "rest"]
    assert rest[0]["voice_rest"] == [96 + 24, 96 + 72]  # shot-relative 1.0-3.0 s -> reel frames


def test_no_blocking_keeps_old_rows():
    assert cs.cue_rows(_sheet())["rows"] == cs.cue_rows(_sheet(), blocking=None)["rows"]


def test_cli_writes_cue_rows(tmp_path, monkeypatch):
    shots = tmp_path / "shots.json"
    shots.write_text("[]", encoding="utf-8")
    vo = tmp_path / "vo.json"
    vo.write_text(json.dumps([{"lang": "en"}]), encoding="utf-8")
    lock = tmp_path / "lock.json"
    bdir = tmp_path / "blocking"
    bdir.mkdir()
    (bdir / "SHOT-002.json").write_text(json.dumps(BLK["SHOT-002"]), encoding="utf-8")
    report = {"ok": True, "errors": [], "warnings": [],
              "stats": {"shots": 2, "total_s": 10.0, "cuts": 1, "hard_cuts": 0, "acts": 1, "voice_coverage": 0.5,
                        "voice_gaps": 0, "impacts": 0}}
    monkeypatch.setattr(cs, "load_lock", lambda p: {"inputs": {}, "params": {}})
    monkeypatch.setattr(cs, "verify_lock", lambda *a, **k: None)
    monkeypatch.setattr(cs, "build_locked_cue_sheet", lambda *a, **k: (_sheet(), report))
    out = tmp_path / "score" / "cue_sheet.json"
    rc = cs.main(["--shots", str(shots), "--vo-report", str(vo), "--lock", str(lock), "--out", str(out),
                  "--blocking-dir", str(bdir)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    kinds = [r["kind"] for r in data["cue_rows"]["rows"]]
    assert "hit" in kinds and "rest" in kinds
    with open(tmp_path / "score" / "cue_rows.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ["frame", "timecode", "kind", "source", "voice_rest"]
    hit = next(r for r in rows if r["kind"] == "hit")
    assert (hit["frame"], hit["timecode"], hit["source"]) == ("132", "00:00:05:12", "conch blast")
    rest = next(r for r in rows if r["kind"] == "rest")
    assert rest["voice_rest"] == "120-168"
