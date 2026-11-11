"""Card X-05 (prompt cast/mouth/sound inputs come from the blocking sheet, v4_to_h3). Synthetic data only; offline.

convert_pack(blocking_dir=...) reads <shot_id>.json sheets; the shot's subjects come from the sheet cast order; a
cast that differs from the V4 character positions is a problem; a shot with a sheet gets cast_lock (the values of
blocking.prompt_args, hand-computed below); with no blocking_dir nothing changes."""
import copy
import json

from h3.tests.test_v4_to_h3 import _row
from h3.v4_to_h3 import convert_pack

SHOT_A = "SHOT-001"
BIBLE = {"style_lock": {"prefix": "2D hand-drawn cel-shaded anime, organic line weight."},
         "characters": {"CHAR-RAJ": {"name": "Raj"}, "CHAR-SATI": {"name": "Sati"}},
         "environments": {"ENV-HALL": {"name": "Teak hall", "continuity_landmarks": ["carved teak door"],
                                       "lighting_baseline": {"key": "warm lamp light from the right"}}},
         "props": {}}


def _pose(x, facing="right", pose="standing", mouth=False):
    return {"x": x, "y": 0.5, "scale": 0.5, "facing": facing, "pose": pose, "mouth_moves": mouth}


def _member(cid, name, start_x, end_x, speaks=False):
    return {"id": cid, "name": name, "speaks": speaks, "arms": 2, "source_refs": ["ch2:p10"],
            "start": _pose(start_x, mouth=speaks), "end": _pose(end_x, mouth=speaks)}


def _sheet(cast):
    return {"schema": "blocking/1", "shot_id": SHOT_A, "plate_id": "PLATE-hall", "location_id": "ENV-HALL",
            "kind": "acting", "camera": {"mode": "fixed", "framing": "medium", "move": None},
            "light": {"key_dir": "left", "palette_id": "PAL-warm"},
            "props": [{"id": "P1", "class": "throne", "x": 0.5, "y": 0.9, "visible": ["A", "B"]}],
            "entries": [], "exits": [], "sound_cues": [{"t": 1.0, "text": "soft wind"}],
            "arc_sec": 2.0, "writer_seconds": 5.0, "cut_to_next": "cut", "source_refs": ["ch2:p10"],
            "cast": cast}


def _write_sheet(folder, sheet):
    (folder / (sheet["shot_id"] + ".json")).write_text(json.dumps(sheet), encoding="utf-8")


def _row_a(anchor_ids=("CHAR-RAJ",)):
    row = _row(SHOT_A, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD")
    row["reference_anchors"]["character_positions"] = [{"id": cid, "screen": "center", "depth": "mid"}
                                                      for cid in anchor_ids]
    return row


def _convert(tmp_path, row, sheet=None):
    if sheet is not None:
        _write_sheet(tmp_path, sheet)
    return convert_pack({"shots": [row], "bible": copy.deepcopy(BIBLE), "stage": {}}, languages=["en"],
                        blocking_dir=str(tmp_path))


def _shot(res):
    return res["story"]["episodes"][0]["shots"][0]


def test_subjects_from_blocking(tmp_path):
    # anchors list Raj then Sati; the sheet lists Sati then Raj: the sheet order is the subject list
    row = _row_a(("CHAR-RAJ", "CHAR-SATI"))
    sheet = _sheet([_member("CHAR-SATI", "Sati", 0.3, 0.3), _member("CHAR-RAJ", "Raj", 0.7, 0.7)])
    res = _convert(tmp_path, row, sheet)
    assert _shot(res)["continuity_and_seam_lock"]["subjects_present"] == ["CHAR-SATI", "CHAR-RAJ"]
    assert res["story"]["registry"]["cast_names"] == {SHOT_A: ["Sati", "Raj"]}
    assert not [p for p in res["problems"] if "cast" in p or "BLK" in p]


def test_cast_mismatch_is_problem(tmp_path):
    row = _row_a(("CHAR-RAJ",))
    sheet = _sheet([_member("CHAR-SATI", "Sati", 0.3, 0.3)])
    res = _convert(tmp_path, row, sheet)
    assert f"{SHOT_A}: cast {{CHAR-RAJ}} != blocking {{CHAR-SATI}}" in res["problems"]
    assert _shot(res)["continuity_and_seam_lock"]["subjects_present"] == ["CHAR-SATI"]


def test_cast_lock_equals_prompt_args(tmp_path):
    # hand-computed from the sheet: both members have x in [0, 1] at start and end, so both are on screen;
    # only Raj speaks; one sound cue; visible = cast names then prop classes
    row = _row_a(("CHAR-SATI", "CHAR-RAJ"))
    sheet = _sheet([_member("CHAR-SATI", "Sati", 0.3, 0.3),
                    _member("CHAR-RAJ", "Raj", 0.7, 0.7, speaks=True)])
    res = _convert(tmp_path, row, sheet)
    assert _shot(res)["cast_lock"] == {"cast": ["Sati", "Raj"], "on_screen": ["Sati", "Raj"],
                                       "speaking": ["Raj"], "sound_cues": ["soft wind"],
                                       "visible": ["Sati", "Raj", "throne"]}


def test_no_blocking_dir_unchanged(tmp_path):
    # golden from the pre-X-05 output of this input: the shot keys, the one problem, subjects from the anchors
    row = _row_a(("CHAR-RAJ",))
    res = convert_pack({"shots": [row], "bible": copy.deepcopy(BIBLE), "stage": {}}, languages=["en"])
    shot = _shot(res)
    assert sorted(shot) == ["anime_timing_cadence", "camera", "continuity_and_seam_lock", "dialogue_and_lip_lock",
                            "emotional_objective", "episode_id", "fl2va_keyframes", "motion_7_stage",
                            "mute_animatic_verification", "sequence_order", "shot_id", "sound_plan", "story_beat",
                            "timing_and_lattice"]
    assert res["problems"] == [f"{SHOT_A}: boundary frames missing (keyframes/{SHOT_A}-A.png, -B.png); "
                               "FL2VA needs both"]
    assert "cast_lock" not in shot
    assert "cast_names" not in res["story"]["registry"]
    assert shot["continuity_and_seam_lock"]["subjects_present"] == ["CHAR-RAJ"]


def test_empty_blocking_dir_reports_missing_sheet(tmp_path):
    res = _convert(tmp_path, _row_a(("CHAR-RAJ",)))
    assert f"{SHOT_A}: no blocking sheet for this shot" in res["problems"]
    assert "cast_lock" not in _shot(res)


def test_invalid_sheet_file_is_problem(tmp_path):
    bad = _sheet([_member("CHAR-RAJ", "Raj", 0.7, 0.7)])
    bad["schema"] = "blocking/9"
    res = _convert(tmp_path, _row_a(("CHAR-RAJ",)), bad)
    assert any("BLK-S02" in p for p in res["problems"])
    assert "cast_lock" not in _shot(res)
