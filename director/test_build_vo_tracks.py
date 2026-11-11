"""Offline tests for build_vo_tracks.pack_shot (pure timing) and scripted_lines. No ffmpeg."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vo_tracks as b  # noqa: E402


def test_a_line_that_fits_keeps_tempo_one_and_its_start():
    t, p = b.pack_shot([{"id": "A", "start": 0.3, "natural": 3.0}], 6.0)
    assert t == 1.0 and p[0]["start"] == 0.3 and p[0]["end"] == 3.3


def test_no_speed_up_when_the_lines_do_not_fit_at_natural_speed():
    # W-04 (owner: no atempo): this used to pass at tempo 1.15; now the shot is reported, never sped up
    with pytest.raises(ValueError, match="does not fit"):
        b.pack_shot([{"id": "A", "start": 0.3, "natural": 3.5}, {"id": "B", "start": 4.5, "natural": 2.5}], 7.0)


def test_overlap_pushes_the_next_line_later_by_the_gap():
    _, p = b.pack_shot([{"id": "A", "start": 0.0, "natural": 2.0}, {"id": "B", "start": 1.0, "natural": 1.0}], 8.0)
    assert p[1]["start"] == pytest.approx(2.12, abs=1e-3)


def test_a_shot_that_cannot_fit_is_reported_not_cut():
    with pytest.raises(ValueError, match="does not fit"):
        b.pack_shot([{"id": "A", "start": 0.3, "natural": 5.0}, {"id": "B", "start": 5.0, "natural": 4.0}], 7.0)


def test_needed_sec_at_a_speed_up_is_shorter():
    """Card case: one line, start 0, natural 3.5. Natural speed (tempo 1.0) gives 3.5 + TAIL = 3.6; a 1.5x speed-up
    gives 3.5 / 1.5 + TAIL (the card's '2.5 + TAIL' does not follow from its own inputs)."""
    assert b.MAX_TEMPO == 1.0   # pack_shot never speeds up by itself: the speed-up is only the tempo passed in
    lines = [{"id": "a", "start": 0, "natural": 3.5}]
    assert abs(b.needed_sec(lines, 1.0) - (3.5 + b.TAIL)) < 1e-6
    assert abs(b.needed_sec(lines, 1.5) - (3.5 / 1.5 + b.TAIL)) < 1e-3   # pack_shot rounds lengths to 3 decimals
    assert b.needed_sec(lines, 1.5) < b.needed_sec(lines, 1.0)


def test_build_refuses_to_run_without_a_lock(tmp_path):
    with pytest.raises(ValueError, match="--lock is required"):
        b.build(tmp_path, tmp_path, tmp_path / "out", ["en"], lock=None)


def test_cli_requires_lock_flag(tmp_path):
    with pytest.raises(SystemExit) as exc:
        b.main(["--pack", str(tmp_path), "--raw", str(tmp_path), "--out", str(tmp_path)])
    assert exc.value.code == 2


def test_scripted_lines_reads_narration_and_dialogue():
    row = {"id": "SHOT-009", "audio_and_dialogue_track": {
        "narration_by_lang": {"en": {"text": "n", "time_range": [5.9, 8.0]}},
        "dialogue_by_lang": {"en": [{"text": "d", "time_range": [1.2, 5.8]}]}}}
    assert b.scripted_lines(row, "en") == [("SHOT-009-N", 5.9), ("SHOT-009-D1", 1.2)]
    assert b.scripted_lines(row, "hi") == []
