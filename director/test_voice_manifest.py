"""D-VOICE: the voice manifest binds the spoken text to the exported wav. Offline, stdlib + tmp_path, no network, no model call."""
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import voice_manifest as vm  # noqa: E402


def wav_file(folder: Path, name: str, payload: bytes = b"RIFF0000WAVEfmt fake") -> Path:
    p = folder / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(payload)
    return p


def make(tmp_path: Path, lang: str = "hi", text: str = "नमस्ते दुनिया।") -> Path:
    """A real manifest for one line: writes two wav files and the manifest next to them."""
    voices = tmp_path / "voices"
    rows = [
        {"id": f"SHOT-001-N.{lang}", "text": text, "wav": wav_file(voices / "wav_export" / "wav" / lang, "a.wav"),
         "seconds": 1.2344, "speaker": "NARRATOR"},
        {"id": f"SHOT-002-D1.{lang}", "text": "दूसरी पंक्ति।", "wav": wav_file(voices / "wav_export" / "wav" / lang, "b.wav", b"second"),
         "seconds": 2.0, "speaker": "BRAHMA"},
    ]
    return vm.write_manifest(voices, lang, rows)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, man: dict) -> None:
    path.write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")


def test_round_trip_loads_the_rows_that_were_written(tmp_path):
    path = make(tmp_path)
    assert path.name == "voice_manifest.hi.json"
    rows = vm.load_voice_manifest(path, lang="hi")
    assert [r["id"] for r in rows] == ["SHOT-001-N.hi", "SHOT-002-D1.hi"]
    first = rows[0]
    assert first["text"] == "नमस्ते दुनिया।"
    assert first["text_sha256"] == hashlib.sha256("नमस्ते दुनिया।".encode("utf-8")).hexdigest()
    assert first["wav_sha256"] == hashlib.sha256(
        (tmp_path / "voices" / "wav_export" / "wav" / "hi" / "a.wav").read_bytes()).hexdigest()
    assert first["seconds"] == 1.234 and first["speaker"] == "NARRATOR"
    assert read(path)["schema"] == "voice_manifest/1" and read(path)["lang"] == "hi"


def test_tampered_text_is_refused(tmp_path):
    path = make(tmp_path)
    man = read(path)
    man["rows"][0]["text"] = "कुछ और बोला गया।"                  # text changed, hash left as it was
    write(path, man)
    with pytest.raises(vm.VoiceManifestError, match="text_sha256 does not match"):
        vm.load_voice_manifest(path, lang="hi")


def test_tampered_text_with_rehashed_row_is_still_refused(tmp_path):
    path = make(tmp_path)
    man = read(path)
    man["rows"][0]["text"] = "कुछ और।"
    man["rows"][0]["text_sha256"] = hashlib.sha256("कुछ और।".encode("utf-8")).hexdigest()
    write(path, man)
    with pytest.raises(vm.VoiceManifestError, match="source_text_sha256 does not match"):
        vm.load_voice_manifest(path, lang="hi")


def test_tampered_wav_is_refused(tmp_path):
    path = make(tmp_path)
    (tmp_path / "voices" / "wav_export" / "wav" / "hi" / "a.wav").write_bytes(b"changed after voicing")
    with pytest.raises(vm.VoiceManifestError, match="wav_sha256 does not match"):
        vm.load_voice_manifest(path, lang="hi")


def test_missing_wav_is_refused(tmp_path):
    path = make(tmp_path)
    (tmp_path / "voices" / "wav_export" / "wav" / "hi" / "b.wav").unlink()
    with pytest.raises(vm.VoiceManifestError, match="wav missing"):
        vm.load_voice_manifest(path, lang="hi")


def test_missing_row_is_refused_by_require_row(tmp_path):
    rows = vm.load_voice_manifest(make(tmp_path), lang="hi")
    assert vm.require_row(rows, "SHOT-002-D1.hi")["speaker"] == "BRAHMA"
    with pytest.raises(vm.VoiceManifestError, match="SHOT-009-N.hi: no row in the voice manifest"):
        vm.require_row(rows, "SHOT-009-N.hi")


def test_wrong_lang_is_refused(tmp_path):
    path = make(tmp_path, lang="hi")
    with pytest.raises(vm.VoiceManifestError, match="wrong lang"):
        vm.load_voice_manifest(path, lang="mr")


