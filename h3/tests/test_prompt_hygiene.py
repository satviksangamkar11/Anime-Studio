import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import prompt_hygiene
from h3.schema_and_linter import MOUTH_LOCK_SENTENCE


def test_collapse_blank_lines_crlf():
    text = "Hello\r\n\r\nWorld\r\n"
    assert prompt_hygiene.collapse_blank_lines(text) == "Hello\nWorld"


def test_collapse_blank_lines_three_blanks():
    text = "A\n\n\n\nB"
    assert prompt_hygiene.collapse_blank_lines(text) == "A\nB"


def test_collapse_blank_lines_trailing_spaces():
    text = "A   \nB  \n"
    assert prompt_hygiene.collapse_blank_lines(text) == "A\nB"


def test_split_sentences():
    text = "First sentence. Second! Third? Fourth\nFifth."
    assert prompt_hygiene.split_sentences(text) == [
        "First sentence.",
        "Second!",
        "Third?",
        "Fourth",
        "Fifth.",
    ]


def test_find_duplicate_sentences():
    text = "Hello world. hello world. Goodbye."
    duplicates = prompt_hygiene.find_duplicate_sentences(text)
    assert duplicates == ["hello world."]


def test_remove_duplicate_sentences_keeps_first():
    text = "A line.\nB line.\nA line.\nC line."
    result = prompt_hygiene.remove_duplicate_sentences(text)
    assert result == "A line.\nB line.\nC line."


def test_find_cue_glue_found():
    text = "with a veil snaps"
    assert prompt_hygiene.find_cue_glue(text) == ["with a veil snaps"]


def test_find_cue_glue_wind_drops():
    text = "with the wind drops"
    assert prompt_hygiene.find_cue_glue(text) == ["with the wind drops"]


def test_find_cue_glue_legitimate_not_found():
    assert prompt_hygiene.find_cue_glue("with a soft rustle") == []
    assert prompt_hygiene.find_cue_glue("with his hand raised") == []


def test_mouth_sentence_single_silent():
    assert prompt_hygiene.mouth_sentence(["A"], []) == "A keeps their lips closed."


def test_mouth_sentence_single_speaking():
    assert prompt_hygiene.mouth_sentence(["A"], ["A"]) == "A speaks with moving lips."


def test_mouth_sentence_two_nobody_speaking():
    assert (
        prompt_hygiene.mouth_sentence(["A", "B"], [])
        == "A and B keep their lips completely closed."
    )


def test_mouth_sentence_three_nobody_speaking():
    assert (
        prompt_hygiene.mouth_sentence(["A", "B", "C"], [])
        == "A, B and C keep their lips completely closed."
    )


def test_mouth_no_while():
    assert (
        prompt_hygiene.mouth_sentence(["Kama", "Rati"], [])
        == "Kama and Rati keep their lips completely closed."
    )


def test_mouth_sentence_speakers_and_silent():
    assert (
        prompt_hygiene.mouth_sentence(["A", "B", "C"], ["A"])
        == "A speaks with moving lips; B and C keep their lips completely closed."
    )


def test_mouth_sentence_speaker_missing():
    try:
        prompt_hygiene.mouth_sentence(["A"], ["B"])
    except prompt_hygiene.PromptError:
        pass
    else:
        raise AssertionError("Expected PromptError")


def test_mouth_sentence_empty_on_screen():
    try:
        prompt_hygiene.mouth_sentence([], [])
    except prompt_hygiene.PromptError:
        pass
    else:
        raise AssertionError("Expected PromptError")


def test_cast_line_one():
    assert (
        prompt_hygiene.cast_line(["A"])
        == "Only A appears in this shot; no extra figures or creatures appear."
    )


def test_cast_line_two():
    assert (
        prompt_hygiene.cast_line(["A", "B"])
        == "Only A and B appear in this shot; no extra figures or creatures appear."
    )


def test_cast_line_three():
    assert (
        prompt_hygiene.cast_line(["A", "B", "C"])
        == "Only A, B and C appear in this shot; no extra figures or creatures appear."
    )


