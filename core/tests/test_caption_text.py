import random
import shutil
from pathlib import Path

import pytest

from core import caption_text as ct

FONTS = Path(__file__).resolve().parents[2] / "styles" / "fonts"
DEVA_FONT = FONTS / "NotoSansDevanagari-Variable.ttf"
LATIN_FONT = FONTS / "Inter-Variable.ttf"

needs_deva = pytest.mark.skipif(not DEVA_FONT.is_file(), reason="Noto Devanagari font missing")
needs_latin = pytest.mark.skipif(not LATIN_FONT.is_file(), reason="Inter font missing")


# ---------- clusters ----------

@pytest.mark.parametrize("text, expected", [
    ("क्ष", ["क्ष"]),
    ("ज्ञ", ["ज्ञ"]),
    ("माझं", ["मा", "झं"]),
    ("कुठे", ["कु", "ठे"]),
    ("ॲप", ["ॲ", "प"]),
    ("र्क", ["र्क"]),
    ("ळ", ["ळ"]),
    ("ऱ", ["ऱ"]),
    ("\r\n", ["\r\n"]),
    ("", []),
])
def test_clusters_corpus(text, expected):
    assert ct.clusters(text) == expected


def test_clusters_round_trip_property():
    rng = random.Random(20261107)
    for _ in range(200):
        n = rng.randint(0, 40)
        text = "".join(chr(rng.randint(0, 0x10FFFF)) for _ in range(n))
        parts = ct.clusters(text)
        assert "".join(parts) == text
        assert all(parts), "no empty cluster"


def test_clusters_junk_input_is_empty():
    assert ct.clusters(None) == []
    assert ct.clusters(12) == []


# ---------- script_of / script_runs ----------

def test_script_of_blocks():
    assert ct.script_of("क") == "deva"
    assert ct.script_of("꣠") == "deva"
    assert ct.script_of("a") == "latin"
    assert ct.script_of("é") == "latin"
    assert ct.script_of("1") == "other"
    assert ct.script_of(" ") == "other"
    assert ct.script_of("!") == "other"


def test_script_runs_mixed_hindi_english():
    assert ct.script_runs("Hello माझं 123 world") == [
        ("latin", "Hello "),
        ("deva", "माझं 123 "),
        ("latin", "world"),
    ]


def test_script_runs_round_trip_and_no_cluster_split():
    text = "कुठे ॲप okay र्क 9!"
    runs = ct.script_runs(text)
    assert "".join(sub for _, sub in runs) == text
    for _, sub in runs:
        joined = "".join(ct.clusters(sub))
        assert joined == sub


def test_script_runs_leading_other_and_empty():
    assert ct.script_runs("123 माझं") == [("deva", "123 माझं")]
    assert ct.script_runs("") == []
    assert ct.script_runs("123 !") == [("other", "123 !")]


# ---------- read_cmap / glyph_coverage / check_font_coverage ----------

@needs_deva
def test_read_cmap_noto_has_devanagari():
    cmap = ct.read_cmap(str(DEVA_FONT))
    assert len(cmap) > 500
    assert 0x0915 in cmap


def test_read_cmap_missing_file_is_empty():
    assert ct.read_cmap("does/not/exist.ttf") == set()


def test_read_cmap_junk_file_is_empty(tmp_path):
    bad = tmp_path / "bad.ttf"
    bad.write_bytes(b"not a font at all")
    assert ct.read_cmap(str(bad)) == set()


@needs_deva
def test_glyph_coverage_ok_and_missing_ignores_space():
    ok = ct.glyph_coverage(str(DEVA_FONT), "माझं कुठे\n")
    assert ok == {"ok": True, "missing": []}
    res = ct.glyph_coverage(str(DEVA_FONT), "‍क")
    assert res["ok"] is False
    assert res["missing"] == [""]


@needs_deva
def test_check_font_coverage_noto_covers_corpus():
    assert ct.check_font_coverage(str(DEVA_FONT)) == []


