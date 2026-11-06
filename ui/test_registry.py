"""Run registry in the UI (offline; fake tools from test_ui.py): GET /api/registry routes and guards, the write_pack
writer shortcut and finished-pack refusal, hooks that never break a request, the stop wiring, the gate hook, and the panel's rules."""
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "director"))
import pipeline  # noqa: E402
import run_registry  # noqa: E402
import server  # noqa: E402
import write_pack  # noqa: E402
from server import ApiError  # noqa: E402
from test_ui import call, world, api, http_srv, wait_for  # noqa: E402,F401  (fixtures and helpers of the fake-tool world)

SUPER = "nvidia/nemotron-3.5-super-vl:free"
WRITER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"


def story_dir(cfg, slug="kaliya_mardan"):
    return cfg.studio / "stories" / slug


def record_pack_run(cfg, pack="pack_x", model=SUPER, via="openrouter"):
    rec = run_registry.Recorder(story_dir(cfg), "writer-super-vl", pack=pack, via=via, model=model)
    with rec.step("analysis_done", None, via=via, model=model) as run:
        run.note = "2 episodes, 4 shots"
    return rec


# ---------------------------------------------------------------- writer shortcut and mirror
def test_the_ui_writer_table_mirrors_write_pack():
    assert server.DEFAULT_WRITER == write_pack.DEFAULT_WRITER == "super-vl"
    assert set(server.WRITER_ROUTE) == {"super-vl", "ultra"}
    for name, (via, model) in server.WRITER_ROUTE.items():
        assert write_pack.WRITERS[name]["via"] == via
        assert write_pack.WRITERS[name]["model"] == model


def test_write_pack_defaults_to_super_vl_and_names_the_route(api):
    out = api.preview({"command": "write_pack", "args": {"slug": "kaliya_mardan", "pack": "pack_new"}})
    argv = out["argv"]
    assert argv[argv.index("--writer") + 1] == "super-vl"
    assert "--via" not in argv and "--model" not in argv and "--staged" in argv
    assert out["route"] == "writer super-vl: openrouter " + SUPER + " (free model, streamed)"


def test_write_pack_ultra_shortcut(api):
    out = api.preview({"command": "write_pack", "args": {"slug": "kaliya_mardan", "pack": "pack_new", "writer": "ultra"}})
    assert out["argv"][out["argv"].index("--writer") + 1] == "ultra"
    assert "openrouter nvidia/nemotron-3-ultra-550b-a55b:free" in out["route"]


def test_write_pack_legacy_model_path_keeps_its_old_argv(api):
    out = api.preview({"command": "write_pack", "args": {"slug": "kaliya_mardan", "pack": "pack_new", "model": WRITER_MODEL}})
    argv = out["argv"]
    assert argv[argv.index("--via") + 1] == "nvidia" and argv[argv.index("--model") + 1] == WRITER_MODEL
    assert "--writer" not in argv and out["route"].startswith("legacy")


def test_write_pack_refuses_a_writer_with_a_model_and_unknown_writers(api):
    for args in ({"slug": "kaliya_mardan", "pack": "p", "writer": "super-vl", "model": WRITER_MODEL},
                 {"slug": "kaliya_mardan", "pack": "p", "writer": "opus"},
                 {"slug": "kaliya_mardan", "pack": "p", "writer": "claude"}):
        with pytest.raises(ApiError) as e:
            api.preview({"command": "write_pack", "args": args})
        assert e.value.code == 400


def test_write_pack_refuses_a_finished_pack_and_suggests_a_new_name(world, api):
    cfg = world[0]
    done = story_dir(cfg) / "pack_done"
    done.mkdir()
    (done / "PACK.md").write_text("finished\n", encoding="utf-8")
    with pytest.raises(ApiError) as e:
        api.preview({"command": "write_pack", "args": {"slug": "kaliya_mardan", "pack": "pack_done"}})
    assert e.value.code == 400 and "already finished" in e.value.msg
    assert f"pack_super-vl_{dt.date.today():%Y%m%d}_v1" in e.value.msg
    assert (done / "PACK.md").read_text(encoding="utf-8") == "finished\n"


# ---------------------------------------------------------------- routes
def test_registry_list_and_one_story(world, http_srv):
    cfg = world[0]
    record_pack_run(cfg)
    srv, port = http_srv
    status, raw, _ = call(port, "GET", "/api/registry")
    assert status == 200
    stories = {s["slug"]: s for s in json.loads(raw)["stories"]}
    assert stories["kaliya_mardan"]["run_count"] == 1
    assert stories["kaliya_mardan"]["pack_models"] == {"pack_x": SUPER}
    status, raw, _ = call(port, "GET", "/api/registry/kaliya_mardan")
    assert status == 200
    data = json.loads(raw)
    assert set(data) == {"slug", "story", "summary", "runs", "steps", "report"}
    assert data["runs"][0]["models"] == [SUPER] and data["runs"][0]["status"] == "ok"
    assert data["steps"] and data["steps"][0]["kind"] == "analysis_done"
    assert isinstance(data["report"], str) and data["report"].strip()


