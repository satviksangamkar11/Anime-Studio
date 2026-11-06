"""Pipeline state for the wizard: stages, gates scoped by story and pack, summary numbers, validator, H3 plan bridge.

Files read: stories/<slug>/<pack>/*, stories/<slug>/story.json, ui/runs/*. Files written here: ui/runs/project.json,
ui/runs/approvals.jsonl, ui/runs/validation/*.json, <pack>/render/human_choices.jsonl (all atomic or append-only).
Gates: a decision is recorded with its story and pack; a record without them (legacy) never counts. The project pointer
(runs/project.json) is the scope the wizard works on: a gate call for another story or pack gets a 409."""
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STUDIO = Path(__file__).resolve().parents[1]

# Constants
STAGES = ["story", "analysis", "images", "readout", "render", "export"]
GATES = {"A": "analysis", "B": "images", "C": "readout", "D": "render"}
GATE_ORDER = ["A", "B", "C", "D"]
LANGS = ("en", "hi", "mr")
PROJECT_DEFAULT = {"story_slug": None, "pack": None, "images_dir": None, "results_dir": None, "takes": 3}
# expected images per shot by route (V4 rows). Legacy rows (no route) keep the old 2 per shot.
ROUTE_IMAGES = {"FL2VA": 2, "I2VA": 1, "REF2VA": 1, "T2VA": 0, "L2VA": 0}
LEGACY_IMAGES_PER_SHOT = 2


