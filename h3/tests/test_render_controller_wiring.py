"""Dry-run pipeline plan in render_controller.plan_pipeline. Never renders; writes nothing."""
import json
import os

import pytest

import h3.render_controller as rc
from h3.fallback_policy import record_attempt
from h3.pipeline_contract import STEP_ORDER
from h3.tests.synth import build_story


def _groups(story):
    return rc.select_scope(story, "all")


def _status(steps):
    return {s["id"]: s["status"] for s in steps}


def test_plan_has_every_step_in_order_and_no_render(tmp_path):
    story = build_story(str(tmp_path / "pics_root"))
    out = str(tmp_path / "build")
    plan = rc.plan_pipeline(story, _groups(story), out, languages=["en"])
    assert [s["id"] for s in plan["steps"]] == [sid for sid, _ in STEP_ORDER]
    st = _status(plan["steps"])
    assert st["render"] == "pending" and st["step9_qc"] == "pending"
    assert plan["assembly_allowed"] is False
    assert st["assembly"] != "ready"
    assert not os.path.exists(out), "dry run must not create the output folder"


def test_plan_routes_are_recorded_per_shot(tmp_path):
    story = build_story(str(tmp_path / "pics_root"))
    plan = rc.plan_pipeline(story, _groups(story), str(tmp_path / "build"), languages=["en"])
    route = next(s for s in plan["steps"] if s["id"] == "route")
    assert set(route["details"]["routes"]) == {"SYN_A", "SYN_B", "SYN_C"}


def test_fourth_failure_blocks_fallback(tmp_path):
    story = build_story(str(tmp_path / "pics_root"))
    out = tmp_path / "build"
    out.mkdir()
    hist = str(out / rc.HISTORY_FILE)
    failure = {"kind": "drift", "shot_row": story["episodes"][0]["shots"][0]}
    for _ in range(3):
        record_attempt(hist, "SYN_A", failure, {"rung": 1, "action": "x", "model": None})
    plan = rc.plan_pipeline(story, _groups(story), str(out), languages=["en"])
    fb = next(s for s in plan["steps"] if s["id"] == "fallback")
    assert fb["status"] == "blocked"
    assert any(r.startswith("SYN_A: human gate") for r in fb["reasons"])


def test_render_ok_moves_render_ready_but_qc_without_measurers_blocks(tmp_path):
    story = build_story(str(tmp_path / "pics_root"))
    results = {"SYN_A": "ok", "SYN_B": "ok", "SYN_C": "ok"}
    plan = rc.plan_pipeline(story, _groups(story), str(tmp_path / "build"), languages=["en"], render_results=results)
    st = _status(plan["steps"])
    assert st["render"] == "ready"
    assert st["step9_qc"] == "blocked"  # fails closed: no measurers supplied
    assert plan["assembly_allowed"] is False


def test_unknown_language_is_refused_by_gate_d(tmp_path):
    story = build_story(str(tmp_path / "pics_root"))
    plan = rc.plan_pipeline(story, _groups(story), str(tmp_path / "build"), languages=["fr"])
    gd = next(s for s in plan["steps"] if s["id"] == "gate_d")
    assert gd["status"] == "blocked"
