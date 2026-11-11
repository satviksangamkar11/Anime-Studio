"""W-04b: build_vo_tracks reads the timeline lock and never speeds a voice up.

Offline: no ffmpeg (render_shot is monkeypatched or subprocess.run is captured), no network, no model call.
"""
import json
import sys
import wave
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_vo_tracks as bvt  # noqa: E402
import timeline_lock_io as tl  # noqa: E402


def _wav(path, seconds):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * int(round(seconds * 24000)))


def _shot(sid, start, n):
    """A lock row that passes timeline_lock_io._check_shots: pixel in 107..345 with (pixel - 5) % 17 == 0."""
    pixel = max(n, 107)
    pixel += (5 - pixel) % 17
    return {"id": sid, "start_frame": start, "edit_frames": n, "pixel_frames": pixel,
            "trim_in_frame": 0, "trim_out_frame": n, "end_frame_position": n - 1, "error_ms": 0.0}


def _pack(tmp_path, ids=("SHOT-001",)):
    """Pack whose shots have one English narration line at 0.5 s, 2.4 s of speech each."""
    pack = tmp_path / "pack"
    pack.mkdir()
    rows = [{"id": sid, "audio_and_dialogue_track": {
        "narration_by_lang": {"en": {"text": "x", "time_range": [0.5, 3.0]}}, "dialogue_by_lang": {}}} for sid in ids]
    (pack / "shots.json").write_text(json.dumps(rows), encoding="utf-8")
    raw = tmp_path / "raw"
    for sid in ids:
        _wav(raw / f"{sid}-N.en.wav", 2.4)
    return pack, raw


def _lock(tmp_path, pack, shots):
    path = tmp_path / "timeline_lock_v1.json"
    tl.write_lock(path, shots, [str(pack / "shots.json")], {"tempo": 1.0})
    return path


def test_max_tempo_is_one_no_speed_up():
    assert bvt.MAX_TEMPO == 1.0


def test_lock_length_fits_at_natural_speed():
    # 72 frames = 3.0 s; the line starts at 0.5 s and lasts 2.4 s, so it ends at 2.9 s = cut - TAIL
    tempo, placed = bvt.pack_shot([{"id": "a", "start": 0.5, "natural": 2.4}], 3.0)
    assert tempo == 1.0
    assert placed[0]["end"] == pytest.approx(2.9)


def test_exact_boundary_fits_without_error():
    tempo, placed = bvt.pack_shot([{"id": "a", "start": 0.0, "natural": 3.4}], 3.5)
    assert tempo == 1.0 and placed[0]["end"] == pytest.approx(3.4)


def test_a_line_that_only_fits_when_sped_up_is_refused():
    # at 1.1x it would fit; with no speed-up it must be reported, never squeezed
    with pytest.raises(ValueError, match="does not fit"):
        bvt.pack_shot([{"id": "a", "start": 0.0, "natural": 3.5}], 3.5)


def test_render_has_no_atempo(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(bvt.subprocess, "run", lambda args, check: calls.append(args))
    placed = [{"id": "SHOT-001-N", "start": 0.5, "length": 2.4, "end": 2.9}]
    bvt.render_shot(placed, tmp_path, "en", 3.0, tmp_path / "o.wav")
    fc = calls[0][calls[0].index("-filter_complex") + 1]    # the filter only; tmp_path itself has the test name in it
    assert "atempo" not in fc and "adelay=500|500" in fc


def test_build_uses_the_lock_length_not_the_editorial_file(tmp_path, monkeypatch):
    pack, raw = _pack(tmp_path)
    (pack / "editorial_by_lang.json").write_text(json.dumps({"SHOT-001": 3.5}), encoding="utf-8")
    lock = _lock(tmp_path, pack, [_shot("SHOT-001", 0, 72)])
    seen = []
    monkeypatch.setattr(bvt, "render_shot", lambda placed, raw_dir, lang, editorial, out: seen.append(editorial))
    report, problems = bvt.build(str(pack), str(raw), str(tmp_path / "out"), ["en"], lock=str(lock))
    assert problems == []
    assert seen == [pytest.approx(3.0)]
    assert report[0]["edit_frames"] == 72


def test_shot_missing_from_the_lock_is_a_problem(tmp_path, monkeypatch):
    pack, raw = _pack(tmp_path, ids=("SHOT-001", "SHOT-002"))
    lock = _lock(tmp_path, pack, [_shot("SHOT-001", 0, 72)])
    monkeypatch.setattr(bvt, "render_shot", lambda *a, **k: None)
    report, problems = bvt.build(str(pack), str(raw), str(tmp_path / "out"), ["en"], lock=str(lock))
    assert problems == ["SHOT-002: not in the timeline lock"]
    assert [r["shot"] for r in report] == ["SHOT-001"]


def test_stale_lock_stops_before_any_render(tmp_path, monkeypatch, capsys):
    pack, raw = _pack(tmp_path)
    lock = _lock(tmp_path, pack, [_shot("SHOT-001", 0, 72)])
    (pack / "shots.json").write_text("[]", encoding="utf-8")   # an input changed after the lock
    called = []
    monkeypatch.setattr(bvt, "render_shot", lambda *a, **k: called.append(a))
    out = tmp_path / "out"
    out.mkdir()
    rc = bvt.main(["--pack", str(pack), "--raw", str(raw), "--out", str(out), "--lock", str(lock)])
    assert rc == 2 and called == []
    assert "timeline_lock" in capsys.readouterr().err


def test_missing_lock_file_returns_2(tmp_path, capsys):
    pack, raw = _pack(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    rc = bvt.main(["--pack", str(pack), "--raw", str(raw), "--out", str(out), "--lock", str(tmp_path / "none.json")])
    assert rc == 2
