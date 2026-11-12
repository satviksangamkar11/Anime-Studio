"""M-13 / C-03: last-frame chaining. Offline: ffmpeg lavfi test clips, tmp_path, no network, no model call."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import chain_step as cs  # noqa: E402

SIZE = (96, 168)  # small render-shaped frame for speed; the module default is 768x1344


def run_ffmpeg(args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def colour_clip(path: Path, colours):
    """One clip of 4 solid frames per colour, in order: frames 0-3 = colours[0], 4-7 = colours[1], ..."""
    parts, labels = [], []
    for i, c in enumerate(colours):
        parts.append(f"color=c={c}:s={SIZE[0]}x{SIZE[1]}:r=24,trim=end_frame=4,setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(colours)}:v=1:a=0[out]"
    run_ffmpeg(["-filter_complex", graph, "-map", "[out]", "-c:v", "mpeg4", "-q:v", "2", str(path)])
    return path


def mean_rgb(png: Path):
    arr = np.asarray(Image.open(png).convert("RGB"), dtype=np.float64).reshape(-1, 3)
    return tuple(float(v) for v in arr.mean(axis=0))


def dominant(png: Path) -> str:
    r, g, b = mean_rgb(png)
    return max((r, "red"), (g, "green"), (b, "blue"))[1]


# ---------------------------------------------------------------- depth rule (refuse > 2)

@pytest.mark.parametrize("depth", [0, 1, 2])
def test_chain_depth_up_to_two_is_allowed(depth):
    cs.check_depth(depth)  # no raise


@pytest.mark.parametrize("depth", [3, 4, -1])
def test_chain_depth_above_two_is_refused_and_negative_too(depth):
    with pytest.raises(cs.ChainError):
        cs.check_depth(depth)


def test_chain_png_path_lives_in_pack_chain_folder(tmp_path):
    assert cs.chain_png_path(tmp_path, "SHOT-003") == tmp_path / "chain" / "SHOT-003-last.png"


# ---------------------------------------------------------------- frame extraction (exact frame index)

def test_last_kept_frame_is_the_frame_after_trim_not_the_clip_end(tmp_path):
    clip = colour_clip(tmp_path / "clip.mp4", ["red", "lime", "blue"])
    out = cs.last_kept_frame(clip, 4, tmp_path / "keep4.png", size=SIZE)  # keep frames 0-3 -> last kept is red
    assert dominant(out) == "red"
    out5 = cs.last_kept_frame(clip, 5, tmp_path / "keep5.png", size=SIZE)  # keep 0-4 -> frame 4 is the first lime
    assert dominant(out5) == "green"


def test_last_kept_frame_refuses_zero_kept_frames(tmp_path):
    clip = colour_clip(tmp_path / "clip.mp4", ["red"])
    with pytest.raises(cs.ChainError):
        cs.last_kept_frame(clip, 0, tmp_path / "x.png", size=SIZE)
    assert not (tmp_path / "x.png").exists()


def test_first_frame_is_frame_zero(tmp_path):
    clip = colour_clip(tmp_path / "clip.mp4", ["blue", "red"])
    assert dominant(cs.first_frame(clip, tmp_path / "f0.png", size=SIZE)) == "blue"


# ---------------------------------------------------------------- SSIM and seam gate

def save_flat(path: Path, value: int) -> Path:
    Image.new("RGB", SIZE, (value, value, value)).save(path)
    return path


def test_ssim_identical_frames_is_one(tmp_path):
    a = save_flat(tmp_path / "a.png", 120)
    assert cs.ssim(a, a) == pytest.approx(1.0, abs=1e-9)


def test_ssim_black_against_white_is_near_zero(tmp_path):
    a = save_flat(tmp_path / "a.png", 0)
    b = save_flat(tmp_path / "b.png", 255)
    assert cs.ssim(a, b) < 0.05


def test_ssim_refuses_different_sizes(tmp_path):
    a = save_flat(tmp_path / "a.png", 10)
    b = tmp_path / "b.png"
    Image.new("RGB", (32, 32), (10, 10, 10)).save(b)
    with pytest.raises(cs.ChainError):
        cs.ssim(a, b)


def test_seam_passes_when_next_clip_starts_on_the_kept_frame(tmp_path):
    prev = colour_clip(tmp_path / "prev.mp4", ["red", "lime"])
    nxt = colour_clip(tmp_path / "next.mp4", ["red", "blue"])  # frame 0 of next is red, same as prev's kept red
    last = cs.last_kept_frame(prev, 4, tmp_path / "last.png", size=SIZE)
    first = cs.first_frame(nxt, tmp_path / "first.png", size=SIZE)
    res = cs.verify_seam(last, first)
    assert res["ok"] is True and res["ssim"] >= cs.SEAM_SSIM_MIN


def test_seam_fails_when_next_clip_resets_to_another_frame(tmp_path):
    prev = colour_clip(tmp_path / "prev.mp4", ["red"])
    nxt = colour_clip(tmp_path / "next.mp4", ["lime"])  # a reset: frame 0 is green
    last = cs.last_kept_frame(prev, 4, tmp_path / "last.png", size=SIZE)
    first = cs.first_frame(nxt, tmp_path / "first.png", size=SIZE)
    res = cs.verify_seam(last, first)
    assert res["ok"] is False and res["ssim"] < cs.SEAM_SSIM_MIN


# ---------------------------------------------------------------- prompt header and the chain step

def test_chain_header_has_the_required_phrases():
    head = cs.chain_header("Riya, red shawl, left hand on the door")
    assert "CURRENT CHARACTER STATE" in head
    assert "Continue directly from this exact frame with no reset" in head
    assert "Riya, red shawl, left hand on the door" in head


def test_prepare_chain_writes_png_and_returns_header(tmp_path):
    clip = colour_clip(tmp_path / "clip.mp4", ["red", "lime"])
    pack = tmp_path / "pack"
    res = cs.prepare_chain(clip, 4, pack, "SHOT-003", depth=1, state="Riya, red shawl", size=SIZE)
    assert res["png"] == pack / "chain" / "SHOT-003-last.png" and res["png"].is_file()
    assert res["depth"] == 1
    assert "CURRENT CHARACTER STATE" in res["header"]
    assert dominant(res["png"]) == "red"


def test_prepare_chain_refuses_depth_three_and_writes_nothing(tmp_path):
    clip = colour_clip(tmp_path / "clip.mp4", ["red"])
    pack = tmp_path / "pack"
    with pytest.raises(cs.ChainError):
        cs.prepare_chain(clip, 4, pack, "SHOT-003", depth=3, state="x", size=SIZE)
    assert not (pack / "chain" / "SHOT-003-last.png").exists()


def test_last_kept_frame_past_clip_end_is_a_chain_error_not_an_ffmpeg_crash(tmp_path):
    clip = colour_clip(tmp_path / "clip.mp4", ["red"])
    with pytest.raises(cs.ChainError):
        cs.last_kept_frame(clip, 9999, tmp_path / "x.png", size=SIZE)
