"""Where each story stands, read from its files only (stdlib, offline, nothing is written).

  python director/story_state.py [SLUG] [--json] [--studio PATH]

summarize(studio, slug) -> dict: the stage reached, the latest pack per writer, the next step (a machine key and a sentence),
whether a partial analysis can resume and from which stage, models used, gates, links and warnings.
summarize_all(studio) -> one such dict per stories/<slug>/ folder (a story that cannot be read gives {"slug", "error"}).

Stages: story, analysis_partial, analysis_done, validated, images, readout, render, export.
Event names come from RUNS.jsonl: a 'pack_check' event with stage None or 'pack' and status ok is the pack validator passing
(stage-level checks of the writer carry the stage name and do not count). Gate decisions carry no pack name, so a Gate A
approval counts for the whole story until the UI scopes approvals per pack."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import run_registry as rr
import story_links as sl

STUDIO = Path(__file__).resolve().parents[1]
MAIN_RAW = re.compile(r"stage_([0-9]{1,2}(?:e[0-9]{1,2})?)_raw\.json")
ANY_RAW = re.compile(r"stage_([0-9]{1,2}(?:e[0-9]{1,2})?)_raw(?:_content_filter_\d+)?\.json")
VALIDATION = re.compile(r"stage_([0-9]{1,2}(?:e[0-9]{1,2})?)_validation\.json")
PACK_NAME = re.compile(r"pack_(?P<writer>.+?)(?:_(?P<day>\d{8}))?(?:_v(?P<n>\d+))?")
EPISODE = re.compile(r"Episode\s+(\d+)\s*:")
TINY_BYTES = 200          # a saved answer this small is an error envelope (the 144-byte failures), not a stage


def _label_key(label: str) -> tuple:
    m = re.fullmatch(r"(\d+)(?:e(\d+))?", label)
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (99, 0)


def _episodes(stage1) -> int | None:
    text = stage1.get("result") if isinstance(stage1, dict) else None
    nums = {int(n) for n in EPISODE.findall(text)} if isinstance(text, str) else set()
    return max(nums) if nums else None


def _pack_info(folder: Path, name: str, models: dict, src_mtime) -> dict:
    pdir = folder / name
    files = [p for p in pdir.rglob("*") if p.is_file()]
    present, failed, length, tiny, validation, stage1 = set(), set(), set(), [], set(), None
    for p in sorted(files):
        if p.stat().st_size <= TINY_BYTES and (ANY_RAW.fullmatch(p.name) or p.name == "raw_response.json"):
            tiny.append(p.name)
        v = VALIDATION.fullmatch(p.name)
        if v:
            validation.add(v.group(1))
        main = MAIN_RAW.fullmatch(p.name)
        if p.name == "raw_response.json":
            label = "single"
        elif main:
            label = main.group(1)
        else:
            continue
        present.add(label)
        info = rr.envelope_file(p)
        if info.get("failed"):
            failed.add(label)
        if info.get("finish") == "length":
            length.add(label)
        if label == "1":
            stage1 = rr.read_json(p)
    failed |= validation
    ok = present - failed
    episodes = _episodes(stage1) if "1" in ok else None
    expected = ["single"] if "single" in present else ["1", "2"] + [f"3e{k}" for k in range(1, (episodes or 0) + 1)] + ["5"]
    finished = rr.is_finished(pdir)
    m = PACK_NAME.fullmatch(name)
    summary = (rr.pack_summary(pdir) or {}) if finished else {}
    return {"name": name, "writer": m.group("writer") if m else name, "empty": not files, "files": len(files),
            "finished": finished, "episodes": episodes, "stages_present": sorted(present, key=_label_key),
            "stages_missing": [label for label in expected if label not in ok], "failed_stages": sorted(failed, key=_label_key),
            "length_stages": sorted(length, key=_label_key), "tiny_files": tiny, "model": models.get(name),
            "source_status": rr.pack_source_status(folder, name) if files else None,
            "reels": summary.get("reels"), "shots": summary.get("shots"), "seconds": summary.get("seconds"),
            "_ts": max(p.stat().st_mtime for p in files) if files else pdir.stat().st_mtime, "_src_mtime": src_mtime}


def _public(pack: dict) -> dict:
    return {k: v for k, v in pack.items() if not k.startswith("_")}


def _stage(has_source, packs, runs, latest, validated, ok_kinds, gate_ok) -> str:
    if latest is None:
        return "analysis_partial" if (packs or runs) else ("story" if has_source else "none")
    stage = "validated" if validated else "analysis_done"
    if gate_ok("A") or ok_kinds & {"spec_built", "jobs_built", "image_review"}:
        stage = "images"
    if gate_ok("B"):
        stage = "readout"
    if gate_ok("C") or "render_prepare" in ok_kinds:
        stage = "render"
    if gate_ok("D"):
        stage = "export"
    return stage


def _next_step(has_source, gates, resume, latest_name, validated, ok_kinds, gate_ok, linked_images) -> tuple:
    rejected = [g for g in rr.GATES if gates.get(g) == "reject"]
    if not has_source:
        return "save_story", "Save the story text or its YouTube link (SOURCE.md) first."
    if rejected:
        return "gate_rejected", (f"Gate {rejected[-1]} was rejected: fix what the owner named, then continue from that gate "
                                 "(a changed plan gets a new pack name).")
    if resume:
        pack = resume["name"]
        if resume["failed_stages"]:
            lab = resume["failed_stages"][0]
            return "fix_failed_stage", (f"Stage {lab} of {pack} failed its checks: delete stage_{lab}_raw.json and "
                                        f"stage_{lab}_validation.json in {pack}, then resume.")
        first = resume["stages_missing"][0] if resume["stages_missing"] else "assembly (all stages saved, PACK.md or shots.json missing)"
        return "run_writer_resume", (f"Resume {pack} from stage {first}: saved stages are reused, "
                                     "so only the missing ones call a model.")
    if latest_name is None:
        return "run_writer", "Run the writer on the story: there is no finished pack yet."
    if not validated:
        return "run_validator", f"Run the pack validator on {latest_name}."
    if not gate_ok("A"):
        return "await_gate_A", f"Owner approves the plan of {latest_name} (Gate A)."
    if "jobs_built" not in ok_kinds:
        return "build_image_jobs", "Build the image jobs from the approved pack."
    if "image_review" not in ok_kinds:
        if not linked_images:
            return "link_images", "Link the images folder of this story (story_links.link) before the image review."
        return "run_image_review", "Review the images, then Gate B."
    if not gate_ok("B"):
        return "await_gate_B", "Owner checks the images (Gate B)."
    if not gate_ok("C"):
        return "await_gate_C", "Read-out, then the owner types START (Gate C)."
    if "render_prepare" not in ok_kinds:
        return "prepare_render", "Prepare the render for the approved plan (router, compile, lint)."
    if not gate_ok("D"):
        return "await_gate_D", "Owner approves the audio and captions mix (Gate D)."
    return "run_final_qc_export", "Run the Step 9 final QC, then export."


def _warnings(folder: Path, story: dict, packs: list, runs: list, links: list) -> list:
    out = []

    def add(key, level, text):
        out.append({"key": key, "level": level, "text": text})

    if rr.read_story(folder) is None:
        add("no_story_json", "warn", "story.json is missing: run director/backfill_registry.py --apply")
    if not (folder / rr.REPORT_FILE).is_file():
        add("no_run_report", "info", "RUN_REPORT.md is missing: run director/backfill_registry.py --apply")
    current = rr.source_file_hash(folder)
    if story.get("source_sha256") and current and story["source_sha256"] != current:
        add("source_changed_since_save", "warn", "SOURCE.md differs from the hash saved in story.json")
    for p in packs:
        n = p["name"]
        if p["empty"]:
            add(f"empty_pack:{n}", "warn", f"{n} has no files: remove it with backfill_registry.py --fix-empty-packs --apply")
        for lab in p["failed_stages"]:
            add(f"stage_failed:{n}:{lab}", "warn", f"stage {lab} of {n} failed its checks (see its validation file)")
        for lab in p["length_stages"]:
            add(f"finish_length:{n}:{lab}", "warn", f"stage {lab} of {n} was cut off (finish=length): delete its raw file and rerun")
        for f in p["tiny_files"]:
            add(f"tiny_stage_file:{n}:{f}", "warn", f"{n}/{f} is only a few bytes: an error answer, not a stage")
        if p["source_status"] == "changed":
            add(f"source_changed:{n}", "warn", f"SOURCE.md changed after {n} was made: the pack may not match the source")
        elif p["source_status"] == "unknown" and p["_src_mtime"] and p["finished"] and p["_src_mtime"] > p["_ts"]:
            add(f"source_newer:{n}", "info", f"SOURCE.md is newer than {n} (file times; that run recorded no hash)")
    for r in runs:
        if r["status"] == "open":
            add(f"open_run:{r['run_id']}", "info", f"run {r['run_id']} still has a step marked started")
    if runs and runs[-1]["status"] in ("failed", "stopped"):
        last = runs[-1]
        add(f"last_run_{last['status']}", "info", f"the last run ({last['run_id']}) {last['status']}: {last['note'] or 'no note'}")
    for link in links:
        if not link["exists"]:
            add(f"link_missing:{link['path']}", "warn", f"linked {link['kind']} path does not exist: {link['path']}")
    return out


def summarize(studio, slug: str) -> dict:
    """One story from its files. Raises ValueError for a bad slug and FileNotFoundError when the folder is missing."""
    if not isinstance(slug, str) or not rr.SLUG.fullmatch(slug):
        raise ValueError("slug must be lower-case letters, digits and _ (1-40)")
    studio = Path(studio)
    folder = studio / "stories" / slug
    if not folder.is_dir():
        raise FileNotFoundError(f"no story folder {folder}")
    story = rr.read_story(folder) or rr.default_story(folder)
    events = rr.read_events(folder)
    rows = rr.steps(events)
    runs = rr.runs(events, rows)
    models = rr.pack_models(rows)
    src = folder / "SOURCE.md"
    src_mtime = src.stat().st_mtime if src.is_file() else None
    names = sorted(p.name for p in folder.iterdir() if p.is_dir() and p.name.startswith("pack_") and rr.PACK.fullmatch(p.name))
    packs = [_pack_info(folder, n, models, src_mtime) for n in names]
    latest_name = rr.latest_pack(folder)
    latest = next((p for p in packs if p["name"] == latest_name), None)
    unfinished = [p for p in packs if not p["finished"] and (p["stages_present"] or p["failed_stages"])]
    newest_open = max(unfinished, key=lambda p: p["_ts"], default=None)
    resume = newest_open if newest_open and (latest is None or newest_open["_ts"] > latest["_ts"]) else None
    ok_kinds = {r.get("kind") for r in rows if r.get("status") == "ok"}
    gates = {}
    for ev in events:
        if ev.get("kind") == "gate_decision" and ev.get("status") == "ok" and ev.get("gate"):
            gates[ev["gate"]] = ev.get("decision")

    def gate_ok(g):
        return gates.get(g) == "approve"

    checks = [r for r in rows if r.get("kind") == "pack_check" and r.get("pack") == latest_name and r.get("stage") in (None, "pack")]
    validated = latest is not None and any(r.get("status") == "ok" for r in checks) and not any(r.get("status") == "failed" for r in checks)
    links = sl.check(studio, slug)
    linked_images = [k for k in links if k["kind"] == "images" and k["exists"] and k.get("pack") in (None, latest_name)]
    key, text = _next_step(src.is_file(), gates, resume, latest_name, validated, ok_kinds, gate_ok, linked_images)
    resume_out = None
    if resume:
        resume_out = {"pack": resume["name"], "from_stage": (resume["stages_missing"] or [None])[0],
                      "present": resume["stages_present"], "missing": resume["stages_missing"], "failed": resume["failed_stages"]}
    writers = {}
    for p in packs:
        cur = writers.get(p["writer"])
        if cur is None or p["_ts"] > cur["_ts"]:
            writers[p["writer"]] = p
    models_used = sorted({m for r in runs for m in r.get("models", [])} | set(models.values()))
    return {"slug": slug, "title": story.get("title") or slug, "language": story.get("language"),
            "output_language": story.get("output_language"), "rating": story.get("rating"),
            "schema_version": story.get("schema_version"), "folder": str(folder),
            "stage": _stage(src.is_file(), packs, runs, latest, validated, ok_kinds, gate_ok),
            "next_step": {"key": key, "text": text},
            "latest_pack": latest_name, "latest_pack_model": models.get(latest_name) if latest_name else None,
            "resume": resume_out,
            "writers": {w: {"latest_pack": p["name"], "finished": p["finished"], "model": p["model"]} for w, p in writers.items()},
            "packs": [_public(p) for p in packs],
            "runs": {"count": len(runs), "last": ({"run_id": runs[-1]["run_id"], "status": runs[-1]["status"],
                                                   "ended_at": runs[-1]["ended_at"]} if runs else None)},
            "models": models_used, "gates": gates,
            "links": [{k: v for k, v in link.items()} for link in links],
            "warnings": _warnings(folder, story, packs, runs, links)}


def summarize_all(studio) -> list:
    root = Path(studio) / "stories"
    if not root.is_dir():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and rr.SLUG.fullmatch(p.name)):
        try:
            out.append(summarize(studio, d.name))
        except Exception as exc:          # one unreadable story never hides the others
            out.append({"slug": d.name, "error": f"{type(exc).__name__}: {exc}"})
    return out


def _table(rows: list) -> str:
    lines = [f"{'slug':<30} {'stage':<16} {'next step':<22} {'latest pack':<30} warnings"]
    for s in rows:
        if "error" in s:
            lines.append(f"{s['slug']:<30} ERROR {s['error']}")
            continue
        lines.append(f"{s['slug']:<30} {s['stage']:<16} {s['next_step']['key']:<22} {(s['latest_pack'] or '-'):<30} "
                     f"{len(s['warnings'])}")
    return "\n".join(lines)


def _detail(s: dict) -> str:
    out = [f"{s['slug']}: {s['title']}", f"stage: {s['stage']}", f"next: {s['next_step']['key']} - {s['next_step']['text']}",
           f"latest pack: {s['latest_pack'] or '-'} (model {s['latest_pack_model'] or '-'})"]
    if s["resume"]:
        out.append(f"resume: {s['resume']['pack']} from stage {s['resume']['from_stage']} "
                   f"(present {', '.join(s['resume']['present']) or '-'}; missing {', '.join(s['resume']['missing']) or '-'})")
    out.append("writers: " + ("; ".join(f"{w} -> {v['latest_pack']}{' (finished)' if v['finished'] else ''}"
                                        for w, v in s["writers"].items()) or "-"))
    out.append(f"models: {', '.join(s['models']) or '-'}")
    out.append(f"gates: {s['gates'] or '-'}")
    out.append("links: " + ("; ".join(f"{k['kind']} {k.get('pack') or 'story'} {'ok' if k['exists'] else 'MISSING'} {k['path']}"
                                      for k in s["links"]) or "-"))
    out += [f"[{w['level']}] {w['text']}" for w in s["warnings"]]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?", help="one story; without it, every story")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    ap.add_argument("--studio", type=Path, default=STUDIO, help="the anime_studio folder (default: this one)")
    a = ap.parse_args(argv)
    try:
        data = summarize(a.studio, a.slug) if a.slug else summarize_all(a.studio)
    except (ValueError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        print(_detail(data) if a.slug else _table(data))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
