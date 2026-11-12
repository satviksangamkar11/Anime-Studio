"""Animatic gate (A-05): A/B stills + a guide track -> one 24 fps MP4 per language, by ffmpeg concat only.

The owner watches these before any Colab go. No model call, no network.
"""
import os
import subprocess
from pathlib import Path

FPS = 24


def shots_to_entries(shots):
    """shots: [{"shot_id", "a": png, "b": png or None, "seconds": float}] -> [(png, seconds)].
    A holds the first half of the shot and B the second half; with no B, A holds the whole shot."""
    entries = []
    for s in shots:
        sec = float(s["seconds"])
        if sec <= 0:
            raise ValueError("%s: seconds must be > 0" % s.get("shot_id"))
        if s.get("b"):
            half = sec / 2
            entries.append((s["a"], half))
            entries.append((s["b"], sec - half))
        else:
            entries.append((s["a"], sec))
    return entries


def check_entries(entries):
    if not entries:
        raise ValueError("at least one still is required")
    for path, sec in entries:
        if sec <= 0:
            raise ValueError("%s: seconds must be > 0" % path)
        if not os.path.isfile(path):
            raise ValueError("missing still: %s" % path)


def _esc(path):
    return str(path).replace("\\", "/").replace("'", "'\\''")


def ffconcat_text(entries):
    """ffconcat list. The last still is repeated without a duration, as the concat demuxer needs."""
    lines = []
    for path, sec in entries:
        lines.append("file '%s'" % _esc(path))
        lines.append("duration %.3f" % sec)
    lines.append("file '%s'" % _esc(entries[-1][0]))
    return "\n".join(lines) + "\n"


def build_command(list_path, guide, out, fps=FPS):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(list_path)]
    if guide:
        cmd += ["-i", str(guide)]
    cmd += ["-r", str(fps), "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if guide:
        cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]
    cmd.append(str(out))
    return cmd


def make_animatic(entries, out, guide=None, runner=subprocess.run):
    check_entries(entries)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    list_path = out.parent / (out.stem + ".concat.txt")
    list_path.write_text(ffconcat_text(entries), encoding="utf-8")
    proc = runner(build_command(list_path, guide, out), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed for %s: %s" % (out.name, (proc.stderr or "").strip()))
    return out


def make_all(entries_by_lang, out_dir, guides=None, runner=subprocess.run):
    guides = guides or {}
    return {lang: make_animatic(entries, Path(out_dir) / ("animatic_%s.mp4" % lang),
                                guide=guides.get(lang), runner=runner)
            for lang, entries in entries_by_lang.items()}
