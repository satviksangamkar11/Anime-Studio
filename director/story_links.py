"""Links from a story (or one of its packs) to what was made from it: images folder, results folder, Flow job files.

stories/<slug>/links.json (local; stories/ is git-ignored):
  {"schema_version": 1, "links": [{"kind": "images" | "results" | "flow_jobs", "pack": "pack_x" or null,
                                   "path": "...", "note": "", "linked_at": "..."}]}
A relative path is taken from the anime_studio folder; an absolute one (for example D:/aai work/flow_outputs/x) as it is.
A link must exist and must not point inside stories/. link() is the only writer and writes only when called; read(),
check() and discover() never write. Stdlib only, offline."""
from __future__ import annotations

import json
from pathlib import Path

import run_registry as rr

LINKS_FILE = "links.json"
KINDS = ("images", "results", "flow_jobs")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
GENERIC = {"katha", "gita", "discourse", "story", "stories"}      # words every story has: they match nothing


def _story_dir(studio, slug) -> Path:
    if not isinstance(slug, str) or not rr.SLUG.fullmatch(slug):
        raise ValueError("slug must be lower-case letters, digits and _ (1-40)")
    return Path(studio) / "stories" / slug


def _inside_stories(studio, full: Path) -> bool:
    root = (Path(studio) / "stories").resolve()
    return full == root or root in full.parents


def resolve_link(studio, path: str) -> Path:
    """The absolute path a stored link points to (relative ones from the studio folder)."""
    p = Path(path)
    return (p if p.is_absolute() else Path(studio) / p).resolve()


def _shown(studio, full: Path) -> str:
    try:
        return full.relative_to(Path(studio).resolve()).as_posix()
    except ValueError:
        return str(full)


def read(studio, slug) -> dict:
    """{'schema_version': 1, 'links': [...]} as stored; an empty list when there is no links.json. Writes nothing."""
    data = rr.read_json(_story_dir(studio, slug) / LINKS_FILE)
    if not isinstance(data, dict) or not isinstance(data.get("links"), list):
        return {"schema_version": 1, "links": []}
    return data


def check(studio, slug) -> list:
    """Each stored link with 'exists' (True/False) and 'resolved' (the absolute path). Writes nothing."""
    out = []
    for link in read(studio, slug)["links"]:
        try:
            full = resolve_link(studio, link.get("path") or "")
            exists = full.exists() and not _inside_stories(studio, full)
            resolved = str(full)
        except (OSError, RuntimeError, ValueError):
            exists, resolved = False, None
        out.append({**link, "exists": exists, "resolved": resolved})
    return out


def link(studio, slug, kind, path, pack=None, note="") -> dict:
    """Adds one link to stories/<slug>/links.json and returns it. The same kind, pack and path twice writes nothing."""
    story_dir = _story_dir(studio, slug)
    if not story_dir.is_dir():
        raise FileNotFoundError(f"no story folder {story_dir}")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    if pack is not None and not (isinstance(pack, str) and rr.PACK.fullmatch(pack) and (story_dir / pack).is_dir()):
        raise ValueError(f"pack must be the name of a pack folder in the story: {pack!r}")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path is empty")
    full = resolve_link(studio, path.strip())
    if _inside_stories(studio, full):
        raise ValueError("a link may not point inside stories/ (the story's own files are not linked)")
    if not full.exists():
        raise FileNotFoundError(f"{full} does not exist")
    if kind == "flow_jobs" and not full.is_file():
        raise ValueError("flow_jobs needs a file (a Flow job or spec .json)")
    if kind != "flow_jobs" and not full.is_dir():
        raise ValueError(f"{kind} needs a folder")
    shown = _shown(studio, full)
    data = read(studio, slug)
    for old in data["links"]:
        if (old.get("kind"), old.get("pack"), old.get("path")) == (kind, pack, shown):
            return old
    entry = {"kind": kind, "pack": pack, "path": shown, "note": (note or "")[:200], "linked_at": rr.now_iso()}
    data["links"].append(entry)
    data["schema_version"] = 1
    rr._write_atomic(story_dir / LINKS_FILE, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    return entry


def name_tokens(slug: str) -> list:
    return [t for t in slug.split("_") if len(t) >= 4 and t not in GENERIC]


def default_roots(studio, slug) -> list:
    studio = Path(studio)
    return [studio.parent / "flow_outputs", studio / "flow", studio / "flow" / "generated" / slug,
            studio / "director" / "t0_pack" / "results"]


def _kind_of(child: Path):
    if child.is_dir():
        has_images = any(p.suffix.lower() in IMAGE_EXT for p in child.iterdir() if p.is_file())
        return "images" if has_images else "results"
    return "flow_jobs" if child.suffix.lower() == ".json" else None


def discover(studio, slug, roots=None) -> list:
    """Candidate links for an old story: entries of the roots whose names contain the slug or its name words.
    Suggestions only: nothing is linked or written. Each has kind, path, pack (None), score and reason."""
    studio = Path(studio)
    tokens = name_tokens(slug)
    found, seen = [], set()
    for root in (roots if roots is not None else default_roots(studio, slug)):
        root = Path(root)
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            name = child.name.lower()
            hits = [t for t in tokens if t in name]
            if not hits and slug not in name:
                continue
            kind = _kind_of(child)
            full = child.resolve()
            if kind is None or _inside_stories(studio, full):
                continue
            shown = _shown(studio, full)
            if (kind, shown) in seen:
                continue
            seen.add((kind, shown))
            score = len(hits) + (len(tokens) + 1 if slug in name else 0)
            found.append({"kind": kind, "pack": None, "path": shown, "score": score,
                          "reason": f"name matches {', '.join(hits) or slug} in {root.name}"})
    found.sort(key=lambda d: (-d["score"], d["path"]))
    return found[:50]
