"""J9c script_inspect: hook check and pacing check on a reel script."""

import json
import os
import sys

SUPPORTED_LANGS = ("en", "hi", "mr")

# script_hook and script_pacing sit next to this file (O18): make the folder importable from any cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def from_pack(rows, lang):
    """Turn pack rows (audio_and_dialogue_track form) into script shots for one language."""
    from pack_validator import _range

    shots = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or "id" not in row:
            raise ValueError("row %d: missing id" % index)
        row_id = row["id"]
        if "editorial_duration_sec" not in row:
            raise ValueError("row %s: missing editorial_duration_sec" % row_id)
        if "audio_and_dialogue_track" not in row:
            raise ValueError("row %s: missing audio_and_dialogue_track" % row_id)
        directives = row.get("per_second_directives") or []
        events = []
        for i, d in enumerate(directives):
            if not isinstance(d, dict):
                raise ValueError("row %s: directive %d has no usable t0" % (row_id, i))
            if d.get("action_pose_expression"):
                t0 = d.get("t0")
                if t0 is None or isinstance(t0, bool) or not isinstance(t0, (int, float)):
                    raise ValueError("row %s: directive %d has no usable t0" % (row_id, i))
                events.append({"t": float(t0)})
        action = directives[0].get("action_pose_expression", "") if directives else ""
        track = row["audio_and_dialogue_track"]
        if not isinstance(track, dict):
            raise ValueError("row %s: audio_and_dialogue_track has a bad type" % row_id)
        narration_by_lang = track.get("narration_by_lang")
        if narration_by_lang is not None and not isinstance(narration_by_lang, dict):
            raise ValueError("row %s: audio_and_dialogue_track has a bad type" % row_id)
        dialogue_by_lang = track.get("dialogue_by_lang")
        if dialogue_by_lang is not None and not isinstance(dialogue_by_lang, dict):
            raise ValueError("row %s: audio_and_dialogue_track has a bad type" % row_id)
        dialogue = (track.get("dialogue_by_lang") or {}).get(lang)
        if dialogue is not None and not isinstance(dialogue, list):
            raise ValueError("row %s: audio_and_dialogue_track has a bad type" % row_id)
        items = []
        narration = (track.get("narration_by_lang") or {}).get(lang)
        if narration:
            items.append(narration)
        items.extend((track.get("dialogue_by_lang") or {}).get(lang) or [])
        lines = []
        for item in items:
            if not isinstance(item, dict) or "text" not in item or "time_range" not in item:
                raise ValueError("row %s: item without text or time_range" % row_id)
            rng = _range(item.get("time_range"))
            if rng is None:
                raise ValueError("row %s: bad time_range %r" % (row_id, item.get("time_range")))
            lines.append({"start_s": rng[0], "end_s": rng[1], "text": item["text"]})
        lines.sort(key=lambda line: line["start_s"])
        shots.append({
            "id": row_id,
            "seconds": float(row["editorial_duration_sec"]),
            "action": action,
            "events": events,
            "lines": lines,
            **({"voice_rest": row["voice_rest"]} if row.get("voice_rest") is not None else {}),   # pacing exempts it
        })
    return shots


def inspect_script(shots, lang, seconds_override=None, story=None):
    """Run hook and pacing checks on a reel script. story: optional dict; its reel_target_s sets the pacing length window.

    Returns {"pass": bool, "hook": dict, "pacing": dict}.
    seconds_override ({id: seconds}, from a timeline lock) replaces the script seconds in pacing.
    Raises ValueError for empty shots or unsupported lang.
    Exceptions from script_hook / script_pacing propagate unchanged.
    """
    if not shots:
        raise ValueError("shots must not be empty")
    if lang not in SUPPORTED_LANGS:
        raise ValueError("unsupported lang: %s" % lang)

    import script_hook
    import script_pacing

    hook_result = script_hook.inspect_hook(shots, lang)
    extra = {"story": story} if story is not None else {}       # the old call shape stays when no story is given
    pacing_result = script_pacing.inspect_pacing(shots, lang, seconds_override=seconds_override, **extra)

    return {
        "pass": bool(hook_result["pass"] and pacing_result["pass"]),
        "hook": hook_result,
        "pacing": pacing_result,
    }


def format_report(result, lang="en"):
    """Build a plain-text inspection report from inspect_script output."""
    lines = []

    overall = "PASS" if result["pass"] else "FAIL"
    lines.append("SCRIPT INSPECTION: %s" % overall)

    hook = result["hook"]
    hook_pass = "PASS" if hook["pass"] else "FAIL"
    lines.append("HOOK score %d/100: %s" % (hook["score"], hook_pass))

    for text in hook["hard_fails"]:
        lines.append("  HARD: %s" % text)

    for text in hook["reasons"]:
        lines.append("  - %s" % text)

    for text in hook["rewrites"]:
        lines.append("  REWRITE: %s" % text)

    pacing = result["pacing"]
    pacing_pass = "PASS" if pacing["pass"] else "FAIL"
    lines.append("PACING: %s" % pacing_pass)

    for text in pacing["problems"]:
        lines.append("  - %s" % text)

    # warnings are printed but never change PASS/FAIL
    for text in pacing.get("warnings", []):
        lines.append("  WARNING: %s" % text)

    return "\n".join(lines) + "\n"


def main(argv=None):
    """CLI entry point. argv = [path_to_shots_json, lang] plus an optional --lock <file>."""
    if argv is None:
        argv = sys.argv[1:]

    lock_path = None
    if "--lock" in argv:
        at = argv.index("--lock")
        if at + 1 >= len(argv):
            print("usage: script_inspect.py <shots.json> <lang> [--lock <file>]")
            return 2
        lock_path = argv[at + 1]
        argv = argv[:at] + argv[at + 2:]

    if len(argv) != 2:
        print("usage: script_inspect.py <shots.json> <lang> [--lock <file>]")
        return 2

    path = argv[0]
    lang = argv[1]

    if not os.path.isfile(path):
        print("missing file: %s" % path)
        return 2

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        print("bad JSON: %s" % path)
        return 2

    if isinstance(data, dict):
        shots = data.get("shots", [])
    else:
        shots = data

    if not shots:
        print("invalid input: %s" % path)
        return 2
    if lang not in SUPPORTED_LANGS:
        print("invalid input: %s" % path)
        return 2

    seconds_override = None
    if lock_path is not None:
        if not os.path.isfile(lock_path):
            print("missing file: %s" % lock_path)
            return 2
        import timeline_lock_io

        try:
            lock = timeline_lock_io.load_lock(lock_path)
            fps = lock["fps"]
            seconds_override = {shot["id"]: shot["edit_frames"] / fps for shot in lock["shots"]}
            lock_ids = set(seconds_override)
            script_ids = set(row["id"] for row in shots if isinstance(row, dict) and "id" in row)
            diff = lock_ids ^ script_ids
            if diff:
                named = sorted(diff)[:5]
                raise ValueError("lock and script ids differ: %s" % ", ".join(named))
        except ValueError as exc:
            print("invalid input: %s" % exc)
            return 2

    try:
        shots = [
            from_pack([row], lang)[0]
            if isinstance(row, dict)
            and (
                "audio_and_dialogue_track" in row
                or "editorial_duration_sec" in row
                or "per_second_directives" in row
            )
            else row
            for row in shots
        ]
        result = inspect_script(shots, lang, seconds_override=seconds_override)
    except ValueError as exc:
        print("invalid input: %s" % exc)
        return 2
    print(format_report(result, lang))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
