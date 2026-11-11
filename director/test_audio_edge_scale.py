import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import audio_edge


def test_roundtrip_error_below_half_lsb(tmp_path):
    import numpy as np
    values = list(np.linspace(-1.0, 0.99996, 1001))
    path = tmp_path / "roundtrip.wav"
    audio_edge.write_wav_mono(path, values, 8000)
    read_back, sr = audio_edge.read_wav_mono(path)
    assert sr == 8000
    max_err = max(abs(a - b) for a, b in zip(values, read_back))
    assert max_err <= 1 / 32768 + 1e-12


def test_half_scale_exact(tmp_path):
    path = tmp_path / "half.wav"
    audio_edge.write_wav_mono(path, [0.5], 8000)
    read_back, sr = audio_edge.read_wav_mono(path)
    assert sr == 8000
    assert read_back[0] == 0.5


def test_minus_one_exact(tmp_path):
    path = tmp_path / "minus_one.wav"
    audio_edge.write_wav_mono(path, [-1.0], 8000)
    read_back, sr = audio_edge.read_wav_mono(path)
    assert sr == 8000
    assert read_back[0] == -1.0


def test_plus_one_clamps(tmp_path):
    path = tmp_path / "plus_one.wav"
    audio_edge.write_wav_mono(path, [1.0], 8000)
    read_back, sr = audio_edge.read_wav_mono(path)
    assert sr == 8000
    assert read_back[0] == 32767 / 32768
