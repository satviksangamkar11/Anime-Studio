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
        return write_pack.envelope(state["answers"].get(name) or state["answers"]["5"], "stop", "claude", "opus")
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
        if stage == "3" and not failed_once["done"]:
            failed_once["done"] = True
            return ["SHOT-001 bad lattice"]
        return []
    seen = fake_validator(monkeypatch, check)
    answer_fake = write_pack.call_claude
    repaired = "```json\n" + json.dumps([wp.example_row(1, 1, ["hi"])], ensure_ascii=False) + "\n```\n"

    def fake(prompt, model, effort):
        if "Return ONLY a JSON list" in prompt:      # the repair call: a fenced list of the corrected row (plain text, as parse_repair reads it)
            fake_claude["calls"].append({"name": stage_of(prompt), "prompt": prompt})
            return repaired
        return answer_fake(prompt, model, effort)
    monkeypatch.setattr(write_pack, "call_claude", fake)
    run(story, tmp_path / "pack_v1")
    names = [c["name"] for c in fake_claude["calls"]]
    assert names == ["1", "2", "3e1", "3e1", "5e1"]               # stage 3e1 twice: the answer, then ONE repair of SHOT-001
    repair = fake_claude["calls"][3]["prompt"]
    assert "SHOT-001 bad lattice" in repair and "Return ONLY a JSON list" in repair
    assert "VALIDATION ERRORS" not in fake_claude["calls"][2]["prompt"]
    assert seen == ["1", "2", "3", "3", "5"]
    assert (tmp_path / "pack_v1" / "stage_3e1_repair1.json").exists()
    assert not (tmp_path / "pack_v1" / "stage_3e1_validation.json").exists()


def test_a_second_failure_fails_the_run_and_saves_the_errors(tmp_path, story, fake_claude, monkeypatch):
    fake_validator(monkeypatch, lambda stage, data, bible: ["SHOT-00 bad lattice"] if stage == "2" else [])
    out = tmp_path / "pack_v1"
    with pytest.raises(write_pack.StageFailed, match="stage 2 fails its checks after the repair retry"):
        run(story, out)
    assert [c["name"] for c in fake_claude["calls"]] == ["1", "2"]              # stage 2 is a bible, not a list of rows: no repair, stop
    assert (out / "stage_2_raw.json").exists()
    saved = json.loads((out / "stage_2_validation.json").read_text(encoding="utf-8"))
    assert saved["errors"] == ["V-1 at 2: SHOT-00 bad lattice"] and saved["repair_retries"] == 0
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
    assert [c["name"] for c in fake_claude["calls"]] == ["1", "2", "3e1", "5e1"]


def test_each_validation_is_recorded_in_the_run_registry(tmp_path, story, fake_claude, monkeypatch):
    def check(stage, data, bible):
        return ["STORY-01 once"] if stage == "1" else []     # a stage 1 failure names no shot id: no repair, the run stops
    fake_validator(monkeypatch, check)
    with pytest.raises(write_pack.StageFailed, match="stage 1 fails its checks"):
        run(story, tmp_path / "pack_v1")
    checks = [e for e in run_registry.read_events(story.parent) if e["kind"] == "pack_check"]
    assert [(e["status"], e.get("stage")) for e in checks if e["status"] != "started"] == [("failed", "1")]
    assert [c["name"] for c in fake_claude["calls"]] == ["1"]


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
    assert shot["lattice_n"] == 10 and shot["pixel_frames"] == 175 and shot["latent_slots"] == 52   # one-shot reel: no cut, the model's n stays (gap 2)
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


def test_without_flags_the_story_json_languages_and_voice_stand(tmp_path, story, fake_claude, monkeypatch, simple_language):
    fake_validator(monkeypatch, lambda *a: [])
    path = story.parent / "story.json"
    meta = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"slug": "t", "schema_version": 1}
    meta.update({"output_languages": ["mr", "en"], "output_language": "mr", "voice_engine": {"mr": "elevenlabs", "en": "h3"}})
    path.write_text(json.dumps(meta), encoding="utf-8")
    fake_claude["state"]["answers"] = canned(["mr", "en"])
    run(story, tmp_path / "pack_v1")                                   # no --out-lang, no --voice
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["output_languages"] == ["mr", "en"] and after["voice_engine"] == {"mr": "elevenlabs", "en": "h3"}


