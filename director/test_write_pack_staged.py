"""Staged writer (write_pack --staged) with fake callers: no network, no model call."""
import json
import re
import sys
import urllib.request

import pytest

import write_pack

SHOT = {"id": "SHOT-01", "episode": 1, "mode": "fl2va", "seconds": 4, "aspect": "9:16", "start": "keyframes/SHOT-01-FRAME-A.png",
        "end": "keyframes/SHOT-01-FRAME-B.png", "refs": [], "subjects": [], "style": "Flat 2D cel anime.", "world": "River at dawn.",
        "action": "0-2s a bird falls.", "camera": "tilt down", "sound": "boiling water hiss"}
BIBLE = {"palette": {"sky": "#aabbcc"}, "characters": ["CHAR-KRISHNA"]}
CANNED = {
    "1": "# Gate 1\n\nEpisode 1: the river\nEpisode 2: the serpent\n",
    "2": "# Gate 2\n\n```json bible\n" + json.dumps(BIBLE) + "\n```",
    "3e1": "# Episode 1 shots\n\n```json shots\n" + json.dumps([SHOT]) + "\n```\n",
    "3e2": "# Episode 2 shots\n\n```json shots\n" + json.dumps([dict(SHOT, id="SHOT-02", episode=2)]) + "\n```\n",
    "5": "# Gate 5\n\nCaptions and QA.\n",
}


def envelope(text, via="claude", model="opus"):
    return write_pack.envelope(text, "stop", via, model)


def stage_of(prompt):
    return re.search(r"Stage (\S+) only", prompt.rsplit("## THIS STAGE", 1)[1]).group(1)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("network call in a test")
    monkeypatch.setattr(write_pack, "call_nvidia", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)


@pytest.fixture(autouse=True)
def no_validator(monkeypatch):
    """These tests cover the staged plumbing (resume, routing, merge) with the canned answers above, which are not V4 answers:
    the validator is switched off here (a warning, not a crash). The V4 checks are in test_writer_v4.py."""
    monkeypatch.setitem(sys.modules, "pack_validator", None)


@pytest.fixture
def story(tmp_path):
    path = tmp_path / "story.md"
    path.write_text("Kaliya story\n", encoding="utf-8")
    return path


@pytest.fixture
def fake_claude(monkeypatch):
    calls = []

    def fake(prompt, model, effort):
        name = stage_of(prompt)
        calls.append({"name": name, "model": model, "prompt": prompt})
        return envelope(CANNED.get(name) or CANNED["5"])
    monkeypatch.setattr(write_pack, "call_claude", fake)
    return calls


def staged(story, out, *extra):
    return write_pack.main([str(story), str(out), "--staged", *extra])


