import json
import math
import os
import re

import shot_router

SCHEMA = "blocking/1"

KINDS = shot_router._VALID_KINDS

_POSES = ("standing", "seated", "kneeling", "lying", "walking", "flying")
_FACINGS = ("left", "right", "camera", "away")
_CAMERA_MODES = ("fixed", "move")
_CAMERA_FRAMINGS = ("wide", "medium", "close", "extreme_close")
_LIGHT_DIRS = ("left", "right", "top", "back", "front")
_SIDES = ("left", "right", "top", "bottom")
_CUT_TO_NEXT = ("match", "cut")


class BlockingError(ValueError):
    pass


def _is_str(value):
    return isinstance(value, str)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _in_range(value, low, high):
    return _is_number(value) and low <= value <= high


def _validate_pose(pose, shot_id, problems):
    if not isinstance(pose, dict):
        problems.append("%s: BLK-S04 pose must be an object" % shot_id)
        return
    for key in ("facing", "pose", "mouth_moves"):
        if key not in pose:
            problems.append("%s: BLK-S04 pose missing %s" % (shot_id, key))
    for key in ("x", "y", "scale"):
        if key not in pose:
            problems.append("%s: BLK-S04 pose missing %s" % (shot_id, key))
        elif not _in_range(pose[key], -0.5, 1.5) and key in ("x", "y"):
            problems.append("%s: BLK-S04 pose %s out of range" % (shot_id, key))
        elif key == "scale" and not _in_range(pose[key], 0.05, 1.2):
            problems.append("%s: BLK-S04 pose scale out of range" % shot_id)
    if "facing" in pose and pose["facing"] not in _FACINGS:
        problems.append("%s: BLK-S04 bad facing" % shot_id)
    if "pose" in pose and pose["pose"] not in _POSES:
        problems.append("%s: BLK-S04 bad pose value" % shot_id)
    for key in ("mouth_moves",):
        if key in pose and not isinstance(pose[key], bool):
            problems.append("%s: BLK-S04 pose %s must be bool" % (shot_id, key))


def _validate_pace(member, shot_id, problems):
    if "pace" in member:
        pace = member.get("pace")
        if pace not in ("walk", "slow"):
            problems.append("%s: BLK-S19 bad pace %s" % (shot_id, pace))


def _validate_turn(member, shot_id, problems):
    if "turn" in member:
        turn = member.get("turn")
        if not isinstance(turn, dict):
            problems.append("%s: BLK-S18 bad turn %s" % (shot_id, turn))
            return
        deg = turn.get("deg")
        sec = turn.get("sec")
        deg_ok = (
            isinstance(deg, int)
            and not isinstance(deg, bool)
            and deg != 0
            and -360 <= deg <= 360
        )
        sec_ok = (
            _is_number(sec)
            and math.isfinite(sec)
            and sec > 0
        )
        if not deg_ok or not sec_ok:
            problems.append("%s: BLK-S18 bad turn %s" % (shot_id, turn))


def pace_of(cast_member):
    if not isinstance(cast_member, dict):
        return "walk"
    pace = cast_member.get("pace")
    if pace in ("walk", "slow"):
        return pace
    return "walk"


