"""yt_transcript.main with the Whisper fallback wired in (all network and model calls mocked)."""
import shutil
from pathlib import Path

import asr_transcribe
import yt_transcript

STUDIO = Path(__file__).resolve().parent.parent
SLUG = "zz_test_tmp_story"
URL = "https://youtu.be/AAAAAAAAAAA"


def _run(monkeypatch, result, extra=()):
    monkeypatch.setattr(asr_transcribe, "_meta", lambda url: {"title": "T", "channel": "C"})
    monkeypatch.setattr(asr_transcribe, "get_transcript", lambda *a, **k: result)
    monkeypatch.setattr(asr_transcribe, "transcribe_url", lambda *a, **k: result)
    return yt_transcript.main([URL, f"stories/{SLUG}", *extra])


def _clean():
    shutil.rmtree(STUDIO / "stories" / SLUG, ignore_errors=True)


def test_captions_result_written(monkeypatch):
    _clean()
    try:
        r = {"engine": "captions", "text": "नमस्ते दुनिया", "language": "hi", "params": {"track": "manual"}}
        assert _run(monkeypatch, r) == 0
        src = (STUDIO / "stories" / SLUG / "SOURCE.md").read_text(encoding="utf-8")
        assert "YouTube captions (manual)" in src and "नमस्ते दुनिया" in src
    finally:
        _clean()


def test_whisper_result_is_labelled_for_owner_check(monkeypatch):
    _clean()
    try:
        r = {"engine": "local", "model": "large-v3-turbo", "text": "कथा शुरू", "language": "mr", "language_confidence": 0.97}
        assert _run(monkeypatch, r) == 0
        src = (STUDIO / "stories" / SLUG / "SOURCE.md").read_text(encoding="utf-8")
        assert "SPEECH RECOGNITION" in src and "large-v3-turbo" in src and "owner checks" in src
    finally:
        _clean()


def test_unclear_language_exits_3_and_writes_nothing(monkeypatch, capsys):
    _clean()
    try:
        r = {"needs_choice": True, "candidates": ["hi", "mr"]}
        assert _run(monkeypatch, r) == 3
        assert "NEEDS_CHOICE" in capsys.readouterr().out
        assert not (STUDIO / "stories" / SLUG / "SOURCE.md").exists()
    finally:
        _clean()
