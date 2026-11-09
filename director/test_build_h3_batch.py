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


def test_pip_install_is_retried_after_a_transient_failure():
    """Render attempt S009-1: one GitHub 504 on a pip wheel killed the whole run in 5 s. The hardened script retries the install."""
    s = b.harden(b.run_kaggle.RUNNER)
    assert "sh_retry(f\"cd {APP} && " in s and "&& pip install -r requirements.txt\", \"setup.log\")" in s
    start = s.index("def sh_retry")
    ns = {"calls": [], "waits": []}
    exec(s[start:s.index("def sh(", start)], ns)               # the helper alone, with stub shell / note / time
    results = iter([1, 1, 0])
    ns["sh"] = lambda cmd, log: ns["calls"].append(cmd) or next(results)
    ns["note"] = lambda m: None
    ns["time"] = type("T", (), {"sleep": staticmethod(lambda n: ns["waits"].append(n))})
    assert ns["sh_retry"]("pip x", "setup.log") == 0 and len(ns["calls"]) == 3 and ns["waits"] == [30, 60]
    ns["calls"].clear()
    results = iter([1, 1, 1, 1, 0])
    assert ns["sh_retry"]("pip x", "setup.log") == 1 and len(ns["calls"]) == 4           # gives up after 4 tries and reports the failure


def test_script_reads_the_hf_token_when_present():
    s = b.harden(b.run_kaggle.RUNNER)
    assert s.count('os.environ["HF_TOKEN"] = open("/content/.hf_token").read().strip()') == 1 and s.index('HF_HOME') < s.index('HF_TOKEN')
    assert "hf_" not in s.replace("HF_", "").replace("/content/.hf_token", "").replace("hf_home", "")    # the token itself is never in the script


def test_vendored_wheel_is_shipped_and_the_install_points_at_it(tmp_path):
    b.write_wheel_upload(tmp_path)
    up = (tmp_path / "upload_wheel.py").read_text(encoding="utf-8")
    assert "/content/wheels" in up and "chumpy-0.71-py3-none-any.whl" in up and "b64decode(" in up
    s = b.harden(b.run_kaggle.RUNNER)
    assert "sed -i 's#^chumpy.*#chumpy @ file:///content/wheels/chumpy-0.71-py3-none-any.whl#' requirements.txt" in s and "sh_retry(" in s


def test_a_wheel_with_another_hash_is_refused(tmp_path):
    bad = tmp_path / "chumpy-0.71-py3-none-any.whl"
    bad.write_bytes(b"not the wheel")
    with pytest.raises(ValueError, match="not the verified"):
        b.write_wheel_upload(tmp_path, wheel=bad)
