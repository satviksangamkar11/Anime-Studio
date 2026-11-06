"""run_registry event fields output_languages and voice_engine: optional, validated, backward compatible."""
import json
from pathlib import Path

import pytest

import run_registry as rr


def _last(story_dir):
    lines = (Path(story_dir) / rr.RUNS_FILE).read_text(encoding="utf-8").splitlines()
    return json.loads(lines[-1])


def test_old_event_without_language_fields_still_writes(tmp_path):
    ev = rr.append_event(tmp_path, "run1", "story_saved", None, "ok")
    assert "output_languages" not in ev and "voice_engine" not in ev


def test_language_fields_are_written(tmp_path):
    rr.append_event(tmp_path, "run1", "story_saved", None, "ok", output_languages=["en", "hi"],
                    voice_engine={"en": "elevenlabs", "hi": "elevenlabs"})
    ev = _last(tmp_path)
    assert ev["output_languages"] == ["en", "hi"]
    assert ev["voice_engine"] == {"en": "elevenlabs", "hi": "elevenlabs"}


@pytest.mark.parametrize("langs", [["fr"], ["en", "en"], "en"])
def test_bad_output_languages_are_refused_and_nothing_is_written(tmp_path, langs):
    with pytest.raises(ValueError):
        rr.append_event(tmp_path, "run1", "story_saved", None, "ok", output_languages=langs)
    assert not (tmp_path / rr.RUNS_FILE).exists()


@pytest.mark.parametrize("engines", [{"en": "azure"}, {"fr": "elevenlabs"}, ["en"]])
def test_bad_voice_engine_is_refused(tmp_path, engines):
    with pytest.raises(ValueError):
        rr.append_event(tmp_path, "run1", "story_saved", None, "ok", voice_engine=engines)
    assert not (tmp_path / rr.RUNS_FILE).exists()


def test_h3_is_an_allowed_engine(tmp_path):
    rr.append_event(tmp_path, "run1", "story_saved", None, "ok", voice_engine={"en": "h3"})
    assert _last(tmp_path)["voice_engine"] == {"en": "h3"}


def test_empty_language_list_is_dropped_like_other_empty_values(tmp_path):
    ev = rr.append_event(tmp_path, "run1", "story_saved", None, "ok", output_languages=[])
    assert "output_languages" not in ev
