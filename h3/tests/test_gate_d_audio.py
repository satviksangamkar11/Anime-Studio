"""Offline tests for h3/gate_d_audio.py. Tiny synthetic wavs, text assertions on the filtergraph and .ass.
No ffmpeg, no network, no model call."""
import math
import wave
from pathlib import Path

import pytest

from h3 import gate_d_audio as gd
from h3.shot_table_spec import CAPTION, LOUDNESS

FMT = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"


def _wav(path, seconds, rate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(round(seconds * rate)))
    return str(path)


def _codes(report):
    return sorted(e["code"] for e in report["errors"])


def _shot(sid, editorial, trk=None, hook="reveal", **extra):
    base = {"id": sid, "editorial_duration_sec": editorial, "hook_type": hook, "is_closing_hook": False,
            "audio_and_dialogue_track": trk or {}}
    base.update(extra)
    return base


# ---------------------------------------------------------------- VO fit

def test_vo_fit_pass_boundary_and_overflow(tmp_path):
    ok = _wav(tmp_path / "ok.wav", 2.90)           # exactly editorial - 0.10 is allowed
    bad = _wav(tmp_path / "bad.wav", 2.95)
    rep = gd.vo_fit_check([{"shot_id": "s1", "wav_path": ok, "editorial_duration_sec": 3.0},
                           {"shot_id": "s2", "wav_path": bad, "editorial_duration_sec": 3.0}])
    assert _codes(rep) == ["VO_OVERFLOW_ERROR"] and rep["errors"][0]["where"] == "s2"
    assert rep["stats"]["s1"]["vo_sec"] == 2.9


def test_vo_unreadable_is_its_own_error(tmp_path):
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not a wav")
    rep = gd.vo_fit_check([{"shot_id": "s1", "wav_path": str(junk), "editorial_duration_sec": 3.0}])
    assert _codes(rep) == ["VO_UNREADABLE"]


def test_closing_vo_tail_silence_and_fit(tmp_path):
    shot = _shot("c", 5.0, {"narration": {"text": "Will you keep the lamp lit?", "language": "en",
                                          "time_range": [3.0, 4.6]},
                            "performance_notes": {"narrator_mouth_closed": True,
                                                  "mouth_state": {"3": "closed", "4": "closed"}}},
                 hook="tender", is_closing_hook=True)
    gate = {"ending_reuses_emotional_anchor": {"pass": True, "evidence": "lamp"}}
    good = gd.check_closing_shot(shot, story_gate_checks=gate, vo_wav_path=_wav(tmp_path / "a.wav", 4.6),
                                 payoff_end_sec=2.5)
    assert good["ok"], good["errors"]
    assert good["stats"]["vo"]["residual_sec"] == 0.4
    tail = gd.check_closing_shot(shot, story_gate_checks=gate, vo_wav_path=_wav(tmp_path / "b.wav", 4.3),
                                 payoff_end_sec=2.5)
    assert _codes(tail) == ["CLOSING_TAIL_SILENCE"]
    over = gd.check_closing_shot(shot, story_gate_checks=gate, vo_wav_path=_wav(tmp_path / "c.wav", 4.95),
                                 payoff_end_sec=2.5)
    assert _codes(over) == ["VO_OVERFLOW_ERROR"]


# ---------------------------------------------------------------- closing contract without VO

def test_closing_requires_strong_hook_flag_and_payoff():
    gate_ok = {"ending_reuses_emotional_anchor": {"pass": True, "evidence": "x"}}
    assert gd.check_closing_shot(_shot("c", 4.0, hook="reveal", is_closing_hook=True),
                                 story_gate_checks=gate_ok)["ok"]
    assert _codes(gd.check_closing_shot(_shot("c", 4.0, hook="chase", is_closing_hook=True),
                                        story_gate_checks=gate_ok)) == ["CLOSING_WEAK_HOOK"]
    assert _codes(gd.check_closing_shot(_shot("c", 4.0, hook="reveal", is_closing_hook=True),
                                        story_gate_checks={})) == ["CLOSING_NO_ANCHOR_PAYOFF"]
    assert _codes(gd.check_closing_shot(_shot("c", 4.0, hook="reveal", is_closing_hook=False),
                                        story_gate_checks=gate_ok)) == ["CLOSING_NOT_FLAGGED"]


