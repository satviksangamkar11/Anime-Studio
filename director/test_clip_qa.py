"""Test file for director/clip_qa.py (X-14). Frozen test gate."""
import sys
import os
import json
import subprocess
import hashlib
import wave
import numpy as np
import pytest

# Add paths to import modules by bare name
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clip_qa
import clip_gates
import blocking
import score.sfx_study as sfx_study


def test_extract_window_count(tmp_path):
    """Test that extract returns exactly (trim_out - trim_in) frames."""
    clip_path = tmp_path / "test_clip.avi"
    # Generate a test clip with exactly 184 frames using lavfi testsrc
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "testsrc=size=768x1344:rate=24:duration=7.6667",
        "-frames:v", "184",
        "-c:v", "rawvideo",
        "-pix_fmt", "gray",
        "-f", "avi",
        str(clip_path)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Extract frames from 8 to 176 (168 frames)
    frames = clip_qa.extract(str(clip_path), 8, 176)
    
    # Check shape: (frames, height, width) = (168, 336, 192)
    assert frames.shape == (168, 336, 192), f"Unexpected shape: {frames.shape}"
    assert frames.dtype == np.float32
    assert frames.min() >= 0.0
    assert frames.max() <= 1.0


def test_snake_not_known_blocks(tmp_path):
    """Test that a class not in the known classes blocks the verdict."""
    # Shot sheet as JSON: blocking.known_classes reads props[].class (person is always known)
    sheet_path = tmp_path / "sheet.json"
    sheet_path.write_text(json.dumps({"props": [{"class": "dog"}, {"class": "car"}]}))
    
    # Create a clip_review.json with a 'snake' class (not in sheet)
    clip_review_path = tmp_path / "clip_review.json"
    # Format: dict mapping frame number (as string) to dict of class counts
    review_data = {
        "0": {"snake": 1},
        "6": {"dog": 2},
    }
    clip_review_path.write_text(json.dumps(review_data))
    
    # Get new classes from clip_qa
    new_classes = clip_qa.new_classes(str(clip_review_path), str(sheet_path))
    assert "snake" in new_classes, "Snake should be flagged as new class"
    
    # Build verdict input; D-CLIP requires all keys
    verdict_input = {
        "tail": {"flag": False},
        "end": {"pass": True, "failed": []},
        "cuts": [],
        "new_classes": new_classes,
        "flicker": 0.0,
        "flicker_limit": 0.1,
    }
    verdict = clip_gates.verdict(verdict_input)
    # Verdict should indicate failure (block) with a NEW_CLASS reason
    assert verdict["pass"] is False, "Verdict should fail when new_classes is non-empty"
    assert [r["code"] for r in verdict["reasons"]] == ["NEW_CLASS"]


def test_malformed_review_raises(tmp_path):
    """Negative case: a clip_review whose frame value is not a class-count object is refused with ClipQAError."""
    sheet_path = tmp_path / "sheet.json"
    sheet_path.write_text(json.dumps({"props": []}))
    review_path = tmp_path / "clip_review.json"
    review_path.write_text(json.dumps({"0": ["snake"]}))
    with pytest.raises(clip_qa.ClipQAError):
        clip_qa.new_classes(str(review_path), str(sheet_path))


def test_clean_clip_has_no_problems(tmp_path):
    """Negative case: matching sha and a passing verdict give no problems."""
    clip_path = tmp_path / "clip.avi"
    clip_path.write_bytes(b"clean clip")
    qa_dir = tmp_path / "results" / "S003"
    qa_dir.mkdir(parents=True)
    qa_path = qa_dir / "clip_qa.json"
    qa_path.write_text(json.dumps({
        "clip_sha256": hashlib.sha256(b"clean clip").hexdigest(),
        "window": [0, 10],
        "results": {},
        "verdict": {"pass": True, "reasons": [], "accepted": []},
        "sfx_keep": [],
        "bed_db": -30.0,
        "owner_accept": None,
    }))
    assert clip_qa.clip_ok(str(qa_path), str(clip_path)) == []


