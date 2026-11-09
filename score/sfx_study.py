"""SFX study for Kalika reel 1: measure the model sound stem per shot and propose KEEP / LOWER / MUTE.

Inputs are read only: the SFX stem (audio of the reel mp4), cue_sheet.json (shot timing, speech
union, expected sfx), shots.json (wanted sound text), the per-language voice tracks and the score mix.
Outputs go to <pack>/score/ep1/sfx_study/ (JSON, report, PNG pictures).

CLI: python -m score.sfx_study   (run from anime_studio_merge)
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw
from scipy import ndimage, signal

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva"
CUE_SHEET = PACK / "score" / "ep1" / "cue_sheet.json"
SHOTS = PACK / "shots.json"
MUSIC = PACK / "score" / "ep1" / "sound" / "score_mix_v4.wav"
OUT = PACK / "score" / "ep1" / "sfx_study"
REEL_MP4 = Path("D:/aai work/flow_outputs/anime_kalika_puran_bhag1/final_reel1_v4/kalika_reel1_video.mp4")
VO_REPORT = Path("D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva/vo_v4/vo_tracks_report.json")
FFMPEG_FALLBACK = Path("C:/Users/Satvik/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.1-full_build/bin/ffmpeg.exe")

SR = 48000
LANGS = ("en", "hi", "mr")
BAND_1_4K = (1000.0, 4000.0)
SPEECH_BAND = (300.0, 3400.0)
SYLLABLE_BAND = (2.0, 8.0)
ENV_REF_BAND = (0.5, 20.0)
# D minor pitch classes (C=0): in-key = D E F G A Bb C; out-of-key = C# D# F# G# B
D_MINOR_IN_KEY = (0, 2, 4, 5, 7, 9, 10)
D_MINOR_OUT_KEY = (1, 3, 6, 8, 11)
PC_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Decision thresholds. Change here; the report and JSON follow.
SPEECH_LIKE_MUTE = 0.6      # bed is mumbling/voice-like
MUSIC_LIKE_MUTE = 0.5       # bed holds tones most of the shot
CLASH_OUT_KEY_MUTE = 0.5    # tonal energy mostly outside D minor
CLASH_MIN_MUSIC_LIKE = 0.2  # clash only counts when tones are really there
NOISE_STD_DB = 2.5          # RMS curve std below this = steady
NOISE_FLATNESS = 0.3        # spectral flatness above this = noise-like
SAFE_BELOW_VOICE_DB = 20.0  # SFX inside speech should sit this far under the voice
EXPECT_TOL_S = 0.4          # hit within a cue window +- this = EXPECTED
MIN_HIT_ABOVE_BED_DB = 3.0  # onset must stand this far above its local bed


def db(power):
    return 10.0 * np.log10(np.maximum(power, 1e-12))


def decode_audio(path, sr=SR):
    """Decode any media file to mono float64 at sr through ffmpeg (no file written)."""
    exe = shutil.which("ffmpeg") or str(FFMPEG_FALLBACK)
    raw = subprocess.run(
        [exe, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def bandpass(x, sr, band, order=4):
    sos = signal.butter(order, band, btype="bandpass", fs=sr, output="sos")
    return signal.sosfiltfilt(sos, x)


def rms_curve_db(x, sr, win_s=0.1, hop_s=0.01):
    """Sliding RMS in dBFS over a 100 ms window. Returns (times_s, dbfs)."""
    n = len(x)
    w = int(round(sr * win_s))
    h = max(1, int(round(sr * hop_s)))
    centers = np.arange(0, n, h)
    lo = np.clip(centers - w // 2, 0, n)
    hi = np.clip(centers - w // 2 + w, 0, n)
    cs = np.concatenate([[0.0], np.cumsum(np.square(x))])
    ms = (cs[hi] - cs[lo]) / np.maximum(hi - lo, 1)
    return centers / sr, db(ms)


def stft_mag(x, sr, n_fft, hop):
    """Magnitude STFT, shape (frames, bins). Frame i starts at sample i*hop."""
    win = signal.get_window("hann", n_fft)
    n_frames = 1 + max(0, (len(x) - n_fft) // hop)
    if n_frames <= 0:
        return np.zeros((0, n_fft // 2 + 1)), np.fft.rfftfreq(n_fft, 1 / sr)
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
    mag = np.abs(np.fft.rfft(x[idx] * win, axis=1))
    return mag, np.fft.rfftfreq(n_fft, 1 / sr)


def spectral_flatness_median(x, sr):
    mag, _ = stft_mag(x, sr, 2048, max(1, sr // 100))
    p = mag ** 2 + 1e-18
    geo = np.exp(np.mean(np.log(p), axis=1))
    ari = np.mean(p, axis=1)
    return float(np.median(geo / ari))


def band_share(x, sr, band):
    mag, f = stft_mag(x, sr, 2048, 512)
    p = mag ** 2
    m = (f >= band[0]) & (f < band[1])
    return float(p[:, m].sum() / max(p.sum(), 1e-18))


def onset_times(x, sr, min_sep_s=0.12):
    """Spectral-flux peaks (10 ms hop, 512-point frames, linear magnitude, 80 Hz-12 kHz). Times in seconds.

    Short frames and linear magnitude were chosen because log-magnitude flux and 2048-point frames
    put the peak up to ~50 ms early on a click (measured on synthetic clicks).
    """
    n_fft = 512
    hop = max(1, sr // 100)
    mag, f = stft_mag(x, sr, n_fft, hop)
    if len(mag) < 3:
        return []
    band = (f >= 80) & (f <= 12000)
    flux = np.maximum(np.diff(mag[:, band], axis=0), 0).sum(axis=1)
    flux = np.concatenate([[0.0], flux])
    med = np.median(flux)
    sigma = 1.4826 * np.median(np.abs(flux - med)) + 1e-9
    thr = med + 4.0 * sigma
    k = max(1, int(round(0.05 * sr / hop)))
    local_max = flux == ndimage.maximum_filter1d(flux, size=2 * k + 1)
    cand = np.where(local_max & (flux > thr))[0]
    picked, last = [], -1e9
    for i in cand:
        t = (i * hop + n_fft // 2) / sr
        if t - last >= min_sep_s:
            picked.append(t)
            last = t
    return picked


def find_hits(x, sr, t0=0.0):
    """Onsets that stand MIN_HIT_ABOVE_BED_DB above their local bed. Times are t0 + offset."""
    t_rms, rms = rms_curve_db(x, sr)
    hits = []
    for t in onset_times(x, sr):
        m = (t_rms >= t - 0.05) & (t_rms <= t + 0.25)
        if not m.any():
            continue
        peak = float(rms[m].max())
        near = (t_rms >= t - 1.0) & (t_rms <= t + 1.0)
        bed = float(np.percentile(rms[near], 20)) if near.any() else peak
        above = peak - bed
        if above >= MIN_HIT_ABOVE_BED_DB:
            hits.append({"t": round(t0 + t, 3), "peak_dbfs": round(peak, 2), "above_bed_db": round(above, 2)})
    return hits


def modulation_ratio(x, sr, band=SPEECH_BAND, mod_band=SYLLABLE_BAND, ref_band=ENV_REF_BAND):
    """Share of the envelope's AC power at syllable rate (2-8 Hz) inside `band`, vs 0.5-20 Hz."""
    env = np.abs(bandpass(x, sr, band))
    dec = max(1, int(round(sr / 1000)))
    n = len(env) // dec
    e = env[: n * dec].reshape(n, dec).mean(axis=1)
    e = e - e.mean()
    f, pxx = signal.periodogram(e, fs=sr / dec, detrend=False)
    total = pxx[(f >= ref_band[0]) & (f < ref_band[1])].sum()
    syl = pxx[(f >= mod_band[0]) & (f < mod_band[1])].sum()
    return float(syl / max(total, 1e-30))


