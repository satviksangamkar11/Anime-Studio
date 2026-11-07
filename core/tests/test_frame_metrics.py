import shutil
import subprocess

import pytest
from PIL import Image

from core.frame_metrics import (
    extract_frames,
    grid_luma,
    grid_red_share,
    mean_lab,
    outside_region_lstar,
    per_frame_stats,
    region_lstar,
    white_share,
)

FFMPEG = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def solid(colour, size=(16, 16)):
    return Image.new("RGB", size, colour)


def test_grid_luma_white_is_all_one_and_black_all_zero():
    assert grid_luma(solid((255, 255, 255))) == pytest.approx([1.0] * 64)
    assert grid_luma(solid((0, 0, 0))) == pytest.approx([0.0] * 64)


def test_grid_luma_uses_wcag_weights_on_linear_light():
    red = grid_luma(solid((255, 0, 0)))
    assert red[0] == pytest.approx(0.2126, abs=1e-4)


def test_grid_red_share_is_zero_for_black_and_one_for_pure_red():
    assert grid_red_share(solid((0, 0, 0))) == pytest.approx([0.0] * 64)
    assert grid_red_share(solid((255, 0, 0))) == pytest.approx([1.0] * 64)


def test_tiny_frames_never_divide_by_zero():
    tiny = solid((10, 200, 30), size=(1, 1))
    assert len(grid_luma(tiny)) == 64
    assert len(grid_red_share(solid((0, 0, 0), size=(1, 1)))) == 64
    assert white_share(solid((0, 0, 0), size=(1, 1))) == 0.0
    assert isinstance(region_lstar(tiny, [0, 0, 1, 1]), float)


def test_white_share_of_white_is_one_and_black_is_zero():
    assert white_share(solid((255, 255, 255))) == 1.0
    assert white_share(solid((0, 0, 0))) == 0.0


def test_region_lstar_sees_white_box_on_black():
    img = solid((0, 0, 0), size=(64, 64))
    for x in range(16, 48):
        for y in range(16, 48):
            img.putpixel((x, y), (255, 255, 255))
    assert region_lstar(img, [0.25, 0.25, 0.75, 0.75]) > 99
    assert outside_region_lstar(img, [0.25, 0.25, 0.75, 0.75]) < 1
    lab = mean_lab(img)
    assert len(lab) == 3


def test_outside_region_lstar_is_none_when_box_covers_frame():
    assert outside_region_lstar(solid((0, 0, 0)), [0, 0, 1, 1]) is None


@FFMPEG
def test_per_frame_stats_one_second_solid_clip_has_24_frames(tmp_path):
    clip = tmp_path / "black.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=black:s=96x160:r=24:d=1", "-c:v", "libx264", str(clip)], check=True)
    stats = per_frame_stats(clip)
    assert len(stats) == 24
    assert [s["frame"] for s in stats] == list(range(24))
    assert all(14 <= s["YAVG"] <= 18 for s in stats)
    assert all({"SATAVG", "HUEMED", "pts_time"} <= set(s) for s in stats)


@FFMPEG
def test_extract_frames_every_second_frame_returns_indices_and_half_size(tmp_path):
    clip = tmp_path / "grey.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=gray:s=96x160:r=24:d=1", "-c:v", "libx264", str(clip)], check=True)
    out = tmp_path / "frames"
    out.mkdir()
    frames = extract_frames(clip, out, scale=0.5, every=2)
    assert [i for i, _ in frames] == list(range(0, 24, 2))
    assert all(p.is_file() for _, p in frames)
    with Image.open(frames[0][1]) as im:
        assert im.size == (48, 80)