def test_extract_frame_count_mismatch_raises(tmp_path):
    """Negative case: a window that does not match the frame count is refused."""
    clip_path = tmp_path / "short.avi"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=768x1344:rate=24:duration=7.6667",
        "-frames:v", "184", "-c:v", "rawvideo", "-pix_fmt", "gray", "-f", "avi", str(clip_path)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Asking for frames 8..200 of a 184-frame clip gives fewer frames than trim_out - trim_in
    with pytest.raises(clip_qa.ClipQAError):
        clip_qa.extract(str(clip_path), 8, 200)


def test_accept_rejects_unknown_code(tmp_path):
    """Negative case: accept refuses a code the gate does not know."""
    qa_dir = tmp_path / "results" / "S004"
    qa_dir.mkdir(parents=True)
    (qa_dir / "clip_qa.json").write_text(json.dumps({"clip_sha256": "x", "verdict": {"pass": False},
                                                     "owner_accept": None}))
    with pytest.raises(clip_qa.ClipQAError):
        clip_qa.accept("S004", "MADE_UP_CODE", "note", root=str(tmp_path))


def test_owner_accept_unblocks_and_is_recorded(tmp_path):
    """Test that owner accept records and unblocks clip_ok."""
    # Create a dummy clip file (not a real video, just for sha)
    clip_path = tmp_path / "clip.avi"
    clip_content = b"dummy clip content for sha"
    clip_path.write_bytes(clip_content)
    clip_sha = hashlib.sha256(clip_content).hexdigest()
    
    # Create results directory and clip_qa.json with failing verdict
    shot = "S001"
    results_dir = tmp_path / "results" / shot
    results_dir.mkdir(parents=True)
    qa_json_path = results_dir / "clip_qa.json"
    qa_data = {
        "clip_sha256": clip_sha,
        "window": [0, 10],
        "results": {},
        "verdict": {"pass": False, "reasons": [{"code": "NEW_CLASS", "text": "snake"}], "accepted": []},
        "sfx_keep": [],
        "bed_db": 0.0,
        "owner_accept": None,
    }
    qa_json_path.write_text(json.dumps(qa_data))
    
    # Before accept, clip_ok should report a problem (verdict fail without owner_accept)
    problems_before = clip_qa.clip_ok(str(qa_json_path), str(clip_path))
    assert len(problems_before) > 0, "Should have problems before accept"
    
    # Call accept to record owner acceptance
    clip_qa.accept(shot, "NEW_OBJECT", "test note", root=str(tmp_path))
    
    # After accept, clip_ok should not report the verdict problem (unblocks)
    problems_after = clip_qa.clip_ok(str(qa_json_path), str(clip_path))
    assert len(problems_after) == 0, "Should have no problems after accept"
    
    # Verify that owner_accept was recorded in the JSON
    updated_qa = json.loads(qa_json_path.read_text())
    # owner_accept is a list of records since the multi-accept change (was a single dict)
    assert isinstance(updated_qa["owner_accept"], list) and len(updated_qa["owner_accept"]) == 1
    assert updated_qa["owner_accept"][0]["code"] == "NEW_OBJECT"
    assert "note" in updated_qa["owner_accept"][0]
    assert "date" in updated_qa["owner_accept"][0] and "at" not in updated_qa["owner_accept"][0]


def test_extract_uses_vsync_zero_as_the_card_says(tmp_path):
    """X-14: the ffmpeg call passes -vsync 0 (card), not -fps_mode; the fake run returns 2 gray 192x336 frames."""
    seen = {}

    class Done:
        stdout = np.zeros((2, 336, 192), dtype=np.uint8).tobytes()

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return Done()

    clip_qa.extract(str(tmp_path / "c.avi"), 0, 2, run=fake_run)
    cmd = seen["cmd"]
    assert cmd[cmd.index("-vsync") + 1] == "0" and "-fps_mode" not in cmd, cmd


