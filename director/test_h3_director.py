import json

import pytest

from h3_director import compile_direction, frames_for, main, settings_for
from test_shot_schema import RICH

FL = {"id": "SHOT-04", "mode": "fl2va", "seconds": 5, "start": "a.png", "end": "b.png", "style": "Flat 2D cel anime.",
      "world": "Riverbank at dawn.", "action": "0-2s he steps forward; 2-5s he looks up.", "camera": "slow crane down"}


def test_frames_follow_the_h3_grid():
    assert frames_for(4) == 107 and frames_for(5) == 124 and frames_for(15) == 362
    assert frames_for(4.5) == 107 and frames_for(5.2) == 124 and frames_for(5.9) == 141 and frames_for(6.6) == 158
    assert frames_for(15.1) == 362
    with pytest.raises(ValueError):
        frames_for(16)


def test_fl2va_shot_matches_the_proven_preset():
    s = settings_for(FL)
    assert s["model_type"] == "minimax_h3_fl2va_pruned" and s["num_inference_steps"] == 6 and s["sample_solver"] == "pika_renoise"
    assert s["image_prompt_type"] == "SE" and s["image_start"] == "a.png" and s["image_end"] == "b.png"
    assert s["resolution"] == "480x832" and s["video_length"] == 124
    assert "integrated_multimodal_description: [Shot 1] A 5.17-second" in s["prompt"]


def test_resolution_is_per_shot_and_checked():
    assert settings_for(dict(FL, resolution="768x1344"))["resolution"] == "768x1344"
    assert settings_for(dict(FL, aspect="16:9", resolution="960x544"))["resolution"] == "960x544"
    for bad in ("1344x768", "500x900"):   # wrong orientation, unknown size
        with pytest.raises(ValueError, match="resolution"):
            settings_for(dict(FL, resolution=bad))


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
        settings_for(dict(FL, start=None, end=None))


def test_rich_shot_compiles_beats_camera_and_light_into_the_prompt():
    s = settings_for(RICH)
    p = s["prompt"]
    assert "integrated_multimodal_description: [Shot 1] A 5.17-second single take. Modern Japanese anime" in p
    for code in ("0-0.8s: ", "0.8-1.6s: ", "1.6-3.4s: ", "3.4-5.2s: "):
        assert code in p
    assert p.index("0-0.8s") < p.index("0.8-1.6s") < p.index("3.4-5.2s")
    assert "0.8-1.6s: lowers centre of gravity, knees bend, shoulders tilt forward; sash still settling" in p
    assert "Camera: track down with the fall, 24mm lens, full body->water surface framing." in p
    assert "Light: low morning sun from screen left; warm gold on Krishna; earthy Braj daylight." in p
    assert "no style change; no on-screen text.\noverall_soundscape: branch creak" in p


def test_rich_shot_keyframes_map_to_the_start_and_end_frames():
    s = settings_for(RICH)
    assert s["image_start"] == "keyframes/SHOT-07-FRAME-A.png" and s["image_end"] == "keyframes/SHOT-07-FRAME-B.png"
    assert s["image_prompt_type"] == "SE" and s["video_length"] == 124 and s["resolution"] == "480x832"


def test_compile_direction_keeps_the_rich_spec(tmp_path):
    assert compile_direction(RICH) == RICH
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([RICH]), encoding="utf-8")
    main(str(shots), str(tmp_path / "out"), "kaliya_mardan")
    out = tmp_path / "out"
    assert json.loads((out / "settings_SHOT-07.json").read_text(encoding="utf-8"))["video_length"] == 124
    assert json.loads((out / "SHOT-07.direction.json").read_text(encoding="utf-8")) == RICH
