"""The shared caption engine's Gate D features: cards, face avoidance, synthetic karaoke, required fonts, forbidden top zone."""
import re
from pathlib import Path

import pytest

from core.captions import build_ass
from core.style_pack import load_core

FONTS = Path(__file__).resolve().parents[2] / "styles" / "fonts"
CORE = load_core()
PACK = {"typography": {"subtitle_latin": "Inter", "subtitle_devanagari": "Noto Sans Devanagari", "min_px_at_1080w": 22,
                       "lockup": {"leader": "devanagari", "latin_size_frac": 0.4, "latin_opacity": 0.7, "gap_px_1080": 16}}}


def lead(text):
    return [ln for ln in text.splitlines() if ln.startswith("Dialogue:") and ",Lead," in ln]


def pos_y(line):
    return int(re.search(r"\\pos\(\d+,(\d+)\)", line).group(1))


def words_in(line):
    return len(re.sub(r"\{[^}]*\}", "", line.split("}", 1)[1]).split())


def test_long_cue_is_split_into_balanced_cards_covering_the_cue():
    text = "one two three four five six seven eight nine ten eleven twelve thirteen"
    ass, _ = build_ass([{"t0": 1.0, "t1": 7.0, "text": text}], PACK, CORE, 1440, 2560, "en")
    rows = lead(ass)
    assert [words_in(r) for r in rows] == [5, 5, 3]                      # 13 words -> 5, 5, 3
    assert rows[0].split(",")[1] == "0:00:01.00" and rows[-1].split(",")[2] == "0:00:07.00"


def test_short_cue_is_not_split_and_aligned_words_are_never_split():
    ass, _ = build_ass([{"t0": 0, "t1": 2, "text": "a b c d e f"}], PACK, CORE, 1080, 1920, "en")
    assert len(lead(ass)) == 1
    words = [{"text": w, "t0": i * 0.3, "t1": (i + 1) * 0.3, "conf": 1.0} for i, w in enumerate("a b c d e f g h".split())]
    ass, _ = build_ass([{"t0": 0, "t1": 2.4, "text": "a b c d e f g h", "words": words}], PACK, CORE, 1080, 1920, "en")
    assert len(lead(ass)) == 1


def test_synthetic_karaoke_splits_each_card_equally_per_word():
    ass, ents = build_ass([{"t0": 0, "t1": 2, "text": "one two three four"}], PACK, CORE, 1080, 1920, "en", karaoke=True)
    row = lead(ass)[0]
    assert re.findall(r"\{\\k(\d+)\}", row) == ["50", "50", "50", "50"] and "\\2c&H00FFFFFF&" in row
    assert not [e for e in ents if "synthetic" in e["message"]]          # asked for with karaoke=True: no warning


def test_a_caption_over_a_face_is_raised_until_it_clears_it():
    cue = [{"t0": 0, "t1": 1, "text": "one two"}]
    y0 = pos_y(lead(build_ass(cue, PACK, CORE, 1440, 2560, "en")[0])[0])
    face = (0, int(y0) - 60, 1440, int(y0) + 60)                          # covers the default caption position
    ass, ents = build_ass(cue, PACK, CORE, 1440, 2560, "en", face_boxes=[face])
    assert pos_y(lead(ass)[0]) < y0 and not [e for e in ents if "face" in e["message"]]
    whole = (0, 0, 1440, 2560)                                           # no clear spot anywhere
    ass2, ents2 = build_ass(cue, PACK, CORE, 1440, 2560, "en", face_boxes=[whole])
    assert pos_y(lead(ass2)[0]) == y0 and any("covers a face" in e["message"] for e in ents2)


@pytest.mark.skipif(not (FONTS / "Inter-Variable.ttf").is_file(), reason="repo fonts missing")
def test_required_fonts_missing_is_a_fail_and_present_is_clean(tmp_path):
    cue = [{"t0": 0, "t1": 1, "text": "Hello there"}]
    _, ents = build_ass(cue, PACK, CORE, 1080, 1920, "en", font_dir=tmp_path, require_fonts=True)
    assert any(e["rule"] == "CAP-FONT" and e["level"] == "FAIL" for e in ents)
    _, ents = build_ass(cue, PACK, CORE, 1080, 1920, "en", font_dir=FONTS, require_fonts=True)
    assert not [e for e in ents if e["level"] == "FAIL"]
    _, ents = build_ass(cue, PACK, CORE, 1080, 1920, "en", require_fonts=True)     # no font dir at all
    assert any(e["rule"] == "CAP-FONT" for e in ents)


def test_a_caption_inside_the_forbidden_top_zone_is_a_fail():
    core = dict(CORE, safe_zone_frac=dict(CORE["safe_zone_frac"], top=0.9, caption_band=[0.50, 0.65]))
    _, ents = build_ass([{"t0": 0, "t1": 1, "text": "Hi"}], PACK, core, 1080, 1920, "en")
    assert any(e["rule"] == "CAP-GEOMETRY" and e["level"] == "FAIL" for e in ents)
    _, ents = build_ass([{"t0": 0, "t1": 1, "text": "Hi"}], PACK, CORE, 1080, 1920, "en")
    assert not [e for e in ents if e["rule"] == "CAP-GEOMETRY"]
