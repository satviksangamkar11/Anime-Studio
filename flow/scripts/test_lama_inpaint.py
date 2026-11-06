"""Checks for lama_inpaint: nothing outside the LaMa window may change.

The window check uses a stand-in model, so it runs everywhere. The real-weights check skips
until big-lama.pt is in D:/aai work/anime_studio/flow/lama_weights/.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lama_inpaint as li  # noqa: E402
import remove_sparkle as rs  # noqa: E402

ORIG, INTER = rs.ORIGINALS, rs.INTERMEDIATES


def scene():
    """Textured 1000x1200 image with one synthetic big star inside the LaMa window, and its mask."""
    rng = np.random.default_rng(0)
    rgb = cv2.GaussianBlur(rng.integers(40, 200, (1000, 1200, 3)).astype(np.uint8), (0, 0), 1.5)
    h, w = rgb.shape[:2]
    hh, n = 48, 99
    y0, x0 = h - rs.BOX + 60, w - rs.BOX + 60          # star top-left in full-image coordinates
    star = np.zeros((h, w), np.float32)
    star[y0:y0 + n, x0:x0 + n] = rs.TEMPLATES[hh]
    a = cv2.GaussianBlur(star, (0, 0), 1.0)[..., None] * 0.7
    rgb = np.clip(np.round(rgb * (1 - a) + 255 * a), 0, 255).astype(np.uint8)
    mask = cv2.dilate((star > 0).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))
    return rgb, mask


class Flat(torch.nn.Module):
    """Stand-in for big-lama: fills every hole with mid grey."""

    def forward(self, image, mask):
        return torch.full_like(image, 0.5)


def test_only_the_window_changes():
    rgb, mask = scene()
    out = li.lama_blend(rgb, mask, Flat())
    assert li.changed_outside(rgb, out) == 0
    assert (out != rgb).any()


@pytest.mark.skipif(not li.WEIGHTS.exists(), reason=f"no weights at {li.WEIGHTS}")
def test_real_lama_only_the_window_changes():
    rgb, mask = scene()
    out = li.lama_blend(rgb, mask, li.load_model())
    assert li.changed_outside(rgb, out) == 0
    assert (out != rgb).any()


def make_final(tmp_path, n=1, originals=ORIG, intermediates=INTER):
    """final/ in the new layout: watermarked original in <originals>/, alpha-cleaned stand-in in <intermediates>/."""
    final = tmp_path / "final"
    for k in range(n):
        rgb, _ = scene()
        (final / originals).mkdir(parents=True, exist_ok=True)
        li.write_rgb(final / originals / f"T{k}__candidate_v01.png", rgb)
        (final / intermediates).mkdir(parents=True, exist_ok=True)
        li.write_rgb(final / intermediates / f"T{k}__candidate_v01__clean.png", rgb)
    return final


def test_process_reads_originals_and_writes_lama_to_intermediates(tmp_path):
    final = make_final(tmp_path)
    li.process(final, model=Flat())
    assert (final / INTER / "T0__candidate_v01__lama.png").is_file()
    assert not (final / "T0__candidate_v01__lama.png").exists()
    assert (final / "_sparkle_check3" / "T0__sheet.png").is_file()
    report = json.loads((final / "_sparkle_check3" / "report.json").read_text())
    assert report["T0"]["changed_outside_window"] == {"lama": 0, "lama_on_clean": 0}
    assert not list(final.glob("*.png"))                       # nothing written to the root


def test_finalize_writes_only_the_master_to_root_and_refuses_overwrite(tmp_path):
    final = make_final(tmp_path)
    li.process(final, model=Flat())
    choices = tmp_path / "choices.json"
    choices.write_text(json.dumps({"T0": {"method": "lama", "verdict": "ok"}}))
    li.main(["finalize", str(final), str(choices)])
    master = final / "T0__candidate_v01__final.png"
    assert np.array_equal(rs.read_rgb(master), rs.read_rgb(final / INTER / "T0__candidate_v01__lama.png"))
    with pytest.raises(FileExistsError):
        li.finalize(final, choices)
    li.main(["finalize", str(final), str(choices), "--overwrite"])
    assert master.is_file()


def test_process_refuses_existing_lama_before_writing(tmp_path):
    final = make_final(tmp_path, n=2)
    (final / INTER / "T1__candidate_v01__lama.png").write_bytes(b"earlier")
    with pytest.raises(FileExistsError):
        li.process(final, model=Flat())
    assert (final / INTER / "T1__candidate_v01__lama.png").read_bytes() == b"earlier"
    assert not (final / INTER / "T0__candidate_v01__lama.png").exists()


def test_process_falls_back_to_root_input_and_custom_names(tmp_path):
    final = make_final(tmp_path, originals="orig_x", intermediates="mid_x")
    li.process(final, model=Flat(), originals="orig_x", intermediates="mid_x")
    assert (final / "mid_x" / "T0__candidate_v01__lama.png").is_file()
    (final / "orig_x" / "T0__candidate_v01.png").rename(final / "T0__candidate_v01.png")
    li.process(final, model=Flat(), originals="nothing_here", intermediates="mid_x", overwrite=True)   # input found in final/ root
    assert (final / "mid_x" / "T0__candidate_v01__lama.png").is_file()


def test_finalize_logs_method_and_backfill_adds_missing_only(tmp_path):
    final = make_final(tmp_path)
    li.process(final, model=Flat())
    choices = tmp_path / "choices.json"
    choices.write_text(json.dumps({"T0": {"method": "lama_on_clean", "verdict": "faint"}}))
    li.main(["finalize", str(final), str(choices)])
    log = final.parent / "watermark_log.jsonl"
    lines = [json.loads(l) for l in log.read_text().splitlines()]
    assert len(lines) == 1 and lines[0]["method"] == "lama_on_clean" and len(lines[0]["final_sha256"]) == 64 and lines[0]["backfilled"] is False
    assert li.backfill(final) == 0            # already logged: nothing added
    log.unlink()
    assert li.backfill(final) == 1 and json.loads(log.read_text())["backfilled"] is True
