"""Tests for director/write_pack_glue.py (card X-07). Written BEFORE the module (rule 54(3)): hand-checked values.

ASSUMED SHAPES (module not written yet):
  error_shot_ids(errors) -> list[str] of unique SHOT-\\d{3} ids in first-appearance order, None when any error
      line has no id, [] for no errors
  repair_prompt(base_prompt, rows, ids, errors) -> str; holds base_prompt, the line
      "Return ONLY a JSON list with the corrected objects for shots: SHOT-002, ...", the JSON of ONLY the
      rows whose id is in ids, and every error line
  merge_repair(rows, repaired) -> new list; repaired objects replace rows by id, other rows are the same
      objects; ValueError for an unknown id or a non-dict item; inputs are not mutated
  repair_file(out, name, k) -> Path out/'stage_<name>_repair<k>.json'
  parse_repair(text) -> list[dict]; a ```json fenced block or bare JSON list; ValueError otherwise
  claude_budget_args(max_budget_usd) -> [] for None, ['--max-budget-usd', '0.50'] for 0.5; ValueError for <= 0,
      NaN or bool
  write_blocking_files(out, rows) -> sorted list of Paths out/'blocking'/<id>.json, written from each row's
      'blocking' dict; ValueError naming the id when a row has no dict 'blocking'
  writer_gate(out, rows, source_text, lang='en', lock=None, est_note='') -> {"shots_sha256", "ok", "problems"},
      also written to out/'writer_gate.json'
"""
import copy
import hashlib
import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import write_pack_glue  # noqa: E402
import writer_guard  # noqa: E402,F401
import blocking  # noqa: E402,F401
import blocking_lint  # noqa: E402,F401
import script_inspect  # noqa: E402,F401
import source_check  # noqa: E402,F401

SOURCE = "first line\nsecond line\nthird line\n"


def _pose(x, y, scale, facing="right", pose="standing", mouth=False):
    return {"x": x, "y": y, "scale": scale, "facing": facing, "pose": pose, "mouth_moves": mouth}


def _good_row(i):
    """A V4-style row that passes validate_pack, lint, script_inspect and citations on its own."""
    rid = "SHOT-%03d" % i
    refs = ["L1"]
    member = {
        "id": "SHIVA",
        "name": "SHIVA",
        "speaks": False,
        "arms": 2,
        "source_refs": refs,
        "start": _pose(0.5, 0.8, 0.5, pose="standing"),
        "end": _pose(0.5, 0.8, 0.5, pose="standing"),
    }
    sheet = {
        "schema": "blocking/1",
        "shot_id": rid,
        "plate_id": "PLATE-throne",
        "location_id": "LOC-palace-hall",
        "kind": "acting",
        "camera": {"mode": "fixed", "framing": "medium", "move": None},
        "light": {"key_dir": "left", "palette_id": "PAL-warm"},
        "props": [],
        "entries": [],
        "exits": [],
        "sound_cues": [],
        "arc_sec": 2.0,
        "writer_seconds": 4.0,
        "cut_to_next": "cut",
        "source_refs": refs,
        "cast": [member],
    }
    return {
        "id": rid,
        "editorial_duration_sec": 4.0,
        "audio_and_dialogue_track": {
            "narration_by_lang": {"en": {"text": "The king sits.", "time_range": [0.0, 3.5]}},
            "dialogue_by_lang": {"en": []},
        },
        "per_second_directives": [
            {"t0": 0.0, "t1": 2.0, "text": "a man sits", "source_refs": refs, "action_pose_expression": "sits"},
            {"t0": 2.0, "t1": 4.0, "text": "he holds still", "source_refs": refs,
             "action_pose_expression": "holds"},
        ],
        "blocking": sheet,
    }


# ---- 1 error_shot_ids -------------------------------------------------------

def test_error_shot_ids_unique_in_first_appearance_order():
    errors = ["BLK-L03 at SHOT-002: x", "SHOT-002 again", "SHOT-001: y"]
    assert write_pack_glue.error_shot_ids(errors) == ["SHOT-002", "SHOT-001"]


@pytest.mark.parametrize("errors", [["no id here"], ["SHOT-001: a", "no id"]])
def test_error_shot_ids_none_when_a_line_has_no_id(errors):
    assert write_pack_glue.error_shot_ids(errors) is None


def test_error_shot_ids_empty_list_is_empty():
    assert write_pack_glue.error_shot_ids([]) == []


# ---- 2 repair_prompt --------------------------------------------------------

def test_repair_prompt_names_only_bad_shots(tmp_path):
    rows = [_good_row(1), _good_row(2), _good_row(3)]
    for row, marker in zip(rows, ("MARKER-ROW-ONE", "MARKER-ROW-TWO", "MARKER-ROW-THREE")):
        row["audio_and_dialogue_track"]["narration_by_lang"]["en"]["text"] = marker
    prompt = write_pack_glue.repair_prompt("BASE PROMPT", rows, ["SHOT-002"], ["BLK-L03 at SHOT-002: too fast"])
    assert "BASE PROMPT" in prompt
    assert "Return ONLY a JSON list with the corrected objects for shots: SHOT-002" in prompt
    assert "SHOT-002" in prompt
    assert "MARKER-ROW-TWO" in prompt
    assert "MARKER-ROW-ONE" not in prompt
    assert "MARKER-ROW-THREE" not in prompt
    assert "BLK-L03 at SHOT-002: too fast" in prompt


def test_repair_prompt_joins_several_ids_with_comma():
    rows = [_good_row(1), _good_row(2)]
    errors = ["SHOT-001: a", "SHOT-002: b"]
    prompt = write_pack_glue.repair_prompt("B", rows, ["SHOT-001", "SHOT-002"], errors)
    assert "for shots: SHOT-001, SHOT-002" in prompt


