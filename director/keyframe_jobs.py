"""Keyframe job generation for card X-09.

Builds the A (authoring) and B (edit-of-A) keyframe jobs for a shot from a
shot sheet, a plate id, and bible names.  Never calls Flow.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Dict, List, Optional, Tuple

try:
    from .blocking import change_list, prompt_args
except ImportError:
    from blocking import change_list, prompt_args

# Flow root holding plates/plates.json; set by the CLI or by the caller.
FLOW_ROOT = None
# STYLE chip (one frame per style pack) attached to every A job; set by the caller.
STYLE_CHIP = None
# Style anchor sentence from the style pack; set by the caller. None = no sentence.
# ponytail: no style-pack reader here, caller passes the text; add when a pack loader exists.
STYLE_ANCHOR = None
MAX_A_WORDS = 110
MAX_B_CHANGES = 3
FRAME_LAW = "Vertical 9:16 frame. Faces stay in the upper two thirds."
# ponytail: fixed exclusion (4 nouns); bible forbidden list not wired yet.
EXCLUSION = "No text, no logo, no extra people, no halo."
B_PREFIX = "Same picture, same framing, same light, same background."

_POSE_ADJ = {"standing": "standing", "seated": "seated", "kneeling": "kneeling", "lying": "lying down",
             "walking": "walking", "flying": "flying"}
_POSE_VERB = {"standing": "stands", "seated": "sits", "kneeling": "kneels", "lying": "lies down",
              "walking": "walks", "flying": "flies"}
_FACING = {"left": "facing screen-left", "right": "facing screen-right",
           "camera": "facing the viewer", "away": "seen from behind"}
_FRAMING = {"wide": "Wide shot", "medium": "Medium shot", "close": "Close-up",
            "extreme_close": "Extreme close-up"}
_ANGLE = {"eye_level": "at eye level", "low": "from a low angle", "high": "from a high angle",
          "ground": "from ground level", "overhead": "from overhead"}
_LENS = {"wide": "gentle wide-angle perspective", "normal": "natural perspective",
         "tele": "soft telephoto perspective"}
_MOVE_RE = re.compile(r"^(.+): move from \(([-\d.]+),([-\d.]+)\) to \(([-\d.]+),([-\d.]+)\)$")
_POSE_RE = re.compile(r"^(.+): (\w+) -> (\w+)$")
_SCALE_RE = re.compile(r"^(.+): scale ([-\d.]+) to ([-\d.]+)$")
_PROP_RE = re.compile(r"^prop (.+): (.+)$")
_KEEP_LINE = "keep everything else exactly the same"


class KeyframeJobError(Exception):
    """Raised when a keyframe job cannot be built (e.g. a plate is missing)."""


def _plate_file(flow_root: str, rel_path: str) -> str:
    """Resolve a registry path: under <flow_root>/plates first, then <flow_root>."""
    candidate = os.path.join(flow_root, "plates", rel_path)
    if not os.path.exists(candidate):
        candidate = os.path.join(flow_root, rel_path)
    return os.path.normpath(candidate)


def plates_index(flow_root: str) -> Dict[str, Dict[str, str]]:
    """Return {plate_id: {"path": ..., "sha256": ...}} for <flow_root>/plates.

    Reads <flow_root>/plates/plates.json and hashes every referenced file.
    """
    plates_dir = os.path.join(flow_root, "plates")
    try:
        with open(os.path.join(plates_dir, "plates.json"), "r", encoding="utf-8") as fh:
            catalog = json.load(fh)
    except FileNotFoundError:
        raise KeyframeJobError("plates registry missing: {p}".format(p=os.path.join(plates_dir, "plates.json")))

    index: Dict[str, Dict[str, str]] = {}
    for plate_id, entry in catalog.items():
        if isinstance(entry, dict):
            if "path" not in entry:
                raise KeyframeJobError("plate {pid} has no path in plates.json".format(pid=plate_id))
            rel_path = entry["path"]
        else:
            rel_path = str(entry)
        candidate = _plate_file(flow_root, rel_path)
        if not os.path.isfile(candidate):
            raise KeyframeJobError("plate {pid} file missing: {p}".format(pid=plate_id, p=candidate))
        with open(candidate, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        index[plate_id] = {"path": rel_path, "sha256": digest}
    return index


def _people_count(cast: List[Dict]) -> int:
    """Count the cast on screen, using the same visibility rule as blocking.prompt_args."""
    return len(prompt_args({"cast": cast})["on_screen"])


def _get(sheet, *names, default=None):
    """Read the first present field from a dict or an object sheet."""
    for name in names:
        if isinstance(sheet, dict):
            if name in sheet:
                return sheet[name]
        elif hasattr(sheet, name):
            return getattr(sheet, name)
    return default


def _x_region(x: float) -> str:
    if x < 0.33:
        return "left third"
    if x <= 0.67:
        return "centre"
    return "right third"


def _y_band(y: float) -> str:
    if y < 0.40:
        return "high in the frame"
    if y < 0.62:
        return "at mid-height"
    return "low in the frame"


def xy_words(x: float, y: float) -> Tuple[str, str]:
    """Blocking x, y to words: ('in the left third', 'low in the frame')."""
    region = _x_region(x)
    in_phrase = "in the centre" if region == "centre" else "in the " + region
    return in_phrase, _y_band(y)


def scale_words(scale: float) -> str:
    if scale >= 0.80:
        return "filling most of the frame height"
    if scale >= 0.45:
        return "full figure about half the frame height"
    if scale >= 0.20:
        return "a small full figure"
    return "a tiny figure"


def _shot_sentence(camera: Dict) -> str:
    framing = _FRAMING.get(camera.get("framing", "medium"), "Medium shot")
    angle = _ANGLE.get(camera.get("angle", "eye_level"), "at eye level")
    lens = _LENS.get(camera.get("lens", "normal"), "natural perspective")
    return f"{framing} {angle}, {lens}."


def _light_sentence(light: Dict) -> str:
    key = light.get("key_dir")
    if key in ("left", "right"):
        return f"Key light from screen-{key}."
    return f"Key light from the {key}."


def a_prompt(sheet) -> str:
    """Eight plain sentences for the start picture A (Opus 4.1). No labels, no coordinates."""
    cast = _get(sheet, "cast", default=[]) or []
    camera = _get(sheet, "camera", default={}) or {}
    light = _get(sheet, "light", default={}) or {}
    sentences = []
    if STYLE_ANCHOR:
        sentences.append(STYLE_ANCHOR)
    sentences.append(_shot_sentence(camera))
    for member in cast:
        start = member.get("start", {})
        name = member.get("name", "?")
        in_phrase, y_phrase = xy_words(start.get("x", 0.5), start.get("y", 0.5))
        sentences.append(f"{name} is {in_phrase}, {y_phrase}, {scale_words(start.get('scale', 0.5))}.")
        pieces = [_POSE_ADJ.get(start.get("pose", "standing"), "standing"),
                  _FACING.get(start.get("facing", "camera"), "")]
        if member.get("expression"):
            pieces.append(f"{member['expression']} expression")
        sentences.append(f"{name}: " + ", ".join(p for p in pieces if p) + ".")
    if light.get("key_dir"):
        sentences.append(_light_sentence(light))
    on_screen = [m.get("name", "?") for m in cast if 0 <= m.get("start", {}).get("x", 0.5) <= 1]
    if on_screen:   # G18: say who IS there, not only who is not
        sentences.append("Exactly these people are in the frame: " + ", ".join(on_screen) + ".")
    sentences.append(FRAME_LAW)
    sentences.append(EXCLUSION)
    prompt = " ".join(sentences)
    if len(prompt.split()) > MAX_A_WORDS:
        raise KeyframeJobError(
            "A prompt for {s} is {n} words, max {m}; shorten the cast or the notes".format(
                s=_get(sheet, "shot", "shot_id", default="SHOT-000"), n=len(prompt.split()), m=MAX_A_WORDS)
        )
    return prompt


def _b_change_words(sheet, raw: str) -> str:
    """Turn one change_list line into words (no coordinates)."""
    move = _MOVE_RE.match(raw)
    if move:
        name, x0, y0, x1, y1 = move.group(1), float(move.group(2)), float(move.group(3)), \
            float(move.group(4)), float(move.group(5))
        end_scale = next(
            (m.get("end", {}).get("scale", 0.5) for m in sheet.get("cast", []) if m.get("name") == name), 0.5
        )
        if (x0, y0) == (x1, y1):
            return f"{name} now {scale_words(end_scale)}."
        text = f"{name} moves to the {_x_region(x1)}"
        if y0 != y1:
            text += f", {_y_band(y1)}"
        return text + "."
    scale = _SCALE_RE.match(raw)
    if scale:
        return f"{scale.group(1)} now {scale_words(float(scale.group(3)))}."
    prop = _PROP_RE.match(raw)
    if prop:
        return f"The {prop.group(1)} {prop.group(2)}."
    pose = _POSE_RE.match(raw)
    if pose:
        return f"{pose.group(1)} now {_POSE_VERB.get(pose.group(3), pose.group(3))}."
    return raw + "."


def b_instruction(sheet) -> str:
    """B text: 'Same picture, same framing, same light, same background. Change only: 1) ... 2) ...'."""
    raw = [c for c in change_list(sheet) if c != _KEEP_LINE]
    if len(raw) > MAX_B_CHANGES:
        raise KeyframeJobError(
            "shot {s}: {n} changes, max {m}; split the shot".format(
                s=_get(sheet, "shot", "shot_id", default="SHOT-000"), n=len(raw), m=MAX_B_CHANGES)
        )
    if not raw:
        return f"{B_PREFIX} Change nothing."
    items = " ".join(f"{i + 1}) {_b_change_words(sheet, c)}" for i, c in enumerate(raw))
    return f"{B_PREFIX} Change only: {items}"


def jobs_for_shot(sheet, plate_id: str, bible_names: List[str]) -> Tuple[Dict, Optional[Dict]]:
    """Build the (job_a, job_b) keyframe jobs for a shot.

    Both jobs have exactly the keys method, chips, prompt, base_edit_id,
    edit_instruction, people_count.  job_b is None for route S (empty plate or
    reveal shot).  Raises KeyframeJobError when the plate is not in the plates
    registry under FLOW_ROOT, when A is over 110 words, or when B has over 3 changes.
    """
    if not FLOW_ROOT:
        raise KeyframeJobError("FLOW_ROOT is not set")
    index = plates_index(FLOW_ROOT)
    if plate_id not in index:
        raise KeyframeJobError(
            "plate {pid} missing: make it once per location first".format(pid=plate_id)
        )
    plate_path = _plate_file(FLOW_ROOT, index[plate_id]["path"])

    shot = _get(sheet, "shot", "shot_id", default="SHOT-000")
    cast = _get(sheet, "cast", default=[]) or []
    people_count = _get(sheet, "people_count", default=None)
    if people_count is None:
        people_count = _people_count(cast)

    a_chips = [plate_path] + ([STYLE_CHIP] if STYLE_CHIP else [])
    job_a = {
        "method": "edit",
        "chips": a_chips,
        "prompt": a_prompt(sheet),
        "base_edit_id": plate_id,
        "edit_instruction": None,
        "people_count": people_count,
    }
    route = _get(sheet, "route", default=None)
    if route in ("S", "REF_S") or (route is None and os.environ.get("SHOT_MODE_S_ALLOW") != "0"):   # M-32: S is the default: no B
        return job_a, None
    chip_ref_id = f"{shot}-A final"
    job_b = {
        "method": "generate_with_chip",
        "chips": [chip_ref_id],
        "chip_ref_id": chip_ref_id,
        "prompt": None,
        "base_edit_id": f"{shot}-A",
        "edit_instruction": b_instruction(sheet),
        "people_count": people_count,
    }
    return job_a, job_b


def main(argv=None) -> int:
    """CLI: flow_root adhyay sheets.json -> <flow_root>/<adhyay>/keyframe_jobs.json.

    sheets.json is a list of shot sheet objects, each with a plate_id.
    """
    import argparse

    global FLOW_ROOT
    parser = argparse.ArgumentParser(
        prog="director.keyframe_jobs",
        description="Write keyframe_jobs.json for an adhyay (never calls Flow).",
    )
    parser.add_argument("flow_root")
    parser.add_argument("adhyay")
    parser.add_argument("sheets")
    args = parser.parse_args(argv)

    FLOW_ROOT = args.flow_root
    with open(args.sheets, "r", encoding="utf-8") as fh:
        sheets = json.load(fh)
    out = {}
    for sheet in sheets:
        shot = _get(sheet, "shot_id", "shot")
        job_a, job_b = jobs_for_shot(sheet, sheet["plate_id"], [])
        out[shot] = [job_a] if job_b is None else [job_a, job_b]

    out_dir = os.path.join(args.flow_root, args.adhyay)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "keyframe_jobs.json"), "w", encoding="utf-8") as fh:
        json.dump({"jobs": out}, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
