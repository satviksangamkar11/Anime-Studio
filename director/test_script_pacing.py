"""Tests for director.script_pacing (J9b: pacing inspection). Written test-first."""

from __future__ import annotations

import copy

import pytest

import script_pacing

LINE_TEXT = {"en": "Arjun speaks", "hi": "अर्जुन बोलता है", "mr": "अर्जुन बोलतो"}

# Known-GOOD reel: 10 shots x 7.0 s = 70 s (inside 60-75).
#   Shot starts: 0, 7, 14, 21, 28, 35, 42, 49, 56, 63.
#   Every shot has one line starting at 0.5 s (within-shot gap: none; later-shot first line 0.5 <= 2.0 ok).
#   Re-hook window 25-35 s: shot 5 starts at 28 with event t=0.4 (<=1.0 after its start, ok);
#       shot 6 starts at 35 (inclusive) with a line at 0.5 (ok).
#   Payoff: last shot (start 63, last 5 s = 65-70 s) has event t=6.0 (shot-relative, 6.0 >= 2.0, ok).
#   Result: no problems, pass True.


def _shot(shot_id, seconds, events, lines, action="Arjun walks to the temple"):
    return {"id": shot_id, "seconds": seconds, "action": action, "events": events, "lines": lines}


def _line(start_s, end_s, text="hello", speaker="narrator"):
    return {"speaker": speaker, "text": text, "start_s": start_s, "end_s": end_s}


def _good_reel(lang="en", count=10, seconds=7.0):
    """The one shared helper: a known-GOOD reel of `count` shots of `seconds` (default 7.0 s).
    Failing variants change one thing."""
    shots = []
    for i in range(count):
        events = []
        if i == 4:
            events = [{"t": 0.4, "what": "entrance"}]
        if i == count - 1:
            events = [{"t": 6.0, "what": "flash"}]
        shots.append(_shot("s%d" % (i + 1), seconds, events, [_line(0.5, 1.5, LINE_TEXT[lang])]))
    return shots


def _has_dead_air(problems):
    return any("dead air" in p for p in problems)


def test_good_reel_passes():
    # 70 s, all rules satisfied (see header): problems [], pass True.
    result = script_pacing.inspect_pacing(_good_reel("en"), "en")
    assert result["pass"] is True
    assert result["problems"] == []


def test_dead_air_of_2_1_inside_shot_is_reported():
    # Shot 1 lines: 0.5-1.5 and 3.6-4.6. Gap 3.6 - 1.5 = 2.1 > 1.5 -> dead air. Total still 70 s.
    shots = _good_reel("en")
    shots[0]["lines"] = [_line(0.5, 1.5), _line(3.6, 4.6)]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is False
    assert _has_dead_air(result["problems"])
    assert len(result["problems"]) == 1


def test_dead_air_of_exactly_1_5_is_not_reported():
    # Shot 1 lines: 0.5-1.5 and 3.0-4.0. Gap 3.0 - 1.5 = 1.5, not longer than 1.5 -> no problem. Pass True.
    shots = _good_reel("en")
    shots[0]["lines"] = [_line(0.5, 1.5), _line(3.0, 4.0)]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is True
    assert result["problems"] == []


def test_later_shot_first_line_2_5_after_start_is_reported():
    # Shot 2 starts at 7.0; its only line starts at 2.5 (shot-relative) -> 2.5 > 2.0 -> dead air. One problem.
    shots = _good_reel("en")
    shots[1]["lines"] = [_line(2.5, 3.5)]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is False
    assert _has_dead_air(result["problems"])
    assert len(result["problems"]) == 1


def test_later_shot_first_line_exactly_2_0_is_not_reported():
    # Shot 2 first line starts at 2.0 -> not longer than 2.0 -> no problem. Pass True.
    shots = _good_reel("en")
    shots[1]["lines"] = [_line(2.0, 3.0)]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is True
    assert result["problems"] == []


def test_last_shot_without_payoff_is_reported():
    # Last shot (7 s): no events; its only line starts at 0.5, not in last 5 s (2.0-7.0). One payoff problem.
    shots = _good_reel("en")
    shots[-1]["events"] = []
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is False
    assert len(result["problems"]) == 1


def test_reel_of_30_s_skips_rehook_check():
    # s1 28 s (line 0.5-1.5), s2 starts at 28 s (in 25-35 window), 2 s, event t=1.5 (not within 1.0 s of start).
    # Total 30 s < 36 s -> re-hook check skipped. Payoff: s2 last 5 s covers whole shot, event 1.5 ok.
    # Only warning: length 30 < 60. problems == [] proves no re-hook problem was added.
    shots = [
        _shot("s1", 28.0, [], [_line(0.5, 1.5)]),
        _shot("s2", 2.0, [{"t": 1.5, "what": "cut"}], []),
    ]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is True
    assert result["problems"] == []
    assert len(result["warnings"]) == 1