def validate(sheet):
    problems = []
    shot_id = "UNKNOWN"
    try:
        if not isinstance(sheet, dict):
            problems.append("%s: BLK-S01 sheet must be an object" % shot_id)
            return problems
        shot_id = sheet.get("shot_id", "UNKNOWN")
        if not isinstance(shot_id, str) or not re.match(r"^SHOT-\d{3}$", shot_id):
            shot_id = "UNKNOWN"
            problems.append("UNKNOWN: BLK-S01 bad shot_id")
        if sheet.get("schema") != SCHEMA:
            problems.append("%s: BLK-S02 schema must be %s" % (shot_id, SCHEMA))
        if "plate_id" not in sheet:
            problems.append("%s: BLK-S03 missing plate_id" % shot_id)
        elif not isinstance(sheet["plate_id"], str) or not re.match(r"^PLATE-[A-Za-z0-9_-]+$", sheet["plate_id"]):
            problems.append("%s: BLK-S03 bad plate_id" % shot_id)
        if "location_id" not in sheet:
            problems.append("%s: BLK-S04 missing location_id" % shot_id)
        if "kind" not in sheet:
            problems.append("%s: BLK-S05 missing kind" % shot_id)
        elif sheet["kind"] not in KINDS:
            problems.append("%s: BLK-S05 bad kind" % shot_id)
        camera = sheet.get("camera")
        if not isinstance(camera, dict):
            problems.append("%s: BLK-S06 camera must be an object" % shot_id)
        else:
            if camera.get("mode") not in _CAMERA_MODES:
                problems.append("%s: BLK-S06 bad camera mode" % shot_id)
            if camera.get("framing") not in _CAMERA_FRAMINGS:
                problems.append("%s: BLK-S06 bad camera framing" % shot_id)
            if "move" not in camera:
                problems.append("%s: BLK-S06 camera missing move" % shot_id)
            elif camera.get("move") is not None and not isinstance(camera.get("move"), str):
                problems.append("%s: BLK-S06 bad camera move" % shot_id)
        light = sheet.get("light")
        if not isinstance(light, dict):
            problems.append("%s: BLK-S07 light must be an object" % shot_id)
        else:
            if light.get("key_dir") not in _LIGHT_DIRS:
                problems.append("%s: BLK-S07 bad light key_dir" % shot_id)
            if not _is_str(light.get("palette_id")):
                problems.append("%s: BLK-S07 bad light palette_id" % shot_id)
        props = sheet.get("props")
        if not isinstance(props, list):
            problems.append("%s: BLK-S08 props must be a list" % shot_id)
        else:
            for prop in props:
                if not isinstance(prop, dict):
                    problems.append("%s: BLK-S08 prop must be an object" % shot_id)
                    continue
                for key in ("id", "class", "x", "y"):
                    if key not in prop:
                        problems.append("%s: BLK-S08 prop missing %s" % (shot_id, key))
                if not _in_range(prop.get("x", 0), -0.5, 1.5):
                    problems.append("%s: BLK-S08 prop x out of range" % shot_id)
                if not _in_range(prop.get("y", 0), -0.5, 1.5):
                    problems.append("%s: BLK-S08 prop y out of range" % shot_id)
                visible = prop.get("visible")
                if not isinstance(visible, list) or not all(v in ("A", "B") for v in visible):
                    problems.append("%s: BLK-S08 prop visible must be [A|B]" % shot_id)
        entries = sheet.get("entries")
        cast_ids = set()
        if isinstance(sheet.get("cast"), list):
            for member in sheet.get("cast", []):
                if isinstance(member, dict) and _is_str(member.get("id")):
                    cast_ids.add(member.get("id"))
        if not isinstance(entries, list):
            problems.append("%s: BLK-S09 entries must be a list" % shot_id)
        else:
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("side") not in _SIDES:
                    problems.append("%s: BLK-S09 bad entry" % shot_id)
                else:
                    char = entry.get("char")
                    if not _is_str(char) or char not in cast_ids:
                        problems.append("%s: BLK-S09 entry bad char %s" % (shot_id, char))
        exits = sheet.get("exits")
        if not isinstance(exits, list):
            problems.append("%s: BLK-S10 exits must be a list" % shot_id)
        else:
            for exit_item in exits:
                if not isinstance(exit_item, dict) or exit_item.get("side") not in _SIDES:
                    problems.append("%s: BLK-S10 bad exit" % shot_id)
                else:
                    char = exit_item.get("char")
                    if not _is_str(char) or char not in cast_ids:
                        problems.append("%s: BLK-S10 exit bad char %s" % (shot_id, char))
        sound_cues = sheet.get("sound_cues")
        if not isinstance(sound_cues, list):
            problems.append("%s: BLK-S11 sound_cues must be a list" % shot_id)
        else:
            for cue in sound_cues:
                if not isinstance(cue, dict) or not _is_number(cue.get("t")) or not _is_str(cue.get("text")):
                    problems.append("%s: BLK-S11 bad sound cue" % shot_id)
        if not _is_number(sheet.get("arc_sec")) or sheet["arc_sec"] < 0:
            problems.append("%s: BLK-S12 arc_sec must be >= 0" % shot_id)
        if not _is_number(sheet.get("writer_seconds")) or sheet["writer_seconds"] <= 0:
            problems.append("%s: BLK-S13 writer_seconds must be > 0" % shot_id)
        if sheet.get("cut_to_next") not in _CUT_TO_NEXT:
            problems.append("%s: BLK-S14 bad cut_to_next" % shot_id)
        source_refs = sheet.get("source_refs")
        if not isinstance(source_refs, list) or not all(_is_str(r) for r in source_refs):
            problems.append("%s: BLK-S15 source_refs must be [str]" % shot_id)
        cast = sheet.get("cast")
        if not isinstance(cast, list):
            problems.append("%s: BLK-S16 cast must be a list" % shot_id)
        else:
            seen_ids = set()
            for member in cast:
                if not isinstance(member, dict):
                    problems.append("%s: BLK-S16 cast member must be an object" % shot_id)
                    continue
                for key in ("id", "name", "source_refs", "start", "end"):
                    if key not in member:
                        problems.append("%s: BLK-S16 cast missing %s" % (shot_id, key))
                if not isinstance(member.get("speaks"), bool):
                    problems.append("%s: BLK-S16 cast speaks must be bool" % shot_id)
                arms = member.get("arms")
                if isinstance(arms, bool) or not isinstance(arms, int) or arms < 2:
                    problems.append("%s: BLK-S16 cast arms must be >= 2" % shot_id)
                if not isinstance(member.get("source_refs"), list) or not all(
                    _is_str(r) for r in member.get("source_refs", [])
                ):
                    problems.append("%s: BLK-S16 cast source_refs must be [str]" % shot_id)
                member_id = member.get("id")
                if _is_str(member_id):
                    if member_id in seen_ids:
                        problems.append("%s: BLK-S16 duplicate cast id %s" % (shot_id, member_id))
                    seen_ids.add(member_id)
                _validate_pose(member.get("start"), shot_id, problems)
                _validate_pose(member.get("end"), shot_id, problems)
                _validate_pace(member, shot_id, problems)
                _validate_turn(member, shot_id, problems)
    except Exception:
        problems.append("%s: BLK-S99 internal validation error" % shot_id)
    return problems


