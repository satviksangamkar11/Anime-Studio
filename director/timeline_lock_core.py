"""Pure frame arithmetic for the one shared timeline."""

from __future__ import annotations

import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from h3.shot_table_spec import LATTICE_N_MAX, LATTICE_N_MIN  # noqa: E402

FPS = 24
PIKA_PRESETS = ("pika", "pika6")
PIKA_MIN_N = 7   # Pika H3 Flex preset: 124-362 frames (17*7+5 = 124), research/OPUS_FINAL_REVIEW_2026-11-12.md B-13


def lattice_frames(n: int) -> int:
    """Return 17*n + 5 frames for an H3 clip, n in LATTICE_N_MIN..LATTICE_N_MAX (6..20)."""
    if isinstance(n, bool) or not isinstance(n, int) or not LATTICE_N_MIN <= n <= LATTICE_N_MAX:
        raise ValueError(f"n must be an int in {LATTICE_N_MIN}..{LATTICE_N_MAX}, got {n!r}")
    return 17 * n + 5


def fit_lattice(min_frames: int) -> int:
    """Smallest 17*n+5 (n in 6..20) that is >= min_frames. Raises above 345 frames."""
    lo, hi = lattice_frames(LATTICE_N_MIN), lattice_frames(LATTICE_N_MAX)
    frames = max(lo, 17 * math.ceil((min_frames - 5) / 17) + 5)
    if frames > hi:
        raise ValueError(f"{min_frames} > {hi} frames: split the shot")
    return frames


def _frames_of(seconds, label, fps: int) -> int:
    """ceil(seconds*fps) with a 1e-9 tolerance, so float noise (n/24*24) never adds a frame."""
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        raise ValueError(f"invalid seconds for {label!r}: {seconds!r}")
    if seconds < 0:
        raise ValueError(f"negative seconds for {label!r}: {seconds!r}")
    product = seconds * fps
    if product > 10**7 or not math.isfinite(product):
        raise ValueError(f"seconds*fps out of range for {label!r}: {seconds!r}")
    return math.ceil(product - 1e-9)


def edit_frames_for_shot(
    seconds_by_lang: dict, margin_frames: int = 6, fps: int = FPS, min_seconds=None
) -> int:
    """max over languages of ceil(seconds*fps) + margin_frames, and at least ceil(min_seconds*fps).

    The margin applies to the voice only. An empty dict is allowed only with min_seconds (a silent shot).
    Raises ValueError for a margin that is not an int >= 0 (bool refused), an empty dict without
    min_seconds, negative or non-finite seconds, or when seconds*fps exceeds 10**7.
    """
    if isinstance(margin_frames, bool) or not isinstance(margin_frames, int) or margin_frames < 0:
        raise ValueError(f"margin_frames must be an int >= 0, got {margin_frames!r}")
    if not seconds_by_lang and min_seconds is None:
        raise ValueError("seconds_by_lang must not be empty")
    best = None
    for lang, seconds in seconds_by_lang.items():
        frames = _frames_of(seconds, lang, fps) + margin_frames
        if best is None or frames > best:
            best = frames
    if min_seconds is not None:
        floor = _frames_of(min_seconds, "min_seconds", fps)
        best = floor if best is None else max(best, floor)
    return best


def beat_candidate(
    need_frames: int,
    bpm: float,
    act_start_frame: int,
    start_in_act_frames: int = 0,
    fps: int = FPS,
) -> dict:
    """Smallest beat index k >= 1 whose rounded grid position minus the shot's
    own start offset is >= need_frames. Grid counted from act start.

    `act_start_frame` shifts the absolute cut only; the returned `frames`
    is measured from the shot's own start offset.
    """
    if need_frames <= 0:
        raise ValueError("need_frames must be > 0")
    if bpm < 20 or bpm > 400:
        raise ValueError("bpm must be finite and between 20 and 400")
    if not math.isfinite(bpm):
        raise ValueError("bpm must be finite and between 20 and 400")
    k = 1
    while k <= 100000:
        grid = k * 60.0 / bpm * fps
        cut = act_start_frame + round(grid)
        frames = cut - act_start_frame - start_in_act_frames
        error_ms = abs(round(grid) - grid) / fps * 1000.0
        if frames >= need_frames:
            return {
                "method": "beat",
                "frames": int(frames),
                "beats": k,
                "error_ms": float(error_ms),
            }
        k += 1
    raise ValueError("no beat grid fits")