def test_closing_vo_must_follow_payoff_and_mouth_must_be_closed(tmp_path):
    trk = {"narration": {"text": "Will you come back?", "language": "en", "time_range": [3.0, 4.6]},
           "performance_notes": {"narrator_mouth_closed": True,
                                 "mouth_state": {"3": "open_non_verbal_breath", "4": "closed"}}}
    shot = _shot("c", 5.0, trk, hook="reveal", is_closing_hook=True)
    gate = {"ending_reuses_emotional_anchor": {"pass": True, "evidence": "x"}}
    wav = _wav(tmp_path / "v.wav", 4.6)                                     # residual 0.4 s: tail is fine
    assert _codes(gd.check_closing_shot(shot, story_gate_checks=gate, vo_wav_path=wav,
                                        payoff_end_sec=2.5)) == ["CLOSING_MOUTH_OPEN"]
    trk["performance_notes"]["mouth_state"]["3"] = "closed"
    assert gd.check_closing_shot(shot, story_gate_checks=gate, vo_wav_path=wav, payoff_end_sec=2.5)["ok"]
    assert _codes(gd.check_closing_shot(shot, story_gate_checks=gate, vo_wav_path=wav,
                                        payoff_end_sec=3.5)) == ["CLOSING_VO_BEFORE_PAYOFF"]


# ---------------------------------------------------------------- opening hook and narration density

def test_opening_hook_needs_voice_and_sfx_in_first_two_seconds():
    good = _shot("o", 4.0, {"narration": {"text": "Listen", "language": "en", "time_range": [0.3, 1.8]},
                            "sfx_cues": [{"time_range": "0.0-0.4s", "sfx_key": "bell", "description": ""}]})
    assert gd.check_opening_hook(good)["ok"]
    late_voice = _shot("o", 4.0, {"narration": {"text": "Listen", "language": "en", "time_range": [2.5, 4.0]},
                                  "sfx_cues": [{"time_range": "0.0-0.4s", "sfx_key": "bell", "description": ""}]})
    assert _codes(gd.check_opening_hook(late_voice)) == ["OPENING_HOOK_NO_VOICE"]
    late_sfx = _shot("o", 4.0, {"narration": {"text": "Listen", "language": "en", "time_range": [0.3, 1.8]},
                                "sfx_cues": [{"time_range": "3.0–3.5s", "sfx_key": "bell", "description": ""}]})
    assert _codes(gd.check_opening_hook(late_sfx)) == ["OPENING_HOOK_NO_SFX"]


def _dense_shots(second_start=0.2, second_words=19, second_end=7.0):
    first = _shot("a", 8.0, {"narration": {"text": " ".join(["w"] * 19), "language": "en", "time_range": [0.0, 7.8]}})
    second = _shot("b", 8.0, {"narration": {"text": " ".join(["w"] * second_words), "language": "en",
                                            "time_range": [second_start, second_end]}})
    return [first, second]


def test_narration_density_pass_and_threshold_edges():
    rep = gd.check_narration_density(_dense_shots())   # 7.8 s, gap 0.4 s, 2nd shot covers 8.2-15.0
    assert rep["ok"], rep["errors"]
    assert rep["stats"]["words_window"] == 38.0
    short = gd.check_narration_density(_dense_shots(second_words=18))
    assert _codes(short) == ["NARRATION_WORDS_LOW"]


def test_narration_density_flags_dead_air_and_low_coverage():
    gap = gd.check_narration_density(_dense_shots(second_start=1.0))   # 1.2 s gap at 7.8-9.0
    assert _codes(gap) == ["DEAD_AIR_PAUSE"]
    silent = gd.check_narration_density([_dense_shots()[0], _shot("b", 8.0)])   # 7.8 s of speech, 19 words
    assert _codes(silent) == ["NARRATION_COVERAGE_LOW", "NARRATION_WORDS_LOW"]
    assert gd.check_narration_density(_dense_shots(second_start=1.0), narration_driven=False)["ok"]


def test_parse_time_range_forms():
    assert gd.parse_time_range([1, 2.5]) == (1.0, 2.5)
    assert gd.parse_time_range("1.2–1.6s") == (1.2, 1.6)
    assert gd.parse_time_range("0.0-0.4s") == (0.0, 0.4)
    with pytest.raises(ValueError):
        gd.parse_time_range("2.0-1.0s")


# ---------------------------------------------------------------- BGM manifest

def test_bgm_manifest_required_fields(tmp_path):
    good = {"tracks": [{"track_id": "bgm_1", "path": "audio/bgm.wav", "license_type": "CC0", "bpm": 92,
                        "lufs": -18.5}]}
    assert gd.validate_bgm_manifest(good)["ok"]
    missing = {"tracks": [{"track_id": "bgm_1", "path": "audio/bgm.wav", "bpm": 92, "lufs": -18.5}]}
    assert _codes(gd.validate_bgm_manifest(missing)) == ["BGM_FIELD_MISSING"]
    bad_bpm = {"tracks": [{"track_id": "b", "path": "p", "license_type": "x", "bpm": "fast", "lufs": -18}]}
    assert _codes(gd.validate_bgm_manifest(bad_bpm)) == ["BGM_FIELD_INVALID"]
    empty = gd.validate_bgm_manifest({"tracks": []})   # Q-R4-13: empty = no BGM, not an error
    assert empty["ok"] and _codes(empty) == []
    path = tmp_path / "bgm_manifest.json"
    path.write_text("{not json", encoding="utf-8")
    assert _codes(gd.read_bgm_manifest(path)) == ["BGM_MANIFEST_UNREADABLE"]


