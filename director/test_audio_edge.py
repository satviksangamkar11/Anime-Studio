"""Tests for director.audio_edge.

Builds synthetic WAV data in memory or in tmp_path. Standard library only.
Imports the module by bare name.
"""

import math
import random
import struct
import sys
import wave
from array import array

import pytest

# Import the module by bare name as required by the spec.
sys.path.insert(0, "director")
import audio_edge  # noqa: E402


def _write_wav(path, samples, sample_rate=44100, samp_width=2, n_channels=1):
    """Write a 16-bit PCM WAV file from a list of floats in [-1, 1]."""
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(n_channels)
        wav.setsampwidth(samp_width)
        wav.setframerate(sample_rate)
        frames = b""
        for s in samples:
            s = max(-1.0, min(1.0, s))
            value = int(s * 32767)
            for _ in range(n_channels):
                frames += struct.pack("<h", value)
        wav.writeframes(frames)


def _write_wav_stereo(path, samples_left, samples_right, sample_rate=44100):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = b""
        for l, r in zip(samples_left, samples_right):
            frames += struct.pack("<h", int(max(-1.0, min(1.0, l)) * 32767))
            frames += struct.pack("<h", int(max(-1.0, min(1.0, r)) * 32767))
        wav.writeframes(frames)


def _sine_burst(sample_rate, duration_s, freq=440.0, start_silence_s=0.0):
    n_start = int(round(sample_rate * start_silence_s))
    n_burst = int(round(sample_rate * duration_s))
    samples = [0.0] * n_start
    for i in range(n_burst):
        t = (n_start + i) / sample_rate
        samples.append(0.5 * math.sin(2.0 * math.pi * freq * t))
    return samples


def test_read_wav_mono_basic(tmp_path):
    samples = _sine_burst(44100, 0.1, 440.0)
    path = tmp_path / "tone.wav"
    _write_wav(path, samples, 44100)
    read, sr = audio_edge.read_wav_mono(path)
    assert sr == 44100
    assert len(read) == len(samples)
    for a, b in zip(read, samples):
        assert abs(a - b) < 1e-3


def test_read_wav_mono_stereo_averaged(tmp_path):
    left = [0.5, 0.5, 0.5, 0.5]
    right = [-0.5, -0.5, -0.5, -0.5]
    path = tmp_path / "stereo.wav"
    _write_wav_stereo(path, left, right, 8000)
    read, sr = audio_edge.read_wav_mono(path)
    assert sr == 8000
    assert len(read) == 4
    for s in read:
        assert abs(s - 0.0) < 1e-3


def test_read_wav_mono_8bit_raises(tmp_path):
    path = tmp_path / "eight.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(1)
        wav.setframerate(8000)
        wav.writeframes(bytes([128] * 100))
    with pytest.raises(ValueError):
        audio_edge.read_wav_mono(path)


def test_read_wav_mono_24bit_raises(tmp_path):
    path = tmp_path / "twentyfour.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(3)
        wav.setframerate(44100)
        wav.writeframes(b"\x00\x00\x40" * 100)
    with pytest.raises(ValueError):
        audio_edge.read_wav_mono(path)


def test_read_wav_mono_non_pcm_raises(tmp_path):
    path = tmp_path / "float.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\x00\x40" * 100)
    data = bytearray(path.read_bytes())
    data[20:22] = struct.pack("<H", 3)  # WAVE_FORMAT_IEEE_FLOAT, not PCM
    path.write_bytes(bytes(data))
    with pytest.raises(ValueError):
        audio_edge.read_wav_mono(path)


def test_read_wav_mono_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        audio_edge.read_wav_mono(tmp_path / "does_not_exist.wav")


def test_rms_empty():
    assert audio_edge.rms([]) == 0.0


def test_rms_constant():
    assert abs(audio_edge.rms([1.0, 1.0, 1.0]) - 1.0) < 1e-9


def test_voiced_threshold_silent():
    assert audio_edge.voiced_threshold([0.0, 0.0, 0.0], 44100) == 0.0


def test_edge_report_burst_at_sample0(tmp_path):
    samples = _sine_burst(44100, 0.2, 440.0, start_silence_s=0.0)
    report = audio_edge.edge_report(samples, 44100)
    assert report["starts_at_sample0"] is True
    assert report["start_abrupt"] is True


def test_edge_report_silent_raises():
    with pytest.raises(ValueError, match="no voiced audio"):
        audio_edge.edge_report([0.0] * 44100, 44100)


