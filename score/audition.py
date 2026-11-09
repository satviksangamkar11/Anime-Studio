"""Gate M0 auditions: stock numpy-synth sketches (no samples, no Ableton), for phone listening only.

Run from the repo root: python -m score.audition OUTDIR
  M0_1_themes.mp3                      sonic logo, then each bible theme alone (MAIN, KALI, SANDHYA, KAMADEVA, BRAHMA, SHIVA)
  M0_2_reel_sketch_70s.mp3             score/note_writer.py notes: reel 1 fixture plan + real cue sheet, exactly 70.0 s
  M0_3_reel_sketch_with_voice_en.mp4   reel 1 picture and audio, with M0_2 mixed 18 dB under it (video copied)
The timbres are temporary stand-ins; the real sound is made later in Ableton + Serum."""
import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from score import note_writer as nw

SR = 44100
PEAK = 10 ** (-1 / 20)  # -1 dBFS
SKETCH_DB = -18
SKETCH_S = 70.0
THEME_ORDER = ("MAIN", "KALI", "SANDHYA", "KAMADEVA", "BRAHMA", "SHIVA")
THEME_GAP_S = 1.0
THEME_TAIL_S = 1.5
THEME_VEL = 100
ROOT = Path(__file__).resolve().parents[1]
BIBLE = ROOT / "stories" / "kalika_puran_bhag1" / "music_bible.json"
CUE = ROOT / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "score" / "ep1" / "cue_sheet.json"
REEL_EXPORT = Path("D:/aai work/flow_outputs/anime_kalika_puran_bhag1/final_reel1_v3/export/kalika_reel1_en.mp4")


def midi_to_hz(pitch):
    return 440.0 * 2.0 ** ((pitch - 69) / 12.0)


def _mono(x):
    return x, x


def _env(n, sr, attack, release):
    t = np.arange(n) / sr
    dur = n / sr
    e = np.minimum(1.0, t / max(attack, 1e-3)) * np.minimum(1.0, (dur - t) / max(release, 1e-3))
    return np.clip(e, 0.0, 1.0)


def _lp(x, k):  # box filter: a cheap low-pass, enough for a sketch
    return np.convolve(x, np.ones(k) / k, mode="same")


def _saw(f, t, detune=(0.995, 1.0, 1.005)):
    return sum(2.0 * ((t * f * d) % 1.0) - 1.0 for d in detune) / len(detune)


def _drum(pitch, t, sr, rng):
    n = len(t)
    noise = rng.uniform(-1.0, 1.0, n)
    if pitch == 36:  # kick: sine sweep down
        f_t = 40 + 110 * np.exp(-25 * t)
        return 0.9 * np.sin(2 * np.pi * np.cumsum(f_t) / sr) * np.exp(-12 * t)
    if pitch in (38, 39):  # snare, clap: noise burst (+ body tone on the snare)
        body = 0.3 * np.sin(2 * np.pi * 190 * t) * np.exp(-30 * t) if pitch == 38 else 0.0
        return 0.5 * noise * np.exp(-(25 if pitch == 38 else 40) * t) + body
    if pitch in (42, 46):  # closed / open hat: high-passed noise
        hp = np.diff(noise, prepend=0.0)
        return 0.25 * hp * np.exp(-(60 if pitch == 42 else 25) * t)
    if pitch in (41, 47):  # folk toms
        f_t = (80 if pitch == 41 else 120) + 60 * np.exp(-10 * t)
        return 0.6 * np.sin(2 * np.pi * np.cumsum(f_t) / sr) * np.exp(-8 * t)
    return 0.4 * np.sin(2 * np.pi * midi_to_hz(pitch) * t) * np.exp(-10 * t)


