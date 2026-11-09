"""Offline tests for score/gate_d_bridge.py. Synthetic stems written with ffmpeg from numpy, no network, no model call.
Stems are 16 s (768000 samples) unless a test says otherwise; one test uses the real reel length (70 s)."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from h3 import gate_d_audio as gd
from score import gate_d_bridge as gb

RATE = 48000
REPO = Path(__file__).resolve().parents[2]


def _cue(seconds=16):
    n = int(seconds * RATE)
    return {"sample_rate": RATE, "total_samples": n, "total_s": float(seconds)}


def _tone(seconds, freq=440.0, amp=0.5):
    t = np.arange(int(round(seconds * RATE))) / RATE
    return amp * np.sin(2 * np.pi * freq * t)


def _stereo(left, right=None):
    right = left if right is None else right
    return np.stack([left, right], axis=1)


def _write(path, arr, codec="pcm_s24le", rate=RATE, channels=2):
    """Write float64 samples (n, ch) with ffmpeg through stdin. mp3 uses libmp3lame."""
    raw = np.ascontiguousarray(arr, dtype="<f4").tobytes()
    cmd = ["ffmpeg", "-y", "-hide_banner", "-v", "error", "-f", "f32le", "-ar", str(rate), "-ac", str(channels),
           "-i", "-", "-c:a", codec]
    if codec == "libmp3lame":
        cmd += ["-b:a", "192k"]
    cmd.append(str(path))
    subprocess.run(cmd, input=raw, check=True, capture_output=True)
    return str(path)


def _codes(rep):
    return sorted(e["code"] for e in rep["errors"])


def _good_stem(tmp_path, name="stem.wav", seconds=16):
    """Centred bass, bright mid tone: passes every B1-B2 check for a 16 s cue."""
    x = _tone(seconds, 440.0, 0.3) + _tone(seconds, 80.0, 0.2)
    return _write(tmp_path / name, _stereo(x))


# ---------------------------------------------------------------- B1 format and length

def test_good_stem_passes(tmp_path):
    rep = gb.check_score_stem(_good_stem(tmp_path), _cue())
    assert rep["ok"], rep["errors"]
    assert rep["stats"]["sample_rate"] == RATE and rep["stats"]["samples"] == 768000


def test_float_wav_is_accepted(tmp_path):
    p = _write(tmp_path / "f.wav", _stereo(_tone(16, 440, 0.3)), codec="pcm_f32le")
    assert gb.check_score_stem(p, _cue())["ok"]


def test_16_bit_wav_is_rejected(tmp_path):
    p = _write(tmp_path / "s16.wav", _stereo(_tone(16, 440, 0.3)), codec="pcm_s16le")
    assert _codes(gb.check_score_stem(p, _cue())) == ["STEM_FORMAT"]


def test_mp3_is_rejected_for_final(tmp_path):
    p = _write(tmp_path / "s.mp3", _stereo(_tone(16, 440, 0.3)), codec="libmp3lame")
    assert "STEM_FORMAT" in _codes(gb.check_score_stem(p, _cue()))


def test_wrong_sample_rate_is_rejected(tmp_path):
    p = _write(tmp_path / "r44.wav", _stereo(_tone(16, 440, 0.3)), rate=44100)
    assert "STEM_FORMAT" in _codes(gb.check_score_stem(p, _cue()))


def test_mono_stem_is_rejected(tmp_path):
    p = _write(tmp_path / "m.wav", _tone(16, 440, 0.3).reshape(-1, 1), channels=1)
    assert "STEM_FORMAT" in _codes(gb.check_score_stem(p, _cue()))


def test_length_exactly_one_frame_off_passes(tmp_path):
    n = 768000 + 2000
    p = _write(tmp_path / "long.wav", _stereo(_tone(n / RATE, 440, 0.3)))
    rep = gb.check_score_stem(p, _cue())
    assert "STEM_LENGTH" not in _codes(rep)


def test_length_two_frames_off_fails(tmp_path):
    p = _write(tmp_path / "short.wav", _stereo(_tone((768000 - 2400) / RATE, 440, 0.3)))
    assert _codes(gb.check_score_stem(p, _cue())) == ["STEM_LENGTH"]


def test_real_reel_length_70s_silent_only_fails_silence(tmp_path):
    """The real cue sheet length (70 s = 3,360,000 samples). Silence is reported, the length is not."""
    p = _write(tmp_path / "silent70.wav", np.zeros((3360000, 2)))
    rep = gb.check_score_stem(p, {"sample_rate": RATE, "total_samples": 3360000, "total_s": 70.0})
    assert _codes(rep) == ["STEM_SILENT"]
    assert rep["stats"]["samples"] == 3360000


def test_unreadable_file_is_reported_not_raised(tmp_path):
    bad = tmp_path / "junk.wav"
    bad.write_bytes(b"not audio at all")
    assert _codes(gb.check_score_stem(str(bad), _cue())) == ["STEM_UNREADABLE"]


def test_missing_file_is_reported_not_raised(tmp_path):
    assert _codes(gb.check_score_stem(str(tmp_path / "nope.wav"), _cue())) == ["STEM_UNREADABLE"]


def test_bad_cue_sheet_is_reported_not_raised(tmp_path):
    p = _good_stem(tmp_path)
    assert _codes(gb.check_score_stem(p, {"sample_rate": RATE})) == ["STEM_CUE_INVALID"]
    assert _codes(gb.check_score_stem(p, None)) == ["STEM_CUE_INVALID"]


def test_silent_stem_is_reported(tmp_path):
    p = _write(tmp_path / "z.wav", np.zeros((768000, 2)))
    assert _codes(gb.check_score_stem(p, _cue())) == ["STEM_SILENT"]


# ---------------------------------------------------------------- B2 bass mono and mono fold

def test_bass_out_of_phase_fails(tmp_path):
    x = _tone(16, 100.0, 0.3)
    p = _write(tmp_path / "wide.wav", _stereo(x, -x))
    assert "STEM_BASS_NOT_MONO" in _codes(gb.check_score_stem(p, _cue()))


def test_bass_centred_passes(tmp_path):
    p = _write(tmp_path / "mono_bass.wav", _stereo(_tone(16, 100.0, 0.3)))
    assert "STEM_BASS_NOT_MONO" not in _codes(gb.check_score_stem(p, _cue()))


def test_side_above_200hz_is_not_a_bass_error(tmp_path):
    x = _tone(16, 1000.0, 0.3)
    p = _write(tmp_path / "side_hi.wav", _stereo(x, -x))
    rep = gb.check_score_stem(p, _cue())
    assert "STEM_BASS_NOT_MONO" not in _codes(rep)
    assert "STEM_MONO_LOSS" in _codes(rep)           # the same stem still fails the fold check


def test_phase_cancelled_stem_fails_mono_loss(tmp_path):
    x = _tone(16, 1000.0, 0.3)
    p = _write(tmp_path / "cancel.wav", _stereo(x, -x))
    rep = gb.check_score_stem(p, _cue())
    assert "STEM_MONO_LOSS" in _codes(rep)
    # 24-bit rounding leaves a tiny residual after folding, so the loss is huge but finite (about 132 dB)
    assert rep["stats"]["mono_loss_db"] > 100


def test_uncorrelated_stereo_fails_mono_loss(tmp_path):
    rng = np.random.default_rng(1)
    p = _write(tmp_path / "uncorr.wav", rng.uniform(-0.3, 0.3, size=(768000, 2)))
    # independent channels fold to half the power: 3.01 dB, just over the 3 dB limit
    assert "STEM_MONO_LOSS" in _codes(gb.check_score_stem(p, _cue()))


def test_correlated_stereo_passes_mono_loss(tmp_path):
    p = _write(tmp_path / "corr.wav", _stereo(_tone(16, 440, 0.3)))
    assert "STEM_MONO_LOSS" not in _codes(gb.check_score_stem(p, _cue()))


# ---------------------------------------------------------------- B3 loudness

def test_measure_lufs_returns_finite_value(tmp_path):
    lufs = gb.measure_lufs(_good_stem(tmp_path))
    assert lufs is not None and -60 < lufs < 0


def test_measure_lufs_none_for_non_audio(tmp_path):
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"nope")
    assert gb.measure_lufs(str(junk)) is None


# ---------------------------------------------------------------- B5 presence

def _presence(tmp_path, stem_db_under):
    voice = _write(tmp_path / "voice.wav", _stereo(_tone(16, 300, 0.5)))
    amp = 0.5 * 10 ** (-stem_db_under / 20.0)
    stem = _write(tmp_path / "stem.wav", _stereo(_tone(16, 220, amp)))
    return gb.presence_levels(voice, stem)


def test_stem_18_db_under_voice_passes(tmp_path):
    v, b = _presence(tmp_path, 18.0)
    rep = gd.check_music_presence(v, b)
    assert rep["ok"], rep["errors"]
    assert rep["stats"]["median_under_voice_db"] == pytest.approx(18.0, abs=0.1)


def test_stem_5_db_under_voice_fails_median(tmp_path):
    v, b = _presence(tmp_path, 5.0)
    assert _codes(gd.check_music_presence(v, b)) == ["BGM_MEDIAN_OUT_OF_BAND"]


def test_silent_stem_fails_silent_floor(tmp_path):
    voice = _write(tmp_path / "voice.wav", _stereo(_tone(16, 300, 0.5)))
    stem = _write(tmp_path / "silent.wav", np.zeros((768000, 2)))
    v, b = gb.presence_levels(voice, stem)
    assert len(v) == len(b) == 32
    assert "BGM_SILENT_FLOOR" in _codes(gd.check_music_presence(v, b))


def test_presence_bad_file_gives_bad_input(tmp_path):
    voice = _write(tmp_path / "voice.wav", _stereo(_tone(4, 300, 0.5)))
    v, b = gb.presence_levels(voice, str(tmp_path / "missing.wav"))
    assert (v, b) == ([], [])
    assert _codes(gd.check_music_presence(v, b)) == ["BGM_PRESENCE_BAD_INPUT"]


# ---------------------------------------------------------------- B4 manifest and B6 Gate D

def test_manifest_is_accepted_by_gate_d(tmp_path):
    stem = _good_stem(tmp_path)
    out = tmp_path / "audio" / "bgm_manifest.json"
    rep = gb.write_bgm_manifest(stem, _cue(), out, bpm=128, lufs=-18.5)
    assert rep["ok"], rep["errors"]
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert len(doc["tracks"]) == 1
    t = doc["tracks"][0]
    assert t["track_id"] == "kp-r1-score" and t["license_type"] == "original_score"
    assert t["bpm"] == 128 and t["lufs"] == -18.5
    assert gd.validate_bgm_manifest(doc)["ok"]


def test_manifest_path_is_absolute_stem(tmp_path):
    stem = _good_stem(tmp_path)
    out = tmp_path / "m.json"
    gb.write_bgm_manifest(stem, _cue(), out, bpm=128, lufs=-18.5)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert Path(doc["tracks"][0]["path"]) == Path(stem).resolve()


def test_bad_stem_writes_no_manifest(tmp_path):
    stem = _good_stem(tmp_path, seconds=10)           # 10 s stem against a 16 s cue
    out = tmp_path / "m.json"
    rep = gb.write_bgm_manifest(stem, _cue(), out, bpm=128, lufs=-18.5)
    assert _codes(rep) == ["STEM_LENGTH"]
    assert not out.exists()


def test_invalid_bpm_is_refused(tmp_path):
    out = tmp_path / "m.json"
    rep = gb.write_bgm_manifest(_good_stem(tmp_path), _cue(), out, bpm=0, lufs=-18.5)
    assert "BGM_FIELD_INVALID" in _codes(rep) and not out.exists()


def test_gate_d_bgm_track_accepts_manifest_path(tmp_path):
    stem = _good_stem(tmp_path)
    out = tmp_path / "bgm_manifest.json"
    gb.write_bgm_manifest(stem, _cue(), out, bpm=128, lufs=-18.5)
    errors, path = gd._bgm_track(str(out))
    assert errors == []
    assert Path(path) == Path(stem).resolve()


# ---------------------------------------------------------------- review fixes GBR-1, GBR-2, GBR-4, GBR-5

def test_length_minus_two_frames_boundary_ok(tmp_path):
    p = _write(tmp_path / "m2000.wav", _stereo(_tone((768000 - 2000) / RATE, 440, 0.3)))
    assert "STEM_LENGTH" not in _codes(gb.check_score_stem(p, _cue()))


def test_length_plus_2001_fails(tmp_path):
    p = _write(tmp_path / "p2001.wav", _stereo(_tone((768000 + 2001) / RATE, 440, 0.3)))
    assert _codes(gb.check_score_stem(p, _cue())) == ["STEM_LENGTH"]


def test_length_minus_2001_fails(tmp_path):
    p = _write(tmp_path / "m2001.wav", _stereo(_tone((768000 - 2001) / RATE, 440, 0.3)))
    assert _codes(gb.check_score_stem(p, _cue())) == ["STEM_LENGTH"]


def test_nan_sample_is_nonfinite(tmp_path):
    x = _tone(16, 440, 0.3)
    x[1000] = np.nan
    p = _write(tmp_path / "nan.wav", _stereo(x), codec="pcm_f32le")
    assert _codes(gb.check_score_stem(p, _cue())) == ["STEM_NONFINITE"]


def test_inf_sample_is_nonfinite(tmp_path):
    x = _tone(16, 440, 0.3)
    x[5000] = np.inf
    p = _write(tmp_path / "inf.wav", _stereo(x), codec="pcm_f32le")
    assert _codes(gb.check_score_stem(p, _cue())) == ["STEM_NONFINITE"]


def test_exact_antiphase_bass_float_fails(tmp_path):
    x = _tone(16, 100.0, 0.3)
    p = _write(tmp_path / "anti_f32.wav", _stereo(x, -x), codec="pcm_f32le")
    rep = gb.check_score_stem(p, _cue())
    assert "STEM_BASS_NOT_MONO" in _codes(rep)
    assert rep["stats"]["bass_side_db"] == float("inf")


def test_bass_side_db_zero_mid_nonzero_side_is_inf():
    left = _tone(16, 100.0, 0.3)
    stereo = np.stack([left, -left], axis=1)
    assert gb._bass_side_db(stereo) == float("inf")


def test_bass_side_db_all_zero_is_none():
    assert gb._bass_side_db(np.zeros((RATE, 2))) is None


def test_presence_nan_window_returns_bad_input(tmp_path):
    voice = _write(tmp_path / "voice.wav", _stereo(_tone(4, 300, 0.5)))
    stem = _write(tmp_path / "stem.wav", _stereo(_tone(4, 220, 0.1)))
    assert gb.presence_levels(voice, stem, win_s=float("nan")) == ([], [])
    assert gb.presence_levels(voice, stem, win_s=float("inf")) == ([], [])


# ---------------------------------------------------------------- B7 CLI

def _cli(*args):
    return subprocess.run([sys.executable, "-m", "score.gate_d_bridge", *args], cwd=str(REPO),
                          capture_output=True, text=True, timeout=600)


def test_cli_exit_0_writes_manifest(tmp_path):
    # centred 220 Hz stem sitting 18 dB under a 300 Hz voice: every check passes
    voice = _write(tmp_path / "voice.wav", _stereo(_tone(16, 300, 0.5)))
    stem = _write(tmp_path / "stem.wav", _stereo(_tone(16, 220, 0.5 * 10 ** (-18.0 / 20.0))))
    cue = tmp_path / "cue.json"
    cue.write_text(json.dumps(_cue()), encoding="utf-8")
    out = tmp_path / "bgm.json"
    res = _cli("--cue-sheet", str(cue), "--stem", stem, "--voice", voice, "--out-manifest", str(out))
    assert res.returncode == 0, res.stdout + res.stderr
    assert gd.validate_bgm_manifest(json.loads(out.read_text(encoding="utf-8")))["ok"]


def test_cli_exit_1_on_failed_stem_and_no_manifest(tmp_path):
    stem = _write(tmp_path / "bad.wav", _stereo(_tone(16, 440, 0.3)), codec="pcm_s16le")
    voice = _write(tmp_path / "voice.wav", _stereo(_tone(16, 300, 0.5)))
    cue = tmp_path / "cue.json"
    cue.write_text(json.dumps(_cue()), encoding="utf-8")
    out = tmp_path / "bgm.json"
    res = _cli("--cue-sheet", str(cue), "--stem", stem, "--voice", voice, "--out-manifest", str(out))
    assert res.returncode == 1
    assert "STEM_FORMAT" in res.stdout and not out.exists()


def test_cli_exit_2_on_unreadable_cue_sheet(tmp_path):
    stem = _good_stem(tmp_path)
    res = _cli("--cue-sheet", str(tmp_path / "missing.json"), "--stem", stem, "--voice", stem,
               "--out-manifest", str(tmp_path / "m.json"))
    assert res.returncode == 2


def test_module_accepts_bad_argv_without_raising():
    assert gb.main(["--cue-sheet"]) == 2


def test_module_docstring_names_decisions():
    assert "Decisions" in gb.__doc__ and "STEM_FORMAT" in gb.__doc__
