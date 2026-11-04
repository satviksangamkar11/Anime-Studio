import pytest

from h3_director import frames_for, settings_for

FL = {"id": "SHOT-04", "mode": "fl2va", "seconds": 5, "start": "a.png", "end": "b.png", "style": "Flat 2D cel anime.",
      "world": "Riverbank at dawn.", "action": "0-2s he steps forward; 2-5s he looks up.", "camera": "slow crane down"}


def test_frames_follow_the_h3_grid():
    assert frames_for(4) == 107 and frames_for(5) == 124 and frames_for(5.2) == 141 and frames_for(15) == 362
    with pytest.raises(ValueError):
        frames_for(16)


def test_fl2va_shot_matches_the_proven_preset():
    s = settings_for(FL)
    assert s["model_type"] == "minimax_h3_fl2va_pruned" and s["num_inference_steps"] == 6 and s["sample_solver"] == "pika_renoise"
    assert s["image_prompt_type"] == "SE" and s["image_start"] == "a.png" and s["image_end"] == "b.png"
    assert s["resolution"] == "480x832" and s["video_length"] == 124
    assert s["prompt"].startswith("integrated_multimodal_description: [Shot 1] A 5.2-second")


def test_ref2va_needs_refs_and_names_subjects():
    shot = dict(FL, mode="ref2va", end=None, refs=["krishna_sheet.png"], subjects=["<Subject 1> is Bala Krishna in <Picture 1>."])
    s = settings_for(shot)
    assert s["image_refs"] == ["krishna_sheet.png"] and s["video_prompt_type"] == "I" and "image_end" not in s
    assert "subject_definitions:\n<Subject 1> is Bala Krishna" in s["prompt"]
    with pytest.raises(ValueError):
        settings_for(dict(shot, refs=[]))
    with pytest.raises(ValueError):
        settings_for(dict(shot, subjects=[]))


def test_fl2va_needs_a_start_frame():
    with pytest.raises(ValueError):
        settings_for(dict(FL, start=None))