@needs_latin
def test_check_font_coverage_inter_fails_on_kssa():
    entries = ct.check_font_coverage(str(LATIN_FONT))
    assert entries, "Inter has no Devanagari, must FAIL"
    assert all(e["rule"] == "CAP-GLYPH" and e["level"] == "FAIL" for e in entries)
    assert all("Inter-Variable.ttf" in e["message"] for e in entries)
    chars = "".join(e["message"] for e in entries)
    assert "क" in chars  # ka from क्ष
    assert "ष" in chars  # ssa from क्ष


def test_check_font_coverage_unreadable_font_fails_once(tmp_path):
    entries = ct.check_font_coverage(str(tmp_path / "missing.ttf"))
    assert len(entries) == 1
    assert entries[0]["rule"] == "CAP-GLYPH" and entries[0]["level"] == "FAIL"


# ---------- shaping engine / measure ----------

def test_shaping_engine_is_known_value():
    assert ct.shaping_engine() in ("raqm", "basic")


@needs_deva
def test_measure_positive_and_fallback(tmp_path):
    w = ct.measure(str(DEVA_FONT), 40, "माझं कुठे")
    assert w > 0
    assert ct.measure(str(DEVA_FONT), 40, "") == 0
    missing = str(tmp_path / "nope.ttf")
    assert ct.measure(missing, 10, "abcd") == pytest.approx(4 * 0.6 * 10)


# ---------- wrap_lines ----------

@needs_deva
def test_wrap_empty_text():
    assert ct.wrap_lines("", str(DEVA_FONT), 40, 300) == ([], [])


@needs_deva
def test_wrap_never_splits_cluster_and_keeps_words():
    text = "माझं कुठे ॲप र्क क्ष ज्ञ"
    lines, entries = ct.wrap_lines(text, str(DEVA_FONT), 40, 130, max_lines=6)
    assert len(lines) >= 2
    rebuilt_words = " ".join(lines).split(" ")
    assert rebuilt_words == text.split(" ")
    for line in lines:
        assert "".join(ct.clusters(line)) == line


@needs_deva
def test_wrap_narrow_devanagari_sentence_two_lines_fit():
    text = "माझं कुठे ॲप"
    width = ct.measure(str(DEVA_FONT), 40, "माझं कुठे") + 5
    lines, entries = ct.wrap_lines(text, str(DEVA_FONT), 40, width, max_lines=2)
    assert lines == ["माझं", "कुठे ॲप"]      # balanced wrap (2026-11-09): same 2 lines, no orphan word on line 2
    assert entries == []


@needs_deva
def test_wrap_over_wide_single_word_warns_and_splits_between_clusters():
    word = "माझंकुठेॲप"
    lines, entries = ct.wrap_lines(word, str(DEVA_FONT), 40, 60, max_lines=5)
    assert "".join(lines) == word
    assert len(lines) > 1
    for line in lines:
        assert "".join(ct.clusters(line)) == line
    warns = [e for e in entries if e["message"] == "word wider than the line, split between clusters"]
    assert len(warns) == 1
    assert warns[0]["rule"] == "CAP-WRAP" and warns[0]["level"] == "WARN"


@needs_deva
def test_wrap_forced_newline():
    lines, entries = ct.wrap_lines("माझं\nकुठे", str(DEVA_FONT), 40, 10000)
    assert lines == ["माझं", "कुठे"]
    assert entries == []


@needs_deva
def test_wrap_too_many_lines_keeps_all_and_warns():
    lines, entries = ct.wrap_lines("a\nb\nc", str(DEVA_FONT), 40, 10000, max_lines=2)
    assert lines == ["a", "b", "c"]
    warn = [e for e in entries if e["message"] == "needs 3 lines, limit 2"]
    assert len(warn) == 1 and warn[0]["rule"] == "CAP-WRAP" and warn[0]["level"] == "WARN"


