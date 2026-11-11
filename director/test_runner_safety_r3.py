import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import runner_safety


def test_stop_decision_missing_id_raises_even_when_not_done(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        runner_safety.stop_decision(
            ["a", "zz"],
            str(tmp_path),
            False,
            expected_frames={"a": 1},
        )


def test_stop_decision_not_done_still_not_stop(tmp_path, monkeypatch):
    result = runner_safety.stop_decision(
        ["a"],
        str(tmp_path),
        False,
        expected_frames={"a": 1},
    )
    assert result["stop"] is False
    assert result["reason"] == "not finished"
    assert result["missing"] == []


def test_stop_decision_empty_ids_behaviour(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        runner_safety.stop_decision(
            [],
            str(tmp_path),
            True,
            expected_frames={},
        )
