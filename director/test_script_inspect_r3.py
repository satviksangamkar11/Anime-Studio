import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import script_inspect


def _write_script(tmp_path, shots):
    path = tmp_path / "script.json"
    path.write_text(json.dumps({"shots": shots}), encoding="utf-8")
    return str(path)


import json


def test_string_track_raises_value_error(tmp_path):
    row = {
        "id": "s1",
        "editorial_duration_sec": 3.0,
        "audio_and_dialogue_track": "not a dict",
    }
    with pytest.raises(ValueError) as exc:
        script_inspect.from_pack([row], "en")
    assert "audio_and_dialogue_track has a bad type" in str(exc.value)


def test_track_dialogue_not_list_raises(tmp_path):
    row = {
        "id": "s1",
        "editorial_duration_sec": 3.0,
        "audio_and_dialogue_track": {
            "narration_by_lang": {},
            "dialogue_by_lang": {"en": "not a list"},
        },
    }
    with pytest.raises(ValueError) as exc:
        script_inspect.from_pack([row], "en")
    assert "audio_and_dialogue_track has a bad type" in str(exc.value)


def test_main_lock_id_missing_in_script_returns_2(tmp_path, monkeypatch):
    import types

    lock_path = tmp_path / "lock.json"
    lock_path.write_text("{}", encoding="utf-8")

    script_path = tmp_path / "script.json"
    script_path.write_text(
        json.dumps({"shots": [{"id": "s1", "seconds": 3.0, "action": "look", "events": [], "lines": [{"start_s": 0.0, "end_s": 1.0, "text": "hi"}]}]}),
        encoding="utf-8",
    )

    fake = types.SimpleNamespace(
        load_lock=lambda path: {
            "fps": 24,
            "shots": [
                {"id": "s1", "edit_frames": 72},
                {"id": "zz", "edit_frames": 72},
            ],
        }
    )
    monkeypatch.setitem(sys.modules, "timeline_lock_io", fake)

    rc = script_inspect.main([str(script_path), "en", "--lock", str(lock_path)])
    assert rc == 2


def test_main_lock_matching_ids_ok(tmp_path, monkeypatch):
    import types

    lock_path = tmp_path / "lock.json"
    lock_path.write_text("{}", encoding="utf-8")

    script_path = tmp_path / "script.json"
    script_path.write_text(
        json.dumps({"shots": [{"id": "s1", "seconds": 3.0, "action": "look", "events": [], "lines": [{"start_s": 0.0, "end_s": 1.0, "text": "hi"}]}]}),
        encoding="utf-8",
    )

    fake = types.SimpleNamespace(
        load_lock=lambda path: {
            "fps": 24,
            "shots": [
                {"id": "s1", "edit_frames": 72},
            ],
        }
    )
    monkeypatch.setitem(sys.modules, "timeline_lock_io", fake)

    rc = script_inspect.main([str(script_path), "en", "--lock", str(lock_path)])
    assert rc in (0, 1)