def _voice(role, pitch, dur, sr, rng):
    """One note as (left, right) mono arrays. Velocity is applied by the caller."""
    n = max(1, int(round(dur * sr)))
    t = np.arange(n) / sr
    f = midi_to_hz(pitch)
    if role in ("drone", "pad"):  # soft detuned saw, low-passed; L and R detune differently for width
        left = _lp(_saw(f, t, (0.995, 1.0, 1.005)), 24) * _env(n, sr, 0.8, 1.0)
        right = _lp(_saw(f, t, (0.993, 1.002, 1.007)), 24) * _env(n, sr, 0.8, 1.0)
        return 0.22 * left, 0.22 * right
    if role == "bass":  # sine + saturated 2nd harmonic for phone speakers
        mid = 0.35 * np.tanh(4.0 * np.sin(2 * np.pi * 2 * f * t))
        return _mono(0.5 * (np.sin(2 * np.pi * f * t) + mid) * _env(n, sr, 0.01, 0.08))
    if role in ("brass", "horn"):  # dull saw
        return _mono(0.25 * _lp(_saw(f, t), 48) * _env(n, sr, 0.08, 0.2))
    if role in ("lead", "pluck"):  # pluck
        w = np.sin(2 * np.pi * f * t) * np.exp(-9 * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-14 * t)
        return _mono(0.5 * w * _env(n, sr, 0.005, 0.15))
    if role == "piano":  # decaying sine with 2nd harmonic
        w = np.sin(2 * np.pi * f * t) * np.exp(-3 * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-6 * t)
        return _mono(0.5 * w * _env(n, sr, 0.005, 0.1))
    if role == "vocal":  # TEMPORARY formant-ish stand-in: saw + two fixed formant tones
        w = _lp(_saw(f, t), 8) + 0.25 * np.sin(2 * np.pi * 700 * t) + 0.15 * np.sin(2 * np.pi * 1200 * t)
        return _mono(0.3 * w * _env(n, sr, 0.05, 0.2))
    if role == "risers":  # rising sine sweep, one octave over the note (no noise)
        phase = 2 * np.pi * f * (t + t * t / (2 * max(dur, 1e-3)))
        return _mono(0.3 * np.sin(phase) * _env(n, sr, 0.3, 0.05))
    if role == "hits":  # low sine thump with a short pitch drop
        f_t = f * (1 + 2 * np.exp(-30 * t))
        return _mono(0.8 * np.sin(2 * np.pi * np.cumsum(f_t) / sr) * np.exp(-8 * t) * _env(n, sr, 0.002, 0.05))
    if role in ("drums", "folk_perc"):
        return _mono(_drum(pitch, t, sr, rng) * _env(n, sr, 0.001, 0.01))
    return _mono(0.3 * np.sin(2 * np.pi * f * t) * _env(n, sr, 0.01, 0.1))


def render_notes(tracks, total_s, sr=SR):
    """Stereo float array (n, 2) of all notes. Peak normalised to -1 dBFS; no notes gives silence."""
    n_total = int(round(total_s * sr))
    out = np.zeros((n_total, 2))
    rng = np.random.RandomState(1234)  # fixed seed: same notes, same drums
    for role in sorted(tracks or {}):
        for note in tracks[role] or []:
            pitch = note.get("pitch")
            dur = float(note.get("dur_s", 0.0))
            if pitch is None or dur <= 0:
                continue
            start = int(round(float(note["t_s"]) * sr))
            left, right = _voice(role, int(pitch), dur, sr, rng)
            if start < 0:
                left, right, start = left[-start:], right[-start:], 0
            m = min(len(left), n_total - start)
            if m <= 0:
                continue
            gain = min(1.0, max(0.0, float(note.get("vel", THEME_VEL)) / 127.0))
            out[start:start + m, 0] += gain * left[:m]
            out[start:start + m, 1] += gain * right[:m]
    peak = float(np.abs(out).max()) if n_total else 0.0
    if peak > 0:
        out *= PEAK / peak
    return out


def _fixture_feels():
    from score.tests.test_note_writer import REEL_PLAN  # the fixture plan, imported not copied
    feels = {}
    for ev in sorted(REEL_PLAN["events"], key=lambda e: e["at_s"]):
        if ev.get("type") == "theme_entry":
            feels.setdefault(ev["theme"], ev.get("feel", "normal"))
    return feels


def theme_tracks(bible):
    """Sonic logo, then each theme alone with a gap. A theme's feel is its first fixture entry (else normal).
    Returns (tracks, total_s). One beat is 1 s (60 BPM), so a note lasts FEEL_STEP seconds."""
    feels = _fixture_feels()
    logo = bible["sonic_logo"]
    tracks = {}
    logo_notes = sorted({nw.note_to_midi(x) for x in re.findall(r"(?<![A-Za-z])([A-G][#b]?-?\d+)(?!\d)", str(logo["notes"]))} - {None})
    tracks[logo["role"]] = [{"t_s": 0.0, "dur_s": float(logo["length_s"]), "pitch": p, "vel": 110} for p in logo_notes]
    t = float(logo["length_s"]) + THEME_GAP_S
    for name in THEME_ORDER:
        theme = bible["themes"][name]
        role = theme["roles"][0]
        step = nw.FEEL_STEP[feels.get(name, "normal")]
        for tok in theme["degrees"].split():
            pitch = nw.note_to_midi(tok)
            if pitch is None:
                raise ValueError(f"theme {name}: unreadable note {tok!r}")
            tracks.setdefault(role, []).append({"t_s": t, "dur_s": 0.9 * step, "pitch": pitch, "vel": THEME_VEL})
            t += step
        t += THEME_GAP_S
    return tracks, t + THEME_TAIL_S


def reel_sketch_tracks():
    from score.tests.test_note_writer import REEL_PLAN  # the fixture plan, imported not copied
    cue = json.loads(CUE.read_text(encoding="utf-8"))
    bible = json.loads(BIBLE.read_text(encoding="utf-8"))
    rep = nw.write_notes(REEL_PLAN, cue, bible)
    if not rep["ok"]:
        raise RuntimeError(f"write_notes failed: {rep['errors']}")
    return rep["tracks"]


def _run(cmd, **kw):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + cmd, check=True, **kw)


