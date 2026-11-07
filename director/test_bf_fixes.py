"""Backlog-fix regression (research/TRIAGE_R4_BF_2026-11-07.md item 9): a non-empty answer cut at the token limit is usable."""
import write_pack


def test_envelope_check_accepts_non_empty_answer_cut_at_length():
    assert write_pack.envelope_check(write_pack.envelope("some answer", "length", "nvidia", "m")) is None
