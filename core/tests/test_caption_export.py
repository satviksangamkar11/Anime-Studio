"""Tests for core/caption_export.py (B9b). Everything runs on tmp_path; no network, no ffmpeg render."""
import os
import re
import shutil
import subprocess

import pytest
from PIL import Image

from core import caption_export as ce


def _rules(entries):
    return [(e["rule"], e["level"]) for e in entries]


@pytest.fixture
def no_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("subprocess must not run in plan tests")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)


# ---- time formats -------------------------------------------------------

def test_srt_and_vtt_time_rounding():
    assert ce.srt_time(1.5) == "00:00:01,500"
    assert ce.vtt_time(1.5) == "00:00:01.500"
    assert ce.srt_time(0.1234) == "00:00:00,123"
    assert ce.srt_time(0.1236) == "00:00:00,124"
    # exact half: 62.5 ms rounds up to 63 (banker's rounding would give 62)
    assert ce.srt_time(0.0625) == "00:00:00,063"
    assert ce.vtt_time(0.0625) == "00:00:00.063"
    assert ce.srt_time(3661.5) == "01:01:01,500"
    assert ce.srt_time(-3) == "00:00:00,000"
    assert ce.vtt_time(-3) == "00:00:00.000"


# ---- to_srt / to_vtt ----------------------------------------------------

CUES = [
    {"t0": 2.0, "t1": 3.5, "text": "नमस्ते"},
    {"t0": 0.5, "t1": 1.25, "text": "Hello & <b>", "latin": "Hi there"},
]


def test_to_srt_exact_two_cues_sorted_with_latin_line():
    text, entries = ce.to_srt(CUES)
    assert text == ("1\n00:00:00,500 --> 00:00:01,250\nHello & <b>\nHi there\n\n"
                    "2\n00:00:02,000 --> 00:00:03,500\nनमस्ते\n\n")
    assert entries == []


def test_to_vtt_exact_two_cues_and_escaping():
    text, entries = ce.to_vtt(CUES)
    assert text == ("WEBVTT\n\n"
                    "00:00:00.500 --> 00:00:01.250\nHello &amp; &lt;b>\nHi there\n\n"
                    "00:00:02.000 --> 00:00:03.500\nनमस्ते\n\n")
    assert entries == []


def test_invalid_cues_are_skipped_with_one_warn_each():
    bad = [
        "not a dict",
        {"t0": float("nan"), "t1": 1.0, "text": "x"},
        {"t0": 0.0, "t1": float("inf"), "text": "x"},
        {"t0": 2.0, "t1": 1.0, "text": "backwards"},
        {"t0": 0.0, "t1": 1.0, "text": "   "},
        {"t0": 0.0, "t1": 1.0, "text": "ok"},
    ]
    text, entries = ce.to_srt(bad)
    assert text == "1\n00:00:00,000 --> 00:00:01,000\nok\n\n"
    assert _rules(entries) == [("CAP-EXPORT", "WARN")] * 5
    vtt, ventries = ce.to_vtt(bad)
    assert vtt == "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nok\n\n"
    assert len(ventries) == 5


def test_blank_lines_inside_cue_text_are_removed():
    text, _ = ce.to_srt([{"t0": 0, "t1": 1, "text": "a\n\nb"}])
    assert text == "1\n00:00:00,000 --> 00:00:01,000\na\nb\n\n"


def test_empty_cue_list_gives_valid_empty_files():
    assert ce.to_srt([]) == ("", [])
    assert ce.to_vtt([]) == ("WEBVTT\n\n", [])


# ---- write_sidecars -----------------------------------------------------

