"""Synthetic checks for watermark_auto.py: no network, no model, no real images. Fakes stand in for both methods."""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

import watermark_auto as wa

H, W = 520, 560


def texture(h=H, w=W):
    """Same flat-ish art every time (fixed seed), so a 'cleaned' fake can rebuild it exactly."""
    rng = np.random.default_rng(0)
    tex = 90 + 20 * np.sin(np.arange(w) / 37.0)[None, :] + rng.normal(0, 4, (h, w))
    return np.stack([tex] * 3, axis=2).clip(0, 255).round().astype(np.uint8)


def dirty(clean):
    """Clean art with one real Flow stamp (big astroid, alpha 0.8) at the same offset remove_sparkle's tests use."""
    rs = wa._flow_module("remove_sparkle")
    a = np.zeros(clean.shape[:2], np.float64)
    n = rs.TEMPLATES[48].shape[0]
    oy, ox = H - rs.BOX + 56, W - rs.BOX + 56
    a[oy:oy + n, ox:ox + n] = rs.TEMPLATES[48] * 0.8
    out = (1 - a[..., None]) * clean + a[..., None] * 255.0
    return out.round().astype(np.uint8)


def save(path, rgb):
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return path


def fake_clean(rgb):
    return texture(*rgb.shape[:2])


def fake_fail(rgb):
    return rgb.copy()


def test_empty_input_refused(tmp_path):
    src = tmp_path / "empty.png"
    src.write_bytes(b"")
    with pytest.raises(wa.WatermarkInputError, match="empty"):
        wa.process(src, tmp_path / "out", lama=fake_clean, lama_on_clean=fake_fail)
    assert not (tmp_path / "out").exists()


def test_non_image_refused(tmp_path):
    src = tmp_path / "text.png"
    src.write_text("this is not a picture")
    with pytest.raises(wa.WatermarkInputError, match="not an image"):
        wa.process(src, tmp_path / "out", lama=fake_clean, lama_on_clean=fake_fail)


