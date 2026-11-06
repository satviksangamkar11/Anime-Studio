import json

import pytest

from h3.asset_manifest import H3_MODEL_ID, SEEDANCE_MODEL_ID, blocking_problems, empty_manifest, make_clip_entry
from h3.fallback_policy import (attempts_for, may_rerender, next_action, record_attempt, reference_anchor_prefix,
                                reset_attempts, load_history, split_shot_row, validate_human_choice, verify_split)
from h3.shot_table_spec import HUMAN_CHOICES, lattice


def _row(sid="A1", dur=10.0, route="FL2VA"):
    return {
        "id": sid, "route": route, "editorial_duration_sec": dur, "lattice_n": 12, "pixel_frames": 209,
        "latent_slots": 62, "hook_type": "reveal", "is_opening_0_2s_hook": True, "is_closing_hook": False,
        "continuity_handoff": {"incoming": "door opens", "outgoing": "lamp is lit", "loop_seam": None},
        "reference_anchors": {
            "fixed_landmarks": ["stone well", "tulsi plant"],
            "character_positions": [{"id": "CHAR-RAM", "screen": "left third", "depth": "mid"}],
            "exited_character_status": [{"id": "CHAR-MOTHER", "left_after_shot": "A0", "off_stage_shots": 1,
                                         "released": False}],
            "lighting_baseline": {"key": "warm lamp", "fill": "soft blue", "rim": "none",
                                  "shot_modifiers": "dusk"}},
        "per_second_directives": [{"t0": 0, "t1": 1, "action_pose_expression": "a", "camera": "c",
                                   "spatial_position": "s", "audio_cue": "u", "handoff_to_next_second": "h"},
                                  {"t0": 7, "t1": 9, "action_pose_expression": "b", "camera": "c",
                                   "spatial_position": "s", "audio_cue": "u", "handoff_to_next_second": "h"}],
        "audio_and_dialogue_track": {
            "narration": None, "dialogue": [],
            "sfx_cues": [{"time_range": "1.0-1.5s", "sfx_key": "door", "description": "d"},
                         {"time_range": "7.0-7.5s", "sfx_key": "bell", "description": "b"}],
            "performance_notes": {"text": "t", "narrator_mouth_closed": True,
                                  "mouth_state": {"0": "closed", "7": "closed"}}},
    }


def _fail(row=None, **extra):
    return {"kind": "reference_drift", "shot_row": row or _row(), **extra}


def _attempts(n):
    return [{"n": i + 1, "kind": "reference_drift", "rung": min(i + 1, 4), "action": "x", "model": None}
            for i in range(n)]


# ---- Reference Anchors prefix (rung 1) ----

def test_prefix_contains_every_anchor_and_is_deterministic():
    row = _row()
    text = reference_anchor_prefix(row)
    assert text == reference_anchor_prefix(_row())
    for needle in ("stone well", "tulsi plant", "CHAR-RAM at left third, depth mid", "CHAR-MOTHER",
                   "still off-stage", "warm lamp", "soft blue", "dusk"):
        assert needle in text
    assert text.startswith("REFERENCE ANCHORS")


def test_prefix_changes_when_an_anchor_changes():
    row = _row()
    row["reference_anchors"]["lighting_baseline"]["key"] = "cold moon"
    assert "cold moon" in reference_anchor_prefix(row)
    assert "warm lamp" not in reference_anchor_prefix(row)


def test_prefix_rejects_missing_anchor_keys():
    row = _row()
    del row["reference_anchors"]["fixed_landmarks"]
    with pytest.raises(ValueError):
        reference_anchor_prefix(row)


# ---- rung transitions ----

@pytest.mark.parametrize("failures,rung", [(1, 1), (2, 2), (3, 3), (4, 4), (5, 4), (9, 4)])
def test_rung_follows_failure_count(failures, rung):
    action = next_action("A1", _attempts(failures - 1), _fail())
    assert action["rung"] == rung
    assert action["failure_count"] == failures


def test_rung1_regenerates_in_h3_with_the_exact_prefix():
    action = next_action("A1", [], _fail())
    assert action["action"] == "regenerate_h3_with_anchor_prefix"
    assert action["model"] == H3_MODEL_ID
    assert action["prompt_prefix"] == reference_anchor_prefix(_row())


