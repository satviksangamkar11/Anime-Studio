"""Round-2 tests for director/writer_guard.py. Written BEFORE the fixes (rule 54(3)): hand-checked values, frozen after.
Every test injects fake call functions and fake streams; no model is called.

ASSUMED SIGNATURES (same as test_writer_guard.py):
  cli_ready(which=shutil.which, run=subprocess.run) -> None; raises WriterUnavailable
  guarded_call(stage, prompt, call_fn, ledger, est_cents, usage_path) -> stdout
  WRITER_CAP_CENTS env var is THE cap; the ledger cap must equal it
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


class _RaisingCall:
    def __init__(self, exc):
        self.exc = exc
        self.count = 0

    def __call__(self, prompt, max_budget_usd=None):
        self.count += 1
        raise self.exc


def _open_reservations(ledger):
    return [jid for jid, r in ledger.rows().items() if r["state"] == "RESERVED"]


def _ledger_lines(tmp_path):
    return [json.loads(line) for line in (tmp_path / "spend.jsonl").read_text(encoding="utf-8").splitlines()]


def _usage_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _pack_row(rid, directives):
    return {
        "id": rid,
        "time_range": "00:00-00:04",
        "audio_and_dialogue_track": "soft wind",
        "per_second_directives": directives,
    }


def _directive(t0, t1, refs=("ch2:p10",)):
    d = {"t0": t0, "t1": t1, "text": "a man sits"}
    if refs is not None:
        d["source_refs"] = list(refs)
    return d


def _sheet(shot_id):
    member = {
        "id": "SHIVA", "name": "SHIVA", "speaks": False, "arms": 2, "source_refs": ["ch2:p10"],
        "start": {"x": 0.5, "y": 0.8, "scale": 0.5, "facing": "right", "pose": "seated", "mouth_moves": False},
        "end": {"x": 0.5, "y": 0.8, "scale": 0.5, "facing": "right", "pose": "standing", "mouth_moves": False},
    }
    return {
        "schema": "blocking/1", "shot_id": shot_id, "plate_id": "PLATE-throne",
        "location_id": "LOC-palace-hall", "kind": "acting",
        "camera": {"mode": "fixed", "framing": "medium", "move": None},
        "light": {"key_dir": "left", "palette_id": "PAL-warm"},
        "props": [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["A", "B"]}],
        "entries": [], "exits": [], "sound_cues": [{"t": 1.0, "text": "soft wind"}],
        "arc_sec": 2.0, "writer_seconds": 5.0, "cut_to_next": "cut", "source_refs": ["ch2:p10"],
        "cast": [member],
    }


def _write_blocking(directory, shot_id):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (shot_id + ".json")).write_text(json.dumps(_sheet(shot_id)), encoding="utf-8")


# ---- 1-3: a failed call must still settle and log ----

def test_call_raises_still_settles_and_logs(tmp_path):
    ledger = _ledger(tmp_path)
    usage = tmp_path / "usage.jsonl"
    call = _RaisingCall(OSError("pipe broke"))
    with pytest.raises(OSError):
        writer_guard.guarded_call("stage1", "prompt", call, ledger, 50, usage)
    assert _open_reservations(ledger) == []
    ledger.reserve("after", 1)  # must not raise: no open reservation is left
    rows = _usage_rows(usage)
    assert len(rows) == 1
    assert rows[0]["is_error"] is True


def test_empty_stream_raises_runtime_error(tmp_path):
    ledger = _ledger(tmp_path)
    usage = tmp_path / "usage.jsonl"
    with pytest.raises(RuntimeError, match="no result"):
        writer_guard.guarded_call("stage1", "prompt", _FakeCall(""), ledger, 50, usage)
    assert _open_reservations(ledger) == []
    assert [r["state"] for r in _ledger_lines(tmp_path)] == ["RESERVED", "SETTLED"]
    assert len(_usage_rows(usage)) == 1


def test_stream_without_result_line_raises(tmp_path):
    ledger = _ledger(tmp_path)
    stream = _retry_line("overloaded")
    with pytest.raises(RuntimeError):
        writer_guard.guarded_call("stage1", "prompt", _FakeCall(stream), ledger, 50, tmp_path / "usage.jsonl")
    assert _open_reservations(ledger) == []


# ---- 4-5: bad cost values in the result line ----

def test_negative_cost_raises(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.reserve("seed", 10)
    ledger.settle("seed", 10, confirmed=True)
    before = ledger.committed()  # 10
    with pytest.raises(RuntimeError):
        writer_guard.guarded_call("stage1", "prompt", _FakeCall(_result_line(cost=-0.5)), ledger, 50,
                                  tmp_path / "usage.jsonl")
    assert ledger.committed() >= before


def _bad_cost_run(tmp_path, cost):
    ledger = _ledger(tmp_path)
    with pytest.raises(RuntimeError):
        writer_guard.guarded_call("stage1", "prompt", _FakeCall(_result_line(cost=cost)), ledger, 50,
                                  tmp_path / "usage.jsonl")
    assert _open_reservations(ledger) == []
    settled = [r for r in ledger.rows().values() if r["state"] == "SETTLED"]
    assert len(settled) == 1
    assert settled[0]["credits"] == 50


def test_nan_cost_raises(tmp_path):
    _bad_cost_run(tmp_path, float("nan"))


def test_string_cost_raises(tmp_path):
    _bad_cost_run(tmp_path, "0.5")


def test_inf_cost_raises(tmp_path):
    _bad_cost_run(tmp_path, float("inf"))


# ---- 6: est_cents must be a positive int ----

def _refuse_est(tmp_path, est):
    call = _FakeCall(_result_line())
    with pytest.raises(SystemExit):
        writer_guard.guarded_call("stage1", "prompt", call, _ledger(tmp_path), est, tmp_path / "usage.jsonl")
    assert call.count == 0


def test_negative_est_cents_refused(tmp_path):
    _refuse_est(tmp_path, -5)


def test_zero_est_cents_refused(tmp_path):
    _refuse_est(tmp_path, 0)


def test_float_est_cents_refused(tmp_path):
    _refuse_est(tmp_path, 50.0)


def test_bool_est_cents_refused(tmp_path):
    _refuse_est(tmp_path, True)


# ---- 7: the env value is THE cap ----

def test_cap_env_is_the_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITER_CAP_CENTS", "5")
    call = _FakeCall(_result_line())
    with pytest.raises(SystemExit):
        writer_guard.guarded_call("stage1", "prompt", call, _ledger(tmp_path, cap=1000), 50,
                                  tmp_path / "usage.jsonl")
    assert call.count == 0


def test_ledger_cap_must_equal_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITER_CAP_CENTS", "200")
    call = _FakeCall(_result_line())
    with pytest.raises(SystemExit):
        writer_guard.guarded_call("stage1", "prompt", call, _ledger(tmp_path, cap=1000), 10,
                                  tmp_path / "usage.jsonl")
    assert call.count == 0


# ---- 8: garbage cap values must be a SystemExit, never ValueError ----

@pytest.mark.parametrize("value", ["abc", "1e9", "0.0", "-5", " ", ""])
def test_cap_env_garbage_systemexit(tmp_path, monkeypatch, value):
    monkeypatch.setenv("WRITER_CAP_CENTS", value)
    call = _FakeCall(_result_line())
    with pytest.raises(SystemExit):
        writer_guard.guarded_call("stage1", "prompt", call, _ledger(tmp_path), 50, tmp_path / "usage.jsonl")
    assert call.count == 0


# ---- 9: cli_ready wraps OS errors ----

def test_cli_ready_oserror_wrapped():
    def run(*args, **kwargs):
        raise OSError("exec failed")
    with pytest.raises(writer_guard.WriterUnavailable):
        writer_guard.cli_ready(which=lambda name: "/usr/bin/claude", run=run)


# ---- 10: validate_pack reports bad rows instead of crashing or passing ----

def test_rows_not_dicts_reported(tmp_path):
    problems = writer_guard.validate_pack([5, "x"], str(tmp_path))
    assert isinstance(problems, list)
    assert problems


def test_row_without_id_reported(tmp_path):
    row = {"time_range": "00:00-00:04", "audio_and_dialogue_track": "wind", "per_second_directives": []}
    problems = writer_guard.validate_pack([row], str(tmp_path))
    assert problems
    assert any("id" in p for p in problems)


def test_row_id_int_reported(tmp_path):
    _write_blocking(tmp_path, "SHOT-001")
    row = _pack_row(7, [_directive(0.0, 2.0), _directive(2.0, 4.0)])
    problems = writer_guard.validate_pack([row], str(tmp_path))
    assert problems


def test_directives_string_reported(tmp_path):
    _write_blocking(tmp_path, "SHOT-001")
    row = _pack_row("SHOT-001", "abc")
    problems = writer_guard.validate_pack([row], str(tmp_path))
    assert problems


def test_duplicate_ids_reported(tmp_path):
    _write_blocking(tmp_path, "SHOT-001")
    rows = [
        _pack_row("SHOT-001", [_directive(0.0, 2.0), _directive(2.0, 4.0)]),
        _pack_row("SHOT-001", [_directive(0.0, 2.0), _directive(2.0, 4.0)]),
    ]
    problems = writer_guard.validate_pack(rows, str(tmp_path))
    assert any("SHOT-001" in p for p in problems)
