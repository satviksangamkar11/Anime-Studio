#!/usr/bin/env python3
"""
Tests for flow/scripts/build_jobs.py

Run with: python flow/scripts/test_build_jobs.py
"""
import json
import sys
import subprocess
import tempfile
import hashlib
from pathlib import Path

# Add the scripts directory to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from build_jobs import build_jobs

# Paths relative to test file's grandparent (the flow/ directory)
FLOW_DIR = Path(__file__).parent.parent
SPEC_PATH = FLOW_DIR / "A_KM_image_spec_keyframesA.json"
SERIES_PATH = FLOW_DIR / "flow_series_kaliya.json"
REFERENCE_JOBS_PATH = FLOW_DIR / "A_KM_flow_jobs_keyframesA.json"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_build_jobs_matches_reference():
    """Test that build_jobs produces jobs matching the reference file exactly."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)
    reference_jobs = load_json(REFERENCE_JOBS_PATH)

    jobs = build_jobs(spec, series, adhyay=1)

    assert len(jobs) == len(reference_jobs) == 5, "Expected 5 jobs"

    for i, (job, ref_job) in enumerate(zip(jobs, reference_jobs)):
        shot_id = ref_job["shot_id"]
        assert job["shot_id"] == shot_id, f"Shot {i}: shot_id mismatch"
        assert job["flow_title"] == ref_job["flow_title"], f"{shot_id}: flow_title mismatch"
        assert job["method"] == ref_job["method"], f"{shot_id}: method mismatch"
        assert job["characters"] == ref_job["characters"], f"{shot_id}: characters mismatch"
        assert job["people_count"] == ref_job["people_count"], f"{shot_id}: people_count mismatch"
        assert job["chips"] == ref_job["chips"], f"{shot_id}: chips mismatch"
        assert job["attempt_cap"] == ref_job["attempt_cap"], f"{shot_id}: attempt_cap mismatch"
        assert job["model"] == ref_job["model"], f"{shot_id}: model mismatch"
        assert job["previous_shot"] == ref_job["previous_shot"], f"{shot_id}: previous_shot mismatch"
        assert job["next_shot"] == ref_job["next_shot"], f"{shot_id}: next_shot mismatch"

        # Prompt contains the action text and light text from the spec
        spec_shot = spec["shots"][i]
        assert spec_shot["action"] in job["prompt"], f"{shot_id}: action text not in prompt"
        assert spec_shot["light"] in job["prompt"], f"{shot_id}: light text not in prompt"

        # Prompt SHA256 matches the prompt content
        expected_sha = hashlib.sha256(job["prompt"].encode("utf-8")).hexdigest()
        assert job["prompt_sha256"] == expected_sha, f"{shot_id}: prompt_sha256 does not match prompt"
        # The prompt text itself matches the reference (the reference file's stored hash is stale)
        assert job["prompt"] == ref_job["prompt"], f"{shot_id}: prompt != reference"


def test_forbidden_words_refusal():
    """Test that forbidden words in prompt cause ValueError naming the shot."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    # Inject a forbidden word from series.forbidden_words
    spec_copy["shots"][0]["action"] = "Krishna is naked on the branch."

    try:
        build_jobs(spec_copy, series, adhyay=1)
        assert False, "Expected ValueError for forbidden word"
    except ValueError as e:
        assert "forbidden word" in str(e).lower()
        assert "LEAP-01A" in str(e)


def test_edit_job_without_base_edit_id_refusal():
    """Test that edit job with None base_edit_id raises ValueError."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    spec_copy["shots"][0]["method"] = "edit"
    spec_copy["shots"][0]["base_edit_id"] = None

    try:
        build_jobs(spec_copy, series, adhyay=1)
        assert False, "Expected ValueError for edit without base_edit_id"
    except ValueError as e:
        assert "edit job requires a valid base_edit_id" in str(e)
        assert "LEAP-01A" in str(e)


def test_edit_job_with_empty_base_edit_id_refusal():
    """Test that edit job with empty string base_edit_id raises ValueError."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    spec_copy["shots"][0]["method"] = "edit"
    spec_copy["shots"][0]["base_edit_id"] = ""

    try:
        build_jobs(spec_copy, series, adhyay=1)
        assert False, "Expected ValueError for edit with empty base_edit_id"
    except ValueError as e:
        assert "edit job requires a valid base_edit_id" in str(e)


def test_edit_job_with_pending_base_edit_id_refusal():
    """Test that edit job with PENDING placeholder base_edit_id raises ValueError."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    spec_copy["shots"][0]["method"] = "edit"
    spec_copy["shots"][0]["base_edit_id"] = "PENDING_123"

    try:
        build_jobs(spec_copy, series, adhyay=1)
        assert False, "Expected ValueError for edit with PENDING base_edit_id"
    except ValueError as e:
        assert "edit job requires a valid base_edit_id" in str(e)


def test_generate_with_chip_accepted_and_chip_attached():
    """generate_with_chip is accepted; the reference chip id goes into chips before the style chip."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    spec_copy["shots"][0]["method"] = "generate_with_chip"
    spec_copy["shots"][0]["chip_ref_id"] = "LEAP-01A final"

    job = build_jobs(spec_copy, series, adhyay=1)[0]
    assert job["method"] == "generate_with_chip"
    assert "LEAP-01A final" in job["chips"]
    assert job["chips"][-1] == series["style"]["chip"]


