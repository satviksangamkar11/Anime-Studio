"""English H3 voice mode (voice_engine en=h3): pure rules and the linter/compiler on a voice story. Offline, no model."""
import copy

import pytest

from h3 import voice_engine as ve
from h3.compile_h3_sing8 import compile_fl2va_prompt
from h3.schema_and_linter import MOUTH_LOCK_PHRASE, MOUTH_PERSON_RE, lint_story, voice_mode
from h3.tests.synth import build_story, codes

ANCHOR = {"audio": "voice/alpha.wav", "duration_sec": 6.0, "voice_description": "a low, calm adult male voice"}
UTT = {"speaker_id": "S1", "character_id": "char_alpha", "is_offscreen_voiceover": False,
       "voiceover_action_cue": "the figure's jaw tightens", "language": "en", "text": "Hold the line.",
       "start_sec": 0.5, "end_sec": 2.5, "lip_lock_clause": ""}


def voice_story(root):
    """Synth story in English H3 voice mode. Shot A: S1 (char_alpha) speaks on screen 0.5-2.5 s, reference_audio = its anchor
    (Ref2VA). Shot B and C stay silent."""
    story = build_story(root)
    reg = story["registry"]
    reg["voice_engine"] = {"en": "h3", "hi": "elevenlabs", "mr": "elevenlabs"}
    reg["characters"]["char_alpha"]["voice_anchor"] = copy.deepcopy(ANCHOR)
    reg["voice_speaker_map"] = {"S1": "char_alpha"}
    a = story["episodes"][0]["shots"][0]
    a["fl2va_keyframes"]["reference_audio"] = ["char_alpha"]
    a["dialogue_and_lip_lock"] = {
        "has_dialogue": True, "utterances": [copy.deepcopy(UTT)],
        "mouth_state_rule": "The speaker's mouth moves only while the line is spoken.",
        "narrator_mouth_closed": True,
        "mouth_state": {str(i): ("speaking" if i < 3 else "closed") for i in range(8)}}  # 175 frames = 8 seconds
    return story


def _lint(story):
    return lint_story(story)


# ---------- pure rules (h3/voice_engine.py) ----------

def test_engine_default_and_explicit_setting():
    assert ve.engine_for(None, "en") == "elevenlabs" and ve.engine_for(None, "hi") == "elevenlabs"  # Option A defaults
    assert ve.engine_for(None, "mr") == "elevenlabs"
    assert ve.engine_for({"en": "elevenlabs"}, "en") == "elevenlabs"


def test_registry_without_voice_engine_is_pure_foley():
    assert voice_mode({}) is False
    assert voice_mode({"voice_engine": {"en": "elevenlabs"}}) is False
    assert voice_mode({"voice_engine": {"en": "h3"}}) is True


def test_parse_overrides_and_bad_pairs():
    assert ve.parse_overrides("en=elevenlabs, hi=elevenlabs") == {"en": "elevenlabs", "hi": "elevenlabs"}
    assert ve.parse_overrides("") == {}
    with pytest.raises(ValueError, match="VE-02"):
        ve.parse_overrides("xx=h3")
    with pytest.raises(ValueError, match="VE-02"):
        ve.parse_overrides("en")


def test_resolve_engines_defaults_and_overrides():
    assert ve.resolve_engines(["en", "hi"]) == {"en": "elevenlabs", "hi": "elevenlabs"}
    assert ve.resolve_engines(["en"], {"en": "h3"}) == {"en": "h3"}
    assert ve.resolve_engines(["en"], {"en": "elevenlabs"}) == {"en": "elevenlabs"}


@pytest.mark.parametrize("engines, langs, expected", [
    ({"en": "elevenlabs", "hi": "elevenlabs", "mr": "elevenlabs"}, ["en", "hi", "mr"], ([], [])),   # Option A defaults
    ({"en": "h3", "hi": "elevenlabs", "mr": "elevenlabs"}, ["en", "hi", "mr"], ([], ["VE-04"])),   # off-by-default switch
    ({"hi": "h3"}, None, (["VE-01"], [])),
    ({"mr": "h3"}, ["mr"], (["VE-01"], [])),
    ({"en": "speech"}, None, (["VE-02"], [])),
    ({"de": "h3"}, None, (["VE-02"], [])),
    ({"mr": "elevenlabs"}, ["en"], (["VE-03"], [])),
    ({"en": "h3"}, ["en", "hi"], ([], ["VE-04"])),
])
def test_voice_engine_problems_codes(engines, langs, expected):
    errs, warns = ve.voice_engine_problems(engines, langs)
    assert ([c for c, _ in errs], [c for c, _ in warns]) == expected


