"""Write settings_<id>.json for each shot, exactly as the Kaggle batch would have them (image paths rewritten, PNG checked),
and <id>.edit.json (render_frames, edit_frames, the shot's direction), for reading before any push. No network, no Kaggle, no GPU.
  python dry_run.py shots.json keyframes_root out_dir style_project
The style project is mandatory: the identity text is part of every prompt. Duplicate shot ids are refused before anything is written."""
import json
import sys
from pathlib import Path

import run_kaggle
import style_bible
from h3_director import check_unique_ids, settings_for


def main(shots_path, root, out_dir, project=None, require_bible=False):
    shots = json.loads(Path(shots_path).read_text(encoding="utf-8"))
    check_unique_ids(shots)
    bible = style_bible.load(project) if project else None
    images = {}
    embed = run_kaggle.embedder(root, images)
    built = [(shot, settings_for(shot, bible, embed, require_bible)) for shot in shots]   # all-or-nothing: nothing is written yet
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    for shot, s in built:
        (out / f"settings_{shot['id']}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
        edit = {"id": shot["id"], "render_frames": s["video_length"], "edit_frames": shot.get("edit_frames", s["video_length"]),
                "direction": shot}
        (out / f"{shot['id']}.edit.json").write_text(json.dumps(edit, indent=1, ensure_ascii=False), encoding="utf-8")
        print(shot["id"], s["video_length"], "frames")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit("usage: python dry_run.py shots.json keyframes_root out_dir style_project")
    main(*sys.argv[1:5], require_bible=True)
