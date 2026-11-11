"""Tests for director.caption_fields."""

import unicodedata

import pytest

from caption_fields import (
    CaptionError,
    caption_lines,
    check_lines,
    diff_report,
    manifest_lines,
    resolve_caption,
    words,
)


def test_identical_text_returns_spoken():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": "नमस्ते"}
    assert resolve_caption(line) == "नमस्ते"


def test_caption_text_absent_returns_spoken():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"}
    assert resolve_caption(line) == "नमस्ते"


def test_empty_caption_text_returns_spoken():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": ""}
    assert resolve_caption(line) == "नमस्ते"


def test_approved_difference_equal_word_count():
    line = {
        "id": "1",
        "lang": "hi",
        "spoken_text": "ब्याही",
        "caption_text": "ब्याहीं",
        "caption_diff_approved": True,
    }
    assert resolve_caption(line) == "ब्याहीं"


def test_approved_difference_equal_word_count_second_pair():
    line = {
        "id": "1",
        "lang": "hi",
        "spoken_text": "गलती",
        "caption_text": "ग़लती",
        "caption_diff_approved": True,
    }
    assert resolve_caption(line) == "ग़लती"


def test_unapproved_difference_refused():
    line = {
        "id": "1",
        "lang": "hi",
        "spoken_text": "ब्याही",
        "caption_text": "ब्याहीं",
    }
    try:
        resolve_caption(line)
    except CaptionError as exc:
        assert "1" in str(exc)
        assert "not approved" in str(exc)
    else:
        raise AssertionError("expected CaptionError")


def test_approved_but_word_count_changed_refused():
    line = {
        "id": "1",
        "lang": "hi",
        "spoken_text": "गलती",
        "caption_text": "ग़लती हुई",
        "caption_diff_approved": True,
    }
    try:
        resolve_caption(line)
    except CaptionError as exc:
        assert "1" in str(exc)
        assert "word count" in str(exc)
    else:
        raise AssertionError("expected CaptionError")


def test_nfc_and_nfd_count_as_equal():
    spoken = "ऩ"
    caption = "ऩ"
    assert spoken != caption
    assert unicodedata.normalize("NFD", spoken) == caption
    line = {"id": "1", "lang": "hi", "spoken_text": spoken, "caption_text": caption}
    assert resolve_caption(line) == spoken


def test_empty_spoken_text_raises():
    line = {"id": "1", "lang": "hi", "spoken_text": ""}
    try:
        resolve_caption(line)
    except CaptionError as exc:
        assert "1" in str(exc)
        assert "missing spoken text" in str(exc)
    else:
        raise AssertionError("expected CaptionError")


def test_missing_spoken_text_raises():
    line = {"id": "1", "lang": "hi"}
    try:
        resolve_caption(line)
    except CaptionError as exc:
        assert "1" in str(exc)
        assert "missing spoken text" in str(exc)
    else:
        raise AssertionError("expected CaptionError")


def test_words_splits_on_whitespace_after_nfc():
    assert words("a  b c") == ["a", "b", "c"]
    assert words("नमस्ते") == ["नमस्ते"]


def test_diff_report_identical():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": "नमस्ते"}
    report = diff_report(line)
    assert report == {
        "id": "1",
        "same": True,
        "approved": False,
        "word_count_equal": True,
        "changed_words": [],
    }


def test_diff_report_approved_hindi_pair():
    line = {
        "id": "1",
        "lang": "hi",
        "spoken_text": "ब्याही",
        "caption_text": "ब्याहीं",
        "caption_diff_approved": True,
    }
    report = diff_report(line)
    assert report["same"] is False
    assert report["approved"] is True
    assert report["word_count_equal"] is True
    assert report["changed_words"] == [("ब्याही", "ब्याहीं")]


def test_diff_report_word_count_changed_empty_changed_words():
    line = {
        "id": "1",
        "lang": "hi",
        "spoken_text": "गलती",
        "caption_text": "ग़लती हुई",
        "caption_diff_approved": True,
    }
    report = diff_report(line)
    assert report["same"] is False
    assert report["word_count_equal"] is False
    assert report["changed_words"] == []


def test_diff_report_caption_absent():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"}
    report = diff_report(line)
    assert report["same"] is True
    assert report["word_count_equal"] is True
    assert report["changed_words"] == []


def test_check_lines_identical_no_problems():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": "नमस्ते"}
    ]
    assert check_lines(lines) == []


def test_check_lines_unapproved_difference():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": "ब्याही", "caption_text": "ब्याहीं"}
    ]
    assert check_lines(lines) == ["line 1: caption difference not approved"]


