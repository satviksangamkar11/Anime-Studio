"""Reference-sheet Flow jobs straight from a plan's bible (stage 2), so the sheets can start before Gate A (owner 2026-11-08).

Each CHAR / ENV / PROP entry with a sheet_prompt becomes one 16:9 'generate' job in the jobs-file format the packet and the
queue read. No chips (the sheets ARE the first chips). Characters first, then places, then props. Refuses to overwrite.

Usage:  python bible_to_sheet_jobs.py <stage_2_raw.json | bible.json> <story_slug> <out_jobs.json> [--only CHAR-A,CHAR-B]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ORDER = ("characters", "environments", "props")


def load_bible(path):
    """bible.json, or a writer stage_2_raw.json envelope (parsed with the writer's own parser)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "result" in data and "characters" not in data:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "director"))
        import write_pack
        return write_pack.parse_bible(Path(path).read_text(encoding="utf-8"))[1]
    return data


def sheet_jobs(bible, only=None):
    jobs = []
    for group in ORDER:
        items = bible.get(group) if isinstance(bible.get(group), dict) else {}
        for sid, item in items.items():
            prompt = item.get("sheet_prompt") if isinstance(item, dict) else None
            if not isinstance(prompt, str) or not prompt.strip() or (only and sid not in only):
                continue
            jobs.append({"adhyay": 1, "shot_id": sid, "scene": "REF", "method": "generate", "file_version": "v01",
                         "flow_title": f"{sid}__v01", "characters": [sid] if group == "characters" else [], "chips": [],
                         "unaccepted_sheets": [], "prompt": prompt.strip(),
                         "prompt_sha256": hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest(),
                         "base_edit_id": None, "edit_instruction": None, "previous_shot": None, "next_shot": None,
                         "attempt_cap": 8, "neighbour_chips": [], "neighbour_sentence": "", "aspect": "16:9",
                         "model": {"name": "Nano Banana 2.1", "fallback": None, "count": "x2", "aspect": "16:9"}, "status": "TODO"})
    return jobs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bible"); ap.add_argument("slug"); ap.add_argument("out")
    ap.add_argument("--only", default="", help="comma list of ids to include (default: all)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        print(f"REFUSED: {out} exists (delete it to rebuild)")
        return 2
    jobs = sheet_jobs(load_bible(a.bible), {x for x in a.only.split(",") if x} or None)
    if not jobs:
        print("REFUSED: no sheet_prompt found in the bible")
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(jobs, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(jobs)} sheet jobs -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
