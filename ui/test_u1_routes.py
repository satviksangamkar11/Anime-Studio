"""U1 backend tests: scoped gates, validator, languages, voices, bgm, render, author dry run, version, ops, file rules.
Offline: temp studio, no model call, no Colab, no ElevenLabs. The Colab CLI is replaced by a text stub in the spend test."""
import json
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline  # noqa: E402
import server  # noqa: E402
from server import ApiError, Config, Job  # noqa: E402

SLUG = "kaliya_mardan"
PACK = "pack_x"
PACK_PATH = f"stories/{SLUG}/{PACK}"
SHOTS = [{"id": "SHOT-01", "episode": 1, "mode": "fl2va", "seconds": 8.0},
         {"id": "SHOT-02", "episode": 1, "mode": "fl2va", "seconds": 8.5}]
V4_SHOTS = [{"id": "SHOT-V1", "episode": 1, "route": "FL2VA", "editorial_duration_sec": 9.0}]
BIBLE_DICT = {"characters": {"CHAR-KRISHNA": {"name": "Krishna"}}, "environments": {"ENV-DAH": {"name": "Dah"}},
              "props": {"PROP-FLUTE": {"name": "flute"}}}


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def _w(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) if not isinstance(data, str) else data, encoding="utf-8")


@pytest.fixture()
def world(tmp_path):
    studio = tmp_path / "anime_studio"
    studio.mkdir()
    story = studio / "stories" / SLUG
    _w(story / "SOURCE.md", "# SOURCE: test\n\n## TRANSCRIPT (verbatim)\n\nhello\n")
    _w(story / PACK / "shots.json", SHOTS)
    _w(story / PACK / "bible.json", BIBLE_DICT)
    (studio / "ui" / "runs").mkdir(parents=True)
    cfg = Config(studio=studio, flow=tmp_path / "flow", downloads=tmp_path / "dl", python=sys.executable,
                 colab=[str(tmp_path / "colab.exe")], clock=Clock(), disk_paths=(str(tmp_path), str(tmp_path)))
    api = server.Api(cfg)
    api.pipeline_project({"story_slug": SLUG, "pack": PACK})
    return cfg, api


def _dispatch(api, method, path, q=None, body=None):
    return server.dispatch(api, method, path, q or {}, body or {})


# ------------------------------------------------------------------ gates: scope, legacy, 409, validator, Gate D
def test_gate_scoped_by_story_and_pack_and_legacy_ignored(world):
    cfg, api = world
    # a legacy record (no story, no pack) must never count
    cfg.runs.mkdir(parents=True, exist_ok=True)
    (cfg.runs / "approvals.jsonl").write_text(json.dumps({"gate": "A", "decision": "approve", "by": "owner"}) + "\n", encoding="utf-8")
    st = pipeline.pipeline_state(cfg.studio, cfg.runs, None, SLUG, PACK)
    assert next(g for g in st["gates"] if g["id"] == "A")["state"] != "approved"
    # another pack of the same story is a separate scope
    pipeline.record_gate(cfg.runs, "A", "approve", "owner", "ok", story_slug=SLUG, pack="pack_other")
    st = pipeline.pipeline_state(cfg.studio, cfg.runs, None, SLUG, PACK)
    assert next(g for g in st["gates"] if g["id"] == "A")["state"] != "approved"


def test_gate_409_when_story_or_pack_differs_from_project(world):
    cfg, api = world
    with pytest.raises(ApiError) as e:
        server.pipeline_gate(api, {"story": "other_story", "pack": PACK, "gate": "A", "decision": "approve", "note": ""})
    assert e.value.code == 409
    with pytest.raises(ApiError) as e:
        server.pipeline_gate(api, {"story": SLUG, "pack": PACK})
    assert e.value.code == 400


def test_gate_A_refused_with_validator_errors(world, monkeypatch):
    cfg, api = world
    monkeypatch.setattr(pipeline, "validator_problems", lambda *a: ["S55-3 SHOT-01"])
    with pytest.raises(ApiError) as e:
        server.pipeline_gate(api, {"story": SLUG, "pack": PACK, "gate": "A", "decision": "approve", "note": ""})
    assert e.value.code == 403 and "validator" in e.value.msg


