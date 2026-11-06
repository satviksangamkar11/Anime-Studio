"""Build the ffmpeg assembly plan for a set of lint-clean shots. Never runs ffmpeg."""
import json
import math
import os

TARGET_LUFS = -16.0
TRUE_PEAK_DB = -1.5


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
    the original audio chain."""
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
    concat = "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vout][aout]"
    return {"filter_complex": ";".join(chains) + ";" + concat, "n_shots": n, "fps": fps,
            "output": output_mp4, "total_frames": cum, "total_duration_sec": round(cum / fps, 2),
            "seam_transitions": seams}


def write_assembly_script(plan, clip_paths, out_dir):
    """Writes filter.txt and assemble.cmd into out_dir. Does not run ffmpeg."""
    if len(clip_paths) != plan["n_shots"]:
        raise ValueError(f"expected {plan['n_shots']} clips, got {len(clip_paths)}")
    os.makedirs(out_dir, exist_ok=True)
    filter_path = os.path.join(out_dir, "filter.txt")
    with open(filter_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(plan["filter_complex"])
    inputs = " ".join(f'-i "{p}"' for p in clip_paths)
    cmd = ("@echo off\r\nchcp 65001 >nul\r\ncd /d \"%~dp0\"\r\n"
           f"ffmpeg -y {inputs} -filter_complex_script filter.txt -map \"[vout]\" -map \"[aout]\" "
           f"-r {plan['fps']} \"{plan['output']}\"\r\n")
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