def test_cast_line_empty():
    try:
        prompt_hygiene.cast_line([])
    except prompt_hygiene.PromptError:
        pass
    else:
        raise AssertionError("Expected PromptError")


def test_check_sound_cue_refused():
    try:
        prompt_hygiene.check_sound_cue("serpents hiss softly")
    except prompt_hygiene.PromptError as exc:
        assert "serpents" in str(exc)
    else:
        raise AssertionError("Expected PromptError")


def test_check_sound_cue_allowed_when_visible():
    prompt_hygiene.check_sound_cue("serpents hiss softly", visible=["serpents"])


def test_check_sound_cue_beehive_not_matched():
    prompt_hygiene.check_sound_cue("a beehive hums")


def test_check_sound_cue_allowed_soft_rustle():
    prompt_hygiene.check_sound_cue("a soft dry rustle as the wind dies down")


def test_clean_prompt_cue_glue_raises_prompt_error():
    text = "detailed_description: Hello world.\n\n\nHello world.\nwith a veil snaps\n"
    try:
        prompt_hygiene.clean_prompt(
            text,
            cast=["A", "B"],
            on_screen=["A", "B"],
            speaking=["A"],
            sound_cues=[],
            visible=[],
        )
    except prompt_hygiene.PromptError:
        pass
    else:
        raise AssertionError("Expected PromptError for cue glue")


def test_clean_prompt_full_flow():
    text = "detailed_description: A line.\n\n\nA line.\nwith a soft rustle\n"
    result = prompt_hygiene.clean_prompt(
        text,
        cast=["A", "B", "C"],
        on_screen=["A", "B", "C"],
        speaking=["A"],
        sound_cues=["a soft dry rustle as the wind dies down"],
        visible=[],
    )
    assert "\n\n" not in result
    assert result.split("\n")[0].endswith(
        "Only A, B and C appear in this shot; no extra figures or creatures appear."
    )
    assert "A speaks with moving lips; B and C keep their lips completely closed." in result
    assert "A line." in result
    assert "with a soft rustle" in result


def test_remove_duplicate_sentences_same_line():
    assert prompt_hygiene.remove_duplicate_sentences("A. A.") == "A."


def test_find_duplicate_sentences_same_line():
    assert prompt_hygiene.find_duplicate_sentences("A. A.") == ["A."]


def test_find_cue_glue_returns_full_phrase():
    assert prompt_hygiene.find_cue_glue("with a veil snaps") == ["with a veil snaps"]


def test_find_cue_glue_comma_after_verb_still_found():
    assert prompt_hygiene.find_cue_glue("with a veil snaps, then fades") == ["with a veil snaps"]


def test_find_duplicate_sentences_three_occurrences_reported_once():
    assert prompt_hygiene.find_duplicate_sentences("A. A. A.") == ["A."]


def test_clean_prompt_input_already_has_cast_line_ends_with_it_once():
    cast_line = "Only A appears in this shot; no extra figures or creatures appear."
    text = "detailed_description: A line.\n" + cast_line + "\n"
    result = prompt_hygiene.clean_prompt(
        text,
        cast=["A"],
        on_screen=["A"],
        speaking=["A"],
        sound_cues=[],
        visible=[],
    )
    assert result.endswith(cast_line)
    assert result.count(cast_line) == 1


def test_clean_prompt_banned_sound_cue_raises():
    try:
        prompt_hygiene.clean_prompt(
            "A line.\n",
            cast=["A"],
            on_screen=["A"],
            speaking=["A"],
            sound_cues=["serpents hiss softly"],
            visible=[],
        )
    except prompt_hygiene.PromptError:
        pass
    else:
        raise AssertionError("Expected PromptError for banned sound cue")


def test_clean_prompt_speaker_missing_from_on_screen_raises():
    try:
        prompt_hygiene.clean_prompt(
            "A line.\n",
            cast=["A", "B"],
            on_screen=["A"],
            speaking=["B"],
            sound_cues=[],
            visible=[],
        )
    except prompt_hygiene.PromptError:
        pass
    else:
        raise AssertionError("Expected PromptError for speaker missing from on_screen")