# ---------------------------------------------------------------- filtergraph and mux argv

def test_mix_filter_exact_text():
    text = gd.build_mix_filter([{"input_index": 1, "trim_in_sec": 0.0, "trim_out_sec": 2.0},
                                {"input_index": 2, "trim_in_sec": 1.0, "trim_out_sec": 3.5}],
                               vo_input=3, bgm_input=4, total_reel_duration_sec=4.5)
    expected = ";".join([
        f"[1:a]atrim=start=0.000:end=2.000,asetpts=PTS-STARTPTS,{FMT},afade=t=in:st=0:d=0.005,"
        "afade=t=out:st=1.995:d=0.005[sfx0]",
        f"[2:a]atrim=start=1.000:end=3.500,asetpts=PTS-STARTPTS,{FMT},afade=t=in:st=0:d=0.005,"
        "afade=t=out:st=2.495:d=0.005[sfx1]",
        "[sfx0][sfx1]concat=n=2:v=0:a=1[h3_sfx_full]",
        f"[3:a]{FMT},apad=whole_dur=4.500[elevenlabs_vo]",
        "[elevenlabs_vo]asplit=3[vo_out][sc_sfx][sc_bgm]",
        "[h3_sfx_full][sc_sfx]sidechaincompress=threshold=0.03:ratio=4:attack=10:release=350[sfx_ducked]",
        f"[4:a]{FMT}[bgm]",
        "[bgm][sc_bgm]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=500[bgm_ducked]",
        "[sfx_ducked][vo_out][bgm_ducked]amix=inputs=3:duration=longest:normalize=0,atrim=0:4.500,"
        "loudnorm=I=-14:TP=-1.8:LRA=11[master]",
    ])
    assert text == expected


def test_mix_filter_guards():
    clip = {"input_index": 1, "trim_in_sec": 0.0, "trim_out_sec": 5.0}
    with pytest.raises(ValueError):
        gd.build_mix_filter([], 2, 3, 5.0)
    with pytest.raises(ValueError):          # SFX longer than the reel would be cut by atrim
        gd.build_mix_filter([clip], 2, 3, 4.0)
    with pytest.raises(ValueError):
        gd.build_mix_filter([{"input_index": 1, "trim_in_sec": 2.0, "trim_out_sec": 2.0}], 2, 3, 4.0)


def test_final_mux_argv_is_aac_and_never_shortest():
    mix = gd.build_mix_filter([{"input_index": 1, "trim_in_sec": 0.0, "trim_out_sec": 5.0}], 2, 3, 5.0)
    argv = gd.build_final_mux_argv("reel.mp4", ["sfx.wav", "vo.wav", "bgm.wav"], mix, "final.mp4",
                                   burn_captions=False)                    # draft copy mode
    assert argv[:3] == ["ffmpeg", "-y", "-i"] and argv[3] == "reel.mp4"
    assert argv[argv.index("-filter_complex") + 1] == mix
    assert argv[argv.index("[master]") - 1] == "-map"                      # audio map (second -map is 0:v:0)
    for flag, value in [("-c:v", "copy"), ("-c:a", "aac"), ("-b:a", "192k"), ("-ar", "48000"), ("-ac", "2")]:
        assert argv[argv.index(flag) + 1] == value
    assert "-shortest" not in argv and argv[-1] == "final.mp4"
    assert argv.count("-i") == 4
    with pytest.raises(ValueError):
        gd.build_final_mux_argv("reel.mp4", ["vo.wav"], "[1:a]anull[x]", "final.mp4")


# ---------------------------------------------------------------- BGM presence and post-AAC loudness

def test_music_presence_band_and_silent_floor():
    voice = [-20.0] * 100
    assert gd.check_music_presence(voice, [-38.0] * 100)["ok"]                   # median 18 dB under
    assert _codes(gd.check_music_presence(voice, [-30.0] * 100)) == ["BGM_MEDIAN_OUT_OF_BAND"]   # 10 dB
    silent_tail = [-38.0] * 90 + [-80.0] * 10                                    # median 18, floor -80
    assert _codes(gd.check_music_presence(voice, silent_tail)) == ["BGM_SILENT_FLOOR"]
    assert _codes(gd.check_music_presence([-60.0] * 10, [-80.0] * 10)) == ["BGM_PRESENCE_NO_SPEECH"]
    assert _codes(gd.check_music_presence([-20.0], [-38.0, -40.0])) == ["BGM_PRESENCE_BAD_INPUT"]


