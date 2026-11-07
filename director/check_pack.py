"""Rule check of a written pack (PACK.md + shots.json + story.json): episode lengths on H3's grid, banned names,
exact counts, modes, and the WP4 pack and retention rules (P0-P13, R1-R10).
  python check_pack.py PACK_DIR [--story PATH] [--strict]
Prints the result as JSON. Exit code 0; with --strict, exit 1 when any rule entry is FAIL."""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from h3_director import FPS, frames_for_shot
from layout_validator import check_layout
from shot_schema import validate_shots

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.append(str(_REPO))
from core.pack_rules import check_pack_rules  # noqa: E402
from core.retention_rules import check_retention_rules  # noqa: E402
from core.style_pack import load_core, load_pack  # noqa: E402
from core.timeline import build_episodes  # noqa: E402

BANNED = re.compile(r"ramayana:\s*the legend of prince rama|solo leveling|ufotable|a-1 pictures|pixar|disney", re.I)
COUNTS = re.compile(r"\b(101|202)\b")


def _p0(message, shot=None):
    return {"rule": "P0", "level": "FAIL", "shot": shot, "episode": None, "message": message}


def _p1(message):
    return {"rule": "P1", "level": "FAIL", "shot": None, "episode": None, "message": message}


def _find_story(pack_dir, story_path):
    """Explicit path, else story.json in the pack folder, its parent, then its grandparent (first hit)."""
    if story_path is not None:
        return Path(story_path)
    base = Path(pack_dir).resolve()
    for folder in (base, base.parent, base.parent.parent):
        if (folder / "story.json").is_file():
            return folder / "story.json"
    return None


def _load_story(story_file):
    """(story dict or None, file exists). Bad JSON counts as present but unreadable: check_pack_rules reports it as P1."""
    if story_file is None or not story_file.is_file():
        return None, False
    try:
        data = json.loads(story_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, True
    return (data if isinstance(data, dict) else None), True


def _read_shots(d, errors):
    try:
        data = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(_p0(f"shots.json could not be read: {type(exc).__name__}: {exc}"))
        return []
    if not isinstance(data, list):
        errors.append(_p0("shots.json must be a list of shots"))
        return []
    return data


def _shot_stats(shots, per_ep, modes, issues, errors):
    for n, s in enumerate(shots):
        if not isinstance(s, dict):
            errors.append(_p0(f"item {n} is not a shot object"))
            continue
        sid = s.get("id")
        try:
            modes[s.get("mode")] += 1
            per_ep[s.get("episode")] += (s["edit_frames"] if "edit_frames" in s else frames_for_shot(s)) / FPS   # kept part counts
            text = " ".join(str(s.get(k, "")) for k in ("style", "world", "action", "camera", "sound"))
            text += " ".join(str(b.get("acting", "")) for b in s.get("beats", []))   # rich shots carry their prompt in beats
            m = BANNED.search(text)
            if m:
                issues.append(f"{sid}: names a film/studio in the video prompt ({m.group(0)})")
            c = COUNTS.search(text)
            if c:
                issues.append(f"{sid}: exact count {c.group(0)} in the video prompt")
        except Exception as exc:  # malformed shot: reported as P0, never a traceback
            errors.append(_p0(f"{type(exc).__name__}: {exc}", shot=sid if isinstance(sid, str) else None))


def _sorted_items(d):
    try:
        return sorted(d.items())
    except TypeError:  # mixed episode keys (for example None and int)
        return sorted(d.items(), key=lambda kv: str(kv[0]))


def check(pack_dir, story_path=None):
    d = Path(pack_dir)
    issues, errors, modes, per_ep = [], [], Counter(), defaultdict(float)
    shots = _read_shots(d, errors)
    _shot_stats(shots, per_ep, modes, issues, errors)
    rich = [s for s in shots if isinstance(s, dict) and "beats" in s]   # rich shots: contract fields, then cross-shot layout
    if rich:
        try:
            issues += validate_shots(rich)
            issues += check_layout(rich)
        except Exception as exc:
            errors.append(_p0(f"shape or layout check could not run: {type(exc).__name__}: {exc}"))
    try:
        pack_text = (d / "PACK.md").read_text(encoding="utf-8")
    except OSError:
        pack_text = ""
    flow_prompts = re.findall(r"```(?:text|prompt)?\n(.*?)```", pack_text, re.S)
    banned_flow = sum(bool(BANNED.search(p)) for p in flow_prompts)

    story, story_exists = _load_story(_find_story(d, story_path))
    pack, pack_errors = None, []
    if story is not None and "style_pack" in story:
        try:
            pack = load_pack(story["style_pack"])
        except ValueError as exc:
            pack_errors.append(_p1(f"style pack could not be loaded: {exc}"))
    core = load_core()
    episodes, problems = build_episodes(shots)
    rules = (errors + problems + pack_errors
             + check_pack_rules(episodes, pack, core, story=story, story_path_exists=story_exists)
             + check_retention_rules(episodes, core, story))
    for e in rules:
        if e["level"] in ("FAIL", "WARN"):
            issues.append(f"{e['rule']} {e['level']}: {e['message']}")
    return {"shots": len(shots), "modes": dict(modes),
            "episode_seconds": {k: round(v, 1) for k, v in _sorted_items(per_ep)},
            "total_seconds": round(sum(per_ep.values()), 1),
            "code_blocks_naming_a_film": banned_flow, "issues": issues,
            "rules": rules, "fail": any(e["level"] == "FAIL" for e in rules)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check a pack folder (shots.json, PACK.md, story.json).")
    ap.add_argument("pack_dir")
    ap.add_argument("--story", default=None, help="path to story.json (default: search the pack folder and up two levels)")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any rule entry is FAIL")
    a = ap.parse_args(argv)
    result = check(a.pack_dir, a.story)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 1 if a.strict and result["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