def test_mouth_sentence_two_speakers_plural_verb():
    # observer 5: plural verb when two or more people speak
    assert (
        prompt_hygiene.mouth_sentence(["A", "B"], ["A", "B"])
        == "A and B speak with moving lips."
    )


def test_mouth_sentence_two_speakers_and_silent_plural():
    # observer 5: plural speakers alongside one silent person
    assert (
        prompt_hygiene.mouth_sentence(["A", "B", "C"], ["A", "B"])
        == "A and B speak with moving lips; C keeps their lips completely closed."
    )


def test_find_cue_glue_with_and_phrase_not_found():
    # seventh run: "and" inside the 40-character window means it is not a bare glue phrase
    assert prompt_hygiene.find_cue_glue("with a veil and dust snaps") == []


def test_find_cue_glue_capitalised_with_found():
    # seventh run: "With" at the start of a sentence still counts as glue
    assert prompt_hygiene.find_cue_glue("With a veil snaps") == ["With a veil snaps"]


def test_clean_prompt_body_line_exact_result():
    # the mouth and cast go at the end of the body line, on the same line
    result = prompt_hygiene.clean_prompt(
        "detailed_description: A line.",
        cast=["A"],
        on_screen=["A"],
        speaking=["A"],
        sound_cues=[],
        visible=[],
    )
    assert result == (
        "detailed_description: A line. A speaks with moving lips. "
        "Only A appears in this shot; no extra figures or creatures appear."
    )


def test_clean_prompt_cast_line_embedded_in_longer_line_appears_once():
    # seventh run: the cast line inside a longer line is removed as a substring, then appended once
    cast_line = "Only A appears in this shot; no extra figures or creatures appear."
    text = "detailed_description: A line. " + cast_line + "\n"
    result = prompt_hygiene.clean_prompt(
        text,
        cast=["A"],
        on_screen=["A"],
        speaking=["A"],
        sound_cues=[],
        visible=[],
    )
    assert result.count(cast_line) == 1


def test_clean_prompt_keeps_section_order():
    text = (
        "HEADER: x\n"
        "\n"
        "integrated_multimodal_description: A walks.\n"
        "soundscape: wind.\n"
        "non_diegetic_music: strings.\n"
    )
    result = prompt_hygiene.clean_prompt(
        text,
        cast=["A"],
        on_screen=["A"],
        speaking=["A"],
        sound_cues=[],
        visible=[],
    )
    lines = result.split("\n")
    assert len(lines) == 4
    assert lines[1].endswith(
        "A speaks with moving lips. "
        "Only A appears in this shot; no extra figures or creatures appear."
    )
    assert lines[-1].startswith("non_diegetic_music:")


def test_no_body_line_raises():
    try:
        prompt_hygiene.clean_prompt(
            "HEADER: x\nnon_diegetic_music: strings.\n",
            cast=["A"],
            on_screen=["A"],
            speaking=["A"],
            sound_cues=[],
            visible=[],
        )
    except prompt_hygiene.PromptError as exc:
        assert "no body line" in str(exc)
    else:
        raise AssertionError("Expected PromptError for missing body line")


def test_single_mouth_sentence():
    result = prompt_hygiene.clean_prompt(
        "detailed_description: A line. " + MOUTH_LOCK_SENTENCE + "\n",
        cast=["A"],
        on_screen=["A"],
        speaking=["A"],
        sound_cues=[],
        visible=[],
    )
    assert MOUTH_LOCK_SENTENCE not in result
    assert "mouth stays" not in result
    assert result.count("lips") == 1


def test_no_blank_line_in_output():
    result = prompt_hygiene.clean_prompt(
        "detailed_description: A line.\n\n\nB line.\nnon_diegetic_music: x\n",
        cast=["A"],
        on_screen=["A"],
        speaking=["A"],
        sound_cues=[],
        visible=[],
    )
    assert "\n\n" not in result
    assert all(line.strip() for line in result.split("\n"))


def test_visible_plural_ok():
    prompt_hygiene.check_sound_cue("serpents hiss", visible=["serpent"])