def test_gate_D_needs_step9_and_language_plan(world):
    cfg, api = world
    probs = pipeline.gate_d_problems(cfg.studio, SLUG, PACK)
    assert probs and "Step 9 QC is not run" in probs[0]


def test_legacy_pack_validator_report_shape_and_get_none_before_run(world):
    cfg, api = world
    # no report yet: 200 {"status": "none"} (coder E, 2026-11-07; the page no longer sees a 404 here)
    assert api.pack_validate_get(PACK_PATH) == {"status": "none"}
    rep = api.pack_validate_run(PACK_PATH, {})
    assert {"ok", "errors", "warnings", "mode", "exit", "time"} <= set(rep)
    assert rep["mode"] == "legacy" and rep["exit"] in (0, 1)
    assert api.pack_validate_get(PACK_PATH)["time"] == rep["time"]


# ------------------------------------------------------------------ summary, pack read, reel mapping, prepare guard
def test_summary_dict_bible_no_500_and_v4_fields(world):
    cfg, api = world
    _w(cfg.studio / "stories" / SLUG / PACK / "shots.json", V4_SHOTS)
    api.pipeline_project({"story_slug": SLUG, "pack": PACK})
    s = pipeline.summary(cfg.studio, cfg.runs)
    assert s["characters"] == ["Krishna"] and s["places"] == ["Dah"] and s["props"] == ["flute"]
    assert s["modes"] == {"FL2VA": 1} and s["seconds"] == 9.0
    p = api.pack(PACK_PATH)
    assert p["shots"][0]["mode"] == "FL2VA" and p["shots"][0]["seconds"] == 9.0
    assert p["character_names"] == ["Krishna"]


def test_reel_scope_maps_to_episode_id_and_prepare_refuses_shots_json(world):
    cfg, api = world
    _w(cfg.studio / "stories/kaliya_mardan/h3_story.json", {"episodes": [], "registry": {}})
    _w(cfg.studio / "h3/render_controller.py", "# built\n")
    got = api.preview({"command": "h3_prepare", "args": {"story": "stories/kaliya_mardan/h3_story.json", "scope": "reel", "reel": 2}})
    assert "EP_02" in got["argv"]
    # audit 11-08: the wizard sends the pack's shots.json; the server converts it to <pack>/h3_story.json first
    got = api.preview({"command": "h3_prepare", "args": {"story": PACK_PATH + "/shots.json", "scope": "all"}})
    assert any(str(x).endswith("h3_story.json") for x in got["argv"])
    (cfg.studio / PACK_PATH / "bible.json").unlink(missing_ok=True)
    with pytest.raises(ApiError) as e:
        api.preview({"command": "h3_prepare", "args": {"story": PACK_PATH + "/shots.json", "scope": "all"}})
    assert e.value.code == 400


def test_render_status_shape_and_choice_guard(world):
    cfg, api = world
    st = api.render_status(SLUG, PACK)
    assert st["prepare_ready"] is False and "gate_d" in st and "step9" in st
    assert st["step9"]["status"] == "not run" and st["bgm"]["label"] == "no BGM (2-stem mix)"
    with pytest.raises(ApiError) as e:
        api.render_choice({"story": SLUG, "pack": PACK, "shot": "SHOT-01", "choice": "make_it_up"})
    assert e.value.code == 400
    ok = api.render_choice({"story": SLUG, "pack": PACK, "shot": "SHOT-01", "choice": "switch_models", "note": "try again"})
    assert ok["ok"] is True
    assert (cfg.studio / PACK_PATH / "render" / "human_choices.jsonl").is_file()


# ------------------------------------------------------------------ spend: lock, cumulative cap, persisted jobs
def test_spend_lock_after_stop_failed(world):
    cfg, api = world
    job = Job("20990101-000000-aaaaaa", "colab_run", [], True, "t0-kaliya", "colab_verify", cfg.runs / "jobs" / "x.log")
    job.state, job.verified = "stop_failed", False
    api.jobs[job.id] = job
    assert api._active() is True
    job.verified = True
    job.state = "done"
    assert api._active() is False