class GateError(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# Imports (lazy, so a missing module is a clear result, not a crash)
# --------------------------------------------------------------------------- #
def _registry():
    """director/run_registry.py (the run log of each story); None when it cannot be imported (the gate is still recorded)."""
    try:
        director = str(STUDIO / "director")
        if director not in sys.path:
            sys.path.append(director)
        import run_registry
        return run_registry
    except Exception:
        return None


def _director(name: str):
    d = str(STUDIO / "director")
    if d not in sys.path:
        sys.path.append(d)
    return importlib.import_module(name)


def _h3(name: str):
    root = str(STUDIO)
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module(f"h3.{name}")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _safe_read_json(path: Path) -> Optional[Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def bible_items(bible: Any, key: str) -> List[Dict[str, Any]]:
    """One bible section as a list of dicts. The V4 bible is a dict keyed by id; the legacy bible is a list."""
    sec = bible.get(key) if isinstance(bible, dict) else None
    if isinstance(sec, dict):
        return [dict(v, id=v.get("id", k)) if isinstance(v, dict) else {"id": k} for k, v in sec.items()]
    if isinstance(sec, list):
        return [x for x in sec if isinstance(x, dict)]
    return []


def shot_route(shot: Dict[str, Any]) -> str:
    """V4 rows keep the route in 'route'; legacy rows keep it in 'mode'."""
    return str(shot.get("route") or shot.get("mode") or "unknown")


def shot_seconds(shot: Dict[str, Any]) -> float:
    """V4 rows: editorial_duration_sec; legacy rows: seconds."""
    v = shot.get("editorial_duration_sec") or shot.get("seconds")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 0.0
    return float(v)


def images_for_shot(shot: Dict[str, Any]) -> int:
    if shot.get("route") is None:
        return LEGACY_IMAGES_PER_SHOT
    return ROUTE_IMAGES.get(str(shot.get("route")).upper(), LEGACY_IMAGES_PER_SHOT)


def read_story_json(studio: Path, slug: str) -> Dict[str, Any]:
    doc = _safe_read_json(Path(studio) / "stories" / slug / "story.json")
    return doc if isinstance(doc, dict) else {}


def update_story_json(studio: Path, slug: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """Changes only the keys given in stories/<slug>/story.json (created when missing). Atomic."""
    folder = Path(studio) / "stories" / slug
    doc = read_story_json(studio, slug)
    doc.update(changes)
    atomic_write(folder / "story.json", json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return doc


def output_languages(studio: Path, slug: Optional[str]) -> List[str]:
    if not slug:
        return []
    langs = read_story_json(studio, slug).get("output_languages")
    return [x for x in langs if x in LANGS] if isinstance(langs, list) else []


# --------------------------------------------------------------------------- #
# Project pointer
# --------------------------------------------------------------------------- #
def load_project(runs: Path) -> Dict[str, Any]:
    """runs/project.json. A file that cannot be read gives the empty pointer plus an 'error' note (never a silent default)."""
    default = dict(PROJECT_DEFAULT)
    project_file = runs / "project.json"
    if not project_file.is_file():
        return default
    try:
        data = json.loads(project_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except (OSError, ValueError) as exc:
        default["error"] = f"project.json cannot be read ({type(exc).__name__}): fix or delete the file"
        return default
    for k, v in PROJECT_DEFAULT.items():
        data.setdefault(k, v)
    return data


def save_project(runs: Path, project: Dict[str, Any]) -> None:
    clean = {k: v for k, v in project.items() if k != "error"}
    atomic_write(runs / "project.json", json.dumps(clean, ensure_ascii=False, indent=2))


def scope(runs: Path, story: Optional[str] = None, pack: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """(story, pack, project). Without arguments the scope is the project pointer."""
    project = load_project(runs)
    if story is None and pack is None:
        return project.get("story_slug"), project.get("pack"), project
    return story, pack, project


# --------------------------------------------------------------------------- #
# Approvals (scoped by story and pack)
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
                records.append(json.loads(line))
            except Exception:
                continue
    return records


def scoped_approvals(approvals: List[Dict[str, Any]], story: Optional[str], pack: Optional[str]) -> List[Dict[str, Any]]:
    """Only records written for this story and pack. Legacy records (no story) never match."""
    if not story or not pack:
        return []
    return [r for r in approvals if isinstance(r, dict) and r.get("story") == story and r.get("pack") == pack]


def record_gate(
    runs: Path,
    gate: str,
    decision: str,
    who: str,
    note: str,
    now: Optional[datetime] = None,
    studio: Optional[Path] = None,
    story_slug: Optional[str] = None,
    pack: Optional[str] = None,
) -> Dict[str, Any]:
    runs.mkdir(parents=True, exist_ok=True)
    approvals_file = runs / "approvals.jsonl"
    timestamp = (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
    record = {"time": timestamp, "gate": gate, "decision": decision, "by": who, "note": note,
              "story": story_slug, "pack": pack}
    with approvals_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    # the decision also goes into the story's run log when the story is known (best effort: never stops the gate)
    rr = _registry() if studio is not None and story_slug else None
    if rr is not None:
        try:
            rr.record_gate_decision(Path(studio) / "stories" / story_slug, gate, decision, note, who)
        except Exception as exc:   # best effort: the decision is already in approvals.jsonl
            print(f"run registry: gate note skipped ({type(exc).__name__}: {str(exc)[:200]})", file=sys.stderr)
    return record


# --------------------------------------------------------------------------- #
# Validator (director/pack_validator.py, reads only) and its stored report
# --------------------------------------------------------------------------- #
def pack_mode(shots: Any) -> str:
    """'v4' when the shot rows carry a route, else 'legacy' (old-format packs)."""
    if isinstance(shots, list) and any(isinstance(s, dict) and "route" in s for s in shots):
        return "v4"
    return "legacy"


def run_validator(studio: Path, slug: str, pack: str, legacy: Optional[bool] = None) -> Dict[str, Any]:
    pack_dir = Path(studio) / "stories" / slug / pack
    if legacy is None:
        legacy = pack_mode(_safe_read_json(pack_dir / "shots.json")) == "legacy"
    try:
        rep = _director("pack_validator").validate_pack(str(pack_dir), legacy=legacy)
    except Exception as exc:   # a crash in the validator is a failed check, never a crash of the page
        rep = {"ok": False, "errors": [{"code": "VAL-EXC", "where": "pack", "message": f"validator could not run: {type(exc).__name__}"}],
               "warnings": [], "stats": {}}
    return {"ok": bool(rep.get("ok")), "errors": list(rep.get("errors") or []), "warnings": list(rep.get("warnings") or []),
            "stats": rep.get("stats") or {}, "mode": "legacy" if legacy else "v4", "exit": 0 if rep.get("ok") else 1,
            "story": slug, "pack": pack}


def _validation_file(runs: Path, slug: str, pack: str) -> Path:
    return runs / "validation" / f"{slug}__{pack}.json"


def save_validation(runs: Path, report: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(report, time=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    atomic_write(_validation_file(runs, report["story"], report["pack"]), json.dumps(doc, ensure_ascii=False, indent=1))
    return doc


def load_validation(runs: Path, slug: str, pack: str) -> Optional[Dict[str, Any]]:
    doc = _safe_read_json(_validation_file(runs, slug, pack))
    return doc if isinstance(doc, dict) else None


def validator_problems(studio: Path, slug: str, pack: str) -> List[str]:
    rep = run_validator(studio, slug, pack)
    return [f"{e.get('code')} {e.get('where')}" for e in rep["errors"]] if not rep["ok"] else []


# --------------------------------------------------------------------------- #
# H3 plan bridge (reads the pack, writes nothing: plan_pipeline is a dry run)
# --------------------------------------------------------------------------- #
def h3_plan(studio: Path, slug: str, pack: str) -> Dict[str, Any]:
    """convert_pack + plan_pipeline on the pack. prepare_ready = no convert problems and the pre-render steps are ready."""
    out = {"ready": False, "problems": [], "steps": [], "languages": [], "error": None, "groups": 0, "episodes": []}
    pack_dir = Path(studio) / "stories" / slug / pack
    try:
        conv = _h3("v4_to_h3")
        rc = _h3("render_controller")
        res = conv.convert_pack(str(pack_dir))
        out["problems"] = list(res.get("problems") or [])
        if res.get("story") is None:
            return out
        story = res["story"]
        groups = rc.select_scope(story, "all")
        out["groups"] = len(groups)
        out["episodes"] = [{"id": g["episode"]["episode_id"], "shots": [sh["id"] for sh in g["shots"]]} for g in groups]
        plan = rc.plan_pipeline(story, groups, str(pack_dir / "render"))
        out["steps"] = plan["steps"]
        out["languages"] = plan["languages"]
        pre = {s["id"]: s["status"] for s in plan["steps"]}
        out["ready"] = not out["problems"] and all(pre.get(k) == "ready" for k in ("lint", "route", "prompt"))
    except Exception as exc:
        out["error"] = f"H3 plan not available ({type(exc).__name__}: {str(exc)[:160]})"
    return out


def read_step9(pack_dir: Path) -> Dict[str, Any]:
    """render/step9_qc.json written by a Step 9 runner. None of them exists yet: 'not run' (fails closed)."""
    doc = _safe_read_json(Path(pack_dir) / "render" / "step9_qc.json")
    if not isinstance(doc, dict) or doc.get("status") not in ("pass", "fail"):
        return {"status": "not run", "checks": []}
    return {"status": doc["status"], "checks": list(doc.get("checks") or [])}


def gate_d_problems(studio: Path, slug: str, pack: str) -> List[str]:
    """Gate D approve needs Step 9 QC pass and every selected language's audio plan ready."""
    probs = []
    step9 = read_step9(Path(studio) / "stories" / slug / pack)
    if step9["status"] != "pass":
        probs.append(f"Step 9 QC is {step9['status']}")
    plan = h3_plan(studio, slug, pack)
    if plan["error"]:
        probs.append(plan["error"])
    gd = next((s for s in plan["steps"] if s["id"] == "gate_d"), None)
    if gd is None:
        probs.append("Gate D plan not available")
    elif gd["status"] != "ready":
        probs += gd["reasons"] or ["Gate D not ready"]
    return probs


# --------------------------------------------------------------------------- #
# Facts computation
# --------------------------------------------------------------------------- #
def facts(studio: Path, runs: Path, story: Optional[str] = None, pack: Optional[str] = None) -> Dict[str, Any]:
    slug, pack, project = scope(runs, story, pack)
    current = project.get("story_slug") == slug and project.get("pack") == pack
    images_dir = project.get("images_dir") if current else None
    results_dir = project.get("results_dir") if current else None
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
        if (Path(studio) / "stories" / slug / "SOURCE.md").is_file():
            story_saved = True

    if slug and pack:
        pack_dir = Path(studio) / "stories" / slug / pack
        if pack_dir.is_dir():
            pack_stage_files = len(list(pack_dir.glob("stage_*_raw.json")))
            shots_data = _safe_read_json(pack_dir / "shots.json")
            bible_data = _safe_read_json(pack_dir / "bible.json")
            if isinstance(shots_data, list) and isinstance(bible_data, dict):
                shots_ready = True
                rows = [s for s in shots_data if isinstance(s, dict)]
                n_shots = len(shots_data)
                expected_images = sum(images_for_shot(s) for s in rows)
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
                if (entry["image_id"], entry["version"]) not in fl_set:
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


def pipeline_state(studio: Path, runs: Path, now: Optional[datetime] = None,
                   story: Optional[str] = None, pack: Optional[str] = None) -> Dict[str, Any]:
    slug, pack, project = scope(runs, story, pack)
    f = facts(studio, runs, slug, pack)
    approvals = scoped_approvals(read_approvals(runs), slug, pack)
    latest = _latest_decisions(approvals)
    cascade = _cascade_approved(latest)

    stages = []

    # Story
    stages.append({
        "id": "story",
        "title": "Story",
        "status": "done" if f["story_saved"] else "ready",
        "detail": "SOURCE.md saved" if f["story_saved"] else "Story not saved",
        "progress": None,
    })

    # Analysis
    if not f["story_saved"]:
        analysis_status, detail, progress = "locked", "Waiting for story", None
    elif f["pack_stage_files"] > 0 and not f["shots_ready"]:
        analysis_status = "ready"
        detail = f"{f['pack_stage_files']} stages saved, run again to resume"
        progress = {"done": f["pack_stage_files"], "total": None}
    elif f["shots_ready"]:
        progress = None
        if cascade["A"]:
            analysis_status, detail = "approved", "Gate A approved"
        elif latest["A"] == "reject":
            analysis_status, detail = "rejected", "Gate A rejected, rerun the stage or decide again"
        else:
            analysis_status, detail = "waiting_approval", "Shots ready, awaiting Gate A"
    else:
        analysis_status, detail, progress = "ready", "Ready for analysis", None
    stages.append({"id": "analysis", "title": "Analysis", "status": analysis_status, "detail": detail, "progress": progress})

    # Images
    if not cascade["A"]:
        images_status, detail, progress = "locked", "Waiting for Gate A", None
    elif f["pending"] > 0 or (f["finals"] > 0 and f["finals"] < f["expected_images"]):
        images_status = "running"
        detail = f"Finals: {f['finals']}/{f['expected_images']}, pending: {f['pending']}"
        progress = {"done": f["finals"], "total": f["expected_images"]}
    elif f["finals"] == 0:
        images_status, detail, progress = "ready", "No finals yet", None
    elif f["finals"] >= f["expected_images"] and f["pending"] == 0:
        progress = None
        if cascade["B"]:
            images_status, detail = "approved", "Gate B approved"
        elif latest["B"] == "reject":
            images_status, detail = "rejected", "Gate B rejected, rerun the stage or decide again"
        else:
            images_status, detail = "waiting_approval", "All finals ready, awaiting Gate B"
    else:
        images_status, detail, progress = "ready", "Ready for images", None
    stages.append({"id": "images", "title": "Images", "status": images_status, "detail": detail, "progress": progress})

    # Readout
    if not cascade["B"]:
        readout_status, detail = "locked", "Waiting for Gate B"
    elif cascade["C"]:
        readout_status, detail = "approved", "Gate C approved"
    elif latest["C"] == "reject":
        readout_status, detail = "rejected", "Gate C rejected, rerun the stage or decide again"
    else:
        readout_status, detail = "waiting_approval", "Awaiting Gate C (START)"
    stages.append({"id": "readout", "title": "Read-out", "status": readout_status, "detail": detail, "progress": None})

    # Render
    progress = None
    if not cascade["C"]:
        render_status, detail = "locked", "Waiting for Gate C"
    elif f["clips_home"] == 0:
        render_status, detail = "ready", "No clips yet"
    elif f["clips_home"] < f["planned_clips"]:
        render_status = "running"
        detail = f"Clips: {f['clips_home']}/{f['planned_clips']}"
        progress = {"done": f["clips_home"], "total": f["planned_clips"]}
    elif f["clips_home"] >= f["planned_clips"] and f["planned_clips"] > 0:
        if cascade["D"]:
            render_status, detail = "approved", "Gate D approved"
        elif latest["D"] == "reject":
            render_status, detail = "rejected", "Gate D rejected, rerun the stage or decide again"
        else:
            render_status, detail = "waiting_approval", "All clips home, awaiting Gate D"
    else:
        render_status, detail = "ready", "Ready for render"
    stages.append({"id": "render", "title": "Render", "status": render_status, "detail": detail, "progress": progress})

    # Export
    if not cascade["D"]:
        export_status, detail = "locked", "Waiting for Gate D"
    else:
        export_status, detail = "ready", "Ready for export"
    stages.append({"id": "export", "title": "Export", "status": export_status, "detail": detail, "progress": None})

    # Gates
    gates = []
    stage_status_map = {s["id"]: s["status"] for s in stages}
    for g in GATE_ORDER:
        stage_status = stage_status_map.get(GATES[g], "locked")
        if cascade[g]:
            state = "approved"
        elif latest[g] == "reject" and stage_status == "rejected":
            state = "rejected"
        elif stage_status == "waiting_approval":
            state = "open"
        else:
            state = "locked"
        last = next((rec for rec in reversed(approvals) if rec.get("gate") == g), None)
        gates.append({
            "id": g,
            "title": f"Gate {g}",
            "stage": GATES[g],
            "state": state,
            "by": last.get("by") if last else None,
            "at": last.get("time") if last else None,
            "note": last.get("note") if last else None,
            "story": slug,
            "pack": pack,
        })

    current = "story"
    for s in stages:
        if s["status"] not in ("approved", "done"):
            current = s["id"]
            break

    return {
        "scope": {"story": slug, "pack": pack},
        "project": project,
        "stages": stages,
        "gates": gates,
        "current": current,
        "output_languages": output_languages(studio, slug),
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
    story: Optional[str] = None,
    pack: Optional[str] = None,
) -> Dict[str, Any]:
    if decision not in ("approve", "reject"):
        raise GateError("decision must be 'approve' or 'reject'", 400)
    if not story or not pack:
        raise GateError("story and pack are required", 400)
    project = load_project(runs)
    if project.get("story_slug") != story or project.get("pack") != pack:
        raise GateError("this gate belongs to another story or pack: switch to it first", 409)

    state = pipeline_state(studio, runs, now, story, pack)
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

    if gate == "C" and decision == "approve" and confirm != "START":
        raise GateError("Gate C requires confirm='START'", 400)
    if gate == "A" and decision == "approve":
        probs = validator_problems(studio, story, pack)
        if probs:
            raise GateError(f"Gate A blocked: {len(probs)} validator error(s), first {probs[0]}", 403)
    if gate == "D" and decision == "approve":
        probs = gate_d_problems(studio, story, pack)
        if probs:
            raise GateError(f"Gate D blocked: {probs[0]}", 403)

    record_gate(runs, gate, decision, who, note, now, studio=studio, story_slug=story, pack=pack)
    new_state = pipeline_state(studio, runs, now, story, pack)
    return next(g for g in new_state["gates"] if g["id"] == gate)


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
def summary(studio: Path, runs: Path, story: Optional[str] = None, pack: Optional[str] = None) -> Dict[str, Any]:
    slug, pack, project = scope(runs, story, pack)
    takes = project.get("takes", 3)
    if not slug or not pack:
        return _empty_summary()

    pack_dir = Path(studio) / "stories" / slug / pack
    shots_data = _safe_read_json(pack_dir / "shots.json")
    bible_data = _safe_read_json(pack_dir / "bible.json")
    if not isinstance(shots_data, list) or not isinstance(bible_data, dict):
        return _empty_summary()
    rows = [s for s in shots_data if isinstance(s, dict)]

    episodes_map: Dict[Any, Dict[str, Any]] = {}
    total_seconds = 0.0
    modes: Dict[str, int] = {}
    shot_ids = set()
    duplicate_ids = False
    all_have_seconds = True
    all_have_episode = True

    for shot in rows:
        sid = shot.get("id")
        if sid in shot_ids:
            duplicate_ids = True
        shot_ids.add(sid)
        ep = shot.get("episode")
        sec = shot_seconds(shot)
        route = shot_route(shot)
        modes[route] = modes.get(route, 0) + 1
        if ep is None:
            all_have_episode = False
            continue
        if sec <= 0:
            all_have_seconds = False
        total_seconds += sec
        if ep not in episodes_map:
            episodes_map[ep] = {"shots": 0, "seconds": 0.0}
        episodes_map[ep]["shots"] += 1
        episodes_map[ep]["seconds"] += sec

    episodes_list = [{"episode": ep, "n": ep, "shots": v["shots"], "seconds": round(v["seconds"], 1)}
                     for ep, v in sorted(episodes_map.items(), key=lambda x: str(x[0]))]

    characters = [c.get("name") for c in bible_items(bible_data, "characters") if c.get("name")]
    places = [e.get("name") for e in bible_items(bible_data, "environments") if e.get("name")]
    props = [p.get("name") or p.get("id") for p in bible_items(bible_data, "props") if p.get("name") or p.get("id")]

    f = facts(studio, runs, slug, pack)
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

    lo, hi = _reel_range()
    warnings = []
    for ep_data in episodes_list:
        if ep_data["seconds"] > hi:
            warnings.append(f"Episode {ep_data['episode']} total seconds {ep_data['seconds']:.1f} above the studio range {lo:g}-{hi:g} s")
    if f["finals"] < f["expected_images"]:
        warnings.append(f"finals {f['finals']} < expected images {f['expected_images']}")

    val = load_validation(runs, slug, pack)
    return {
        "reels": len(episodes_map),
        "episodes": episodes_list,
        "shots": len(rows),
        "seconds": round(total_seconds, 1),
        "characters": characters,
        "places": places,
        "props": props,
        "modes": modes,
        "images": {"expected": f["expected_images"], "final": f["finals"], "pending": f["pending"], "reviewed": f["reviewed"]},
        "video": {"shots": f["n_shots"], "takes": takes, "clips_home": f["clips_home"], "planned_clips": planned_clips},
        "estimate": {"g4_units": g4_units, "minutes": minutes},
        "checks": checks,
        "warnings": warnings,
        "validator": ({"ok": val.get("ok"), "errors": len(val.get("errors") or []), "warnings": len(val.get("warnings") or []),
                       "mode": val.get("mode"), "time": val.get("time")} if val else None),
        "output_languages": output_languages(studio, slug),
    }


def _reel_range() -> Tuple[float, float]:
    try:
        return _h3("shot_table_spec").STUDIO_REEL_RANGE
    except Exception:
        return (60.0, 75.0)


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
        "validator": None,
        "output_languages": [],
    }


# --------------------------------------------------------------------------- #
# Render status (plan, asset manifest, fallback rungs, Step 9, Gate D per language)
# --------------------------------------------------------------------------- #
def caption_safe_zone() -> str:
    try:
        c = _h3("shot_table_spec").CAPTION
        return f"bottom {c['margin_v']} / top {c['top_blocked_y']} / sides {c['margin_l']} (Instagram Reels + YouTube Shorts)"
    except Exception:
        return "unavailable"


def render_status(studio: Path, slug: str, pack: str) -> Dict[str, Any]:
    pack_dir = Path(studio) / "stories" / slug / pack
    plan = h3_plan(studio, slug, pack)
    shots = _safe_read_json(pack_dir / "shots.json")
    shots = [s for s in shots if isinstance(s, dict)] if isinstance(shots, list) else []
    return {
        "story": slug,
        "pack": pack,
        "prepare_ready": plan["ready"],
        "prepare": {"ready": plan["ready"], "problems": plan["problems"] + ([plan["error"]] if plan["error"] else [])},
        "steps": plan["steps"],
        "images": {"expected": sum(images_for_shot(s) for s in shots)},
        "asset_manifest": _manifest_status(pack_dir, shots),
        "fallback": _fallback_rows(pack_dir, shots),
        "human_choices": list(_h3("shot_table_spec").HUMAN_CHOICES) if _h3_ok() else [],
        "step9": read_step9(pack_dir),
        "gate_d": {"languages": _per_language(plan, pack_dir / "render", output_languages(studio, slug))},
        "bgm": _bgm_label(read_story_json(studio, slug)),
        "caption_safe_zone": caption_safe_zone(),
    }


def _h3_ok() -> bool:
    try:
        _h3("shot_table_spec")
        return True
    except Exception:
        return False


def _bgm_label(story: Dict[str, Any]) -> Dict[str, Any]:
    bgm = story.get("bgm") if isinstance(story.get("bgm"), dict) else {}
    on = bool(bgm.get("enabled"))
    return {"enabled": on, "manifest": bgm.get("manifest") if on else None,
            "label": "BGM on (3-stem)" if on else "no BGM (2-stem mix)"}


def _per_language(plan: Dict[str, Any], render_dir: Path, chosen: List[str]) -> List[Dict[str, Any]]:
    """One row per language: VO files present/expected, captions .ass, final mp4, and the checks of the audio plan."""
    gd = next((s for s in plan["steps"] if s["id"] == "gate_d"), None)
    langs = list(plan.get("languages") or chosen)
    rows = []
    for lang in langs:
        vo_present = vo_expected = 0
        captions = final = True
        for ep in plan.get("episodes") or []:
            ep_dir = render_dir / ep["id"]
            for sid in ep["shots"]:
                vo_expected += 1
                if (ep_dir / "audio" / "vo" / lang / f"{sid}.wav").is_file():
                    vo_present += 1
            if not (ep_dir / "captions").is_dir() or not any((ep_dir / "captions").glob("*.ass")):
                captions = False
            if not (ep_dir / "export" / f"{ep['id']}_{lang}.mp4").is_file():
                final = False
        reasons = [r for r in (gd["reasons"] if gd else []) if f" {lang}: " in r]
        if gd is None:
            reasons = ["Gate D not planned yet"]
        checks = [{"name": "audio plan", "ok": bool(gd and gd["status"] == "ready" and not reasons),
                   "detail": "; ".join(reasons) if reasons else ("ready" if gd and gd["status"] == "ready" else "not ready")}]
        checks.append({"name": "VO files", "ok": vo_expected > 0 and vo_present == vo_expected,
                       "detail": f"{vo_present}/{vo_expected} lines"})
        rows.append({"lang": lang, "vo": {"present": vo_present, "expected": vo_expected}, "captions_ass": captions,
                     "final_mp4": final, "checks": checks})
    return rows


def _manifest_status(pack_dir: Path, shots: List[Dict[str, Any]]) -> Dict[str, Any]:
    empty = {"present": False, "clips": 0, "placeholders": 0, "stale": 0, "blocking_problems": []}
    path = pack_dir / "render" / "asset_manifest.json"
    if not path.is_file():
        return empty
    try:
        am = _h3("asset_manifest")
        manifest = am.load_manifest(str(path))
    except Exception as exc:
        return {**empty, "present": True, "blocking_problems": [f"manifest unreadable: {str(exc)[:160]}"]}
    clips = manifest.get("clips", {})
    placeholders = sum(1 for e in clips.values() if isinstance(e, dict) and e.get("status") == am.PLACEHOLDER_STATUS)
    bible = _safe_read_json(pack_dir / "bible.json")
    current = {}
    for s in shots:
        sid = s.get("id")
        entry = clips.get(sid)
        if isinstance(sid, str) and isinstance(entry, dict) and isinstance(bible, dict):
            current[sid] = {"bible_sha256": am.hash_bible(bible), "shot_row_sha256": am.hash_shot_row(s),
                            "start_frame_sha256": entry.get("start_frame_sha256"), "end_frame_sha256": entry.get("end_frame_sha256"),
                            "model_id": entry.get("model_id")}
    try:
        blocking = am.blocking_problems(manifest, current)
    except Exception as exc:
        blocking = [f"manifest check failed: {type(exc).__name__}"]
    stale = sum(1 for sid, cur in current.items() if am.is_stale(clips[sid], cur))
    return {"present": True, "clips": len(clips), "placeholders": placeholders, "stale": stale, "blocking_problems": blocking}


def _fallback_rows(pack_dir: Path, shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        fp = _h3("fallback_policy")
        hist = fp.load_history(str(pack_dir / "render" / "fallback_history.json"))
        rungs = _h3("shot_table_spec").FALLBACK_RUNGS
        human = list(_h3("shot_table_spec").HUMAN_CHOICES)
    except Exception:
        return []
    rows = []
    for s in shots:
        sid = s.get("id")
        attempts = fp.attempts_for(hist, sid) if isinstance(sid, str) else []
        if not attempts:
            continue
        n = len(attempts)
        rows.append({"shot_id": sid, "attempts": n, "rung": min(n, rungs),
                     "action": f"rung {min(n, rungs)} of {rungs}", "human_choices": human if n >= rungs else []})
    return rows


def record_human_choice(studio: Path, slug: str, pack: str, shot: str, choice: str, note: str) -> Dict[str, Any]:
    """Appends one owner choice to render/human_choices.jsonl. Only the four HUMAN_CHOICES are accepted."""
    fp = _h3("fallback_policy")
    fp.validate_human_choice(choice)
    rec = {"time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "story": slug, "pack": pack,
           "shot": shot, "choice": choice, "note": note}
    path = Path(studio) / "stories" / slug / pack / "render" / "human_choices.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# --------------------------------------------------------------------------- #
# Voice map (bible.voice_map, validated by h3/voice_engine.py)
# --------------------------------------------------------------------------- #
def read_voice_map(pack_dir: Path) -> Dict[str, Any]:
    bible = _safe_read_json(pack_dir / "bible.json")
    vm = bible.get("voice_map") if isinstance(bible, dict) else None
    return vm if isinstance(vm, dict) else {}


def write_voice_map(pack_dir: Path, voice_map: Dict[str, Any], langs: List[str]) -> List[str]:
    """Returns [] and writes bible.json, or the VM-* problem messages and writes nothing."""
    bible = _safe_read_json(pack_dir / "bible.json")
    if not isinstance(bible, dict):
        return ["VM-03 bible.json is missing or not an object"]
    ve = _h3("voice_engine")
    chars = {x.get("id") for x in bible_items(bible, "characters") if x.get("id")}
    probs = ve.voice_map_problems(voice_map, chars, langs)
    if probs:
        return [f"{code} {msg}" for code, msg in probs]
    bible["voice_map"] = voice_map
    atomic_write(pack_dir / "bible.json", json.dumps(bible, ensure_ascii=False, indent=1) + "\n")
    return []


def voice_names(pack_dir: Path) -> List[Dict[str, Any]]:
    bible = _safe_read_json(pack_dir / "bible.json")
    return [{"id": c["id"], "name": c.get("name") or c["id"]} for c in bible_items(bible, "characters")] if isinstance(bible, dict) else []
