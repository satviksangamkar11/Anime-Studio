"""The writer shortcuts (--writer super-vl / ultra / opus), the free-only rule, the OpenRouter call and its SSE reading.
Every network call is mocked; no model is called."""
import io
import json
import urllib.error
import urllib.request

import pytest

import run_registry
import write_pack

SUPER = "nvidia/nemotron-3.5-super-vl:free"
ULTRA = "nvidia/nemotron-3-ultra-550b-a55b:free"


class FakeHTTP:
    """What urlopen returns: readable in full (json.load) and line by line (SSE)."""

    def __init__(self, body: bytes):
        self.body = body

    def read(self, *a):
        return self.body

    def __iter__(self):
        return iter(self.body.splitlines(keepends=True))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def sse(*events) -> bytes:
    return b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events) + b"data: [DONE]\n\n"


@pytest.fixture
def key_file(tmp_path, monkeypatch):
    path = tmp_path / "openrouter_key.txt"
    path.write_text("sk-or-test-not-a-real-key\n", encoding="utf-8")
    monkeypatch.setattr(write_pack, "OPENROUTER_KEY", path)
    return path


@pytest.fixture
def chat(monkeypatch):
    """urlopen: the catalog URL gets `catalog`, the chat URL gets the SSE body. Records every chat request."""
    calls = {"chat": [], "catalog": 0, "sse": None, "catalog_body": {"data": []}}

    def fake_urlopen(req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        if url.endswith("/models"):
            calls["catalog"] += 1
            return FakeHTTP(json.dumps(calls["catalog_body"]).encode())
        calls["chat"].append({"req": req, "body": json.loads(req.data.decode("utf-8")),
                              "headers": {k.lower(): v for k, v in req.header_items()}})
        if isinstance(calls["sse"], Exception):
            raise calls["sse"]
        return FakeHTTP(calls["sse"] or sse({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}))
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def free_catalog(*models):
    return {"data": [{"id": m, "pricing": {"prompt": "0", "completion": "0"}} for m in models]}


# ---------------------------------------------------------------- routes
def test_no_option_at_all_is_the_super_vl_writer():
    assert write_pack.resolve_route(None, None, None, None) == ("super-vl", "openrouter", SUPER, "medium")
    assert write_pack.DEFAULT_WRITER == "super-vl"


def test_ultra_is_the_free_nemotron_ultra_on_openrouter():
    assert write_pack.resolve_route("ultra", None, None, None) == ("ultra", "openrouter", ULTRA, "medium")


def test_opus_is_the_claude_path_at_medium_and_effort_can_be_raised():
    assert write_pack.resolve_route("opus", None, None, None) == ("opus", "claude", "opus", "medium")
    assert write_pack.resolve_route("opus", None, None, "high") == ("opus", "claude", "opus", "high")


def test_a_writer_excludes_via_and_model():
    with pytest.raises(ValueError, match="do not pass"):
        write_pack.resolve_route("super-vl", "openrouter", None, None)
    with pytest.raises(ValueError, match="do not pass"):
        write_pack.resolve_route("ultra", None, "x/y:free", None)


def test_unknown_writer_is_refused():
    with pytest.raises(ValueError, match="unknown writer"):
        write_pack.resolve_route("gpt-x", None, None, None)


def test_openrouter_without_a_model_is_refused_and_a_model_without_via_too():
    with pytest.raises(ValueError, match="--model is required"):
        write_pack.resolve_route(None, "openrouter", None, None)
    with pytest.raises(ValueError, match="needs --via"):
        write_pack.resolve_route(None, None, "x/y:free", None)


def test_writer_and_via_together_is_a_usage_error(tmp_path):
    story = tmp_path / "story.md"
    story.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit):
        write_pack.main([str(story), str(tmp_path / "pack"), "--writer", "ultra", "--via", "claude"])


def test_default_single_run_goes_to_super_vl_on_openrouter(tmp_path, monkeypatch):
    seen = {}

    def fake_run_single(story_text, out, via, model, effort, allow_paid, rec=None):
        seen.update(via=via, model=model, effort=effort)
        return []
    monkeypatch.setattr(write_pack, "run_single", fake_run_single)
    story = tmp_path / "story.md"
    story.write_text("x", encoding="utf-8")
    write_pack.main([str(story), str(tmp_path / "pack")])
    assert seen == {"via": "openrouter", "model": SUPER, "effort": "medium"}


def test_default_staged_run_goes_to_super_vl_on_openrouter(tmp_path, monkeypatch):
    seen = {}

    def fake_run_staged(story_text, out, via, model, effort, allow_paid, stage_via, stage_model, rec=None, out_langs=None,
                        voice=None):
        seen.update(via=via, model=model, stage_via=stage_via, out_langs=out_langs)
        return []
    monkeypatch.setattr(write_pack, "run_staged", fake_run_staged)
    story = tmp_path / "story.md"
    story.write_text("x", encoding="utf-8")
    write_pack.main([str(story), str(tmp_path / "pack"), "--staged"])
    assert seen == {"via": "openrouter", "model": SUPER, "stage_via": {}, "out_langs": ["hi"]}


# ---------------------------------------------------------------- free-only rule
def test_a_paid_model_is_refused_before_the_chat_call(chat, key_file):
    chat["catalog_body"] = {"data": [{"id": "x/paid", "pricing": {"prompt": "0.000001", "completion": "0.000002"}}]}
    with pytest.raises(ValueError, match="paid"):
        write_pack.call_openrouter("prompt", "x/paid")
    assert chat["chat"] == []


