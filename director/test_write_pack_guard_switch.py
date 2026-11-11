import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import write_pack  # noqa: E402

STREAM = "\n".join([
    json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "```json shots\n[]\n```"}]}}),
    json.dumps({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.30,
                "num_turns": 2, "usage": {}, "result": "ok"}),
])


def _counting_run(calls):
    def fake_run(*args, **kwargs):
        calls.append(list(args[0]))
        return SimpleNamespace(returncode=0, stdout=STREAM, stderr="")
    return fake_run


def test_guard_off_by_default():
    assert write_pack.GUARD is False


def test_guard_on_without_cap_refuses(monkeypatch):
    calls = []
    monkeypatch.setattr(write_pack, "GUARD", True)
    monkeypatch.delenv("WRITER_CAP_CENTS", raising=False)
    monkeypatch.setattr(write_pack.subprocess, "run", _counting_run(calls))
    monkeypatch.setattr(write_pack.shutil, "which", lambda name, *a, **k: "/usr/bin/claude")
    with pytest.raises(SystemExit):
        write_pack.call_claude("prompt", "opus", "medium")
    assert len(calls) == 0


def test_guard_on_with_cap_logs_usage(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(write_pack, "GUARD", True)
    monkeypatch.setenv("WRITER_CAP_CENTS", "500")
    monkeypatch.setattr(write_pack, "LEDGERS", tmp_path)
    monkeypatch.setattr(write_pack.subprocess, "run", _counting_run(calls))
    monkeypatch.setattr(write_pack.shutil, "which", lambda name, *a, **k: "/usr/bin/claude")
    out = write_pack.call_claude("prompt", "opus", "medium")
    assert out == write_pack.join_stream(STREAM)
    assert len(calls) == 1
    assert (tmp_path / "writer_spend.jsonl").exists()
    usage_rows = (tmp_path / "writer_usage.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(usage_rows) == 1


# test_main_sets_guard_for_claude_route: not written. main() runs the whole pipeline and calls the claude CLI,
# so it cannot be exercised here without a real run; the GUARD assignment in main() is checked by reading only.