def test_row_of_another_language_is_refused(tmp_path):
    path = make(tmp_path, lang="hi")
    man = read(path)
    man["rows"][1]["id"] = "SHOT-002-D1.mr"
    write(path, man)
    with pytest.raises(vm.VoiceManifestError, match="wrong lang"):
        vm.load_voice_manifest(path, lang="hi")


def test_unknown_schema_is_refused(tmp_path):
    path = make(tmp_path)
    man = read(path)
    man["schema"] = "voice_manifest/2"
    write(path, man)
    with pytest.raises(vm.VoiceManifestError, match="unknown schema"):
        vm.load_voice_manifest(path, lang="hi")


def test_missing_top_field_is_refused(tmp_path):
    path = make(tmp_path)
    man = read(path)
    del man["source_text_sha256"]
    write(path, man)
    with pytest.raises(vm.VoiceManifestError, match="missing fields"):
        vm.load_voice_manifest(path, lang="hi")


def test_missing_row_field_is_refused(tmp_path):
    path = make(tmp_path)
    man = read(path)
    del man["rows"][0]["wav_sha256"]
    write(path, man)
    with pytest.raises(vm.VoiceManifestError, match="wav_sha256"):
        vm.load_voice_manifest(path, lang="hi")


def test_duplicate_id_is_refused(tmp_path):
    path = make(tmp_path)
    man = read(path)
    man["rows"][1]["id"] = man["rows"][0]["id"]
    write(path, man)
    with pytest.raises(vm.VoiceManifestError, match="duplicate id"):
        vm.load_voice_manifest(path, lang="hi")


def test_hindi_hash_is_over_nfc_utf8(tmp_path):
    decomposed = "é"                                # e + combining acute: NFC composes it to U+00E9 (Devanagari pairs are composition-excluded)
    composed = unicodedata.normalize("NFC", decomposed)
    assert composed != decomposed
    assert vm.text_sha256(decomposed) == hashlib.sha256(composed.encode("utf-8")).hexdigest()
    assert vm.text_sha256(decomposed) != hashlib.sha256(decomposed.encode("utf-8")).hexdigest()
    voices = tmp_path / "voices"
    path = vm.write_manifest(voices, "hi", [{"id": "SHOT-003-N.hi", "text": decomposed,
                                             "wav": wav_file(voices / "w", "c.wav"), "seconds": 1.0, "speaker": "NARRATOR"}])
    row = vm.load_voice_manifest(path, lang="hi")[0]
    assert row["text"] == composed and row["text_sha256"] == vm.text_sha256(composed)


def test_build_final_reel_loads_the_same_rows(tmp_path):
    import build_final_reel as b
    path = make(tmp_path)
    rows = b.load_manifest_rows(str(path), "hi")
    assert [r["id"] for r in rows] == ["SHOT-001-N.hi", "SHOT-002-D1.hi"]
    with pytest.raises(SystemExit, match="voice manifest"):
        b.load_manifest_rows(str(path), "mr")


def test_export_writes_manifest_bound_to_the_wav(tmp_path, monkeypatch):
    """export_wavs with manifest_dir writes voice_manifest.hi.json from the voiced text and the exported wav."""
    import voice_cast as v
    real_write = v.audio_edge.write_wav_mono

    def fake_ffmpeg(args, **kw):
        Path(args[-1]).parent.mkdir(parents=True, exist_ok=True)
        real_write(args[-1], [0.5] * 4410, 44100)
    monkeypatch.setattr(v.subprocess, "run", fake_ffmpeg)
    out = tmp_path / "voices"
    out.mkdir()
    man = {"lines": [{"id": "SHOT-001-N.hi", "line": "SHOT-001-N", "lang": "hi", "voice": "NARRATOR", "text": "नमस्ते।",
                      "file": "mp3/hi/x.mp3", "ok": True}]}
    assert v.export_wavs(man, out, out / "wav_export", "m", manifest_dir=out) == 1
    path = out / "voice_manifest.hi.json"
    rows = vm.load_voice_manifest(path, lang="hi")
    assert rows[0]["id"] == "SHOT-001-N.hi" and rows[0]["text"] == "नमस्ते।" and rows[0]["speaker"] == "NARRATOR"
    assert rows[0]["wav"] == "wav_export/wav/hi/" + v.wav_name("SHOT-001-N", "hi")
    (out / rows[0]["wav"]).write_bytes(b"changed")
    with pytest.raises(vm.VoiceManifestError, match="wav_sha256"):
        vm.load_voice_manifest(path, lang="hi")
