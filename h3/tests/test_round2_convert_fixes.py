"""Round-2 review fixes (Super VL batch r5, 2026-11-07): a non-dict authored entry is ignored with a note, a failed
check inside author_shot becomes a per-shot 'MODEL check failed' problem, the --shots CLI refuses a bad shape with
exit 2, pixel_frames/latent_slots are compared only when the row carries them, one problem per missing location_id,
and stage_1 story_gate_checks are copied into registry['story_gate_checks'] (never invented)."""
import copy
import json
import os

from h3 import h3_author as ha
from h3 import v4_to_h3 as conv
from h3 import voice_manifest as vm
from h3.tests.test_v4_to_h3 import SHOT_A, build_pack, _problems_for

GATES = {"active_protagonist": {"pass": True, "evidence": "spine line one"},
         "crisis_from_flaw": {"pass": True, "evidence": "spine line two"}}


def _edit_shots(root, fn):
    path = os.path.join(root, "shots.json")
    shots = json.load(open(path, encoding="utf-8"))
    fn(shots)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(shots, f)


def _edit_stage(root, fn):
    path = os.path.join(root, "stage_1_story.json")
    stage = json.load(open(path, encoding="utf-8"))
    fn(stage)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stage, f)


def _pack(tmp_path):
    root = str(tmp_path / "pack")
    os.makedirs(root)
    build_pack(root)
    return root


# ---- finding 1: a non-dict authored entry is ignored, not a crash ----

def test_non_dict_authored_entry_is_ignored_with_a_note(tmp_path):
    root = _pack(tmp_path)
    _edit_shots(root, lambda s: s[0]["h3_fields"].pop("emotional_objective"))
    res = conv.convert_pack(root, authored={SHOT_A: "a plain string"})
    assert any(n.startswith(SHOT_A + ":") and "ignored" in n for n in res["notes"])
    assert any("emotional_objective" in p for p in _problems_for(res, SHOT_A))


# ---- finding 2: an exception inside the check is a per-shot problem ----

def test_exception_in_check_becomes_a_model_check_problem(tmp_path, monkeypatch):
    root = _pack(tmp_path)
    _edit_shots(root, lambda s: [r.pop("h3_fields") for r in s])
    def boom(*a, **k):
        raise KeyError("boom")
    monkeypatch.setattr(ha.conv, "convert_pack", boom)
    reply = json.dumps({k: "x" for k in conv.AUTHOR_FIELDS})
    report = ha.author_pack(root, caller=lambda prompt: reply)
    entry = report["shots"][0]
    assert entry["status"] == "failed"
    assert any(p.startswith("MODEL check failed") for p in entry["problems"])


def test_author_shot_returns_model_check_problem_not_a_traceback(tmp_path, monkeypatch):
    root = _pack(tmp_path)
    _edit_shots(root, lambda s: [r.pop("h3_fields") for r in s])
    shots = json.load(open(os.path.join(root, "shots.json"), encoding="utf-8"))
    bible = json.load(open(os.path.join(root, "bible.json"), encoding="utf-8"))
    derived, _ = conv.derive_fields(shots[0], None, shots[1], bible, True, False, os.path.join(root, "keyframes"))
    def broken_lint(story):
        raise ValueError("lint broke")
    monkeypatch.setattr(ha, "lint_story", broken_lint)
    reply = json.dumps({k: "x" for k in conv.AUTHOR_FIELDS})
    res = ha.author_shot(shots[0], derived, lambda prompt: reply, max_repairs=0, bible=bible, pack_root=root)
    assert res["fields"] is None
    assert res["problems"] and res["problems"][0].startswith("MODEL check failed")


# ---- finding 3: --shots without a list is a clean exit 2 ----

def test_cli_shots_object_without_shots_key_exits_two(tmp_path, capsys):
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps({"rows": []}), encoding="utf-8")
    assert vm._cli(["--vo-root", str(tmp_path), "--shots", str(shots), "--lang", "en"]) == 2
    assert "shots" in capsys.readouterr().out


def test_cli_shots_not_a_list_exits_two(tmp_path, capsys):
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps({"shots": "S1"}), encoding="utf-8")
    assert vm._cli(["--vo-root", str(tmp_path), "--shots", str(shots), "--lang", "en"]) == 2
    assert "list" in capsys.readouterr().out


# ---- finding 4: pixel_frames and latent_slots compared only when the row has them ----

def test_row_with_only_lattice_n_has_no_mismatch_problem(tmp_path):
    root = _pack(tmp_path)
    _edit_shots(root, lambda s: [r.pop(k) for r in s[:1] for k in ("pixel_frames", "latent_slots")])
    res = conv.convert_pack(root)
    assert not any("do not match" in p for p in _problems_for(res, SHOT_A))
    assert res["story"] is not None


def test_present_wrong_pixel_frames_still_reported(tmp_path):
    root = _pack(tmp_path)
    _edit_shots(root, lambda s: s[0].update(pixel_frames=999))
    res = conv.convert_pack(root)
    assert any("do not match" in p for p in _problems_for(res, SHOT_A))


# ---- finding 5: an underived location_id is reported once ----

def test_missing_location_id_is_reported_once(tmp_path):
    root = _pack(tmp_path)
    _edit_shots(root, lambda s: s[0]["h3_fields"].pop("location_id"))
    # the landmarks no longer match one ENV card, so tier 1 derives no location
    _edit_shots(root, lambda s: s[0]["reference_anchors"].update(fixed_landmarks=["unknown lintel"]))
    res = conv.convert_pack(root)
    loc = [p for p in _problems_for(res, SHOT_A) if "location_id" in p]
    assert len(loc) == 1, loc


# ---- finding 6: story_gate_checks from stage_1 reach registry ----

def test_story_gate_checks_are_copied_into_registry(tmp_path):
    root = _pack(tmp_path)
    _edit_stage(root, lambda st: st.update(story_gate_checks=GATES))
    res = conv.convert_pack(root)
    assert res["story"]["registry"]["story_gate_checks"] == GATES


def test_story_gate_checks_come_from_the_dict_stage_key(tmp_path):
    root = _pack(tmp_path)
    shots = json.load(open(os.path.join(root, "shots.json"), encoding="utf-8"))
    bible = json.load(open(os.path.join(root, "bible.json"), encoding="utf-8"))
    stage = dict(json.load(open(os.path.join(root, "stage_1_story.json"), encoding="utf-8")), story_gate_checks=GATES)
    res = conv.convert_pack({"shots": shots, "bible": bible, "stage": stage, "asset_root": root})
    assert res["story"]["registry"]["story_gate_checks"] == GATES


def test_absent_story_gate_checks_stay_absent(tmp_path):
    root = _pack(tmp_path)
    res = conv.convert_pack(root)
    assert "story_gate_checks" not in res["story"]["registry"]