def test_reel_shorter_than_60_s_gives_length_warning():
    # 8 shots x 7 s = 56 s. Re-hook window shots (28, 35) still ok; payoff event in last shot ok. Only length warning.
    result = script_pacing.inspect_pacing(_good_reel("en", count=8), "en")
    assert result["pass"] is True
    assert result["problems"] == []
    assert len(result["warnings"]) == 1


def test_reel_longer_than_75_s_gives_length_warning():
    # 11 shots x 7 s = 77 s. Window shots (28, 35) ok; payoff event in last shot ok. Only length warning.
    result = script_pacing.inspect_pacing(_good_reel("en", count=11), "en")
    assert result["pass"] is True
    assert result["problems"] == []
    assert len(result["warnings"]) == 1


def test_spec_example_1_passes():
    # s1 30 s (line 0.0-1.0 "hi"); s2 40 s starts at 30, event t=0.4 (re-hook ok), event t=38.0 (last 5 s = 35-40, ok).
    # Total 70 s. pass True, problems [].
    shots = [
        _shot("s1", 33.0, [], [_line(0.0, 1.0, "hi")]),
        _shot("s2", 40.0, [{"t": 0.4, "what": "entrance"}, {"t": 38.0, "what": "flash"}], []),
    ]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is True
    assert result["problems"] == []


def test_spec_example_2_one_rehook_problem():
    # As example 1 but the t=0.4 event removed. Total 73 s: window 0.45-0.60 = 32.85-43.8 s; s2 starts at 33
    # (inside), no event or line within 1.0 s of start. Exactly one problem (re-hook). Payoff ok at 38.0.
    shots = [
        _shot("s1", 33.0, [], [_line(0.0, 1.0, "hi")]),
        _shot("s2", 40.0, [{"t": 38.0, "what": "flash"}], []),
    ]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is False
    assert len(result["problems"]) == 1


def test_spec_example_3_single_30_s_shot():
    # s1 alone, 30 s, line 0.0-1.0, no events. Payoff: last 5 s = 25-30 s, no event,
    # line starts 0.0 -> payoff problem. Length 30 < 60 -> length problem. Re-hook skipped (30 < 36).
    # One problem (payoff) and one warning (length). None about re-hook.
    shots = [_shot("s1", 30.0, [], [_line(0.0, 1.0, "hi")])]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is False
    assert len(result["problems"]) == 1
    assert "payoff" in result["problems"][0]
    assert len(result["warnings"]) == 1


def test_spec_example_4_gap_of_exactly_1_5_passes():
    # s1 30 s, lines 0.0-1.0 "hello" and 2.5-3.5 "world": gap 1.5, not > 1.5 -> ok.
    # s2 as example 1. Total 70. Pass True.
    shots = [
        _shot("s1", 33.0, [], [_line(0.0, 1.0, "hello"), _line(2.5, 3.5, "world")]),
        _shot("s2", 40.0, [{"t": 0.4, "what": "entrance"}, {"t": 38.0, "what": "flash"}], []),
    ]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is True
    assert result["problems"] == []


def test_spec_example_5_gap_of_2_2_is_dead_air():
    # s1 10 s, lines 0.0-1.0 and 3.2-4.2: gap 3.2 - 1.0 = 2.2 > 1.5 -> dead air. Pass False.
    shots = [_shot("s1", 10.0, [], [_line(0.0, 1.0, "hello"), _line(3.2, 4.2, "world")])]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is False
    assert _has_dead_air(result["problems"])


def test_spec_example_6_later_first_line_2_5_is_dead_air():
    # s1 10 s no lines; s2 10 s, line starts 2.5 (> 2.0 after its start) -> dead air. Pass False.
    shots = [
        _shot("s1", 10.0, [], []),
        _shot("s2", 10.0, [], [_line(2.5, 3.5, "hello")]),
    ]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is False
    assert _has_dead_air(result["problems"])


def test_all_three_languages_good_reel_passes():
    for lang in ("en", "hi", "mr"):
        result = script_pacing.inspect_pacing(_good_reel(lang), lang)
        assert result["pass"] is True, lang
        assert result["problems"] == [], lang


def test_supported_langs_constant():
    assert script_pacing.SUPPORTED_LANGS == ("en", "hi", "mr")


