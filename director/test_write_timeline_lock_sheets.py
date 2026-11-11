"""Gap 7: write_timeline_lock.main() reads a folder of blocking/1 sheets (<SHOT-ID>.json), not only blocking.json.

Derivation (write_timeline_lock.sheet_entry):
  bpm, snap, cue: the sheet's own keys when it carries them, else None, False, None (blocking/1 has none today).
  min_seconds: the sheet's writer_seconds, for a silent shot only (no scripted line in any language).
An old blocking.json ({shot id: {bpm, snap, cue, min_seconds}}) in --blocking-dir is still read, and wins when present.

Hand-computed numbers (24 fps, narration starts at 0.5 s, 0.1 s tail):
  SHOT-001 en 2.70 s -> need 3.3 s = 79.2 -> 80 frames (first shot; same as test_write_timeline_lock.py)
  SHOT-002 en 2.40 s -> need 3.0 s = 72 frames
  SHOT-003 silent, writer_seconds 4.0 -> 96 frames
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

import timeline_lock_io as lio
import write_timeline_lock as wtl

RATE = 24000
LANGS = ["en", "hi"]
IDS = ("SHOT-001", "SHOT-002", "SHOT-003")
EXPECT_EDIT = [80, 72, 96]


def _wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(bytes(2 * round(seconds * RATE)))


def _row(sid, narr):
    narration = {lang: {"text": "line", "time_range": [0.5, 0.5 + natural]} for lang, natural in narr.items()}
    return {"id": sid, "audio_and_dialogue_track": {"narration_by_lang": narration, "dialogue_by_lang": {}},
            "bpm": None, "snap": False, "cue": None}


def _rows():
    return [_row("SHOT-001", {"en": 2.70, "hi": 2.00}), _row("SHOT-002", {"en": 2.40, "hi": 2.00}),
            _row("SHOT-003", {})]


def _sheet(sid, writer=4.0):
    return {"schema": "blocking/1", "shot_id": sid, "plate_id": "PLATE-hall", "location_id": "ENV-HALL",
            "kind": "acting", "camera": {"mode": "fixed", "framing": "medium", "move": None},
            "light": {"key_dir": "left", "palette_id": "PAL-warm"}, "props": [], "entries": [], "exits": [],
            "sound_cues": [], "arc_sec": 2.0, "writer_seconds": writer, "cut_to_next": "cut",
            "source_refs": ["ch2:p10"], "cast": []}


def _write_sheet(blk: Path, sid: str, sheet: dict) -> None:
    (blk / f"{sid}.json").write_text(json.dumps(sheet), encoding="utf-8")


@pytest.fixture
def setup(tmp_path):
    """Pack (shots.json + manifest), line WAVs for SHOT-001 and SHOT-002, and a blocking folder with three sheets."""
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "shots.json").write_text(json.dumps(_rows()), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    root = tmp_path / "wav"
    for row in _rows():
        for lang, line in row["audio_and_dialogue_track"]["narration_by_lang"].items():
            natural = line["time_range"][1] - line["time_range"][0]
            _wav(root / lang / f"{row['id']}-N.{lang}.wav", natural)
    blk = tmp_path / "blocking"
    blk.mkdir()
    for sid in IDS:
        _write_sheet(blk, sid, _sheet(sid))
    return pack, root, manifest, blk, tmp_path / "lock"


def _run(setup):
    pack, root, manifest, blk, out = setup
    rc = wtl.main(["--pack", str(pack), "--wav-root", str(root), "--manifest", str(manifest),
                   "--out-dir", str(out), "--langs", "en,hi", "--blocking-dir", str(blk)])
    return rc, out / "timeline_lock_v1.json"


def test_sheet_folder_drives_the_lock_through_main(setup):
    rc, v1 = _run(setup)
    assert rc == 0
    lock = lio.load_lock(v1)
    assert [r["edit_frames"] for r in lock["shots"]] == EXPECT_EDIT
    assert [r["method"] for r in lock["shots"]] == ["free", "free", "free"]
    text = json.dumps(lock["inputs"]).lower()  # the lock writer stores paths lowercased
    assert all(f"blocking/{sid.lower()}.json" in text for sid in IDS), "every sheet is an input of the lock"


def test_sheet_entry_derivation_is_the_documented_one():
    voiced = wtl.sheet_entry(_sheet("SHOT-001"), _row("SHOT-001", {"en": 2.70}), LANGS)
    assert voiced == {"bpm": None, "snap": False, "cue": None}, "a voiced shot takes its length from the voice"
    silent = wtl.sheet_entry(_sheet("SHOT-003", writer=4.0), _row("SHOT-003", {}), LANGS)
    assert silent == {"bpm": None, "snap": False, "cue": None, "min_seconds": 4.0}
    carried = dict(_sheet("SHOT-004"), bpm=128, snap=True, cue="act1")
    assert wtl.sheet_entry(carried, _row("SHOT-004", {}), LANGS) == {"bpm": 128, "snap": True, "cue": "act1",
                                                                    "min_seconds": 4.0}


def test_sheet_mode_replaces_shots_json_bpm_snap_cue(setup):
    pack = setup[0]
    rows = _rows()
    rows[0].update(bpm=128, snap=True, cue="intro")
    (pack / "shots.json").write_text(json.dumps(rows), encoding="utf-8")
    rc, v1 = _run(setup)
    assert rc == 0
    first = lio.load_lock(v1)["shots"][0]
    assert (first["bpm"], first["snap"], first["cue"]) == (None, False, None)


def test_bad_sheet_refused_with_its_blk_code(setup):
    blk = setup[3]
    _write_sheet(blk, "SHOT-002", dict(_sheet("SHOT-002"), writer_seconds=0))
    with pytest.raises(SystemExit, match="BLK-S13"):
        _run(setup)


def test_sheet_with_wrong_shot_id_refused(setup):
    blk = setup[3]
    _write_sheet(blk, "SHOT-002", _sheet("SHOT-009"))
    with pytest.raises(SystemExit, match="BLK-S17"):
        _run(setup)


def test_missing_sheet_refused(setup):
    blk = setup[3]
    (blk / "SHOT-002.json").unlink()
    with pytest.raises(SystemExit, match="no blocking sheet"):
        _run(setup)


def test_old_blocking_json_still_works(setup):
    blk = setup[3]
    for sid in IDS:
        (blk / f"{sid}.json").unlink()
    (blk / "blocking.json").write_text(json.dumps({"SHOT-003": {"min_seconds": 4.0}}), encoding="utf-8")
    rc, v1 = _run(setup)
    assert rc == 0
    assert [r["edit_frames"] for r in lio.load_lock(v1)["shots"]] == EXPECT_EDIT


def test_edited_sheet_makes_the_lock_stale(setup):
    blk = setup[3]
    rc, v1 = _run(setup)
    assert rc == 0
    lock = lio.load_lock(v1)
    lio.verify_lock(v1, lock["inputs"], lock["params"])
    _write_sheet(blk, "SHOT-003", _sheet("SHOT-003", writer=5.0))
    with pytest.raises(lio.StaleLockError):
        lio.verify_lock(v1, lock["inputs"], lock["params"])
