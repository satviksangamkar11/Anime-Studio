"""Tests for director/shot_router.py (spec J14). Pure table rules; expectations worked out by hand.

Base features used by most tests (rules 1-6 are tried in order, first match wins):
  kind "acting", duration 4.0, needs_end_pose False, cast_count 1, multi_arm False, arc_sec 0.0
  -> nothing before rule 6 matches -> route "S" with allow_s=True, "SE" with the default allow_s=False.
"""
import copy

import pytest

from shot_router import RouterError, ROUTES, route_shot, plan_reel


def feat(**over):
    base = {
        "kind": "acting",
        "duration_sec": 4.0,
        "needs_end_pose": False,
        "cast_count": 1,
        "multi_arm": False,
        "arc_sec": 0.0,
    }
    base.update(over)
    return base


# Exact per-route results (hand-written from the spec table)
EXPECTED_S = {
    "route": "S",
    "image_prompt_type": "S",
    "input_video_strength": None,
    "keyframes": ["A"],
    "gpu": True,
    "est_units": 1.1,
    "requires_owner_flag": True,
    "h3_mode": "I2VA",
    "reasons": ["start frame only: no end-frame lock"],
}
EXPECTED_REF_S = {
    "route": "REF_S",
    "image_prompt_type": "S",
    "input_video_strength": None,
    "keyframes": ["A", "refs"],
    "gpu": True,
    "est_units": 1.4,
    "requires_owner_flag": True,
    "h3_mode": "Ref2VA",
    "reasons": ["start frame plus face/body references for identity or extra arms"],
}
EXPECTED_SE = {
    "route": "SE",
    "image_prompt_type": "SE",
    "input_video_strength": None,
    "keyframes": ["A", "B"],
    "gpu": True,
    "est_units": 1.2,
    "requires_owner_flag": False,
    "h3_mode": "FL2VA",
    "reasons": ["start and end frame locked (default image mode)"],
}
EXPECTED_REF_SE = {
    "route": "REF_SE",
    "image_prompt_type": "SE",
    "input_video_strength": None,
    "keyframes": ["A", "B", "refs"],
    "gpu": True,
    "est_units": 1.4,
    "requires_owner_flag": False,
    "h3_mode": "Ref2VA",
    "reasons": ["start and end frame plus face/body references"],
}
EXPECTED_SOFT_SE = {
    "route": "SOFT_SE",
    "image_prompt_type": "SE",
    "input_video_strength": 0.6,
    "keyframes": ["A", "B"],
    "gpu": True,
    "est_units": 1.2,
    "requires_owner_flag": False,
    "h3_mode": "FL2VA",
    "reasons": ["end frame softened to 0.6 and placed at the cut"],
}
EXPECTED_KFI = {
    "route": "KFI",
    "image_prompt_type": "SE",
    "input_video_strength": 0.65,
    "keyframes": ["A", "MID", "B"],
    "gpu": True,
    "est_units": 1.4,
    "requires_owner_flag": False,
    "h3_mode": "FL2VA",
    "reasons": ["middle keyframe for a movement longer than 1.5 s"],
}
EXPECTED_POST = {
    "route": "POST",
    "image_prompt_type": None,
    "input_video_strength": None,
    "keyframes": ["A", "plate"],
    "gpu": False,
    "est_units": 0.0,
    "requires_owner_flag": False,
    "h3_mode": None,
    "reasons": ["no video render: 2.5D hold, pan or shake"],
}


def test_routes_constant():
    assert ROUTES == ("S", "REF_S", "SE", "REF_SE", "SOFT_SE", "KFI", "POST")


def test_plain_shot_routes_se():
    # default allow_s=False: SE row plus the fallback reason
    expected = dict(EXPECTED_SE, reasons=EXPECTED_SE["reasons"] + ["S not approved: SE fallback"])
    assert route_shot(feat()) == expected


def test_allow_s_true_routes_s():
    assert route_shot(feat(), allow_s=True) == EXPECTED_S


