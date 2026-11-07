"""Make a draft .cube LUT for one act of a style pack (WP8).

    python tools/make_lut.py PACK ACT [--styles-dir DIR] [--size 33] [--force]

Writes <styles-dir>/<acts[ACT].lut> from the act's grade numbers, TITLE "DRAFT — owner to approve".
An existing LUT whose TITLE does not start with DRAFT (an owner Resolve export) is refused
(exit 2) unless --force. Exit 2 also for an unknown pack or act.
"""
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.lut import grade_fn, identity_fn, write_cube  # noqa: E402
from core.style_pack import _lut_ok, load_pack  # noqa: E402

DRAFT_TITLE = "DRAFT — owner to approve"


def _error(message):
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def _existing_title(path):
    """TITLE text of an existing .cube, "" when there is none, None when unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if line.upper().startswith("TITLE"):
            t = line[5:].strip()
            return t[1:-1] if len(t) >= 2 and t[0] == '"' and t[-1] == '"' else t
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make a draft LUT for one act of a style pack.")
    ap.add_argument("pack")
    ap.add_argument("act")
    ap.add_argument("--styles-dir", default=None)
    ap.add_argument("--size", type=int, default=33)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if args.size < 2:
        return _error("--size must be at least 2")
    styles = Path(args.styles_dir) if args.styles_dir else _ROOT / "styles"
    try:
        pack = load_pack(args.pack, styles_dir=styles)
    except ValueError as exc:
        return _error(str(exc))

    acts = pack.get("acts")
    if not isinstance(acts, dict) or not isinstance(acts.get(args.act), dict):
        return _error(f"unknown act {args.act!r} in pack {args.pack!r}")
    act = acts[args.act]
    rel = act.get("lut")
    if not _lut_ok(rel):
        return _error(f"act {args.act!r} has no usable lut path: {rel!r}")

    target = styles / rel
    if target.exists() and not args.force:
        title = _existing_title(target)
        if title is None or not title.startswith("DRAFT"):
            return _error(f"{target} exists and is not a DRAFT LUT (TITLE {title!r}); use --force to overwrite")

    grade = act.get("grade")
    if isinstance(grade, dict):
        fn = grade_fn(grade)
    else:
        print(f"WARN: act {args.act} has no grade; writing an identity LUT")
        fn = identity_fn
    write_cube(target, fn, size=args.size, title=DRAFT_TITLE)
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