def test_registry_get_refuses_a_bad_slug_and_a_missing_story(http_srv):
    srv, port = http_srv
    for path in ("/api/registry/Bad%20Slug", "/api/registry/..%2Fetc", "/api/registry/%3Bls"):
        status, _, _ = call(port, "GET", path)
        assert status == 400, path
    status, _, _ = call(port, "GET", "/api/registry/no_such_story")
    assert status == 404


def test_registry_is_read_only_and_keeps_the_guards(http_srv):
    srv, port = http_srv
    status, _, _ = call(port, "POST", "/api/registry", {})
    assert status == 404
    status, _, _ = call(port, "POST", "/api/registry/kaliya_mardan", {})
    assert status == 404
    status, _, _ = call(port, "GET", "/api/registry", host="evil.example")
    assert status == 403
    status, _, _ = call(port, "GET", "/api/registry", origin="http://evil.example")
    assert status == 403


def test_registry_list_without_the_module_is_503(world, api, monkeypatch):
    monkeypatch.setattr(server, "_registry", lambda: None)
    with pytest.raises(ApiError) as e:
        api.registry_list()
    assert e.value.code == 503
    listed = api.stories()["slugs"]   # the story list still works without the run log
    assert any(s["slug"] == "kaliya_mardan" and s["latest_pack"] is None for s in listed)


def test_stories_carry_the_latest_model(world, api):
    record_pack_run(world[0])
    entry = next(s for s in api.stories()["slugs"] if s["slug"] == "kaliya_mardan")
    assert entry["latest_pack"] == "pack_x" and entry["latest_model"] == SUPER


def test_registry_output_is_redacted(world, api):
    rec = run_registry.Recorder(story_dir(world[0]), "writer-super-vl", pack="pack_x", via="openrouter", model=SUPER)
    with pytest.raises(ValueError):
        with rec.step("analysis_stage", "2", via="openrouter", model=SUPER):
            raise ValueError("refused Bearer SECRET999xyz")
    text = json.dumps(api.registry_get("kaliya_mardan"))
    assert "SECRET999xyz" not in text and "[REDACTED]" in text


# ---------------------------------------------------------------- hooks never break a request
def test_story_save_writes_the_run_log_and_survives_a_failing_hook(world, api, monkeypatch):
    cfg = world[0]
    out = api.story_save("kaliya_mardan", {"text": "# SOURCE: Kaliya\n\nHari om.\n", "overwrite": True})
    assert out["saved"] == "stories/kaliya_mardan/SOURCE.md"
    assert (story_dir(cfg) / "story.json").is_file()
    assert any(json.loads(x)["kind"] == "story_saved" for x in (story_dir(cfg) / "RUNS.jsonl").read_text(encoding="utf-8").splitlines())

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(run_registry, "record_story_saved", boom)
    out = api.story_save("kaliya_mardan", {"text": "# SOURCE: Kaliya again\n", "overwrite": True})
    assert out["saved"]
    assert "registry_hook_failed" in (cfg.runs / "audit.jsonl").read_text(encoding="utf-8")


def test_a_stopped_write_pack_closes_its_open_steps(world, api, monkeypatch):
    cfg = world[0]
    run_registry.append_event(story_dir(cfg), "run-open", "analysis_done", None, "started", pack="slow_pack", via="openrouter")
    p = api.preview({"command": "write_pack", "args": {"slug": "kaliya_mardan", "pack": "slow_pack"}})
    jid = api.run({"token": p["token"]})["job_id"]
    api.job_stop(jid)

    def closed_rows():
        return [r for r in run_registry.steps(run_registry.read_events(story_dir(cfg))) if r["run_id"] == "run-open"]
    wait_for(lambda: any(r["status"] == "stopped" for r in closed_rows()))   # the closing line is written after the process ends
    assert run_registry.run_status(closed_rows()) == "stopped"
    assert api.jobs[jid].state == "stopped"


def test_gate_decision_is_recorded_and_a_failing_hook_does_not_stop_the_gate(world, monkeypatch):
    cfg = world[0]
    rec = pipeline.record_gate(cfg.runs, "A", "approve", "owner", "ok", studio=cfg.studio, story_slug="kaliya_mardan")
    assert rec["gate"] == "A"
    events = run_registry.read_events(story_dir(cfg))
    assert any(e["kind"] == "gate_decision" and e.get("gate") == "A" for e in events)

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(run_registry, "record_gate_decision", boom)
    rec = pipeline.record_gate(cfg.runs, "A", "reject", "owner", "again", studio=cfg.studio, story_slug="kaliya_mardan")
    assert rec["decision"] == "reject"


# ---------------------------------------------------------------- the panel and the docs
def test_the_panel_is_text_only_and_the_routes_are_in_the_plan():
    js = (HERE / "static" / "pipeline.js").read_text(encoding="utf-8")
    assert "/api/registry" in js and "registryPanel" in js
    assert "innerHTML" not in js
    assert not re.search(r"https?://", js)
    plan = (HERE / "PLAN.md").read_text(encoding="utf-8")
    assert "| GET | `/api/registry` |" in plan and "| GET | `/api/registry/{slug}` |" in plan
    app = (HERE / "static" / "app.js").read_text(encoding="utf-8")
    assert "WRITER_NAMES = ['super-vl', 'ultra']" in app
    assert "WRITER_MODELS" not in app
