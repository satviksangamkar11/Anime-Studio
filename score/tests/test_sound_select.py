"""Tests for score/sound_select.py: pure filter rules and measured scoring on synthetic signals."""
import math

import numpy as np
import soundfile as sf

from score import sound_select as ss


def _entry(**kw):
    base = {"path": "D:/lib/x.wav", "pack": "Sounds of KSHMR Vol 4 Complete Edition", "name": "x.wav",
            "bpm": 128.0, "key": None, "categories": ["drum_loop"], "seconds": 4.0, "sr": 44100,
            "detected_key": None, "detected_confidence": 0.1}
    base.update(kw)
    return base


def test_tonal_fit_accepts_d_minor_and_f_major_targets_within_three_semitones():
    assert ss.tonal_fit("D min") == ("D min", 0)
    assert ss.tonal_fit("E min") == ("D min", -2)
    assert ss.tonal_fit("B min") == ("D min", 3)
    assert ss.tonal_fit("D maj") == ("F maj", 3)


def test_tonal_fit_rejects_keys_more_than_three_semitones_away():
    assert ss.tonal_fit("G# min") is None  # +6 or -6
    assert ss.tonal_fit("A min") is None   # +5 needed
    assert ss.tonal_fit(None) is None
    assert ss.tonal_fit("root") is None


def test_lyric_and_word_names_are_rejected():
    assert ss.is_lyric(_entry(name="Vocal lyric phrase.wav"))
    assert ss.is_lyric(_entry(name="vox phrase 01.wav"))
    assert ss.is_lyric(_entry(name="words in it.wav"))
    assert not ss.is_lyric(_entry(name="KSHMR Dance 01.wav"))


def test_loop_needs_bpm_within_stretch_limit_or_half_double_feel():
    e = _entry(bpm=128.0, seconds=4 * 240 / 128.0 * 2)  # exactly 2 bars at 128
    conform = ss.conform_plan(e, ss.BLEND[2]["groove"], 128.0)
    assert conform is not None and conform["stretch"] == 1.0
    # 88 BPM drum loop read as half-time feel for 176: no stretch needed
    half = _entry(bpm=88.0, seconds=4 * 240 / 176.0 * 2)
    c2 = ss.conform_plan(half, ss.BLEND[5]["groove"], 176.0)
    assert c2 is not None and c2["feel_bpm"] == 176.0 and abs(c2["stretch"] - 1.0) < 1e-9
    # 112 BPM at 128 would need a 14 % stretch: rejected
    assert ss.conform_plan(_entry(bpm=112.0, seconds=2.0), ss.BLEND[2]["groove"], 128.0) is None


def test_loop_rejected_when_not_whole_bars():
    # 1.5 bars at 128 BPM
    e = _entry(bpm=128.0, seconds=1.5 * 240 / 128.0)
    assert ss.conform_plan(e, ss.BLEND[2]["groove"], 128.0) is None


def test_tonal_slot_rejects_file_out_of_key_range():
    spec = ss.BLEND[2]["bass"]
    assert ss.conform_plan(_entry(categories=["bass_loop"], detected_key="G# min", bpm=128.0,
                                  seconds=2 * 240 / 128.0), spec, 128.0) is None


def test_passes_filter_indian_and_category():
    perc = ss.BLEND[1]["indian_perc"]
    dharma = _entry(pack="Dharma Studio - Sounds of KSHMR Vol.5 Complete Edition", categories=["perc"])
    modern = _entry(categories=["perc"])
    assert ss.passes_filter(dharma, perc, True)
    assert not ss.passes_filter(modern, perc, True)
    assert ss.passes_filter(modern, perc, None)
    assert not ss.passes_filter(dharma, ss.BLEND[2]["groove"], False)  # drum_loop cat not in dharma perc item


