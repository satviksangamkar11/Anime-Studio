import sys
from pathlib import Path
import hashlib
import json
import os
import pytest

# Insert paths to allow importing modules by bare name
_director_dir = Path(__file__).resolve().parent
_project_root = _director_dir.parent
_flow_scripts_dir = _project_root / "flow" / "scripts"
sys.path.insert(0, str(_director_dir))
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_flow_scripts_dir))

# Constants for test data
SHOT_NAME = "SHOT-001"
PLATE_ID = "PLATE-001"
PLATE_FILENAME = "plate.jpg"
PLATE_CONTENT = b"fake plate image content"
BIBLE_NAMES = ["Alice", "Bob"]
JOB_KEYS = {"method", "chips", "prompt", "base_edit_id", "edit_instruction", "people_count"}

# X-03 hand case: Shiva seated -> standing only.
SHIVA_SEATED_TO_STANDING = {
    "name": "SHIVA",
    "start": {"x": 0.5, "y": 0.6, "scale": 1.0, "facing": "camera", "pose": "seated"},
    "end": {"x": 0.5, "y": 0.6, "scale": 1.0, "facing": "camera", "pose": "standing"},
}



@pytest.fixture(autouse=True)
def _s_gate_off(monkeypatch):
    # M-32: S is the default route now; this file pins the SE behaviour (A and B jobs), so it switches the S gate off
    monkeypatch.setenv("SHOT_MODE_S_ALLOW", "0")

def create_flow_root(tmp_path):
    """Create a mock flow root with plates directory and plates.json."""
    flow_root = tmp_path / "flow"
    plates_dir = flow_root / "plates"
    plates_dir.mkdir(parents=True)
    plate_file = plates_dir / PLATE_FILENAME
    plate_file.write_bytes(PLATE_CONTENT)
    sha256 = hashlib.sha256(PLATE_CONTENT).hexdigest()
    plates_json = {
        PLATE_ID: {
            "path": str(plate_file),
            "sha256": sha256
        }
    }
    (plates_dir / "plates.json").write_text(json.dumps(plates_json))
    return flow_root


def write_catalog(flow_root, catalog):
    """Replace plates.json under flow_root with the given catalog."""
    (flow_root / "plates" / "plates.json").write_text(json.dumps(catalog))


def _member(name, start_x, end_x):
    """Cast member with the full start/end schema blocking.change_list reads."""
    return {
        "name": name,
        "start": {"x": start_x, "y": 0.6, "scale": 1.0, "facing": "camera", "pose": "standing"},
        "end": {"x": end_x, "y": 0.6, "scale": 1.0, "facing": "camera", "pose": "standing"},
    }


def FakeSheet(shot, people_count=0):
    """Minimal dict sheet with shot name and people count."""
    return {"shot": shot, "people_count": people_count, "cast": [], "props": []}


def sheet_with(cast, shot=SHOT_NAME):
    """Dict sheet with a cast and no explicit people_count (the on-screen rule decides)."""
    return {"shot": shot, "cast": cast, "props": []}


def _setup_module(tmp_path, monkeypatch):
    """Helper to set up the test environment for jobs_for_shot tests (real blocking module)."""
    flow_root = create_flow_root(tmp_path)
    # Force re-import of keyframe_jobs so each test sees its own FLOW_ROOT
    sys.modules.pop("keyframe_jobs", None)
    import keyframe_jobs
    keyframe_jobs.FLOW_ROOT = str(flow_root)
    return keyframe_jobs, flow_root


def _build_jobs_fixture():
    """One real job from flow/scripts/build_jobs.py, the schema reference."""
    import build_jobs
    spec = {
        "adhyay": 1,
        "slot_order": {"S1": [SHOT_NAME]},
        "shots": [{
            "shot_id": SHOT_NAME, "scene": "S1", "method": "edit", "base_edit_id": "PLATE-X",
            "characters": [], "place": "P1", "props": [], "action": "a", "light": "l",
            "reference_sentence": "r",
        }],
    }
    series = {
        "style": {"chip": "STYLE-CHIP", "text": "style"},
        "characters": {},
        "places": {"P1": {"chip": "PLACE-CHIP", "text": "place"}},
        "props": {},
        "model": {"name": "m"},
        "tail": "",
    }
    return build_jobs.build_jobs(spec, series, 1)[0]


def test_job_keys_match_build_jobs(tmp_path, monkeypatch):
    keyframe_jobs, _ = _setup_module(tmp_path, monkeypatch)
    fixture_job = _build_jobs_fixture()
    job_a, job_b = keyframe_jobs.jobs_for_shot(FakeSheet(SHOT_NAME), PLATE_ID, BIBLE_NAMES)
    assert set(job_a) == JOB_KEYS
    assert set(job_b) == JOB_KEYS | {"chip_ref_id"}  # B is generate_with_chip (M-06b)
    # Every key we emit is a key the real build_jobs job carries (same names, same schema)
    assert JOB_KEYS <= set(fixture_job)


