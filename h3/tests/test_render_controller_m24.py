"""M-24 tests for h3/render_controller.py: the 3-render stop (owner flag to go further) and the drift iteration order record.
Pure functions, no GPU, no network."""
import pytest

import h3.render_controller as rc


def _history(n, shot="S1"):
    return {"schema": 1, "shots": {shot: [{"n": i + 1, "kind": "qc_fail"} for i in range(n)]}}


def test_first_three_renders_are_allowed():
    for n in range(3):
        ok, reason = rc.render_allowed(_history(n), "S1")
        assert ok is True, reason


def test_fourth_render_refused_without_owner_flag():
    ok, reason = rc.render_allowed(_history(3), "S1")
    assert ok is False
    assert "owner" in reason


def test_fourth_render_allowed_with_owner_flag():
    ok, _ = rc.render_allowed(_history(3), "S1", owner_flag=True)
    assert ok is True


def test_count_is_per_shot():
    assert rc.render_allowed(_history(3, shot="S2"), "S1")[0] is True


def test_drift_order_is_the_six_owner_steps():
    assert rc.DRIFT_ORDER == ("simplify", "remove_camera_move", "move_b_closer", "split_or_chain", "new_seed", "route_change")


def test_drift_steps_recorded_in_order():
    log = rc.record_drift_step([], "simplify")
    log = rc.record_drift_step(log, "remove_camera_move")
    log = rc.record_drift_step(log, "new_seed")
    assert log == ["simplify", "remove_camera_move", "new_seed"]


def test_drift_step_out_of_order_refused():
    with pytest.raises(ValueError):
        rc.record_drift_step(["new_seed"], "simplify")


def test_drift_step_repeated_refused():
    with pytest.raises(ValueError):
        rc.record_drift_step(["simplify"], "simplify")


def test_unknown_drift_step_refused():
    with pytest.raises(ValueError):
        rc.record_drift_step([], "turn_up_the_music")


def test_record_drift_does_not_mutate_input():
    prior = ["simplify"]
    rc.record_drift_step(prior, "remove_camera_move")
    assert prior == ["simplify"]
