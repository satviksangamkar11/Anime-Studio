import os
import sys
import math

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
for _p in (_HERE, os.path.join(_ROOT, "h3"), _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import blocking  # noqa: E402
import shot_router  # noqa: E402
import prompt_hygiene  # noqa: E402

MAX_SPEED_H = 0.5  # ponytail: uncalibrated
SLOW_SPEED_H = 0.25  # ponytail: uncalibrated
TURN_90_MIN_SEC = 1.0  # ponytail: uncalibrated
TURN_180_MIN_SEC = 2.0  # ponytail: uncalibrated
POSE_CHANGE_MIN_SEC = 1.0  # ponytail: uncalibrated
CONT_TOL = 0.05  # ponytail: uncalibrated
MAX_MOVING = 3  # ponytail: uncalibrated


def _shot_id(sheet):
    if isinstance(sheet, dict) and isinstance(sheet.get("shot_id"), str):
        return sheet["shot_id"]
    return "SHOT-?"


def _seconds(sheet, lock, fps):
    shot_id = _shot_id(sheet)
    if lock is not None and isinstance(lock, dict):
        shots = lock.get("shots")
        if isinstance(shots, list):
            for shot in shots:
                if isinstance(shot, dict) and shot.get("id") == shot_id:
                    edit_frames = shot.get("edit_frames")
                    if _is_number(edit_frames):
                        lock_fps = lock.get("fps", fps)
                        if _is_number(lock_fps) and lock_fps != 0:
                            return edit_frames / lock_fps
    writer = sheet.get("writer_seconds") if isinstance(sheet, dict) else None
    if _is_number(writer):
        return writer
    return 0.0


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _has_geometry(member):
    if not isinstance(member, dict):
        return False
    start = member.get("start")
    end = member.get("end")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return False
    for key in ("x", "y", "scale"):
        for pose in (start, end):
            value = pose.get(key)
            if not _is_number(value) or not math.isfinite(value):
                return False
    return True


def _valid_turn(turn):
    return (isinstance(turn, dict)
            and isinstance(turn.get('deg'), int)
            and not isinstance(turn.get('deg'), bool)
            and turn.get('deg') != 0
            and -360 <= turn.get('deg') <= 360
            and _is_number(turn.get('sec'))
            and turn.get('sec') > 0)


def _moving(member):
    if not _has_geometry(member):
        return False
    return blocking.distance(member) > 0.02


def lint(sheets, lock=None, fps=24):
    problems = []
    if not isinstance(sheets, list):
        problems.append("LINT: L01 sheets must be a list")
        return problems
    for sheet in sheets:
        if not isinstance(sheet, dict):
            problems.append("LINT: L01 sheet #%d is not a dict" % sheets.index(sheet))
            continue
        shot_id = _shot_id(sheet)

        for p in blocking.validate(sheet):
            if p.startswith(shot_id + ": "):
                p = p[len(shot_id) + 2:]
            problems.append("%s: L01 %s" % (shot_id, p))

        cast = sheet.get("cast")
        if not isinstance(cast, list):
            cast = []
        seconds = _seconds(sheet, lock, fps)

        moving_count = 0
        for member in cast:
            if not _has_geometry(member):
                continue
            if _moving(member):
                moving_count += 1
                dist = blocking.distance(member)
                if seconds > 0:
                    limit = SLOW_SPEED_H if blocking.pace_of(member) == "slow" else MAX_SPEED_H
                    if dist / seconds > limit:
                        n_frames = int(round(dist / limit * fps))
                        problems.append("%s: L03 end not reachable in %d frames" % (shot_id, n_frames))
                else:
                    problems.append("%s: L03 shot has no duration for %s" % (shot_id, member.get("id")))
            start = member.get("start", {})
            end = member.get("end", {})
            if start.get("pose") != end.get("pose"):
                if seconds < POSE_CHANGE_MIN_SEC:
                    if seconds >= 0.5:
                        code = "L03"
                    else:
                        code = "L02"
                    problems.append("%s: %s pose change too fast" % (shot_id, code))

        if moving_count > MAX_MOVING:
            problems.append("%s: L06 too many moving cast (%d)" % (shot_id, moving_count))

        for i in range(len(cast)):
            a = cast[i]
            if not _has_geometry(a):
                continue
            if not _moving(a):
                continue
            for j in range(i + 1, len(cast)):
                b = cast[j]
                if not _has_geometry(b):
                    continue
                if not _moving(b):
                    continue
                ax = a.get("start", {}).get("x", 0)
                ay = a.get("start", {}).get("y", 0)
                bx = b.get("start", {}).get("x", 0)
                by = b.get("start", {}).get("y", 0)
                aex = a.get("end", {}).get("x", 0)
                aey = a.get("end", {}).get("y", 0)
                bex = b.get("end", {}).get("x", 0)
                bey = b.get("end", {}).get("y", 0)
                if _sign(ax - bx) != _sign(aex - bex):
                    problems.append("%s: L04 crossing cast %s and %s" % (shot_id, a.get("id"), b.get("id")))

        for member in cast:
            if not _has_geometry(member):
                continue
            speaks = member.get("speaks")
            mouth_start = member.get("start", {}).get("mouth_moves", False)
            mouth_end = member.get("end", {}).get("mouth_moves", False)
            if speaks and not mouth_start and not mouth_end:
                problems.append("%s: L07 speaks but mouth_moves false at start and end" % shot_id)
            if not speaks and (mouth_start or mouth_end):
                problems.append("%s: L07 mouth_moves without speaks" % shot_id)

        sound_cues = sheet.get("sound_cues")
        if isinstance(sound_cues, list):
            visible = []
            for member in cast:
                if isinstance(member, dict):
                    name = member.get("name")
                    if isinstance(name, str):
                        visible.append(name)
            for prop in sheet.get("props", []):
                if isinstance(prop, dict):
                    prop_class = prop.get("class")
                    if isinstance(prop_class, str):
                        visible.append(prop_class)
            for cue in sound_cues:
                if isinstance(cue, dict):
                    text = cue.get("text")
                    if isinstance(text, str):
                        try:
                            prompt_hygiene.check_sound_cue(text, visible=visible)
                        except prompt_hygiene.PromptError:
                            problems.append("%s: L08 bad sound cue: %s" % (shot_id, text))

        for entry in sheet.get("entries", []):
            if not isinstance(entry, dict):
                continue
            char = entry.get("char")
            for member in cast:
                if not _has_geometry(member):
                    continue
                if member.get("id") == char or member.get("name") == char:
                    sx = member.get("start", {}).get("x", 0)
                    if 0 <= sx <= 1:
                        problems.append("%s: L09 entry char %s starts on screen" % (shot_id, char))
        for exit_item in sheet.get("exits", []):
            if not isinstance(exit_item, dict):
                continue
            char = exit_item.get("char")
            for member in cast:
                if not _has_geometry(member):
                    continue
                if member.get("id") == char or member.get("name") == char:
                    ex = member.get("end", {}).get("x", 0)
                    if 0 <= ex <= 1:
                        problems.append("%s: L09 exit char %s ends on screen" % (shot_id, char))

        for member in cast:
            if not _has_geometry(member):
                continue
            start = member.get("start")
            end = member.get("end")
            turn = member.get("turn")
            has_turn = _valid_turn(turn)
            if start.get("facing") != end.get("facing") and not has_turn:
                problems.append("%s: L10 facing changes without a turn record for %s" % (shot_id, member.get("id")))
            if has_turn:
                abs_deg = abs(turn['deg'])
                min_sec = TURN_180_MIN_SEC if abs_deg >= 180 else (TURN_90_MIN_SEC if abs_deg >= 90 else 0.0)
                if min_sec > 0 and turn['sec'] < min_sec:
                    problems.append("%s: L10 turn of %d degrees needs at least %s s for %s"
                                    % (shot_id, turn['deg'], min_sec, member.get("id")))
                if turn['sec'] > seconds:
                    problems.append("%s: L10 turn longer than the shot for %s" % (shot_id, member.get("id")))

    for i in range(len(sheets) - 1):
        a = sheets[i]
        b = sheets[i + 1]
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        if a.get("cut_to_next") == "cut":
            continue
        a_id = _shot_id(a)
        b_id = _shot_id(b)
        a_cast = a.get("cast", [])
        b_cast = b.get("cast", [])
        if not isinstance(a_cast, list):
            a_cast = []
        if not isinstance(b_cast, list):
            b_cast = []
        for am in a_cast:
            if not isinstance(am, dict):
                continue
            aid = am.get("id")
            for bm in b_cast:
                if not isinstance(bm, dict):
                    continue
                if bm.get("id") != aid:
                    continue
                if not _has_geometry(am) or not _has_geometry(bm):
                    continue
                a_end = am.get("end", {})
                b_start = bm.get("start", {})
                dx = abs((b_start.get("x", 0) or 0) - (a_end.get("x", 0) or 0))
                dy = abs((b_start.get("y", 0) or 0) - (a_end.get("y", 0) or 0))
                if dx > CONT_TOL or dy > CONT_TOL:
                    problems.append("%s: L05 continuity break vs %s" % (a_id, b_id))
                    continue
                if a_end.get("pose") != b_start.get("pose"):
                    problems.append("%s: L05 continuity break vs %s" % (a_id, b_id))
                    continue
                if a_end.get("facing") != b_start.get("facing"):
                    problems.append("%s: L05 continuity break vs %s" % (a_id, b_id))

    return problems


def _sign(value):
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def main(argv=None):
    import argparse

    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="lint blocking sheets")
    parser.add_argument("blocking_dir")
    parser.add_argument("--lock", default=None)
    args = parser.parse_args(argv)

    lock = None
    if args.lock:
        import json
        with open(args.lock, "r", encoding="utf-8") as handle:
            lock = json.load(handle)

    sheets = []
    for name in sorted(os.listdir(args.blocking_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(args.blocking_dir, name)
        with open(path, "r", encoding="utf-8") as handle:
            sheets.append(json.load(handle))

    problems = lint(sheets, lock=lock)
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
