"""Round-3 regression (triage R3-DIR): a *_by_lang block whose language label differs from its key is an ML-01 error."""
import pack_validator as pv


def _row(hi_label):
    return {"id": "S1", "episode": 1, "duration": 5,
            "audio_and_dialogue_track": {"narration_by_lang": {
                "en": {"text": "Hi there.", "time_range": [0, 2], "language": "en"},
                "hi": {"text": "नमस्ते", "time_range": [0, 2], "language": hi_label}}}}


def _ml01(label):
    errs = []
    pv._check_languages([_row(label)], ["en", "hi"], None, errs)
    return [e for e in errs if e["code"] == "ML-01" and e["where"].endswith(".language")]


def test_wrong_language_label_on_a_narration_block_is_flagged():
    assert len(_ml01("en")) == 1


def test_matching_language_label_is_not_flagged():
    assert _ml01("hi") == []
