"""Round-3 regressions (triage R3-DIR): unusable saved answers stop the run as StageFailed, not a traceback."""
import json

import pytest

import test_write_pack_staged as base
import write_pack
from test_write_pack_staged import fake_claude, no_network, no_validator, story  # noqa: F401  (pytest fixtures)


def test_stage_1_with_no_episode_numbers_is_a_stage_failure(tmp_path, story, fake_claude, monkeypatch):
    bad = "```json story\n" + json.dumps({"episodes": [{"title": "Intro"}]}) + "\n```"
    monkeypatch.setitem(base.CANNED, "1", bad)
    with pytest.raises(write_pack.StageFailed, match="stage 1 answer is unusable"):
        base.staged(story, tmp_path / "pack", "--via", "claude")
    assert [c["name"] for c in fake_claude] == ["1", "2"]     # stage 2 runs before the episode list is read


def test_single_call_with_an_unparsable_saved_answer_is_a_stage_failure(tmp_path):
    out = tmp_path / "pack"
    out.mkdir()
    (out / "raw_response.json").write_text(write_pack.envelope("no shots block here", "stop", "claude", "opus"), encoding="utf-8")
    with pytest.raises(write_pack.StageFailed, match="saved answer is unusable"):
        write_pack.run_single("story text", out, "claude", "opus", "medium", False)
    assert not (out / "shots.json").exists()