def test_free_check_reads_every_price_field(chat):
    catalog = [{"id": "a/free", "pricing": {"prompt": "0", "completion": "0", "image": "0"}},
               {"id": "a/half", "pricing": {"prompt": "0", "completion": "0.5"}},
               {"id": "a/none", "pricing": {}}]
    assert write_pack.openrouter_is_free("a/free", catalog) is True
    assert write_pack.openrouter_is_free("a/half", catalog) is False
    assert write_pack.openrouter_is_free("a/none", catalog) is True
    with pytest.raises(ValueError, match="not in OpenRouter"):
        write_pack.openrouter_is_free("a/missing", catalog)


def test_allow_paid_is_the_only_way_past_the_free_check(chat, key_file):
    chat["catalog_body"] = {"data": [{"id": "x/paid", "pricing": {"prompt": "1", "completion": "1"}}]}
    env = json.loads(write_pack.call_openrouter("prompt", "x/paid", allow_paid=True))
    assert env["model"] == "x/paid" and len(chat["chat"]) == 1


# ---------------------------------------------------------------- the OpenRouter call
def test_request_body_is_streamed_with_the_full_output_budget(chat, key_file):
    chat["catalog_body"] = free_catalog(SUPER)
    write_pack.call_openrouter("the whole brief", SUPER)
    body = chat["chat"][0]["body"]
    assert body["model"] == SUPER
    assert body["stream"] is True
    assert body["max_tokens"] == 65536
    assert body["messages"] == [{"role": "user", "content": "the whole brief"}]
    assert chat["chat"][0]["headers"]["x-title"] == "anime-studio-writer"


def test_reasoning_deltas_are_not_part_of_the_answer(chat, key_file):
    chat["catalog_body"] = free_catalog(SUPER)
    chat["sse"] = sse({"choices": [{"delta": {"reasoning": "private thinking"}}]},
                      {"choices": [{"delta": {"content": "Hello "}}]},
                      {"choices": [{"delta": {"content": "world"}, "finish_reason": "stop"}]})
    env = json.loads(write_pack.call_openrouter("p", SUPER))
    assert env["result"] == "Hello world"
    assert env["is_error"] is False and env["finish_reason"] == "stop"
    assert env["via"] == "openrouter" and env["model"] == SUPER


def test_a_cut_off_answer_is_an_error_in_the_envelope(chat, key_file):
    chat["catalog_body"] = free_catalog(SUPER)
    chat["sse"] = sse({"choices": [{"delta": {"content": "half a sentence"}, "finish_reason": "length"}]})
    env = json.loads(write_pack.call_openrouter("p", SUPER))
    assert env["is_error"] is True and env["finish_reason"] == "length"


def test_an_http_refusal_is_raised_with_the_reason_and_no_key_in_it(chat, key_file):
    chat["catalog_body"] = free_catalog(SUPER)
    chat["sse"] = urllib.error.HTTPError("https://openrouter.ai/x", 400, "Bad Request", {},
                                         io.BytesIO(b'{"error": "max_tokens not allowed Bearer SECRET123abc"}'))
    with pytest.raises(RuntimeError) as info:
        write_pack.call_openrouter("p", SUPER)
    message = str(info.value)
    assert "HTTP 400" in message and "SECRET123abc" not in message and "[REDACTED]" in message


def test_a_provider_error_in_the_stream_keeps_its_reason(chat, key_file):
    chat["catalog_body"] = free_catalog(SUPER)
    chat["sse"] = sse({"choices": [{"delta": {"content": "partial"}}]},
                      {"error": {"code": 502, "message": "upstream went away Bearer SECRET777abc"}})
    with pytest.raises(RuntimeError, match="stream error from the provider") as info:
        write_pack.call_openrouter("p", SUPER)
    assert "upstream went away" in str(info.value) and "SECRET777abc" not in str(info.value)


def test_the_envelope_is_read_by_the_registry_helpers(chat, key_file):
    chat["catalog_body"] = free_catalog(SUPER)
    info = run_registry.envelope_info(write_pack.call_openrouter("p", SUPER))
    assert info["via"] == "openrouter" and info["model"] == SUPER and info["failed"] is False


# ---------------------------------------------------------------- finished packs and hooks
def test_a_finished_pack_is_never_written_again(tmp_path, monkeypatch):
    out = tmp_path / "pack_done"
    out.mkdir()
    (out / "PACK.md").write_text("finished\n", encoding="utf-8")
    monkeypatch.setattr(write_pack, "call_path", lambda *a, **k: pytest.fail("no call into a finished pack"))
    with pytest.raises(ValueError, match="already finished"):
        write_pack.run_single("story", out, "openrouter", SUPER, "medium", False)
    assert (out / "PACK.md").read_text(encoding="utf-8") == "finished\n"


def test_a_failing_registry_hook_does_not_stop_the_pack(tmp_path, monkeypatch, capsys):
    story = tmp_path / "stories" / "kaliya_hook" / "SOURCE.md"
    story.parent.mkdir(parents=True)
    story.write_text("Kaliya story.\n", encoding="utf-8")
    out = story.parent / "pack_hook_v1"

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(run_registry, "append_event", boom)
    monkeypatch.setattr(write_pack, "call_path", lambda prompt, via, model, effort, allow_paid:
                        write_pack.envelope("# Pack\n", "stop", via, model))
    monkeypatch.setattr(write_pack, "parse", lambda raw: ("# Pack\n", [{"id": "SHOT-001", "episode": 1, "seconds": 4}]))
    write_pack.main([str(story), str(out)])
    assert (out / "PACK.md").read_text(encoding="utf-8") == "# Pack\n"
    assert "skipped" in capsys.readouterr().err