def speech_like_score(x, sr):
    return modulation_ratio(x, sr)


def _long_runs(mask, need):
    m = np.concatenate([[0], mask.astype(int), [0]])
    d = np.diff(m)
    out = np.zeros(len(mask), dtype=bool)
    for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
        if e - s >= need:
            out[s:e] = True
    return out


def tonal_summary(x, sr, min_hold_s=0.5):
    """Held tonal peaks (>= min_hold_s in one bin). music_like = share of frames holding a tone."""
    n_fft = 1 << int(round(math.log2(sr * 0.17)))
    hop = sr // 10
    mag, f = stft_mag(x, sr, n_fft, hop)
    empty = {"music_like": 0.0, "top_pitch_classes": [], "out_of_key_frac": 0.0}
    if len(mag) == 0:
        return empty
    s_db = 20 * np.log10(mag + 1e-9)
    band = (f >= 80) & (f <= 4000)
    sb, fb = s_db[:, band], f[band]
    med = np.median(sb, axis=1, keepdims=True)
    loc = (sb >= np.roll(sb, 1, axis=1)) & (sb >= np.roll(sb, -1, axis=1))
    loc[:, 0] = False
    loc[:, -1] = False
    peaks = loc & (sb > med + 15.0)
    need = int(math.ceil(min_hold_s / (hop / sr)))
    held = np.zeros_like(peaks)
    for j in range(peaks.shape[1]):
        if peaks[:, j].any():
            held[:, j] = _long_runs(peaks[:, j], need)
    music_like = float(held.any(axis=1).mean())
    if not held.any():
        return empty
    w = np.where(held, 10 ** (sb / 10), 0.0)
    midi = 69 + 12 * np.log2(fb / 440.0)
    pc = np.round(midi).astype(int) % 12
    hist = np.zeros(12)
    np.add.at(hist, pc, w.sum(axis=0))
    top = [PC_NAMES[i] for i in np.argsort(-hist)[:3] if hist[i] > 0]
    out_frac = float(hist[list(D_MINOR_OUT_KEY)].sum() / max(hist.sum(), 1e-30))
    return {"music_like": music_like, "top_pitch_classes": top, "out_of_key_frac": out_frac}


