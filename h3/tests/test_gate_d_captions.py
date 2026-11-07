"""Gate D captions run on the one shared caption engine (core/captions.py): this file re-points the old private-builder
tests (geometry, cards, karaoke, escaping, face avoidance, fonts, per-language family) at gd.build_captions."""
import re
import shutil
from pathlib import Path

import pytest

from h3 import gate_d_audio as gd
from h3.shot_table_spec import CAPTION

REPO_FONTS = Path(__file__).resolve().parents[2] / "styles" / "fonts"
needs_fonts = pytest.mark.skipif(not (REPO_FONTS / "NotoSansDevanagari-Variable.ttf").is_file(), reason="repo fonts missing")


def lead_rows(ass):
    return [ln for ln in ass.splitlines() if ln.startswith("Dialogue:") and ",Lead," in ln]


def words_in(row):
    return len(re.sub(r"\{[^}]*\}", "", row.split("}", 1)[1]).replace("\\N", " ").split())


def pos(row):
    x, y = re.search(r"\\pos\((\d+),(\d+)\)", row).groups()
    return int(x), int(y)


def fails(entries):
    return [e for e in entries if e["level"] == "FAIL"]


@needs_fonts
def test_header_geometry_uses_the_play_res_and_the_style_pack_fonts():
    ass, entries = gd.build_captions([{"t0": 0.0, "t1": 2.0, "text": "one two three"}], lang="en", fonts_dir=REPO_FONTS)
    assert not fails(entries)
    assert f"PlayResX: {CAPTION['play_res'][0]}" in ass and f"PlayResY: {CAPTION['play_res'][1]}" in ass
    assert "Style: Lead,Inter," in ass and "{\\k" in lead_rows(ass)[0]            # karaoke highlight tags


@needs_fonts
def test_cards_have_at_most_six_words_and_cover_the_cue():
    text = "one two three four five six seven eight nine ten eleven twelve thirteen"
    ass, _ = gd.build_captions([{"t0": 1.0, "t1": 7.0, "text": text}], lang="en", fonts_dir=REPO_FONTS)
    rows = lead_rows(ass)
    assert [words_in(r) for r in rows] == [5, 5, 3]                              # 13 words -> 5, 5, 3
    assert all(words_in(r) <= CAPTION["max_words"] for r in rows)
    assert rows[0].split(",")[1] == "0:00:01.00" and rows[-1].split(",")[2] == "0:00:07.00"


@needs_fonts
def test_words_are_escaped_so_override_blocks_cannot_leak():
    ass, _ = gd.build_captions([{"t0": 0.0, "t1": 1.0, "text": "{bad} word"}], lang="en", fonts_dir=REPO_FONTS)
    body = lead_rows(ass)[0].split("}", 1)[1]
    assert "{bad}" not in body and "bad" in body and "word" in body


@needs_fonts
def test_caption_stays_inside_the_band_and_a_forbidden_top_zone_is_a_fail(monkeypatch):
    ass, entries = gd.build_captions([{"t0": 0.0, "t1": 1.0, "text": "one two"}], lang="en", fonts_dir=REPO_FONTS)
    h = CAPTION["play_res"][1]
    assert 0.50 * h <= pos(lead_rows(ass)[0])[1] <= 0.65 * h and not fails(entries)   # the Reels band, bottom 35% kept clear
    from core.style_pack import load_core
    core = load_core()
    monkeypatch.setattr(gd, "load_core", lambda: dict(core, safe_zone_frac=dict(core["safe_zone_frac"], top=0.95)))
    _, entries = gd.build_captions([{"t0": 0.0, "t1": 1.0, "text": "one two"}], lang="en", fonts_dir=REPO_FONTS)
    assert any(e["rule"] == "CAP-GEOMETRY" for e in fails(entries))


@needs_fonts
def test_caption_over_a_face_is_raised_or_flagged():
    cue = [{"t0": 0.0, "t1": 1.0, "text": "one two"}]
    w, h = CAPTION["play_res"]
    y0 = pos(lead_rows(gd.build_captions(cue, lang="en", fonts_dir=REPO_FONTS)[0])[0])[1]
    face = (0, y0 - 80, w, y0 + 80)                                              # covers the default caption position
    ass, entries = gd.build_captions(cue, lang="en", fonts_dir=REPO_FONTS, face_boxes=[face])
    assert pos(lead_rows(ass)[0])[1] < y0 and not [e for e in entries if "face" in e["message"]]
    ass2, entries2 = gd.build_captions(cue, lang="en", fonts_dir=REPO_FONTS, face_boxes=[(0, 0, w, h)])
    assert pos(lead_rows(ass2)[0])[1] == y0 and any("covers a face" in e["message"] for e in entries2)


