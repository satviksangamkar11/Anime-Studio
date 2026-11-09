"""Measured musical key of an audio file (chroma + Krumhansl-Schmuckler profiles). Pure numpy + soundfile.

estimate_key(mono, sr) -> {"key": "D min", "confidence": float, "corr": float}
  confidence = best correlation minus the best correlation of any other key (0 = tie). Relative keys share all
  pitch classes, so a D minor / F major pair is decided by the tonic profile only; treat low confidence as unknown.
detect_file(path, max_s=30.0) -> same dict plus "seconds" (reads at most max_s seconds from the file start).
"""
import numpy as np
import soundfile as sf

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
FMIN, FMAX = 65.0, 2000.0
N_FFT, HOP = 8192, 4096


def _chroma(mono, sr):
    if len(mono) < N_FFT:
        mono = np.pad(mono, (0, N_FFT - len(mono)))
    win = np.hanning(N_FFT)
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / sr)
    band = (freqs >= FMIN) & (freqs <= FMAX)
    pcs = (np.round(12 * np.log2(freqs[band] / 440.0)).astype(int) + 9) % 12
    chroma = np.zeros(12)
    for start in range(0, len(mono) - N_FFT + 1, HOP):
        spec = np.abs(np.fft.rfft(mono[start:start + N_FFT] * win)) ** 2
        np.add.at(chroma, pcs, spec[band])
    total = chroma.sum()
    return chroma / total if total > 0 else chroma


def estimate_key(mono, sr):
    mono = np.asarray(mono, dtype=np.float64)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    if mono.size == 0 or not np.any(mono):
        return {"key": None, "confidence": 0.0, "corr": 0.0}
    c = _chroma(mono, sr)
    scores = []
    for tonic in range(12):
        for mode, prof in (("maj", MAJOR), ("min", MINOR)):
            r = np.corrcoef(c, np.roll(prof, tonic))[0, 1]
            scores.append((r if np.isfinite(r) else -1.0, f"{NAMES[tonic]} {mode}"))
    scores.sort(reverse=True)
    best, second = scores[0], scores[1]
    return {"key": best[1], "confidence": round(float(best[0] - second[0]), 4), "corr": round(float(best[0]), 4)}


def detect_file(path, max_s=30.0):
    info = sf.info(path)
    frames = min(int(info.frames), int(max_s * info.samplerate))
    data, sr = sf.read(path, frames=frames, dtype="float64", always_2d=True)
    out = estimate_key(data, sr)
    out["seconds"] = round(info.frames / float(info.samplerate), 4)
    return out
