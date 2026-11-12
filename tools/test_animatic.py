import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animatic as a  # noqa: E402

FFMPEG = shutil.which("ffmpeg")


def _fake_run(args, **kwargs):
    _fake_run.calls.append(args)
    Path(args[-1]).write_bytes(b"mp4")
    return subprocess.CompletedProcess(args, 0, "", "")


def _fail_run(args, **kwargs):
    return subprocess.CompletedProcess(args, 1, "", "boom")


def _img(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"png")
    return str(p)


def test_concat_list_repeats_last_still_and_escapes_quotes():
    text = a.ffconcat_text([("a.png", 2.0), ("it's.png", 1.5)])
    assert text == "file 'a.png'\nduration 2.000\nfile 'it'\\''s.png'\nduration 1.500\nfile 'it'\\''s.png'\n"


def test_shot_splits_a_and_b_halves():
    entries = a.shots_to_entries([{"shot_id": "SHOT-001", "a": "A.png", "b": "B.png", "seconds": 4.0},
                                  {"shot_id": "SHOT-002", "a": "C.png", "b": None, "seconds": 3.0}])
    assert entries == [("A.png", 2.0), ("B.png", 2.0), ("C.png", 3.0)]


def test_zero_seconds_rejected():
    with pytest.raises(ValueError):
        a.shots_to_entries([{"shot_id": "SHOT-001", "a": "A.png", "b": None, "seconds": 0}])


def test_missing_still_rejected(tmp_path):
    with pytest.raises(ValueError):
        a.check_entries([(str(tmp_path / "nope.png"), 1.0)])


def test_command_is_24fps_h264_and_takes_guide_audio():
    cmd = a.build_command("list.txt", "guide.wav", "out.mp4")
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-r") + 1] == "24"
    assert cmd[cmd.index("-c:v") + 1] == "libx264" and cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert "-shortest" in cmd and cmd.count("-i") == 2
    assert cmd[-1] == "out.mp4"


def test_command_without_audio_has_one_input():
    assert a.build_command("list.txt", None, "out.mp4").count("-i") == 1


def test_make_animatic_runs_ffmpeg_and_returns_path(tmp_path):
    img = _img(tmp_path, "a.png")
    _fake_run.calls = []
    out = a.make_animatic([(img, 1.0)], tmp_path / "animatic_en.mp4", guide=None, runner=_fake_run)
    assert Path(out).exists() and _fake_run.calls[0][0] == "ffmpeg"


def test_make_animatic_raises_on_ffmpeg_failure(tmp_path):
    img = _img(tmp_path, "a.png")
    with pytest.raises(RuntimeError):
        a.make_animatic([(img, 1.0)], tmp_path / "x.mp4", guide=None, runner=_fail_run)


def test_one_mp4_per_language(tmp_path):
    img = _img(tmp_path, "a.png")
    _fake_run.calls = []
    outs = a.make_all({"en": [(img, 1.0)], "hi": [(img, 1.0)]}, tmp_path, guides={"en": None, "hi": None},
                      runner=_fake_run)
    assert sorted(outs) == ["en", "hi"]
    assert outs["en"].name == "animatic_en.mp4" and outs["hi"].name == "animatic_hi.mp4"


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not on PATH")
def test_real_ffmpeg_output_is_24fps(tmp_path):
    png = tmp_path / "red.png"
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x64", "-frames:v", "1",
                    str(png)], check=True)
    out = a.make_animatic([(str(png), 1.0), (str(png), 1.0)], tmp_path / "animatic_en.mp4", guide=None)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=r_frame_rate", "-of", "csv=p=0", str(out)], capture_output=True, text=True)
    assert probe.stdout.strip() == "24/1"


# M-31: an empty still list is a clear validation error, not an IndexError in ffconcat_text
def test_empty_entries_refused():
    with pytest.raises(ValueError, match="at least one still"):
        a.check_entries([])
