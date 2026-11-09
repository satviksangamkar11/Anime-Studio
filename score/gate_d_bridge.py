"""Score stage S4 bridge: check the finished score stem and hand it to Gate D as its one BGM track.

Reads h3/gate_d_audio.py and never edits it. Calls ffmpeg/ffprobe from PATH (subprocess) and numpy. No network,
no model call, never touches Ableton. Bad input is reported, never raised.

Reports match the other validators: {"ok", "errors": [{"code", "where", "message"}], "warnings": [...], "stats": {...}}.

CLI: python -m score.gate_d_bridge --cue-sheet C --stem S --voice V --out-manifest M [--bpm 128]
Exit codes: 0 = every check passed and the manifest was written; 1 = a check failed (report printed, no manifest);
2 = bad usage, unreadable cue sheet, or loudness could not be measured.

Codes: STEM_UNREADABLE, STEM_FORMAT, STEM_LENGTH, STEM_SILENT, STEM_BASS_NOT_MONO, STEM_MONO_LOSS, STEM_CUE_INVALID,
STEM_LOUDNESS (CLI only). Presence codes come from h3.gate_d_audio.check_music_presence.

Decisions (the stricter reading where the checklist is open):
- Stem format: WAV only, PCM 24-bit (pcm_s24le) or 32-bit float (pcm_f32le), 2 channels, 48000 Hz. 16-bit, mono,
  other rates, mp3 and any other container are STEM_FORMAT.
- Length: |stem samples - cue total_samples| must be <= 2000 (one 24 fps frame at 48 kHz). Beyond that is STEM_LENGTH.
- Bass mono: side (L-R) energy below 200 Hz must be <= -20 dB under mid (L+R) energy below 200 Hz, measured over the
  whole file with a brick-wall FFT split at 200 Hz. A stem with no bass at all passes.
- Mono fold: 10*log10(stereo power / folded-mono power) over the whole file must be <= 3 dB. Phase-cancelled
  content (folded power 0) is an infinite loss and fails.
- Silent stem (every sample zero) is STEM_SILENT. The checklist does not name it; a silent score is never valid.
- Presence levels are measured on the raw stem and the raw voice (before Gate D's ducking), 0.5 s RMS windows, in
  dBFS with a -120 dB floor so silence stays finite and shows up as BGM_SILENT_FLOOR.
- Presence uses the one voice file the caller passes (the reel's voice mix, not one language's cut).
- Loudness: integrated LUFS from ffmpeg `-af ebur128` (summary line parsed by h3.gate_d_audio.parse_loudness_text).
- write_bgm_manifest writes the manifest only when check_score_stem passes, so a bad stem can never reach Gate D.
  It re-runs the stem check itself, so it does not trust the caller. The manifest path is stored absolute.
- BPM: the score has no single tempo, so the CLI default is 128 (the BUILD tempo the score-reel skill uses) and the
  manifest value is informational only. Pass --bpm to change it.
- track_id defaults to "kp-r1-score" (the reel the checklist names); pass track_id to reuse the module for others.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

from h3 import gate_d_audio as gd

SAMPLE_RATE = 48000
LENGTH_TOLERANCE_SAMPLES = 2000          # one frame at 24 fps and 48 kHz
BASS_HZ = 200.0
BASS_SIDE_MAX_DB = -20.0                 # side below 200 Hz must sit 20 dB under mid
MONO_LOSS_MAX_DB = 3.0
ACCEPTED_CODECS = ("pcm_s24le", "pcm_f32le")
DEFAULT_TRACK_ID = "kp-r1-score"
DEFAULT_BPM = 128
WINDOW_S = 0.5
DB_FLOOR = -120.0
TIMEOUT_S = 900
_FAILS = (RuntimeError, OSError, ValueError, subprocess.SubprocessError, IndexError, TypeError)


def _err(code, where, message):
    return {"code": code, "where": where, "message": message}


def _report(errors, warnings=(), stats=None):
    return {"ok": not errors, "errors": list(errors), "warnings": list(warnings), "stats": dict(stats or {})}


def _probe(path):
    """(codec, sample_rate, channels, format_name) of the first audio stream. Raises on failure."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
           "stream=codec_name,sample_rate,channels:format=format_name", "-of", "json", str(path)]
    out = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_S)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace").strip() or "ffprobe failed")
    doc = json.loads(out.stdout.decode("utf-8"))
    streams = doc.get("streams") or []
    if not streams:
        raise RuntimeError("no audio stream")
    s = streams[0]
    return (str(s.get("codec_name")), int(s.get("sample_rate", 0) or 0), int(s.get("channels", 0) or 0),
            str((doc.get("format") or {}).get("format_name", "")))


def _decode(path):
    """(sample_rate, float64 array shape (n, 2)). Mono input is duplicated to 2 channels. Raises on failure."""
    rate = _probe(path)[1]
    cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "f32le",
           "-acodec", "pcm_f32le", "-ac", "2", "-"]
    out = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_S)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace").strip() or "ffmpeg failed")
    arr = np.frombuffer(out.stdout, dtype="<f4")
    if arr.size % 2:
        raise RuntimeError("decoded sample count is not whole stereo frames")
    return rate, arr.reshape(-1, 2).astype(np.float64)


