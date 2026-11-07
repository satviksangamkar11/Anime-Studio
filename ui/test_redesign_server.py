"""Server half of the UI redesign (docs/UI_REDESIGN_PLAN_2026-11-07.md section 2.3 and 3.1, tasks T1 items B1 and B9).
Offline, fake studio from test_ui.py. No process is started: every /api/run uses a fake _start. No key text is read or printed."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402
from server import ApiError  # noqa: E402
from test_ui import call, world, api, http_srv, wait_for, write  # noqa: E402,F401  (fixtures and helpers of the fake-tool world)

PACK = "stories/kaliya_mardan/pack_x"
SUPER_VL_NV = "nvidia/nemotron-3.5-super-vl-120b-a12b"
SAFE_ARGS = {"slug": "kaliya_mardan", "pack": "pack_new", "out_lang": "hi"}
OPTION_IDS = ["nv-ultra", "nv-super-vl", "or-super-vl", "or-ultra", "claude-opus"]
OPTION_KEYS = {"id", "group", "command", "args", "cost", "speed", "quality", "tested", "available", "reason"}


def option(writers, oid):
    return next(o for o in writers["options"] if o["id"] == oid)


def or_file(tmp_path, monkeypatch, text="sk-or-TESTSECRET456"):
    p = tmp_path / "or_key.txt"
    p.write_text(text, encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_KEY_FILE", str(p))
    return p


def fake_start(monkeypatch, api):
    monkeypatch.setattr(api, "_start", lambda *a, **k: SimpleNamespace(id="job1"))


# ---------------------------------------------------------------- GET /api/writers (model chooser, section 2.2)
def test_writers_shape_order_and_default(api, monkeypatch, tmp_path):
    or_file(tmp_path, monkeypatch)
    w = api.writers()
    assert set(w) == {"default", "claude_allowed", "confirm_word", "checks", "options"}
    assert w["default"] == "or-super-vl" and w["claude_allowed"] is False and w["confirm_word"] == "CLAUDE"
    assert [o["id"] for o in w["options"]] == OPTION_IDS
    assert set(w["checks"]) == {"nvidia_key_files", "openrouter_key_file", "claude_cli"}
    assert w["checks"]["nvidia_key_files"] == 2 and w["checks"]["openrouter_key_file"] is True
    assert all(set(o) == OPTION_KEYS for o in w["options"])
    assert option(w, "or-super-vl")["available"] is True and option(w, "or-super-vl")["reason"] == ""


def test_writers_reasons_when_keys_are_missing(api, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_KEY_FILE", str(tmp_path / "none.txt"))
    for p in (api.cfg.studio.parent / "secrets" / "nvidia").glob("nvidia_api_key*.txt"):
        p.unlink()
    w = api.writers()
    assert option(w, "nv-ultra")["available"] is False and option(w, "nv-ultra")["reason"] == "no_nvidia_key"
    assert option(w, "nv-super-vl")["reason"] == "no_nvidia_key"
    for oid in ("or-super-vl", "or-ultra"):
        assert option(w, oid)["available"] is False and option(w, oid)["reason"] == "no_openrouter_key"
    assert option(w, "claude-opus")["available"] is False and option(w, "claude-opus")["reason"] == "claude_off"
    assert w["checks"]["nvidia_key_files"] == 0 and w["checks"]["openrouter_key_file"] is False


def test_claude_reason_when_allowed_but_cli_missing(api, monkeypatch):
    api.cfg.allow_claude = True
    monkeypatch.setattr(server.shutil, "which", lambda name: None)
    c = option(api.writers(), "claude-opus")
    assert c["available"] is False and c["reason"] == "claude_missing"
    monkeypatch.setattr(server.shutil, "which", lambda name: "C:/bin/claude.exe")
    c = option(api.writers(), "claude-opus")
    assert c["available"] is True and c["reason"] == "" and api.writers()["claude_allowed"] is True


def test_writers_never_sends_key_text_or_paths(api, monkeypatch, tmp_path):
    (api.cfg.studio.parent / "secrets" / "nvidia" / "nvidia_api_key_3.txt").write_text("nvapi-TESTSECRET123", encoding="utf-8")
    or_file(tmp_path, monkeypatch, "sk-or-TESTSECRET456")
    text = json.dumps(api.writers())
    assert "TESTSECRET" not in text and "nvapi-" not in text and "sk-or-" not in text and "secrets" not in text


def test_writers_route_is_served(api):
    assert server.dispatch(api, "GET", "/api/writers", {}, {})["default"] == "or-super-vl"


def test_status_says_whether_claude_is_allowed(api):
    assert api.status()["claude_allowed"] is False
    api.cfg.allow_claude = True
    assert api.status()["claude_allowed"] is True


def test_config_claude_is_off_by_default():
    assert server.Config().allow_claude is False


# ---------------------------------------------------------------- write_pack: NVIDIA Super VL model and the Claude command
def test_write_pack_nvidia_super_vl_model_builds_the_nvidia_path(api):
    argv = api.preview({"command": "write_pack", "args": {**SAFE_ARGS, "model": SUPER_VL_NV}})["argv"]
    assert argv[argv.index("--via") + 1] == "nvidia" and argv[argv.index("--model") + 1] == SUPER_VL_NV
    assert "--writer" not in argv


def test_write_pack_still_refuses_opus_and_claude(api):
    for args in ({**SAFE_ARGS, "writer": "opus"}, {**SAFE_ARGS, "model": "claude-opus"}):
        with pytest.raises(ApiError) as e:
            api.preview({"command": "write_pack", "args": args})
        assert e.value.code == 400


def test_write_pack_claude_is_off_without_the_flag(api):
    with pytest.raises(ApiError) as e:
        api.preview({"command": "write_pack_claude", "args": SAFE_ARGS})
    assert e.value.code == 403 and e.value.msg.startswith("claude is off")


def test_write_pack_claude_preview_needs_the_typed_word(api):
    api.cfg.allow_claude = True
    out = api.preview({"command": "write_pack_claude", "args": SAFE_ARGS})
    argv = out["argv"]
    assert argv[argv.index("--writer") + 1] == "opus" and "--via" not in argv
    assert out["needs_confirm"] is True and out["confirm_text"] == "CLAUDE"
    assert "claude" in out["route"].lower()


def test_write_pack_claude_needs_an_output_language(api):
    api.cfg.allow_claude = True
    with pytest.raises(ApiError) as e:
        api.preview({"command": "write_pack_claude", "args": {"slug": "kaliya_mardan", "pack": "pack_new"}})
    assert e.value.code == 400


def test_write_pack_claude_run_needs_the_exact_word_and_the_flag(api, monkeypatch):
    api.cfg.allow_claude = True
    fake_start(monkeypatch, api)
    token = api.preview({"command": "write_pack_claude", "args": SAFE_ARGS})["token"]
    for body in ({"token": token}, {"token": token, "confirm": "claude "}):
        with pytest.raises(ApiError) as e:
            api.run(body)
        assert e.value.code == 400 and e.value.msg == "type exactly: CLAUDE"
    assert api.run({"token": token, "confirm": "CLAUDE"}) == {"job_id": "job1"}
    token2 = api.preview({"command": "write_pack_claude", "args": SAFE_ARGS})["token"]
    api.cfg.allow_claude = False
    with pytest.raises(ApiError) as e:
        api.run({"token": token2, "confirm": "CLAUDE"})
    assert e.value.code == 403 and "claude is off" in e.value.msg


def test_check_argv_allows_only_the_named_pair():
    with pytest.raises(ApiError):
        server.check_argv(["x", "--writer", "opus"])
    server.check_argv(["x", "--writer", "opus"], frozenset({("--writer", "opus")}))
    with pytest.raises(ApiError):
        server.check_argv(["x", "--via", "claude"], frozenset({("--writer", "opus")}))
    with pytest.raises(ApiError):
        server.check_argv(["x", "--via", "openrouter"])


def test_free_commands_do_not_ask_for_a_typed_word(api):
    out = api.preview({"command": "check_pack", "args": {"pack": PACK}})
    assert out["needs_confirm"] is False and out["confirm_text"] is None


# ---------------------------------------------------------------- B1 server half: approve refused while out of date
def test_gate_is_refused_while_the_server_is_out_of_date(api, monkeypatch):
    monkeypatch.setattr(server, "SERVER_MTIME0", 0.0)
    with pytest.raises(ApiError) as e:
        server.pipeline_gate(api, {"story": "kaliya_mardan", "pack": "pack_x", "gate": "A", "decision": "approve", "note": ""})
    assert e.value.code == 409 and "out of date" in e.value.msg


def test_gate_is_not_blocked_by_the_stale_guard_when_current(api):
    assert api.version()["stale"] is False
    try:
        server.pipeline_gate(api, {"story": "kaliya_mardan", "pack": "pack_x", "gate": "A", "decision": "approve", "note": ""})
    except ApiError as e:
        assert "out of date" not in e.msg


# ---------------------------------------------------------------- B9 server half: Colab sessions only on request
def test_ops_asks_colab_for_sessions_only_when_told(api, monkeypatch):
    calls = []

    def fake_cli(args, timeout=60):
        calls.append(list(args))
        return ""
    monkeypatch.setattr(api, "_cli_text", fake_cli)
    quiet = server.dispatch(api, "GET", "/api/ops", {}, {})
    assert calls == [] and quiet["colab"]["sessions_checked"] is False and quiet["colab"]["sessions_listed"] is None
    asked = server.dispatch(api, "GET", "/api/ops", {"colab": "1"}, {})
    assert calls == [["sessions"]] and asked["colab"]["sessions_checked"] is True and asked["colab"]["sessions_listed"] == []


# ---------------------------------------------------------------- i18n and font routes (section 3.1)
def test_i18n_and_font_routes(api):
    static = api.cfg.studio / "ui" / "static" / "i18n"
    write(static / "en.json", {"app.title": "Anime Studio"})
    write(static / "mr.json", {"app.title": "ॲनिमे स्टुडिओ"})
    raw = server.dispatch(api, "GET", "/i18n/en.json", {}, {})
    assert isinstance(raw, server.Raw) and raw.ctype == server.JSON_CT
    assert json.loads(raw.data.decode("utf-8")) == {"app.title": "Anime Studio"}
    assert json.loads(server.dispatch(api, "GET", "/i18n/mr.json", {}, {}).data.decode("utf-8"))["app.title"] == "ॲनिमे स्टुडिओ"
    with pytest.raises(ApiError) as e:
        server.dispatch(api, "GET", "/i18n/xx.json", {}, {})
    assert e.value.code == 404
    with pytest.raises(ApiError) as e:
        server.dispatch(api, "GET", "/fonts/NotoSansDevanagari-Variable.ttf", {}, {})
    assert e.value.code == 404
    font = api.cfg.studio / "styles" / "fonts" / "NotoSansDevanagari-Variable.ttf"
    font.parent.mkdir(parents=True, exist_ok=True)
    font.write_bytes(b"\x00\x01\x00\x00fake")
    got = server.dispatch(api, "GET", "/fonts/NotoSansDevanagari-Variable.ttf", {}, {})
    assert isinstance(got, server.Raw) and got.ctype == "font/ttf" and got.data.startswith(b"\x00\x01\x00\x00")


# ---------------------------------------------------------------- PLAN.md section 4 (the static test parses this table)
def test_plan_section4_lists_the_new_routes_and_the_claude_confirm():
    plan = (HERE / "PLAN.md").read_text(encoding="utf-8")
    assert "| GET | `/api/writers` |" in plan
    assert "| GET | `/i18n/{lang}.json` |" in plan
    assert "| GET | `/fonts/NotoSansDevanagari-Variable.ttf` |" in plan
    run_row = next(line for line in plan.splitlines() if line.startswith("| POST | `/api/run` |"))
    assert "write_pack_claude" in run_row and "CLAUDE" in run_row