EBUR_TEXT = """[Parsed_ebur128_0 @ 0000]
Summary:

  Integrated loudness:
    I:         -14.2 LUFS
    Threshold: -24.4 LUFS

  Loudness range:
    LRA:        6.1 LU

  True peak:
    Peak:       -1.7 dBFS
"""
LOUDNORM_TEXT = "Input Integrated:    -14.02 LUFS\nInput True Peak:    -1.50 dBTP\n"


def test_loudness_parse_both_formats():
    assert gd.parse_loudness_text(EBUR_TEXT) == {"integrated_lufs": -14.2, "true_peak_dbtp": -1.7}
    assert gd.parse_loudness_text(LOUDNORM_TEXT) == {"integrated_lufs": -14.02, "true_peak_dbtp": -1.5}


def test_post_aac_loudness_gate():
    assert gd.check_post_aac_loudness(EBUR_TEXT)["ok"]
    assert gd.check_post_aac_loudness(LOUDNORM_TEXT)["ok"]                     # TP exactly -1.5 is allowed
    too_loud = EBUR_TEXT.replace("-14.2 LUFS", "-13.2 LUFS")
    assert _codes(gd.check_post_aac_loudness(too_loud)) == ["LOUDNESS_OUT_OF_TARGET"]
    hot_peak = EBUR_TEXT.replace("-1.7 dBFS", "-1.4 dBFS")
    assert _codes(gd.check_post_aac_loudness(hot_peak)) == ["TRUE_PEAK_OVER"]
    assert _codes(gd.check_post_aac_loudness("nothing here")) == ["LOUDNESS_UNREADABLE"]
    argv = gd.build_loudness_verify_argv("final.mp4")
    assert "ebur128=peak=true" in argv and LOUDNESS["target_lufs"] == -14.0


# ---------------------------------------------------------------- .ass captions

def _events(ass):
    return [line for line in ass.splitlines() if line.startswith("Dialogue:")]


def _card_words(event):
    import re
    return len(re.sub(r"\{\\k\d+\}", "", event.split(",", 9)[9]).split())


def test_ass_header_geometry_and_margins():
    ass, warnings = gd.build_ass([{"text": "one two three", "start": 0.0, "end": 2.0}])
    assert warnings == []
    assert "PlayResX: 1440" in ass and "PlayResY: 2560" in ass
    style = next(l for l in ass.splitlines() if l.startswith("Style: Caption,"))
    fields = style.split(",")
    assert fields[1] == "Noto Sans Devanagari" and fields[18] == "2"        # Alignment 2 (bottom centre)
    assert fields[19] == "160" and fields[20] == "160" and fields[21] == "896"  # symmetric L/R, MarginV
    ev = _events(ass)[0].split(",", 9)
    assert ev[5] == "160" and ev[6] == "160" and ev[7] == "896"
    assert "{\\k" in ev[9]                                                  # karaoke highlight tags
    assert "&H0000FFFF" in style                                           # yellow active colour


def test_ass_cards_at_most_six_words_and_timing_covers_cue():
    text = "one two three four five six seven eight nine ten eleven twelve thirteen"
    ass, _ = gd.build_ass([{"text": text, "start": 1.0, "end": 7.0}])
    events = _events(ass)
    assert len(events) == 3                                                # 13 words -> 5, 5, 3
    assert all(_card_words(e) <= CAPTION["max_words"] for e in events)
    assert sum(_card_words(e) for e in events) == 13
    assert events[0].split(",")[1] == "0:00:01.00" and events[-1].split(",")[2] == "0:00:07.00"


def test_split_cards_is_balanced():
    assert [len(c) for c in gd.split_cards("a b c d e f g")] == [4, 3]
    assert gd.split_cards("") == []


def test_ass_words_are_escaped_so_override_blocks_cannot_leak():
    ass, _ = gd.build_ass([{"text": "{bad} word", "start": 0.0, "end": 1.0}])
    text = _events(ass)[0].split(",", 9)[9]
    assert "{bad}" not in text and "bad" in text and "word" in text
    # a six-word card at the default margin sits well below the blocked top line
    assert gd._caption_top(gd._estimate_lines(["xxxxxxxxxx"] * 6), CAPTION["margin_v"]) >= CAPTION["top_blocked_y"]


def test_ass_guard_raises_when_caption_would_sit_above_line(monkeypatch):
    monkeypatch.setitem(CAPTION, "margin_v", 2300)                          # 260 px from the top: too high
    with pytest.raises(ValueError):
        gd.build_ass([{"text": "one two", "start": 0.0, "end": 1.0}])


