"""Card X-13: timeline gate, Gate B gate, Gate D on lock seconds, render_ready.json. No network, no model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import hashlib
import json

import pytest

import h3.render_controller as rc
from director.timeline_lock_io import write_lock
from h3.pipeline_contract import BLOCKED, PRE_RENDER, READY, build_plan
from h3.tests.synth import build_story

# edit frames per synthetic shot (24 fps): 168 -> 7.0 s, 120 -> 5.0 s, 170 -> 170/24 s; pixel_frames 175 covers all
FRAMES = {"SYN_A": 168, "SYN_B": 120, "SYN_C": 170}


def _story(tmp_path):
    return build_story(str(tmp_path / "pics_root"))


def _write_story(tmp_path, story):
    path = tmp_path / "story.json"
    path.write_text(json.dumps(story), encoding="utf-8")
    return path


def _script(tmp_path):
    path = tmp_path / "input_script.txt"
    path.write_text("line one\n", encoding="utf-8")
    return path


def _lock(tmp_path, script):
    shots, cursor = [], 0
    for sid, n in FRAMES.items():
        shots.append({"id": sid, "edit_frames": n, "start_frame": cursor, "pixel_frames": 175,
                      "trim_in_frame": 0, "trim_out_frame": n, "end_frame_position": n - 1, "error_ms": 0.0})
        cursor += n
    path = tmp_path / "timeline.lock.json"
    write_lock(path, shots, [str(script)], {"sing8": True})
    return path


def _step(steps, sid):
    return next(s for s in steps if s["id"] == sid)


def test_plan_pipeline_no_lock_blocks(tmp_path):
    story = _story(tmp_path)
    plan = rc.plan_pipeline(story, rc.select_scope(story, "all"), str(tmp_path / "build"), languages=["en"])
    timeline = _step(plan["steps"], "timeline")
    assert timeline["status"] == BLOCKED
    assert timeline["reasons"] == ["no timeline lock"]
    assert plan["assembly_allowed"] is False


def test_stale_script_byte_blocks(tmp_path):
    story = _story(tmp_path)
    groups = rc.select_scope(story, "all")
    script = _script(tmp_path)
    lock = _lock(tmp_path, script)
    before = rc.plan_pipeline(story, groups, str(tmp_path / "build"), lock_path=str(lock))
    assert _step(before["steps"], "timeline")["status"] == READY  # control: the untouched lock passes
    script.write_text("line one\n!", encoding="utf-8")  # one byte more
    after = rc.plan_pipeline(story, groups, str(tmp_path / "build"), lock_path=str(lock))
    timeline = _step(after["steps"], "timeline")
    assert timeline["status"] == BLOCKED
    assert "stale" in timeline["reasons"][0]


def test_missing_gate_b_blocks(tmp_path):
    story = _story(tmp_path)
    lock = _lock(tmp_path, _script(tmp_path))
    plan = rc.plan_pipeline(story, rc.select_scope(story, "all"), str(tmp_path / "build"), lock_path=str(lock))
    assert _step(plan["steps"], "timeline")["status"] == READY
    assert _step(plan["steps"], "keyframes")["status"] == BLOCKED
    assert plan["assembly_allowed"] is False


def test_gate_d_uses_lock_seconds(tmp_path, monkeypatch):
    story = _story(tmp_path)
    groups = rc.select_scope(story, "all")
    lock = _lock(tmp_path, _script(tmp_path))
    seen = {}

    def fake_plan(ep_id, languages, vo_dir, _unused, *, shots, **kwargs):
        seen["shots"] = shots
        return {"reports": {}}

    monkeypatch.setattr(rc, "plan_language_outputs", fake_plan)
    story_rows = [s for g in groups for s in g["episode"]["shots"]]
    story_a = next(s for s in story_rows if s["shot_id"] == "SYN_A")
    assert story_a["timing_and_lattice"]["editorial_duration_sec"] == pytest.approx(6.04)  # 145 frames; lock says 168
    rc._gate_d_result(story, groups, str(tmp_path / "build"), ["en"], str(lock))  # ok is False here (no gate checks)
    got = {s["shot_id"]: s["editorial_duration_sec"] for s in seen["shots"]}
    assert got["SYN_A"] == pytest.approx(7.0)
    assert got["SYN_B"] == pytest.approx(5.0)
    assert got["SYN_C"] == pytest.approx(170 / 24)


def test_gate_d_shot_row_without_shot_id_is_a_problem_not_a_crash(tmp_path, monkeypatch):
    story = _story(tmp_path)
    groups = rc.select_scope(story, "all")
    lock = _lock(tmp_path, _script(tmp_path))
    monkeypatch.setattr(rc, "plan_language_outputs", lambda *a, **k: {"reports": {}})
    del groups[0]["episode"]["shots"][0]["shot_id"]
    result = rc._gate_d_result(story, groups, str(tmp_path / "build"), ["en"], str(lock))
    assert result["ok"] is False
    assert any("not readable for the timeline lock" in r for r in result["reasons"])


def test_gate_b_reads_real_approval_sheet(tmp_path):
    story = _story(tmp_path)
    groups = rc.select_scope(story, "all")
    keyframes = tmp_path / "keyframe_gates"
    keyframes.mkdir()
    records = []
    for sid in FRAMES:
        gate_file = keyframes / f"{sid}.json"
        gate_file.write_text(json.dumps({"pass": True}), encoding="utf-8")
        digest = hashlib.sha256(gate_file.read_bytes()).hexdigest()
        records.append({"shot": sid, "by": "owner", "date": "2026-11-11", "keyframe_gate_sha256": digest})
    gate_b = tmp_path / "gate_b.json"
    gate_b.write_text(json.dumps(records), encoding="utf-8")
    assert rc._keyframe_result(str(gate_b), str(keyframes), groups)["ok"] is True
    gate_b.write_text(json.dumps(records[:2]), encoding="utf-8")  # SYN_C has no approval
    result = rc._keyframe_result(str(gate_b), str(keyframes), groups)
    assert result["ok"] is False and any("SYN_C" in r for r in result["reasons"])
    assert not any("not built" in r for r in result["reasons"])


def test_execute_without_lock_exit_2(tmp_path):
    story_file = _write_story(tmp_path, _story(tmp_path))
    out = tmp_path / "out"
    code = rc.main(["--story-file", str(story_file), "--scope", "all", "--mode", "execute",
                    "--execute-render", "--out-dir", str(out)])
    assert code == 2
    assert not out.exists()


def test_render_ready_written_only_when_clean(tmp_path, monkeypatch):
    story = _story(tmp_path)
    story_file = _write_story(tmp_path, story)
    script = _script(tmp_path)
    lock = _lock(tmp_path, script)
    gate_b = tmp_path / "gate_b.json"
    gate_b.write_text(json.dumps([]), encoding="utf-8")
    keyframes = tmp_path / "keyframe_gates"
    keyframes.mkdir()
    out = tmp_path / "out"
    ready_path = out / "render_ready.json"
    argv = ["--story-file", str(story_file), "--scope", "all", "--mode", "execute", "--execute-render",
            "--out-dir", str(out), "--lock", str(lock)]

    # Gate B missing: the real plan blocks keyframes, nothing is written
    assert rc.main(argv) == 1
    assert not ready_path.exists()

    # every pre-render gate ready: the synthetic story cannot pass manifest and Gate D on its own, so the plan is
    # stubbed here; the real gates are covered by the tests above
    all_ready = build_plan({sid: {"ok": True, "reasons": [], "details": {}} for sid in PRE_RENDER})
    monkeypatch.setattr(rc, "plan_pipeline", lambda *a, **k: {"steps": all_ready})
    code = rc.main(argv + ["--gate-b", str(gate_b), "--keyframe-gates", str(keyframes)])
    assert code == 3  # gates passed; no backend is configured, so nothing started
    record = json.loads(ready_path.read_text(encoding="utf-8"))
    assert record["ok"] is True
    assert record["lock_input_sha256"] == json.loads(lock.read_text(encoding="utf-8"))["input_sha256"]
    assert record["gate_b_sha256"] == hashlib.sha256(gate_b.read_bytes()).hexdigest()
    assert record["story_sha256"] == hashlib.sha256(story_file.read_bytes()).hexdigest()
