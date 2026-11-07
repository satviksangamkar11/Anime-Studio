"""core/caption_cues.py: spoken-script reader, the one script validator, and the hook policy (owner brief 2026-11-07)."""
import pytest

from core import caption_cues as cc
from core import caption_export as cx

TEXT = {"en": "Krishna jumps into the river.", "hi": "कृष्ण यमुना में कूद पड़ा।", "mr": "कृष्ण यमुनेत उडी मारतो."}


def shot(**track):
    return {"audio_and_dialogue_track": track}


def test_parse_time_range_forms_and_errors():
    assert cc.parse_time_range([0.5, 1.5]) == (0.5, 1.5)
    assert cc.parse_time_range("1.2-1.6s") == (1.2, 1.6)
    assert cc.parse_time_range("1.2–1.6s") == (1.2, 1.6)
    for bad in ("x", [1, 1], [2, 1], None, [1], "3-2"):
        with pytest.raises(ValueError):
            cc.parse_time_range(bad)


def test_spoken_cues_pick_the_language_and_shift_to_the_reel_clock():
    shots = [shot(narration_by_lang={lang: {"text": t, "time_range": [0.2, 1.8]} for lang, t in TEXT.items()}),
             shot(narration_by_lang={lang: {"text": t + "!", "time_range": [0.0, 1.0]} for lang, t in TEXT.items()})]
    cues = cc.spoken_cues(shots, [0.0, 2.0], "hi")
    assert [(c["t0"], c["t1"], c["kind"]) for c in cues] == [(0.2, 1.8, "spoken"), (2.0, 3.0, "spoken")]
    assert cues[0]["text"] == TEXT["hi"]


def test_captions_by_lang_wins_and_dialogue_is_captioned():
    s = shot(narration_by_lang={"en": {"text": "narration", "time_range": [0, 1]}},
             dialogue_by_lang={"en": [{"text": "line", "time_range": "1.0-2.0s"}]},
             captions_by_lang={"en": {"text": "override", "time_range": [0, 2]}})
    assert [c["text"] for c in cc.spoken_cues([s], [0.0], "en")] == ["override"]
    s = shot(narration_by_lang={"en": {"text": "narration", "time_range": [0, 1]}},
             dialogue_by_lang={"en": [{"text": "line", "time_range": "1.0-2.0s"}]})
    assert [c["text"] for c in cc.spoken_cues([s], [0.0], "en")] == ["narration", "line"]


def test_single_language_shot_serves_only_its_language():
    s = shot(narration={"language": "hi", "text": TEXT["hi"], "time_range": [0, 1]})
    assert cc.spoken_cues([s], [0.0], "hi") and cc.spoken_cues([s], [0.0], "en") == []


@pytest.mark.parametrize("lang,text,bad", [("en", TEXT["hi"], True), ("en", TEXT["en"], False),
                                           ("hi", "Krishna jumps", True), ("hi", TEXT["hi"], False),
                                           ("mr", "Krishna", True), ("mr", TEXT["mr"], False),
                                           ("hi", "कृष्ण is here", False), ("hi", "123 !", False)])
def test_script_validator(lang, text, bad):
    assert bool(cc.script_problems([{"text": text}], lang)) is bad


def test_validator_ignores_junk_and_limits_messages():
    assert cc.script_problems([None, {"text": None}, {"text": " "}, "x"], "en") == []
    many = [{"text": TEXT["hi"]}] * 9
    assert len(cc.script_problems(many, "en")) == 3


def spoken(*items):
    return [{"t0": a, "t1": b, "text": t, "kind": "spoken"} for a, b, t in items]


def test_hook_alone_when_no_spoken_script():
    cues, ents = cc.build_cue_list([], "Why is he blue?", hook_end=3.0)
    assert cues == [{"t0": 0.0, "t1": 3.0, "text": "Why is he blue?", "kind": "hook"}] and ents == []