def _db(power):
    return 10.0 * math.log10(max(power, 10.0 ** (DB_FLOOR / 10.0)))


def _bass_side_db(stereo):
    """Side (L-R) energy below BASS_HZ relative to mid (L+R) energy below it, in dB. None when there is no bass."""
    left, right = stereo[:, 0], stereo[:, 1]
    n = left.shape[0]
    mid = np.fft.rfft((left + right) / 2.0)
    side = np.fft.rfft((left - right) / 2.0)
    freqs = np.fft.rfftfreq(n, d=1.0 / SAMPLE_RATE)
    low = freqs < BASS_HZ
    mid_p = float(np.sum(np.abs(mid[low]) ** 2))
    side_p = float(np.sum(np.abs(side[low]) ** 2))
    if mid_p <= 0.0:                      # GBR-2: side with zero mid is anti-phase bass, not "no bass"
        return None if side_p <= 0.0 else math.inf
    if side_p <= 0.0:
        return -math.inf
    return 10.0 * math.log10(side_p / mid_p)


def _mono_loss_db(stereo):
    """Loss in dB when the stem is folded to mono (power over the whole file). None when silent."""
    left, right = stereo[:, 0], stereo[:, 1]
    stereo_p = float(np.mean((left ** 2 + right ** 2) / 2.0))
    mono_p = float(np.mean(((left + right) / 2.0) ** 2))
    if stereo_p <= 0.0:
        return None
    if mono_p <= 0.0:
        return math.inf
    return 10.0 * math.log10(stereo_p / mono_p)


def check_score_stem(path, cue_sheet):
    """B1 + B2: format, length against the cue sheet, bass mono and mono fold loss. Never raises."""
    where = str(path)
    if not isinstance(cue_sheet, dict) or not isinstance(cue_sheet.get("total_samples"), int) \
            or isinstance(cue_sheet.get("total_samples"), bool) or cue_sheet["total_samples"] <= 0:
        return _report([_err("STEM_CUE_INVALID", "cue_sheet", "cue sheet needs an integer total_samples > 0")])
    total = cue_sheet["total_samples"]
    errors, stats = [], {"expected_samples": total}
    try:
        codec, rate, channels, fmt = _probe(path)
    except _FAILS as exc:
        return _report([_err("STEM_UNREADABLE", where, f"cannot probe stem: {exc}")])
    stats.update({"codec": codec, "sample_rate": rate, "channels": channels, "format": fmt})
    if codec not in ACCEPTED_CODECS or "wav" not in fmt.split(","):
        errors.append(_err("STEM_FORMAT", where, f"stem must be WAV pcm_s24le or pcm_f32le; got {fmt}/{codec}"))
    if rate != SAMPLE_RATE:
        errors.append(_err("STEM_FORMAT", where, f"sample rate {rate} Hz, need {SAMPLE_RATE}"))
    if channels != 2:
        errors.append(_err("STEM_FORMAT", where, f"{channels} channel(s), need stereo"))
    try:
        _, stereo = _decode(path)
    except _FAILS as exc:
        errors.append(_err("STEM_UNREADABLE", where, f"cannot decode stem: {exc}"))
        return _report(errors, stats=stats)
    n = stereo.shape[0]
    stats["samples"] = n
    if not np.all(np.isfinite(stereo)):   # GBR-1: NaN or inf in the decoded stem; nothing after this is meaningful
        errors.append(_err("STEM_NONFINITE", where, "stem contains NaN or inf samples"))
        return _report(errors, stats=stats)
    if abs(n - total) > LENGTH_TOLERANCE_SAMPLES:
        errors.append(_err("STEM_LENGTH", where, f"{n} samples, cue sheet says {total} (tolerance "
                                                 f"{LENGTH_TOLERANCE_SAMPLES})"))
    if n == 0 or not np.any(stereo):
        errors.append(_err("STEM_SILENT", where, "stem has no signal"))
        return _report(errors, stats=stats)
    side_db = _bass_side_db(stereo)
    stats["bass_side_db"] = None if side_db is None else round(side_db, 2)
    if side_db is not None and side_db > BASS_SIDE_MAX_DB:
        errors.append(_err("STEM_BASS_NOT_MONO", where, f"side below {BASS_HZ:g} Hz is {side_db:.1f} dB under mid, "
                                                        f"need <= {BASS_SIDE_MAX_DB:g} dB"))
    loss = _mono_loss_db(stereo)
    stats["mono_loss_db"] = None if loss is None else (None if math.isinf(loss) else round(loss, 2))
    if loss is not None and loss > MONO_LOSS_MAX_DB:
        errors.append(_err("STEM_MONO_LOSS", where, f"folded mono loses {loss:.1f} dB, need <= {MONO_LOSS_MAX_DB:g}"))
    return _report(errors, stats=stats)


