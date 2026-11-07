"""Audit C 11-08: the converted H3 shot carries the writer's look block as metadata.look (post.py and assemble_reel need it)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "director"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import writer_prompts as wp  # noqa: E402
from h3 import v4_to_h3  # noqa: E402


def test_converted_shot_has_metadata_look():
    wp.LOOK_EXAMPLE = {"palette_id": "shiva_neelkanth", "act": "HOOK", "phase": "PH-HOOK", "focal": "CHAR-RAJ", "focal_value": "lightest",
                       "hook": {"type": "H-03", "caption": "Why?"}, "impact_frames": [], "vfx": [], "accent_use": False, "hold_purpose": None}
    try:
        row = wp.example_row(1, 1, ["en"])
    finally:
        wp.LOOK_EXAMPLE = None
    res = v4_to_h3.convert_pack({"shots": [row], "bible": {"characters": {"CHAR-RAJ": {"name": "Raj"}}, "environments": {}, "props": {},
                                                       "style_lock": {"prefix": "2D cel anime"}}})
    story = res["story"]
    assert story is not None
    shot = story["episodes"][0]["shots"][0]
    assert shot["metadata"]["look"]["act"] == "HOOK" and shot["metadata"]["look"]["hook"]["type"] == "H-03"
