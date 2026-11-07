"""Owner-approved fixes of 2026-11-07 (research/TRIAGE_R5_2026-11-07.md): Q-R4-5, Q-R4-8 and Q-R5-1."""
import pytest

import h3.render_controller as rc
import h3.schema_and_linter as sl
from h3.tests.synth import build_story


# Q-R5-1: every exception type that _qc_result wraps is blocked, none is raised
@pytest.mark.parametrize("exc", [KeyError("k"), TypeError("t"), ValueError("v"), AttributeError("a")])
def test_qc_result_wraps_every_listed_exception_type(monkeypatch, exc):
    def broken(shots, measurers=None):
        raise exc
    monkeypatch.setattr(rc, "final_qc", broken)
    res = rc._qc_result([{"episode": {"episode_id": "E1", "shots": []}}], {})
    assert res["ok"] is False
    assert f"Step 9 QC not run: {type(exc).__name__}" in res["reasons"][0]


# Q-R4-5: no own picture_1 but a reuse id and an upstream shot: picture_1 is the upstream picture_2 (REUSED)
def test_resolve_keyframes_reuses_upstream_when_own_picture_is_absent():
    up = {"fl2va_keyframes": {"picture_2_path": "up_end.png"}}
    shot = {"fl2va_keyframes": {"picture_1_path": None, "picture_2_path": "end.png", "reuse_upstream_b_id": "UP"}}
    assert sl.resolve_keyframes(shot, up, "root") == {"picture_1": "up_end.png", "picture_2": "end.png", "reused": True}


def test_resolve_keyframes_without_reuse_id_keeps_picture_1_none():
    up = {"fl2va_keyframes": {"picture_2_path": "up_end.png"}}
    shot = {"fl2va_keyframes": {"picture_1_path": None, "picture_2_path": "end.png"}}
    assert sl.resolve_keyframes(shot, up, "root") == {"picture_1": None, "picture_2": "end.png", "reused": False}
    assert sl.resolve_keyframes(shot, None, "root")["reused"] is False


# Q-R4-8: a non-object shot row is a lint error entry, never a crash
def test_lint_shot_non_object_is_an_error_entry():
    res = sl.lint_shot("junk", {}, {}, "root")
    assert res["warnings"] == [] and "SH-00" in res["errors"][0]


def test_lint_story_non_object_shot_row_is_reported_not_raised(tmp_path):
    story = build_story(tmp_path)
    story["episodes"][0]["shots"].append("junk")
    res = sl.lint_story(story)
    assert any("SH-00" in e for e in res["errors"])
