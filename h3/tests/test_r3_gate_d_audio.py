"""Round-3 regressions (triage R3-H3, gate_d_audio.py + render_controller.py): a non-object block in a shot or gate
is reported as a PLAN-01 error for that language, not raised as AttributeError out of the planner."""
import copy

import pytest

import h3.gate_d_audio as gd
from h3.render_controller import _gate_d_result
from h3.tests.test_gate_d_audio import GATE, _story, _vo_root


def _plan(tmp_path, shots, gate=GATE):
    return gd.plan_language_outputs("reel", ["en"], _vo_root(tmp_path, ["en"]), None, shots=shots,
                                    video_path="reel.mp4", video_has_audio=True,
                                    captions_dir=str(tmp_path / "c"), export_dir=str(tmp_path / "e"),
                                    story_gate_checks=gate, payoff_end_sec=None, voice_engines=None)


CASES = {
    "closing_mouth_state_is_a_string": lambda s: s[2]["audio_and_dialogue_track"]["performance_notes"].update(mouth_state="closed"),
    "dialogue_by_lang_item_is_a_string": lambda s: s[0]["audio_and_dialogue_track"].update(dialogue_by_lang={"en": ["hello"]}),
    "captions_by_lang_is_a_string": lambda s: s[0]["audio_and_dialogue_track"].update(captions_by_lang="x"),
    "audio_track_is_a_string": lambda s: s[0].update(audio_and_dialogue_track="x"),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_non_object_block_is_plan_error_not_crash(tmp_path, name):
    shots = _story(langs=["en"])
    CASES[name](shots)
    res = _plan(tmp_path, shots)
    assert res["ok"] is False
    assert "PLAN-01" in {e["code"] for e in res["reports"]["en"]["errors"]}


def test_non_object_story_gate_is_plan_error_not_crash(tmp_path):
    res = _plan(tmp_path, _story(langs=["en"]), gate=["not", "an", "object"])
    assert res["ok"] is False


def test_render_controller_gate_result_survives_attribute_error(tmp_path):
    """_gate_d_result catches the planner's failures; an AttributeError must become a problem line, not a traceback."""
    story = {"registry": {"story_gate_checks": GATE, "voice_engine": {"en": "elevenlabs"}}, "episodes": []}
    shots = _story(langs=["en"])
    shots[0]["audio_and_dialogue_track"] = "x"
    story["episodes"] = [{"episode_id": "E1", "shots": shots, "asset_root": str(tmp_path)}]
    groups = [{"episode": story["episodes"][0], "shots": shots}]
    res = _gate_d_result(story, groups, str(tmp_path / "out"), ["en"])
    assert res["ok"] is False and res["reasons"]
