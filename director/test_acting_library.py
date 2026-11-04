import pytest

import acting_library as al

BHAVAS = ["affection", "mischief", "maternal_anxiety", "anger", "courage", "surrender", "compassion",
          "devotion", "fear", "wonder", "grief", "relief", "playful_defeat"]
CHARS = [None, "CHAR-KRISHNA", "CHAR-YASHODA", "CHAR-BALARAMA", "CHAR-KALIYA"]


def test_all_bhavas_present_with_nine_ordered_steps():
    assert set(BHAVAS) == set(al.BHAVAS)
    for name in BHAVAS:
        steps = al.BHAVAS[name]["steps"]
        assert len(steps) == len(al.STEPS) == 9, name
        assert all(sec > 0 and text for text, sec in steps), name


@pytest.mark.parametrize("bhava", BHAVAS)
@pytest.mark.parametrize("char", CHARS)
def test_progression_ordered_and_contiguous(bhava, char):
    beats = al.progression(bhava, char)
    assert [b["step"] for b in beats] == list(al.STEPS)
    assert beats[0]["t"][0] == 0
    for prev, cur in zip(beats, beats[1:]):
        assert prev["t"][1] == cur["t"][0]
    assert all(b["t"][1] > b["t"][0] for b in beats)


@pytest.mark.parametrize("bhava", BHAVAS)
@pytest.mark.parametrize("seconds", [3.0, 5.2, 9.5])
def test_durations_scale_to_seconds(bhava, seconds):
    beats = al.progression(bhava, "CHAR-YASHODA", seconds=seconds)
    assert beats[-1]["t"][1] == seconds
    assert beats[0]["t"][0] == 0


def test_character_tempo_changes_default_length():
    base = al.progression("anger")[-1]["t"][1]
    kaliya = al.progression("anger", "CHAR-KALIYA")[-1]["t"][1]
    assert kaliya > base


def test_overrides_replace_steps_for_kaliya():
    beats = al.progression("fear", "CHAR-KALIYA")
    hands = next(b for b in beats if b["step"] == "hands")
    assert "no hands" in hands["action"]


def test_krishna_mischief_example_present():
    beats = al.progression("mischief", "CHAR-KRISHNA")
    by = {b["step"]: b["action"] for b in beats}
    assert "Dau" in by["eyes"]
    assert "smile" in by["mouth"]
    assert "tilts" in by["head"] or "tilt" in by["head"]
    assert "forearm" in by["full_body"] and "brighten" in by["full_body"]
    order = [b["step"] for b in beats]
    assert order.index("eyes") < order.index("full_body")


def test_unknown_bhava_raises():
    with pytest.raises(KeyError):
        al.progression("rage")
