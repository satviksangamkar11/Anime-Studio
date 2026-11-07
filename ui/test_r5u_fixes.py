"""Regression tests for the R5U fixes (research/TRIAGE_R5_UI_FIX_2026-11-07.md)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import pipeline  # noqa: E402
import server  # noqa: E402
from server import Config  # noqa: E402
from test_r3_fixes import Clock, SLUG, PACK, _w, studio  # noqa: E402,F401  (fixture and helpers)


def test_scope_ids_unhashable_shot_id_does_not_raise(studio):
    shots = studio / "shots.json"
    _w(shots, [{"id": ["x"], "episode": 1}, {"id": "S1", "episode": 1}])
    assert server.scope_ids(shots, "shots", ["S1"]) == ["S1"]
    with pytest.raises(server.ApiError):   # a real missing id is still refused
        server.scope_ids(shots, "shots", ["NOPE"])


def test_export_unhashable_shot_id_does_not_raise(studio, monkeypatch):
    d = studio / "stories" / SLUG / PACK
    _w(d / "shots.json", [{"id": ["x"], "episode": 1}, {"id": "S1", "episode": 1}])
    _w(d / "bible.json", {})
    results = studio / "results"
    (results / "S1").mkdir(parents=True)
    (results / "S1" / "take1.mp4").write_bytes(b"x")
    cfg = Config(studio=studio, flow=studio.parent / "flow", downloads=studio.parent / "dl", python=sys.executable,
                 colab=[], clock=Clock(), disk_paths=(str(studio), str(studio)))
    monkeypatch.setattr(server.Api, "results_roots", lambda self, slug, pack: [results])
    out = server.Api(cfg).export(1, SLUG, PACK)
    assert [c["shot"] for c in out["clips_in_order"]] == ["S1"]


def test_facts_unhashable_version_does_not_raise(studio):
    runs = studio / "ui" / "runs"
    images = studio / "images"
    _w(runs / "project.json", {"story_slug": SLUG, "pack": PACK, "images_dir": str(images)})
    _w(studio / "stories" / SLUG / PACK / "shots.json", [{"id": "S1"}])
    _w(studio / "stories" / SLUG / PACK / "bible.json", {})
    images.mkdir(parents=True)
    (images / "download_queue.jsonl").write_text(
        json.dumps({"shot_id": "S1", "version": [1], "image_id": "img1"}) + "\n", encoding="utf-8")
    (images / "flow_log.jsonl").write_text(
        json.dumps({"image_id": "img1", "version": {"n": 1}}) + "\n", encoding="utf-8")
    f = pipeline.facts(studio, runs, SLUG, PACK)
    assert f["pending"] == 1   # no TypeError; the queued image has no matching flow entry


def test_gate_d_plan_without_reasons_does_not_raise(studio, monkeypatch):
    plan = {"steps": [{"id": "gate_d", "status": "blocked"}], "languages": ["hi"], "episodes": []}
    rows = pipeline._per_language(plan, studio / "render", ["hi"])
    assert len(rows) == 1
    monkeypatch.setattr(pipeline, "h3_plan", lambda s, slug, pack: {"error": None, "steps": [{"id": "gate_d", "status": "blocked"}]})
    probs = pipeline.gate_d_problems(studio, SLUG, PACK)
    assert "Gate D not ready" in probs


def test_read_pack_string_seconds_row_is_zero(studio):
    rel = f"stories/{SLUG}/{PACK}"
    d = studio / "stories" / SLUG / PACK
    _w(d / "shots.json", [{"id": "S1", "episode": 1, "editorial_duration_sec": "12"},
                          {"id": "S2", "episode": 1, "editorial_duration_sec": 4.5}])
    _w(d / "bible.json", {})
    cfg = Config(studio=studio, flow=studio.parent / "flow", downloads=studio.parent / "dl", python=sys.executable,
                 colab=[], clock=Clock(), disk_paths=(str(studio), str(studio)))
    out = server.read_pack(cfg, rel)
    rows = {r["id"]: r["seconds"] for r in out["shots"]}
    assert rows["S1"] == 0
    assert rows["S2"] == 4.5