def test_hook_window_runs_until_the_first_spoken_cue():          # rule 1
    cues, _ = cc.build_cue_list(spoken((1.5, 3.0, "line one")), "Hook words")
    assert [(c["kind"], c["t0"], c["t1"]) for c in cues] == [("hook", 0.0, 1.5), ("spoken", 1.5, 3.0)]


def test_explicit_hook_duration_shortens_the_window():          # rule 1, the shorter wins
    cues, _ = cc.build_cue_list(spoken((2.0, 3.0, "line")), "Hook", hook_duration=1.0)
    assert cues[0]["t1"] == 1.0
    cues, _ = cc.build_cue_list(spoken((0.8, 3.0, "line")), "Hook", hook_duration=1.0)
    assert cues[0]["t1"] == 0.8


def test_hook_equal_to_the_first_spoken_line_is_burned_once():  # rule 3
    cues, _ = cc.build_cue_list(spoken((0.0, 2.0, "Why is he blue?")), "  why is   he blue? ")
    assert [c["kind"] for c in cues] == ["spoken"]


def test_hook_with_no_window_warns_and_is_not_burned():
    cues, ents = cc.build_cue_list(spoken((0.0, 2.0, "line")), "Other hook")
    assert [c["kind"] for c in cues] == ["spoken"] and ents and ents[0]["level"] == "WARN"


def test_hook_is_the_first_cue_in_srt_and_vtt():                 # rule 4
    cues, _ = cc.build_cue_list(spoken((1.0, 2.0, "line")), "Hook words")
    srt, _ = cx.to_srt(cues)
    vtt, _ = cx.to_vtt(cues)
    assert srt.splitlines()[2] == "Hook words" and vtt.splitlines()[3] == "Hook words"
    cues, _ = cc.build_cue_list(spoken((0.0, 2.0, "Same")), "Same")
    assert cx.to_srt(cues)[0].count("Same") == 1


def test_no_hook_text_returns_the_spoken_cues_sorted():
    cues, _ = cc.build_cue_list(spoken((3, 4, "b"), (1, 2, "a")), None)
    assert [c["text"] for c in cues] == ["a", "b"]


def test_hook_of_prefers_the_language_caption_and_tolerates_junk():
    s = {"metadata": {"look": {"hook": {"caption": "fallback", "caption_by_lang": {"hi": "हुक"}, "duration_s": 1.5}}}}
    assert cc.hook_of(s, "hi") == ("हुक", 1.5)
    assert cc.hook_of(s, "en") == ("fallback", 1.5) and cc.hook_of(s) == ("fallback", 1.5)
    for junk in (None, {}, {"metadata": 1}, {"metadata": {"look": {"hook": "x"}}}, {"metadata": {"look": {"hook": {"caption": 5}}}}):
        assert cc.hook_of(junk, "en") == (None, None)


def test_junk_tracks_and_cues_never_raise():            # review round 8: Super VL and Dots
    junk = [{"audio_and_dialogue_track": {"captions_by_lang": ["x"], "narration_by_lang": {"en": {"text": "ok", "time_range": [0, 1]}}}},
            {"audio_and_dialogue_track": {"dialogue_by_lang": {"en": "text"}, "narration_by_lang": {"en": "n"}}},
            {"audio_and_dialogue_track": {"dialogue_by_lang": {"en": ["bad", {"text": "good", "time_range": [1, 2]}]}}},
            {"audio_and_dialogue_track": {"narration": "string"}}, {"audio_and_dialogue_track": []}, "not a shot", None]
    got = cc.spoken_cues(junk, [0.0] * len(junk), "en")
    assert [c["text"] for c in got] == ["ok", "good"]
    cues, ents = cc.build_cue_list([{"t0": 1, "t1": 2, "text": "fine"}, {"t0": None, "t1": 2, "text": "x"}, "junk", {"text": "no times"}], "Hook")
    assert [c["text"] for c in cues] == ["Hook", "fine"] and any("malformed" in e["message"] for e in ents)