def window_samples(x, sr, windows, t0=0.0):
    """Concatenate the samples of x that fall inside windows (seconds on the x timeline, offset t0)."""
    parts = []
    for a, b in windows:
        i0 = max(0, int(round((a - t0) * sr)))
        i1 = min(len(x), int(round((b - t0) * sr)))
        if i1 > i0:
            parts.append(x[i0:i1])
    return np.concatenate(parts) if parts else np.zeros(0)


def level_db(x):
    return float(db(np.mean(np.square(x)))) if len(x) else None


def sfx_vs_voice_db(sfx, voice, sr, windows, t0=0.0):
    """SFX level minus voice level inside windows (dB). None when no window has samples."""
    s = window_samples(sfx, sr, windows, t0)
    v = window_samples(voice, sr, windows, t0)
    if len(s) == 0 or len(v) == 0:
        return None
    return float(db(np.mean(s ** 2)) - db(np.mean(v ** 2)))


def clip_windows(windows, a, b):
    return [(max(x0, a), min(x1, b)) for x0, x1 in windows if x1 > a and x0 < b]


def match_cues(hits, cues, tol=EXPECT_TOL_S, shot_range=None):
    """Mark each hit EXPECTED when it lies within a cue window (+-tol); a cue with no time matches any hit in the shot."""
    matched_cue = [False] * len(cues)
    out = []
    for h in hits:
        key = None
        for ci, c in enumerate(cues):
            if c.get("start") is None:
                if shot_range is not None and shot_range[0] <= h["t"] <= shot_range[1]:
                    key = c["key"]
                    matched_cue[ci] = True
                    break
                continue
            if c["start"] - tol <= h["t"] <= c["end"] + tol:
                key = c["key"]
                matched_cue[ci] = True
                break
        out.append({**h, "expected": key is not None, "matched_key": key})
    cue_rows = [{"key": c["key"], "start": c.get("start"), "end": c.get("end"), "matched": matched_cue[i]}
                for i, c in enumerate(cues)]
    return out, cue_rows


def inside_any(t, windows, tol=0.0):
    return any(a - tol <= t <= b + tol for a, b in windows)


