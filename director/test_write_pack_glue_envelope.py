"""parse_repair reads a saved repair answer in both forms: the raw text answer and the saved write_pack envelope JSON.
Standard library and the existing fakes only: no network, no model call.
"""
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import write_pack
import write_pack_glue


FENCED_ROWS = [{"id": "SHOT-002", "text": "fixed"}]


def _fenced(rows):
    return "Here is the repair:\n```json\n" + json.dumps(rows, ensure_ascii=False, indent=1) + "\n```\n"


# ---- raw text answer (unchanged behaviour) ----------------------------------

def test_parse_repair_raw_fenced_text():
    assert write_pack_glue.parse_repair(_fenced(FENCED_ROWS)) == FENCED_ROWS


def test_parse_repair_raw_bare_list():
    assert write_pack_glue.parse_repair('[{"id": "SHOT-003"}]') == [{"id": "SHOT-003"}]


# ---- saved envelope file (the real shape write_pack writes) ----------------

def test_parse_repair_envelope_text_with_fence():
    env = write_pack.envelope(_fenced(FENCED_ROWS), "stop", "nvidia", "some-model")
    assert write_pack_glue.parse_repair(env) == FENCED_ROWS


def test_parse_repair_envelope_bare_list():
    env = write_pack.envelope(json.dumps(FENCED_ROWS), "stop", "claude", "opus")
    assert write_pack_glue.parse_repair(env) == FENCED_ROWS


def test_parse_repair_envelope_written_to_tmp_file(tmp_path):
    env = write_pack.envelope(_fenced(FENCED_ROWS), "stop", "openrouter", "m")
    path = tmp_path / "stage_3e1_repair1.json"
    path.write_text(env, encoding="utf-8")
    assert write_pack_glue.parse_repair(path.read_text(encoding="utf-8")) == FENCED_ROWS


def test_parse_repair_failed_envelope_raises():
    env = write_pack.envelope("", "length", "nvidia", "m")
    with pytest.raises(ValueError, match="failed or was cut off"):
        write_pack_glue.parse_repair(env)


@pytest.mark.parametrize("text", [
    write_pack.envelope("no list here", "stop", "claude", "opus"),
    write_pack.envelope('{"id": "SHOT-001"}', "stop", "claude", "opus"),
    write_pack.envelope('["just strings"]', "stop", "claude", "opus"),
])
def test_parse_repair_envelope_without_list_raises(text):
    with pytest.raises(ValueError):
        write_pack_glue.parse_repair(text)


# ---- end to end through write_pack.run_stage's repair path -----------------

class _Rec:
    @contextmanager
    def step(self, *args, **kwargs):
        yield SimpleNamespace(chars=None, files=[], note="")


def _check(data):
    if any(r.get("id") == "SHOT-002" and "BAD" in r.get("text", "") for r in data):
        return ["BLK-L03 at SHOT-002: end not reachable"]
    return []


def _parse(raw):
    text = json.loads(raw)["result"]
    return text, json.loads(text)


def test_run_stage_repair_reads_saved_envelope(tmp_path):
    rows = [{"id": "SHOT-001", "text": "ok"}, {"id": "SHOT-002", "text": "BAD"}]
    calls = []

    def call(prompt, path):
        calls.append(prompt)
        if len(calls) == 1:
            answer = json.dumps(rows)
        else:
            answer = _fenced(FENCED_ROWS)        # the repair answer, fenced, inside the saved envelope
        path.write_text(write_pack.envelope(answer, "stop", "claude", "opus"), encoding="utf-8")

    out = tmp_path / "pack_v1"
    out.mkdir()
    text, data = write_pack.run_stage("3e1", out, prompt_for=lambda errors: "BASE", call=call, parse_fn=_parse,
                                      check_fn=_check, rec=_Rec())
    assert len(calls) == 2
    assert data == [{"id": "SHOT-001", "text": "ok"}, {"id": "SHOT-002", "text": "fixed"}]
    assert (out / "stage_3e1_repair1.json").exists()
