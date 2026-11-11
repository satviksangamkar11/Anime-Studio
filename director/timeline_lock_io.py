"""Read, write and verify the single timeline contract file."""

from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

LOCK_VERSION = 2
PIXEL_MIN = 107
PIXEL_MAX = 345
_LOCK_NAME = re.compile(r"timeline_lock_v([0-9]+)\.json")
_DIFF_FIELDS = ("edit_frames", "start_frame", "bpm", "snap", "cue")
RETIME_LIMIT = 0.06
RETIME_MIN = 1.0 - RETIME_LIMIT
RETIME_MAX = 1.0 + RETIME_LIMIT


class StaleLockError(ValueError):
    """Raised when a timeline lock no longer matches its inputs."""


def _normalise(path: str | os.PathLike[str]) -> str:
    """Return the absolute, case-folded, forward-slash path string (one file, one key)."""
    return os.path.normcase(os.path.abspath(str(path))).replace("\\", "/")


def input_sha256(paths: list) -> str:
    """Return a sha256 digest over the given input files.

    For each path, sorted by its normalised string, the digest covers the
    pair (name bytes, file bytes).  A missing file raises FileNotFoundError
    naming it.
    """
    normalised = [_normalise(p) for p in paths]
    ordered = sorted(normalised)

    digest = hashlib.sha256()
    for path_str in ordered:
        path_obj = Path(path_str)
        if not path_obj.is_file():
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path_str)
        name_bytes = path_obj.name.encode("utf-8")
        file_bytes = path_obj.read_bytes()
        digest.update(len(name_bytes).to_bytes(8, "big"))
        digest.update(name_bytes)
        digest.update(len(file_bytes).to_bytes(8, "big"))
        digest.update(file_bytes)
    return digest.hexdigest()


def _shot_label(shot, index: int) -> str:
    if isinstance(shot, dict) and "id" in shot:
        return f"shot {shot['id']!r}"
    return f"shot #{index}"


def _is_int(value) -> bool:
    return type(value) is int


def _lock_hash(input_hash: str, params: dict) -> str:
    """sha256 over the input digest and the canonical JSON of params: a change to either makes a lock stale."""
    canonical = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((input_hash + canonical).encode("utf-8")).hexdigest()


def _check_shots(shots, fps: int) -> int:
    """Validate the shot rows of a lock (shared by write_lock and load_lock). Return the total frames."""
    if not isinstance(shots, list) or len(shots) == 0:
        raise ValueError("timeline lock must contain non-empty shots")

    seen_ids = set()
    cursor = 0
    total = 0
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise ValueError(f"shot entry at index {index} must be a dict: {shot!r}")
        shot_id = shot.get("id")
        if not isinstance(shot_id, str):
            raise ValueError(f"shot #{index} has invalid id: {shot_id!r}")
        if shot_id in seen_ids:
            raise ValueError(f"duplicate shot id: {shot_id!r}")
        seen_ids.add(shot_id)
        label = _shot_label(shot, index)

        edit_frames = shot.get("edit_frames")
        if not _is_int(edit_frames) or edit_frames < 1:
            raise ValueError(f"{label} has invalid edit_frames: {edit_frames!r}")

        start = shot.get("start_frame")
        if not _is_int(start) or start != cursor:
            raise ValueError(f"{label} start_frame must be {cursor}, got {start!r}")

        pixel = shot.get("pixel_frames")
        if not _is_int(pixel) or not PIXEL_MIN <= pixel <= PIXEL_MAX or (pixel - 5) % 17 != 0:
            raise ValueError(f"{label} has invalid pixel_frames: {pixel!r}")

        trim_in = shot.get("trim_in_frame")
        trim_out = shot.get("trim_out_frame")
        if not (_is_int(trim_in) and _is_int(trim_out)) or not 0 <= trim_in < trim_out <= pixel:
            raise ValueError(f"{label} has invalid trims {trim_in!r}..{trim_out!r} in {pixel} pixel frames")
        if trim_out - trim_in != edit_frames:
            raise ValueError(f"{label} trim span {trim_out - trim_in} does not equal edit_frames {edit_frames}")

        end = shot.get("end_frame_position")
        if not _is_int(end) or end != trim_out - 1:
            raise ValueError(f"{label} end_frame_position must be trim_out_frame - 1 = {trim_out - 1}")

        error_ms = shot.get("error_ms")
        if (
            isinstance(error_ms, bool)
            or not isinstance(error_ms, (int, float))
            or not math.isfinite(error_ms)
            or error_ms < 0
            or error_ms > 1000.0 / (2 * fps) + 1e-9
        ):
            raise ValueError(f"{label} has invalid error_ms: {error_ms!r}")

        retime = shot.get("retime")
        if retime is not None:
            if not isinstance(retime, dict):
                raise ValueError(f"{label} has invalid retime: {retime!r}")
            for lang, value in retime.items():
                if not isinstance(lang, str) or lang == "":
                    raise ValueError(f"{label} has invalid retime: {retime!r}")
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < RETIME_MIN - 1e-9
                    or value > RETIME_MAX + 1e-9
                ):
                    raise ValueError(f"{label} has invalid retime: {retime!r}")

        cursor += edit_frames
        total += edit_frames
    return total


