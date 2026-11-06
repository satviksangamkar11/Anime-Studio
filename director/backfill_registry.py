"""Backfill the run registry (story.json, RUNS.jsonl, RUN_REPORT.md) for the stories that were run before it existed.

  python director/backfill_registry.py [--studio PATH] [--only SLUG]

Idempotent: a second run adds nothing (every backfilled line has a fixed event_id; story.json is kept when it exists).
For every stories/<slug>/ folder it reads what is on disk, in order of trust:
  1. saved answers: stage_*_raw.json and raw_response.json (via, model, is_error, finish_reason, chars)
  2. writer logs (*.log in the story folder): the stages each run wrote, its traceback or its "N episodes, M shots" line,
     and "exit=N" when present. An empty log is a run that stopped before its first stage.
  3. file times: used for every time stamp. They are approximate and each story.json source note says so.
A claude run with no saved answer is inferred from the pack folder name (opus) and marked as inferred in the note.
Nothing is read from the network and no model is called."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

import run_registry as rr

STUDIO = Path(__file__).resolve().parents[1]
LOG_STAGE = re.compile(r"^stage ([0-9]{1,2}(?:e[0-9]{1,2})?): ", re.M)
LOG_DONE = re.compile(r"^\d+ episodes, \d+ shots", re.M)
LOG_EXIT = re.compile(r"^exit=(\d+)\s*$", re.M)
PACK_IN_LOG = re.compile(r"(pack_[a-z0-9_-]{1,40})[\\/]")
RAW_FILE = re.compile(r"stage_([0-9]{1,2}(?:e[0-9]{1,2})?)_raw(?:_content_filter_\d+)?\.json")


def _when(path) -> dt.datetime:
    return dt.datetime.fromtimestamp(Path(path).stat().st_mtime).astimezone()


def _iso(when) -> str:
    return when.isoformat(timespec="seconds")


def _order(stage) -> tuple:
    m = re.match(r"(\d+)(?:e(\d+))?", stage or "")
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (99, 0)


def _error_line(text: str) -> str:
    """The last 'SomeError: message' line of a traceback in a log (the exit=N line comes after it)."""
    found = re.findall(r"^[A-Za-z_][\w.]*(?:Error|Exception|Exit)\b.*$", text, re.M)
    return found[-1].strip() if found else ""


def _owner_request(text: str) -> str:
    for line in text.splitlines():
        if line.startswith(("Supplied by the owner", "Fetched from")):
            return re.split(r"(?<=\.)\s", line.strip(), maxsplit=1)[0][:200]
    return ""


def _plan(key, run, kind, stage, status, at, **fields) -> dict:
    return {"key": key, "run": run, "kind": kind, "stage": stage, "status": status, "at": at, "fields": fields}


def _stage_plan(pack, label, raw, end, prev, run, key_prefix):
    """(plan, envelope info, time) for one stage that has a saved answer, or that a log names without one."""
    exists = raw is not None and raw.is_file()
    info = rr.envelope_file(raw) if exists else {}
    at = _when(raw) if exists else end
    plan = _plan(f"{key_prefix}|{label}", run, "analysis_stage", label, "failed" if info.get("failed") else "ok", _iso(at),
                 started_at=_iso(prev) if prev else None, ended_at=_iso(at), pack=pack, via=info.get("via"), model=info.get("model"),
                 effort="medium" if info.get("via") == "claude" else None, files=[f"{pack}/{raw.name}"] if exists else None,
                 chars=info.get("chars"), note="backfilled from the saved answer" + (f"; finish {info['finish']}" if info.get("failed") else ""))
    return plan, info, at


def _route(infos, pack):
    """(model, via, inferred) of a run from its stage answers; 'mixed' when they disagree; the folder name when nothing is saved."""
    models = {i.get("model") for i in infos if i.get("model")}
    vias = {i.get("via") for i in infos if i.get("via")}
    model = next(iter(models)) if len(models) == 1 else ("mixed" if models else None)
    via = next(iter(vias)) if len(vias) == 1 else ("mixed" if vias else None)
    if model is None and pack and "opus" in pack:
        return "opus", "claude", True
    return model, via, False


def _log_runs(story_dir: Path, pack_dirs: list, covered: dict) -> list:
    """pack_dirs: every pack-named folder, empty ones too (a log with no pack name belongs to the only one, if there is one)."""
    plans = []
    for log in sorted(story_dir.glob("*.log")):
        text = log.read_text(encoding="utf-8", errors="replace")
        found = PACK_IN_LOG.findall(text)
        pack = found[0] if found else (pack_dirs[0] if len(pack_dirs) == 1 else None)
        pdir = story_dir / pack if pack else None
        labels = LOG_STAGE.findall(text)
        end = _when(log)
        times = [_when(pdir / f"stage_{l}_raw.json") for l in labels if pdir and (pdir / f"stage_{l}_raw.json").is_file()]
        start = min(times) if times else end
        run = rr.run_id("backfill-" + log.stem, when=start)
        key_prefix = f"log|{log.name}"
        stage_plans, infos, prev = [], [], None
        for label in labels:
            raw = pdir / f"stage_{label}_raw.json" if pdir else None
            plan, info, at = _stage_plan(pack, label, raw, end, prev, run, key_prefix)
            stage_plans.append(plan)
            infos.append(info)
            prev = at
            if pack:
                covered.setdefault(pack, set()).add(f"stage_{label}_raw.json")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        exits = LOG_EXIT.findall(text)
        done = LOG_DONE.search(text)
        if not text.strip():
            status, note = "stopped", "empty log: no output and no result, so the run stopped or was killed before its first stage"
        elif "Traceback" in text:
            status, note = "failed", (_error_line(text) or (lines[-1] if lines else ""))[:300]
        elif done:
            status, note = "ok", done.group(0)
        elif exits and exits[-1] != "0":
            status, note = "failed", f"exit {exits[-1]}"
        elif exits:
            status, note = "ok", "exit 0"
        else:
            status, note = "failed", "log ends without a result line: " + (lines[-1][:200] if lines else "")
        model, via, inferred = _route(infos, pack)
        if inferred:
            note += "; model inferred from the folder name (no saved answer)"
        files = [f"{pack}/{n}" for n in ("PACK.md", "bible.json", "shots.json") if pdir and (pdir / n).is_file()] if status == "ok" else []
        plans.extend(stage_plans)
        plans.append(_plan(f"{key_prefix}|run", run, "analysis_done", None, status, _iso(end), started_at=_iso(start),
                           ended_at=_iso(end), pack=pack, via=via, model=model, effort="medium" if via == "claude" else None,
                           note=note, files=files or None))
    return plans


def _pack_plans(story_dir: Path, packs: list, covered: dict) -> list:
    plans = []
    for pack in packs:
        pdir = story_dir / pack
        raws = sorted(pdir.glob("stage_*_raw*.json"))
        if (pdir / "raw_response.json").is_file():
            raws.append(pdir / "raw_response.json")
        leftover = [r for r in raws if r.name not in covered.get(pack, set())]
        if not leftover:
            continue
        start = min(_when(r) for r in leftover)
        run = rr.run_id("backfill-" + pack, when=start)
        infos, stage_plans = [], []
        for raw in sorted(leftover, key=lambda r: _order(RAW_FILE.fullmatch(r.name).group(1) if RAW_FILE.fullmatch(r.name) else None)):
            if raw.name == "raw_response.json":
                label = "single"
            elif RAW_FILE.fullmatch(raw.name):
                label = RAW_FILE.fullmatch(raw.name).group(1)
            else:
                continue
            plan, info, _ = _stage_plan(pack, label, raw, _when(raw), None, run, f"raw|{pack}|{raw.name}")
            stage_plans.append(plan)
            infos.append(info)
        finished = rr.is_finished(pdir)
        model, via, inferred = _route(infos, pack)
        if finished:
            summary = rr.pack_summary(pdir) or {}
            note = f"{summary.get('reels', '-')} reels, {summary.get('shots', '-')} shots (from shots.json)"
            status = "ok"
        else:
            note, status = "no PACK.md: the run did not finish", "started"
        if inferred:
            note += "; model inferred from the folder name (no saved answer)"
        end = max(_when(r) for r in leftover + [pdir / "PACK.md"] if r.is_file())
        plans.extend(stage_plans)
        plans.append(_plan(f"raw|{pack}|run", run, "analysis_done", None, status, _iso(end), started_at=_iso(start), ended_at=_iso(end),
                           pack=pack, via=via, model=model, effort="medium" if via == "claude" else None, note=note,
                           files=[f"{pack}/{n}" for n in ("PACK.md", "bible.json", "shots.json") if (pdir / n).is_file()] if finished else None))
    return plans


def _story_plans(story_dir: Path, text: str) -> list:
    plans = []
    source = story_dir / "SOURCE.md"
    if not source.is_file():
        return plans
    saved = _when(source)
    plans.append(_plan("SOURCE.md", rr.run_id("backfill-story-save", when=saved), "story_saved", None, "ok", _iso(saved),
                       files=["SOURCE.md"], chars=rr.transcript_chars(text), note="backfilled from the SOURCE.md file time"))
    found = re.search(r"Fetched from (https?://\S+)", text)
    if found:
        plans.append(_plan("transcript", rr.run_id("backfill-transcript", when=saved), "transcript_fetched", None, "ok", _iso(saved),
                           url=found.group(1).rstrip(".,)"), chars=rr.transcript_chars(text), files=["SOURCE.md"],
                           note="backfilled from the SOURCE.md file time"))
    return plans


def backfill_story(story_dir: Path) -> dict:
    slug = story_dir.name
    result = {"slug": slug, "story": "kept", "added": 0, "already": 0, "runs": []}
    source = story_dir / "SOURCE.md"
    text = source.read_text(encoding="utf-8", errors="replace") if source.is_file() else ""
    if source.is_file() and rr.read_story(story_dir) is None:
        saved = _when(source)
        meta = rr.detect_source(text, saved_at=_iso(saved))
        meta["note"] = "backfilled: times are file times"
        if meta["type"] == "youtube":
            meta["fetched_at"] = _iso(saved)
        rr.update_story(story_dir, title=rr.title_from_source(text, slug), language=rr.detect_language(text), source=meta,
                        owner_request_text=_owner_request(text), tags=["backfilled"], created_at=_iso(saved))
        result["story"] = "created"
    covered: dict = {}
    packs = rr.pack_folders(story_dir)
    pack_dirs = sorted(p.name for p in story_dir.iterdir() if p.is_dir() and rr.PACK.fullmatch(p.name))
    plans = _story_plans(story_dir, text) + _log_runs(story_dir, pack_dirs, covered) + _pack_plans(story_dir, packs, covered)
    existing = {e.get("event_id") for e in rr.read_events(story_dir)}
    for p in sorted(plans, key=lambda p: (p["fields"].get("started_at") or p["at"], p["at"])):
        event_id = "bf-" + hashlib.sha1(f"{slug}|{p['key']}".encode("utf-8")).hexdigest()[:16]
        if event_id in existing:
            result["already"] += 1
            continue
        rr.append_event(story_dir, p["run"], p["kind"], p["stage"], p["status"], at=p["at"], event_id=event_id, **p["fields"])
        existing.add(event_id)
        result["added"] += 1
    result["runs"] = sorted({p["run"] for p in plans})
    rr.write_report(story_dir)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--studio", type=Path, default=STUDIO, help="the anime_studio folder (default: this one)")
    ap.add_argument("--only", default="", help="one story slug")
    a = ap.parse_args(argv)
    root = a.studio / "stories"
    if not root.is_dir():
        print(f"no stories folder at {root}")
        return 1
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and rr.SLUG.fullmatch(p.name)):
        if a.only and folder.name != a.only:
            continue
        r = backfill_story(folder)
        print(f"{r['slug']}: story.json {r['story']}; RUNS.jsonl +{r['added']} events ({r['already']} already there); "
              f"runs {', '.join(r['runs']) or 'none'}; RUN_REPORT.md written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
