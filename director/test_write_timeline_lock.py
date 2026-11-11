"""Tests for director/write_timeline_lock.py (card W-03).

Synthetic 24 kHz mono WAVs are written with the wave module into tmp_path. Expected numbers are hand-computed:
  narration starts at 0.5 s, en 2.40 s, hi 2.00 s: need = max(0.5+2.4+0.1, 0.5+2.0+0.1) = 3.0 s = 72 frames.
  128 BPM = 11.25 frames per beat: beat 7 = 78.75 -> 79 frames (spare 7); 60 BPM is 24 frames per beat.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

import build_vo_tracks as bvt
import timeline_lock_io as lio
import write_timeline_lock as wtl
from h3 import v4_to_h3 as v4

RATE = 24000
LANGS = ["en", "hi"]
NARR = {"en": (0.5, 2.40), "hi": (0.5, 2.00)}


def _wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = round(seconds * RATE)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(bytes(2 * frames))


def _wavs(root: Path, natural_by_shot: dict) -> None:
    """natural_by_shot = {shot id: {lang: seconds}}: writes the narration WAV <root>/<lang>/<id>-N.<lang>.wav."""
    for sid, per_lang in natural_by_shot.items():
        for lang, seconds in per_lang.items():
            _wav(root / lang / f"{sid}-N.{lang}.wav", seconds)


def _row(sid, narr=NARR, bpm=None, snap=False, cue=None):
    """One pack row. narr = {lang: (start, natural)}: one narration line per language, id <sid>-N."""
    narration = {
        lang: {"text": "line", "time_range": [start, start + natural]} for lang, (start, natural) in narr.items()
    }
    return {
        "id": sid,
        "audio_and_dialogue_track": {"narration_by_lang": narration, "dialogue_by_lang": {}},
        "bpm": bpm,
        "snap": snap,
        "cue": cue,
    }


def _secs(root: Path):
    return lambda lang, line_id: bvt.wav_seconds(root / lang / wtl.wav_name(line_id, lang))


def _pack(tmp_path: Path, rows: list, natural_by_shot: dict):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "shots.json").write_text(json.dumps(rows), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    root = tmp_path / "wav"
    _wavs(root, natural_by_shot)
    return pack, root, manifest


def _cli(pack, root, manifest, out):
    return wtl.main(["--pack", str(pack), "--wav-root", str(root), "--manifest", str(manifest),
                     "--out-dir", str(out), "--langs", "en,hi"])


# H3 rule: a first shot whose outgoing cut is dynamic needs its editorial length inside the 6_impact_result span
# (76..91 at 107 frames), so the reel starts with S0 at 80 frames (en 2.70 + 0.5 + 0.1 = 3.3 s); S1 and S2 are 72.
FREE_NATURAL = {"S0": {"en": 2.70, "hi": 2.00}, "S1": {"en": 2.40, "hi": 2.00}, "S2": {"en": 2.40, "hi": 2.00}}


def _free_rows():
    return [_row("S0", {"en": (0.5, 2.70), "hi": (0.5, 2.00)}), _row("S1"), _row("S2")]


def test_needed_seconds_drive_edit_frames(tmp_path):
    _wavs(tmp_path / "wav", FREE_NATURAL)
    lock = wtl.plan_lock(_free_rows(), _secs(tmp_path / "wav"), LANGS, None, {})
    assert [r["edit_frames"] for r in lock] == [80, 72, 72]
    assert [r["method"] for r in lock] == ["free", "free", "free"]


def test_snap_only_groove_shots(tmp_path):
    rows = [_row("S1", bpm=128, snap=True), _row("S2", bpm=128, snap=False), _row("S3", bpm=60, snap=False)]
    _wavs(tmp_path / "wav", {"S1": {"en": 2.40, "hi": 2.00}, "S2": {"en": 2.40, "hi": 2.00},
                             "S3": {"en": 2.40, "hi": 2.00}})
    lock = wtl.plan_lock(rows, _secs(tmp_path / "wav"), LANGS, None, {})
    assert [r["edit_frames"] for r in lock] == [79, 72, 72]
    assert [r["method"] for r in lock] == ["beat", "free", "free"]
    assert [r["beats"] for r in lock] == [7, None, None]
    assert [r["spare"] for r in lock] == [7, 0, 0]
    assert [r["bpm"] for r in lock] == [128, 128, 60]


def test_non_snap_mid_act_refused(tmp_path):
    rows = [_row("S1", bpm=128, snap=False), _row("S2", bpm=128, snap=True), _row("S3", bpm=60)]
    _wavs(tmp_path / "wav", {"S1": {"en": 2.40, "hi": 2.00}, "S2": {"en": 2.40, "hi": 2.00},
                             "S3": {"en": 2.40, "hi": 2.00}})
    with pytest.raises(SystemExit):
        wtl.plan_lock(rows, _secs(tmp_path / "wav"), LANGS, None, {})


def test_exempt_non_snap_shots_with_one_cue_stay_one_act(tmp_path):
    """W-03: an act is a run of one cue. Two groove-free shots (bpm 60, not snapped) with the same cue are one act."""
    rows = [_row("S0"), _row("S1", cue="c1"), _row("S2", cue="c1")]  # S0: the 80-frame first shot of the H3 rule
    _wavs(tmp_path / "wav", FREE_NATURAL)
    lock = wtl.plan_lock(rows, _secs(tmp_path / "wav"), LANGS, None, {})
    assert lock[1]["act_start_frame"] == lock[2]["act_start_frame"]


def test_non_snap_last_shot_of_act_is_allowed(tmp_path):
    """W-03: a non-snapped 128 BPM shot is allowed when it is the last shot of its act."""
    rows = [_row("S1", bpm=128, snap=True, cue="c1"), _row("S2", bpm=128, snap=False, cue="c1"),
            _row("S3", bpm=60, cue="c2")]
    _wavs(tmp_path / "wav", {"S1": {"en": 2.40, "hi": 2.00}, "S2": {"en": 2.40, "hi": 2.00},
                             "S3": {"en": 2.40, "hi": 2.00}})
    lock = wtl.plan_lock(rows, _secs(tmp_path / "wav"), LANGS, None, {})
    assert [r["id"] for r in lock] == ["S1", "S2", "S3"]


def test_handles_legal(tmp_path):
    rows = [_row("S1", bpm=128, snap=True), _row("S2", bpm=128, snap=False), _row("S3", bpm=60)]
    _wavs(tmp_path / "wav", {"S1": {"en": 2.40, "hi": 2.00}, "S2": {"en": 2.40, "hi": 2.00},
                             "S3": {"en": 2.40, "hi": 2.00}})
    lock = wtl.plan_lock(rows, _secs(tmp_path / "wav"), LANGS, None, {})
    for row in lock:
        pf, ed = row["pixel_frames"], row["edit_frames"]
        assert 107 <= pf <= 345 and (pf - 5) % 17 == 0
        assert row["trim_out_frame"] - row["trim_in_frame"] == ed
        assert row["end_frame_position"] == row["trim_out_frame"] - 1
        _, problems = v4._plan_handles(row["id"], pf, ed, row["incoming_seam_type"], row["outgoing_seam_type"],
                                       row["lattice_n"])
        assert problems == []


def test_silent_shot_needs_min_seconds(tmp_path):
    rows = _free_rows()[:2] + [_row("S2", narr={})]
    _wavs(tmp_path / "wav", FREE_NATURAL)
    secs = _secs(tmp_path / "wav")
    with pytest.raises(SystemExit, match="silent shot needs blocking min_seconds"):
        wtl.plan_lock(rows, secs, LANGS, None, {})
    lock = wtl.plan_lock(rows, secs, LANGS, None, {"S2": 4.0})
    assert lock[2]["edit_frames"] == 96
    assert lock[2]["method"] == "free"


def test_wav_byte_change_is_stale(tmp_path):
    pack, root, manifest = _pack(tmp_path, _free_rows(), FREE_NATURAL)
    out = tmp_path / "lock"
    assert _cli(pack, root, manifest, out) == 0
    v1 = out / "timeline_lock_v1.json"
    lock = lio.load_lock(v1)
    lio.verify_lock(v1, lock["inputs"], lock["params"])
    _wav(root / "en" / "S1-N.en.wav", 2.60)
    with pytest.raises(lio.StaleLockError):
        lio.verify_lock(v1, lock["inputs"], lock["params"])


def test_params_change_is_stale(tmp_path):
    pack, root, manifest = _pack(tmp_path, _free_rows(), FREE_NATURAL)
    out = tmp_path / "lock"
    assert _cli(pack, root, manifest, out) == 0
    v1 = out / "timeline_lock_v1.json"
    lock = lio.load_lock(v1)
    params_file = out / "timeline_lock_v1.params.json"
    params_file.write_text(json.dumps(dict(lock["params"], margin_frames=6)), encoding="utf-8")
    with pytest.raises(lio.StaleLockError):
        lio.verify_lock(v1, lock["inputs"], lock["params"])


def test_versioned_never_replaced(tmp_path):
    pack, root, manifest = _pack(tmp_path, _free_rows(), FREE_NATURAL)
    out = tmp_path / "lock"
    assert _cli(pack, root, manifest, out) == 0
    v1 = out / "timeline_lock_v1.json"
    v1_bytes = v1.read_bytes()

    _wav(root / "en" / "S2-N.en.wav", 3.00)   # last shot: 3.0 s -> 3.6 s need -> 87 frames
    assert _cli(pack, root, manifest, out) == 0

    assert v1.read_bytes() == v1_bytes
    v2 = out / "timeline_lock_v2.json"
    assert v2.is_file()
    diff = json.loads((out / "timeline_lock_v2.diff.json").read_text(encoding="utf-8"))
    assert diff == [{"id": "S2", "old": 72, "new": 87}]
    assert [r["edit_frames"] for r in lio.load_lock(v2)["shots"]] == [80, 72, 87]