def test_b_is_edit_of_a(tmp_path, monkeypatch):
    keyframe_jobs, _ = _setup_module(tmp_path, monkeypatch)
    sheet = FakeSheet(SHOT_NAME)
    jobs = keyframe_jobs.jobs_for_shot(sheet, PLATE_ID, BIBLE_NAMES)
    job_a, job_b = jobs
    assert job_b["base_edit_id"] == f"{SHOT_NAME}-A"
    assert job_b["chips"] == [f"{SHOT_NAME}-A final"]
    assert len(job_b["chips"]) == 1
    assert job_a["method"] == "edit" and job_b["method"] == "generate_with_chip"
    assert job_b["chip_ref_id"] == f"{SHOT_NAME}-A final"


def test_a_chip_is_plate_under_flow_root_plates(tmp_path, monkeypatch):
    keyframe_jobs, flow_root = _setup_module(tmp_path, monkeypatch)
    job_a, _ = keyframe_jobs.jobs_for_shot(FakeSheet(SHOT_NAME), PLATE_ID, BIBLE_NAMES)
    expected = os.path.normpath(os.path.join(str(flow_root), "plates", PLATE_FILENAME))
    assert job_a["chips"] == [expected]
    assert job_a["base_edit_id"] == PLATE_ID


def test_relative_registry_path_resolves_under_plates(tmp_path, monkeypatch):
    keyframe_jobs, flow_root = _setup_module(tmp_path, monkeypatch)
    write_catalog(flow_root, {PLATE_ID: {"path": PLATE_FILENAME, "sha256": "x"}})
    job_a, _ = keyframe_jobs.jobs_for_shot(FakeSheet(SHOT_NAME), PLATE_ID, BIBLE_NAMES)
    assert job_a["chips"] == [os.path.normpath(os.path.join(str(flow_root), "plates", PLATE_FILENAME))]


def test_b_instruction_from_change_list(tmp_path, monkeypatch):
    keyframe_jobs, _ = _setup_module(tmp_path, monkeypatch)
    jobs = keyframe_jobs.jobs_for_shot(sheet_with([SHIVA_SEATED_TO_STANDING]), PLATE_ID, BIBLE_NAMES)
    job_b = jobs[1]
    expected_instruction = (
        "Same picture, same framing, same light, same background. Change only: 1) SHIVA now stands."
    )
    assert job_b["edit_instruction"] == expected_instruction


def test_missing_plate_raises(tmp_path, monkeypatch):
    keyframe_jobs, _ = _setup_module(tmp_path, monkeypatch)
    sheet = FakeSheet(SHOT_NAME)
    with pytest.raises(keyframe_jobs.KeyframeJobError) as exc:
        keyframe_jobs.jobs_for_shot(sheet, "PLATE-MISSING", BIBLE_NAMES)
    assert "plate PLATE-MISSING missing" in str(exc.value)
    assert "make it once per location first" in str(exc.value)


def test_registry_entry_without_path_raises(tmp_path, monkeypatch):
    keyframe_jobs, flow_root = _setup_module(tmp_path, monkeypatch)
    write_catalog(flow_root, {PLATE_ID: {"sha256": "x"}})
    with pytest.raises(keyframe_jobs.KeyframeJobError):
        keyframe_jobs.jobs_for_shot(FakeSheet(SHOT_NAME), PLATE_ID, BIBLE_NAMES)


def test_registry_file_missing_raises(tmp_path, monkeypatch):
    keyframe_jobs, flow_root = _setup_module(tmp_path, monkeypatch)
    write_catalog(flow_root, {PLATE_ID: {"path": "gone.jpg", "sha256": "x"}})
    with pytest.raises(keyframe_jobs.KeyframeJobError) as exc:
        keyframe_jobs.jobs_for_shot(FakeSheet(SHOT_NAME), PLATE_ID, BIBLE_NAMES)
    assert "file missing" in str(exc.value)


def test_people_count(tmp_path, monkeypatch):
    keyframe_jobs, _ = _setup_module(tmp_path, monkeypatch)
    sheet = FakeSheet(SHOT_NAME, people_count=7)
    jobs = keyframe_jobs.jobs_for_shot(sheet, PLATE_ID, BIBLE_NAMES)
    for job in jobs:
        assert job["people_count"] == 7


def test_people_count_counts_only_on_screen_cast(tmp_path, monkeypatch):
    keyframe_jobs, _ = _setup_module(tmp_path, monkeypatch)
    on_screen = _member("A", 0.5, 0.5)
    entering = _member("B", 1.5, 0.9)
    off_screen = _member("C", 2.0, 3.0)
    jobs = keyframe_jobs.jobs_for_shot(sheet_with([on_screen, entering, off_screen]), PLATE_ID, BIBLE_NAMES)
    for job in jobs:
        assert job["people_count"] == 2


def test_empty_cast_is_zero_not_bible_count(tmp_path, monkeypatch):
    keyframe_jobs, _ = _setup_module(tmp_path, monkeypatch)
    jobs = keyframe_jobs.jobs_for_shot(sheet_with([]), PLATE_ID, BIBLE_NAMES)
    for job in jobs:
        assert job["people_count"] == 0
