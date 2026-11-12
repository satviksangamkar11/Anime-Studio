"""M-03: the five worked video-prompt examples of research/OPUS_CALIBRATION_REVIEW_2026-11-12.md section 5.2, compiled
from blocking/1.1 sheets (slow scale reveal, dialogue with lip movement, chained second clip, crowd, close-up), plus the
unit rules: time-pointed stages (single point, never a range, TG-01 stays), one camera sentence, hold wording.
Synthetic, offline."""
import copy
import re

import pytest

from h3 import v4_to_h3 as v
from h3.compile_h3_sing8 import compile_fl2va_prompt
from h3.schema_and_linter import lint_story, prompt_lock_problems
from h3.tests.test_v4_to_h3 import _row

S1, S2 = "SHOT-001", "SHOT-002"
POSE = {"x": 0.5, "y": 0.8, "scale": 0.5, "facing": "right", "pose": "standing", "mouth_moves": False}


@pytest.fixture(autouse=True)
def _time_points_on(monkeypatch):
    # M-32: time points are an opt-in profile flag (default off); these examples pin the time-pointed format
    real = v.load_default_profile

    def with_flag(name):
        return dict(real(name), time_points=True)
    monkeypatch.setattr(v, "load_default_profile", with_flag)


LINT_PREFIXES = ("CM-", "TG-", "TX-", "TP-", "MO-", "SX-", "PR-02", "PR-07")


def _member(cid, name, speaks=False, hold=False):
    return {"id": cid, "name": name, "speaks": speaks, "arms": 2, "hold": hold, "source_refs": ["L1"],
            "start": dict(POSE), "end": dict(POSE)}


def _sheet(sid, cast, *, move=None, motivation=None, shake=None, kind="acting", beats=None, chain_from=None,
           cut="cut", extra=None):
    cam = {"mode": "move" if move else "fixed", "framing": "medium", "move": move, "angle": "eye_level",
           "lens": "normal", "motivation": motivation, "shake": shake}
    sheet = {"schema": "blocking/1.1", "shot_id": sid, "plate_id": "PLATE-hall", "location_id": "ENV-HALL",
             "kind": kind, "camera": cam, "light": {"key_dir": "left", "palette_id": "PAL-warm"}, "props": [],
             "entries": [], "exits": [], "sound_cues": [{"t": 1.0, "text": "soft wind", "kind": "bed"}],
             "arc_sec": 0.0, "writer_seconds": 7.29, "cut_to_next": cut, "chain_from": chain_from,
             "source_refs": ["L1"], "cast": cast}
    if beats:
        sheet["beats"] = beats
    sheet.update(extra or {})
    return sheet


def _pack(sheets, rows):
    chars = {m["id"]: {"name": m["name"]} for s in sheets.values() for m in s["cast"]}
    bible = {"style_lock": {"prefix": "2D hand-drawn cel-shaded anime, organic line weight."},
             "characters": chars,
             "environments": {"ENV-HALL": {"name": "Teak hall", "continuity_landmarks": ["carved teak door"],
                                           "lighting_baseline": {"key": "warm lamp light from the right"}}},
             "props": {}}
    for row in rows:
        sheet = sheets[row["id"]]
        row["reference_anchors"]["character_positions"] = [{"id": m["id"], "screen": "center", "depth": "mid"}
                                                          for m in sheet["cast"]]
    res = v.convert_pack({"shots": rows, "bible": bible, "stage": {}}, languages=["en"], blocking=sheets)
    return res


def _compile(sheets, rows, sid):
    res = _pack(sheets, rows)
    assert res["story"] is not None
    shots = {s["shot_id"]: s for ep in res["story"]["episodes"] for s in ep["shots"]}
    text = compile_fl2va_prompt(shots[sid], res["story"]["registry"])["compiled_prompt"]
    return text, res, shots[sid]


