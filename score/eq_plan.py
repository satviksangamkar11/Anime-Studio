"""EQ, masking measurement and sidechain helpers for the reel 1 score (v5). Pure functions.

stem_builder wires these in. Order of work: measure the stems (band_db, section_band_levels,
find_clashes), turn the sustained clashes into static cuts on the lower-priority layer
(clash_cuts), build the EQ chain per layer and section (chain_for), then sidechain the written
stems (duck_gr_db, event_dip_db, band_duck). The voice gate and the gain riding stay last.
"""
from __future__ import annotations

import math
import re

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
BAND_CENTERS = [50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600,
                2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500]  # 1/3-octave centres, Hz
FRAME_S = 0.25        # masking frames: 250 ms
CLASH_DELTA_DB = 6.0  # two layers both loud in a band: within 6 dB of each other
FLOOR_DB = -45.0      # a band below this in a frame is silent
SUSTAIN = 0.05        # a clash that holds for >= 5 % of a section's frames counts (measured: max share 0.19)
PRIORITY = {"indian_lead": 0, "indian_lead2": 0, "groove": 1, "bass": 2, "indian_perc": 3,
            "chords": 4, "bed": 5, "hit": 6}  # lower number owns the band; the higher one is cut

# ---------------------------------------------------------------- measurement
def band_edges():
    c = np.array(BAND_CENTERS, dtype=float)
    return c * 2 ** (-1 / 6), c * 2 ** (1 / 6)


def band_db(mono, frame_s=FRAME_S, sr=SR):
    """Band level (dBFS, mean-square of the band) per frame: array (frames, bands)."""
    n = int(round(frame_s * sr))
    nf = len(mono) // n
    if nf == 0:
        return np.full((0, len(BAND_CENTERS)), -120.0)
    w = np.hanning(n)
    spec = np.fft.rfft(mono[:nf * n].reshape(nf, n) * w, axis=1)
    # Parseval: a band's mean-square = 2 * sum |X|^2 / (n * sum w^2) (one-sided spectrum)
    power = 2.0 * np.abs(spec) ** 2 / (n * np.sum(w ** 2))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    lo, hi = band_edges()
    out = np.empty((nf, len(lo)))
    for i in range(len(lo)):
        m = (freqs >= lo[i]) & (freqs < hi[i])
        out[:, i] = 10 * np.log10(power[:, m].sum(axis=1) + 1e-20)
    return out


def section_band_levels(stems, spans):
    """stems: {layer: (2, n)}; spans: [(a, b)] per section in samples. Returns one dict per section."""
    out = []
    for a, b in spans:
        out.append({layer: band_db(arr[:, a:b].mean(axis=0)) for layer, arr in stems.items()})
    return out


def find_clashes(sec_levels, floor=FLOOR_DB, delta=CLASH_DELTA_DB):
    """Per section: rows for every layer pair and band where both are loud and within delta dB.
    frac = share of the section's frames that clash; db = median level of the quieter of the two."""
    result = []
    for lv in sec_levels:
        rows = []
        names = sorted(lv)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                A, B = lv[a], lv[b]
                if A.shape[0] == 0:
                    continue
                for j, f in enumerate(BAND_CENTERS):
                    both = (A[:, j] > floor) & (B[:, j] > floor) & (np.abs(A[:, j] - B[:, j]) <= delta)
                    frac = float(both.mean())
                    if frac > 0:
                        db = float(np.median(np.minimum(A[both, j], B[both, j])))
                        rows.append({"band": f, "a": a, "b": b, "frac": round(frac, 3), "db": round(db, 1)})
        rows.sort(key=lambda r: (-r["frac"], -r["db"]))
        result.append(rows)
    return result


def summarise(rows_by_section, top=5):
    """Per section: number of sustained clashes, their load (sum of frac), and the top rows."""
    out = []
    for i, rows in enumerate(rows_by_section):
        sus = [r for r in rows if r["frac"] >= SUSTAIN]
        out.append({"section": i + 1, "sustained": len(sus), "load": round(sum(r["frac"] for r in sus), 2),
                    "top": rows[:top]})
    return out