def test_voice_map_rules():
    chars = {"CHAR-A": {}}
    ok = {"CHAR-A": {"en": "placeholder-A-en", "hi": "v-A-hi", "mr": "v-A-mr"}, "NARRATOR": {"hi": "v-N-hi", "mr": "v-N-mr"}}
    assert ve.voice_map_problems(ok, chars, ["hi", "mr"]) == []
    assert [c for c, _ in ve.voice_map_problems({"CHAR-A": {"hi": "x"}}, chars, ["hi", "mr"])] == ["VM-01"]
    assert [c for c, _ in ve.voice_map_problems({"CHAR-Z": {"hi": "x"}}, chars, ["hi"])] == ["VM-03"]
    assert [c for c, _ in ve.voice_map_problems({"CHAR-A": "x"}, chars, None)] == ["VM-03"]
    assert [c for c, _ in ve.voice_map_problems(None, chars, None)] == ["VM-03"]


def test_voice_engine_not_a_dict_is_ve02():
    assert [c for c, _ in ve.voice_engine_problems(["en"])[0]] == ["VE-02"]


def test_anchor_problems():
    assert ve.anchor_problems(copy.deepcopy(ANCHOR)) == []
    # pending form: audio not extracted yet; comes from the first approved H3 clip (UNVERIFIED timbre stability)
    pending = {"audio": None, "duration_sec": None, "source": ve.ANCHOR_SOURCE, "clip_shot_id": "SHOT-01",
               "voice_description": ANCHOR["voice_description"]}
    assert ve.anchor_problems(pending) == []
    assert {c for c, _ in ve.anchor_problems({**pending, "source": "owner_clip"})} == {"VA-03"}
    for bad in ({**ANCHOR, "duration_sec": 1.0}, {**ANCHOR, "duration_sec": 16.0}, {**ANCHOR, "duration_sec": True},
                {**ANCHOR, "voice_description": ""}, {**ANCHOR, "voice_description": "a <d> voice"},
                {**ANCHOR, "audio": " "}, None):
        assert [c for c, _ in ve.anchor_problems(bad)] == ["VA-03"], bad


def test_speaker_map_problems():
    chars = {"CHAR-A": {}, "CHAR-B": {}}
    assert ve.speaker_map_problems({"S1": "CHAR-A", "S2": "CHAR-B"}, chars) == []
    assert [c for c, _ in ve.speaker_map_problems({"1": "CHAR-A"}, chars)] == ["SP-01"]
    assert [c for c, _ in ve.speaker_map_problems({"S1": "CHAR-X"}, chars)] == ["SP-02"]
    assert [c for c, _ in ve.speaker_map_problems({"S1": "CHAR-A", "S2": "CHAR-A"}, chars)] == ["SP-03"]


def test_audio_ref_problems_count_and_total_length():
    six = dict(ANCHOR)
    assert ve.audio_ref_problems([six, six]) == []                       # 12 s total
    assert [c for c, _ in ve.audio_ref_problems([six] * 4)] == ["VA-05", "VA-06"]
    assert [c for c, _ in ve.audio_ref_problems([six] * 3)] == ["VA-06"]  # 18 s total > 15 s


# ---------- linter and compiler on a voice story ----------

def test_voice_story_lints_clean(tmp_path):
    assert _lint(voice_story(str(tmp_path))) == {"errors": [], "warnings": []}


def test_english_line_is_emitted_in_the_official_form(tmp_path):
    story = voice_story(str(tmp_path))
    text = compile_fl2va_prompt(story["episodes"][0]["shots"][0], story["registry"])["compiled_prompt"]
    assert "(S1), a low, calm adult male voice, says: <d>[English] Hold the line.</d>" in text
    assert "<Audio 1> is the voice timbre reference for S1" in text
    assert "<Audio 1>" in text and "[Shot" not in text.split("integrated")[0]  # Ref2VA, no [Shot N] tag
    assert MOUTH_LOCK_PHRASE not in text                                # a speaker is on screen: no silent-figure lock


def test_silent_shot_keeps_the_mouth_lock_in_voice_mode(tmp_path):
    # M-01b: was "MOUTH_LOCK_PHRASE in text". MO-01 is per person now: a cast member gets a mouth sentence.
    story = voice_story(str(tmp_path))
    text = compile_fl2va_prompt(story["episodes"][0]["shots"][1], story["registry"])["compiled_prompt"]
    assert MOUTH_PERSON_RE.search(text) and "<d>" not in text


def test_offscreen_voiceover_says_so_and_states_lips_closed(tmp_path):
    story = voice_story(str(tmp_path))
    u = story["episodes"][0]["shots"][0]["dialogue_and_lip_lock"]["utterances"][0]
    u["is_offscreen_voiceover"] = True
    story["episodes"][0]["shots"][0]["dialogue_and_lip_lock"]["mouth_state"] = {str(i): "closed" for i in range(8)}
    text = compile_fl2va_prompt(story["episodes"][0]["shots"][0], story["registry"])["compiled_prompt"]
    assert "says in an off-screen voiceover: <d>[English] Hold the line.</d>" in text
    assert "lips remain completely closed" in text
    assert _lint(story)["errors"] == []


