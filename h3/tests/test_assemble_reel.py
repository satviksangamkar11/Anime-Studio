import os
import subprocess

import pytest

from h3.assemble_reel import build_ffmpeg_assembly_plan, write_assembly_script


def _shots(story):
    return story["episodes"][0]["shots"]


def test_every_shot_has_5ms_afade_in_and_out(story):
    fc = build_ffmpeg_assembly_plan(_shots(story), "out.mp4")["filter_complex"]
    for i in range(3):
        assert f"[{i}:a]atrim=" in fc
    assert fc.count("afade=t=in:st=0:d=0.005") == 3
    assert fc.count("afade=t=out:st=") == 3 and fc.count(":d=0.005[a") == 3


def test_concat_chain_and_trim_values(story):
    plan = build_ffmpeg_assembly_plan(_shots(story), "out.mp4")
    fc = plan["filter_complex"]
    assert "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[vcat][aout];[vcat]scale=out_color_matrix=bt709:out_range=tv[vout]" in fc
    assert "[0:v]trim=start_frame=0:end_frame=145,setpts=PTS-STARTPTS[v0]" in fc
    assert "[1:a]atrim=start=0.50:end=6.04" in fc


def test_frame_totals(story):
    plan = build_ffmpeg_assembly_plan(_shots(story), "out.mp4")
    assert plan["total_frames"] == 145 + 133 + 175 == 453
    assert plan["total_duration_sec"] == round(453 / 24, 2)
    assert plan["n_shots"] == 3 and plan["fps"] == 24


def test_seam_transitions_with_pose_deltas(story):
    seams = build_ffmpeg_assembly_plan(_shots(story), "out.mp4")["seam_transitions"]
    assert [(s["from_shot"], s["to_shot"], s["frame"]) for s in seams] == [("SYN_A", "SYN_B", 145), ("SYN_B", "SYN_C", 278)]
    assert seams[0]["outgoing_seam_type"] == "DYNAMIC_MATCH_ON_ACTION"
    assert seams[1]["incoming_seam_type"] == "CHAINED_POSE_HOLD"
    d0, d1 = seams[0]["pose_delta"], seams[1]["pose_delta"]
    assert d0 == pytest.approx({"torso_pitch_deg": 0.5, "knee_flex_deg": -1.0, "com_y_ratio": 0.01}, abs=1e-9)
    assert d1 == pytest.approx({"torso_pitch_deg": 0.5, "knee_flex_deg": 0.5, "com_y_ratio": 0.005}, abs=1e-9)


def test_write_assembly_script_writes_files_and_never_runs_ffmpeg(story, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ffmpeg / subprocess must not run")
    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, boom)
    monkeypatch.setattr(os, "system", boom)
    plan = build_ffmpeg_assembly_plan(_shots(story), "out.mp4")
    clips = [str(tmp_path / f"clip_{i}.mp4") for i in range(3)]
    paths = write_assembly_script(plan, clips, str(tmp_path / "asm"))
    with open(paths["filter"], encoding="utf-8") as f:
        assert f.read() == plan["filter_complex"]
    with open(paths["cmd"], encoding="utf-8") as f:
        cmd = f.read()
    assert os.path.basename(paths["cmd"]) == "assemble.cmd"
    assert "-filter_complex_script filter.txt" in cmd and "-r 24" in cmd
    assert cmd.count("-i ") == 3 and '-map "[vout]" -map "[aout]"' in cmd


def test_write_assembly_script_rejects_clip_count_mismatch(story, tmp_path):
    plan = build_ffmpeg_assembly_plan(_shots(story), "out.mp4")
    with pytest.raises(ValueError, match="expected 3 clips"):
        write_assembly_script(plan, ["only_one.mp4"], str(tmp_path))
