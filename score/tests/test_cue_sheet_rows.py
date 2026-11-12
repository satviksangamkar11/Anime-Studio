"""M-15 / A-01: cue rows (hit / bed / rest) and the no-silence note in score/cue_sheet.py. Pure, offline."""
import copy
import json
from pathlib import Path

import pytest

from score import cue_sheet as cs

ROOT = Path(__file__).resolve().parents[2]
KALIKA = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "shots.json"
KEYS = {"shot", "t_frame", "kind", "source", "voice_rest"}


def synth_sheet(shots, fps=24, total_s=None):
    """A minimal sheet dict: only the keys cue_rows reads."""
    total_frames = sum(s["frames"] for s in shots)
    return {"fps": fps, "total_s": total_s if total_s is not None else total_frames / fps,
            "shots": shots}


def synth_shot(sid, start_frame, frames, impacts=(), beats=(), voice_rest=None, fps=24):
    return {"id": sid, "start_frame": start_frame, "frames": frames, "start_s": start_frame / fps,
            "end_s": (start_frame + frames) / fps,
            "impacts": [{"at_s": f / fps, "at_frame": f, "type": "hit", "frames": 2, "in_voice": False}
                        for f in impacts],
            "beats": list(beats), "voice_rest": voice_rest}


@pytest.fixture(scope="module")
def kalika_sheet():
    sheet, report = cs.build_cue_sheet(json.loads(KALIKA.read_text(encoding="utf-8")))
    assert sheet is not None, report
    return sheet


# ---------------------------------------------------------------- field presence and kinds

def test_every_row_has_the_required_fields_and_a_known_kind(kalika_sheet):
    out = cs.cue_rows(kalika_sheet)
    assert out["rows"], "no rows"
    for r in out["rows"]:
        assert KEYS <= set(r), r
        assert r["kind"] in {"hit", "bed", "rest"}, r


def test_kalika_rows_cover_every_shot_with_a_bed(kalika_sheet):
    rows = cs.cue_rows(kalika_sheet)["rows"]
    beds = {r["shot"] for r in rows if r["kind"] == "bed" and r.get("role") is None}
    assert beds == {s["id"] for s in kalika_sheet["shots"]}


def test_kalika_hits_sit_on_impact_frames(kalika_sheet):
    expected = {(s["id"], i["at_frame"]) for s in kalika_sheet["shots"] for i in s["impacts"]}
    hits = [(r["shot"], r["t_frame"]) for r in cs.cue_rows(kalika_sheet)["rows"] if r["kind"] == "hit"]
    assert set(hits) == expected
    assert all(r["tolerance_frames"] == 1 for r in cs.cue_rows(kalika_sheet)["rows"] if r["kind"] == "hit")


# ---------------------------------------------------------------- hits, riser, rest

def test_hit_row_is_on_the_impact_frame():
    sheet = synth_sheet([synth_shot("SHOT-001", 0, 96, impacts=[30])])
    hits = [r for r in cs.cue_rows(sheet)["rows"] if r["kind"] == "hit"]
    assert len(hits) == 1 and hits[0]["t_frame"] == 30 and hits[0]["tolerance_frames"] == 1


def test_riser_is_two_seconds_before_the_primary_beat():
    sheet = synth_sheet([synth_shot("SHOT-001", 0, 240, impacts=[120, 200])])
    risers = [r for r in cs.cue_rows(sheet)["rows"] if r.get("role") == "riser"]
    assert len(risers) == 1, "one riser, before the first (primary) hit only"
    assert risers[0]["kind"] == "bed"
    assert risers[0]["t_frame"] == 120 - 48 and risers[0]["frames"] == 48


def test_riser_does_not_start_before_frame_zero():
    sheet = synth_sheet([synth_shot("SHOT-001", 0, 96, impacts=[10])])
    riser = next(r for r in cs.cue_rows(sheet)["rows"] if r.get("role") == "riser")
    assert riser["t_frame"] == 0 and riser["frames"] == 10


def test_rest_rows_come_from_voice_rest_windows():
    sheet = synth_sheet([synth_shot("SHOT-001", 0, 144, voice_rest=(1.0, 3.0)),
                         synth_shot("SHOT-002", 144, 96)])
    rests = [r for r in cs.cue_rows(sheet)["rows"] if r["kind"] == "rest"]
    assert len(rests) == 1
    assert rests[0]["shot"] == "SHOT-001" and rests[0]["t_frame"] == 24
    assert rests[0]["voice_rest"] == [24, 72]


def test_no_voice_rest_means_no_rest_row():
    sheet = synth_sheet([synth_shot("SHOT-001", 0, 96)])
    assert not [r for r in cs.cue_rows(sheet)["rows"] if r["kind"] == "rest"]


def test_build_cue_sheet_keeps_voice_rest_in_reel_seconds():
    shots = json.loads(KALIKA.read_text(encoding="utf-8"))
    shots = copy.deepcopy(shots)
    first = shots[0]
    first["voice_rest"] = [1.0, 2.0]
    sheet, report = cs.build_cue_sheet(shots)
    assert sheet is not None, report
    row = sheet["shots"][0]
    assert row["voice_rest"] == [pytest.approx(row["start_s"] + 1.0), pytest.approx(row["start_s"] + 2.0)]


# ---------------------------------------------------------------- no-silence note

def test_note_says_no_silence_when_beds_cover_the_reel():
    sheet = synth_sheet([synth_shot("SHOT-001", 0, 48), synth_shot("SHOT-002", 48, 48)])
    notes = cs.cue_rows(sheet)["notes"]
    assert any("no silence" in n for n in notes), notes


def test_note_names_a_silence_gap_longer_than_point_three_seconds():
    # shot 2 starts at 6 s, so 2 s to 6 s has no bed row: the note must name it
    sheet = synth_sheet([synth_shot("SHOT-001", 0, 48), synth_shot("SHOT-002", 144, 48)], total_s=8.0)
    notes = cs.cue_rows(sheet)["notes"]
    assert any("silence" in n and "2" in n and "6" in n for n in notes), notes
    assert not any(n.startswith("no silence") for n in notes)


# M-31: a voice_rest the pack gave but the sheet cannot use is reported, never dropped silently
def test_unreadable_voice_rest_is_reported_not_silently_dropped():
    shots = json.loads(KALIKA.read_text(encoding="utf-8"))
    shots[1]["voice_rest"] = "not a range"
    sheet, report = cs.build_cue_sheet(shots)
    assert sheet is not None
    assert any(w["code"] == "VOICE_REST_BAD" for w in report["warnings"])
    assert sheet["shots"][1]["voice_rest"] is None
