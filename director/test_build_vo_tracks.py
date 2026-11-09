"""Offline tests for build_vo_tracks.pack_shot (pure timing) and scripted_lines. No ffmpeg."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vo_tracks as b  # noqa: E402


def test_a_line_that_fits_keeps_tempo_one_and_its_start():
    t, p = b.pack_shot([{"id": "A", "start": 0.3, "natural": 3.0}], 6.0)
    assert t == 1.0 and p[0]["start"] == 0.3 and p[0]["end"] == 3.3


def test_the_smallest_tempo_that_fits_is_used():
    t, p = b.pack_shot([{"id": "A", "start": 0.3, "natural": 3.5}, {"id": "B", "start": 4.5, "natural": 2.5}], 7.0)
    assert 1.0 < t <= 1.15 and p[-1]["end"] <= 7.0 - b.TAIL + 1e-6 and p[1]["start"] >= p[0]["end"] + b.GAP - 1e-6


def test_overlap_pushes_the_next_line_later_by_the_gap():
    _, p = b.pack_shot([{"id": "A", "start": 0.0, "natural": 2.0}, {"id": "B", "start": 1.0, "natural": 1.0}], 8.0)
    assert p[1]["start"] == pytest.approx(2.12, abs=1e-3)


def test_a_shot_that_cannot_fit_is_reported_not_cut():
    with pytest.raises(ValueError, match="does not fit"):
        b.pack_shot([{"id": "A", "start": 0.3, "natural": 5.0}, {"id": "B", "start": 5.0, "natural": 4.0}], 7.0)


def test_scripted_lines_reads_narration_and_dialogue():
    row = {"id": "SHOT-009", "audio_and_dialogue_track": {
        "narration_by_lang": {"en": {"text": "n", "time_range": [5.9, 8.0]}},
        "dialogue_by_lang": {"en": [{"text": "d", "time_range": [1.2, 5.8]}]}}}
    assert b.scripted_lines(row, "en") == [("SHOT-009-N", 5.9), ("SHOT-009-D1", 1.2)]
    assert b.scripted_lines(row, "hi") == []
