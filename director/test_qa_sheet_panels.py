"""WP9 / A16: the clip QA sheet from clip_tools.qa carries a 270 px thumbnail panel and a deuteranopia panel (core.cvd)."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_tools  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from core.cvd import simulate_deuteranopia  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                                  reason="ffmpeg/ffprobe not on PATH")
TILE_W, TILE_H = 1440, 360          # three 480 px frames, 320x240 source scaled to 480 wide


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "synthetic.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=1",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@needs_ffmpeg
def test_qa_sheet_gets_thumbnail_and_deuteranopia_panels(clip, tmp_path):
    report = clip_tools.qa(clip, tmp_path / "out")
    assert report["panels"] == ["first_mid_last", "thumb_270", "deuteranopia_270"]
    sheet = Image.open(report["sheet"]).convert("RGB")
    assert sheet.width == TILE_W and sheet.height > TILE_H          # panel row added under the tile
    panel = sheet.crop((0, TILE_H, 540, sheet.height))              # thumb (0-270) | deuteranopia (270-540)
    left, right = panel.crop((0, 0, 270, panel.height)), panel.crop((270, 0, 540, panel.height))
    assert ImageChops.difference(right, simulate_deuteranopia(left)).getbbox() is None   # reused core.cvd, exact
    assert ImageChops.difference(left, right).getbbox() is not None                     # colours really changed


@needs_ffmpeg
def test_qa_still_writes_the_qa_json_with_the_sheet_path(clip, tmp_path):
    report = clip_tools.qa(clip, tmp_path / "out")
    assert Path(report["sheet"]).is_file()
    assert (tmp_path / "out" / "synthetic_qa.json").is_file()
