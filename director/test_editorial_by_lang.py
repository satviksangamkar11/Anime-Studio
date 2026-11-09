"""Offline tests for editorial_by_lang: missing file = v3 lengths, shared timeline only, trims/windows, rounding rules. No ffmpeg."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editorial_by_lang as e  # noqa: E402


def h3(n=3):
    out = []
    for i in range(n):
        out.append({"shot_id": f"SHOT-00{i + 1}", "timing_and_lattice": {"fps": 24, "pixel_frames": 200, "trim_in_frame": 8, "trim_out_frame": 152,
                    "editorial_frames": 144, "editorial_duration_sec": 6.0, "trim_in_sec": 0.33, "trim_out_sec": 6.33}})
    return out


def test_missing_file_changes_nothing(tmp_path):
    rows = [{"id": "SHOT-001", "editorial_duration_sec": 6.0}]
    assert e.load(tmp_path) == {}
    assert e.apply_rows(rows, {}) == rows
    shots = h3()
    out = e.apply_shots(shots, {})
    assert [s["timing_and_lattice"]["trim_out_frame"] for s in out] == [152] * 3 and shots == h3()   # input untouched


def test_languages_must_share_one_timeline(tmp_path):
    (tmp_path / e.FILE).write_text(json.dumps({"by_lang": {"en": {"SHOT-001": {"extend_frames": 5}}, "hi": {"SHOT-001": {"extend_frames": 6}}}}))
    with pytest.raises(ValueError):
        e.load(tmp_path)


def test_extensions_move_trims_and_master_windows():
    ext = {"SHOT-001": (12, "end"), "SHOT-003": (6, "start")}
    out = [s["timing_and_lattice"] for s in e.apply_shots(h3(), ext)]
    assert out[0]["trim_out_frame"] == 164 and out[0]["editorial_frames"] == 156 and out[0]["editorial_duration_sec"] == 6.5
    assert out[1]["master_reel_frame_window"] == [156, 300]
    assert out[2]["trim_in_frame"] == 2 and out[2]["trim_out_frame"] == 152 and out[2]["master_reel_frame_window"] == [300, 450]
    assert e.apply_rows([{"id": "SHOT-001", "editorial_duration_sec": 6.0}], ext)[0]["editorial_duration_sec"] == 6.5
    with pytest.raises(ValueError):
        e.apply_shots(h3(), {"SHOT-001": (49, "end")})                 # more than the 48 spare tail frames


def test_rounding_rules():
    beat = 60 / 176
    assert e.plan_shot(6.9, 6.8, 7.0, 33, 24, beat) == (0, "fits at natural speed")
    f, note = e.plan_shot(7.393, 7.274, 7.0, 33, 24, beat)                # 0.393 s -> 2 beats = 0.682 s -> 16 frames
    assert f == 16 and "up to 2" in note
    f, note = e.plan_shot(7.2, 7.1, 7.0, 6, 24, 60 / 128)                  # 1 beat (11 fr) does not fit in 6 spare -> 0 beats, voice > 1.03
    assert f == 0 and "down" in note and "ABOVE" in note
    assert e.plan_shot(5.37, 5.2, 5.0, 30, 24)[0] == 9                     # no rounding: ceil(0.37 * 24)
    assert e.plan_shot(5.37, 5.2, 5.0, 4, 24)[0] == 4                      # capped by spare


def test_needed_sec_at_a_speed_up_is_shorter():
    lines = [{"id": "a", "start": 0.5, "natural": 3.0}]
    assert abs(e.needed_sec(lines, 1.0) - (3.5 + e.TAIL)) < 1e-6
    assert abs(e.needed_sec(lines, 1.5) - (2.5 + e.TAIL)) < 1e-6
