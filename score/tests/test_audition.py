"""Tests for score/audition.py. Unit parts need no ffmpeg; the CLI test is skipped when ffmpeg or the reel is missing."""
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from score import audition as au
from score import note_writer as nw
from score.tests.test_note_writer import REEL_PLAN

NOTES = {
    "pad": [{"t_s": 0.5, "dur_s": 1.0, "pitch": 62, "vel": 100}],
    "drums": [{"t_s": 0.0, "dur_s": 0.3, "pitch": 36, "vel": 127}, {"t_s": 0.5, "dur_s": 0.2, "pitch": 42, "vel": 90}],
    "risers": [{"t_s": 1.0, "dur_s": 0.5, "pitch": 50, "vel": 80}],
}

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe not on PATH")


def test_midi_to_hz():
    assert au.midi_to_hz(69) == pytest.approx(440.0)
    assert au.midi_to_hz(38) == pytest.approx(73.42, abs=0.01)
    assert au.midi_to_hz(62) == pytest.approx(293.66, abs=0.01)


def test_render_length_and_peak():
    out = au.render_notes(NOTES, 2.0)
    assert out.shape == (88200, 2)
    peak = float(np.abs(out).max())
    assert 0.0 < peak <= 1.0
    assert peak == pytest.approx(au.PEAK)


def test_silent_roles_give_silence():
    assert not np.any(au.render_notes({}, 1.0))
    assert not np.any(au.render_notes({"pad": []}, 1.0))


def test_render_is_deterministic():
    assert np.array_equal(au.render_notes(NOTES, 2.0), au.render_notes(NOTES, 2.0))


FROZEN_CUE_V3 = Path(__file__).resolve().parent / "fixtures" / "cue_sheet_reel1_v3.json"  # frozen v3 (70.0 s)


def test_reel_sketch_is_exactly_70_s():
    cue = json.loads(FROZEN_CUE_V3.read_text(encoding="utf-8"))
    bible = json.loads(au.BIBLE.read_text(encoding="utf-8"))
    rep = nw.write_notes(REEL_PLAN, cue, bible)
    assert rep["ok"], rep["errors"]
    out = au.render_notes(rep["tracks"], au.SKETCH_S)
    assert out.shape == (int(round(70.0 * au.SR)), 2)
    assert float(np.abs(out).max()) <= 1.0


def test_theme_tracks_cover_all_six_themes():
    bible = json.loads(au.BIBLE.read_text(encoding="utf-8"))
    tracks, total = au.theme_tracks(bible)
    notes = [n for v in tracks.values() for n in v]
    assert len(notes) == sum(len(bible["themes"][k]["degrees"].split()) for k in au.THEME_ORDER) + 3
    assert total > max(n["t_s"] + n["dur_s"] for n in notes)


@needs_ffmpeg
def test_cli_builds_three_files(tmp_path, monkeypatch):
    if not au.REEL_EXPORT.exists():
        pytest.skip("reel export not present")
    monkeypatch.setattr(au, "CUE", FROZEN_CUE_V3)   # REEL_PLAN is the 70 s v3 plan; the live sheet is now v4 (72.833 s)
    paths = au.build(tmp_path)
    assert [p.name for p in paths] == ["M0_1_themes.mp3", "M0_2_reel_sketch_70s.mp3", "M0_3_reel_sketch_with_voice_en.mp4"]
    assert abs(au.probe_duration(paths[1]) - 70.0) <= 0.05
    assert abs(au.probe_duration(paths[2]) - 70.0) <= 0.1


def test_plan_cue_cuts_variant_a_to_its_window():
    cue = json.loads(FROZEN_CUE_V3.read_text(encoding="utf-8"))
    cue["cuts"] = [{"at_s": 6.0, "at_frame": 144, "hard_cut": False, "act_change": False},
                   {"at_s": 18.833, "at_frame": 452, "hard_cut": True, "act_change": False}]
    plan = {"window_s": [0.0, 18.833]}
    out, end = au.plan_cue(plan, cue)
    assert end == pytest.approx(18.833)
    assert out["total_s"] == pytest.approx(18.833)
    assert [c["at_s"] for c in out["cuts"]] == [6.0]
    assert all(float(s["end_s"]) <= 18.833 for s in out["shots"])
    assert out["retention"]["rehook_window_s"] is None
    assert cue["total_s"] != out["total_s"]  # the input cue is not modified


def test_plan_cue_leaves_a_full_plan_alone():
    cue = json.loads(FROZEN_CUE_V3.read_text(encoding="utf-8"))
    out, end = au.plan_cue({"variant": "B"}, cue)
    assert out is cue and end is None


@needs_ffmpeg
def test_cli_variant_a_window_length(tmp_path):
    v4 = ROOT_STORY = Path(au.ROOT) / "stories" / "kalika_puran_bhag1" / "pack_opus_high_20261108_v4_deva" / "score" / "ep1"
    paths = au.build_plan(tmp_path, str(v4 / "score_plan_A_0_18.json"), str(v4 / "cue_sheet.json"), None, "M1_A_0_18")
    assert [p.name for p in paths] == ["M1_A_0_18.mp3"]
    assert abs(au.probe_duration(paths[0]) - 18.833) <= 0.05
