"""Prompt hygiene helpers for the GranthStudio pipeline."""

import os
import sys
import re
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from h3.schema_and_linter import MOUTH_LOCK_SENTENCE

__all__ = [
    "PromptError",
    "GLUE_VERBS",
    "BANNED_SOUND_NOUNS",
    "collapse_blank_lines",
    "split_sentences",
    "find_duplicate_sentences",
    "remove_duplicate_sentences",
    "find_cue_glue",
    "mouth_sentence",
    "cast_line",
    "check_sound_cue",
    "clean_prompt",
]

GLUE_VERBS = (
    "snaps",
    "drops",
    "rises",
    "falls",
    "hisses",
    "swells",
    "fades",
    "breaks",
    "rustles",
    "cracks",
    "thuds",
    "echoes",
    "settles",
)

BANNED_SOUND_NOUNS = (
    "serpent",
    "serpents",
    "snake",
    "snakes",
    "cobra",
    "cobras",
    "bird",
    "birds",
    "bee",
    "bees",
    "lion",
    "tiger",
    "elephant",
    "horse",
    "creature",
    "creatures",
    "animal",
    "animals",
    "monster",
    "demon",
    "ghost",
)

BODY_PREFIXES = ("integrated_multimodal_description: ", "detailed_description: ")

MOUTH_STAY_RE = re.compile(
    r"\b(?:mouth stays (?:closed|shut)|(?:keeps?|keep) (?:their|his|her) "
    r"(?:completely )?lips? (?:completely )?closed|lips? remains? "
    r"(?:completely )?closed)\b",
    re.IGNORECASE,
)


class PromptError(ValueError):
    """Raised when a prompt fails a hygiene rule."""