def propose(st):
    """KEEP / LOWER / MUTE per sound part for one shot, from its measured stats."""
    parts = []
    speech = st["speech_windows"]
    en_sv = st["sfx_vs_voice_full_db"].get("en")
    bed_reason = None
    if st["speech_like"] >= SPEECH_LIKE_MUTE:
        bed_reason = ("MUTE", 0, f"bed is voice-like (speech_like {st['speech_like']:.2f} >= {SPEECH_LIKE_MUTE}): mumbling")
    elif st["music_like"] >= MUSIC_LIKE_MUTE or (
            st["out_of_key_frac"] >= CLASH_OUT_KEY_MUTE and st["music_like"] >= CLASH_MIN_MUSIC_LIKE):
        bed_reason = ("MUTE", 0, f"bed holds tones (music_like {st['music_like']:.2f}, "
                                 f"{st['out_of_key_frac']:.0%} out of D minor)")
    elif st["bed_std_db"] < NOISE_STD_DB and st["bed_flatness"] > NOISE_FLATNESS:
        bed_reason = ("MUTE", 0, f"constant noise bed (RMS std {st['bed_std_db']:.1f} dB, flatness {st['bed_flatness']:.2f})")
    elif en_sv is not None and en_sv > -SAFE_BELOW_VOICE_DB:
        n = int(math.ceil(en_sv + SAFE_BELOW_VOICE_DB))
        rel = (f"{en_sv:.1f} dB ABOVE voice" if en_sv > 0 else f"only {-en_sv:.1f} dB under voice")
        bed_reason = ("LOWER", n, f"SFX {rel} in speech (en); target {SAFE_BELOW_VOICE_DB:.0f} dB under")
    else:
        bed_reason = ("KEEP", 0, "bed is quiet enough under speech and not tonal or noisy")
    parts.append({"part": "bed (continuous ambience)", "decision": bed_reason[0], "lower_db": bed_reason[1],
                  "reason": bed_reason[2]})
    for c in st["cues"]:
        if c["matched"]:
            parts.append({"part": f"expected: {c['key']}", "decision": "KEEP", "lower_db": 0,
                          "reason": "a measured hit lies on this cue"})
        else:
            parts.append({"part": f"expected: {c['key']}", "decision": "NONE", "lower_db": 0,
                          "reason": "no hit measured for this cue; nothing to keep"})
    for e in st["events"]:
        if e["expected"]:
            continue
        if e["inside_speech"]:
            parts.append({"part": f"extra hit at {e['t']:.2f} s", "decision": "MUTE", "lower_db": 0,
                          "reason": f"extra hit under speech ({e['peak_dbfs']:.1f} dBFS)"})
        else:
            parts.append({"part": f"extra hit at {e['t']:.2f} s", "decision": "KEEP", "lower_db": 0,
                          "reason": "extra hit outside speech; no speech clash measured"})
    return parts


def load_voice_reel(report, lang, total_n, shot_start):
    """Place each shot's voice wav for one language on the reel timeline at its shot start."""
    buf = np.zeros(total_n)
    for row in report:
        if row["lang"] != lang:
            continue
        x, sr = sf.read(row["file"], dtype="float64")
        if x.ndim > 1:
            x = x.mean(axis=1)
        if sr != SR:
            x = signal.resample_poly(x, SR, sr)
        s = int(round(shot_start[row["shot"]] * SR))
        if s >= total_n:
            continue
        seg = x[: total_n - s]
        buf[s: s + len(seg)] += seg
    return buf