@needs_deva
def test_wrap_is_deterministic():
    a = ct.wrap_lines("माझं कुठे ॲप र्क", str(DEVA_FONT), 40, 120, max_lines=4)
    b = ct.wrap_lines("माझं कुठे ॲप र्क", str(DEVA_FONT), 40, 120, max_lines=4)
    assert a == b


# ---------- fit_text ----------

@needs_deva
def test_fit_text_shrinks_to_fit():
    text = "माझं कुठे ॲप र्क क्ष ज्ञ"
    full_w = ct.measure(str(DEVA_FONT), 60, text)
    lines, size, entries = ct.fit_text(text, str(DEVA_FONT), 60, full_w / 4 + 5,
                                       max_lines=2, min_size_px=20)
    assert size < 60
    assert len(lines) <= 2
    assert not [e for e in entries if e["level"] == "FAIL"]


@needs_deva
def test_fit_text_no_shrink_when_fits():
    lines, size, entries = ct.fit_text("माझं", str(DEVA_FONT), 40, 1000)
    assert lines == ["माझं"] and size == 40 and entries == []


@needs_deva
def test_fit_text_fail_at_minimum_size():
    text = "माझं कुठे ॲप र्क क्ष ज्ञ"
    lines, size, entries = ct.fit_text(text, str(DEVA_FONT), 40, 20,
                                       max_lines=1, min_size_px=36)
    assert size == 36
    fails = [e for e in entries if e["level"] == "FAIL"]
    assert len(fails) == 1
    assert fails[0]["rule"] == "CAP-WRAP"
    assert fails[0]["message"] == "does not fit in 1 lines at the minimum size"


@needs_deva
def test_fit_text_is_deterministic():
    a = ct.fit_text("माझं कुठे ॲप", str(DEVA_FONT), 50, 90, max_lines=2, min_size_px=20)
    b = ct.fit_text("माझं कुठे ॲप", str(DEVA_FONT), 50, 90, max_lines=2, min_size_px=20)
    assert a == b


# ---------- ass_lines / fallback_markup ----------

def test_ass_lines_joins_with_ass_break():
    assert ct.ass_lines(["ab", "cd"]) == "ab\\Ncd"
    assert ct.ass_lines([]) == ""


def test_fallback_markup_mixed_hindi_english():
    out = ct.fallback_markup("Hello माझं 123", "DevaFam", "LatinFam")
    assert out == "Hello {\\fnDevaFam}माझं 123{\\fnLatinFam}"


def test_fallback_markup_mixed_hindi_first():
    out = ct.fallback_markup("माझं hello", "DevaFam", "LatinFam")
    assert out == "माझं {\\fnLatinFam}hello{\\fnDevaFam}"


def test_fallback_markup_plain_text_unchanged():
    assert ct.fallback_markup("Hello world 42", "DevaFam", "LatinFam") == "Hello world 42"
    assert ct.fallback_markup("माझं कुठे", "DevaFam", "LatinFam") == "माझं कुठे"


def test_fallback_markup_escapes_braces_and_backslashes():
    assert ct.fallback_markup("a{b}\\c", "D", "L") == "a(b)c"


def test_fallback_markup_missing_family_warns_and_no_override():
    out = ct.fallback_markup("Hello माझं", None, "LatinFam")
    assert "\\fn" not in out
    assert out == "Hello माझं"
    entries = ct.fallback_markup_entries("Hello माझं", None, "LatinFam")
    assert len(entries) == 1
    assert entries[0]["rule"] == "CAP-TEXT" and entries[0]["level"] == "WARN"


def test_fallback_markup_entries_clean_when_families_set():
    assert ct.fallback_markup_entries("Hello माझं", "D", "L") == []
    assert ct.fallback_markup_entries("Hello", None, None) == []


def test_fallback_markup_empty_and_junk():
    assert ct.fallback_markup("", "D", "L") == ""
    assert ct.fallback_markup(None, "D", "L") == ""


def test_fallback_markup_is_deterministic():
    a = ct.fallback_markup("Hello माझं 1 world", "D", "L")
    assert a == ct.fallback_markup("Hello माझं 1 world", "D", "L")
