import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import pytest

import image_gates
import plate_composite


def test_background_lock_nonfinite_ssim_fails(monkeypatch):
    def fake_block_ssim(a, b, valid, block=8):
        return float("nan")

    monkeypatch.setattr(image_gates, "block_ssim", fake_block_ssim)

    img = np.zeros((16, 16, 3), dtype=np.uint8)
    mask = np.zeros((16, 16), dtype=bool)
    result = image_gates.background_lock(img, img, mask, mask)
    assert result["pass"] is False
    assert any("ssim is not a finite number" in r for r in result["reasons"])


def test_background_lock_equal_images_pass():
    img = np.full((64, 64, 3), 128, dtype=np.uint8)
    mask = np.zeros((64, 64), dtype=bool)
    result = image_gates.background_lock(img, img, mask, mask)
    assert result["pass"] is True


def test_hole_fraction_rejects_lists():
    with pytest.raises(plate_composite.CompositeError):
        plate_composite.hole_fraction([[1]], np.zeros((2, 2), bool))
    with pytest.raises(plate_composite.CompositeError):
        plate_composite.hole_fraction(np.zeros((2, 2), bool), [[1]])


def test_hole_fraction_shape_mismatch_raises():
    a = np.zeros((2, 2), bool)
    b = np.zeros((3, 3), bool)
    with pytest.raises(plate_composite.CompositeError):
        plate_composite.hole_fraction(a, b)
