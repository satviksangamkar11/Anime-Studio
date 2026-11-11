"""Caption field resolution for the GranthStudio pipeline."""

import unicodedata


class CaptionError(ValueError):
    """Raised when a caption line cannot be resolved safely."""


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def words(text: str) -> list:
    """Split text into words after NFC normalisation."""
    return _nfc(text).split()


def resolve_caption(line: dict) -> str:
    """Return the caption text to use for a line.

    If ``caption_text`` is missing, empty, or equal to ``spoken_text`` after
    NFC normalisation, the spoken text is returned.  If the caption differs,
    ``caption_diff_approved`` must be ``True`` and the word counts must match;
    otherwise a :class:`CaptionError` is raised naming the line id and the
    failing condition.
    """
    line_id = line.get("id", "<unknown>")
    spoken = line.get("spoken_text")
    if spoken is None or (isinstance(spoken, str) and not spoken.strip()):
        raise CaptionError(f"line {line_id}: missing spoken text")
    if not isinstance(spoken, str):
        raise CaptionError(f"line {line_id}: spoken_text is not text")

    spoken_norm = _nfc(spoken)
    caption = line.get("caption_text")
    if caption is None:
        return spoken
    if not isinstance(caption, str):
        raise CaptionError(f"line {line_id}: caption_text is not text")
    if not caption.strip():
        return spoken

    caption_norm = _nfc(caption)
    if caption_norm == spoken_norm:
        return spoken

    approved = line.get("caption_diff_approved", False)
    if approved is not True:
        raise CaptionError(f"line {line_id}: caption difference not approved")

    spoken_word_count = len(words(spoken))
    caption_word_count = len(words(caption))
    if spoken_word_count != caption_word_count:
        raise CaptionError(
            f"line {line_id}: caption word count differs from spoken text"
        )

    return caption


def diff_report(line: dict) -> dict:
    """Build a difference report for a line."""
    line_id = line.get("id", "<unknown>")
    spoken = line.get("spoken_text", "")
    if spoken is None or (isinstance(spoken, str) and not spoken.strip()):
        raise CaptionError(f"line {line_id}: missing spoken text")
    if not isinstance(spoken, str):
        raise CaptionError(f"line {line_id}: spoken_text is not text")

    caption = line.get("caption_text")
    if caption is None:
        caption_present = False
    elif not isinstance(caption, str):
        raise CaptionError(f"line {line_id}: caption_text is not text")
    elif not caption.strip():
        caption_present = False
    else:
        caption_present = True

    spoken_norm = _nfc(spoken)
    caption_norm = _nfc(caption) if caption_present else spoken_norm

    same = spoken_norm == caption_norm
    approved = line.get("caption_diff_approved", False) is True

    spoken_word_list = words(spoken)
    caption_word_list = words(caption) if caption_present else spoken_word_list
    word_count_equal = len(spoken_word_list) == len(caption_word_list)

    if word_count_equal:
        changed_words = [
            (s, c)
            for s, c in zip(spoken_word_list, caption_word_list)
            if s != c
        ]
    else:
        changed_words = []

    return {
        "id": line_id,
        "same": same,
        "approved": approved,
        "word_count_equal": word_count_equal,
        "changed_words": changed_words,
    }


def check_lines(lines: list) -> list:
    """Return problem strings for bad lines without raising."""
    problems = []
    seen = set()
    for idx, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            problems.append(f"line {idx}: not a mapping")
            continue

        line_id = line["id"] if "id" in line else str(idx)
        lang = line.get("lang", "")

        spoken = line.get("spoken_text")
        if spoken is None or (isinstance(spoken, str) and not spoken.strip()):
            problems.append(f"line {line_id}: missing spoken text")
        elif not isinstance(spoken, str):
            problems.append(f"line {line_id}: spoken_text is not text")

        caption = line.get("caption_text")
        if caption is not None and not isinstance(caption, str):
            problems.append(f"line {line_id}: caption_text is not text")

        key = (repr(line_id), repr(lang))
        if key in seen:
            problems.append(f"line {line_id}: duplicate id for lang {lang}")
        else:
            seen.add(key)

        if (
            isinstance(spoken, str)
            and spoken.strip()
            and isinstance(caption, str)
            and caption.strip()
        ):
            spoken_norm = _nfc(spoken)
            caption_norm = _nfc(caption)
            if caption_norm != spoken_norm:
                if line.get("caption_diff_approved", False) is not True:
                    problems.append(
                        f"line {line_id}: caption difference not approved"
                    )
                spoken_words = words(spoken)
                caption_words = words(caption)
                if len(spoken_words) != len(caption_words):
                    problems.append(
                        f"line {line_id}: caption word count differs from spoken text"
                    )

    return problems


def caption_lines(lines: list) -> list:
    """Resolve captions for a list of lines, raising on the first bad line."""
    result = []
    for line in lines:
        text = resolve_caption(line)
        result.append(
            {"id": line.get("id"), "lang": line.get("lang"), "text": text}
        )
    return result


def manifest_lines(rows: list, overrides: dict | None = None) -> list:
    """Build caption lines from accepted manifest rows ``{line, lang, text}``.

    ``spoken_text`` is the manifest ``text`` (after voices.prep_text), never
    shots.json. ``overrides`` maps ``(line, lang)`` to
    ``{caption_text, caption_diff_approved}``. Identical duplicate rows are
    merged; duplicates with different text raise :class:`CaptionError`.
    """
    by_key = {}
    for row in rows:
        if isinstance(row, dict) and row.get("ok") is False:
            continue
        key = (row["line"], row["lang"])
        text = row.get("text")
        if key in by_key:
            if by_key[key]["spoken_text"] != text:
                raise CaptionError(
                    f"line {row['line']} ({row['lang']}): duplicate rows with different text"
                )
            continue
        by_key[key] = {"id": row["line"], "lang": row["lang"], "spoken_text": text}
    for key, ov in (overrides or {}).items():
        if key not in by_key:
            raise CaptionError(f"unknown line {key[0]} ({key[1]}) in overrides")
        by_key[key]["caption_text"] = ov.get("caption_text")
        by_key[key]["caption_diff_approved"] = ov.get("caption_diff_approved", False)
    return list(by_key.values())
