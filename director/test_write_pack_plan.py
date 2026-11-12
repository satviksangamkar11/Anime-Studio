"""--plan story_plan_v2.json --reel N (REPLAN 2026-11-12 section D step 3): stage 1 is not called; reel N's premise, arc,
hook_type, voice_rest, length and context packet plus the last continuity ledger entry reach every later stage and the gates.
--bible PATH reuses a bible (stage 2 not called). Synthetic fixtures only (rule 53/54: no reel 1 file is read). No network."""
import json

import pytest

import script_inspect
import story_shape
import write_pack
import writer_prompts as wp
import test_writer_v4 as t4
from test_writer_v4 import no_network, simple_language, story  # noqa: F401  (fixtures)

@pytest.fixture(autouse=True)
def _no_plan_leak(monkeypatch):
    """main() sets the module globals REEL_PLAN and BASE_BIBLE; monkeypatch puts them back after each test."""
    monkeypatch.setattr(write_pack, "REEL_PLAN", None)
    monkeypatch.setattr(write_pack, "BASE_BIBLE", None)


PREMISE = {"character": "Raj", "goal": "open the door", "obstacle": "his fear", "stakes": "the village",
           "payoff": "he steps out"}
CONTEXT = {"story_so_far": ["Raj found the lamp."], "previous_reel_end_state": {"place": "ENV-PLAN-OLD"},
           "open_question_in": "Will the door open?", "must_not_repeat": ["the lamp lighting UNIQUE-MNR"],
           "cast_present": ["CHAR-RAJ"], "locations_used": [], "props_in_play": [], "continuity_flags": [],
           "end_state_out": {"place": "the door"}, "mood": "hush", "language_notes": "Raj / राज / राज"}


