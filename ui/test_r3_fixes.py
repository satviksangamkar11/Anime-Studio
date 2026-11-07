"""Regression tests for the round-3 UI triage fixes (research/TRIAGE_R3_UI_2026-11-07.md)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import pipeline  # noqa: E402
import server  # noqa: E402
from server import Config  # noqa: E402

STATIC = Path(__file__).parent / "static"
SLUG, PACK = "r3_story", "pack_a"


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def _w(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def studio(tmp_path):
    root = tmp_path / "anime_studio"
    (root / "ui" / "runs").mkdir(parents=True)
    return root


# --- pipeline.shot_seconds: zero and negative seconds are 0; only a missing field falls back
def test_shot_seconds_zero_does_not_fall_back_to_seconds():
    assert pipeline.shot_seconds({"editorial_duration_sec": 0, "seconds": 10}) == 0.0


def test_shot_seconds_negative_counts_as_zero():
    assert pipeline.shot_seconds({"editorial_duration_sec": -5}) == 0.0


def test_shot_seconds_missing_field_falls_back_and_positive_kept():
    assert pipeline.shot_seconds({"seconds": 10}) == 10.0
    assert pipeline.shot_seconds({"editorial_duration_sec": 4.5, "seconds": 10}) == 4.5


# --- pipeline.facts: non-dict items are not shots
def test_facts_counts_only_dict_shots(studio):
    story = studio / "stories" / SLUG
    _w(story / PACK / "shots.json", [{"id": "S1"}, "garbage", {"id": "S2"}])
    _w(story / PACK / "bible.json", {})
    f = pipeline.facts(studio, studio / "ui" / "runs", SLUG, PACK)
    assert f["n_shots"] == 2
    assert f["planned_clips"] == 2 * 3   # default takes = 3


# --- pipeline.summary: unhashable ids do not raise; numeric episodes sort numerically
def test_summary_unhashable_id_and_numeric_episode_order(studio):
    story = studio / "stories" / SLUG
    shots = [
        {"id": [1, 2], "episode": 10, "editorial_duration_sec": 1},
        {"id": "S2", "episode": 2, "editorial_duration_sec": 1},
        {"id": "S3", "episode": 10, "editorial_duration_sec": 1},
    ]
    _w(story / PACK / "shots.json", shots)
    _w(story / PACK / "bible.json", {})
    out = pipeline.summary(studio, studio / "ui" / "runs", SLUG, PACK)
    eps = [e["episode"] for e in out["episodes"]]
    assert eps == [2, 10]


# --- server.read_pack: zero seconds shown as 0; negative seconds not summed
def test_read_pack_zero_seconds_and_negative_clamped(studio):
    rel = f"stories/{SLUG}/{PACK}"
    d = studio / "stories" / SLUG / PACK
    _w(d / "shots.json", [
        {"id": "S1", "episode": 1, "editorial_duration_sec": 0, "seconds": 5},
        {"id": "S2", "episode": 1, "editorial_duration_sec": -3},
    ])
    _w(d / "bible.json", {})
    cfg = Config(studio=studio, flow=studio.parent / "flow", downloads=studio.parent / "dl", python=sys.executable,
                 colab=[], clock=Clock(), disk_paths=(str(studio), str(studio)))
    out = server.read_pack(cfg, rel)
    rows = {r["id"]: r for r in out["shots"]}
    assert rows["S1"]["seconds"] == 0
    assert rows["S2"]["seconds"] == 0    # a negative shot counts as 0 in the row too (R4 fix) ...
    assert out["episodes"][0]["seconds"] == 0.0   # ... but the episode total never goes negative


# --- server.Api.run: a start that fails leaves the preview usable
def test_run_failed_start_keeps_preview_usable(studio):
    cfg = Config(studio=studio, flow=studio.parent / "flow", downloads=studio.parent / "dl", python=sys.executable,
                 colab=[], clock=Clock(), disk_paths=(str(studio), str(studio)))
    api = server.Api(cfg)
    rec = {"command": "x", "argv": ["a"], "digest": "", "spend": False, "session": "s", "post": False,
           "used": False, "created": 1000.0, "gpu": None, "batch": None, "est": 0, "confirm": "", "story": ""}
    api.tokens["tok"] = rec

    def boom(*a, **k):
        raise RuntimeError("popen failed")
    api._start = boom
    with pytest.raises(RuntimeError):
        api.run({"token": "tok"})
    assert rec["used"] is False

    api._start = lambda *a, **k: SimpleNamespace(id="job1")
    assert api.run({"token": "tok"}) == {"job_id": "job1"}
    assert rec["used"] is True


# --- static UI: app.js api() timeout and h3Run shot-file guard; pipeline.js busy held during confirm
def test_app_api_has_timeout_and_h3run_guard():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "AbortController" in js and "120000" in js
    start = js.index("function h3Run()")
    body = js[start:start + 400]
    assert "'adv.video.err_pick_shot_file'" in body[:400]


def test_pipeline_js_keeps_busy_while_confirm_open():
    js = (STATIC / "pipeline.js").read_text(encoding="utf-8")
    assert "State.confirmPending = true" in js
    close = js[js.index("function closeModal()"):]
    assert "State.confirmPending" in close[:300]
    # the preview chains must not clear busy while the confirm is still open
    assert js.count("if (!State.confirmPending) State.busy = false;") >= 4