def test_features_records_that_lpips_was_not_measured():
    """X-14: the end record says lpips was not measured, not only a code comment."""
    rng = np.random.default_rng(0)
    frames = rng.random((6, 336, 192), dtype=np.float32)  # flicker needs 3 of every 2nd frame
    key = rng.random((336, 192), dtype=np.float32)
    end = clip_qa.features(frames, key, key)["end"]
    assert end["lpips"] == 0.0 and end["lpips_note"] == "lpips not measured"


def test_sha_mismatch_blocks(tmp_path):
    """Test that sha mismatch is reported as a problem."""
    clip_path = tmp_path / "clip.avi"
    clip_content = b"real clip content"
    clip_path.write_bytes(clip_content)
    real_sha = hashlib.sha256(clip_content).hexdigest()
    
    shot = "S002"
    results_dir = tmp_path / "results" / shot
    results_dir.mkdir(parents=True)
    qa_json_path = results_dir / "clip_qa.json"
    # Use a wrong sha
    qa_data = {
        "clip_sha256": "wrongsha00000000000000000000000000000000000000000000",
        "window": [0, 10],
        "results": {},
        "verdict": {"pass": True, "reasons": [], "accepted": []},
        "sfx_keep": [],
        "bed_db": 0.0,
        "owner_accept": None,
    }
    qa_json_path.write_text(json.dumps(qa_data))
    
    problems = clip_qa.clip_ok(str(qa_json_path), str(clip_path))
    # Check that there is a problem mentioning sha or mismatch
    sha_problem_found = any("sha" in p.lower() or "mismatch" in p.lower() for p in problems)
    assert sha_problem_found, f"Should report sha mismatch, got: {problems}"


def test_sfx_keep_matches_cue(tmp_path):
    """Test that a click at 2.0s matches a cue at 2.1s within tolerance 0.4."""
    # Create synthetic audio with a click at 2.0s
    audio_path = tmp_path / "test_audio.wav"
    sample_rate = 48000
    duration = 5.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    signal = np.zeros_like(t)
    # Click: short sine burst at 1000 Hz, 0.01s duration, at 2.0s
    click_start = 2.0
    click_end = 2.01
    click_mask = (t >= click_start) & (t <= click_end)
    signal[click_mask] = 0.5 * np.sin(2 * np.pi * 1000 * t[click_mask])
    # Convert to 16-bit PCM
    audio_data = (signal * 32767).astype(np.int16)
    # Write WAV
    with wave.open(str(audio_path), 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio_data.tobytes())
    
    # Create sheet with a sound cue at 2.1s
    sheet = {
        "sound_cues": [
            {"t": 2.1, "name": "test_cue"}
        ]
    }
    
    # Call the audio analysis function from clip_qa
    # Assume function returns (sfx_keep, bed_db)
    sfx_keep, bed_db = clip_qa.audio_analysis(str(audio_path), sheet)
    
    # sfx_keep should be a list of (t0, t1) tuples
    # Check that there is a kept interval that matches the click (near 2.0s)
    found = False
    for t0, t1 in sfx_keep:
        if abs(t0 - 2.0) < 0.4:  # tolerance 0.4 as per card
            found = True
            break
    assert found, f"No sfx_keep interval near 2.0s: {sfx_keep}"
    
    # bed_db should be a float
    assert isinstance(bed_db, float)