def test_close_up_ref_se_ref2va():
    res = route_shot(feat(kind="close_up"))
    assert res["route"] == "REF_SE"
    assert res["h3_mode"] == "Ref2VA"
    assert res["reasons"] == [
        "start and end frame plus face/body references",
        "S not approved: SE fallback",
    ]


def test_missing_features_router_error():
    with pytest.raises(RouterError, match="shot #0"):
        plan_reel([{"id": "x"}])
    with pytest.raises(RouterError, match="shot #1"):
        plan_reel([{"id": "a", "features": feat()}, "not a dict"])
    with pytest.raises(RouterError, match="missing features"):
        plan_reel([{"id": "a"}])


def test_every_gpu_route_has_workflow():
    # every route reachable with allow_s=False, from features that hit each rule
    samples = [
        feat(),
        feat(kind="close_up"),
        feat(needs_end_pose=True, arc_sec=0.5),
        feat(needs_end_pose=True, arc_sec=2.0),
        feat(kind="camera_move"),
    ]
    seen = set()
    for f in samples:
        res = route_shot(f)
        seen.add(res["route"])
        if res["gpu"]:
            assert res["h3_mode"] in {"FL2VA", "Ref2VA"}
            assert res["requires_owner_flag"] is False
    assert seen == {"SE", "REF_SE", "SOFT_SE", "KFI", "POST"}
    plan = plan_reel([{"id": f"s{i}", "features": f} for i, f in enumerate(samples)])
    assert plan["needs_owner_flag"] == []


def test_crowd_reason_only_if_over_3():
    assert route_shot(feat(kind="crowd"))["reasons"] == ["no video render: 2.5D hold, pan or shake"]
    assert route_shot(feat(cast_count=4))["reasons"] == [
        "no video render: 2.5D hold, pan or shake",
        "more than 3 moving people",
    ]


# ---------- each rule once ----------

def test_rule1_camera_move_only_gives_post():
    assert route_shot(feat(kind="camera_move"))["route"] == "POST"


def test_rule2_crowd_only_gives_post_without_crowd_reason():
    # the crowd reason is added only when cast_count > 3 (S-06)
    res = route_shot(feat(kind="crowd"))
    assert res["route"] == "POST"
    assert not any("more than 3 moving people" in r for r in res["reasons"])


def test_rule2_cast_count_above_3_gives_post_with_reason():
    res = route_shot(feat(cast_count=4))
    assert res["route"] == "POST"
    assert any("more than 3 moving people" in r for r in res["reasons"])


def test_rule2_crowd_reasons_exact_table_only():
    # S-06: a crowd kind with cast_count <= 3 keeps the table reason only
    res = route_shot(feat(kind="crowd"))
    assert res["reasons"] == ["no video render: 2.5D hold, pan or shake"]


def test_rule2_cast_count_4_reasons_exact_table_first_then_extra():
    # round 9 (observer 8): same exact two-entry list for cast_count > 3
    res = route_shot(feat(cast_count=4))
    assert res["reasons"] == ["no video render: 2.5D hold, pan or shake", "more than 3 moving people"]


def test_rule2_cast_count_3_is_not_crowd():
    # 3 is not > 3, so rule 2 does not fire; the base acting shot goes to S
    assert route_shot(feat(cast_count=3), allow_s=True)["route"] == "S"


def test_rule3_end_pose_and_long_arc_gives_kfi():
    assert route_shot(feat(needs_end_pose=True, arc_sec=1.6))["route"] == "KFI"


def test_rule4_end_pose_short_arc_gives_soft_se():
    assert route_shot(feat(needs_end_pose=True, arc_sec=0.5))["route"] == "SOFT_SE"


def test_rule5_close_up_gives_ref_s():
    assert route_shot(feat(kind="close_up"), allow_s=True)["route"] == "REF_S"


def test_rule5_multi_arm_gives_ref_s():
    assert route_shot(feat(multi_arm=True), allow_s=True)["route"] == "REF_S"


