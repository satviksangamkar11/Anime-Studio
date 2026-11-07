"""visual_qa colour criteria (G4, WP9 / A16 / A6 / A20) with fakes: no network, no model call, no ffmpeg."""
import json
import urllib.request

import pytest

import clip_tools
import visual_qa
import write_pack

NAMES9 = list(visual_qa.RUBRIC)
NAMES11 = list(visual_qa.RUBRIC_FULL)
DIRECTION = {"id": "SHOT-07", "purpose": "Krishna dives into the Yamuna"}
BIBLE_TEXT = '{"palette": {"sky": "PALETTE-SENTINEL"}}'
PACK = {
    "pack_id": "test_pack",
    "guardrails": ["GUARD-ONE: no neon on faces", "GUARD-TWO: saffron stays on the focal figure"],
    "frame_law": {"area_split": [70, 20, 10], "max_neon_hues_per_shot": 1},
}


def scored(names, twos):
    """The first `twos` criteria score 2, the rest 1."""
    return {n: {"score": 2 if i < twos else 1, "reason": ""} for i, n in enumerate(names)}


def answer(names, scores=None, default=2):
    scores = scores or {}
    return json.dumps({n: {"score": scores.get(n, default), "reason": "ok"} for n in names})


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("network call in a test")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(write_pack, "call_claude", boom)


@pytest.fixture
def clip(monkeypatch, tmp_path):
    sheet = tmp_path / "SHOT-07_first_mid_last.png"
    sheet.write_bytes(b"\x89PNG fake")
    monkeypatch.setattr(clip_tools, "qa", lambda clip_path, out: {"sheet": str(sheet)})
    direction = tmp_path / "SHOT-07.direction.json"
    direction.write_text(json.dumps(DIRECTION), encoding="utf-8")
    bible = tmp_path / "bible.json"
    bible.write_text(BIBLE_TEXT, encoding="utf-8")
    return {"clip": tmp_path / "SHOT-07.mp4", "direction": direction, "bible": bible, "sheet": sheet, "out": tmp_path / "qa"}


def test_colour_rubric_adds_exactly_two_criteria_and_the_new_constants():
    assert set(visual_qa.RUBRIC_COLOUR) == {"colour_script_match", "focal_reads"}
    assert set(visual_qa.RUBRIC_FULL) == set(visual_qa.RUBRIC) | {"colour_script_match", "focal_reads"}
    assert len(visual_qa.RUBRIC_FULL) == 11 and 2 * len(visual_qa.RUBRIC_FULL) == 22
    assert visual_qa.ACCEPT_TOTAL_COLOUR == 17
    assert visual_qa.ACCEPT_TOTAL == 14 and len(visual_qa.RUBRIC) == 9      # A16: the old rubric is untouched
    assert all(text.strip() for text in visual_qa.RUBRIC_COLOUR.values())


def test_nine_score_record_accepts_at_fourteen_of_eighteen():
    verdict = visual_qa.judge_any(scored(NAMES9, 5))                       # 5 x 2 + 4 x 1 = 14
    assert verdict == {"total": 14, "max": 18, "zeros": [], "accept": True, "threshold": 14}
    assert not visual_qa.judge_any(scored(NAMES9, 4))["accept"]            # 13 refused


def test_eleven_score_record_accepts_at_seventeen_of_twenty_two():
    verdict = visual_qa.judge_any(scored(NAMES11, 6))                      # 6 x 2 + 5 x 1 = 17
    assert verdict == {"total": 17, "max": 22, "zeros": [], "accept": True, "threshold": 17}


def test_eleven_score_record_refuses_at_sixteen_of_twenty_two():
    verdict = visual_qa.judge_any(scored(NAMES11, 5))                      # 5 x 2 + 6 x 1 = 16
    assert verdict["total"] == 16 and verdict["accept"] is False and verdict["threshold"] == 17


def test_a_zero_on_focal_reads_refuses_even_with_a_high_total():
    record = scored(NAMES11, 11)
    record["focal_reads"] = {"score": 0, "reason": "the focal figure vanishes in the thumbnail"}
    verdict = visual_qa.judge_any(record)
    assert verdict["total"] == 20 and verdict["accept"] is False and verdict["zeros"] == ["focal_reads"]


def test_a_zero_on_colour_script_match_refuses_too():
    record = scored(NAMES11, 11)
    record["colour_script_match"] = {"score": 0, "reason": "wrong phase"}
    assert visual_qa.judge_any(record)["zeros"] == ["colour_script_match"]


def test_mixed_or_unknown_key_sets_raise_value_error():
    ten = scored(NAMES9, 9) | {"colour_script_match": {"score": 2, "reason": ""}}     # 10 keys
    renamed = scored(NAMES9, 9)
    renamed["focal_read"] = renamed.pop("continuity")                                 # 9 keys, one unknown
    eleven_with_unknown = scored(NAMES11, 11)
    eleven_with_unknown["extra"] = eleven_with_unknown.pop("continuity")              # 11 keys, one unknown
    twelve = scored(NAMES11, 11) | {"extra": {"score": 2, "reason": ""}}
    for bad in (ten, renamed, eleven_with_unknown, twelve, {}):
        with pytest.raises(ValueError):
            visual_qa.judge_any(bad)


def test_judge_any_refuses_a_missing_or_non_integer_score():
    blank = scored(NAMES9, 9)
    blank["continuity"] = {"score": None, "reason": ""}                               # a blank manual score
    with pytest.raises(ValueError):
        visual_qa.judge_any(blank)


