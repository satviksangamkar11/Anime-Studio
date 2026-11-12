"""NO_SILENCE v2 (owner 2026-11-12, research/OPUS_FINAL_REVIEW_2026-11-12.md section E): measured on the final
per-language master and on the Ableton mix WAV, never on the pre-mix clip audio.

Fail (never waivable): DIGITAL_SILENCE, DROPOUT, CHANNEL_DROP. Fail (waivable): DEAD_AIR. Warning: QUIET, HEAD.
Reads 16-bit PCM WAV. numpy only. No ffmpeg, no model. Findings are {"code", "where", "message"} dicts.
voice_rest / silence_ok windows are (start, end) seconds on the REEL clock (reel_windows converts shot-relative ones).
"""
from __future__ import annotations

import math
import wave

import numpy as np

DIGITAL_PEAK_DBFS = -90.0
DIGITAL_MIN_S = 0.05
EDGE_IGNORE_S = 0.05
DROPOUT_PRE_DBFS = -40.0
DROPOUT_FLOOR_DBFS = -70.0
DROPOUT_FALL_S = 0.02
DROPOUT_MIN_S = 0.02
DROPOUT_MAX_S = 1.0
CHANNEL_DROP_MIN_S = 0.5
CHANNEL_OTHER_MIN_DBFS = -50.0
DEAD_AIR_DBFS = -60.0
DEAD_AIR_MAX_S = 1.0
SILENCE_OK_MAX_S = 2.0
QUIET_DBFS = -50.0
QUIET_MAX_S = 0.3
HEAD_IGNORE_S = 0.10
TAIL_IGNORE_S = 0.50
RMS_WINDOW_S = 0.05
PEAK_WINDOW_S = 0.01
CRITICAL = ("DIGITAL_SILENCE", "DROPOUT", "CHANNEL_DROP")     # mirrored in director/waivers.py CRITICAL_CODES
EPS = 1e-9


def read_pcm16(path):
    """(rate, float64 array (samples, channels) in -1..1) of a 16-bit PCM WAV."""
    with wave.open(str(path), "rb") as w:
        rate, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise ValueError(f"silence rule reads 16-bit PCM WAV only, got sample width {width}")
    return rate, np.frombuffer(raw, dtype="<i2").reshape(-1, ch).astype(np.float64) / 32768.0


def reel_windows(shot_windows, offset_sec):
    """Shot-relative [(a, b)] -> reel-clock [(a + offset, b + offset)] using the lock's offset_sec of that shot."""
    return [(float(a) + offset_sec, float(b) + offset_sec) for a, b in shot_windows]


def _db(v):
    return 20.0 * np.log10(np.maximum(v, 1e-12))


def _runs(mask):
    """(start, end_exclusive) of every run of True in a 1-D bool array."""
    if not mask.size:
        return []
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def _starts(n, win):
    return np.arange(0, n, win)


def _rms_db(x, win):
    """RMS dBFS of each window of x (samples, channels), all channels together; the last window may be shorter."""
    st = _starts(len(x), win)
    ends = np.append(st[1:], len(x))
    sums = np.add.reduceat((x * x).sum(axis=1), st)
    return _db(np.sqrt(sums / ((ends - st) * x.shape[1])))


def _peak_db(x1d, win):
    return _db(np.maximum.reduceat(np.abs(x1d), _starts(len(x1d), win)))


def _find(code, a, b, message):
    return {"code": code, "where": f"{a:.2f}-{b:.2f}s", "message": message}


def _overlaps(a, b, windows):
    return any(min(b, hi) - max(a, lo) > 0 for lo, hi in windows)


