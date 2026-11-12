"""NO_SILENCE v2 tests (OPUS_FINAL_REVIEW E6). Synthetic stereo signals; levels hand-computed:
a sine of peak A has RMS A/sqrt(2) = A - 3.01 dB, so peak 0.1414 -> RMS -20 dBFS."""
import time

import numpy as np

from h3 import silence_rule as sr

R = 48000


def tone(sec, rms_db, ch=2):
    t = np.arange(int(round(sec * R))) / R
    a = 10 ** (rms_db / 20) * np.sqrt(2)
    return np.tile((a * np.sin(2 * np.pi * 220 * t))[:, None], (1, ch))


def zeros(sec, ch=2):
    return np.zeros((int(round(sec * R)), ch))


def run(x, **kw):
    return sr.check_array(x, R, **kw)


def codes(rep, key="errors"):
    return [f["code"] for f in rep[key]]


def test_digital_silence_60ms_fails():
    rep = run(np.vstack([tone(1, -20), zeros(0.06), tone(1, -20)]))
    assert "DIGITAL_SILENCE" in codes(rep) and not rep["ok"]


def test_digital_silence_40ms_passes():
    # 40 ms of zeros inside a quiet bed (-55 dBFS): not digital silence, and not a dropout (bed is not loud)
    rep = run(np.vstack([tone(1, -55), zeros(0.04), tone(1, -55)]))
    assert rep["ok"], rep["errors"]


def test_dropout_cut_fails_fade_passes():
    cut = run(np.vstack([tone(1, -20), zeros(0.1), tone(1, -20)]))
    assert "DROPOUT" in codes(cut)
    fade = tone(2, -20) * np.linspace(1, 10 ** (-45 / 20), 96000)[:, None]       # -20 -> -65 dBFS
    rep = run(np.vstack([tone(0.5, -20), fade, tone(0.5, -20)]))
    assert "DROPOUT" not in codes(rep)


def test_channel_drop_fails():
    x = tone(2, -30)
    x[24000:24000 + 28800, 0] = 0.0                      # left dead for 0.6 s, right stays at -30 dBFS
    assert "CHANNEL_DROP" in codes(run(x))


def test_quiet_bed_minus55_is_warning_only():
    rep = run(tone(2, -55))
    assert rep["ok"] and "QUIET" in codes(rep, "warnings")


def test_dead_air_1_2s_minus65_fails():
    rep = run(np.vstack([tone(1, -20), tone(1.2, -65), tone(1, -20)]))
    assert "DEAD_AIR" in codes(rep)


def test_silence_ok_window_allows_1_8s():
    x = np.vstack([tone(1, -20), tone(1.8, -65), tone(1, -20)])
    assert "DEAD_AIR" in codes(run(x))
    rep = run(x, silence_ok=[(1.0, 2.8)])
    assert rep["ok"], rep["errors"]
    assert "DEAD_AIR" in codes(run(np.vstack([tone(1, -20), tone(2.3, -65), tone(1, -20)]), silence_ok=[(1.0, 3.3)]))


def test_voice_rest_exempts_quiet_warning():
    x = np.vstack([tone(1, -20), tone(1.0, -55), tone(1, -20)])
    assert "QUIET" in codes(run(x), "warnings")
    assert "QUIET" not in codes(run(x, voice_rest=[(0.9, 2.1)]), "warnings")


def test_tail_fade_exempt():
    x = np.vstack([tone(2, -20), tone(0.5, -20) * np.linspace(1, 0, 24000)[:, None]])
    assert codes(run(x), "warnings") == []


def test_head_silence_warns():
    rep = run(np.vstack([tone(0.2, -70), tone(2, -20)]))
    assert "HEAD" in codes(rep, "warnings") and rep["ok"]


def test_reel_windows_convert_shot_relative():
    assert sr.reel_windows([(1.0, 2.0)], 7.0) == [(8.0, 9.0)]


def test_75s_stereo_under_2s():
    x = tone(75, -20)
    t0 = time.time()
    run(x)
    assert time.time() - t0 < 2.0
