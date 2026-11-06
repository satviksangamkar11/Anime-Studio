"""Voice rules of the V4 pack (voice_map for elevenlabs, anchors and speaker map for en h3). Offline."""
import copy

import pack_validator as pv

LANGS_HI = ["hi"]
CHARS = {"CHAR-A": {"short_disambiguator": "the tall figure"}}
VOICE_MAP = {"CHAR-A": {"en": "placeholder-A-en", "hi": "v-A-hi", "mr": "v-A-mr"},
             "NARRATOR": {"hi": "v-N-hi", "mr": "v-N-mr"}}
ANCHOR = {"audio": None, "duration_sec": None, "source": "first_approved_h3_clip", "clip_shot_id": "SHOT-01",
          "voice_description": "a low, calm adult male voice"}


def _row(dialogue=None, narration=None, by_lang=None, rid="SHOT-02"):
    track = {"narration": narration, "dialogue": dialogue or [], "sfx_cues": [], "performance_notes": {}}
    if by_lang is not None:
        track["dialogue_by_lang"] = by_lang
    return {"id": rid, "audio_and_dialogue_track": track}


def _run(rows, bible, engines, langs):
    errs, warns = [], []
    pv._check_voice(rows, bible, engines, langs, errs, warns)
    return [e["code"] for e in errs], [w["code"] for w in warns]


def _line(speaker, **extra):
    return {"speaker": speaker, "text": "Keep going.", "tone": "calm", "time_range": [0.5, 2.0], **extra}


def test_no_voice_setting_skips_the_voice_checks():
    assert _run([_row([_line("CHAR-Z")])], {}, None, LANGS_HI) == ([], [])


def test_elevenlabs_line_with_voice_map_entry_passes():
    bible = {"characters": CHARS, "voice_map": VOICE_MAP}
    rows = [_row([_line("CHAR-A")], narration={"text": "x", "language": "hi", "time_range": [0, 1]})]
    assert _run(rows, bible, {"hi": "elevenlabs"}, LANGS_HI) == ([], [])


def test_missing_voice_id_for_a_speaker_is_vm01():
    bible = {"characters": CHARS, "voice_map": {"CHAR-A": {"en": "x"}}}   # no hi id
    assert _run([_row([_line("CHAR-A")])], bible, {"hi": "elevenlabs"}, LANGS_HI)[0] == ["VM-01"]


def test_speaker_not_in_voice_map_is_vm01():
    bible = {"characters": CHARS, "voice_map": {}}
    assert _run([_row([_line("CHAR-A")])], bible, {"hi": "elevenlabs"}, LANGS_HI)[0] == ["VM-01"]


def test_narration_needs_the_narrator_voice_id():
    bible = {"characters": CHARS, "voice_map": {"CHAR-A": VOICE_MAP["CHAR-A"]}}
    rows = [_row(narration={"text": "x", "language": "hi", "time_range": [0, 1]})]
    assert _run(rows, bible, {"hi": "elevenlabs"}, LANGS_HI)[0] == ["VM-01"]


def test_changing_voice_id_between_shots_is_vm02():
    bible = {"characters": CHARS, "voice_map": VOICE_MAP}
    rows = [_row([_line("CHAR-A", voice_id="v-A-hi")], rid="SHOT-01"),
            _row([_line("CHAR-A", voice_id="v-OTHER")], rid="SHOT-02")]
    assert _run(rows, bible, {"hi": "elevenlabs"}, LANGS_HI)[0] == ["VM-02"]


def test_by_lang_dialogue_is_checked_per_language():
    bible = {"characters": CHARS, "voice_map": {"CHAR-A": {"hi": "v-A-hi"}}}
    rows = [_row(by_lang={"hi": [_line("CHAR-A")], "mr": [_line("CHAR-A")]})]
    assert _run(rows, bible, {"hi": "elevenlabs", "mr": "elevenlabs"}, ["hi", "mr"])[0] == ["VM-01"]


def test_en_h3_line_needs_map_anchor_and_verbatim_description():
    bible = {"characters": {"CHAR-A": {"short_disambiguator": "x", "voice_anchor": copy.deepcopy(ANCHOR)}},
             "voice_speaker_map": {"S1": "CHAR-A"}}
    good = _row([_line("S1", voice_description=ANCHOR["voice_description"])], rid="SHOT-02")
    assert _run([good], bible, {"en": "h3"}, ["en"]) == ([], [])
    assert _run([_row([_line("S9")])], bible, {"en": "h3"}, ["en"])[0] == ["VA-01"]
    assert _run([_row([_line("S1", voice_description="another voice")])], bible, {"en": "h3"}, ["en"])[0] == ["VA-02"]


def test_en_h3_narration_warns_ve05_and_en_elevenlabs_needs_voice_map():
    bible = {"characters": CHARS, "voice_map": {"CHAR-A": {"en": "x"}, "NARRATOR": {"en": "n"}}}
    rows = [_row(narration={"text": "x", "language": "en", "time_range": [0, 1]})]
    assert _run(rows, bible, {"en": "h3"}, ["en"]) == ([], ["VE-05"])
    assert _run(rows, bible, {"en": "elevenlabs"}, ["en"]) == ([], [])