def test_generate_with_chip_without_chip_ref_id_refusal():
    """generate_with_chip with no (or PENDING) chip_ref_id raises ValueError naming the shot."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    for bad in (None, "", "PENDING_9"):
        spec_copy = json.loads(json.dumps(spec))
        spec_copy["shots"][0]["method"] = "generate_with_chip"
        spec_copy["shots"][0]["chip_ref_id"] = bad
        try:
            build_jobs(spec_copy, series, adhyay=1)
            assert False, f"Expected ValueError for chip_ref_id={bad!r}"
        except ValueError as e:
            assert "generate_with_chip job requires a valid chip_ref_id" in str(e)
            assert "LEAP-01A" in str(e)


def test_edit_method_still_accepted_for_existing_jobs():
    """Old 'edit' jobs with a real base_edit_id still build (no rename break for existing packs)."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    spec_copy["shots"][0]["method"] = "edit"
    spec_copy["shots"][0]["base_edit_id"] = "LEAP-01A-base"

    job = build_jobs(spec_copy, series, adhyay=1)[0]
    assert job["method"] == "edit"
    assert job["base_edit_id"] == "LEAP-01A-base"


def test_unknown_character_refusal():
    """Test that unknown character ID raises ValueError."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    spec_copy["shots"][0]["characters"] = ["CHAR-UNKNOWN"]

    try:
        build_jobs(spec_copy, series, adhyay=1)
        assert False, "Expected ValueError for unknown character"
    except ValueError as e:
        assert "unknown character" in str(e).lower()
        assert "CHAR-UNKNOWN" in str(e)


def test_unknown_place_refusal():
    """Test that unknown place ID raises ValueError."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    spec_copy["shots"][0]["place"] = "ENV-UNKNOWN"

    try:
        build_jobs(spec_copy, series, adhyay=1)
        assert False, "Expected ValueError for unknown place"
    except ValueError as e:
        assert "unknown place" in str(e).lower()
        assert "ENV-UNKNOWN" in str(e)


def test_duplicate_shot_id_refusal():
    """Test that duplicate shot IDs in spec.shots raise ValueError."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    spec_copy = json.loads(json.dumps(spec))
    # Duplicate the first shot
    spec_copy["shots"].append(spec_copy["shots"][0].copy())

    try:
        build_jobs(spec_copy, series, adhyay=1)
        assert False, "Expected ValueError for duplicate shot_id"
    except ValueError as e:
        assert "duplicate shot_id" in str(e).lower()


def test_model_name_override():
    """Test that the series model name can be overridden (via --model-name in CLI)."""
    spec = load_json(SPEC_PATH)
    series = load_json(SERIES_PATH)

    jobs = build_jobs(spec, series, adhyay=1)
    original_model_name = jobs[0]["model"]["name"]

    series_copy = json.loads(json.dumps(series))
    series_copy["model"]["name"] = "Test Model 99"

    jobs2 = build_jobs(spec, series_copy, adhyay=1)
    assert jobs2[0]["model"]["name"] == "Test Model 99"
    assert jobs2[0]["model"]["name"] != original_model_name


def test_cli_writes_file_and_refuses_overwrite():
    """Test CLI writes output file and refuses to overwrite without --overwrite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test_jobs.json"
        spec_path = SPEC_PATH
        series_path = SERIES_PATH
        script_path = SCRIPTS_DIR / "build_jobs.py"

        # First run - should succeed
        result = subprocess.run([
            sys.executable, str(script_path),
            "--adhyay", "1",
            "--spec", str(spec_path),
            "--series", str(series_path),
            "--out", str(out_path)
        ], capture_output=True, text=True)

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert out_path.exists(), "Output file not created"

        # Verify content
        with open(out_path, "r", encoding="utf-8") as f:
            jobs = json.load(f)
        assert len(jobs) == 5

        # Second run without --overwrite - should fail
        result2 = subprocess.run([
            sys.executable, str(script_path),
            "--adhyay", "1",
            "--spec", str(spec_path),
            "--series", str(series_path),
            "--out", str(out_path)
        ], capture_output=True, text=True)

        assert result2.returncode != 0, "CLI should refuse overwrite without --overwrite"
        output = (result2.stdout + result2.stderr).lower()
        assert "refusing to overwrite" in output or "refuse to overwrite" in output

        # Third run with --overwrite - should succeed
        result3 = subprocess.run([
            sys.executable, str(script_path),
            "--adhyay", "1",
            "--spec", str(spec_path),
            "--series", str(series_path),
            "--out", str(out_path),
            "--overwrite"
        ], capture_output=True, text=True)

        assert result3.returncode == 0, f"CLI with --overwrite failed: {result3.stderr}"


if __name__ == "__main__":
    test_build_jobs_matches_reference()
    print("✓ test_build_jobs_matches_reference passed")

    test_forbidden_words_refusal()
    print("✓ test_forbidden_words_refusal passed")

    test_edit_job_without_base_edit_id_refusal()
    print("✓ test_edit_job_without_base_edit_id_refusal passed")

    test_edit_job_with_empty_base_edit_id_refusal()
    print("✓ test_edit_job_with_empty_base_edit_id_refusal passed")

    test_edit_job_with_pending_base_edit_id_refusal()
    print("✓ test_edit_job_with_pending_base_edit_id_refusal passed")

    test_unknown_character_refusal()
    print("✓ test_unknown_character_refusal passed")

    test_unknown_place_refusal()
    print("✓ test_unknown_place_refusal passed")

    test_duplicate_shot_id_refusal()
    print("✓ test_duplicate_shot_id_refusal passed")

    test_model_name_override()
    print("✓ test_model_name_override passed")

    test_cli_writes_file_and_refuses_overwrite()
    print("✓ test_cli_writes_file_and_refuses_overwrite passed")

    print("\nAll tests passed!")