def test_write_sidecars_files_utf8_no_bom_and_bad_lang_skipped(tmp_path):
    out = tmp_path / "side"
    paths, entries = ce.write_sidecars(
        {"hi": CUES, "en": [{"t0": 0, "t1": 1, "text": "Yes"}], "BAD": CUES},
        str(out), "ep1")
    names = sorted(os.path.basename(p) for p in paths)
    assert names == ["ep1.en.srt", "ep1.en.vtt", "ep1.hi.srt", "ep1.hi.vtt"]
    assert paths == sorted(paths)
    for p in paths:
        raw = open(p, "rb").read()
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert b"\r" not in raw
        raw.decode("utf-8")
    assert "नमस्ते" in open(out / "ep1.hi.srt", encoding="utf-8").read()
    assert not (out / "ep1.BAD.srt").exists()
    assert any(e["level"] == "WARN" and "BAD" in e["message"] for e in entries)


def test_write_sidecars_rejects_stem_with_path_separator(tmp_path):
    paths, entries = ce.write_sidecars({"hi": CUES}, str(tmp_path), "../evil")
    assert paths == []
    assert _rules(entries) == [("CAP-EXPORT", "FAIL")]


# ---- words_from_elevenlabs ----------------------------------------------

ALIGN = {
    "characters": ["H", "i", " ", "y", "o"],
    "character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4],
    "character_end_times_seconds": [0.1, 0.2, 0.3, 0.4, 0.5],
}
EXPECT_WORDS = [
    {"text": "Hi", "t0": 0.0, "t1": 0.2, "conf": 1.0},
    {"text": "yo", "t0": 0.3, "t1": 0.5, "conf": 1.0},
]


@pytest.mark.parametrize("doc", [
    ALIGN,
    {"alignment": ALIGN},
    {"normalized_alignment": ALIGN},
])
def test_elevenlabs_parse_top_level_and_nested(doc):
    words, entries = ce.words_from_elevenlabs(doc)
    assert entries == []
    assert len(words) == 2
    for got, want in zip(words, EXPECT_WORDS):
        assert got["text"] == want["text"]
        assert got["t0"] == pytest.approx(want["t0"])
        assert got["t1"] == pytest.approx(want["t1"])
        assert got["conf"] == 1.0


def test_elevenlabs_broken_length_is_fail():
    bad = dict(ALIGN, character_end_times_seconds=[0.1, 0.2])
    words, entries = ce.words_from_elevenlabs(bad)
    assert words == []
    assert _rules(entries) == [("CAP-ALIGN", "FAIL")]


def test_elevenlabs_non_numeric_time_is_fail():
    bad = dict(ALIGN, character_start_times_seconds=[0.0, "x", 0.2, 0.3, 0.4])
    words, entries = ce.words_from_elevenlabs(bad)
    assert words == []
    assert _rules(entries) == [("CAP-ALIGN", "FAIL")]


def test_elevenlabs_junk_input_never_raises():
    assert ce.words_from_elevenlabs(None)[0] == []
    assert _rules(ce.words_from_elevenlabs("junk")[1]) == [("CAP-ALIGN", "FAIL")]


# ---- karaoke_text -------------------------------------------------------

def _word(text, t0, t1, conf=0.9):
    return {"text": text, "t0": t0, "t1": t1, "conf": conf}


GOOD = [_word("Hi", 0.0, 0.2), _word("yo", 0.3, 0.5)]


def test_karaoke_word_mode_centiseconds_sum_to_line_duration():
    text, mode, entries = ce.karaoke_text(GOOD, line_t0=0.0, line_t1=0.5)
    assert mode == "word"
    assert entries == []
    assert text == r"{\k30}Hi {\k20}yo"
    assert sum(int(x) for x in re.findall(r"\\k(\d+)", text)) == 50


def test_karaoke_low_confidence_falls_back_to_phrase():
    words = [_word("Hi", 0.0, 0.2, 0.9), _word("yo", 0.3, 0.5, 0.2)]
    text, mode, entries = ce.karaoke_text(words, min_conf=0.6)
    assert mode == "phrase"
    assert text == "Hi yo"
    assert _rules(entries) == [("CAP-ALIGN", "WARN")]
    assert "low confidence" in entries[0]["message"]


