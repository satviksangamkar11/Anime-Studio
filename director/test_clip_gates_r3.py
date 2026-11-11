import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import clip_gates


def _valid_results():
    return {
        "tail": {"flag": False, "first_spike_index": None},
        "end": {"pass": True, "failed": []},
        "cuts": [],
        "new_classes": [],
        "flicker": 0.1,
        "flicker_limit": 0.5,
    }


def test_tail_without_flag_raises():
    results = _valid_results()
    results["tail"] = {}
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results)


def test_tail_flag_not_bool_raises():
    results = _valid_results()
    results["tail"] = {"flag": 1}
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results)


def test_flicker_none_raises_clip_gate_error():
    results = _valid_results()
    results["flicker"] = None
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results)


def test_flicker_nan_raises():
    results = _valid_results()
    results["flicker"] = float("nan")
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results)


def test_limit_nan_raises():
    results = _valid_results()
    results["flicker_limit"] = float("nan")
    with pytest.raises(clip_gates.ClipGateError):
        clip_gates.verdict(results)


def test_valid_results_still_pass():
    results = _valid_results()
    out = clip_gates.verdict(results)
    assert out["pass"] is True
    assert out["reasons"] == []
