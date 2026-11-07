import copy
import math
import re

import pytest

from core import captions
from core.captions import ass_time, build_ass, contrast_ratio, wrap_estimate
from core.style_pack import load_core

CORE = load_core()
BAND = CORE["safe_zone_frac"]["caption_band"]

PACK = {
    "pack_id": "test_pack",
    "typography": {
        "display": None,
        "sacred": None,
        "subtitle_latin": "LatinTest",
        "subtitle_devanagari": "DevaTest",
        "min_px_at_1080w": 10,
        "font_dir": "fonts",
        "lockup": {"leader": "devanagari", "latin_size_frac": 0.4,
                   "latin_opacity": 0.7, "gap_px_1080": 16},
    },
}
DEVA = "नमस्ते"


def _core_with(**retention):
    core = copy.deepcopy(CORE)
    core["retention"].update(retention)
    return core


def _dialogues(text):
    return [line for line in text.split("\n") if line.startswith("Dialogue:")]


def _style_fields(text):
    out = {}
    for line in text.split("\n"):
        if line.startswith("Style: "):
            fields = line[len("Style: "):].split(",")
            out[fields[0]] = fields
    return out


def _pos_y(line):
    m = re.search(r"\\pos\((-?[\d.]+),(-?[\d.]+)\)", line)
    assert m, line
    return float(m.group(2))


def _warns(entries):
    return [e for e in entries if e["level"] == "WARN"]


def _messages(entries):
    return " | ".join(e["message"] for e in entries)


# ---- header ----
@pytest.mark.parametrize("w,h", [(768, 1344), (1080, 1920)])
def test_header_play_res(w, h):
    text, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hi"}], PACK, CORE, w, h)
    assert f"PlayResX: {w}\n" in text
    assert f"PlayResY: {h}\n" in text
    assert "WrapStyle: 2\n" in text
    assert "ScaledBorderAndShadow: yes\n" in text
    assert "ScriptType: v4.00+\n" in text
    assert "\r" not in text
    assert "[V4+ Styles]" in text and "[Events]" in text
    assert set(_style_fields(text)) == {"Lead", "Sub"}


def test_sizes_scale_with_width():
    text, _ = build_ass([{"t0": 0, "t1": 2, "text": "Hi"}], PACK, CORE, 768, 1344)
    lead = int(_style_fields(text)["Lead"][2])
    assert lead >= 34 * 768 / 1080
    assert lead == math.ceil(34 * 768 / 1080)
    text, _ = build_ass([{"t0": 0, "t1": 2, "text": "Hi"}], PACK, CORE, 1080, 1920)
    assert int(_style_fields(text)["Lead"][2]) == 34


# ---- placement ----
def test_positions_inside_caption_band():
    cues = [{"t0": 0, "t1": 2, "text": "Hi", "latin": "Hello"},
            {"t0": 2, "t1": 4, "text": "Only lead"}]
    text, entries = build_ass(cues, PACK, CORE, 768, 1344)
    top, bottom = BAND[0] * 1344, BAND[1] * 1344
    lines = _dialogues(text)
    assert len(lines) == 3
    for line in lines:
        assert top <= _pos_y(line) <= bottom
    assert _pos_y(lines[0]) == pytest.approx(sum(BAND) / 2 * 1344, abs=1)   # the lead sits at the band centre
    assert not _warns(entries)


def test_lockup_latin_below_lead_by_expected_gap():
    text, _ = build_ass([{"t0": 0, "t1": 2, "text": "Hi", "latin": "Hello"}],
                        PACK, CORE, 1080, 1920)
    lines = _dialogues(text)
    lead_line = [ln for ln in lines if ",Lead," in ln][0]
    latin_line = [ln for ln in lines if ",Sub," in ln][0]
    lead_size, latin_size = 34, round(0.4 * 34)
    expected = lead_size / 2 + 16 + latin_size / 2
    assert _pos_y(latin_line) - _pos_y(lead_line) == pytest.approx(expected, abs=1)


