"""Offline tests for build_h3_batch: aspect crop, unknown episode, frame lattice. No GPU, no network."""
import io
import base64
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_h3_batch as b  # noqa: E402


def _se_inputs(story, ep_id="EP1"):
    """W-09: legacy_rows needs routes and a lock. This gives every shot of the episode an SE route and a lock row (end position one frame short of the end)."""
    shots = next(e for e in story["episodes"] if e.get("episode_id", e.get("id")) == ep_id)["shots"]
    routes, lock = {"routes": {}}, {"shots": []}
    for sh in shots:
        sid, pf = sh["shot_id"], sh["timing_and_lattice"]["pixel_frames"]
        routes["routes"][sid] = {"route": "SE", "image_prompt_type": "SE", "input_video_strength": None}
        lock["shots"].append({"id": sid, "pixel_frames": pf, "end_frame_position": pf - 5})
    return routes, lock


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
    routes, lock = _se_inputs(story)
    row = b.legacy_rows(story, "EP1", routes=routes, lock=lock)[0][0]
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


@pytest.mark.skipif(not b.WHEEL.exists(), reason="vendored chumpy wheel not on this machine (W-01 review)")
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


def _synth_story():
    """The h3 synthetic story (h3/tests/synth.py): real compiler, real registry, episode SYN_EP1."""
    import tempfile
    from h3.tests.synth import build_story
    return build_story(tempfile.mkdtemp())


def test_prompt_override_reaches_settings():
    import h3_director
    story = _synth_story()
    routes, lock = _se_inputs(story, "SYN_EP1")
    rows = b.legacy_rows(story, "SYN_EP1", routes=routes, lock=lock)[0]
    row = dict(rows[0], id="SHOT-01")          # the synth story names its shots SYN_A; settings_for needs SHOT-NN
    s = h3_director.settings_for(row)
    assert s["prompt"] == row["prompt_override"]
    assert not s["prompt"].startswith("[Shot 1] A ")          # the prompt_for body must not replace the compiled prompt


def test_real_compiler_prompt_has_no_blank_line():
    story = _synth_story()
    routes, lock = _se_inputs(story, "SYN_EP1")
    rows = b.legacy_rows(story, "SYN_EP1", routes=routes, lock=lock)[0]
    assert len(rows) >= 1 and all("\n\n" not in r["prompt_override"] for r in rows)


def test_crlf_blank_line_collapsed(monkeypatch):
    monkeypatch.setattr(b, "compile_fl2va_prompt", lambda sh, reg: {"compiled_prompt": "a\r\n\r\nb"})
    story = {"registry": {}, "episodes": [{"episode_id": "EP1", "shots": [{"shot_id": "SHOT-001", "timing_and_lattice": {"pixel_frames": 175}}]}]}
    routes, lock = _se_inputs(story)
    assert b.legacy_rows(story, "EP1", routes=routes, lock=lock)[0][0]["prompt_override"] == "a\nb"
    # a lone CR line end and a blank line made of spaces and tabs collapse too (the regex is the real guard, see W-07)
    monkeypatch.setattr(b, "compile_fl2va_prompt", lambda sh, reg: {"compiled_prompt": "a\r \t\r\n\rb"})
    assert b.legacy_rows(story, "EP1", routes=routes, lock=lock)[0][0]["prompt_override"] == "a\nb"