def check_array(x, rate, voice_rest=(), silence_ok=()):
    """The rule on a float array (samples, channels). Returns {"ok", "errors", "warnings", "stats"}."""
    n, ch = x.shape
    dur = n / rate
    errors, warnings = [], []
    exempt = [tuple(map(float, w)) for w in (*voice_rest, *silence_ok)]
    ok_windows = [tuple(map(float, w)) for w in silence_ok]

    # 1. DIGITAL_SILENCE: every channel at/below -90 dBFS peak for >= 50 ms, away from the file edges
    edge, need = int(round(EDGE_IGNORE_S * rate)), int(round(DIGITAL_MIN_S * rate))
    dead = np.abs(x).max(axis=1) <= 10 ** (DIGITAL_PEAK_DBFS / 20)
    for s, e in _runs(dead):
        s, e = max(s, edge), min(e, n - edge)
        if e - s >= need:
            errors.append(_find("DIGITAL_SILENCE", s / rate, e / rate, f"digital silence {(e - s) / rate:.3f}s"))

    # 2. DROPOUT: loud (>= -40) -> below -70 within 20 ms, 20 ms..1.0 s long, back to loud: a cut-out, not a fade
    pw = max(1, int(round(PEAK_WINDOW_S * rate)))
    lv = _rms_db(x, pw)
    lo, hi = int(round(DROPOUT_MIN_S / PEAK_WINDOW_S)), int(round(DROPOUT_MAX_S / PEAK_WINDOW_S))
    for s, e in _runs(lv < DROPOUT_FLOOR_DBFS):
        if not lo <= e - s <= hi or s < 1 or e >= len(lv):
            continue
        pre, post = lv[max(0, s - 2):s].max(), lv[e:e + 2].max()
        if pre >= DROPOUT_PRE_DBFS and post >= DROPOUT_PRE_DBFS:
            errors.append(_find("DROPOUT", s * pw / rate, e * pw / rate, f"cut-out of {(e - s) * PEAK_WINDOW_S:.2f}s"))

    # 3. CHANNEL_DROP: one channel dead for >= 0.5 s while another is audible
    if ch >= 2:
        for c in range(ch):
            others = np.delete(x, c, axis=1)
            for s, e in _runs(_peak_db(x[:, c], pw) <= DIGITAL_PEAK_DBFS):
                if (e - s) * PEAK_WINDOW_S < CHANNEL_DROP_MIN_S - EPS:
                    continue
                seg = others[s * pw:e * pw]
                rms = 20 * math.log10(max(float(np.sqrt(np.mean(seg * seg))), 1e-12))
                if rms >= CHANNEL_OTHER_MIN_DBFS:
                    errors.append(_find("CHANNEL_DROP", s * pw / rate, e * pw / rate,
                                         f"channel {c} dead, others {rms:.1f} dBFS"))

    # 4. DEAD_AIR (fail, waivable) and 5. QUIET (warning), on 50 ms RMS windows
    rw = int(round(RMS_WINDOW_S * rate))
    lv50 = _rms_db(x, rw)
    t = np.arange(len(lv50)) * RMS_WINDOW_S
    for s, e in _runs(lv50 < DEAD_AIR_DBFS):
        a, b = s * RMS_WINDOW_S, e * RMS_WINDOW_S
        limit = SILENCE_OK_MAX_S if _overlaps(a, b, ok_windows) else DEAD_AIR_MAX_S
        if b - a > limit + EPS:
            errors.append(_find("DEAD_AIR", a, b, f"{b - a:.2f}s below {DEAD_AIR_DBFS:g} dBFS, limit {limit:g}s"))
    centre = t + RMS_WINDOW_S / 2
    skip = (centre < HEAD_IGNORE_S) | (centre >= dur - TAIL_IGNORE_S)
    for i, c in enumerate(centre):
        if not skip[i] and any(lo_ <= c < hi_ for lo_, hi_ in exempt):
            skip[i] = True
    for s, e in _runs((lv50 < QUIET_DBFS) & ~skip):
        if (e - s) * RMS_WINDOW_S > QUIET_MAX_S + EPS:
            warnings.append(_find("QUIET", s * RMS_WINDOW_S, e * RMS_WINDOW_S,
                                  f"{(e - s) * RMS_WINDOW_S:.2f}s below {QUIET_DBFS:g} dBFS"))

    # 6. HEAD: sound must be there within the first 0.10 s
    head = lv[:max(1, int(round(HEAD_IGNORE_S / PEAK_WINDOW_S)))]
    if head.max() < QUIET_DBFS:
        warnings.append(_find("HEAD", 0.0, HEAD_IGNORE_S,
                              f"no sound above {QUIET_DBFS:g} dBFS in the first {HEAD_IGNORE_S:g}s"))

    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "stats": {"seconds": round(dur, 3), "channels": ch, "rate": rate}}


def check_wav(path, voice_rest=(), silence_ok=()):
    rate, x = read_pcm16(path)
    return check_array(x, rate, voice_rest, silence_ok)


def fail_text(finding):
    return f"{finding['code']} at {finding['where']}: {finding['message']}"
