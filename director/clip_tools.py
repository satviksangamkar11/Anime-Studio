"""After a clip comes back: QA sheet (first / middle / last frame side by side + duration, frames, loudness) and continuity (the real last
frame becomes the next shot's start keyframe).
  python clip_tools.py qa clip.mp4 out_dir
  python clip_tools.py last clip.mp4 next_start.png"""
import json
import re
import subprocess
import sys
from pathlib import Path


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


USAGE = "usage: clip_tools.py qa CLIP OUT_DIR | last CLIP NEXT_START.png | (legacy) CLIP NEXT_START.png"


def main(argv=None):
    """G13: explicit subcommands. Any other first word is an error (it used to run the last-frame step by accident).
    Two arguments with no subcommand keep the old last-frame behaviour."""
    argv = list(sys.argv[1:] if argv is None else argv)
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
