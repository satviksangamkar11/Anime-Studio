"""Round-3 regression (triage R3-H3, render_controller.py): readiness seconds are never negative."""
import h3.render_controller as rc
from h3.tests.synth import SHOT_IDS


def test_readiness_seconds_clamp_to_zero_for_negative_frames(story, tmp_path):
    bad = story["episodes"][0]["shots"][0]
    bad["timing_and_lattice"]["pixel_frames"] = -50
    groups = rc.select_scope(story, "all")
    res = rc.prepare(story, groups, str(tmp_path / "out"), write=False)
    rows = {r["shot_id"]: r for e in res["episodes"] for r in e["rows"]}
    assert rows[bad["shot_id"]]["seconds"] == 0.0
    assert set(rows) == set(SHOT_IDS)
