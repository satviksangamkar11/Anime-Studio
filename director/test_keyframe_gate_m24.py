"""M-24 tests for director/keyframe_gate.py: background SSIM 0.80 and the palette dE2000 <= 6 check.

Hand-checked values:
- A flat sRGB grey 128 has L* about 53.6; grey 130 has L* about 54.4 (dL about 0.75): dE2000 well under 6.
- Grey 128 vs grey 160: L* about 53.6 vs 65.8 (dL about 12): dE2000 above 6.
- Sharma 2005 pair (50, 2.6772, -79.7751) vs (50, 0, -82.7485) has dE2000 = 2.0425 (published reference value).
"""

import numpy as np
import pytest

import keyframe_gate as kg


def _flat(value, h=64, w=64):
    return np.full((h, w, 3), value, dtype=np.uint8)


def _all_valid(h=64, w=64):
    return np.ones((h, w), dtype=bool)


def test_min_ssim_is_080_not_the_097_default():
    assert kg.KEYFRAME_MIN_SSIM == 0.80


def test_max_de2000_is_6():
    assert kg.KEYFRAME_MAX_DE2000 == 6.0


def test_delta_e_reference_pair_is_wired_to_core():
    assert kg.delta_e_2000((50, 2.6772, -79.7751), (50, 0, -82.7485)) == pytest.approx(2.0425, abs=1e-3)


def test_palette_identical_background_passes():
    img = _flat(128)
    assert kg.palette_ok(img, img, _all_valid()) is True
    assert kg.palette_de2000(img, img, _all_valid()) == pytest.approx(0.0, abs=1e-9)


def test_palette_small_shift_passes():
    assert kg.palette_ok(_flat(128), _flat(130), _all_valid()) is True


def test_palette_large_shift_fails():
    assert kg.palette_ok(_flat(128), _flat(160), _all_valid()) is False


def test_palette_no_valid_pixels_fails():
    none_valid = np.zeros((64, 64), dtype=bool)
    assert kg.palette_ok(_flat(128), _flat(128), none_valid) is False
    assert kg.palette_de2000(_flat(128), _flat(128), none_valid) is None


def test_palette_accepts_float_images_in_unit_range():
    a = _flat(128).astype(np.float64) / 255.0
    b = _flat(160).astype(np.float64) / 255.0
    assert kg.palette_ok(a, b, _all_valid()) is False
    assert kg.palette_ok(a, a, _all_valid()) is True
