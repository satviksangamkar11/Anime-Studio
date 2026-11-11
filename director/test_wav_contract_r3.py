import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wav_contract


def test_reserved_name_with_trailing_space_refused():
    with pytest.raises(ValueError):
        wav_contract.wav_name("con .x", "hi")
    with pytest.raises(ValueError):
        wav_contract.wav_name("NUL ", "hi")


def test_illegal_chars_refused():
    for ch in ["<", ">", "|", "?", "*", chr(34)]:
        with pytest.raises(ValueError):
            wav_contract.wav_name("SHOT-001" + ch, "hi")


def test_normal_ids_still_ok():
    assert wav_contract.wav_name("SHOT-001-N", "hi") == "SHOT-001-N.hi.wav"
