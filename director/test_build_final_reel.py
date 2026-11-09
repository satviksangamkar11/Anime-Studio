"""Offline tests for build_final_reel: mux argv, waived findings, caption spec v2 (card limits, colour and scale tags, PlayRes and
position, the burn filter) and the owner's two Hindi caption fixes. No ffmpeg."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_final_reel as b  # noqa: E402

FONTS = Path(__file__).resolve().parents[1] / "styles" / "fonts"


def rows():
    return [{"id": "SHOT-001", "editorial_duration_sec": 6.0}, {"id": "SHOT-002", "editorial_duration_sec": 5.0},
            {"id": "SHOT-003", "editorial_duration_sec": 7.0}]


def test_mux_argv_uses_one_voice_file_per_shot_that_has_one(tmp_path):
    (tmp_path / "hi").mkdir()
    (tmp_path / "hi" / "SHOT-001.wav").write_bytes(b"x")
    (tmp_path / "hi" / "SHOT-003.wav").write_bytes(b"x")                   # shot 2 has no voice file: it gets silence of its length
    argv, total = b.mux_argv(rows(), "hi", tmp_path, tmp_path / "v.mp4", tmp_path / "out.mp4", tmp_path / "c.ass", "styles/fonts")
    assert total == 18.0 and argv[0] == "ffmpeg"
    assert [a for a in argv if a.endswith(".wav")] == [str(tmp_path / "hi" / "SHOT-001.wav"), str(tmp_path / "hi" / "SHOT-003.wav")]
    graph = argv[argv.index("-filter_complex") + 1]
    assert "[master]" in graph and "anullsrc" in graph and "ass=filename=" in graph and "shaping=complex" in graph
    assert "concat=n=3:v=0:a=1[vo_full]" in graph
    assert argv[-1] == str(tmp_path / "out.mp4") and "-ac" in argv


def test_only_script_level_findings_are_waived():
    assert b.WAIVED == {"NARRATION_COVERAGE_LOW", "NARRATION_WORDS_LOW", "DEAD_AIR_PAUSE", "CLOSING_NO_ANCHOR_PAYOFF", "CLOSING_MOUTH_OPEN"}
    for must_block in ("VO_OVERFLOW_ERROR", "VO_MISSING", "FONT_MISSING", "GLYPH_MISSING", "TIME-01", "NO_CAPTIONS"):
        assert must_block not in b.WAIVED


def test_cards_are_at_most_four_words_for_english_and_cut_at_sentence_ends():
    text = "Brahma made the gods, the sages and Daksha. Then, from his deep thought, a daughter was born."
    cards = b.split_cards(text, "en")
    assert all(len(c) <= 4 for c in cards) and all(not w.endswith(".") for c in cards for w in c[:-1])
    assert [w for c in cards for w in c] == text.split()
    assert b.split_cards("At dawn, sages came.", "en") == [["At", "dawn,", "sages", "came."]]


@pytest.mark.parametrize("lang", ["hi", "mr"])
def test_cards_are_at_most_three_words_and_eighteen_characters_for_hindi_and_marathi(lang):
    text = "सती कैसे जन्मीं और ब्याही? ब्रह्मा ने दक्ष की कन्या से विवाह किया, और फिर शक्ति प्रकट हुई।"
    cards = b.split_cards(text, lang)
    assert all(len(c) <= 3 and len(" ".join(c)) <= 18 for c in cards)
    assert [w for c in cards for w in c] == text.split()


def test_no_card_is_punctuation_only_and_stray_space_dot_is_joined():
    cards = b.split_cards("The sages began . Then the gods came.", "en")
    assert ["began."] == [w for c in cards for w in c if w.startswith("began")]
    for c in b.split_cards("Sages began , . Then came . Gods.", "en"):
        assert all(re.search(r"\w", w) for w in c)


def test_fits_callback_adds_splits_until_the_card_wraps_in_two_lines():
    cards = b.split_cards("one two three four", "en", fits=lambda s: len(s) <= 8)
    assert all(len(" ".join(c)) <= 8 for c in cards)


def test_word_cues_cover_the_line_time_without_gaps_or_overlap():
    cues = b.word_cues("Brahma made the gods, the sages and Daksha. Then, from his deep thought, a daughter was born.", 18.0, 25.0)
    assert cues[0]["t0"] == 18.0 and abs(cues[-1]["t1"] - 25.0) < 0.01
    for a, c in zip(cues, cues[1:]):
        assert abs(a["t1"] - c["t0"]) < 0.01
    for c in cues:
        ws = c["words"]
        assert ws[0]["t0"] == c["t0"] and all(x["t1"] > x["t0"] for x in ws) and all(x["t1"] <= y["t0"] + 1e-6 for x, y in zip(ws, ws[1:]))


def _cue(text, t0=0.0, t1=3.0, lang="en"):
    return b.word_cues(text, t0, t1, lang)


def test_caption_ass_has_playres_position_font_and_the_green_pop_on_one_word():
    ass = b.caption_ass(_cue("At dawn"), "en", FONTS)
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "Style: Cap,Mukta ExtraBold,112," in ass and ",9,4,5," in ass and "&H66000000&" in ass
    ev = [ln for ln in ass.splitlines() if ln.startswith("Dialogue")]
    assert len(ev) == 2                                              # one event per spoken word
    assert all("\\an5\\pos(510,1290)" in ln for ln in ev)
    for i, ln in enumerate(ev):
        assert ln.count("\\fscx108\\fscy108") == 1                               # the pop: one word per event
        assert ln.count("{\\1c" + b.GREEN_BGR[:-1]) == 1                         # the green tag: one word per event
        assert ln.count("\\fscx100\\fscy100}") == 1                              # scale reset after the word
        assert "{\\1c&H004EFF3C&\\fscx108\\fscy108}" in ln and "&H004EFF3C&" in b.GREEN_BGR


def test_green_is_the_right_bgr_colour_for_3cff4e():
    assert b.GREEN_BGR == "&H004EFF3C&"                       # #3CFF4E: R 3C, G FF, B 4E, ASS order BBGGRR
    assert b.WHITE_BGR == "&H00FFFFFF&"


def test_caption_ass_hindi_uses_its_own_size():
    ass = b.caption_ass(_cue("सती कैसे जन्मीं", lang="hi"), "hi", FONTS)
    assert "Style: Cap,Mukta ExtraBold,104," in ass and ",9,4,5," in ass


def test_two_line_card_keeps_its_bottom_line_at_y_1290():
    from core import caption_text as ct
    words = ["Brahma", "made", "the", "gods"]
    cue = {"t0": 0.0, "t1": 2.0, "words": [{"text": w, "t0": i * 0.5, "t1": (i + 1) * 0.5} for i, w in enumerate(words)]}
    font = FONTS / b.CAPTION_FONT_FILE
    lines, _ = ct.wrap_lines(" ".join(words), str(font), b.CAPTION_SIZE["en"], b.CAPTION_MAX_W, 2)
    assert len(lines) == 2                                           # really a 2-line card
    asc, desc = ct._font(str(font), b.CAPTION_SIZE["en"]).getmetrics()
    line_h = asc + desc
    ev = [ln for ln in b.caption_ass([cue], "en", FONTS).splitlines() if ln.startswith("Dialogue")]
    cy = int(re.search(r"\\pos\(510,(\d+)\)", ev[0]).group(1))
    assert abs(cy - (1290 - line_h / 2)) <= 1                        # the centre moved up by half a line
    assert abs((cy + line_h / 2) - 1290) <= 1                        # so the bottom line's centre stays at 1290
    assert cy + line_h / 2 + 0.5 * line_h <= 1420                    # and the bottom of the block stays inside the safe zone


def test_one_line_card_stays_at_the_spec_position():
    ev = [ln for ln in b.caption_ass(_cue("At dawn"), "en", FONTS).splitlines() if ln.startswith("Dialogue")]
    assert all("\\an5\\pos(510,1290)" in ln for ln in ev)


def test_burn_filter_is_ass_with_complex_shaping():
    from h3 import gate_d_audio as gd
    assert gd.build_subtitles_filter("captions/x.ass", "styles/fonts").endswith(":shaping=complex")
    assert gd.build_subtitles_filter("captions/x.ass", "styles/fonts").startswith("ass=filename=")


@pytest.mark.parametrize("line_id,lang_text,old,new", [
    ("SHOT-003-D1", "सती कैसे जन्मीं और ब्याही?", "ब्याही", "ब्याहीं"),
    ("SHOT-010-D1", "आपने कहा, सब पर चलाओ। मेरी गलती क्या?", "गलती", "ग़लती"),
])
def test_owner_hindi_caption_fixes_apply_and_keep_the_word_timing(line_id, lang_text, old, new):
    assert b.CAPTION_FIXES[(line_id, "hi")] == (old, new)
    shot = line_id.rsplit("-D", 1)[0]
    rw = [{"id": shot, "editorial_duration_sec": 6.0,
           "audio_and_dialogue_track": {"narration_by_lang": {}, "dialogue_by_lang": {"hi": [{"text": lang_text}]}}}]
    rep = [{"shot": shot, "lang": "hi", "lines": [{"id": line_id, "start": 0.5, "end": 5.5}]}]
    cues = b.spoken_cues_real(rw, rep, "hi")
    words = [w["text"] for c in cues for w in c["words"]]
    assert new in " ".join(words) and old not in " ".join(words).replace(new, "")
    assert len(words) == len(lang_text.split())                       # same word count, so the timing is unchanged
    assert cues[0]["t0"] == 0.5 and abs(cues[-1]["t1"] - 5.5) < 0.01
    plain = b.spoken_cues_real(rw, rep, "en")
    assert plain == []                                                # the fix is for hi only
