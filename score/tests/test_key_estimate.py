"""Tests for score/key_estimate.py: synthetic triads with a known key must read that key."""
import numpy as np
import soundfile as sf

from score.key_estimate import detect_file, estimate_key

SR = 48000


def _triad(freqs, seconds=4.0):
    t = np.arange(int(seconds * SR)) / SR
    x = sum(np.sin(2 * np.pi * f * t) for f in freqs)
    return x / np.max(np.abs(x))


def test_d_minor_triad_reads_d_minor():
    # D3 F3 A3 with the root doubled an octave down so the tonic is the bass
    x = _triad([146.83, 174.61, 220.0, 73.42])
    res = estimate_key(x, SR)
    assert res["key"] in ("D min", "F maj"), res
    assert res["key"] == "D min", res


def test_c_major_triad_reads_c_major():
    # C4 E4 G4 with C2 in the bass: tonic C, major third
    x = _triad([261.63, 329.63, 392.0, 65.41])
    res = estimate_key(x, SR)
    assert res["key"] == "C maj", res


def test_silence_is_unknown():
    res = estimate_key(np.zeros(SR), SR)
    assert res["key"] is None and res["confidence"] == 0.0


def test_detect_file_reads_wav(tmp_path):
    p = tmp_path / "dm.wav"
    sf.write(str(p), _triad([146.83, 174.61, 220.0, 73.42], 3.0), SR)
    res = detect_file(str(p))
    assert res["key"] == "D min" and res["seconds"] == 3.0