def test_a_multi_language_shot_missing_a_language_fails_the_stage_without_a_validator(tmp_path, story, fake_claude, monkeypatch):
    monkeypatch.setitem(sys.modules, "pack_validator", None)           # the writer's own language checks are the fallback
    answers = canned(["en", "hi"])
    rows = [wp.example_row(1, 1, ["en", "hi"])]
    del rows[0]["audio_and_dialogue_track"]["narration_by_lang"]["hi"]
    answers["3e1"] = "# Episode 1\n\n```json shots\n" + json.dumps(rows, ensure_ascii=False) + "\n```\n"
    fake_claude["state"]["answers"] = answers
    with pytest.raises(write_pack.StageFailed, match="stage 3e1 fails its checks"):
        run(story, tmp_path / "pack_v1", "--out-lang", "en,hi")
    assert [c["name"] for c in fake_claude["calls"]].count("3e1") == 2     # LANG-03 names SHOT-001: one repair call, its answer has no list


def test_writer_stages_never_get_tools_only_the_notes_call_does(monkeypatch):
    import write_pack as w
    seen = {}

    class R:
        returncode, stdout, stderr = 0, '{"type": "result", "result": ""}', ""

    def fake_run(cmd, input=None, **kw):
        seen["cmd"], seen["prompt"] = cmd, input
        return R()
    monkeypatch.setattr(w.subprocess, "run", fake_run)
    monkeypatch.setattr(w, "WEB", True)                     # even with --web, a writer stage runs with no tools
    w.call_claude("brief", "opus", "high")
    assert seen["cmd"][seen["cmd"].index("--tools") + 1] == "" and seen["prompt"] == "brief"
    w.call_claude("brief", "haiku", "low", web=True, rule=False)    # the research-notes call
    assert seen["cmd"][seen["cmd"].index("--tools") + 1] == "WebSearch,WebFetch" and "--allowedTools" in seen["cmd"]


@pytest.mark.real_style
def test_the_stage_3_example_row_passes_the_pack_checker(tmp_path):
    import write_pack as w
    import writer_prompts as wpm
    pack = w.load_style_pack("deva_neon")
    monkeypatch_look = wpm.LOOK_EXAMPLE
    try:
        wpm.LOOK_EXAMPLE = wpm.look_example(pack)
        row = w.legacy_fields(wpm.example_row(1, 1, ["en"]), {})
    finally:
        wpm.LOOK_EXAMPLE = monkeypatch_look
    d = tmp_path / "stories" / "t" / "pack_x"
    d.mkdir(parents=True)
    (d.parent / "story.json").write_text(json.dumps({"slug": "t", "style_pack": "deva_neon", "schema_version": 1}), encoding="utf-8")
    (d / "shots.json").write_text(json.dumps([row]), encoding="utf-8")
    (d / "bible.json").write_text("{}", encoding="utf-8")
    report = w.pack_check_report(d)
    assert report is not None and not report["fail"], report["issues"]
    assert row["look"]["hook"]["type"] == "H-03" and "palette_id" in row["look"]


def test_stage_3_brief_states_the_rehook_rule_the_validator_enforces():
    import pack_validator as pv
    import writer_prompts as wpm
    assert (wpm.REHOOK_REEL_MIN_SEC, wpm.REHOOK_WINDOW_FRAC) == (pv.REHOOK_REEL_MIN_SEC, pv.REHOOK_WINDOW_FRAC)
    text = wpm.stage3_text(1)
    assert "STARTS between 45% and 60%" in text and "36 s or longer" in text


