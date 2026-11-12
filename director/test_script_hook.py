"""Tests for director.script_hook (J9a: first-3-seconds hook inspection). Written test-first."""

from __future__ import annotations

import copy

import pytest

import script_hook

# Known-GOOD first shot per language. Hand arithmetic for each:
#   en: event t=0.4 (<=1.0, H1 ok); first line start 0.3 (<=0.6, H2 ok);
#       "Who can stop the curse?" = 5 words (<=8, H4 ok); "Who"/"can" question words, "?" and "curse" (H3 ok);
#       not an opener (H5 ok); action "Archer stands by the river" has listed noun "river" (H6 ok).
#       score 100, pass True.
#   hi: "यह श्राप कौन तोड़ेगा" = 4 words (<=6, H4 ok); stakes "श्राप" and question "कौन" (H3 ok);
#       not an opener (H5 ok); action "राजा नदी के किनारे खड़ा है" has listed noun "नदी" (H6 ok). score 100.
#   mr: "हा शाप कोण तोडेल" = 4 words (<=6, H4 ok); stakes "शाप" and question "कोण" (H3 ok);
#       not an opener (H5 ok); action "राजा नदी काठी उभा आहे" has listed noun "नदी" (H6 ok). score 100.
GOOD = {
    "en": {"action": "Archer stands by the river", "text": "Who can stop the curse?"},
    "hi": {"action": "राजा नदी के किनारे खड़ा है", "text": "यह श्राप कौन तोड़ेगा"},
    "mr": {"action": "राजा नदी काठी उभा आहे", "text": "हा शाप कोण तोडेल"},
}


def _good_hook(lang="en"):
    """The one shared helper: a known-GOOD reel of one shot. Failing variants change one thing."""
    good = GOOD[lang]
    return [
        {
            "id": "s1",
            "seconds": 5.0,
            "action": good["action"],
            "events": [{"t": 0.4, "what": "flash"}],
            "lines": [{"speaker": "narrator", "text": good["text"], "start_s": 0.3, "end_s": 2.0}],
        }
    ]


def _has(items, code):
    """True when some hard-fail / reason / rewrite entry mentions the rule code (e.g. 'H1')."""
    return any(code in item for item in items)


def test_good_hook_passes_en():
    # Good hook, unchanged: 100 - 0 = 100, no fails, pass True.
    result = script_hook.inspect_hook(_good_hook("en"), "en")
    assert result["pass"] is True
    assert result["score"] == 100
    assert result["hard_fails"] == []
    assert result["reasons"] == []
    assert result["rewrites"] == []


def test_no_event_before_2_0_fails_h1():
    # Event moved to t=2.5 (> 2.0 = HOOK_WINDOW_S): H1 hard -40 -> score 60. Line still at 0.3 and a question.
    shots = _good_hook("en")
    shots[0]["events"] = [{"t": 2.5, "what": "flash"}]
    result = script_hook.inspect_hook(shots, "en")
    assert result["pass"] is False
    assert _has(result["hard_fails"], "H1")
    assert result["score"] == 60


def test_first_line_at_1_2_fails_h2():
    # First voiced word moved to 1.2 (> 1.0): H2 hard -40 -> score 60. Event at 0.4 still ok (H1 ok).
    shots = _good_hook("en")
    shots[0]["lines"][0]["start_s"] = 1.2
    result = script_hook.inspect_hook(shots, "en")
    assert result["pass"] is False
    assert _has(result["hard_fails"], "H2")
    assert result["score"] == 60


def test_once_upon_a_time_fails_h5():
    # Line "Once upon a time there was a king" = 8 words (H4 ok); no stakes/question (H3 soft -15);
    # opener "once upon" (H5 hard -40). Score 100 - 40 - 15 = 45, pass False.
    shots = _good_hook("en")
    shots[0]["lines"][0]["text"] = "Once upon a time there was a king"
    result = script_hook.inspect_hook(shots, "en")
    assert result["pass"] is False
    assert _has(result["hard_fails"], "H5")
    assert result["score"] == 45


def test_hi_opener_fails_h5():
    # Line "एक समय की बात है" = 5 words (<=6 ok); no stakes/question (H3 -15); opener "एक समय की बात" (H5 -40).
    # Score 100 - 40 - 15 = 45, pass False. Action has listed noun नदी (H6 ok).
    shots = _good_hook("hi")
    shots[0]["lines"][0]["text"] = "एक समय की बात है"
    result = script_hook.inspect_hook(shots, "hi")
    assert result["pass"] is False
    assert _has(result["hard_fails"], "H5")
    assert result["score"] == 45


