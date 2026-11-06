"""Tests for h3/h3_author.py and the tier-1 derivation in h3/v4_to_h3.py. Offline: a fake caller stands in for the model,
no network, no scheduler import. Covers: frame and handle derivation (static, dynamic, impossible), every CN rule on
derived output through lint, prompt content, reply parsing, the repair loop, the 4-repair stop, the cache (hit and
stale), the dry-run CLI (no call), the live gate, and a full round trip V4 pack -> authored -> convert -> lint clean."""
import json
import os
import re

import pytest

from h3 import h3_author
from h3 import v4_to_h3 as conv
from h3.schema_and_linter import lint_story, write_minimal_valid_png
from h3.h3_author import author_pack, author_shot, build_author_prompt, main, parse_author_answer

SHOT_A, SHOT_B = "SHOT-001", "SHOT-002"
ACTIONS = ["Raj lifts his eyes", "Raj turns toward the door", "Raj stands", "Raj steps one pace",
           "Raj stops at the latch", "Raj looks back", "Raj opens the door a crack", "Raj pulls the shutter closed"]
CUES = ["a page rustles", "wooden hinge creaks", "cloth sleeve swish", "a soft step on stone", "latch click",
        "lamp hiss", "door creak and night insects", "shutter thud"]
LANDMARKS = ["carved teak door on the left wall", "brass lamp on the low table"]


def _directives():
    out = [{"t0": float(t), "t1": float(t + 1), "action_pose_expression": ACTIONS[t], "camera": "medium, slow push in",
            "spatial_position": "center-left", "audio_cue": CUES[t], "handoff_to_next_second": "eyes stay"}
           for t in range(7)]
    out.append({"t0": 7.0, "t1": 7.29, "action_pose_expression": ACTIONS[7], "camera": "medium, slow push in",
                "spatial_position": "center-right", "audio_cue": CUES[7], "handoff_to_next_second": "light"})
    return out


def _row(sid, ep, ed, *, explicit_h3=None):
    """A V4 row, lattice 10 (pixel_frames 175). No h3_fields unless given, so tiers 1 and 2 must supply them."""
    row = {"id": sid, "episode": ep, "route": "Ref2VA", "lattice_n": 10, "pixel_frames": 175, "latent_slots": 52,
           "editorial_duration_sec": round(ed / 24, 2),
           "continuity_handoff": {"incoming": f"{sid} opens with the lamp lit. More text.", "outgoing": f"{sid} hands on.",
                                  "loop_seam": None},
           "reference_anchors": {"fixed_landmarks": list(LANDMARKS),
                                 "character_positions": [{"id": "CHAR-RAJ", "screen": "center-left", "depth": "mid"}],
                                 "exited_character_status": [], "lighting_baseline": {}},
           "hook_type": "reveal", "per_second_directives": _directives(),
           "audio_and_dialogue_track": {
               "narration": {"text": "The lamp is lit.", "language": "en", "time_range": [0.5, 5.0]},
               "dialogue": [], "performance_notes": {"narrator_mouth_closed": True,
                                                     "mouth_state": {str(s): "closed" for s in range(8)}},
               "sfx_cues": [{"time_range": "1.2-1.6s", "sfx_key": "pop", "description": "a small pop as the flame bends"},
                            {"time_range": "3.0-3.4s", "sfx_key": "hinge", "description": "a wooden hinge creaks"}]}}
    if explicit_h3 is not None:
        row["h3_fields"] = explicit_h3
    return row


def _bible():
    return {"style_lock": {"prefix": "2D hand-drawn cel-shaded anime, clean ink lines."},
            "forbidden_looks": ["3D CG"],
            "characters": {"CHAR-RAJ": {"name": "Raj"}},
            "environments": {"ENV-HALL": {"name": "Teak hall", "continuity_landmarks": list(LANDMARKS)},
                             "ENV-YARD": {"name": "Yard", "continuity_landmarks": ["stone well"]}},
            "props": {"PROP-LAMP": {"name": "Brass lamp"}}}


