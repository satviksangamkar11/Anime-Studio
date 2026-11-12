import copy
import json
import sys

try:
    from timeline_lock_io import frames_for, load_lock
except ImportError:          # imported as a package module from outside the director folder (h3 tests)
    from director.timeline_lock_io import frames_for, load_lock


ROUTES = ("S", "REF_S", "SE", "REF_SE", "SOFT_SE", "KFI", "POST")

# one table from route to h3 mode (the third-router issue, h3/router.py)
# REF_SE added: the card table lacked it and route_shot falls back to REF_SE when S is not allowed
H3_MODE = {
    "SE": "FL2VA",
    "REF_SE": "Ref2VA",
    "SOFT_SE": "FL2VA",
    "KFI": "FL2VA",
    "REF_S": "Ref2VA",
    "S": "I2VA",
    "POST": None,
}


class RouterError(ValueError):
    pass


_VALID_KINDS = ("acting", "body_action", "camera_move", "crowd", "close_up", "seam")


def _validate(features):
    if not isinstance(features, dict):
        raise RouterError("features")
    required = {
        "kind": str,
        "duration_sec": (int, float),
        "needs_end_pose": bool,
        "cast_count": int,
        "multi_arm": bool,
        "arc_sec": (int, float),
    }
    for key, expected_type in required.items():
        if key not in features:
            raise RouterError(key)
        value = features[key]
        if isinstance(value, bool) and expected_type is not bool:
            raise RouterError(key)
        if not isinstance(value, expected_type):
            raise RouterError(key)
    if features["kind"] not in _VALID_KINDS:
        raise RouterError("kind")
    if not features["duration_sec"] > 0:
        raise RouterError("duration_sec")
    if features["cast_count"] < 0:
        raise RouterError("cast_count")
    if not features["arc_sec"] >= 0:
        raise RouterError("arc_sec")


_ROUTE_TABLE = {
    "S": {
        "route": "S",
        "image_prompt_type": "S",
        "input_video_strength": None,
        "keyframes": ["A"],
        "gpu": True,
        "est_units": 1.1,
        "requires_owner_flag": True,
        "h3_mode": "I2VA",
        "reasons": ["start frame only: no end-frame lock"],
    },
    "REF_S": {
        "route": "REF_S",
        "image_prompt_type": "S",
        "input_video_strength": None,
        "keyframes": ["A", "refs"],
        "gpu": True,
        "est_units": 1.4,
        "requires_owner_flag": True,
        "h3_mode": "Ref2VA",
        "reasons": ["start frame plus face/body references for identity or extra arms"],
    },
    "SE": {
        "route": "SE",
        "image_prompt_type": "SE",
        "input_video_strength": None,
        "keyframes": ["A", "B"],
        "gpu": True,
        "est_units": 1.2,
        "requires_owner_flag": False,
        "h3_mode": "FL2VA",
        "reasons": ["start and end frame locked (default image mode)"],
    },
    "REF_SE": {
        "route": "REF_SE",
        "image_prompt_type": "SE",
        "input_video_strength": None,
        "keyframes": ["A", "B", "refs"],
        "gpu": True,
        "est_units": 1.4,
        "requires_owner_flag": False,
        "h3_mode": "Ref2VA",
        "reasons": ["start and end frame plus face/body references"],
    },
    "SOFT_SE": {
        "route": "SOFT_SE",
        "image_prompt_type": "SE",
        "input_video_strength": 0.6,
        "keyframes": ["A", "B"],
        "gpu": True,
        "est_units": 1.2,
        "requires_owner_flag": False,
        "h3_mode": "FL2VA",
        "reasons": ["end frame softened to 0.6 and placed at the cut"],
    },
    "KFI": {
        "route": "KFI",
        "image_prompt_type": "SE",
        "input_video_strength": 0.65,
        "keyframes": ["A", "MID", "B"],
        "gpu": True,
        "est_units": 1.4,
        "requires_owner_flag": False,
        "h3_mode": "FL2VA",
        "reasons": ["middle keyframe for a movement longer than 1.5 s"],
    },
    "POST": {
        "route": "POST",
        "image_prompt_type": None,
        "input_video_strength": None,
        "keyframes": ["A", "plate"],
        "gpu": False,
        "est_units": 0.0,
        "requires_owner_flag": False,
        "h3_mode": None,
        "reasons": ["no video render: 2.5D hold, pan or shake"],
    },
}


