"""The V4 writer: staged prompts, the validator gate with ONE repair retry, the canonical bible, the V4 rows with legacy fields, and the
output languages (--out-lang en|hi|mr|en,hi|all). No network, no model call: the model is a canned fake and the validator is a fake
module injected into sys.modules (the real pack_validator is not needed here)."""
import json
import re
import sys
import types

import pytest

import run_registry
import write_pack
import writer_prompts as wp
from writer_prompts import spec

STORY_ANSWER = {"story_gate_checks": {c: {"pass": True, "evidence": "the spine line"} for c in spec.STORY_GATE_CHECKS},
                "duration_bucket": "60-90", "reel_seconds": 68.0, "episodes": [{"episode": 1, "title": "river", "seconds": 68.0}]}


def bible_answer():
    return wp._bible_example()


def captions_items(langs):
    if len(langs) > 1:
        return [{"shot_id": "SHOT-001", "captions_by_lang": {c: ["one short card"] for c in langs},
                 "narration_text_by_lang": None, "dialogue_texts_by_lang": None}]
    return [{"shot_id": "SHOT-001", "cards": ["one short card"], "narration_text": None, "dialogue_texts": []}]


def canned(langs):
    rows = [wp.example_row(1, 1, langs)]
    return {
        "1": "# Gate 1\n\nEpisode 1: the river\n\n```json story\n" + json.dumps(STORY_ANSWER) + "\n```\n",
        "2": "# Gate 2\n\n```json bible\n" + json.dumps(bible_answer(), ensure_ascii=False) + "\n```",
        "3e1": "# Episode 1\n\n```json shots\n" + json.dumps(rows, ensure_ascii=False) + "\n```\n",
        "5": "# Gate 5\n\n```json captions\n" + json.dumps(captions_items(langs), ensure_ascii=False) + "\n```\n",
    }


def stage_of(prompt):
    return re.search(r"Stage (\S+) only", prompt.rsplit("## THIS STAGE", 1)[1]).group(1)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network call in a test")
    monkeypatch.setattr(write_pack, "call_nvidia", boom)
    monkeypatch.setattr(write_pack, "call_openrouter", boom)