def test_edge_report_with_lead_and_tail(tmp_path):
    samples = _sine_burst(44100, 0.2, 440.0, start_silence_s=0.2)
    # Add 200 ms of silence after.
    samples += [0.0] * int(round(44100 * 0.2))
    report = audio_edge.edge_report(samples, 44100)
    assert report["clipped_tail"] is False
    assert report["starts_at_sample0"] is False
    assert report["lead_in_ms"] >= 190.0


def test_apply_edges_lead_in_and_first_sample(tmp_path):
    samples = _sine_burst(44100, 0.2, 440.0, start_silence_s=0.0)
    original = list(samples)
    result = audio_edge.apply_edges(samples, 44100)
    assert result is not samples  # new list
    assert samples == original  # not mutated
    assert result[0] == 0.0
    # Find first voiced frame.
    threshold = audio_edge.voiced_threshold(result, 44100)
    frame_size = int(round(44100 * 20 / 1000.0))
    first_voiced = None
    for start in range(0, len(result), frame_size):
        if audio_edge.rms(result[start : start + frame_size]) >= threshold:
            first_voiced = start
            break
    assert first_voiced is not None
    assert (first_voiced / 44100) * 1000.0 >= 80.0


def test_apply_edges_output_length_growth(tmp_path):
    # Corrected (supervisor, 2026-11-10, spec REFERENCE IMPLEMENTATION): padding is only the shortfall measured
    # on exact zero runs. The sine starts at exactly 0.0, so the first non-zero index is 1 and the front pad is
    # 3528 - 1 = 3527. The burst ends on a non-zero sample, so trailing zeros = 0 and the back pad is 2646.
    # Expected length: 8820 + 3527 + 2646 = 14993. (Was a fixed growth 8820 + 3528 + 2646.)
    samples = _sine_burst(44100, 0.2, 440.0, start_silence_s=0.0)
    result = audio_edge.apply_edges(samples, 44100)
    first_nonzero = next(i for i, v in enumerate(samples) if v != 0.0)
    last_nonzero = max(i for i, v in enumerate(samples) if v != 0.0)
    trailing_zeros = len(samples) - 1 - last_nonzero
    min_lead = int(math.ceil(80 / 1000.0 * 44100))
    min_tail = int(math.ceil(60 / 1000.0 * 44100))
    pad_front = max(0, min_lead - first_nonzero)
    pad_back = max(0, min_tail - trailing_zeros)
    assert (pad_front, pad_back) == (3527, 2646)
    assert len(result) == len(samples) + pad_front + pad_back == 14993


def test_apply_edges_idempotent(tmp_path):
    # Corrected (supervisor, 2026-11-10): exact equality dropped. Second call keeps the length and never
    # grows a sample in absolute value (the fades only scale by gains in [0, 1]).
    samples = _sine_burst(44100, 0.2, 440.0, start_silence_s=0.0)
    once = audio_edge.apply_edges(samples, 44100)
    twice = audio_edge.apply_edges(once, 44100)
    assert len(twice) == len(once)
    assert all(abs(t) <= abs(o) for t, o in zip(twice, once))


def test_apply_edges_no_unneeded_padding(tmp_path):
    samples = _sine_burst(44100, 0.2, 440.0, start_silence_s=0.2)
    samples += [0.0] * int(round(44100 * 0.2))
    result = audio_edge.apply_edges(samples, 44100)
    assert len(result) == len(samples)


def test_cut_margin_problems_start_too_close():
    problems = audio_edge.cut_margin_problems(0.15, 0.5, 0.1, 0.6, 0.10)
    assert "starts too close to the cut-in" in problems


def test_cut_margin_problems_start_exactly_margin():
    problems = audio_edge.cut_margin_problems(0.2, 0.5, 0.1, 0.6, 0.10)
    assert "starts too close to the cut-in" not in problems


def test_cut_margin_problems_end_too_close():
    problems = audio_edge.cut_margin_problems(0.2, 0.55, 0.1, 0.6, 0.10)
    assert "ends too close to the cut-out" in problems


def test_cut_margin_problems_end_before_start():
    problems = audio_edge.cut_margin_problems(0.5, 0.4, 0.1, 0.6, 0.10)
    assert "end before start" in problems


def test_cut_margin_problems_line_outside():
    problems = audio_edge.cut_margin_problems(0.05, 0.5, 0.1, 0.6, 0.10)
    assert "line outside [cut_in, cut_out]" in problems


def test_cut_margin_problems_no_issues():
    problems = audio_edge.cut_margin_problems(0.2, 0.4, 0.1, 0.6, 0.10)
    assert problems == []