def test_a_missing_font_is_a_fail_and_writes_nothing(tmp_path):
    out = tmp_path / "cap.ass"
    _, entries = gd.build_captions([{"t0": 0.0, "t1": 1.0, "text": "one"}], lang="en", fonts_dir=tmp_path)
    assert any(e["rule"] == "CAP-FONT" for e in fails(entries))
    with pytest.raises(ValueError, match="font file"):
        gd.write_captions(out, [{"t0": 0.0, "t1": 1.0, "text": "one"}], fonts_dir=tmp_path, lang="en")
    assert not out.exists()


@needs_fonts
def test_font_present_is_written_and_the_burn_filter_names_the_fonts_dir(tmp_path):
    out = tmp_path / "cap.ass"
    assert gd.write_captions(out, [{"t0": 0.0, "t1": 1.0, "text": "one two"}], fonts_dir=REPO_FONTS, lang="en") == []
    assert out.read_text(encoding="utf-8").startswith("[Script Info]")
    assert "fontsdir=" in gd.build_subtitles_filter(out, tmp_path)


@needs_fonts
@pytest.mark.parametrize("lang,family,text", [("hi", "Noto Sans Devanagari", "कृष्ण यमुना में कूद पड़ा"),
                                              ("mr", "Noto Sans Devanagari", "कृष्ण यमुनेत उडी मारतो"),
                                              ("en", "Inter", "Krishna jumps into the river")])
def test_each_language_uses_its_family_with_shared_layout(lang, family, text):
    ass, entries = gd.build_captions([{"t0": 0.0, "t1": 4.0, "text": text}], lang=lang, fonts_dir=REPO_FONTS)
    assert not fails(entries)
    row = lead_rows(ass)[0]
    assert (f"Style: Lead,{family}," in ass) and pos(row)[1] == round(0.575 * CAPTION["play_res"][1])


@needs_fonts
def test_default_language_is_hindi_devanagari():
    ass, _ = gd.build_captions([{"t0": 0.0, "t1": 1.0, "text": "कृष्ण"}], fonts_dir=REPO_FONTS)
    assert "Style: Lead,Noto Sans Devanagari," in ass


def test_unknown_language_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        gd.build_captions([{"t0": 0.0, "t1": 1.0, "text": "a"}], lang="fr", fonts_dir=tmp_path)


@needs_fonts
def test_font_check_is_per_language(tmp_path):
    shutil.copy(REPO_FONTS / "NotoSansDevanagari-Variable.ttf", tmp_path)            # only the Devanagari file present
    cue = [{"t0": 0.0, "t1": 1.0, "text": "कृष्ण"}]
    assert not fails(gd.build_captions(cue, lang="hi", fonts_dir=tmp_path)[1])
    assert not fails(gd.build_captions(cue, lang="mr", fonts_dir=tmp_path)[1])
    assert any(e["rule"] == "CAP-FONT" for e in fails(gd.build_captions([{"t0": 0.0, "t1": 1.0, "text": "one"}],
                                                                         lang="en", fonts_dir=tmp_path)[1]))
    shutil.copy(REPO_FONTS / "Inter-Variable.ttf", tmp_path)
    assert not fails(gd.build_captions([{"t0": 0.0, "t1": 1.0, "text": "one"}], lang="en", fonts_dir=tmp_path)[1])


@needs_fonts
def test_gate_d_refuses_a_wrong_script_and_adds_the_hook_through_the_engine(tmp_path):
    from h3.tests.test_gate_d_audio import _run, _story
    shots = _story()
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"]["hi"]["text"] = " ".join(f"hi{i}" for i in range(19))
    out = _run(tmp_path, ["hi"], shots=shots)
    assert "CAPTION_SCRIPT" in {e["code"] for e in out["reports"]["hi"]["errors"]} and not out["ok"]
    shots = _story()
    shots[0]["metadata"] = {"look": {"hook": {"caption": "Why is he blue?"}}}      # English hook in an English reel
    out = _run(tmp_path, ["en"], shots=shots)
    assert out["ok"], out["reports"]["en"]["errors"]
