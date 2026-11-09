"""Small checks for score/sfx_study.py: scores on synthetic signals, onset times, overlap math, cue matching."""
import numpy as np
from scipy import signal

from score import sfx_study as ss

SR = 16000


def _rng():
    return np.random.default_rng(0)


def test_speech_like_high_on_4hz_am_speech_band_noise_low_on_steady():
    rng = np.random.default_rng(1)
    n = SR * 6
    t = np.arange(n) / SR
    carrier = bandpass_noise(rng, n, (300, 3400))
    am = carrier * (0.5 + 0.5 * np.cos(2 * np.pi * 4 * t))
    steady = bandpass_noise(rng, n, (300, 3400))
    assert ss.speech_like_score(am, SR) > 0.6
    assert ss.speech_like_score(steady, SR) < 0.4


def bandpass_noise(rng, n, band):
    sos = signal.butter(4, band, btype="bandpass", fs=SR, output="sos")
    return signal.sosfilt(sos, rng.standard_normal(n))


def test_music_like_high_on_held_chord_low_on_noise():
    t = np.arange(SR * 3) / SR
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 330.0, 440.0)) / 3
    noise = _rng().standard_normal(len(t)) * 0.3
    assert ss.tonal_summary(chord, SR)["music_like"] > 0.8
    assert ss.tonal_summary(noise, SR)["music_like"] < 0.2


def test_onsets_find_clicks_at_known_times():
    x = np.zeros(SR * 4)
    rng = np.random.default_rng(2)
    times = [0.5, 1.4, 2.6, 3.3]
    for t in times:
        i = int(t * SR)
        x[i:i + 40] = rng.standard_normal(40) * 0.8
    found = ss.onset_times(x, SR)
    assert len(found) == len(times)
    for t, f in zip(times, found):
        assert abs(t - f) < 0.025


def test_overlap_math_on_toy_timeline():
    sr = 1000
    sfx = np.zeros(sr * 4)
    voice = np.zeros(sr * 4)
    sfx[1000:2000] = 0.1
    voice[1000:2000] = 1.0
    # window covers the 1 s block only, so the level difference is exactly 20 dB
    assert abs(ss.sfx_vs_voice_db(sfx, voice, sr, [(1.0, 2.0)]) + 20.0) < 1e-6
    # window that holds no voice energy plus no sfx gives None
    assert ss.sfx_vs_voice_db(sfx, voice, sr, [(3.0, 3.0)]) is None


def test_match_cues_marks_expected_and_extra():
    cues = [{"key": "bell", "start": 2.0, "end": 2.8}]
    hits = [{"t": 2.2, "peak_dbfs": -20.0, "above_bed_db": 10.0},
            {"t": 5.0, "peak_dbfs": -22.0, "above_bed_db": 9.0}]
    rows, cue_rows = ss.match_cues(hits, cues, shot_range=(0.0, 8.0))
    assert rows[0]["expected"] and rows[0]["matched_key"] == "bell"
    assert not rows[1]["expected"]
    assert cue_rows[0]["matched"]