def analyse_shot(shot, cue_sfx, sound_text, stem, stem_band, voice, voice_band, union, per_lang):
    a, b = shot["start_s"], shot["end_s"]
    i0, i1 = int(round(a * SR)), int(round(b * SR))
    x = stem[i0:i1]
    xb = stem_band[i0:i1]
    t_rms, rms = rms_curve_db(x, SR)
    bed = float(np.percentile(rms, 20))
    hits = find_hits(x, SR, t0=a)
    shot_range = (a, b)
    cues = [{"key": c["key"], "start": c["start"], "end": c["end"]} for c in cue_sfx]
    events, cue_rows = match_cues(hits, cues, shot_range=shot_range)
    speech = clip_windows(union, a, b)
    for e in events:
        e["inside_speech"] = inside_any(e["t"], speech)
    tonal = tonal_summary(x, SR)
    sv_full, sv_band = {}, {}
    for lang in LANGS:
        # each language is compared inside its OWN speech windows (where that voice actually talks)
        own = clip_windows(per_lang[lang], a, b)
        sv_full[lang] = sfx_vs_voice_db(x, voice[lang][i0:i1], SR, own, t0=a)
        sv_band[lang] = sfx_vs_voice_db(xb, voice_band[lang][i0:i1], SR, own, t0=a)
    loudest = max((e["peak_dbfs"] for e in events), default=None)
    st = {
        "shot": shot["id"], "start_s": a, "end_s": b,
        "wanted_sound": sound_text,
        "bed_dbfs": round(bed, 2),
        "bed_std_db": round(float(np.std(rms)), 2),
        "bed_flatness": round(spectral_flatness_median(x, SR), 3),
        "hits_count": len(events),
        "loudest_hit_dbfs": loudest,
        "expected_cues": len(cues),
        "expected_matched": sum(1 for c in cue_rows if c["matched"]),
        "extra_hits": sum(1 for e in events if not e["expected"]),
        "speech_like": round(speech_like_score(x, SR), 3),
        "music_like": round(tonal["music_like"], 3),
        "top_pitch_classes": tonal["top_pitch_classes"],
        "out_of_key_frac": round(tonal["out_of_key_frac"], 3),
        "band_1_4k_share": round(band_share(x, SR, BAND_1_4K), 3),
        "speech_windows": [[round(p, 3), round(q, 3)] for p, q in speech],
        "speech_s": round(sum(q - p for p, q in speech), 3),
        "sfx_vs_voice_full_db": {k: (None if v is None else round(v, 2)) for k, v in sv_full.items()},
        "sfx_vs_voice_1_4k_db": {k: (None if v is None else round(v, 2)) for k, v in sv_band.items()},
        "events": [{**e, "t": round(e["t"], 3)} for e in events],
        "cues": cue_rows,
    }
    st["proposal"] = propose(st)
    return st


SPEC_STOPS = [(0.0, (0, 0, 0)), (0.35, (60, 0, 110)), (0.6, (200, 60, 60)), (0.8, (250, 180, 40)), (1.0, (255, 255, 220))]


def _colormap(v):
    xs = [s[0] for s in SPEC_STOPS]
    out = np.zeros(v.shape + (3,), dtype=np.uint8)
    for c in range(3):
        out[..., c] = np.interp(v, xs, [s[1][c] for s in SPEC_STOPS]).astype(np.uint8)
    return out


def shot_picture(path, x, t0, dur, st, n_fft=1024, hop=128):
    """Log-frequency spectrogram 50 Hz-8 kHz with speech shaded, onsets red, expected cues green."""
    mag, f = stft_mag(x, SR, n_fft, hop)
    s_db = db(mag ** 2)
    top_db = max(float(s_db.max()), -10.0) if s_db.size else 0.0
    norm = np.clip((s_db - (top_db - 90.0)) / 90.0, 0, 1)
    H, W = 420, 1000
    rows = 50.0 * (8000.0 / 50.0) ** (1 - np.arange(H) / (H - 1))
    bi = np.clip(np.searchsorted(f, rows), 0, len(f) - 1)
    frames = norm[:, bi].T  # (H, frames), row 0 = high frequency
    img = _colormap(frames)
    pic = Image.fromarray(img, "RGB").resize((W, H), Image.NEAREST)
    LM, TM, BM = 70, 40, 40
    canvas = Image.new("RGB", (W + LM + 20, H + TM + BM), (20, 20, 20))
    canvas.paste(pic, (LM, TM))
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)

    def xt(t):
        return LM + (t - t0) / dur * W

    for p, q in st["speech_windows"]:
        od.rectangle([xt(p), TM, xt(q), TM + H], fill=(255, 255, 255, 55))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(canvas)
    for fr in (100, 500, 1000, 2000, 4000, 8000):
        y = TM + (1 - (math.log(fr / 50) / math.log(8000 / 50))) * (H - 1)
        d.line([(LM - 6, y), (LM, y)], fill=(230, 230, 230))
        d.text((4, y - 6), f"{fr} Hz" if fr < 1000 else f"{fr // 1000} kHz", fill=(230, 230, 230))
    for e in st["events"]:
        x_ = xt(e["t"])
        d.line([(x_, TM), (x_, TM + H)], fill=(255, 60, 60) if not e["expected"] else (120, 255, 120), width=1)
    for c in st["cues"]:
        if c["start"] is not None:
            x_ = xt(c["start"])
            d.line([(x_, TM + H - 14), (x_, TM + H)], fill=(60, 220, 60), width=3)
    for sec in range(int(math.ceil(dur)) + 1):
        xs = xt(t0 + sec)
        d.text((xs - 6, TM + H + 8), f"{t0 + sec:.0f}s", fill=(230, 230, 230))
    title = (f"{st['shot']}  bed {st['bed_dbfs']} dBFS  hits {st['hits_count']}  speech_like {st['speech_like']}  "
             f"music_like {st['music_like']}  (red = extra hit, green = hit on a cue, shaded = speech)")
    d.text((LM, 10), title, fill=(240, 240, 240))
    canvas.save(path)


