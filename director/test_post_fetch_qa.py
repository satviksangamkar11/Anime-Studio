"""M-28 tests: post-fetch QA runner (post_fetch_qa) and per-shot render history in run_colab_batch.
Offline: fake qa_shot, fake key loader, fake batch. No colab, no ffmpeg."""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "t0_pack"))
sys.path.insert(0, str(HERE.parent))

import clip_qa  # noqa: E402
import post_fetch_qa as pq  # noqa: E402
import run_colab_batch as r  # noqa: E402
from h3 import fallback_policy as fp  # noqa: E402
from h3.render_controller import render_allowed  # noqa: E402
from test_run_colab_batch_w11 import _batch, _margs, _cli  # noqa: E402


def _plan(tmp_path, ids=("SHOT-001",)):
    shots = {}
    for sid in ids:
        d = tmp_path / "res" / sid
        d.mkdir(parents=True, exist_ok=True)
        (d / "clip.mp4").write_bytes(b"x" * 60000)
        shots[sid] = {"clip": f"{sid}/clip.mp4", "key_a": "a.png", "key_b": "b.png", "review": "rev.json",
                      "sheet": "sheet.json", "audio": "a.wav"}
    plan = {"lock": "lock.json", "root": str(tmp_path / "qa"), "shots": shots}
    p = tmp_path / "qa_plan.json"
    p.write_text(json.dumps(plan), encoding="utf-8")
    return p


def _inputs(sid):
    return {"route": "SE", "chain_prev": "prev.png" if sid == "SHOT-002" else None}


def _fake_qa(passing=("SHOT-001", "SHOT-002"), calls=None):
    def qa(shot, clip, lock, key_a, key_b, review, sheet, audio, root, route="SE", chain_prev=None):
        if calls is not None:
            calls.append({"shot": shot, "clip": clip, "key_a": key_a, "key_b": key_b, "route": route,
                          "chain_prev": chain_prev})
        if shot == "BOOM":
            raise clip_qa.ClipQAError("shot not in timeline lock: BOOM")
        return {"verdict": {"pass": shot in passing, "reasons": [{"code": "FLICKER"}]}}
    return qa


def _run(tmp_path, ids=("SHOT-001", "SHOT-002"), qa=None, **kw):
    plan = pq.load_plan(_plan(tmp_path, ids))
    return pq.run(plan, tmp_path / "res", _inputs, qa=qa or _fake_qa(), load_sheet=lambda p: {},
                  load_key=lambda p: "key:" + str(p), **kw)


def test_run_calls_qa_per_shot_with_route_chain_and_keys(tmp_path):
    calls = []
    out = _run(tmp_path, qa=_fake_qa(calls=calls))
    assert [c["shot"] for c in calls] == ["SHOT-001", "SHOT-002"]
    assert calls[0]["route"] == "SE" and calls[0]["chain_prev"] is None
    assert calls[1]["chain_prev"] == "prev.png"
    assert calls[0]["key_a"] == "key:a.png" and calls[0]["key_b"] == "key:b.png"
    assert calls[0]["clip"] == str(tmp_path / "res" / "SHOT-001" / "clip.mp4")
    assert all(v["ok"] for v in out.values())


def test_route_s_uses_key_a_as_the_end_key(tmp_path):
    calls = []
    plan = pq.load_plan(_plan(tmp_path, ("SHOT-001",)))
    pq.run(plan, tmp_path / "res", lambda sid: {"route": "S", "chain_prev": None}, qa=_fake_qa(calls=calls),
           load_sheet=lambda p: {}, load_key=lambda p: "key:" + str(p))
    assert calls[0]["key_b"] == calls[0]["key_a"]


def test_failed_verdict_is_a_failure_with_codes(tmp_path):
    out = _run(tmp_path, qa=_fake_qa(passing=("SHOT-001",)))
    assert out["SHOT-001"]["ok"] is True
    assert out["SHOT-002"]["ok"] is False and "FLICKER" in out["SHOT-002"]["reason"]


