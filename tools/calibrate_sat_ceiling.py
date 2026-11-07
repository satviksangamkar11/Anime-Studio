"""Sets gates.sat_avg_ceiling in core/core.json from owner-approved reference frames or clips (A26).
usage: python tools/calibrate_sat_ceiling.py FILE [FILE ...] [--percentile 99] [--write] [--core PATH]
The ceiling is the chosen percentile (nearest rank, default 99) of the per-frame ffmpeg signalstats SATAVG over every
frame of every file. G2 divides a clip's mean SATAVG by it, so 1.0 means "as saturated as the approved references".
Without --write it only prints the value. Run only on owner-approved material and never commit the images.
Exit codes: 0 ok, 2 refused (no files, unreadable file, bad percentile, no core.json)."""
import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.frame_metrics import per_frame_stats  # noqa: E402

CORE = ROOT / "core" / "core.json"
_KEY = re.compile(r'("sat_avg_ceiling"\s*:\s*)(null|[0-9.eE+-]+)')


def percentile(values, pct):
    """Nearest-rank percentile of a non-empty list."""
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[rank - 1]


def calibrate(paths, pct=99.0):
    """-> {"ceiling": float, "frames": int, "files": int}. ValueError on no files, a bad percentile or an unreadable file."""
    if not paths:
        raise ValueError("no reference files given")
    if not (isinstance(pct, (int, float)) and not isinstance(pct, bool) and 0 < pct <= 100):
        raise ValueError("percentile must be in (0, 100]")
    values = []
    for p in paths:
        if not Path(p).is_file():
            raise ValueError(f"not a file: {p}")
        try:
            stats = per_frame_stats(p)
        except (RuntimeError, OSError) as exc:   # ffmpeg failed or the file could not be opened
            raise ValueError(str(exc)) from exc
        values += [s["SATAVG"] for s in stats if "SATAVG" in s]
    if not values:
        raise ValueError("no frames measured")
    return {"ceiling": round(percentile(values, pct), 2), "frames": len(values), "files": len(paths)}


def write_ceiling(core_path, value):
    """Replaces the gates.sat_avg_ceiling value in place (formatting and key order of the file are kept)."""
    path = Path(core_path)
    text = path.read_bytes().decode("utf-8")   # bytes in and out: CRLF or LF line endings are kept as they are
    if len(_KEY.findall(text)) != 1:
        raise ValueError("core.json must contain exactly one sat_avg_ceiling key")
    new = _KEY.sub(lambda m: m.group(1) + repr(float(value)), text)
    json.loads(new)   # the result must still be valid JSON
    path.write_bytes(new.encode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Calibrate gates.sat_avg_ceiling from approved reference frames.")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--percentile", type=float, default=99.0)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--core", default=str(CORE))
    args = ap.parse_args(argv)
    try:
        res = calibrate(args.files, args.percentile)
        if args.write:
            write_ceiling(args.core, res["ceiling"])
    except (ValueError, OSError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"sat_avg_ceiling={res['ceiling']} from {res['frames']} frame(s) in {res['files']} file(s)"
          + (f"; written to {args.core}" if args.write else "; not written (use --write)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
