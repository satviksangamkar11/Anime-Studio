"""Regression tests for the round-4 UI triage fixes (research/TRIAGE_R4_2026-11-07.md)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import pipeline  # noqa: E402
import server  # noqa: E402
from server import Config  # noqa: E402
from test_r3_fixes import Clock, SLUG, PACK, _w, studio  # noqa: E402,F401  (fixture and helpers)


def test_summary_unhashable_episode_does_not_raise(studio):
    story = studio / "stories" / SLUG
    _w(story / PACK / "shots.json", [{"id": "S1", "episode": [1], "editorial_duration_sec": 2},
                                     {"id": "S2", "episode": 2, "editorial_duration_sec": 1}])
    _w(story / PACK / "bible.json", {})
    out = pipeline.summary(studio, studio / "ui" / "runs", SLUG, PACK)
    assert {str(e["episode"]) for e in out["episodes"]} == {"[1]", "2"}


def test_read_pack_unhashable_episode_does_not_raise(studio):
    rel = f"stories/{SLUG}/{PACK}"
    d = studio / "stories" / SLUG / PACK
    _w(d / "shots.json", [{"id": "S1", "episode": {"a": 1}, "editorial_duration_sec": 2}])
    _w(d / "bible.json", {})
    cfg = Config(studio=studio, flow=studio.parent / "flow", downloads=studio.parent / "dl", python=sys.executable,
                 colab=[], clock=Clock(), disk_paths=(str(studio), str(studio)))
    out = server.read_pack(cfg, rel)
    assert out["episodes"][0]["seconds"] == 2.0


def test_zero_seconds_shot_without_episode_clears_all_have_seconds(studio):
    story = studio / "stories" / SLUG
    _w(story / PACK / "shots.json", [{"id": "S1", "editorial_duration_sec": 2, "episode": 1},
                                     {"id": "S2", "editorial_duration_sec": 0}])   # no episode, zero seconds
    _w(story / PACK / "bible.json", {})
    out = pipeline.summary(studio, studio / "ui" / "runs", SLUG, PACK)
    seconds_check = next(c for c in out["checks"] if c["name"] == "every shot has seconds>0")
    assert seconds_check["ok"] is False


def test_string_takes_in_project_json_does_not_break_the_summary(studio):
    _w(studio / "ui" / "runs" / "project.json", {"story_slug": SLUG, "pack": PACK, "takes": "3"})
    story = studio / "stories" / SLUG
    _w(story / PACK / "shots.json", [{"id": "S1", "episode": 1, "editorial_duration_sec": 2}])
    _w(story / PACK / "bible.json", {})
    out = pipeline.summary(studio, studio / "ui" / "runs", SLUG, PACK)
    assert out["video"]["takes"] == 3
    assert isinstance(out["estimate"]["minutes"], float)


def test_takes_outside_one_to_ten_falls_back_to_three():
    assert pipeline.takes_of({"takes": 0}) == 3
    assert pipeline.takes_of({"takes": 11}) == 3
    assert pipeline.takes_of({"takes": 5}) == 5