def route_shot(features, allow_s=None):
    allow_s = s_allowed() if allow_s is None else allow_s
    _validate(features)
    kind = features["kind"]
    needs_end_pose = features["needs_end_pose"]
    arc_sec = features["arc_sec"]
    cast_count = features["cast_count"]
    multi_arm = features["multi_arm"]

    if kind == "camera_move":
        route = "POST"
    elif kind == "crowd" or cast_count > 3:
        result = copy.deepcopy(_ROUTE_TABLE["POST"])
        if cast_count > 3:
            result["reasons"].append("more than 3 moving people")
        return result
    elif needs_end_pose and not allow_s and arc_sec > 1.5:   # M-32: with S on, an exact end pose is a per-shot SE override
        route = "KFI"
    elif needs_end_pose and not allow_s:
        route = "SOFT_SE"
    elif kind == "close_up" or multi_arm:
        route = "REF_S"
    else:
        route = "S"

    fallback = False
    if not allow_s and route == "S":
        route = "SE"
        fallback = True
    elif not allow_s and route == "REF_S":
        route = "REF_SE"
        fallback = True

    result = copy.deepcopy(_ROUTE_TABLE[route])
    if fallback:
        result["reasons"].append("S not approved: SE fallback")
    return result


def plan_reel(shots, allow_s=None):
    if not isinstance(shots, list):
        raise RouterError("shots")
    seen_ids = set()
    routes = {}
    total_est_units = 0.0
    keyframe_count = 0
    gpu_shots = 0
    needs_owner_flag = []
    image_names = ("A", "B", "MID", "plate")
    for i, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise RouterError(f"shot #{i}: not a dict")
        if "id" not in shot:
            raise RouterError(f"shot #{i}: missing id")
        if "features" not in shot:
            raise RouterError(f"shot #{i}: missing features")
        shot_id = shot["id"]
        if not isinstance(shot_id, str):
            raise RouterError("shot #%d: id must be a str" % i)
        if shot_id in seen_ids:
            raise RouterError(shot_id)
        seen_ids.add(shot_id)
        result = route_shot(shot["features"], allow_s=allow_s)
        routes[shot_id] = result
        total_est_units += result["est_units"]
        for name in result["keyframes"]:
            if name in image_names:
                keyframe_count += 1
        if result["gpu"]:
            gpu_shots += 1
        if result["requires_owner_flag"]:
            needs_owner_flag.append(shot_id)
    total_est_units = round(total_est_units, 2)
    return {
        "routes": routes,
        "total_est_units": total_est_units,
        "keyframe_count": keyframe_count,
        "gpu_shots": gpu_shots,
        "needs_owner_flag": needs_owner_flag,
    }


def s_allowed(env=None):
    """Gate for start-only (S), M-32: on by default; only SHOT_MODE_S_ALLOW=0 switches it off (same rule as h3/shot_mode.py)."""
    import os
    return (os.environ if env is None else env).get("SHOT_MODE_S_ALLOW") != "0"


def plan_from_blocking(sheets, lock, allow_s=None):
    allow_s = s_allowed() if allow_s is None else allow_s
    # blocking is imported here, not at top: blocking.py imports shot_router at load time
    import blocking

    if not isinstance(sheets, dict) or not isinstance(lock, dict):
        raise RouterError("sheets and lock must be dicts")
    lock_ids = [shot.get("id") for shot in lock.get("shots", [])]
    missing = [shot_id for shot_id in lock_ids if shot_id not in sheets]
    if missing:
        raise RouterError(f"lock shot {missing[0]} has no blocking sheet")
    extra = [shot_id for shot_id in sheets if shot_id not in lock_ids]
    if extra:
        raise RouterError(f"blocking sheet {extra[0]} is not a lock shot")
    routes = {}
    for shot_id in lock_ids:
        features = blocking.router_features(sheets[shot_id], frames_for(lock, shot_id))
        if sheets[shot_id].get("chain_from"):   # M-03: a continuation starts from the previous last frame: start-only S, no B
            if not allow_s:
                raise RouterError(f"{shot_id}: chain_from needs the start-only route S (SHOT_MODE_S_ALLOW=1 not set)")
            result = copy.deepcopy(_ROUTE_TABLE["S"])
            result["reasons"].append("chain_from: continues from the previous clip's last kept frame")
        elif sheets[shot_id].get("route") in _ROUTE_TABLE:   # M-32: an explicit per-shot route (e.g. "SE") wins over the default
            result = copy.deepcopy(_ROUTE_TABLE[sheets[shot_id]["route"]])
        else:
            result = route_shot(features, allow_s=allow_s)
        result["h3_mode"] = H3_MODE[result["route"]]
        routes[shot_id] = result
    return routes


def main(argv=None):
    import argparse
    import blocking

    parser = argparse.ArgumentParser(description="Route each lock shot from its blocking sheet.")
    parser.add_argument("--blocking", required=True, help="folder with <SHOT-ID>.json blocking sheets")
    parser.add_argument("--lock", required=True, help="timeline lock json")
    parser.add_argument("--out", required=True, help="routes.json to write")
    args = parser.parse_args(argv)

    lock = load_lock(args.lock)
    shot_ids = [shot["id"] for shot in lock["shots"]]
    sheets = blocking.load_reel(args.blocking, shot_ids)
    routes = plan_from_blocking(sheets, lock, allow_s=s_allowed())
    payload = {"lock_sha256": lock["input_sha256"], "routes": routes}
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