def collapse_blank_lines(text: str) -> str:
    """Normalise line endings, strip trailing spaces, drop empty lines."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.rstrip(" ")
        if line != "":
            cleaned.append(line)
    return "\n".join(cleaned)


def split_sentences(text: str) -> list:
    """Split text into non-empty stripped sentences."""
    text = collapse_blank_lines(text)
    parts = re.split(r"(?<=[.!?]) |\n", text)
    sentences = []
    for part in parts:
        part = part.strip()
        if part:
            sentences.append(part)
    return sentences


def _normalise_sentence(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence.strip().lower())


def find_duplicate_sentences(text: str) -> list:
    """Return sentences that occur more than once, each reported once."""
    sentences = split_sentences(text)
    seen = {}
    duplicates = []
    for sentence in sentences:
        key = _normalise_sentence(sentence)
        if key in seen:
            if seen[key] is True:
                duplicates.append(sentence)
                seen[key] = False
        else:
            seen[key] = True
    return duplicates


def remove_duplicate_sentences(text: str) -> str:
    """Remove duplicate sentences, keeping the first occurrence and line breaks."""
    lines = collapse_blank_lines(text).split("\n")
    seen = set()
    kept = []
    for line in lines:
        sentence_keys = [_normalise_sentence(s) for s in split_sentences(line)]
        line_kept = []
        for sentence, key in zip(split_sentences(line), sentence_keys):
            if key not in seen:
                seen.add(key)
                line_kept.append(sentence)
        if line_kept:
            kept.append(" ".join(line_kept))
    return "\n".join(kept)


GLUE_RE = re.compile(
    r"\bwith\b[^,.;]{0,40}?\b(?:" + "|".join(re.escape(v) for v in GLUE_VERBS) + r")\b",
    re.IGNORECASE,
)


def find_cue_glue(text: str) -> find_cue_glue:
    """Find 'with' followed within 40 characters by a bare third-person verb."""
    cleaned = collapse_blank_lines(text)
    results = []
    for match in GLUE_RE.finditer(cleaned):
        if re.search(r"\band\b", match.group(0), re.IGNORECASE):
            continue
        results.append(match.group(0))
    return results


def mouth_sentence(on_screen: list, speaking: list) -> str:
    """Build the mouth/lips sentence for the people in the shot."""
    if not on_screen:
        raise PromptError("on_screen is empty")
    for speaker in speaking:
        if speaker not in on_screen:
            raise PromptError(f"speaker {speaker!r} is not in on_screen")

    silent = [name for name in on_screen if name not in speaking]

    def join_names(names):
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} and {names[1]}"
        return f"{', '.join(names[:-1])} and {names[-1]}"

    if len(on_screen) == 1:
        name = on_screen[0]
        if speaking:
            return f"{name} speaks with moving lips."
        return f"{name} keeps their lips closed."

    if not speaking:
        return f"{join_names(on_screen)} keep their lips completely closed."

    parts = []
    if speaking:
        if len(speaking) == 1:
            parts.append(f"{join_names(speaking)} speaks with moving lips")
        else:
            parts.append(f"{join_names(speaking)} speak with moving lips")
    if silent:
        if len(silent) == 1:
            parts.append(f"{join_names(silent)} keeps their lips completely closed")
        else:
            parts.append(f"{join_names(silent)} keep their lips completely closed")
    return "; ".join(parts) + "."


def cast_line(cast: list) -> str:
    """Build the cast line naming exactly who appears in the shot."""
    if not cast:
        raise PromptError("cast is empty")
    if len(cast) == 1:
        names = cast[0]
        verb = "appears"
    elif len(cast) == 2:
        names = f"{cast[0]} and {cast[1]}"
        verb = "appear"
    else:
        names = f"{', '.join(cast[:-1])} and {cast[-1]}"
        verb = "appear"
    return f"Only {names} {verb} in this shot; no extra figures or creatures appear."


def check_sound_cue(cue: str, visible: list = ()) -> None:
    """Raise PromptError if a banned sound noun appears and is not visible."""
    visible_normalised = {name.lower() for name in visible}
    for noun in BANNED_SOUND_NOUNS:
        pattern = r"\b" + re.escape(noun) + r"\b"
        if re.search(pattern, cue, flags=re.IGNORECASE):
            other_form = noun[:-1] if noun.endswith("s") else noun + "s"
            if noun not in visible_normalised and other_form not in visible_normalised:
                raise PromptError(f"banned sound noun: {noun}")


def clean_prompt(
    text: str,
    cast: list,
    on_screen: list,
    speaking: list,
    sound_cues: list = (),
    visible: list = (),
) -> str:
    """Clean and check a video prompt, returning a single safe block of text.

    The mouth sentence and the cast line are appended to the end of the body line
    (the line starting with integrated_multimodal_description: or detailed_description:).
    The last line (non_diegetic_music:) stays last. Old mouth sentences are removed,
    so exactly one mouth sentence remains. Raises PromptError("no body line") if there
    is no body line.

    Output has no blank lines. The linter accepts it only after step 7 changes
    schema_and_linter.py:79 to a single "\\n". Do not wire this function before
    v4_to_h3.py:160 is fixed (Opus 10f).
    """
    for cue in sound_cues:
        check_sound_cue(cue, visible=list(visible))

    mouth = mouth_sentence(on_screen, speaking)
    cast = cast_line(cast)

    text = text.replace(mouth, "").replace(cast, "").replace(MOUTH_LOCK_SENTENCE, "")
    text = "\n".join(_drop_mouth_sentences(line) for line in collapse_blank_lines(text).split("\n"))
    text = collapse_blank_lines(text)
    text = remove_duplicate_sentences(text)

    if find_cue_glue(text):
        raise PromptError("cue glue detected after cleaning")

    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.startswith(BODY_PREFIXES):
            lines[index] = f"{line} {mouth} {cast}"
            break
    else:
        raise PromptError("no body line")

    return collapse_blank_lines("\n".join(lines))


def _drop_mouth_sentences(line: str) -> str:
    """Remove every sentence on the line that says the mouth stays closed or shut."""
    kept = [sentence for sentence in re.split(r"(?<=[.!?]) ", line) if not MOUTH_STAY_RE.search(sentence)]
    return " ".join(kept)