def write_lock(path, shots: list, inputs: list, params: dict, fps: int = 24) -> dict:
    """Write a version 2 timeline lock JSON file atomically and return the dict written.

    Never overwrites: raises FileExistsError when the target exists.
    """
    if type(fps) is not int or fps <= 0:
        raise ValueError("fps must be a positive integer")
    if not isinstance(inputs, list) or len(inputs) == 0:
        raise ValueError("timeline lock needs at least one input")
    if not isinstance(params, dict):
        raise ValueError("params must be a dict")

    total_frames = _check_shots(shots, fps)
    input_hash = input_sha256(inputs)

    target = Path(path)
    if target.exists():
        raise FileExistsError(errno.EEXIST, "timeline lock already exists, refusing to overwrite", str(target))

    lock = {
        "version": LOCK_VERSION,
        "fps": fps,
        "input_sha256": input_hash,
        "params": params,
        "lock_sha256": _lock_hash(input_hash, params),
        "inputs": [_normalise(p) for p in inputs],
        "total_frames": total_frames,
        "total_seconds": round(total_frames / fps, 6),
        "shots": shots,
    }

    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(lock, handle, ensure_ascii=False, indent=1)
            handle.write("\n")
        try:
            os.link(tmp_name, target)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        os.unlink(tmp_name)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return lock


