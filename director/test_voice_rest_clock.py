"""G11: one clock for voice_rest (shot-relative seconds on the sheet; reel seconds = shot start + value) and
the silence_ok field (shot-relative, max 2.0 s). Hand-computed: durations 3.5, 6.6, 12.0 -> shot 3 starts at 10.1 s."""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import blocking  # noqa: E402
import story_shape  # noqa: E402
from score import cue_sheet as cs  # noqa: E402
from test_blocking_11 import OPUS_EXAMPLE  # noqa: E402


def _rows():
    rows = [{"id": "SHOT-%03d" % (i + 1), "editorial_duration_sec": d} for i, d in enumerate([3.5, 6.6, 12.0])]
    rows[2]["voice_rest"] = [2.0, 4.5]
    return rows


def _sheet(**extra):
    s = copy.deepcopy(OPUS_EXAMPLE)  # writer_seconds 5.9
    s.update(extra)
    return s


def test_voice_rest_same_reel_window_in_story_shape_cue_sheet_silence():
    rows = _rows()
    win = story_shape.reel_window(rows, 2)
    assert [round(v, 3) for v in win] == [12.1, 14.6]
    # cue_sheet: pack value is shot-relative, shot starts at 10.1 s, length 12.0
    assert cs._rest_window({"voice_rest": [2.0, 4.5]}, 10.1, 12.0) == [12.1, 14.6]
    # the blocking sheet (silence rule input) gives the same reel window for voice_rest
    assert cs.blocking_window({"voice_rest": [2.0, 4.5]}, 10.1, "voice_rest") == [12.1, 14.6]
    assert cs.blocking_window({"voice_rest": None}, 10.1, "voice_rest") is None
    assert cs.blocking_window({"silence_ok": [1.0, 2.5]}, 10.1, "silence_ok") == [11.1, 12.6]
    errors, _ = story_shape.lint(rows, {})
    assert not any(e.startswith("SHAPE-10") for e in errors)


def test_story_shape_voice_rest_is_checked_against_its_own_shot():
    rows = _rows()
    rows[2]["voice_rest"] = [10.0, 13.0]  # past the end of the 12.0 s shot (but inside the reel)
    errors, warnings = story_shape.lint(rows, {"premise": {}})
    assert any(e.startswith("SHAPE-10") for e in errors + warnings)
    rows[2]["voice_rest"] = [2.0, 3.5]  # 1.5 s span
    errors, warnings = story_shape.lint(rows, {"premise": {}})
    assert any(e.startswith("SHAPE-10") for e in errors + warnings)


def test_silence_ok_max_2s():
    assert blocking.validate(_sheet(silence_ok=[1.0, 3.0])) == []
    assert blocking.validate(_sheet(silence_ok=None)) == []
    for bad in ([1.0, 3.1], [3.0, 1.0], [1.0], [-0.5, 1.0], [1.0, 6.5], "1-2", [1.0, "2"]):
        probs = blocking.validate(_sheet(silence_ok=bad))
        assert any("bad silence_ok" in p for p in probs), (bad, probs)


def test_blocking_10_sheet_ignores_silence_ok():
    s = _sheet(silence_ok=[1.0, 9.0], schema="blocking/1.0")
    assert not any("silence_ok" in p for p in blocking.validate(s))
