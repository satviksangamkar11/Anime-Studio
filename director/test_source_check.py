"""Tests for director/source_check.py (card X-08). Every reviewer is a fake function; no model is called.

ASSUMED SIGNATURES (module not written yet):
  line_ids(source_text) -> {"L1": text, ...}: physical lines, 1-based, blank lines skipped, numbers kept
  citations(source_text, rows, sheets) -> list[str] problems; codes C1, C2, C3 appear in each message
      rows: pack rows, per_second_directives[].source_refs; sheets: blocking sheets, cast[].source_refs
      refs are line ids such as "L1"
  review(items, reviewer_fn, writer_model, reviewer_model) -> list of {"kind", "claim", "verdict"}
      items: [{"kind": "cast" | "directive", "claim": str, "refs": [str]}]
      reviewer_fn(claim, cited_lines) -> "supported" | "unsupported" | "unclear"; cited_lines = {ref: text}
      raises SameModelError (subclass of ValueError) when writer_model == reviewer_model
  write_report(path, source_text, shots_text, rows, sheets, items, reviewer_fn, writer_model, reviewer_model)
      writes JSON {source_sha256, shots_sha256, citations, verdicts, pass}
      pass = no citation problem and no "unsupported" verdict on a cast item
  main(argv) -> int; argv = ["--citations-only", source_path, shots_json_path, blocking_dir]
      shots_json_path holds a JSON list of pack rows; blocking_dir/*.json holds blocking sheets
      returns 0 when there are no problems, 1 otherwise
"""
import os
import sys
import json
import hashlib
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import source_check  # noqa: E402

SOURCE = "first line\nsecond line\nthird line\n"


def _sheet(shot_id, cast_refs):
    return {
        "shot_id": shot_id,
        "cast": [{"id": "SHIVA", "name": "SHIVA", "source_refs": cast_refs}],
    }


def _row(rid, refs):
    return {
        "id": rid,
        "per_second_directives": [
            {"t0": 0.0, "t1": 2.0, "text": "a man sits", "source_refs": refs},
            {"t0": 2.0, "t1": 4.0, "text": "he stands", "source_refs": ["L2"]},
        ],
    }


def _good_rows():
    return [_row("SHOT-001", ["L1"])]


def _good_sheets():
    return [_sheet("SHOT-001", ["L1"])]


def test_line_ids_skip_blank():
    assert source_check.line_ids("a\nb\n\nc\n\n") == {"L1": "a", "L2": "b", "L4": "c"}


def test_unknown_ref_L3_fails():
    rows = [_row("SHOT-001", ["L9"])]
    problems = source_check.citations(SOURCE, rows, _good_sheets())
    assert any("C2" in p for p in problems)


def test_cast_without_ref_fails():
    sheets = [_sheet("SHOT-001", [])]
    problems = source_check.citations(SOURCE, _good_rows(), sheets)
    assert any("C1" in p for p in problems)


def test_directive_without_ref_fails():
    rows = [{"id": "SHOT-001", "per_second_directives": [
        {"t0": 0.0, "t1": 2.0, "text": "a man sits"},
        {"t0": 2.0, "t1": 4.0, "text": "he stands", "source_refs": ["L2"]},
    ]}]
    problems = source_check.citations(SOURCE, rows, _good_sheets())
    assert any("C3" in p for p in problems)


def test_all_good_citations_pass():
    assert source_check.citations(SOURCE, _good_rows(), _good_sheets()) == []


def test_same_model_refused():
    items = [{"kind": "cast", "claim": "SHIVA sits", "refs": ["L1"]}]
    assert issubclass(source_check.SameModelError, ValueError)
    with pytest.raises(source_check.SameModelError):
        source_check.review(items, lambda claim, cited: "supported", "opus", "opus")


def test_unsupported_cast_fails_pass(tmp_path):
    items = [{"kind": "cast", "claim": "SHIVA sits", "refs": ["L1"]}]
    path = tmp_path / "source_check.json"
    source_check.write_report(str(path), SOURCE, json.dumps(_good_rows()), _good_rows(), _good_sheets(),
                              items, lambda claim, cited: "unsupported", "opus", "nemotron-super")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["pass"] is False


def test_write_report_pass_true_when_all_supported(tmp_path):
    items = [{"kind": "cast", "claim": "SHIVA sits", "refs": ["L1"]}]
    path = tmp_path / "source_check.json"
    source_check.write_report(str(path), SOURCE, json.dumps(_good_rows()), _good_rows(), _good_sheets(),
                              items, lambda claim, cited: "supported", "opus", "nemotron-super")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["pass"] is True
    assert len(report["verdicts"]) == 1


def test_unclear_does_not_fail_pass(tmp_path):
    items = [{"kind": "cast", "claim": "SHIVA sits", "refs": ["L1"]}]
    path = tmp_path / "source_check.json"
    source_check.write_report(str(path), SOURCE, json.dumps(_good_rows()), _good_rows(), _good_sheets(),
                              items, lambda claim, cited: "unclear", "opus", "nemotron-super")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["pass"] is True


def test_report_shas(tmp_path):
    shots_text = json.dumps(_good_rows())
    path = tmp_path / "source_check.json"
    source_check.write_report(str(path), SOURCE, shots_text, _good_rows(), _good_sheets(),
                              [], lambda claim, cited: "supported", "opus", "nemotron-super")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["source_sha256"] == hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
    assert report["shots_sha256"] == hashlib.sha256(shots_text.encode("utf-8")).hexdigest()


def _write_cli_inputs(tmp_path, rows):
    source_path = tmp_path / "source.txt"
    source_path.write_text(SOURCE, encoding="utf-8")
    shots_path = tmp_path / "shots.json"
    shots_path.write_text(json.dumps(rows), encoding="utf-8")
    blocking_dir = tmp_path / "blocking"
    blocking_dir.mkdir()
    (blocking_dir / "SHOT-001.json").write_text(json.dumps(_good_sheets()[0]), encoding="utf-8")
    return str(source_path), str(shots_path), str(blocking_dir)


def test_cli_citations_only_exit_codes(tmp_path):
    good = _write_cli_inputs(tmp_path, _good_rows())
    assert source_check.main(["--citations-only", *good]) == 0

    bad_rows = [{"id": "SHOT-001", "per_second_directives": [{"t0": 0.0, "t1": 2.0, "text": "no refs"}]}]
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    bad = _write_cli_inputs(bad_dir, bad_rows)
    assert source_check.main(["--citations-only", *bad]) == 1