def test_qa_error_fails_that_shot_and_the_rest_still_run(tmp_path):
    out = _run(tmp_path, ids=("BOOM", "SHOT-001"), qa=_fake_qa())
    assert out["BOOM"]["ok"] is False and "not in timeline lock" in out["BOOM"]["reason"]
    assert out["SHOT-001"]["ok"] is True


def test_missing_clip_fails_without_calling_qa(tmp_path):
    calls = []
    plan = pq.load_plan(_plan(tmp_path, ("SHOT-001",)))
    (tmp_path / "res" / "SHOT-001" / "clip.mp4").unlink()
    out = pq.run(plan, tmp_path / "res", _inputs, qa=_fake_qa(calls=calls), load_sheet=lambda p: {},
                 load_key=lambda p: p)
    assert out["SHOT-001"]["ok"] is False and "clip missing" in out["SHOT-001"]["reason"] and calls == []


def test_inputs_error_fails_the_shot(tmp_path):
    def bad(sid):
        raise ValueError(f"{sid}: no route in the routes file")
    plan = pq.load_plan(_plan(tmp_path, ("SHOT-001",)))
    out = pq.run(plan, tmp_path / "res", bad, qa=_fake_qa(), load_sheet=lambda p: {}, load_key=lambda p: p)
    assert out["SHOT-001"]["ok"] is False and "no route" in out["SHOT-001"]["reason"]


def test_shot_without_plan_entry_fails(tmp_path):
    plan = pq.load_plan(_plan(tmp_path, ("SHOT-001",)))
    out = pq.run(plan, tmp_path / "res", _inputs, qa=_fake_qa(), load_sheet=lambda p: {}, load_key=lambda p: p,
                 shot_ids=["SHOT-001", "SHOT-009"])
    assert out["SHOT-009"]["ok"] is False and "no entry" in out["SHOT-009"]["reason"]