def test_mouth_state_must_follow_the_on_screen_line(tmp_path):
    story = voice_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["dialogue_and_lip_lock"]["mouth_state"]["0"] = "closed"
    assert "MO-01" in codes(_lint(story)["errors"])


def test_mouth_speaking_outside_the_line_is_refused(tmp_path):
    story = voice_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["dialogue_and_lip_lock"]["mouth_state"]["6"] = "speaking"
    assert "MO-01" in codes(_lint(story)["errors"])


def test_speaker_not_in_map_is_va01(tmp_path):
    story = voice_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["dialogue_and_lip_lock"]["utterances"][0]["speaker_id"] = "S9"
    assert "VA-01" in codes(_lint(story)["errors"])


def test_speaker_mapped_to_another_character_is_va04(tmp_path):
    story = voice_story(str(tmp_path))
    story["registry"]["voice_speaker_map"] = {"S1": "char_beta"}
    assert "VA-04" in codes(_lint(story)["errors"])


def test_speaker_without_anchor_is_va01(tmp_path):
    story = voice_story(str(tmp_path))
    del story["registry"]["characters"]["char_alpha"]["voice_anchor"]
    errs = codes(_lint(story)["errors"])
    assert "VA-01" in errs


def test_speaker_anchor_must_be_referenced_by_the_shot(tmp_path):
    story = voice_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["fl2va_keyframes"]["reference_audio"] = []
    assert "VA-07" in codes(_lint(story)["errors"])


def test_more_than_three_anchors_in_one_shot_is_va05(tmp_path):
    story = voice_story(str(tmp_path))
    reg = story["registry"]
    reg["characters"]["char_beta"]["voice_anchor"] = dict(ANCHOR, audio="voice/beta.wav")
    reg["characters"]["char_gamma"] = {"short_disambiguator": "a third figure", "voice_anchor": dict(ANCHOR, audio="g.wav")}
    reg["characters"]["char_delta"] = {"short_disambiguator": "a fourth figure", "voice_anchor": dict(ANCHOR, audio="d.wav")}
    story["episodes"][0]["shots"][0]["fl2va_keyframes"]["reference_audio"] = ["char_alpha", "char_beta", "char_gamma", "char_delta"]
    assert "VA-05" in codes(_lint(story)["errors"])


def test_hindi_line_in_voice_mode_is_refused(tmp_path):
    story = voice_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["dialogue_and_lip_lock"]["utterances"][0]["language"] = "hi"
    assert "VE-06" in codes(_lint(story)["errors"])


def test_speech_tags_in_free_text_are_still_refused_in_voice_mode(tmp_path):
    story = voice_story(str(tmp_path))
    story["episodes"][0]["shots"][1]["motion_7_stage"]["4_drive"] += " He says <d>[English] stay.</d>"
    assert {"SL-02", "SL-03"} & codes(_lint(story)["errors"])          # the free-text speech pattern is refused


def test_audio_tag_without_matching_reference_is_au01(tmp_path):
    story = voice_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["motion_7_stage"]["4_drive"] += " A voice from <Audio 2> leads the turn."
    assert "AU-01" in codes(_lint(story)["errors"])


def test_pending_anchor_is_refused_when_referenced(tmp_path):
    story = voice_story(str(tmp_path))
    story["registry"]["characters"]["char_alpha"]["voice_anchor"] = {
        "audio": None, "duration_sec": None, "source": ve.ANCHOR_SOURCE, "clip_shot_id": "SYN_B",
        "voice_description": ANCHOR["voice_description"]}
    assert "VA-08" in codes(_lint(story)["errors"])                    # shot A references it, its clip is SYN_B


def test_source_shot_of_a_pending_anchor_needs_no_reference(tmp_path):
    story = voice_story(str(tmp_path))
    story["registry"]["characters"]["char_alpha"]["voice_anchor"] = {
        "audio": None, "duration_sec": None, "source": ve.ANCHOR_SOURCE, "clip_shot_id": "SYN_A",
        "voice_description": ANCHOR["voice_description"]}
    story["episodes"][0]["shots"][0]["fl2va_keyframes"]["reference_audio"] = []   # shot A is the source render
    errs = codes(_lint(story)["errors"])
    assert "VA-07" not in errs and "VA-08" not in errs


def test_pure_foley_story_still_refuses_audio_refs(tmp_path):
    story = voice_story(str(tmp_path))
    del story["registry"]["voice_engine"]          # back to pure Foley: the same shot is refused
    errs = codes(_lint(story)["errors"])
    assert "AU-01" in errs