def load_sheet(path):
    with open(path, "r", encoding="utf-8") as handle:
        sheet = json.load(handle)
    file_id = os.path.splitext(os.path.basename(path))[0]
    sheet_id = sheet.get("shot_id") if isinstance(sheet, dict) else None
    if sheet_id != file_id:
        raise BlockingError(["%s: BLK-S17 shot_id %s does not match file name %s" % (sheet_id, sheet_id, file_id)])
    problems = validate(sheet)
    if problems:
        raise BlockingError(problems)
    return sheet


def load_reel(directory, shot_ids):
    reel = {}
    for shot_id in shot_ids:
        path = os.path.join(directory, shot_id + ".json")
        reel[shot_id] = load_sheet(path)
    return reel


def distance(cast_member):
    start = cast_member["start"]
    end = cast_member["end"]
    dx = (end["x"] - start["x"]) * 9 / 16
    dy = end["y"] - start["y"]
    return math.hypot(dx, dy) + abs(end["scale"] - start["scale"])


def is_moving(cast_member):
    if distance(cast_member) > 0.02:
        return True
    start = cast_member["start"]
    end = cast_member["end"]
    for key in ("pose", "facing"):
        if start.get(key) != end.get(key):
            return True
    return False


def router_features(sheet, edit_frames, fps=24):
    cast = sheet.get("cast", [])
    moving = [c for c in cast if is_moving(c)]
    return {
        "kind": sheet.get("kind"),
        "duration_sec": edit_frames / fps,
        "needs_end_pose": any(is_moving(c) for c in cast),
        "cast_count": sum(1 for c in cast if is_moving(c)),
        "multi_arm": any(c.get("arms", 0) > 2 for c in cast),
        "arc_sec": sheet.get("arc_sec", 0),
    }


