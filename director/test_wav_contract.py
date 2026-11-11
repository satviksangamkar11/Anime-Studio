"""Tests for director/wav_contract.py."""

from __future__ import annotations

import math
from pathlib import Path

import wav_contract


# --- wav_name ---------------------------------------------------------------

def test_wav_name_each_language(tmp_path):
    assert wav_contract.wav_name("SHOT-001", "en") == "SHOT-001.en.wav"
    assert wav_contract.wav_name("SHOT-001", "hi") == "SHOT-001.hi.wav"
    assert wav_contract.wav_name("SHOT-001", "mr") == "SHOT-001.mr.wav"


def test_wav_name_bad_language(tmp_path):
    try:
        wav_contract.wav_name("SHOT-001", "xx")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unsupported language")


def test_wav_name_empty_shot_id(tmp_path):
    try:
        wav_contract.wav_name("", "en")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty shot_id")


def test_wav_name_path_like_shot_id(tmp_path):
    for bad in ("../a", "a/b", "a\\b", "a..b"):
        try:
            wav_contract.wav_name(bad, "en")
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")


# --- sniff_audio ------------------------------------------------------------

def _write_bytes(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_sniff_riff_wave(tmp_path):
    p = _write_bytes(tmp_path / "a.wav", b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE")
    assert wav_contract.sniff_audio(p) == "wav"


def test_sniff_riff_avi_refused(tmp_path):
    p = _write_bytes(tmp_path / "a.wav", b"RIFF" + b"\x00\x00\x00\x00" + b"AVI ")
    try:
        wav_contract.sniff_audio(p)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for AVI header")


def test_sniff_id3_mp3(tmp_path):
    p = _write_bytes(tmp_path / "a.mp3", b"ID3" + b"\x00" * 9)
    assert wav_contract.sniff_audio(p) == "mp3"


def test_sniff_frame_sync_mp3(tmp_path):
    p = _write_bytes(tmp_path / "a.mp3", bytes([0xFF, 0xE0]) + b"\x00" * 10)
    assert wav_contract.sniff_audio(p) == "mp3"


def test_sniff_text_refused(tmp_path):
    p = _write_bytes(tmp_path / "a.txt", b"hello world this is text")
    try:
        wav_contract.sniff_audio(p)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for text file")


def test_sniff_short_file_refused(tmp_path):
    p = _write_bytes(tmp_path / "a.wav", b"RIFF")
    try:
        wav_contract.sniff_audio(p)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for file shorter than 12 bytes")


def test_sniff_five_byte_file_refused(tmp_path):
    p = _write_bytes(tmp_path / "a.wav", b"RIFFX")
    try:
        wav_contract.sniff_audio(p)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for 5-byte file shorter than 12 bytes")


def test_sniff_missing_file(tmp_path):
    p = tmp_path / "missing.wav"
    try:
        wav_contract.sniff_audio(p)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError for missing file")


# --- require_wav ------------------------------------------------------------

def test_require_wav_valid(tmp_path):
    p = _write_bytes(tmp_path / "x.wav", b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE")
    result = wav_contract.require_wav(p)
    assert result == p


def test_require_wav_mp3_extension_with_wav_content_refused(tmp_path):
    p = _write_bytes(tmp_path / "x.mp3", b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE")
    try:
        wav_contract.require_wav(p)
    except ValueError as exc:
        assert "extension" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for mp3 extension with wav content")


def test_require_wav_wav_extension_with_mp3_content_refused(tmp_path):
    p = _write_bytes(tmp_path / "x.wav", b"ID3" + b"\x00" * 9)
    try:
        wav_contract.require_wav(p)
    except ValueError as exc:
        assert "looks like mp3" in str(exc)
    else:
        raise AssertionError("expected ValueError for wav extension with mp3 content")


# --- slot_seconds -----------------------------------------------------------

def test_slot_seconds_max():
    assert wav_contract.slot_seconds({"en": 2.0, "hi": 3.0, "mr": 2.5}) == 3.0


def test_slot_seconds_empty_refused():
    try:
        wav_contract.slot_seconds({})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty dict")


def test_slot_seconds_negative_refused():
    try:
        wav_contract.slot_seconds({"en": 2.0, "hi": -1.0})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for negative slot length")


def test_slot_seconds_non_finite_refused():
    try:
        wav_contract.slot_seconds({"en": math.inf})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for non-finite slot length")


# --- find_voice -------------------------------------------------------------

def test_find_voice_exists(tmp_path):
    folder = tmp_path / "voices"
    (folder / "hi").mkdir(parents=True)
    target = folder / "hi" / "SHOT-003.hi.wav"
    target.write_bytes(b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE")
    result = wav_contract.find_voice(folder, "SHOT-003", "hi")
    assert result == target


def test_find_voice_missing_names_file(tmp_path):
    folder = tmp_path / "voices"
    try:
        wav_contract.find_voice(folder, "SHOT-003", "hi")
    except FileNotFoundError as exc:
        assert "SHOT-003.hi.wav" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError naming the expected file")


# --- plan_names -------------------------------------------------------------

def test_plan_names_order_and_count():
    triples = wav_contract.plan_names(["A", "B"])
    assert len(triples) == 6
    assert triples[0] == ("A", "en", "A.en.wav")
    assert triples[1] == ("A", "hi", "A.hi.wav")
    assert triples[2] == ("A", "mr", "A.mr.wav")
    assert triples[3] == ("B", "en", "B.en.wav")
    assert triples[4] == ("B", "hi", "B.hi.wav")
    assert triples[5] == ("B", "mr", "B.mr.wav")


def test_plan_names_duplicates_refused():
    try:
        wav_contract.plan_names(["A", "A"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for duplicate shot_ids")


# --- third run (2026-11-10) additions ---------------------------------------

def test_wav_name_colon_refused():
    for bad in ("C:x", "a:b"):
        try:
            wav_contract.wav_name(bad, "en")
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")


def test_find_voice_accepts_str_folder(tmp_path):
    folder = tmp_path / "voices"
    (folder / "hi").mkdir(parents=True)
    target = folder / "hi" / "SHOT-003.hi.wav"
    target.write_bytes(b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE")
    result = wav_contract.find_voice(str(folder), "SHOT-003", "hi")
    assert Path(result) == target


def test_find_voice_directory_at_voice_path_refused(tmp_path):
    folder = tmp_path / "voices"
    (folder / "hi" / "SHOT-003.hi.wav").mkdir(parents=True)
    try:
        wav_contract.find_voice(folder, "SHOT-003", "hi")
    except FileNotFoundError as exc:
        assert "SHOT-003.hi.wav" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError when a directory sits at the voice path")


def test_plan_names_case_insensitive_duplicate_refused():
    try:
        wav_contract.plan_names(["A", "a"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for case-only duplicate shot_ids")


def test_require_wav_uppercase_extension_passes(tmp_path):
    p = _write_bytes(tmp_path / "X.WAV", b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE")
    assert wav_contract.require_wav(p) == p


def test_slot_seconds_nan_refused():
    try:
        wav_contract.slot_seconds({"en": float("nan")})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for NaN slot length")


# --- S-03 (2026-11-11): Windows reserved names, trailing dot/space, control chars

def test_reserved_names_refused():
    for bad in ("CON", "nul", "Com1", "lpt9.x"):
        try:
            wav_contract.wav_name(bad, "en")
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for reserved name {bad!r}")


def test_line_id_ok():
    assert wav_contract.wav_name("SHOT-001-N", "hi") == "SHOT-001-N.hi.wav"


def test_trailing_dot_space_refused():
    for bad in ("SHOT-001.", "SHOT-001 "):
        try:
            wav_contract.wav_name(bad, "en")
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")


def test_control_char_refused():
    try:
        wav_contract.wav_name("a\x01", "en")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for control character")
