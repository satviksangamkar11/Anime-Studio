import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import subprocess

import pytest

import script_inspect


def test_row_without_id_raises_value_error():
    rows = [{"editorial_duration_sec": 5.0, "audio_and_dialogue_track": {}}]
    with pytest.raises(ValueError) as exc:
        script_inspect.from_pack(rows, "en")
    assert "row 0: missing id" in str(exc.value)


def test_row_without_duration_raises():
    rows = [{"id": "r1", "audio_and_dialogue_track": {}}]
    with pytest.raises(ValueError) as exc:
        script_inspect.from_pack(rows, "en")
    assert "row r1: missing editorial_duration_sec" in str(exc.value)


def test_row_without_track_raises():
    rows = [{"id": "r1", "editorial_duration_sec": 5.0}]
    with pytest.raises(ValueError) as exc:
        script_inspect.from_pack(rows, "en")
    assert "row r1: missing audio_and_dialogue_track" in str(exc.value)


def test_directive_without_t0_raises():
    rows = [{
        "id": "r1",
        "editorial_duration_sec": 5.0,
        "audio_and_dialogue_track": {},
        "per_second_directives": [{"action_pose_expression": "smile"}],
    }]
    with pytest.raises(ValueError) as exc:
        script_inspect.from_pack(rows, "en")
    assert "row r1: directive 0 has no usable t0" in str(exc.value)


def test_item_without_text_raises():
    rows = [{
        "id": "r1",
        "editorial_duration_sec": 5.0,
        "audio_and_dialogue_track": {
            "dialogue_by_lang": {
                "en": [{"time_range": [0.0, 1.0]}],
            },
        },
    }]
    with pytest.raises(ValueError) as exc:
        script_inspect.from_pack(rows, "en")
    assert "row r1: item without text or time_range" in str(exc.value)


def test_main_returns_2_for_incomplete_row(tmp_path):
    pack = [{"editorial_duration_sec": 5.0, "audio_and_dialogue_track": {}}]
    p = tmp_path / "pack.json"
    p.write_text(json.dumps(pack), encoding="utf-8")
    rc = script_inspect.main([str(p), "en"])
    assert rc == 2


def test_import_from_other_folder_still_finds_siblings(tmp_path):
    shots = [
        {
            "id": "s1",
            "seconds": 3.0,
            "action": "look",
            "events": [],
            "lines": [{"start_s": 0.0, "end_s": 1.0, "text": "hi"}],
        }
    ]
    code = (
        "import importlib.util\n"
        "spec = importlib.util.spec_from_file_location(\"si\", %r)\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "r = m.inspect_script(%r, \"en\")\n"
        "print(r[\"pass\"] in (True, False))\n"
    ) % (os.path.abspath(os.path.join(os.path.dirname(__file__), "script_inspect.py")), shots)
    result = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "True"