def test_prompt_without_pack_is_the_same_as_the_default_call():
    default = visual_qa.build_review_prompt(DIRECTION, BIBLE_TEXT)
    assert default == visual_qa.build_review_prompt(DIRECTION, BIBLE_TEXT, visual_qa.RUBRIC, None)
    assert "STYLE PACK" not in default and "colour_script_match" not in default


def test_prompt_with_pack_adds_guardrails_area_split_neon_rule_and_panels():
    prompt = visual_qa.build_review_prompt(DIRECTION, BIBLE_TEXT, visual_qa.RUBRIC_FULL, PACK)
    assert "## STYLE PACK (what pixels cannot measure)" in prompt
    assert "GUARD-ONE: no neon on faces" in prompt and "GUARD-TWO: saffron stays" in prompt
    assert "environment 70%" in prompt and "character 20%" in prompt and "ignition 10%" in prompt
    assert "At most 1 neon hue per shot" in prompt                                 # the one-neon rule
    assert "270 px" in prompt and "deuteranopia" in prompt
    assert "a score of 0 on colour_script_match or focal_reads is a FAIL" in prompt
    assert '"colour_script_match"' in prompt and '"focal_reads"' in prompt        # the 11 criteria are named
    assert prompt.index("## STYLE PACK") > prompt.index("Return only one JSON object")  # appended, not inserted


def test_prompt_with_pack_omits_the_area_split_when_the_pack_has_none():
    bare = {"guardrails": [], "frame_law": {"max_neon_hues_per_shot": 1}}
    prompt = visual_qa.build_review_prompt(DIRECTION, BIBLE_TEXT, visual_qa.RUBRIC_FULL, bare)
    assert "environment" not in prompt and "STYLE PACK" in prompt


def test_parse_scores_reads_an_eleven_key_answer_with_the_full_rubric():
    scores = visual_qa.parse_scores("```json\n" + answer(NAMES11, {"focal_reads": 1}) + "\n```", visual_qa.RUBRIC_FULL)
    assert len(scores) == 11 and scores["focal_reads"]["score"] == 1 and scores["colour_script_match"]["score"] == 2
    with pytest.raises(ValueError):
        visual_qa.parse_scores(answer(NAMES9), visual_qa.RUBRIC_FULL)           # 9 keys is not enough for the full rubric


def test_manual_mode_with_a_pack_writes_eleven_blank_scores(clip):
    visual_qa.review(clip["clip"], clip["direction"], clip["out"], "manual", None, clip["bible"], PACK)
    saved = json.loads((clip["out"] / "SHOT-07_visual_qa.json").read_text(encoding="utf-8"))
    assert set(saved["scores"]) == set(NAMES11) and len(saved["scores"]) == 11
    assert all(saved["scores"][n] == {"score": None, "reason": ""} for n in NAMES11)
    assert "STYLE PACK" in (clip["out"] / "SHOT-07_visual_qa_prompt.txt").read_text(encoding="utf-8")


def test_manual_mode_without_a_pack_still_writes_nine_blank_scores(clip):
    visual_qa.review(clip["clip"], clip["direction"], clip["out"], "manual", None, clip["bible"])
    saved = json.loads((clip["out"] / "SHOT-07_visual_qa.json").read_text(encoding="utf-8"))
    assert set(saved["scores"]) == set(NAMES9)


def test_model_path_with_a_pack_judges_eleven_criteria_at_seventeen(clip, monkeypatch):
    sent = {}

    def fake_nvidia(prompt, model, content=None):
        sent["prompt"] = prompt
        return write_pack.envelope(answer(NAMES11, {n: 1 for n in NAMES11[:6]}), "stop", "nvidia", model)  # six 1s, five 2s
    monkeypatch.setattr(write_pack, "call_nvidia", fake_nvidia)
    record = visual_qa.review(clip["clip"], clip["direction"], clip["out"], "nvidia", "vision-model", clip["bible"], PACK)
    assert "STYLE PACK" in sent["prompt"]
    assert record["max"] == 22 and record["threshold"] == 17
    assert record["total"] == 16 and record["accept"] is False                  # 6 criteria at 1, 5 at 2 = 16


def test_model_path_without_a_pack_keeps_the_nine_criterion_verdict(clip, monkeypatch):
    monkeypatch.setattr(write_pack, "call_nvidia", lambda prompt, model, content=None:
                        write_pack.envelope(answer(NAMES9), "stop", "nvidia", model))
    record = visual_qa.review(clip["clip"], clip["direction"], clip["out"], "nvidia", "vision-model", clip["bible"])
    assert record["accept"] and record["total"] == 18 and record["max"] == 18 and set(record["scores"]) == set(NAMES9)


def test_load_style_pack_reads_plain_json_and_names_a_missing_pack(tmp_path):
    (tmp_path / "demo.json").write_text(json.dumps(PACK), encoding="utf-8")
    assert visual_qa.load_style_pack("demo", tmp_path) == PACK
    with pytest.raises(ValueError, match="style pack"):
        visual_qa.load_style_pack("no_such_pack", tmp_path)


def test_the_cli_refuses_a_missing_style_pack_before_any_call(clip, capsys):
    with pytest.raises(ValueError, match="style pack"):
        visual_qa.main([str(clip["clip"]), str(clip["direction"]), str(clip["out"]), "--via", "manual",
                        "--style-pack", "no_such_pack_xyz"])
