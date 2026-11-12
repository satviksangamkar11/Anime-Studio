"""M-02 start-only (S) route, director side: router table, settings dry run, batch rows. Offline, no GPU, no Colab."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_h3_batch as b  # noqa: E402
import h3_director  # noqa: E402
from h3.shot_mode import ShotModeError  # noqa: E402
from h3.tests.synth import build_story  # noqa: E402
from shot_router import H3_MODE, route_shot, s_allowed  # noqa: E402

LOCK_SHA = "m02lock"


@pytest.fixture
def story(tmp_path):
    return build_story(str(tmp_path))


def feat(**over):
    base = {"kind": "acting", "duration_sec": 4.0, "needs_end_pose": False, "cast_count": 1,
            "multi_arm": False, "arc_sec": 0.0}
    base.update(over)
    return base


def test_router_default_is_se():   # M-32: the default is S now; SE is the gate-off route
    assert route_shot(feat())["route"] == "S"
    assert route_shot(feat(), allow_s=False)["route"] == "SE"


def test_router_s_only_when_allowed():
    on = route_shot(feat(), allow_s=True)
    assert on["route"] == "S"
    assert H3_MODE[on["route"]] == "I2VA"
    off = route_shot(feat(), allow_s=False)
    assert off["route"] == "SE"
    assert any("S not approved" in r for r in off["reasons"])


def test_s_allowed_reads_only_the_flag():
    assert s_allowed({}) is True   # M-32: on by default
    assert s_allowed({"SHOT_MODE_S_ALLOW": "0"}) is False
    assert s_allowed({"SHOT_MODE_S_ALLOW": "1"}) is True


def _s_batch(story, env):
    ep = story["episodes"][0]
    ep["episode_id"] = "EP1"
    ep["shots"] = ep["shots"][:1]   # one shot: the routes and lock cover only it
    ep["shots"][0]["shot_id"] = "SHOT-001"   # settings_for needs a real shot id
    sid = ep["shots"][0]["shot_id"]
    pf = ep["shots"][0]["timing_and_lattice"]["pixel_frames"]
    routes = {"lock_sha256": LOCK_SHA, "routes": {sid: {"route": "S", "image_prompt_type": "S", "input_video_strength": None}}}
    lock = {"input_sha256": LOCK_SHA, "shots": [{"id": sid, "pixel_frames": pf}]}
    rows, post = b.legacy_rows(story, "EP1", routes=routes, lock=lock, env=env)
    return sid, rows, post


def test_s_batch_refused_without_flag(story):
    with pytest.raises(ShotModeError):
        _s_batch(story, {"SHOT_MODE_S_ALLOW": "0"})   # M-32: refused only when switched off


def test_s_settings_dry_run_has_start_only(story):
    sid, rows, post = _s_batch(story, {"SHOT_MODE_S_ALLOW": "1"})
    assert post == [] and rows[0]["id"] == sid
    s = h3_director.settings_for(rows[0])
    assert s["image_prompt_type"] == "S"
    assert "image_start" in s
    assert "image_end" not in s
    assert "Picture 2" not in s["prompt"]


def test_settings_refuses_declared_s_when_end_present(story):
    sid, rows, _ = _s_batch(story, {"SHOT_MODE_S_ALLOW": "1"})
    bad = copy.deepcopy(rows[0])
    bad["end"] = "keyframes/x-B.png"
    with pytest.raises(ValueError, match="image_prompt_type"):
        h3_director.settings_for(bad)