def clash_cuts(rows_by_section, max_per_layer=2, cut_db=-2.5):
    """Measured cuts: for each sustained clash the lower-priority layer gets a notch at the band centre.
    Returns {section index: {layer: [(hz, dB), ...]}}."""
    cuts = {}
    for si, rows in enumerate(rows_by_section):
        taken = {}
        for r in rows:
            if r["frac"] < SUSTAIN:
                break
            pa, pb = PRIORITY.get(r["a"], 5), PRIORITY.get(r["b"], 5)
            if pa == pb:
                continue
            loser = r["a"] if pa > pb else r["b"]
            bands = taken.setdefault(loser, [])
            if len(bands) < max_per_layer and r["band"] not in bands:
                bands.append(r["band"])
        cuts[si] = {layer: [(float(f), cut_db) for f in bands] for layer, bands in taken.items()}
    return cuts


def sustained_pair_rows(rows_by_section, a_name, b_name):
    """Rows of one layer pair (either order) that are sustained, per section."""
    return [[r for r in rows if r["frac"] >= SUSTAIN and {r["a"], r["b"]} == {a_name, b_name}]
            for rows in rows_by_section]


# ---------------------------------------------------------------- EQ chains
ROLE_HP = {"bed": 180.0, "chords": 180.0, "lead": 250.0, "perc": 120.0, "hats": 1500.0,
           "riser": 250.0, "kick": 35.0}
BASS_LP_HZ = 3000.0        # bass owns the low end; above 3 kHz it is only grit
BASS_LP_REESE_HZ = 4000.0  # reese keeps a little more grit
GRID8_LP_HZ = 3500.0
MUD_HZ, MUD_DB, MUD_Q = 320.0, -2.5, 1.0   # low-mid mud on beds and chords when the bass plays
BED_DIP = (2500.0, -2.5, 0.9)               # legacy 1-4 kHz dip on beds, kept
CUT_Q = 1.4
DYN_DIP = (2500.0, -3.0, 0.9)               # dynamic 1-4 kHz dip on non-lead layers under voice
DYN_DIP_LAYERS = ("bed", "groove", "chords", "indian_perc")


def role_of(layer, kind, name):
    n = (name or "").lower()
    if layer in ("bed", "chords", "bass"):
        return layer
    if layer in ("indian_lead", "indian_lead2"):
        return "lead"
    if layer == "indian_perc":
        return "perc"
    if layer == "groove":
        return "hats" if re.search(r"hat|tick|click|shaker", n) else "kick"
    if layer == "hit":
        return "riser" if kind == "riser" else "impact"
    return "other"


def peaking_sos(f0, gain_db, q):
    """RBJ peaking EQ as one second-order section."""
    a = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2 * q)
    cs = math.cos(w0)
    b0, b1, b2 = 1 + alpha * a, -2 * cs, 1 - alpha * a
    a0, a1, a2 = 1 + alpha / a, -2 * cs, 1 - alpha / a
    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])


def chain_for(layer, role, kind, name, cuts=(), mud=False):
    """List of SOS filters for one layer in one section: high-pass by role, bass low-pass, grid low-pass,
    mud cut (beds and chords, when the bass plays), legacy bed dip, then the measured clash notches."""
    chain = []
    hp = ROLE_HP.get(role)
    if hp:
        chain.append(butter(2, hp, btype="highpass", fs=SR, output="sos"))
    if layer == "bass":
        lp = BASS_LP_REESE_HZ if "reese" in (name or "").lower() else BASS_LP_HZ
        chain.append(butter(4, lp, btype="lowpass", fs=SR, output="sos"))
    if kind == "grid8":
        chain.append(butter(4, GRID8_LP_HZ, btype="lowpass", fs=SR, output="sos"))
    if layer in ("bed", "chords") and mud:
        chain.append(peaking_sos(MUD_HZ, MUD_DB, MUD_Q))
    if layer == "bed":
        chain.append(peaking_sos(*BED_DIP))
    for f, g in cuts:
        chain.append(peaking_sos(f, g, CUT_Q))
    return chain


def apply_chain(x, chain):
    for sos in chain:
        x = sosfilt(sos, x, axis=-1)
    return x


def dyn_dip_sos():
    return peaking_sos(*DYN_DIP)


