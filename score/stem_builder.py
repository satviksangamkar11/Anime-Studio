"""Stem builder for the reel 1 score (SMP2). Pure helpers plus a CLI.

Reads sound/selection.json (chosen rank per slot), score_plan.json and cue_sheet.json. Builds
layer stems at 48 kHz on the reel clock (cue total_samples), each sample conformed with ffmpeg
rubberband to the section tempo and key, looped on whole bars, cut and faded on frame
boundaries, gated under voice.union, low-cut, sidechained, mono in the low end. Then the mix
is set to the musical level, and per-window gain riding puts the score 15-21.5 dB under the
voice in EVERY voice window (target midpoint -18.25 dB).

Writes: sound/stems/<layer>.wav, sound/work/voice_ref.wav, sound/score_mix_<v>.wav/.mp3,
sound/sample_log.json, and the '## Mix measurements' section of sound/SELECTION_BOARD.md.

CLI:
  python -m score.stem_builder [--version v2] [--preview]
    --preview also writes preview_reel1_en_small_<v>.mp4 (540 wide) and the loudness numbers.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt, sosfiltfilt

from score import sound_select as ss
from score import eq_plan as eq
from score.key_estimate import estimate_key

SR = ss.SR
FRAME = SR // 24  # 2000 samples per frame at 24 fps
SOUND = ss.SOUND_DIR
STEMS = os.path.join(SOUND, "stems")
WORK = os.path.join(SOUND, "work")
EXPORT_MP4 = "D:/aai work/flow_outputs/anime_kalika_puran_bhag1/final_reel1_v4/export/kalika_reel1_en.mp4"
STEM_LAYERS = ss.LAYERS + (ss.EXTRA_LAYER,)
DUCK_DB = -18.0           # busy and tonal layers under voice (rule 48: score 15-21.5 dB under voice)
LOW_DUCK_DB = -6.0        # bass and hits under voice: low band only, at this level
LOW_BAND_HZ = 250.0
LOW_CUT_HZ = 100.0
GROOVE_CUT_HZ = 40.0
FADE_S = 0.01
VOICE_TARGET_DB = -18.25  # midpoint of 15 to 21.5 dB under voice
RIDE_SMOOTH_S = 0.075     # gain riding ramps (50-100 ms)
RIDE_CLAMP_DB = (-18.0, 12.0)
DIP_HZ, DIP_DB, DIP_Q = 2500.0, -2.5, 0.9  # gentle 1-4 kHz dip on beds
SIDECHAIN_DEPTH = 0.25    # bass and pads drop up to 25 % in groove peaks
AUDIBLE_DB = -50.0        # a stem counts as audible in a section above this RMS
MEASURE_HEADING = ss.MEASURE_HEADING


# ---------------------------------------------------------------- pure helpers
def snap_frame(t):
    """Sample index of a time snapped to the 24 fps frame grid (cut points are exact samples)."""
    return int(round(t * 24)) * FRAME


def time_sample(t):
    return int(round(t * SR))


def fade_edges(x, n_fade):
    """Linear fade in and out of length n_fade on a (2, n) array, copy returned."""
    y = x.copy()
    n = y.shape[1]
    k = min(n_fade, n // 2)
    if k > 0:
        ramp = np.linspace(0.0, 1.0, k)
        y[:, :k] *= ramp
        y[:, n - k:] *= ramp[::-1]
    return y


def tile(sample, n, xf_s=0.02):
    """Repeat a (2, L) sample to n samples with a linear crossfade between repeats."""
    length = sample.shape[1]
    xf = min(int(xf_s * SR), length // 4)
    out = np.zeros((2, n))
    if length == 0 or n <= 0:
        return out
    step = length - xf
    ramp_in = np.linspace(0.0, 1.0, xf) if xf > 0 else np.zeros(0)
    seg = sample.copy()
    if xf > 0:
        seg[:, :xf] *= ramp_in
        seg[:, length - xf:] *= ramp_in[::-1]
    pos = 0
    while pos < n:
        end = min(n, pos + length)
        out[:, pos:end] += seg[:, :end - pos]
        pos += step
    return out


def place(target, sample, start, limit):
    """Add sample into target at start, cut at limit (exact sample) and cropped at 0."""
    total = target.shape[1]
    a = max(0, start)
    skip = a - start
    b = min(limit, total, start + sample.shape[1])
    if b <= a or skip >= sample.shape[1]:
        return 0
    target[:, a:b] += sample[:, skip:skip + (b - a)]
    return b - a


def loop_length(sample, tempo):
    """Cut a conformed loop to whole bars at the section tempo (bars = conformed length * tempo / 240)."""
    bars = max(1, round(sample.shape[1] * tempo / 240.0 / SR))
    n = int(round(bars * 240.0 / tempo * SR))
    return sample[:, :min(n, sample.shape[1])]


peaking_sos = eq.peaking_sos
GRID8_LP_HZ = 3500.0     # Indian perc groove (v4 rules): filtered low, under 3.5 kHz
GRID8_OFF_GAIN = 0.45    # off-beat eighths sit at about 45% of the downbeats


def process_layer(sample, layer, kind, chain=None):
    """Low-cut, low band and EQ rules applied to one conformed piece before it is placed.
    chain: the v5 EQ chain (eq_plan.chain_for). None = the v4 rules, kept so v4 can be rebuilt."""
    if chain is not None:
        return eq.apply_chain(sample, chain)
    if layer == "bass":
        return sample
    if layer == "hit" and kind in ("hit", "sting"):
        return sample
    if kind == "grid8":  # filtered low groove: low cut plus lowpass under GRID8_LP_HZ
        x = sosfilt(butter(4, GRID8_LP_HZ, btype="lowpass", fs=SR, output="sos"), sample, axis=1)
        return sosfilt(butter(2, LOW_CUT_HZ, btype="highpass", fs=SR, output="sos"), x, axis=1)
    cut = GROOVE_CUT_HZ if layer == "groove" else LOW_CUT_HZ
    x = sosfilt(butter(2, cut, btype="highpass", fs=SR, output="sos"), sample, axis=1)
    if layer == "bed":
        x = sosfilt(peaking_sos(DIP_HZ, DIP_DB, DIP_Q), x, axis=1)
    return x


def voice_mask(total, windows_s, ramp_s=0.01):
    """1.0 inside voice.union windows, linear ramps at each edge (length total)."""
    m = np.zeros(total)
    for a, b in windows_s:
        m[max(0, time_sample(a)):min(total, time_sample(b))] = 1.0
    r = max(1, int(ramp_s * SR))
    kernel = np.ones(r) / r
    return np.clip(fftconvolve(m, kernel, mode="same"), 0.0, 1.0)


def gate_layer(stem, layer, mask, dip=False):
    """Duck a layer under voice. Bass and hits keep only the low band under speech.
    dip: also a 1-4 kHz dip under voice (eq_plan.DYN_DIP) on the non-lead layers."""
    if layer in ("bass", "hit"):
        low = sosfiltfilt(butter(4, LOW_BAND_HZ, btype="lowpass", fs=SR, output="sos"), stem, axis=1)
        under = low * 10 ** (LOW_DUCK_DB / 20.0)
    else:
        leads = layer in ("indian_lead", "indian_lead2")
        src = sosfilt(eq.dyn_dip_sos(), stem, axis=1) if (dip and not leads) else stem
        under = src * 10 ** (DUCK_DB / 20.0)
    return stem * (1.0 - mask) + under * mask


def sidechain_gain(groove):
    """Gain curve from the kick/groove envelope: 1 at rest, 1 - SIDECHAIN_DEPTH on peaks."""
    env = np.abs(groove).max(axis=0)
    rel = np.exp(-1.0 / (0.08 * SR))
    out = np.empty_like(env)
    acc = 0.0
    for i, v in enumerate(env):  # one-pole release (80 ms), instant attack
        acc = v if v > acc else acc * rel
        out[i] = acc
    ref = np.percentile(out, 95) or 1.0
    return 1.0 - SIDECHAIN_DEPTH * np.clip(out / ref, 0.0, 1.0)


def rms_db(x):
    r = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    return 20.0 * math.log10(r) if r > 0 else -120.0


def window_levels(score_mix, voice_mono, windows_s):
    """Score and voice RMS over the voice windows (concatenated)."""
    sc, vc = [], []
    for a, b in windows_s:
        i, j = time_sample(a), min(time_sample(b), score_mix.shape[1])
        sc.append(score_mix[:, i:j].mean(axis=0))
        vc.append(voice_mono[i:j])
    sc = np.concatenate(sc) if sc else np.zeros(1)
    vc = np.concatenate(vc) if vc else np.zeros(1)
    return rms_db(sc), rms_db(vc)


def window_diffs(score_mean, voice_mono, windows_s):
    """Per voice window: score RMS minus voice RMS (dB). score_mean is the channel mean."""
    out = []
    for a, b in windows_s:
        i, j = time_sample(a), min(time_sample(b), score_mean.shape[0])
        out.append(rms_db(score_mean[i:j]) - rms_db(voice_mono[i:j]))
    return out


def gain_curve_db(total, windows_s, gains_db, smooth_s=RIDE_SMOOTH_S):
    """Per-sample gain in dB: each voice window gets its gain, 0 elsewhere, ramped over smooth_s."""
    g = np.zeros(total)
    for (a, b), gd in zip(windows_s, gains_db):
        g[max(0, time_sample(a)):min(total, time_sample(b))] = gd
    k = max(1, int(smooth_s * SR))
    return fftconvolve(g, np.ones(k) / k, mode="same")


def riding_gain_db(score_mean, voice_mono, windows_s, target_db=VOICE_TARGET_DB, iters=3,
                   clamp=RIDE_CLAMP_DB, smooth_s=RIDE_SMOOTH_S):
    """Per-window gains so every voice window sits at target_db. Returns (curve_db, gains, diffs_after)."""
    total = score_mean.shape[0]
    gains = np.zeros(len(windows_s))
    for _ in range(iters):
        curve = gain_curve_db(total, windows_s, gains, smooth_s)
        diffs = window_diffs(score_mean * 10 ** (curve / 20.0), voice_mono, windows_s)
        for k, d in enumerate(diffs):
            gains[k] = float(np.clip(gains[k] + (target_db - d), *clamp))
    curve = gain_curve_db(total, windows_s, gains, smooth_s)
    after = window_diffs(score_mean * 10 ** (curve / 20.0), voice_mono, windows_s)
    return curve, gains, after


def window_table(diffs):
    arr = np.array(diffs)
    return {"min": float(arr.min()), "median": float(np.median(arr)), "max": float(arr.max()),
            "inside_target_count": int(np.sum((arr <= -15.0) & (arr >= -21.5))), "windows": len(arr)}


def section_sanity(stems, sample_log, plan, total):
    """Per section: mix RMS and which placed layers are audible (stem RMS above AUDIBLE_DB)."""
    mix = sum(stems.values())
    mean = mix.mean(axis=0)
    rows = []
    n_sec = len(plan["sections"])
    for idx, sec in enumerate(plan["sections"]):
        a = snap_frame(sec["start_s"])
        b = total if idx == n_sec - 1 else snap_frame(sec["end_s"])
        layers = []
        for e in sample_log:
            if e["section"] != idx + 1:
                continue
            seg = stems[e["layer"]][:, a:b]
            level = rms_db(seg.mean(axis=0))
            indian = bool(ss.indian_sound(e))  # round 3: instrument word in path or name, not the pack
            layers.append({"layer": e["layer"], "file": e["file"], "rms_dbfs": round(level, 1),
                           "audible": level > AUDIBLE_DB, "kind": "Indian" if indian else "modern"})
        audible = [x for x in layers if x["audible"]]
        rows.append({"section": idx + 1, "act": sec["act"], "start_s": sec["start_s"], "end_s": sec["end_s"],
                     "mix_rms_dbfs": round(rms_db(mean[a:b]), 1),
                     "indian_audible": sum(1 for x in audible if x["kind"] == "Indian"),
                     "modern_audible": sum(1 for x in audible if x["kind"] == "modern"),
                     "layers": layers})
    return rows


# ---------------------------------------------------------------- ffmpeg
def ebur(path):
    """Integrated loudness (LUFS), loudness range and true peak from ffmpeg ebur128."""
    res = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    summary = res.stderr.split("Summary:")[-1]
    out = {}
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    out["integrated_lufs"] = float(m.group(1)) if m else None
    m = re.search(r"LRA:\s+(-?[\d.]+) LU", summary)
    out["lra_lu"] = float(m.group(1)) if m else None
    m = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    out["true_peak_dbfs"] = float(m.group(1)) if m else None
    return out


def extract_voice(mp4, out_wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-ac", "2", "-ar", str(SR), out_wav], check=True)


VO_SHOT_DIR = "D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva/vo_v4/en"
VOICE_ONLY_WAV = os.path.join(WORK, "voice_only_en.wav")


def build_voice_only(cue, out_path=VOICE_ONLY_WAV, shot_dir=VO_SHOT_DIR):
    """Voice-only reference: each shot's VO clip (44.1 kHz mono) resampled to 48 kHz and placed at its
    cue start. No model SFX. Returns rows (shot, start_s, clip_s, slot_s) for the report."""
    from scipy.signal import resample_poly
    total = int(cue["total_samples"])
    out = np.zeros(total)
    rows = []
    for shot in cue["shots"]:
        clip, sr_in = sf.read(os.path.join(shot_dir, shot["id"] + ".wav"), dtype="float64", always_2d=True)
        mono = clip.mean(axis=1)
        if sr_in != SR:
            mono = resample_poly(mono, SR, sr_in)
        slot_s = shot["end_s"] - shot["start_s"]
        if len(mono) / SR > slot_s + 1e-6:
            raise ValueError(f"{shot['id']} VO is {len(mono) / SR:.3f} s, slot is {slot_s:.3f} s")
        start = time_sample(shot["start_s"])
        n = min(len(mono), total - start)
        out[start:start + n] += mono[:n]
        rows.append((shot["id"], shot["start_s"], round(len(mono) / SR, 3), round(slot_s, 3)))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sf.write(out_path, np.stack([out, out], axis=1).astype(np.float32), SR, subtype="PCM_24")
    return rows


# ---------------------------------------------------------------- build
def _spans(sample_log, plan, layers, kinds, acts=None):
    """(a, b, bpm, section) in samples where the chosen entries of these layers play."""
    out = []
    for e in sample_log:
        if e["layer"] not in layers or e["kind"] not in kinds:
            continue
        if acts and plan["sections"][e["section"] - 1]["act"] not in acts:
            continue
        if e["kind"] == "window":
            a, b = time_sample(e["window_s"][0]), time_sample(e["window_s"][1])
        else:
            a, b = e["section_start_sample"], e["section_end_sample"]
        out.append((a, b, e["tempo_bpm"], e["section"]))
    return out


def _sc_row(sc_id, key, targets, sections, depth, attack, release, gr):
    active = gr[gr > 1e-6]
    return {"id": sc_id, "key": key, "targets": list(targets), "sections": sorted(set(sections)),
            "depth_db": depth, "attack_ms": attack, "release": release,
            "max_gr_db": round(float(gr.max()), 2) if gr.size else 0.0,
            "mean_gr_db": round(float(active.mean()), 2) if active.size else 0.0,
            "max_step_db": round(eq.max_step_db(gr), 4)}


def sidechain_stems(stems, plan, sample_log, total, perc_clash=()):
    """The v5 sidechains, measured on the written stems. Keys are read before any duck.
    kick -> bass (5 dB) and pads (3 dB) in BUILD/DROP; lead 1-4 kHz band -> bed and chords (2.5 dB);
    hit and war horn events -> every other layer (4.5 / 3 dB); perc vs groove on measured clash sections.
    Returns (stems, rows)."""
    rows = []
    keys = {k: v.mean(axis=0) for k, v in stems.items()}
    # kick -> bass and pads
    kspans = _spans(sample_log, plan, ("groove",), ("loop",), eq.KICK_ACTS)
    kick = sosfilt(butter(4, 150.0, btype="lowpass", fs=SR, output="sos"), keys["groove"])
    for spec in (eq.KICK_BASS, eq.KICK_PADS):
        gr = eq.duck_gr_db(kick, kspans, spec["depth_db"], spec["attack_ms"], release_beats=spec["release_beats"])
        for t in spec["targets"]:
            stems[t] = stems[t] * eq.gain_from_gr(gr)[None, :]
        rel = ", ".join(f"S{s} {spec['release_beats'] * 60000 / bpm:.0f} ms" for _, _, bpm, s in sorted(set(kspans), key=lambda x: x[3]))
        rows.append(_sc_row(spec["id"], "groove (kick, <150 Hz)", spec["targets"], [s for *_, s in kspans],
                            spec["depth_db"], spec["attack_ms"], f"{spec['release_beats']} beat: {rel}", gr))
    # lead 1-4 kHz -> bed and chords, only while the lead plays
    lspans = _spans(sample_log, plan, ("indian_lead", "indian_lead2"), ("bed", "window"))
    lead = keys["indian_lead"] + keys["indian_lead2"]
    lead_band = sosfilt(butter(4, [eq.LEAD_PADS["band"][0], eq.LEAD_PADS["band"][1]], btype="bandpass",
                               fs=SR, output="sos"), lead)
    spec = eq.LEAD_PADS
    gr = eq.duck_gr_db(lead_band, lspans, spec["depth_db"], spec["attack_ms"], release_ms=spec["release_ms"])
    for t in spec["targets"]:
        stems[t] = eq.band_duck(stems[t], gr, *spec["band"])
    rows.append(_sc_row(spec["id"], "indian_lead + indian_lead2 (1-4 kHz)", spec["targets"],
                        [s for *_, s in lspans], spec["depth_db"], spec["attack_ms"],
                        f"{spec['release_ms']:.0f} ms", gr))
    # hit events -> every other layer; war horn stab -> every other layer
    for spec, src, kinds in ((eq.HIT_DIP, "hit", None), (eq.HORN_DIP, "indian_lead", ("oneshot",))):
        ev = [time_sample(t) for e in sample_log if e["layer"] == src and (kinds is None or e["kind"] in kinds)
              for t in e["times_s"]]
        secs = [e["section"] for e in sample_log if e["layer"] == src and (kinds is None or e["kind"] in kinds)]
        gr = eq.event_dip_db(total, ev, spec["depth_db"], spec["attack_ms"], spec["release_ms"])
        targets = [l for l in STEM_LAYERS if l != src]
        for t in targets:
            stems[t] = stems[t] * eq.gain_from_gr(gr)[None, :]
        rows.append(_sc_row(spec["id"], f"{src} events ({len(ev)})", targets, secs, spec["depth_db"],
                            spec["attack_ms"], f"{spec['release_ms']:.0f} ms", gr))
    # perc vs groove: the weaker layer ducks on the stronger one's hits, only where they clash
    spec = eq.PERC_GROOVE
    for si in perc_clash:
        sec = plan["sections"][si]
        a = snap_frame(sec["start_s"])
        b = total if si == len(plan["sections"]) - 1 else snap_frame(sec["end_s"])
        rms = {l: rms_db(stems[l][:, a:b]) for l in ("groove", "indian_perc")}
        strong, weak = ("groove", "indian_perc") if rms["groove"] >= rms["indian_perc"] else ("indian_perc", "groove")
        gr = eq.duck_gr_db(keys[strong], [(a, b, float(sec["bpm"]), si + 1)], spec["depth_db"], spec["attack_ms"],
                           release_ms=spec["release_ms"])
        stems[weak] = stems[weak] * eq.gain_from_gr(gr)[None, :]
        rows.append(_sc_row(spec["id"], f"{strong} (stronger)", [weak], [si + 1], spec["depth_db"],
                            spec["attack_ms"], f"{spec['release_ms']:.0f} ms", gr))
    return stems, rows


def build(selection, plan, cue, log=print, eq_on=True, cuts=None, perc_clash=(), sidechain=True):
    """Layer stems before the voice gate and the gain riding (see finish). Returns (stems, sample_log, sc_rows).
    eq_on False and sidechain False rebuild the v4 stems exactly (legacy rules)."""
    total = int(cue["total_samples"])
    stems = {layer: np.zeros((2, total)) for layer in STEM_LAYERS}
    sample_log = []
    n_sec = len(plan["sections"])
    for idx, sec in enumerate(plan["sections"]):
        a = snap_frame(sec["start_s"])
        b = total if idx == n_sec - 1 else snap_frame(sec["end_s"])
        tempo = float(sec["bpm"])
        bass_slot = selection["slots"].get(ss.slot_id(idx, "bass"))
        mud = bass_slot is not None and bass_slot["status"] == "active"
        for layer in STEM_LAYERS:
            slot = selection["slots"].get(ss.slot_id(idx, layer))
            if slot is None or slot["status"] != "active":
                continue
            opt = next(o for o in slot["options"] if o["rank"] == slot["chosen"])
            spec = ss.BLEND[idx][layer] if layer in ss.LAYERS else ss.EXTRA_SPEC
            kind = slot.get("kind") or spec["kind"]  # fallback bass slots are pulses
            chain = None
            if eq_on:
                sec_cuts = (cuts or {}).get(idx, {}).get(layer, ())
                chain = eq.chain_for(layer, eq.role_of(layer, kind, opt["name"]), kind, opt["name"],
                                     sec_cuts, mud)
            src = ss.conform_audio(opt["path"], opt["stretch"], opt["shift"])
            measured_after = None
            if spec["tonal"]:
                measured_after = estimate_key(src[:, :30 * SR].mean(axis=0), SR)["key"]
            if kind == "window":
                w0, w1 = spec["window"]
                times = [w0]
                limit = time_sample(w1)
            else:
                times = ss.placements(plan, idx, kind)
                limit = b
            if kind == "loop":
                src = loop_length(src, tempo)
            if kind in ("bed", "loop"):
                # bed: free crossfade tile; loop: whole bars, butt joins (bars are exact)
                piece = tile(src, b - a, 0.02 if kind == "bed" else 0.0)
                piece = process_layer(fade_edges(piece, int(FADE_S * SR)), layer, kind, chain)
                stems[layer][:, a:b] += piece * (10 ** (float(slot.get("level_db", 0.0)) / 20.0))
                placed = [round(sec["start_s"], 6)]
            else:
                src = process_layer(fade_edges(src, int(FADE_S * SR)), layer, kind, chain)
                placed = []
                level_gain = 10 ** (float(slot.get("level_db", 0.0)) / 20.0)
                for k, t in enumerate(times):
                    # riser: ends on the cut (its start may fall in the previous section)
                    start = b - src.shape[1] if kind == "riser" else time_sample(t)
                    accent = 1.0 if (kind != "grid8" or k % 2 == 0) else GRID8_OFF_GAIN
                    place(stems[layer], src * (level_gain * accent), start, limit if kind != "riser" else b)
                    placed.append(round(t, 6))
            sample_log.append({
                "slot": ss.slot_id(idx, layer), "layer": layer, "section": idx + 1, "kind": kind,
                "file": opt["file"], "path": opt["path"], "pack": opt["pack"], "name": opt["name"],
                "times_s": placed, "section_start_sample": a, "section_end_sample": b,
                "window_s": list(spec["window"]) if kind == "window" else None,
                "tempo_bpm": tempo, "feel_bpm": opt["feel_bpm"], "stretch": opt["stretch"],
                "shift_semitones": opt["shift"], "target_key": opt["target_key"] if spec["tonal"] else None,
                "measured_key_before": opt["index_key"] if spec["tonal"] else None,
                "measured_key_after": measured_after,
                "premium": opt["premium"], "indian_pack": opt["indian_pack"],
            })
            log(f"{ss.slot_id(idx, layer)}: {opt['file']} placed {len(placed)}x")
    if sidechain:
        stems, sc_rows = sidechain_stems(stems, plan, sample_log, total, perc_clash)
    else:  # v4: bass and chords follow the groove envelope
        sc = sidechain_gain(stems["groove"]) if np.any(stems["groove"]) else np.ones(total)
        stems["bass"] *= sc
        stems["chords"] *= sc
        sc_rows = []
    stems["bass"][:] = stems["bass"].mean(axis=0, keepdims=True)  # mono low end
    return stems, sample_log, sc_rows


def finish(stems, cue, voice_mono, gate=True, ride=True, dips=True):
    """Last stages, in place: voice gate (with the 1-4 kHz dip under voice when dips), then the musical
    level and the per-window gain riding against voice_mono (the voice-only reference).
    gate=False and ride=False give the un-ducked listening copy. Returns (stems, level or None)."""
    total = int(cue["total_samples"])
    voice_windows = [tuple(w) for w in cue["voice"]["union"]]
    if gate:
        mask = voice_mask(total, voice_windows)
        for layer in STEM_LAYERS:
            stems[layer] = gate_layer(stems[layer], layer, mask, dip=dips and layer in eq.DYN_DIP_LAYERS)
    if not ride:
        return stems, None
    mix = sum(stems.values())
    score_db, voice_db = window_levels(mix, voice_mono, voice_windows)
    global_gain_db = VOICE_TARGET_DB - (score_db - voice_db)  # musical level outside the windows
    for layer in STEM_LAYERS:
        stems[layer] *= 10 ** (global_gain_db / 20.0)
    # per-window gain riding: every voice window at the target, smooth ramps, musical level elsewhere
    mean = sum(stems.values()).mean(axis=0)
    curve, gains, after = riding_gain_db(mean, voice_mono, voice_windows)
    for layer in STEM_LAYERS:
        stems[layer] *= 10 ** (curve / 20.0)
    level = {"global_gain_db": global_gain_db, "riding_gains_db": [round(float(g), 3) for g in gains],
             "per_window_db": [round(float(d), 3) for d in after], "windows": [list(w) for w in voice_windows],
             "table": window_table(after)}
    return stems, level


def load_voice_mono(path, total):
    data, _ = sf.read(path, dtype="float64", always_2d=True)
    mono = data.mean(axis=1)
    return np.pad(mono, (0, max(0, total - len(mono))))[:total]


def write_noduck(stems, total, version, target_lufs=-14.0):
    """Un-ducked listening copy: no voice gate, no riding (the caller applies the v5 global gain).
    Gain set so the mp3 measures target_lufs, with a limiter at -1 dBTP; up to 3 passes because the
    limiter moves the loudness. Returns (mp3 path, measured before, measured after, gain dB)."""
    mix = sum(stems.values())[:, :total].T.astype(np.float32)
    pre = os.path.join(WORK, f"mix_noduck_pre_{version}.wav")
    sf.write(pre, mix, SR, subtype="PCM_24")
    before = ebur(pre)
    gain = target_lufs - before["integrated_lufs"]
    mp3 = os.path.join(SOUND, f"score_full_noduck_{version}.mp3")
    for _ in range(3):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", pre, "-af",
                        f"volume={gain:.3f}dB,alimiter=limit=0.89:attack=5:release=50",
                        "-c:a", "libmp3lame", "-b:a", "192k", mp3], check=True)
        after = ebur(mp3)
        if after["integrated_lufs"] is None or abs(after["integrated_lufs"] - target_lufs) < 0.1:
            break
        gain += target_lufs - after["integrated_lufs"]
    return mp3, before, after, round(gain, 3)


def write_outputs(stems, sample_log, level, total, version):
    stems_dir = os.path.join(SOUND, f"stems_{version}")
    os.makedirs(stems_dir, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    for layer, arr in stems.items():
        sf.write(os.path.join(stems_dir, f"{layer}.wav"), arr[:, :total].T.astype(np.float32), SR, subtype="PCM_24")
    mix = sum(stems.values())
    pre = os.path.join(WORK, f"mix_pre_bus_{version}.wav")
    sf.write(pre, mix[:, :total].T.astype(np.float32), SR, subtype="PCM_24")
    bus = os.path.join(SOUND, f"score_mix_{version}.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", pre, "-af",
                    "acompressor=threshold=0.25:ratio=2:attack=20:release=200:makeup=1,"
                    "alimiter=limit=0.89:attack=5:release=50",
                    "-ar", str(SR), "-c:a", "pcm_s24le", bus], check=True)
    with open(os.path.join(SOUND, f"sample_log_{version}.json"), "w", encoding="utf-8") as fh:
        json.dump({"sample_rate": SR, "total_samples": total, "version": version, "level": level,
                   "files": sample_log}, fh, indent=1, ensure_ascii=False)
    return bus


def preview(bus, version, total_s):
    out_mp4 = os.path.join(SOUND, f"preview_reel1_en_small_{version}.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", EXPORT_MP4, "-i", bus, "-filter_complex",
                    "[0:a]aformat=sample_fmts=fltp:sample_rates=48000[v];"
                    "[1:a]aformat=sample_fmts=fltp:sample_rates=48000[s];"
                    "[v][s]amix=inputs=2:duration=first:normalize=0[a]",
                    "-map", "0:v", "-map", "[a]", "-vf", "scale=540:-2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                    "-c:a", "aac", "-b:a", "128k", "-t", f"{total_s:.3f}", out_mp4], check=True)
    mp3 = os.path.join(SOUND, f"score_mix_{version}.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", bus, "-c:a", "libmp3lame", "-b:a", "192k", mp3], check=True)
    return out_mp4, mp3


def measurement_section(version, level, sanity, loud, voice_loud, bus_windows, mp4, mp3):
    """Markdown for the '## Mix measurements' section: loudness, per-window table, per-section sanity."""
    t = bus_windows
    lines = [MEASURE_HEADING, "",
             f"Build {version}. Per-window levels measured from the written score_mix_{version}.wav against "
             "voice_ref.wav over every cue voice.union window (score RMS minus voice RMS, channel mean).", "",
             f"- Score alone: integrated {loud['integrated_lufs']} LUFS, LRA {loud['lra_lu']} LU, true peak {loud['true_peak_dbfs']} dBFS.",
             f"- Voice alone: integrated {voice_loud['integrated_lufs']} LUFS, LRA {voice_loud['lra_lu']} LU, true peak {voice_loud['true_peak_dbfs']} dBFS.",
             f"- Under voice, {t['windows']} windows: min {t['min']:.2f} dB, median {t['median']:.2f} dB, max {t['max']:.2f} dB. "
             f"Windows inside 15-21.5 dB under voice: {t['inside_target_count']} of {t['windows']}.",
             f"- Musical level outside the windows: global gain {level['global_gain_db']:.2f} dB. Riding gains per window (dB): "
             + ", ".join(f"{g:+.1f}" for g in level["riding_gains_db"]) + ".",
             f"- Files: {os.path.basename(mp4)}, {os.path.basename(mp3)}.", "",
             "### Per-window levels (score minus voice, dB)", "",
             "| window | start-end s | score minus voice dB |", "|---|---|---|"]
    for k, (w, d) in enumerate(zip(level["windows"], level["per_window_db"]), 1):
        lines.append(f"| {k} | {w[0]:.3f}-{w[1]:.3f} | {d:.2f} |")
    lines += ["", "### Per-section sanity (final mix)", "",
              "Audible = stem RMS above -50 dBFS inside the section. Indian/modern from the chosen sample's pack.", "",
              "| section | act | s | mix RMS dBFS | Indian audible | modern audible | audible layers |",
              "|---|---|---|---|---|---|---|"]
    for r in sanity:
        names = ", ".join(f"{x['layer']} ({x['kind']}, {x['rms_dbfs']} dBFS)" for x in r["layers"] if x["audible"])
        lines.append(f"| S{r['section']} | {r['act']} | {r['start_s']}-{r['end_s']} | {r['mix_rms_dbfs']} | "
                     f"{r['indian_audible']} | {r['modern_audible']} | {names or '-'} |")
    bad = [r["section"] for r in sanity if r["indian_audible"] < 1 or r["modern_audible"] < 1]
    lines += ["", f"Sections missing an audible Indian or modern layer: {bad or 'none'}.", ""]
    return "\n".join(lines)


def write_measurement_section(text):
    """Replace (or add) the Mix measurements section of the board; the rest of the board is kept."""
    path = ss.BOARD_PATH
    with open(path, encoding="utf-8") as fh:
        board = fh.read()
    i = board.find(MEASURE_HEADING)
    head = board[:i] if i >= 0 else board.rstrip() + "\n\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(head + text)


def section_spans(plan, total):
    """(a, b) sample span of each plan section on the frame grid; the last one runs to total."""
    n = len(plan["sections"])
    return [(snap_frame(s["start_s"]), total if i == n - 1 else snap_frame(s["end_s"]))
            for i, s in enumerate(plan["sections"])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", default="v5")
    args = ap.parse_args(argv)
    ep = ss.EP_DIR
    with open(os.path.join(ep, "score_plan.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    with open(os.path.join(ep, "cue_sheet.json"), encoding="utf-8") as fh:
        cue = json.load(fh)
    total = int(cue["total_samples"])
    os.makedirs(WORK, exist_ok=True)
    v = args.version
    vo_rows = build_voice_only(cue)  # voice-only reference (riding, window table); voice_ref.wav is not used
    voice_mono = load_voice_mono(VOICE_ONLY_WAV, total)
    spans = section_spans(plan, total)
    selection = ss.load_selection()
    log = lambda m: print(m, flush=True)
    # before: the v4 rules, measured on the stems as v4 wrote them (eq off, no sidechain)
    pre, _, _ = build(selection, plan, cue, log=log, eq_on=False, sidechain=False)
    fin, _ = finish(pre, cue, voice_mono)
    before_rows = eq.find_clashes(eq.section_band_levels(fin, spans))
    del pre, fin
    cuts = eq.clash_cuts(before_rows)
    perc_clash = [i for i, r in enumerate(eq.sustained_pair_rows(before_rows, "indian_perc", "groove")) if r]
    # after: v5 (EQ, sidechains, then gate and riding against the voice-only reference)
    stems, sample_log, sc_rows = build(selection, plan, cue, log=log, eq_on=True, cuts=cuts, perc_clash=perc_clash)
    noduck = {k: x.copy() for k, x in stems.items()}
    stems, level = finish(stems, cue, voice_mono)
    after_rows = eq.find_clashes(eq.section_band_levels(stems, spans))
    bus = write_outputs(stems, sample_log, level, total, v)
    sanity = section_sanity(stems, sample_log, plan, total)
    # independent check: read the written mix back and measure the windows against the voice-only reference
    mix, _ = sf.read(bus, dtype="float64", always_2d=True)
    windows = [tuple(w) for w in cue["voice"]["union"]]
    bus_table = window_table(window_diffs(mix[:total].mean(axis=1), voice_mono, windows))
    mp4, mp3 = preview(bus, v, cue["total_s"])
    for layer in noduck:  # the same musical level as v5, without the gate and the riding
        noduck[layer] *= 10 ** (level["global_gain_db"] / 20.0)
    nd_mp3, nd_before, nd_after, nd_gain = write_noduck(noduck, total, v)
    loud, voice_loud = ebur(bus), ebur(VOICE_ONLY_WAV)
    level["table_from_file"] = bus_table
    report = {"version": v, "reference": VOICE_ONLY_WAV, "cuts": cuts, "perc_clash_sections": [i + 1 for i in perc_clash],
              "sidechains": sc_rows, "before": eq.summarise(before_rows), "after": eq.summarise(after_rows),
              "before_top": before_rows, "after_top": after_rows,
              "level": level, "window_table_file": bus_table, "sanity": sanity, "loud": loud,
              "voice_loud": voice_loud, "noduck": {"mp3": nd_mp3, "gain_db": nd_gain,
                                                   "before": nd_before, "after": nd_after},
              "voice_only_rows": vo_rows, "mp4": mp4, "mp3": mp3}
    with open(os.path.join(WORK, f"eq_measure_{v}.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False, default=float)
    with open(os.path.join(SOUND, f"sample_log_{v}.json"), "w", encoding="utf-8") as fh:
        json.dump({"sample_rate": SR, "total_samples": total, "version": v, "level": level,
                   "files": sample_log, "sanity": sanity, "sidechains": sc_rows}, fh, indent=1, ensure_ascii=False)
    print("before", [(r["section"], r["sustained"], r["load"]) for r in report["before"]])
    print("after", [(r["section"], r["sustained"], r["load"]) for r in report["after"]])
    print("per-window min/median/max", round(bus_table["min"], 2), round(bus_table["median"], 2),
          round(bus_table["max"], 2), "inside", bus_table["inside_target_count"], "of", bus_table["windows"])
    print("loud", loud, "voice", voice_loud, "noduck", nd_after)
    print("per-window min/median/max", round(bus_table["min"], 2), round(bus_table["median"], 2),
          round(bus_table["max"], 2), "inside", bus_table["inside_target_count"], "of", bus_table["windows"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
