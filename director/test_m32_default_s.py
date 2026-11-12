"""M-32 part 1: start-only route S is the default; SE stays selectable per shot. Offline, no GPU, no Colab."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_h3_batch as b  # noqa: E402
import clip_qa  # noqa: E402
import h3_director  # noqa: E402
import keyframe_jobs as kj  # noqa: E402
import shot_router  # noqa: E402
from h3 import shot_mode  # noqa: E402
from h3.shot_mode import ShotModeError  # noqa: E402
from h3.tests.synth import build_story  # noqa: E402
from shot_router import plan_from_blocking, route_shot, s_allowed  # noqa: E402
from test_shot_router_x04 import _lock, _sheet  # noqa: E402

OFF = {"SHOT_MODE_S_ALLOW": "0"}


def feat(**over):
    base = {"kind": "acting", "duration_sec": 4.0, "needs_end_pose": False, "cast_count": 1,
            "multi_arm": False, "arc_sec": 0.0}
    base.update(over)
    return base


# ---- the gate is on by default; only an explicit "0" switches it off
def test_gate_default_on_env_can_switch_off():
    assert s_allowed({}) is True
    assert s_allowed({"SHOT_MODE_S_ALLOW": "1"}) is True
    assert s_allowed(OFF) is False
    assert shot_mode.s_allowed({}) is True and shot_mode.s_allowed(OFF) is False


def test_shot_mode_accepts_s_by_default_and_refuses_when_off():
    assert shot_mode.image_prompt_type({"image_prompt_type": "S"}, {}) == "S"
    with pytest.raises(ShotModeError):
        shot_mode.image_prompt_type({"image_prompt_type": "S"}, OFF)


def test_shot_mode_s_row_has_no_end_keys():
    row = shot_mode.frame_row({"id": "A", "image_prompt_type": "S", "start": "a.png", "end": "b.png",
                               "pixel_frames": 107, "end_frame_position": 80}, {})
    assert "end" not in row and "end_frame_position" not in row


# ---- router default
def test_router_default_is_s():
    r = route_shot(feat())
    assert r["route"] == "S" and r["keyframes"] == ["A"]


def test_router_default_is_s_even_when_a_person_moves():
    assert route_shot(feat(needs_end_pose=True, arc_sec=2.0))["route"] == "S"
    assert route_shot(feat(kind="close_up"))["route"] == "REF_S"


def test_router_gate_off_restores_old_routes():
    assert route_shot(feat(), allow_s=False)["route"] == "SE"
    assert route_shot(feat(needs_end_pose=True, arc_sec=2.0), allow_s=False)["route"] == "KFI"
    assert route_shot(feat(needs_end_pose=True, arc_sec=1.0), allow_s=False)["route"] == "SOFT_SE"


def test_plan_from_blocking_default_s_with_se_override():
    sheets = {"SHOT-001": _sheet("SHOT-001", arc_sec=2.0), "SHOT-002": _sheet("SHOT-002", arc_sec=2.0)}
    sheets["SHOT-002"]["route"] = "SE"
    routes = plan_from_blocking(sheets, _lock(168, 120))
    assert routes["SHOT-001"]["route"] == "S" and routes["SHOT-001"]["h3_mode"] == "I2VA"
    assert routes["SHOT-002"]["route"] == "SE" and routes["SHOT-002"]["h3_mode"] == "FL2VA"
    assert routes["SHOT-002"]["keyframes"] == ["A", "B"]


def test_plan_from_blocking_gate_off_is_old_behaviour():
    routes = plan_from_blocking({"SHOT-001": _sheet(arc_sec=2.0)}, _lock(168), allow_s=False)
    assert routes["SHOT-001"]["route"] == "KFI"


# ---- keyframe jobs: no B for S
def _kj_sheet(route):
    sheet = {"shot": "SHOT-009", "cast": [], "people_count": 1}
    if route is not None:
        sheet["route"] = route
    return sheet


@pytest.fixture
def flow(tmp_path, monkeypatch):
    from h3.tests.synth import write_minimal_valid_png
    plates = tmp_path / "flow" / "plates"
    plates.mkdir(parents=True)
    write_minimal_valid_png(str(plates / "hall.png"), 64, 64)
    import json
    (plates / "plates.json").write_text(json.dumps({"PLATE-hall": {"path": "hall.png"}}), encoding="utf-8")
    monkeypatch.setattr(kj, "FLOW_ROOT", str(tmp_path / "flow"))


def test_keyframe_jobs_no_b_by_default(flow):
    assert kj.jobs_for_shot(_kj_sheet(None), "PLATE-hall", [])[1] is None
    assert kj.jobs_for_shot(_kj_sheet("S"), "PLATE-hall", [])[1] is None


def test_keyframe_jobs_b_only_for_explicit_se_family(flow):
    for route in ("SE", "SOFT_SE", "KFI"):
        assert kj.jobs_for_shot(_kj_sheet(route), "PLATE-hall", [])[1] is not None


def test_keyframe_jobs_gate_off_gives_b(flow, monkeypatch):
    monkeypatch.setenv("SHOT_MODE_S_ALLOW", "0")
    assert kj.jobs_for_shot(_kj_sheet(None), "PLATE-hall", [])[1] is not None


# ---- clip gate: end check skipped for S (the default)
def test_clip_qa_end_result_skipped_for_s():
    assert clip_qa._end_result("S", None)["skipped"]
    assert clip_qa._end_result("SE", {"ssim": 0.9, "lpips": 0.0, "cosine": 0.95})["pass"] is True


def test_clip_qa_default_route_is_s():
    import inspect
    assert inspect.signature(clip_qa.qa_shot).parameters["route"].default == "S"


def test_clip_qa_features_without_key_b():
    import numpy as np
    frames = np.random.RandomState(1).rand(5, 8, 8).astype("float32")
    out = clip_qa.features(frames, frames[0], None)
    assert out["end"]["ssim"] is None or isinstance(out["end"]["ssim"], float)


# ---- batch dry run writes S settings
@pytest.fixture
def story(tmp_path):
    return build_story(str(tmp_path))


def _batch(story, route_row):
    ep = story["episodes"][0]
    ep["episode_id"] = "EP1"
    ep["shots"] = ep["shots"][:1]
    ep["shots"][0]["shot_id"] = "SHOT-001"
    pf = ep["shots"][0]["timing_and_lattice"]["pixel_frames"]
    routes = {"lock_sha256": "l", "routes": {"SHOT-001": route_row}}
    lock = {"input_sha256": "l", "shots": [{"id": "SHOT-001", "pixel_frames": pf, "end_frame_position": pf - 8}]}
    return b.legacy_rows(story, "EP1", routes=routes, lock=lock, env={})


def test_dry_run_default_writes_s_settings(story):
    rows, _ = _batch(story, {"route": "S"})   # no image_prompt_type in the route row: the default is S
    s = h3_director.settings_for(rows[0])
    assert s["image_prompt_type"] == "S" and "image_end" not in s and "Picture 2" not in s["prompt"]
    assert "end" not in rows[0]


def test_dry_run_se_override_keeps_end(story):
    rows, _ = _batch(copy.deepcopy(story), {"route": "SE", "image_prompt_type": "SE", "input_video_strength": None})
    s = h3_director.settings_for(rows[0])
    assert s["image_prompt_type"] == "SE" and "image_end" in s


def test_h3_director_start_only_shot_is_s_and_both_images_is_se():
    shot = {"id": "SHOT-001", "mode": "fl2va", "start": "keyframes/a.png", "action": "x", "render_frames": 107,
            "prompt_override": "p"}
    assert h3_director.settings_for(shot)["image_prompt_type"] == "S"
    shot["end"] = "keyframes/b.png"
    assert h3_director.settings_for(shot)["image_prompt_type"] == "SE"