def test_inspect_pacing_is_deterministic():
    good = _good_reel("en")
    bad = _good_reel("en")
    bad[0]["lines"] = [_line(0.5, 1.5), _line(3.6, 4.6)]
    assert script_pacing.inspect_pacing(good, "en") == script_pacing.inspect_pacing(good, "en")
    assert script_pacing.inspect_pacing(bad, "en") == script_pacing.inspect_pacing(bad, "en")


def test_inspect_pacing_does_not_mutate_inputs():
    shots = _good_reel("en")
    shots[0]["lines"] = [_line(0.5, 1.5), _line(3.6, 4.6)]
    before = copy.deepcopy(shots)
    script_pacing.inspect_pacing(shots, "en")
    assert shots == before


def test_empty_shots_raises_value_error():
    with pytest.raises(ValueError):
        script_pacing.inspect_pacing([], "en")


def test_missing_key_raises_value_error():
    shots = _good_reel("en")
    del shots[0]["lines"]
    with pytest.raises(ValueError):
        script_pacing.inspect_pacing(shots, "en")


def test_unsupported_language_raises_value_error():
    with pytest.raises(ValueError):
        script_pacing.inspect_pacing(_good_reel("en"), "fr")


def test_within_shot_gap_in_later_shot_is_reported():
    # observer 5: a within-shot gap of 2.1 s in a LATER shot (shot 3) must be reported
    shots = _good_reel("en")
    shots[2]["lines"] = [_line(0.5, 1.0), _line(3.1, 4.0)]
    result = script_pacing.inspect_pacing(shots, "en")
    assert result["pass"] is False
    assert _has_dead_air(result["problems"])
    assert any("inside shot " + shots[2]["id"] in p for p in result["problems"])


def test_ten_shot_reel_of_7_5_s_passes():
    # 10 x 7.5 s = 75.0 (upper edge, allowed). Starts: ..., 22.5, 30.0, ... Shot 5 starts at 30.0 (in 25-35)
    # with event t=0.4 (re-hook ok). Last shot starts 67.5; event t=6.0 is in its last 5 s (2.5-7.5). Pass True.
    result = script_pacing.inspect_pacing(_good_reel("en", count=10, seconds=7.5), "en")
    assert result["pass"] is True
    assert result["problems"] == []


def test_eight_shot_reel_of_7_5_s_passes():
    # 8 x 7.5 s = 60.0 (lower edge, allowed). Shot 5 starts at 30.0 (in 25-35) with event t=0.4.
    # Last shot starts 52.5; event t=6.0 is in its last 5 s (2.5-7.5). Pass True.
    result = script_pacing.inspect_pacing(_good_reel("en", count=8, seconds=7.5), "en")
    assert result["pass"] is True
    assert result["problems"] == []


def test_length_just_outside_60_and_75_gives_one_length_problem():
    # 8 x 7.4875 = 59.9 (below 60) and 10 x 7.51 = 75.1 (above 75). Re-hook and payoff still ok in both.
    # No problems; exactly one warning each, and it is the length warning.
    for shots in (
        _good_reel("en", count=8, seconds=(60.0 - 0.1) / 8),
        _good_reel("en", count=10, seconds=(75.0 + 0.1) / 10),
    ):
        result = script_pacing.inspect_pacing(shots, "en")
        assert result["pass"] is True
        assert result["problems"] == []
        assert len(result["warnings"]) == 1
        assert "length" in result["warnings"][0]


def test_58s_reel_passes_with_warning():
    # 8 x 7.25 = 58.0 (below 60, warning only). Shot 5 starts at 29.0 (in 25-35) with event t=0.4 (re-hook ok).
    # Last shot starts 50.75; event t=6.0 is in its last 5 s (2.25-7.25). Pass True, 1 warning.
    result = script_pacing.inspect_pacing(_good_reel("en", count=8, seconds=7.25), "en")
    assert result["pass"] is True
    assert result["problems"] == []
    assert len(result["warnings"]) == 1


def test_seconds_override_changes_total():
    # Script: 10 x 7.0 = 70, no warning. Override s1-s9 to 6.0 and s10 to 4.0 = 58.0 -> one length warning.
    # Override total 58 < 60 adds the warning. P2 on s10 (4.0 s): line at 0.5 is in its window (0-4), ok.
    # P3 on s6 (starts 30.0): line at 0.5 is the re-hook, ok. No problems.
    shots = _good_reel("en")
    assert script_pacing.inspect_pacing(shots, "en")["warnings"] == []
    override = {"s%d" % i: 6.0 for i in range(1, 10)}
    override["s10"] = 4.0
    result = script_pacing.inspect_pacing(shots, "en", seconds_override=override)
    assert result["pass"] is True
    assert result["problems"] == []
    assert len(result["warnings"]) == 1