def test_placements_on_plan_grid():
    plan = {"sections": [{"start_s": 0.0, "end_s": 6.0, "bpm": 60},
                         {"start_s": 6.0, "end_s": 11.375, "bpm": 60}],
            "events": [{"at_s": 7.0, "type": "hit"}, {"at_s": 70.0, "type": "end_sting"}]}
    assert ss.placements(plan, 1, "pulse") == [6.0, 7.0, 8.0, 9.0, 10.0, 11.0]
    assert ss.placements(plan, 1, "riser") == [11.375]
    assert ss.placements(plan, 1, "hit") == [7.0]


def test_check_selection_catches_file_used_twice_and_big_shift():
    opt = {"path": "D:/lib/a.wav", "file": "a.wav", "shift": 0, "stretch": 1.0, "feel_bpm": None}
    sel = {"slots": {"S1-bed": {"section": 1, "layer": "bed", "status": "active", "indian": True,
                                "options": [opt]},
                     "S1-hit": {"section": 1, "layer": "hit", "status": "active", "indian": False,
                                "options": [dict(opt, shift=5)]}}}
    errors = ss.check_selection(sel)
    assert any("used twice" in e for e in errors)
    assert any("shift" in e for e in errors)


def test_score_prefers_zone_and_penalises_low_end_under_voice_layers():
    spec = ss.BLEND[0]["indian_lead"]
    conform = {"stretch": 1.0, "shift": 0}
    good = {"centroid": 600.0, "low": 0.01, "mid": 0.05, "onset": 1.0}
    muddy = {"centroid": 600.0, "low": 0.6, "mid": 0.05, "onset": 1.0}
    e = _entry(detected_key="D min", detected_confidence=0.2)
    assert ss.score_features(e, spec, "indian_lead", conform, good, 0.12) > \
        ss.score_features(e, spec, "indian_lead", conform, muddy, 0.12)


def test_measure_pure_tone_centroid_and_clean_peak(tmp_path):
    sr = 44100
    t = np.arange(sr * 2) / sr
    x = 0.5 * np.sin(2 * math.pi * 440.0 * t)
    path = str(tmp_path / "tone.wav")
    sf.write(path, np.stack([x, x], axis=1), sr)
    f = ss.measure(path, 2.0)
    assert abs(f["centroid"] - 440.0) < 40.0
    assert f["low"] < 0.01          # 440 Hz is above 120 Hz
    assert 0.45 < f["peak"] < 0.55  # no clipping


def test_measure_2khz_tone_sits_in_mid_band(tmp_path):
    sr = 44100
    t = np.arange(sr * 2) / sr
    x = 0.5 * np.sin(2 * math.pi * 2000.0 * t)
    path = str(tmp_path / "tone2k.wav")
    sf.write(path, np.stack([x, x], axis=1), sr)
    f = ss.measure(path, 2.0)
    assert f["mid"] > 0.9
    assert abs(f["centroid"] - 2000.0) < 80.0


def test_loop_key_check_uses_at_least_two_cycles_capped_at_30s():
    # 2-bar loop at 128 BPM = 3.75 s; two cycles = 7.5 s
    cycle = ss.loop_cycle_seconds(4.0, 128.0, 128.0)
    assert abs(cycle - 3.75) < 1e-9
    assert abs(ss.key_check_seconds("loop", cycle, 4.0) - 7.5) < 1e-9
    # long loop: capped at 30 s
    assert ss.key_check_seconds("loop", 20.0, 40.0) == 30.0
    # non-loop: the whole conformed file up to 30 s
    assert ss.key_check_seconds("bed", None, 12.0) == 12.0
    assert ss.key_check_seconds("window", None, 50.0) == 30.0


def test_window_slot_is_slowed_and_fixed_stretch():
    spec = ss.EXTRA_SPEC
    assert spec["window"] == (56.0, 64.0)
    c = ss.conform_plan(_entry(detected_key="D min", categories=["sitar"]), spec, 176.0)
    assert c is not None and abs(c["stretch"] - 0.88) < 1e-9 and c["shift"] == 0