def test_ass_raises_caption_off_a_face_or_flags_it():
    face = (0, 1400, 1440, 1700)                                           # covers the default caption band
    ass, warnings = gd.build_ass([{"text": "one two", "start": 0.0, "end": 1.0}], face_boxes=[face])
    assert warnings == []
    mv = int(_events(ass)[0].split(",", 9)[7])
    assert mv > CAPTION["margin_v"]
    whole = (0, 0, 1440, 2560)                                             # no clear spot anywhere
    ass2, warnings2 = gd.build_ass([{"text": "one two", "start": 0.0, "end": 1.0}], face_boxes=[whole])
    assert warnings2 and int(_events(ass2)[0].split(",", 9)[7]) == CAPTION["margin_v"]


def test_font_missing_fails_clearly_and_writes_nothing(tmp_path):
    with pytest.raises(FileNotFoundError, match="NotoSansDevanagari-Bold.ttf"):
        gd.ensure_font(tmp_path)
    out = tmp_path / "cap.ass"
    with pytest.raises(FileNotFoundError):
        gd.write_captions(out, [{"text": "one", "start": 0.0, "end": 1.0}], fonts_dir=tmp_path)
    assert not out.exists()


def test_font_present_is_returned_and_written(tmp_path):
    (tmp_path / CAPTION["font"]).write_bytes(b"\x00")                       # placeholder bytes, never parsed
    assert gd.ensure_font(tmp_path).name == CAPTION["font"]
    out = tmp_path / "cap.ass"
    assert gd.write_captions(out, [{"text": "one two", "start": 0.0, "end": 1.0}], fonts_dir=tmp_path) == []
    assert out.read_text(encoding="utf-8").startswith("[Script Info]")
    assert "fontsdir=" in gd.build_subtitles_filter(out, tmp_path)


def test_no_ffmpeg_or_network_imports_in_module():
    src = open(gd.__file__, encoding="utf-8").read()
    for banned in ("subprocess", "urllib", "requests", "socket", "http"):
        assert f"import {banned}" not in src


SIDS = ("s1", "s2", "s3")
ALL_LANGS = ["en", "hi", "mr"]
BGM = {"tracks": [{"track_id": "bgm_1", "path": "audio/bgm.wav", "license_type": "CC0", "bpm": 90, "lufs": -18.0}]}
GATE = {"ending_reuses_emotional_anchor": {"pass": True, "evidence": "lamp"}}


def _story(langs=ALL_LANGS):
    """Three 5 s shots. Speech 0-4.9 s in every shot (gaps 0.1 s), so coverage and words pass. s1 opens the reel,
    s3 closes it with a 4.9 s VO (residual 0.1 s) and the mouth closed on 0-4 s."""
    def trk():
        return {"narration_by_lang": {l: {"text": " ".join(f"{l}{i}" for i in range(19)), "language": l,
                                          "time_range": [0.0, 4.9]} for l in langs},
                "dialogue_by_lang": {},
                "sfx_cues": [{"time_range": "0.0-0.4s", "sfx_key": "bell", "description": "bell"}],
                "performance_notes": {"narrator_mouth_closed": True,
                                      "mouth_state": {str(i): "closed" for i in range(5)}}}
    return [{"id": sid, "editorial_duration_sec": 5.0, "hook_type": "reveal",
             "is_opening_0_2s_hook": i == 0, "is_closing_hook": i == 2, "audio_and_dialogue_track": trk()}
            for i, sid in enumerate(SIDS)]


def _vo_root(root, langs=ALL_LANGS, skip=()):
    base = root / "audio" / "vo"
    for lang in langs:
        for sid in SIDS:
            if (lang, sid) in skip:
                continue
            p = base / lang / f"{sid}.wav"
            p.parent.mkdir(parents=True, exist_ok=True)
            _wav(p, 4.9)
    return base


def _fonts(root, names=("hi", "en")):
    fonts = root / "fonts"
    fonts.mkdir(exist_ok=True)
    if "hi" in names:
        (fonts / CAPTION["font"]).write_bytes(b"\x00")
    if "en" in names:
        (fonts / "NotoSans-Bold.ttf").write_bytes(b"\x00")
    return fonts


def _run(root, langs, vo_dir=None, fonts=("hi", "en"), shots=None, **kw):
    kw.setdefault("video_has_audio", True)
    return gd.plan_language_outputs("reel", langs, vo_dir or _vo_root(root), BGM, shots=shots or _story(),
                                    video_path="reel.mp4", fonts_dir=_fonts(root, fonts),
                                    story_gate_checks=GATE, payoff_end_sec=0.0, **kw)