def reel_picture(path, sfx_db, voice_db, music_db, cuts, total_s):
    W, H, LM, TM, BM = 1400, 420, 60, 30, 40
    canvas = Image.new("RGB", (W + LM + 20, H + TM + BM), (20, 20, 20))
    d = ImageDraw.Draw(canvas)

    def xt(t):
        return LM + t / total_s * W

    def yv(v):
        return TM + (1 - (np.clip(v, -90, 0) + 90) / 90) * H

    for name, curve, col in (("SFX stem", sfx_db, (255, 150, 60)), ("voice (en)", voice_db, (90, 200, 255)),
                             ("music", music_db, (140, 255, 140))):
        t, v = curve
        pts = [(xt(tt), yv(vv)) for tt, vv in zip(t[::5], v[::5])]
        d.line(pts, fill=col, width=1)
        d.text((W + LM - 110, TM + 4 + 14 * list(("SFX stem", "voice (en)", "music")).index(name)),
               name, fill=col)
    for c in cuts:
        d.line([(xt(c), TM), (xt(c), TM + H)], fill=(110, 110, 110))
    for v in range(-90, 1, 10):
        y = yv(v)
        d.text((4, y - 6), f"{v}", fill=(200, 200, 200))
    for sec in range(0, int(total_s) + 1, 5):
        d.text((xt(sec) - 6, TM + H + 8), f"{sec}s", fill=(200, 200, 200))
    d.text((LM, 6), "Kalika reel 1: 100 ms loudness (dBFS) of SFX stem, en voice, music; grey = shot cuts",
           fill=(240, 240, 240))
    canvas.save(path)


def curve_db(x, sr):
    return rms_curve_db(x, sr)


def fmt(v, nd=1):
    return "-" if v is None else f"{v:.{nd}f}"


