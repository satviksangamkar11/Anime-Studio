import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audio_edge


def test_failed_write_leaves_no_tmp(tmp_path, monkeypatch):
    target = tmp_path / "out.wav"
    tmp_path_str = str(target) + ".tmp"

    def failing_open(name, mode):
        raise OSError("disk error")

    monkeypatch.setattr(audio_edge.wave, "open", failing_open)

    with pytest.raises(OSError):
        audio_edge.write_wav_mono(str(target), [0.0, 0.5], 8000)

    assert not os.path.exists(tmp_path_str)
    assert not os.path.exists(str(target))


def test_good_write_leaves_only_target(tmp_path):
    target = tmp_path / "out.wav"
    audio_edge.write_wav_mono(str(target), [0.0, 0.5], 8000)

    names = os.listdir(str(tmp_path))
    assert names == [str(target.name)]
