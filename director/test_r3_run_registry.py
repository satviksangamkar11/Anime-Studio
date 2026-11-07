"""Round-3 regression (triage R3-DIR): an empty voice_engine map is refused, nothing is written."""
import pytest

import run_registry as rr


def test_empty_voice_engine_map_is_refused_and_nothing_is_written(tmp_path):
    with pytest.raises(ValueError, match="voice_engine"):
        rr.append_event(tmp_path, "20261107-0101-ab", "analysis_done", None, "ok", voice_engine={})
    assert not (tmp_path / rr.RUNS_FILE).exists()


def test_a_real_voice_engine_map_is_still_accepted(tmp_path):
    ev = rr.append_event(tmp_path, "20261107-0101-ab", "analysis_done", None, "ok", voice_engine={"en": "h3", "hi": "elevenlabs"})
    assert ev["voice_engine"] == {"en": "h3", "hi": "elevenlabs"}