def test_check_lines_word_count_change():
    lines = [
        {
            "id": "1",
            "lang": "hi",
            "spoken_text": "गलती",
            "caption_text": "ग़लती हुई",
            "caption_diff_approved": True,
        }
    ]
    assert check_lines(lines) == [
        "line 1: caption word count differs from spoken text"
    ]


def test_check_lines_missing_spoken_text():
    lines = [{"id": "1", "lang": "hi"}]
    assert check_lines(lines) == ["line 1: missing spoken text"]


def test_check_lines_duplicate_ids():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"},
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"},
    ]
    assert check_lines(lines) == ["line 1: duplicate id for lang hi"]


def test_check_lines_returns_problems_in_input_order():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": "ब्याही", "caption_text": "ब्याहीं"},
        {"id": "2", "lang": "hi"},
        {
            "id": "3",
            "lang": "hi",
            "spoken_text": "गलती",
            "caption_text": "ग़लती हुई",
            "caption_diff_approved": True,
        },
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"},
    ]
    assert check_lines(lines) == [
        "line 1: caption difference not approved",
        "line 2: missing spoken text",
        "line 3: caption word count differs from spoken text",
        "line 1: duplicate id for lang hi",
    ]


def test_caption_lines_returns_list_of_dicts():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"},
        {
            "id": "2",
            "lang": "hi",
            "spoken_text": "ब्याही",
            "caption_text": "ब्याहीं",
            "caption_diff_approved": True,
        },
    ]
    result = caption_lines(lines)
    assert result == [
        {"id": "1", "lang": "hi", "text": "नमस्ते"},
        {"id": "2", "lang": "hi", "text": "ब्याहीं"},
    ]


def test_caption_lines_raises_on_first_bad_line():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"},
        {"id": "2", "lang": "hi", "spoken_text": "ब्याही", "caption_text": "ब्याहीं"},
    ]
    try:
        caption_lines(lines)
    except CaptionError as exc:
        assert "2" in str(exc)
    else:
        raise AssertionError("expected CaptionError")


def test_resolve_caption_non_boolean_approval_refused():
    line = {
        "id": "1",
        "lang": "hi",
        "spoken_text": "ब्याही",
        "caption_text": "ब्याहीं",
        "caption_diff_approved": 1,
    }
    try:
        resolve_caption(line)
    except CaptionError as exc:
        assert "not approved" in str(exc)
    else:
        raise AssertionError("expected CaptionError for non-boolean approval")


def test_check_lines_non_boolean_approval_reported():
    lines = [
        {
            "id": "1",
            "lang": "hi",
            "spoken_text": "ब्याही",
            "caption_text": "ब्याहीं",
            "caption_diff_approved": 1,
        }
    ]
    assert check_lines(lines) == ["line 1: caption difference not approved"]


def test_check_lines_duplicate_detected_after_missing_spoken_text():
    lines = [{"id": "1", "lang": "hi"}, {"id": "1", "lang": "hi"}]
    assert check_lines(lines) == [
        "line 1: missing spoken text",
        "line 1: missing spoken text",
        "line 1: duplicate id for lang hi",
    ]


def test_check_lines_caption_without_spoken_text_does_not_raise():
    lines = [{"id": "1", "lang": "hi", "caption_text": "नमस्ते"}]
    assert check_lines(lines) == ["line 1: missing spoken text"]


def test_check_lines_none_entry_reported_without_raising():
    problems = check_lines([None])
    assert len(problems) == 1
    assert "not a mapping" in problems[0]


def test_check_lines_non_str_spoken_reported_and_duplicates_still_checked():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": 5},
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"},
    ]
    problems = check_lines(lines)
    assert any("not text" in p for p in problems)
    assert any("duplicate id" in p for p in problems)


def test_check_lines_non_str_caption_reported_without_raising():
    lines = [{"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": 7}]
    problems = check_lines(lines)
    assert len(problems) == 1
    assert "not text" in problems[0]


def test_diff_report_none_spoken_raises_caption_error():
    try:
        diff_report({"id": "1", "lang": "hi", "spoken_text": None})
    except CaptionError as exc:
        assert "missing spoken text" in str(exc)
    else:
        raise AssertionError("expected CaptionError for None spoken_text")


def test_whitespace_only_spoken_counts_as_missing():
    try:
        resolve_caption({"id": "1", "lang": "hi", "spoken_text": "   "})
    except CaptionError as exc:
        assert "missing spoken text" in str(exc)
    else:
        raise AssertionError("expected CaptionError for whitespace spoken_text")
    assert check_lines([{"id": "1", "lang": "hi", "spoken_text": "  "}]) == [
        "line 1: missing spoken text"
    ]