@pytest.mark.parametrize("langs", [["hi"], ["en", "mr"], ["en", "hi", "mr"]])
def test_one_two_or_three_languages_each_get_a_final_reel(tmp_path, langs):
    out = _run(tmp_path, langs)
    assert out["ok"], {l: r["errors"] for l, r in out["reports"].items()}
    assert list(out["reports"]) == langs and list(out["languages"]) == langs
    exports = set()
    for lang in langs:
        plan = out["languages"][lang]
        assert plan["export_path"] == f"export/reel_{lang}.mp4"
        assert plan["caption_path"] == f"captions/reel_{lang}.ass"
        assert plan["mux_argv"][-1] == f"export/reel_{lang}.mp4"
        assert plan["mix_filter"].endswith("[master]") and "[vo_full]" in plan["mix_filter"]
        assert plan["mux_argv"].count("-i") == 1 + len(SIDS) + 1       # video + 3 VO files + BGM
        assert [Path(p).parts[-3:] for p in plan["vo_files"].values()] == \
            [("vo", lang, f"{sid}.wav") for sid in SIDS]
        assert all(Path(p).is_file() for p in plan["vo_files"].values())
        assert plan["loudness_argv"][-1] == "-"
        exports.add(plan["export_path"])
    assert len(exports) == len(langs)


def test_missing_vo_fails_only_that_language_and_the_aggregate(tmp_path):
    vo_dir = _vo_root(tmp_path, skip={("hi", "s2")})
    out = _run(tmp_path, ["en", "hi", "mr"], vo_dir=vo_dir)
    assert not out["ok"]
    assert _codes(out["reports"]["hi"]) == ["VO_MISSING"]
    assert out["reports"]["hi"]["errors"][0]["where"] == "s2"
    assert out["reports"]["en"]["ok"] and out["reports"]["mr"]["ok"]
    assert out["languages"]["hi"]["mux_argv"] is None and out["languages"]["hi"]["mix_filter"] is None
    assert out["languages"]["en"]["mux_argv"] is not None and out["languages"]["mr"]["mux_argv"] is not None


def test_language_with_no_vo_files_at_all_fails_only_itself(tmp_path):
    vo_dir = _vo_root(tmp_path, langs=("en", "mr"))                 # no hi folder at all
    out = _run(tmp_path, ["en", "hi", "mr"], vo_dir=vo_dir)
    assert set(_codes(out["reports"]["hi"])) == {"NO_VO_FILES", "VO_MISSING"}
    assert out["reports"]["en"]["ok"] and out["reports"]["mr"]["ok"]
    assert out["languages"]["hi"]["mux_argv"] is None


def test_language_with_no_vo_and_no_captions_fails_only_itself(tmp_path):
    shots = _story(langs=("en", "hi"))                              # mr has no text in any shot
    out = _run(tmp_path, ["en", "hi", "mr"], vo_dir=_vo_root(tmp_path, langs=("en", "hi")), shots=shots)
    assert "NO_CAPTIONS" in set(_codes(out["reports"]["mr"]))
    assert "NO_VO_FILES" not in set(_codes(out["reports"]["mr"]))   # mr has no speech, so no VO is expected
    assert out["reports"]["en"]["ok"] and out["reports"]["hi"]["ok"]
    assert out["languages"]["mr"]["mux_argv"] is None and out["languages"]["mr"]["captions"] == []


def test_missing_font_fails_only_that_language(tmp_path):
    out = _run(tmp_path, ["en", "hi"], fonts=("hi",))               # Latin font not bundled
    assert _codes(out["reports"]["en"]) == ["FONT_MISSING"]
    assert out["reports"]["hi"]["ok"]


def test_loudness_is_checked_per_language_and_does_not_block_the_mux(tmp_path):
    hot = EBUR_TEXT.replace("-14.2 LUFS", "-12.0 LUFS")
    out = _run(tmp_path, ["en", "hi"], measured_text={"en": EBUR_TEXT, "hi": hot})
    assert _codes(out["reports"]["hi"]) == ["LOUDNESS_OUT_OF_TARGET"]
    assert out["reports"]["en"]["ok"] and not out["ok"]
    assert out["languages"]["hi"]["mux_argv"] is not None              # loudness is measured after render


def test_unmeasured_loudness_is_a_warning_not_an_error(tmp_path):
    out = _run(tmp_path, ["mr"])
    assert out["ok"]
    assert any("loudness for mr not measured" in w for w in out["reports"]["mr"]["warnings"])


@pytest.mark.parametrize("bad", [[], ["fr"], ["hi", "hi"], "hi"])
def test_invalid_language_selection_is_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        _run(tmp_path, bad)