def test_karaoke_non_monotonic_falls_back_to_phrase():
    words = [_word("Hi", 0.0, 0.2), _word("yo", 0.1, 0.5)]
    text, mode, entries = ce.karaoke_text(words)
    assert mode == "phrase" and text == "Hi yo"
    assert "non-monotonic timing" in entries[0]["message"]


def test_karaoke_short_word_falls_back_to_phrase():
    words = [_word("Hi", 0.0, 0.02), _word("yo", 0.3, 0.5)]
    text, mode, entries = ce.karaoke_text(words, min_word_s=0.04)
    assert mode == "phrase"
    assert "word shorter than min_word_s" in entries[0]["message"]


def test_karaoke_synthetic_equal_split():
    text, mode, entries = ce.karaoke_text(["one", "two"], line_t0=0.0, line_t1=1.0)
    assert mode == "synthetic"
    assert text == r"{\k50}one {\k50}two"
    assert _rules(entries) == [("CAP-ALIGN", "WARN")]
    assert "synthetic equal split" in entries[0]["message"]


def test_karaoke_plain_strings_without_line_times_is_phrase():
    text, mode, entries = ce.karaoke_text(["one", "two"])
    assert mode == "phrase" and text == "one two"
    assert "missing timing" in entries[0]["message"]


def test_karaoke_escapes_ass_specials():
    text, mode, _ = ce.karaoke_text(["a{b}\\c"], line_t0=0.0, line_t1=1.0)
    assert mode == "synthetic"
    assert text == r"{\k100}a(b)c"


# ---- timing_error_stats -------------------------------------------------

def test_timing_error_stats_numbers():
    pred = [{"t0": 1.0}, {"t0": 2.0}, {"t0": 3.5}, {"t0": 10.0}]
    truth = [{"t0": 1.1}, {"t0": 2.0}, {"t0": 3.0}, {"t0": 8.0}]
    stats = ce.timing_error_stats(pred, truth)
    assert stats["n"] == 4
    assert stats["median_s"] == pytest.approx(0.3)
    assert stats["p90_s"] == pytest.approx(2.0)   # nearest rank: ceil(0.9*4)=4th value
    assert stats["max_s"] == pytest.approx(2.0)


def test_timing_error_stats_empty():
    assert ce.timing_error_stats([], []) == {
        "n": 0, "median_s": None, "p90_s": None, "max_s": None}


# ---- contact_sheet_plan (plan only, nothing runs) -----------------------

def test_contact_sheet_plan_argv_exact_relative_names_and_cwd(tmp_path, no_subprocess):
    ass = tmp_path / "caps" / "ep1.ass"
    out = tmp_path / "sheet"
    fonts = tmp_path / "caps" / "fonts"   # the relative fontsdir name only resolves when it sits beside the ass file
    plans, entries = ce.contact_sheet_plan(
        str(ass), [{"id": "c1", "t": 2.5}], 1080, 1920, str(out),
        fontsdir=str(fonts), bg="#202020", ffmpeg="ffmpeg")
    assert entries == []
    assert len(plans) == 1
    png = os.path.join(str(out), "c1.png")
    assert plans[0] == {
        "id": "c1",
        "png": png,
        "argv": ["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i",
                 "color=c=202020:s=1080x1920:r=24:d=3.5",
                 "-vf", "subtitles=ep1.ass:fontsdir=fonts",
                 "-ss", "2.500", "-frames:v", "1", png],
        "cwd": str(tmp_path / "caps"),
    }


def test_contact_sheet_plan_without_fontsdir(tmp_path, no_subprocess):
    plans, _ = ce.contact_sheet_plan(
        str(tmp_path / "ep1.ass"), [{"id": "a", "t": 0}], 640, 360, str(tmp_path))
    assert "subtitles=ep1.ass" in plans[0]["argv"]
    assert "-vf" in plans[0]["argv"]
    assert not any("fontsdir" in a for a in plans[0]["argv"])


