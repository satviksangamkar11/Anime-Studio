"""M-14 / A-02 (test side): voice_cast.export_wavs with a FAKE TTS -> voice_manifest.<lang>.json -> build_final_reel
load_manifest_rows + spoken_cues_real. No ElevenLabs, no network, no model call. tmp_path only."""
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_final_reel as bfr  # noqa: E402
import voice_cast as vc  # noqa: E402
import voice_manifest as vm  # noqa: E402

ROW_ID = re.compile(r"^SHOT-\d{3}-(N|D\d+)\.(en|hi|mr)$")
DECOMPOSED = "café nè"  # NFD on purpose; NFC is "café nè"


def fake_tts(path: Path, seconds: float) -> Path:
    """The fake TTS: writes a real audio file (a sine tone) where the model would have written the mp3."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    "-ac", "1", "-ar", "24000", str(path)], check=True)
    return path


def build_fixture(tmp_path: Path):
    """Two shots, hi and en lines. Returns (out_dir, wav_dir, voices_dir, man, shots, report)."""
    out = tmp_path / "clips"
    voices = tmp_path / "voices"
    voices.mkdir(parents=True)  # write_manifest does not create its folder
    specs = [
        ("SHOT-001-N", "hi", "NARRATOR", "नमस्ते दुनिया।", 1.2),
        ("SHOT-002-D1", "hi", "BRAHMA", "दूसरी पंक्ति।", 1.6),
        ("SHOT-001-N", "en", "NARRATOR", DECOMPOSED, 1.4),
    ]
    lines = []
    for line, lang, voice, text, secs in specs:
        fname = f"{line}.{lang}.mp3.wav"
        fake_tts(out / fname, secs)
        lines.append({"id": f"{line}.{lang}", "line": line, "lang": lang, "voice": voice, "text": text,
                      "file": fname, "ok": True})
    man = {"lines": lines}
    shots = [
        {"id": "SHOT-001", "editorial_duration_sec": 2.0, "audio_and_dialogue_track": {
            "narration_by_lang": {"hi": {"text": "नमस्ते दुनिया।", "time_range": [0.0, 1.2]},
                                  "en": {"text": DECOMPOSED, "time_range": [0.0, 1.4]}},
            "dialogue_by_lang": {"hi": []}}},
        {"id": "SHOT-002", "editorial_duration_sec": 2.0, "audio_and_dialogue_track": {
            "narration_by_lang": {}, "dialogue_by_lang": {"hi": [
                {"speaker": "BRAHMA", "text": "दूसरी पंक्ति।", "time_range": [0.0, 1.6]}]}}},
    ]
    report = [{"lang": "hi", "shot": "SHOT-001", "lines": [{"id": "SHOT-001-N", "start": 0.0, "end": 1.2}]},
              {"lang": "hi", "shot": "SHOT-002", "lines": [{"id": "SHOT-002-D1", "start": 0.0, "end": 1.6}]}]
    return out, tmp_path / "wav_export", voices, man, shots, report


def export(tmp_path: Path):
    out, wav_dir, voices, man, shots, report = build_fixture(tmp_path)
    n = vc.export_wavs(man, out, wav_dir, model="fake-tts", manifest_dir=voices)
    assert n == 3
    return voices, shots, report


def template(voices: Path) -> str:
    return str(voices / "voice_manifest.{lang}.json")


def read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_export_writes_one_manifest_per_language_with_schema(tmp_path):
    voices, _, _ = export(tmp_path)
    hi, en = read(voices / "voice_manifest.hi.json"), read(voices / "voice_manifest.en.json")
    assert hi["schema"] == "voice_manifest/1" and hi["lang"] == "hi"
    assert en["schema"] == "voice_manifest/1" and en["lang"] == "en"
    assert {r["id"] for r in hi["rows"]} == {"SHOT-001-N.hi", "SHOT-002-D1.hi"}
    assert all(ROW_ID.match(r["id"]) for r in hi["rows"] + en["rows"])


def test_manifest_rows_are_nfc_and_hash_their_nfc_text(tmp_path):
    voices, _, _ = export(tmp_path)
    row = next(r for r in read(voices / "voice_manifest.en.json")["rows"] if r["id"] == "SHOT-001-N.en")
    nfc = unicodedata.normalize("NFC", DECOMPOSED)
    assert row["text"] == nfc
    assert row["text_sha256"] == hashlib.sha256(nfc.encode("utf-8")).hexdigest()


def test_manifest_loads_and_spoken_cues_read_its_text(tmp_path):
    voices, shots, report = export(tmp_path)
    rows = bfr.load_manifest_rows(template(voices), "hi")
    assert [r["id"] for r in rows] == ["SHOT-001-N.hi", "SHOT-002-D1.hi"]
    cues = bfr.spoken_cues_real(shots, report, "hi", rows)
    assert cues, "no caption cues built"
    assert cues == sorted(cues, key=lambda c: c["t0"])
    joined = " ".join(c["text"] for c in cues)
    assert "नमस्ते" in joined and "दूसरी" in joined
    # the second line starts at shot 2's offset (2.0 s) plus its own start (0.0 s)
    assert min(c["t0"] for c in cues if "दूसरी" in c["text"]) == pytest.approx(2.0, abs=0.01)


def test_mutated_wav_raises_system_exit(tmp_path):
    voices, _, _ = export(tmp_path)
    wav = voices / read(voices / "voice_manifest.hi.json")["rows"][0]["wav"]
    with open(wav, "ab") as f:
        f.write(b"\x00\x01")  # the audio changed after it was voiced
    with pytest.raises(SystemExit, match="wav_sha256"):
        bfr.load_manifest_rows(template(voices), "hi")


def test_mutated_text_raises_system_exit(tmp_path):
    voices, shots, report = export(tmp_path)
    path = voices / "voice_manifest.hi.json"
    man = read(path)
    man["rows"][0]["text"] = "कुछ और बोला गया।"  # text changed, hashes left as they were
    path.write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="text_sha256"):
        bfr.load_manifest_rows(template(voices), "hi")


def test_mutated_text_is_caught_by_spoken_cues_when_loaded_without_file_check(tmp_path):
    voices, shots, report = export(tmp_path)
    path = voices / "voice_manifest.hi.json"
    rows = vm.load_voice_manifest(path, lang="hi")
    rows[0]["text"] = "बदला हुआ पाठ।"  # the row in memory no longer matches its hash
    with pytest.raises(SystemExit, match="text_sha256"):
        bfr.spoken_cues_real(shots, report, "hi", rows)
