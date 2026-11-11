"""Tests for director/writer_guard.py (card X-06). Every test injects fake call functions and fake streams.

ASSUMED SIGNATURES (module not written yet):
  cli_ready(which=shutil.which, run=subprocess.run) -> None; raises WriterUnavailable
  scan_stream(stdout: str) -> {"limit_error", "is_error", "cost_usd", "num_turns", "usage"}
  guarded_call(stage, prompt, call_fn, ledger, est_cents, usage_path) -> stdout
      call_fn(prompt, max_budget_usd=float) -> stdout text (the stream)
      usage_path is a Path; one JSON line is appended per call
  WRITER_CAP_CENTS env var is read inside guarded_call; unset or "0" -> SystemExit before any call
  validate_pack(rows, blocking_dir) -> list[str]; blocking_dir/<row id>.json is the blocking sheet
  Row: {"id", "time_range", "audio_and_dialogue_track", "per_second_directives": [{"t0","t1","text","source_refs"}]}
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import voice_cast  # noqa: E402
import writer_guard  # noqa: E402


@pytest.fixture(autouse=True)
def cap_env(monkeypatch):
    monkeypatch.setenv("WRITER_CAP_CENTS", "200")


def _ledger(tmp_path, cap=200):
    return voice_cast.Ledger(tmp_path / "spend.jsonl", cap)


def _result_line(cost=0.5, turns=3, is_error=False):
    return json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": is_error,
        "total_cost_usd": cost,
        "num_turns": turns,
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "result": "ok",
    })


def _retry_line(error):
    return json.dumps({"type": "system", "subtype": "api_retry", "error": error})


class _FakeCall:
    def __init__(self, stream):
        self.stream = stream
        self.count = 0

    def __call__(self, prompt, max_budget_usd=None):
        self.count += 1
        return self.stream


def _pose(x, y, scale, facing="right", pose="standing", mouth=False):
    return {"x": x, "y": y, "scale": scale, "facing": facing, "pose": pose, "mouth_moves": mouth}


def _sheet(shot_id):
    member = {
        "id": "SHIVA",
        "name": "SHIVA",
        "speaks": False,
        "arms": 2,
        "source_refs": ["ch2:p10"],
        "start": _pose(0.5, 0.8, 0.5, pose="seated"),
        "end": _pose(0.5, 0.8, 0.5, pose="standing"),
    }
    return {
        "schema": "blocking/1",
        "shot_id": shot_id,
        "plate_id": "PLATE-throne",
        "location_id": "LOC-palace-hall",
        "kind": "acting",
        "camera": {"mode": "fixed", "framing": "medium", "move": None},
        "light": {"key_dir": "left", "palette_id": "PAL-warm"},
        "props": [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["A", "B"]}],
        "entries": [],
        "exits": [],
        "sound_cues": [{"t": 1.0, "text": "soft wind"}],
        "arc_sec": 2.0,
        "writer_seconds": 5.0,
        "cut_to_next": "cut",
        "source_refs": ["ch2:p10"],
        "cast": [member],
    }


def _write_blocking(directory, shot_id):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (shot_id + ".json")).write_text(json.dumps(_sheet(shot_id)), encoding="utf-8")


def _directive(t0, t1, refs=("ch2:p10",)):
    d = {"t0": t0, "t1": t1, "text": "a man sits"}
    if refs is not None:
        d["source_refs"] = list(refs)
    return d


def _row(rid, directives):
    return {
        "id": rid,
        "time_range": "00:00-00:04",
        "audio_and_dialogue_track": "soft wind",
        "per_second_directives": directives,
    }


def test_over_cap_refuses_before_call(tmp_path):
    ledger = _ledger(tmp_path, cap=200)
    ledger.reserve("seed", 100)
    ledger.settle("seed", 100, confirmed=True)
    call = _FakeCall(_result_line())
    with pytest.raises(SystemExit):
        writer_guard.guarded_call("stage1", "prompt", call, ledger, 150, tmp_path / "usage.jsonl")
    assert call.count == 0


def test_settle_rounds_cost_up(tmp_path):
    ledger = _ledger(tmp_path)
    call = _FakeCall(_result_line(cost=0.734))
    writer_guard.guarded_call("stage1", "prompt", call, ledger, 50, tmp_path / "usage.jsonl")
    settled = [r for r in ledger.rows().values() if r["state"] == "SETTLED"]
    assert len(settled) == 1
    assert settled[0]["credits"] == 74  # ceil(73.4)


def test_rate_limit_event_raises_writer_limit(tmp_path):
    stream = "\n".join([_retry_line("rate_limit"), _result_line(is_error=False)])
    call = _FakeCall(stream)
    with pytest.raises(writer_guard.WriterLimit):
        writer_guard.guarded_call("stage1", "prompt", call, _ledger(tmp_path), 50, tmp_path / "usage.jsonl")
    assert call.count == 1


def test_is_error_result_raises(tmp_path):
    call = _FakeCall(_result_line(is_error=True))
    with pytest.raises(RuntimeError):
        writer_guard.guarded_call("stage1", "prompt", call, _ledger(tmp_path), 50, tmp_path / "usage.jsonl")


@pytest.mark.parametrize("value", [None, "0"])
def test_unset_cap_refuses(tmp_path, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("WRITER_CAP_CENTS", raising=False)
    else:
        monkeypatch.setenv("WRITER_CAP_CENTS", value)
    call = _FakeCall(_result_line())
    with pytest.raises(SystemExit):
        writer_guard.guarded_call("stage1", "prompt", call, _ledger(tmp_path), 50, tmp_path / "usage.jsonl")
    assert call.count == 0


def test_cli_ready_missing_binary():
    with pytest.raises(writer_guard.WriterUnavailable):
        writer_guard.cli_ready(which=lambda name: None)


def test_scan_stream_reads_result():
    stream = "\n".join([_result_line(cost=0.5, turns=3)])
    got = writer_guard.scan_stream(stream)
    assert got["cost_usd"] == 0.5
    assert got["num_turns"] == 3
    assert got["is_error"] is False
    assert got["limit_error"] is None
    assert got["usage"] == {"input_tokens": 10, "output_tokens": 5}


def test_scan_stream_ignores_bad_lines():
    stream = "\n".join(["not json at all", "{broken", '{"type": "result", ', _result_line(cost=0.5, turns=3),
                        "}{ garbage"])
    got = writer_guard.scan_stream(stream)
    assert got["cost_usd"] == 0.5
    assert got["num_turns"] == 3
    assert got["limit_error"] is None


def test_usage_row_appended(tmp_path):
    usage = tmp_path / "usage.jsonl"
    writer_guard.guarded_call("stage1", "prompt", _FakeCall(_result_line(cost=0.5, turns=3)),
                              _ledger(tmp_path), 50, usage)
    lines = usage.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["stage"] == "stage1"
    assert row["num_turns"] == 3
    assert row["cost_usd"] == 0.5
    assert row["is_error"] is False
    assert row["limit_error"] is None
    for key in ("t", "usage"):
        assert key in row


@pytest.mark.parametrize("error", ["rate_limit", "authentication_failed", "billing_error",
                                   "account_on_hold", "oauth_org_not_allowed"])
def test_limit_error_values(tmp_path, error):
    call = _FakeCall(_retry_line(error))
    with pytest.raises(writer_guard.WriterLimit):
        writer_guard.guarded_call("stage1", "prompt", call, _ledger(tmp_path), 50, tmp_path / "usage.jsonl")


def test_unknown_api_retry_error_not_a_limit(tmp_path):
    stream = "\n".join([_retry_line("overloaded"), _result_line(is_error=False)])
    assert writer_guard.scan_stream(stream)["limit_error"] is None
    writer_guard.guarded_call("stage1", "prompt", _FakeCall(stream), _ledger(tmp_path), 50,
                              tmp_path / "usage.jsonl")


def test_validate_pack_gap_in_events(tmp_path):
    _write_blocking(tmp_path, "SHOT-001")
    rows = [_row("SHOT-001", [_directive(0.0, 2.0), _directive(2.5, 3.0)])]
    problems = writer_guard.validate_pack(rows, str(tmp_path))
    assert problems  # the gap 2.0 -> 2.5 is the only problem: the blocking file is valid


def test_validate_pack_missing_blocking(tmp_path):
    rows = [_row("SHOT-002", [_directive(0.0, 2.0)])]
    problems = writer_guard.validate_pack(rows, str(tmp_path))
    assert any("SHOT-002" in p for p in problems)


def test_validate_pack_good_pack_has_no_problems(tmp_path):
    _write_blocking(tmp_path, "SHOT-001")
    _write_blocking(tmp_path, "SHOT-002")
    rows = [
        _row("SHOT-001", [_directive(0.0, 2.0), _directive(2.0, 4.0)]),
        _row("SHOT-002", [_directive(0.0, 1.5), _directive(1.5, 3.0)]),
    ]
    assert writer_guard.validate_pack(rows, str(tmp_path)) == []


def test_validate_pack_directive_without_source_refs(tmp_path):
    _write_blocking(tmp_path, "SHOT-001")
    rows = [_row("SHOT-001", [_directive(0.0, 2.0, refs=None), _directive(2.0, 4.0)])]
    assert writer_guard.validate_pack(rows, str(tmp_path))


def test_validate_pack_directives_must_start_at_zero(tmp_path):
    _write_blocking(tmp_path, "SHOT-001")
    rows = [_row("SHOT-001", [_directive(0.5, 2.0), _directive(2.0, 4.0)])]
    assert writer_guard.validate_pack(rows, str(tmp_path))