def plan_file(folder, hook="kinetic", rest=True):
    reel = {"number": 2, "title": "The Door", "premise": PREMISE, "source_span": "P1 chars ~0.0k-0.1k: the door",
            "target_seconds": 13, "arc": {"hook": "a", "setup": "b", "escalation": "c", "payoff": "d"},
            "hook_type": hook, "shot_shape": {"shots_s": [7.0, 6.0]}, "restraint": False, "context": CONTEXT}
    if rest:
        reel["voice_rest"] = {"shot": "SHOT-002", "window_s": [3.0, 5.5], "clock": "shot-relative"}
    other = dict(reel, number=3, title="Other Reel", context=dict(CONTEXT, must_not_repeat=["OTHER-REEL-ONLY"]))
    path = folder / "story_plan_v2.json"
    path.write_text(json.dumps({"schema": "story_plan/2", "reels": [reel, other]}, ensure_ascii=False), encoding="utf-8")
    ledger = {"schema": "continuity_ledger/1", "entries": [
        {"reel": 1, "title": "Lamp", "status": "published", "end_state": {"place": "LEDGER-WINS-PLACE"}},
        {"reel": 2, "title": "The Door", "status": "planned", "end_state": {"place": "NOT-FOR-REEL-2"}}]}
    (folder / "continuity_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    return path


def test_load_reel_plan_gives_the_stage1_shape_and_the_packet_text(tmp_path):
    text, plan = write_pack.load_reel_plan(plan_file(tmp_path), 2)
    assert plan["episodes"] == [{"episode": 2, "title": "The Door", "seconds": 13.0}]
    assert plan["premise"] == PREMISE and plan["reel_target_s"] == 13
    assert plan["hook_type"] == "kinetic" and plan["arc"]["payoff"] == "d" and plan["voice_rest"]["shot"] == "SHOT-002"
    assert "UNIQUE-MNR" in text and "OTHER-REEL-ONLY" not in text
    assert "LEDGER-WINS-PLACE" in text and "NOT-FOR-REEL-2" not in text      # last entry BEFORE reel 2 only
    assert "overrides" in text


def test_load_reel_plan_refuses_an_unknown_reel(tmp_path):
    with pytest.raises(ValueError, match="reel 9"):
        write_pack.load_reel_plan(plan_file(tmp_path), 9)


def test_reel_source_keeps_the_notes_and_the_line_numbers_and_cuts_to_the_span():
    part1 = "a" * 5000 + "SPAN-TEXT" + "b" * 9000
    text = "# head\nnote line\n## TRANSCRIPT (verbatim) PART 1\n" + part1 + "\n\n## TRANSCRIPT (verbatim) PART 2\nPART2-TEXT\n"
    out = write_pack.reel_source(text, "P1 chars ~5.0k-5.1k: something")
    assert "note line" in out and "SPAN-TEXT" in out and "PART2-TEXT" not in out
    assert len(out) < len(text) - 5000
    assert len(out.split("\n")) == len(text.split("\n"))                     # source_refs line ids (L4 ...) stay valid
    assert write_pack.reel_source(text, "no span here") == text


def test_bible_for_prompt_keeps_only_the_cards_the_reel_names():
    bible = {"style_lock": {"x": 1}, "forbidden_looks": ["3D"], "characters": {"CHAR-RAJ": {}, "CHAR-FAR": {}},
             "environments": {"ENV-HOME": {}}, "props": {"PROP-LAMP": {}},
             "voice_map": {"NARRATOR": {}, "CHAR-RAJ": {}, "CHAR-FAR": {}}}
    small = write_pack.bible_for_prompt(bible, {"cast": ["CHAR-RAJ"], "where": "ENV-HOME: the hut"})
    assert list(small["characters"]) == ["CHAR-RAJ"] and list(small["environments"]) == ["ENV-HOME"]
    assert small["props"] == {} and set(small["voice_map"]) == {"NARRATOR", "CHAR-RAJ"}
    assert small["style_lock"] == {"x": 1} and small["forbidden_looks"] == ["3D"]


def _rows(hook="kinetic"):
    r1 = dict(wp.example_row(2, 1, ["hi"], v24=True), shape_hook_type=hook)
    r2 = dict(wp.example_row(2, 2, ["hi"], v24=True), arc_beat="payoff", editorial_duration_sec=6.0, voice_rest=[3.0, 5.5])
    r2.pop("shape_hook_type", None)
    for r in (r1, r2):
        r["per_second_directives"] = [dict(d, source_refs=["L1"]) for d in r["per_second_directives"]]
    return [r1, r2]


def _run(tmp_path, monkeypatch, story, *extra, rows=None, plan_kw=None, repair_rows=None):
    t4.fake_validator(monkeypatch, lambda stage, data, bible: [])
    plan = plan_file(story.parent, **(plan_kw or {}))
    canned = t4.canned(["hi"])
    canned["3e2"] = "# Episode 2\n\n```json shots\n" + json.dumps(rows or _rows(), ensure_ascii=False) + "\n```\n"
    items = [dict(t4.captions_items(["hi"])[0], shot_id=f"SHOT-00{n}") for n in (1, 2)]
    canned["5e2"] = "# Gate 5\n\n```json captions\n" + json.dumps(items, ensure_ascii=False) + "\n```\n"
    calls = []

    def fake(prompt, model, effort):
        name = t4.stage_of(prompt)
        calls.append((name, prompt))
        if "Return ONLY a JSON list with the corrected objects" in prompt:     # the row repair: the same rows come back
            back = repair_rows or rows or _rows()
            return write_pack.envelope("```json\n" + json.dumps(back, ensure_ascii=False) + "\n```", "stop", "claude", "opus")
        return write_pack.envelope(canned[name], "stop", "claude", "opus")
    monkeypatch.setattr(write_pack, "call_claude", fake)
    out = tmp_path / "pack_reel2"
    t4.run(story, out, "--prompt-version", "v2.4", "--plan", str(plan), "--reel", "2", *extra)
    return out, calls


def test_a_plan_run_skips_stage_1_and_feeds_the_packet_to_the_reel(tmp_path, monkeypatch, story):
    out, calls = _run(tmp_path, monkeypatch, story)
    names = [n for n, _ in calls]
    assert "1" not in names and names == ["2", "3e2", "5e2"]
    stage3 = dict(calls)["3e2"]
    assert "UNIQUE-MNR" in stage3 and "LEDGER-WINS-PLACE" in stage3 and "Episode 2 only" in stage3
    plan = json.loads((out / "story_plan.json").read_text(encoding="utf-8"))
    assert plan["premise"] == PREMISE and plan["reel_target_s"] == 13 and plan["hook_type"] == "kinetic"
    shots = json.loads((out / "shots.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in shots] == ["SHOT-001", "SHOT-002"]
    assert json.loads((out / "story_shape.json").read_text(encoding="utf-8"))["errors"] == []


def test_a_plan_run_with_a_bible_makes_no_stage_2_call_and_keeps_the_bible(tmp_path, monkeypatch, story):
    bible_path = tmp_path / "base_bible.json"
    bible = t4.bible_answer()
    bible_path.write_text(json.dumps(bible, ensure_ascii=False), encoding="utf-8")
    out, calls = _run(tmp_path, monkeypatch, story, "--bible", str(bible_path))
    assert [n for n, _ in calls] == ["3e2", "5e2"]
    assert json.loads((out / "bible.json").read_text(encoding="utf-8")) == write_pack.canonical_bible(bible)


def test_shot_1_must_carry_the_plan_hook_type(tmp_path, monkeypatch, story):
    with pytest.raises(write_pack.StageFailed, match="PLAN-HOOK"):
        _run(tmp_path, monkeypatch, story, rows=_rows(hook="scale_tableau"))


def test_a_planned_voice_rest_must_exist(tmp_path, monkeypatch, story):
    rows = _rows()
    for r in rows:
        r.pop("voice_rest", None)
    with pytest.raises(write_pack.StageFailed, match="PLAN-REST"):
        _run(tmp_path, monkeypatch, story, rows=rows)


def test_plan_errors_name_shot_ids_so_the_repair_can_fix_them():
    errs = write_pack.plan_reel_errors(_rows(hook="none"), {"hook_type": "kinetic", "voice_rest": {"shot": "SHOT-002"}})
    assert errs and all("SHOT-" in e for e in errs)
    assert write_pack.plan_reel_errors(_rows(), {"hook_type": "kinetic", "voice_rest": {"shot": "SHOT-002"}}) == []


def test_a_reel_route_is_asked_for_and_checked_on_every_blocking_sheet():
    rows = _rows()
    rows[0]["blocking"], rows[1]["blocking"] = {"route": "S"}, {"route": "SE"}
    route_errs = lambda: [e for e in write_pack.plan_reel_errors(rows, {"route": "S"}) if e.startswith("PLAN-ROUTE")]
    assert route_errs() == ["PLAN-ROUTE at SHOT-002: blocking route is 'SE', this reel is written with route 'S' only"]
    rows[1]["blocking"]["route"] = "S"
    assert route_errs() == []
    text, plan = write_pack.with_route(("plan text", {"hook_type": "kinetic"}), "S")
    assert plan["route"] == "S" and '"route": "S"' in text and "no B end frame" in text


def test_a_plan_run_with_route_s_puts_the_route_in_the_stage_3_prompt(tmp_path, monkeypatch, story):
    with pytest.raises(write_pack.StageFailed, match="no blocking sheet"):   # the fixture rows carry no blocking sheet
        _run(tmp_path, monkeypatch, story, "--route", "S")
    assert (tmp_path / "pack_reel2" / "stage_3e2_raw.json").exists()        # stage 3 was called
    assert write_pack.REEL_PLAN[1]["route"] == "S" and '"route": "S"' in write_pack.REEL_PLAN[0]


def test_route_without_a_blocking_sheet_is_an_error():
    errs = write_pack.plan_reel_errors(_rows(), {"route": "S"})
    assert [e.split(":")[0] for e in errs] == ["PLAN-ROUTE at SHOT-001", "PLAN-ROUTE at SHOT-002"]
    assert "no blocking sheet" in errs[0]


def test_stage3_v24_asks_for_the_blocking_sheet_and_the_speaker_key():
    new, old = wp.stage3_text(2, v24=True), wp.stage3_text(2)
    assert "blocking/1.1" in new and "blocking/1.1" not in old
    assert '"speaker"' in new and 'never "who"' in new
    assert "round editorial_duration_sec down" in new


def test_a_repair_answer_in_a_tagged_shots_fence_is_read():
    import write_pack_glue
    raw = write_pack.envelope('```json shots\n[{"id": "SHOT-004"}]\n```', "stop", "nvidia", "m")
    assert write_pack_glue.parse_repair(raw) == [{"id": "SHOT-004"}]


def test_an_uncuttable_row_gets_the_lengths_that_cut_in_its_error(monkeypatch):
    from h3 import v4_to_h3

    def fake_fit(shots):                    # stand-in: SHOT-002 cuts only up to 5.0 s
        bad = [s["id"] for s in shots if s["id"] == "SHOT-002" and s["editorial_duration_sec"] > 5.0 + 1e-9]
        return shots, [], [f"{i}: no lattice n gives a legal cut" for i in bad]
    monkeypatch.setattr(v4_to_h3, "fit_lattice", fake_fit)
    rows = [{"id": "SHOT-001", "editorial_duration_sec": 4.0}, {"id": "SHOT-002", "editorial_duration_sec": 5.6}]
    errs = write_pack.fit_lattice_rows(rows)
    assert len(errs) == 1 and errs[0].startswith("H3-TIME SHOT-002")
    assert "lengths H3 can cut for SHOT-002 here: 4.1-5.0 s" in errs[0]
    assert rows[1]["editorial_duration_sec"] == 5.6                       # the row itself is not changed


def test_a_repair_only_replaces_the_rows_it_was_asked_for(tmp_path, monkeypatch, story):
    rows = _rows()
    rows[1]["arc_beat"] = "BAD"                                           # a fake validator error on SHOT-002 only
    t4.fake_validator(monkeypatch, lambda stage, data, bible:
                      [f"X at {s['id']}" for s in data["shots"] if s.get("arc_beat") == "BAD"] if stage == "3" else [])
    monkeypatch.setattr(t4, "fake_validator", lambda *a, **k: None)
    fixed = _rows()
    fixed[0]["arc_beat"] = "SHOULD-NOT-LAND"                              # the repair answer returns BOTH rows
    out, calls = _run(tmp_path, monkeypatch, story, rows=rows, repair_rows=fixed)
    shots = json.loads((out / "shots.json").read_text(encoding="utf-8"))
    assert shots[0]["arc_beat"] == "hook" and shots[1]["arc_beat"] == "payoff"
    stage5 = dict(calls)["5e2"]                                           # later stages see the repaired rows, not the stale ones
    assert "ROWS AFTER THE REPAIR" in stage5 and '"arc_beat": "payoff"' in stage5.split("ROWS AFTER THE REPAIR", 1)[1]


def test_row_index_errors_are_named_by_shot_id_so_the_repair_can_target_them():
    rows = [{"id": "SHOT-001"}, {"id": "SHOT-002"}]
    named = write_pack.name_rows(["ML-08 at shots[1].dialogue: stiff", "X at SHOT-001: bad", "REEL-01 at episode 2: long"], rows)
    assert named == ["ML-08 at shots[1] (SHOT-002).dialogue: stiff", "X at SHOT-001: bad", "REEL-01 at episode 2: long"]
    assert write_pack.name_rows(["at shots[7]: out of range"], rows) == ["at shots[7]: out of range"]


def test_a_lattice_problem_does_not_hide_the_other_stage_3_errors(tmp_path, monkeypatch, story):
    seen = []
    t4.fake_validator(monkeypatch, lambda stage, data, bible: seen.append(stage) or [])
    monkeypatch.setattr(t4, "fake_validator", lambda *a, **k: None)
    monkeypatch.setattr(write_pack, "fit_lattice_rows", lambda shots: ["H3-TIME SHOT-001: cannot cut"])
    with pytest.raises(write_pack.StageFailed, match="H3-TIME"):
        _run(tmp_path, monkeypatch, story)
    assert "3" in seen                                                    # the validator still ran on the rows


def test_an_untagged_captions_block_is_read_like_the_other_stages():
    items = [{"shot_id": "SHOT-001", "captions_by_lang": {"en": [{"text": "Go", "time_range": [0.4, 1.4]}]}}]
    raw = write_pack.envelope("# Gate 5\n\n```json\n" + json.dumps(items) + "\n```", "stop", "nvidia", "m")
    assert write_pack.parse_captions(raw)[1]["captions"] == items
    wrapped = write_pack.envelope("```json captions\n" + json.dumps({"captions": items}) + "\n```", "stop", "nvidia", "m")
    assert write_pack.parse_captions(wrapped)[1]["captions"] == items      # {"captions": [...]} is unwrapped
    other = write_pack.envelope("```json\n[1, 2]\n```", "stop", "nvidia", "m")      # not a captions list: still none
    assert write_pack.parse_captions(other)[1]["captions"] == []


def test_a_repaired_row_keeps_the_keys_the_repair_left_out(tmp_path, monkeypatch, story):
    rows = _rows()
    rows[1]["arc_beat"] = "BAD"
    t4.fake_validator(monkeypatch, lambda stage, data, bible:
                      [f"X at {s['id']}" for s in data["shots"] if s.get("arc_beat") == "BAD"] if stage == "3" else [])
    monkeypatch.setattr(t4, "fake_validator", lambda *a, **k: None)
    back = dict(_rows()[1])
    back.pop("voice_rest")                                                # the repair answer forgot voice_rest
    out, _ = _run(tmp_path, monkeypatch, story, rows=rows, repair_rows=[back])
    shots = json.loads((out / "shots.json").read_text(encoding="utf-8"))
    assert shots[1]["arc_beat"] == "payoff" and shots[1]["voice_rest"] == [3.0, 5.5]


def test_a_saved_repair_answer_is_reused_not_sent_again(tmp_path, monkeypatch, story):
    rows = _rows()
    rows[1]["arc_beat"] = "BAD"
    t4.fake_validator(monkeypatch, lambda stage, data, bible:
                      [f"X at {s['id']}" for s in data["shots"] if s.get("arc_beat") == "BAD"] if stage == "3" else [])
    monkeypatch.setattr(t4, "fake_validator", lambda *a, **k: None)
    out = tmp_path / "pack_reel2"
    out.mkdir()
    (out / "stage_3e2_repair1.json").write_text(write_pack.envelope(
        "```json\n" + json.dumps([_rows()[1]], ensure_ascii=False) + "\n```", "stop", "nvidia", "m"), encoding="utf-8")
    _, calls = _run(tmp_path, monkeypatch, story, rows=rows, repair_rows=[dict(_rows()[1], arc_beat="BAD")])
    assert not any("Return ONLY a JSON list" in p for _, p in calls)


def test_a_planned_voice_rest_is_not_dead_air():
    import script_pacing
    shot = {"id": "SHOT-001", "seconds": 10.0, "action": "a", "events": [{"t": 0.0}, {"t": 9.0}],
            "lines": [{"start_s": 0.4, "end_s": 1.4, "text": "a"}, {"start_s": 5.4, "end_s": 7.4, "text": "b"}]}
    assert any("dead air" in p for p in script_pacing.inspect_pacing([shot], "en")["problems"])
    rested = dict(shot, voice_rest=[2.0, 5.0])                            # gap 4.0 s, 3.0 s of it is the rest: 1.0 s left
    assert not any("dead air" in p for p in script_pacing.inspect_pacing([rested], "en")["problems"])
    row = dict(wp.example_row(1, 1, ["en"], v24=True))
    assert script_inspect.from_pack([row], "en")[0]["voice_rest"] == row["voice_rest"]


def test_plan_rows_get_the_blocking_sheet_and_source_ref_checks_with_shot_ids(tmp_path):
    rows = _rows()
    rows[0]["blocking"] = {"route": "S", "shot_id": "SHOT-001"}            # an incomplete sheet
    rows[1]["blocking"] = {"route": "S", "shot_id": "SHOT-002"}
    errs = write_pack.plan_reel_errors(rows, {"route": "S"})
    assert errs and all(e.startswith("PLAN-") and "SHOT-00" in e for e in errs)
    assert any("BLK-" in e for e in errs) and any("source_refs" in e for e in errs)


def test_stage3_v24_names_the_blocking_pose_and_camera_words():
    import blocking
    text = wp.stage3_text(2, v24=True)
    for word in blocking._POSES + blocking._CAMERA_11_MOVES:
        assert word in text
    assert "source_refs" in text and "stakes or a question" in text


def test_a_multilingual_shot_with_no_narration_needs_no_narration_by_lang():
    import pack_validator
    row = wp.example_row(1, 1, ["en", "hi"])
    row["audio_and_dialogue_track"].update(narration=None, narration_by_lang=None)
    errs, warns = [], []
    pack_validator._check_languages([row], ["en", "hi"], None, errs)
    assert not [e for e in errs if e["code"] == "ML-03"]
    row["audio_and_dialogue_track"]["narration"] = {"text": "x", "language": "en", "time_range": [0.5, 2.0]}
    errs = []
    pack_validator._check_languages([row], ["en", "hi"], None, errs)        # narration present: the by-lang block is still required
    assert [e for e in errs if e["code"] == "ML-03"]


def test_the_validator_takes_the_reel_target_for_reel_01():
    import pack_validator
    assert pack_validator.reel_range_for({"reel_target_s": 40}) == pytest.approx((36.0, 44.0))
    assert pack_validator.reel_range_for({"shots": []}) == pack_validator.STUDIO_REEL_RANGE
    assert pack_validator.reel_range_for([]) == pack_validator.STUDIO_REEL_RANGE


def test_stage_3_data_carries_the_reel_target(tmp_path, monkeypatch, story):
    seen = {}

    def check(stage, data, bible):
        if stage == "3":
            seen.update(data)
        return []
    t4.fake_validator(monkeypatch, check)
    monkeypatch.setattr(t4, "fake_validator", lambda *a, **k: None)          # keep this capturing validator in _run
    _run(tmp_path, monkeypatch, story)
    assert seen.get("reel_target_s") == 13


@pytest.mark.parametrize("extra", [["--plan", "x.json"], ["--reel", "2"], ["--plan", "x.json", "--reel", "2", "--episodes", "2"]])
def test_the_cli_refuses_half_a_plan_or_plan_with_episodes(tmp_path, story, extra):
    with pytest.raises(SystemExit):
        write_pack.main([str(story), str(tmp_path / "p"), "--staged", "--via", "claude", *extra])
    with pytest.raises(SystemExit):
        write_pack.main([str(story), str(tmp_path / "p"), "--plan", "x.json", "--reel", "2"])   # needs --staged


def test_script_inspect_takes_the_reel_target_for_the_length_window():
    shots = [{"id": "SHOT-001", "seconds": 20.0, "action": "Raj runs", "events": [{"t": 0.0}],
              "lines": [{"start_s": 0.5, "end_s": 2.0, "text": "Run!"}]},
             {"id": "SHOT-002", "seconds": 20.0, "action": "Raj stops", "events": [{"t": 0.0}, {"t": 18.0}], "lines": []}]
    default = script_inspect.inspect_script(shots, "en")
    planned = script_inspect.inspect_script(shots, "en", story={"reel_target_s": 40})
    assert any("60 and 75" in w for w in default["pacing"]["warnings"])
    assert not any("60 and 75" in w for w in planned["pacing"]["warnings"])


def test_a_null_shape_hook_type_on_a_later_row_is_no_hook_type():
    rows = _rows()
    rows[1]["shape_hook_type"] = None                                     # the writer wrote null on a later row
    errors, _ = story_shape.lint(write_pack.shape_rows(rows), {"premise": PREMISE})
    assert not [e for e in errors if e.startswith("SHAPE-09")]


def test_story_shape_premise_from_the_plan_passes(tmp_path):
    _, plan = write_pack.load_reel_plan(plan_file(tmp_path), 2)
    errors, _ = story_shape.lint(write_pack.shape_rows(_rows()), plan)
    assert errors == []
