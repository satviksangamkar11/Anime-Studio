"""G24: the v2.4 staged writer emits the story-shape fields (premise, arc_beat, hook_type, voice_rest) and story_shape passes on them.

Row hook_type is the H3 vocabulary (reveal, ...). The shape hook (kinetic | scale_tableau | voice_call) is written as
shape_hook_type on shot 1; story_shape.lint reads it from shape_hook_type (never from hook_type). No network, no model call."""
import json

import pytest

import story_shape
import write_pack
import writer_prompts as wp
import test_writer_v4 as t4
from test_writer_v4 import no_network, simple_language, story  # noqa: F401  (fixtures)

PREMISE = {"character": "Raj", "goal": "open the door", "obstacle": "his fear", "stakes": "the village",
           "payoff": "he steps out"}


def v24_story_answer():
    return dict(t4.STORY_ANSWER, premise=PREMISE, reel_target_s=13)


def v24_rows(langs=("hi",)):
    r1 = wp.example_row(1, 1, list(langs), v24=True)
    r2 = dict(wp.example_row(1, 2, list(langs), v24=True), arc_beat="payoff", editorial_duration_sec=6.0,
              voice_rest=[3.0, 5.5])
    r2.pop("shape_hook_type", None)
    return [r1, r2]


def test_stage1_v24_asks_for_the_premise_and_the_old_text_does_not():
    new, old = wp.stage1_text(v24=True), wp.stage1_text()
    for key in story_shape.PREMISE_KEYS:
        assert f'"{key}"' in new
    assert '"premise"' in new and "premise" not in old


def test_stage3_v24_asks_for_arc_beat_shape_hook_and_voice_rest():
    new, old = wp.stage3_text(1, v24=True), wp.stage3_text(1)
    for word in ("arc_beat", "shape_hook_type", "voice_rest", "kinetic", "shot-relative"):
        assert word in new and word not in old


def test_example_row_v24_carries_the_fields_and_default_row_does_not():
    row, plain = wp.example_row(1, 1, "hi", v24=True), wp.example_row(1, 1, "hi")
    assert row["arc_beat"] == "hook" and row["shape_hook_type"] in story_shape.HOOK_TYPES
    assert row["hook_type"] == "reveal"                      # the H3 value stays
    assert story_shape.REST_RANGE[0] <= row["voice_rest"][1] - row["voice_rest"][0] <= story_shape.REST_RANGE[1]
    assert not {"arc_beat", "shape_hook_type", "voice_rest"} & set(plain)


def test_stage_instruction_passes_v24_through():
    assert "arc_beat" in wp.stage_instruction("3e1", v24=True) and "arc_beat" not in wp.stage_instruction("3e1")
    assert '"premise"' in wp.stage_instruction("1", v24=True) and "premise" not in wp.stage_instruction("1")


def test_shape_rows_keeps_both_hook_fields_and_drops_null_rest_without_touching_the_input():
    rows = [{"id": "SHOT-001", "hook_type": "reveal", "shape_hook_type": "kinetic", "voice_rest": None},
            {"id": "SHOT-002", "hook_type": "callback", "voice_rest": [1.0, 3.0]}]
    out = write_pack.shape_rows(rows)
    assert out[0]["hook_type"] == "reveal" and out[0]["shape_hook_type"] == "kinetic" and "voice_rest" not in out[0]
    assert out[1]["hook_type"] == "callback" and "shape_hook_type" not in out[1] and out[1]["voice_rest"] == [1.0, 3.0]
    assert rows[0]["hook_type"] == "reveal" and rows[0]["voice_rest"] is None


def test_shape_rows_keep_a_bad_shape_hook_so_the_lint_sees_it():
    out = write_pack.shape_rows([{"id": "SHOT-001", "shape_hook_type": "reveal"}])
    errors, _ = story_shape.lint(out, {"premise": PREMISE})
    assert any(e.startswith("SHAPE-09") for e in errors)


def _run_v24(tmp_path, monkeypatch, story, answer, rows):
    t4.fake_validator(monkeypatch, lambda stage, data, bible: [])
    canned = t4.canned(["hi"])
    canned["1"] = "# Gate 1\n\nEpisode 1: the river\n\n```json story\n" + json.dumps(answer) + "\n```\n"
    canned["3e1"] = "# Episode 1\n\n```json shots\n" + json.dumps(rows, ensure_ascii=False) + "\n```\n"
    items = [dict(t4.captions_items(["hi"])[0], shot_id=f"SHOT-00{n}") for n in (1, 2)]
    canned["5"] = "# Gate 5\n\n```json captions\n" + json.dumps(items, ensure_ascii=False) + "\n```\n"
    monkeypatch.setattr(write_pack, "call_claude",
                        lambda prompt, model, effort: write_pack.envelope(
                            canned.get(t4.stage_of(prompt)) or canned["5"], "stop", "claude", "opus"))
    out = tmp_path / "pack"
    t4.run(story, out, "--prompt-version", "v2.4")
    return out


def test_v24_pack_has_story_fields(tmp_path, monkeypatch, story):
    out = _run_v24(tmp_path, monkeypatch, story, v24_story_answer(), v24_rows())
    plan = json.loads((out / "story_plan.json").read_text(encoding="utf-8"))
    shots = json.loads((out / "shots.json").read_text(encoding="utf-8"))
    assert plan["premise"] == PREMISE
    assert [s["arc_beat"] for s in shots] == ["hook", "payoff"]
    assert shots[0]["shape_hook_type"] in story_shape.HOOK_TYPES and shots[1]["voice_rest"] == [3.0, 5.5]
    report = json.loads((out / "story_shape.json").read_text(encoding="utf-8"))
    assert report["errors"] == []                            # story_shape passes on the fixture
    errors, warnings = story_shape.lint(write_pack.shape_rows(shots), plan)
    assert errors == []


def test_v24_run_stops_when_the_premise_is_missing(tmp_path, monkeypatch, story):
    with pytest.raises(write_pack.StageFailed) as exc:
        _run_v24(tmp_path, monkeypatch, story, t4.STORY_ANSWER, v24_rows())
    assert "SHAPE-01" in str(exc.value)


def test_a_v23_run_writes_no_story_shape_report(tmp_path, monkeypatch, story):
    t4.fake_validator(monkeypatch, lambda stage, data, bible: [])
    monkeypatch.setattr(write_pack, "call_claude",
                        lambda prompt, model, effort: write_pack.envelope(
                            t4.canned(["hi"]).get(t4.stage_of(prompt)) or t4.canned(["hi"])["5"], "stop", "claude", "opus"))
    out = tmp_path / "pack"
    t4.run(story, out, "--prompt-version", "v2.3")
    assert not (out / "story_shape.json").exists()
