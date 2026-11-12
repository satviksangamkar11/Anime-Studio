"""Tests for tools/convert_deva_shots.py --h3 (A25) and the flat-mode guard. Reads the DEVA template copy in
core/tests/fixtures. No network, no model calls, nothing written into the repo (tmp_path only)."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from core.style_pack import load_pack
from h3.schema_and_linter import SHOT_KEYS, lint_story, load_default_profile

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "deva_shots_template.json"
TOOL = REPO / "tools" / "convert_deva_shots.py"

_spec = importlib.util.spec_from_file_location("convert_deva_shots", TOOL)
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)

# sha256 of the flat-mode output for the fixture (--pack deva_neon), recorded before the --h3 change.
FLAT_SHA256 = "cc67d5f018b2852b88281facacf83de0e5435663aeaeb0fcf93145fcfe8f82bf"

# Known linter ERRORs on the converted template. Every one comes from template content or registry content the
# DEVA template does not carry, not from a converter bug:
#   KF-02  the keyframes/SHOT-xx-FRAME-*.png files named by the template are not in the repo (asset_root is empty)
#   SD-01  the template's `sound` text is 37 characters on SHOT-01 and SHOT-02 (linter needs at least 40)
#   CM-01  SHOT-03 camera text "snap zoom to eye, then hold as dust clears" names no official camera motion
#   PR-05  the compiled prompt body is 328-359 chars; the linter needs at least 450 (the template is thin, and the
#          registry style_lock prefix below is a placeholder, so this count is for the test registry only)
#   SX-01  retired per stage (M-01, 2026-11-12): sound cues live in overall_soundscape; no longer an error here
#   CM-05  SHOT-03 has no mappable camera motion, so its description has 0 camera sentences (M-03; same root cause as CM-01)
#   (M-31: PR-05 min is the interim 450 and the body is 328-359 chars after M-01b/M-03; 600 breaks h3 test_h3_author)
#          (MO-01 is satisfied by the converter: narrator_mouth_closed true, mouth_state closed)
KNOWN_ERRORS = sorted([
    "SHOT-01: KF-02 picture_1 file missing: keyframes/SHOT-01-FRAME-A.png",
    "SHOT-01: KF-02 picture_2 file missing: keyframes/SHOT-01-FRAME-B.png",
    "SHOT-01: PR-05 description length 336 outside [450, 4000]",
    "SHOT-01: SD-01 sound_plan.overall_soundscape too short (37 chars), need at least 40",
    "SHOT-02: KF-02 picture_1 file missing: keyframes/SHOT-02-FRAME-A.png",
    "SHOT-02: KF-02 picture_2 file missing: keyframes/SHOT-02-FRAME-B.png",
    "SHOT-02: PR-05 description length 333 outside [450, 4000]",
    "SHOT-02: SD-01 sound_plan.overall_soundscape too short (37 chars), need at least 40",
    "SHOT-03: CM-01 motion_type None is not an official camera motion",
    "SHOT-03: CM-05 the description has 0 camera sentences, need exactly 1",
    "SHOT-03: KF-02 picture_1 file missing: keyframes/SHOT-03-FRAME-A.png",
    "SHOT-03: KF-02 picture_2 file missing: keyframes/SHOT-03-FRAME-B.png",
    "SHOT-03: PR-05 description length 328 outside [450, 4000]",
    "SHOT-04: KF-02 picture_1 file missing: keyframes/SHOT-04-FRAME-A.png",
    "SHOT-04: KF-02 picture_2 file missing: keyframes/SHOT-04-FRAME-B.png",
    "SHOT-04: PR-05 description length 359 outside [450, 4000]",
])


def template():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def h3_shots():
    return conv.to_h3(conv.convert(template(), load_pack("deva_neon")), load_default_profile("sing8_864x1536"))


def story_for(shots, asset_root):
    """Test registry only. The DEVA template carries no registry: execution profile is the real sing8 profile,
    style_lock is a placeholder prefix (no error depends on its wording), and characters is empty (no speech)."""
    reg = {"execution_profile": load_default_profile("sing8_864x1536"),
           "style_lock": {"mandatory_prefix": "PLACEHOLDER STYLE", "banned_style_tokens": []},
           "characters": {}}
    return {"registry": reg, "episodes": [{"episode_id": "EP1", "asset_root": str(asset_root), "shots": shots}]}


def test_flat_mode_output_is_unchanged(tmp_path):
    out = tmp_path / "flat.json"
    r = subprocess.run([sys.executable, str(TOOL), str(FIXTURE), "--out", str(out), "--pack", "deva_neon"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert hashlib.sha256(out.read_bytes()).hexdigest() == FLAT_SHA256
    assert all("metadata" not in s for s in json.loads(out.read_text(encoding="utf-8")))


def test_h3_shot_shape_has_no_extra_top_level_keys():
    shots = h3_shots()
    assert [s["shot_id"] for s in shots] == ["SHOT-01", "SHOT-02", "SHOT-03", "SHOT-04"]
    for s in shots:
        assert SHOT_KEYS <= set(s) <= SHOT_KEYS | {"metadata"}
        assert "look" not in s and "converter_notes" not in s
        assert {"look", "converter_notes"} <= set(s["metadata"])
        assert s["metadata"]["look"]["palette_id"] == "shiva_neelkanth"


def test_h3_timing_windows_and_seams_follow_the_linter_rules():
    shots = h3_shots()
    first = shots[0]["timing_and_lattice"]
    assert (first["lattice_n"], first["pixel_frames"], first["editorial_frames"]) == (6, 107, 72)
    assert first["master_reel_frame_window"] == [0, 72]
    assert shots[1]["timing_and_lattice"]["master_reel_frame_window"] == [72, 168]
    assert shots[0]["continuity_and_seam_lock"]["incoming_seam_type"] == "INTER_REEL_HANDSHAKE"
    assert shots[1]["continuity_and_seam_lock"]["incoming_seam_type"] == "DYNAMIC_MATCH_ON_ACTION"
    assert shots[1]["timing_and_lattice"]["head_handle_frames"] == 12


def test_h3_linter_reports_exactly_the_known_template_gaps(tmp_path):
    r = lint_story(story_for(h3_shots(), tmp_path))  # tmp_path holds no keyframe PNGs
    assert sorted(r["errors"]) == KNOWN_ERRORS


def test_unmappable_values_go_to_converter_notes_not_h3_fields():
    shots = h3_shots()
    notes3 = shots[2]["metadata"]["converter_notes"]
    assert any("camera motion not determinable" in n for n in notes3)
    assert shots[2]["camera"]["motion_type"] is None
    assert any("white_flash" in n for n in notes3)
    assert "white_flash" not in json.dumps(shots[2]["timing_and_lattice"])
    assert any("location_id UNSET" in n for n in shots[0]["metadata"]["converter_notes"])


def test_malformed_shot_does_not_raise():
    bad = [{"id": "SHOT-09", "episode": 1, "seconds": "soon", "mode": "fl2va", "action": None,
            "camera": None, "sound": None}]
    out = conv.to_h3(bad, load_default_profile("sing8_864x1536"))
    assert out[0]["timing_and_lattice"]["editorial_frames"] == conv.DEFAULT_SECONDS * 24
    assert any("seconds 'soon' missing or not positive" in n for n in out[0]["metadata"]["converter_notes"])


def test_cli_h3_writes_the_same_shots_as_to_h3(tmp_path):
    out = tmp_path / "h3.json"
    r = subprocess.run([sys.executable, str(TOOL), str(FIXTURE), "--h3", "--out", str(out), "--pack", "deva_neon"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    assert json.loads(raw.decode("utf-8")) == h3_shots()