@pytest.fixture
def story(tmp_path):
    folder = tmp_path / "stories" / "kaliya_v4"
    folder.mkdir(parents=True)
    path = folder / "SOURCE.md"
    path.write_text("Kaliya story\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def simple_language(monkeypatch):
    """A stand-in for director/simple_language.py: text containing BAD is not simple; everything else is."""
    mod = types.ModuleType("simple_language")
    mod.check_text = lambda text, lang: ({"ok": False, "flags": [{"word": "BAD", "reason": "stiff", "suggestion": ""}]}
                                         if "BAD" in text else {"ok": True, "flags": []})
    monkeypatch.setitem(sys.modules, "simple_language", mod)
    return mod


@pytest.fixture
def fake_claude(monkeypatch):
    calls = []
    state = {"answers": canned(["hi"])}

    def fake(prompt, model, effort):
        name = stage_of(prompt)
        calls.append({"name": name, "prompt": prompt})
        return write_pack.envelope(state["answers"][name], "stop", "claude", "opus")
    monkeypatch.setattr(write_pack, "call_claude", fake)
    return {"calls": calls, "state": state}


def fake_validator(monkeypatch, check):
    """check(stage, data, bible) -> list of error codes (strings). Returns the list of stages it was asked about."""
    seen = []

    def validate_stage(stage, data, bible=None, *, output_languages=None, lang_check=None, voice_engines=None):
        seen.append(stage)
        errors = check(stage, data, bible)
        return {"ok": not errors, "errors": [{"code": "V-1", "where": stage, "message": e} for e in errors], "warnings": [],
                "stats": {}}
    mod = types.ModuleType("pack_validator")
    mod.validate_stage = validate_stage
    monkeypatch.setitem(sys.modules, "pack_validator", mod)
    return seen


def run(story, out, *extra):
    return write_pack.main([str(story), str(out), "--staged", "--via", "claude", *extra])


# ------------------------------------------------------------------ prompts: the V4 requirements
def test_stage_prompts_carry_the_v4_requirements():
    one = wp.stage_instruction("1")
    for check in spec.STORY_GATE_CHECKS:
        assert check in one
    assert "60.0" in one and "75.0" in one and "story" in one
    two = wp.stage_instruction("2")
    for needle in ("continuity_landmarks", "16:9", "plain neutral backdrop", "2D hand-drawn", "cel-shaded", "Puranic", "forbidden_looks",
                   "ENV-", "CHAR-", "PROP-"):
        assert needle in two
    three = wp.stage_instruction("3e1", 68.0, 1)
    for needle in ("lattice_n", "pixel_frames", "latent_slots", "continuity_handoff", "reference_anchors", "fixed_landmarks",
                   "character_positions", "exited_character_status", "lighting_baseline", "hook_type", "is_opening_0_2s_hook",
                   "is_closing_hook", "deliberate_flip_marker", "per_second_directives", "handoff_to_next_second",
                   "audio_and_dialogue_track", "sfx_cues", "narrator_mouth_closed", "mouth_state", "SHOT-001"):
        assert needle in three
    for hook in spec.HOOKS:
        assert hook in three
    assert "5 + 17n" in three and "5n + 2" in three
    five = wp.stage_instruction("5")
    assert "6 words" in five and "captions" in five


def test_every_prompt_bans_speech_in_h3_and_the_3d_look():
    rules = wp.rules_block()
    assert "(S1)" in rules and "[Language]" in rules and "<Audio N>" in rules
    assert "narrator_mouth_closed" in rules and "Non-diegetic music is N/A" in rules
    assert "Pixar" in rules and "never" in rules.lower()


def test_the_override_names_the_superseded_v22_sections():
    assert "V4 OVERRIDE" in wp.OVERRIDE and "section (c)" in wp.OVERRIDE and "section (d)" in wp.OVERRIDE


def test_the_stage_prompt_is_the_brief_the_story_the_override_the_rules_and_the_stage():
    brief = write_pack.staged_brief().read_text(encoding="utf-8")
    prompt = write_pack.build_stage_prompt(brief, "Kaliya story", [("1", "earlier")], wp.stage_instruction("2"))
    assert brief in prompt and "Kaliya story" in prompt and "SAVED OUTPUT OF STAGE 1" in prompt
    assert prompt.index("V4 OVERRIDE") < prompt.index("V4 RULES") < prompt.index("## THIS STAGE") < prompt.index("Stage 2 only")


# ------------------------------------------------------------------ the validator gate
def test_a_validator_failure_triggers_exactly_one_repair_call(tmp_path, story, fake_claude, monkeypatch):
    failed_once = {"done": False}

    def check(stage, data, bible):
        if stage == "1" and not failed_once["done"]:
            failed_once["done"] = True
            return ["STORY-01 missing story_gate_checks"]
        return []
    seen = fake_validator(monkeypatch, check)
    run(story, tmp_path / "pack_v1")
    names = [c["name"] for c in fake_claude["calls"]]
    assert names == ["1", "1", "2", "3e1", "5"]                 # stage 1 twice: the answer, then ONE repair
    repair = fake_claude["calls"][1]["prompt"]
    assert "VALIDATION ERRORS IN YOUR LAST ANSWER" in repair and "STORY-01 missing story_gate_checks" in repair
    assert "VALIDATION ERRORS" not in fake_claude["calls"][0]["prompt"]
    assert seen == ["1", "1", "2", "3", "5"]
    assert not (tmp_path / "pack_v1" / "stage_1_validation.json").exists()


def test_a_second_failure_fails_the_run_and_saves_the_errors(tmp_path, story, fake_claude, monkeypatch):
    fake_validator(monkeypatch, lambda stage, data, bible: ["SHOT-00 bad lattice"] if stage == "2" else [])
    out = tmp_path / "pack_v1"
    with pytest.raises(write_pack.StageFailed, match="stage 2 fails its checks after the repair retry"):
        run(story, out)
    assert [c["name"] for c in fake_claude["calls"]] == ["1", "2", "2"]          # one call, one repair, then stop
    assert (out / "stage_2_raw.json").exists()
    saved = json.loads((out / "stage_2_validation.json").read_text(encoding="utf-8"))
    assert saved["errors"] == ["V-1 at 2: SHOT-00 bad lattice"] and saved["repair_retries"] == 1
    assert not (out / "PACK.md").exists() and not (out / "shots.json").exists()
    fake_claude["calls"].clear()
    with pytest.raises(write_pack.StageFailed, match="delete both files"):   # a second run makes no call until the files go
        run(story, out)
    assert fake_claude["calls"] == []


def test_a_missing_validator_module_is_a_warning_not_a_crash(tmp_path, story, fake_claude, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pack_validator", None)
    run(story, tmp_path / "pack_v1")
    assert "pack_validator unavailable" in capsys.readouterr().err
    assert (tmp_path / "pack_v1" / "shots.json").exists()
    assert [c["name"] for c in fake_claude["calls"]] == ["1", "2", "3e1", "5"]


def test_each_validation_is_recorded_in_the_run_registry(tmp_path, story, fake_claude, monkeypatch):
    fails = {"n": 0}

    def check(stage, data, bible):
        if stage == "1" and fails["n"] == 0:
            fails["n"] += 1
            return ["STORY-01 once"]
        return []
    fake_validator(monkeypatch, check)
    run(story, tmp_path / "pack_v1")
    checks = [e for e in run_registry.read_events(story.parent) if e["kind"] == "pack_check"]
    stage1 = [(e["status"], e.get("stage")) for e in checks if e.get("stage") == "1"]
    assert ("failed", "1") in stage1 and ("ok", "1") in stage1
    assert {e.get("stage") for e in checks} >= {"1", "2", "3e1", "5"}


def test_the_stage_checks_get_the_bible_of_stage_2(tmp_path, story, fake_claude, monkeypatch):
    got = {}

    def check(stage, data, bible):
        got[stage] = bible
        return []
    fake_validator(monkeypatch, check)
    run(story, tmp_path / "pack_v1")
    assert got["1"] is None and got["2"] is None
    assert got["3"] == bible_answer() and got["5"] == bible_answer()


# ------------------------------------------------------------------ pack assembly
def test_the_canonical_bible_and_the_v4_rows_are_written(tmp_path, story, fake_claude, monkeypatch):
    fake_validator(monkeypatch, lambda *a: [])
    out = tmp_path / "pack_v1"
    run(story, out)
    bible = json.loads((out / "bible.json").read_text(encoding="utf-8"))
    assert list(bible)[:4] == ["style_lock", "characters", "environments", "props"]
    assert set(bible["characters"]) == {"CHAR-RAJ"} and set(bible["environments"]) == {"ENV-HALL"}
    assert bible["environments"]["ENV-HALL"]["continuity_landmarks"]
    shot = json.loads((out / "shots.json").read_text(encoding="utf-8"))[0]
    assert shot["lattice_n"] == 10 and shot["pixel_frames"] == 175 and shot["latent_slots"] == 52
    assert shot["reference_anchors"]["lighting_baseline"]["key"]
    assert shot["mode"] == "ref2va" and shot["seconds"] == 7.0 and shot["aspect"] == "9:16"       # legacy fields derived
    assert shot["action"].startswith("0.0-1.0s Raj lifts his eyes")
    assert "a small pop as the flame bends" in shot["sound"]
    assert shot["style"] == bible["style_lock"]["prefix"]
    story_plan = json.loads((out / "story_plan.json").read_text(encoding="utf-8"))
    assert story_plan["reel_seconds"] == 68.0 and "text" not in story_plan


def test_a_legacy_row_is_kept_as_it_came(tmp_path):
    row = {"id": "SHOT-01", "episode": 1, "mode": "fl2va", "seconds": 4}
    assert write_pack.legacy_fields(row, None) is row
    v4 = write_pack.legacy_fields({"id": "SHOT-02", "episode": 1, "route": "FL2VA", "lattice_n": 6, "editorial_duration_sec": 4.0,
                                   "mode": "keep-me"}, None)
    assert v4["mode"] == "keep-me" and v4["seconds"] == 4.0 and v4["mode"] != "ref2va"


def test_stage_5_captions_land_on_the_shot_rows(tmp_path, story, fake_claude, monkeypatch):
    fake_validator(monkeypatch, lambda *a: [])
    fake_claude["state"]["answers"]["5"] = ("# Gate 5\n\n```json captions\n" + json.dumps([
        {"shot_id": "SHOT-001", "cards": ["the lamp is lit"], "narration_text": "रात में दीया जला।", "dialogue_texts": []}])
        + "\n```\n")
    out = tmp_path / "pack_v1"
    run(story, out)
    shot = json.loads((out / "shots.json").read_text(encoding="utf-8"))[0]
    assert shot["captions"] == ["the lamp is lit"]
    assert shot["audio_and_dialogue_track"]["narration"]["text"] == "रात में दीया जला।"


# ------------------------------------------------------------------ output languages: parsing and the flag
@pytest.mark.parametrize("text, expected", [("en", ["en"]), ("hi", ["hi"]), ("mr", ["mr"]), ("en,hi", ["en", "hi"]),
                                            ("mr,en", ["mr", "en"]), ("all", ["en", "hi", "mr"]), ("ALL", ["en", "hi", "mr"]),
                                            (" hi , mr ", ["hi", "mr"])])
def test_out_lang_flag_parses_one_two_or_all(text, expected):
    assert wp.parse_langs(text) == expected


@pytest.mark.parametrize("text", ["fr", "en,fr", "hi,hi", "", ",", "en,,hi", "english"])
def test_out_lang_flag_refuses_bad_values(text):
    with pytest.raises(ValueError):
        wp.parse_langs(text)


def test_the_cli_refuses_a_bad_out_lang_and_out_lang_without_staged(tmp_path, story):
    with pytest.raises(SystemExit):
        write_pack.main([str(story), str(tmp_path / "p"), "--staged", "--via", "claude", "--out-lang", "fr"])
    with pytest.raises(SystemExit):
        write_pack.main([str(story), str(tmp_path / "p"), "--via", "claude", "--out-lang", "hi"])


def test_the_language_rule_is_in_the_prompt_for_each_language():
    expected = {
        "en": ("plain everyday spoken English", "English"),
        "hi": ("simple everyday spoken Hindi", "Hindi"),
        "mr": ("simple everyday spoken Marathi", "Marathi"),
    }
    for code, (rule_text, name) in expected.items():
        for prompt in (wp.rules_block([code]), wp.stage_instruction("3e1", 68.0, 1, [code]), wp.stage_instruction("5", langs=[code])):
            assert name in prompt and rule_text in prompt
    assert "no Hindi words" in wp.rules_block(["mr"])
    english_rule = wp.rules_block(["en"]).split("7. Output language")[1].split("8. Characters")[0]
    assert "Hindi" not in english_rule and "Marathi" not in english_rule


def test_single_language_prompts_have_no_by_lang_fields_and_the_example_uses_the_code():
    for code in ("en", "hi", "mr"):
        stage3 = wp.stage_instruction("3e1", 68.0, 1, [code])
        assert "_by_lang" not in stage3 and "captions_by_lang" not in wp.stage_instruction("5", langs=[code])
        example = json.loads(re.search(r"```json shots\n(.*?)\n```", stage3, re.DOTALL).group(1))[0]
        assert example["audio_and_dialogue_track"]["narration"]["language"] == code
        assert "narration_by_lang" not in example["audio_and_dialogue_track"]


def test_multi_language_prompts_ask_for_every_selected_language_with_the_same_timing():
    langs = ["en", "hi", "mr"]
    stage3 = wp.stage_instruction("3e1", 68.0, 1, langs)
    for field in ("narration_by_lang", "dialogue_by_lang", "captions_by_lang"):
        assert field in stage3
    assert "SAME time_range" in stage3 and "primary" in stage3
    for name in ("English", "Hindi", "Marathi"):
        assert name in stage3
    stage5 = wp.stage_instruction("5", langs=langs)
    assert "captions_by_lang" in stage5 and "narration_text_by_lang" in stage5
    example = json.loads(re.search(r"```json shots\n(.*?)\n```", stage3, re.DOTALL).group(1))[0]["audio_and_dialogue_track"]
    assert set(example["narration_by_lang"]) == set(langs)
    assert {v["time_range"][0] for v in example["narration_by_lang"].values()} == {example["narration"]["time_range"][0]}
    assert all(v["language"] == k for k, v in example["narration_by_lang"].items())


def test_stage_1_data_carries_the_selected_languages_for_the_validator(tmp_path, story, fake_claude, monkeypatch):
    seen = {}

    def validate_stage(stage, data, bible=None, *, output_languages=None, lang_check=None, voice_engines=None):
        if stage == "1":
            seen["data"], seen["langs"], seen["hook"] = data, output_languages, lang_check
        return {"ok": True, "errors": [], "warnings": [], "stats": {}}
    mod = types.ModuleType("pack_validator")
    mod.validate_stage = validate_stage
    monkeypatch.setitem(sys.modules, "pack_validator", mod)
    fake_claude["state"]["answers"] = canned(["en", "hi"])     # the run is en,hi: the stage 5 answer must cover both (writer caption checks run)
    run(story, tmp_path / "pack_v1", "--out-lang", "en,hi")
    assert seen["langs"] == ["en", "hi"] and seen["data"]["output_languages"] == ["en", "hi"]
    assert seen["data"]["output_language"] == "en" and seen["hook"] is not None
    plan = json.loads((tmp_path / "pack_v1" / "story_plan.json").read_text(encoding="utf-8"))
    assert plan["output_languages"] == ["en", "hi"]


def test_the_language_rule_of_the_primary_comes_first_in_a_two_language_prompt():
    text = wp.rules_block(["mr", "en"])
    assert "primary first: mr, en" in text and "Marathi" in text and "English" in text


# ------------------------------------------------------------------ output languages: checks
def shot_with(narration_lang="mr", text="रात्री दिवा लावला.", time_range=(0.5, 5.0)):
    return {"id": "SHOT-001", "audio_and_dialogue_track": {
        "narration": {"text": text, "language": narration_lang, "time_range": list(time_range)}, "dialogue": []}}


def test_one_language_narration_must_carry_that_language(simple_language):
    assert write_pack.shot_language_errors([shot_with("mr")], ["mr"]) == []
    errors = write_pack.shot_language_errors([shot_with("hi")], ["mr"])
    assert errors and errors[0].startswith("LANG-01") and "output language is 'mr'" in errors[0]


def test_a_non_simple_text_is_flagged_for_its_language(simple_language):
    errors = write_pack.shot_language_errors([shot_with("mr", "BAD मराठी")], ["mr"])
    assert errors and errors[0].startswith("LANG-02 at SHOT-001.narration")


def multi_shot(langs=("en", "hi", "mr"), time_range=(0.5, 5.0), **overrides):
    shot = wp.example_row(1, 1, list(langs))
    track = shot["audio_and_dialogue_track"]
    for c in langs:
        track["narration_by_lang"][c]["time_range"] = list(time_range)
    track.update(overrides)
    return shot


def test_multi_language_shots_pass_when_every_language_is_present_and_timed_alike(simple_language):
    assert write_pack.shot_language_errors([multi_shot()], ["en", "hi", "mr"]) == []


def test_multi_language_shots_flag_a_missing_language_and_a_timing_mismatch(simple_language):
    missing = multi_shot()
    del missing["audio_and_dialogue_track"]["narration_by_lang"]["hi"]
    assert any(e.startswith("LANG-03") for e in write_pack.shot_language_errors([missing], ["en", "hi", "mr"]))
    shifted = multi_shot()
    shifted["audio_and_dialogue_track"]["narration_by_lang"]["mr"]["time_range"] = [1.0, 5.0]
    assert any(e.startswith("LANG-04") for e in write_pack.shot_language_errors([shifted], ["en", "hi", "mr"]))
    wrong_code = multi_shot()
    wrong_code["audio_and_dialogue_track"]["narration_by_lang"]["en"]["language"] = "hi"
    assert any(e.startswith("LANG-01") for e in write_pack.shot_language_errors([wrong_code], ["en", "hi", "mr"]))


def test_multi_language_dialogue_must_match_speakers_and_timing(simple_language):
    shot = multi_shot()
    line = {"speaker": "CHAR-RAJ", "text": "नमस्ते", "tone": "soft", "time_range": [1.0, 2.0]}
    shot["audio_and_dialogue_track"]["dialogue_by_lang"] = {"en": [dict(line, text="hello")],
                                                            "hi": [dict(line)], "mr": [dict(line, time_range=[1.5, 2.0])]}
    errors = write_pack.shot_language_errors([shot], ["en", "hi", "mr"])
    assert len(errors) == 1 and errors[0].startswith("LANG-04") and "mr" in errors[0]


def test_captions_are_checked_for_word_count_and_language(simple_language):
    too_long = [{"shot_id": "SHOT-001", "cards": ["one two three four five six seven"]}]
    assert any(e.startswith("CAP-01") for e in write_pack.caption_language_errors(too_long, ["hi"]))
    bad = [{"shot_id": "SHOT-001", "cards": ["BAD"]}]
    assert any(e.startswith("LANG-02") for e in write_pack.caption_language_errors(bad, ["hi"]))
    uneven = [{"shot_id": "SHOT-001", "captions_by_lang": {"en": ["a"], "hi": ["a", "b"], "mr": ["a"]}}]
    assert any("same number of cards" in e for e in write_pack.caption_language_errors(uneven, ["en", "hi", "mr"]))
    ok = [{"shot_id": "SHOT-001", "captions_by_lang": {"en": ["a"], "hi": ["a"], "mr": ["a"]}}]
    assert write_pack.caption_language_errors(ok, ["en", "hi", "mr"]) == []


def test_a_missing_simple_language_module_skips_the_text_check_with_a_warning(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "simple_language", None)
    assert write_pack.text_language_errors([("x", "BAD")], "hi") == []
    assert "simple_language unavailable" in capsys.readouterr().err


def test_english_text_is_not_run_through_the_simple_language_check(simple_language):
    assert write_pack.text_language_errors([("x", "BAD")], "en") == []


# ------------------------------------------------------------------ output languages: runs and records
def test_the_default_run_is_hindi_and_records_it_in_story_json(tmp_path, story, fake_claude, monkeypatch, simple_language):
    fake_validator(monkeypatch, lambda *a: [])
    fake_claude["state"]["answers"] = canned(["hi"])
    run(story, tmp_path / "pack_v1")
    meta = json.loads((story.parent / "story.json").read_text(encoding="utf-8"))
    assert meta["output_languages"] == ["hi"] and meta["output_language"] == "hi"
    assert "_by_lang" not in fake_claude["calls"][2]["prompt"].split("## THIS STAGE", 1)[1]


def test_all_languages_run_records_the_list_and_the_first_as_primary(tmp_path, story, fake_claude, monkeypatch, simple_language):
    fake_validator(monkeypatch, lambda *a: [])
    fake_claude["state"]["answers"] = canned(["en", "hi", "mr"])
    out = tmp_path / "pack_v1"
    run(story, out, "--out-lang", "all")
    meta = json.loads((story.parent / "story.json").read_text(encoding="utf-8"))
    assert meta["output_languages"] == ["en", "hi", "mr"] and meta["output_language"] == "en"
    shot = json.loads((out / "shots.json").read_text(encoding="utf-8"))[0]
    assert shot["audio_and_dialogue_track"]["narration"]["language"] == "en"
    assert set(shot["audio_and_dialogue_track"]["narration_by_lang"]) == {"en", "hi", "mr"}
    stage3_prompt = [c for c in fake_claude["calls"] if c["name"] == "3e1"][0]["prompt"]
    assert "narration_by_lang" in stage3_prompt.split("## THIS STAGE", 1)[1]
    run_event = [e for e in run_registry.read_events(story.parent) if e["kind"] == "analysis_done" and e["status"] == "ok"][-1]
    assert "output languages en,hi,mr" in run_event["note"]


def test_a_subset_run_keeps_the_order_of_the_selection(tmp_path, story, fake_claude, monkeypatch, simple_language):
    fake_validator(monkeypatch, lambda *a: [])
    fake_claude["state"]["answers"] = canned(["mr", "en"])
    run(story, tmp_path / "pack_v1", "--out-lang", "mr,en")
    meta = json.loads((story.parent / "story.json").read_text(encoding="utf-8"))
    assert meta["output_languages"] == ["mr", "en"] and meta["output_language"] == "mr"


def test_a_multi_language_shot_missing_a_language_fails_the_stage_without_a_validator(tmp_path, story, fake_claude, monkeypatch):
    monkeypatch.setitem(sys.modules, "pack_validator", None)           # the writer's own language checks are the fallback
    answers = canned(["en", "hi"])
    rows = [wp.example_row(1, 1, ["en", "hi"])]
    del rows[0]["audio_and_dialogue_track"]["narration_by_lang"]["hi"]
    answers["3e1"] = "# Episode 1\n\n```json shots\n" + json.dumps(rows, ensure_ascii=False) + "\n```\n"
    fake_claude["state"]["answers"] = answers
    with pytest.raises(write_pack.StageFailed, match="LANG-03"):
        run(story, tmp_path / "pack_v1", "--out-lang", "en,hi")
