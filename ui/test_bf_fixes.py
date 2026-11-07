"""Backlog-fix regressions (research/TRIAGE_R4_BF_2026-11-07.md): one test per fixed item in ui."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import pipeline  # noqa: E402
import server  # noqa: E402
from server import ApiError, Config  # noqa: E402
from test_r3_fixes import Clock, SLUG, PACK, _w, studio  # noqa: E402,F401  (fixture and helpers)
from test_pipeline import make_images_dir, make_pack, make_runs, make_story  # noqa: E402


# Item 6: row seconds for a bool or None value show as 0
def test_row_seconds_bool_and_none_are_zero(studio):
    d = studio / "stories" / SLUG / PACK
    _w(d / "shots.json", [
        {"id": "S1", "episode": 1, "editorial_duration_sec": True},
        {"id": "S2", "episode": 1, "editorial_duration_sec": None},
    ])
    _w(d / "bible.json", {})
    cfg = Config(studio=studio, flow=studio.parent / "flow", downloads=studio.parent / "dl", python=sys.executable,
                 colab=[], clock=Clock(), disk_paths=(str(studio), str(studio)))
    rows = {r["id"]: r for r in server.read_pack(cfg, f"stories/{SLUG}/{PACK}")["shots"]}
    assert rows["S1"]["seconds"] == 0
    assert rows["S2"]["seconds"] == 0


# Item 7: the preview is single-use once its job exists; a ledger failure is reported, not hidden
def _spend_api(studio, record_spend):
    cfg = Config(studio=studio, flow=studio.parent / "flow", downloads=studio.parent / "dl", python=sys.executable,
                 colab=[], clock=Clock(), disk_paths=(str(studio), str(studio)), spend=True)
    api = server.Api(cfg)
    rec = {"command": "x", "argv": ["a"], "digest": "", "spend": True, "session": "s", "post": False,
           "used": False, "created": 1000.0, "gpu": None, "batch": None, "est": 0, "confirm": "", "story": ""}
    api.tokens["tok"] = rec
    api._spend_gate = lambda est: None
    api._start = lambda *a, **k: SimpleNamespace(id="job1")
    return api, rec


def test_preview_spend_recorded_then_second_run_refused(studio, monkeypatch):
    calls = []
    monkeypatch.setattr(server, "estimate_units", lambda g, b: 0)
    monkeypatch.setattr(server, "batch_clips", lambda c, b: None)
    monkeypatch.setattr(server, "_ops_checks", lambda: SimpleNamespace(record_spend=lambda *a, **k: calls.append(k)))
    api, rec = _spend_api(studio, None)
    assert api.run({"token": "tok", "confirm": ""}) == {"job_id": "job1"}
    assert len(calls) == 1 and rec["used"] is True
    with pytest.raises(ApiError) as exc:
        api.run({"token": "tok", "confirm": ""})
    assert exc.value.code == 403


def test_preview_ledger_failure_refuses_the_job(studio, monkeypatch):
    def broken(*a, **k):
        raise OSError("ledger disk full")
    monkeypatch.setattr(server, "estimate_units", lambda g, b: 0)
    monkeypatch.setattr(server, "batch_clips", lambda c, b: None)
    monkeypatch.setattr(server, "_ops_checks", lambda: SimpleNamespace(record_spend=broken))
    api, rec = _spend_api(studio, None)
    started = []
    api._start = lambda *a, **k: started.append(1) or SimpleNamespace(id="job1")
    with pytest.raises(ApiError) as exc:     # owner 2026-11-07: no ledger row, no job
        api.run({"token": "tok", "confirm": ""})
    assert exc.value.code == 500 and "NOT started" in exc.value.msg
    assert started == [] and rec["used"] is False and not rec.get("recorded")


# Item 8: an unhashable image_id in the JSONL logs does not raise; list and text form match
def test_unhashable_image_id_in_jsonl_does_not_raise(tmp_path):
    studio_dir = tmp_path / "studio"
    studio_dir.mkdir()
    make_story(studio_dir, "s")
    make_pack(studio_dir, "s", "p", shots=[], bible={})
    dq = [{"shot_id": "S1", "version": 1, "image_id": ["IMG1"]}]
    img_dir = make_images_dir(tmp_path, "img", dq_lines=dq, fl_lines=[])
    runs = make_runs(tmp_path, slug="s", pack="p", images_dir=str(img_dir))
    assert pipeline.facts(studio_dir, runs)["pending"] == 1

    img_dir2 = make_images_dir(tmp_path, "img2", dq_lines=dq, fl_lines=[{"image_id": ["IMG1"], "version": 1}])
    (tmp_path / "b").mkdir()
    runs2 = make_runs(tmp_path / "b", slug="s", pack="p", images_dir=str(img_dir2))
    assert pipeline.facts(studio_dir, runs2)["pending"] == 0


# R5: a file deleted between glob() and stat() must not crash the listing (size is None, file still listed)
def test_size_of_vanished_file_is_none_not_a_crash(tmp_path):
    assert server._size(tmp_path / "gone.mp4") is None
    real = tmp_path / "here.mp4"
    real.write_bytes(b"abc")
    assert server._size(real) == 3
