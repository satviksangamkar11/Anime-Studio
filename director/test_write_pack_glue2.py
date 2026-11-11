"""Tests for the X-07 additions to director/write_pack_glue.py: stage_est_cents and guarded_claude_call.
Written BEFORE the code (rule 54(3)): hand-checked values. No real claude, no network: every call is a fake.

ASSUMED SHAPES (not written yet):
  stage_est_cents(name, env=None) -> int: 150 by default; WRITER_STAGE_EST_CENTS (positive integer string) overrides;
      garbage or non-positive values -> ValueError
  guarded_claude_call(stage, prompt, raw_call, ledger_path, usage_path, est_cents=None, env=None) -> str
      cap = int(WRITER_CAP_CENTS) read from env (default os.environ); unset -> SystemExit before any call
      Ledger(ledger_path, cap) from voice_cast; returns writer_guard.guarded_call(stage, prompt, call_fn, ledger,
      est_cents or stage_est_cents(stage), usage_path) where call_fn(prompt, max_budget_usd=...) calls
      raw_call(prompt, max_budget_usd). raw_call returns the stream text.
      Hand values: a 0.30 USD result settles to 30 cents (math.ceil(0.30 * 100) == 30 in Python).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import voice_cast  # noqa: E402
import write_pack_glue  # noqa: E402
import writer_guard  # noqa: E402


@pytest.fixture(autouse=True)
def env_clean(monkeypatch):
    monkeypatch.setenv("WRITER_CAP_CENTS", "200")
    monkeypatch.delenv("WRITER_STAGE_EST_CENTS", raising=False)


def _good_stream(cost=0.30):
    return "\n".join([
        json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "```json shots\n[]\n```"}]}}),
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": cost,
                    "num_turns": 2, "usage": {}, "result": "ok"}),
    ])


def _limit_stream():
    return "\n".join([
        json.dumps({"type": "system", "subtype": "api_retry", "error": "rate_limit"}),
        json.dumps({"type": "result", "subtype": "success", "is_error": True, "total_cost_usd": 0.10,
                    "num_turns": 1, "usage": {}, "result": ""}),
    ])


class _FakeRaw:
    """The raw claude call: returns a fixed stream and records every call."""

    def __init__(self, stream):
        self.stream = stream
        self.count = 0
        self.budgets = []

    def __call__(self, prompt, max_budget_usd=None):
        self.count += 1
        self.budgets.append(max_budget_usd)
        return self.stream


def _usage_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _settled(ledger_path):
    rows = voice_cast.Ledger(ledger_path, 200).rows()
    return {jid: r for jid, r in rows.items() if r.get("state") == "SETTLED"}


# stage_est_cents

def test_stage_est_default_is_150_cents():
    assert write_pack_glue.stage_est_cents("1", env={}) == 150


def test_stage_est_override_from_env():
    assert write_pack_glue.stage_est_cents("3e1", env={"WRITER_STAGE_EST_CENTS": "75"}) == 75


@pytest.mark.parametrize("bad", ["abc", "0", "-3"])
def test_stage_est_garbage_or_non_positive_raises(bad):
    with pytest.raises(ValueError):
        write_pack_glue.stage_est_cents("1", env={"WRITER_STAGE_EST_CENTS": bad})


# guarded_claude_call

def test_good_call_returns_stream_and_logs(tmp_path):
    raw = _FakeRaw(_good_stream(0.30))
    ledger_path = tmp_path / "spend.jsonl"
    usage_path = tmp_path / "usage.jsonl"
    text = write_pack_glue.guarded_claude_call("1", "prompt", raw, ledger_path, usage_path)
    assert text == _good_stream(0.30)
    assert raw.count == 1
    rows = _usage_rows(usage_path)
    assert len(rows) == 1
    assert rows[0]["stage"] == "1"
    assert rows[0]["cost_usd"] == 0.30
    settled = _settled(ledger_path)
    assert sum(r["credits"] for r in settled.values()) == 30


def test_cap_unset_refuses_before_call(tmp_path, monkeypatch):
    monkeypatch.delenv("WRITER_CAP_CENTS", raising=False)
    raw = _FakeRaw(_good_stream())
    with pytest.raises(SystemExit):
        write_pack_glue.guarded_claude_call("1", "prompt", raw, tmp_path / "spend.jsonl", tmp_path / "usage.jsonl")
    assert raw.count == 0


def test_limit_stream_raises_writer_limit(tmp_path):
    raw = _FakeRaw(_limit_stream())
    usage_path = tmp_path / "usage.jsonl"
    with pytest.raises(writer_guard.WriterLimit):
        write_pack_glue.guarded_claude_call("3e1", "prompt", raw, tmp_path / "spend.jsonl", usage_path)
    assert raw.count == 1
    rows = _usage_rows(usage_path)
    assert len(rows) == 1
    assert rows[0]["limit_error"] is not None


def test_budget_passed_to_raw_call(tmp_path):
    raw = _FakeRaw(_good_stream(0.10))
    write_pack_glue.guarded_claude_call("3e1", "prompt", raw, tmp_path / "spend.jsonl", tmp_path / "usage.jsonl", est_cents=75)
    assert raw.budgets == [0.75]


def test_stage_est_default_used(tmp_path, monkeypatch):
    monkeypatch.delenv("WRITER_STAGE_EST_CENTS", raising=False)
    raw = _FakeRaw(_good_stream(0.30))
    ledger_path = tmp_path / "spend.jsonl"
    write_pack_glue.guarded_claude_call("1", "prompt", raw, ledger_path, tmp_path / "usage.jsonl")
    # no est_cents given: the stage default (150 cents) is reserved and passed as the budget, then settled to the real 30 cents
    assert raw.budgets == [1.5]
    settled = _settled(ledger_path)
    assert sum(r["credits"] for r in settled.values()) == 30
