import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pipeline
from pipeline import (
    STAGES, GATES, GateError,
    load_project, save_project, read_approvals, record_gate,
    facts, pipeline_state, apply_gate, summary,
)

import json
import pytest


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_runs(tmp_path, slug="test-slug", pack="pack1", takes=3,
              images_dir=None, results_dir=None):
    runs = tmp_path / "runs"
    runs.mkdir(exist_ok=True)
    project = {
        "story_slug": slug,
        "pack": pack,
        "images_dir": str(images_dir) if images_dir else None,
        "results_dir": str(results_dir) if results_dir else None,
        "takes": takes,
    }
    save_project(runs, project)
    return runs


def make_story(studio, slug="test-slug"):
    story_dir = studio / "stories" / slug
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "SOURCE.md").write_text("Once upon a time...", encoding="utf-8")
    return story_dir


def make_pack(studio, slug="test-slug", pack="pack1", shots=None, bible=None,
              stage_files=0):
    pack_dir = studio / "stories" / slug / pack
    pack_dir.mkdir(parents=True, exist_ok=True)
    if shots is not None:
        (pack_dir / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
    if bible is not None:
        (pack_dir / "bible.json").write_text(json.dumps(bible), encoding="utf-8")
    for i in range(stage_files):
        (pack_dir / f"stage_{i}_raw.json").write_text("{}", encoding="utf-8")
    return pack_dir


def make_images_dir(tmp_path, name="images", finals=0, reviews=0,
                    dq_lines=None, fl_lines=None):
    img_dir = tmp_path / name
    (img_dir / "final").mkdir(parents=True, exist_ok=True)
    (img_dir / "shots").mkdir(parents=True, exist_ok=True)
    for i in range(finals):
        (img_dir / "final" / f"SHOT-{i:03d}__final.png").write_text("", encoding="utf-8")
    for i in range(reviews):
        (img_dir / "shots" / f"SHOT-{i:03d}__review.json").write_text("{}", encoding="utf-8")
    if dq_lines is not None:
        with open(img_dir / "download_queue.jsonl", "w", encoding="utf-8") as f:
            for line in dq_lines:
                f.write(json.dumps(line) + "\n")
    if fl_lines is not None:
        with open(img_dir / "flow_log.jsonl", "w", encoding="utf-8") as f:
            for line in fl_lines:
                f.write(json.dumps(line) + "\n")
    return img_dir


def make_results_dir(tmp_path, name="results", clips=0):
    res_dir = tmp_path / name
    res_dir.mkdir(parents=True, exist_ok=True)
    for i in range(clips):
        (res_dir / f"clip_{i}.mp4").write_text("", encoding="utf-8")
    return res_dir


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_load_save_project(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    # missing -> defaults
    proj = load_project(runs)
    assert proj["story_slug"] is None
    assert proj["pack"] is None
    assert proj["takes"] == 3
    # save and load
    proj["story_slug"] = "abc"
    proj["pack"] = "p"
    save_project(runs, proj)
    proj2 = load_project(runs)
    assert proj2["story_slug"] == "abc"
    assert proj2["pack"] == "p"


def test_read_approvals_skip_malformed(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "approvals.jsonl").write_text(
        '{"gate":"A","decision":"approve","by":"owner","note":""}\n'
        'not json\n'
        '{"gate":"B","decision":"reject","by":"owner","note":"no"}\n'
        , encoding="utf-8"
    )
    recs = read_approvals(runs)
    assert len(recs) == 2
    assert recs[0]["gate"] == "A"
    assert recs[1]["gate"] == "B"


def test_record_gate_creates_folder(tmp_path):
    runs = tmp_path / "runs"
    rec = record_gate(runs, "A", "approve", "owner", "ok")
    assert rec["gate"] == "A"
    assert rec["decision"] == "approve"
    assert (runs / "approvals.jsonl").is_file()


def test_facts_no_pack(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    runs = make_runs(tmp_path, slug=None, pack=None)
    f = facts(studio, runs)
    assert f["story_saved"] is False
    assert f["pack_stage_files"] == 0
    assert f["shots_ready"] is False
    assert f["n_shots"] == 0
    assert f["expected_images"] == 0
    assert f["finals"] == 0
    assert f["pending"] == 0
    assert f["reviewed"] == 0
    assert f["clips_home"] == 0
    assert f["planned_clips"] == 0


def test_facts_with_pack(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "my-slug"
    pack = "pack1"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, pack, shots=shots, bible=bible, stage_files=2)
    img_dir = make_images_dir(tmp_path, "img", finals=1, reviews=2,
                              dq_lines=[{"shot_id": "S1", "version": 1, "image_id": "IMG1"}],
                              fl_lines=[{"image_id": "IMG1", "version": 1}])
    res_dir = make_results_dir(tmp_path, "res", clips=3)
    runs = make_runs(tmp_path, slug=slug, pack=pack,
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=2)
    f = facts(studio, runs)
    assert f["story_saved"] is True
    assert f["pack_stage_files"] == 2
    assert f["shots_ready"] is True
    assert f["n_shots"] == 1
    assert f["expected_images"] == 2
    assert f["finals"] == 1
    assert f["pending"] == 0
    assert f["reviewed"] == 2
    assert f["clips_home"] == 3
    assert f["planned_clips"] == 2  # n_shots * takes


def test_pending_computation(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    pack = "p"
    make_story(studio, slug)
    make_pack(studio, slug, pack, shots=[], bible={})
    # download queue: two shots, latest version each
    dq = [
        {"shot_id": "S1", "version": 1, "image_id": "IMG1"},
        {"shot_id": "S1", "version": 2, "image_id": "IMG2"},
        {"shot_id": "S2", "version": 1, "image_id": "IMG3"},
    ]
    # flow log only has IMG1 (old version) -> S1v2 pending, S2v1 pending
    fl = [{"image_id": "IMG1", "version": 1}]
    img_dir = make_images_dir(tmp_path, "img", dq_lines=dq, fl_lines=fl)
    runs = make_runs(tmp_path, slug=slug, pack=pack, images_dir=str(img_dir))
    f = facts(studio, runs)
    assert f["pending"] == 2


def test_pipeline_state_story_ready(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    runs = make_runs(tmp_path, slug="s", pack="p")
    state = pipeline_state(studio, runs)
    assert state["project"]["story_slug"] == "s"
    story_stage = next(s for s in state["stages"] if s["id"] == "story")
    assert story_stage["status"] == "ready"
    assert state["current"] == "story"


def test_pipeline_state_story_done(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    state = pipeline_state(studio, runs)
    story_stage = next(s for s in state["stages"] if s["id"] == "story")
    assert story_stage["status"] == "done"
    # analysis should be ready (story done, no pack files)
    analysis_stage = next(s for s in state["stages"] if s["id"] == "analysis")
    assert analysis_stage["status"] == "ready"
    assert state["current"] == "analysis"


def test_pipeline_state_analysis_locked(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    runs = make_runs(tmp_path, slug="s", pack="p")
    state = pipeline_state(studio, runs)
    analysis_stage = next(s for s in state["stages"] if s["id"] == "analysis")
    assert analysis_stage["status"] == "locked"


def test_pipeline_state_analysis_partial_is_ready(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    make_pack(studio, slug, "p", stage_files=3)  # no shots.json yet
    runs = make_runs(tmp_path, slug=slug, pack="p")
    state = pipeline_state(studio, runs)
    analysis_stage = next(s for s in state["stages"] if s["id"] == "analysis")
    assert analysis_stage["status"] == "ready"  # partial files: run again to resume
    assert "run again to resume" in analysis_stage["detail"]
    assert analysis_stage["progress"]["done"] == 3
    assert analysis_stage["progress"]["total"] is None


def test_pipeline_state_analysis_waiting_approval(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    state = pipeline_state(studio, runs)
    analysis_stage = next(s for s in state["stages"] if s["id"] == "analysis")
    assert analysis_stage["status"] == "waiting_approval"
    gate_a = next(g for g in state["gates"] if g["id"] == "A")
    assert gate_a["state"] == "open"


def test_pipeline_state_analysis_approved(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    analysis_stage = next(s for s in state["stages"] if s["id"] == "analysis")
    assert analysis_stage["status"] == "approved"
    gate_a = next(g for g in state["gates"] if g["id"] == "A")
    assert gate_a["state"] == "approved"


def test_pipeline_state_analysis_rejected(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "reject", "owner", "no")
    state = pipeline_state(studio, runs)
    analysis_stage = next(s for s in state["stages"] if s["id"] == "analysis")
    assert analysis_stage["status"] == "rejected"
    gate_a = next(g for g in state["gates"] if g["id"] == "A")
    assert gate_a["state"] == "rejected"


def test_pipeline_state_images_locked(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    state = pipeline_state(studio, runs)
    images_stage = next(s for s in state["stages"] if s["id"] == "images")
    assert images_stage["status"] == "locked"


def test_pipeline_state_images_ready(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    images_stage = next(s for s in state["stages"] if s["id"] == "images")
    assert images_stage["status"] == "ready"


def test_pipeline_state_images_running_finals(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=1)  # expected 2
    runs = make_runs(tmp_path, slug=slug, pack="p", images_dir=str(img_dir))
    record_gate(runs, "A", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    images_stage = next(s for s in state["stages"] if s["id"] == "images")
    assert images_stage["status"] == "running"
    assert images_stage["progress"]["done"] == 1
    assert images_stage["progress"]["total"] == 2


def test_pipeline_state_images_running_pending(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    # pending > 0, finals = 0
    dq = [{"shot_id": "S1", "version": 1, "image_id": "IMG1"}]
    fl = []
    img_dir = make_images_dir(tmp_path, "img", finals=0, dq_lines=dq, fl_lines=fl)
    runs = make_runs(tmp_path, slug=slug, pack="p", images_dir=str(img_dir))
    record_gate(runs, "A", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    images_stage = next(s for s in state["stages"] if s["id"] == "images")
    assert images_stage["status"] == "running"
    assert images_stage["progress"]["done"] == 0
    assert images_stage["progress"]["total"] == 2


def test_pipeline_state_images_waiting_approval(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)  # expected 2
    runs = make_runs(tmp_path, slug=slug, pack="p", images_dir=str(img_dir))
    record_gate(runs, "A", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    images_stage = next(s for s in state["stages"] if s["id"] == "images")
    assert images_stage["status"] == "waiting_approval"
    gate_b = next(g for g in state["gates"] if g["id"] == "B")
    assert gate_b["state"] == "open"


def test_pipeline_state_images_approved(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    runs = make_runs(tmp_path, slug=slug, pack="p", images_dir=str(img_dir))
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    images_stage = next(s for s in state["stages"] if s["id"] == "images")
    assert images_stage["status"] == "approved"
    gate_b = next(g for g in state["gates"] if g["id"] == "B")
    assert gate_b["state"] == "approved"


def test_pipeline_state_images_rejected(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    runs = make_runs(tmp_path, slug=slug, pack="p", images_dir=str(img_dir))
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "reject", "owner", "bad")
    state = pipeline_state(studio, runs)
    images_stage = next(s for s in state["stages"] if s["id"] == "images")
    assert images_stage["status"] == "rejected"
    gate_b = next(g for g in state["gates"] if g["id"] == "B")
    assert gate_b["state"] == "rejected"


def test_pipeline_state_readout_locked(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    readout_stage = next(s for s in state["stages"] if s["id"] == "readout")
    assert readout_stage["status"] == "locked"


def test_pipeline_state_readout_waiting_approval(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    readout_stage = next(s for s in state["stages"] if s["id"] == "readout")
    assert readout_stage["status"] == "waiting_approval"
    gate_c = next(g for g in state["gates"] if g["id"] == "C")
    assert gate_c["state"] == "open"


def test_pipeline_state_readout_approved(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    readout_stage = next(s for s in state["stages"] if s["id"] == "readout")
    assert readout_stage["status"] == "approved"
    gate_c = next(g for g in state["gates"] if g["id"] == "C")
    assert gate_c["state"] == "approved"


def test_pipeline_state_readout_rejected(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "reject", "owner", "no")
    state = pipeline_state(studio, runs)
    readout_stage = next(s for s in state["stages"] if s["id"] == "readout")
    assert readout_stage["status"] == "rejected"
    gate_c = next(g for g in state["gates"] if g["id"] == "C")
    assert gate_c["state"] == "rejected"


def test_pipeline_state_render_locked(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    render_stage = next(s for s in state["stages"] if s["id"] == "render")
    assert render_stage["status"] == "locked"


def test_pipeline_state_render_ready(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    res_dir = make_results_dir(tmp_path, "res", clips=0)
    runs = make_runs(tmp_path, slug=slug, pack="p",
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=1)
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    render_stage = next(s for s in state["stages"] if s["id"] == "render")
    assert render_stage["status"] == "ready"


def test_pipeline_state_render_running(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    res_dir = make_results_dir(tmp_path, "res", clips=1)  # planned_clips = 1*1=1? Wait takes=1, n_shots=1 -> planned=1, clips_home=1 -> not running. Let's use takes=2.
    runs = make_runs(tmp_path, slug=slug, pack="p",
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=2)
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    render_stage = next(s for s in state["stages"] if s["id"] == "render")
    assert render_stage["status"] == "running"
    assert render_stage["progress"]["done"] == 1
    assert render_stage["progress"]["total"] == 2


def test_pipeline_state_render_waiting_approval(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    res_dir = make_results_dir(tmp_path, "res", clips=2)  # planned_clips = 2
    runs = make_runs(tmp_path, slug=slug, pack="p",
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=2)
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    render_stage = next(s for s in state["stages"] if s["id"] == "render")
    assert render_stage["status"] == "waiting_approval"
    gate_d = next(g for g in state["gates"] if g["id"] == "D")
    assert gate_d["state"] == "open"


def test_pipeline_state_render_approved(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    res_dir = make_results_dir(tmp_path, "res", clips=2)
    runs = make_runs(tmp_path, slug=slug, pack="p",
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=2)
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    record_gate(runs, "D", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    render_stage = next(s for s in state["stages"] if s["id"] == "render")
    assert render_stage["status"] == "approved"
    gate_d = next(g for g in state["gates"] if g["id"] == "D")
    assert gate_d["state"] == "approved"


def test_pipeline_state_render_rejected(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    res_dir = make_results_dir(tmp_path, "res", clips=2)
    runs = make_runs(tmp_path, slug=slug, pack="p",
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=2)
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    record_gate(runs, "D", "reject", "owner", "bad")
    state = pipeline_state(studio, runs)
    render_stage = next(s for s in state["stages"] if s["id"] == "render")
    assert render_stage["status"] == "rejected"
    gate_d = next(g for g in state["gates"] if g["id"] == "D")
    assert gate_d["state"] == "rejected"


def test_pipeline_state_export_locked(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    export_stage = next(s for s in state["stages"] if s["id"] == "export")
    assert export_stage["status"] == "locked"


def test_pipeline_state_export_ready(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    res_dir = make_results_dir(tmp_path, "res", clips=1)
    runs = make_runs(tmp_path, slug=slug, pack="p",
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=1)
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    record_gate(runs, "D", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    export_stage = next(s for s in state["stages"] if s["id"] == "export")
    assert export_stage["status"] == "ready"


def test_cascade_reject_A_invalidates_later(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    # approve all gates
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    record_gate(runs, "D", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    assert all(g["state"] == "approved" for g in state["gates"])
    # now reject A
    record_gate(runs, "A", "reject", "owner", "no")
    state2 = pipeline_state(studio, runs)
    gate_a = next(g for g in state2["gates"] if g["id"] == "A")
    assert gate_a["state"] == "rejected"
    # later gates become locked
    for gid in ["B", "C", "D"]:
        g = next(g for g in state2["gates"] if g["id"] == gid)
        assert g["state"] == "locked"


def test_gate_C_requires_START(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    runs = make_runs(tmp_path, slug=slug, pack="p", images_dir=str(img_dir))
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    # gate C is open
    with pytest.raises(GateError) as exc:
        apply_gate(studio, runs, "C", "approve", "", confirm="WRONG")
    assert exc.value.code == 400
    # with correct confirm
    gate = apply_gate(studio, runs, "C", "approve", "", confirm="START")
    assert gate["state"] == "approved"


def test_reject_requires_note(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    # gate A is open
    with pytest.raises(GateError) as exc:
        apply_gate(studio, runs, "A", "reject", "")
    assert exc.value.code == 400
    # too long note
    with pytest.raises(GateError):
        apply_gate(studio, runs, "A", "reject", "x" * 301)
    # newline in note
    with pytest.raises(GateError):
        apply_gate(studio, runs, "A", "reject", "line1\nline2")
    # non-printable
    with pytest.raises(GateError):
        apply_gate(studio, runs, "A", "reject", "bad\x00char")
    # valid reject
    gate = apply_gate(studio, runs, "A", "reject", "not good")
    assert gate["state"] == "rejected"


def test_apply_gate_locked_gate(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    # gate A open
    gate = apply_gate(studio, runs, "A", "approve", "ok")
    assert gate["state"] == "approved"
    # gate B is locked
    with pytest.raises(GateError) as exc:
        apply_gate(studio, runs, "B", "approve", "ok")
    assert exc.value.code == 409


def test_apply_gate_invalid_decision(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    with pytest.raises(GateError) as exc:
        apply_gate(studio, runs, "A", "maybe", "note")
    assert exc.value.code == 400


def test_apply_gate_invalid_gate(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    with pytest.raises(GateError) as exc:
        apply_gate(studio, runs, "Z", "approve", "note")
    assert exc.value.code == 400


def test_summary_numbers(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    shots = [
        {"id": "S1", "episode": 1, "seconds": 10.0, "mode": "fl2va"},
        {"id": "S2", "episode": 1, "seconds": 20.0, "mode": "fl2va"},
        {"id": "S3", "episode": 2, "seconds": 30.0, "mode": "gen"},
    ]
    bible = {
        "characters": [{"name": "Krishna"}, {"name": "Kaliya"}],
        "environments": [{"name": "River"}],
        "props": [{"id": "P1", "name": "Ball"}],
    }
    make_story(studio, slug)
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=4, reviews=2)
    res_dir = make_results_dir(tmp_path, "res", clips=3)
    runs = make_runs(tmp_path, slug=slug, pack="p",
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=2)
    s = summary(studio, runs)
    assert s["reels"] == 2
    assert len(s["episodes"]) == 2
    assert s["shots"] == 3
    assert s["seconds"] == 60.0
    assert s["characters"] == ["Krishna", "Kaliya"]
    assert s["places"] == ["River"]
    assert s["props"] == ["Ball"]
    assert s["modes"]["fl2va"] == 2
    assert s["modes"]["gen"] == 1
    assert s["images"]["expected"] == 6
    assert s["images"]["final"] == 4
    assert s["images"]["reviewed"] == 2
    assert s["video"]["shots"] == 3
    assert s["video"]["takes"] == 2
    assert s["video"]["clips_home"] == 3
    # estimate: planned_clips = 3*2=6, minutes = 7 + 6*2.2 + 5 = 7+13.2+5=25.2
    # g4 = round(10.05 * 25.2 / 60, 1) = round(253.26/60=4.221, 1) = 4.2
    assert s["estimate"]["minutes"] == 25.2
    assert s["estimate"]["g4_units"] == 4.2
    # checks
    assert len(s["checks"]) == 6
    assert all(c["ok"] for c in s["checks"])
    # warnings: episode 1 seconds=30 (ok), episode 2 seconds=30 (ok), finals 4 < 6 -> warning
    assert len(s["warnings"]) == 1
    assert "finals" in s["warnings"][0]


def test_summary_no_pack(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    runs = make_runs(tmp_path, slug=None, pack=None)
    s = summary(studio, runs)
    assert s["reels"] == 0
    assert s["shots"] == 0
    assert s["seconds"] == 0
    assert s["characters"] == []
    assert s["warnings"] == ["no pack yet"]


def test_estimate_formula(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_story(studio, slug)
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p", takes=4)
    s = summary(studio, runs)
    # planned_clips = 1*4 = 4
    # minutes = 7 + 4*2.2 + 5 = 7 + 8.8 + 5 = 20.8
    # g4 = round(10.05 * 20.8 / 60, 1) = round(209.04/60=3.484, 1) = 3.5
    assert s["estimate"]["minutes"] == 20.8
    assert s["estimate"]["g4_units"] == 3.5


def test_current_stage_selection(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    state = pipeline_state(studio, runs)
    # story done, analysis ready -> current = analysis
    assert state["current"] == "analysis"
    # after analysis approved, current = images
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    record_gate(runs, "A", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    assert state["current"] == "images"
    # after images approved, current = readout
    img_dir = make_images_dir(tmp_path, "img", finals=2)
    runs = make_runs(tmp_path, slug=slug, pack="p", images_dir=str(img_dir))
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    assert state["current"] == "readout"
    # after readout approved, current = render
    record_gate(runs, "C", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    assert state["current"] == "render"
    # after render approved, current = export
    res_dir = make_results_dir(tmp_path, "res", clips=1)
    runs = make_runs(tmp_path, slug=slug, pack="p",
                     images_dir=str(img_dir), results_dir=str(res_dir), takes=1)
    record_gate(runs, "A", "approve", "owner", "ok")
    record_gate(runs, "B", "approve", "owner", "ok")
    record_gate(runs, "C", "approve", "owner", "ok")
    record_gate(runs, "D", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    assert state["current"] == "export"


def test_gate_state_from_latest_approval(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    runs = make_runs(tmp_path, slug=slug, pack="p")
    # first approve
    record_gate(runs, "A", "approve", "owner", "first")
    # then reject
    record_gate(runs, "A", "reject", "owner", "second")
    state = pipeline_state(studio, runs)
    gate_a = next(g for g in state["gates"] if g["id"] == "A")
    assert gate_a["state"] == "rejected"
    assert gate_a["note"] == "second"
    assert gate_a["by"] == "owner"


def test_progress_dict_when_running(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    slug = "s"
    make_story(studio, slug)
    shots = [{"id": "S1", "episode": 1, "seconds": 5.0, "mode": "fl2va"}]
    bible = {"characters": [], "environments": [], "props": []}
    make_pack(studio, slug, "p", shots=shots, bible=bible)
    img_dir = make_images_dir(tmp_path, "img", finals=1)
    runs = make_runs(tmp_path, slug=slug, pack="p", images_dir=str(img_dir))
    record_gate(runs, "A", "approve", "owner", "ok")
    state = pipeline_state(studio, runs)
    images_stage = next(s for s in state["stages"] if s["id"] == "images")
    assert images_stage["progress"] == {"done": 1, "total": 2}
    # analysis running progress
    make_pack(studio, slug, "p2", stage_files=5)
    runs2 = make_runs(tmp_path, slug=slug, pack="p2")
    state2 = pipeline_state(studio, runs2)
    analysis_stage = next(s for s in state2["stages"] if s["id"] == "analysis")
    assert analysis_stage["progress"] == {"done": 5, "total": None}
    # render running progress
    res_dir = make_results_dir(tmp_path, "res", clips=1)
    runs3 = make_runs(tmp_path, slug=slug, pack="p",
                      images_dir=str(img_dir), results_dir=str(res_dir), takes=3)
    record_gate(runs3, "A", "approve", "owner", "ok")
    record_gate(runs3, "B", "approve", "owner", "ok")
    record_gate(runs3, "C", "approve", "owner", "ok")
    state3 = pipeline_state(studio, runs3)
    render_stage = next(s for s in state3["stages"] if s["id"] == "render")
    assert render_stage["progress"] == {"done": 1, "total": 3}
