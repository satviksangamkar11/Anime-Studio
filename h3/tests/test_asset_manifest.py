import hashlib
import json
import os

import pytest

from h3 import asset_manifest as am
from h3.asset_manifest import (H3_MODEL_ID, PLACEHOLDER_STATUS, SEEDANCE_MODEL_ID, blocking_problems, clip_key,
                               hash_bible, hash_frame_file, hash_shot_row, is_stale, load_manifest, make_clip_entry,
                               make_placeholder_entry, record_model_switch, render_plan, save_manifest, empty_manifest)

B = "1" * 64
R = "2" * 64
S = "3" * 64
E = "4" * 64


def _current(**over):
    cur = {"bible_sha256": B, "shot_row_sha256": R, "start_frame_sha256": S, "end_frame_sha256": E,
           "model_id": H3_MODEL_ID}
    cur.update(over)
    return cur


def _entry(shot_id="A1", **over):
    cur = _current(**over)
    return make_clip_entry(shot_id, **cur, path=f"clips/{shot_id}.mp4")


def _manifest(*entries):
    m = empty_manifest()
    for e in entries:
        m["clips"][e["shot_id"]] = e
    return m


# ---- clip key and hashes ----

def test_clip_key_is_stable_and_binds_every_component():
    base = clip_key(B, R, S, E, H3_MODEL_ID)
    assert base == clip_key(B, R, S, E, H3_MODEL_ID)
    changed = {"bible_sha256": "5" * 64, "shot_row_sha256": "6" * 64, "start_frame_sha256": "7" * 64,
               "end_frame_sha256": "8" * 64, "model_id": SEEDANCE_MODEL_ID}
    for name, value in changed.items():
        args = dict(bible_sha256=B, shot_row_sha256=R, start_frame_sha256=S, end_frame_sha256=E, model_id=H3_MODEL_ID)
        args[name] = value
        assert clip_key(**args) != base, name


def test_clip_key_allows_missing_frames_for_t2va_and_rejects_bad_input():
    assert clip_key(B, R, None, None, H3_MODEL_ID) != clip_key(B, R, S, E, H3_MODEL_ID)
    with pytest.raises(ValueError):
        clip_key("abc", R, S, E, H3_MODEL_ID)
    with pytest.raises(ValueError):
        clip_key(B, R, "A" * 64, E, H3_MODEL_ID)     # uppercase hex is rejected
    with pytest.raises(ValueError):
        clip_key(None, R, S, E, H3_MODEL_ID)
    with pytest.raises(ValueError):
        clip_key(B, R, S, E, "  ")


def test_hash_bible_and_row_use_canonical_json():
    row = {"id": "A1", "x": [1, 2], "y": {"b": 1, "a": 2}}
    same_other_order = {"y": {"a": 2, "b": 1}, "x": [1, 2], "id": "A1"}
    assert hash_shot_row(row) == hash_shot_row(same_other_order)
    assert hash_shot_row(row) != hash_shot_row({**row, "x": [2, 1]})
    assert hash_bible({"characters": {}}) != hash_bible({"characters": {"CHAR-1": {}}})
    with pytest.raises(ValueError):
        hash_bible([])
    with pytest.raises(ValueError):
        hash_shot_row({"x": float("nan")})


def test_hash_frame_file_matches_sha256(tmp_path):
    p = tmp_path / "frame.png"
    p.write_bytes(b"frame-bytes" * 1000)
    assert hash_frame_file(str(p), chunk=7) == hashlib.sha256(b"frame-bytes" * 1000).hexdigest()
    p.write_bytes(b"other")
    assert hash_frame_file(str(p)) != hashlib.sha256(b"frame-bytes" * 1000).hexdigest()


# ---- staleness: hash changes invalidate clips ----

def test_is_stale_false_for_matching_hashes():
    assert is_stale(_entry(), _current()) is False


@pytest.mark.parametrize("field,new", [("bible_sha256", "5" * 64), ("shot_row_sha256", "5" * 64),
                                       ("start_frame_sha256", "5" * 64), ("end_frame_sha256", "5" * 64),
                                       ("model_id", SEEDANCE_MODEL_ID)])
def test_is_stale_true_when_any_upstream_hash_changes(field, new):
    assert is_stale(_entry(), _current(**{field: new})) is True


def test_is_stale_true_for_tampered_clip_key_or_missing_fields():
    e = _entry()
    e["clip_key"] = "0" * 64
    assert is_stale(e, _current()) is True
    e2 = _entry()
    del e2["end_frame_sha256"]
    assert is_stale(e2, _current()) is True


def test_upstream_edit_makes_clip_stale_and_blocks_assembly():
    row = {"id": "A1", "x": 1}
    row2 = {"id": "A1", "x": 2}
    clip_row_hash = hash_shot_row(row)
    entry = make_clip_entry("A1", bible_sha256=B, shot_row_sha256=clip_row_hash, start_frame_sha256=S,
                            end_frame_sha256=E, model_id=H3_MODEL_ID)
    m = _manifest(entry)
    assert blocking_problems(m, {"A1": _current(shot_row_sha256=clip_row_hash)}) == []
    problems = blocking_problems(m, {"A1": _current(shot_row_sha256=hash_shot_row(row2))})
    assert len(problems) == 1 and "stale" in problems[0]


def test_bible_edit_invalidates_every_shot():
    e1, e2 = _entry("A1"), _entry("A2")
    m = _manifest(e1, e2)
    problems = blocking_problems(m, {"A1": _current(bible_sha256="9" * 64), "A2": _current(bible_sha256="9" * 64)})
    assert len(problems) == 2 and all("stale" in p for p in problems)