def test_check_lines_none_entry_exact_message():
    # observer 7 (TEST_FINDINGS ultra): exact format, not a substring
    assert check_lines([None]) == ["line 1: not a mapping"]


def test_check_lines_non_str_spoken_exact_problem_list():
    # observer 7 (TEST_FINDINGS codex): the complete problem list, nothing extra
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": 5},
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते"},
    ]
    assert check_lines(lines) == [
        "line 1: spoken_text is not text",
        "line 1: duplicate id for lang hi",
    ]


def test_resolve_caption_whitespace_only_caption_returns_spoken():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": "   "}
    assert resolve_caption(line) == "नमस्ते"


def test_resolve_caption_none_caption_returns_spoken():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": None}
    assert resolve_caption(line) == "नमस्ते"


def test_diff_report_whitespace_only_caption_is_absent():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": "   "}
    report = diff_report(line)
    assert report["same"] is True
    assert report["word_count_equal"] is True
    assert report["changed_words"] == []


def test_diff_report_none_caption_is_absent():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": None}
    report = diff_report(line)
    assert report["same"] is True
    assert report["word_count_equal"] is True
    assert report["changed_words"] == []


def test_check_lines_whitespace_only_and_none_caption_no_problems():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": "   "},
        {"id": "2", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": None},
    ]
    assert check_lines(lines) == []


def test_check_lines_unhashable_id_returns_list_without_raising():
    lines = [{"id": [1], "lang": "hi", "spoken_text": "नमस्ते"}]
    result = check_lines(lines)
    assert isinstance(result, list)
    assert len(result) == 0 or all(isinstance(p, str) for p in result)


def test_resolve_caption_non_text_caption_raises():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": 5}
    try:
        resolve_caption(line)
    except CaptionError as exc:
        assert "caption_text is not text" in str(exc)
    else:
        raise AssertionError("expected CaptionError for non-text caption_text")


def test_diff_report_non_text_caption_raises():
    line = {"id": "1", "lang": "hi", "spoken_text": "नमस्ते", "caption_text": 5}
    try:
        diff_report(line)
    except CaptionError as exc:
        assert "caption_text is not text" in str(exc)
    else:
        raise AssertionError("expected CaptionError for non-text caption_text")


def test_check_lines_duplicate_and_unapproved_difference_both_reported():
    lines = [
        {"id": "1", "lang": "hi", "spoken_text": "ब्याही", "caption_text": "ब्याहीं"},
        {"id": "1", "lang": "hi", "spoken_text": "ब्याही", "caption_text": "ब्याहीं"},
    ]
    problems = check_lines(lines)
    assert "line 1: caption difference not approved" in problems
    assert "line 1: duplicate id for lang hi" in problems


def test_spoken_text_is_manifest_text():
    rows = [
        {"line": "L1", "lang": "hi", "text": "ब्रह्मा उठे", "shot_text": "Brahma stands up"}
    ]
    lines = manifest_lines(rows)
    assert lines[0]["spoken_text"] == "ब्रह्मा उठे"
    assert caption_lines(lines) == [{"id": "L1", "lang": "hi", "text": "ब्रह्मा उठे"}]


def test_unapproved_override_raises():
    rows = [{"line": "L1", "lang": "hi", "text": "ब्याही"}]
    overrides = {("L1", "hi"): {"caption_text": "ब्याहीं", "caption_diff_approved": False}}
    with pytest.raises(CaptionError, match="not approved"):
        caption_lines(manifest_lines(rows, overrides))


def test_approved_same_wordcount_used():
    rows = [{"line": "L1", "lang": "hi", "text": "ब्याही"}]
    overrides = {("L1", "hi"): {"caption_text": "ब्याहीं", "caption_diff_approved": True}}
    assert caption_lines(manifest_lines(rows, overrides)) == [
        {"id": "L1", "lang": "hi", "text": "ब्याहीं"}
    ]


def test_unknown_override_raises():
    rows = [{"line": "L1", "lang": "hi", "text": "नमस्ते"}]
    overrides = {("L9", "hi"): {"caption_text": "नमस्ते", "caption_diff_approved": True}}
    with pytest.raises(CaptionError, match="unknown line"):
        manifest_lines(rows, overrides)


def test_duplicate_row_conflict_raises():
    rows = [
        {"line": "L1", "lang": "hi", "text": "नमस्ते"},
        {"line": "L1", "lang": "hi", "text": "नमस्ते दोस्त"},
    ]
    with pytest.raises(CaptionError, match="duplicate rows"):
        manifest_lines(rows)