def load_lock(path) -> dict:
    """Load and validate a timeline lock file."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"missing timeline lock: {target}")

    try:
        with target.open("r", encoding="utf-8") as handle:
            lock = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"corrupt timeline lock: {target}") from exc

    if not isinstance(lock, dict):
        raise ValueError("timeline lock must be a JSON object")

    version = lock.get("version")
    if type(version) is not int or version != LOCK_VERSION:
        raise ValueError("unsupported timeline lock version")

    fps = lock.get("fps")
    if type(fps) is not int or fps <= 0:
        raise ValueError("invalid fps in timeline lock")

    inputs = lock.get("inputs")
    if not isinstance(inputs, list) or not inputs or not all(isinstance(item, str) for item in inputs):
        raise ValueError("invalid inputs in timeline lock")

    total_frames = _check_shots(lock.get("shots"), fps)

    recorded_total = lock.get("total_frames")
    if type(recorded_total) is not int or recorded_total != total_frames:
        raise ValueError("total_frames does not match sum of shot edit_frames")

    recorded_seconds = lock.get("total_seconds")
    if (isinstance(recorded_seconds, bool) or not isinstance(recorded_seconds, (int, float))
            or recorded_seconds != round(total_frames / fps, 6)):
        raise ValueError("total_seconds does not match total_frames / fps")

    return lock


def verify_lock(path, inputs: list, params: dict) -> dict:
    """Load a lock and confirm it still matches the given inputs and params (StaleLockError otherwise)."""
    if not isinstance(params, dict):
        raise ValueError("params must be a dict")
    lock = load_lock(path)

    try:
        current_hash = input_sha256(inputs)
    except FileNotFoundError as exc:
        raise StaleLockError(f"stale timeline lock: missing input {exc.filename}") from exc

    if current_hash != lock.get("input_sha256"):
        raise StaleLockError("stale timeline lock: input hash mismatch")

    normalised_inputs = {_normalise(p) for p in inputs}
    recorded_inputs = set(lock.get("inputs", []))
    if normalised_inputs != recorded_inputs:
        raise StaleLockError("stale timeline lock: input path set mismatch")

    if _lock_hash(current_hash, params) != lock.get("lock_sha256"):
        raise StaleLockError("stale timeline lock: params or lock hash mismatch")

    return lock


def frames_for(lock: dict, shot_id: str) -> int:
    """Return edit_frames for the shot with the given id."""
    shots = lock.get("shots", [])
    for shot in shots:
        if shot.get("id") == shot_id:
            edit_frames = shot.get("edit_frames")
            if type(edit_frames) is not int:
                raise ValueError(f"shot {shot_id!r} has invalid edit_frames")
            return edit_frames
    raise KeyError(f"shot id not found: {shot_id!r}")


def _versions(folder) -> list:
    """Sorted (N, path) pairs for every timeline_lock_vN.json in folder."""
    base = Path(folder)
    if not base.is_dir():
        return []
    found = []
    for item in base.iterdir():
        match = _LOCK_NAME.fullmatch(item.name)
        if match and item.is_file():
            found.append((int(match.group(1)), item))
    return sorted(found, key=lambda pair: pair[0])


def next_lock_path(folder) -> Path:
    """Return folder/timeline_lock_v{N+1}.json, N being the highest existing version (0 if none)."""
    found = _versions(folder)
    highest = found[-1][0] if found else 0
    return Path(folder) / f"timeline_lock_v{highest + 1}.json"


def latest_lock_path(folder) -> Path:
    """Return the highest-numbered timeline lock in folder, or raise FileNotFoundError."""
    found = _versions(folder)
    if not found:
        raise FileNotFoundError(f"no timeline lock in {folder}")
    return found[-1][1]


def diff_locks(old: dict, new: dict) -> list:
    """Field changes between two lock dicts, plus added and removed shot ids."""
    old_by_id = {shot["id"]: shot for shot in old["shots"]}
    new_by_id = {shot["id"]: shot for shot in new["shots"]}
    changes = []
    for shot_id, before in old_by_id.items():
        if shot_id not in new_by_id:
            changes.append({"id": shot_id, "field": "removed", "old": None, "new": None})
            continue
        after = new_by_id[shot_id]
        for field in _DIFF_FIELDS:
            if before.get(field) != after.get(field):
                changes.append({"id": shot_id, "field": field, "old": before.get(field), "new": after.get(field)})
    for shot_id in new_by_id:
        if shot_id not in old_by_id:
            changes.append({"id": shot_id, "field": "added", "old": None, "new": None})
    return changes


def lock_rows(lock: dict) -> list[dict]:
    """{id, start_frame, edit_frames, offset_sec, editorial_duration_sec, trim_in_frame, trim_out_frame} per shot in lock order.

    start_frame is recomputed as a running integer clock; a recorded value that
    differs raises ValueError.  Missing trim keys raise KeyError naming the shot.
    """
    fps = lock.get("fps")
    if type(fps) is not int or fps <= 0:
        raise ValueError("invalid fps in timeline lock")

    shots = lock.get("shots")
    if not isinstance(shots, list):
        raise ValueError("timeline lock must contain shots")

    rows: list[dict] = []
    cursor = 0
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError(f"shot entry must be a dict: {shot!r}")
        shot_id = shot.get("id")
        if not isinstance(shot_id, str):
            raise ValueError(f"shot entry has invalid id: {shot_id!r}")

        edit_frames = shot.get("edit_frames")
        if type(edit_frames) is not int or edit_frames < 1:
            raise ValueError(f"shot {shot_id!r} has invalid edit_frames: {edit_frames!r}")

        recorded_start = shot.get("start_frame")
        if type(recorded_start) is not int or recorded_start != cursor:
            raise ValueError(
                f"shot {shot_id!r} start_frame must be {cursor}, got {recorded_start!r}"
            )

        if "trim_in_frame" not in shot or "trim_out_frame" not in shot:
            raise KeyError(f"shot {shot_id!r} missing trim_in_frame or trim_out_frame")

        rows.append(
            {
                "id": shot_id,
                "start_frame": cursor,
                "edit_frames": edit_frames,
                "offset_sec": cursor / fps,
                "editorial_duration_sec": edit_frames / fps,
                "trim_in_frame": shot["trim_in_frame"],
                "trim_out_frame": shot["trim_out_frame"],
            }
        )
        cursor += edit_frames
    return rows


def retime_for(lock, shot_id, lang):
    """Return the picture retime factor for a shot and language, or 1.0 when unset."""
    shots = lock.get("shots", [])
    for shot in shots:
        if shot.get("id") == shot_id:
            retime = shot.get("retime")
            if retime is None:
                return 1.0
            if lang in retime:
                return float(retime[lang])
            return 1.0
    raise ValueError(f"unknown shot id: {shot_id!r}")


def suggest_retime(master_frames, lang_frames, limit=RETIME_LIMIT):
    """Return the duration multiplier clamped to [1 - limit, 1 + limit], rounded to 6 decimals."""
    if type(master_frames) is not int or master_frames <= 0:
        raise ValueError("master_frames must be a positive integer")
    if type(lang_frames) is not int or lang_frames <= 0:
        raise ValueError("lang_frames must be a positive integer")
    if type(limit) is not float or not 0.0 <= limit <= 0.5:
        raise ValueError("limit must be a float between 0 and 0.5")
    factor = lang_frames / master_frames
    low = 1.0 - limit
    high = 1.0 + limit
    if factor < low:
        factor = low
    elif factor > high:
        factor = high
    return round(factor, 6)
