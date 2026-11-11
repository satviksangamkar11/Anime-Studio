"""Tests for director.waivers (S-17)."""

import json

import pytest

from waivers import load_waivers


def _write(tmp_path, data):
    p = tmp_path / "waivers.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def _good(**over):
    data = {
        "reel": 2,
        "codes": ["DEAD_AIR_PAUSE"],
        "owner": "Satvik",
        "date": "2026-11-11",
        "reason": "test fixture",
    }
    data.update(over)
    return data


def test_missing_file_empty(tmp_path):
    assert load_waivers(str(tmp_path / "nope.json"), 2) == frozenset()


def test_reel_mismatch_raises(tmp_path):
    path = _write(tmp_path, _good(reel=1))
    with pytest.raises(ValueError):
        load_waivers(path, 2)


def test_good_file_codes(tmp_path):
    path = _write(tmp_path, _good(codes=["DEAD_AIR_PAUSE", "CLOSING_MOUTH_OPEN"]))
    assert load_waivers(path, 2) == frozenset({"DEAD_AIR_PAUSE", "CLOSING_MOUTH_OPEN"})


@pytest.mark.parametrize("code", ["dead_air", "DEAD-AIR", "DEAD AIR", "DEAD1", ""])
def test_bad_code_raises(tmp_path, code):
    path = _write(tmp_path, _good(codes=[code]))
    with pytest.raises(ValueError):
        load_waivers(path, 2)
