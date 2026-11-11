import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import clip_gates


def _valid_results():
    return {
        "tail": {"flag": False, "ratio": 1.0, "first_spike_index": None, "median": 1.0},
        "end": {"pass": True, "failed": []},
        "cuts": [],
        "new_classes": [],
        "flicker": 0.1,
        "flicker_limit": 1.0,
    }


def test_valid_date_accepted():
    results = _valid_results()
    out = clip_gates.verdict(results, owner_accept=[{"code": "TAIL_SNAP", "date": "2026-11-11", "note": "ok"}])
    assert isinstance(out, dict)
    assert "pass" in out


def test_month_13_refused():
    results = _valid_results()
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results, owner_accept=[{"code": "TAIL_SNAP", "date": "2026-13-01", "note": "x"}])


def test_feb_30_refused():
    results = _valid_results()
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results, owner_accept=[{"code": "TAIL_SNAP", "date": "2026-02-30", "note": "x"}])


def test_day_first_format_refused():
    results = _valid_results()
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results, owner_accept=[{"code": "TAIL_SNAP", "date": "11-11-2026", "note": "x"}])


def test_unpadded_refused():
    results = _valid_results()
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results, owner_accept=[{"code": "TAIL_SNAP", "date": "2026-1-1", "note": "x"}])


def test_int_date_refused():
    results = _valid_results()
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results, owner_accept=[{"code": "TAIL_SNAP", "date": 20261111, "note": "x"}])
