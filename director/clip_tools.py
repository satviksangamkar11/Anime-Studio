"""After a clip comes back: QA sheet (first / middle / last frame side by side + duration, frames, loudness) and continuity (the real last
frame becomes the next shot's start keyframe).
  python clip_tools.py qa clip.mp4 out_dir
  python clip_tools.py last clip.mp4 next_start.png"""
import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.append(str(_REPO))   # core/ lives at the repo root; imported lazily by gates()


def probe(clip):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
                        "-show_entries", "format=duration", "-of", "json", str(clip)], capture_output=True, text=True, check=True)
    info = json.loads(r.stdout)
    v = info["streams"][0]
    seconds = float(info["format"]["duration"])
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    frames = int(v["nb_frames"]) if v.get("nb_frames") else round(seconds * num / den)   # webm/mkv may omit nb_frames
    return {"width": v["width"], "height": v["height"], "fps": v["r_frame_rate"], "frames": frames, "seconds": round(seconds, 3)}


def loudness(clip):
    r = subprocess.run(["ffmpeg", "-i", str(clip), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    found = dict(re.findall(r"(mean_volume|max_volume): (-?[\d.]+) dB", r.stderr))
    return {k: float(v) for k, v in found.items()}


def qa(clip, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    info = probe(clip)
    n = info["frames"]
    sheet = out / f"{Path(clip).stem}_first_mid_last.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vf",
                    f"select='eq(n\\,0)+eq(n\\,{n // 2})+eq(n\\,{n - 1})',scale=480:-1,tile=3x1", "-frames:v", "1", str(sheet)], check=True)
    report = {**info, **loudness(clip), "sheet": str(sheet)}
    (out / f"{Path(clip).stem}_qa.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def last_frame(clip, png):
    # -update 1 overwrites the PNG with every decoded frame from 0.5 s before the end, so the true last frame remains
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.5", "-i", str(clip), "-update", "1", str(png)], check=True)
    return png


# ---- clip gates (WP6): G2 luma/drift, G6 pure white, G7 focal box. F1/F2/G3/G5 run on the episode in post.py. ----
GATE_SAT_PROVISIONAL = 181.02   # A18: unverified reviewer ceiling, used only while gates.sat_avg_ceiling is null


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _range2(v):
    return isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v) and v[0] <= v[1]


def _gate_entry(rule, level, message, shot_id=None):
    return {"rule": rule, "level": level, "shot": shot_id, "episode": None, "message": message}


def _read_json_obj(source, label, entries):
    """A dict from a dict or a JSON file path. A problem appends a P0 FAIL and returns None."""
    if isinstance(source, dict):
        return source
    if not isinstance(source, (str, Path)):
        entries.append(_gate_entry("P0", "FAIL", f"{label}: expected a path or an object"))
        return None
    try:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    except OSError as exc:
        entries.append(_gate_entry("P0", "FAIL", f"{label} unreadable: {exc}"))
        return None
    except ValueError as exc:
        entries.append(_gate_entry("P0", "FAIL", f"{label} is not valid JSON: {exc}"))
        return None
    if not isinstance(data, dict):
        entries.append(_gate_entry("P0", "FAIL", f"{label} must be a JSON object"))
        return None
    return data


def _gate_checks(clip, shot, story, styles_dir, entries):
    from PIL import Image

    from core.frame_metrics import (extract_frames, mean_lab, outside_region_lstar, per_frame_stats,
                                    region_lstar, white_share)
    from core.style_pack import delta_e_2000, load_core, load_pack

    core = load_core()
    fps, gcfg = core["fps"], core["gates"]
    shot_id = shot.get("id") if isinstance(shot.get("id"), str) else None

    def add(rule, level, message):
        entries.append(_gate_entry(rule, level, message, shot_id))

    if not isinstance(story.get("style_pack"), str):
        add("P0", "FAIL", "story.json needs a string style_pack")
        return
    try:
        pack = load_pack(story["style_pack"], styles_dir=styles_dir)
    except ValueError as exc:
        add("P0", "FAIL", f"style pack unusable: {exc}")
        return
    frame_law = pack.get("frame_law") if isinstance(pack.get("frame_law"), dict) else {}
    acts = pack.get("acts") if isinstance(pack.get("acts"), dict) else {}

    look = shot.get("look")
    if look is None and isinstance(shot.get("metadata"), dict):
        look = shot["metadata"].get("look")
    if look is None:
        add("G2", "WARN", "no look block: act ranges skipped")
        look = {}
    elif not isinstance(look, dict):
        add("P0", "FAIL", "look must be an object")
        look = {}

    trim = 0
    timing = shot.get("timing_and_lattice")
    if isinstance(timing, dict) and "trim_in_frame" in timing:
        if isinstance(timing["trim_in_frame"], int) and not isinstance(timing["trim_in_frame"], bool) \
                and timing["trim_in_frame"] >= 0:
            trim = timing["trim_in_frame"]
        else:
            add("P0", "FAIL", "timing_and_lattice.trim_in_frame must be an integer >= 0")

    exempt = set()
    impacts = look.get("impact_frames", [])
    if not isinstance(impacts, list):
        add("P0", "FAIL", "look.impact_frames must be a list")
        impacts = []
    for i, imp in enumerate(impacts):
        if not (isinstance(imp, dict) and _num(imp.get("at_s")) and imp["at_s"] >= 0
                and isinstance(imp.get("frames"), int) and not isinstance(imp.get("frames"), bool)
                and imp["frames"] >= 0):
            add("P0", "FAIL", f"look.impact_frames[{i}] needs at_s >= 0 and integer frames >= 0")
            continue
        start = round(imp["at_s"] * fps) + trim
        exempt.update(range(start, start + imp["frames"] + 1))

    act_name = look.get("act")
    act = acts.get(act_name) if act_name is not None else None
    if act_name is not None and not isinstance(act, dict):
        add("G2", "WARN", f"act {act_name!r} not in pack: act ranges skipped")
        act = None

    if not clip.is_file():
        add("G2", "FAIL", f"clip not found: {clip.name}")
        return
    try:
        stats = per_frame_stats(clip)
    except RuntimeError as exc:
        add("G2", "FAIL", f"could not read clip frames: {exc}")
        return
    if not stats:
        add("G2", "FAIL", "clip has no decodable frames")
        return

    # G2 luma step: FAIL on undeclared jumps; at most 5 frames listed, then a summary.
    ys = [s["YAVG"] / 255.0 for s in stats]
    step_max = gcfg["g2_luma_step_max"]
    over = [(k, abs(ys[k] - ys[k - 1])) for k in range(1, len(ys))
            if abs(ys[k] - ys[k - 1]) > step_max and k not in exempt]
    for k, step in over[:5]:
        add("G2", "FAIL", f"frame {k}: luma step {step:.3f} exceeds {step_max} outside declared impacts")
    if len(over) > 5:
        add("G2", "FAIL", f"{len(over) - 5} more luma-step FAIL frames not listed (total {len(over)})")

    if act is not None:
        mean_y = sum(ys) / len(ys)
        lm = act.get("luma_mean")
        if not _range2(lm):
            add("P0", "FAIL", f"act {act_name}.luma_mean must be [lo, hi]")
        elif not lm[0] <= mean_y <= lm[1]:
            add("G2", "WARN", f"mean luma {mean_y:.3f} outside act {act_name} range {lm}")
        ceiling = gcfg.get("sat_avg_ceiling")
        if ceiling is None:
            add("G2", "WARN", f"sat_avg_ceiling unset: provisional {GATE_SAT_PROVISIONAL}")
            ceiling = GATE_SAT_PROVISIONAL
        elif not _num(ceiling) or ceiling <= 0:
            add("P0", "FAIL", "gates.sat_avg_ceiling must be a positive number")
            ceiling = GATE_SAT_PROVISIONAL
        sm = act.get("sat_mean")
        mean_sat = sum(s.get("SATAVG", 0.0) for s in stats) / len(stats) / ceiling
        if not _range2(sm):
            add("P0", "FAIL", f"act {act_name}.sat_mean must be [lo, hi]")
        elif not sm[0] <= mean_sat <= sm[1]:
            add("G2", "WARN", f"mean sat {mean_sat:.3f} outside act {act_name} range {sm}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)   # one sub-folder per extraction: extract_frames counts only new files
        try:
            first = extract_frames(clip, tmp / "first", scale=0.5, every=1, start=0, count=1)
            last = extract_frames(clip, tmp / "last", scale=0.5, every=1, start=len(stats) - 1, count=1)
            samples = extract_frames(clip, tmp / "samples", scale=0.5, every=6)
        except RuntimeError as exc:
            add("G2", "FAIL", f"could not extract frames: {exc}")
            return
        if not first or not last:
            add("G2", "FAIL", "could not extract first or last frame")
            return
        with Image.open(first[0][1]) as im:
            lab_first = mean_lab(im)
        with Image.open(last[0][1]) as im:
            lab_last = mean_lab(im)
        drift = delta_e_2000(lab_first, lab_last)
        if drift > gcfg["g2_drift_de2000_max"]:
            add("G2", "WARN", f"first-vs-last frame drift dE2000 {drift:.2f} exceeds {gcfg['g2_drift_de2000_max']}")

        # G6 (WARN): pure-white share on sampled frames outside declared impact frames.
        cap = frame_law.get("pure_white_area_cap_frac")
        if not _num(cap):
            add("G6", "WARN", "frame_law.pure_white_area_cap_frac missing: G6 skipped")
        else:
            worst = None
            for idx, path in samples:
                if idx in exempt:
                    continue
                with Image.open(path) as im:
                    share = white_share(im)
                if worst is None or share > worst[1]:
                    worst = (idx, share)
            if worst is not None and worst[1] > cap:
                add("G6", "WARN", f"frame {worst[0]}: pure-white area {worst[1]:.3f} exceeds cap {cap}")

        # G7 (WARN): focal box must differ from the rest by min_dL, and be the extreme in focal_value's direction.
        box = look.get("focal_box")
        if box is None:
            return
        if not (isinstance(box, list) and len(box) == 4 and all(_num(v) and 0 <= v <= 1 for v in box)
                and box[0] < box[2] and box[1] < box[3]):
            add("P0", "FAIL", "look.focal_box must be [x0, y0, x1, y1] fractions with x0 < x1 and y0 < y1")
            return
        min_dl = frame_law.get("min_dL_focal_vs_bg")
        if not _num(min_dl):
            return
        fv = look.get("focal_value")
        check_dir = fv in ("lightest", "darkest")
        if not check_dir:
            add("G7", "WARN", "look.focal_value must be lightest or darkest: direction not checked")
        worst_gap = None
        worst_dir = None
        for idx, path in samples:
            with Image.open(path) as im:
                inside = region_lstar(im, box)
                outside = outside_region_lstar(im, box)
            if outside is None:
                add("G7", "WARN", "focal_box covers the whole frame: G7 cannot compare")
                break
            gap = abs(inside - outside)
            if worst_gap is None or gap < worst_gap[1]:
                worst_gap = (idx, gap)
            if check_dir and worst_dir is None and ((fv == "lightest" and inside <= outside)
                                                    or (fv == "darkest" and inside >= outside)):
                worst_dir = (idx, inside, outside)
        if worst_gap is not None and worst_gap[1] < min_dl:
            add("G7", "WARN", f"frame {worst_gap[0]}: focal box dL* {worst_gap[1]:.1f} below minimum {min_dl}")
        if worst_dir is not None:
            idx, inside, outside = worst_dir
            add("G7", "WARN", f"frame {idx}: focal box is not the {fv} part of the frame "
                              f"(box L* {inside:.1f}, rest {outside:.1f})")


def _gate_report(clip, entries, out_dir):
    report = {"clip": str(clip), "fail": any(e["level"] == "FAIL" for e in entries), "entries": entries}
    out = Path(out_dir) if out_dir is not None else clip.parent
    path = out / f"{clip.stem}_gates.json"
    try:
        out.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    except OSError as exc:
        entries.append(_gate_entry("P0", "FAIL", f"could not write {path.name}: {exc}"))
        report["fail"] = True
    return report


def gates(clip, shot, story_path, out_dir=None, styles_dir=None):
    """G2, G6, G7 on one clip. shot / story_path: a JSON path or an already-loaded dict.
    Writes <clip stem>_gates.json to out_dir (default: next to the clip) and returns
    {"clip", "fail", "entries"}. Never raises on bad input: problems become FAIL/WARN entries."""
    clip = Path(clip)
    entries = []
    shot_obj = _read_json_obj(shot, "shot.json", entries)
    story_obj = _read_json_obj(story_path, "story.json", entries)
    if shot_obj is not None and story_obj is not None:
        _gate_checks(clip, shot_obj, story_obj, styles_dir, entries)
    return _gate_report(clip, entries, out_dir)


def _gates_cli(argv):
    p = argparse.ArgumentParser(prog="clip_tools.py gates")
    p.add_argument("clip")
    p.add_argument("--shot", required=True)
    p.add_argument("--story", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--styles-dir", default=None)
    try:
        ns = p.parse_args(argv)
    except SystemExit:
        return 2
    report = gates(ns.clip, ns.shot, ns.story, out_dir=ns.out, styles_dir=ns.styles_dir)
    print(json.dumps(report, indent=1))
    return 1 if report["fail"] else 0


USAGE = ("usage: clip_tools.py qa CLIP OUT_DIR | last CLIP NEXT_START.png | "
         "gates CLIP --shot shot.json --story story.json [--out DIR] [--styles-dir DIR] | "
         "(legacy) CLIP NEXT_START.png")


def main(argv=None):
    """G13: explicit subcommands. Any other first word is an error (it used to run the last-frame step by accident).
    Two arguments with no subcommand keep the old last-frame behaviour."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "gates":
        return _gates_cli(argv[1:])
    if len(argv) == 3 and argv[0] == "qa":
        print(json.dumps(qa(argv[1], argv[2]), indent=1))
    elif len(argv) == 3 and argv[0] == "last":
        print(last_frame(argv[1], argv[2]))
    elif len(argv) == 2:
        print(last_frame(argv[0], argv[1]))
    else:
        print(USAGE, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
