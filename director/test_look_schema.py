import json
import re
from pathlib import Path

import pytest

import write_pack
from shot_schema import validate_shot

HERE = Path(__file__).resolve().parent

# a valid v2.2 rich shot, built the same way test_shot_schema.py does (helper copied, not imported)
RICH = {"id": "SHOT-07", "episode": 2, "scene": "kadamba_leap", "mode": "fl2va", "seconds": 5.2, "aspect": "9:16",
        "purpose": "Krishna commits to the leap; the river is the stakes",
        "cast": [{"id": "CHAR-KRISHNA", "screen": "center", "facing": "right", "start_pose": "POSE-crouch-branch", "end_pose": "POSE-dive"}],
        "props": [{"id": "PROP-KALI-KAMLI", "where": "tied at waist"}], "set": "ENV-KADAMBA-BANK",
        "beats": [{"t": [0.0, 0.8], "acting": "bare foot grips the branch, hand tightens on bark, gaze settles on the river", "bhava": "resolve"},
                  {"t": [0.8, 1.6], "acting": "lowers centre of gravity, knees bend, shoulders tilt forward", "secondary": "sash still settling", "primary": True},
                  {"t": [1.6, 3.4], "acting": "holds the crouch, eyes fixed on the water", "hold": True, "bhava": "resolve"},
                  {"t": [3.4, 5.2], "acting": "launches, body arcs out over the bank", "secondary": "hair and sash trail"}],
        "camera": {"move": "track down with the fall", "lens_mm": 24, "height": "branch level", "start_framing": "full body", "end_framing": "water surface"},
        "layers": {"fg": "kadamba leaves, out of focus", "mid": "Krishna (cel)", "bg": "painted river and far bank", "fx": "splash sheet, composited"},
        "light": {"key": "low morning sun from screen left", "rim": "warm gold on Krishna", "mood": "earthy Braj daylight"},
        "compositing": {"generated": "character motion + splash", "held": "background plate", "post": "on-2s holds, impact frame at 4.1s"},
        "start_state": "Krishna crouched on the high branch, facing river (screen right)",
        "end_state": "white water sheet rising where Krishna entered",
        "cut_in": "match on action from SHOT-06", "cut_out": "splash wipe into SHOT-08",
        "keyframes": {"start": "keyframes/SHOT-07-FRAME-A.png", "end": "keyframes/SHOT-07-FRAME-B.png"},
        "refs": [], "subjects": [],
        "sound": "branch creak, wind, splash (no dialogue words)",
        "dialogue": [{"who": "SHRIDAMA", "t": [0.2, 1.4], "line_hi": "नहीं-नहीं लाला!", "line_en": "No, no, Lala!"}]}

LOOK = {"palette_id": "shiva_neelkanth", "act": "HOOK", "phase": "PH-PLAY", "focal": "CHAR-SHIVA", "focal_value": "lightest",
        "hook": {"type": "H-03", "caption": "Why is his throat blue?"},
        "impact_frames": [{"at_s": 2.10, "type": "white_out", "frames": 2}],
        "vfx": [{"color": "Neel Cyan", "role": "throat glow"}],
        "accent_use": False, "hold_purpose": None}


def edit(**kw):
    return {**RICH, **kw}


def with_look(**kw):
    return edit(look={**LOOK, **kw})


def look_problems(**kw):
    return validate_shot(with_look(**kw))


def test_a_valid_look_passes():
    assert validate_shot(edit(look=LOOK)) == []
    assert validate_shot(edit(look=dict(LOOK, focal_box=[0.1, 0.2, 0.6, 0.9], tags=["tragic"], hold_purpose="divine reveal"))) == []


def test_a_v22_shot_without_look_is_unchanged():
    assert validate_shot(RICH) == []
    assert validate_shot(edit(purpose=None)) == ["SHOT-07: missing purpose"]


def test_look_must_be_an_object():
    assert validate_shot(edit(look="HOOK")) == ["SHOT-07: look must be an object"]
    assert validate_shot(edit(look=None)) == ["SHOT-07: look must be an object"]


@pytest.mark.parametrize("field", ["palette_id", "act"])
def test_palette_id_and_act_are_non_empty_strings(field):
    assert any(f"look.{field} must be a non-empty string" in p for p in look_problems(**{field: ""}))
    assert any(f"look.{field} must be a non-empty string" in p for p in look_problems(**{field: 3}))


def test_a_look_without_palette_id_is_named():
    shot = {k: v for k, v in LOOK.items() if k != "palette_id"}
    assert any("look.palette_id" in p for p in validate_shot(edit(look=shot)))