# WM: proven system order. lama (from the original) first, lama_on_clean second, alpha-only only with the flag.
def test_lama_is_tried_first_and_wins(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    calls = []
    rec = wa.process(src, tmp_path / "out", lama=lambda r: calls.append("lama") or fake_clean(r),
                     lama_on_clean=lambda r: calls.append("hybrid") or fake_clean(r),
                     alpha_only=lambda r: calls.append("alpha") or fake_clean(r), allow_alpha_only=True)
    assert calls == ["lama"] and rec["method"] == "lama" and rec["verified"] and rec["status"] == "clean"


def test_lama_on_clean_is_second(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    calls = []
    rec = wa.process(src, tmp_path / "out", lama=lambda r: calls.append("lama") or fake_fail(r),
                     lama_on_clean=lambda r: calls.append("hybrid") or fake_clean(r))
    assert calls == ["lama", "hybrid"] and rec["method"] == "lama_on_clean" and rec["needs_review"] is True
    assert any("lama: stamps left" in e for e in rec["errors"])


def test_failing_lama_method_falls_to_hybrid(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))

    def boom(rgb):
        raise RuntimeError("lama broke")

    rec = wa.process(src, tmp_path / "out", lama=boom, lama_on_clean=fake_clean)
    assert rec["method"] == "lama_on_clean" and any("lama broke" in e for e in rec["errors"])


def test_alpha_only_needs_the_flag(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    calls = []

    def alpha(rgb):
        calls.append(1)
        return fake_clean(rgb)

    rec = wa.process(src, tmp_path / "out", lama=fake_fail, lama_on_clean=fake_fail, alpha_only=alpha)
    assert calls == [] and rec["status"] == "needs_manual" and rec["needs_review"] is True
    rec = wa.process(src, tmp_path / "out", lama=fake_fail, lama_on_clean=fake_fail, alpha_only=alpha, allow_alpha_only=True)
    assert calls == [1] and rec["method"] == "alpha_only" and rec["needs_review"] is True


def test_all_failing_gives_needs_manual(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    rec = wa.process(src, tmp_path / "out", lama=fake_fail, lama_on_clean=fake_fail)
    assert rec["status"] == "needs_manual" and rec["verified"] is False and rec["method"] is None
    assert rec["clean_path"] is None and rec["sha256_after"] is None
    assert not (tmp_path / "out" / "pic__final.png").exists()


def test_master_is_png_with_variant_kept(tmp_path):
    src = save(tmp_path / "pic.jpg", dirty(texture()))
    rec = wa.process(src, tmp_path / "out", lama=fake_clean, lama_on_clean=fake_fail)
    master = Path(rec["clean_path"])
    assert master.name == "pic__final.png" and master.read_bytes()[1:4] == b"PNG"
    out = cv2.cvtColor(cv2.imread(str(master)), cv2.COLOR_BGR2RGB)
    assert np.array_equal(out, texture())                       # lossless
    assert (tmp_path / "out" / "_sparkle_check" / "pic__lama.png").is_file()


def test_original_never_overwritten(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    before = wa.sha256_file(src)
    wa.process(src, tmp_path / "out", lama=fake_clean)
    wa.process(src, src.parent, lama=fake_clean)               # output folder = input folder: still a new name
    assert wa.sha256_file(src) == before
    assert (src.parent / "pic__final.png").exists()


def test_record_has_the_lama_inpaint_fields_and_more(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    rec = wa.process(src, tmp_path / "out", lama=fake_clean)
    lines = (tmp_path / "out" / "watermark_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    for key in ("time", "title", "method", "verdict", "final_sha256", "weights", "backfilled", "stamps_before", "stamps_after",
                "needs_review", "sha256_before", "sha256_after"):
        assert key in row, key
    assert row["title"] == "pic" and row["method"] == "lama" and row["weights"] == "big-lama.pt"
    assert row["final_sha256"] == rec["sha256_after"] == wa.sha256_file(rec["clean_path"])
    assert row["sha256_before"] == wa.sha256_file(src)
    assert row["stamps_before"] > 0 and row["stamps_after"] == 0


def test_marginal_match_sets_needs_review(tmp_path, monkeypatch):
    src = save(tmp_path / "pic.png", dirty(texture()))
    monkeypatch.setattr(wa, "_min_score", lambda rgb: 0.66)
    assert wa.process(src, tmp_path / "out", lama=fake_clean)["needs_review"] is True
    monkeypatch.setattr(wa, "_min_score", lambda rgb: 0.95)
    assert wa.process(src, tmp_path / "out", lama=fake_clean)["needs_review"] is False


def test_missing_weights_raise_and_do_not_fall_back(tmp_path, monkeypatch):
    src = save(tmp_path / "pic.png", dirty(texture()))
    def no_weights(rgb):
        raise wa.WeightsMissingError("no weights")

    monkeypatch.setattr(wa, "_lama_method", no_weights)
    monkeypatch.setattr(wa, "_lama_on_clean_method", no_weights)
    with pytest.raises(wa.WeightsMissingError):
        wa.process(src, tmp_path / "out", alpha_only=fake_clean)
    assert not (tmp_path / "out" / "pic__final.png").exists()
    rec = wa.process(src, tmp_path / "out", alpha_only=fake_clean, allow_alpha_only=True)
    assert rec["method"] == "alpha_only" and rec["needs_review"] is True


def test_batch_counts(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    save(folder / "a_art.png", texture())
    save(folder / "b.png", dirty(texture()))
    (folder / "c.png").write_bytes(b"")
    counts = wa.process_folder(folder, tmp_path / "out", lama=fake_clean, lama_on_clean=fake_fail)
    assert counts == {"total": 3, "clean": 2, "needs_manual": 0, "refused": 1}


def test_batch_needs_manual_counted(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    save(folder / "b.png", dirty(texture()))
    counts = wa.process_folder(folder, tmp_path / "out", lama=fake_fail, lama_on_clean=fake_fail)
    assert counts == {"total": 1, "clean": 0, "needs_manual": 1, "refused": 0}


def test_failed_record_keeps_measured_stamp_count(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    expected = wa.sparkle_left(wa.load_rgb(src))
    rec = wa.process(src, tmp_path / "out", lama=fake_fail, lama_on_clean=fake_fail)
    assert expected and expected > 0
    assert rec["stamps_left"] == expected == rec["stamps_after"]


def test_calibrate_reports_counts_for_known_folders(tmp_path, capsys):
    clean_dir, dirty_dir = tmp_path / "clean", tmp_path / "dirty"
    clean_dir.mkdir()
    dirty_dir.mkdir()
    save(clean_dir / "ok.png", texture())
    save(dirty_dir / "bad.png", dirty(texture()))
    report = wa.calibrate(clean_dir, dirty_dir)
    assert report["clean"][0]["stamps"] == 0
    assert report["dirty"][0]["stamps"] > 0
    wa.main(["--calibrate", str(clean_dir), str(dirty_dir)])
    assert json.loads(capsys.readouterr().out) == report


def test_import_loads_no_torch_or_model():
    code = ("import sys; sys.path.insert(0, %r); import watermark_auto as wa; "
            "assert 'torch' not in sys.modules and 'lama_inpaint' not in sys.modules and not wa._LAMA") % str(
                Path(wa.__file__).resolve().parent)
    subprocess.run([sys.executable, "-c", code], check=True)
