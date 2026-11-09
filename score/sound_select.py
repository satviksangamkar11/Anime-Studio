"""Library sample selection for the reel 1 score (SMP2).

Pure functions plus a CLI. Reads the measured library index, the score plan and the
cue sheet. For every plan section and every layer of the blend table it filters the
library, measures the audio of up to 30 candidates, keeps the best 3 and renders each
as a 6 s snippet conformed to the section tempo and key. Writes:
  sound/SELECTION_BOARD.md, sound/selection.json, sound/snippets/<slot>_<rank>.mp3

Rules enforced here: tonal samples must MEASURE D minor (minor sources) or F major
(major sources) after a shift of at most 3 semitones; tempo stretch at most 12 %
(feel may be x2 or /2); lyric and word files never; no file used twice in the reel;
measured key of every rendered tonal snippet is re-checked. Library folders are only read.

CLI:
  python -m score.sound_select                     full run (measure, select, render)
  python -m score.sound_select --set S6-groove=2  change the chosen rank only (no re-run)
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
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import find_peaks

from score.key_estimate import estimate_key

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EP_DIR = os.path.join(ROOT, "stories", "kalika_puran_bhag1", "pack_opus_high_20261108_v4_deva", "score", "ep1")
INDEX_PATH = os.path.join(ROOT, "research", "sample_index_reel_libs.json")
SOUND_DIR = os.path.join(EP_DIR, "sound")
SNIP_DIR = os.path.join(SOUND_DIR, "snippets")
SELECTION_PATH = os.path.join(SOUND_DIR, "selection.json")
BOARD_PATH = os.path.join(SOUND_DIR, "SELECTION_BOARD.md")

SR = 48000
STRETCH_LIMIT = 0.12
MAX_SHIFT = 3
TOP_N = 3
CAND_CAP = 30
CAND_EXTEND = 300          # hard ceiling when extending a slot whose first CAND_CAP are mostly rejected
MIN_SCORED = 12            # keep extending until this many survive measuring (room for key-check drops)
SNIPPET_S = 6.0
MEASURE_S = 12.0
LAYERS = ("bed", "groove", "bass", "chords", "indian_perc", "indian_lead", "hit")
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
TARGET_KEYS = {"min": ("D min", 2), "maj": ("F maj", 5)}  # mode -> (name, tonic pitch class)
INDIAN_PACK_KEYS = ("dharma studio", "indian perc")
PREMIUM_PACK_KEYS = ("kshmr", "production music live", "pml -")
BANNED_WORDS = ("lyric", "vox phrase", "words")
ZONE_ORDER = ("bed", "groove", "bass", "chords", "indian_perc", "indian_lead", "hit")
LOW_PENALTY_LAYERS = ("bed", "chords", "indian_lead", "indian_perc")


# ---------------------------------------------------------------- blend table
WINDOW_STRETCH = 0.88      # slowed by 12 % at most (curse phrase)
KEY_MAX_S = 30.0           # key check uses up to 30 s of conformed audio (as the index does)


def _L(kind, cats, indian=None, tonal=False, kw=(), density=2.0, zone=(200, 3000)):
    """One layer spec. kind: bed | loop | pulse | oneshot | riser | hit | sting."""
    return {"kind": kind, "cats": list(cats), "indian": indian, "tonal": tonal,
            "kw": list(kw), "density": float(density), "zone": tuple(zone)}


# Index = plan section (0 = S1 ... 7 = S8). None = layer off in this section.
BLEND = [
    # S1 HOOK 0-6 s, ambient 60: dark sub, drone texture, Dharma chant hum as sonic logo
    {"bed": _L("bed", ["texture", "strings", "pad"], None, True, ["drone", "tanpura", "sustain", "dark"], 1.0, (150, 900)),
     "groove": None,
     "bass": _L("bed", ["bass_loop"], None, True, ["sub", "dark"], 1.0, (60, 300)),
     "chords": _L("bed", ["pad", "chord_loop"], False, True, ["pad", "drone", "dark"], 1.0, (400, 2000)),
     "indian_perc": None,
     "indian_lead": _L("bed", ["vocal_chant"], True, True, ["chant", "hum", "dharma", "om"], 1.0, (200, 1200)),
     "hit": None},
    # S2 HOOK 6-11.375 s, ambient 60: soft heartbeat, low dhol/tabla hits as the heartbeat
    {"bed": _L("bed", ["texture", "strings", "pad"], None, True, ["drone", "tanpura", "sustain", "dark"], 1.0, (150, 900)),
     "groove": _L("pulse", ["kick", "drum_oneshot"], False, False, ["kick", "sub", "low", "heart"], 1.0, (40, 250)),
     "bass": _L("bed", ["bass_loop"], None, True, ["sub", "dark"], 1.0, (60, 300)),
     "chords": _L("bed", ["pad", "chord_loop"], False, True, ["pad", "drone", "dark"], 1.0, (400, 2000)),
     "indian_perc": _L("pulse", ["perc", "drum_oneshot"], True, False, ["dhol", "tabla", "taiko", "low"], 1.0, (60, 500)),
     "indian_lead": _L("bed", ["vocal_chant"], True, True, ["chant", "hum", "dharma", "om"], 1.0, (200, 1200)),
     "hit": _L("riser", ["riser"], None, False, ["reverse", "swell"], 0.0, (1000, 8000))},
    # S3 BUILD 11.375-18.833 s, hypnotic techno 128: kick loop, tabla/ghatam loop, filtered and low
    {"bed": _L("bed", ["texture", "pad"], None, True, ["drone", "dark", "texture"], 1.0, (150, 1200)),
     "groove": _L("loop", ["drum_loop"], False, False, ["techno", "house", "kick", "hypnotic"], 4.5, (800, 4000)),
     "bass": _L("loop", ["bass_loop"], False, True, ["techno", "sub", "bass"], 3.0, (60, 400)),
     "chords": _L("loop", ["chord_loop", "arp"], False, True, ["arp", "techno", "melodic", "loop"], 4.0, (600, 3000)),
     "indian_perc": _L("loop", ["perc", "drum_loop"], True, False, ["tabla", "ghatam", "perc", "loop"], 4.0, (800, 4000)),
     "indian_lead": None,
     "hit": _L("riser", ["riser"], None, False, ["reverse", "swell"], 0.0, (1000, 8000))},
    # S4 BUILD 18.833-26.833 s, melodic techno 128: wide pad, bansuri flute for Sandhya
    {"bed": _L("bed", ["pad", "texture"], False, True, ["pad", "wide", "melodic"], 1.0, (300, 2000)),
     "groove": _L("loop", ["drum_loop"], False, False, ["house", "techno", "drum"], 4.0, (800, 4000)),
     "bass": _L("loop", ["bass_loop"], False, True, ["bass", "techno", "sub"], 3.0, (60, 400)),
     "chords": _L("loop", ["chord_loop", "arp"], False, True, ["chord", "melodic", "pad", "arp"], 2.0, (600, 3000)),
     "indian_perc": _L("loop", ["perc", "drum_loop"], True, False, ["ghatam", "tabla", "perc"], 4.0, (800, 4000)),
     "indian_lead": _L("bed", ["flute"], True, True, ["bansuri", "flute", "breath"], 1.0, (1000, 4000)),
     "hit": None},
    # S5 BUILD 26.833-35.125 s, club + folk groove 128: Bagal Bachha folk perc, sitar/pluck hook
    {"bed": None,
     "groove": _L("loop", ["drum_loop"], False, False, ["house", "dance", "club", "kick"], 4.5, (800, 4000)),
     "bass": _L("loop", ["bass_loop"], False, True, ["bass", "club"], 4.0, (60, 400)),
     "chords": None,
     "indian_perc": _L("loop", ["perc", "drum_loop"], True, False, ["bagal", "folk", "perc", "kuthu"], 5.0, (1000, 5000)),
     "indian_lead": _L("bed", ["sitar", "flute"], True, True, ["sitar", "pluck", "hook"], 3.0, (1000, 4000)),
     "hit": _L("riser", ["riser"], None, False, ["reverse", "swell"], 0.0, (1000, 8000))},
    # S6 DROP 35.125-49.792 s, drum and bass 176: reese bass, tabla rolls, chant chops in the gaps
    {"bed": _L("bed", ["drone", "texture"], None, True, ["drone", "dark", "texture"], 1.0, (150, 1200)),
     "groove": _L("loop", ["drum_loop"], False, False, ["drum and bass", "dnb", "break", "amen", "jungle", "drum"], 8.0, (1000, 5000)),
     "bass": _L("loop", ["bass_loop"], False, True, ["reese", "dnb", "bass", "neuro"], 6.0, (80, 500)),
     "chords": _L("loop", ["chord_loop", "arp"], False, True, ["stab", "ostinato", "arp", "chord"], 5.0, (600, 3000)),
     "indian_perc": _L("loop", ["perc", "drum_loop"], True, False, ["tabla", "dhol", "roll", "fill"], 7.0, (1000, 5000)),
     "indian_lead": _L("bed", ["vocal_chant"], True, True, ["chant", "chop", "dharma"], 3.0, (300, 2000)),
     "hit": _L("hit", ["impact", "sub_drop"], None, False, ["low", "hit", "sub"], 0.0, (60, 800))},
    # S7 DROP 49.792-66.833 s, half-time DnB 176 (feel 88): Shiva, war horn/conch, chant choir
    {"bed": _L("bed", ["pad", "strings", "vocal_chant"], None, True, ["choir", "pad", "dark", "dharma"], 1.0, (200, 1500)),
     "groove": _L("loop", ["drum_loop"], False, False, ["drum and bass", "dnb", "break", "half", "heavy", "drum"], 4.0, (800, 4000)),
     "bass": _L("loop", ["bass_loop"], False, True, ["distort", "crawl", "sub", "bass"], 2.0, (60, 300)),
     "chords": None,
     "indian_perc": _L("loop", ["perc", "drum_loop"], True, False, ["taiko", "dhol", "war", "tabla"], 4.0, (600, 4000)),
     "indian_lead": _L("oneshot", ["war_horn", "brass"], True, True, ["horn", "conch", "war", "brass"], 1.0, (200, 1500)),
     "hit": _L("hit", ["impact", "sub_drop"], None, False, ["low", "hit", "sub"], 0.0, (60, 600))},
    # S8 OUTRO 66.833-72.833 s, unplugged 60: piano MAIN, soft tick pulse, tanpura-like drone
    {"bed": _L("bed", ["drone", "texture"], True, True, ["tanpura", "drone", "sustain"], 1.0, (150, 900)),
     "groove": _L("pulse", ["hat", "perc", "drum_oneshot"], False, False, ["tick", "hat", "click"], 1.0, (2000, 9000)),
     "bass": None,
     "chords": _L("bed", ["piano"], False, True, ["piano", "soft", "main"], 1.0, (300, 2500)),
     "indian_perc": None,
     "indian_lead": None,
     "hit": _L("sting", ["impact"], None, False, ["end", "sting", "hit"], 0.0, (60, 1200))},
]


# Extra slot: a library sitar phrase in the Kamadeva curse window (56-64 s, plan transform), slowed.
EXTRA_IDX = 6                       # S7 (section index 6)
EXTRA_LAYER = "indian_lead2"
EXTRA_SPEC = dict(_L("window", ["sitar"], True, True, ["sitar", "pluck", "curse", "slow", "hook"], 1.0, (300, 2500)),
                  window=(56.0, 64.0))


# ---------------------------------------------------------------- pure helpers
def is_lyric(entry):
    text = (entry.get("name", "") + " " + entry.get("path", "")).lower()
    return any(w in text for w in BANNED_WORDS)


def is_indian(entry):
    return any(k in entry.get("pack", "").lower() for k in INDIAN_PACK_KEYS)


def is_premium(entry):
    return any(k in entry.get("pack", "").lower() for k in PREMIUM_PACK_KEYS)


def parse_key(text):
    """'D min' -> (2, 'min'). None when the text is not a measured key."""
    m = re.match(r"^([A-G]#?) (min|maj)$", text or "")
    if not m:
        return None
    return NOTE_NAMES.index(m.group(1)), m.group(2)


def tonal_fit(detected_key):
    """Shift that brings a measured key to D minor (minor source) or F major (major source).

    Returns (target_key_name, shift_semitones) or None when the shift is more than MAX_SHIFT.
    """
    parsed = parse_key(detected_key)
    if parsed is None:
        return None
    tonic, mode = parsed
    target_name, target_tonic = TARGET_KEYS[mode]
    shift = ((target_tonic - tonic + 6) % 12) - 6  # range -6..5
    if abs(shift) > MAX_SHIFT:
        return None
    return target_name, shift


def conform_plan(entry, spec, tempo):
    """How a file is conformed for one slot. None = rejected by the rules.

    Returns dict(feel_bpm, stretch, shift, target_key) or None.
    feel_bpm is the tempo the file is counted at (its bpm, or x2 / /2 for half and double feel).
    stretch = tempo / feel_bpm is the rubberband tempo factor (|stretch - 1| <= 12 %).
    """
    out = {"feel_bpm": None, "stretch": 1.0, "shift": 0, "target_key": None}
    if spec["tonal"]:
        fit = tonal_fit(entry.get("detected_key"))
        if fit is None:
            return None
        out["target_key"], out["shift"] = fit
    kind = spec["kind"]
    if kind == "window":  # slowed phrase in a fixed window (S7 curse): slowed by up to 12 %
        out["stretch"] = WINDOW_STRETCH
        return out
    if kind in ("pulse", "oneshot", "riser", "hit", "sting"):
        return out
    bpm = entry.get("bpm")
    if bpm is None:
        if kind == "loop":
            return None
        return out
    best = None
    for feel in (bpm, 2.0 * bpm, bpm / 2.0):
        stretch = tempo / feel
        if abs(stretch - 1.0) <= STRETCH_LIMIT and (best is None or abs(stretch - 1.0) < abs(best[1] - 1.0)):
            best = (feel, stretch)
    if best is None:
        return None
    feel, stretch = best
    if kind == "loop":
        bars = entry["seconds"] * feel / 240.0  # 4/4 bar = 240 / bpm seconds
        if round(bars) < 1 or abs(bars - round(bars)) > 0.1:
            return None
    out["feel_bpm"] = feel
    out["stretch"] = stretch
    return out


def passes_filter(entry, spec, indian):
    """Category, pack, lyric and length rules (key and tempo are in conform_plan)."""
    if is_lyric(entry):
        return False
    seconds = entry.get("seconds") or 0.0
    if seconds < 0.3:
        return False
    if not set(entry.get("categories") or []) & set(spec["cats"]):
        return False
    if indian is True and not is_indian(entry):
        return False
    if indian is False and is_indian(entry):
        return False
    return True


def meta_score(entry, spec, conform, conf_ref):
    """Cheap pre-score from metadata only, used to cap the candidates that get measured."""
    text = (entry["name"] + " " + entry["path"]).lower()
    kw = min(0.1, 0.03 * sum(1 for k in spec["kw"] if k in text))
    premium = 0.05 if is_premium(entry) else 0.0
    conf = min(1.0, (entry.get("detected_confidence") or 0.0) / conf_ref) if conf_ref else 0.0
    key_ok = 1.0 - 0.12 * abs(conform["shift"]) if spec["tonal"] else 1.0
    stretch_ok = 1.0 - 0.4 * abs(conform["stretch"] - 1.0) / STRETCH_LIMIT
    return 0.1 * key_ok + 0.1 * stretch_ok + 0.1 * conf + kw + premium


def zone_score(centroid, lo, hi):
    if centroid <= 0:  # silent or DC-only: no role fit
        return 0.0
    if lo <= centroid <= hi:
        return 1.0
    d = math.log(centroid / lo) if centroid < lo else math.log(centroid / hi)
    return math.exp(-1.5 * abs(d))


def score_features(entry, spec, layer, conform, feats, conf_ref):
    """Measured score in roughly 0..1.3. Pure: numbers in, number out."""
    role = zone_score(feats["centroid"], *spec["zone"])
    if layer in LOW_PENALTY_LAYERS:
        low_ok = max(0.0, 1.0 - 3.0 * feats["low"])
    else:
        low_ok = 1.0
    mid_ok = max(0.0, 1.0 - 2.0 * feats["mid"])
    target = max(spec["density"], 1.0)
    dens = math.exp(-abs(feats["onset"] - spec["density"]) / target)
    stretch_ok = 1.0 - 0.4 * abs(conform["stretch"] - 1.0) / STRETCH_LIMIT
    key_ok = 1.0 - 0.12 * abs(conform["shift"]) if spec["tonal"] else 1.0
    conf = min(1.0, (entry.get("detected_confidence") or 0.0) / conf_ref) if conf_ref else 0.0
    total = (0.25 * role + 0.15 * low_ok + 0.15 * mid_ok + 0.15 * dens
             + 0.10 * stretch_ok + 0.10 * key_ok + 0.10 * conf)
    text = (entry["name"] + " " + entry["path"]).lower()
    total += min(0.1, 0.03 * sum(1 for k in spec["kw"] if k in text))
    total += 0.05 if is_premium(entry) else 0.0
    declared = parse_key(entry.get("key")) if entry.get("key") else None
    if declared and entry.get("detected_key") and parse_key(entry["detected_key"]) != declared:
        total *= 0.92  # file name key disagrees with the measured key: name is often wrong
    return round(total, 4)


def placements(plan, idx, kind):
    """Times (s) where a layer of kind `kind` is placed in section idx of the plan."""
    sec = plan["sections"][idx]
    s0, s1 = float(sec["start_s"]), float(sec["end_s"])
    if kind in ("bed", "loop"):
        return [s0]
    if kind == "pulse":
        beat = 60.0 / float(sec["bpm"])
        n = int(math.ceil((s1 - s0) / beat - 1e-9))
        return [round(s0 + k * beat, 6) for k in range(n)]
    if kind == "oneshot":
        return [s0]
    if kind == "riser":
        return [s1]  # the riser ends on the cut
    if kind == "hit":
        return [float(e["at_s"]) for e in plan["events"] if e["type"] == "hit" and s0 <= e["at_s"] < s1]
    if kind == "sting":
        return [float(e["at_s"]) for e in plan["events"] if e["type"] == "end_sting" and s0 <= e["at_s"] < s1]
    return []


def slot_id(idx, layer):
    return f"S{idx + 1}-{layer}"


def parse_slot(sid):
    m = re.match(r"^S(\d+)-(\w+)$", sid)
    return int(m.group(1)) - 1, m.group(2)


def check_selection(selection):
    """Errors for the rules that do not depend on audio: no file twice, one Indian layer per section."""
    errors = []
    seen = {}
    for sid, slot in selection["slots"].items():
        for opt in slot["options"]:
            if opt["path"] in seen:
                errors.append(f"file used twice: {opt['file']} in {seen[opt['path']]} and {sid}")
            seen[opt["path"]] = sid
            if opt["shift"] and abs(opt["shift"]) > MAX_SHIFT:
                errors.append(f"{sid}: shift {opt['shift']} over {MAX_SHIFT}")
            if opt.get("feel_bpm") and abs(opt["stretch"] - 1.0) > STRETCH_LIMIT + 1e-9:
                errors.append(f"{sid}: stretch {opt['stretch']} over limit")
    for i in range(len(BLEND)):
        sec_slots = [slot for slot in selection["slots"].values() if slot["section"] == i + 1]
        if sec_slots and not any(s["layer"] in ("indian_perc", "indian_lead", "bed") and s["status"] == "active"
                                 and s["indian"] for s in sec_slots):
            errors.append(f"S{i + 1}: no Indian layer")
    return errors


# ---------------------------------------------------------------- audio
def measure(path, seconds):
    """Features of the first MEASURE_S seconds: peak, centroid, low and 1-4 kHz energy share, onset rate."""
    info = sf.info(path)
    frames = min(int(info.frames), int(MEASURE_S * info.samplerate))
    data, sr = sf.read(path, frames=frames, dtype="float64", always_2d=True)
    mono = data.mean(axis=1)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    n_fft, hop = 2048, 512
    if len(mono) < n_fft:
        mono = np.pad(mono, (0, n_fft - len(mono)))
    frames_m = sliding_window_view(mono, n_fft)[::hop] * np.hanning(n_fft)
    mag = np.abs(np.fft.rfft(frames_m, axis=1))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    power = mag ** 2
    total = power.sum() + 1e-12
    low = float(power[:, freqs < 120].sum() / total)
    mid = float(power[:, (freqs >= 1000) & (freqs <= 4000)].sum() / total)
    centroid = float((freqs * mag).sum() / (mag.sum() + 1e-12))
    flux = np.maximum(0.0, np.diff(mag, axis=0)).sum(axis=1)
    thr = flux.mean() + 0.5 * flux.std()
    peaks, _ = find_peaks(flux, height=thr, distance=max(1, int(0.08 * sr / hop)))
    dur = max(len(mono) / float(sr), 1e-3)
    return {"peak": peak, "centroid": centroid, "low": low, "mid": mid,
            "onset": float(len(peaks) / dur), "seconds_measured": float(dur)}


def render_snippet(src, stretch, shift, out_path, seconds=SNIPPET_S):
    """ffmpeg rubberband to the section tempo and key, 6 s, 48 kHz stereo mp3 128k."""
    pitch = 2.0 ** (shift / 12.0)
    filters = []
    if abs(stretch - 1.0) > 1e-6 or abs(pitch - 1.0) > 1e-6:
        filters.append(f"rubberband=tempo={stretch:.6f}:pitch={pitch:.6f}")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd += ["-t", f"{seconds:.3f}", "-ac", "2", "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "128k", out_path]
    subprocess.run(cmd, check=True)


def measured_key_of_file(path):
    data, sr = sf.read(path, dtype="float64", always_2d=True)
    return estimate_key(data.mean(axis=1), sr)


def conform_audio(path, stretch, shift):
    """Whole file to 48 kHz stereo float64: rubberband tempo=stretch, pitch=2**(shift/12)."""
    pitch = 2.0 ** (shift / 12.0)
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if abs(stretch - 1.0) > 1e-6 or abs(pitch - 1.0) > 1e-6:
        cmd += ["-af", f"rubberband=tempo={stretch:.6f}:pitch={pitch:.6f}"]
    cmd += ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.astype(np.float64)


def loop_cycle_seconds(seconds, feel_bpm, tempo):
    """Length of the whole-bar loop after conform (bars counted at the feel tempo)."""
    bars = max(1, round(seconds * feel_bpm / 240.0))
    return bars * 240.0 / tempo


def key_check_seconds(kind, cycle_s, duration_s):
    """Conformed seconds used for the key check.

    Loops: at least 2 full loop cycles (never less than 2 s), capped at KEY_MAX_S.
    Everything else: the whole conformed file, capped at KEY_MAX_S.
    """
    if kind == "loop" and cycle_s:
        return min(KEY_MAX_S, max(2.0 * cycle_s, 2.0))
    return min(KEY_MAX_S, duration_s)


def conformed_key(path, conform, kind, seconds, tempo):
    """Measured key of the CONFORMED audio over the check length. Returns (key, audio)."""
    audio = conform_audio(path, conform["stretch"], conform["shift"])
    duration = audio.shape[1] / float(SR)
    cycle = None
    if kind == "loop" and conform.get("feel_bpm"):
        cycle = loop_cycle_seconds(seconds, conform["feel_bpm"], tempo)
    n = int(key_check_seconds(kind, cycle, duration) * SR)
    n = min(max(n, SR), audio.shape[1])
    return estimate_key(audio[:, :n].mean(axis=0), SR)["key"], audio


# ---------------------------------------------------------------- selection
def select_all(plan, entries, log=print):
    """Full selection and rendering. Returns the selection dict (also written by main)."""
    conf_vals = [e["detected_confidence"] for e in entries if e.get("detected_confidence") is not None]
    conf_ref = float(np.percentile(conf_vals, 75)) if conf_vals else 0.1
    used = set()
    cache = {}
    slots = {}
    os.makedirs(SNIP_DIR, exist_ok=True)
    for idx, sec in enumerate(plan["sections"]):
        tempo = float(sec["bpm"])
        for layer in LAYERS + (EXTRA_LAYER,) * (idx == EXTRA_IDX):
            sid = slot_id(idx, layer)
            spec = BLEND[idx][layer] if layer in LAYERS else EXTRA_SPEC
            base = {"section": idx + 1, "layer": layer, "start_s": sec["start_s"], "end_s": sec["end_s"],
                    "tempo": tempo, "genre": sec["genre"], "act": sec["act"], "indian": False}
            if spec is None:
                slots[sid] = dict(base, status="off", kind=None, relaxed=False, chosen=None, options=[],
                                  note="layer off in this section (plan roles_on)")
                log(f"{sid}: off")
                continue
            indian_req = spec["indian"]
            relaxed = False
            options = []
            # only an Indian-required layer may relax its pack constraint, and the board says so
            for indian in ([True, None] if indian_req is True else [indian_req]):
                if options:
                    break
                cands = []
                for e in entries:
                    if e["path"] in used or not passes_filter(e, spec, indian):
                        continue
                    conform = conform_plan(e, spec, tempo)
                    if conform is None:
                        continue
                    cands.append((meta_score(e, spec, conform, conf_ref), e, conform))
                cands.sort(key=lambda t: -t[0])
                scored = []
                # measure the best CAND_CAP; extend to CAND_EXTEND only when too few survive (clipping, missing)
                for pos, (_, e, conform) in enumerate(cands[:CAND_EXTEND]):
                    if pos == CAND_CAP and len(scored) >= MIN_SCORED:
                        break
                    if not os.path.exists(e["path"]):
                        continue
                    if e["path"] not in cache:
                        cache[e["path"]] = measure(e["path"], e.get("seconds"))
                    feats = cache[e["path"]]
                    if feats["peak"] >= 0.999:
                        continue  # clipping
                    scored.append((score_features(e, spec, layer, conform, feats, conf_ref), e, conform, feats))
                scored.sort(key=lambda t: -t[0])
                log(f"{sid}: {len(cands)} candidates measured {len(scored)} (indian={indian})")
                for sc, e, conform, feats in scored:
                    if len(options) >= TOP_N:
                        break
                    if e["path"] in used:
                        continue
                    rank = len(options) + 1
                    snip_name = f"{sid}_{rank}.mp3"
                    snip_path = os.path.join(SNIP_DIR, snip_name)
                    snippet_key = None
                    if spec["tonal"]:
                        # key of the CONFORMED audio over the whole loop (>= 2 cycles, up to 30 s), not the 6 s snippet
                        try:
                            snippet_key, _ = conformed_key(e["path"], conform, spec["kind"], e.get("seconds"), tempo)
                        except subprocess.CalledProcessError:
                            log(f"{sid}: conform failed for {e['name']}")
                            continue
                        if snippet_key != conform["target_key"]:
                            log(f"{sid}: {e['name']} measures {snippet_key} after conform, dropped")
                            continue
                    try:
                        render_snippet(e["path"], conform["stretch"], conform["shift"], snip_path)
                    except subprocess.CalledProcessError:
                        log(f"{sid}: render failed for {e['name']}")
                        continue
                    used.add(e["path"])
                    options.append(_option(rank, e, conform, feats, sc, snip_name, snippet_key, spec))
                if options:
                    relaxed = indian is None and indian_req is not None
                    break
            status = "active" if options else "empty"
            slots[sid] = dict(base, status=status, kind=spec["kind"], indian=bool(indian_req),
                              relaxed=relaxed, chosen=1 if options else None, options=options,
                              note="" if len(options) >= TOP_N else f"only {len(options)} option(s) found")
            log(f"{sid}: {status}, {len(options)} option(s){' (Indian relaxed)' if relaxed else ''}")
    return {"schema": 1, "episode": 1, "sample_rate": SR, "stretch_limit": STRETCH_LIMIT,
            "max_shift": MAX_SHIFT, "snippet_s": SNIPPET_S, "target_keys": ["D min", "F maj"],
            "confidence_ref": conf_ref, "slots": slots}


def _option(rank, e, conform, feats, score, snip_name, snippet_key, spec):
    shift = conform["shift"]
    stretch = conform["stretch"]
    why = (f"centroid {feats['centroid']:.0f} Hz, low {feats['low']:.2f}, 1-4 kHz {feats['mid']:.2f}, "
           f"onsets {feats['onset']:.1f}/s (target {spec['density']:.1f}), "
           f"stretch {stretch:.3f}, shift {shift:+d}, score {score:.3f}")
    return {"rank": rank, "file": os.path.basename(e["path"]), "path": e["path"], "pack": e["pack"],
            "name": e["name"], "categories": e["categories"], "index_key": e.get("detected_key"),
            "index_key_confidence": e.get("detected_confidence"), "shift": shift,
            "target_key": conform["target_key"], "feel_bpm": conform["feel_bpm"], "stretch": round(stretch, 6),
            "score": score, "snippet": os.path.join("snippets", snip_name), "snippet_key": snippet_key,
            "why": why, "premium": is_premium(e), "indian_pack": is_indian(e)}


def write_board(selection, path=BOARD_PATH):
    lines = ["# Selection board: reel 1 score samples (SMP2)", "",
             "Measured on the audio (chroma key, centroid, low and 1-4 kHz energy, onset rate). Tonal samples: only",
             f"D minor (minor sources) or F major (major sources), shift at most {MAX_SHIFT}. Tempo stretch at most",
             f"{int(STRETCH_LIMIT * 100)} %, feel may be x2 or /2. Chosen rank = the one in the stems (rank 1 by default).", ""]
    for sid, slot in selection["slots"].items():
        head = (f"## {sid}: {slot['layer']} | section {slot['section']} {slot['act']} "
                f"{slot['start_s']}-{slot['end_s']} s | {slot['genre']} {slot['tempo']:.0f} BPM")
        lines += [head]
        if slot["status"] == "off":
            lines += [f"Off: {slot['note']}", ""]
            continue
        if slot["relaxed"]:
            lines += ["Indian pack constraint relaxed for this slot (too few Indian candidates).", ""]
        if slot["note"]:
            lines += [slot["note"], ""]
        lines += ["| rank | file | pack | index key | shift | stretch | feel BPM | snippet key | score | why |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for o in slot["options"]:
            mark = " (chosen)" if o["rank"] == slot["chosen"] else ""
            feel = "" if o["feel_bpm"] is None else f"{o['feel_bpm']:.0f}"
            lines.append(f"| {o['rank']}{mark} | {o['file']} | {o['pack']} | {o['index_key'] or '-'} | "
                         f"{o['shift']:+d} | {o['stretch']:.3f} | {feel or '-'} | {o['snippet_key'] or '-'} | "
                         f"{'-' if o['score'] is None else format(o['score'], '.3f')} | {o['why']} |")
        lines.append("")
    tail = read_measure_tail(path)  # measurements written by stem_builder survive reruns and --set
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        if tail:
            fh.write("\n" + tail)


MEASURE_HEADING = "## Mix measurements"


def read_measure_tail(path=BOARD_PATH):
    """The '## Mix measurements' section of an existing board (empty when there is none)."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    i = text.find(MEASURE_HEADING)
    return text[i:] if i >= 0 else ""


