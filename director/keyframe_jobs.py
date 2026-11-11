"""Keyframe job generation for card X-09.

Builds the A (authoring) and B (edit-of-A) keyframe jobs for a shot from a
shot sheet, a plate id, and bible names.  Never calls Flow.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Tuple

try:
    from .blocking import change_list, prompt_args
except ImportError:
    from blocking import change_list, prompt_args

# Flow root holding plates/plates.json; set by the CLI or by the caller.
FLOW_ROOT = None


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
    with open(os.path.join(plates_dir, "plates.json"), "r", encoding="utf-8") as fh:
        catalog = json.load(fh)

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


def _prompt_from_cast(cast: List[Dict]) -> str:
    parts = []
    for member in cast:
        start = member.get("start", {})
        parts.append(
            "{name} at ({x},{y}), scale {scale}, facing {facing}, pose {pose}".format(
                name=member.get("name", "?"),
                x=start.get("x", 0),
                y=start.get("y", 0),
                scale=start.get("scale", 1),
                facing=start.get("facing", "camera"),
                pose=start.get("pose", "standing"),
            )
        )
    if not parts:
        return "same set"
    return "same set, add: " + "; ".join(parts)


def _instruction_from_change_list(changes: List[str]) -> str:
    if not changes:
        return "same picture, make no changes"
    numbered = " ".join(f"{i + 1}) {c}" for i, c in enumerate(changes))
    return f"same picture, make these exact changes only: {numbered}"


def jobs_for_shot(sheet, plate_id: str, bible_names: List[str]) -> Tuple[Dict, Dict]:
    """Build the (job_a, job_b) keyframe jobs for a shot.

    Both jobs have exactly the keys method, chips, prompt, base_edit_id,
    edit_instruction, people_count.  Raises KeyframeJobError when the plate
    is not in the plates registry under FLOW_ROOT.
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

    instruction = _instruction_from_change_list(change_list(sheet))

    job_a = {
        "method": "edit",
        "chips": [plate_path],
        "prompt": _prompt_from_cast(cast),
        "base_edit_id": plate_id,
        "edit_instruction": None,
        "people_count": people_count,
    }
    job_b = {
        "method": "edit",
        "chips": [f"{shot}-A final"],
        "prompt": None,
        "base_edit_id": f"{shot}-A",
        "edit_instruction": instruction,
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
        out[shot] = [job_a, job_b]

    out_dir = os.path.join(args.flow_root, args.adhyay)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "keyframe_jobs.json"), "w", encoding="utf-8") as fh:
        json.dump({"jobs": out}, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
