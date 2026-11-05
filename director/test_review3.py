"""Third review (plan v4.3, phase 1B): rich shots must pass validate_shot before settings are built; h3_director.main refuses
duplicate ids before writing and needs a style project."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import h3_director
from h3_director import main, settings_for
from test_shot_schema import RICH

DIRECTOR = Path(__file__).resolve().parent


def test_a_rich_shot_that_validate_shot_rejects_is_refused():
    with pytest.raises(ValueError, match="beats end at 5.2"):
        settings_for(dict(RICH, render_frames=107))


def test_warnings_do_not_block_a_rich_shot():
    no_primary = dict(RICH, beats=[dict(b, primary=False) for b in RICH["beats"]])
    assert settings_for(no_primary)["video_length"] == 124   # validate_shot reports only a WARN here


def test_main_refuses_duplicate_ids_before_writing_anything(tmp_path):
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([RICH, dict(RICH, seconds=5.2, render_frames=124)]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        main(str(shots), str(tmp_path / "out"), "kaliya_mardan")
    out = tmp_path / "out"
    assert not out.exists() or not list(out.glob("settings_*.json"))


def test_main_writes_settings_and_direction_with_the_style_bible(tmp_path):
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([RICH]), encoding="utf-8")
    main(str(shots), str(tmp_path / "out"), "kaliya_mardan")
    s = json.loads((tmp_path / "out" / "settings_SHOT-07.json").read_text(encoding="utf-8"))
    assert s["video_length"] == 124 and "Kadamba bank" in s["prompt"] and "Style: " in s["prompt"]
    assert (tmp_path / "out" / "SHOT-07.direction.json").exists()


def test_main_needs_a_style_project_on_the_command_line(tmp_path):
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([RICH]), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(DIRECTOR / "h3_director.py"), str(shots), str(tmp_path / "out")],
                          capture_output=True, text=True)
    assert proc.returncode != 0 and "style_project" in proc.stderr + proc.stdout
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").glob("settings_*.json"))