def choose(
    need_frames: int,
    bpm: float | None,
    start_in_act_frames: int = 0,
    snap: bool = False,
    fps: int = FPS,
) -> dict:
    """Free cut (frames = need) unless the shot is snapped to its act's beat grid.

    A snapped shot uses beat_candidate only: the smallest whole-beat cut >= need_frames, counted from the
    act start offset start_in_act_frames. The bar path was removed: an off-grid start makes a bar cut up
    to half a beat off (breaks D16).
    """
    if need_frames <= 0:
        raise ValueError("need_frames must be > 0")
    if bpm is None or not snap:
        return {
            "method": "free",
            "frames": need_frames,
            "beats": None,
            "error_ms": 0.0,
            "spare": 0,
        }
    best = dict(beat_candidate(need_frames, bpm, 0, start_in_act_frames, fps=fps))
    best["spare"] = best["frames"] - need_frames
    return best


def plan_pixels(ids: list, edit_frames: list, fps: int = FPS, preset=None) -> list:
    """Lattice size and cut handles per shot, from the H3 rules in h3/v4_to_h3.py (the one lattice picker).

    preset "pika"/"pika6": a shot the picker fits below n = 7 is raised to 124 frames (the preset floor).
    Raises ValueError for a one-shot list (fit_lattice skips it), a shot that fits no lattice size, or a cut
    that breaks the handle rules.
    """
    import h3.v4_to_h3 as v  # lazy: the H3 module is heavy and only needed here

    if fps != FPS:
        raise ValueError(f"the H3 lattice is {FPS} fps, got {fps}")
    if len(ids) != len(edit_frames):
        raise ValueError("ids and edit_frames differ in length")
    if len(ids) < 2:
        raise ValueError("a reel needs at least 2 shots: fit_lattice skips a one-shot list")
    rows = [{"id": sid, "episode": 1, "editorial_duration_sec": ed / fps} for sid, ed in zip(ids, edit_frames)]
    fitted, _changes, problems = v.fit_lattice(rows)
    if problems:
        raise ValueError("; ".join(problems))
    last = len(fitted) - 1
    out = []
    for i, row in enumerate(fitted):
        ed, pf, n = edit_frames[i], row["pixel_frames"], row["lattice_n"]
        if preset in PIKA_PRESETS and n < PIKA_MIN_N:
            n, pf = PIKA_MIN_N, lattice_frames(PIKA_MIN_N)
        inc, outg = v._seam_defaults(i == 0, i == last, ed, pf)
        plan, probs = v._plan_handles(row["id"], pf, ed, inc, outg, n)
        if probs:
            raise ValueError("; ".join(probs))
        out.append({
            "lattice_n": n,
            "pixel_frames": pf,
            "trim_in_frame": plan["trim_in_frame"],
            "trim_out_frame": plan["trim_out_frame"],
            "head_handle": plan["head_handle_frames"],
            "tail_handle": plan["tail_handle_frames"],
            "incoming_seam": inc,
            "outgoing_seam": outg,
            "end_frame_position": plan["trim_out_frame"] - 1,
        })
    return out


def plan_shots(shots: list, voice_seconds: dict, margin_frames: int = 6, fps: int = FPS, preset=None) -> list:
    """Plan every shot in reel order. Shot keys: id, bpm (optional), snap (default False), cue, min_seconds.

    The act restarts when (bpm, cue) differs from the previous shot. A shot with no entry in voice_seconds
    needs min_seconds, else ValueError. Inputs are never mutated.
    """
    rows = []
    absolute_start = 0
    act_start_frame = 0
    start_in_act = 0
    prev_key = None

    for shot in shots:
        sid = shot["id"]
        bpm = shot.get("bpm")
        snap = shot.get("snap", False)
        cue = shot.get("cue")
        min_seconds = shot.get("min_seconds")
        if sid not in voice_seconds and min_seconds is None:
            raise ValueError(f"{sid}: no voice seconds and no min_seconds")

        key = (bpm, cue)
        if key != prev_key:
            act_start_frame, start_in_act, prev_key = absolute_start, 0, key

        need = edit_frames_for_shot(voice_seconds.get(sid, {}), margin_frames, fps, min_seconds)
        chosen = choose(need, bpm, start_in_act, snap, fps)
        edit_frames = chosen["frames"]
        rows.append({
            "id": sid,
            "start_frame": absolute_start,
            "edit_frames": edit_frames,
            "method": chosen["method"],
            "beats": chosen["beats"],
            "error_ms": chosen["error_ms"],
            "spare": chosen["spare"],
            "bpm": bpm,
            "snap": snap,
            "cue": cue,
            "act_start_frame": act_start_frame,
        })
        absolute_start += edit_frames
        start_in_act += edit_frames

    pixels = plan_pixels([r["id"] for r in rows], [r["edit_frames"] for r in rows], fps, preset)
    for row, pix in zip(rows, pixels):
        row.update(pix)
    return rows
