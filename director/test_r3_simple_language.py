"""Round-3 regressions (triage R3-DIR): a closing quote after the stop still splits a sentence; an unknown caption
language key is flagged LANG-02 whether the caption is strict or not, with or without a captions_by_lang block."""
import simple_language as sl


def _codes(res):
    return [f["code"] for r in res for f in r["flags"]]


def test_sentence_ending_in_a_closing_quote_is_split_before_the_length_check():
    n = sl.EN_MAX_SENTENCE_WORDS
    text = " ".join(["alpha"] * n) + ".” " + " ".join(["beta"] * n) + "."
    assert "SEN-01" not in [f["code"] for f in sl._check_en(text)]


def test_long_plain_sentence_is_still_flagged():
    n = sl.EN_MAX_SENTENCE_WORDS
    assert "SEN-01" in [f["code"] for f in sl._check_en(" ".join(["alpha"] * (2 * n)) + ".")]


def test_unknown_caption_language_is_flagged_when_a_captions_block_exists():
    shot = {"id": "S1", "audio_and_dialogue_track": {"captions_by_lang": {"en": {"text": "Hello there."}}},
            "caption": {"text": "hi", "language": "xyz"}}
    assert "LANG-02" in _codes(sl.check_shot_texts([shot], default_lang="en"))


def test_unknown_caption_language_is_flagged_without_a_captions_block():
    shot = {"id": "S1", "caption": {"text": "hi", "language": "xyz"}}
    assert "LANG-02" in _codes(sl.check_shot_texts([shot], default_lang="en"))


def test_unknown_strict_caption_language_is_still_flagged():
    shot = {"id": "S1", "audio_and_dialogue_track": {"captions_by_lang": {"xyz": {"text": "hi"}}}}
    assert "LANG-02" in _codes(sl.check_shot_texts([shot], default_lang="en"))


def test_caption_without_a_language_field_is_not_flagged_as_a_key_error():
    shot = {"id": "S1", "caption": {"text": "hi"}}
    assert "LANG-02" not in _codes(sl.check_shot_texts([shot], default_lang="en"))
