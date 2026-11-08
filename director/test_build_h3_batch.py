"""Offline tests for build_h3_batch: aspect crop, unknown episode, frame lattice. No GPU, no network."""
import io
import base64
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_h3_batch as b  # noqa: E402


def test_jpeg_is_cropped_not_stretched(tmp_path):
    im = Image.new("RGB", (864, 1536), (10, 20, 30))
    im.putpixel((0, 700), (255, 0, 0))               # a pixel in the left edge: cropped away by the centred crop
    p = tmp_path / "k.png"
    im.save(p)
    out = Image.open(io.BytesIO(base64.b64decode(b.jpeg_b64(p)))).convert("RGB")
    assert out.size == (768, 1344)
    assert out.getpixel((0, 600))[0] < 100            # no red column left: a stretch would keep the edge


def test_unknown_episode_raises():
    with pytest.raises(ValueError, match="unknown episode"):
        b.legacy_rows({"episodes": [{"episode_id": "EP1", "shots": []}], "registry": {}}, "EP9")


def test_prompt_has_no_blank_line(monkeypatch):
    raw = "line one\n\nline two\n \nline three"
    monkeypatch.setattr(b, "compile_fl2va_prompt", lambda sh, reg: {"compiled_prompt": raw})
    story = {"registry": {}, "episodes": [{"episode_id": "EP1", "shots": [{"shot_id": "SHOT-001", "timing_and_lattice": {"pixel_frames": 175}}]}]}
    row = b.legacy_rows(story, "EP1")[0]
    assert row["prompt_override"] == "line one\nline two\nline three"