def _lock_fixture(tmp_path):
    """A real timeline lock (one shot, 10 frames) over one voice file. Returns (lock_path, voice_path)."""
    import timeline_lock_io
    voice = tmp_path / "lock_in" / "voice.wav"
    voice.parent.mkdir(parents=True)
    voice.write_bytes(b"voice v1")
    shot = {"id": "S001", "start_frame": 0, "edit_frames": 10, "pixel_frames": 107, "trim_in_frame": 0,
            "trim_out_frame": 10, "end_frame_position": 9, "error_ms": 0.0}
    lock_path = tmp_path / "lock" / "timeline_lock_v1.json"
    lock_path.parent.mkdir(parents=True)
    timeline_lock_io.write_lock(lock_path, [shot], [voice], {"margin_frames": 6}, fps=24)
    return lock_path, voice


def _qa_doc(tmp_path, shot, codes, clip_bytes=b"clip bytes"):
    """clip_qa.json for one shot with a failed verdict carrying the given reason codes. Returns (qa_path, clip)."""
    clip = tmp_path / shot / "clip.avi"
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(clip_bytes)
    qa_dir = tmp_path / "results" / shot
    qa_dir.mkdir(parents=True, exist_ok=True)
    qa_path = qa_dir / "clip_qa.json"
    reasons = [{"code": c, "text": "x"} for c in codes]
    qa_path.write_text(json.dumps({
        "clip_sha256": hashlib.sha256(clip_bytes).hexdigest(), "window": [0, 10], "results": {},
        "verdict": {"pass": False, "reasons": reasons, "accepted": []}, "sfx_keep": [], "bed_db": 0.0,
        "owner_accept": None}))
    return qa_path, clip


def test_qa_shot_refuses_a_stale_lock_before_any_analysis(tmp_path):
    """A lock whose voice file changed is refused before ffmpeg runs, and no clip_qa.json is written."""
    lock_path, voice = _lock_fixture(tmp_path)
    voice.write_bytes(b"voice v2 changed")
    root = tmp_path / "root"
    with pytest.raises(clip_qa.ClipQAError, match="stale timeline lock"):
        clip_qa.qa_shot("S001", str(tmp_path / "missing.avi"), str(lock_path), None, None,
                        str(tmp_path / "review.json"), {}, str(voice), str(root))
    assert not (root / "results" / "S001" / "clip_qa.json").exists()


def test_qa_shot_refuses_a_missing_lock(tmp_path):
    """A lock file that does not exist is refused with ClipQAError, not a bare FileNotFoundError."""
    with pytest.raises(clip_qa.ClipQAError, match="missing timeline lock"):
        clip_qa.qa_shot("S001", str(tmp_path / "x.avi"), str(tmp_path / "nope.json"), None, None,
                        str(tmp_path / "review.json"), {}, str(tmp_path / "v.wav"), str(tmp_path / "root"))


def test_accept_of_flicker_does_not_clear_new_class(tmp_path):
    """Negative case: an owner accept of FLICKER leaves a NEW_CLASS failure blocked."""
    qa_path, clip = _qa_doc(tmp_path, "S010", ["NEW_CLASS"])
    clip_qa.accept("S010", "FLICKER", "unrelated accept", root=str(tmp_path))
    problems = clip_qa.clip_ok(str(qa_path), str(clip))
    assert len(problems) == 1 and problems[0].endswith("NEW_CLASS"), problems


def test_accept_clears_only_its_own_code(tmp_path):
    """Two failures, accept of NEW_CLASS only: FLICKER is still reported as the open problem."""
    qa_path, clip = _qa_doc(tmp_path, "S011", ["NEW_CLASS", "FLICKER"])
    clip_qa.accept("S011", "NEW_CLASS", "owner saw the dog", root=str(tmp_path))
    problems = clip_qa.clip_ok(str(qa_path), str(clip))
    assert len(problems) == 1 and problems[0].endswith("FLICKER"), problems


def test_accept_of_new_class_clears_new_class(tmp_path):
    """Positive case: accept with the reason code itself clears that failure."""
    qa_path, clip = _qa_doc(tmp_path, "S012", ["NEW_CLASS"])
    clip_qa.accept("S012", "NEW_CLASS", "owner accepts the dog", root=str(tmp_path))
    assert clip_qa.clip_ok(str(qa_path), str(clip)) == []


