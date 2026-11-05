"""Checks the anime Flow filer. Tmp folders only; fake JPEGs made with PIL. Reads (never writes) the Granth catalog via the filer."""
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import download_queue as dq  # noqa: E402

TITLE = "KRISHNA_TURNAROUND__v01"
EDIT = "34ba531b-b5c7-43fa-82a5-7b7746b57016"


def make_jpg(path: Path, size, seed: int) -> Path:
    Image.new("RGB", size, (seed * 37 % 256, seed * 91 % 256, 40)).save(path, "JPEG", quality=90)
    return path


def setup(tmp_path: Path):
    root = tmp_path / "anime_kaliya"
    dl = tmp_path / "Downloads"
    dl.mkdir()
    dq.add(root, 1, "KRISHNA_TURNAROUND", "v01", EDIT)
    return root, dl


def test_exact_title_filed_into_final(tmp_path):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", (2752, 1536), 1)
    make_jpg(dl / f"{TITLE}1_a1b2c3_2K.jpg", (2752, 1536), 2)  # near-miss title: must be ignored
    out = dq.collect(root, 1, dl)
    assert out == [f"FILED {TITLE} <- {TITLE}_a1b2c3_2K.jpg"], out
    assert (root / "adhyay_01" / "final" / "KRISHNA_TURNAROUND__candidate_v01__2K_source.jpg").is_file()
    assert dq.status(root, 1)["pending"] == []


def test_duplicate_bytes_refused(tmp_path):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", (2752, 1536), 1)
    dq.collect(root, 1, dl)
    dq.add(root, 1, "KRISHNA_ACTING_SHEET", "v01", EDIT)
    shutil.copy(dl / f"{TITLE}_a1b2c3_2K.jpg", dl / "KRISHNA_ACTING_SHEET__v01_d4e5f6_2K.jpg")
    out = dq.collect(root, 1, dl)
    assert len(out) == 1 and out[0].startswith("REFUSED KRISHNA_ACTING_SHEET__v01") and "identical" in out[0], out


def test_wrong_size_refused_and_nothing_filed(tmp_path):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", (1024, 1024), 3)
    out = dq.collect(root, 1, dl)
    assert len(out) == 1 and out[0].startswith("REFUSED") and "not 2K" in out[0], out
    assert not (root / "adhyay_01" / "final").exists()
    assert len(dq.status(root, 1)["pending"]) == 1


@pytest.mark.parametrize("size", [(2752, 1536), (1536, 2752)])
def test_both_orientations_accepted(tmp_path, size):
    root, dl = setup(tmp_path)
    make_jpg(dl / f"{TITLE}_a1b2c3_2K.jpg", size, 4)
    out = dq.collect(root, 1, dl)
    assert out[0].startswith("FILED"), out