def measure_lufs(path):
    """Integrated loudness (LUFS) from ffmpeg ebur128, or None when it cannot be measured. Never raises."""
    try:
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"]
        out = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_S)
        if out.returncode != 0:
            return None
        value = gd.parse_loudness_text(out.stderr.decode("utf-8", "replace"))["integrated_lufs"]
    except _FAILS:
        return None
    return value if value is not None and math.isfinite(value) else None


def presence_levels(voice_wav, stem_wav, win_s=WINDOW_S):
    """B5: per-window RMS levels in dBFS of the voice and the stem, as (voice_db, bgm_db) lists for
    gate_d_audio.check_music_presence. Both files are cut to the shorter length. Returns ([], []) when a file cannot
    be read or the rates differ, which check_music_presence then reports as BGM_PRESENCE_BAD_INPUT."""
    if not isinstance(win_s, (int, float)) or isinstance(win_s, bool) or not math.isfinite(win_s) or win_s <= 0:
        return [], []                     # GBR-4: NaN, inf, zero or negative window is bad input, never raised
    try:
        rate_v, voice = _decode(voice_wav)
        rate_s, stem = _decode(stem_wav)
    except _FAILS:
        return [], []
    if rate_v != rate_s:
        return [], []
    win = int(round(win_s * rate_v))
    n = min(voice.shape[0], stem.shape[0]) // win if win > 0 else 0
    if n == 0:
        return [], []
    v_mono = voice[: n * win].mean(axis=1).reshape(n, win)
    s_mono = stem[: n * win].mean(axis=1).reshape(n, win)
    v_db = [_db(float(p)) for p in np.mean(v_mono ** 2, axis=1)]
    s_db = [_db(float(p)) for p in np.mean(s_mono ** 2, axis=1)]
    return v_db, s_db


def write_bgm_manifest(stem_path, cue_sheet, out_json, bpm, lufs, track_id=DEFAULT_TRACK_ID):
    """B4: write audio/bgm_manifest.json for Gate D, but only when check_score_stem passes. Returns the report.
    The manifest is validated with gate_d_audio.validate_bgm_manifest before it is written."""
    stem_report = check_score_stem(stem_path, cue_sheet)
    if not stem_report["ok"]:
        return _report(stem_report["errors"], stem_report["warnings"], stem_report["stats"])
    abs_path = str(Path(stem_path).resolve())
    doc = {"tracks": [{"track_id": track_id, "path": abs_path, "license_type": "original_score",
                       "bpm": bpm, "lufs": lufs}]}
    rep = gd.validate_bgm_manifest(doc)
    if not rep["ok"]:
        return rep
    try:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        return _report([_err("BGM_MANIFEST_UNREADABLE", str(out_json), f"cannot write manifest: {exc}")])
    return _report([], stats={"manifest": str(Path(out_json).resolve()), "track_id": track_id, "lufs": lufs})


def _print_report(rep, label):
    for e in rep["errors"]:
        print(f"ERROR {label} {e['code']} {e['where']}: {e['message']}")
    for w in rep["warnings"]:
        print(f"warn  {label} {w['code']} {w['where']}: {w['message']}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m score.gate_d_bridge",
                                description="Check the score stem against its cue sheet and write Gate D's BGM manifest.")
    p.add_argument("--cue-sheet", required=True, help="cue_sheet.json of the reel")
    p.add_argument("--stem", required=True, help="score stem .wav (48 kHz, 24-bit or float, stereo)")
    p.add_argument("--voice", required=True, help="voice mix .wav of the reel (presence reference)")
    p.add_argument("--out-manifest", required=True, help="audio/bgm_manifest.json to write when every check passes")
    p.add_argument("--bpm", type=float, default=DEFAULT_BPM, help="informational tempo for the manifest (default 128)")
    try:
        a = p.parse_args(argv)
    except SystemExit:
        return 2
    try:
        cue = json.loads(Path(a.cue_sheet).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {a.cue_sheet}: {exc}", file=sys.stderr)
        return 2
    stem_rep = check_score_stem(a.stem, cue)
    _print_report(stem_rep, "stem")
    voice_db, bgm_db = presence_levels(a.voice, a.stem)
    pres_rep = gd.check_music_presence(voice_db, bgm_db)
    _print_report(pres_rep, "presence")
    if not stem_rep["ok"] or not pres_rep["ok"]:
        print("FAIL: score not written to Gate D (fix the errors above, then rerun)")
        return 1
    lufs = measure_lufs(a.stem)
    if lufs is None:
        print(f"cannot measure loudness of {a.stem}", file=sys.stderr)
        return 2
    out = write_bgm_manifest(a.stem, cue, a.out_manifest, a.bpm, lufs)
    _print_report(out, "manifest")
    if not out["ok"]:
        print("FAIL: manifest not written")
        return 1
    print(f"OK: {a.out_manifest} written (lufs {lufs:.1f}, median presence "
          f"{pres_rep['stats']['median_under_voice_db']} dB under voice)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