def test_spend_ledger_cap_is_cumulative(world, monkeypatch):
    cfg, api = world
    cfg.total_cap = 20.0
    pipeline_ops = server._ops_checks()
    pipeline_ops.record_spend(cfg.ledger, units=15, session="s", story="kaliya_mardan", reason="test")
    monkeypatch.setattr(api, "_cli_text", lambda args, timeout=60: "Balance: 500 units\n")
    with pytest.raises(ApiError) as e:
        api._spend_gate(10.0)
    assert e.value.code == 403 and "total cap" in e.value.msg
    assert api._spend_gate(4.0) == 500.0


def test_persisted_jobs_survive_restart(world):
    cfg, api = world
    d = cfg.runs / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    (d / "j1.json").write_text(json.dumps({"id": "j1", "command": "write_pack", "state": "done", "rc": 0, "spend": False,
                                           "argv": [], "log": "j1.log"}), encoding="utf-8")
    (d / "j2.json").write_text(json.dumps({"id": "j2", "command": "colab_run", "state": "running", "spend": True,
                                           "session": "s2", "argv": [], "log": "j2.log"}), encoding="utf-8")
    fresh = server.Api(cfg)
    assert fresh.jobs["j1"].state == "done"
    assert fresh.jobs["j2"].state == "lost" and fresh._active() is True


# ------------------------------------------------------------------ languages, voices, bgm, author, versions
def test_languages_order_all_and_refusals(world):
    cfg, api = world
    assert api.set_languages(SLUG, {"languages": ["hi", "en"]})["output_languages"] == ["hi", "en"]
    assert api.set_languages(SLUG, {"languages": "all"})["output_languages"] == ["en", "hi", "mr"]
    for bad_value in (["mr", "mr"], [], "fr"):
        with pytest.raises(ApiError) as e:
            api.set_languages(SLUG, {"languages": bad_value})
        assert e.value.code == 400


def test_voice_engine_hi_h3_refused_and_en_h3_warned(world):
    cfg, api = world
    with pytest.raises(ApiError) as e:
        api.set_voices(SLUG, {"voice_engine": {"en": "elevenlabs", "hi": "h3"}})
    assert e.value.code == 400
    out = api.set_voices(SLUG, {"voice_engine": {"en": "h3"}})
    assert out["voice_engine"]["en"] == "h3" and out["warnings"]


def test_bgm_on_needs_a_valid_manifest(world):
    cfg, api = world
    assert api.set_bgm(SLUG, {"enabled": False})["label"] == "no BGM (2-stem mix)"
    with pytest.raises(ApiError) as e:
        api.set_bgm(SLUG, {"enabled": True})
    assert e.value.code == 400
    with pytest.raises(ApiError) as e:
        api.set_bgm(SLUG, {"enabled": True, "manifest": "stories/kaliya_mardan/missing.json"})
    assert e.value.code in (400, 403)


def test_pack_voices_round_trip_and_bad_key(world):
    cfg, api = world
    got = api.pack_voices_set(PACK_PATH, {"voices": {"CHAR-KRISHNA": {"en": "pending", "hi": "pending", "mr": "pending"}}})
    assert got["voices"]["CHAR-KRISHNA"]["hi"] == "pending" and got["characters"][0]["id"] == "CHAR-KRISHNA"
    with pytest.raises(ApiError) as e:
        api.pack_voices_set(PACK_PATH, {"voices": {"CHAR-NOBODY": {"en": "a", "hi": "b", "mr": "c"}}})
    assert e.value.code == 400


def test_author_status_is_dry_run_and_never_runnable(world):
    cfg, api = world
    out = api.author_status(PACK_PATH)
    assert out["dry_run"] is True and out["run_allowed"] is False
    assert isinstance(out["shots"], list)


def test_out_lang_argv_and_validation(world):
    cfg, api = world
    base = {"slug": SLUG, "pack": "pack_new"}
    got = api.preview({"command": "write_pack", "args": {**base, "out_lang": "hi,en"}})
    assert got["argv"][-2:] == ["--out-lang", "hi,en"]
    got = api.preview({"command": "write_pack", "args": {**base, "out_lang": "all"}})
    assert got["argv"][-1] == "en,hi,mr"
    for bad_value in ("mr,mr", "", "fr"):
        with pytest.raises(ApiError) as e:
            api.preview({"command": "write_pack", "args": {**base, "out_lang": bad_value}})
        assert e.value.code == 400
    with pytest.raises(ApiError) as e:
        api.preview({"command": "write_pack", "args": base})
    assert e.value.code == 400


