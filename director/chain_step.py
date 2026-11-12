"""M-13 / C-03: last-frame chaining between clips.

The next clip's start picture is the LAST KEPT decoded frame of the accepted clip before it (after trim), saved as
<pack>/chain/<SHOT>-last.png at the render size 768x1344. It is never regenerated in Flow.
Chain depth above 2 is refused: re-anchor to a fresh Flow keyframe. Frame 0 of the next clip must match that PNG (SSIM >= 0.90).

Stdlib + numpy + PIL + the ffmpeg binary. No network, no model call."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

RENDER_SIZE = (768, 1344)
MAX_CHAIN_DEPTH = 2
SEAM_SSIM_MIN = 0.90
BLOCK = 8  # ponytail: non-overlapping 8x8 block SSIM, not the gaussian window; upgrade if the seam gate flaps
_C1 = (0.01 * 255) ** 2
_C2 = (0.03 * 255) ** 2
CONTINUE_TEXT = "Continue directly from this exact frame with no reset."


class ChainError(ValueError):
    """A refusal: depth too deep, no kept frame, or two pictures that cannot be compared."""


def check_depth(depth: int) -> None:
    """Refuses a chain depth outside 0..MAX_CHAIN_DEPTH (depth 0 = a clip started from a fresh Flow keyframe)."""
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0 or depth > MAX_CHAIN_DEPTH:
        raise ChainError(f"chain depth {depth!r} refused: allowed 0..{MAX_CHAIN_DEPTH}; "
                         "re-anchor to a fresh Flow keyframe")


def chain_png_path(pack, shot_id: str) -> Path:
    return Path(pack) / "chain" / f"{shot_id}-last.png"


def _run(args) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def last_kept_frame(clip, kept_frames: int, out_png, size=RENDER_SIZE) -> Path:
    """Writes decoded frame number kept_frames-1 (0-based) of clip, scaled to size. kept_frames counts the frames that
    survive the trim, so the frame after the trim is never used."""
    if not isinstance(kept_frames, int) or kept_frames < 1:
        raise ChainError(f"kept_frames {kept_frames!r}: need at least one kept frame")
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    _run(["-i", str(clip), "-vf", f"select=eq(n\\,{kept_frames - 1}),scale={w}:{h}", "-frames:v", "1",
          str(out_png)])
    if not out_png.is_file():
        raise ChainError(f"no frame {kept_frames - 1} in {clip}")
    return out_png


def first_frame(clip, out_png, size=RENDER_SIZE) -> Path:
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    _run(["-i", str(clip), "-vf", f"scale={w}:{h}", "-frames:v", "1", str(out_png)])
    return out_png


def _gray(png) -> np.ndarray:
    return np.asarray(Image.open(png).convert("L"), dtype=np.float64)


def ssim(a_png, b_png) -> float:
    """Mean SSIM over non-overlapping BLOCK x BLOCK blocks of the grey images (1.0 = identical)."""
    a, b = _gray(a_png), _gray(b_png)
    if a.shape != b.shape:
        raise ChainError(f"size differs: {a.shape} vs {b.shape}")
    h, w = (a.shape[0] // BLOCK) * BLOCK, (a.shape[1] // BLOCK) * BLOCK
    if h == 0 or w == 0:
        raise ChainError("image smaller than one block")

    def blocks(x):
        return x[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK).transpose(0, 2, 1, 3).reshape(-1, BLOCK * BLOCK)

    x, y = blocks(a), blocks(b)
    mx, my = x.mean(axis=1), y.mean(axis=1)
    vx, vy = x.var(axis=1), y.var(axis=1)
    cov = ((x - mx[:, None]) * (y - my[:, None])).mean(axis=1)
    s = ((2 * mx * my + _C1) * (2 * cov + _C2)) / ((mx ** 2 + my ** 2 + _C1) * (vx + vy + _C2))
    return float(s.mean())


def verify_seam(prev_last_png, next_first_png, min_ssim: float = SEAM_SSIM_MIN) -> dict:
    s = ssim(prev_last_png, next_first_png)
    return {"ok": s >= min_ssim, "ssim": round(s, 4), "min_ssim": min_ssim}


def chain_header(state: str) -> str:
    """Prompt header for the chained clip (M-03 uses it): the character state, then the continue order."""
    return f"CURRENT CHARACTER STATE: {state}. {CONTINUE_TEXT}"


def prepare_chain(clip, kept_frames: int, pack, shot_id: str, depth: int, state: str, size=RENDER_SIZE) -> dict:
    """The chain step after an accepted clip: refuse depth > 2, write <pack>/chain/<SHOT>-last.png from the last kept
    frame, return {"png", "depth", "header"}. Nothing is written when the depth is refused."""
    check_depth(depth)
    png = last_kept_frame(clip, kept_frames, chain_png_path(pack, shot_id), size=size)
    return {"png": png, "depth": depth, "header": chain_header(state)}
