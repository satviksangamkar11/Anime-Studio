"""Audio edge detection and repair for the GranthStudio pipeline.

Standard library only: wave, struct, math, array.
"""

import math
import os
import struct
import wave


def read_wav_mono(path):
    """Read a WAV file and return (samples, sample_rate).

    Supports 16-bit PCM mono and stereo (stereo is averaged).
    8-bit, 24-bit or non-PCM raise ValueError. Missing file raises
    FileNotFoundError.
    """
    try:
        with wave.open(str(path), "rb") as wav:
            n_channels = wav.getnchannels()
            samp_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            n_frames = wav.getnframes()
            comptype = wav.getcomptype()
            raw = wav.readframes(n_frames)
    except wave.Error as exc:
        raise ValueError(str(exc)) from exc

    if comptype != "NONE":
        raise ValueError("non-PCM WAV is not supported")

    if n_channels not in (1, 2):
        raise ValueError(f"unsupported channel count: {n_channels}")

    if samp_width == 2:
        fmt = "<" + str(n_channels * n_frames) + "h"
        values = struct.unpack(fmt, raw)
        scale = 1.0 / 32768.0
        samples = []
        for i in range(0, len(values), n_channels):
            frame = values[i : i + n_channels]
            samples.append(sum(frame) / len(frame) * scale)
        return samples, sample_rate

    if samp_width == 1:
        raise ValueError("8-bit PCM is not supported")

    if samp_width == 3:
        raise ValueError("24-bit PCM is not supported")

    raise ValueError(f"unsupported sample width: {samp_width}")


def rms(samples):
    """Root-mean-square of a list of samples (0.0 for empty)."""
    if not samples:
        return 0.0
    total = 0.0
    for s in samples:
        total += s * s
    return math.sqrt(total / len(samples))


