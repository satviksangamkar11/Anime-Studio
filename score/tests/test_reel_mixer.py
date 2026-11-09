"""Tests for score/reel_mixer.py: SFX policy and speech-clarity math on a toy timeline. Pure, no ffmpeg."""
import numpy as np
import pytest

from score import reel_mixer as rm

SR = 48000


def _toy(total_s=10.0):
    n = int(total_s * SR)
    t = np.arange(n) / SR
    # bed: steady low noise at -40 dBFS-ish
    rng = np.random.default_rng(0)
    stem = 0.3 * rng.standard_normal(n)  # about -10 dBFS: louder than the voice targets, so lowering applies
    return n, stem, t


def _cue(shots, cuts=()):
    return {"cuts": [{"at_s": c} for c in cuts],
            "shots": [{"id": sid, "start_s": a, "end_s": b} for sid, a, b in shots]}


def test_expected_hit_kept_and_capped_at_1_2s():
    n, stem, t = _toy()
    # a long decaying tone starting at 2.0 s (never decays 20 dB inside cap -> capped)
    stem[_s(2.0):] += 0.5 * np.sin(2 * np.pi * 440 * t[_s(2.0):])
    env = rm.rms_grid_db(stem)
    a, b, fade = rm.hit_window(env, 2.0, n)
    assert a == _s_(1.95)
    assert (b - a) / SR <= rm.HIT_MAX_S + 1e-6
    assert fade == int(round(rm.HIT_FADE_S * SR))


def test_expected_hit_level_and_extra_under_speech_muted():
    n, stem, t = _toy()
    # click at 1.0 (outside speech) and click at 3.0 (inside speech)
    stem[_s(1.0):_s(1.0) + 500] += 0.2
    stem[_s(3.0):_s(3.0) + 500] += 0.2
    env = rm.rms_grid_db(stem)
    cue = _cue([("SHOT-A", 0.0, 10.0)], cuts=[])
    speech = [(2.5, 4.0)]
    vo = np.zeros(n)
    vo[_s(2.5):_s(4.0)] = 0.3 * np.sin(2 * np.pi * 200 * t[_s(2.5):_s(4.0)])
    vo_peak_db = float(20 * np.log10(np.max(np.abs(vo))))
    events = [
        {"t": 1.0, "expected": True, "matched_key": "k1"},
        {"t": 3.0, "expected": False, "matched_key": None},
    ]
    G, recs = rm.sfx_gain(n, stem, env, cue, events, speech, vo, vo_peak_db)
    kept = [r for r in recs if r["t"] == 1.0][0]
    assert kept["kept"] and kept["target_db"] == pytest.approx(vo_peak_db - rm.HIT_LEVEL_OUT_DB, abs=0.01)
    # extra inside speech: muted everywhere in its window
    extra = [r for r in recs if r["t"] == 3.0][0]
    assert not extra["kept"]
    assert np.all(G[_s(extra["a_s"]):_s(extra["b_s"])] == 0.0)


def test_bed_lowered_by_22_and_12_db_and_tonal_shot_muted():
    n, stem, t = _toy(10.0)
    vo = np.zeros(n)
    speech = [(1.0, 3.0)]
    vo[_s(1.0):_s(3.0)] = 0.1 * np.sin(2 * np.pi * 300 * t[_s(1.0):_s(3.0)])
    vo_peak_db = float(20 * np.log10(np.max(np.abs(vo))))
    env = rm.rms_grid_db(stem)
    cue = _cue([("SHOT-A", 0.0, 5.0), ("SHOT-004", 5.0, 10.0)], cuts=[5.0])
    G, _ = rm.sfx_gain(n, stem, env, cue, [], speech, vo, vo_peak_db)
    # shot A inside speech: bed after gain sits 22 dB under the shot voice RMS
    shot_v = rm.rms_db(vo[_s(1.0):_s(3.0)])
    bed_after = rm.rms_db(stem[_s(1.5):_s(2.5)] * G[_s(1.5):_s(2.5)])
    assert bed_after == pytest.approx(shot_v - rm.BED_SPEECH_DB, abs=0.5)
    # shot A gap: 12 dB under the shot voice RMS
    gap_after = rm.rms_db(stem[_s(3.5):_s(4.5)] * G[_s(3.5):_s(4.5)])
    assert gap_after == pytest.approx(shot_v - rm.BED_GAP_DB, abs=0.5)
    # tonal shot 004: bed fully muted
    assert np.all(G[_s(5.0):_s(10.0)] == 0.0)


