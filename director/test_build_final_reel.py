"""Offline tests for build_final_reel: the mux argv (inputs, voice references, master label) and the waived-finding list. No ffmpeg."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_final_reel as b  # noqa: E402


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
    assert "[master]" in graph and "anullsrc" in graph and "subtitles=" in graph and "concat=n=3:v=0:a=1[vo_full]" in graph
    assert argv[-1] == str(tmp_path / "out.mp4") and "-ac" in argv


def test_only_script_level_findings_are_waived():
    assert b.WAIVED == {"NARRATION_COVERAGE_LOW", "NARRATION_WORDS_LOW", "DEAD_AIR_PAUSE", "CLOSING_NO_ANCHOR_PAYOFF", "CLOSING_MOUTH_OPEN"}
    for must_block in ("VO_OVERFLOW_ERROR", "VO_MISSING", "FONT_MISSING", "GLYPH_MISSING", "TIME-01", "NO_CAPTIONS"):
        assert must_block not in b.WAIVED


def test_cards_are_at_most_six_words_and_cut_at_sentence_ends():
    cards = b.split_cards("Brahma made the gods, the sages and Daksha. Then, from his deep thought, a daughter was born.")
    assert all(len(c) <= 6 for c in cards) and all(not w.endswith(".") for c in cards for w in c[:-1])
    assert [w for c in cards for w in c] == "Brahma made the gods, the sages and Daksha. Then, from his deep thought, a daughter was born.".split()
    assert b.split_cards("At dawn, sages came.") == [["At", "dawn,", "sages", "came."]]


def test_word_cues_cover_the_line_time_without_gaps_or_overlap():
    cues = b.word_cues("Brahma made the gods, the sages and Daksha. Then, from his deep thought, a daughter was born.", 18.0, 25.0)
    assert cues[0]["t0"] == 18.0 and abs(cues[-1]["t1"] - 25.0) < 0.01
    for a, c in zip(cues, cues[1:]):
        assert abs(a["t1"] - c["t0"]) < 0.01
    for c in cues:
        ws = c["words"]
        assert ws[0]["t0"] == c["t0"] and all(x["t1"] > x["t0"] for x in ws) and all(x["t1"] <= y["t0"] + 1e-6 for x, y in zip(ws, ws[1:]))


def test_style_colours_make_the_spoken_word_yellow_and_the_rest_white():
    ass = "[V4+ Styles]\nStyle: Lead,Mukta,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,6,0,5,160,160,0,1\n"
    ass += "Dialogue: 0,0:00:01.00,0:00:03.00,Lead,,0,0,0,,{\\an5\\pos(640,1472)\\1c&H004DD8FF&\\2c&H00FFFFFF&}{\\k50}At {\\k60}dawn,\\N{\\k40}sages\n"
    out = b.style_colours(ass)
    assert ",&H00FFFFFF,&H00FFFFFF," in out and "\\k" not in out and "4DD8FF" not in out
    ev = [ln for ln in out.splitlines() if ln.startswith("Dialogue")]
    assert [ln.split(",")[1:3] for ln in ev] == [["0:00:01.00", "0:00:01.50"], ["0:00:01.50", "0:00:02.10"], ["0:00:02.10", "0:00:03.00"]]
    for i, ln in enumerate(ev):      # exactly one yellow word per event, and it is word i
        assert ln.count(b.YELLOW_BGR + "&}") == 1 and ln.split("{\\1c")[i + 1].startswith(b.YELLOW_BGR + "&}")
        assert "{\\an5\\pos(640,1472)}" in ln and "dawn,\\N" in ln
