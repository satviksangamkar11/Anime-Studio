"""Shot mode handling for the GranthStudio batch pipeline."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h3.shot_table_spec import LATTICE_N_MAX, LATTICE_N_MIN  # noqa: E402

VALID_MODES = ("SE", "S")


def s_allowed(env: dict | None = None) -> bool:
    """M-32: start-only S is on by default; SHOT_MODE_S_ALLOW=0 switches it off."""
    return (os.environ if env is None else env).get("SHOT_MODE_S_ALLOW") != "0"


class ShotModeError(ValueError):
    """Raised when a shot mode or frame count is invalid."""


def image_prompt_type(shot: dict, env: dict | None = None) -> str:
    """Return the image prompt mode for a shot, defaulting to "SE"."""
    mode = shot.get("image_prompt_type", "SE")
    if mode is None:
        raise ShotModeError("POST shots never reach the batch")
    if mode not in VALID_MODES:
        raise ShotModeError(f"unknown image_prompt_type {mode!r}; valid modes are {VALID_MODES}")
    if mode == "S":
        if not s_allowed(env):
            raise ShotModeError("start-only mode 'S' is switched off (SHOT_MODE_S_ALLOW=0)")
    return mode


def check_pixel_frames(pixel_frames: int) -> int:
    """Validate that pixel_frames is 5 + 17*n with LATTICE_N_MIN <= n <= LATTICE_N_MAX (107..345).

    For an invalid value the message names only real valid counts: the nearest valid count when the
    value is below 107 or above 345, otherwise the valid count below and the valid count above.
    """
    if isinstance(pixel_frames, bool) or not isinstance(pixel_frames, int):
        raise ShotModeError(
            f"pixel_frames must be an int, got {pixel_frames!r} ({type(pixel_frames).__name__})"
        )
    remainder = pixel_frames - 5
    if remainder % 17 != 0:
        valid = [5 + 17 * k for k in range(LATTICE_N_MIN, LATTICE_N_MAX + 1)]
        lower = [v for v in valid if v < pixel_frames]
        higher = [v for v in valid if v > pixel_frames]
        below = max(lower) if lower else None
        above = min(higher) if higher else None
        if below is None:
            detail = f"the nearest valid count is {above}"
        elif above is None:
            detail = f"the nearest valid count is {below}"
        else:
            detail = f"nearest valid counts are {below} and {above}"
        raise ShotModeError(f"pixel_frames {pixel_frames} is invalid; {detail}")
    n = remainder // 17
    if not LATTICE_N_MIN <= n <= LATTICE_N_MAX:
        raise ShotModeError(
            f"pixel_frames {pixel_frames} is outside the lattice; n must be "
            f"{LATTICE_N_MIN}..{LATTICE_N_MAX} ({5 + 17 * LATTICE_N_MIN}..{5 + 17 * LATTICE_N_MAX} frames)"
        )
    return pixel_frames


def _check_strength(value):
    """input_video_strength: None, or a float with 0 < x <= 1."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, float) or not 0 < value <= 1:
        raise ShotModeError(f"input_video_strength must be None or a float in (0, 1], got {value!r}")
    return value


def _check_end_frame_position(value, pixel_frames):
    """end_frame_position: an int with 0 < value < pixel_frames."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < pixel_frames:
        raise ShotModeError(f"end_frame_position must be an int in (0, {pixel_frames}), got {value!r}")
    return value


def frame_row(shot: dict, env=None) -> dict:
    """Build a frame row dict for a shot."""
    if "id" not in shot:
        raise ShotModeError("shot is missing required 'id'")
    shot_id = shot["id"]
    mode = image_prompt_type(shot, env)
    if "start" not in shot:
        raise ShotModeError(f"shot {shot_id!r} is missing required 'start'")
    start = shot["start"]
    if "pixel_frames" not in shot:
        raise ShotModeError(f"shot {shot_id!r} is missing required 'pixel_frames'")
    checked = check_pixel_frames(shot["pixel_frames"])
    row = {
        "id": shot_id,
        "image_prompt_type": mode,
        "pixel_frames": checked,
        "start": start,
    }
    if "route" in shot:
        row["route"] = shot["route"]
    if "input_video_strength" in shot:
        row["input_video_strength"] = _check_strength(shot["input_video_strength"])
    if mode == "SE":
        if "end" not in shot:
            raise ShotModeError(f"shot {shot_id!r} is missing required 'end' for mode 'SE'")
        row["end"] = shot["end"]
        if "end_frame_position" not in shot:
            raise ShotModeError(f"shot {shot_id!r} is missing required 'end_frame_position' for mode 'SE'")
    if "end_frame_position" in shot and mode == "SE":   # S has no end anchor: the key is dropped, not sent
        row["end_frame_position"] = _check_end_frame_position(shot["end_frame_position"], checked)
    if shot.get("route") == "KFI":
        if "mid" not in shot or shot["mid"] is None:
            raise ShotModeError(f"shot {shot_id!r} is route KFI and is missing required 'mid'")
        mid_frame = shot.get("mid_frame")
        efp = row.get("end_frame_position")
        if isinstance(mid_frame, bool) or not isinstance(mid_frame, int) or efp is None or not 0 < mid_frame < efp:
            raise ShotModeError(
                f"shot {shot_id!r} is route KFI and needs 'mid_frame' with 0 < mid_frame < end_frame_position"
            )
        row["mid"] = shot["mid"]
        row["mid_frame"] = mid_frame
    return row


def rows(shots: list, env=None) -> list:
    """Build frame rows for a list of shots, rejecting duplicate ids."""
    result = []
    seen = set()
    for shot in shots:
        if "id" not in shot:
            raise ShotModeError("shot is missing required 'id'")
        shot_id = shot["id"]
        if shot_id in seen:
            raise ShotModeError(f"duplicate shot id {shot_id!r}")
        seen.add(shot_id)
        try:
            result.append(frame_row(shot, env))
        except ShotModeError as exc:
            raise ShotModeError(f"shot {shot_id!r}: {exc}") from exc
    return result
