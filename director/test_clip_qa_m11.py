"""clip_qa M-11 (plan items T-07, T-08, C-04): HSV histogram correlation, SSIM_1s warn, chain frame-0 check, route S.

Pure-function cases use numpy frames with hand-computed values. Clip cases use synthetic ffmpeg clips (lavfi).
Hand-computed histogram values: the histogram has 128 bins (16 hue x 8 saturation), frame 0 is all pure red
(one-hot at bin 7), a later frame is a fraction p red and (1-p) pure blue (one-hot at bin 87). The Pearson
correlation of e_a and p*e_a + (1-p)*e_b over n = 128 bins is (p - 1/n) / sqrt((1 - 1/n) * (p^2 + (1-p)^2 - 1/n)).
p = 0.4 -> 0.5501 (warn band), p = 0.2 -> 0.2353 (fail), pure red vs pure blue -> -1/127 (fail).
"""
import os
import subprocess
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clip_qa  # noqa: E402


def _ff(args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _solid(p_red, h=100, w=8):
    """RGB frame: the first p_red fraction of rows pure red, the rest pure blue."""
    f = np.zeros((h, w, 3), dtype=np.uint8)
    cut = int(round(p_red * h))
    f[:cut, :, 0] = 255
    f[cut:, :, 2] = 255
    return f


def test_hsv_hist_pure_red_and_blue_land_in_different_bins():
    red = clip_qa.hsv_hist(_solid(1.0))
    blue = clip_qa.hsv_hist(_solid(0.0))
    assert red.shape == (128,)
    assert red[7] == pytest.approx(1.0)      # hue 0 -> bin 0, saturation 1 -> bin 7: index 0*8 + 7
    assert blue[87] == pytest.approx(1.0)    # hue 240 -> bin 10, saturation 1 -> index 10*8 + 7


def test_hist_identical_frames_are_ok():
    rep = clip_qa.hist_check([_solid(1.0)] * 5)
    assert rep["corr_min"] == pytest.approx(1.0)
    assert rep["status"] == "ok"


def test_hist_mixture_p40_is_warn_band():
    rep = clip_qa.hist_check([_solid(1.0), _solid(0.4)])
    assert rep["corr_min"] == pytest.approx(0.5501, abs=1e-3)
    assert rep["status"] == "warn"


def test_hist_mixture_p20_is_fail():
    rep = clip_qa.hist_check([_solid(1.0), _solid(0.2)])
    assert rep["corr_min"] == pytest.approx(0.2353, abs=1e-3)
    assert rep["status"] == "fail"


def test_hist_red_to_blue_is_fail_with_minus_one_over_127():
    rep = clip_qa.hist_check([_solid(1.0), _solid(0.0)])
    assert rep["corr_min"] == pytest.approx(-1.0 / 127.0, abs=1e-9)
    assert rep["status"] == "fail"


def test_ffmpeg_red_to_blue_clip_fails_hist(tmp_path):
    clip = tmp_path / "switch.avi"
    _ff(["-f", "lavfi", "-i", "color=c=red:s=192x336:r=24:d=1",
         "-f", "lavfi", "-i", "color=c=blue:s=192x336:r=24:d=1",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
         "-c:v", "rawvideo", "-pix_fmt", "rgb24", "-f", "avi", str(clip)])
    frames = clip_qa.extract_rgb(str(clip), 0, 48)
    assert frames.shape == (48, 336, 192, 3)
    rep = clip_qa.hist_check(frames)
    assert rep["status"] == "fail"


def test_ffmpeg_solid_clip_passes_hist(tmp_path):
    clip = tmp_path / "solid.avi"
    _ff(["-f", "lavfi", "-i", "color=c=red:s=192x336:r=24:d=1", "-c:v", "rawvideo", "-pix_fmt", "rgb24",
         "-f", "avi", str(clip)])
    rep = clip_qa.hist_check(clip_qa.extract_rgb(str(clip), 0, 24))
    assert rep["status"] == "ok"


def test_ssim_1s_static_clip_no_warn(tmp_path):
    clip = tmp_path / "static.avi"
    _ff(["-f", "lavfi", "-i", "color=c=gray:s=768x1344:r=24:d=2", "-c:v", "rawvideo", "-pix_fmt", "gray",
         "-f", "avi", str(clip)])
    rep = clip_qa.ssim_1s_check(clip_qa.extract(str(clip), 0, 48))
    assert rep["value"] == pytest.approx(1.0)
    assert rep["warn"] is False


def test_ssim_1s_noise_clip_warns(tmp_path):
    clip = tmp_path / "noise.avi"
    _ff(["-f", "lavfi", "-i", "color=c=gray:s=768x1344:r=24:d=2,noise=alls=100:allf=t",
         "-c:v", "rawvideo", "-pix_fmt", "gray", "-f", "avi", str(clip)])
    rep = clip_qa.ssim_1s_check(clip_qa.extract(str(clip), 0, 48))
    assert rep["value"] < 0.20
    assert rep["warn"] is True


def test_ssim_1s_needs_more_than_one_second():
    frames = np.zeros((24, 336, 192), dtype=np.float32)   # 24 frames: no pair one second apart
    rep = clip_qa.ssim_1s_check(frames)
    assert rep["value"] is None
    assert rep["warn"] is False


def _png_from(tmp_path, clip, name):
    out = tmp_path / name
    _ff(["-i", str(clip), "-frames:v", "1", str(out)])
    return str(out)


def test_chain_same_frame_passes(tmp_path):
    clip = tmp_path / "static.avi"
    _ff(["-f", "lavfi", "-i", "color=c=gray:s=768x1344:r=24:d=1", "-c:v", "rawvideo", "-pix_fmt", "gray",
         "-f", "avi", str(clip)])
    last = _png_from(tmp_path, clip, "last.png")
    rep = clip_qa.chain_check(str(clip), last)
    assert rep["pass"] is True
    assert rep["ssim"] >= 0.90


def test_chain_mismatch_fails(tmp_path):
    static = tmp_path / "static.avi"
    _ff(["-f", "lavfi", "-i", "color=c=gray:s=768x1344:r=24:d=1", "-c:v", "rawvideo", "-pix_fmt", "gray",
         "-f", "avi", str(static)])
    noise = tmp_path / "noise.avi"
    _ff(["-f", "lavfi", "-i", "color=c=gray:s=768x1344:r=24:d=1,noise=alls=100:allf=t",
         "-c:v", "rawvideo", "-pix_fmt", "gray", "-f", "avi", str(noise)])
    last = _png_from(tmp_path, static, "last.png")
    rep = clip_qa.chain_check(str(noise), last)
    assert rep["pass"] is False
    assert rep["ssim"] < 0.90


def test_route_s_skips_end_frame_check():
    bad_end = {"ssim": 0.1, "lpips": 0.9, "cosine": 0.1}
    assert clip_qa._end_result("S", bad_end)["pass"] is True


def test_route_se_keeps_end_frame_check():
    bad_end = {"ssim": 0.1, "lpips": 0.9, "cosine": 0.1}
    res = clip_qa._end_result("SE", bad_end)
    assert res["pass"] is False
    assert "ssim" in res["failed"]


def test_unknown_route_refused():
    with pytest.raises(clip_qa.ClipQAError):
        clip_qa._end_result("X", {"ssim": 1.0, "lpips": 0.0, "cosine": 1.0})


def _passing():
    return {"pass": True, "reasons": [], "accepted": []}


def test_hist_fail_blocks_uncut_clip():
    v, warns = clip_qa._m11_verdict(_passing(), [], {"corr_min": 0.2, "status": "fail"}, None)
    assert v["pass"] is False
    assert [r["code"] for r in v["reasons"]] == ["HIST_CORR"]


def test_hist_fail_ignored_on_cut_clip():
    v, warns = clip_qa._m11_verdict(_passing(), [5], {"corr_min": 0.2, "status": "fail"}, None)
    assert v["pass"] is True
    assert any("hist" in w for w in warns)


def test_hist_warn_is_warning_not_block():
    v, warns = clip_qa._m11_verdict(_passing(), [], {"corr_min": 0.5, "status": "warn"}, None)
    assert v["pass"] is True
    assert any("hist" in w for w in warns)


def test_chain_fail_blocks_even_on_cut_clip():
    v, _ = clip_qa._m11_verdict(_passing(), [5], None, {"ssim": 0.5, "pass": False})
    assert [r["code"] for r in v["reasons"]] == ["CHAIN_SSIM"]


def test_new_codes_are_owner_acceptable_not_critical():
    assert "HIST_CORR" in clip_qa.ACCEPT_CODES
    assert "CHAIN_SSIM" in clip_qa.ACCEPT_CODES
    assert "HIST_CORR" not in clip_qa.CRITICAL_CODES
