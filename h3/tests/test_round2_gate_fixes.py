"""Round-2 review fixes (Super VL batch r4, W3): closing-shot args from the story, payoff unknown is a warning,
scalar *_by_lang values are reported (not crashed), non-dict narration is a clear per-language error, and an
unknown voice engine fails only its own language. Offline, synthetic wavs, no ffmpeg, no model call."""
import pytest

from h3 import gate_d_audio as gd
from h3 import render_controller as rc
from h3.shot_table_spec import STRONG_HOOKS
from h3.tests.test_gate_d_audio import BGM, GATE, _codes, _run, _shot, _wav


def _story_shots():
    """Opening + closing shot for _gate_d_result (no VO files, so only the closing gate matters)."""
    op = _shot("o1", 3.0, {}, hook="reveal", is_opening_0_2s_hook=True)
    cl = _shot("c1", 3.0, {}, hook=STRONG_HOOKS[0], is_closing_hook=True)
    return [op, cl]


def _group(shots, **ep_extra):
    ep = {"episode_id": "EP_01", "shots": shots, **ep_extra}
    return {"episode": ep}


# ---- finding 1: _gate_d_result passes story_gate_checks and payoff_end_sec

def test_gate_d_result_reads_story_gate_checks_from_registry_not_fail_closed(tmp_path):
    story = {"registry": {"story_gate_checks": GATE}, "episodes": []}
    res = rc._gate_d_result(story, [_group(_story_shots())], str(tmp_path), ["en"])
    assert not any("CLOSING_NO_ANCHOR_PAYOFF" in r for r in res["reasons"]), res["reasons"]


def test_gate_d_result_missing_story_gate_checks_fails_closed_and_says_where(tmp_path):
    story = {"registry": {}, "episodes": []}
    res = rc._gate_d_result(story, [_group(_story_shots())], str(tmp_path), ["en"])
    assert res["ok"] is False
    assert any("story_gate_checks" in r and "registry" in r for r in res["reasons"]), res["reasons"]


def test_gate_d_result_passes_payoff_end_and_story_gate_from_their_sources(monkeypatch, tmp_path):
    seen = {}

    def spy(*a, **kw):
        seen.update(kw)
        return {"ok": True, "reports": {}, "languages": {}}

    monkeypatch.setattr(rc, "plan_language_outputs", spy)
    story = {"registry": {}, "episodes": [], "story_gate_checks": GATE}
    rc._gate_d_result(story, [_group(_story_shots(), payoff_end_sec=2.5)], str(tmp_path), ["en"])
    assert seen["story_gate_checks"] == GATE
    assert seen["payoff_end_sec"] == 2.5


# ---- finding 2: payoff end unknown -> warning, not CLOSING_VO_BEFORE_PAYOFF

def test_closing_vo_with_unknown_payoff_end_warns_instead_of_failing(tmp_path):
    shot = _shot("c", 5.0, {"narration": {"text": "Will you keep the lamp lit?", "language": "en",
                                          "time_range": [3.0, 4.6]},
                            "performance_notes": {"narrator_mouth_closed": True,
                                                  "mouth_state": {"3": "closed", "4": "closed"}}},
                 hook="tender", is_closing_hook=True)
    rep = gd.check_closing_shot(shot, story_gate_checks=GATE, vo_wav_path=_wav(tmp_path / "v.wav", 4.6),
                                payoff_end_sec=None)
    assert "CLOSING_VO_BEFORE_PAYOFF" not in _codes(rep)
    assert rep["ok"]
    assert any("payoff end not known, VO-after-payoff not verified" in w for w in rep["warnings"])


# ---- finding 3: scalar *_by_lang value -> TIME-01, no TypeError

@pytest.mark.parametrize("bad", [5, 2.5, True, "3.0-4.0"])
def test_scalar_by_lang_value_is_a_time01_error_not_a_crash(bad):
    shot = _shot("s1", 4.0, {"narration_by_lang": {"en": bad}})
    errs = gd.same_timing_problems([shot])
    assert [e["code"] for e in errs] == ["TIME-01"]
    assert errs[0]["where"] == "s1"


def test_list_and_dict_by_lang_values_still_work():
    tr = {"time_range": [0.0, 1.0]}
    shot = _shot("s1", 4.0, {"narration_by_lang": {"en": tr, "hi": [tr]}})
    assert gd.same_timing_problems([shot]) == []


# ---- finding 4: non-dict narration -> clear error for that language

def test_speech_items_refuses_non_dict_narration_clearly():
    with pytest.raises(ValueError, match="narration must be an object"):
        gd._speech_items({"narration": "just a string"})


def test_string_narration_fails_only_its_language(tmp_path):
    shot = _shot("s1", 3.0, {"narration_by_lang": {"en": "plain text", "hi": None}})
    out = _run(tmp_path, ["en", "hi"], shots=[shot])
    en_codes = [e["code"] for e in out["reports"]["en"]["errors"]]
    assert "PLAN-01" in en_codes
    assert any("narration must be an object" in e["message"] for e in out["reports"]["en"]["errors"])


# ---- finding 5: voice engine must be elevenlabs or h3 (h3 English only), per language

@pytest.mark.parametrize("engine,lang", [("google", "hi"), ("h3", "hi"), ("h3", "mr")])
def test_bad_voice_engine_fails_only_that_language(tmp_path, engine, lang):
    out = _run(tmp_path, ["en", lang], voice_engines={lang: engine})
    errs = out["reports"][lang]["errors"]
    assert [e["code"] for e in errs] == ["PLAN-01"], errs
    assert engine in errs[0]["message"]
    assert out["reports"]["en"]["ok"] is True, out["reports"]["en"]["errors"]
    assert out["languages"][lang]["mux_argv"] is None
