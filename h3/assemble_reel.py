"""Build the ffmpeg assembly plan for a set of lint-clean shots. Never runs ffmpeg."""
import json
import math
import os
import tempfile
from pathlib import Path

from PIL import Image

from core.frame_metrics import extract_frames, mean_lab
from core.style_pack import delta_e_2000, load_core

_AUDIO = load_core()["delivery"]["audio"]   # one loudness standard: core/core.json delivery.audio (owner 2026-11-07)
TARGET_LUFS = _AUDIO["lufs"]
TRUE_PEAK_DB = _AUDIO["true_peak_db"]
G3_WINDOW = 6  # frames per edge window (spec G3: last 6 vs first 6 editorial frames)
_CLIP_ERRORS = (RuntimeError, ValueError, OSError, KeyError, TypeError)


def loudness_plan(measured, target_lufs=TARGET_LUFS, true_peak_db=TRUE_PEAK_DB):
    """Pure: measured maps clip name -> integrated LUFS; returns clip -> {"gain_db", "limit"} (linear gain
    to target_lufs, true-peak limit as a linear factor). ValueError on a missing or non-finite value."""
    limit = round(10 ** (true_peak_db / 20), 4)
    plan = {}
    for clip, lufs in measured.items():
        if isinstance(lufs, bool) or not isinstance(lufs, (int, float)) or not math.isfinite(lufs):
            raise ValueError(f"measured loudness for {clip!r} is missing or not finite: {lufs!r}")
        plan[clip] = {"gain_db": round(target_lufs - lufs, 2), "limit": limit}
    return plan


def _audio_chain(idx, t, loud):
    """Without loud (or for a clip with no gain) this is the original chain, byte for byte. With loud the gain
    and limiter come before the 5 ms fades, so the fades are applied after the gain at every cut."""
    gain = f",volume={loud['gain_db']}dB,alimiter=limit={loud['limit']}:level=disabled" if loud else ""
    return (f"[{idx}:a]atrim=start={t['trim_in_sec']:.2f}:end={t['trim_out_sec']:.2f},asetpts=PTS-STARTPTS{gain},"
            f"afade=t=in:st=0:d=0.005,afade=t=out:st={t['editorial_duration_sec'] - 0.005:.3f}:d=0.005[a{idx}]")


def build_ffmpeg_assembly_plan(shots, output_mp4, loudness=None):
    """loudness: optional loudness_plan() output keyed by shot_id (the clip name). Shots without an entry keep
    the original audio chain. The video tail is scaled to the delivery colour matrix and range (section 3.1)."""
    delivery = load_core()["delivery"]
    fps = shots[0]["timing_and_lattice"]["fps"]
    chains, cum, seams = [], 0, []
    for idx, s in enumerate(shots):
        t = s["timing_and_lattice"]
        chains.append(f"[{idx}:v]trim=start_frame={t['trim_in_frame']}:end_frame={t['trim_out_frame']},"
                      f"setpts=PTS-STARTPTS[v{idx}]")
        chains.append(_audio_chain(idx, t, (loudness or {}).get(s["shot_id"])))
        cum += t["editorial_frames"]
        if idx + 1 < len(shots):
            nxt = shots[idx + 1]
            a, b = s["continuity_and_seam_lock"]["cut_out_pose_vector"], nxt["continuity_and_seam_lock"]["cut_in_pose_vector"]
            seams.append({"from_shot": s["shot_id"], "to_shot": nxt["shot_id"], "frame": cum,
                          "outgoing_seam_type": s["continuity_and_seam_lock"]["outgoing_seam_type"],
                          "incoming_seam_type": nxt["continuity_and_seam_lock"]["incoming_seam_type"],
                          "pose_delta": {k: round(b[k] - a[k], 3) for k in ("torso_pitch_deg", "knee_flex_deg", "com_y_ratio")}})
    n = len(shots)
    concat = ("".join(f"[v{i}][a{i}]" for i in range(n))
              + f"concat=n={n}:v=1:a=1[vcat][aout];"
              + f"[vcat]scale=out_color_matrix={delivery['colorspace']}:out_range={delivery['color_range']}[vout]")
    return {"filter_complex": ";".join(chains) + ";" + concat, "n_shots": n, "fps": fps,
            "output": output_mp4, "total_frames": cum, "total_duration_sec": round(cum / fps, 2),
            "seam_transitions": seams, "colour_seams": [], "colour_seams_note": NO_CLIPS_NOTE}


