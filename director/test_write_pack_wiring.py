"""Frozen tests for the X-07 edits inside director/write_pack.py (rule 54(3): written before the code).
No real claude: subprocess.run and shutil.which are monkeypatched; run_stage is driven with fakes.

ASSUMED SHAPES (not written yet):
  call_claude_raw(prompt, model, effort, web=False, rule=True, max_budget_usd=None) -> str (r.stdout, raw)
      max_budget_usd not None adds ['--max-budget-usd', '%.2f' % value] to argv
  call_claude(prompt, model, effort, ...) keeps working: returns join_stream(call_claude_raw(...))
  run_stage(name, out, *, prompt_for, call, parse_fn, check_fn, rec): unchanged signature. Targeted repair:
      check errors that all name a SHOT id -> ONE repair call whose prompt holds only the named rows; the answer goes to
      stage_<name>_repair<k>.json (never to stage_<name>_raw.json); rows merged by id; re-checked.
      An error line without a SHOT id, or a dict stage, raises StageFailed with no second call.
      writer_guard.WriterLimit propagates (not wrapped), with no repair.
  prompt_for(errors) in these tests returns a base brief only (no rows): the rows reach the repair prompt from the
      saved answer, so the markers can only come from the repair itself.
  The call fake writes its answer to the path it is given; parse_fn(raw) -> (raw, list of rows).
"""
import json
import os
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import write_pack  # noqa: E402
import writer_guard  # noqa: E402

STREAM = "\n".join([
    json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "```json shots\n[]\n```"}]}}),
    json.dumps({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.30,
                "num_turns": 2, "usage": {}, "result": "ok"}),
])


class _Proc:
    def __init__(self, stdout):
        self.returncode = 0
        self.stdout = stdout
        self.stderr = ""


def _fake_popen_run(stdout, calls):
    def fake_run(*args, **kwargs):
        calls.append(list(args[0]))
        return _Proc(stdout)
    return fake_run


def test_call_claude_raw_has_budget_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(write_pack.subprocess, "run", _fake_popen_run(STREAM, calls))
    monkeypatch.setattr(write_pack.shutil, "which", lambda name, *a, **k: "/usr/bin/claude")
    out = write_pack.call_claude_raw("prompt", "opus", "medium", max_budget_usd=0.5)
    assert out == STREAM
    argv = calls[0]
    assert "--max-budget-usd" in argv
    assert argv[argv.index("--max-budget-usd") + 1] == "0.50"


def test_call_claude_raw_without_budget_has_no_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(write_pack.subprocess, "run", _fake_popen_run(STREAM, calls))
    monkeypatch.setattr(write_pack.shutil, "which", lambda name, *a, **k: "/usr/bin/claude")
    write_pack.call_claude_raw("prompt", "opus", "medium", max_budget_usd=None)
    assert "--max-budget-usd" not in calls[0]


def test_call_claude_still_joins_stream(monkeypatch):
    calls = []
    monkeypatch.setattr(write_pack.subprocess, "run", _fake_popen_run(STREAM, calls))
    monkeypatch.setattr(write_pack.shutil, "which", lambda name, *a, **k: "/usr/bin/claude")
    assert write_pack.call_claude("prompt", "opus", "medium") == write_pack.join_stream(STREAM)


# run_stage fakes: three shot rows; row 2 carries a bad marker until repaired

class _Rec:
    @contextmanager
    def step(self, *args, **kwargs):
        yield SimpleNamespace(chars=None, files=[], note="")


def _rows():
    return [
        {"id": "SHOT-001", "text": "MARK-ROW-1 fine"},
        {"id": "SHOT-002", "text": "MARK-ROW-2 BAD-2"},
        {"id": "SHOT-003", "text": "MARK-ROW-3 fine"},
    ]


def _parse(raw):
    return raw, json.loads(raw)


def _check_row2(data):
    if isinstance(data, list) and any(r.get("id") == "SHOT-002" and "BAD-2" in r.get("text", "") for r in data):
        return ["BLK-L03 at SHOT-002: end not reachable"]
    return []


