"""Audit A 11-08: the writer's captions_by_lang[lang] is a LIST of cards; spoken_cues must use them."""
from core.caption_cues import spoken_cues


def test_a_list_of_caption_cards_becomes_cues():
    shot = {"audio_and_dialogue_track": {
        "narration_by_lang": {"en": {"text": "Long narration line", "language": "en", "time_range": [0.5, 5.0]}},
        "dialogue_by_lang": {"en": []},
        "captions_by_lang": {"en": [{"text": "Short card one", "time_range": [0.5, 2.0]}, {"text": "Card two", "time_range": [2.0, 4.0]}]}}}
    cues = spoken_cues([shot], [10.0], "en")
    assert [(c["t0"], c["t1"], c["text"]) for c in cues] == [(10.5, 12.0, "Short card one"), (12.0, 14.0, "Card two")]
