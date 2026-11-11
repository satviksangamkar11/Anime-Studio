import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import h3.prompt_hygiene as prompt_hygiene


def test_old_keep_lips_closed_sentence_removed(tmp_path, monkeypatch):
    text = "detailed_description: A walks. While A and B keep their lips completely closed."
    result = prompt_hygiene.clean_prompt(text, ["A", "B"], ["A", "B"], [])
    lip_sentences = [s for s in prompt_hygiene.split_sentences(result) if "lips" in s]
    assert len(lip_sentences) == 1


def test_old_keeps_their_lips_closed_removed_when_speaker_added(tmp_path, monkeypatch):
    text = "detailed_description: A talks. A keeps their lips closed."
    result = prompt_hygiene.clean_prompt(text, ["A"], ["A"], ["A"])
    lip_sentences = [s for s in prompt_hygiene.split_sentences(result) if "lips" in s]
    assert len(lip_sentences) == 1
    assert "speaks with moving lips" in lip_sentences[0]


def test_new_sentence_not_removed(tmp_path, monkeypatch):
    text = "detailed_description: A talks. A speaks with moving lips."
    result = prompt_hygiene.clean_prompt(text, ["A"], ["A"], ["A"])
    lip_sentences = [s for s in prompt_hygiene.split_sentences(result) if "lips" in s]
    assert len(lip_sentences) == 1
