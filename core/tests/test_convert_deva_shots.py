"""Tests for tools/convert_deva_shots.py (flat mode). Reads the DEVA template copy in core/tests/fixtures. No network."""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from core.style_pack import load_pack

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "deva_shots_template.json"
TOOL = REPO / "tools" / "convert_deva_shots.py"

_spec = importlib.util.spec_from_file_location("convert_deva_shots", TOOL)
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)

MOVED = {"palette_id", "grade", "hook_type", "impact_frames", "vfx_tokens"}


def template():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def converted():
    return conv.convert(template(), load_pack("deva_neon"))


def by_id(shots):
    return {s["id"]: s for s in shots}


def test_moved_keys_leave_the_top_level_and_others_stay():
    src = template()
    out = conv.convert(copy.deepcopy(src), load_pack("deva_neon"))
    for before, after in zip(src, out):
        assert not (MOVED & set(after))
        assert {k: v for k, v in before.items() if k not in MOVED} == \
            {k: v for k, v in after.items() if k not in ("look", "converter_notes")}


def test_input_is_not_mutated():
    src = template()
    before = copy.deepcopy(src)
    conv.convert(src, load_pack("deva_neon"))
    assert src == before


def test_look_block_fields_and_act_from_grade():
    shots = by_id(converted())
    look = shots["SHOT-01"]["look"]
    assert look["palette_id"] == "shiva_neelkanth"
    assert look["act"] == "HOOK" and look["phase"] == "PH-HOOK"
    assert look["focal"] == "CHAR-SHIVA" and look["focal_value"] == "lightest"
    assert look["accent_use"] is False and look["hold_purpose"] is None
    assert shots["SHOT-02"]["look"]["act"] == "BUILD" and shots["SHOT-02"]["look"]["phase"] == "PH-BUILD"
    assert shots["SHOT-03"]["look"]["phase"] == "PH-DROP"
    assert shots["SHOT-04"]["look"]["phase"] == "PH-OUTRO"


def test_hook_only_on_first_shot_with_placeholder_caption():
    shots = by_id(converted())
    assert shots["SHOT-01"]["look"]["hook"] == {"type": "H-03", "caption": "<hook caption>"}
    for sid in ("SHOT-02", "SHOT-03", "SHOT-04"):
        assert "hook" not in shots[sid]["look"]
    assert any("<hook caption>" in n for n in shots["SHOT-01"]["converter_notes"])


def test_impact_name_becomes_seconds_from_the_action_range_end():
    shots = by_id(converted())
    # SHOT-02 "trishul_rest": first name word "trishul" is in the 0.0-2.0 s range
    assert shots["SHOT-02"]["look"]["impact_frames"] == [{"at_s": 2.0, "type": "white_out", "frames": 2}]
    # SHOT-03 "eye_open": the 1.0-2.5 s range holds both "eye" and "open" (opens)
    assert shots["SHOT-03"]["look"]["impact_frames"] == [{"at_s": 2.5, "type": "inverted", "frames": 2}]
    assert shots["SHOT-01"]["look"]["impact_frames"] == []


def test_vfx_tokens_map_to_neon_colours_with_roles():
    shots = by_id(converted())
    # cyan_core -> Neel Cyan, role energy; saffron_edge -> Trialokya Saffron, role edge (not third eye)
    assert shots["SHOT-02"]["look"]["vfx"] == [{"color": "Neel Cyan", "role": "energy"},
                                               {"color": "Trialokya Saffron", "role": "edge"}]
    assert shots["SHOT-01"]["look"]["vfx"] == [{"color": "Neel Cyan", "role": "rim"},
                                               {"color": "Neel Cyan", "role": "fog"}]
    # saffron_burn gets third_eye only because SHOT-03's action mentions the third eye
    assert shots["SHOT-03"]["look"]["vfx"] == [{"color": "Trialokya Saffron", "role": "third_eye"}]


def test_unmatched_token_is_dropped_and_noted_on_the_shot_not_in_look():
    shots = by_id(converted())
    assert all("white_flash" not in json.dumps(s["look"]) for s in shots.values())
    assert any("white_flash" in n for n in shots["SHOT-03"]["converter_notes"])
    assert "converter_notes" not in shots["SHOT-04"]


def test_output_is_deterministic():
    a = json.dumps(converted(), indent=2, ensure_ascii=False)
    b = json.dumps(converted(), indent=2, ensure_ascii=False)
    assert a == b


def test_cli_writes_lf_json_equal_to_convert(tmp_path):
    out = tmp_path / "out.json"
    r = subprocess.run([sys.executable, str(TOOL), str(FIXTURE), "--out", str(out), "--pack", "deva_neon"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    assert json.loads(raw.decode("utf-8")) == converted()
