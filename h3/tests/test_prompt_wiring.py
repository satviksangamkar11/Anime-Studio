"""Card W-07 (wiring of the prompt): one blank line at most, sound nouns checked at compile time, the cast line from the
blocking sheet, a duplicate sentence refused, and no new PR-01 lint error. Synthetic story only; offline.

SX-01 glue rule is decision D1 = B (research/CHANGE_PLAN_FROM_OPUS_2026-11-12.md, card M-01): stage cues go to the
soundscape, not into the action sentences."""
import copy

import pytest

from h3 import compile_h3_sing8 as comp
from h3.compile_h3_sing8 import compile_fl2va_prompt
from h3.prompt_hygiene import find_cue_glue
import json
import re

from h3 import v4_to_h3 as v
from h3.schema_and_linter import MOUTH_LOCK_SENTENCE, PROMPT_RE, REF2VA_RE, lint_story, sx02_problems
from h3.tests.synth import build_story, codes, ref2va_story
from h3.tests.test_v4_to_h3 import _row
from h3.v4_to_h3 import _stages, convert_pack


# ---- M-01 (W-07 finish, D1 = B): stage cues in the soundscape, per-person mouth, SX-02, blocking from the pack ----

def test_soundscape_max_4_sentences_with_7_cues():
    extra = [(float(i), f"bell {i} rings") for i in range(7)]
    problems = []
    text = v._soundscape({"sfx_cues": []}, "SHOT-001", problems, extra=extra)
    assert problems == []
    sentences = [s for s in re.split(r"(?<=\.) ", text) if s]
    assert 1 <= len(sentences) <= 4
    assert re.findall(r"bell (\d) rings", text) == [str(i) for i in range(7)]   # all 7 cues, in t order
    assert text.startswith("First bell 0 rings")


def test_no_breath_exception():
    ms = {str(s): "closed" for s in range(8)}
    ms["3"] = "open_non_verbal_breath"
    track = {"performance_notes": {"narrator_mouth_closed": True, "mouth_state": ms}}
    states, rule = v._mouth(track, 175, "S", [], ed=None, ti=0)
    assert states["3"] == "open_non_verbal_breath"
    assert "breath" not in rule


def test_sx02_all_cues_in_soundscape_in_order():
    cues = [{"t": 1.0, "text": "a veil snaps"}, {"t": 3.0, "text": "rain drips"}]
    assert sx02_problems("Sound effects only: a veil snaps; then rain drips.", cues) == []
    assert sx02_problems("Sound effects only: rain drips; a veil snaps.", cues) != []   # out of t order
    assert sx02_problems("Sound effects only: a veil snaps.", cues) != []               # a cue is missing


def test_mouth_two_people_one_speaker(tmp_path):
    story = build_story(str(tmp_path))
    shot = _shot(story, "SYN_A")
    shot["continuity_and_seam_lock"]["subjects_present"] = ["char_alpha", "char_beta"]
    story["registry"]["cast_names"] = {"SYN_A": ["Sati", "Shiva"]}
    shot["cast_lock"] = {"speaking": ["Sati"]}
    text = compile_fl2va_prompt(shot, story["registry"])["compiled_prompt"]
    assert "Sati speaks with moving lips; Shiva keeps their lips completely closed." in text   # prompt_hygiene form
    assert MOUTH_LOCK_SENTENCE not in text   # the positive lock is for zero-cast shots only


def _pack_sheet():
    pose = {"x": 0.5, "y": 0.8, "scale": 0.5, "facing": "right", "pose": "standing", "mouth_moves": False}
    return {"schema": "blocking/1", "shot_id": SHOT_A, "plate_id": "PLATE-hall", "location_id": "ENV-HALL",
            "kind": "acting", "camera": {"mode": "fixed", "framing": "medium", "move": None},
            "light": {"key_dir": "left", "palette_id": "PAL-warm"}, "props": [], "entries": [], "exits": [],
            "sound_cues": [{"t": 1.0, "text": "soft wind"}], "arc_sec": 0.0, "writer_seconds": 5.0,
            "cut_to_next": "cut", "source_refs": ["ch2:p10"],
            "cast": [{"id": "CHAR-RAJ", "name": "Raj", "speaks": False, "arms": 2, "source_refs": ["ch2:p10"],
                      "start": dict(pose), "end": dict(pose)}]}


def test_blocking_loaded_from_pack_folder(tmp_path):
    row = _row(SHOT_A, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD")
    (tmp_path / "shots.json").write_text(json.dumps([row]), encoding="utf-8")
    (tmp_path / "bible.json").write_text(json.dumps(copy.deepcopy(BIBLE)), encoding="utf-8")
    (tmp_path / "blocking").mkdir()
    (tmp_path / "blocking" / (SHOT_A + ".json")).write_text(json.dumps(_pack_sheet()), encoding="utf-8")
    res = convert_pack(str(tmp_path), languages=["en"])
    assert res["story"]["registry"]["cast_names"] == {SHOT_A: ["Raj"]}


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
