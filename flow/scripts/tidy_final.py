"""Tidy an adhyay's final/ folder. For every finished image (a <T>__candidate_v01__final.png in final/), moves the other working
variants into final/_intermediates/: <T>__candidate_v01.png (original, watermarked), __2K_source.jpg, __clean.png, __lama.png.
The __final.png stays in place. Nothing is deleted or overwritten. A title with no __final.png is left alone.
Dry run by default; --apply moves the files.

  python tidy_final.py --root "D:/aai work/flow_outputs/anime_kaliya" --adhyay 1           # plan only
  python tidy_final.py --root "D:/aai work/flow_outputs/anime_kaliya" --adhyay 1 --apply

After --apply: lama_inpaint.py and remove_sparkle.py read the watermarked originals from final/_original_with_watermark and
the __clean.png / __lama.png files from final/_intermediates (they were updated for this layout; see their docstrings)."""
import argparse
from pathlib import Path

from download_queue import OUT_ROOT, chapter

FINAL = "__candidate_v01__final.png"
VARIANTS = ("__candidate_v01.png", "__candidate_v01__2K_source.jpg", "__candidate_v01__clean.png", "__candidate_v01__lama.png")
INTERMEDIATES = "_intermediates"


def plan(final: Path):
    """(moves, notes): moves = [(src, dst)] for files directly in final/; notes say why a file or title was skipped."""
    titles = {f.name[: -len(v)] for f in final.iterdir() if f.is_file() for v in VARIANTS if f.name.endswith(v)}
    moves, notes = [], []
    for t in sorted(titles):
        if not (final / (t + FINAL)).is_file():
            notes.append(f"SKIP {t}: no {FINAL} in final/, nothing moved")
            continue
        for v in VARIANTS:
            src = final / (t + v)
            if not src.is_file():
                continue
            dst = final / INTERMEDIATES / src.name
            if dst.exists():
                notes.append(f"SKIP {src.name}: already in {INTERMEDIATES}, not overwritten")
                continue
            moves.append((src, dst))
    return moves, notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=OUT_ROOT)
    ap.add_argument("--adhyay", type=int, default=1)
    ap.add_argument("--apply", action="store_true", help="move the files (default: dry run, print the plan only)")
    a = ap.parse_args(argv)
    final = chapter(a.root, a.adhyay) / "final"
    if not final.is_dir():
        print(f"no folder {final}")
        return 1
    moves, notes = plan(final)
    for n in notes:
        print(n)
    for src, _ in moves:
        print(f"{'MOVE' if a.apply else 'PLAN'} {src.name} -> {INTERMEDIATES}/")
    if not a.apply:
        print(f"dry run: {len(moves)} file(s) would move; add --apply to move them")
        return 0
    inter = final / INTERMEDIATES
    inter.mkdir(exist_ok=True)
    for src, dst in moves:
        if dst.exists():  # rename would overwrite on POSIX; plan() already skipped these, this is the last guard
            raise FileExistsError(dst)
        src.rename(dst)
    print(f"moved {len(moves)} file(s) to {inter}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