def test_rung2_shortens_to_6s_and_splits_the_rest_onto_the_lattice():
    action = next_action("A1", _attempts(1), _fail())
    assert action["action"] == "shorten_split_recheck_rerender"
    rows = action["split_rows"]
    assert rows[0]["id"] == "A1" and rows[0]["editorial_duration_sec"] <= 6.0
    assert [r["id"] for r in rows] == ["A1", "A1_s2"]
    for r in rows:
        lat = lattice(r["lattice_n"])
        assert (r["pixel_frames"], r["latent_slots"]) == (lat["pixel_frames"], lat["latent_slots"])
        assert r["editorial_duration_sec"] == lat["seconds"]
    total = sum(r["editorial_duration_sec"] for r in rows)
    assert abs(total - 10.0) < 0.5 and action["total_drift_sec"] == round(total - 10.0, 3)
    assert action["self_check_required"] is True and action["self_check_ok"] is None


def test_rung2_rebases_directives_and_moves_sfx_by_start_time():
    rows, warnings, drift = split_shot_row(_row())
    first, second = rows
    assert first["per_second_directives"][0]["t0"] == 0.0
    assert [d["t0"] for d in second["per_second_directives"]] == [1.125]
    assert [c["time_range"] for c in first["audio_and_dialogue_track"]["sfx_cues"]] == ["1-1.5s"]
    assert [c["time_range"] for c in second["audio_and_dialogue_track"]["sfx_cues"]] == ["1.125-1.625s"]
    assert first["audio_and_dialogue_track"]["performance_notes"]["mouth_state"] == {"0": "closed"}
    assert second["audio_and_dialogue_track"]["performance_notes"]["mouth_state"] == {"1": "closed"}
    assert second["continuity_handoff"] == {"incoming": "continues from A1", "outgoing": "lamp is lit",
                                            "loop_seam": None}
    assert first["continuity_handoff"]["outgoing"] == "continues into A1_s2"
    assert second["is_opening_0_2s_hook"] is False and first["is_opening_0_2s_hook"] is True
    assert any("route FL2VA" in w for w in warnings)


def test_rung2_warns_when_narration_crosses_a_split_boundary():
    row = _row()
    row["audio_and_dialogue_track"]["narration"] = {"text": "x", "language": "hi", "time_range": [5.5, 6.5]}
    _, warnings, _ = split_shot_row(row)
    assert any("narration crosses" in w for w in warnings)


def test_rung2_short_row_is_not_split():
    row = _row(dur=5.0)
    action = next_action("A1", _attempts(1), _fail(row))
    assert len(action["split_rows"]) == 1 and action["total_drift_sec"] == 0.0


def test_rung2_optional_route_switch_only_for_boundary_drift():
    assert "optional_route_switch" not in next_action("A1", _attempts(1), _fail())
    act = next_action("A1", _attempts(1), _fail(boundary_framing_drift=True))
    assert act["optional_route_switch"] == "Ref2VA"
    act = next_action("A1", _attempts(1), _fail(_row(route="Ref2VA"), boundary_framing_drift=True))
    assert act["optional_route_switch"] == "FL2VA"
    act = next_action("A1", _attempts(1), _fail(_row(route="T2VA"), boundary_framing_drift=True))
    assert "optional_route_switch" not in act


def test_rung2_must_pass_self_check_before_rerender():
    action = next_action("A1", _attempts(1), _fail())
    assert may_rerender(action) is False
    calls = []

    def passing(rows):
        calls.append([r["id"] for r in rows])
        return {"ok": True, "errors": []}

    verify_split(action, passing)
    assert calls == [["A1", "A1_s2"]] and action["self_check_ok"] is True and may_rerender(action) is True


def test_rung2_failing_self_check_blocks_rerender():
    action = verify_split(next_action("A1", _attempts(1), _fail()),
                          lambda rows: {"ok": False, "errors": [{"code": "S55-2"}]})
    assert action["self_check_ok"] is False and may_rerender(action) is False


def test_verify_split_only_for_rung2():
    with pytest.raises(ValueError):
        verify_split(next_action("A1", [], _fail()), lambda rows: {"ok": True})


