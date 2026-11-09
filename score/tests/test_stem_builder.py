"""Tests for score/stem_builder.py: timing on exact samples, tiling, gating under voice, level maths."""
import numpy as np

from score import stem_builder as sb


def test_cut_points_are_exact_frame_samples():
    # 24 fps at 48 kHz: 2000 samples per frame; reel 1 cut at 11.375 s = frame 273
    assert sb.snap_frame(11.375) == 273 * 2000 == 546000
    assert sb.snap_frame(18.833) == 452 * 2000  # snapped to the frame grid, not rounded in seconds
    assert sb.time_sample(35.125) == 1686000


def test_stem_length_equals_total_samples_after_placement():
    total = 3496000
    stem = np.zeros((2, total))
    piece = np.ones((2, 500000))
    n = sb.place(stem, piece, 3000000, total)  # crosses the end: cut at total
    assert n == total - 3000000
    assert stem.shape[1] == total
    assert stem[:, total - 1].sum() == 2.0


def test_place_cuts_at_limit_and_crops_before_zero():
    target = np.zeros((2, 100))
    sample = np.arange(1, 51, dtype=float)[None, :].repeat(2, axis=0)
    sb.place(target, sample, -10, 100)  # first 10 samples of the sample are before the start
    assert target[0, 0] == 11.0 and target[0, 39] == 50.0 and target[0, 40] == 0.0
    sb.place(target, sample, 90, 95)     # limit at sample 95 cuts it
    assert np.all(target[:, 95:] == 0.0)


def test_tile_repeats_length_exactly():
    sample = np.ones((2, 1000))
    out = sb.tile(sample, 3500, 0.0)
    assert out.shape == (2, 3500)
    assert np.allclose(out, 1.0)


def test_loop_length_whole_bars():
    tempo = 128.0
    bar = 240.0 / tempo * sb.SR  # 90000 samples per bar
    sample = np.ones((2, int(round(2.2 * bar))))  # 2.2 bars conformed
    out = sb.loop_length(sample, tempo)
    assert out.shape[1] == 2 * 90000  # rounded to whole bars


def test_gate_applies_under_voice_and_not_outside():
    total = 48000 * 2
    mask = sb.voice_mask(total, [(0.5, 1.0)], ramp_s=0.001)
    stem = np.ones((2, total))
    gated = sb.gate_layer(stem, "indian_lead", mask)
    inside = gated[0, 30000:40000]
    outside = gated[0, 80000:90000]
    assert np.allclose(outside, 1.0)
    assert np.allclose(inside, 10 ** (sb.DUCK_DB / 20.0), atol=1e-6)
    assert 10 ** (sb.DUCK_DB / 20.0) < 0.2  # at least 15 dB down


def test_bass_under_voice_keeps_only_low_band():
    total = 48000
    t = np.arange(total) / sb.SR
    high = np.sin(2 * np.pi * 3000 * t)
    stem = np.stack([high, high])
    mask = np.ones(total)  # whole clip under voice
    gated = sb.gate_layer(stem, "bass", mask)
    assert np.sqrt(np.mean(gated[0, 5000:] ** 2)) < 0.01  # 3 kHz removed under speech


def test_level_gain_hits_target_difference():
    voice = np.ones(48000)
    score = np.stack([np.full(48000, 0.1), np.full(48000, 0.1)])
    windows = [(0.0, 1.0)]
    s_db, v_db = sb.window_levels(score, voice, windows)
    gain_db = sb.VOICE_TARGET_DB - (s_db - v_db)
    after = s_db + gain_db - v_db
    assert abs(after - sb.VOICE_TARGET_DB) < 1e-9


def test_sidechain_drops_on_kick_peaks():
    total = 48000
    groove = np.zeros((2, total))
    groove[:, ::12000] = 0.9  # four kicks
    g = sb.sidechain_gain(groove)
    assert g.min() < 0.8 and g.max() <= 1.0 + 1e-9
    assert g[0] < 1.0


def test_fade_edges_no_click_at_ends():
    x = np.ones((2, 1000))
    y = sb.fade_edges(x, 100)
    assert y[0, 0] == 0.0 and y[0, -1] == 0.0 and y[0, 500] == 1.0


def test_riding_puts_every_window_on_target():
    sr = sb.SR
    total = sr * 10
    voice = np.zeros(total)
    windows = [(1.0, 2.0), (4.0, 5.0), (7.0, 8.5)]
    rng = np.random.default_rng(0)
    for a, b in windows:
        voice[int(a * sr):int(b * sr)] = 0.3 * rng.standard_normal(int((b - a) * sr))
    score = 0.05 * rng.standard_normal(total)  # score level well above target everywhere
    curve, gains, after = sb.riding_gain_db(score, voice, windows)
    assert all(abs(d - sb.VOICE_TARGET_DB) < 0.5 for d in after)
    # outside the windows the gain curve is zero (musical level kept)
    assert abs(curve[int(3.0 * sr)]) < 1e-9
    assert abs(curve[int(9.5 * sr)]) < 1e-9


def test_window_table_counts_inside_target():
    t = sb.window_table([-18.0, -20.0, -12.0, -25.0])
    assert t["min"] == -25.0 and t["max"] == -12.0
    assert t["inside_target_count"] == 2
    assert t["windows"] == 4