def test_bgm_manifest_with_two_tracks_fails_every_language(tmp_path):
    two = {"tracks": BGM["tracks"] + [dict(BGM["tracks"][0], track_id="bgm_2", path="audio/b2.wav")]}
    out = gd.plan_language_outputs("reel", ["en", "hi"], _vo_root(tmp_path), two, shots=_story(),
                                   video_path="reel.mp4", video_has_audio=True, fonts_dir=_fonts(tmp_path),
                                   story_gate_checks=GATE, payoff_end_sec=0.0)
    assert all(_codes(out["reports"][l]) == ["BGM_TRACK_COUNT"] for l in ("en", "hi"))


def _pair(argv, flag):
    return argv[argv.index(flag) + 1]


def test_burn_mux_argv_applies_subtitles_and_reencodes_video():
    mix = gd.build_mix_filter([{"input_index": 1, "trim_in_sec": 0.0, "trim_out_sec": 5.0}], 2, 3, 5.0)
    argv = gd.build_final_mux_argv("reel.mp4", ["vo.wav", "bgm.wav"], mix, "export/reel_en.mp4",
                                   ass_path="captions/reel_en.ass", fonts_dir="assets/fonts")
    graph = _pair(argv, "-filter_complex")
    assert graph.startswith(mix + ";")
    assert "[0:v]subtitles=filename=captions/reel_en.ass:fontsdir=assets/fonts[vsub]" in graph
    assert _pair(argv, "-map") == "[vsub]" and "[master]" in argv
    assert _pair(argv, "-c:v") == "libx264" and "copy" not in argv
    assert _pair(argv, "-crf") == "14" and _pair(argv, "-preset") == "slow"
    assert _pair(argv, "-pix_fmt") == "yuv420p" and _pair(argv, "-r") == "24"
    assert _pair(argv, "-c:a") == "aac" and _pair(argv, "-b:a") == "192k"
    assert "-shortest" not in argv and argv[-1] == "export/reel_en.mp4"


def test_burn_needs_an_ass_file():
    mix = gd.build_mix_filter([{"input_index": 1, "trim_in_sec": 0.0, "trim_out_sec": 5.0}], 2, 3, 5.0)
    with pytest.raises(ValueError, match="ass_path"):
        gd.build_final_mux_argv("reel.mp4", ["vo.wav", "bgm.wav"], mix, "final.mp4")


def test_subtitle_paths_are_windows_safe():
    assert gd.build_subtitles_filter("captions/reel_en.ass") == \
        "subtitles=filename=captions/reel_en.ass:fontsdir=assets/fonts"
    assert gd.build_subtitles_filter("D:/aai work/captions/x.ass", "D:/aai work/assets/fonts") == \
        "subtitles=filename='D\\:/aai work/captions/x.ass':fontsdir='D\\:/aai work/assets/fonts'"
    assert gd.build_subtitles_filter("D:\\aai work\\captions\\x.ass", "assets/fonts").startswith(
        "subtitles=filename='D\\:/aai work/captions/x.ass'")
    with pytest.raises(ValueError):
        gd.build_subtitles_filter("captions/a,b.ass")
    with pytest.raises(ValueError):
        gd.build_subtitles_filter("cap:tions/x.ass")


def test_copy_mode_when_captions_are_not_burned():
    mix = gd.build_mix_filter([{"input_index": 1, "trim_in_sec": 0.0, "trim_out_sec": 5.0}], 2, 3, 5.0)
    argv = gd.build_final_mux_argv("reel.mp4", ["vo.wav", "bgm.wav"], mix, "final.mp4", burn_captions=False)
    assert _pair(argv, "-c:v") == "copy" and "libx264" not in argv and "[vsub]" not in argv
    assert _pair(argv, "-map") == "0:v:0" and _pair(argv, "-filter_complex") == mix


def test_plan_burns_each_language_caption_into_its_reel(tmp_path):
    out = _run(tmp_path, ["en", "hi"])
    for lang in ("en", "hi"):
        argv = out["languages"][lang]["mux_argv"]
        assert _pair(argv, "-c:v") == "libx264" and "copy" not in argv
        assert f"subtitles=filename=captions/reel_{lang}.ass:fontsdir='" in _pair(argv, "-filter_complex")
    off = _run(tmp_path, ["en"], burn_captions=False)
    assert _pair(off["languages"]["en"]["mux_argv"], "-c:v") == "copy"


@pytest.mark.parametrize("video_has_audio", [None, False])
def test_no_sfx_source_fails_clearly(tmp_path, video_has_audio):
    with pytest.raises(ValueError, match="no H3 SFX source"):
        gd.plan_language_outputs("reel", ["en"], _vo_root(tmp_path), BGM, shots=_story(), video_path="reel.mp4",
                                 video_has_audio=video_has_audio, fonts_dir=_fonts(tmp_path),
                                 story_gate_checks=GATE, payoff_end_sec=0.0)


