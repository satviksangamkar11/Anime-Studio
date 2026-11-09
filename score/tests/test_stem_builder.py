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


def test_under_voice_dip_only_inside_voice_windows():
    total = sb.SR * 2
    t = np.arange(total) / sb.SR
    stem = np.stack([np.sin(2 * np.pi * 2500.0 * t)] * 2)  # 2.5 kHz: the centre of the dip
    mask = sb.voice_mask(total, [(0.5, 1.0)], ramp_s=0.001)
    dipped = sb.gate_layer(stem, "bed", mask, dip=True)
    plain = sb.gate_layer(stem, "bed", mask, dip=False)
    inside = slice(int(0.6 * sb.SR), int(0.9 * sb.SR))
    outside = slice(int(1.2 * sb.SR), int(1.9 * sb.SR))
    assert np.allclose(dipped[:, outside], stem[:, outside])     # outside voice: untouched
    ratio_db = 20 * np.log10(np.max(np.abs(dipped[0, inside])) / np.max(np.abs(plain[0, inside])))
    assert abs(ratio_db - (-3.0)) < 0.2                          # a 3 dB dip, only under voice
    lead = sb.gate_layer(stem, "indian_lead", mask, dip=True)    # leads are never dipped
    assert np.allclose(lead[0, inside], plain[0, inside])


def test_sidechain_depth_and_sections_on_synthetic_stems():
    # three 1 s sections: HOOK (no kick), BUILD (kick loop), OUTRO (no kick)
    sr = sb.SR
    total = sr * 3
    plan = {"sections": [
        {"start_s": 0.0, "end_s": 1.0, "act": "HOOK", "bpm": 120},
        {"start_s": 1.0, "end_s": 2.0, "act": "BUILD", "bpm": 120},
        {"start_s": 2.0, "end_s": 3.0, "act": "OUTRO", "bpm": 120}]}
    stems = {layer: np.zeros((2, total)) for layer in sb.STEM_LAYERS}
    t = np.arange(total) / sr
    tone = 0.2 * np.sin(2 * np.pi * 90.0 * t)
    stems["bass"][:] = tone
    stems["chords"][:] = 0.1 * np.sin(2 * np.pi * 440.0 * t)
    for k in range(total // (sr // 2)):           # kicks every half second, everywhere
        stems["groove"][:, k * sr // 2: k * sr // 2 + 480] = 0.9
    log = [{"layer": "groove", "kind": "loop", "section": 2, "section_start_sample": sr,
            "section_end_sample": 2 * sr, "window_s": None, "tempo_bpm": 120.0, "times_s": [1.0]},
           {"layer": "bass", "kind": "bed", "section": 2, "section_start_sample": sr,
            "section_end_sample": 2 * sr, "window_s": None, "tempo_bpm": 120.0, "times_s": [1.0]}]
    before = stems["bass"].copy()
    before_chords = stems["chords"].copy()
    out, rows = sb.sidechain_stems(stems, plan, log, total)
    gain_db = 20 * np.log10(np.maximum(np.abs(out["bass"][0]), 1e-12) / np.maximum(np.abs(before[0]), 1e-12))
    in_build = gain_db[sr:2 * sr]
    assert in_build.min() < -4.9 and in_build.min() > -5.2         # depth 5 dB at the kick peaks
    assert np.allclose(out["bass"][:, :sr], before[:, :sr])        # HOOK has no kick: no duck
    assert np.allclose(out["bass"][:, 2 * sr:], before[:, 2 * sr:])  # OUTRO has no kick: no duck
    # pads duck with the 3 dB depth, on the same kick: the smoothed level drops by about 3 dB at the kick
    rms_b = np.sqrt(np.mean(before_chords[0, sr:2 * sr].reshape(-1, 480) ** 2, axis=1))
    rms_o = np.sqrt(np.mean(out["chords"][0, sr:2 * sr].reshape(-1, 480) ** 2, axis=1))
    pad_drop = 20 * np.log10(rms_o / rms_b)
    assert -3.2 < pad_drop.min() < -2.4
    bass_row = next(r for r in rows if r["id"] == "kick>bass")
    assert bass_row["sections"] == [2] and bass_row["depth_db"] == 5.0
    pad_row = next(r for r in rows if r["id"] == "kick>pads")
    assert pad_row["sections"] == [2] and abs(pad_row["max_gr_db"] - 3.0) < 0.05
    assert bass_row["max_step_db"] < 0.2                           # no clicks


def test_voice_only_reference_places_each_shot_at_its_start(tmp_path):
    sr_clip = 44100
    shot_dir = tmp_path / "vo"
    shot_dir.mkdir()
    import soundfile as sf
    clip = np.full(sr_clip, 0.5)                                   # 1 s clip at 44.1 kHz
    sf.write(shot_dir / "SHOT-001.wav", clip, sr_clip)
    cue = {"total_samples": sb.SR * 3,
           "shots": [{"id": "SHOT-001", "start_s": 1.0, "end_s": 2.5}]}
    out_path = tmp_path / "voice_only.wav"
    rows = sb.build_voice_only(cue, out_path=str(out_path), shot_dir=str(shot_dir))
    data, sr = sf.read(out_path, dtype="float64", always_2d=True)
    assert sr == sb.SR and len(data) == sb.SR * 3
    assert abs(data[sb.SR // 2, 0]) < 1e-6                          # silent before the shot
    assert abs(data[sb.SR + sb.SR // 2, 0] - 0.5) < 0.02            # the clip starts at 1.0 s
    assert rows[0][0] == "SHOT-001" and rows[0][2] == 1.0