def test_mr_opener_fails_h5():
    # Line "एकेकाळी एक राजा होता" = 4 words (<=6 ok); no stakes/question (H3 -15); opener "एकेकाळी" (H5 -40).
    # Score 100 - 40 - 15 = 45, pass False. Action has listed noun नदी (H6 ok).
    shots = _good_hook("mr")
    shots[0]["lines"][0]["text"] = "एकेकाळी एक राजा होता"
    result = script_hook.inspect_hook(shots, "mr")
    assert result["pass"] is False
    assert _has(result["hard_fails"], "H5")
    assert result["score"] == 45


def test_ten_word_english_line_loses_15():
    # "Who dares to wake the great Lord Shiva from meditation" = 10 words, counted: Who1 dares2 to3 wake4 the5
    # great6 Lord7 Shiva8 from9 meditation10. H4 soft -15 -> score 85. H3 ok ("Who"). Pass True (85 >= 70).
    shots = _good_hook("en")
    shots[0]["lines"][0]["text"] = "Who dares to wake the great Lord Shiva from meditation"
    result = script_hook.inspect_hook(shots, "en")
    assert result["pass"] is True
    assert result["score"] == 85
    assert result["hard_fails"] == []


def test_no_stakes_and_no_question_loses_15():
    # "The sun rises over the hills" = 6 words (H4 ok); no stakes word, no '?', no question word -> H3 soft -15.
    # Score 85, pass True.
    shots = _good_hook("en")
    shots[0]["lines"][0]["text"] = "The sun rises over the hills"
    result = script_hook.inspect_hook(shots, "en")
    assert result["pass"] is True
    assert result["score"] == 85
    assert result["hard_fails"] == []


def test_no_concrete_subject_loses_15():
    # Action "It moves quickly now": first word "It" is not counted; no capitalised word after it;
    # no listed noun -> H6 soft -15. Score 85, pass True.
    shots = _good_hook("en")
    shots[0]["action"] = "It moves quickly now"
    result = script_hook.inspect_hook(shots, "en")
    assert result["pass"] is True
    assert result["score"] == 85


def test_each_failure_has_reason_and_rewrite():
    # 10-word line variant (from above): one soft fail H4 -> exactly 1 reason and exactly 1 rewrite, both non-empty.
    shots = _good_hook("en")
    shots[0]["lines"][0]["text"] = "Who dares to wake the great Lord Shiva from meditation"
    result = script_hook.inspect_hook(shots, "en")
    assert len(result["reasons"]) == 1
    assert len(result["rewrites"]) == 1
    assert result["reasons"][0].strip() != ""
    assert result["rewrites"][0].strip() != ""


def test_all_three_languages_good_hook():
    # Each good hook computed above: score 100, pass True.
    for lang in ("en", "hi", "mr"):
        result = script_hook.inspect_hook(_good_hook(lang), lang)
        assert result["pass"] is True, lang
        assert result["score"] == 100, lang
        assert result["hard_fails"] == [], lang


def test_inspect_hook_is_deterministic():
    # Same input twice gives equal results, for a passing and a failing hook.
    good = _good_hook("en")
    bad = _good_hook("en")
    bad[0]["events"] = [{"t": 1.5, "what": "flash"}]
    assert script_hook.inspect_hook(good, "en") == script_hook.inspect_hook(good, "en")
    assert script_hook.inspect_hook(bad, "en") == script_hook.inspect_hook(bad, "en")


def test_inspect_hook_does_not_mutate_inputs():
    shots = _good_hook("en")
    shots[0]["lines"][0]["text"] = "Once upon a time there was a king"
    before = copy.deepcopy(shots)
    script_hook.inspect_hook(shots, "en")
    assert shots == before


def test_empty_shots_raises_value_error():
    with pytest.raises(ValueError):
        script_hook.inspect_hook([], "en")


def test_missing_key_raises_value_error():
    shots = _good_hook("en")
    del shots[0]["events"]
    with pytest.raises(ValueError):
        script_hook.inspect_hook(shots, "en")


def test_unsupported_language_raises_value_error():
    with pytest.raises(ValueError):
        script_hook.inspect_hook(_good_hook("en"), "fr")


def test_public_constants_match_spec():
    assert script_hook.HOOK_WINDOW_S == 2.0
    assert script_hook.MAX_FIRST_LINE_WORDS == {"en": 8, "hi": 6, "mr": 6}