def encode_mp3(buf, path):
    pcm = (np.clip(buf, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    _run(["-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", str(path)],
         input=pcm)


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def reel_mix(sketch_mp3, out_mp4, reel=REEL_EXPORT):
    fc = f"[1:a]volume={SKETCH_DB}dB[s];[0:a][s]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
    _run(["-i", str(reel), "-i", str(sketch_mp3), "-filter_complex", fc, "-map", "0:v:0", "-map", "[a]",
          "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_mp4)])


def build(out_dir):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg/ffprobe not on PATH")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bible = json.loads(BIBLE.read_text(encoding="utf-8"))
    tracks, total = theme_tracks(bible)
    p1 = out_dir / "M0_1_themes.mp3"
    encode_mp3(render_notes(tracks, total), p1)
    p2 = out_dir / "M0_2_reel_sketch_70s.mp3"
    encode_mp3(render_notes(reel_sketch_tracks(), SKETCH_S), p2)
    p3 = out_dir / "M0_3_reel_sketch_with_voice_en.mp4"
    reel_mix(p2, p3)
    return [p1, p2, p3]


def plan_cue(plan, cue):
    """The cue the notes are written against. A variant A plan (window_s [0, end]) gets the cue cut to that window:
    total_s = end, shots, cuts, voice union and impacts clipped to it, no re-hook or end-hook windows. Else the cue itself.
    Returns (cue, window_end or None)."""
    win = plan.get("window_s")
    if not (isinstance(win, list) and len(win) == 2):
        return cue, None
    end = float(win[1])
    c = copy.deepcopy(cue)
    c["total_s"] = end
    c["shots"] = [dict(s, end_s=min(float(s["end_s"]), end),
                       impacts=[i for i in s.get("impacts", []) if float(i["at_s"]) < end])
                  for s in cue["shots"] if float(s["start_s"]) < end]
    c["cuts"] = [x for x in cue["cuts"] if float(x["at_s"]) < end]
    c["voice"] = dict(cue["voice"], union=[[a, min(float(b), end)] for a, b in cue["voice"]["union"] if float(a) < end])
    c["retention"] = {"rehook_window_s": None, "end_hook_window_s": None,
                      "last_speech_end_s": None, "last_voice_end_s": None}
    return c, end


def build_plan(out_dir, plan_path=None, cue_path=None, reel=None, out_prefix=None, clip_s=None, phone=False):
    """Sketch audio (and, with reel, a picture mix) from one plan's notes. Returns the written paths.
    No plan: the frozen REEL_PLAN fixture. No cue: the live v4 cue sheet. Length: clip_s, else the window end, else total_s."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg/ffprobe not on PATH")
    if plan_path is None:
        from score.tests.test_note_writer import REEL_PLAN
        plan = REEL_PLAN
    else:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    cue_full = json.loads(Path(cue_path or CUE).read_text(encoding="utf-8"))
    bible = json.loads(BIBLE.read_text(encoding="utf-8"))
    cue_used, window_end = plan_cue(plan, cue_full)
    rep = nw.write_notes(plan, cue_used, bible)
    if not rep["ok"]:
        raise RuntimeError(f"write_notes failed: {rep['errors']}")
    length = clip_s or window_end or float(cue_full["total_s"])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_prefix or "sketch"
    mp3 = out_dir / f"{prefix}.mp3"
    encode_mp3(render_notes(rep["tracks"], length), mp3)
    paths = [mp3]
    if reel:
        mix = out_dir / f"{prefix}_with_voice_en.mp4"
        reel_mix(mp3, mix, Path(reel))
        if phone:  # phone copy (540 wide), then the full-size mix is deleted to save disk
            small = out_dir / f"{prefix}_with_voice_en_small.mp4"
            _run(["-i", str(mix), "-vf", "scale=540:-2", "-c:v", "libx264", "-crf", "27", "-preset", "veryfast",
                  "-c:a", "aac", "-b:a", "128k", str(small)])
            mix.unlink()
            paths.append(small)
        else:
            paths.append(mix)
    return paths


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 1 and not args[0].startswith("-"):  # the old form: OUTDIR only, unchanged output
        for p in build(args[0]):
            print(f"{p} {probe_duration(p):.3f}s")
        return 0
    p = argparse.ArgumentParser(prog="python -m score.audition",
                                description="Audition sketches. OUTDIR alone builds the M0 set; the options build one plan's sketch.")
    p.add_argument("outdir")
    p.add_argument("--plan", help="score_plan.json (variant A cuts to its window_s)")
    p.add_argument("--cue-sheet", help="cue_sheet.json (default: the live v4 sheet)")
    p.add_argument("--reel", help="reel mp4 to mix the sketch under (no mix without it)")
    p.add_argument("--out-prefix", help="file name base for the outputs")
    p.add_argument("--clip-s", type=float, help="render length in seconds (default: window end or the reel length)")
    p.add_argument("--phone", action="store_true", help="with --reel: make the 540 px phone copy and delete the full mix")
    a = p.parse_args(args)
    for path in build_plan(a.outdir, a.plan, a.cue_sheet, a.reel, a.out_prefix, a.clip_s, a.phone):
        print(f"{path} {probe_duration(path):.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