def test_critical_code_is_refused_at_accept(tmp_path):
    """Negative case: CRITICAL failures (frame count, corrupt) can never be accepted."""
    _qa_doc(tmp_path, "S013", ["FRAME_COUNT"])
    for code in ("FRAME_COUNT", "CORRUPT"):
        with pytest.raises(clip_qa.ClipQAError):
            clip_qa.accept("S013", code, "owner note", root=str(tmp_path))


def test_each_code_needs_its_own_accept(tmp_path):
    """Positive case: NEW_CLASS and END_MISMATCH each need a record; after both, the clip is clear."""
    qa_path, clip = _qa_doc(tmp_path, "S015", ["NEW_CLASS", "END_MISMATCH"])
    clip_qa.accept("S015", "NEW_CLASS", "owner saw the dog", root=str(tmp_path))
    problems = clip_qa.clip_ok(str(qa_path), str(clip))
    assert len(problems) == 1 and problems[0].endswith("END_MISMATCH"), problems
    clip_qa.accept("S015", "END_MISMATCH", "owner accepts the end frame", root=str(tmp_path))
    assert clip_qa.clip_ok(str(qa_path), str(clip)) == []
    assert [r["code"] for r in json.loads(qa_path.read_text(encoding="utf-8"))["owner_accept"]] == [
        "NEW_CLASS", "END_MISMATCH"]


def test_accept_new_object_alone_leaves_the_other_two_blocked(tmp_path):
    """Negative case: NEW_OBJECT clears NEW_CLASS only; END_MISMATCH and SCENE_CUT stay blocked."""
    qa_path, clip = _qa_doc(tmp_path, "S016", ["NEW_CLASS", "END_MISMATCH", "SCENE_CUT"])
    clip_qa.accept("S016", "NEW_OBJECT", "owner saw the dog", root=str(tmp_path))
    problems = clip_qa.clip_ok(str(qa_path), str(clip))
    assert len(problems) == 1 and problems[0].endswith("END_MISMATCH, SCENE_CUT"), problems


def test_same_code_accepted_twice_is_a_noop(tmp_path):
    """Negative case: a second accept of the same code adds no record."""
    qa_path, _clip = _qa_doc(tmp_path, "S017", ["FLICKER"])
    first = clip_qa.accept("S017", "FLICKER", "first note", root=str(tmp_path))
    again = clip_qa.accept("S017", "FLICKER", "second note", root=str(tmp_path))
    assert again == first
    assert len(json.loads(qa_path.read_text(encoding="utf-8"))["owner_accept"]) == 1


def test_legacy_single_dict_accept_still_clears(tmp_path):
    """Positive case: an old clip_qa.json with one dict owner_accept is still read and clears its code."""
    qa_path, clip = _qa_doc(tmp_path, "S018", ["FLICKER"])
    doc = json.loads(qa_path.read_text(encoding="utf-8"))
    doc["owner_accept"] = {"code": "FLICKER", "date": "2026-11-11", "note": "old form"}
    qa_path.write_text(json.dumps(doc), encoding="utf-8")
    assert clip_qa.clip_ok(str(qa_path), str(clip)) == []


def test_critical_code_blocks_even_with_a_recorded_accept(tmp_path):
    """Negative case: a hand-written owner_accept of a CRITICAL code does not clear the clip."""
    qa_path, clip = _qa_doc(tmp_path, "S014", ["CORRUPT"])
    doc = json.loads(qa_path.read_text(encoding="utf-8"))
    doc["owner_accept"] = {"code": "CORRUPT", "date": "2026-11-11", "note": "x"}
    qa_path.write_text(json.dumps(doc), encoding="utf-8")
    problems = clip_qa.clip_ok(str(qa_path), str(clip))
    assert problems and "CORRUPT" in problems[0], problems
