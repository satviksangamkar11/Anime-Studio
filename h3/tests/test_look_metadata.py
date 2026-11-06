import copy

from h3.schema_and_linter import lint_story
from h3.tests.synth import build_story, codes

LOOK = {"palette_id": "shiva_neelkanth", "act": "HOOK", "phase": "PH-PLAY", "focal": "CHAR-SHIVA", "focal_value": "lightest",
        "hook": {"type": "H-03", "caption": "Why is his throat blue?"},
        "impact_frames": [{"at_s": 2.10, "type": "white_out", "frames": 2}],
        "vfx": [{"color": "Neel Cyan", "role": "throat glow"}],
        "accent_use": False, "hold_purpose": None}


def _with_look(story, put):
    for ep in story["episodes"]:
        for shot in ep["shots"]:
            put(shot)
    return story


def test_look_in_metadata_passes_the_h3_linter(tmp_path):
    story = _with_look(build_story(str(tmp_path)), lambda s: s.setdefault("metadata", {}).update(look=copy.deepcopy(LOOK)))
    assert "SC-01" not in codes(lint_story(story)["errors"])


def test_look_at_a_new_top_level_key_breaks_sc01(tmp_path):
    story = _with_look(build_story(str(tmp_path)), lambda s: s.update(look=copy.deepcopy(LOOK)))
    assert "SC-01" in codes(lint_story(story)["errors"])
