import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

import pytest

import shot_mode
from shot_mode import ShotModeError

KFI_SHOT = {
    "id": "k1",
    "route": "KFI",
    "image_prompt_type": "SE",
    "input_video_strength": 0.65,
    "start": "a.png",
    "end": "b.png",
    "pixel_frames": 192,
    "end_frame_position": 151,
    "mid": "M.png",
    "mid_frame": 75,
}

SE_SHOT = {
    "id": "s1",
    "route": "SE",
    "image_prompt_type": "SE",
    "start": "a.png",
    "end": "b.png",
    "pixel_frames": 192,
    "end_frame_position": 151,
}


def test_kfi_row_carries_mid_and_mid_frame():
    row = shot_mode.frame_row(KFI_SHOT)
    assert row["mid"] == "M.png"
    assert row["mid_frame"] == 75


def test_non_kfi_row_has_no_mid_keys():
    row = shot_mode.frame_row(SE_SHOT)
    assert "mid" not in row
    assert "mid_frame" not in row


def test_message_below_minimum_names_107_only():
    with pytest.raises(ShotModeError) as exc:
        shot_mode.check_pixel_frames(10)
    assert str(exc.value) == "pixel_frames 10 is invalid; the nearest valid count is 107"


def test_message_above_maximum_names_345_only():
    with pytest.raises(ShotModeError) as exc:
        shot_mode.check_pixel_frames(400)
    assert str(exc.value) == "pixel_frames 400 is invalid; the nearest valid count is 345"


def test_message_between_names_both():
    with pytest.raises(ShotModeError) as exc:
        shot_mode.check_pixel_frames(110)
    assert str(exc.value) == "pixel_frames 110 is invalid; nearest valid counts are 107 and 124"
