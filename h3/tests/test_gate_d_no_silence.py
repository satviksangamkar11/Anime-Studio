"""Gate D NO_SILENCE (quiet span > 0.3 s below -50 dBFS) and LRA warn (> 11 LU). Card M-09, plan item T-06.

Synthetic WAVs written by the test itself. Expected values are hand-computed:
a sine of peak amplitude A has RMS A/sqrt(2); 0.01 peak -> 0.00707 RMS -> -43.0 dBFS (above the -50 floor).
Digital silence has no level at all (-inf dBFS), so it always counts as quiet.
"""
import array
import math
import sys
import wave

from h3 import gate_d_audio as gd

RATE = 8000  # 80 samples per 10 ms window


def _write_wav(path, samples, rate=RATE):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        a = array.array("h", samples)
        if sys.byteorder == "big":
            a.byteswap()
        w.writeframes(a.tobytes())
    return str(path)


def _tone(seconds, amp, rate=RATE, freq=220.0):
    return [int(round(amp * 32767 * math.sin(2 * math.pi * freq * i / rate))) for i in range(int(round(seconds * rate)))]


def _codes(rep):
    return [e["code"] for e in rep["errors"]]


def test_half_second_digital_silence_fails(tmp_path):
    # NO_SILENCE v2: 0.5 s of digital zeros mid-file is DIGITAL_SILENCE (never waivable)
    wav = _write_wav(tmp_path / "gap.wav", _tone(0.25, 0.5) + [0] * 4000 + _tone(0.25, 0.5))
    rep = gd.check_no_silence(wav)
    assert rep["ok"] is False
    assert "DIGITAL_SILENCE" in _codes(rep)


def test_low_noise_bed_passes(tmp_path):
    # a 1 s bed at peak 0.01 is about -43 dBFS: above the -50 floor, no finding at all
    rep = gd.check_no_silence(_write_wav(tmp_path / "bed.wav", _tone(1.0, 0.01)))
    assert rep["ok"] is True and rep["errors"] == [] and rep["warnings"] == []


def test_quiet_span_is_only_a_warning(tmp_path):
    # peak 0.002 -> RMS -57 dBFS for 1 s: the old rule failed this, v2 warns QUIET and passes
    rep = gd.check_no_silence(_write_wav(tmp_path / "quiet.wav", _tone(1.0, 0.002)))
    assert rep["ok"] is True
    assert any(w.startswith("QUIET") for w in rep["warnings"])


def _ebur(lra):
    return ("  I:         -14.0 LUFS\n"
            "  LRA:       " + str(lra) + " LU\n"
            "True peak:\n    Peak:      -1.5 dBFS\n")


def test_lra_above_11_warns_but_does_not_fail():
    rep = gd.check_post_aac_loudness(_ebur(12.3))
    assert rep["ok"] is True
    assert any("LRA" in w for w in rep["warnings"])
    assert rep["stats"]["lra"] == 12.3


def test_lra_at_11_gives_no_warning():
    rep = gd.check_post_aac_loudness(_ebur(11.0))
    assert rep["ok"] is True
    assert not any("LRA" in w for w in rep["warnings"])


def test_lra_missing_is_none_and_no_warning():
    text = "  I:         -14.0 LUFS\nTrue peak:\n    Peak:      -1.5 dBFS\n"
    assert gd.parse_lra(text) is None
    rep = gd.check_post_aac_loudness(text)
    assert rep["warnings"] == []
    assert rep["stats"]["lra"] is None
