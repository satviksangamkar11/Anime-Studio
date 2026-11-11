import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import timeline_lock_core


def test_plan_pixels_length_mismatch_raises():
    ids = ["a", "b", "c"]
    edit_frames = [144, 144]
    with pytest.raises(ValueError, match="differ in length"):
        timeline_lock_core.plan_pixels(ids, edit_frames)


def test_plan_pixels_equal_lengths_still_work(tmp_path, monkeypatch):
    ids = ["a", "b", "c"]
    edit_frames = [144, 144, 144]
    result = timeline_lock_core.plan_pixels(ids, edit_frames)
    assert len(result) == 3