def test_latin_alpha_is_4D_for_opacity_0_7():
    text, _ = build_ass([{"t0": 0, "t1": 2, "text": "Hi", "latin": "Hello"}],
                        PACK, CORE, 1080, 1920)
    latin_line = [ln for ln in _dialogues(text) if ",Sub," in ln][0]
    assert "\\alpha&H4D&" in latin_line


def test_latin_size_is_point4_of_lead():
    text, _ = build_ass([{"t0": 0, "t1": 2, "text": "Hi", "latin": "Hello"}],
                        PACK, CORE, 1080, 1920)
    styles = _style_fields(text)
    assert int(styles["Sub"][2]) == round(0.4 * int(styles["Lead"][2]))


def test_latin_raised_to_minimum_with_warn():
    pack = copy.deepcopy(PACK)
    pack["typography"]["min_px_at_1080w"] = 20
    pack["typography"]["lockup"]["latin_size_frac"] = 0.2
    text, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hi", "latin": "Hello"}],
                              pack, CORE, 1080, 1920)
    assert int(_style_fields(text)["Sub"][2]) == 20
    assert "raised to the minimum" in _messages(_warns(entries))


def test_pair_shifted_up_when_it_leaves_band():
    core = copy.deepcopy(CORE)
    core["safe_zone_frac"]["caption_band"] = [0.60, 0.62]
    text, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hi", "latin": "Hello"}],
                              PACK, core, 1080, 1920)
    bottom = 0.62 * 1920
    for line in _dialogues(text):
        assert _pos_y(line) <= bottom
    assert "shifted up" in _messages(_warns(entries))


def test_long_cue_reported_as_too_long():
    text, entries = build_ass([{"t0": 0, "t1": 2, "text": "x" * 200}], PACK, CORE, 768, 1344)
    assert "one line" in _messages(_warns(entries))
    assert len(_dialogues(text)) == 1


# ---- timing ----
def test_short_cue_extended_to_min_on_screen():
    text, entries = build_ass([{"t0": 0.5, "t1": 0.9, "text": "Hi"}], PACK, CORE, 1080, 1920)
    line = _dialogues(text)[0]
    fields = line.split(",", 9)
    assert fields[1] == "0:00:00.50"
    assert fields[2] == "0:00:01.70"
    assert not _warns(entries)


def test_extension_that_would_overlap_keeps_time_and_warns():
    cues = [{"t0": 0, "t1": 0.5, "text": "A"}, {"t0": 0.6, "t1": 2.0, "text": "B"}]
    text, entries = build_ass(cues, PACK, CORE, 1080, 1920)
    first = _dialogues(text)[0].split(",", 9)
    assert first[2] == "0:00:00.50"
    assert "overlap" in _messages(_warns(entries))


def test_cues_sorted_by_start_time():
    cues = [{"t0": 5, "t1": 7, "text": "second"}, {"t0": 1, "t1": 3, "text": "first"}]
    text, _ = build_ass(cues, PACK, CORE, 1080, 1920)
    lines = _dialogues(text)
    assert lines[0].endswith("first") and lines[1].endswith("second")


# ---- fonts ----
def test_devanagari_text_uses_devanagari_lead_font():
    text, _ = build_ass([{"t0": 0, "t1": 2, "text": DEVA}], PACK, CORE, 1080, 1920,
                        language="en")
    styles = _style_fields(text)
    assert styles["Lead"][1] == "DevaTest"
    assert styles["Sub"][1] == "LatinTest"


def test_latin_text_with_language_en_uses_latin_family():
    text, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hello"}], PACK, CORE, 1080, 1920,
                              language="en")
    assert _style_fields(text)["Lead"][1] == "LatinTest"
    assert not _warns(entries)