def test_missing_key_message_names_the_key():
    # observer 5: the ValueError must name the missing key
    shots = _good_hook("en")
    del shots[0]["events"]
    with pytest.raises(ValueError, match="events"):
        script_hook.inspect_hook(shots, "en")


def test_public_word_lists_match_spec():
    # observer 5: OPENERS, STAKES_WORDS and QUESTION_WORDS are checked against the spec
    assert script_hook.OPENERS["en"] == (
        "once upon", "in ancient", "long ago", "in the beginning", "this is the story", "it was a time",
    )
    assert script_hook.OPENERS["hi"] == ("एक समय की बात", "प्राचीन काल", "बहुत समय पहले", "एक बार की बात", "यह कहानी")
    assert script_hook.OPENERS["mr"] == ("एकेकाळी", "खूप वर्षांपूर्वी", "प्राचीन काळी", "ही गोष्ट", "एका काळी")
    assert script_hook.STAKES_WORDS["en"] == (
        "dies", "die", "curse", "cursed", "fails", "fail", "war", "lost", "burn", "burns",
        "destroy", "never", "kill", "trap", "fear", "danger", "secret", "only",
    )
    assert len(script_hook.STAKES_WORDS["hi"]) >= 8
    assert len(script_hook.STAKES_WORDS["mr"]) >= 8
    assert "कभी नहीं" in script_hook.STAKES_WORDS["hi"]
    assert "कधीच नाही" in script_hook.STAKES_WORDS["mr"]
    assert script_hook.QUESTION_WORDS["en"] == ("what", "why", "how", "who", "can")
    assert script_hook.QUESTION_WORDS["hi"] == ("क्या", "क्यों", "कैसे", "कौन")
    assert script_hook.QUESTION_WORDS["mr"] == ("काय", "का", "कसे", "कोण")


def test_multiword_hi_stakes_phrase_matches_consecutive_tokens():
    # observer 7 (TEST_FINDINGS codex): "कभी नहीं" is a phrase; it must avoid H3
    shots = _good_hook("hi")
    shots[0]["lines"][0]["text"] = "कभी नहीं"
    result = script_hook.inspect_hook(shots, "hi")
    assert not _has(result["reasons"], "H3")
    assert result["score"] == 100


def test_multiword_mr_stakes_phrase_matches_consecutive_tokens():
    # observer 7 (TEST_FINDINGS codex): "कधीच नाही" is a phrase; it must avoid H3
    shots = _good_hook("mr")
    shots[0]["lines"][0]["text"] = "कधीच नाही"
    result = script_hook.inspect_hook(shots, "mr")
    assert not _has(result["reasons"], "H3")
    assert result["score"] == 100


def test_stakes_phrase_first_half_alone_does_not_match():
    # observer 7: "कभी" alone is not the phrase "कभी नहीं", so H3 (-15) still fires: 85
    shots = _good_hook("hi")
    shots[0]["lines"][0]["text"] = "कभी"
    result = script_hook.inspect_hook(shots, "hi")
    assert _has(result["reasons"], "H3")
    assert result["score"] == 85


@pytest.mark.parametrize("code", ["H1", "H2", "H3", "H4", "H5", "H6"])
def test_each_rule_failure_has_coded_reason_and_rewrite(code):
    # observer 7 (TEST_FINDINGS codex): every rule, not only H4, gives its coded reason and a rewrite
    shots = _good_hook("en")
    if code == "H1":
        shots[0]["events"] = [{"t": 2.5, "what": "flash"}]
    elif code == "H2":
        shots[0]["lines"][0]["start_s"] = 1.2
    elif code == "H3":
        shots[0]["lines"][0]["text"] = "The sun rises over the hills"
    elif code == "H4":
        shots[0]["lines"][0]["text"] = "Who dares to wake the great Lord Shiva from meditation"
    elif code == "H5":
        shots[0]["lines"][0]["text"] = "Once upon a time there was a king"
    else:
        shots[0]["action"] = "It moves quickly now"
    result = script_hook.inspect_hook(shots, "en")
    assert any(item.startswith(code + ": ") for item in result["reasons"])
    assert len(result["rewrites"]) == len(result["reasons"])
    assert all(text.strip() for text in result["rewrites"])


