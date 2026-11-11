"""Tests for card W-06: h3/v4_to_h3.py takes the lattice, trims, seam types and end_frame_position from a timeline lock.

The lock is real: director/write_timeline_lock.plan_lock makes the shot rows from silent shots (min_seconds, so no WAV
is read), write_lock writes the versioned file, load_lock and verify_lock read it back. The pack rows are built with
the helpers of h3/tests/test_v4_to_h3.py but deliberately carry the wrong lattice and length (10 / 7.29 s), so a test
fails if the lock is ignored. Offline: no model call, no network. Frame numbers are hand-checked:
  5.0 s = 120 editorial frames. Lattice n=9 = 158 pixel frames, n=8 = 141 pixel frames (5 + 17n).
  Shot 1 (first in reel, INTER in; outgoing DYNAMIC): trims 0..120. Shot 2 (incoming DYNAMIC, outgoing INTER, 141 px):
  head = 141 - 120 = 21, so trims 21..141.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "director"))  # write_timeline_lock imports its neighbours by bare name

from director import timeline_lock_io as lio  # noqa: E402
from director import write_timeline_lock as wtl  # noqa: E402
from h3.schema_and_linter import write_minimal_valid_png  # noqa: E402
from h3.tests.test_v4_to_h3 import ACTIONS, CUES, _row, build_pack  # noqa: E402
from h3.v4_to_h3 import convert_pack, main  # noqa: E402

SID1, SID2, SID3 = "SHOT-001", "SHOT-002", "SHOT-003"
SECONDS = {SID1: 5.0, SID2: 5.0}


def _directives(sec):
    """One bracket per whole second: 5 brackets for 5.0 s, with the SX-01 sound words the linter recognises."""
    out = []
    for t in range(int(sec)):
        out.append({"t0": float(t), "t1": float(t + 1), "action_pose_expression": ACTIONS[t],
                    "camera": "medium, slow push in", "spatial_position": "center-left, mid depth",
                    "audio_cue": CUES[t], "handoff_to_next_second": "eyes stay on the door"})
    return out


def _make_lock(folder, secs):
    """A real lock for silent shots {id: seconds}, written to folder and read back with load_lock."""
    rows = [{"id": sid, "audio_and_dialogue_track": {"narration_by_lang": {}, "dialogue_by_lang": {}},
             "bpm": None, "snap": False, "cue": None} for sid in secs]
    shots = wtl.plan_lock(rows, lambda lang, line_id: 0.0, ["en"], None, dict(secs))
    inputs = folder / "shots.json"
    inputs.write_text(json.dumps([sid for sid in secs]), encoding="utf-8")
    path = folder / "lock" / "timeline_lock_v1.json"
    lio.write_lock(path, shots, [str(inputs)], {"test": "w06"})
    return path, inputs


@pytest.fixture
def lock_pack(tmp_path):
    """A pack whose rows say lattice 10 and 7.29 s, plus the lock for SECONDS. Returns (pack dir, lock path)."""
    root = tmp_path / "pack"
    root.mkdir()
    build_pack(str(root))
    rows = []
    for sid in (SID1, SID2):
        row = _row(sid, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD")
        row["per_second_directives"] = _directives(5.0)
        rows.append(row)
        write_minimal_valid_png(str(root / "keyframes" / f"{sid}-A.png"), 864, 1536)
        write_minimal_valid_png(str(root / "keyframes" / f"{sid}-B.png"), 864, 1536)
    (root / "shots.json").write_text(json.dumps(rows), encoding="utf-8")
    lock_path, _ = _make_lock(tmp_path, SECONDS)
    return str(root), str(lock_path)


def _shot_in(story, sid):
    return next(s for ep in story["episodes"] for s in ep["shots"] if s["shot_id"] == sid)


def _problems_for(res, sid):
    return [p for p in res["problems"] if p.startswith(sid + ":")]


def test_timing_equals_lock(lock_pack):
    pack, lock_path = lock_pack
    lock = lio.load_lock(lock_path)
    res = convert_pack(pack, lock=lock)
    for lock_shot in lock["shots"]:
        sid = lock_shot["id"]
        assert _problems_for(res, sid) == []
        timing = _shot_in(res["story"], sid)["timing_and_lattice"]
        pixel = lock_shot["pixel_frames"]
        assert timing["pixel_frames"] == pixel
        assert timing["lattice_n"] == (pixel - 5) // 17
        assert timing["latent_slots"] == 5 * timing["lattice_n"] + 2
        assert timing["trim_in_frame"] == lock_shot["trim_in_frame"]
        assert timing["trim_out_frame"] == lock_shot["trim_out_frame"]
        assert timing["head_handle_frames"] == lock_shot["head_handle_frames"]
        assert timing["tail_handle_frames"] == lock_shot["tail_handle_frames"]
        assert timing["editorial_frames"] == lock_shot["edit_frames"]
        assert timing["end_frame_position"] == lock_shot["end_frame_position"] == lock_shot["trim_out_frame"] - 1
        seams = _shot_in(res["story"], sid)["continuity_and_seam_lock"]
        assert seams["incoming_seam_type"] == lock_shot["incoming_seam_type"]


def test_lock_wins_over_row_seam_and_input_unchanged(lock_pack):
    pack, lock_path = lock_pack
    lock = lio.load_lock(lock_path)
    before = json.loads(Path(pack, "shots.json").read_text(encoding="utf-8"))
    res = convert_pack(pack, lock=lock)
    shot1 = _shot_in(res["story"], SID1)["continuity_and_seam_lock"]
    assert shot1["incoming_seam_type"] == "INTER_REEL_HANDSHAKE"
    # the row says CHAINED out; the lock says DYNAMIC out, and the lock wins
    assert lock["shots"][0]["outgoing_seam_type"] == "DYNAMIC_MATCH_ON_ACTION"
    assert _shot_in(res["story"], SID1)["continuity_and_seam_lock"]["outgoing_seam_type"] == "DYNAMIC_MATCH_ON_ACTION"
    assert json.loads(Path(pack, "shots.json").read_text(encoding="utf-8")) == before


def test_shot_missing_from_lock_problem(lock_pack, tmp_path):
    pack, lock_path = lock_pack
    rows = json.loads(Path(pack, "shots.json").read_text(encoding="utf-8"))
    orphan = _row(SID3, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="INTER_REEL_HANDSHAKE")
    orphan["per_second_directives"] = _directives(5.0)
    rows.append(orphan)
    Path(pack, "shots.json").write_text(json.dumps(rows), encoding="utf-8")
    write_minimal_valid_png(str(Path(pack, "keyframes", f"{SID3}-A.png")), 864, 1536)
    write_minimal_valid_png(str(Path(pack, "keyframes", f"{SID3}-B.png")), 864, 1536)
    res = convert_pack(pack, lock=lio.load_lock(lock_path))
    assert f"{SID3}: not in the timeline lock" in res["problems"]
    assert all(s["shot_id"] != SID3 for ep in res["story"]["episodes"] for s in ep["shots"])
    assert _shot_in(res["story"], SID1)["timing_and_lattice"]["pixel_frames"] == 158


def test_tampered_lock_trim_problem(lock_pack):
    pack, lock_path = lock_pack
    lock = lio.load_lock(lock_path)
    lock["shots"][1]["trim_in_frame"] += 1          # derived is 21..141; the lock now says 22..141
    res = convert_pack(pack, lock=lock)
    assert f"{SID2}: lock trims 22..141 in 141 pixel frames != derived 21..141 in 141 pixel frames" in res["problems"]
    assert _shot_in(res["story"], SID2)["timing_and_lattice"]["trim_in_frame"] == 22   # the lock still decides


def test_stale_lock_exits_2(lock_pack, tmp_path):
    pack, lock_path = lock_pack
    assert main([pack, "--lock", lock_path]) != 2
    inputs = Path(json.loads(Path(lock_path).read_text(encoding="utf-8"))["inputs"][0])
    inputs.write_text("[\"changed\"]", encoding="utf-8")   # the recorded input no longer matches its hash
    assert main([pack, "--lock", lock_path]) == 2