NO_CLIPS_NOTE = "no clips yet: G3 not run"


def write_assembly_script(plan, clip_paths, out_dir):
    """Writes filter.txt and assemble.cmd into out_dir. Does not run ffmpeg."""
    if len(clip_paths) != plan["n_shots"]:
        raise ValueError(f"expected {plan['n_shots']} clips, got {len(clip_paths)}")
    d = load_core()["delivery"]
    encode = (f"-c:v {d['codec']} -crf {d['crf']} -pix_fmt {d['pix_fmt']} -colorspace {d['colorspace']} "
              f"-color_primaries {d['color_primaries']} -color_trc {d['color_trc']} -color_range {d['color_range']} "
              f"-c:a {d['audio']['codec']} -b:a {d['audio']['bitrate']} -movflags +faststart")
    os.makedirs(out_dir, exist_ok=True)
    filter_path = os.path.join(out_dir, "filter.txt")
    with open(filter_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(plan["filter_complex"])
    inputs = " ".join(f'-i "{p}"' for p in clip_paths)
    cmd = ("@echo off\r\nchcp 65001 >nul\r\ncd /d \"%~dp0\"\r\n"
           f"ffmpeg -y {inputs} -filter_complex_script filter.txt -map \"[vout]\" -map \"[aout]\" "
           f"-r {plan['fps']} {encode} \"{plan['output']}\"\r\n")
    cmd_path = os.path.join(out_dir, "assemble.cmd")
    with open(cmd_path, "w", encoding="utf-8", newline="") as f:
        f.write(cmd)
    return {"cmd": cmd_path, "filter": filter_path}


def write_loudness_json(path, measured, plan, target_lufs=TARGET_LUFS, true_peak_db=TRUE_PEAK_DB):
    """Audit record: measured LUFS, gain and limit per clip, plus the target. Does not run ffmpeg."""
    doc = {"target_lufs": target_lufs, "true_peak_db": true_peak_db,
           "clips": {clip: {"measured_lufs": measured[clip], "gain_db": plan[clip]["gain_db"],
                            "limit": plan[clip]["limit"]} for clip in measured}}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    return path


def _finite_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def load_loudness_plan(path):
    """-> {clip: {"gain_db", "limit"}} read from a loudness.json (write_loudness_json format), or None when the
    file is absent. ValueError (message names loudness.json) when the file is corrupt or has the wrong shape."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        raise ValueError(f"loudness.json at {path} is unreadable: {exc}") from exc
    clips = doc.get("clips") if isinstance(doc, dict) else None
    if not isinstance(clips, dict):
        raise ValueError(f"loudness.json at {path} has no 'clips' object")
    out = {}
    for clip, v in clips.items():
        if not isinstance(v, dict) or not _finite_num(v.get("gain_db")) or not _finite_num(v.get("limit")):
            raise ValueError(f"loudness.json at {path}: clip {clip!r} needs numeric gain_db and limit")
        out[clip] = {"gain_db": v["gain_db"], "limit": v["limit"]}
    return out


# ---- G3 colour seams ----

def _g3(shot, episode, message):
    return {"rule": "G3", "level": "FAIL", "shot": shot, "episode": episode, "message": message}


def _shot_id(shot):
    return shot.get("shot_id") if isinstance(shot, dict) else None


def _episode(shot):
    return shot.get("episode_id") if isinstance(shot, dict) else None


def _act(shot):
    meta = shot.get("metadata") if isinstance(shot, dict) else None
    look = meta.get("look") if isinstance(meta, dict) else None
    return look.get("act") if isinstance(look, dict) else None


def _editorial_window(shot):
    """(trim_in, trim_out) frames of the clip file; ValueError when they cannot hold a G3 window."""
    t = shot["timing_and_lattice"]
    ti, to = t["trim_in_frame"], t["trim_out_frame"]
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (ti, to)) or ti < 0:
        raise ValueError(f"trim_in_frame/trim_out_frame must be ints with trim_in >= 0: {ti!r}, {to!r}")
    if to - ti < G3_WINDOW:
        raise ValueError(f"editorial length {to - ti} frames is shorter than the {G3_WINDOW}-frame G3 window")
    return ti, to


def _window_lab(clip, start, work_dir):
    frames = extract_frames(clip, work_dir, scale=0.25, start=start, count=G3_WINDOW)
    if len(frames) != G3_WINDOW:
        raise ValueError(f"only {len(frames)} of {G3_WINDOW} frames at clip frame {start}")
    labs = []
    for _, p in frames:
        with Image.open(p) as im:
            labs.append(mean_lab(im.convert("RGB")))
    return tuple(sum(lab[i] for lab in labs) / len(labs) for i in range(3))


def colour_seams(clip_paths, shots, core=None):
    """G3: for every cut N -> N+1 (skipped when look.act changes) compare the mean Lab of the last 6 editorial
    frames of clip N with the first 6 of clip N+1. dE2000 above gates.g3_cut_jump_de2000_max is a FAIL.
    Missing, short or unreadable clips are FAIL entries naming the clip. Never raises on bad input."""
    core = load_core() if core is None else core
    limit = core["gates"]["g3_cut_jump_de2000_max"]
    if len(clip_paths) != len(shots):
        return [_g3(None, None, f"G3 needs one clip per shot: got {len(clip_paths)} clips for {len(shots)} shots")]
    entries, cache, reported = [], {}, set()

    def edge(idx, which, work):
        """(lab, None) or (None, reason) for the tail (last window) or head (first window) of clip idx."""
        key = (idx, which)
        if key not in cache:
            clip, shot = clip_paths[idx], shots[idx]
            if not os.path.isfile(clip):
                cache[key] = (None, f"clip missing: {clip}")
            else:
                try:
                    ti, to = _editorial_window(shot)
                    start = to - G3_WINDOW if which == "tail" else ti
                    cache[key] = (_window_lab(clip, start, os.path.join(work, f"{idx}_{which}")), None)
                except _CLIP_ERRORS as exc:
                    cache[key] = (None, f"clip {clip} cannot be checked: {exc}")
        return cache[key]

    def report(idx, which, reason):
        if (idx, which) not in reported:
            reported.add((idx, which))
            entries.append(_g3(_shot_id(shots[idx]), _episode(shots[idx]), reason))

    with tempfile.TemporaryDirectory() as work:
        for k in range(len(shots) - 1):
            a, b = shots[k], shots[k + 1]
            if _act(a) != _act(b):
                continue
            tail, why_a = edge(k, "tail", work)
            head, why_b = edge(k + 1, "head", work)
            if why_a or why_b:
                if why_a:
                    report(k, "tail", why_a)
                if why_b:
                    report(k + 1, "head", why_b)
                continue
            de = delta_e_2000(tail, head)
            if de > limit:
                ida, idb = _shot_id(a), _shot_id(b)
                entries.append(_g3(ida, _episode(a), f"cut jump dE {de:.2f} > {limit:g} between {ida} and {idb}"))
    return entries


def attach_colour_seams(plan, clip_paths, shots, core=None):
    """Sets plan["colour_seams"] from colour_seams() when every clip file exists; otherwise an empty list and
    the 'no clips yet' note. Returns the same plan dict."""
    if all(os.path.isfile(p) for p in clip_paths):
        plan["colour_seams"] = colour_seams(clip_paths, shots, core)
        plan.pop("colour_seams_note", None)
    else:
        plan["colour_seams"] = []
        plan["colour_seams_note"] = NO_CLIPS_NOTE
    return plan
