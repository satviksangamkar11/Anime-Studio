"""Rule check of a written pack (PACK.md + shots.json): episode lengths on H3's grid, banned names, exact counts, modes.
  python check_pack.py pack_dir"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from h3_director import FPS, frames_for
from layout_validator import check_layout
from shot_schema import validate_shots

BANNED = re.compile(r"ramayana|solo leveling|ufotable|a-1 pictures|pixar|disney", re.I)
COUNTS = re.compile(r"\b(101|202)\b")


def check(pack_dir):
    d = Path(pack_dir)
    shots = json.loads((d / "shots.json").read_text(encoding="utf-8"))
    pack = (d / "PACK.md").read_text(encoding="utf-8")
    per_ep = defaultdict(float)
    issues = []
    for s in shots:
        per_ep[s.get("episode")] += frames_for(s["seconds"]) / FPS
        text = " ".join(str(s.get(k, "")) for k in ("style", "world", "action", "camera", "sound"))
        text += " ".join(b.get("acting", "") for b in s.get("beats", []))   # rich shots carry their prompt in beats
        if BANNED.search(text):
            issues.append(f"{s['id']}: names a film/studio in the video prompt ({BANNED.search(text).group(0)})")
        if COUNTS.search(text):
            issues.append(f"{s['id']}: exact count {COUNTS.search(text).group(0)} in the video prompt")
    rich = [s for s in shots if "beats" in s]   # rich shots: contract fields per shot, then cross-shot layout
    if rich:
        issues += validate_shots(rich)
        issues += check_layout(rich)
    flow_prompts = re.findall(r"```(?:text|prompt)?\n(.*?)```", pack, re.S)
    banned_flow = sum(bool(BANNED.search(p)) for p in flow_prompts)
    return {"shots": len(shots), "modes": dict(__import__("collections").Counter(s["mode"] for s in shots)),
            "episode_seconds": {k: round(v, 1) for k, v in sorted(per_ep.items())}, "total_seconds": round(sum(per_ep.values()), 1),
            "code_blocks_naming_a_film": banned_flow, "issues": issues}


if __name__ == "__main__":
    print(json.dumps(check(sys.argv[1]), indent=1, ensure_ascii=False))