def test_rule6_default_gives_s():
    assert route_shot(feat(), allow_s=True)["route"] == "S"
    assert route_shot(feat(kind="body_action"), allow_s=True)["route"] == "S"
    assert route_shot(feat(kind="seam"), allow_s=True)["route"] == "S"


def test_long_arc_without_end_pose_is_not_kfi():
    # rule 3 needs needs_end_pose; a 3 s movement alone is still S (SE when S is not allowed)
    assert route_shot(feat(arc_sec=3.0), allow_s=True)["route"] == "S"
    assert route_shot(feat(arc_sec=3.0))["route"] == "SE"


# ---------- order ----------

def test_crowd_beats_needs_end_pose():
    res = route_shot(feat(kind="crowd", needs_end_pose=True, arc_sec=3.0))
    assert res["route"] == "POST"


def test_cast_count_beats_needs_end_pose():
    assert route_shot(feat(cast_count=4, needs_end_pose=True))["route"] == "POST"


def test_camera_move_beats_everything():
    res = route_shot(feat(kind="camera_move", cast_count=5, needs_end_pose=True, arc_sec=3.0, multi_arm=True))
    assert res["route"] == "POST"
    # rule 1 wins, so the reason is the table reason, not the crowd reason
    assert res["reasons"] == ["no video render: 2.5D hold, pan or shake"]


def test_crowd_beats_multi_arm():
    assert route_shot(feat(kind="crowd", multi_arm=True))["route"] == "POST"


def test_end_pose_beats_close_up():
    assert route_shot(feat(kind="close_up", needs_end_pose=True, arc_sec=0.0))["route"] == "SOFT_SE"


def test_end_pose_beats_multi_arm():
    assert route_shot(feat(multi_arm=True, needs_end_pose=True, arc_sec=0.0))["route"] == "SOFT_SE"


def test_arc_exactly_1_5_is_soft_se():
    # 1.5 is not > 1.5
    assert route_shot(feat(needs_end_pose=True, arc_sec=1.5))["route"] == "SOFT_SE"


def test_arc_1_51_is_kfi():
    assert route_shot(feat(needs_end_pose=True, arc_sec=1.51))["route"] == "KFI"


# ---------- exact per-route values ----------

def test_exact_result_s():
    assert route_shot(feat(), allow_s=True) == EXPECTED_S


def test_exact_result_ref_s():
    assert route_shot(feat(kind="close_up"), allow_s=True) == EXPECTED_REF_S


def test_exact_result_ref_se():
    expected = dict(EXPECTED_REF_SE, reasons=EXPECTED_REF_SE["reasons"] + ["S not approved: SE fallback"])
    assert route_shot(feat(kind="close_up")) == expected


def test_exact_result_soft_se():
    assert route_shot(feat(needs_end_pose=True, arc_sec=0.0)) == EXPECTED_SOFT_SE


def test_exact_result_kfi():
    assert route_shot(feat(needs_end_pose=True, arc_sec=2.0)) == EXPECTED_KFI


def test_exact_result_post_from_camera_move():
    assert route_shot(feat(kind="camera_move")) == EXPECTED_POST


# ---------- validation ----------

@pytest.mark.parametrize(
    "bad_features, key",
    [
        ({k: v for k, v in feat().items() if k != "arc_sec"}, "arc_sec"),
        (feat(kind="dance"), "kind"),
        (feat(duration_sec=0.0), "duration_sec"),
        (feat(duration_sec=-2.0), "duration_sec"),
        (feat(duration_sec="4"), "duration_sec"),
        (feat(cast_count=-1), "cast_count"),
        (feat(cast_count=2.5), "cast_count"),
        (feat(arc_sec=-0.1), "arc_sec"),
        (feat(needs_end_pose="yes"), "needs_end_pose"),
        (feat(multi_arm="no"), "multi_arm"),
    ],
)
def test_validation_errors_name_the_key(bad_features, key):
    with pytest.raises(RouterError, match=key):
        route_shot(bad_features)


