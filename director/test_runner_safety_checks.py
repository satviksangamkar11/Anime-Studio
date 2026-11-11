import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import runner_safety


def test_can_stop_missing_id_in_expected_frames_raises():
    with pytest.raises(ValueError):
        runner_safety.can_stop(["a", "b"], "results", expected_frames={"a": 100})


def test_stop_decision_missing_id_raises():
    with pytest.raises(ValueError):
        runner_safety.stop_decision(["a", "b"], "results", True, expected_frames={"a": 100})


def test_preflight_script_path_directory_fails(tmp_path, monkeypatch):
    failures = runner_safety.preflight(
        ["http://example.com"],
        tmp_path,
        min_free_gb=0.0,
        script_path=tmp_path,
        head=lambda url: 200,
        disk_usage=shutil.disk_usage,
    )
    assert any("not a file" in f for f in failures)


def test_preflight_script_path_file_ok(tmp_path, monkeypatch):
    script_file = tmp_path / "script.py"
    script_file.write_text("print(1)")
    failures = runner_safety.preflight(
        ["http://example.com"],
        tmp_path,
        min_free_gb=0.0,
        script_path=str(script_file),
        head=lambda url: 200,
        disk_usage=shutil.disk_usage,
    )
    assert not any("not a file" in f for f in failures)


def test_preflight_missing_script_path_still_cannot_stat(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist.py"
    failures = runner_safety.preflight(
        ["http://example.com"],
        tmp_path,
        min_free_gb=0.0,
        script_path=str(missing),
        head=lambda url: 200,
        disk_usage=shutil.disk_usage,
    )
    assert any("cannot stat" in f for f in failures)


def test_missing_script_path_gives_exactly_one_failure(tmp_path):
    missing = tmp_path / "nope.py"
    failures = runner_safety.preflight(
        ["http://example.com"],
        tmp_path,
        min_free_gb=0.0,
        script_path=str(missing),
        head=lambda url: 200,
        disk_usage=shutil.disk_usage,
    )
    script_failures = [f for f in failures if "script" in f]
    assert len(script_failures) == 1
    assert "cannot stat" in script_failures[0]
    assert "not a file" not in script_failures[0]
