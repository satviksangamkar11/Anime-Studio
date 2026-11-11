"""Tests for X-04: shot_router.plan_from_blocking and the CLI (routes.json).

Hand-worked values (frames at 24 fps):
  168 frames -> 7.0 s; 120 frames -> 5.0 s.
  KFI case: one cast member seated -> standing, same spot, arc_sec 2.0 -> needs_end_pose True, cast_count 1,
  arc 2.0 > 1.5 -> KFI, h3_mode FL2VA.
"""
import ast
import copy
import json
import os
import sys
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, str(Path(HERE).parent))

import blocking  # noqa: E402
import shot_router  # noqa: E402
from shot_router import H3_MODE, ROUTES, RouterError, plan_from_blocking, route_shot  # noqa: E402
from timeline_lock_io import write_lock  # noqa: E402
from h3.router import REF2VA  # noqa: E402  the h3 name the sing8 compiler uses


def _pose(x, pose, facing="camera"):
    return {"x": x, "y": 0.9, "scale": 0.6, "facing": facing, "pose": pose, "mouth_moves": False}


def _member(start_pose="seated", end_pose="standing", arms=2, mid="SHIVA", end_x=0.5):
    return {
        "id": mid,
        "name": mid,
        "speaks": False,
        "arms": arms,
        "source_refs": ["ch2:p10"],
        "start": _pose(0.5, start_pose),
        "end": dict(_pose(end_x, end_pose)),
    }


def _sheet(shot_id="SHOT-001", arc_sec=2.0, cast=None, writer_seconds=3.0, kind="acting"):
    return {
        "schema": "blocking/1",
        "shot_id": shot_id,
        "plate_id": "PLATE-throne",
        "location_id": "LOC-palace-hall",
        "kind": kind,
        "camera": {"mode": "fixed", "framing": "medium", "move": None},
        "light": {"key_dir": "left", "palette_id": "PAL-warm"},
        "props": [],
        "entries": [],
        "exits": [],
        "sound_cues": [],
        "arc_sec": arc_sec,
        "writer_seconds": writer_seconds,
        "cut_to_next": "cut",
        "source_refs": ["ch2:p10"],
        "cast": [_member()] if cast is None else cast,
    }


def _lock(*frames, ids=None, sha="lock-input-sha"):
    ids = ids or [f"SHOT-{i + 1:03d}" for i in range(len(frames))]
    shots = []
    cursor = 0
    for shot_id, edit in zip(ids, frames):
        shots.append({"id": shot_id, "start_frame": cursor, "edit_frames": edit})
        cursor += edit
    return {"fps": 24, "input_sha256": sha, "shots": shots}


def test_plan_from_blocking_uses_lock_seconds(monkeypatch):
    # the sheet says writer_seconds 3, the lock says 168 frames: the router must see 7.0 s
    seen = []
    real = shot_router.route_shot

    def spy(features, allow_s=False):
        seen.append(copy.deepcopy(features))
        return real(features, allow_s=allow_s)

    monkeypatch.setattr(shot_router, "route_shot", spy)
    plan_from_blocking({"SHOT-001": _sheet(writer_seconds=3.0)}, _lock(168))
    assert seen[0]["duration_sec"] == 7.0


def test_kfi_case_routes_to_fl2va():
    routes = plan_from_blocking({"SHOT-001": _sheet(arc_sec=2.0)}, _lock(168))
    res = routes["SHOT-001"]
    assert res["route"] == "KFI"
    assert res["h3_mode"] == "FL2VA"
    assert res["keyframes"] == ["A", "MID", "B"]


def test_soft_se_case_short_arc():
    routes = plan_from_blocking({"SHOT-001": _sheet(arc_sec=1.0)}, _lock(168))
    assert routes["SHOT-001"]["route"] == "SOFT_SE"


def test_routes_keep_lock_order():
    lock = _lock(168, 120, ids=["SHOT-002", "SHOT-001"])
    sheets = {"SHOT-001": _sheet("SHOT-001"), "SHOT-002": _sheet("SHOT-002")}
    routes = plan_from_blocking(sheets, lock)
    assert list(routes) == ["SHOT-002", "SHOT-001"]


def test_missing_sheet_raises_router_error():
    # lock shot SHOT-002 has no sheet
    with pytest.raises(RouterError, match="SHOT-002"):
        plan_from_blocking({"SHOT-001": _sheet("SHOT-001")}, _lock(168, 120))


def test_sheet_without_lock_shot_raises_router_error():
    sheets = {"SHOT-001": _sheet("SHOT-001"), "SHOT-009": _sheet("SHOT-009")}
    with pytest.raises(RouterError, match="SHOT-009"):
        plan_from_blocking(sheets, _lock(168))


