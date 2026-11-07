"""Round-3 regressions (triage R3-H3, v4_to_h3.py): JSON Infinity/NaN timings and scalar reference anchors are
reported as problems for their shot, not raised out of the converter."""
import copy

from h3.tests.test_v4_to_h3 import build_pack
from h3.v4_to_h3 import convert_pack


def _convert(tmp_path, mutate):
    shots, bible, stage = build_pack(str(tmp_path))
    mutate(shots)
    return convert_pack({"shots": shots, "bible": bible, "stage": stage})


def test_infinite_editorial_duration_is_a_problem_not_an_overflow(tmp_path):
    res = _convert(tmp_path, lambda s: s[0].update(editorial_duration_sec=float("inf")))
    assert any("editorial_duration_sec" in p for p in res["problems"])


def test_nan_editorial_duration_is_a_problem_not_a_crash(tmp_path):
    res = _convert(tmp_path, lambda s: s[0].update(editorial_duration_sec=float("nan")))
    assert any("editorial_duration_sec" in p for p in res["problems"])


def test_scalar_character_positions_do_not_abort_the_shot(tmp_path):
    res = _convert(tmp_path, lambda s: s[0].update(reference_anchors={"character_positions": 42}))
    assert res is not None
    assert "story" in res
