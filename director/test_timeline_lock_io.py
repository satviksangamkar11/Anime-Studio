"""Tests for director.timeline_lock_io."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

import timeline_lock_io

PARAMS = {"margin_frames": 6}


def _shot(sid, start, edit, pf=None):
    """Valid v2 shot row: trims 0..edit, error 0, smallest lattice size (17n+5 >= 107) that holds edit."""
    if pf is None:
        pf = 17 * math.ceil((max(edit, 107) - 5) / 17) + 5
    return {
        "id": sid,
        "start_frame": start,
        "edit_frames": edit,
        "pixel_frames": pf,
        "trim_in_frame": 0,
        "trim_out_frame": edit,
        "end_frame_position": edit - 1,
        "error_ms": 0.0,
    }


def _write_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_round_trip_write_load_equality(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("shot_1", 0, 10), _shot("shot_2", 10, 15)]

    lock_path = tmp_path / "timeline_lock.json"
    lock = timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS, fps=24)

    assert lock["version"] == 2
    assert lock["fps"] == 24
    assert lock["total_frames"] == 25
    assert lock["total_seconds"] == round(25 / 24, 6)
    assert lock["shots"] == shots

    loaded = timeline_lock_io.load_lock(lock_path)
    assert loaded == lock


def test_atomic_write_leaves_no_temp_file(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("s1", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS)

    temp_files = [p for p in tmp_path.iterdir() if p.name.startswith(lock_path.name + ".") and p.suffix == ".tmp"]
    assert temp_files == []
    assert lock_path.is_file()


def test_hash_changes_when_voice_file_changes_one_byte(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("s1", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    lock_a = timeline_lock_io.write_lock(tmp_path / "lock_a.json", shots, [voice], PARAMS)

    voice.write_bytes(b"audio datb")  # one byte changed
    lock_b = timeline_lock_io.write_lock(tmp_path / "lock_b.json", shots, [voice], PARAMS)

    assert lock_a["input_sha256"] != lock_b["input_sha256"]


def test_same_hash_for_reordered_inputs(tmp_path):
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    _write_file(a, b"aaa")
    _write_file(b, b"bbb")

    hash_ab = timeline_lock_io.input_sha256([a, b])
    hash_ba = timeline_lock_io.input_sha256([b, a])

    assert hash_ab == hash_ba


def test_verify_raises_stale_lock_on_changed_input(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("s1", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS)

    voice.write_bytes(b"audio datb")

    try:
        timeline_lock_io.verify_lock(lock_path, [voice], PARAMS)
    except timeline_lock_io.StaleLockError as exc:
        assert "stale timeline lock" in str(exc).lower()
    else:
        raise AssertionError("expected StaleLockError")


def test_verify_raises_stale_lock_on_missing_input_path(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("s1", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS)

    try:
        timeline_lock_io.verify_lock(lock_path, [tmp_path / "missing.wav"], PARAMS)
    except timeline_lock_io.StaleLockError as exc:
        assert "stale timeline lock" in str(exc).lower()
    else:
        raise AssertionError("expected StaleLockError")


def test_duplicate_shot_id_refused_and_file_not_created(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("s1", 0, 5), _shot("s1", 5, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    try:
        timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for duplicate shot id")

    assert not lock_path.exists()


def test_non_positive_edit_frames_refused(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [{"id": "s1", "edit_frames": 0, "pixel_frames": 4, "start_frame": 1}]
    lock_path = tmp_path / "timeline_lock.json"

    try:
        timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for non-positive edit_frames")

    assert not lock_path.exists()


def test_corrupt_json_raises_value_error(tmp_path):
    lock_path = tmp_path / "timeline_lock.json"
    lock_path.write_text("{ not valid json", encoding="utf-8")

    try:
        timeline_lock_io.load_lock(lock_path)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for corrupt JSON")


def test_total_frames_mismatch_raises_value_error(tmp_path):
    lock_path = tmp_path / "timeline_lock.json"
    bad_lock = {
        "version": 2,
        "fps": 24,
        "input_sha256": "abc",
        "inputs": [],
        "total_frames": 999,
        "total_seconds": 0.0,
        "shots": [_shot("s1", 0, 5)],
    }
    lock_path.write_text(json.dumps(bad_lock, ensure_ascii=False, indent=1), encoding="utf-8")

    try:
        timeline_lock_io.load_lock(lock_path)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for total_frames mismatch")


def test_devanagari_shot_id_survives_round_trip(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("\u0928\u092e\u0938\u094d\u092f\u093e\u0930\u094d\u0921\u093c\u0940", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS)
    loaded = timeline_lock_io.load_lock(lock_path)

    assert loaded["shots"][0]["id"] == shots[0]["id"]


def test_frames_for_returns_edit_frames(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("s1", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    lock = timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS)
    assert timeline_lock_io.frames_for(lock, "s1") == 5


def test_frames_for_key_error_when_absent(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")

    shots = [_shot("s1", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    lock = timeline_lock_io.write_lock(lock_path, shots, [voice], PARAMS)

    try:
        timeline_lock_io.frames_for(lock, "missing")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected KeyError for absent shot id")


def test_missing_lock_file_raises_file_not_found(tmp_path):
    lock_path = tmp_path / "timeline_lock.json"

    try:
        timeline_lock_io.load_lock(lock_path)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError for missing lock")


def test_input_sha256_missing_file_raises_file_not_found(tmp_path):
    try:
        timeline_lock_io.input_sha256([tmp_path / "missing.wav"])
    except FileNotFoundError as exc:
        assert "missing.wav" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError for missing input")


def test_verify_raises_stale_lock_when_path_differs_but_bytes_identical(tmp_path):
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    _write_file(first, b"same audio bytes")
    _write_file(second, b"same audio bytes")

    shots = [_shot("s1", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    timeline_lock_io.write_lock(lock_path, shots, [first], PARAMS)

    try:
        timeline_lock_io.verify_lock(lock_path, [second], PARAMS)
    except timeline_lock_io.StaleLockError as exc:
        assert "stale timeline lock" in str(exc).lower()
    else:
        raise AssertionError("expected StaleLockError for different input path with identical bytes")


def test_verify_raises_stale_lock_same_basename_other_directory(tmp_path):
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    _write_file(first_dir / "voice.wav", b"same audio bytes")
    _write_file(second_dir / "voice.wav", b"same audio bytes")

    shots = [_shot("s1", 0, 5)]
    lock_path = tmp_path / "timeline_lock.json"

    timeline_lock_io.write_lock(lock_path, shots, [first_dir / "voice.wav"], PARAMS)

    try:
        timeline_lock_io.verify_lock(lock_path, [second_dir / "voice.wav"], PARAMS)
    except timeline_lock_io.StaleLockError as exc:
        assert "path set" in str(exc)
    else:
        raise AssertionError("expected StaleLockError: same basename, other folder")


def _write_raw_lock(path: Path, shots: list, total: int) -> None:
    lock = {
        "version": 2,
        "fps": 24,
        "input_sha256": "x",
        "inputs": [],
        "total_frames": total,
        "total_seconds": 0.0,
        "shots": shots,
    }
    path.write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")


def test_load_lock_string_edit_frames_refused(tmp_path):
    lock_path = tmp_path / "timeline_lock.json"
    _write_raw_lock(lock_path, [{"id": "s1", "edit_frames": "5", "pixel_frames": 4, "start_frame": 1}], 5)
    try:
        timeline_lock_io.load_lock(lock_path)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for string edit_frames")


def test_load_lock_bool_edit_frames_refused(tmp_path):
    lock_path = tmp_path / "timeline_lock.json"
    _write_raw_lock(lock_path, [{"id": "s1", "edit_frames": True, "pixel_frames": 4, "start_frame": 1}], 1)
    try:
        timeline_lock_io.load_lock(lock_path)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for bool edit_frames")


def test_load_lock_non_dict_shot_refused(tmp_path):
    lock_path = tmp_path / "timeline_lock.json"
    _write_raw_lock(lock_path, ["s1"], 0)
    try:
        timeline_lock_io.load_lock(lock_path)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for non-dict shot entry")


def test_failed_write_leaves_no_target_and_no_temp(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio")
    target = tmp_path / "timeline_lock.json"
    shots = [dict(_shot("s1", 0, 10), extra=object())]
    with pytest.raises(TypeError):
        timeline_lock_io.write_lock(target, shots, [voice], PARAMS)
    assert not target.exists()
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_same_bytes_different_name_changes_hash(tmp_path):
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    _write_file(a, b"same bytes")
    _write_file(b, b"same bytes")
    assert timeline_lock_io.input_sha256([a]) != timeline_lock_io.input_sha256([b])


def test_name_and_bytes_boundary_is_not_ambiguous(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "ab"
    _write_file(first, b"bc")
    _write_file(second, b"c")
    assert timeline_lock_io.input_sha256([first]) != timeline_lock_io.input_sha256([second])


def test_backslash_path_hashes_like_forward_slash_and_is_stored_forward(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")
    back = str(voice)
    fwd = back.replace("\\", "/")
    assert timeline_lock_io.input_sha256([back]) == timeline_lock_io.input_sha256([fwd])
    shots = [_shot("s1", 0, 10)]
    lock = timeline_lock_io.write_lock(tmp_path / "lock.json", shots, [back], PARAMS)
    assert all("\\" not in p for p in lock["inputs"])


def test_write_lock_rejects_float_and_string_edit_frames(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio")
    for bad in (2.5, "5"):
        target = tmp_path / "lock.json"
        shots = [{"id": "s1", "edit_frames": bad, "pixel_frames": 22, "start_frame": 0}]
        with pytest.raises(ValueError, match="invalid edit_frames"):
            timeline_lock_io.write_lock(target, shots, [voice], PARAMS)
        assert not target.exists()


def _raw_lock(path: Path, **overrides) -> None:
    # changed 2026-11-11 (owner-approved): inputs must be non-empty
    lock = {
        "version": 2,
        "fps": 24,
        "input_sha256": "x",
        "lock_sha256": "x",
        "params": {},
        "inputs": ["x"],
        "total_frames": 10,
        "total_seconds": 0.416667,
        "shots": [_shot("s1", 0, 10)],
    }
    lock.update(overrides)
    path.write_text(json.dumps(lock), encoding="utf-8")


def test_load_lock_refuses_true_version(tmp_path):
    path = tmp_path / "lock.json"
    _raw_lock(path, version=True)
    with pytest.raises(ValueError):
        timeline_lock_io.load_lock(path)


def test_load_lock_refuses_float_total_frames(tmp_path):
    path = tmp_path / "lock.json"
    _raw_lock(path, total_frames=5.0, shots=[_shot("s1", 0, 5)])
    with pytest.raises(ValueError):
        timeline_lock_io.load_lock(path)


def test_load_lock_refuses_non_list_inputs(tmp_path):
    path = tmp_path / "lock.json"
    _raw_lock(path, inputs="voice.wav")
    with pytest.raises(ValueError):
        timeline_lock_io.load_lock(path)


def test_write_lock_refuses_non_str_shot_id(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio")
    for bad_id in (5, ["unhashable"]):
        target = tmp_path / "lock.json"
        shots = [{"id": bad_id, "edit_frames": 10, "pixel_frames": 22, "start_frame": 0}]
        with pytest.raises(ValueError):
            timeline_lock_io.write_lock(target, shots, [voice], PARAMS)
        assert not target.exists()


def test_write_lock_refuses_invalid_fps(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio")
    shots = [_shot("s1", 0, 10)]
    for bad_fps in (True, 24.0, 0, -1):
        target = tmp_path / "lock.json"
        with pytest.raises(ValueError):
            timeline_lock_io.write_lock(target, shots, [voice], PARAMS, fps=bad_fps)
        assert not target.exists()


def test_load_lock_refuses_invalid_fps(tmp_path):
    path = tmp_path / "lock.json"
    for bad_fps in (True, 24.0, 0, -1):
        _raw_lock(path, fps=bad_fps)
        with pytest.raises(ValueError):
            timeline_lock_io.load_lock(path)


def test_write_lock_missing_id_message_uses_index(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio")
    shots = [
        _shot("s1", 0, 10),
        {"edit_frames": 10, "pixel_frames": 22, "start_frame": 10},
    ]
    with pytest.raises(ValueError) as info:
        timeline_lock_io.write_lock(tmp_path / "lock.json", shots, [voice], PARAMS)
    assert "#1" in str(info.value)
    assert "shot None" not in str(info.value)


def test_dot_path_equals_abs_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_file(tmp_path / "a.wav", b"audio")
    lock_path = tmp_path / "lock.json"
    timeline_lock_io.write_lock(lock_path, [_shot("s1", 0, 10)], ["./a.wav"], PARAMS)
    lock = timeline_lock_io.verify_lock(lock_path, [str(tmp_path / "a.wav")], PARAMS)
    assert lock["shots"][0]["id"] == "s1"


def test_params_change_is_stale(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")
    lock_path = tmp_path / "lock.json"
    timeline_lock_io.write_lock(lock_path, [_shot("s1", 0, 10)], [voice], {"margin_frames": 6})
    with pytest.raises(timeline_lock_io.StaleLockError):
        timeline_lock_io.verify_lock(lock_path, [voice], {"margin_frames": 0})


def test_wav_byte_change_is_stale(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")
    lock_path = tmp_path / "lock.json"
    timeline_lock_io.write_lock(lock_path, [_shot("s1", 0, 10)], [voice], PARAMS)
    voice.write_bytes(b"audio datb")
    with pytest.raises(timeline_lock_io.StaleLockError):
        timeline_lock_io.verify_lock(lock_path, [voice], PARAMS)


def test_refuses_overwrite(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")
    lock_path = tmp_path / "lock.json"
    timeline_lock_io.write_lock(lock_path, [_shot("s1", 0, 10)], [voice], PARAMS)
    original = lock_path.read_bytes()
    with pytest.raises(FileExistsError):
        timeline_lock_io.write_lock(lock_path, [_shot("s1", 0, 11)], [voice], PARAMS)
    assert lock_path.read_bytes() == original


def test_empty_inputs_refused(tmp_path):
    with pytest.raises(ValueError):
        timeline_lock_io.write_lock(tmp_path / "lock.json", [_shot("s1", 0, 10)], [], PARAMS)
    assert not (tmp_path / "lock.json").exists()


def test_next_lock_path(tmp_path):
    assert timeline_lock_io.next_lock_path(tmp_path).name == "timeline_lock_v1.json"
    (tmp_path / "timeline_lock_v1.json").write_text("{}", encoding="utf-8")
    (tmp_path / "timeline_lock_v2.json").write_text("{}", encoding="utf-8")
    (tmp_path / "timeline_lock_v2.json.tmp").write_text("{}", encoding="utf-8")
    assert timeline_lock_io.next_lock_path(tmp_path).name == "timeline_lock_v3.json"
    assert timeline_lock_io.latest_lock_path(tmp_path).name == "timeline_lock_v2.json"


def test_diff_locks_reports_shot():
    old = {"shots": [_shot("S1", 0, 146), _shot("S2", 146, 102), _shot("S3", 248, 50)]}
    new = {"shots": [_shot("S1", 0, 146), _shot("S2", 146, 110), _shot("S3", 256, 50)]}
    changes = timeline_lock_io.diff_locks(old, new)
    assert {"id": "S2", "field": "edit_frames", "old": 102, "new": 110} in changes
    assert {"id": "S3", "field": "start_frame", "old": 248, "new": 256} in changes
    assert all(change["id"] != "S1" for change in changes)


def test_load_rejects_pf_22(tmp_path):
    path = tmp_path / "lock.json"
    _raw_lock(path, shots=[dict(_shot("s1", 0, 10), pixel_frames=22)])
    with pytest.raises(ValueError, match="pixel_frames"):
        timeline_lock_io.load_lock(path)


def test_load_rejects_trim_mismatch(tmp_path):
    path = tmp_path / "lock.json"
    _raw_lock(path, shots=[dict(_shot("s1", 0, 10), trim_out_frame=9)])
    with pytest.raises(ValueError, match="trim span"):
        timeline_lock_io.load_lock(path)


def test_load_rejects_duplicate_id(tmp_path):
    path = tmp_path / "lock.json"
    _raw_lock(path, shots=[_shot("s1", 0, 5), _shot("s1", 5, 5)])
    with pytest.raises(ValueError, match="duplicate shot id"):
        timeline_lock_io.load_lock(path)


def test_load_rejects_total_seconds_mismatch(tmp_path):
    path = tmp_path / "lock.json"
    _raw_lock(path, total_seconds=0.5)
    with pytest.raises(ValueError, match="total_seconds"):
        timeline_lock_io.load_lock(path)


def test_lock_rows_integer_offsets(tmp_path):
    voice = tmp_path / "voice.wav"
    _write_file(voice, b"audio data")
    shots = [_shot("S1", 0, 144), _shot("S2", 144, 144), _shot("S3", 288, 144)]
    lock = timeline_lock_io.write_lock(tmp_path / "lock.json", shots, [voice], PARAMS)
    rows = timeline_lock_io.lock_rows(lock)       # X-12: dict rows (was tuples)
    assert [(r["id"], r["start_frame"], r["edit_frames"]) for r in rows] == [("S1", 0, 144), ("S2", 144, 144), ("S3", 288, 144)]


# X-12: lock_rows helper (moved here from test_lock_rows_x12.py; names kept)
def test_lock_rows_hand():
    """Hand-computed values from the card: edit_frames [168,120,192] -> start [0,168,288],
    offsets [0.0, 7.0, 12.0], editorial durations [7.0, 5.0, 8.0], total 480 frames = 20.0 s.
    """
    lock = {
        "fps": 24,
        "shots": [
            {"id": "A", "start_frame": 0, "edit_frames": 168,
             "trim_in_frame": 0, "trim_out_frame": 168},
            {"id": "B", "start_frame": 168, "edit_frames": 120,
             "trim_in_frame": 0, "trim_out_frame": 120},
            {"id": "C", "start_frame": 288, "edit_frames": 192,
             "trim_in_frame": 0, "trim_out_frame": 192},
        ],
    }
    rows = timeline_lock_io.lock_rows(lock)
    assert len(rows) == 3

    assert rows[0] == {
        "id": "A",
        "start_frame": 0,
        "edit_frames": 168,
        "offset_sec": 0.0,
        "editorial_duration_sec": 7.0,
        "trim_in_frame": 0,
        "trim_out_frame": 168,
    }
    assert rows[1] == {
        "id": "B",
        "start_frame": 168,
        "edit_frames": 120,
        "offset_sec": 7.0,
        "editorial_duration_sec": 5.0,
        "trim_in_frame": 0,
        "trim_out_frame": 120,
    }
    assert rows[2] == {
        "id": "C",
        "start_frame": 288,
        "edit_frames": 192,
        "offset_sec": 12.0,
        "editorial_duration_sec": 8.0,
        "trim_in_frame": 0,
        "trim_out_frame": 192,
    }

    total_frames = sum(r["edit_frames"] for r in rows)
    assert total_frames == 480
    assert total_frames / lock["fps"] == 20.0


def test_start_frame_mismatch_raises():
    """A recorded start_frame that differs from the running integer sum must raise ValueError."""
    lock = {
        "fps": 24,
        "shots": [
            {"id": "A", "start_frame": 0, "edit_frames": 168,
             "trim_in_frame": 0, "trim_out_frame": 168},
            {"id": "B", "start_frame": 200, "edit_frames": 120,   # should be 168
             "trim_in_frame": 0, "trim_out_frame": 120},
        ],
    }
    with pytest.raises(ValueError):
        timeline_lock_io.lock_rows(lock)


def test_missing_trim_keys_raises():
    """Missing trim_in_frame or trim_out_frame must raise KeyError naming the shot."""
    lock = {
        "fps": 24,
        "shots": [
            {"id": "A", "start_frame": 0, "edit_frames": 168},   # no trim keys
        ],
    }
    with pytest.raises(KeyError) as exc_info:
        timeline_lock_io.lock_rows(lock)
    assert "A" in str(exc_info.value)