def _one(cast, directives=8, **kw):
    row = _row(S1, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD")
    row["per_second_directives"] = row["per_second_directives"][:directives]
    row["per_second_directives"][-1]["t1"] = 7.29
    return _compile({S1: _sheet(S1, cast, **kw)}, [row], S1)


def _body(text):
    return re.search(r"^integrated_multimodal_description: (.*)$", text, re.M).group(1)


def _camera_sentences(body):
    return [s for s in re.split(r"(?<=[.!?]) ", body) if re.search(r"\bthe camera\b", s, re.I)]


def _lint_codes(res):
    errors = lint_story(res["story"], asset_root_override=".")["errors"]
    return [e for e in errors if re.search("(" + "|".join(LINT_PREFIXES) + ")", e)]


def _assert_time_pointed(body):
    points = re.findall(r"\b(?:At|By) second (\d+(?:\.\d+)?)\b", body)
    assert len(points) >= 5, body
    assert not re.search(r"\bsecond \d+(?:\.\d+)?\s*(?:-|to|–)\s*\d", body), "a range, not a time point"
    assert not [p for p in prompt_lock_problems(body + "\noverall_soundscape: x.\n") if p[0] == "TG-01"]
    nums = [float(p) for p in points]
    assert nums[0] == 0 and nums == sorted(nums)


# ---------- the five worked examples ----------

def test_example1_slow_scale_reveal_pull_back():
    text, res, _ = _one([_member("CHAR-KALIYA", "Kaliya"), _member("CHAR-KRISHNA", "Krishna", hold=True)],
                        directives=3, move="pull_back", motivation="the audience must feel its size")
    body = _body(text)
    cams = _camera_sentences(body)
    assert cams == ["The camera pulls back slowly, because the audience must feel its size."]
    assert "Only Kaliya and Krishna appear in this shot; no extra figures or creatures appear." in body
    assert "Krishna does not move." in body   # the held cast member, once the three actions are used up
    assert "Kaliya does not move" not in body
    _assert_time_pointed(body)
    assert not _lint_codes(res), _lint_codes(res)


def test_example2_dialogue_lip_movement_camera_locked():
    text, res, _ = _one([_member("CHAR-YASHODA", "Yashoda", speaks=True), _member("CHAR-KRISHNA", "Krishna")],
                        motivation="the argument is between the two of them")
    body = _body(text)
    assert _camera_sentences(body) == ["The camera stays locked, because the argument is between the two of them."]
    assert "Yashoda speaks with moving lips; Krishna keeps their lips completely closed." in body
    _assert_time_pointed(body)
    assert not _lint_codes(res), _lint_codes(res)


def test_example3_chained_second_clip_has_current_character_state():
    rows = [_row(S1, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD"),
            _row(S2, 1, incoming="CHAINED_POSE_HOLD", outgoing="INTER_REEL_HANDSHAKE")]
    state = "Krishna is mid-leap above the river, body arched forward, both arms reaching down toward the water"
    sheets = {S1: _sheet(S1, [_member("CHAR-KRISHNA", "Krishna")], cut="match"),
              S2: _sheet(S2, [_member("CHAR-KRISHNA", "Krishna")], move="tilt_down",
                         motivation="the dive leads the eye into the river", chain_from=S1,
                         extra={"chain_state": state})}
    text, res, _ = _compile(sheets, rows, S2)
    body = _body(text)
    header = f"CURRENT CHARACTER STATE: {state}. Continue directly from this exact frame with no reset."
    assert header in body
    assert body.index("[Shot 1]") < body.index(header) < body.index("At second 0")
    assert _camera_sentences(body) == ["The camera tilts down slowly, because the dive leads the eye into the river."]
    assert not [p for p in res["problems"] if "chain" in p.lower() and "state" in p.lower()]


def test_example3_chain_without_any_state_is_a_problem():
    rows = [_row(S1, 1, incoming="INTER_REEL_HANDSHAKE", outgoing="CHAINED_POSE_HOLD"),
            _row(S2, 1, incoming="CHAINED_POSE_HOLD", outgoing="INTER_REEL_HANDSHAKE")]
    sheets = {S1: _sheet(S1, [_member("CHAR-KRISHNA", "Krishna")], cut="match"),
              S2: _sheet(S2, [_member("CHAR-KRISHNA", "Krishna")], chain_from=S1)}
    res = _pack(sheets, rows)
    assert any(p.startswith(f"{S2}:") and "CURRENT CHARACTER STATE" in p for p in res["problems"])


def test_example4_crowd_push_in():
    text, res, _ = _one([_member("CHAR-VILLAGERS", "the villagers")], kind="crowd", move="push_in",
                        motivation="their hope is the subject")
    body = _body(text)
    assert _camera_sentences(body) == ["The camera pushes in slowly, because their hope is the subject."]
    _assert_time_pointed(body)
    assert not _lint_codes(res), _lint_codes(res)


def test_example5_close_up_locked_and_shake_wording():
    text, res, _ = _one([_member("CHAR-DEVAKI", "Devaki")], motivation="her face carries the moment",
                        shake={"t": 3.0, "dur": 0.5})
    body = _body(text)
    cams = _camera_sentences(body)
    assert len(cams) == 1 and cams[0].startswith("The camera stays locked, because her face carries the moment")
    assert "a short shake at second 3" in cams[0]
    assert "Devaki keeps their lips closed." in body
    assert not _lint_codes(res), _lint_codes(res)


# ---------- unit rules ----------

def _directives(n=8):
    return [{"t0": float(i), "t1": float(i + 1), "action_pose_expression": f"Raj does thing {i}",
             "camera": "slow push in", "audio_cue": "x"} for i in range(n)]


def test_stage_time_points_pass_tg01():
    out, _ = v._stages(_directives(), 175, "S", [], 0, time_points=True)
    sentences = [out[k] for k in v.STAGE_NAMES]
    assert sentences[0].startswith("At second 0, ")
    assert sentences[6].startswith("By second ")
    for s in sentences:
        assert re.match(r"(At|By) second \d+(\.5)?, ", s), s
        assert not [p for p in prompt_lock_problems(s + "\noverall_soundscape: x.\n") if p[0] == "TG-01"]
    pts = [float(re.match(r"(?:At|By) second ([\d.]+)", s).group(1)) for s in sentences]
    assert pts == sorted(pts)


def test_stage_time_point_comes_from_a_beat_when_the_sheet_has_beats():
    beats = [{"t": 0.0, "label": "A", "action": "a", "physics": "p", "primary": False},
             {"t": 2.5, "label": "B", "action": "b", "physics": "p", "primary": True}]
    out, _ = v._stages(_directives(), 175, "S", [], 0, beats=beats, time_points=True)
    assert any(s.startswith("At second 2.5, ") for s in out.values())


def test_one_camera_sentence_from_enum_and_locked_default():
    cam = v._camera_from_sheet({"schema": "blocking/1.1", "camera": {"mode": "move", "move": "pan_left",
                                "motivation": "follow her gaze", "shake": None}}, 0)
    assert cam["compiled_clause"] == "The camera pans left slowly, because follow her gaze."
    assert cam["motion_type"] == "Pan Left"
    cam = v._camera_from_sheet({"schema": "blocking/1.1", "camera": {"mode": "fixed", "move": None,
                                "motivation": None, "shake": {"t": 1.25, "dur": 1.0}}}, 0)
    assert cam["compiled_clause"] == "The camera stays locked; a short shake at second 1.2."
    assert cam["motion_type"] == "Static Shot"


def test_hold_emits_does_not_move():
    d = _directives(2)   # two directives for seven stages: the empty stages hold
    out, _ = v._stages(d, 175, "S", [], 0, hold_names=["Raj", "Sati"])
    holds = [s for s in out.values() if "does not move" in s]
    assert holds, out
    assert all("Raj does not move" in s and "Sati does not move" in s for s in holds)
    assert not any("part" in s and "of 7" in s for s in out.values())
    assert len(set(out.values())) == 7   # duplicate guard: every sentence stays unique


def test_hold_without_cast_names_still_unique_and_no_placeholder():
    out, _ = v._stages(_directives(2), 175, "S", [], 0)
    assert len(set(out.values())) == 7
    assert not any("of 7" in s for s in out.values())


def test_linter_flags_two_camera_sentences_and_a_range():
    text, res, shot = _one([_member("CHAR-DEVAKI", "Devaki")])
    story = copy.deepcopy(res["story"])
    sh = story["episodes"][0]["shots"][0]
    sh["motion_7_stage"]["2_anticipation"] = "At second 1-2, Devaki breathes. The camera pushes in."
    errs = lint_story(story, asset_root_override=".")["errors"]
    assert any("CM-05" in e for e in errs)
    assert any("TP-02" in e for e in errs)


def test_chain_continuation_routes_to_s_and_needs_the_flag():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "director"))
    import shot_router
    sheets = {S1: _sheet(S1, [_member("CHAR-KRISHNA", "Krishna")], cut="match"),
              S2: _sheet(S2, [_member("CHAR-KRISHNA", "Krishna")], chain_from=S1)}
    lock = {"shots": [{"id": S1, "pixel_frames": 175, "edit_frames": 175}, {"id": S2, "pixel_frames": 175,
                                                                           "edit_frames": 175}]}
    routes = shot_router.plan_from_blocking(sheets, lock, allow_s=True)
    assert routes[S2]["route"] == "S"
    with pytest.raises(shot_router.RouterError, match="chain_from"):
        shot_router.plan_from_blocking(sheets, lock, allow_s=False)


def test_lint_story_lints_an_s_row_chosen_only_by_the_routes_file(tmp_path):
    from h3.tests.synth import build_story
    story = build_story(str(tmp_path))
    shot = story["episodes"][0]["shots"][0]
    sid = shot["shot_id"]
    s_prompt = compile_fl2va_prompt(shot, story["registry"], start_only=True)["compiled_prompt"]
    # the story still carries picture_2; only the routes file says S, and the prompt on hand is the start-only one
    plain = [e for e in lint_story(story, compiled={sid: s_prompt})["errors"] if sid in e and "PR-01" in e]
    routed = lint_story(story, compiled={sid: s_prompt}, routes={sid: {"image_prompt_type": "S"}})["errors"]
    assert plain, "without the routes file the start-only prompt must not fit the two-picture layout"
    assert not [e for e in routed if sid in e and "PR-01" in e], routed


def test_unknown_camera_move_falls_back_to_locked_instead_of_keyerror():
    # M-31: blocking.validate reports the bad enum, but conversion must not crash on it
    cam = v._camera_from_sheet({"schema": "blocking/1.1", "camera": {"mode": "move", "move": "spin_wildly"}}, 0)
    assert cam["compiled_clause"] == "The camera stays locked."
