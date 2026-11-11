"""Card W-07 (wiring of the prompt): one blank line at most, sound nouns checked at compile time, the cast line from the
blocking sheet, a duplicate sentence refused, and no new PR-01 lint error. Synthetic story only; offline.

The SX-01 glue rule waits for owner decision D1 (research/OPUS_PLAN_P2_WIRING_2026-11-11.md). test_glue_gone is marked
xfail(strict) until D1 is written into v4_to_h3.py:160; when D1 lands, remove the marker."""
import copy

import pytest

from h3 import compile_h3_sing8 as comp
from h3.compile_h3_sing8 import compile_fl2va_prompt
from h3.prompt_hygiene import find_cue_glue
from h3.schema_and_linter import PROMPT_RE, REF2VA_RE, lint_story
from h3.tests.synth import build_story, codes, ref2va_story
from h3.tests.test_v4_to_h3 import _row
from h3.v4_to_h3 import _stages, convert_pack

SHOT_A = "SHOT-001"
CAST_LINE = "Only Sati and Shiva appear in this shot; no extra figures or creatures appear."


def _all_prompts(story):
    reg = story["registry"]
    return {s["shot_id"]: compile_fl2va_prompt(s, reg)["compiled_prompt"]
            for ep in story["episodes"] for s in ep["shots"]}


def _shot(story, sid):
    return next(s for ep in story["episodes"] for s in ep["shots"] if s["shot_id"] == sid)


def test_no_blank_line_any_shot(tmp_path):
    for story in (build_story(str(tmp_path / "a")), ref2va_story(str(tmp_path / "b"))):
        prompts = _all_prompts(story)
        assert prompts
        for sid, text in prompts.items():
            assert "\n\n" not in text, sid
            assert PROMPT_RE.match(text) or REF2VA_RE.match(text), sid


def test_blank_line_guard_refuses(tmp_path, monkeypatch):
    story = build_story(str(tmp_path))
    monkeypatch.setattr(comp, "_fl2va", lambda shot, registry: ("header\n\nbody", "body"))
    monkeypatch.setattr(comp, "_ref2va", lambda shot, registry: ("header\n\nbody", "body"))
    with pytest.raises(ValueError, match="blank line"):
        compile_fl2va_prompt(_shot(story, "SYN_A"), story["registry"])


def test_lint_errors_not_increased(tmp_path):
    res = lint_story(build_story(str(tmp_path)))
    found = codes(res["errors"])
    assert "PR-01" not in found
    assert "PR-00" not in found


@pytest.mark.xfail(strict=True,
                   reason="SX-01 owner decision D1 pending: v4_to_h3.py:160 still joins cues with ', with '")
def test_glue_gone():
    out, _ = _stages([{"t0": 0, "t1": 1, "action_pose_expression": "Sati lifts the veil",
                       "audio_cue": "a veil snaps"}], 107, "S1", [])
    for sentence in out.values():
        assert "with a veil" not in sentence
    assert find_cue_glue(" ".join(out.values())) == []


def test_banned_noun_refused(tmp_path):
    story = build_story(str(tmp_path))
    shot = _shot(story, "SYN_A")
    shot["sound_plan"]["overall_soundscape"] = "serpents hiss softly in the dark corners of the hall"
    with pytest.raises(ValueError, match="banned sound noun: serpents"):
        compile_fl2va_prompt(shot, story["registry"])


def test_safe_soundscape_compiles(tmp_path):
    story = build_story(str(tmp_path))
    shot = _shot(story, "SYN_A")
    shot["sound_plan"]["overall_soundscape"] = "a soft rustle as the wind dies down"
    assert "overall_soundscape: Sound effects only:" in compile_fl2va_prompt(shot, story["registry"])["compiled_prompt"]


def test_cast_line_from_blocking(tmp_path):
    story = build_story(str(tmp_path))
    shot = _shot(story, "SYN_A")
    shot["continuity_and_seam_lock"]["subjects_present"] = ["char_alpha", "char_beta"]
    story["registry"]["cast_names"] = {"SYN_A": ["Sati", "Shiva"]}
    assert CAST_LINE in compile_fl2va_prompt(shot, story["registry"])["compiled_prompt"]


def test_cast_line_absent_without_subjects(tmp_path):
    story = build_story(str(tmp_path))
    shot = _shot(story, "SYN_A")
    shot["continuity_and_seam_lock"]["subjects_present"] = []
    assert "Only " not in compile_fl2va_prompt(shot, story["registry"])["compiled_prompt"]


@pytest.mark.xfail(strict=True, reason="duplicate guard waits for owner decision: the stage fill repeats one directive "
                   "in several stages (test_h3_author dynamic pack), so the guard would refuse real packs")
def test_duplicate_sentence_refused(tmp_path):
    story = build_story(str(tmp_path))
    shot = _shot(story, "SYN_A")
    shot["motion_7_stage"]["6_impact_result"] = shot["motion_7_stage"]["5_contact_approach"]
    with pytest.raises(ValueError, match="duplicate sentence"):
        compile_fl2va_prompt(shot, story["registry"])


# ---- convert_pack: the cast comes from the blocking sheet ----

BIBLE = {"style_lock": {"prefix": "2D hand-drawn cel-shaded anime, organic line weight."},
         "characters": {"CHAR-RAJ": {"name": "Raj"}},
         "environments": {"ENV-HALL": {"name": "Teak hall", "continuity_landmarks": ["carved teak door"],
                                       "lighting_baseline": {"key": "warm lamp light from the right"}}},
         "props": {}}


def _pack(blocking=None):
    row = _row(SHOT_A, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD")
    return convert_pack({"shots": [row], "bible": copy.deepcopy(BIBLE), "stage": {}}, languages=["en"],
                        blocking=blocking)


def _blocking(ids):
    # haiku-gap2: convert_pack now lints sheets, so each cast member carries the fields blocking.validate requires
    pose = {"x": 0.5, "y": 0.8, "scale": 0.5, "facing": "right", "pose": "standing", "mouth_moves": False}
    return {SHOT_A: {"schema": "blocking/1", "shot_id": SHOT_A,
                     "cast": [{"id": cid, "name": name, "speaks": False, "arms": 2, "source_refs": ["ch2:p10"],
                               "start": dict(pose), "end": dict(pose)} for cid, name in ids]}}


def test_cast_names_come_from_blocking():
    res = _pack(_blocking([("CHAR-RAJ", "Raj")]))
    assert res["story"]["registry"]["cast_names"] == {SHOT_A: ["Raj"]}
    assert not [p for p in res["problems"] if "cast" in p]
    shot = res["story"]["episodes"][0]["shots"][0]
    assert shot["continuity_and_seam_lock"]["subjects_present"] == ["CHAR-RAJ"]


def test_cast_mismatch_problem():
    res = _pack(_blocking([("CHAR-OTHER", "Other")]))
    assert f"{SHOT_A}: cast {{CHAR-RAJ}} != blocking {{CHAR-OTHER}}" in res["problems"]


def test_missing_blocking_sheet_is_problem():
    res = _pack(blocking={})
    assert f"{SHOT_A}: no blocking sheet for this shot" in res["problems"]


def test_no_blocking_means_no_cast_names():
    res = _pack(blocking=None)
    assert "cast_names" not in res["story"]["registry"]