def test_no_first_line_hard_fail():
    # No spoken line in the first shot: H2 hard -40. H1 ok (event 0.4), H6 ok ("river"); H3/H4/H5 skip (no line).
    # Score 100 - 40 = 60, pass False.
    shots = _good_hook("en")
    shots[0]["lines"] = []
    result = script_hook.inspect_hook(shots, "en")
    assert result["pass"] is False
    assert "H2: no spoken line in the first shot" in result["hard_fails"]
    assert result["score"] == 60


def test_event_without_t_raises():
    # Event with no t: validate_shots raises ValueError naming shot id "s1".
    shots = _good_hook("en")
    shots[0]["events"] = [{"what": "flash"}]
    with pytest.raises(ValueError, match="s1"):
        script_hook.validate_shots(shots)


def test_non_dict_event_raises():
    shots = _good_hook("en")
    shots[0]["events"] = ["flash"]
    with pytest.raises(ValueError):
        script_hook.validate_shots(shots)


def test_it_was_a_timeline_not_opener():
    # "It was a timeline of kings": starts with the string "it was a time" but the token is "timeline", not "time".
    # Not an opener, so no H5. 6 words (H4 ok); no stakes/question (H3 -15); action ok. Score 85, pass True.
    shots = _good_hook("en")
    shots[0]["lines"][0]["text"] = "It was a timeline of kings"
    result = script_hook.inspect_hook(shots, "en")
    assert not _has(result["hard_fails"], "H5")
    assert script_hook._is_opener("It was a timeline of kings", "en") is False
    assert result["score"] == 85


def test_once_upon_a_time_is_opener():
    # "Once upon a time there was a king": tokens start with "once upon", so it is an opener (H5 -40).
    assert script_hook._is_opener("Once upon a time there was a king", "en") is True
    shots = _good_hook("en")
    shots[0]["lines"][0]["text"] = "Once upon a time there was a king"
    result = script_hook.inspect_hook(shots, "en")
    assert _has(result["hard_fails"], "H5")
    assert result["score"] == 45


# M-08 (CHANGE_PLAN D-06 / T-03): 2.0 s visual hook window, scale_tableau exemption, narrated shot 1 must not be none.

def test_hook_window_2s_event_at_1_9_passes_h1():
    shots = _good_hook("en")
    shots[0]["events"] = [{"t": 1.9, "what": "flash"}]
    result = script_hook.inspect_hook(shots, "en")
    assert not _has(result["hard_fails"], "H1")


def test_hook_window_2s_event_at_2_1_fails_h1():
    shots = _good_hook("en")
    shots[0]["events"] = [{"t": 2.1, "what": "flash"}]
    result = script_hook.inspect_hook(shots, "en")
    assert _has(result["hard_fails"], "H1")


def test_scale_tableau_exempt_from_h1():
    # Frame 0 extreme scale contrast is the visual hook itself: no event needed within 2.0 s.
    shots = _good_hook("en")
    shots[0]["hook_type"] = "scale_tableau"
    shots[0]["events"] = []
    result = script_hook.inspect_hook(shots, "en")
    assert not _has(result["hard_fails"], "H1")
    assert not _has(result["reasons"], "H1")
    assert result["pass"] is True


def test_other_hook_types_are_not_exempt_from_h1():
    shots = _good_hook("en")
    shots[0]["hook_type"] = "kinetic"
    shots[0]["events"] = []
    result = script_hook.inspect_hook(shots, "en")
    assert _has(result["hard_fails"], "H1")


def test_hook_type_none_refused_for_narrated_shot1():
    shots = _good_hook("en")
    shots[0]["hook_type"] = "none"
    result = script_hook.inspect_hook(shots, "en")
    assert result["pass"] is False
    assert _has(result["hard_fails"], "H0")


def test_hook_type_none_allowed_for_showcase_reel():
    # Showcase use (narrated=False): the hook rule is optional, so none is not refused and H1 is skipped.
    shots = _good_hook("en")
    shots[0]["hook_type"] = "none"
    shots[0]["events"] = []
    result = script_hook.inspect_hook(shots, "en", narrated=False)
    assert not _has(result["hard_fails"], "H0")
    assert not _has(result["hard_fails"], "H1")


def test_first_voiced_word_band_0_3_to_1_0():
    for start, expect_fail in ((0.2, True), (0.3, False), (1.0, False), (1.2, True)):
        shots = _good_hook("en")
        shots[0]["lines"][0]["start_s"] = start
        result = script_hook.inspect_hook(shots, "en")
        assert _has(result["hard_fails"], "H2") is expect_fail, start
