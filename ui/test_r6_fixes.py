"""Owner-approved fixes of 2026-11-07 (research/TRIAGE_R5_2026-11-07.md): Q-R4-9, Q-R4-10, Q-R4-14, Q-R5-1, Q-R5-2, ledger first."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import pipeline  # noqa: E402
import server  # noqa: E402
from server import ApiError, Config  # noqa: E402
from test_r3_fixes import Clock, SLUG, PACK, _w, studio  # noqa: E402,F401  (fixture and helpers)
from test_u1_routes import PACK_PATH, world  # noqa: E402,F401
from test_pipeline import make_pack, make_runs, make_story  # noqa: E402
from test_bf_fixes import _spend_api  # noqa: E402


def _cfg(studio):
    return Config(studio=studio, flow=studio.parent / "flow", downloads=studio.parent / "dl", python=sys.executable,
                  colab=[], clock=Clock(), disk_paths=(str(studio), str(studio)))


# Q-R4-14: a string episode in shots.json still exports its clips
def test_export_string_episode_matches_the_reel_number(studio, monkeypatch):
    d = studio / "stories" / SLUG / PACK
    _w(d / "shots.json", [{"id": "S1", "episode": "1"}, {"id": "S2", "episode": 2}])
    _w(d / "bible.json", {})
    results = studio / "results"
    (results / "S1").mkdir(parents=True)
    (results / "S1" / "take1.mp4").write_bytes(b"x")
    monkeypatch.setattr(server.Api, "results_roots", lambda self, slug, pack: [results])
    out = server.Api(_cfg(studio)).export(1, SLUG, PACK)
    assert out["shot_ids"] == ["S1"] and [c["shot"] for c in out["clips_in_order"]] == ["S1"]


# Q-R4-10: the seconds total includes a shot without an episode, like the shot count does
def test_summary_seconds_total_includes_episode_less_shots(tmp_path):
    studio_dir = tmp_path / "studio"
    studio_dir.mkdir()
    make_story(studio_dir, "s")
    make_pack(studio_dir, "s", "p", shots=[{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"},
                                           {"id": "S2", "seconds": 3.0, "mode": "fl2va"}], bible={})
    runs = make_runs(tmp_path, slug="s", pack="p")
    out = pipeline.summary(studio_dir, runs, "s", "p")
    assert out["shots"] == 2 and out["seconds"] == 8.0
    assert out["episodes"][0]["seconds"] == 5.0     # the per-episode total is unchanged


# Q-R5-1: a negative row shows 0 seconds and does not reduce the episode total
def test_negative_row_seconds_show_zero(studio):
    d = studio / "stories" / SLUG / PACK
    _w(d / "shots.json", [{"id": "S1", "episode": 1, "editorial_duration_sec": -5}])
    _w(d / "bible.json", {})
    rows = server.read_pack(_cfg(studio), f"stories/{SLUG}/{PACK}")["shots"]
    assert rows[0]["seconds"] == 0


# Q-R4-9: the author panel gets derived, missing and cache
def test_author_status_sends_the_panel_fields(world):
    cfg, api = world
    out = api.author_status(PACK_PATH)
    assert isinstance(out["derived"], dict) and "count" in out["derived"]
    assert isinstance(out["missing"], list)
    assert out["cache"] in ("fresh", "stale or missing", "not needed")


# ledger first (owner 2026-11-07), Q-R5-2: the spend row is written before the job starts
def test_ledger_row_is_written_before_the_job_starts(studio, monkeypatch):
    order = []
    monkeypatch.setattr(server, "estimate_units", lambda g, b: 0)
    monkeypatch.setattr(server, "batch_clips", lambda c, b: None)
    monkeypatch.setattr(server, "_ops_checks", lambda: SimpleNamespace(record_spend=lambda *a, **k: order.append("ledger")))
    api, rec = _spend_api(studio, None)
    api._start = lambda *a, **k: order.append("start") or SimpleNamespace(id="job1")
    assert api.run({"token": "tok", "confirm": ""}) == {"job_id": "job1"}
    assert order == ["ledger", "start"]


# a start failure after the row was written: the retry does not record the same spend twice
def test_start_failure_then_retry_records_the_spend_once(studio, monkeypatch):
    calls = []
    monkeypatch.setattr(server, "estimate_units", lambda g, b: 0)
    monkeypatch.setattr(server, "batch_clips", lambda c, b: None)
    monkeypatch.setattr(server, "_ops_checks", lambda: SimpleNamespace(record_spend=lambda *a, **k: calls.append(1)))
    api, rec = _spend_api(studio, None)
    attempts = []

    def flaky(*a, **k):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("popen failed")
        return SimpleNamespace(id="job1")
    api._start = flaky
    with pytest.raises(OSError):
        api.run({"token": "tok", "confirm": ""})
    assert rec["used"] is False and len(calls) == 1
    assert api.run({"token": "tok", "confirm": ""}) == {"job_id": "job1"}
    assert len(calls) == 1