def test_negative_arc_raises_router_error():
    # the router validates features: a negative arc from the sheet is a RouterError, not a silent route
    with pytest.raises(RouterError, match="arc_sec"):
        plan_from_blocking({"SHOT-001": _sheet(arc_sec=-1.0)}, _lock(168))


def test_h3_mode_table_covers_every_route():
    assert set(H3_MODE) == set(ROUTES)
    assert H3_MODE["POST"] is None
    for route in ROUTES:
        if route != "POST":
            assert H3_MODE[route] is not None


def _compile_known_routes():
    """Route names compile_h3_sing8.py accepts: the tuple in its 'route not in (...)' check (read from source)."""
    src = (Path(HERE).parent / "h3" / "compile_h3_sing8.py").read_text(encoding="utf-8")
    known = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.NotIn):
            for elt in getattr(node.comparators[0], "elts", []):
                if isinstance(elt, ast.Constant):
                    known.add(elt.value)
                elif isinstance(elt, ast.Name) and elt.id == "REF2VA":
                    known.add(REF2VA)
    return known


def test_gpu_h3_modes_are_known_to_compile_h3_sing8():
    known = _compile_known_routes()
    assert {"FL2VA", REF2VA} <= known
    for route in ROUTES:
        mode = H3_MODE[route]
        if route != "POST" and mode in ("FL2VA", REF2VA):
            assert mode in known, route


def test_every_gpu_route_has_h3_mode():
    # one sheet per route, every route reached with allow_s both ways
    cases = {
        "S": _sheet(arc_sec=0.0, cast=[_member("standing", "standing")], kind="acting"),
        "REF_S": _sheet(arc_sec=0.0, cast=[_member("standing", "standing")], kind="close_up"),
        "SE": _sheet(arc_sec=0.0, cast=[_member("standing", "standing")], kind="acting"),
        "REF_SE": _sheet(arc_sec=0.0, cast=[_member("standing", "standing")], kind="close_up"),
        "SOFT_SE": _sheet(arc_sec=0.5),
        "KFI": _sheet(arc_sec=2.0),
        "POST": _sheet(kind="camera_move"),
    }

    reached = set()
    for route, sheet in cases.items():
        allow = route in ("S", "REF_S")
        res = plan_from_blocking({"SHOT-001": sheet}, _lock(168), allow_s=allow)["SHOT-001"]
        reached.add(res["route"])
        if res["gpu"]:
            assert res["h3_mode"] in ("FL2VA", REF2VA, "I2VA")
        else:
            assert res["h3_mode"] is None
    assert reached == set(ROUTES)
    assert H3_MODE["REF_S"] == REF2VA
    assert H3_MODE["SE"] == "FL2VA"


def test_routes_json_carries_lock_sha(tmp_path):
    blocking_dir = tmp_path / "blocking"
    blocking_dir.mkdir()
    for shot_id, arc in (("SHOT-001", 2.0), ("SHOT-002", 0.0)):
        (blocking_dir / f"{shot_id}.json").write_text(
            json.dumps(_sheet(shot_id, arc_sec=arc)), encoding="utf-8")
    inputs = tmp_path / "shots.json"
    inputs.write_text("{}", encoding="utf-8")
    shots = [
        {"id": "SHOT-001", "start_frame": 0, "edit_frames": 168, "pixel_frames": 175,
         "trim_in_frame": 0, "trim_out_frame": 168, "end_frame_position": 167, "error_ms": 0.0},
        {"id": "SHOT-002", "start_frame": 168, "edit_frames": 120, "pixel_frames": 175,
         "trim_in_frame": 0, "trim_out_frame": 120, "end_frame_position": 119, "error_ms": 0.0},
    ]
    lock_path = tmp_path / "timeline_lock.json"
    lock = write_lock(str(lock_path), shots, [str(inputs)], {"test": True})

    out = tmp_path / "routes.json"
    assert shot_router.main(["--blocking", str(blocking_dir), "--lock", str(lock_path), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["lock_sha256"] == lock["input_sha256"]
    assert list(payload["routes"]) == ["SHOT-001", "SHOT-002"]
    assert payload["routes"]["SHOT-001"]["route"] == "KFI"
    assert payload["routes"]["SHOT-001"]["h3_mode"] == "FL2VA"


def test_existing_route_shot_unchanged_by_x04():
    # guard: X-04 adds code only; the plain rule path still gives SE with the fallback reason
    res = route_shot({"kind": "acting", "duration_sec": 4.0, "needs_end_pose": False,
                      "cast_count": 1, "multi_arm": False, "arc_sec": 0.0})
    assert res["route"] == "SE"
    assert res["reasons"][-1] == "S not approved: SE fallback"