# ---------- plan_reel ----------

def mixed_reel():
    # hand arithmetic:
    # s1 acting base            -> S        est 1.1, images A (1), gpu True,  owner True
    # s2 camera_move            -> POST     est 0.0, images A, plate (2), gpu False, owner False
    # s3 body_action end arc 2  -> KFI      est 1.4, images A, MID, B (3), gpu True,  owner False
    # s4 close_up               -> REF_S    est 1.4, images A (1; refs not counted), gpu True, owner True
    # s5 end pose arc 0.5       -> SOFT_SE  est 1.2, images A, B (2), gpu True,  owner False
    # total est = 1.1 + 0.0 + 1.4 + 1.4 + 1.2 = 5.1
    # keyframe_count = 1 + 2 + 3 + 1 + 2 = 9
    # gpu_shots = S, KFI, REF_S, SOFT_SE = 4
    # needs_owner_flag = s1 (S) and s4 (REF_S)
    return [
        {"id": "s1", "features": feat()},
        {"id": "s2", "features": feat(kind="camera_move")},
        {"id": "s3", "features": feat(kind="body_action", needs_end_pose=True, arc_sec=2.0)},
        {"id": "s4", "features": feat(kind="close_up")},
        {"id": "s5", "features": feat(needs_end_pose=True, arc_sec=0.5)},
    ]


def test_plan_reel_mixed_totals():
    res = plan_reel(mixed_reel(), allow_s=True)
    assert set(res.keys()) == {"routes", "total_est_units", "keyframe_count", "gpu_shots", "needs_owner_flag"}
    assert res["total_est_units"] == pytest.approx(5.1)
    assert res["keyframe_count"] == 9
    assert res["gpu_shots"] == 4
    assert res["needs_owner_flag"] == ["s1", "s4"]


def test_plan_reel_routes_per_shot():
    res = plan_reel(mixed_reel(), allow_s=True)
    routes = res["routes"]
    assert set(routes.keys()) == {"s1", "s2", "s3", "s4", "s5"}
    assert routes["s1"] == EXPECTED_S
    assert routes["s2"] == EXPECTED_POST
    assert routes["s3"] == EXPECTED_KFI
    assert routes["s4"] == EXPECTED_REF_S
    assert routes["s5"] == EXPECTED_SOFT_SE


def test_plan_reel_duplicate_ids_raise():
    shots = mixed_reel()
    shots.append({"id": "s1", "features": feat()})
    with pytest.raises(RouterError):
        plan_reel(shots)


def test_plan_reel_bad_features_raise():
    shots = [{"id": "x", "features": feat(kind="dance")}]
    with pytest.raises(RouterError, match="kind"):
        plan_reel(shots)


# ---------- inputs not mutated ----------

@pytest.mark.parametrize("bad", [[], None, "acting"])
def test_non_dict_features_raise_router_error(bad):
    # observer 9 (TEST_FINDINGS codex): a non-dict input must raise RouterError naming "features"
    with pytest.raises(RouterError, match="features"):
        route_shot(bad)


def test_returned_result_does_not_alias_route_table():
    # observer 9 (spec J14 round-10 item 1): mutating a returned result must not change later results.
    first = route_shot(feat(), allow_s=True)
    first["keyframes"].append("X")
    first["reasons"].append("Y")
    assert route_shot(feat(), allow_s=True)["keyframes"] == ["A"]
    assert route_shot(feat(), allow_s=True)["reasons"] == ["start frame only: no end-frame lock"]


def test_route_shot_does_not_mutate_features():
    f = feat(kind="crowd", needs_end_pose=True, arc_sec=3.0)
    before = copy.deepcopy(f)
    route_shot(f)
    assert f == before


def test_plan_reel_does_not_mutate_shots():
    shots = mixed_reel()
    before = copy.deepcopy(shots)
    plan_reel(shots)
    assert shots == before
