"""Contract between flow/scripts/pack_to_spec.py and the h3 compile (V4 pack).

Finding (2026-11-07): pack_to_spec reads the legacy Flow pack (shots with id/cast/keyframes) and writes a Flow image
spec (characters, places, props, style chips). It does not read V4 shot rows. The V4 -> H3 half is h3/v4_to_h3.py
(convert_pack); its test proves a V4 pack goes through convert_pack and lints clean in h3.schema_and_linter.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

FLOW_SCRIPTS = Path(__file__).resolve().parents[2] / "flow" / "scripts"


def _p2s():
    spec = importlib.util.spec_from_file_location("pack_to_spec_under_test", FLOW_SCRIPTS / "pack_to_spec.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(FLOW_SCRIPTS))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(FLOW_SCRIPTS))
    return mod


def _v4_pack():
    """Small synthetic V4 pack (shot rows as the V4 writer emits them, bible in the canonical layout)."""
    shot = {"id": "SHOT-01", "route": "FL2VA", "episode": "EP1", "editorial_duration_sec": 4.0,
            "continuity_handoff": {"incoming": "still", "outgoing": "turn", "loop_seam": None},
            "reference_anchors": {"fixed_landmarks": ["lamp"], "character_positions": [],
                                  "exited_character_status": [], "lighting_baseline": {}},
            "fl2va_keyframes": {"picture_1_path": "keyframes/SHOT-01-A.png", "picture_2_path": "keyframes/SHOT-01-B.png"},
            "audio_and_dialogue_track": {"narration": None, "dialogue": [], "sfx_cues": [], "performance_notes": {
                "text": "", "narrator_mouth_closed": True, "mouth_state": {"0": "closed"}}}}
    bible = {"characters": {"CHAR-MIRA": {"age": "adult"}}, "environments": {"ENV-STAIR": {"continuity_landmarks": ["lamp"]}},
             "props": {}}
    return [shot], bible


def test_pack_to_spec_still_converts_its_legacy_pack():
    p2s = _p2s()
    legacy_shots = [{"id": "SHOT-01", "scene": "climb", "mode": "fl2va", "aspect": "9:16", "cast": [], "props": [],
                     "set": "ENV-STAIR",
                     "camera": {"move": "static", "lens_mm": 35, "height": "low", "start_framing": "full body",
                                "end_framing": "medium"},
                     "light": {"key": "dusk", "mood": "cold blue", "rim": "none"},
                     "start_state": "stands at the stair", "end_state": "stops at the top",
                     "keyframes": {"start": "keyframes/SHOT-01-FRAME-A.png", "end": "keyframes/SHOT-01-FRAME-B.png"}}]
    bible = {"characters": {}, "environments": {"ENV-STAIR": {"layers": ["FG_rail", "MID_stair", "BG_sea"],
                                                              "light": "dusk_screen_right_35mm"}},
             "props": {}}
    spec, series = p2s.convert(legacy_shots, bible, 1, "lighthouse")
    assert series["slug"] == "lighthouse"
    assert spec is not None


def test_pack_to_spec_refuses_a_v4_shot_row():
    """Documents the gap: V4 rows have no id/cast/keyframes layout that pack_to_spec reads."""
    p2s = _p2s()
    shots, bible = _v4_pack()
    with pytest.raises((p2s.PackError, KeyError, TypeError, ValueError)):
        p2s.convert(shots, bible, 1, "v4pack")


def test_v4_pack_converts_to_an_h3_story_that_lints_clean(tmp_path):
    from h3.tests.test_v4_to_h3 import build_pack
    from h3.v4_to_h3 import convert_pack
    from h3.schema_and_linter import lint_story

    root = str(tmp_path / "pack")
    Path(root).mkdir()
    build_pack(root)
    res = convert_pack(root)
    assert res["problems"] == []
    assert lint_story(res["story"])["errors"] == []
