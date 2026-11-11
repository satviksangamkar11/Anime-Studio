"""Offline tests for X-17 of build_final_reel: the --mix intake (length, rate, voice-over-bus level), the versioned export name
(never overwrite) and the free-disk check before export. Synthetic WAVs only; no ffmpeg, no model call, no network."""
import math
import struct
import sys
import wave
from collections import namedtuple
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_final_reel as b  # noqa: E402

RATE = 48000
FRAMES_TOTAL_LOCK = 480                      # 20.0 s at 24 fps
NEED = FRAMES_TOTAL_LOCK * 2000              # 48000 / 24 samples per frame = 960000


def write_wav(path, samples, rate=RATE):
    """Mono 16-bit WAV. samples: iterable of floats in -1..1."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples))
    return Path(path)


def sine(n, amp, freq=440.0, rate=RATE):
    return [amp * math.sin(2 * math.pi * freq * i / rate) for i in range(n)]


def windows_for_one_second():
    """One report row at offset 0 with one spoken line from 0.0 s to 1.0 s (the speech window the level check measures)."""
    return [{"offset_sec": 0.0, "lines": [{"start": 0.0, "end": 1.0}]}]


def test_mix_one_frame_short_refused(tmp_path):
    n = NEED - 2000                           # one frame short
    mix = write_wav(tmp_path / "mix.wav", sine(n, 0.55))
    voice = write_wav(tmp_path / "voice.wav", sine(n, 0.5))
    with pytest.raises(SystemExit) as e:
        b.intake(mix, voice, FRAMES_TOTAL_LOCK, windows_for_one_second(), work_dir=tmp_path)
    assert "short" in str(e.value)


def test_mix_wrong_rate_refused(tmp_path):
    mix = write_wav(tmp_path / "mix.wav", sine(NEED, 0.55, rate=44100), rate=44100)
    voice = write_wav(tmp_path / "voice.wav", sine(NEED, 0.5, rate=44100), rate=44100)
    with pytest.raises(SystemExit):
        b.intake(mix, voice, FRAMES_TOTAL_LOCK, windows_for_one_second(), work_dir=tmp_path)


def test_mix_long_trimmed_to_960000(tmp_path):
    mix = write_wav(tmp_path / "mix.wav", sine(NEED + 500, 0.55))
    voice = write_wav(tmp_path / "voice.wav", sine(NEED + 500, 0.5))
    res = b.intake(mix, voice, FRAMES_TOTAL_LOCK, windows_for_one_second(), work_dir=tmp_path)
    with wave.open(res["trimmed_path"], "rb") as w:
        assert w.getnframes() == NEED
        assert w.getframerate() == RATE
    # the trim keeps the FIRST `need` samples, not the last ones (a 500-sample tail would shift every value)
    _, got = b.read_wav(res["trimmed_path"])
    _, src = b.read_wav(mix)
    assert got.shape == (NEED, 1)
    assert np.allclose(got, src[:NEED], atol=1e-4)


def test_voice_over_bus_20db_passes(tmp_path):
    mix = write_wav(tmp_path / "mix.wav", [v + u for v, u in zip(sine(NEED, 0.5), sine(NEED, 0.05))])
    voice = write_wav(tmp_path / "voice.wav", sine(NEED, 0.5))
    res = b.intake(mix, voice, FRAMES_TOTAL_LOCK, windows_for_one_second(), work_dir=tmp_path)
    assert res["median_db"] == pytest.approx(20.0, abs=0.05)
    assert res["min_db"] == pytest.approx(20.0, abs=0.05)


def test_bus_too_loud_fails(tmp_path):
    # bus amplitude 0.2 against voice 0.5: 20*log10(0.5/0.2) = 7.96 dB, below the 12 dB floor
    mix = write_wav(tmp_path / "mix.wav", [v + u for v, u in zip(sine(NEED, 0.5), sine(NEED, 0.2))])
    voice = write_wav(tmp_path / "voice.wav", sine(NEED, 0.5))
    with pytest.raises(SystemExit) as e:
        b.intake(mix, voice, FRAMES_TOTAL_LOCK, windows_for_one_second(), work_dir=tmp_path)
    assert "7.9" in str(e.value)


def test_next_version_r3_and_r1_untouched(tmp_path):
    (tmp_path / "kalika_x_hi_r1.mp4").write_bytes(b"first")
    (tmp_path / "kalika_x_hi_r2.mp4").write_bytes(b"second")
    (tmp_path / "kalika_x_en_r7.mp4").write_bytes(b"other language")
    nxt = b.next_export(tmp_path, "kalika_x", "hi")
    assert nxt.name == "kalika_x_hi_r3.mp4"
    assert (tmp_path / "kalika_x_hi_r1.mp4").read_bytes() == b"first"
    assert b.next_export(tmp_path / "empty_dir_missing", "kalika_x", "hi").name == "kalika_x_hi_r1.mp4"


def test_low_disk_refused(tmp_path):
    Usage = namedtuple("Usage", "total used free")
    low = lambda p: Usage(10 * 2**30, 9 * 2**30, 1 * 2**30)       # 1 GB free
    with pytest.raises(SystemExit):
        b.check_free_disk(tmp_path, min_gb=2.0, disk_usage=low)
    enough = lambda p: Usage(10 * 2**30, 7 * 2**30, 3 * 2**30)    # 3 GB free
    b.check_free_disk(tmp_path, min_gb=2.0, disk_usage=enough)
    with pytest.raises(SystemExit):                                # default floor = MIN_FREE_GB_EXPORT (2.0 GB)
        b.check_free_disk(tmp_path, disk_usage=low)
    b.check_free_disk(tmp_path, disk_usage=enough)
