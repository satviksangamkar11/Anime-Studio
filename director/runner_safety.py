import hashlib
import math
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

MIN_CLIP_BYTES = 50_000
PART_SUFFIXES = (".part.mp4", ".tmp.mp4")


def _valid_shot_id(shot_id):
    if not isinstance(shot_id, str):
        return False
    if shot_id == "":
        return False
    if shot_id == "." or shot_id == "..":
        return False
    if "/" in shot_id:
        return False
    if "\\" in shot_id:
        return False
    if ":" in shot_id:
        return False
    if shot_id.endswith(".") or shot_id.endswith(" "):
        return False
    for ch in shot_id:
        code = ord(ch)
        if code < 32 or 127 <= code <= 159:
            return False
    return True


def _ffprobe_frames(path):
    # same call as build_final_reel.probe_frames (lines 35-38)
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    return int(r.stdout.strip())


def clip_verified(results_dir, shot_id, expected_frames, probe_frames=None, exists=None, size=None):
    if not _valid_shot_id(shot_id):
        return False
    if probe_frames is None:
        probe_frames = _ffprobe_frames
    clip_dir = Path(results_dir) / shot_id
    if clip_dir.resolve() != (Path(results_dir).resolve() / shot_id):
        return False
    injected = exists is not None and size is not None
    if injected:
        candidate = clip_dir / (shot_id + ".mp4")
        try:
            return (exists(candidate) and size(candidate) > MIN_CLIP_BYTES
                    and probe_frames(candidate) == expected_frames)
        except (OSError, ValueError, subprocess.CalledProcessError):
            return False
    size = os.path.getsize
    if not clip_dir.is_dir():
        return False
    for entry in clip_dir.glob("*.mp4"):
        if entry.name.lower().endswith(PART_SUFFIXES):
            continue
        if entry.is_file() and not entry.is_symlink():
            try:
                if size(entry) > MIN_CLIP_BYTES and probe_frames(entry) == expected_frames:
                    return True
            except (OSError, ValueError, subprocess.CalledProcessError):
                continue
    return False


def can_stop(expected_ids, results_dir, *, expected_frames, **kw):
    if not isinstance(expected_ids, (list, tuple)):
        raise ValueError("expected_ids must be a list or tuple of str")
    if len(expected_ids) == 0:
        raise ValueError("expected_ids must not be empty")
    for shot_id in expected_ids:
        if not isinstance(shot_id, str):
            raise ValueError("expected_ids must be a list or tuple of str")
    missing = []
    for shot_id in expected_ids:
        if shot_id not in expected_frames:
            raise ValueError("no expected frame count for " + shot_id)
        if not clip_verified(results_dir, shot_id, expected_frames[shot_id], **kw):
            missing.append(shot_id)
    return (len(missing) == 0, missing)


def stop_decision(expected_ids, results_dir, all_done, *, expected_frames, **kw):
    for shot_id in expected_ids:
        if shot_id not in expected_frames:
            raise ValueError("no expected frame count for " + str(shot_id))
    if all_done is not True:
        return {"stop": False, "reason": "not finished", "missing": []}
    ok, missing = can_stop(expected_ids, results_dir, expected_frames=expected_frames, **kw)
    if ok:
        return {"stop": True, "reason": "all clips verified", "missing": []}
    missing_names = ", ".join(str(m) for m in missing)
    reason = "missing clips " + missing_names + "; session kept for manual fetch"
    return {"stop": False, "reason": reason, "missing": missing}


def deadman_seconds(clip_seconds_estimate, n_clips, setup_seconds=900, factor=1.5):
    if isinstance(n_clips, bool) or not isinstance(n_clips, int):
        raise ValueError("n_clips must be an int")
    if n_clips <= 0:
        raise ValueError("n_clips must be positive")
    for name, value in (("clip_seconds_estimate", clip_seconds_estimate),
                        ("setup_seconds", setup_seconds),
                        ("factor", factor)):
        if not math.isfinite(value):
            raise ValueError(name + " must be finite")
        if value <= 0:
            raise ValueError(name + " must be positive")
    total = setup_seconds + clip_seconds_estimate * n_clips
    return int(math.ceil(total * factor))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def wheel_ok(path, expected_sha256):
    p = Path(path)
    if not p.is_file():
        return False
    actual = sha256_file(p)
    return actual.lower() == expected_sha256.lower()


def _default_head(url, timeout=10):
    # E8: a server that refuses HEAD (405/501) is checked with GET, Range bytes=0-0
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        if exc.code not in (405, 501):
            raise
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def preflight(urls, disk_path, *, min_free_gb, script_path, part_paths=(), max_part_mb=3.0,
              key_checks=None, head=None, disk_usage=None):
    # Owner decision 6 (2026-11-11): no fixed script size cap; the script goes up in parts of <= max_part_mb.
    if not urls:
        raise ValueError("urls must not be empty")
    failures = []
    if head is None:
        head = _default_head
    if disk_usage is None:
        disk_usage = shutil.disk_usage
    if key_checks is None:
        key_checks = {}

    for url in urls:
        try:
            status = head(url)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code is not None:
                failures.append("url check failed for " + str(url) + ": HTTP " + str(code))
            else:
                failures.append("url check failed for " + str(url) + ": " + type(exc).__name__)
            continue
        if not isinstance(status, int):
            failures.append(str(url) + ": invalid status " + str(status))
            continue
        if not (200 <= status <= 399):
            failures.append("url check failed for " + str(url) + ": HTTP " + str(status))

    try:
        usage = disk_usage(disk_path)
    except Exception as exc:
        failures.append("disk check failed for " + str(disk_path) + ": " + type(exc).__name__)
    else:
        free_gb = usage.free / (1024 ** 3)
        if free_gb < min_free_gb:
            failures.append("disk free " + str(round(free_gb, 2)) + " GB below minimum " + str(min_free_gb) + " GB")

    for name, check in key_checks.items():
        try:
            result = check()
        except Exception:
            failures.append("key check failed: " + str(name))
            continue
        if not result:
            failures.append("key check failed: " + str(name))

    try:
        os.path.getsize(script_path)
    except OSError:
        failures.append("script check failed: cannot stat " + str(script_path))
    else:
        if not os.path.isfile(script_path):
            failures.append("script check failed: not a file: " + str(script_path))

    max_bytes = max_part_mb * 1024 * 1024
    for part in part_paths:
        try:
            part_size = os.path.getsize(part)
        except OSError:
            failures.append("part check failed: cannot stat " + str(part))
            continue
        if part_size > max_bytes:
            failures.append("part too large: " + str(part) + " "
                            + str(round(part_size / (1024 * 1024), 2))
                            + " MB > " + str(max_part_mb) + " MB")

    return failures