def test_staged_run_writes_pack_bible_and_merged_shots(tmp_path, story, fake_claude):
    out = tmp_path / "pack"
    staged(story, out, "--via", "claude")
    assert [c["name"] for c in fake_claude] == ["1", "2", "3e1", "3e2", "5e1", "5e2"]
    pack = (out / "PACK.md").read_text(encoding="utf-8")
    positions = [pack.index(CANNED[n].strip()[:20]) for n in ("1", "2", "3e1", "3e2", "5")]
    assert positions == sorted(positions)
    assert json.loads((out / "bible.json").read_text(encoding="utf-8")) == BIBLE
    shots = json.loads((out / "shots.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in shots] == ["SHOT-01", "SHOT-02"]
    for n in ("1", "2", "3e1", "3e2", "5e1", "5e2"):
        assert (out / f"stage_{n}_raw.json").exists()


def test_a_second_run_makes_no_calls(tmp_path, story, fake_claude, monkeypatch):
    out = tmp_path / "pack"
    staged(story, out, "--writer", "opus")
    before = (out / "shots.json").read_text(encoding="utf-8")
    monkeypatch.setattr(write_pack, "call_claude", lambda *a: pytest.fail("resume must not call the model"))
    staged(story, out, "--writer", "opus")
    assert (out / "shots.json").read_text(encoding="utf-8") == before


def test_each_stage_gets_the_brief_the_story_and_earlier_saved_text(tmp_path, story, fake_claude):
    staged(story, tmp_path / "pack", "--writer", "opus")
    prompts = {c["name"]: c["prompt"] for c in fake_claude}
    assert all("Kaliya story" in p and write_pack.staged_brief().read_text(encoding="utf-8") in p for p in prompts.values())
    assert CANNED["1"].strip() in prompts["2"] and CANNED["1"].strip() not in prompts["1"]
    assert CANNED["3e1"].strip() in prompts["3e2"] and CANNED["2"].strip() in prompts["3e2"]
    assert CANNED["3e2"].strip() not in prompts["3e1"]


def test_the_raw_answer_is_saved_before_parsing_and_resume_redoes_only_the_bad_stage(tmp_path, story, fake_claude, monkeypatch):
    out = tmp_path / "pack"
    good = CANNED["3e1"]
    monkeypatch.setitem(CANNED, "3e1", "no shots block here")
    with pytest.raises(ValueError):
        staged(story, out, "--writer", "opus")
    assert (out / "stage_3e1_raw.json").exists()                 # saved although it did not parse
    monkeypatch.setitem(CANNED, "3e1", good)
    (out / "stage_3e1_raw.json").unlink()                        # the owner deletes the bad answer to redo it
    fake_claude.clear()
    staged(story, out, "--writer", "opus")
    assert [c["name"] for c in fake_claude] == ["3e1", "3e2", "5e1", "5e2"]


def test_stage_routing_per_stage_via_and_model(tmp_path, story, monkeypatch):
    seen = []

    def claude(prompt, model, effort):
        seen.append(("claude", stage_of(prompt), model))
        return envelope(CANNED.get(stage_of(prompt)) or CANNED["5"], "claude", model)

    def nvidia(prompt, model):
        seen.append(("nvidia", stage_of(prompt), model))
        return envelope(CANNED.get(stage_of(prompt)) or CANNED["5"], "nvidia", model)
    monkeypatch.setattr(write_pack, "call_claude", claude)
    monkeypatch.setattr(write_pack, "call_nvidia", nvidia)
    staged(story, tmp_path / "pack", "--via", "claude", "--model", "sonnet", "--stage-via", "2=nvidia,3=claude", "--stage-model", "3=haiku")
    assert seen == [("claude", "1", "sonnet"), ("nvidia", "2", write_pack.DEFAULT_MODEL["nvidia"]),
                    ("claude", "3e1", "haiku"), ("claude", "3e2", "haiku"), ("claude", "5e1", "sonnet"),
                    ("claude", "5e2", "sonnet")]


def test_stage_map_exact_name_beats_the_gate_number():
    table = write_pack.parse_stage_map("3=claude,3e2=nvidia", write_pack.check_via)
    assert write_pack.stage_setting(table, "3e1", "x") == "claude"
    assert write_pack.stage_setting(table, "3e2", "x") == "nvidia"
    assert write_pack.stage_setting({}, "5", "openrouter") == "openrouter"
    with pytest.raises(ValueError):
        write_pack.parse_stage_map("9=claude", write_pack.check_via)
    with pytest.raises(ValueError):
        write_pack.parse_stage_map("2=gpt", write_pack.check_via)


def test_a_paid_openrouter_stage_is_refused_before_any_call(tmp_path, story, monkeypatch):
    monkeypatch.setattr(write_pack, "openrouter_is_free", lambda model, catalog=None: False)
    monkeypatch.setattr(write_pack, "OPENROUTER_KEY", tmp_path / "no_such_key_file.txt")
    with pytest.raises(ValueError, match="paid"):
        staged(story, tmp_path / "pack", "--via", "openrouter", "--model", "x/paid")


def test_stage_1_names_episodes_from_lines_or_a_json_block():
    assert write_pack.episodes_from("Episode 2: b\nEp 1 - a\nEpisode 2 again\n") == [1, 2]
    assert write_pack.episodes_from("intro\n```json episodes\n[3, 4]\n```\n") == [3, 4]
    with pytest.raises(ValueError):
        write_pack.episodes_from("no episodes named here")


def test_bible_parse_is_tolerant_and_strict_about_its_block():
    assert write_pack.bible_from('{"a": 1}\n{"b": 2}') == {"a": 1, "b": 2}
    assert write_pack.parse_bible(envelope("x\n```json bible\n" + json.dumps(BIBLE) + "\n```"))[1] == BIBLE
    with pytest.raises(ValueError):
        write_pack.parse_bible(envelope("```json bible\n{}\n```\nthanks"))         # must end with the block
    with pytest.raises(ValueError):
        write_pack.parse_bible(envelope("```json bible\n{}\n```\n```json bible\n{}\n```"))
    with pytest.raises(ValueError):
        write_pack.bible_from("[1, 2]")


def test_an_untagged_json_bible_block_is_accepted():
    assert write_pack.parse_bible(envelope("# Gate 2\n\n```json\n" + json.dumps(BIBLE) + "\n```"))[1] == BIBLE


def test_untagged_bible_fallback_takes_the_last_object_and_a_tagged_block_wins():
    last = envelope("```json\n{\"a\": 1}\n```\nnotes\n```json\n{\"b\": 2}\n```")
    assert write_pack.parse_bible(last)[1] == {"b": 2}
    tagged = envelope("```json\n{\"b\": 2}\n```\n```json bible\n" + json.dumps(BIBLE) + "\n```")
    assert write_pack.parse_bible(tagged)[1] == BIBLE
    with pytest.raises(ValueError, match="found 0"):
        write_pack.parse_bible(envelope("```json\n[1, 2]\n```"))


def test_an_untagged_json_shots_block_is_accepted_when_no_shots_block_exists():
    assert write_pack.parse(envelope("notes\n```json\n" + json.dumps([SHOT]) + "\n```"))[1] == [SHOT]


def test_untagged_shots_fallback_takes_the_last_list_of_objects():
    text = envelope("```json\n" + json.dumps([dict(SHOT, id="SHOT-09")]) + "\n```\n```json\n{\"x\": 1}\n```\n```json\n" + json.dumps([SHOT]) + "\n```")
    assert write_pack.parse(text)[1] == [SHOT]
    with pytest.raises(ValueError, match="found 0"):
        write_pack.parse(envelope("```json\n{\"x\": 1}\n```"))


def test_episodes_that_restart_their_shot_numbers_merge_into_unique_ids(tmp_path, story, fake_claude, monkeypatch):
    ep1 = [dict(SHOT, id="SHOT-01", episode=1), dict(SHOT, id="SHOT-02", episode=1, cut_in="match on action from SHOT-01")]
    ep2 = [dict(SHOT, id="SHOT-01", episode=2),
           dict(SHOT, id="SHOT-02", episode=2, cut_in="match on action from SHOT-01", start="keyframes/SHOT-02-FRAME-A.png")]
    monkeypatch.setitem(CANNED, "3e1", "```json shots\n" + json.dumps(ep1) + "\n```")
    monkeypatch.setitem(CANNED, "3e2", "```json shots\n" + json.dumps(ep2) + "\n```")
    staged(story, tmp_path / "pack", "--writer", "opus")
    shots = json.loads((tmp_path / "pack" / "shots.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in shots] == ["SHOT-001", "SHOT-002", "SHOT-003", "SHOT-004"]
    assert [s["source_id"] for s in shots] == ["SHOT-01", "SHOT-02", "SHOT-01", "SHOT-02"]
    assert shots[1]["cut_in"] == "match on action from SHOT-001"
    assert shots[3]["cut_in"] == "match on action from SHOT-003"
    assert shots[3]["start"] == "keyframes/SHOT-004-FRAME-A.png"


# ---- the fixed default style (owner 2026-11-07): a story without a style pack gets Deva Neon ----
def test_story_pack_id_defaults_to_deva_neon_and_keeps_an_explicit_pack(tmp_path):
    import json as _json
    import write_pack as _wp
    d = tmp_path / "s"
    d.mkdir()
    src = d / "SOURCE.md"
    src.write_text("x", encoding="utf-8")
    assert _wp.story_pack_id(src) == "deva_neon"                      # no story.json
    (d / "story.json").write_text(_json.dumps({"slug": "s"}), encoding="utf-8")
    assert _wp.story_pack_id(src) == "deva_neon"                      # story.json without a pack
    (d / "story.json").write_text(_json.dumps({"style_pack": "braj_earth"}), encoding="utf-8")
    assert _wp.story_pack_id(src) == "braj_earth"                     # the story's own choice wins


def test_a_new_story_json_carries_the_default_style_pack(tmp_path):
    import run_registry as _rr
    assert _rr.default_story(tmp_path / "newstory")["style_pack"] == "deva_neon"
