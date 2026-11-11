import os
import sys
import pytest
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import waivers


def _write_waiver(tmp_path, reason="ok reason"):
    path = tmp_path / "waivers.json"
    data = {
        "reel": 1,
        "codes": ["BAD_CODE"],
        "owner": "Alice",
        "date": "2024-01-15",
        "reason": reason,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_empty_reason_refused(tmp_path):
    path = _write_waiver(tmp_path, reason="")
    with pytest.raises(ValueError) as exc:
        waivers.load_waivers(path, 1)
    assert "reason" in str(exc.value)


def test_blank_reason_refused(tmp_path):
    path = _write_waiver(tmp_path, reason="   ")
    with pytest.raises(ValueError) as exc:
        waivers.load_waivers(path, 1)
    assert "reason" in str(exc.value)


def test_directory_path_refused(tmp_path):
    directory = tmp_path / "subdir"
    directory.mkdir()
    with pytest.raises(ValueError) as exc:
        waivers.load_waivers(directory, 1)
    assert "waivers path is not a file" in str(exc.value)


def test_missing_file_still_empty_frozenset(tmp_path):
    path = tmp_path / "does_not_exist.json"
    result = waivers.load_waivers(path, 1)
    assert result == frozenset()


def test_arabic_indic_digits_date_refused(tmp_path):
    path = _write_waiver(tmp_path, reason="ok reason")
    text = path.read_text(encoding="utf-8")
    bad_date = chr(1633) + chr(1634) + chr(1635) + chr(1636) + "-" + chr(1637) + chr(1638) + "-" + chr(1639) + chr(1640)
    text = text.replace("2024-01-15", bad_date)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        waivers.load_waivers(path, 1)
    assert "date" in str(exc.value)


def test_valid_file_still_loads(tmp_path):
    path = _write_waiver(tmp_path, reason="ok reason")
    result = waivers.load_waivers(path, 1)
    assert result == frozenset({"BAD_CODE"})