def _median(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def voiced_threshold(samples, sr, frame_ms: int = 20) -> float:
    """0.5 x the median rms of frames whose rms is above 0.02 x the loudest
    frame rms. A silent signal returns 0.0."""
    if sr <= 0:
        return 0.0
    frame_size = max(1, int(round(sr * frame_ms / 1000.0)))
    if not samples:
        return 0.0

    frame_rms = []
    for start in range(0, len(samples), frame_size):
        frame = samples[start : start + frame_size]
        frame_rms.append(rms(frame))

    if not frame_rms:
        return 0.0

    loudest = max(frame_rms)
    if loudest == 0.0:
        return 0.0

    cutoff = 0.02 * loudest
    voiced = [r for r in frame_rms if r > cutoff]
    if not voiced:
        return 0.0

    return 0.5 * _median(voiced)


def edge_report(samples, sr, edge_ms: int = 40) -> dict:
    """Report on the leading and trailing edges of an audio signal."""
    if sr <= 0:
        raise ValueError("sample rate must be positive")

    threshold = voiced_threshold(samples, sr)
    if threshold == 0.0:
        raise ValueError("no voiced audio")

    frame_ms = 20
    frame_size = max(1, int(round(sr * frame_ms / 1000.0)))

    # Build the list of frame starts used by both forward and reverse scans.
    frame_starts = list(range(0, len(samples), frame_size))

    # First voiced frame (20 ms frame with rms >= threshold).
    first_voiced_index = None
    for start in frame_starts:
        frame = samples[start : start + frame_size]
        if rms(frame) >= threshold:
            first_voiced_index = start
            break

    # Last voiced frame: scan the same frame starts in reverse.
    last_voiced_index = None
    for start in reversed(frame_starts):
        frame = samples[start : start + frame_size]
        if rms(frame) >= threshold:
            last_voiced_index = start
            break

    if first_voiced_index is None or last_voiced_index is None:
        raise ValueError("no voiced audio")

    lead_in_ms = (first_voiced_index / sr) * 1000.0
    tail_end = min(last_voiced_index + frame_size, len(samples))
    tail_ms = ((len(samples) - tail_end) / sr) * 1000.0

    starts_at_sample0 = lead_in_ms < 5.0 or samples[0] != 0.0

    edge_size = max(1, int(round(sr * edge_ms / 1000.0)))
    start_edge = samples[:edge_size]
    end_edge = samples[len(samples) - edge_size :]

    # Median voiced rms: voiced_threshold = 0.5 * median_voiced_rms.
    median_voiced_rms = 2 * threshold

    start_abrupt = rms(start_edge) > 0.5 * median_voiced_rms
    end_abrupt = rms(end_edge) > 0.5 * median_voiced_rms

    clipped_tail = tail_ms < 20.0 and end_abrupt

    return {
        "lead_in_ms": lead_in_ms,
        "tail_ms": tail_ms,
        "starts_at_sample0": starts_at_sample0,
        "start_abrupt": start_abrupt,
        "end_abrupt": end_abrupt,
        "clipped_tail": clipped_tail,
    }


def _apply_edges_detail(
    samples,
    sr,
    fade_in_ms: int = 12,
    fade_out_ms: int = 30,
    min_lead_in_ms: int = 80,
    min_tail_ms: int = 60,
    noise_floor_db: float = -50.0,
):
    """Shared body of apply_edges. Returns (samples, info) where info holds
    pad_front, pad_back, faded_in and faded_out."""
    if sr <= 0:
        raise ValueError("sample rate must be positive")

    x = [float(v) for v in samples]
    gate = 10 ** (noise_floor_db / 20.0)
    idx = [i for i, v in enumerate(x) if abs(v) >= gate]
    if not idx:
        raise ValueError("no voiced audio")
    first, last = idx[0], idx[-1]

    need_lead = int(math.ceil(min_lead_in_ms / 1000.0 * sr))
    need_tail = int(math.ceil(min_tail_ms / 1000.0 * sr))
    pad_front = max(0, need_lead - first)
    pad_back = max(0, need_tail - (len(x) - 1 - last))

    y = [0.0] * pad_front + x + [0.0] * pad_back
    f = first + pad_front
    l = last + pad_front
    span = l - f + 1

    n_in = min(int(round(fade_in_ms / 1000.0 * sr)), span)
    n_out = min(int(round(fade_out_ms / 1000.0 * sr)), span)

    # Fade only when the voiced edge is loud enough (rms of the edge window vs the voiced threshold).
    thr = voiced_threshold(y, sr)
    do_in = n_in > 0 and rms(y[f : f + n_in]) >= thr
    do_out = n_out > 0 and rms(y[l - n_out + 1 : l + 1]) >= thr

    if do_in:
        for k in range(n_in):
            y[f + k] *= k / n_in

    if do_out:
        for k in range(n_out):
            y[l - k] *= k / n_out

    out = [max(-1.0, min(1.0, v)) for v in y]
    info = {"pad_front": pad_front, "pad_back": pad_back, "faded_in": do_in, "faded_out": do_out}
    return out, info


def apply_edges(
    samples,
    sr,
    fade_in_ms: int = 12,
    fade_out_ms: int = 30,
    min_lead_in_ms: int = 80,
    min_tail_ms: int = 60,
    noise_floor_db: float = -50.0,
) -> list:
    """Return a new list with padding and fades applied.

    Prepends zeros so the first voiced frame is at least min_lead_in_ms from
    the start, appends zeros so there are at least min_tail_ms after the last
    voiced frame, then applies a linear fade-in over the first fade_in_ms and
    a linear fade-out over the last fade_out_ms of the final signal. Never
    clips beyond [-1, 1]. The original list is not modified. Voiced edges are
    the first and last samples with abs >= 10 ** (noise_floor_db / 20), so
    sub-floor noise is not treated as voice and padding cannot move the gate.
    Pads only the shortfall measured against that gate; fades the voiced edges; keeps
    three guarantees: a second call returns the same length, the faded edge
    samples are exactly 0.0, and no value leaves [-1, 1] or grows on a
    second call.
    """
    out, _info = _apply_edges_detail(
        samples, sr, fade_in_ms, fade_out_ms, min_lead_in_ms, min_tail_ms, noise_floor_db
    )
    return out


def write_wav_mono(path, samples, sr):
    """Write mono 16-bit PCM. Each value is round(v * 32768), clamped to the int16 range [-32768, 32767].
    Written to a temp file next to path, then moved into place with os.replace."""
    frames = bytearray()
    for v in samples:
        k = max(-32768, min(32767, int(round(v * 32768.0))))
        frames += struct.pack("<h", k)
    tmp_path = str(path) + ".tmp"
    try:
        with wave.open(tmp_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sr)
            wav.writeframes(bytes(frames))
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    os.replace(tmp_path, str(path))


def fix_wav(src, dst):
    """Read src, apply edges (padding and fades), write mono 16-bit WAV to dst.

    Runs in voice_cast export BEFORE the lock measures the audio (O13), so the
    lock sees the repaired file. Refuses dst == src. Returns a dict with
    pad_front_ms, pad_back_ms, faded_in, faded_out, seconds_before, seconds_after.
    """
    if os.path.normcase(os.path.abspath(str(src))) == os.path.normcase(os.path.abspath(str(dst))):
        raise ValueError("dst must differ from src")
    samples, sr = read_wav_mono(src)
    out, info = _apply_edges_detail(samples, sr)
    write_wav_mono(dst, out, sr)
    return {
        "pad_front_ms": info["pad_front"] / sr * 1000.0,
        "pad_back_ms": info["pad_back"] / sr * 1000.0,
        "faded_in": info["faded_in"],
        "faded_out": info["faded_out"],
        "seconds_before": len(samples) / sr,
        "seconds_after": len(out) / sr,
    }


def cut_margin_problems(
    line_start_s: float,
    line_end_s: float,
    cut_in_s: float,
    cut_out_s: float,
    margin_s: float = 0.10,
) -> list:
    """Return a list of violation strings for line/cut margins."""
    problems = []

    if line_end_s < line_start_s:
        problems.append("end before start")

    if line_start_s < cut_in_s or line_end_s > cut_out_s:
        problems.append("line outside [cut_in, cut_out]")

    if line_start_s - cut_in_s < margin_s - 1e-9:
        problems.append("starts too close to the cut-in")

    if cut_out_s - line_end_s < margin_s - 1e-9:
        problems.append("ends too close to the cut-out")

    return problems


def inspect_wav(path) -> dict:
    """Read a WAV file, compute its edge report, and flag if it needs a fix."""
    samples, sr = read_wav_mono(path)
    report = edge_report(samples, sr)
    report["needs_fix"] = (
        report["starts_at_sample0"]
        or report["start_abrupt"]
        or report["end_abrupt"]
        or report["clipped_tail"]
    )
    return report
