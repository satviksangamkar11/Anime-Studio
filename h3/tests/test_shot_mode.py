"""Tests for h3/shot_mode.py."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import shot_mode  # noqa: E402
from director import shot_router  # noqa: E402


def test_default_mode_is_SE():
    shot = {"id": "s1", "start": "a.png", "end": "b.png", "pixel_frames": 158, "end_frame_position": 151}
    row = shot_mode.frame_row(shot)
    assert row["image_prompt_type"] == "SE"
    assert row["end"] == "b.png"


def test_S_refused_without_env_flag():   # M-32: refused only when switched off with SHOT_MODE_S_ALLOW=0
    shot = {"id": "s1", "image_prompt_type": "S", "start": "a.png", "pixel_frames": 158}
    try:
        shot_mode.frame_row(shot, env={"SHOT_MODE_S_ALLOW": "0"})
    except shot_mode.ShotModeError as exc:
        assert "SHOT_MODE_S_ALLOW=0" in str(exc)
    else:
        raise AssertionError("expected ShotModeError")


def test_S_accepted_with_env_flag():
    shot = {"id": "s1", "image_prompt_type": "S", "start": "a.png", "pixel_frames": 158}
    row = shot_mode.frame_row(shot, env={"SHOT_MODE_S_ALLOW": "1"})
    assert row["image_prompt_type"] == "S"


def test_S_refused_with_env_flag_zero():
    shot = {"id": "s1", "image_prompt_type": "S", "start": "a.png", "pixel_frames": 158}
    try:
        shot_mode.frame_row(shot, env={"SHOT_MODE_S_ALLOW": "0"})
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError")


def test_unknown_mode_refused():
    shot = {"id": "s1", "image_prompt_type": "E", "start": "a.png", "pixel_frames": 158}
    try:
        shot_mode.frame_row(shot)
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError")


def test_valid_pixel_frames():
    for value in (158, 175, 209, 243):
        assert shot_mode.check_pixel_frames(value) == value


def test_valid_pixel_frames_spec_examples_192_226():
    for value in (192, 226):
        assert shot_mode.check_pixel_frames(value) == value


# changed 2026-11-11 (owner-approved): message wording for the real lattice 107..345
def test_pixel_frames_message_never_lists_5_as_valid():
    try:
        shot_mode.check_pixel_frames(10)
    except shot_mode.ShotModeError as exc:
        assert "nearest valid count is 107" in str(exc)
        assert "is 5" not in str(exc)
        assert "and 5" not in str(exc)
    else:
        raise AssertionError("expected ShotModeError")


def test_frame_row_missing_start_refused():
    try:
        shot_mode.frame_row({"id": "s1", "pixel_frames": 175})
    except shot_mode.ShotModeError as exc:
        assert "s1" in str(exc)
    else:
        raise AssertionError("expected ShotModeError for missing start")


def test_rows_missing_start_refused():
    try:
        shot_mode.rows([{"id": "s1", "pixel_frames": 175}])
    except shot_mode.ShotModeError as exc:
        assert "s1" in str(exc)
    else:
        raise AssertionError("expected ShotModeError for missing start")


def test_frame_row_missing_id_refused():
    try:
        shot_mode.frame_row({"start": "a.png", "pixel_frames": 175})
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError for missing id")


def test_rows_missing_id_refused():
    try:
        shot_mode.rows([{"start": "a.png", "pixel_frames": 175}])
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError for missing id")


def test_invalid_pixel_frames():
    for value in (160, 100, 5):
        try:
            shot_mode.check_pixel_frames(value)
        except shot_mode.ShotModeError:
            pass
        else:
            raise AssertionError(f"expected ShotModeError for {value}")


# changed 2026-11-11 (owner-approved): message wording for the real lattice 107..345
def test_invalid_pixel_frames_message_names_neighbours():
    cases = (
        (160, "nearest valid counts are 158 and 175"),
        (100, "the nearest valid count is 107"),
    )
    for value, expected in cases:
        try:
            shot_mode.check_pixel_frames(value)
        except shot_mode.ShotModeError as exc:
            assert str(value) in str(exc)
            assert expected in str(exc)
        else:
            raise AssertionError(f"expected ShotModeError for {value}")


def test_bool_pixel_frames_refused():
    try:
        shot_mode.check_pixel_frames(True)
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError for bool")


def test_float_pixel_frames_refused():
    try:
        shot_mode.check_pixel_frames(158.0)
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError for float")


def test_S_result_has_no_end_key():
    shot = {
        "id": "s1",
        "image_prompt_type": "S",
        "start": "a.png",
        "end": "b.png",
        "pixel_frames": 158,
    }
    row = shot_mode.frame_row(shot, env={"SHOT_MODE_S_ALLOW": "1"})
    assert "end" not in row


def test_SE_without_end_refused():
    shot = {"id": "s1", "start": "a.png", "pixel_frames": 158}
    try:
        shot_mode.frame_row(shot)
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError")


def test_duplicate_ids_refused():
    shots = [
        {"id": "s1", "start": "a.png", "end": "b.png", "pixel_frames": 158, "end_frame_position": 151},
        {"id": "s1", "start": "c.png", "end": "d.png", "pixel_frames": 158, "end_frame_position": 151},
    ]
    try:
        shot_mode.rows(shots)
    except shot_mode.ShotModeError as exc:
        assert "s1" in str(exc)
    else:
        raise AssertionError("expected ShotModeError")


def test_bad_shot_names_id():
    shots = [
        {"id": "s1", "start": "a.png", "end": "b.png", "pixel_frames": 158, "end_frame_position": 151},
        {"id": "s2", "start": "c.png", "pixel_frames": 160},
    ]
    try:
        shot_mode.rows(shots)
    except shot_mode.ShotModeError as exc:
        assert "s2" in str(exc)
    else:
        raise AssertionError("expected ShotModeError")


def test_S_with_env_flag_omits_end():
    shot = {
        "id": "s1",
        "image_prompt_type": "S",
        "start": "a.png",
        "end": "b.png",
        "pixel_frames": 175,
    }
    row = shot_mode.frame_row(shot, env={"SHOT_MODE_S_ALLOW": "1"})
    assert row == {
        "id": "s1",
        "image_prompt_type": "S",
        "pixel_frames": 175,
        "start": "a.png",
    }


def test_22_is_refused():
    try:
        shot_mode.check_pixel_frames(22)
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError for 22 (n=1 is below LATTICE_N_MIN=6)")


def test_rows_wraps_error_with_shot_id_for_short_ids():
    for sid in ("s", "158"):
        shot = {"id": sid, "start": "a.png", "end": "b.png", "pixel_frames": 160}
        try:
            shot_mode.rows([shot])
        except shot_mode.ShotModeError as exc:
            assert f"shot {sid!r}" in str(exc)
        else:
            raise AssertionError(f"expected ShotModeError for id {sid!r}")


def test_frame_row_missing_pixel_frames_names_shot_not_keyerror():
    try:
        shot_mode.frame_row({"id": "s1", "start": "a.png"})
    except shot_mode.ShotModeError as exc:
        assert "s1" in str(exc)
    else:
        raise AssertionError("expected ShotModeError for missing pixel_frames")


def test_pf_22_refused():
    try:
        shot_mode.check_pixel_frames(22)
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError for 22")


def test_pf_107_and_345_ok():
    assert shot_mode.check_pixel_frames(107) == 107
    assert shot_mode.check_pixel_frames(345) == 345


def test_pf_362_refused():
    try:
        shot_mode.check_pixel_frames(362)
    except shot_mode.ShotModeError:
        pass
    else:
        raise AssertionError("expected ShotModeError for 362 (n=21 > LATTICE_N_MAX=20)")


def test_post_none_refused():
    shot = {"id": "p1", "image_prompt_type": None, "start": "a.png", "pixel_frames": 192, "route": "POST"}
    try:
        shot_mode.frame_row(shot)
    except shot_mode.ShotModeError as exc:
        assert str(exc) == "POST shots never reach the batch"
    else:
        raise AssertionError("expected ShotModeError for image_prompt_type None")


def test_soft_se_keeps_strength_and_end_position():
    shot = {
        "id": "s1",
        "route": "SOFT_SE",
        "image_prompt_type": "SE",
        "input_video_strength": 0.6,
        "start": "a.png",
        "end": "b.png",
        "pixel_frames": 192,
        "end_frame_position": 151,
    }
    row = shot_mode.frame_row(shot)
    assert row["input_video_strength"] == 0.6
    assert row["end_frame_position"] == 151


def test_kfi_without_mid_raises():
    shot = {
        "id": "k1",
        "route": "KFI",
        "image_prompt_type": "SE",
        "input_video_strength": 0.65,
        "start": "a.png",
        "end": "b.png",
        "pixel_frames": 192,
        "end_frame_position": 151,
        "mid_frame": 75,
    }
    try:
        shot_mode.frame_row(shot)
    except shot_mode.ShotModeError as exc:
        assert "mid" in str(exc)
    else:
        raise AssertionError("expected ShotModeError for KFI without mid")


def test_router_rows_accepted():
    for name in shot_router.ROUTES:
        entry = shot_router._ROUTE_TABLE[name]
        if entry["image_prompt_type"] == "S":
            continue  # S routes need SHOT_MODE_S_ALLOW; route_shot(allow_s=False) never returns them
        shot = {
            "id": name,
            "route": name,
            "image_prompt_type": entry["image_prompt_type"],
            "input_video_strength": entry["input_video_strength"],
            "start": "a.png",
            "end": "b.png",
            "pixel_frames": 192,
            "end_frame_position": 151,
        }
        if name == "KFI":
            shot["mid"] = "m.png"
            shot["mid_frame"] = 75
        if name == "POST":
            try:
                shot_mode.frame_row(shot)
            except shot_mode.ShotModeError:
                continue
            raise AssertionError("expected POST to be refused")
        row = shot_mode.frame_row(shot)
        assert row["route"] == name
        assert row["input_video_strength"] == entry["input_video_strength"]


if __name__ == "__main__":
    test_default_mode_is_SE()
    test_S_refused_without_env_flag()
    test_S_accepted_with_env_flag()
    test_S_refused_with_env_flag_zero()
    test_unknown_mode_refused()
    test_valid_pixel_frames()
    test_invalid_pixel_frames()
    test_bool_pixel_frames_refused()
    test_float_pixel_frames_refused()
    test_S_result_has_no_end_key()
    test_SE_without_end_refused()
    test_duplicate_ids_refused()
    test_bad_shot_names_id()
    test_S_with_env_flag_omits_end()
    test_22_is_refused()
    print("all tests passed")