def test_plan_errors_catch_a_broken_stage_1_plan():
    import write_pack as w
    good = {"episodes": [{"episode": 1, "seconds": 70}, {"episode": 2, "seconds": 66.5}]}
    assert w.plan_errors(good) == []
    assert w.plan_errors({"episodes": []})[0].startswith("PLAN-01")
    assert w.plan_errors({"episodes": [{"episode": 1, "seconds": 5}]})[0].startswith("PLAN-02")
    assert w.plan_errors({"episodes": [{"episode": 1, "seconds": 70}, {"episode": 3, "seconds": 70}]})[0].startswith("PLAN-03")
    assert w.plan_errors({"episodes": [{"episode": 1, "seconds": 70}, {"episode": 1, "seconds": 70}]})[0].startswith("PLAN-03")


def test_a_story_json_that_is_not_an_object_is_ignored(tmp_path, story, fake_claude, monkeypatch, simple_language):
    fake_validator(monkeypatch, lambda *a: [])
    (story.parent / "story.json").write_text("[1, 2]", encoding="utf-8")
    fake_claude["state"]["answers"] = canned(["en"])
    run(story, tmp_path / "pack_v1")                       # no flags: must not crash on meta_story.get


def test_every_claude_call_uses_stream_json(monkeypatch):
    import write_pack as w
    seen = {}

    class R:
        returncode, stderr = 0, ""
        stdout = '{"type": "result", "result": "x"}'

    monkeypatch.setattr(w.subprocess, "run", lambda cmd, **kw: seen.setdefault("cmd", cmd) and R())
    w.call_claude("brief", "opus", "high")                                  # a writer stage, no web
    assert seen["cmd"][seen["cmd"].index("--output-format") + 1] == "stream-json"


def test_web_notes_reach_every_writer(monkeypatch):
    import write_pack as w
    monkeypatch.setattr(w, "WEB", True)
    monkeypatch.setattr(w, "WEB_NOTES", "Kali has four arms")
    seen = {}
    monkeypatch.setattr(w, "call_nvidia", lambda prompt, model: seen.setdefault("nv", prompt) or "{}")
    monkeypatch.setattr(w, "call_claude", lambda prompt, model, effort: seen.setdefault("cl", prompt) or "{}")
    w.call_path("brief", "nvidia", "m", "high", False)
    w.call_path("brief", "claude", "opus", "high", False)
    for p in (seen["nv"], seen["cl"]):
        assert "Kali has four arms" in p and p.endswith("brief") and "story source stays the authority" in p


def test_make_web_notes_uses_haiku_low_with_web_and_reuses_the_file(monkeypatch, tmp_path):
    import json as _j
    import write_pack as w
    story = tmp_path / "SOURCE.md"
    story.write_text("Sati story", encoding="utf-8")
    calls = []
    body = "- Sati: daughter of Daksha (source link). " * 10
    monkeypatch.setattr(w, "call_claude", lambda prompt, model, effort, web=None, rule=True:
                        calls.append((model, effort, web, rule)) or _j.dumps({"result": "Done.\n```markdown\n" + body + "\n```"}))
    notes = w.make_web_notes(story)
    assert notes.startswith("- Sati: daughter of Daksha") and "```" not in notes
    assert calls == [("haiku", "low", True, False)]
    w.make_web_notes(story)
    assert len(calls) == 1 and (tmp_path / "WEB_NOTES.md").exists()
    (tmp_path / "WEB_NOTES.md").unlink()
    monkeypatch.setattr(w, "call_claude", lambda *a, **k: _j.dumps({"result": "short"}))
    with pytest.raises(RuntimeError):
        w.make_web_notes(story)
    assert not (tmp_path / "WEB_NOTES.md").exists()


@pytest.mark.real_style
def test_style_rules_send_the_whole_look():
    import write_pack as w
    r = w.style_rules("deva_neon")
    assert "Frame law: at most 1 neon colour per shot" in r and "#27E0FC" in r and "durga_kali_shakti" in r
    assert "every form or avatar of them" in r


