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
        wa.process(src, tmp_path / "out", first=fake_clean)
    assert not (tmp_path / "out").exists()


def test_non_image_refused(tmp_path):
    src = tmp_path / "text.png"
    src.write_text("this is not a picture")
    with pytest.raises(wa.WatermarkInputError, match="not an image"):
        wa.process(src, tmp_path / "out", first=fake_clean)


def test_clean_image_passes_untouched(tmp_path):
    src = save(tmp_path / "pic.png", texture())
    calls = []
    rec = wa.process(src, tmp_path / "out", first=lambda r: calls.append(1) or r.copy(), fallback=fake_fail)
    assert rec["verified"] and rec["status"] == "clean" and rec["method"] == "remove_sparkle"
    assert calls == [1] and rec["sha256_after"] is not None
    out = cv2.cvtColor(cv2.imread(rec["clean_path"]), cv2.COLOR_BGR2RGB)
    assert np.array_equal(out, texture())


def test_dirty_image_cleaned_by_first_method(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    fallback_calls = []
    rec = wa.process(src, tmp_path / "out", first=fake_clean,
                     fallback=lambda r: fallback_calls.append(1) or r)
    assert rec["verified"] and rec["method"] == "remove_sparkle"
    assert fallback_calls == []
    assert Path(rec["clean_path"]).name == "pic_clean.png"


def test_first_method_failing_falls_back(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))

    def boom(rgb):
        raise RuntimeError("remove_sparkle broke")

    rec = wa.process(src, tmp_path / "out", first=boom, fallback=fake_clean)
    assert rec["verified"] and rec["method"] == "lama"
    assert any("remove_sparkle broke" in e for e in rec["errors"])


def test_first_method_dirty_result_falls_back(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    rec = wa.process(src, tmp_path / "out", first=fake_fail, fallback=fake_clean)
    assert rec["method"] == "lama" and rec["verified"]


def test_both_failing_gives_needs_manual(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    rec = wa.process(src, tmp_path / "out", first=fake_fail, fallback=fake_fail)
    assert rec["status"] == "needs_manual" and rec["verified"] is False and rec["method"] is None
    assert rec["clean_path"] is None and rec["sha256_after"] is None
    assert not (tmp_path / "out" / "pic_clean.png").exists()


def test_original_never_overwritten(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    before = wa.sha256_file(src)
    wa.process(src, tmp_path / "out", first=fake_clean)
    wa.process(src, src.parent, first=fake_clean)          # output folder = input folder: still a new name
    assert wa.sha256_file(src) == before
    assert (src.parent / "pic_clean.png").exists()


def test_record_line_written(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    rec = wa.process(src, tmp_path / "out", first=fake_clean)
    lines = (tmp_path / "out" / "watermark_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["path"] == str(src) and row["method"] == "remove_sparkle" and row["verified"] is True
    assert row["sha256_before"] == wa.sha256_file(src) and row["sha256_after"] == rec["sha256_after"]


def test_batch_counts(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    save(folder / "a_clean_art.png", texture())
    save(folder / "b.png", dirty(texture()))
    (folder / "c.png").write_bytes(b"")
    counts = wa.process_folder(folder, tmp_path / "out", first=fake_clean, fallback=fake_fail)
    assert counts == {"total": 3, "clean": 2, "needs_manual": 0, "refused": 1}


def test_batch_needs_manual_counted(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    save(folder / "b.png", dirty(texture()))
    counts = wa.process_folder(folder, tmp_path / "out", first=fake_fail, fallback=fake_fail)
    assert counts == {"total": 1, "clean": 0, "needs_manual": 1, "refused": 0}


def test_failed_record_keeps_measured_stamp_count(tmp_path):
    src = save(tmp_path / "pic.png", dirty(texture()))
    expected = wa.sparkle_left(wa.load_rgb(src))
    rec = wa.process(src, tmp_path / "out", first=fake_fail, fallback=fake_fail)
    assert expected and expected > 0
    assert rec["stamps_left"] == expected


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
