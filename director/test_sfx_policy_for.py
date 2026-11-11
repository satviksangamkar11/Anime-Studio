"""Offline test for X-18 (rule 50(6)): build_final_reel.sfx_policy_for builds one policy entry per shot from clip_qa.json and the
shot's voice RMS. A shot with no voice file gets no ducking and no level. A missing clip_qa.json raises. Synthetic WAVs and JSON only;
no ffmpeg, no model call, no network."""
import json
import sys
import wave
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_final_reel as b  # noqa: E402

RATE = 48000


def write_const_wav(path, value, n):
    """Mono 16-bit WAV with n samples of a constant value in -1..1."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(int(round(value * 32767)).to_bytes(2, "little", signed=True) * n)


def write_qa(clip_dir, bed_db, keep):
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "clip.mp4").write_bytes(b"")
    (clip_dir / "clip_qa.json").write_text(json.dumps({"bed_db": bed_db, "sfx_keep": keep}), encoding="utf-8")
    return str(clip_dir / "clip.mp4")


def test_policy_and_levels_from_clip_qa_and_voice(tmp_path):
    # voice RMS over the 0-1 s line is -18 dB (constant 10^(-18/20)); bed -30 dB -> gain = min(0, (-18-22) - (-30)) = -10 dB
    vo_dir = tmp_path / "vo"
    (vo_dir / "en").mkdir(parents=True)
    write_const_wav(vo_dir / "en" / "s1.wav", 10 ** (-18.0 / 20), RATE)
    clips = {"s1": write_qa(tmp_path / "clips" / "s1", -30.0, [[0.5, 1.5]])}
    vo_report = [{"shot": "s1", "lang": "en", "lines": [{"start": 0.0, "end": 1.0}]}]
    policy, levels = b.sfx_policy_for([{"id": "s1"}], clips, vo_dir, "en", vo_report)
    assert len(policy) == 1 and policy[0]["keep"] == [(0.5, 1.5)]
    assert policy[0]["bed_gain_db"] == pytest.approx(-10.0, abs=0.05)
    assert levels[0]["shot"] == "s1" and levels[0]["bed_db"] == -30.0
    assert levels[0]["voice_db"] == pytest.approx(-18.0, abs=0.05)


def test_shot_without_voice_file_gets_no_policy_and_no_level(tmp_path):
    vo_dir = tmp_path / "vo"
    (vo_dir / "en").mkdir(parents=True)
    clips = {"s1": write_qa(tmp_path / "clips" / "s1", -30.0, [[0.5, 1.5]]),
             "s2": write_qa(tmp_path / "clips" / "s2", -30.0, [])}
    policy, levels = b.sfx_policy_for([{"id": "s1"}, {"id": "s2"}], clips, vo_dir, "en", [])
    assert policy == [None, None] and levels == []


def test_missing_clip_qa_raises(tmp_path):
    clip_dir = tmp_path / "clips" / "s1"
    clip_dir.mkdir(parents=True)
    clips = {"s1": str(clip_dir / "clip.mp4")}
    with pytest.raises(FileNotFoundError):
        b.sfx_policy_for([{"id": "s1"}], clips, tmp_path / "vo", "en", [])