def test_phase_must_be_a_string_when_present():
    assert any("look.phase must be a string" in p for p in look_problems(phase=5))


def test_focal_must_be_a_non_empty_string_when_present():
    assert any("look.focal must be a non-empty string" in p for p in look_problems(focal=""))
    assert validate_shot(edit(look={k: v for k, v in LOOK.items() if k != "focal"})) == []


def test_focal_value_is_lightest_or_darkest():
    assert any("look.focal_value" in p for p in look_problems(focal_value="middle"))
    assert look_problems(focal_value="darkest") == []


def test_hook_type_and_caption():
    assert any("look.hook.type must be one of H-01..H-06" in p for p in look_problems(hook={"type": "H-07", "caption": "x"}))
    assert any("look.hook.caption" in p for p in look_problems(hook={"type": "H-06", "caption": ""}))
    assert any("look.hook must be an object" in p for p in look_problems(hook="H-01"))
    assert look_problems(hook={"type": "H-06", "caption": "Who took his cows?"}) == []


def test_impact_frames_shape():
    assert any("look.impact_frames must be a list" in p for p in look_problems(impact_frames={"at_s": 1}))
    assert any("look.impact_frames[0] must be an object" in p for p in look_problems(impact_frames=["white_out"]))
    assert any("look.impact_frames[0].at_s" in p for p in look_problems(impact_frames=[{"at_s": -0.1, "type": "t", "frames": 1}]))
    assert any("look.impact_frames[0].at_s" in p for p in look_problems(impact_frames=[{"at_s": True, "type": "t", "frames": 1}]))
    assert any("look.impact_frames[0].type" in p for p in look_problems(impact_frames=[{"at_s": 1, "type": "", "frames": 1}]))
    assert any("look.impact_frames[0].frames" in p for p in look_problems(impact_frames=[{"at_s": 1, "type": "t", "frames": 0}]))
    assert any("look.impact_frames[0].frames" in p for p in look_problems(impact_frames=[{"at_s": 1, "type": "t", "frames": True}]))
    assert look_problems(impact_frames=[]) == []


def test_vfx_needs_color_and_role():
    assert any("look.vfx[0].color" in p for p in look_problems(vfx=[{"color": "", "role": "glow"}]))
    assert any("look.vfx[0].role" in p for p in look_problems(vfx=[{"color": "Neel Cyan"}]))
    assert any("look.vfx must be a list" in p for p in look_problems(vfx="glow"))


def test_accent_use_and_hold_purpose_types():
    assert any("look.accent_use must be true or false" in p for p in look_problems(accent_use="yes"))
    assert any("look.hold_purpose must be a string or null" in p for p in look_problems(hold_purpose=3))
    assert look_problems(hold_purpose=None) == []


@pytest.mark.parametrize("box", [[0.1, 0.1, 0.5], [0, 0, 1.2, 1], [0.5, 0, 0.2, 1], [0, 0.5, 1, 0.5], ["a", 0, 1, 1], [True, 0, 1, 1]])
def test_focal_box_must_be_four_fractions_with_ordered_corners(box):
    assert any("look.focal_box" in p for p in look_problems(focal_box=box))


def test_focal_box_valid_corners_pass():
    assert look_problems(focal_box=[0, 0, 1, 1]) == []


def test_tags_must_be_a_list_of_strings():
    assert any("look.tags" in p for p in look_problems(tags="tragic"))
    assert any("look.tags" in p for p in look_problems(tags=[1]))


def test_beat_reveal_must_be_a_bool():
    beats = [dict(b) for b in RICH["beats"]]
    beats[1]["reveal"] = "yes"
    problems = validate_shot(edit(beats=beats))
    assert any("beat 2 reveal must be true or false" in p for p in problems)
    beats[1]["reveal"] = True
    assert validate_shot(edit(beats=beats)) == []


def test_unknown_look_key_is_a_warning_only():
    problems = look_problems(mood="dusk")
    assert problems and all(p.startswith("SHOT-07: WARN") for p in problems)
    assert any("mood" in p for p in problems)


def test_a_style_key_inside_look_is_an_error():
    problems = look_problems(style="Flat 2D cel anime.")
    assert any("look.style" in p and not p.startswith("SHOT-07: WARN") for p in problems)