def test_contact_sheet_plan_skips_bad_and_duplicate_ids(tmp_path, no_subprocess):
    cards = [{"id": "ok", "t": 1}, {"id": "bad id", "t": 1},
             {"id": "ok", "t": 2}, {"id": "fine.1_x-2", "t": 3}]
    plans, entries = ce.contact_sheet_plan(
        str(tmp_path / "ep.ass"), cards, 100, 100, str(tmp_path))
    assert [p["id"] for p in plans] == ["ok", "fine.1_x-2"]
    assert [e["level"] for e in entries] == ["WARN", "WARN"]
    assert all(e["rule"] == "CAP-EXPORT" for e in entries)


# ---- frame_hash / compare_frames ----------------------------------------

def test_frame_hash_equal_for_identical_pixels_and_differs_otherwise(tmp_path):
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(a)
    Image.new("RGB", (8, 8), (10, 20, 30)).save(b)
    Image.new("RGB", (8, 8), (200, 20, 30)).save(c)
    ha, hb, hc = ce.frame_hash(str(a)), ce.frame_hash(str(b)), ce.frame_hash(str(c))
    assert ha and len(ha) == 64
    assert ha == hb
    assert ha != hc


def test_frame_hash_none_when_unreadable(tmp_path):
    assert ce.frame_hash(str(tmp_path / "missing.png")) is None


def test_compare_frames(tmp_path):
    a, c = tmp_path / "a.png", tmp_path / "c.png"
    Image.new("RGB", (4, 4), (1, 2, 3)).save(a)
    Image.new("RGB", (4, 4), (9, 9, 9)).save(c)
    ref = ce.frame_hash(str(a))
    assert ce.compare_frames(str(a), ref) == []
    diff = ce.compare_frames(str(c), ref)
    assert _rules(diff) == [("CAP-QA", "FAIL")]
    assert diff[0]["message"] == "caption frame differs from the reference"


# ---- preflight ----------------------------------------------------------

FULL = "configuration: --enable-libass --enable-libharfbuzz --enable-libfribidi --enable-fontconfig"


def test_preflight_all_present_is_empty():
    assert ce.preflight_from_buildconf(FULL) == []


def test_preflight_no_libass_is_fail():
    text = FULL.replace("--enable-libass ", "")
    assert _rules(ce.preflight_from_buildconf(text)) == [("CAP-PREFLIGHT", "FAIL")]


def test_preflight_no_harfbuzz_is_fail():
    text = FULL.replace("--enable-libharfbuzz ", "")
    assert _rules(ce.preflight_from_buildconf(text)) == [("CAP-PREFLIGHT", "FAIL")]


def test_preflight_no_fribidi_is_warn():
    text = FULL.replace("--enable-libfribidi ", "")
    assert _rules(ce.preflight_from_buildconf(text)) == [("CAP-PREFLIGHT", "WARN")]


def test_ffmpeg_preflight_missing_binary_is_one_fail():
    entries = ce.ffmpeg_preflight(ffmpeg="definitely_not_a_binary")
    assert _rules(entries) == [("CAP-PREFLIGHT", "FAIL")]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_ffmpeg_preflight_real_call_returns_only_preflight_entries():
    entries = ce.ffmpeg_preflight()
    assert isinstance(entries, list)
    assert all(e["rule"] == "CAP-PREFLIGHT" for e in entries)


def test_contact_sheet_plan_png_is_absolute_and_a_misplaced_fonts_dir_warns(tmp_path, no_subprocess, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plans, entries = ce.contact_sheet_plan(str(tmp_path / "caps" / "a.ass"), [{"id": "c1", "t": 1}], 540, 960, "sheet",
                                           fontsdir=str(tmp_path / "elsewhere" / "fonts"))
    assert os.path.isabs(plans[0]["png"]) and plans[0]["png"] == str(tmp_path / "sheet" / "c1.png")
    assert any("fonts dir is not next to the ass file" in e["message"] for e in entries)