def test_yt_result_map():
    assert server.YT_URL.fullmatch("https://evil.example/x") is None
    ok = server.yt_result(0, "written /x/SOURCE.md (1234 chars of transcript)")
    assert ok["status"] == "ok" and ok["chars"] == 1234 and ok["file"] == "/x/SOURCE.md"
    need = server.yt_result(3, "NEEDS_CHOICE: the language is unclear; the candidates are ['hi', 'mr']. Run again")
    assert need["status"] == "needs_choice" and need["candidates"] == ["hi", "mr"]
    refused = server.yt_result(2, "REFUSED: /x/SOURCE.md exists (use --overwrite)")
    assert refused["status"] == "refused" and refused["overwrite_offer"] is True


def test_link_preview_refuses_bad_url(world):
    cfg, api = world
    with pytest.raises(ApiError) as e:
        api.link(SLUG, {"url": "https://evil.example/watch?v=1"})
    assert e.value.code == 400
    got = api.link(SLUG, {"url": "https://www.youtube.com/watch?v=abc", "lang": "auto"})
    assert "yt_transcript.py" in " ".join(got["argv"]) and got["spend_allowed"] is not None


# ------------------------------------------------------------------ scoped images, export, packet, files, status
def test_images_no_kaliya_fallback_for_other_story(world):
    cfg, api = world
    _w(cfg.studio / "flow/generated/kaliya_mardan/kaliya_mardan_flow_jobs_x.json", [{"shot_id": "A", "prompt": "p"}])
    other = api.images("1", "other_story")
    assert other["exists"] is False and other["jobs"] == []


def test_export_requires_story_and_pack(world):
    cfg, api = world
    with pytest.raises(ApiError) as e:
        api.export("1", "", "")
    assert e.value.code == 400


def test_version_stale_flag(world, monkeypatch):
    cfg, api = world
    assert api.version()["stale"] is False
    monkeypatch.setattr(server, "SERVER_MTIME0", 0.0)
    assert api.version()["stale"] is True
    assert "pid" in api.ops()["server"] and set(api.ops()["disk"]) == {"C", "D"}


def test_file_endpoint_redacts_text_and_blocks_runs(world):
    cfg, api = world
    _w(cfg.studio / "stories/kaliya_mardan/writer_run.log", "line " + "hf" + "_" + "ABCDEFGHIJKLMNOPQRSTUVWX end")  # fake token built at runtime (secret scan)
    raw = api.file_response("stories/kaliya_mardan/writer_run.log")
    assert b"hf" + b"_ABCDEF" not in raw.data and b"[REDACTED]" in raw.data
    _w(cfg.runs / "a.log", "x")
    with pytest.raises(ApiError) as e:
        api.file_response("ui/runs/a.log")
    assert e.value.code == 403


def test_story_save_keeps_a_backup_on_overwrite(world):
    cfg, api = world
    api.story_save(SLUG, {"text": "new text", "overwrite": True})
    backups = list((cfg.studio / "stories" / SLUG).glob("SOURCE.md.bak-*"))
    assert backups and "hello" in backups[0].read_text(encoding="utf-8")


def test_project_switch_warns_for_missing_pack(world):
    cfg, api = world
    out = api.pipeline_project({"story_slug": SLUG, "pack": "pack_missing"})
    assert out["scope"] == {"story": SLUG, "pack": "pack_missing"} and out["warning"]


def test_dispatch_routes_are_wired_and_unknown_is_404(world):
    cfg, api = world
    assert "build" in _dispatch(api, "GET", "/api/version")
    assert "disk" in _dispatch(api, "GET", "/api/ops")
    assert "scope" in _dispatch(api, "GET", "/api/pipeline", {"story": SLUG, "pack": PACK})
    with pytest.raises(ApiError) as e:
        _dispatch(api, "POST", "/api/nope")
    assert e.value.code == 404
    with pytest.raises(ApiError) as e:
        _dispatch(api, "POST", f"/api/story/{SLUG}/languages", {}, {"languages": []})
    assert e.value.code == 400