def test_rung3_switches_to_seedance_1080p():
    action = next_action("A1", _attempts(2), _fail())
    assert action["action"] == "switch_to_seedance"
    assert action["model"] == SEEDANCE_MODEL_ID and action["resolution"] == [1080, 1920]
    assert action["mode"] == "hybrid_per_shot_mixed" and action["manifest_log_required"] is True


def test_rung4_is_a_human_gate_with_the_four_choices_and_no_clip():
    action = next_action("A1", _attempts(3), _fail())
    assert action["action"] == "human_gate" and action["blocking"] is True
    assert action["clip_emitted"] is False
    assert action["human_choices"] == list(HUMAN_CHOICES) and len(action["human_choices"]) == 4
    assert may_rerender(action) is False


def test_validate_human_choice():
    for choice in HUMAN_CHOICES:
        assert validate_human_choice(choice) == choice
    with pytest.raises(ValueError):
        validate_human_choice("ignore_it")


def test_next_action_input_validation():
    with pytest.raises(ValueError):
        next_action("", [], _fail())
    with pytest.raises(ValueError):
        next_action("A1", [], {"kind": "  ", "shot_row": _row()})
    with pytest.raises(ValueError):
        next_action("A1", [], {"kind": "drift"})          # rung 1 needs the shot row
    with pytest.raises(ValueError):
        next_action("A1", ["not-a-dict"], _fail())


# ---- restart persistence ----

def test_restart_keeps_the_rung(tmp_path):
    path = str(tmp_path / "fallback_history.json")
    row = _row()
    for expected in (1, 2):
        history = load_history(path)
        action = next_action("A1", attempts_for(history, "A1"), _fail(row))
        assert action["rung"] == expected
        record_attempt(path, "A1", _fail(), action)
    # process restarts: a fresh load sees two recorded failures, so the next failure is rung 3
    fresh = load_history(path)
    assert len(attempts_for(fresh, "A1")) == 2
    assert next_action("A1", attempts_for(fresh, "A1"), _fail(row))["rung"] == 3


def test_history_never_stores_the_shot_row(tmp_path):
    path = str(tmp_path / "h.json")
    action = next_action("A1", [], _fail())
    record_attempt(path, "A1", _fail(), action)
    text = open(path, encoding="utf-8").read()
    assert "reference_anchors" not in text and "per_second_directives" not in text
    assert json.loads(text)["shots"]["A1"][0]["rung"] == 1


def test_reset_after_a_passing_clip_starts_again_at_rung1(tmp_path):
    path = str(tmp_path / "h.json")
    for _ in range(3):
        record_attempt(path, "A1", _fail(), next_action("A1", attempts_for(load_history(path), "A1"), _fail()))
    assert next_action("A1", attempts_for(load_history(path), "A1"), _fail())["rung"] == 4
    reset_attempts(path, "A1")
    assert next_action("A1", attempts_for(load_history(path), "A1"), _fail())["rung"] == 1


def test_history_is_per_shot(tmp_path):
    path = str(tmp_path / "h.json")
    record_attempt(path, "A1", _fail(), next_action("A1", [], _fail()))
    assert attempts_for(load_history(path), "A2") == []


# ---- integration with the manifest: a rung 3 switch must be logged, rung 4 must block ----

def test_rung3_switch_logged_in_manifest_and_rung4_blocks_assembly():
    from h3.asset_manifest import record_model_switch
    manifest = empty_manifest()
    act3 = next_action("A1", _attempts(2), _fail())
    record_model_switch(manifest, "A1", H3_MODEL_ID, act3["model"], rung=3, reason="drift after rung 2")
    seedance_entry = make_clip_entry("A1", bible_sha256="1" * 64, shot_row_sha256="2" * 64,
                                     start_frame_sha256="3" * 64, end_frame_sha256="4" * 64,
                                     model_id=SEEDANCE_MODEL_ID)
    manifest["clips"]["A1"] = seedance_entry
    current = {"A1": {"bible_sha256": "1" * 64, "shot_row_sha256": "2" * 64, "start_frame_sha256": "3" * 64,
                      "end_frame_sha256": "4" * 64, "model_id": SEEDANCE_MODEL_ID}}
    assert blocking_problems(manifest, current) == []
    gate = next_action("A1", _attempts(3), _fail())
    manifest["clips"]["A1"] = {**seedance_entry, "status": "human_gate"}
    assert blocking_problems(manifest, current) != []
    assert gate["clip_emitted"] is False
