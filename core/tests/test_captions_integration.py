"""build_ass with font_dir, emphasis, karaoke words, mixed scripts and safe-zone templates (checklist 9.2, 9.4, 9.5, 9.7, 9.8)."""
import re
from pathlib import Path

import pytest

from core.captions import build_ass
from core.style_pack import load_core

FONTS = Path(__file__).resolve().parents[2] / "styles" / "fonts"
needs_fonts = pytest.mark.skipif(not (FONTS / "NotoSansDevanagari-Variable.ttf").is_file(), reason="repo fonts missing")
CORE = load_core()
PACK = {"typography": {"subtitle_latin": "Inter", "subtitle_devanagari": "Noto Sans Devanagari", "min_px_at_1080w": 22,
                       "lockup": {"leader": "devanagari", "latin_size_frac": 0.4, "latin_opacity": 0.7, "gap_px_1080": 16}}}
LONG = "यमुनेच्या काठावर बाळकृष्ण गाई चारत होता आणि सर्वजण त्याला पाहत होते आणि हसत होते"
BREAK = "\\N"   # the ASS line break: backslash + N


def lead(text):
    return [ln for ln in text.splitlines() if ln.startswith("Dialogue:") and ",Lead," in ln]


def body_of(line):
    return line.split("}", 1)[1]


def pos_y(line):
    return int(re.search(r"\\pos\(\d+,(\d+)\)", line).group(1))


@needs_fonts
def test_measured_wrap_gives_at_most_two_lines_with_explicit_breaks():
    text, entries = build_ass([{"t0": 0, "t1": 3, "text": LONG}], PACK, CORE, 1080, 1920, "mr", font_dir=FONTS)
    body = body_of(lead(text)[0])
    assert body.count(BREAK) == 1
    assert not [e for e in entries if e["level"] == "FAIL"]


@needs_fonts
def test_text_that_cannot_fit_in_two_lines_is_a_fail_entry():
    huge = " ".join(["बाळकृष्णाच्या"] * 30)
    _, entries = build_ass([{"t0": 0, "t1": 3, "text": huge}], PACK, CORE, 1080, 1920, "mr", font_dir=FONTS)
    assert any(e["rule"] == "CAP-WRAP" and e["level"] == "FAIL" for e in entries)


@needs_fonts
def test_a_missing_glyph_is_a_fail_entry():
    pack = {"typography": dict(PACK["typography"], subtitle_devanagari="Inter")}   # Inter has no Devanagari
    _, entries = build_ass([{"t0": 0, "t1": 3, "text": "क्ष"}], pack, CORE, 1080, 1920, "hi", font_dir=FONTS)
    assert any(e["rule"] == "CAP-GLYPH" and e["level"] == "FAIL" for e in entries)


def test_without_font_dir_the_output_is_the_old_estimate_path():
    text, _ = build_ass([{"t0": 0, "t1": 3, "text": "Hello there"}], PACK, CORE, 1080, 1920, "en")
    assert lead(text)[0].endswith("}Hello there")


def test_emphasis_word_gets_the_emphasis_colour_and_scale():
    text, _ = build_ass([{"t0": 0, "t1": 3, "text": "Why is he blue?", "emphasis": ["blue"]}], PACK, CORE, 1080, 1920, "en")
    body = body_of(lead(text)[0])
    assert "\\fscx112\\fscy112}blue" in body and body.index("Why is he") < body.index("\\fscx112")
    assert "?" in body and "\ue000" not in body and "\ue001" not in body


def test_mixed_script_line_gets_font_overrides():
    text, _ = build_ass([{"t0": 0, "t1": 3, "text": "कृष्ण is here आज"}], PACK, CORE, 1080, 1920, "hi")
    body = body_of(lead(text)[0])
    assert "{\\fnInter}" in body and "{\\fnNoto Sans Devanagari}" in body


def test_karaoke_words_in_word_mode():
    words = [{"text": "कृष्ण", "t0": 0.0, "t1": 0.6, "conf": 1.0}, {"text": "कहाँ", "t0": 0.6, "t1": 1.5, "conf": 0.9}]
    text, entries = build_ass([{"t0": 0, "t1": 1.5, "text": "कृष्ण कहाँ", "words": words}], PACK, CORE, 1080, 1920, "hi")
    line = lead(text)[0]
    assert "{\\k60}" in line and "{\\k90}" in line and "\\2c&H00FFFFFF&" in line
    assert not [e for e in entries if e["rule"] == "CAP-ALIGN"]


def test_karaoke_low_confidence_falls_back_to_the_plain_line():
    words = [{"text": "कृष्ण", "t0": 0.0, "t1": 0.6, "conf": 0.2}, {"text": "कहाँ", "t0": 0.6, "t1": 1.5, "conf": 0.9}]
    text, entries = build_ass([{"t0": 0, "t1": 1.5, "text": "कृष्ण कहाँ", "words": words}], PACK, CORE, 1080, 1920, "hi")
    assert "\\k" not in lead(text)[0] and lead(text)[0].endswith("}कृष्ण कहाँ")
    assert any(e["rule"] == "CAP-ALIGN" for e in entries)


@needs_fonts
def test_karaoke_long_line_is_wrapped_into_two_lines_without_losing_words():
    toks = LONG.split(" ")
    words = [{"text": t, "t0": i * 0.4, "t1": (i + 1) * 0.4, "conf": 1.0} for i, t in enumerate(toks)]
    text, _ = build_ass([{"t0": 0, "t1": len(toks) * 0.4, "text": LONG, "words": words}], PACK, CORE, 1080, 1920, "mr",
                        font_dir=FONTS)
    body = body_of(lead(text)[0])
    assert BREAK in body and len(re.findall(r"\{\\k\d+\}", body)) == len(toks)


def test_templates_move_the_caption_band_and_an_unknown_one_warns():
    cue = [{"t0": 0, "t1": 3, "text": "Hi"}]
    y_reels = pos_y(lead(build_ass(cue, PACK, CORE, 1080, 1920, "en", template="reels")[0])[0])
    y_youtube = pos_y(lead(build_ass(cue, PACK, CORE, 1080, 1920, "en", template="youtube")[0])[0])
    assert y_reels == round(0.575 * 1920) and y_youtube == round(0.86 * 1920)
    _, entries = build_ass(cue, PACK, CORE, 1080, 1920, "en", template="nope")
    assert any("template" in e["message"] for e in entries)
