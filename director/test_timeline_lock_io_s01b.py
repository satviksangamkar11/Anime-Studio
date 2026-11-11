import os
import sys
import math
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import timeline_lock_io


def _shot(sid, start, edit, pf=None):
    if pf is None:
        pf = 17 * math.ceil((max(edit, 107) - 5) / 17) + 5
    return {'id': sid, 'start_frame': start, 'edit_frames': edit, 'pixel_frames': pf, 'trim_in_frame': 0, 'trim_out_frame': edit, 'end_frame_position': edit - 1, 'error_ms': 0.0}


def _write(tmp_path, shots):
    inputs = [str(tmp_path / "input.bin")]
    with open(inputs[0], "wb") as handle:
        handle.write(b"x" * 100)
    path = str(tmp_path / "timeline_lock_v1.json")
    return timeline_lock_io.write_lock(path, shots, inputs, {'margin_frames': 6})


def test_suggest_retime_equal_is_one():
    assert timeline_lock_io.suggest_retime(144, 144) == 1.0


def test_suggest_retime_shorter_language():
    assert timeline_lock_io.suggest_retime(144, 136) == 0.944444


def test_suggest_retime_clamped_low():
    assert timeline_lock_io.suggest_retime(144, 100) == 0.94


def test_suggest_retime_clamped_high():
    assert timeline_lock_io.suggest_retime(144, 200) == 1.06


def test_suggest_retime_custom_limit():
    assert timeline_lock_io.suggest_retime(144, 100, limit=0.1) == 0.9


def test_suggest_retime_bad_values_raise():
    with pytest.raises(ValueError):
        timeline_lock_io.suggest_retime(0, 100)
    with pytest.raises(ValueError):
        timeline_lock_io.suggest_retime(100, -5)
    with pytest.raises(ValueError):
        timeline_lock_io.suggest_retime(True, 100)
    with pytest.raises(ValueError):
        timeline_lock_io.suggest_retime(100, 100.5)
    with pytest.raises(ValueError):
        timeline_lock_io.suggest_retime(144, 100, limit=0.9)


def test_lock_with_retime_round_trips(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    shots[0]['retime'] = {'hi': 0.97, 'mr': 1.03}
    lock = _write(tmp_path, shots)
    loaded = timeline_lock_io.load_lock(lock['path'] if 'path' in lock else str(tmp_path / "timeline_lock_v1.json"))
    assert timeline_lock_io.retime_for(loaded, 's1', 'hi') == 0.97
    assert timeline_lock_io.retime_for(loaded, 's1', 'mr') == 1.03
    assert timeline_lock_io.retime_for(loaded, 's1', 'en') == 1.0
    assert timeline_lock_io.retime_for(loaded, 's2', 'hi') == 1.0


def test_load_rejects_retime_out_of_range(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    shots[0]['retime'] = {'hi': 0.5}
    with pytest.raises(ValueError):
        _write(tmp_path, shots)
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    shots[0]['retime'] = {'hi': 1.5}
    with pytest.raises(ValueError):
        _write(tmp_path, shots)


def test_load_rejects_retime_bool_nan_and_bad_keys(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    shots[0]['retime'] = {'hi': True}
    with pytest.raises(ValueError):
        _write(tmp_path, shots)
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    shots[0]['retime'] = {'hi': float('nan')}
    with pytest.raises(ValueError):
        _write(tmp_path, shots)
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    shots[0]['retime'] = {'': 1.0}
    with pytest.raises(ValueError):
        _write(tmp_path, shots)
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    shots[0]['retime'] = [1.0]
    with pytest.raises(ValueError):
        _write(tmp_path, shots)


def test_retime_for_unknown_shot_raises(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    lock = _write(tmp_path, shots)
    loaded = timeline_lock_io.load_lock(lock['path'] if 'path' in lock else str(tmp_path / "timeline_lock_v1.json"))
    with pytest.raises(ValueError):
        timeline_lock_io.retime_for(loaded, 'nope', 'hi')