def prompt_args(sheet):
    cast = sheet.get("cast", [])
    props = sheet.get("props", [])
    names = [c.get("name") for c in cast]
    on_screen = [
        c.get("name")
        for c in cast
        if 0 <= c.get("start", {}).get("x", 0) <= 1 or 0 <= c.get("end", {}).get("x", 0) <= 1
    ]
    speaking = [c.get("name") for c in cast if c.get("speaks")]
    sound_cues = [cue.get("text") for cue in sheet.get("sound_cues", [])]
    visible = list(names) + [prop.get("class") for prop in props]
    return {
        "cast": names,
        "on_screen": on_screen,
        "speaking": speaking,
        "sound_cues": sound_cues,
        "visible": visible,
    }


def image_expect(sheet, edit_frames, fps=24):
    cast = sheet.get("cast", [])
    on_screen_both = [
        c for c in cast
        if 0 <= c.get("start", {}).get("x", 0) <= 1 and 0 <= c.get("end", {}).get("x", 0) <= 1
    ]
    posture = {}
    for c in cast:
        start_pose = c.get("start", {}).get("pose")
        end_pose = c.get("end", {}).get("pose")
        posture[c.get("id")] = (
            start_pose if start_pose in ("standing", "seated") else None,
            end_pose if end_pose in ("standing", "seated") else None,
        )
    return {
        "required_cast_count": len(on_screen_both),
        "entry_exit_allowed": bool(sheet.get("entries") or sheet.get("exits")),
        "arms": {c.get("id"): c.get("arms") for c in cast},
        "posture": posture,
        "displacement": {c.get("id"): distance(c) for c in cast},
        "seconds": edit_frames / fps,
    }


def known_classes(sheet):
    """Classes the clip reviewer may count for this shot: 'person' while the sheet has any cast member, plus its props.

    Every cast member is a person, so removing the last cast member removes 'person' from the allowed set.
    """
    classes = set()
    if sheet.get("cast"):
        classes.add("person")
    for prop in sheet.get("props", []):
        classes.add(prop.get("class"))
    return classes


def change_list(sheet):
    changes = []
    for c in sheet.get("cast", []):
        if not is_moving(c):
            continue
        name = c.get("name")
        start = c.get("start", {})
        end = c.get("end", {})
        if distance(c) > 0.02:
            changes.append(
                "%s: move from (%.2f,%.2f) to (%.2f,%.2f)"
                % (name, start.get("x", 0), start.get("y", 0), end.get("x", 0), end.get("y", 0))
            )
        if start.get("pose") != end.get("pose"):
            changes.append("%s: %s -> %s" % (name, start.get("pose"), end.get("pose")))
        turn = c.get("turn")
        turn_line = None
        if isinstance(turn, dict):
            deg = turn.get("deg")
            sec = turn.get("sec")
            deg_ok = (
                isinstance(deg, int)
                and not isinstance(deg, bool)
                and deg != 0
                and -360 <= deg <= 360
            )
            sec_ok = (
                _is_number(sec)
                and math.isfinite(sec)
                and sec > 0
            )
            if deg_ok and sec_ok:
                direction = "right" if deg > 0 else "left"
                turn_line = "%s: turn %d degrees %s" % (name, abs(deg), direction)
        if turn_line is not None:
            changes.append(turn_line)
        elif start.get("facing") != end.get("facing"):
            changes.append("%s: turn to face %s" % (name, end.get("facing")))
        if start.get("mouth_moves") != end.get("mouth_moves"):
            if end.get("mouth_moves"):
                changes.append("%s: mouth open" % name)
            else:
                changes.append("%s: mouth closed" % name)
    for prop in sheet.get("props", []):
        visible = prop.get("visible", [])
        if "A" in visible and "B" not in visible:
            changes.append("%s: disappears" % prop.get("class"))
        elif "B" in visible and "A" not in visible:
            changes.append("%s: appears" % prop.get("class"))
    changes.append("keep everything else exactly the same")
    return changes
