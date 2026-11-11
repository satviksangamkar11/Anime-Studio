import os
import sys
import math
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import timeline_lock_io


def _shot(sid, start, edit, pf=None):
    if pf is None:
        pf = 17 * math.ceil((max(edit, 107) - 5) / 17) + 5
    return {'id': sid, 'start_frame': start, 'edit_frames': edit, 'pixel_frames': pf, 'trim_in_frame': 0, 'trim_out_frame': edit, 'end_frame_position': edit - 1, 'error_ms': 0.0}


def _make_lock(tmp_path, shots, inputs, params):
    target = tmp_path / "timeline_lock_v2.json"
    timeline_lock_io.write_lock(target, shots, inputs, params)
    return target


def test_second_write_to_same_target_raises_file_exists(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    inputs = [str(tmp_path / "input.bin")]
    with open(inputs[0], "wb") as handle:
        handle.write(b"hello")
    params = {'margin_frames': 6}
    target = _make_lock(tmp_path, shots, inputs, params)
    with pytest.raises(FileExistsError):
        timeline_lock_io.write_lock(target, shots, inputs, params)


def test_write_race_target_created_meanwhile(tmp_path, monkeypatch):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    inputs = [str(tmp_path / "input.bin")]
    with open(inputs[0], "wb") as handle:
        handle.write(b"hello")
    params = {'margin_frames': 6}
    target = str(tmp_path / "timeline_lock_v2.json")

    real_link = os.link

    def fake_link(source, destination):
        with open(destination, "w", encoding="utf-8") as handle:
            handle.write("race")
        real_link(source, destination)

    monkeypatch.setattr(timeline_lock_io.os, "link", fake_link)

    with pytest.raises(FileExistsError):
        timeline_lock_io.write_lock(target, shots, inputs, params)

    remaining = [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]
    assert remaining == []


def test_version_1_lock_refused(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    inputs = [str(tmp_path / "input.bin")]
    with open(inputs[0], "wb") as handle:
        handle.write(b"hello")
    params = {'margin_frames': 6}
    target = _make_lock(tmp_path, shots, inputs, params)

    with open(target, "r", encoding="utf-8") as handle:
        lock = json.load(handle)
    lock["version"] = 1
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(lock, handle)

    with pytest.raises(ValueError):
        timeline_lock_io.load_lock(target)


def test_empty_inputs_refused_on_load(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    inputs = [str(tmp_path / "input.bin")]
    with open(inputs[0], "wb") as handle:
        handle.write(b"hello")
    params = {'margin_frames': 6}
    target = _make_lock(tmp_path, shots, inputs, params)

    with open(target, "r", encoding="utf-8") as handle:
        lock = json.load(handle)
    lock["inputs"] = []
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(lock, handle)

    with pytest.raises(ValueError):
        timeline_lock_io.load_lock(target)


def test_negative_end_frame_position_refused_on_load(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    inputs = [str(tmp_path / "input.bin")]
    with open(inputs[0], "wb") as handle:
        handle.write(b"hello")
    params = {'margin_frames': 6}
    target = _make_lock(tmp_path, shots, inputs, params)

    with open(target, "r", encoding="utf-8") as handle:
        lock = json.load(handle)
    lock["shots"][0]["end_frame_position"] = -1
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(lock, handle)

    with pytest.raises(ValueError):
        timeline_lock_io.load_lock(target)


def test_negative_error_ms_refused_on_load(tmp_path):
    shots = [_shot('s1', 0, 144), _shot('s2', 144, 144)]
    inputs = [str(tmp_path / "input.bin")]
    with open(inputs[0], "wb") as handle:
        handle.write(b"hello")
    params = {'margin_frames': 6}
    target = _make_lock(tmp_path, shots, inputs, params)

    with open(target, "r", encoding="utf-8") as handle:
        lock = json.load(handle)
    lock["shots"][0]["error_ms"] = -1.0
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(lock, handle)

    with pytest.raises(ValueError):
        timeline_lock_io.load_lock(target)