def test_empty_devanagari_family_falls_back_with_warn():
    pack = copy.deepcopy(PACK)
    pack["typography"]["subtitle_devanagari"] = ""
    text, entries = build_ass([{"t0": 0, "t1": 2, "text": DEVA}], pack, CORE, 1080, 1920)
    assert _style_fields(text)["Lead"][1] == "LatinTest"
    assert "font" in _messages(_warns(entries)).lower()


def test_empty_latin_family_falls_back_with_warn():
    pack = copy.deepcopy(PACK)
    pack["typography"]["subtitle_latin"] = None
    text, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hello"}], pack, CORE, 1080, 1920,
                              language="en")
    assert _style_fields(text)["Lead"][1] == "DevaTest"
    assert "font" in _messages(_warns(entries)).lower()


# ---- contrast ----
def test_white_on_black_contrast_is_21():
    assert contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.01)


def test_default_build_has_no_contrast_warn():
    _, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hi"}], PACK, CORE, 1080, 1920)
    assert not _warns(entries)


def test_contrast_below_core_minimum_warns():
    core = _core_with(caption_min_contrast=30)
    _, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hi"}], PACK, core, 1080, 1920)
    msg = _messages(_warns(entries))
    assert "contrast" in msg and "21.00" in msg and "30" in msg


def test_fill_close_to_outline_gives_delta_l_warn(monkeypatch):
    monkeypatch.setattr(captions, "FILL_HEX", "#202020")
    _, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hi"}], PACK, CORE, 1080, 1920)
    assert "L*" in _messages(_warns(entries))


# ---- text escapes ----
def test_ass_specials_escaped():
    text, _ = build_ass([{"t0": 0, "t1": 2, "text": "a{b}c\\d" + "\n" + "e"}],
                        PACK, CORE, 1080, 1920)
    line = _dialogues(text)[0]
    body = line.split(",", 9)[9]
    assert body.endswith("a(b)cd\\Ne")
    assert "{b}" not in body


# ---- invalid input ----
def test_invalid_cues_skipped_with_warn():
    cues = ["x",
            {"t0": 1, "t1": 1, "text": "equal"},
            {"t0": "a", "t1": 2, "text": "str time"},
            {"t0": 0, "t1": 2, "text": "   "},
            {"t0": 0, "t1": 2, "text": "ok"}]
    text, entries = build_ass(cues, PACK, CORE, 1080, 1920)
    assert len(_dialogues(text)) == 1
    assert len(_warns(entries)) >= 4
    assert all(e["rule"] == "CAP" for e in entries)


@pytest.mark.parametrize("bad_pack", [None, "garbage", {}])
def test_junk_pack_gives_fail_and_minimal_ass(bad_pack):
    text, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hi"}], bad_pack, CORE, 1080, 1920)
    fails = [e for e in entries if e["level"] == "FAIL"]
    assert fails and fails[0]["rule"] == "CAP"
    assert text.startswith("[Script Info]")
    assert "[Events]" in text
    assert _dialogues(text) == []
    assert "PlayResX: 1080" in text


def test_junk_core_gives_fail():
    _, entries = build_ass([{"t0": 0, "t1": 2, "text": "Hi"}], PACK, None, 1080, 1920)
    assert any(e["level"] == "FAIL" and e["rule"] == "CAP" for e in entries)


# ---- helpers and determinism ----
def test_ass_time_format():
    assert ass_time(3661.239) == "1:01:01.24"
    assert ass_time(0) == "0:00:00.00"


def test_wrap_estimate_is_width_of_longest_line():
    assert wrap_estimate("abcd", 10) == 24
    assert wrap_estimate("ab\nabcd", 10) == 24


def test_output_deterministic():
    cues = [{"t0": 1, "t1": 2, "text": DEVA, "latin": "Namaste"},
            {"t0": 0, "t1": 0.4, "text": "Hi"}]
    a = build_ass(cues, PACK, CORE, 768, 1344, language="hi")
    b = build_ass(cues, PACK, CORE, 768, 1344, language="hi")
    assert a == b
    assert "\r" not in a[0]
