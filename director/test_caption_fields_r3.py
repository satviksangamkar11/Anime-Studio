import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import caption_fields


def test_failed_row_skipped():
    rows = [
        {"line": "L1", "lang": "en", "text": "hello world", "ok": True},
        {"line": "L2", "lang": "en", "text": "bad line", "ok": False},
    ]
    result = caption_fields.manifest_lines(rows)
    assert len(result) == 1
    assert result[0]["id"] == "L1"


def test_row_without_ok_key_kept():
    rows = [
        {"line": "L1", "lang": "en", "text": "hello world"},
    ]
    result = caption_fields.manifest_lines(rows)
    assert len(result) == 1
    assert result[0]["id"] == "L1"


def test_override_for_skipped_row_is_unknown():
    rows = [
        {"line": "L1", "lang": "en", "text": "hello world", "ok": True},
        {"line": "L2", "lang": "en", "text": "bad line", "ok": False},
    ]
    overrides = {
        ("L2", "en"): {"caption_text": "x", "caption_diff_approved": True}
    }
    with pytest.raises(caption_fields.CaptionError, match="unknown line"):
        caption_fields.manifest_lines(rows, overrides)