@pytest.mark.real_style
def test_style_pack_errors_catch_an_off_style_bible_and_pass_a_good_one():
    import write_pack as w
    pack = w.load_style_pack("deva_neon")
    shiva = [c["hex"] for c in pack["palettes"]["shiva_neelkanth"]["colors"].values()]
    kali = [c["hex"] for c in pack["palettes"]["durga_kali_shakti"]["colors"].values()]
    bad = {"style_lock": {"colour": "earth tones first"},
           "characters": {"CHAR-SHIVA": {"sheet_prompt": "swatches #E8E6DF #7A4A2A #C98A2E"},
                          "CHAR-ADYA-KALI": {"sheet_prompt": "swatches #111111 #222222"},
                          "CHAR-SATI": {"sheet_prompt": "swatches #C9925E"}}}
    errs = w.style_pack_errors(bad, pack)
    assert sorted(e.split(" at ")[0] + " " + e.split(" at ")[1].split(":")[0] for e in errs) == [
        "STYLE-01 characters.CHAR-ADYA-KALI", "STYLE-01 characters.CHAR-SHIVA", "STYLE-02 style_lock"]
    good = {"style_lock": {"colour": f"night key {shiva[0]} with {kali[0]} accents"},
            "characters": {"CHAR-SHIVA": {"sheet_prompt": "swatches " + " ".join(shiva[:3])},
                           "CHAR-ADYA-KALI": {"sheet_prompt": "swatches " + " ".join(kali[:3])},
                           "CHAR-SATI": {"sheet_prompt": "swatches #C9925E"}}}
    assert w.style_pack_errors(good, pack) == []
    assert w.style_pack_errors(bad, {"palettes": {}}) == []


def test_join_stream_keeps_an_answer_split_by_a_search():
    import json as _j
    import write_pack as w
    ev = lambda t, **k: _j.dumps(dict(type=t, **k))   # noqa: E731
    say = lambda s: ev("assistant", message={"content": [{"type": "text", "text": s}]})   # noqa: E731
    lines = [ev("system"), say("Let me check a name."), ev("assistant", message={"content": [{"type": "tool_use", "name": "WebSearch"}]}),
             say("Here is the bible.\n```json\n{\"a\": "), ev("user"), say("1}\n```\n"),
             ev("result", result="1}\n```\n", total_cost_usd=2.0)]
    out = _j.loads(w.join_stream("\n".join(lines)))
    assert out["result"] == "Here is the bible.\n```json\n{\"a\": 1}\n```\n" and out["total_cost_usd"] == 2.0
    assert _j.loads(w.join_stream("\n".join([say("no fence"), ev("result", result="plain")])))["result"] == "plain"


def test_web_call_reads_the_stream(monkeypatch):
    import json as _j
    import write_pack as w
    seen = {}

    class R:
        returncode, stderr = 0, ""
        stdout = _j.dumps({"type": "result", "result": "x"})

    monkeypatch.setattr(w.subprocess, "run", lambda cmd, **kw: seen.setdefault("cmd", cmd) and R())
    w.call_claude("brief", "opus", "high", web=True)
    assert "stream-json" in seen["cmd"] and "--verbose" in seen["cmd"]


def test_episodes_option_writes_only_the_named_reel(tmp_path, story, fake_claude, monkeypatch):
    two = dict(STORY_ANSWER, episodes=[{"episode": 1, "title": "river", "seconds": 68.0}, {"episode": 2, "title": "lake", "seconds": 66.0}])
    fake_claude["state"]["answers"]["1"] = "# Gate 1\n\nEpisode 1: the river\nEpisode 2: the lake\n\n```json story\n" + json.dumps(two) + "\n```\n"
    monkeypatch.setattr(write_pack, "ONLY_EPISODES", None)
    fake_validator(monkeypatch, lambda stage, data, bible: [])
    run(story, tmp_path / "pack", "--episodes", "1")
    names = [c["name"] for c in fake_claude["calls"]]
    assert "3e1" in names and "3e2" not in names and "5e2" not in names


def test_style_rules_tell_the_writer_the_impact_budget():
    text = write_pack.style_rules("deva_neon")
    assert "Impact frames" in text and "white_out" in text and "at most 4 in total" in text and "shake" not in text
