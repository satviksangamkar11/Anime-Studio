"""Round-2 review fixes (Super VL + Dots, 2026-11-07). One test per fix; no network, no model call."""
import json
import sys
import types
import urllib.request

import pytest

import pack_validator
import retry_policy
import run_registry as rr
import write_pack

SHOT = {"id": "SHOT-01", "episode": 1, "mode": "fl2va", "seconds": 4, "aspect": "9:16", "start": "keyframes/SHOT-01-FRAME-A.png",
        "end": "keyframes/SHOT-01-FRAME-B.png", "refs": [], "subjects": [], "style": "Flat 2D cel anime.", "world": "River at dawn.",
        "action": "0-2s a bird falls.", "camera": "tilt down", "sound": "boiling water hiss"}
CANNED = {
    "1": "# Gate 1\n\nEpisode 1: the river\n",
    "2": "# Gate 2\n\n```json bible\n" + json.dumps({"palette": {"sky": "#aabbcc"}}) + "\n```",
    "3e1": "# Episode 1 shots\n\n```json shots\n" + json.dumps([SHOT]) + "\n```\n",
    "5": "# Gate 5\n",
}


def stage_of(prompt):
    import re
    return re.search(r"Stage (\S+) only", prompt.rsplit("## THIS STAGE", 1)[1]).group(1)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("network call in a test")
    monkeypatch.setattr(write_pack, "call_nvidia", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)


@pytest.fixture
def story(tmp_path):
    path = tmp_path / "story.md"
    path.write_text("Kaliya story\n", encoding="utf-8")
    return path


@pytest.fixture
def fake_claude(monkeypatch):
    def fake(prompt, model, effort):
        return write_pack.envelope(CANNED[stage_of(prompt)], "stop", "claude", "opus")
    monkeypatch.setattr(write_pack, "call_claude", fake)


class FakeStream:
    def __init__(self, lines):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self._lines)


# 1. gate: the writer's caption checks run even when the validator exists
def test_caption_checks_still_run_when_the_validator_passes(tmp_path, story, fake_claude, monkeypatch):
    fake = types.ModuleType("pack_validator")
    fake.validate_stage = lambda *a, **k: {"ok": True, "errors": []}
    monkeypatch.setitem(sys.modules, "pack_validator", fake)
    long_card = " ".join(["word"] * 30)
    CANNED["5"] = "```json captions\n" + json.dumps([{"shot_id": "SHOT-01", "cards": [long_card]}]) + "\n```"
    try:
        with pytest.raises(write_pack.StageFailed, match="CAP-01"):
            write_pack.main([str(story), str(tmp_path / "pack"), "--staged", "--writer", "opus", "--out-lang", "en"])
    finally:
        CANNED["5"] = "# Gate 5\n"


# 2. apply_captions: captions keyed by the original per-episode id reach the merged shot
def test_captions_find_their_shot_by_source_id_after_the_episode_merge():
    shots = [{"id": "SHOT-004", "source_id": "SHOT-01"}, {"id": "SHOT-002", "source_id": "SHOT-02"}]
    items = [{"shot_id": "SHOT-004", "cards": ["X"]}, {"shot_id": "SHOT-01", "cards": ["Y"]}, {"shot_id": "SHOT-02", "cards": ["Z"]}]
    out = write_pack.apply_captions(shots, items, "en")
    assert out[0]["captions"] == ["Y"]          # the original id wins: SHOT-004 is only the merged number
    assert out[1]["captions"] == ["Z"]


# 3. parse: a legacy row that settings_for cannot read is a parse error (ValueError), not a KeyError traceback
def test_a_legacy_row_settings_for_cannot_read_is_a_parse_error():
    raw = write_pack.envelope('```json shots\n[{"id": "SHOT-01", "seconds": 4}]\n```', "stop", "claude", "opus")
    with pytest.raises(ValueError):
        write_pack.parse(raw)


# 4a. stream_chat: a malformed SSE data line is a classified, retryable model error
def test_a_malformed_stream_line_is_a_classified_network_error(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeStream(
        [b'data: {"choices":[{"delta":{"content":"a"}}]}\n', b"data: {broken\n"]))
    with pytest.raises(retry_policy.ModelError) as err:
        write_pack.stream_chat("http://x", "k", {})
    assert err.value.kind == retry_policy.NETWORK


# 4b. episodes_from: invalid JSON in the ```json episodes block names the block
def test_invalid_json_in_the_episodes_block_is_a_clear_value_error():
    with pytest.raises(ValueError, match="episodes block"):
        write_pack.episodes_from("```json episodes\n{bad\n```")


# 5. run_stage / run_single: a failed model call becomes StageFailed (no traceback)
def test_a_failed_model_call_in_a_staged_run_is_a_stage_failure(tmp_path, story, monkeypatch):
    def no_key(prompt, model, effort):
        raise RuntimeError("no NVIDIA key files")
    monkeypatch.setattr(write_pack, "call_claude", no_key)
    with pytest.raises(write_pack.StageFailed, match="model call failed"):
        write_pack.main([str(story), str(tmp_path / "pack"), "--staged", "--writer", "opus"])


def test_a_failed_model_call_in_a_single_run_is_a_stage_failure(tmp_path, story, monkeypatch):
    def no_key(prompt, model, effort):
        raise RuntimeError("no NVIDIA key files")
    monkeypatch.setattr(write_pack, "call_claude", no_key)
    with pytest.raises(write_pack.StageFailed, match="model call failed"):
        write_pack.main([str(story), str(tmp_path / "pack"), "--writer", "opus"])


# 6. _s55_4: a bool is not an off-stage shot count
def test_a_boolean_off_stage_count_is_refused(monkeypatch):
    monkeypatch.setattr(pack_validator, "EXIT_RELEASE_SHOTS", 1)     # with 1, True >= 1 would pass as a count
    shot = {"reference_anchors": {"exited_character_status": [{"id": "K", "released": True, "off_stage_shots": True}]}}
    errs = []
    pack_validator._s55_4([shot], None, errs)
    assert any("released after True" in str(e) for e in errs)


# 7. record_gate_decision: a lowercase gate is stored as its upper-case gate
def test_a_lowercase_gate_decision_is_recorded(tmp_path):
    rr.record_gate_decision(tmp_path, "a", "approve", note="ok")
    gates = [e for e in rr.read_events(tmp_path) if e.get("kind") == "gate_decision"]
    assert gates and gates[-1]["gate"] == "A"


# 8. is_free_model: a None or non-numeric price field is not free (also in the writer's own check)
def test_a_null_price_field_is_not_free():
    catalog = [{"id": "a/half-null:free", "pricing": {"prompt": 0, "completion": None}},
               {"id": "a/word:free", "pricing": {"prompt": "free", "completion": "0"}}]
    assert retry_policy.is_free_model("a/half-null:free", catalog) is False
    assert retry_policy.is_free_model("a/word:free", catalog) is False
    assert write_pack.openrouter_is_free("a/half-null:free", catalog) is False
