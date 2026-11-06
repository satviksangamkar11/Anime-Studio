"""Cut the Ref2VA identity references out of the filed 2K identity master (3 panels: face | front | back, no text labels).
  python make_refs.py <identity_master.png> <out_dir>
Writes CHAR-KRISHNA__ref_face.png, __ref_front.png, __ref_back.png. Panel boxes are fractions of the sheet width,
measured on KRISHNA_IDENTITY_MASTER__candidate_v01 (2752x1536, approved U-tilak version)."""
import sys
from pathlib import Path

from PIL import Image

PANELS = {"face": (0.0, 0.35), "front": (0.37, 0.67), "back": (0.67, 1.0)}   # ponytail: fixed layout; re-measure if the sheet changes


def main(src, out_dir):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, (a, b) in PANELS.items():
        p = out / f"CHAR-KRISHNA__ref_{name}.png"
        im.crop((round(a * w), 0, round(b * w), h)).save(p)
        print(p)


if __name__ == "__main__":
    main(*sys.argv[1:3])
