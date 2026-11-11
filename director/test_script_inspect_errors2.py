import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import script_inspect


def test_bool_t0_refused():
    row = {
        "id": "r1",
        "editorial_duration_sec": 5.0,
        "audio_and_dialogue_track": {},
        "per_second_directives": [{"action_pose_expression": "x", "t0": True}],
    }
    with pytest.raises(ValueError):
        script_inspect.from_pack([row], "en")


def test_non_dict_directive_refused():
    row = {
        "id": "r1",
        "editorial_duration_sec": 5.0,
        "audio_and_dialogue_track": {},
        "per_second_directives": [5],
    }
    with pytest.raises(ValueError):
        script_inspect.from_pack([row], "en")


def test_non_dict_item_refused():
    row = {
        "id": "r1",
        "editorial_duration_sec": 5.0,
        "audio_and_dialogue_track": {
            "dialogue_by_lang": {"en": ["text"]}
        },
    }
    with pytest.raises(ValueError, match="item without text or time_range"):
        script_inspect.from_pack([row], "en")


def test_main_prints_invalid_input_for_incomplete_row(tmp_path, capsys):
    path = tmp_path / "shots.json"
    path.write_text(json.dumps([{"editorial_duration_sec": 1.0, "audio_and_dialogue_track": {}}]), encoding="utf-8")
    rc = script_inspect.main([str(path), "en"])
    assert rc == 2
    assert "invalid input" in capsys.readouterr().out


def test_main_row_without_track_goes_through_from_pack(tmp_path, capsys):
    path = tmp_path / "shots.json"
    path.write_text(json.dumps([{"id": "r1", "editorial_duration_sec": 5.0}]), encoding="utf-8")
    rc = script_inspect.main([str(path), "en"])
    assert rc == 2
    assert "invalid input" in capsys.readouterr().out


def test_minimal_script_shot_without_lines_is_not_a_pack_row(tmp_path, capsys):
    path = tmp_path / "shots.json"
    path.write_text(json.dumps([{"id": "s1", "seconds": 3.0}]), encoding="utf-8")
    script_inspect.main([str(path), "en"])
    out = capsys.readouterr().out
    assert "invalid input: row" not in out
    assert "editorial_duration_sec" not in out


def test_script_shots_still_pass_through():
    shots = [{
        "id": "s1",
        "seconds": 3.0,
        "action": "look",
        "events": [],
        "lines": [{"start_s": 0.0, "end_s": 1.0, "text": "hi"}],
    }]
    result = script_inspect.inspect_script(shots, "en")
    assert isinstance(result, dict)
    assert "pass" in result