def test_separate_sfx_stem_file_becomes_its_own_input(tmp_path):
    out = _run(tmp_path, ["en"], video_has_audio=False, sfx_stem_path="audio/h3_sfx_stem.wav")
    plan = out["languages"]["en"]
    assert out["ok"], out["reports"]["en"]["errors"]
    assert plan["mux_argv"][plan["mux_argv"].index("-i") + 1] == "reel.mp4"
    assert "audio/h3_sfx_stem.wav" in plan["mux_argv"]
    assert plan["mix_filter"].startswith("[1:a]asplit=3[h3s0]")       # stem is input 1, before the VO files
    assert plan["mux_argv"].count("-i") == 1 + 1 + len(SIDS) + 1


def _style_fields(ass):
    return next(l for l in ass.splitlines() if l.startswith("Style: Caption,")).split(",")


@pytest.mark.parametrize("lang,family", [("hi", "Noto Sans Devanagari"), ("mr", "Noto Sans Devanagari"),
                                         ("en", "Noto Sans")])
def test_each_language_uses_its_font_family_with_shared_layout(lang, family):
    text = "one two three four five six seven eight nine ten"
    ass, warnings = gd.build_ass([{"text": text, "start": 0.0, "end": 4.0}], lang=lang)
    assert warnings == []
    fields = _style_fields(ass)
    assert fields[1] == family
    assert fields[18] == "2" and fields[19] == "160" and fields[20] == "160" and fields[21] == "896"
    events = _events(ass)
    assert len(events) == 2 and all(_card_words(e) <= CAPTION["max_words"] for e in events)
    for e in events:
        f = e.split(",", 9)
        assert f[5] == "160" and f[6] == "160" and f[7] == "896"


def test_en_guard_above_top_line_is_shared(monkeypatch):
    monkeypatch.setitem(CAPTION, "margin_v", 2300)
    with pytest.raises(ValueError):
        gd.build_ass([{"text": "one two", "start": 0.0, "end": 1.0}], lang="en")


def test_default_language_is_hindi_devanagari():
    assert _style_fields(gd.build_ass([{"text": "a b", "start": 0.0, "end": 1.0}])[0])[1] == "Noto Sans Devanagari"


def test_unknown_language_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        gd.build_ass([{"text": "a", "start": 0.0, "end": 1.0}], lang="fr")
    with pytest.raises(ValueError):
        gd.ensure_font(tmp_path, "fr")


def test_font_check_is_per_language(tmp_path):
    (tmp_path / CAPTION["font"]).write_bytes(b"\x00")                       # only the Devanagari file present
    assert gd.ensure_font(tmp_path, "hi").name == CAPTION["font"]
    assert gd.ensure_font(tmp_path, "mr").name == CAPTION["font"]
    with pytest.raises(FileNotFoundError, match="NotoSans-Bold.ttf"):
        gd.ensure_font(tmp_path, "en")
    out = tmp_path / "en.ass"
    with pytest.raises(FileNotFoundError):
        gd.write_captions(out, [{"text": "one", "start": 0.0, "end": 1.0}], fonts_dir=tmp_path, lang="en")
    assert not out.exists()
    (tmp_path / "NotoSans-Bold.ttf").write_bytes(b"\x00")
    assert gd.ensure_font(tmp_path, "en").name == "NotoSans-Bold.ttf"
    assert gd.write_captions(out, [{"text": "one two", "start": 0.0, "end": 1.0}], fonts_dir=tmp_path,
                             lang="en") == []
    assert "Style: Caption,Noto Sans," in out.read_text(encoding="utf-8")


def test_mix_without_bgm_is_a_two_stem_graph():
    g = gd.build_mix_filter([{"input_index": 0, "trim_in_sec": 0.0, "trim_out_sec": 5.0}], 1, None, 5.0)
    assert "asplit=2[vo_out][sc_sfx]" in g and "sc_bgm" not in g and "amix=inputs=2" in g
    assert "amix=inputs=3" in gd.build_mix_filter([{"input_index": 0, "trim_in_sec": 0.0, "trim_out_sec": 5.0}], 1, 2, 5.0)


def test_review_fixes_bad_reel_id_empty_bgm_and_bad_time_range(tmp_path):
    with pytest.raises(ValueError):                               # the reel id becomes part of file paths
        gd.plan_language_outputs("../evil", ["hi"], _vo_root(tmp_path), None, shots=_story(), video_path="r.mp4",
                                 video_has_audio=True)
    assert gd._bgm_track({"tracks": []}) == ([], None)            # explicit "no BGM" is allowed
    shots = _story()
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"] = {"en": {"text": "x", "time_range": "bad"}}
    out = _run(tmp_path, ["hi", "en"], shots=shots)               # a malformed range is a report, never a crash
    assert out["ok"] is False
