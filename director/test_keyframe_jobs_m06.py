"""M-06 tests: sentence-form A prompt, B = 'Same picture ... Change only' (max 3), route S has no B.

Fixtures are the Opus calibration examples (research/OPUS_CALIBRATION_REVIEW_2026-11-12.md section 4.4).
No model call, no Flow call, no network.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pytest

_director_dir = Path(__file__).resolve().parent
_project_root = _director_dir.parent
sys.path.insert(0, str(_director_dir))
sys.path.insert(0, str(_project_root))

PLATE_ID = "PLATE-yamuna-bank-morning"
PLATE_FILE = "yamuna-bank-morning.jpg"
PLATE_BYTES = b"plate jpg bytes for m06"
FRAME_LAW = "Vertical 9:16 frame. Faces stay in the upper two thirds."
EXCLUSION = "No text, no logo, no extra people, no halo."

# Opus example A (SHOT-012): Krishna kneels on the river bank, start of a kneel-to-stand.
KRISHNA_START = {"x": 0.25, "y": 0.65, "scale": 0.5, "facing": "right", "pose": "kneeling"}
KRISHNA_STAND = {"x": 0.25, "y": 0.65, "scale": 0.5, "facing": "right", "pose": "standing"}
SHOT_012 = {
    "shot": "SHOT-012",
    "camera": {"mode": "fixed", "framing": "medium", "move": None, "angle": "eye_level", "lens": "normal"},
    "light": {"key_dir": "left", "palette_id": "PAL-morning"},
    "props": [{"id": "P1", "class": "flute", "x": 0.30, "y": 0.62, "visible": ["A", "B"]}],
    "cast": [{"name": "KRISHNA", "expression": "calm", "start": dict(KRISHNA_START),
              "end": dict(KRISHNA_STAND)}],
}



@pytest.fixture(autouse=True)
def _s_gate_off(monkeypatch):
    # M-32: S is the default route now; this file pins the SE-family behaviour, so it switches the S gate off
    monkeypatch.setenv("SHOT_MODE_S_ALLOW", "0")

def _flow_root(tmp_path):
    root = tmp_path / "flow"
    plates = root / "plates"
    plates.mkdir(parents=True)
    (plates / PLATE_FILE).write_bytes(PLATE_BYTES)
    catalog = {PLATE_ID: {"path": PLATE_FILE, "sha256": hashlib.sha256(PLATE_BYTES).hexdigest()}}
    (plates / "plates.json").write_text(json.dumps(catalog), encoding="utf-8")
    return root


@pytest.fixture
def kj(tmp_path, monkeypatch):
    sys.modules.pop("keyframe_jobs", None)
    import keyframe_jobs
    monkeypatch.setattr(keyframe_jobs, "FLOW_ROOT", str(_flow_root(tmp_path)))
    monkeypatch.setattr(keyframe_jobs, "STYLE_CHIP", None)
    monkeypatch.setattr(keyframe_jobs, "STYLE_ANCHOR", None)
    return keyframe_jobs


def _member(name, start, end, **extra):
    m = {"name": name, "start": dict(start), "end": dict(end)}
    m.update(extra)
    return m


def _shot(cast, props=None, shot="SHOT-T"):
    base = {k: v for k, v in SHOT_012.items() if k != "cast"}
    base.update({"shot": shot, "cast": cast, "props": props if props is not None else []})
    return base


def test_a_prompt_has_no_digits_coords(kj):
    job_a, _ = kj.jobs_for_shot(SHOT_012, PLATE_ID, ["KRISHNA"])
    assert FRAME_LAW in job_a["prompt"]   # M-31: the frame law must really be there before it is excluded below
    text = job_a["prompt"].replace(FRAME_LAW, "")  # the fixed frame law is the only digit allowed
    assert not re.search(r"\d", text)
    assert "(" not in job_a["prompt"]
    assert not re.search(r"\d\.\d", job_a["prompt"])


def test_a_prompt_opus_example_sentences(kj):
    job_a, _ = kj.jobs_for_shot(SHOT_012, PLATE_ID, ["KRISHNA"])
    p = job_a["prompt"]
    for fragment in (
        "Medium shot at eye level",
        "KRISHNA is in the left third",
        "low in the frame",
        "full figure about half the frame height",
        "kneeling",
        "facing screen-right",
        "calm expression",
        "Key light from screen-left.",
        FRAME_LAW,
        EXCLUSION,
    ):
        assert fragment in p, fragment
    assert len(p.split()) <= 110


def test_a_prompt_positive_cast_sentence(kj):
    job_a, _ = kj.jobs_for_shot(SHOT_012, PLATE_ID, ["KRISHNA"])
    p = job_a["prompt"]
    assert "Exactly these people are in the frame: KRISHNA." in p
    assert p.index("Exactly these people") < p.index(EXCLUSION)
    assert len(p.split()) <= 110
    two = _shot([_member("KRISHNA", KRISHNA_START, KRISHNA_STAND), _member("RADHA", KRISHNA_START, KRISHNA_STAND)])
    assert "in the frame: KRISHNA, RADHA." in kj.jobs_for_shot(two, PLATE_ID, [])[0]["prompt"]
    empty = kj.a_prompt(_shot([]))
    assert "Exactly these people" not in empty


def test_a_prompt_word_budget_refused_when_too_long(kj):
    long_cast = [_member("N%d" % i, KRISHNA_START, KRISHNA_STAND) for i in range(40)]
    with pytest.raises(kj.KeyframeJobError):
        kj.jobs_for_shot(_shot(long_cast), PLATE_ID, [])


def test_position_words_boundaries(kj):
    assert kj.xy_words(0.32, 0.30)[0] == "in the left third"
    assert kj.xy_words(0.33, 0.30)[0] == "in the centre"
    assert kj.xy_words(0.67, 0.30)[0] == "in the centre"
    assert kj.xy_words(0.68, 0.30)[0] == "in the right third"
    assert kj.xy_words(0.5, 0.39)[1] == "high in the frame"
    assert kj.xy_words(0.5, 0.40)[1] == "at mid-height"
    assert kj.xy_words(0.5, 0.61)[1] == "at mid-height"
    assert kj.xy_words(0.5, 0.62)[1] == "low in the frame"


def test_scale_words_boundaries(kj):
    assert kj.scale_words(0.80) == "filling most of the frame height"
    assert kj.scale_words(0.79) == "full figure about half the frame height"
    assert kj.scale_words(0.45) == "full figure about half the frame height"
    assert kj.scale_words(0.44) == "a small full figure"
    assert kj.scale_words(0.20) == "a small full figure"
    assert kj.scale_words(0.19) == "a tiny figure"


def test_b_text_form_opus_example(kj):
    _, job_b = kj.jobs_for_shot(SHOT_012, PLATE_ID, ["KRISHNA"])
    assert job_b["edit_instruction"] == (
        "Same picture, same framing, same light, same background. Change only: 1) KRISHNA now stands."
    )
    assert job_b["chips"] == ["SHOT-012-A final"]


def test_b_max_3_changes(kj):
    cast = [
        _member("A", {"x": 0.3, "y": 0.6, "scale": 0.5, "facing": "right", "pose": "kneeling"},
                {"x": 0.3, "y": 0.6, "scale": 0.5, "facing": "right", "pose": "standing"},
                ),
        _member("B", {"x": 0.7, "y": 0.6, "scale": 0.5, "facing": "left", "pose": "seated"},
                {"x": 0.7, "y": 0.6, "scale": 0.5, "facing": "left", "pose": "standing"}),
    ]
    cast[0]["end"]["mouth_moves"] = True
    # 2 pose changes + 1 mouth change = 3 changes: allowed
    _, job_b = kj.jobs_for_shot(_shot(cast), PLATE_ID, [])
    assert job_b["edit_instruction"].count(") ") == 3
    # one prop disappearing makes 4: refused, the shot must be split
    props = [{"id": "P1", "class": "flute", "x": 0.3, "y": 0.6, "visible": ["A"]}]
    with pytest.raises(kj.KeyframeJobError) as exc:
        kj.jobs_for_shot(_shot(cast, props=props), PLATE_ID, [])
    assert "max 3" in str(exc.value)


def test_b_no_keep_everything_line_and_no_coords(kj):
    cast = [_member("KRISHNA", KRISHNA_START,
                    {"x": 0.5, "y": 0.5, "scale": 0.5, "facing": "right", "pose": "kneeling"})]
    _, job_b = kj.jobs_for_shot(_shot(cast), PLATE_ID, [])
    assert "keep everything else" not in job_b["edit_instruction"]
    assert "(" not in job_b["edit_instruction"]
    assert job_b["edit_instruction"] == (
        "Same picture, same framing, same light, same background. Change only: "
        "1) KRISHNA moves to the centre, at mid-height."
    )


def test_b_nothing_changed_text(kj):
    _, job_b = kj.jobs_for_shot(_shot([]), PLATE_ID, [])
    assert job_b["edit_instruction"] == (
        "Same picture, same framing, same light, same background. Change nothing."
    )


def test_s_route_has_no_b_job(kj):
    # Opus 4.2: empty-plate and reveal shots have no B (route S).
    plate_shot = {"shot": "SHOT-000", "route": "S", "cast": [], "props": []}
    job_a, job_b = kj.jobs_for_shot(plate_shot, PLATE_ID, [])
    assert job_b is None
    assert job_a["base_edit_id"] == PLATE_ID


def test_b_method_is_generate_with_chip(kj):
    _, job_b = kj.jobs_for_shot(SHOT_012, PLATE_ID, ["KRISHNA"])
    assert job_b["method"] == "generate_with_chip"
    assert job_b["chip_ref_id"] == "SHOT-012-A final"
    assert job_b["chips"] == [job_b["chip_ref_id"]]


def test_scale_only_change_is_reported_as_scale(kj):
    import blocking
    cast = [_member("KRISHNA", KRISHNA_START,
                    {"x": 0.25, "y": 0.65, "scale": 0.3, "facing": "right", "pose": "kneeling"})]
    lines = blocking.change_list(_shot(cast))
    assert "KRISHNA: scale 0.50 to 0.30" in lines
    assert not any("move from" in line for line in lines)
    _, job_b = kj.jobs_for_shot(_shot(cast), PLATE_ID, [])
    assert job_b["edit_instruction"].endswith("1) KRISHNA now a small full figure.")


def test_style_chip_attached_to_every_a_job(kj, monkeypatch, tmp_path):
    monkeypatch.setattr(kj, "STYLE_CHIP", "style-chip.png")
    job_a, job_b = kj.jobs_for_shot(SHOT_012, PLATE_ID, ["KRISHNA"])
    assert job_a["chips"][-1] == "style-chip.png"
    assert len(job_a["chips"]) == 2
    assert job_b["chips"] == ["SHOT-012-A final"]


def test_missing_plates_registry_is_a_keyframe_job_error(kj, tmp_path):
    # M-31: a missing plates.json is reported as a plate problem, not a bare FileNotFoundError
    with pytest.raises(kj.KeyframeJobError, match="plates registry missing"):
        kj.plates_index(str(tmp_path / "no_such_flow_root"))