def test_gain_ramps_have_no_steps():
    n = 5 * SR
    G = np.zeros(n)
    G[SR:2 * SR] = 1.0
    G[3 * SR:4 * SR] = 0.25
    g = rm.ramp_smooth(G)
    kernel_peak = 2.0 / int(round(rm.RAMP_S * SR))  # max slope of a 30 ms raised cosine
    assert np.max(np.abs(np.diff(g))) <= kernel_peak * 1.05
    assert g.min() >= 0.0


def test_clarity_margin_math():
    n = 4 * SR
    t = np.arange(n) / SR
    voice = 0.5 * np.sin(2 * np.pi * 2000 * t)  # in the 1-4 kHz band
    sfx = 0.5 * 10 ** (-14 / 20) * np.sin(2 * np.pi * 900 * t)  # 14 dB under voice full band
    music = np.zeros(n)
    speech = [(0.0, 3.0)]
    res = rm.clarity(voice, sfx, music, speech, [], float(20 * np.log10(0.5)), 4.0)
    assert res["min_full_margin_db"] == pytest.approx(14.0, abs=0.1)
    assert res["clarity_full_ok"] is True
    # 1-4 kHz band: the 900 Hz tone is out of band, so its share there is ~0 -> margin large
    assert res["min_band_margin_db"] > rm.CLARITY_BAND_DB


def test_ducker_meets_12_and_15_db_never_boosts_and_ramps_smooth():
    n = 10 * SR
    t = np.arange(n) / SR
    voice = np.zeros(n)
    voice[_s(1.0):_s(3.0)] = 0.3 * np.sin(2 * np.pi * 2000 * t[_s(1.0):_s(3.0)])
    rng = np.random.default_rng(1)
    bus = 0.3 * rng.standard_normal(n)  # broadband bus, louder than the voice in full band
    bus[:_s(1.0)] = 1e-4 * bus[:_s(1.0)]  # quiet outside speech: the gap rule must not fire here
    bus[_s(3.0):] = 1e-4 * bus[_s(3.0):]
    speech = [(1.0, 3.0)]
    g_full, g_mid, stats = rm.duck_gains(voice, bus, speech, [])
    assert g_full.max() <= 1.0 + 1e-9 and g_mid.max() <= 1.0 + 1e-9  # never boost
    assert g_full.min() >= 0.0 and g_mid.min() >= 0.0
    # smooth: no steps (slope bounded by a raised cosine of DUCK_ATTACK_S)
    att_n = int(round(rm.DUCK_ATTACK_S * SR))
    assert np.max(np.abs(np.diff(g_full))) <= 2.5 / att_n
    assert np.max(np.abs(np.diff(g_mid))) <= 2.5 / att_n
    # outside speech and after release: no reduction at all
    # release tail (250 ms constant) has run out 2 s after speech ends
    assert np.all(g_full[_s(5.0):] == pytest.approx(1.0, abs=1e-3))
    assert np.all(g_full[:_s(0.9)] == pytest.approx(1.0, abs=1e-6))
    # clear the voice margins on the ducked bus
    bus_d = rm.apply_duck(bus[:, None] * np.ones((1, 2)), g_full, g_mid)[:, 0]
    res = rm.clarity(voice, bus_d, np.zeros(n), speech, [], float(20 * np.log10(0.3)), 10.0)
    assert res["min_full_margin_db"] >= rm.CLARITY_FULL_DB
    assert res["min_band_margin_db"] >= rm.CLARITY_BAND_DB
    assert stats["mean_reduction_speech_db"] > 0.0


def test_ducker_leaves_quiet_bus_alone():
    n = 6 * SR
    voice = np.zeros(n)
    voice[_s(1.0):_s(3.0)] = 0.3 * np.sin(2 * np.pi * 2000 * np.arange(_s(2.0)) / SR)
    bus = 1e-4 * np.random.default_rng(2).standard_normal(n)  # far under the voice
    g_full, g_mid, _ = rm.duck_gains(voice, bus, [(1.0, 3.0)], [])
    assert np.allclose(g_full, 1.0) and np.allclose(g_mid, 1.0)


def _s_(t):
    return rm._s(t)


def _s(t):
    return rm._s(t)
