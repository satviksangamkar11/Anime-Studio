import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import shot_router


_VALID_FEATURES = {
    "kind": "acting",
    "duration_sec": 1.0,
    "needs_end_pose": False,
    "cast_count": 1,
    "multi_arm": False,
    "arc_sec": 0.0,
}



@pytest.fixture(autouse=True)
def _s_gate_off(monkeypatch):
    # M-32: S is the default route now; this file pins the SE-family behaviour, so it switches the S gate off
    monkeypatch.setenv("SHOT_MODE_S_ALLOW", "0")

def test_list_id_raises_router_error():
    shots = [{"id": [1, 2], "features": _VALID_FEATURES}]
    with pytest.raises(shot_router.RouterError):
        shot_router.plan_reel(shots)


def test_int_id_raises_router_error():
    shots = [{"id": 5, "features": _VALID_FEATURES}]
    with pytest.raises(shot_router.RouterError):
        shot_router.plan_reel(shots)


def test_str_id_still_works():
    shots = [{"id": "shot_1", "features": _VALID_FEATURES}]
    result = shot_router.plan_reel(shots)
    assert result["routes"]["shot_1"]["route"] == "SE"