class _Calls:
    """First call writes all three rows; any later call writes only the corrected row 2 (as the repair asks)."""

    def __init__(self, first_rows=None, raise_on_first=None):
        self.prompts = []
        self.paths = []
        self.written = []
        self.first_rows = first_rows if first_rows is not None else _rows()
        self.raise_on_first = raise_on_first

    def __call__(self, prompt, path):
        self.prompts.append(prompt)
        self.paths.append(path)
        if len(self.prompts) == 1 and self.raise_on_first is not None:
            raise self.raise_on_first
        if len(self.prompts) == 1:
            body = json.dumps(self.first_rows, ensure_ascii=False, indent=1)
        else:
            body = json.dumps([{"id": "SHOT-002", "text": "MARK-ROW-2 FIXED"}], ensure_ascii=False, indent=1)
        path.write_text(body, encoding="utf-8")
        self.written.append(path.read_bytes())


def _prompt_for(errors):
    return "BASE BRIEF" + ("\n" + "\n".join(errors) if errors else "")


def test_repair_only_named_shots(tmp_path):
    out = tmp_path / "pack"
    out.mkdir()
    calls = _Calls()
    text, data = write_pack.run_stage("3e1", out, prompt_for=_prompt_for, call=calls, parse_fn=_parse,
                                      check_fn=_check_row2, rec=_Rec())
    assert len(calls.prompts) == 2
    repair_prompt = calls.prompts[1]
    assert "SHOT-002" in repair_prompt
    assert "MARK-ROW-2" in repair_prompt
    assert "MARK-ROW-1" not in repair_prompt
    assert "MARK-ROW-3" not in repair_prompt
    first = _rows()
    assert data[0] == first[0]
    assert data[2] == first[2]
    assert data[1]["text"] == "MARK-ROW-2 FIXED"
    raw_path = out / "stage_3e1_raw.json"
    assert raw_path.read_bytes() == calls.written[0]
    assert (out / "stage_3e1_repair1.json").exists()


def test_unattributable_error_fails_stage(tmp_path):
    out = tmp_path / "pack"
    out.mkdir()
    calls = _Calls()
    with pytest.raises(write_pack.StageFailed):
        write_pack.run_stage("3e1", out, prompt_for=_prompt_for, call=calls, parse_fn=_parse,
                             check_fn=lambda data: ["something is wrong"], rec=_Rec())
    assert len(calls.prompts) == 1


def test_dict_stage_without_ids_fails_without_repair(tmp_path):
    out = tmp_path / "pack"
    out.mkdir()
    calls = _Calls(first_rows={"episodes": [1, 2]})
    with pytest.raises(write_pack.StageFailed):
        write_pack.run_stage("1", out, prompt_for=_prompt_for, call=calls, parse_fn=_parse,
                             check_fn=lambda data: ["plan has no episode list"], rec=_Rec())
    assert len(calls.prompts) == 1


def test_limit_error_stops_without_repair(tmp_path):
    out = tmp_path / "pack"
    out.mkdir()
    calls = _Calls(raise_on_first=writer_guard.WriterLimit("writer limit error: rate_limit"))
    with pytest.raises(writer_guard.WriterLimit):
        write_pack.run_stage("3e1", out, prompt_for=_prompt_for, call=calls, parse_fn=_parse,
                             check_fn=_check_row2, rec=_Rec())
    assert len(calls.prompts) == 1


def test_good_stage_unchanged(tmp_path):
    out = tmp_path / "pack"
    out.mkdir()
    good = [{"id": "SHOT-001", "text": "MARK-ROW-1 fine"}]
    calls = _Calls(first_rows=good)
    text, data = write_pack.run_stage("3e1", out, prompt_for=_prompt_for, call=calls, parse_fn=_parse,
                                      check_fn=lambda d: [], rec=_Rec())
    assert len(calls.prompts) == 1
    assert data == good
    assert text.replace("\r\n", "\n") == calls.written[0].decode("utf-8").replace("\r\n", "\n")
    assert not (out / "stage_3e1_repair1.json").exists()
