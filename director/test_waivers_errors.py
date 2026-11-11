import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import waivers


def _write(tmp_path, data):
    p = tmp_path / "waivers.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_bool_reel_refused(tmp_path):
    path = _write(tmp_path, {"reel": True, "codes": [], "owner": "A", "date": "2024-01-01", "reason": ""})
    with pytest.raises(ValueError, match="reel"):
        waivers.load_waivers(path, 1)


def test_string_reel_refused(tmp_path):
    path = _write(tmp_path, {"reel": "1", "codes": [], "owner": "A", "date": "2024-01-01", "reason": ""})
    with pytest.raises(ValueError, match="reel"):
        waivers.load_waivers(path, 1)


def test_empty_owner_refused(tmp_path):
    path = _write(tmp_path, {"reel": 1, "codes": [], "owner": "", "date": "2024-01-01", "reason": ""})
    with pytest.raises(ValueError, match="owner"):
        waivers.load_waivers(path, 1)


def test_non_string_code_refused(tmp_path):
    path = _write(tmp_path, {"reel": 1, "codes": [1], "owner": "A", "date": "2024-01-01", "reason": ""})
    with pytest.raises(ValueError, match="code"):
        waivers.load_waivers(path, 1)


def test_codes_not_a_list_refused(tmp_path):
    path = _write(tmp_path, {"reel": 1, "codes": "ABC", "owner": "A", "date": "2024-01-01", "reason": ""})
    with pytest.raises(ValueError, match="codes"):
        waivers.load_waivers(path, 1)


def test_date_wrong_format_refused(tmp_path):
    path = _write(tmp_path, {"reel": 1, "codes": [], "owner": "A", "date": "01-01-2024", "reason": ""})
    with pytest.raises(ValueError, match="date"):
        waivers.load_waivers(path, 1)


def test_date_not_real_refused(tmp_path):
    path = _write(tmp_path, {"reel": 1, "codes": [], "owner": "A", "date": "2024-02-30", "reason": ""})
    with pytest.raises(ValueError, match="date"):
        waivers.load_waivers(path, 1)


def test_unknown_key_refused(tmp_path):
    path = _write(tmp_path, {"reel": 1, "codes": [], "owner": "A", "date": "2024-01-01", "reason": "", "extra": 1})
    with pytest.raises(ValueError, match="unknown"):
        waivers.load_waivers(path, 1)


def test_missing_key_refused(tmp_path):
    path = _write(tmp_path, {"reel": 1, "codes": [], "owner": "A", "date": "2024-01-01"})
    with pytest.raises(ValueError, match="missing"):
        waivers.load_waivers(path, 1)


# changed 2026-11-11 (owner delegated): reason must now be non-empty
def test_empty_reason_refused(tmp_path):
    path = _write(tmp_path, {"reel": 1, "codes": [], "owner": "A", "date": "2024-01-01", "reason": ""})
    with pytest.raises(ValueError):
        waivers.load_waivers(path, 1)