def write_markdown(path, stats, meta):
    lines = [
        "# SFX study, reel 1 (Kalika Puran bhag 1)",
        "",
        "Plain-English reading of the model sound stem (the SFX inside final_reel1_v4). Measured only, no listening.",
        "",
        f"Inputs: {meta['stem']} (decoded to 48 kHz mono), cue_sheet.json speech union, voice tracks en/hi/mr, shots.json.",
        "",
        "## Per-shot table",
        "",
        "| Shot | bed dBFS | hits (expected/extra) | loudest hit dBFS | speech-like | music-like | out of D minor | SFX-vs-voice in speech en full / 1-4 kHz (dB) | 1-4 kHz share |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in stats:
        lines.append(
            f"| {s['shot']} | {s['bed_dbfs']:.1f} | {s['hits_count']} ({s['hits_count'] - s['extra_hits']}/{s['extra_hits']}) | "
            f"{fmt(s['loudest_hit_dbfs'])} | {s['speech_like']:.2f} | {s['music_like']:.2f} | {s['out_of_key_frac']:.0%} | "
            f"{fmt(s['sfx_vs_voice_full_db'].get('en'))} / {fmt(s['sfx_vs_voice_1_4k_db'].get('en'))} | {s['band_1_4k_share']:.0%} |"
        )
    lines += ["", "Languages inside speech (SFX minus voice, full band, dB): " + "; ".join(
        f"{s['shot']} hi {fmt(s['sfx_vs_voice_full_db'].get('hi'))} mr {fmt(s['sfx_vs_voice_full_db'].get('mr'))}"
        for s in stats), ""]
    lines += ["## Proposal per shot", ""]
    for s in stats:
        lines.append(f"### {s['shot']}")
        lines.append(f"Wanted (shots.json): {s['wanted_sound']}")
        lines.append("")
        for p in s["proposal"]:
            tag = p["decision"] + (f" by {p['lower_db']} dB" if p["decision"] == "LOWER" else "")
            lines.append(f"- **{tag}**: {p['part']}. {p['reason']}")
        lines.append("")
    lines += ["## Could not measure", ""] + [f"- {x}" for x in meta["limits"]] + [""]
    lines += ["## Thresholds used", ""] + [f"- {k} = {v}" for k, v in meta["thresholds"].items()] + [""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cue = json.loads(CUE_SHEET.read_text(encoding="utf-8"))
    shots_src = json.loads(SHOTS.read_text(encoding="utf-8"))
    sound_text = {s["id"]: s.get("sound") for s in shots_src}
    vo_report = json.loads(VO_REPORT.read_text(encoding="utf-8"))

    stem = decode_audio(REEL_MP4)
    total_n = len(stem)
    stem_band = bandpass(stem, SR, BAND_1_4K)
    shot_start = {s["id"]: s["start_s"] for s in cue["shots"]}
    voice, voice_band = {}, {}
    for lang in LANGS:
        voice[lang] = load_voice_reel(vo_report, lang, total_n, shot_start)
        voice_band[lang] = bandpass(voice[lang], SR, BAND_1_4K)
    union = [tuple(w) for w in cue["voice"]["union"]]

    music, msr = sf.read(MUSIC, dtype="float64")
    if music.ndim > 1:
        music = music.mean(axis=1)
    if msr != SR:
        music = signal.resample_poly(music, SR, msr)
    music = music[:total_n]

    stats = []
    for shot in cue["shots"]:
        cue_sfx = shot.get("sfx", [])
        per_lang = {k: [tuple(w) for w in v] for k, v in cue["voice"]["per_language"].items()}
        st = analyse_shot(shot, cue_sfx, sound_text.get(shot["id"]), stem, stem_band, voice, voice_band, union,
                          per_lang)
        stats.append(st)
        sfx_seg = stem[int(round(shot["start_s"] * SR)): int(round(shot["end_s"] * SR))]
        shot_picture(OUT / f"{shot['id']}_spectrogram.png", sfx_seg, shot["start_s"],
                     shot["end_s"] - shot["start_s"], st)

    sfx_curve = curve_db(stem, SR)
    voice_curve = curve_db(voice["en"], SR)
    music_curve = curve_db(music, SR)
    reel_picture(OUT / "reel1_sfx_voice_music.png", sfx_curve, voice_curve, music_curve,
                 [c["at_s"] for c in cue["cuts"]], total_n / SR)

    meta = {
        "stem": str(REEL_MP4), "total_s": round(total_n / SR, 3),
        "thresholds": {"SPEECH_LIKE_MUTE": SPEECH_LIKE_MUTE, "MUSIC_LIKE_MUTE": MUSIC_LIKE_MUTE,
                       "CLASH_OUT_KEY_MUTE": CLASH_OUT_KEY_MUTE, "NOISE_STD_DB": NOISE_STD_DB,
                       "NOISE_FLATNESS": NOISE_FLATNESS, "SAFE_BELOW_VOICE_DB": SAFE_BELOW_VOICE_DB,
                       "EXPECT_TOL_S": EXPECT_TOL_S, "MIN_HIT_ABOVE_BED_DB": MIN_HIT_ABOVE_BED_DB},
        "limits": [
            "shots.json sfx_cues is null for every shot; the expected list used is cue_sheet.json shots[].sfx (reel seconds).",
            "The SFX stem is the mp4 audio (AAC 32 kHz stereo, decoded here to 48 kHz mono); tonal and speech scores are heuristics, not listening tests.",
            "Hits are spectral-flux peaks; a soft sound with no clear onset can be missed.",
            "Pitch classes come from held spectral peaks; inharmonic bells can show up as false pitch classes.",
            "Voice level is measured on the voice wav placed at each shot start, in the cue_sheet speech windows.",
        ],
    }
    report = {"meta": meta, "shots": stats}
    (OUT / "sfx_study.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    write_markdown(OUT / "SFX_STUDY_REEL1.md", stats, meta)
    for s in stats:
        print(f"{s['shot']} bed {s['bed_dbfs']:.1f} hits {s['hits_count']} exp {s['expected_matched']}/{s['expected_cues']} "
              f"speech {s['speech_like']:.2f} music {s['music_like']:.2f} sv_en {s['sfx_vs_voice_full_db'].get('en')}")


if __name__ == "__main__":
    main()
