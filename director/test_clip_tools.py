"""G13: clip_tools subcommands are explicit; a typo can no longer run the last-frame step. No ffmpeg is called (both steps are faked)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_tools  # noqa: E402


@pytest.fixture
def calls(monkeypatch):
    seen = []
    monkeypatch.setattr(clip_tools, "qa", lambda clip, out: seen.append(("qa", clip, out)) or {"ok": True})
    monkeypatch.setattr(clip_tools, "last_frame", lambda clip, png: seen.append(("last", clip, png)) or png)
    return seen


def test_qa_subcommand_runs_only_the_qa_step(calls):
    assert clip_tools.main(["qa", "clip.mp4", "out"]) == 0
    assert calls == [("qa", "clip.mp4", "out")]


def test_last_subcommand_runs_only_the_last_frame_step(calls):
    assert clip_tools.main(["last", "clip.mp4", "next.png"]) == 0
    assert calls == [("last", "clip.mp4", "next.png")]


def test_unknown_subcommand_is_refused_and_runs_nothing(calls, capsys):
    assert clip_tools.main(["lst", "clip.mp4", "next.png"]) == 2
    assert calls == [] and "usage" in capsys.readouterr().err


def test_two_arguments_without_a_subcommand_keep_the_old_last_frame_behaviour(calls):
    assert clip_tools.main(["clip.mp4", "next.png"]) == 0
    assert calls == [("last", "clip.mp4", "next.png")]


def test_no_arguments_prints_usage(calls):
    assert clip_tools.main([]) == 2 and calls == []