def test_inspect_wav_needs_fix_false(tmp_path):
    # 200 ms silence before, 200 ms silence after, gentle 30 ms fades.
    sr = 44100
    pre = [0.0] * int(round(sr * 0.2))
    post = [0.0] * int(round(sr * 0.2))
    burst = []
    for i in range(int(round(sr * 0.2))):
        t = (len(pre) + i) / sr
        burst.append(0.5 * math.sin(2.0 * math.pi * 440.0 * t))
    # Gentle 30 ms fade in/out on the burst itself.
    fade = int(round(sr * 0.03))
    for i in range(fade):
        burst[i] *= i / fade
        burst[-(i + 1)] *= i / fade
    samples = pre + burst + post
    path = tmp_path / "clean.wav"
    _write_wav(path, samples, sr)
    info = audio_edge.inspect_wav(path)
    assert info["needs_fix"] is False


def test_apply_edges_never_clips():
    samples = [1.0] * 44100  # full scale
    result = audio_edge.apply_edges(samples, 44100)
    for s in result:
        assert -1.0 <= s <= 1.0


def test_apply_edges_returns_new_list_object():
    samples = [0.5] * 4410
    result = audio_edge.apply_edges(samples, 44100)
    assert result is not samples


def test_edge_report_fields_with_lead_and_tail_direct():
    sr = 44100
    tone = [0.5 if i % 2 == 0 else -0.5 for i in range(sr // 2)]
    samples = [0.0] * (sr // 5) + tone + [0.0] * (sr // 5)
    report = audio_edge.edge_report(samples, sr)
    assert set(report) == {
        "lead_in_ms",
        "tail_ms",
        "starts_at_sample0",
        "start_abrupt",
        "end_abrupt",
        "clipped_tail",
    }
    assert report["starts_at_sample0"] is False


def test_apply_edges_applies_linear_fades():
    # observer 5: the fades must really scale the samples (a no-op fade would fail here)
    # Corrected (supervisor, 2026-11-10, spec REFERENCE IMPLEMENTATION): gains are k/N, not k/(N-1), so the ramp
    # does not reach 1.0. Fade-in: N = 12, sample k multiplied by k/12 (k = 0..11), index 12 untouched.
    # Fade-out: N = 30 over indices 170..199, sample 199-k multiplied by k/30 (k = 0..29).
    out = audio_edge.apply_edges([0.5] * 200, 1000, min_lead_in_ms=0, min_tail_ms=0)
    assert out[0] == 0.0
    assert abs(out[1] - 0.5 * 1 / 12) < 1e-9
    assert abs(out[11] - 0.5 * 11 / 12) < 1e-9
    assert out[12] == 0.5
    assert out[169] == 0.5
    assert abs(out[170] - 0.5 * 29 / 30) < 1e-9
    assert abs(out[185] - 0.5 * 14 / 30) < 1e-9
    assert out[-1] == 0.0


def test_apply_edges_idempotent_with_subthreshold_head():
    # observer 7 (review_1_codex MED): a quiet, non-silent head and no padding needed on the first call.
    # Corrected (supervisor, 2026-11-10): exact equality dropped. Second call keeps the length and never
    # grows a sample in absolute value.
    samples = [0.001] * 100 + [0.5] * 300 + [0.0] * 100
    once = audio_edge.apply_edges(samples, 1000)
    twice = audio_edge.apply_edges(once, 1000)
    assert len(twice) == len(once)
    assert all(abs(t) <= abs(o) for t, o in zip(twice, once))


def test_second_call_guarantees_fixed_seed_random_signals():
    # Spec CORRECTION (supervisor, 2026-11-10) and CORRECTION 2: exact idempotence is dropped. Checked for
    # 60 fixed-seed signals (seed 12345, length 30..400, 0..10 zeros at each end, body uniform in [-0.9, 0.9]).
    # Guarantees, for x = input signal, y = once (first call), z = twice (second call):
    # (1) len(z) == len(y); (3) values of z in [-1, 1] and abs(z[i]) <= abs(y[i]) for every i;
    # (2, CORRECTION 2) NO CLICK as an ENVELOPE bound on the fade ramps of y, not a step limit:
    #   N_in  = round(12 / 1000 * 1000) = 12 fade-in samples, N_out = round(30 / 1000 * 1000) = 30 fade-out samples.
    #   f = first non-zero index of x, l = last non-zero index of x (body is uniform, so no body sample is 0.0).
    #   start_in = f + pad_front, end_out = l + pad_front (the input sits pad_front samples later in y).
    #   for j in 0..N_in-1:  abs(y[start_in + j]) <= abs(x[f + j]) * j / N_in + 1e-9, and y[start_in] == 0.0
    #   for j in 0..N_out-1: abs(y[end_out - j]) <= abs(x[l - j]) * j / N_out + 1e-9, and y[end_out] == 0.0
    #   Padding by hand (padding is measured on exact zero runs, CORRECTION 1):
    #     trailing zero run of x: z0 = n - 1 - l (0..10 here), so the tail rule (>= 60 zeros) gives
    #       pad_back = max(0, 60 - z0) = 60 - z0, between 50 and 60.
    #     the output length is n + pad_front + pad_back, so pad_front = len(y) - n - pad_back.
    #   Corrected: N is the effective length min(N, span); the ramp checks run only over that many samples, so
    #   x[f + j] and x[l - j] never leave the body (a negative index would wrap in Python).
    #   Constant-body edge: for x = [0.0625]*100 the bound gives an edge step <= 0.0625 / 30, so the constant
    #   voice click test (test_voice_end_has_no_click) still holds.
    rng = random.Random(12345)
    for index in range(60):
        n = rng.randint(30, 400)
        lead = rng.randint(0, 10)
        tail = rng.randint(0, 10)
        body = [rng.uniform(-0.9, 0.9) for _ in range(n - lead - tail)]
        signal = [0.0] * lead + body + [0.0] * tail
        once = audio_edge.apply_edges(signal, 1000)
        twice = audio_edge.apply_edges(once, 1000)
        assert len(twice) == len(once), f"signal {index}: second call changed the length"
        for i in range(len(once)):
            assert -1.0 <= twice[i] <= 1.0, f"signal {index}: value out of range at {i}"
            assert abs(twice[i]) <= abs(once[i]), f"signal {index}: sample {i} grew"

        f = next(i for i, s in enumerate(signal) if s != 0.0)
        l = max(i for i, s in enumerate(signal) if s != 0.0)
        z0 = n - 1 - l
        pad_back = max(0, 60 - z0)
        pad_front = len(once) - n - pad_back
        assert pad_front >= 0, f"signal {index}: negative front padding"
        start_in = f + pad_front
        end_out = l + pad_front
        # Corrected (supervisor, 2026-11-10, spec REFERENCE): the effective fade length is min(N, span) where
        # span = last_nonzero - first_nonzero + 1 of the signal (padding shifts both ends equally).
        # Reference skips a fade when its edge sample has abs <= 0.02; then no 0.0 end and no envelope apply.
        span = l - f + 1
        n_in = min(12, span)
        n_out = min(30, span)
        if abs(signal[f]) > 0.02:
            assert once[start_in] == 0.0, f"signal {index}: fade-in start is not 0.0"
            for j in range(n_in):
                bound = abs(signal[f + j]) * j / n_in + 1e-9
                assert abs(once[start_in + j]) <= bound, f"signal {index}: fade-in envelope at j={j}"
        if abs(signal[l]) > 0.02:
            assert once[end_out] == 0.0, f"signal {index}: fade-out end is not 0.0"
            for j in range(n_out):
                bound = abs(signal[l - j]) * j / n_out + 1e-9
                assert abs(once[end_out - j]) <= bound, f"signal {index}: fade-out envelope at j={j}"


def test_voice_end_has_no_click():
    # Hand check, sr 1000, defaults: 80 lead zeros + 100 voiced + 60 tail zeros = 240 samples.
    # Voice ends at index 179. Fade-out covers indices 150..179 with gain (29-k)/30 for k = 0..29:
    # index 149 = 0.0625, index 150 = 0.0625*29/30, each step is 0.0625/30 = 0.00208 <= 0.02,
    # index 179 = 0.0625*0/30 = 0.0.
    # The literal last 40 samples (200..239) are all zeros and test nothing, so the window is the last
    # 40 voiced samples (140..179) plus the first silent sample (180): out[140:181].
    # Step limit is 0.1 per the spec CORRECTION (was 0.02); the actual max step is 0.00208.
    out = audio_edge.apply_edges([0.0625] * 100, 1000)
    assert len(out) == 240
    assert out[179] == 0.0
    window = out[140:181]
    steps = [abs(window[i + 1] - window[i]) for i in range(len(window) - 1)]
    assert max(steps) <= 0.1


def test_hand_check_spec_example():
    # Hand check, x = [0.5] * 100, sr 1000: 80 lead zeros, 100 voiced, 60 tail zeros, length 240.
    # Fade-in over indices 80..91, gain k/12, so index 80 = 0.5*0/12 = 0.0.
    # Fade-out over indices 150..179, gain (29-k)/30, so index 179 = 0.0.
    out = audio_edge.apply_edges([0.5] * 100, 1000)
    assert len(out) == 240
    assert all(s == 0.0 for s in out[:80])
    assert out[80] == 0.0
    assert out[179] == 0.0
    assert all(s == 0.0 for s in out[180:])


def test_cut_margin_start_exact_margin_float_noise():
    # Hand check: 0.3 - 0.2 is 0.1 in decimal, but float gives 0.09999999999999998 (2e-17 below 0.10).
    # The spec tolerance of 1e-9 makes this exactly the margin, so there is no cut-in problem.
    problems = audio_edge.cut_margin_problems(0.3, 0.5, 0.2, 0.6, 0.10)
    assert "starts too close to the cut-in" not in problems


def test_starts_at_sample0_when_first_sample_nonzero():
    # Hand check, sr 1000: 100 samples of 0.5 then 200 zeros. Frames of 20 samples: frames 0..4 have
    # rms 0.5, frames 5..14 rms 0. Threshold = 0.5 * median(0.5) = 0.25. First voiced frame starts at
    # index 0, so lead_in_ms = 0 < 5 and starts_at_sample0 is True.
    samples = [0.5] * 100 + [0.0] * 200
    report = audio_edge.edge_report(samples, 1000)
    assert report["starts_at_sample0"] is True


def test_noise_floor_no_extra_pad():
    # Hand check, 44.1 kHz: 200 ms of 0.001 noise (below the -50 dB gate 0.0031623), then 200 ms of a
    # 0.8 tone at 440 Hz, then 100 ms of 0.001 noise. The tone is the first and last voiced sample, so
    # pad_front = max(0, 3528 - 8820) = 0 and pad_back = max(0, 2646 - 4410) = 0. Length stays 22050.
    # The old code treated the noise as voice (first index 0), added 3528 leading samples and grew.
    sr = 44100
    rng = random.Random(1)
    noise_a = [rng.uniform(-0.001, 0.001) for _ in range(8820)]
    tone = [0.8 * math.sin(2.0 * math.pi * 440.0 * i / sr) for i in range(8820)]
    noise_b = [rng.uniform(-0.001, 0.001) for _ in range(4410)]
    samples = noise_a + tone + noise_b
    out = audio_edge.apply_edges(samples, sr)
    assert len(samples) == 22050
    assert len(out) == 22050


def test_loud_onset_on_quiet_sample_faded():
    # Hand check, 44.1 kHz, amplitude 0.2 sine with phase 0. Sample 0 is exactly 0.0, sample 1 is
    # 0.2 * sin(2*pi*440/44100) = 0.01252, which is <= 0.02, so the old fade test skipped the fade.
    # First voiced index = 1, so pad_front = 3528 - 1 = 3527 and the onset lands at index 3528.
    # The fade-in is applied (rms of the 12 ms window is about 0.14, above the voiced threshold).
    sr = 44100
    x = [0.2 * math.sin(2.0 * math.pi * 440.0 * i / sr) for i in range(8820)]
    y = audio_edge.apply_edges(x, sr)
    f = 3528
    assert y[f] == 0.0
    n_in = int(round(12 / 1000.0 * sr))
    assert audio_edge.rms(y[f : f + n_in]) < audio_edge.rms(x[1 : 1 + n_in])


def test_second_call_same_length():
    # Same signal as test_noise_floor_no_extra_pad. The second call must keep the length.
    sr = 44100
    rng = random.Random(1)
    noise_a = [rng.uniform(-0.001, 0.001) for _ in range(8820)]
    tone = [0.8 * math.sin(2.0 * math.pi * 440.0 * i / sr) for i in range(8820)]
    noise_b = [rng.uniform(-0.001, 0.001) for _ in range(4410)]
    once = audio_edge.apply_edges(noise_a + tone + noise_b, sr)
    twice = audio_edge.apply_edges(once, sr)
    assert len(twice) == len(once) == 22050


def test_write_read_roundtrip(tmp_path):
    # Values in [-0.5, 0.5]: the write error (rounding, then reading back with the 1/32768 scale)
    # is at most 1/32767 for these values. Full-scale values can exceed that bound (see report).
    rng = random.Random(7)
    samples = [rng.uniform(-0.5, 0.5) for _ in range(1000)]
    path = tmp_path / "roundtrip.wav"
    audio_edge.write_wav_mono(path, samples, 44100)
    back, sr = audio_edge.read_wav_mono(path)
    assert sr == 44100
    assert len(back) == len(samples)
    assert max(abs(a - b) for a, b in zip(samples, back)) <= 1.0 / 32767


def test_fix_wav_refuses_same_path(tmp_path):
    path = tmp_path / "same.wav"
    _write_wav(path, _sine_burst(44100, 0.1, 440.0), 44100)
    with pytest.raises(ValueError):
        audio_edge.fix_wav(path, path)
