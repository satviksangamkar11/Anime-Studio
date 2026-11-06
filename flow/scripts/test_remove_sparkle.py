"""Synthetic checks for remove_sparkle.py: no network, no real images."""
import hashlib
import json

import cv2
import numpy as np
import pytest

import remove_sparkle as rs

ORIG, INTER = rs.ORIGINALS, rs.INTERMEDIATES


def make_group(n=6, h=900, w=1200, seed=0):
    """Same translucent 4-point stamp over different random textures, with known ground truth."""
    rng = np.random.default_rng(seed)
    truth, imgs = [], []
    for k in range(n):
        tex = 90 + 20 * np.sin(np.arange(w) / 37.0)[None, :] + rng.normal(0, 4, (h, w))
        J = np.stack([tex] * 3, axis=2).clip(0, 255)
        J[600:605, 100:700] = 40                      # a dark line far from the corner
        a = np.zeros((h, w))
        hh = rs.HALF[1]
        n_ = 2 * hh + 3
        oy, ox = h - rs.BOX + 56, w - rs.BOX + 56     # big stamp, same offset in every image
        a[oy:oy + n_, ox:ox + n_] = rs.TEMPLATES[hh] * (0.5 + 0.05 * k)
        I = (1 - a[..., None]) * J + a[..., None] * 255.0
        truth.append(J)
        imgs.append(np.round(I).astype(np.uint8))
    return imgs, truth


def test_stamp_removed_and_rest_identical():
    imgs, truth = make_group()
    items = []
    for k, rgb in enumerate(imgs):
        stamps = rs.find_stars(rgb, rs.THR)
        assert any(hh == 48 for _, hh, _, _ in stamps)
        items.append((f"t{k}", rgb, stamps))
    result = rs.process_group(items)
    for k, rgb in enumerate(imgs):
        clean, a, _ = result[f"t{k}"]
        mask = np.zeros(rgb.shape[:2], bool)
        mask[rgb.shape[0] - rs.BOX:, rgb.shape[1] - rs.BOX:] = a > 0.001
        assert np.array_equal(clean[~mask], rgb[~mask])        # outside the window: byte-identical
        core = np.zeros(rgb.shape[:2], bool)
        core[rgb.shape[0] - rs.BOX + 56 + 20: rgb.shape[0] - rs.BOX + 56 + 80,
             rgb.shape[1] - rs.BOX + 56 + 20: rgb.shape[1] - rs.BOX + 56 + 80] = True
        err = np.abs(clean[core].astype(float) - truth[k][core]).mean()
        assert err < 4.0, f"image {k}: mean error {err:.2f} in stamp core"


def test_no_star_returns_none():
    rgb = np.full((900, 1200, 3), 120, np.uint8)
    assert rs.find_stars(rgb, rs.THR) == []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rgb(path, rgb):
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def make_final(tmp_path, n=2, originals=ORIG):
    """final/ with n watermarked originals in <originals>/ and a stand-in 2K_source.jpg next to each."""
    final = tmp_path / "final"
    imgs, _ = make_group(n=n)
    for k, rgb in enumerate(imgs):
        write_rgb(final / originals / f"t{k}__candidate_v01.png", rgb)
        (final / originals / f"t{k}__candidate_v01__2K_source.jpg").write_bytes(b"\xff\xd8 stand-in \xff\xd9")
    return final, imgs


def test_cli_reads_originals_and_writes_clean_to_intermediates(tmp_path):
    final, imgs = make_final(tmp_path)
    before = {p.name: sha(p) for p in (final / ORIG).iterdir()}
    rs.main([str(final)])
    assert {p.name: sha(p) for p in (final / ORIG).iterdir()} == before          # originals untouched, nothing added
    assert not list(final.glob("*__clean.png"))                                  # nothing written to the root
    for k, rgb in enumerate(imgs):
        clean = rs.read_rgb(final / INTER / f"t{k}__candidate_v01__clean.png")
        assert clean.shape == rgb.shape and not np.array_equal(clean, rgb)
    assert len(json.loads((final / "_sparkle_check2" / "report.json").read_text())) == len(imgs)


def test_input_falls_back_to_root_and_is_backed_up(tmp_path):
    final, imgs = make_final(tmp_path)
    for p in list((final / ORIG).iterdir()):
        p.rename(final / p.name)                                                 # old layout: inputs sit in final/
    rs.main([str(final)])
    assert sha(final / ORIG / "t0__candidate_v01.png") == sha(final / "t0__candidate_v01.png")
    assert (final / INTER / "t0__candidate_v01__clean.png").is_file()
    assert not (final / "t0__candidate_v01__clean.png").exists()


def test_refuses_existing_clean_before_writing_and_flag_replaces_it(tmp_path):
    final, _ = make_final(tmp_path)
    inter = final / INTER
    inter.mkdir()
    (inter / "t1__candidate_v01__clean.png").write_bytes(b"earlier")
    with pytest.raises(FileExistsError):
        rs.run(final)
    assert (inter / "t1__candidate_v01__clean.png").read_bytes() == b"earlier"
    assert not (inter / "t0__candidate_v01__clean.png").exists()                 # nothing written before the refusal
    rs.main([str(final), "--overwrite"])
    assert (inter / "t1__candidate_v01__clean.png").read_bytes() != b"earlier"


def test_custom_folder_names(tmp_path):
    final, imgs = make_final(tmp_path, originals="orig_x")
    rs.main([str(final), "--originals", "orig_x", "--intermediates", "mid_x"])
    assert (final / "mid_x" / "t0__candidate_v01__clean.png").is_file()
    assert (final / "orig_x" / "t0__candidate_v01.png").is_file()


def test_find_input_order(tmp_path):
    final = tmp_path / "final"
    places = {ORIG: final / ORIG, INTER: final / INTER, "": final}
    for d in places.values():
        write_rgb(d / "x.png", np.full((4, 4, 3), 10, np.uint8))
    for name in (ORIG, INTER, ""):
        assert rs.find_input(final, "x.png") == places[name] / "x.png"
        (places[name] / "x.png").unlink()
    with pytest.raises(FileNotFoundError):
        rs.find_input(final, "x.png")