def load_selection(path=SELECTION_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def set_chosen(selection, sid, rank):
    slot = selection["slots"][sid]
    if not any(o["rank"] == rank for o in slot["options"]):
        raise ValueError(f"{sid} has no rank {rank}")
    slot["chosen"] = rank
    return selection


ROOT_BASS_HZ = 73.416      # D2, the bass root used by the fallback route (bible SHIVA/KAMADEVA low end)


def estimate_f0(mono, sr, fmin=30.0, fmax=200.0):
    """Fundamental of a short monophonic sound by autocorrelation (Hz) or None."""
    x = np.asarray(mono, dtype=np.float64)[: int(sr * 1.0)]
    if x.size < int(sr / fmin) * 2:
        return None
    x = x - x.mean()
    n = 1
    while n < 2 * x.size:
        n *= 2
    ac = np.fft.irfft(np.abs(np.fft.rfft(x, n)) ** 2)[: x.size]
    lo, hi = int(sr / fmax), min(int(sr / fmin), x.size - 1)
    if hi <= lo or ac[0] <= 0:
        return None
    lag = lo + int(np.argmax(ac[lo:hi]))
    if ac[lag] < 0.3 * ac[0]:
        return None
    return sr / lag


def fill_empty_bass(selection, entries, log=print):
    """Bass fallback: sub or 808 one-shots pitched to D2 and placed on the beat grid (kind pulse).

    Only for bass slots with no option from the loop route. Returns the number filled.
    """
    used = {o["path"] for sl in selection["slots"].values() for o in sl["options"]}
    filled = 0
    os.makedirs(SNIP_DIR, exist_ok=True)
    for sid, slot in selection["slots"].items():
        if slot["layer"] != "bass" or slot["status"] != "empty":
            continue
        cands = [e for e in entries if e["path"] not in used and not is_lyric(e)
                 and ("sub_drop" in e.get("categories", []) or "808" in e["name"].lower())
                 and 0.2 <= (e.get("seconds") or 0.0) <= 6.0]
        options = []
        for e in cands:
            if len(options) >= TOP_N:
                break
            if not os.path.exists(e["path"]):
                continue
            data, sr = sf.read(e["path"], frames=int(1.0 * 48000), dtype="float64", always_2d=True)
            mono = data.mean(axis=1)
            if np.max(np.abs(data)) >= 0.999:
                continue
            f0 = estimate_f0(mono, sr)
            if f0 is None:
                continue
            semis = 12.0 * math.log2(ROOT_BASS_HZ / f0)
            shift = int(round(semis))
            if abs(shift) > 12:
                continue
            rank = len(options) + 1
            snip_name = f"{sid}_{rank}.mp3"
            render_snippet(e["path"], 1.0, shift, os.path.join(SNIP_DIR, snip_name))
            snip, _ = sf.read(os.path.join(SNIP_DIR, snip_name), dtype="float64", always_2d=True)
            f0_after = estimate_f0(snip.mean(axis=1), SR)
            if f0_after is None or abs(12.0 * math.log2(f0_after / ROOT_BASS_HZ)) > 1.0:
                continue
            used.add(e["path"])
            options.append({
                "rank": rank, "file": os.path.basename(e["path"]), "path": e["path"], "pack": e["pack"],
                "name": e["name"], "categories": e["categories"], "index_key": None, "index_key_confidence": None,
                "shift": shift, "target_key": "D2", "feel_bpm": None, "stretch": 1.0,
                "score": None, "snippet": os.path.join("snippets", snip_name),
                "snippet_key": f"root D2 (f0 {f0_after:.1f} Hz)",
                "why": f"fallback route: one-shot pitched to D2; measured f0 {f0:.1f} Hz before, {f0_after:.1f} Hz after, "
                       f"shift {shift:+d}; placed on the beat grid",
                "premium": is_premium(e), "indian_pack": is_indian(e)})
        if options:
            slot.update(status="active", kind="pulse", chosen=1, options=options, relaxed=False,
                        route="fallback: sub/808 one-shot pitched to D2 on the beat grid",
                        note=f"only {len(options)} option(s) found" if len(options) < TOP_N else "")
            filled += 1
            log(f"{sid}: fallback route, {len(options)} option(s)")
        else:
            slot["route"] = "fallback tried: no sub/808 one-shot pitched to D2 within rules"
            log(f"{sid}: fallback found nothing")
    return filled


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--set", action="append", default=[], metavar="SLOT=RANK",
                    help="change the chosen rank of one slot, e.g. S6-groove=2 (no re-run)")
    ap.add_argument("--index", default=INDEX_PATH)
    ap.add_argument("--plan", default=os.path.join(EP_DIR, "score_plan.json"))
    ap.add_argument("--fill-bass", action="store_true", help="run only the bass fallback on selection.json")
    args = ap.parse_args(argv)
    if args.fill_bass:
        sel = load_selection()
        with open(args.index, encoding="utf-8") as fh:
            entries = json.load(fh)["entries"]
        n = fill_empty_bass(sel, entries, log=lambda m: print(m, flush=True))
        with open(SELECTION_PATH, "w", encoding="utf-8") as fh:
            json.dump(sel, fh, indent=1, ensure_ascii=False)
        write_board(sel)
        print("bass fallback filled", n)
        return 0
    if args.set:
        sel = load_selection()
        for item in args.set:
            sid, rank = item.split("=")
            set_chosen(sel, sid, int(rank))
        with open(SELECTION_PATH, "w", encoding="utf-8") as fh:
            json.dump(sel, fh, indent=1, ensure_ascii=False)
        write_board(sel)
        print("chosen updated:", args.set)
        return 0
    with open(args.plan, encoding="utf-8") as fh:
        plan = json.load(fh)
    with open(args.index, encoding="utf-8") as fh:
        entries = json.load(fh)["entries"]
    os.makedirs(SOUND_DIR, exist_ok=True)
    selection = select_all(plan, entries, log=lambda m: print(m, flush=True))
    fill_empty_bass(selection, entries, log=lambda m: print(m, flush=True))
    errors = check_selection(selection)
    with open(SELECTION_PATH, "w", encoding="utf-8") as fh:
        json.dump(selection, fh, indent=1, ensure_ascii=False)
    write_board(selection)
    n_active = sum(1 for s in selection["slots"].values() if s["status"] == "active")
    n_opts = sum(len(s["options"]) for s in selection["slots"].values())
    print(f"slots {len(selection['slots'])} active {n_active} options {n_opts} errors {len(errors)}")
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
