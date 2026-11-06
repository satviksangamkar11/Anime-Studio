import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple


def _registry():
    """director/run_registry.py (the run log of each story); None when it cannot be imported (the gate is still recorded)."""
    try:
        director = str(Path(__file__).resolve().parents[1] / "director")
        if director not in sys.path:
            sys.path.append(director)
        import run_registry
        return run_registry
    except Exception:
        return None

# Constants
STAGES = ["story", "analysis", "images", "readout", "render", "export"]
GATES = {"A": "analysis", "B": "images", "C": "readout", "D": "render"}
GATE_ORDER = ["A", "B", "C", "D"]


class GateError(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# Project persistence
# --------------------------------------------------------------------------- #
def load_project(runs: Path) -> Dict[str, Any]:
    project_file = runs / "project.json"
    default = {
        "story_slug": None,
        "pack": None,
        "images_dir": None,
        "results_dir": None,
        "takes": 3,
    }
    if not project_file.is_file():
        return default
    try:
        with project_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in default.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return default


def save_project(runs: Path, project: Dict[str, Any]) -> None:
    runs.mkdir(parents=True, exist_ok=True)
    project_file = runs / "project.json"
    with project_file.open("w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# Approvals
# --------------------------------------------------------------------------- #
def read_approvals(runs: Path) -> List[Dict[str, Any]]:
    approvals_file = runs / "approvals.jsonl"
    if not approvals_file.is_file():
        return []
    records = []
    with approvals_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records.append(rec)
            except Exception:
                continue
    return records


def record_gate(
    runs: Path,
    gate: str,
    decision: str,
    who: str,
    note: str,
    now: Optional[datetime] = None,
    studio: Optional[Path] = None,
    story_slug: Optional[str] = None,
) -> Dict[str, Any]:
    runs.mkdir(parents=True, exist_ok=True)
    approvals_file = runs / "approvals.jsonl"
    timestamp = (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
    record = {
        "time": timestamp,
        "gate": gate,
        "decision": decision,
        "by": who,
        "note": note,
    }
    with approvals_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    # the decision also goes into the story's run log when the story is known (best effort: never stops the gate)
    rr = _registry() if studio is not None and story_slug else None
    if rr is not None:
        rr.record_gate_decision(Path(studio) / "stories" / story_slug, gate, decision, note, who)
    return record


# --------------------------------------------------------------------------- #
# Facts computation
# --------------------------------------------------------------------------- #
def _safe_read_json(path: Path) -> Optional[Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def facts(studio: Path, runs: Path) -> Dict[str, Any]:
    project = load_project(runs)
    slug = project.get("story_slug")
    pack = project.get("pack")
    images_dir = project.get("images_dir")
    results_dir = project.get("results_dir")
    takes = project.get("takes", 3)

    story_saved = False
    pack_stage_files = 0
    shots_ready = False
    n_shots = 0
    expected_images = 0
    finals = 0
    pending = 0
    reviewed = 0
    clips_home = 0
    planned_clips = 0

    if slug:
        story_dir = studio / "stories" / slug
        if (story_dir / "SOURCE.md").is_file():
            story_saved = True

    if slug and pack:
        pack_dir = studio / "stories" / slug / pack
        if pack_dir.is_dir():
            pack_stage_files = len(list(pack_dir.glob("stage_*_raw.json")))
            shots_data = _safe_read_json(pack_dir / "shots.json")
            bible_data = _safe_read_json(pack_dir / "bible.json")
            if isinstance(shots_data, list) and isinstance(bible_data, dict):
                shots_ready = True
                n_shots = len(shots_data)
                expected_images = 2 * n_shots
                planned_clips = n_shots * takes

    if images_dir:
        img_path = Path(images_dir)
        if img_path.is_dir():
            final_dir = img_path / "final"
            if final_dir.is_dir():
                finals = len(list(final_dir.glob("*__final.png")))
            shots_dir = img_path / "shots"
            if shots_dir.is_dir():
                reviewed = len(list(shots_dir.glob("*__review.json")))

            dq_file = img_path / "download_queue.jsonl"
            fl_file = img_path / "flow_log.jsonl"
            dq_entries: Dict[Tuple[str, int], Dict] = {}
            if dq_file.is_file():
                with dq_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            shot_id = entry.get("shot_id")
                            version = entry.get("version")
                            image_id = entry.get("image_id")
                            if shot_id is not None and version is not None and image_id is not None:
                                dq_entries[(shot_id, version)] = entry
                        except Exception:
                            continue
            fl_set = set()
            if fl_file.is_file():
                with fl_file.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            img_id = entry.get("image_id")
                            ver = entry.get("version")
                            if img_id is not None and ver is not None:
                                fl_set.add((img_id, ver))
                        except Exception:
                            continue
            for entry in dq_entries.values():
                key = (entry["image_id"], entry["version"])
                if key not in fl_set:
                    pending += 1

    if results_dir:
        res_path = Path(results_dir)
        if res_path.is_dir():
            clips_home = len(list(res_path.rglob("*.mp4")))

    return {
        "story_saved": story_saved,
        "pack_stage_files": pack_stage_files,
        "shots_ready": shots_ready,
        "n_shots": n_shots,
        "expected_images": expected_images,
        "finals": finals,
        "pending": pending,
        "reviewed": reviewed,
        "clips_home": clips_home,
        "planned_clips": planned_clips,
    }


# --------------------------------------------------------------------------- #
# Pipeline state
# --------------------------------------------------------------------------- #
def _latest_decisions(approvals: List[Dict]) -> Dict[str, Optional[str]]:
    latest = {g: None for g in GATE_ORDER}
    for rec in approvals:
        gate = rec.get("gate")
        decision = rec.get("decision")
        if gate in latest and decision in ("approve", "reject"):
            latest[gate] = decision
    return latest


def _cascade_approved(latest: Dict[str, Optional[str]]) -> Dict[str, bool]:
    cascade = {}
    approved_so_far = True
    for g in GATE_ORDER:
        if approved_so_far and latest[g] == "approve":
            cascade[g] = True
        else:
            cascade[g] = False
            approved_so_far = False
    return cascade


def pipeline_state(studio: Path, runs: Path, now: Optional[datetime] = None) -> Dict[str, Any]:
    project = load_project(runs)
    f = facts(studio, runs)
    approvals = read_approvals(runs)
    latest = _latest_decisions(approvals)
    cascade = _cascade_approved(latest)

    stages = []

    # Story
    story_status = "done" if f["story_saved"] else "ready"
    stages.append({
        "id": "story",
        "title": "Story",
        "status": story_status,
        "detail": "SOURCE.md saved" if f["story_saved"] else "Story not saved",
        "progress": None,
    })

    # Analysis
    if not f["story_saved"]:
        analysis_status = "locked"
        detail = "Waiting for story"
        progress = None
    elif f["pack_stage_files"] > 0 and not f["shots_ready"]:
        analysis_status = "ready"
        detail = f"{f['pack_stage_files']} stages saved, run again to resume"
        progress = {"done": f["pack_stage_files"], "total": None}
    elif f["shots_ready"]:
        if cascade["A"]:
            analysis_status = "approved"
            detail = "Gate A approved"
            progress = None
        elif latest["A"] == "reject":
            # rejected gate re-opens when stage is complete again
            analysis_status = "rejected"
            detail = "Gate A rejected, rerun the stage or decide again"
            progress = None
        else:
            analysis_status = "waiting_approval"
            detail = "Shots ready, awaiting Gate A"
            progress = None
    else:
        analysis_status = "ready"
        detail = "Ready for analysis"
        progress = None
    stages.append({
        "id": "analysis",
        "title": "Analysis",
        "status": analysis_status,
        "detail": detail,
        "progress": progress,
    })

    # Images
    if not cascade["A"]:
        images_status = "locked"
        detail = "Waiting for Gate A"
        progress = None
    elif f["pending"] > 0 or (f["finals"] > 0 and f["finals"] < f["expected_images"]):
        images_status = "running"
        detail = f"Finals: {f['finals']}/{f['expected_images']}, pending: {f['pending']}"
        progress = {"done": f["finals"], "total": f["expected_images"]}
    elif f["finals"] == 0:
        images_status = "ready"
        detail = "No finals yet"
        progress = None
    elif f["finals"] >= f["expected_images"] and f["pending"] == 0:
        if cascade["B"]:
            images_status = "approved"
            detail = "Gate B approved"
            progress = None
        elif latest["B"] == "reject":
            images_status = "rejected"
            detail = "Gate B rejected, rerun the stage or decide again"
            progress = None
        else:
            images_status = "waiting_approval"
            detail = "All finals ready, awaiting Gate B"
            progress = None
    else:
        images_status = "ready"
        detail = "Ready for images"
        progress = None
    stages.append({
        "id": "images",
        "title": "Images",
        "status": images_status,
        "detail": detail,
        "progress": progress,
    })

    # Readout
    if not cascade["B"]:
        readout_status = "locked"
        detail = "Waiting for Gate B"
    elif cascade["C"]:
        readout_status = "approved"
        detail = "Gate C approved"
    elif latest["C"] == "reject":
        readout_status = "rejected"
        detail = "Gate C rejected, rerun the stage or decide again"
    else:
        readout_status = "waiting_approval"
        detail = "Awaiting Gate C (START)"
    stages.append({
        "id": "readout",
        "title": "Read-out",
        "status": readout_status,
        "detail": detail,
        "progress": None,
    })

    # Render
    if not cascade["C"]:
        render_status = "locked"
        detail = "Waiting for Gate C"
        progress = None
    elif f["clips_home"] == 0:
        render_status = "ready"
        detail = "No clips yet"
        progress = None
    elif f["clips_home"] < f["planned_clips"]:
        render_status = "running"
        detail = f"Clips: {f['clips_home']}/{f['planned_clips']}"
        progress = {"done": f["clips_home"], "total": f["planned_clips"]}
    elif f["clips_home"] >= f["planned_clips"] and f["planned_clips"] > 0:
        if cascade["D"]:
            render_status = "approved"
            detail = "Gate D approved"
            progress = None
        elif latest["D"] == "reject":
            render_status = "rejected"
            detail = "Gate D rejected, rerun the stage or decide again"
            progress = None
        else:
            render_status = "waiting_approval"
            detail = "All clips home, awaiting Gate D"
            progress = None
    else:
        render_status = "ready"
        detail = "Ready for render"
        progress = None
    stages.append({
        "id": "render",
        "title": "Render",
        "status": render_status,
        "detail": detail,
        "progress": progress,
    })

    # Export
    if not cascade["D"]:
        export_status = "locked"
        detail = "Waiting for Gate D"
    else:
        export_status = "ready"
        detail = "Ready for export"
    stages.append({
        "id": "export",
        "title": "Export",
        "status": export_status,
        "detail": detail,
        "progress": None,
    })

    # Gates
    gates = []
    stage_status_map = {s["id"]: s["status"] for s in stages}
    for g in GATE_ORDER:
        stage_id = GATES[g]
        stage_status = stage_status_map.get(stage_id, "locked")
        if cascade[g]:
            state = "approved"
        elif latest[g] == "reject" and stage_status == "rejected":
            state = "rejected"
        elif stage_status == "waiting_approval":
            state = "open"
        else:
            state = "locked"
        by = None
        at = None
        note = None
        for rec in reversed(approvals):
            if rec.get("gate") == g:
                by = rec.get("by")
                at = rec.get("time")
                note = rec.get("note")
                break
        gates.append({
            "id": g,
            "title": f"Gate {g}",
            "stage": stage_id,
            "state": state,
            "by": by,
            "at": at,
            "note": note,
        })

    current = "story"
    for s in stages:
        if s["status"] not in ("approved", "done"):
            current = s["id"]
            break

    return {
        "project": project,
        "stages": stages,
        "gates": gates,
        "current": current,
    }


# --------------------------------------------------------------------------- #
# Apply gate
# --------------------------------------------------------------------------- #
def apply_gate(
    studio: Path,
    runs: Path,
    gate: str,
    decision: str,
    note: str,
    confirm: Optional[str] = None,
    who: str = "owner",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    if decision not in ("approve", "reject"):
        raise GateError("decision must be 'approve' or 'reject'", 400)

    state = pipeline_state(studio, runs, now)
    gate_info = next((g for g in state["gates"] if g["id"] == gate), None)
    if not gate_info:
        raise GateError("invalid gate", 400)

    # a rejected gate can be decided again (approve after a fix, or reject again)
    if gate_info["state"] not in ("open", "rejected"):
        raise GateError("gate is locked", 409)

    # note: required for a reject, optional for an approve; always printable, no newlines, max 300 chars
    note = note or ""
    if decision == "reject" and not note.strip():
        raise GateError("note must not be empty", 400)
    if len(note) > 300:
        raise GateError("note too long (max 300 chars)", 400)
    if any(c in note for c in "\r\n"):
        raise GateError("note must not contain newlines", 400)
    if not all(c.isprintable() for c in note):
        raise GateError("note must contain only printable characters", 400)

    if gate == "C" and decision == "approve":
        if confirm != "START":
            raise GateError("Gate C requires confirm='START'", 400)

    record_gate(runs, gate, decision, who, note, now, studio=studio, story_slug=load_project(runs).get("story_slug"))
    new_state = pipeline_state(studio, runs, now)
    new_gate = next(g for g in new_state["gates"] if g["id"] == gate)
    return new_gate


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
def summary(studio: Path, runs: Path) -> Dict[str, Any]:
    project = load_project(runs)
    slug = project.get("story_slug")
    pack = project.get("pack")
    takes = project.get("takes", 3)

    if not slug or not pack:
        return _empty_summary()

    pack_dir = studio / "stories" / slug / pack
    shots_data = _safe_read_json(pack_dir / "shots.json")
    bible_data = _safe_read_json(pack_dir / "bible.json")

    if not isinstance(shots_data, list) or not isinstance(bible_data, dict):
        return _empty_summary()

    episodes_map: Dict[int, Dict[str, Any]] = {}
    total_seconds = 0.0
    modes: Dict[str, int] = {}
    shot_ids = set()
    duplicate_ids = False
    all_have_seconds = True
    all_have_episode = True

    for shot in shots_data:
        sid = shot.get("id")
        if sid in shot_ids:
            duplicate_ids = True
        shot_ids.add(sid)
        ep = shot.get("episode")
        sec = shot.get("seconds", 0)
        if isinstance(sec, bool) or not isinstance(sec, (int, float)):
            sec = 0
        mode = shot.get("mode", "unknown")
        if ep is None:
            all_have_episode = False
            # skip shots with no episode for episode grouping
            continue
        if sec <= 0:
            all_have_seconds = False
        total_seconds += sec
        modes[mode] = modes.get(mode, 0) + 1
        if ep not in episodes_map:
            episodes_map[ep] = {"shots": 0, "seconds": 0.0}
        episodes_map[ep]["shots"] += 1
        episodes_map[ep]["seconds"] += sec

    episodes_list = [
        {"episode": ep, "n": ep, "shots": v["shots"], "seconds": v["seconds"]}
        for ep, v in sorted(episodes_map.items())
    ]

    characters = [c.get("name") for c in bible_data.get("characters", []) if c.get("name")]
    places = [e.get("name") for e in bible_data.get("environments", []) if e.get("name")]
    props_raw = bible_data.get("props", [])
    props = []
    for p in props_raw:
        if p.get("name"):
            props.append(p["name"])
        elif p.get("id"):
            props.append(p["id"])

    f = facts(studio, runs)

    planned_clips = f["planned_clips"]
    minutes = round(7 + planned_clips * 2.2 + 5, 1)
    g4_units = round(10.05 * minutes / 60, 1)

    checks = [
        {"name": "shots.json present", "ok": True, "detail": "shots.json found and parsed"},
        {"name": "bible.json present", "ok": True, "detail": "bible.json found and parsed"},
        {"name": "every shot has seconds>0", "ok": all_have_seconds, "detail": "all shots have positive seconds" if all_have_seconds else "some shots missing or zero seconds"},
        {"name": "every shot has an episode", "ok": all_have_episode, "detail": "all shots have episode" if all_have_episode else "some shots missing episode"},
        {"name": "at least one episode", "ok": len(episodes_map) > 0, "detail": f"{len(episodes_map)} episodes" if episodes_map else "no episodes"},
        {"name": "no duplicate shot ids", "ok": not duplicate_ids, "detail": "no duplicate shot ids" if not duplicate_ids else "duplicate shot ids found"},
    ]

    warnings = []
    for ep_data in episodes_list:
        sec = ep_data["seconds"]
        # warn only above 80 s (the 55..80 band is the target; short episodes are shown in the table)
        if sec > 80:
            warnings.append(f"Episode {ep_data['episode']} total seconds {sec:.1f} above the 80 s limit")
    if f["finals"] < f["expected_images"]:
        warnings.append(f"finals {f['finals']} < expected images {f['expected_images']}")

    return {
        "reels": len(episodes_map),
        "episodes": episodes_list,
        "shots": len(shots_data),
        "seconds": total_seconds,
        "characters": characters,
        "places": places,
        "props": props,
        "modes": modes,
        "images": {
            "expected": f["expected_images"],
            "final": f["finals"],
            "pending": f["pending"],
            "reviewed": f["reviewed"],
        },
        "video": {
            "shots": f["n_shots"],
            "takes": takes,
            "clips_home": f["clips_home"],
            "planned_clips": planned_clips,
        },
        "estimate": {
            "g4_units": g4_units,
            "minutes": minutes,
        },
        "checks": checks,
        "warnings": warnings,
    }


def _empty_summary() -> Dict[str, Any]:
    return {
        "reels": 0,
        "episodes": [],
        "shots": 0,
        "seconds": 0.0,
        "characters": [],
        "places": [],
        "props": [],
        "modes": {},
        "images": {"expected": 0, "final": 0, "pending": 0, "reviewed": 0},
        "video": {"shots": 0, "takes": 0, "clips_home": 0, "planned_clips": 0},
        "estimate": {"g4_units": 0.0, "minutes": 0.0},
        "checks": [],
        "warnings": ["no pack yet"],
    }
