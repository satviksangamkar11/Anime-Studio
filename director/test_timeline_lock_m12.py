"""Tests for card M-12 (plan T-04 snap default false, T-05 short edits with trim records).

Hand-computed values:
  5.0 s voice at 24 fps = 120 frames (margin 0). 128 BPM = 11.25 frames per beat:
  beat 11 = 123.75 -> 124 frames (spare 4). Free cut = 120 frames.
  A 2.5 s edit = 60 frames trimmed from a 107-frame lattice render: trim_out 60, tail handle 47.
"""

from __future__ import annotations

import copy
import wave
from pathlib import Path

import pytest

import build_vo_tracks as bvt
import timeline_lock_core as core
import timeline_lock_io as lio
import write_timeline_lock as wtl

RATE = 24000
FIVE_S = {"en": 5.0}


def _wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(bytes(2 * round(seconds * RATE)))


def _row(sid, bpm=None, snap=None, natural=4.5):
    """Narration from 0.5 s, so the lock needs the spoken line plus the tail."""
    row = {
        "id": sid,
        "audio_and_dialogue_track": {
            "narration_by_lang": {"en": {"text": "line", "time_range": [0.5, 0.5 + natural]}},
            "dialogue_by_lang": {},
        },
        "bpm": bpm,
        "cue": None,
    }
    if snap is not None:
        row["snap"] = snap
    return row


# ---- T-04: snap default false ----

def test_snap_default_is_free_cut_in_core():
    """No snap key: the 128 BPM shot keeps its 120 free frames, no beat grid."""
    plan = core.plan_shots(
        [{"id": "a", "bpm": 128.0}, {"id": "b"}],
        {"a": FIVE_S, "b": FIVE_S},
        margin_frames=0,
    )
    assert plan[0]["method"] == "free"
    assert plan[0]["edit_frames"] == 120
    assert plan[0]["beats"] is None
    assert plan[0]["snap"] is False


def test_snap_true_still_moves_to_the_beat_grid():
    plan = core.plan_shots(
        [{"id": "a", "bpm": 128.0, "snap": True}, {"id": "b"}],
        {"a": FIVE_S, "b": {"en": 124 / 24}},  # b = 124 frames so the H3 seam class matches a's 124
        margin_frames=0,
    )
    assert plan[0]["method"] == "beat"
    assert plan[0]["edit_frames"] == 124
    assert plan[0]["beats"] == 11
    assert plan[0]["spare"] == 4


def test_write_plan_lock_snap_missing_is_free(tmp_path):
    """The writer's own rows: a row without snap is planned free, same as snap false."""
    root = tmp_path / "wav"
    for lang in ("en",):
        _wav(root / lang / "S1-N.en.wav", 4.5)
        _wav(root / lang / "S2-N.en.wav", 4.5)
    rows = [_row("S1", bpm=128), _row("S2")]
    lock_rows = wtl.plan_lock(rows, lambda lang, lid: bvt.wav_seconds(root / lang / wtl.wav_name(lid, lang)),
                              ["en"], None, {})
    assert lock_rows[0]["snap"] is False
    assert lock_rows[0]["method"] == "free"
    assert lock_rows[0]["beats"] is None


# ---- T-05: short edits with trim records ----

@pytest.mark.xfail(
    strict=True, raises=ValueError,
    reason="H3 rules (MO-03 impact span, CN-05 tail) reject a 60-frame DYNAMIC cut from 107; needs an h3 owner decision",
)
def test_trimmed_short_shot():
    """A 2.5 s edit (60 frames) cut from a 107-frame render: trim span 60, pixel 107, tail handle 47."""
    result = core.plan_pixels(["a", "b"], [60, 120])
    first = result[0]
    assert first["pixel_frames"] == 107
    assert first["trim_out_frame"] - first["trim_in_frame"] == 60
    assert first["tail_handle"] == 47


def test_trimmed_short_shot_80_frames_passes():
    """An 80-frame edit (3.3 s) cut from a 107-frame render passes: trim span 80, tail handle 107 - 80 = 27."""
    result = core.plan_pixels(["a", "b"], [80, 120])
    first = result[0]
    assert first["pixel_frames"] == 107
    assert first["trim_out_frame"] - first["trim_in_frame"] == 80
    assert first["tail_handle"] == 27


def test_short_trim_record_is_accepted_by_lock_io(tmp_path):
    """The lock file format already takes a trimmed short shot: span equals edit_frames, end = trim_out - 1."""
    shot = {"id": "a", "edit_frames": 60, "start_frame": 0, "pixel_frames": 107, "trim_in_frame": 0,
            "trim_out_frame": 60, "end_frame_position": 59, "error_ms": 0.0, "method": "free"}
    src = tmp_path / "in.txt"
    src.write_text("x", encoding="utf-8")
    lock = lio.write_lock(tmp_path / "timeline_lock_v1.json", [shot], [src], {"tempo": 1.0})
    assert lock["total_frames"] == 60
    assert lio.load_lock(tmp_path / "timeline_lock_v1.json")["shots"][0]["trim_out_frame"] == 60


def test_short_trim_span_mismatch_is_refused(tmp_path):
    shot = {"id": "a", "edit_frames": 60, "start_frame": 0, "pixel_frames": 107, "trim_in_frame": 0,
            "trim_out_frame": 70, "end_frame_position": 69, "error_ms": 0.0, "method": "free"}
    src = tmp_path / "in.txt"
    src.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="trim span"):
        lio.write_lock(tmp_path / "timeline_lock_v1.json", [shot], [src], {"tempo": 1.0})


# ---- older locks still verify ----

def test_older_lock_without_retime_still_verifies(tmp_path):
    """A lock written before the retime field existed (no key) still verifies against its inputs."""
    src = tmp_path / "shots.json"
    src.write_text("[]", encoding="utf-8")
    shot = {"id": "a", "edit_frames": 107, "start_frame": 0, "pixel_frames": 107, "trim_in_frame": 0,
            "trim_out_frame": 107, "end_frame_position": 106, "error_ms": 0.0, "method": "free"}
    target = tmp_path / "timeline_lock_v1.json"
    lio.write_lock(target, [copy.deepcopy(shot)], [src], {"tempo": 1.0})
    lock = lio.verify_lock(target, [src], {"tempo": 1.0})
    assert lock["version"] == lio.LOCK_VERSION
    src.write_text("[1]", encoding="utf-8")
    with pytest.raises(lio.StaleLockError):
        lio.verify_lock(target, [src], {"tempo": 1.0})


def test_lock_picks_124_for_short_shot():
    """Pika preset: a short shot (80 frames) is planned on the 124-frame floor (n = 7), never 107. The H3 handle rules
    then refuse a dynamic cut of 80 from 124 (head handle 44 > 35), so the planner says so instead of using 107."""
    with pytest.raises(ValueError, match="pixel 124"):
        core.plan_pixels(["a", "b"], [120, 80], preset="pika6")
    assert core.plan_pixels(["a", "b"], [120, 80])[1]["pixel_frames"] == 107   # no preset: unchanged
    first = core.plan_pixels(["a", "b"], [90, 120], preset="pika6")[0]
    assert (first["lattice_n"], first["pixel_frames"]) == (7, 124)
    assert first["trim_out_frame"] - first["trim_in_frame"] == 90
