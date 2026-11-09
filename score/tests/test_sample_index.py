"""Tests for score/sample_index.py on a tiny temp library (no real library is touched)."""
import json

import numpy as np
import soundfile as sf

from score import sample_index as si


def _wav(path, seconds=0.5, sr=48000):
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.zeros(int(seconds * sr), dtype="float32"), sr)


def test_parse_bpm_and_key():
    assert si.parse_bpm("Tech Loop 128bpm.wav") == 128.0
    assert si.parse_bpm("Drum_Loop_124_Dm.wav") == 124.0
    assert si.parse_bpm("Kick 808.wav") is None  # 808 is out of range
    assert si.parse_key("Bass Loop Dm 128.wav") == "D min"
    assert si.parse_key("Pad F# maj.wav") == "F# maj"
    assert si.parse_key("Lead Bb minor.wav") == "Bb min"
    assert si.parse_key("Kick A Hit.wav") is None  # bare letter is never a key


def test_categorize_and_exclusions():
    assert "kick" in si.categorize(["Drums", "Kick", "k1.wav"])
    assert "drum_loop" in si.categorize(["Drum Loops", "Techno", "loop.wav"])
    assert "impact" in si.categorize(["FX", "Impacts", "x.wav"])
    assert si._excluded(["Hooks With Lyrics", "a.wav"])


def test_index_roots_scans_and_skips(tmp_path):
    lib = tmp_path / "PackA"
    _wav(lib / "Drum Loops" / "Techno_128bpm_loop.wav", seconds=2.0)
    _wav(lib / "Synths" / "BASS" / "Reese_Dm_140.wav", seconds=1.0)
    _wav(lib / "Hooks With Lyrics" / "chant_120.wav")
    (lib / "notes.txt").write_text("not audio", encoding="utf-8")
    entries = si.index_roots([str(lib)])
    names = {e["name"]: e for e in entries}
    assert set(names) == {"Techno_128bpm_loop.wav", "Reese_Dm_140.wav"}
    loop = names["Techno_128bpm_loop.wav"]
    assert loop["bpm"] == 128.0 and loop["seconds"] == 2.0 and loop["pack"] == "PackA"
    assert "drum_loop" in loop["categories"]
    assert names["Reese_Dm_140.wav"]["key"] == "D min"


def test_write_index_cli(tmp_path):
    lib = tmp_path / "Lib"
    _wav(lib / "Kick_01.wav")
    out = tmp_path / "idx.json"
    assert si.main(["--root", str(lib), "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["count"] == 1 and data["entries"][0]["categories"] == ["kick"]


def test_parse_bpm_in_parentheses():
    assert si.parse_bpm("KSHMR Vocal Hum - Dot Dot (125, Gm).wav") == 125.0
    assert si.parse_key("KSHMR Vocal Hum - Dot Dot (125, Gm).wav") == "G min"
    assert si.parse_bpm("PML_MH4_Bass_Loop_007_114BPM_G#min_Time.wav") == 114.0


def test_parse_root_only_key():
    assert si.parse_key("KSHMR Sub Drop 05 (C#).wav") == "C# root"
    assert si.parse_key("KSHMR War Horn - Alarm (D).wav") == "D root"


def test_measure_tonal_adds_detected_key(tmp_path):
    lib = tmp_path / "Lib"
    t = np.arange(48000 * 2) / 48000.0
    x = sum(np.sin(2 * np.pi * f * t) for f in (146.83, 174.61, 220.0, 73.42))
    lib.mkdir()
    sf.write(str(lib / "Bass Dm 120bpm.wav"), (x / np.max(np.abs(x))).astype("float32"), 48000)
    entries = si.index_roots([str(lib)])
    si.measure_tonal(entries)
    assert entries[0]["detected_key"] == "D min"
    assert "detected_confidence" in entries[0]