def build_pack(root, rows):
    os.makedirs(os.path.join(root, "keyframes"), exist_ok=True)
    for r in rows:
        for letter in ("A", "B"):
            write_minimal_valid_png(os.path.join(root, "keyframes", f"{r['id']}-{letter}.png"), 864, 1536)
    with open(os.path.join(root, "shots.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f)
    with open(os.path.join(root, "bible.json"), "w", encoding="utf-8") as f:
        json.dump(_bible(), f)
    with open(os.path.join(root, "stage_1_story.json"), "w", encoding="utf-8") as f:
        json.dump({"output_languages": ["en"], "output_language": "en"}, f)
    return root


def static_pack(tmp_path):
    """Two static shots in one reel: SHOT-001 INTER in / CHAINED out, SHOT-002 CHAINED in / INTER out."""
    return build_pack(str(tmp_path / "pack"), [_row(SHOT_A, 1, 175), _row(SHOT_B, 1, 175)])


def dynamic_pack(tmp_path):
    """SHOT-001 (ed 140, static in, DYNAMIC out: tail 35, trim_out 140), SHOT-002 (ed 160, DYNAMIC in: head 15, static out)."""
    return build_pack(str(tmp_path / "pack"), [_row(SHOT_A, 1, 140), _row(SHOT_B, 1, 160)])


# ---------- a fake model: answers any prompt from its own FIXED BLUEPRINT and FIELDS TO WRITE ----------

def _blueprint_of(prompt):
    return json.loads(prompt.split("FIXED BLUEPRINT")[1].split(":\n", 1)[1].split("\n\nSHOT (V4 row")[0])


def _wanted_of(prompt):
    block = prompt.split("FIELDS TO WRITE:")[1].split("RULES:")[0]
    return re.findall(r"^- (\w+):", block, re.M)


def good_values(bp):
    pf = bp["pixel_frames"]
    a, b = round(pf * 0.45), round(pf * 0.7)
    return {"emotional_objective": "quiet resolve", "shot_scale": "medium", "screen_direction_vector": "left_to_right",
            "camera_axis_side": "left", "horizon_line_y_ratio": 0.4,
            "cut_in_biomechanical_state_tag": "idle_at_door", "cut_out_biomechanical_state_tag": "turns_toward_door",
            "cut_in_pose_vector": {"torso_pitch_deg": 8.5, "knee_flex_deg": 15.5, "com_y_ratio": 0.505},
            "cut_out_pose_vector": {"torso_pitch_deg": 9.0, "knee_flex_deg": 15.0, "com_y_ratio": 0.51},
            "hold_window_frames": [0, a], "burst_window_frames": [a + 1, b], "impact_or_settle_frames": [b + 1, pf],
            "cadence_clause": "Hold the pose quietly, then a quick burst, then settle."}


class FakeModel:
    """Answers with good_values for the fields asked. bad_first=N returns broken JSON for the first N calls."""

    def __init__(self, bad_first=0, broken=None):
        self.calls, self.prompts, self.bad_first, self.broken = 0, [], bad_first, broken

    def __call__(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        if self.calls <= self.bad_first:
            return self.broken if self.broken is not None else "not json at all"
        bp = _blueprint_of(prompt)
        vals = good_values(bp)
        return json.dumps({k: vals[k] for k in _wanted_of(prompt)})


def _load(pack, name):
    return json.load(open(os.path.join(pack, name), encoding="utf-8"))


def _shot(story, sid):
    return next(s for ep in story["episodes"] for s in ep["shots"] if s["shot_id"] == sid)


# ---------- tier 1: derivation of trim, handles, seams, location, props, story beat ----------

def test_static_pair_derives_seams_and_zero_handles(tmp_path):
    pack = static_pack(tmp_path)
    shots = _load(pack, "shots.json")
    f1, _ = conv.derive_fields(shots[0], None, shots[1], _bible(), True, False, os.path.join(pack, "keyframes"))
    f2, _ = conv.derive_fields(shots[1], shots[0], None, _bible(), False, True, os.path.join(pack, "keyframes"))
    assert (f1["incoming_seam_type"], f1["outgoing_seam_type"]) == ("INTER_REEL_HANDSHAKE", "CHAINED_POSE_HOLD")
    assert (f2["incoming_seam_type"], f2["outgoing_seam_type"]) == ("CHAINED_POSE_HOLD", "INTER_REEL_HANDSHAKE")
    assert (f1["trim_in_frame"], f1["trim_out_frame"], f1["head_handle_frames"], f1["tail_handle_frames"]) == (0, 175, 0, 0)
    assert f1["picture_1_path"] == "keyframes/SHOT-001-A.png" and f1["picture_2_path"] == "keyframes/SHOT-001-B.png"
    assert f2["picture_1_path"] is None           # CHAINED: the converter takes the previous picture_2


def test_dynamic_out_cut_splits_handles_inside_the_span(tmp_path):
    shots = _load(build_pack(str(tmp_path / "d"), [_row(SHOT_A, 1, 140)]), "shots.json")
    f, notes = conv.derive_fields(shots[0], None, _row("N", 1, 160), _bible(), True, False, None)
    # first shot: static in (INTER), dynamic out: trim_out = 140, tail = 35 (24..47), 140 inside 6_impact_result 125..149
    assert (f["trim_in_frame"], f["trim_out_frame"], f["head_handle_frames"], f["tail_handle_frames"]) == (0, 140, 0, 35)
    assert not [n for n in notes if n.startswith("PROBLEM")]


def test_both_dynamic_split_picks_one_inside_the_bounds(tmp_path):
    shots = _load(build_pack(str(tmp_path / "b"), [_row(SHOT_A, 1, 140)]), "shots.json")
    f, notes = conv.derive_fields(shots[0], _row("P", 1, 175), _row("N", 1, 175), _bible(), False, False, None)
    assert f["incoming_seam_type"] == "DYNAMIC_MATCH_ON_ACTION" and f["outgoing_seam_type"] == "DYNAMIC_MATCH_ON_ACTION"
    assert f["head_handle_frames"] + f["tail_handle_frames"] == 35                 # pixel 175 - editorial 140
    assert 8 <= f["head_handle_frames"] <= 35 and 24 <= f["tail_handle_frames"] <= 47
    assert 125 <= f["trim_out_frame"] <= 149                                        # MO-03
    assert f["trim_in_frame"] == f["head_handle_frames"]
    assert not [n for n in notes if n.startswith("PROBLEM")]


def test_impossible_numbers_are_reported_precisely(tmp_path):
    rows = [_row(SHOT_A, 1, 155)]           # both dynamic needs handle sum >= 32; 175 - 155 = 20
    shots = _load(build_pack(str(tmp_path / "i"), rows), "shots.json")
    f, notes = conv.derive_fields(shots[0], _row("P", 1, 175), _row("N", 1, 175), _bible(), False, False, None)
    probs = [n for n in notes if n.startswith("PROBLEM")]
    assert probs and "no dynamic split fits" in probs[0] and "must add up to 20" in probs[0]
    assert f["trim_out_frame"] == 155 and f["tail_handle_frames"] == 20   # static fallback keeps the timing sums consistent


def test_both_dynamic_editorial_outside_cn06_bounds_is_a_problem(tmp_path):
    shots = _load(build_pack(str(tmp_path / "c"), [_row(SHOT_A, 1, 100)]), "shots.json")
    _f, notes = conv.derive_fields(shots[0], _row("P", 1, 175), _row("N", 1, 175), _bible(), False, False, None)
    assert any("both-dynamic cut at n=10 needs editorial 115..143" in n for n in notes if n.startswith("PROBLEM"))


def test_single_dynamic_side_with_too_long_head_is_a_problem(tmp_path):
    shots = _load(build_pack(str(tmp_path / "h"), [_row(SHOT_B, 1, 100)]), "shots.json")
    _f, notes = conv.derive_fields(shots[0], _row("P", 1, 175), None, _bible(), False, True, None)
    assert any("incoming DYNAMIC head handle 75 outside 8..35" in n for n in notes if n.startswith("PROBLEM"))


def test_location_props_and_story_beat_are_derived_from_the_row(tmp_path):
    row = _row(SHOT_A, 1, 175)
    row["continuity_handoff"]["incoming"] = "Raj reaches the door. Then he waits."
    row["purpose"] = "The keeper lights the brass lamp"          # purpose wins when present
    row["per_second_directives"][0]["action_pose_expression"] = "Raj lifts PROP-LAMP"
    f, _ = conv.derive_fields(row, None, None, _bible(), True, True, None)
    assert f["location_id"] == "ENV-HALL"
    assert f["props_present"] == ["PROP-LAMP"]
    assert f["story_beat"] == "The keeper lights the brass lamp"


def test_location_not_derived_when_no_card_matches(tmp_path):
    row = _row(SHOT_A, 1, 175)
    row["reference_anchors"]["fixed_landmarks"] = ["unknown well"]
    f, notes = conv.derive_fields(row, None, None, _bible(), True, True, None)
    assert "location_id" not in f and any("location_id not derived" in n for n in notes)


def test_derive_does_not_change_its_input(tmp_path):
    row = _row(SHOT_A, 1, 140)
    before = json.dumps(row, sort_keys=True)
    conv.derive_fields(row, None, None, _bible(), True, False, None)
    assert json.dumps(row, sort_keys=True) == before


def test_authored_and_derived_names_cover_every_h3_field():
    assert set(conv.DERIVED_FIELDS) | set(conv.AUTHOR_FIELDS) == set(conv.H3_FIELDS)
    assert not set(conv.DERIVED_FIELDS) & set(conv.AUTHOR_FIELDS)


# ---------- prompt ----------

def test_prompt_contains_blueprint_and_only_the_missing_fields(tmp_path):
    shots = _load(static_pack(tmp_path), "shots.json")
    f, _ = conv.derive_fields(shots[1], shots[0], None, _bible(), False, True, None)
    bp = conv.build_blueprint(f, {"tag": "turns_toward_door", "pose": {"torso_pitch_deg": 9.0, "knee_flex_deg": 15.0,
                                                                      "com_y_ratio": 0.51}})
    prompt = build_author_prompt(shots[1], f, bp)
    wanted = _wanted_of(prompt)
    assert "cut_in_biomechanical_state_tag" not in wanted and "cut_in_pose_vector" not in wanted   # fixed by SHOT-001
    assert "emotional_objective" in wanted and "cadence_clause" in wanted
    assert "story_beat" not in wanted and "incoming_seam_type" not in wanted                       # derived
    assert '"pixel_frames": 175' in prompt and "CHAINED_POSE_HOLD" in prompt
    shot_block = prompt.split("SHOT (V4 row")[1].split("ALREADY")[0]
    assert '"audio_and_dialogue_track"' not in shot_block and "The lamp is lit." not in prompt


# ---------- parsing ----------

def test_parse_tolerates_fences_think_blocks_and_wrappers():
    obj = {"shot_scale": "medium"}
    assert parse_author_answer("<think>hmm {x}</think>\n```json\n" + json.dumps(obj) + "\n```") == obj
    assert parse_author_answer("Here you go: " + json.dumps(obj) + " thanks") == obj
    assert parse_author_answer(json.dumps({"shots": [obj]})) == obj


def test_parse_rejects_non_objects():
    with pytest.raises(ValueError):
        parse_author_answer("no braces here")
    with pytest.raises(ValueError):
        parse_author_answer("[1, 2]")


# ---------- the loop ----------

def test_repair_loop_fails_twice_then_passes(tmp_path):
    pack = static_pack(tmp_path)
    shots = _load(pack, "shots.json")
    f, _ = conv.derive_fields(shots[0], None, shots[1], _bible(), True, False, os.path.join(pack, "keyframes"))
    model = FakeModel(bad_first=2)
    res = author_shot(shots[0], f, model, bible=_bible(), pack_root=pack)
    assert res["problems"] == [] and res["rounds"] == 3 and model.calls == 3
    assert "PARSE" in model.prompts[1] or "PARSE" in model.prompts[2]   # the exact messages went back
    assert set(res["fields"]) == set(_wanted_of(model.prompts[0]))


def test_repair_loop_sends_lint_codes_back(tmp_path):
    pack = static_pack(tmp_path)
    shots = _load(pack, "shots.json")
    f, _ = conv.derive_fields(shots[0], None, shots[1], _bible(), True, False, os.path.join(pack, "keyframes"))
    model = FakeModel()

    def wrong_cadence_first(prompt):
        reply = json.loads(model(prompt))
        if model.calls == 1 and "hold_window_frames" in reply:
            reply["hold_window_frames"] = [0, 10]          # breaks CD-01 contiguity on the first reply only
        return json.dumps(reply)
    res = author_shot(shots[0], f, wrong_cadence_first, bible=_bible(), pack_root=pack)
    assert res["problems"] == [] and res["rounds"] == 2
    assert "CD-01" in model.prompts[1]                       # the exact lint code went back to the model


def test_stops_after_four_repairs_with_a_problem(tmp_path):
    shots = _load(static_pack(tmp_path), "shots.json")
    f, _ = conv.derive_fields(shots[0], None, shots[1], _bible(), True, False, None)
    model = FakeModel(bad_first=99, broken="{}")
    res = author_shot(shots[0], f, model, bible=_bible(), pack_root=None)
    assert model.calls == 1 + h3_author.MAX_REPAIRS == 5
    assert res["fields"] is None and res["rounds"] == 5 and res["problems"]


def test_caller_exception_is_a_problem_not_a_default(tmp_path):
    shots = _load(static_pack(tmp_path), "shots.json")
    f, _ = conv.derive_fields(shots[0], None, shots[1], _bible(), True, False, None)

    def boom(prompt):
        raise RuntimeError("scheduler down")
    res = author_shot(shots[0], f, boom, bible=_bible(), pack_root=None)
    assert res["fields"] is None and "MODEL call failed" in res["problems"][0]


# ---------- pack driver, cache, round trip ----------

def test_round_trip_static_pack_lints_clean(tmp_path):
    pack = static_pack(tmp_path)
    model = FakeModel()
    report = author_pack(pack, model)
    assert [s["status"] for s in report["shots"]] == ["authored", "authored"]
    assert os.path.isfile(os.path.join(pack, "h3_authored", "SHOT-001.json"))
    res = conv.convert_pack(pack)
    assert res["problems"] == []
    assert lint_story(res["story"])["errors"] == []


def test_round_trip_dynamic_pack_lints_clean(tmp_path):
    pack = dynamic_pack(tmp_path)
    report = author_pack(pack, FakeModel())
    assert all(s["status"] == "authored" for s in report["shots"])
    res = convert_pack_ok(pack)
    t1 = _shot(res["story"], SHOT_A)["timing_and_lattice"]
    t2 = _shot(res["story"], SHOT_B)["timing_and_lattice"]
    assert (t1["trim_out_frame"], t1["tail_handle_frames"]) == (140, 35)
    assert (t2["trim_in_frame"], t2["head_handle_frames"]) == (15, 15)
    assert lint_story(res["story"])["errors"] == []


def convert_pack_ok(pack):
    res = conv.convert_pack(pack)
    assert res["problems"] == [], res["problems"]
    return res


def test_cache_hit_makes_no_call_and_stale_reauthors(tmp_path):
    pack = static_pack(tmp_path)
    author_pack(pack, FakeModel())
    silent = FakeModel()
    report = author_pack(pack, silent)
    assert silent.calls == 0 and [s["status"] for s in report["shots"]] == ["fresh", "fresh"]
    rows = _load(pack, "shots.json")
    rows[0]["continuity_handoff"]["incoming"] = "A different opening sentence."
    json.dump(rows, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    again = FakeModel()
    report = author_pack(pack, again)
    assert again.calls >= 1 and report["shots"][0]["status"] == "authored"


def test_stale_cache_is_a_problem_in_convert(tmp_path):
    pack = static_pack(tmp_path)
    author_pack(pack, FakeModel())
    rows = _load(pack, "shots.json")
    rows[1]["continuity_handoff"]["outgoing"] = "Changed after authoring."
    json.dump(rows, open(os.path.join(pack, "shots.json"), "w", encoding="utf-8"))
    res = conv.convert_pack(pack)
    assert any("SHOT-002" in n and "stale" in n for n in res["notes"])


def test_authored_cache_is_refused_when_the_bible_changes(tmp_path):
    pack = static_pack(tmp_path)
    author_pack(pack, FakeModel())
    bible = _load(pack, "bible.json")
    bible["style_lock"]["prefix"] = "A different look."
    json.dump(bible, open(os.path.join(pack, "bible.json"), "w", encoding="utf-8"))
    res = conv.convert_pack(pack)
    assert any("authored fields stale" in n for n in res["notes"])


def test_failed_shot_blocks_the_next_one_in_the_reel(tmp_path):
    pack = static_pack(tmp_path)
    report = author_pack(pack, FakeModel(bad_first=99, broken="{}"))
    assert [s["status"] for s in report["shots"]] == ["failed", "blocked"]


def test_explicit_h3_fields_are_kept_and_not_authored(tmp_path):
    explicit = {k: v for k, v in good_values({"pixel_frames": 175, "fixed": {}}).items()}
    explicit["cut_in_biomechanical_state_tag"] = "explicit_tag"
    rows = [_row(SHOT_A, 1, 175, explicit_h3=dict(explicit, incoming_seam_type="INTER_REEL_HANDSHAKE",
                                                  outgoing_seam_type="CHAINED_POSE_HOLD")),
            _row(SHOT_B, 1, 175)]
    pack = build_pack(str(tmp_path / "e"), rows)
    model = FakeModel()
    report = author_pack(pack, model)
    assert report["shots"][0]["status"] == "nothing to author"
    res = conv.convert_pack(pack)
    assert _shot(res["story"], SHOT_A)["continuity_and_seam_lock"]["cut_in_biomechanical_state_tag"] == "explicit_tag"


# ---------- CLI: dry run, live gate ----------

def test_dry_run_prints_fields_and_makes_no_call(tmp_path, monkeypatch, capsys):
    pack = static_pack(tmp_path)

    def must_not(*_a, **_k):
        raise AssertionError("dry run must not build the scheduler caller")
    monkeypatch.setattr(h3_author, "scheduler_caller", must_not)
    code = main([pack, "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "SHOT-001" in out and "missing (13)" in out and "prompt chars" in out
    assert not os.path.isdir(os.path.join(pack, "h3_authored"))


def test_dry_run_exit_one_when_derivation_has_a_problem(tmp_path, capsys):
    pack = build_pack(str(tmp_path / "x"), [_row(SHOT_A, 1, 155), _row(SHOT_B, 1, 175)])
    assert main([pack, "--dry-run"]) == 1


def test_live_is_refused_without_the_env_flag(tmp_path, monkeypatch, capsys):
    pack = static_pack(tmp_path)
    monkeypatch.delenv("ANIME_STUDIO_ALLOW_FREE_MODEL", raising=False)

    def must_not(*_a, **_k):
        raise AssertionError("refused run must not build the scheduler caller")
    monkeypatch.setattr(h3_author, "scheduler_caller", must_not)
    assert main([pack, "--live"]) == 2
    assert "ANIME_STUDIO_ALLOW_FREE_MODEL=1" in capsys.readouterr().err


def test_mode_is_required(tmp_path):
    with pytest.raises(SystemExit):
        main([static_pack(tmp_path)])


def test_live_with_flag_uses_the_caller(tmp_path, monkeypatch):
    pack = static_pack(tmp_path)
    monkeypatch.setenv("ANIME_STUDIO_ALLOW_FREE_MODEL", "1")
    model = FakeModel()
    monkeypatch.setattr(h3_author, "scheduler_caller", lambda: model)
    assert main([pack, "--live"]) == 0
    assert model.calls == 2