# ---- 3 merge_repair ---------------------------------------------------------

def test_merge_repair_replaces_by_id_and_keeps_other_objects():
    rows = [_good_row(1), _good_row(2), _good_row(3)]
    fixed = _good_row(2)
    fixed["editorial_duration_sec"] = 5.0
    out = write_pack_glue.merge_repair(rows, [fixed])
    assert len(out) == 3
    assert out[1] is fixed
    assert out[0] is rows[0]
    assert out[2] is rows[2]


def test_merge_repair_unknown_id_raises():
    rows = [_good_row(1)]
    with pytest.raises(ValueError):
        write_pack_glue.merge_repair(rows, [_good_row(9)])


@pytest.mark.parametrize("bad", [["not a dict"], [None], "text"])
def test_merge_repair_non_dict_items_raise(bad):
    rows = [_good_row(1)]
    with pytest.raises(ValueError):
        write_pack_glue.merge_repair(rows, bad)


def test_merge_repair_does_not_mutate_inputs():
    rows = [_good_row(1), _good_row(2)]
    snapshot = copy.deepcopy(rows)
    repaired = [_good_row(2)]
    repaired_snapshot = copy.deepcopy(repaired)
    write_pack_glue.merge_repair(rows, repaired)
    assert rows == snapshot
    assert repaired == repaired_snapshot


# ---- 4 repair_file ----------------------------------------------------------

def test_repair_file_path(tmp_path):
    assert write_pack_glue.repair_file(tmp_path, "3e1", 2) == tmp_path / "stage_3e1_repair2.json"


# ---- 5 parse_repair ---------------------------------------------------------

def test_parse_repair_fenced_block_and_bare_json():
    fenced = "Here you go:\n```json\n[{\"id\": \"SHOT-002\", \"x\": 1}]\n```\n"
    assert write_pack_glue.parse_repair(fenced) == [{"id": "SHOT-002", "x": 1}]
    bare = "[{\"id\": \"SHOT-003\"}]"
    assert write_pack_glue.parse_repair(bare) == [{"id": "SHOT-003"}]


@pytest.mark.parametrize("text", ["no list at all", "{\"id\": \"SHOT-001\"}", "[\"just strings\"]"])
def test_parse_repair_rejects_no_list_or_non_dict_items(text):
    with pytest.raises(ValueError):
        write_pack_glue.parse_repair(text)


# ---- 6 claude_budget_args ---------------------------------------------------

def test_claude_budget_args_none_and_value():
    assert write_pack_glue.claude_budget_args(None) == []
    assert write_pack_glue.claude_budget_args(0.5) == ["--max-budget-usd", "0.50"]


@pytest.mark.parametrize("bad", [0, 0.0, -1.0, float("nan"), True])
def test_claude_budget_args_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        write_pack_glue.claude_budget_args(bad)


# ---- 7 write_blocking_files -------------------------------------------------

def test_write_blocking_files_sorted_and_content(tmp_path):
    rows = [_good_row(2), _good_row(1)]
    paths = write_pack_glue.write_blocking_files(tmp_path, rows)
    assert paths == [tmp_path / "blocking" / "SHOT-001.json", tmp_path / "blocking" / "SHOT-002.json"]
    for path, row in zip(paths, [_good_row(1), _good_row(2)]):
        assert json.loads(path.read_text(encoding="utf-8")) == row["blocking"]


def test_write_blocking_files_missing_blocking_names_the_id(tmp_path):
    rows = [_good_row(1), _good_row(2)]
    del rows[1]["blocking"]
    with pytest.raises(ValueError) as info:
        write_pack_glue.write_blocking_files(tmp_path, rows)
    assert "SHOT-002" in str(info.value)


# ---- 8 writer_gate ----------------------------------------------------------

def _write_pack(out, rows):
    write_pack_glue.write_blocking_files(out, rows)


def test_writer_gate_written_and_blocks_on_lint(tmp_path):
    rows = [_good_row(1), _good_row(2)]
    bad = rows[1]["blocking"]
    bad["writer_seconds"] = 0.2
    bad["cast"][0]["end"] = _pose(0.9, 0.8, 0.5, pose="standing")
    _write_pack(tmp_path, rows)
    result = write_pack_glue.writer_gate(tmp_path, rows, SOURCE)
    assert result["ok"] is False
    assert any("L03" in line for line in result["problems"])
    saved = json.loads((tmp_path / "writer_gate.json").read_text(encoding="utf-8"))
    assert saved == result


def test_writer_gate_ok_on_clean_pack(tmp_path):
    rows = [_good_row(1), _good_row(2)]
    _write_pack(tmp_path, rows)
    result = write_pack_glue.writer_gate(tmp_path, rows, SOURCE)
    assert result["problems"] == []
    assert result["ok"] is True
    expected = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    assert result["shots_sha256"] == expected
    assert json.loads((tmp_path / "writer_gate.json").read_text(encoding="utf-8")) == result


def test_gate_sha_changes_when_a_row_changes(tmp_path):
    rows = [_good_row(1), _good_row(2)]
    _write_pack(tmp_path, rows)
    first = write_pack_glue.writer_gate(tmp_path, rows, SOURCE)
    changed = copy.deepcopy(rows)
    changed[0]["per_second_directives"][0]["text"] = "a woman stands"
    second = write_pack_glue.writer_gate(tmp_path, changed, SOURCE)
    assert first["shots_sha256"] != second["shots_sha256"]
    assert len(first["shots_sha256"]) == 64
    assert math.isfinite(len(first["shots_sha256"]))
