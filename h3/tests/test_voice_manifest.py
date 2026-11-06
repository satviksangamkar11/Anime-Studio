"""h3/voice_manifest.py: wav manifest per language. Offline; writes tiny wav files with the stdlib."""
import json
import wave

from h3 import voice_manifest as vm


def _wav(path, seconds, rate=8000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def _shot(sid, text, ed=4.0, lang="en"):
    return {"id": sid, "editorial_duration_sec": ed,
            "audio_and_dialogue_track": {"narration": {"text": text, "language": lang, "time_range": [0, 2]},
                                         "dialogue": [{"speaker": "CHAR-1", "text": "hi", "time_range": [1, 2]}]}}


VMAP = {"NARRATOR": {"en": "narr_en", "hi": "narr_hi"}, "CHAR-1": {"en": "char1_en"}}


def test_entry_has_hash_duration_and_voice_ids(tmp_path):
    _wav(tmp_path / "audio/vo/en/S1.wav", 1.5)
    man = vm.build_manifest(str(tmp_path), [_shot("S1", "Hello there.")], ["en"], VMAP)
    e = man["entries"][0]
    assert e["path"] == "audio/vo/en/S1.wav" and e["exists"] is True
    assert e["duration_sec"] == 1.5 and len(e["sha256"]) == 64
    assert e["voice_ids"] == {"narrator": "narr_en", "speakers": {"CHAR-1": "char1_en"}}
    assert man["fit"]["ok"] is True


def test_missing_wav_is_an_error(tmp_path):
    man = vm.build_manifest(str(tmp_path), [_shot("S1", "Hello there.")], ["en"], VMAP)
    assert man["fit"]["ok"] is False
    assert man["fit"]["errors"][0]["code"] == "VO_MISSING"


def test_vo_longer_than_editorial_minus_margin_overflows(tmp_path):
    _wav(tmp_path / "audio/vo/en/S1.wav", 3.95)  # editorial 4.0 minus 0.10 margin = 3.90
    man = vm.build_manifest(str(tmp_path), [_shot("S1", "Hello there.")], ["en"], VMAP)
    assert man["fit"]["ok"] is False
    assert any(e["code"] == "VO_OVERFLOW_ERROR" for e in man["fit"]["errors"])


def test_text_change_marks_entry_stale(tmp_path):
    _wav(tmp_path / "audio/vo/en/S1.wav", 1.0)
    shots = [_shot("S1", "Hello there.")]
    man = vm.build_manifest(str(tmp_path), shots, ["en"], VMAP)
    assert vm.stale_entries(man, shots) == []
    edited = [_shot("S1", "Hello there, friend.")]
    assert vm.stale_entries(man, edited) == [("en", "S1")]


def test_language_without_narration_needs_no_wav(tmp_path):
    man = vm.build_manifest(str(tmp_path), [_shot("S1", "Hello there.")], ["hi"], VMAP)
    assert man["entries"] == [] and man["fit"]["ok"] is True


def test_cli_exit_codes(tmp_path, capsys):
    _wav(tmp_path / "audio/vo/en/S1.wav", 1.0)
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps({"shots": [_shot("S1", "Hello there.")]}), encoding="utf-8")
    assert vm._cli(["--vo-root", str(tmp_path), "--shots", str(shots), "--lang", "en"]) == 0
    assert vm._cli(["--vo-root", str(tmp_path), "--shots", str(shots), "--lang", "fr"]) == 2
    assert "entries=1 fit_ok=True" in capsys.readouterr().out