def test_nested_missing_start_s_raises():
    shots = _good_reel("en")
    del shots[1]["lines"][0]["start_s"]
    with pytest.raises(ValueError):
        script_pacing.inspect_pacing(shots, "en")


# M-07 (CHANGE_PLAN T-01 / T-02): re-hook window = core.retention.rehook_window_frac x total (reels >= 36 s);
# length target comes from story.reel_target_s (optional), default window stays 60-75 s (warning only).

def _hook_reel(hook_index, count=10, seconds=10.0):
    # Every shot's first line starts at 1.5 s (no re-hook); shot `hook_index` starts its line at 0.5 s.
    shots = []
    for i in range(count):
        start = 0.5 if i == hook_index else 1.5
        events = [{"t": 6.0, "what": "flash"}] if i == count - 1 else []
        shots.append(_shot("s%d" % (i + 1), seconds, events, [_line(start, start + 1.0, LINE_TEXT["en"])]))
    return shots


def test_rehook_uses_core_fraction_default_file():
    # 100 s reel, default core.json [0.45, 0.60] -> window 45-60 s. Hook at 50 s passes, hook at 30 s is outside.
    assert script_pacing.inspect_pacing(_hook_reel(5), "en")["pass"] is True
    result = script_pacing.inspect_pacing(_hook_reel(3), "en")
    assert result["pass"] is False
    assert any("re-hook missing" in p for p in result["problems"])


def test_rehook_window_end_is_inclusive():
    # Hook at exactly 60 s (= 0.60 x 100) passes.
    assert script_pacing.inspect_pacing(_hook_reel(6), "en")["pass"] is True


def test_rehook_uses_passed_core_fraction():
    # Explicit core window [0.20, 0.30] -> 20-30 s: the hook at 30 s now passes and the one at 50 s fails.
    core = {"retention": {"rehook_window_frac": [0.20, 0.30]}}
    assert script_pacing.inspect_pacing(_hook_reel(3), "en", core=core)["pass"] is True
    assert script_pacing.inspect_pacing(_hook_reel(5), "en", core=core)["pass"] is False


def test_length_target_from_story_warns_outside_10_percent():
    # Story target 40 s, reel 70 s -> outside 36-44 s: one length warning, pass stays True.
    result = script_pacing.inspect_pacing(_good_reel("en"), "en", story={"reel_target_s": 40.0})
    assert result["pass"] is True
    assert len(result["warnings"]) == 1
    assert "length" in result["warnings"][0]


def test_length_target_from_story_no_warning_when_on_target():
    result = script_pacing.inspect_pacing(_good_reel("en"), "en", story={"reel_target_s": 70.0})
    assert result["warnings"] == []


def test_length_target_within_10_percent_no_warning():
    # Reel 76 s vs target 70 s (+8.6%): inside tolerance. Reel 80 s (+14%): warning.
    assert script_pacing.inspect_pacing(_good_reel("en", seconds=7.6), "en",
                                        story={"reel_target_s": 70.0})["warnings"] == []
    result = script_pacing.inspect_pacing(_good_reel("en", seconds=8.0), "en", story={"reel_target_s": 70.0})
    assert len(result["warnings"]) == 1


def test_story_without_target_uses_default_window():
    # No reel_target_s: default 60-75 s window applies. 40 s reel warns, 70 s reel does not.
    assert script_pacing.inspect_pacing(_good_reel("en", count=8, seconds=5.0), "en",
                                        story={"other": 1})["warnings"]
    assert script_pacing.inspect_pacing(_good_reel("en"), "en", story={"other": 1})["warnings"] == []


def test_story_target_must_be_positive_finite_number():
    for bad in (0, -5.0, True, float("nan"), "70"):
        with pytest.raises(ValueError):
            script_pacing.inspect_pacing(_good_reel("en"), "en", story={"reel_target_s": bad})


# M-31: a shot's own seconds must be a positive finite number (bad input must not pass silently)
@pytest.mark.parametrize("bad", [-1.0, 0, float("nan"), float("inf"), "7", True])
def test_bad_shot_seconds_is_refused(bad):
    reel = _good_reel("en")
    reel[3]["seconds"] = bad
    with pytest.raises(ValueError, match="seconds"):
        script_pacing.inspect_pacing(reel, "en")


def test_good_and_bad_reel_verdicts_differ():
    bad = _good_reel("en")
    bad[0]["lines"] = [_line(0.5, 1.5), _line(3.6, 4.6)]
    assert script_pacing.inspect_pacing(_good_reel("en"), "en")["pass"] is True
    assert script_pacing.inspect_pacing(bad, "en")["pass"] is False
