"""Hardening tests for path traversal, ID safety, picture path validation, and sound plan rules."""
import json
import os
import pytest

from h3.schema_and_linter import lint_story, ID_PATTERN
from h3.render_controller import load_story, prepare, _safe_join
from h3.tests.synth import build_story, SHOT_IDS


# ---------- ID safety (ID-01) ----------

@pytest.mark.parametrize("bad_id", [
    "../x", "a/b", "/absolute", "C:\\abs", "", "a" * 70, "a" * 65,
])
def test_unsafe_ids_rejected_by_lint(tmp_path, bad_id):
    story = build_story(str(tmp_path))
    story["episodes"][0]["episode_id"] = bad_id
    res = lint_story(story)
    assert any("ID-01" in e and "episode" in e for e in res["errors"])

    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["shot_id"] = bad_id
    res = lint_story(story)
    assert any("ID-01" in e and "shot" in e for e in res["errors"])


def test_controller_refuses_unsafe_episode_id(tmp_path, capsys):
    story = build_story(str(tmp_path))
    story["episodes"][0]["episode_id"] = "../evil"
    path = tmp_path / "story.json"
    path.write_text(json.dumps(story))
    out = tmp_path / "out"
    code, text = rc_main(["--story-file", str(path), "--scope", "all", "--out-dir", str(out)], capsys)
    assert code == 1
    assert "ID-01" in text or "unsafe" in text
    assert not out.exists()


def test_controller_refuses_unsafe_shot_id(tmp_path, capsys):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["shot_id"] = "a/b"
    path = tmp_path / "story.json"
    path.write_text(json.dumps(story))
    out = tmp_path / "out"
    code, text = rc_main(["--story-file", str(path), "--scope", "all", "--out-dir", str(out)], capsys)
    assert code == 1
    assert "ID-01" in text or "unsafe" in text
    assert not out.exists()


# ---------- Picture path validation (KF-07) ----------

@pytest.mark.parametrize("bad_rel", ["../evil.png", "sub/../evil.png", "/absolute.png", "C:\\evil.png"])
def test_picture_path_with_traversal_rejected_by_lint(tmp_path, bad_rel):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["fl2va_keyframes"]["picture_1_path"] = bad_rel
    res = lint_story(story)
    assert any("KF-07" in e and "picture_1" in e for e in res["errors"])


@pytest.mark.parametrize("bad_rel", ["../evil.png", "sub/../evil.png", "/absolute.png", "C:\\evil.png"])
def test_flow_source_path_with_traversal_rejected_by_lint(tmp_path, bad_rel):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["fl2va_keyframes"]["flow_source_a"] = bad_rel
    res = lint_story(story)
    assert any("KF-07" in e and "flow_source_a" in e for e in res["errors"])


# ---------- Controller never writes/deletes outside out folder ----------

def test_safe_join_prevents_traversal(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    target = _safe_join(str(base), "sub", "file.txt")
    assert target == base / "sub" / "file.txt"
    with pytest.raises(ValueError):
        _safe_join(str(base), "..", "outside.txt")
    with pytest.raises(ValueError):
        _safe_join(str(base), "/absolute.txt")


def test_controller_does_not_write_outside_out_dir(tmp_path, capsys, monkeypatch):
    # _safe_join is the last line of defence: if it ever resolves outside the build
    # folder the controller must refuse cleanly (exit 1) and write nothing.
    story = build_story(str(tmp_path))
    path = tmp_path / "story.json"
    path.write_text(json.dumps(story))
    out = tmp_path / "out"
    import h3.render_controller as rc
    def bad_safe_join(base, *parts):
        raise ValueError("path traversal attempt: resolved target is outside the build folder")
    monkeypatch.setattr(rc, "_safe_join", bad_safe_join)
    code, text = rc_main(["--story-file", str(path), "--scope", "all", "--out-dir", str(out)], capsys)
    assert code == 1
    assert "path traversal attempt" in text
    # No executable files should have been written
    assert not any(out.rglob("*.txt")) and not any(out.rglob("*.json"))


# ---------- Sound plan SD-01 ----------

def test_sd01_empty_soundscape(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["sound_plan"]["overall_soundscape"] = ""
    res = lint_story(story)
    assert any("SD-01" in e and "non-empty" in e for e in res["errors"])


def test_sd01_short_soundscape(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["sound_plan"]["overall_soundscape"] = "Short."
    res = lint_story(story)
    assert any("SD-01" in e and "too short" in e for e in res["errors"])


def test_sd01_music_not_na(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["sound_plan"]["non_diegetic_music"] = "Some music"
    res = lint_story(story)
    assert any("SD-01" in e and "N/A" in e for e in res["errors"])


def test_sd01_music_na_case_insensitive(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["sound_plan"]["non_diegetic_music"] = "n/a"
    res = lint_story(story)
    assert not any("SD-01" in e and "N/A" in e for e in res["errors"])


def test_sd01_allow_model_music_profile_flag(tmp_path):
    story = build_story(str(tmp_path))
    story["registry"]["execution_profile"]["allow_model_music"] = True
    story["episodes"][0]["shots"][0]["sound_plan"]["non_diegetic_music"] = "Epic orchestral score"
    res = lint_story(story)
    assert not any("SD-01" in e and "N/A" in e for e in res["errors"])


def test_sd01_passing_case(tmp_path):
    story = build_story(str(tmp_path))
    # The synthetic story already has a valid soundscape and music "N/A"
    res = lint_story(story)
    assert not any("SD-01" in e for e in res["errors"])


# ---------- Sound plan SD-02 warning ----------

def test_sd02_warning_when_no_keywords(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["sound_plan"]["overall_soundscape"] = "A completely silent void with no audible cues at all."
    res = lint_story(story)
    assert any("SD-02" in w for w in res["warnings"])


def test_sd02_no_warning_when_keywords_present(tmp_path):
    story = build_story(str(tmp_path))
    # The synthetic story already contains "Rain", "wind", etc.
    res = lint_story(story)
    assert not any("SD-02" in w for w in res["warnings"])


# ---------- Helper to run controller main ----------

def rc_main(argv, capsys):
    import h3.render_controller as rc
    code = rc.main(argv)
    out = capsys.readouterr().out
    return code, out