# ---- blocking ----

def test_clean_manifest_has_no_blocking_problems():
    assert blocking_problems(_manifest(_entry("A1")), {"A1": _current()}) == []


def test_missing_clip_blocks():
    problems = blocking_problems(_manifest(_entry("A1")), {"A1": _current(), "A2": _current()})
    assert problems == ["A2: missing clip (no manifest entry)"]


def test_orphan_clip_blocks():
    problems = blocking_problems(_manifest(_entry("A1"), _entry("GONE")), {"A1": _current()})
    assert any("GONE" in p and "orphan" in p for p in problems)


def test_unresolved_placeholder_blocks_and_resolved_one_does_not_block_itself():
    m = _manifest(make_placeholder_entry("A1"))
    problems = blocking_problems(m, {"A1": _current()})
    assert problems == [f"A1: {PLACEHOLDER_STATUS} unresolved"]
    m["clips"]["A1"]["resolved"] = True
    assert blocking_problems(m, {"A1": _current()}) == []


def test_human_gate_blocks():
    e = _entry("A1")
    e["status"] = "human_gate"
    problems = blocking_problems(_manifest(e), {"A1": _current()})
    assert len(problems) == 1 and "human choice" in problems[0]


def test_seedance_clip_without_logged_switch_is_silent_mix_and_blocks():
    e = _entry("A1", model_id=SEEDANCE_MODEL_ID)
    m = _manifest(e)
    problems = blocking_problems(m, {"A1": _current(model_id=SEEDANCE_MODEL_ID)})
    assert len(problems) == 1 and "silent mix" in problems[0]


def test_logged_seedance_switch_passes_and_is_recorded():
    e = _entry("A1", model_id=SEEDANCE_MODEL_ID)
    m = _manifest(e)
    record_model_switch(m, "A1", H3_MODEL_ID, SEEDANCE_MODEL_ID, rung=3, reason="drift after 2 failures")
    assert blocking_problems(m, {"A1": _current(model_id=SEEDANCE_MODEL_ID)}) == []
    assert m["model_switches"][0]["rung"] == 3


def test_model_switch_needs_two_different_models():
    with pytest.raises(ValueError):
        record_model_switch(empty_manifest(), "A1", H3_MODEL_ID, H3_MODEL_ID, rung=3, reason="x")


# ---- atomic persistence ----

def test_save_and_load_roundtrip_and_no_temp_left(tmp_path):
    path = str(tmp_path / "sub" / "manifest.json")
    m = _manifest(_entry("A1"))
    save_manifest(path, m)
    assert load_manifest(path)["clips"]["A1"]["clip_key"] == m["clips"]["A1"]["clip_key"]
    assert [f for f in os.listdir(os.path.dirname(path))] == ["manifest.json"]


def test_load_missing_file_gives_empty_manifest(tmp_path):
    assert load_manifest(str(tmp_path / "none.json")) == empty_manifest()


def test_failed_save_keeps_previous_file_intact(tmp_path):
    path = str(tmp_path / "manifest.json")
    save_manifest(path, _manifest(_entry("A1")))
    before = open(path, encoding="utf-8").read()
    bad = _manifest(_entry("A1"))
    bad["clips"]["A1"]["path"] = object()   # not JSON serialisable
    with pytest.raises(TypeError):
        save_manifest(path, bad)
    assert open(path, encoding="utf-8").read() == before
    assert sorted(os.listdir(tmp_path)) == ["manifest.json"]


def test_load_rejects_wrong_schema(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema": 99, "clips": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(str(path))


# ---- resolution ladder ----

def test_render_plan_pass1_base_and_pass2_only_for_approved():
    clips = [{"shot_id": "A1", "model_id": H3_MODEL_ID}, {"shot_id": "A2", "model_id": H3_MODEL_ID},
             {"shot_id": "A3", "model_id": SEEDANCE_MODEL_ID}]
    jobs = render_plan(clips, approved_ids=["A2", "A3"])
    pass1 = [j for j in jobs if j["pass"] == 1]
    pass2 = [j for j in jobs if j["pass"] == 2]
    assert [(j["shot_id"], j["width"], j["height"]) for j in pass1] == [
        ("A1", 864, 1536), ("A2", 864, 1536), ("A3", 1080, 1920)]
    assert [(j["shot_id"], j["width"], j["height"]) for j in pass2] == [
        ("A2", 1440, 2560), ("A3", 1080, 1920)]
    assert jobs[:3] == pass1  # all pass-1 jobs first, then the approved second passes


def test_render_plan_without_approvals_has_no_second_pass():
    jobs = render_plan([{"shot_id": "A1", "model_id": H3_MODEL_ID}])
    assert [j["pass"] for j in jobs] == [1]


def test_resolution_sizes_are_true_9_16():
    for w, h in (am.BASE_RES, am.SECOND_PASS_RES, am.SEEDANCE_RES):
        assert w * 16 == h * 9


def test_render_plan_rejects_bad_input():
    h3 = {"shot_id": "A1", "model_id": H3_MODEL_ID}
    with pytest.raises(ValueError):
        render_plan([h3, h3])
    with pytest.raises(ValueError):
        render_plan([h3], approved_ids=["NOPE"])
    with pytest.raises(ValueError):
        render_plan([{"shot_id": "A1", "model_id": "unknown-model"}])