def test_staged_brief_default_is_the_v23_file_text():   # owner decision Q5, 2026-11-07: the staged default moved from v2.2 to v2.3
    assert write_pack.staged_brief().read_text(encoding="utf-8") == (HERE / "MASTER_PROMPT_v2.3.md").read_text(encoding="utf-8")
    assert write_pack.staged_brief("v2.2").read_text(encoding="utf-8") == (HERE / "MASTER_PROMPT_v2.2.md").read_text(encoding="utf-8")


def test_staged_brief_v23_has_the_look_rules_and_proportions():
    text = write_pack.staged_brief("v2.3").read_text(encoding="utf-8")
    assert "4.5" in text and "look" in text and "R1" in text
    assert "child characters 5-6 heads" in text


def test_v22_brief_still_says_5_to_6_heads():
    assert "child Krishna and child characters 5-6 heads" in (HERE / "MASTER_PROMPT_v2.2.md").read_text(encoding="utf-8")


def test_staged_brief_rejects_unknown_version_and_missing_v23(monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        write_pack.staged_brief("v9")
    monkeypatch.setattr(write_pack, "BRIEF_V23", tmp_path / "missing.md")
    with pytest.raises(ValueError):
        write_pack.staged_brief("v2.3")


def write_pack_json(folder, pack_id="demo"):
    pack = {"pack_id": pack_id, "guardrails": ["No neon halo on any figure.", "Flat colour fields only."],
            "prompt_forbidden_words": ["neon", "glow"], "acts": {"HOOK": {}, "BUILD": {}},
            "colour_script": {"phases": [{"id": "PH-PLAY"}, {"id": "PH-THREAT"}]}}
    (folder / f"{pack_id}.json").write_text(json.dumps(pack), encoding="utf-8")
    return pack


def test_style_rules_lists_guardrails_forbidden_words_acts_and_phases(tmp_path):
    write_pack_json(tmp_path)
    text = write_pack.style_rules("demo", styles_dir=tmp_path)
    assert "## STYLE PACK RULES" in text
    assert "No neon halo on any figure." in text and "Flat colour fields only." in text
    assert "neon" in text and "glow" in text
    assert "HOOK" in text and "PH-THREAT" in text


def test_style_rules_is_empty_for_a_missing_or_junk_pack(tmp_path):
    assert write_pack.style_rules("nope", styles_dir=tmp_path) == ""
    (tmp_path / "junk.json").write_text("{not json", encoding="utf-8")
    assert write_pack.style_rules("junk", styles_dir=tmp_path) == ""
    assert write_pack.style_rules("../x", styles_dir=tmp_path) == ""


def test_v23_stage_prompts_carry_the_style_rules(tmp_path):
    write_pack_json(tmp_path)
    rules = write_pack.style_rules("demo", styles_dir=tmp_path)
    prompts = []
    canned = {"1": "# Gate 1\n\nEpisode 1: the river\n",
              "2": "# Gate 2\n\n```json bible\n{}\n```",
              "3e1": "# Episode 1\n\n```json shots\n" + json.dumps([dict(RICH, id="SHOT-01", episode=1)]) + "\n```",
              "5": "# Gate 5\n"}

    def fake(prompt, model, effort):
        prompts.append(prompt)
        name = re.search(r"## THIS STAGE\n\nStage (\w+) only", prompt).group(1)
        return write_pack.envelope(canned[name], "stop", "claude", "opus")

    old, old_validator = write_pack.call_claude, write_pack.validator
    write_pack.call_claude = fake
    write_pack.validator = lambda: None   # this test is about the prompt text; the V4 stage checks have their own tests
    try:
        write_pack.run_staged("Story text", tmp_path / "pack", "claude", "opus", "medium", False, {}, {},
                              prompt_version="v2.3", style_rules=rules)
    finally:
        write_pack.call_claude, write_pack.validator = old, old_validator
    assert len(prompts) == 4
    assert all("## STYLE PACK RULES" in p and "No neon halo on any figure." in p for p in prompts)
    assert all("R1" in p and "4.5" in p for p in prompts)


def run_main(argv):
    return write_pack.main(argv)


def test_prompt_version_without_staged_is_an_argparse_error(tmp_path):
    story = tmp_path / "story.md"
    story.write_text("A story.", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run_main([str(story), str(tmp_path / "pack"), "--prompt-version", "v2.3"])
    assert exc.value.code == 2


def test_style_pack_without_staged_is_an_argparse_error(tmp_path):
    story = tmp_path / "story.md"
    story.write_text("A story.", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run_main([str(story), str(tmp_path / "pack"), "--style-pack", "demo"])
    assert exc.value.code == 2