def test_load_plan_refuses_missing_fields(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"lock": "l.json", "shots": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        pq.load_plan(p)
    p.write_text(json.dumps({"lock": "l.json", "root": "r", "shots": {"S": {"clip": "c"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="key_a"):
        pq.load_plan(p)


def test_exit_code_nonzero_on_any_failure(tmp_path):
    assert pq.exit_code({"A": {"ok": True}, "B": {"ok": True}}) == 0
    assert pq.exit_code({"A": {"ok": True}, "B": {"ok": False}}) == 1
    assert pq.exit_code({}) == 1       # nothing checked is not a pass


# ---- render history in run_colab_batch ----------------------------------------------------------

SH = {"id": "SHOT-001", "render_version": "rv1", "settings_sha256": "s1", "seed": 7}


def test_record_render_appends_numbered_record(tmp_path):
    h = tmp_path / "fallback_history.json"
    rec = r.record_render(h, SH, drift_step=None)
    assert rec["n"] == 1 and rec["render_version"] == "rv1" and rec["settings_sha256"] == "s1" and rec["seed"] == 7
    rec2 = r.record_render(h, SH, drift_step="seed")
    assert rec2["n"] == 2 and rec2["drift_step"] == "seed"
    assert len(fp.attempts_for(fp.load_history(str(h)), "SHOT-001")) == 2


def test_three_recorded_renders_stop_the_fourth(tmp_path):
    h = tmp_path / "fallback_history.json"
    for _ in range(3):
        r.record_render(h, SH, drift_step=None)
    ok, reason = render_allowed(fp.load_history(str(h)), "SHOT-001", False)
    assert ok is False and "3 renders" in reason


def test_record_fetched_records_only_shots_with_a_clip(tmp_path):
    res = tmp_path / "res"
    (res / "SHOT-001").mkdir(parents=True)
    (res / "SHOT-001" / "SHOT-001.mp4").write_bytes(b"x" * 60000)
    (res / "SHOT-002").mkdir()
    (res / "SHOT-002" / "SHOT-002.mp4").write_bytes(b"x" * 10)      # too small: not a finished clip
    shots = [SH, {"id": "SHOT-002", "render_version": "rv2", "settings_sha256": "s2"}, {"id": "SHOT-003"}]
    h = tmp_path / "fallback_history.json"
    done = r.record_fetched(h, res, shots, {"SHOT-001": ["seed"]})
    assert done == ["SHOT-001"]
    doc = fp.load_history(str(h))
    assert list(doc["shots"]) == ["SHOT-001"]
    assert doc["shots"]["SHOT-001"][0]["drift_step"] == "seed"


# ---- main: --go records renders then runs the QA plan -------------------------------------------

def _go(tmp_path, monkeypatch, extra=(), batch_rc_error=False):
    _batch(tmp_path)
    monkeypatch.setattr(r, "HERE", tmp_path)
    monkeypatch.setattr(r, "free_checks", lambda *a, **k: [])
    monkeypatch.setattr(r, "run_cli", _cli([]))

    def fake_batch(name, gpu, run_py, results, expected=None, **k):
        d = Path(results) / "SHOT-001"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SHOT-001.mp4").write_bytes(b"x" * 60000)
        if batch_rc_error:
            raise r.RunError("run.py exited 1")
    monkeypatch.setattr(r, "batch", fake_batch)
    return r.main(["synth", "--results", str(tmp_path / "res"), "--go", *_margs(tmp_path), *extra])


def test_go_records_render_in_default_history(tmp_path, monkeypatch):
    assert _go(tmp_path, monkeypatch, ["--no-qa"]) == 0
    doc = fp.load_history(str(tmp_path / "res" / "fallback_history.json"))
    assert len(doc["shots"]["SHOT-001"]) == 1 and doc["shots"]["SHOT-001"][0]["settings_sha256"]


def test_go_records_render_even_when_the_batch_stops(tmp_path, monkeypatch):
    assert _go(tmp_path, monkeypatch, ["--no-qa"], batch_rc_error=True) == 1
    assert len(fp.load_history(str(tmp_path / "res" / "fallback_history.json"))["shots"]["SHOT-001"]) == 1


def test_go_runs_post_fetch_qa_and_exits_nonzero_on_fail(tmp_path, monkeypatch):
    seen = []
    def fake(plan, results, routes, pack, shot_ids):
        seen.append(shot_ids)
        return {"SHOT-001": {"ok": False, "reason": "FLICKER"}}
    monkeypatch.setattr(r.post_fetch_qa, "run_from_files", fake)
    code = _go(tmp_path, monkeypatch, ["--qa-plan", "plan.json", "--routes", "routes.json", "--pack", "pk"])
    assert code == 1 and seen == [["SHOT-001"]]


def test_go_qa_pass_exits_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(r.post_fetch_qa, "run_from_files", lambda *a, **k: {"SHOT-001": {"ok": True}})
    assert _go(tmp_path, monkeypatch, ["--qa-plan", "plan.json", "--routes", "routes.json", "--pack", "pk"]) == 0


def test_qa_plan_without_routes_is_refused_before_any_render(tmp_path, monkeypatch):
    assert _go(tmp_path, monkeypatch, ["--qa-plan", "plan.json"]) == 1
    assert not (tmp_path / "res" / "SHOT-001").exists()


# M-31: one malformed plan entry or an unexpected QA exception fails that shot; it must not crash the whole run
def test_malformed_plan_entry_fails_that_shot_only(tmp_path):
    plan = pq.load_plan(_plan(tmp_path))
    del plan["shots"]["SHOT-001"]["key_a"]
    out = pq.run(plan, tmp_path / "res", _inputs, qa=_fake_qa(), load_sheet=lambda p: {},
                 load_key=lambda p: "key:" + str(p))
    assert out["SHOT-001"]["ok"] is False and "SHOT-001" in out["SHOT-001"]["reason"]


def test_unexpected_qa_exception_fails_that_shot_only(tmp_path):
    def qa(shot, *a, **k):
        raise AttributeError("doc is not a mapping")
    out = _run(tmp_path, ids=("SHOT-001", "SHOT-002"), qa=qa)
    assert [out[s]["ok"] for s in ("SHOT-001", "SHOT-002")] == [False, False]