# ---------------------------------------------------------------- sidechain (envelope followers)
def envelope(x, attack_s, release_s, sr=SR):
    """Peak follower on |x|: one-pole attack and release (seconds). Continuous output, no steps."""
    aa = math.exp(-1.0 / max(1.0, attack_s * sr))
    ar = math.exp(-1.0 / max(1.0, release_s * sr))
    out = np.empty(len(x))
    acc = 0.0
    for i, v in enumerate(np.abs(np.asarray(x, dtype=float)).tolist()):
        if v > acc:
            acc = aa * acc + (1.0 - aa) * v
        else:
            acc = ar * acc
        out[i] = acc
    return out


def edge_ramp(n, ramp_s=0.02):
    """Linear ramps of ramp_s at both ends of a block of n samples (0 at the very edges, 1 inside)."""
    k = max(1, min(int(ramp_s * SR), n // 2))
    i = np.arange(n)
    return np.minimum(1.0, np.minimum(i + 1, n - i) / k)


def duck_gr_db(key, spans, depth_db, attack_ms, release_ms=None, release_beats=None, ref_pct=95.0):
    """Gain reduction in dB (>= 0) from a key signal, inside each span (a, b, bpm, ...).
    Envelope follower per span; release = release_ms, or release_beats of the span's tempo.
    GR = depth_db * min(1, env / ref), ref = the ref_pct percentile of the span's envelope."""
    total = len(key)
    gr = np.zeros(total)
    for span in spans:
        a, b, bpm = span[0], span[1], span[2]
        a, b = max(0, a), min(total, b)
        if b <= a:
            continue
        rel = release_ms if release_ms is not None else release_beats * 60000.0 / bpm
        env = envelope(key[a:b], attack_ms / 1000.0, rel / 1000.0)
        ref = float(np.percentile(env, ref_pct))
        if ref <= 0:
            continue
        gr[a:b] = depth_db * np.clip(env / ref, 0.0, 1.0) * edge_ramp(b - a)
    return gr


def event_dip_db(total, events, depth_db, attack_ms=3.0, release_ms=180.0):
    """Short dip around each event sample: fast ramp in, exponential release. Max over events."""
    gr = np.zeros(total)
    att = max(1.0, attack_ms / 1000.0 * SR)
    rel = release_ms / 1000.0 * SR
    span = int(5 * rel)
    for s in events:
        s = int(s)
        if s < 0 or s >= total:
            continue
        e = min(total, s + span)
        t = np.arange(e - s)
        g = depth_db * np.minimum(1.0, (t + 1) / att) * np.exp(-t / rel)
        gr[s:e] = np.maximum(gr[s:e], g)
    return gr


def gain_from_gr(gr_db):
    return 10 ** (-np.asarray(gr_db) / 20.0)


def band_duck(x, gr_db, lo=1000.0, hi=4000.0):
    """Duck only the lo..hi band of x (shape (2, n) or (n,)) by gr_db (per sample, dB)."""
    bp = sosfilt(butter(4, [lo, hi], btype="bandpass", fs=SR, output="sos"), x, axis=-1)
    return x + (gain_from_gr(gr_db) - 1.0) * bp


def max_step_db(gr_db):
    """Largest change of the gain reduction between two samples (dB). Small = no clicks or steps."""
    return float(np.max(np.abs(np.diff(gr_db)))) if len(gr_db) > 1 else 0.0


# Sidechain specs (depth in dB, times in ms; release in beats of the span tempo where given)
KICK_BASS = dict(id="kick>bass", key="groove", targets=("bass",), depth_db=5.0, attack_ms=3.0, release_beats=0.5)
KICK_PADS = dict(id="kick>pads", key="groove", targets=("bed", "chords"), depth_db=3.0, attack_ms=5.0,
                 release_beats=0.75)
LEAD_PADS = dict(id="lead 1-4k>pads", key="lead", targets=("bed", "chords"), depth_db=2.5, attack_ms=10.0,
                 release_ms=150.0, band=(1000.0, 4000.0))
HIT_DIP = dict(id="hit>all", source="hit", kinds=("riser", "hit", "sting"), depth_db=4.5, attack_ms=3.0,
               release_ms=180.0)
HORN_DIP = dict(id="war horn>all", source="indian_lead", kinds=("oneshot",), depth_db=3.0, attack_ms=3.0,
                release_ms=180.0)
PERC_GROOVE = dict(id="perc|groove", depth_db=1.5, attack_ms=2.0, release_ms=60.0)
KICK_ACTS = ("BUILD", "DROP")  # sections with a kick; HOOK and OUTRO have none
