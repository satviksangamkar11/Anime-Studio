"""Reel 1 mix v6: voice first, expected SFX kept under policy, bed lowered or muted, music, loudness.

Inputs (read only): the SFX stem (audio of final_reel1_v4 video), cue_sheet.json, sfx_study/sfx_study.json
(measured hit events), vo_tracks_report.json (per language shot voice), a music wav (already ducked).
Outputs: <pack>/score/ep1/mix_v6/ (report, json, PNG) and final_reel1_v6 export + phone mp4 files.

CLI: python -m score.reel_mixer --music <wav>   (run from anime_studio_merge)
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw
from scipy import signal

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva"
EP1 = PACK / "score" / "ep1"
CUE_SHEET = EP1 / "cue_sheet.json"
SFX_JSON = EP1 / "sfx_study" / "sfx_study.json"
MIX_DIR = EP1 / "mix_v6"
DEFAULT_MUSIC = EP1 / "sound" / "score_mix_v4.wav"
FLOW = Path("D:/aai work/flow_outputs/anime_kalika_puran_bhag1")
VO_REPORT = FLOW / "voices" / "pack_opus_high_20261108_v4_deva" / "vo_v4" / "vo_tracks_report.json"
V4 = FLOW / "final_reel1_v4"
STEM_MP4 = V4 / "kalika_reel1_video.mp4"
OUT_ROOT = FLOW / "final_reel1_v6"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
LANGS = ("en", "hi", "mr")
SR = 48000

# shots whose model bed is musical tones: bed muted, expected hit windows still kept
MUTE_BED_SHOTS = {"SHOT-004", "SHOT-006", "SHOT-008"}
RAMP_S = 0.030            # every gain change is smoothed over this window
HIT_PRE_S = 0.050         # an expected hit starts this long before its onset
HIT_MAX_S = 1.2           # longest kept hit
HIT_FADE_S = 0.150        # fade used when a hit tail is cut at HIT_MAX_S
HIT_DECAY_DB = 20.0       # hit ends where its 100 ms envelope has fallen this far below peak
HIT_LEVEL_OUT_DB = 6.0    # expected hit peak below voice peak, outside speech
HIT_LEVEL_IN_DB = 6.0     # expected hit peak capped this far under the voice RMS of its speech window (inside speech)
EXTRA_LEVEL_DB = 10.0     # extra hit kept (outside speech, near a cut) at this depth under voice peak
CUT_NEAR_S = 0.3          # an extra hit counts as a transition accent within this of a shot cut
HIT_MAX_BOOST_DB = 12.0   # a hit is raised toward its target by at most this much
BED_SPEECH_DB = 22.0      # bed RMS inside speech sits this far under the shot's voice RMS
BED_GAP_DB = 12.0         # bed RMS in gaps sits this far under the shot's voice RMS
BAND_DIP_DB = 6.0         # extra dip of the SFX 1-4 kHz band inside speech
BAND = (1000.0, 4000.0)
CLARITY_FULL_DB = 12.0    # voice above SFX+music in every speech window
CLARITY_BAND_DB = 15.0    # same, in 1-4 kHz
LAYER_CLOSE_DB = 10.0     # three layers within this span count as crowding
FRAME_S = 0.1
DUCK_FRAME_S = 0.05       # ducker measurement frame
DUCK_HOP_S = 0.01         # ducker frame hop
DUCK_LOOK_S = 0.03        # look-ahead: reduction starts this early
DUCK_ATTACK_S = 0.02      # reduction edge smoothing
DUCK_RELEASE_S = 0.25     # reduction release
DUCK_WIN_FLOOR_DB = 6.0   # a frame's voice reference is floored at the window voice RMS minus this (no pumping in pauses)
GAP_BUS_OFFSET_DB = 3.0   # gap frames over the voice average are pulled to the voice average minus this
_CORE_JSON = Path(__file__).resolve().parent.parent / "core" / "core.json"
LUFS_TARGET = json.loads(_CORE_JSON.read_text(encoding="utf-8"))["delivery"]["audio"]["lufs"]  # one target: core.json
TP_MAX = -1.5             # true-peak ceiling for loudnorm and the final limiter
LIMIT_START = 10 ** (-1.5 / 20)  # alimiter ceiling to start from


def db(p):
    return 10.0 * np.log10(np.maximum(p, 1e-12))


def lin(d):
    return 10.0 ** (d / 20.0)


def _s(t, sr=SR):
    return int(round(t * sr))


def inside(t, windows):
    return any(a <= t <= b for a, b in windows)


def clip_windows(windows, a, b):
    return [(max(x0, a), min(x1, b)) for x0, x1 in windows if x1 > a and x0 < b]


def segments(a, b, windows):
    """Split [a, b] (seconds) into runs (x0, x1, inside_speech)."""
    pts = sorted({a, b} | {x for w in windows for x in w if a < x < b})
    out = []
    for x0, x1 in zip(pts[:-1], pts[1:]):
        if x1 > x0:
            out.append((x0, x1, inside((x0 + x1) / 2, windows)))
    return out


def gaps(windows, total_s):
    return [(x0, x1) for x0, x1, ins in segments(0.0, total_s, windows) if not ins]


def rms_db(x):
    x = np.asarray(x, dtype=float)
    return float(db(np.mean(np.square(x)))) if x.size else -120.0


def speech_db(x, windows, sr=SR):
    parts = [x[_s(a, sr):_s(b, sr)] for a, b in windows]
    parts = [p for p in parts if p.size]
    if not parts:
        return None
    return rms_db(np.concatenate(parts))


def ramp_smooth(g, sr=SR):
    """Smooth any gain curve with a raised-cosine kernel of RAMP_S: no steps, no clicks."""
    n = int(round(RAMP_S * sr))
    k = np.hanning(n + 2)[1:-1]
    k = k / k.sum()
    return np.maximum(signal.fftconvolve(g, k, mode="same"), 0.0)


def band_filter(x, sr=SR):
    sos = signal.butter(4, BAND, btype="bandpass", fs=sr, output="sos")
    return signal.sosfiltfilt(sos, x, axis=0)


def rms_grid_db(x, sr=SR, win_s=0.1, hop_s=0.01):
    """100 ms RMS in dBFS on a 10 ms grid: index k is time k * 0.01 s."""
    n = len(x)
    w = int(round(sr * win_s))
    h = int(round(sr * hop_s))
    c = np.arange(0, n, h)
    lo = np.clip(c - w // 2, 0, n)
    hi = np.clip(c - w // 2 + w, 0, n)
    cs = np.concatenate([[0.0], np.cumsum(np.square(x))])
    return db((cs[hi] - cs[lo]) / np.maximum(hi - lo, 1))


def hit_window(env_db, t, total_n, sr=SR):
    """Keep window of a hit at onset t: from HIT_PRE_S before it to its decay (max HIT_MAX_S).

    Returns (a, b, fade_samples). fade_samples > 0 when the tail was longer than HIT_MAX_S.
    """
    k0 = int(round(t * 100))
    if k0 >= len(env_db):
        return None
    kp = k0 + int(np.argmax(env_db[k0:k0 + 10]))
    peak = env_db[kp]
    cap = k0 + int(round((HIT_MAX_S - HIT_PRE_S) * 100))  # whole kept window (pre-roll included) <= HIT_MAX_S
    k = kp
    while k < min(len(env_db), cap) and env_db[k] > peak - HIT_DECAY_DB:
        k += 1
    capped = k >= cap
    end_s = min(k, cap) / 100.0
    a = max(0, _s(t - HIT_PRE_S, sr))
    b = min(total_n, _s(end_s, sr))
    if b <= a:
        return None
    return a, b, (_s(HIT_FADE_S, sr) if capped else 0)


def sfx_gain(total_n, stem_mono, env_db, cue, events, speech, vo_mono, vo_peak_db, sr=SR):
    """Raw per-sample gain for the mono SFX stem (before ramps) plus one record per measured hit.

    Order: bed first, then extra hits (muted, or kept near a cut), then expected hits last so they win overlaps.
    """
    G = np.zeros(total_n)
    cuts = [float(c["at_s"]) for c in cue["cuts"]]
    avg_db = speech_db(vo_mono, speech, sr)
    for shot in cue["shots"]:
        if shot["id"] in MUTE_BED_SHOTS:
            continue
        s0, s1 = float(shot["start_s"]), float(shot["end_s"])
        shot_db = speech_db(vo_mono, clip_windows(speech, s0, s1), sr)
        if shot_db is None:
            shot_db = avg_db
        for x0, x1, ins in segments(s0, s1, speech):
            a, b = _s(x0, sr), min(total_n, _s(x1, sr))
            if b <= a:
                continue
            if shot_db is None:
                G[a:b] = 1.0
                continue
            bed = rms_db(stem_mono[a:b])
            target = shot_db - (BED_SPEECH_DB if ins else BED_GAP_DB)
            G[a:b] = lin(min(0.0, target - bed))

    def shot_of(t):
        for s in cue["shots"]:
            if s["start_s"] <= t < s["end_s"]:
                return s["id"]
        return None

    recs = []
    for ev in sorted(events, key=lambda e: bool(e["expected"])):
        t = float(ev["t"])
        win = hit_window(env_db, t, total_n, sr)
        if win is None:
            continue
        a, b, fade = win
        in_sp = inside(t, speech)
        rec = {"t": round(t, 3), "shot": shot_of(t), "expected": bool(ev["expected"]),
               "key": ev.get("matched_key"), "in_speech": in_sp, "a_s": round(a / sr, 3), "b_s": round(b / sr, 3)}
        cap = lin(HIT_MAX_BOOST_DB)
        if ev["expected"] and in_sp:
            w = next(x for x in speech if x[0] <= t <= x[1])
            target = rms_db(vo_mono[_s(w[0], sr):_s(w[1], sr)]) - HIT_LEVEL_IN_DB
            cap = 1.0  # inside speech the hit is only capped, never raised
        elif ev["expected"]:
            target = vo_peak_db - HIT_LEVEL_OUT_DB
        elif in_sp or not any(abs(t - c) <= CUT_NEAR_S for c in cuts):
            G[a:b] = 0.0
            recs.append({**rec, "kept": False, "gain_db": None, "reason": "extra hit muted"})
            continue
        else:
            target = vo_peak_db - EXTRA_LEVEL_DB
        peak = float(np.max(np.abs(stem_mono[a:b]))) if b > a else 0.0
        g = 0.0 if peak <= 0 else min(lin(target) / peak, cap)
        env = np.full(b - a, g)
        if fade > 0:
            env[-fade:] *= np.linspace(1.0, 0.0, fade)
        G[a:b] = env
        recs.append({**rec, "kept": g > 0, "gain_db": round(20 * np.log10(g), 2) if g > 0 else None,
                     "target_db": round(float(target), 2), "reason": "expected hit kept" if ev["expected"]
                     else "extra hit kept near cut"})
    return G, recs


def render_sfx(stem_st, band_st, G, speech, sr=SR):
    """Apply the smoothed gain map, and the extra 1-4 kHz dip inside speech."""
    mask = np.zeros(len(G))
    for a, b in speech:
        mask[_s(a, sr):_s(b, sr)] = 1.0
    dip = ramp_smooth(1.0 - (1.0 - lin(-BAND_DIP_DB)) * mask, sr)
    g = ramp_smooth(G, sr)
    return g[:, None] * stem_st - (g * (1.0 - dip))[:, None] * band_st


def _smooth_s(x, seconds, sr=SR):
    n = max(2, int(round(seconds * sr)))
    k = np.hanning(n + 2)[1:-1]
    return signal.fftconvolve(x, k / k.sum(), mode="same")


def duck_gains(voice, bus, speech, hit_windows, sr=SR):
    """Voice-priority ducker for the non-voice bus (processed SFX + music). Mono analysis arrays.

    Per 50 ms frame (10 ms hop, 30 ms look-ahead, 250 ms release, 20 ms edge smoothing): the bus is pulled
    down until the voice is >= CLARITY_FULL_DB above it in full band and >= CLARITY_BAND_DB above it in
    1-4 kHz. The same is done per speech window (window RMS) so the window check holds. In gaps, bus
    frames above the voice average are pulled to the voice average minus GAP_BUS_OFFSET_DB (outside kept
    expected hits). Reductions only: gains are <= 1. Returns (g_full, g_mid, stats); g_mid scales the
    1-4 kHz band on top of g_full (apply with apply_duck).
    """
    n = len(voice)
    hop = _s(DUCK_HOP_S, sr)
    fl = _s(DUCK_FRAME_S, sr)
    centers = np.arange(0, n, hop)
    lo = np.clip(centers - fl // 2, 0, n)
    hi = np.clip(centers - fl // 2 + fl, 0, n)

    def fdb(x):
        cs = np.concatenate([[0.0], np.cumsum(x * x)])
        return db((cs[hi] - cs[lo]) / np.maximum(hi - lo, 1))

    vb, bb = band_filter(voice, sr), band_filter(bus, sr)
    v_db, b_db = fdb(voice), fdb(bus)
    vm_db, bm_db = fdb(vb), fdb(bb)
    fc = centers / sr
    in_sp = np.array([inside(t, speech) for t in fc])
    in_hit = np.array([inside(t, hit_windows) for t in fc])
    avg_db = speech_db(voice, speech, sr)

    r_full = np.zeros(len(centers))
    r_mid = np.zeros(len(centers))
    # frame level, voice reference floored at its window RMS minus DUCK_WIN_FLOOR_DB
    for a, b in speech:
        m = (fc >= a) & (fc < b)
        vw = rms_db(voice[_s(a, sr):_s(b, sr)])
        vwm = rms_db(vb[_s(a, sr):_s(b, sr)])
        bw = rms_db(bus[_s(a, sr):_s(b, sr)])
        bwm = rms_db(bb[_s(a, sr):_s(b, sr)])
        r_full[m] = np.maximum(0.0, b_db[m] - (np.maximum(v_db[m], vw - DUCK_WIN_FLOOR_DB) - CLARITY_FULL_DB))
        r_mid[m] = np.maximum(0.0, bm_db[m] - (np.maximum(vm_db[m], vwm - DUCK_WIN_FLOOR_DB) - CLARITY_BAND_DB))
        # window level: the window check itself must hold
        r_full[m] = np.maximum(r_full[m], max(0.0, bw - (vw - CLARITY_FULL_DB)))
        r_mid[m] = np.maximum(r_mid[m], max(0.0, bwm - (vwm - CLARITY_BAND_DB)))
    # gap rule
    gap_m = (~in_sp) & (~in_hit)
    if avg_db is not None:
        r_full[gap_m] = np.maximum(r_full[gap_m], np.maximum(0.0, b_db[gap_m] - (avg_db - GAP_BUS_OFFSET_DB)))
    r_full_tot = r_full
    r_mid_tot = np.maximum(r_mid, r_full)
    extra = r_mid_tot - r_full_tot  # extra reduction of the 1-4 kHz band only

    look = max(1, _s(DUCK_LOOK_S, sr) // hop)
    decay = np.exp(-DUCK_HOP_S / DUCK_RELEASE_S)

    def hold(r):
        ahead = r.copy()
        for k in range(1, look + 1):
            ahead[:-k] = np.maximum(ahead[:-k], r[k:])  # max over the next look frames
        out = np.zeros_like(ahead)
        prev = 0.0
        for k in range(len(ahead)):
            prev = max(ahead[k], prev * decay)
            out[k] = prev
        return out

    R = np.interp(np.arange(n), centers, hold(r_full_tot))
    E = np.interp(np.arange(n), centers, hold(extra))
    R = _smooth_s(R, DUCK_ATTACK_S, sr)
    E = _smooth_s(E, DUCK_ATTACK_S, sr)
    g_full = lin(-np.maximum(R, 0.0))
    g_mid = lin(-np.maximum(E, 0.0))
    sp_mask = np.zeros(n, dtype=bool)
    for a, b in speech:
        sp_mask[_s(a, sr):_s(b, sr)] = True
    stats = {
        "mean_reduction_speech_db": round(float(np.mean(R[sp_mask])), 2) if sp_mask.any() else 0.0,
        "max_reduction_speech_db": round(float(np.max(R[sp_mask])), 2) if sp_mask.any() else 0.0,
        "mean_mid_extra_speech_db": round(float(np.mean(E[sp_mask])), 2) if sp_mask.any() else 0.0,
        "max_mid_extra_speech_db": round(float(np.max(E[sp_mask])), 2) if sp_mask.any() else 0.0,
        "max_reduction_db": round(float(np.max(R)), 2),
    }
    return g_full, g_mid, stats


def apply_duck(x_st, g_full, g_mid, sr=SR):
    """Scale a stereo layer: the whole layer by g_full, its 1-4 kHz band also by g_mid."""
    mid = band_filter(x_st, sr)
    return g_full[:, None] * (x_st - mid) + (g_full * g_mid)[:, None] * mid


def clarity(voice, sfx, music, speech, expected, vo_peak_db, total_s, sr=SR):
    """Speech-clarity and layering checks on mono analysis signals."""
    mix_sm = sfx + music
    vb, mb = band_filter(voice, sr), band_filter(mix_sm, sr)
    rows = []
    for a, b in speech:
        i, j = _s(a, sr), _s(b, sr)
        v = rms_db(voice[i:j])
        m = rms_db(mix_sm[i:j])
        vbd = rms_db(vb[i:j])
        mbd = rms_db(mb[i:j])
        rows.append({"start": round(a, 3), "end": round(b, 3), "full_margin_db": round(v - m, 2),
                     "band_margin_db": round(vbd - mbd, 2)})
    min_full = min(r["full_margin_db"] for r in rows)
    min_band = min(r["band_margin_db"] for r in rows)

    avg_voice = speech_db(voice, speech, sr)
    flen = int(round(FRAME_S * sr))
    gap_frames = gap_viol = 0
    gap_max_excess = -np.inf
    for x0, x1 in gaps(speech, total_s):
        for st in range(_s(x0, sr), _s(x1, sr) - flen + 1, flen):
            fr = (st, st + flen)
            gap_frames += 1
            m_db = rms_db(music[fr[0]:fr[1]])
            ex_m = m_db - avg_voice
            hit_here = any(a < fr[1] / sr and b > fr[0] / sr for a, b in expected)
            s_db = -120.0 if hit_here else rms_db(sfx[fr[0]:fr[1]])
            ex = max(s_db, m_db) - avg_voice
            gap_max_excess = max(gap_max_excess, ex, ex_m)
            if ex > 0 or ex_m > 0:
                gap_viol += 1
    hit_excess = -np.inf
    for a, b in expected:
        pk = float(np.max(np.abs(sfx[_s(a, sr):_s(b, sr)]))) if b > a else 0.0
        hit_excess = max(hit_excess, 20 * np.log10(max(pk, 1e-12)) - vo_peak_db)

    close_frames = close_viol = 0
    for a, b in speech:
        for st in range(_s(a, sr), _s(b, sr) - flen + 1, flen):
            fr = slice(st, st + flen)
            levels = [rms_db(voice[fr]), rms_db(sfx[fr]), rms_db(music[fr])]
            close_frames += 1
            if max(levels) - min(levels) <= LAYER_CLOSE_DB:
                close_viol += 1
    return {
        "speech_rows": rows,
        "min_full_margin_db": round(min_full, 2),
        "min_band_margin_db": round(min_band, 2),
        "clarity_full_ok": min_full >= CLARITY_FULL_DB,
        "clarity_band_ok": min_band >= CLARITY_BAND_DB,
        "voice_avg_db": round(avg_voice, 2),
        "gap_frames": gap_frames,
        "gap_violations": gap_viol,
        "gap_max_excess_db": round(float(gap_max_excess), 2),
        "hit_peak_max_over_voice_peak_db": round(float(hit_excess), 2),
        "close_frames": close_frames,
        "close_violations": close_viol,
    }


def decode_stereo(path, sr=SR):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "2", "-ar", str(sr),
                          "-f", "f32le", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4").astype(np.float64).reshape(-1, 2)


def fit(x, n):
    if x.shape[0] >= n:
        return x[:n]
    pad = np.zeros((n - x.shape[0],) + x.shape[1:])
    return np.concatenate([x, pad])


def load_voice(report, lang, total_n, shot_start, sr=SR):
    buf = np.zeros(total_n)
    for row in report:
        if row["lang"] != lang:
            continue
        x, fsr = sf.read(row["file"], dtype="float64")
        if x.ndim > 1:
            x = x.mean(axis=1)
        if fsr != sr:
            x = signal.resample_poly(x, sr, fsr)
        s = _s(shot_start[row["shot"]], sr)
        seg = x[: total_n - s]
        buf[s:s + len(seg)] += seg
    return buf


def loudness(path):
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af",
           f"loudnorm=I={LUFS_TARGET}:TP={TP_MAX}:LRA=11:print_format=json", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         check=True).stderr
    j = json.loads(err[err.rfind("{"): err.rfind("}") + 1])
    return {k: float(j[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}


def encode(video_src, wav, out, meas, abr, limit):
    af = (f"loudnorm=I={LUFS_TARGET}:TP={TP_MAX}:LRA=11:measured_I={meas['input_i']}:"
          f"measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:"
          f"measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true:print_format=summary"
          f",alimiter=limit={limit:.5f}:attack=5:release=50:level=disabled")
    cmd = [FFMPEG, "-hide_banner", "-y", "-i", str(video_src), "-i", str(wav), "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", abr, "-ar", "48000", "-ac", "2", "-shortest",
           "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)


def encode_limited(video_src, wav, out, meas, abr):
    """Encode, measure true peak, and iterate the limiter ceiling once if the peak is above TP_MAX."""
    limit = LIMIT_START
    encode(video_src, wav, out, meas, abr, limit)
    m = loudness(out)
    if m["input_tp"] > TP_MAX:
        limit *= 10 ** ((TP_MAX - m["input_tp"] - 0.1) / 20)
        encode(video_src, wav, out, meas, abr, limit)
        m = loudness(out)
    return limit, m


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True).stdout
    nb = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                         "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(path)],
                        capture_output=True, text=True, check=True).stdout
    return {"duration_s": round(float(out.strip()), 4), "video_frames": int(nb.strip())}


def draw_png(path, layers, cuts, total_s):
    W, H, LM, TM, BM = 1400, 420, 60, 30, 40
    canvas = Image.new("RGB", (W + LM + 120, H + TM + BM), (20, 20, 20))
    d = ImageDraw.Draw(canvas)

    def xt(t):
        return LM + t / total_s * W

    def yv(v):
        return TM + (1 - (np.clip(v, -90, 0) + 90) / 90) * H

    cols = [(255, 150, 60), (90, 200, 255), (140, 255, 140)]
    for i, (name, (t, v)) in enumerate(layers.items()):
        pts = [(xt(tt), yv(vv)) for tt, vv in zip(t, v)]
        d.line(pts, fill=cols[i], width=1)
        d.text((W + LM + 8, TM + 4 + 14 * i), name, fill=cols[i])
    for c in cuts:
        d.line([(xt(c), TM), (xt(c), TM + H)], fill=(110, 110, 110))
    for v in range(-90, 1, 10):
        d.text((4, yv(v) - 6), f"{v}", fill=(200, 200, 200))
    for sec in range(0, int(total_s) + 1, 5):
        d.text((xt(sec) - 6, TM + H + 8), f"{sec}s", fill=(200, 200, 200))
    d.text((LM, 6), "Kalika reel 1 v6 en mix: 100 ms level (dBFS): processed SFX, voice, music; grey = shot cuts",
           fill=(240, 240, 240))
    canvas.save(path)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", default=str(DEFAULT_MUSIC))
    args = ap.parse_args(argv)
    MIX_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("export", "phone"):
        (OUT_ROOT / sub).mkdir(parents=True, exist_ok=True)

    cue = json.loads(CUE_SHEET.read_text(encoding="utf-8"))
    sj = json.loads(SFX_JSON.read_text(encoding="utf-8"))
    events = [ev for s in sj["shots"] for ev in s["events"]]
    vo_report = json.loads(VO_REPORT.read_text(encoding="utf-8"))
    total_n = int(cue["total_samples"])
    total_s = total_n / SR
    shot_start = {s["id"]: s["start_s"] for s in cue["shots"]}

    stem_st = fit(decode_stereo(STEM_MP4), total_n)
    stem_mono = stem_st.mean(axis=1)
    env_db = rms_grid_db(stem_mono)
    band_st = band_filter(stem_st)
    music_st, msr = sf.read(args.music, dtype="float64")
    if music_st.ndim == 1:
        music_st = np.repeat(music_st[:, None], 2, axis=1)
    if msr != SR:
        music_st = signal.resample_poly(music_st, SR, msr, axis=0)
    music_st = fit(music_st, total_n)
    music_mono = music_st.mean(axis=1)

    results = {}
    for lang in LANGS:
        speech = [tuple(w) for w in cue["voice"]["per_language"][lang]]
        vo = load_voice(vo_report, lang, total_n, shot_start)
        vo_peak_db = float(20 * np.log10(np.max(np.abs(vo))))
        G, recs = sfx_gain(total_n, stem_mono, env_db, cue, events, speech, vo, vo_peak_db)
        sfx_st = render_sfx(stem_st, band_st, G, speech)
        kept = [(r["a_s"], r["b_s"]) for r in recs if r["expected"] and r["kept"]]
        bus_mono = (sfx_st + music_st).mean(axis=1)
        g_full, g_mid, dstats = duck_gains(vo, bus_mono, speech, kept)
        sfx_st = apply_duck(sfx_st, g_full, g_mid)
        music_d = apply_duck(music_st, g_full, g_mid)
        voice_st = np.repeat(vo[:, None], 2, axis=1)
        mix = voice_st + sfx_st + music_d
        wav = MIX_DIR / f"tmp_mix_{lang}.wav"
        sf.write(str(wav), mix.astype(np.float32), SR, subtype="FLOAT")
        chk = clarity(vo, sfx_st.mean(axis=1), music_d.mean(axis=1), speech, kept, vo_peak_db, total_s)
        chk["duck"] = dstats
        pre = loudness(wav)
        master = OUT_ROOT / "export" / f"kalika_reel1_{lang}.mp4"
        phone = OUT_ROOT / "phone" / f"kalika_reel1_{lang}_phone.mp4"
        m_limit, meas_final = encode_limited(V4 / "export" / f"kalika_reel1_{lang}.mp4", wav, master, pre, "192k")
        p_limit, meas_phone = encode_limited(V4 / "phone" / f"kalika_reel1_{lang}_phone.mp4", wav, phone, pre, "160k")
        results[lang] = {"checks": chk, "recs": recs, "pre_mix_lufs": pre["input_i"],
                         "pre_mix_tp": pre["input_tp"], "master_lufs": meas_final["input_i"],
                         "master_tp": meas_final["input_tp"], "master_lra": meas_final["input_lra"],
                         "limiter_master": m_limit, "limiter_phone": p_limit,
                         "phone_lufs": meas_phone["input_i"], "phone_tp": meas_phone["input_tp"],
                         "master_probe": probe(master), "phone_probe": probe(phone),
                         "master": str(master), "phone": str(phone)}
        if lang == "en":
            layers = {}
            for name, sig in (("processed SFX", sfx_st.mean(axis=1)), ("voice", vo), ("music", music_d.mean(axis=1))):
                t_db = rms_grid_db(sig, SR, 0.1, 0.1)
                layers[name] = (np.arange(len(t_db)) * 0.1, t_db)
            draw_png(MIX_DIR / "reel1_v6_en_sfx_voice_music.png", layers,
                     [c["at_s"] for c in cue["cuts"]], total_s)
        wav.unlink()

    (MIX_DIR / "mix_v6_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    print(json.dumps({k: {kk: v[kk] for kk in ("master_lufs", "master_tp", "phone_lufs", "phone_tp")}
                      | {"checks": {c: v["checks"][c] for c in ("min_full_margin_db", "min_band_margin_db",
                                                              "gap_violations", "close_violations")}}
                      for k, v in results.items()}, indent=1))


if __name__ == "__main__":
    main()
