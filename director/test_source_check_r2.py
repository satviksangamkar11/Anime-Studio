"""Round-2 tests for director/source_check.py. Written BEFORE the fixes (rule 54(3)): hand-checked values, frozen after.
Every reviewer is a fake function; no model is called.

ASSUMED SIGNATURES (same as test_source_check.py):
  line_ids(source_text) -> {"L<n>": text}: physical lines, 1-based, blank lines skipped, numbers kept
  citations(source_text, rows, sheets) -> list[str]; codes C1, C2, C3 appear in each message
  write_report(path, source_text, shots_text, rows, sheets, items, reviewer_fn, writer_model, reviewer_model)
  reviewer_fn(claim, cited_lines) -> "supported" | "unsupported" | "unclear" | other; cited_lines = {ref: text}
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import source_check  # noqa: E402

SOURCE = "first line\nsecond line\nthird line\n"


def _good_rows():
    return [{
        "id": "SHOT-001",
        "per_second_directives": [
            {"t0": 0.0, "t1": 2.0, "text": "a man sits", "source_refs": ["L1"]},
            {"t0": 2.0, "t1": 4.0, "text": "he stands", "source_refs": ["L2"]},
        ],
    }]


def _good_sheets():
    return [{"shot_id": "SHOT-001", "cast": [{"id": "SHIVA", "name": "SHIVA", "source_refs": ["L1"]}]}]


def _report(tmp_path, items, reviewer_fn, sheets=None):
    path = tmp_path / "source_check.json"
    source_check.write_report(str(path), SOURCE, json.dumps(_good_rows()), _good_rows(),
                              _good_sheets() if sheets is None else sheets,
                              items, reviewer_fn, "opus", "nemotron-super")
    return json.loads(path.read_text(encoding="utf-8"))


def test_cast_unknown_ref_does_not_crash():
    sheets = [{"shot_id": "SHOT-001", "cast": [{"id": "SHIVA", "name": "SHIVA", "source_refs": ["L9"]}]}]
    problems = source_check.citations(SOURCE, _good_rows(), sheets)
    assert any("C2" in p for p in problems)


def test_cast_member_without_name_ok():
    sheets = [{"shot_id": "SHOT-001", "cast": [{"id": "SHIVA", "source_refs": ["L1"]}]}]
    assert source_check.citations(SOURCE, _good_rows(), sheets) == []


def test_non_str_ref_reported():
    sheets = [{"shot_id": "SHOT-001", "cast": [{"id": "SHIVA", "name": "SHIVA", "source_refs": [5, None]}]}]
    problems = source_check.citations(SOURCE, _good_rows(), sheets)
    assert any("C2" in p for p in problems)


def test_list_ref_does_not_crash():
    sheets = [{"shot_id": "SHOT-001", "cast": [{"id": "SHIVA", "name": "SHIVA", "source_refs": [["L1"]]}]}]
    problems = source_check.citations(SOURCE, _good_rows(), sheets)
    assert problems


def test_refs_string_reported():
    sheets = [{"shot_id": "SHOT-001", "cast": [{"id": "SHIVA", "name": "SHIVA", "source_refs": "L1"}]}]
    problems = source_check.citations(SOURCE, _good_rows(), sheets)
    assert problems


def test_cast_member_not_dict_reported():
    sheets = [{"shot_id": "SHOT-001", "cast": ["SHIVA"]}]
    problems = source_check.citations(SOURCE, _good_rows(), sheets)
    assert problems


def test_row_not_dict_reported():
    problems = source_check.citations(SOURCE, [5], _good_sheets())
    assert problems


def test_line_ids_crlf():
    # physical numbering: line 2 is the blank CRLF line, so "c" is L3
    assert source_check.line_ids("a\r\n\r\nc\r\n") == {"L1": "a", "L3": "c"}


def test_line_ids_matches_splitlines_unicode():
    text = "alpha" + chr(0x2028) + "beta"
    assert source_check.line_ids(text) == {"L1": "alpha", "L2": "beta"}


def test_reviewer_receives_source_text(tmp_path):
    recorded = {}

    def reviewer(claim, cited):
        recorded.update(cited)
        return "supported"

    _report(tmp_path, [{"kind": "cast", "claim": "SHIVA sits", "refs": ["L2"]}], reviewer)
    assert recorded["L2"] == "second line"


def test_unknown_verdict_fails_pass(tmp_path):
    items = [{"kind": "cast", "claim": "SHIVA sits", "refs": ["L1"]}]
    report = _report(tmp_path, items, lambda claim, cited: "maybe")
    assert report["pass"] is False


def test_empty_items_do_not_pass(tmp_path):
    # coverage rule: every cast member needs at least one verdict
    report = _report(tmp_path, [], lambda claim, cited: "supported")
    assert report["pass"] is False


def test_unclear_still_allowed_when_covered(tmp_path):
    items = [
        {"kind": "cast", "claim": "SHIVA sits", "refs": ["L1"]},
        {"kind": "cast", "claim": "SHIVA stands", "refs": ["L1"]},
    ]

    def reviewer(claim, cited):
        return "unclear" if claim == "SHIVA sits" else "supported"

    report = _report(tmp_path, items, reviewer)
    assert report["pass"] is True
