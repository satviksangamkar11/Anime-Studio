"""visual_qa with fakes: no network, no model call, no ffmpeg."""
import json
import urllib.request

import pytest

import clip_tools
import visual_qa
import write_pack

NAMES = list(visual_qa.RUBRIC)
DIRECTION = {"id": "SHOT-07", "purpose": "Krishna dives into the Yamuna"}
BIBLE_TEXT = '{"palette": {"sky": "PALETTE-SENTINEL"}}'


def answer(scores=None, default=2):
    scores = scores or {}
    return json.dumps({n: {"score": scores.get(n, default), "reason": "ok"} for n in NAMES})


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


def test_rubric_has_nine_criteria_scored_zero_to_two_and_accept_at_fourteen():
    assert len(visual_qa.RUBRIC) == 9 and 2 * len(visual_qa.RUBRIC) == 18 and visual_qa.ACCEPT_TOTAL == 14


def test_prompt_names_every_criterion_the_direction_and_the_bible():
    prompt = visual_qa.build_review_prompt(DIRECTION, BIBLE_TEXT)
    assert all(f'"{n}"' in prompt and f"- {n}:" in prompt for n in NAMES)
    assert "SHOT-07" in prompt and "PALETTE-SENTINEL" in prompt
    assert "first frame" in prompt and "Return only one JSON object" in prompt
    assert "(none given)" in visual_qa.build_review_prompt(DIRECTION, "")


def test_parse_scores_accepts_fenced_json_and_refuses_bad_ones():
    scores = visual_qa.parse_scores("here you go\n```json\n" + answer({"proportions": 1}) + "\n```")
    assert scores["proportions"] == {"score": 1, "reason": "ok"} and len(scores) == 9
    assert visual_qa.parse_scores(answer({"continuity": "2"}))["continuity"]["score"] == 2
    with pytest.raises(ValueError):
        visual_qa.parse_scores(answer({"continuity": 3}))
    with pytest.raises(ValueError):
        visual_qa.parse_scores(answer({"continuity": True}))
    with pytest.raises(ValueError):
        visual_qa.parse_scores(json.dumps({n: {"score": 2} for n in NAMES[:-1]}))   # one criterion missing
    with pytest.raises(ValueError):
        visual_qa.parse_scores("no json at all")


def test_accept_needs_no_zero_and_a_total_of_at_least_fourteen():
    def scored(twos):
        return {n: {"score": 2 if i < twos else 1, "reason": ""} for i, n in enumerate(NAMES)}
    assert visual_qa.judge(scored(9)) == {"total": 18, "max": 18, "zeros": [], "accept": True}
    assert visual_qa.judge(scored(5))["total"] == 14 and visual_qa.judge(scored(5))["accept"]        # 5x2 + 4x1 = 14
    assert not visual_qa.judge(scored(4))["accept"]                                                 # 4x2 + 5x1 = 13
    zero = scored(9)
    zero["light_motivated"] = {"score": 0, "reason": "glow hides the acting"}
    verdict = visual_qa.judge(zero)
    assert verdict["total"] == 16 and not verdict["accept"] and verdict["zeros"] == ["light_motivated"]


def test_manual_mode_writes_the_prompt_with_the_sheet_and_a_blank_score_file(clip):
    record = visual_qa.review(clip["clip"], clip["direction"], clip["out"], "manual", None, clip["bible"])
    prompt_file = clip["out"] / "SHOT-07_visual_qa_prompt.txt"
    assert str(clip["sheet"]) in prompt_file.read_text(encoding="utf-8") and "PALETTE-SENTINEL" in prompt_file.read_text(encoding="utf-8")
    saved = json.loads((clip["out"] / "SHOT-07_visual_qa.json").read_text(encoding="utf-8"))
    assert saved == record and "accept" not in saved and saved["status"] == "awaiting manual scores"
    assert all(saved["scores"][n] == {"score": None, "reason": ""} for n in NAMES)


def test_nvidia_path_sends_the_sheet_as_an_image_and_judges_the_scores(clip, monkeypatch):
    sent = {}

    def fake_nvidia(prompt, model, content=None):
        sent.update(prompt=prompt, model=model, content=content)
        return write_pack.envelope(answer(), "stop", "nvidia", model)
    monkeypatch.setattr(write_pack, "call_nvidia", fake_nvidia)
    record = visual_qa.review(clip["clip"], clip["direction"], clip["out"], "nvidia", "vision-model", clip["bible"])
    assert sent["model"] == "vision-model" and sent["content"][0] == {"type": "text", "text": sent["prompt"]}
    assert sent["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert record["accept"] and record["total"] == 18 and record["via"] == "nvidia"
    assert json.loads((clip["out"] / "SHOT-07_visual_qa.json").read_text(encoding="utf-8"))["accept"]


def test_openrouter_path_checks_the_vision_model_then_refuses_a_failing_clip(clip, monkeypatch):
    checked = []
    monkeypatch.setattr(visual_qa, "check_openrouter_vision", lambda model, catalog=None: checked.append(model))

    def fake_openrouter(prompt, model, allow_paid=False, content=None):
        assert allow_paid is False and content[1]["type"] == "image_url"
        return write_pack.envelope(answer({"indian_identity": 0}), "stop", "openrouter", model)
    monkeypatch.setattr(write_pack, "call_openrouter", fake_openrouter)
    record = visual_qa.review(clip["clip"], clip["direction"], clip["out"], "openrouter", "free/vision:free")
    assert checked == ["free/vision:free"]
    assert not record["accept"] and record["zeros"] == ["indian_identity"]


def test_openrouter_vision_check_refuses_text_only_and_paid_models():
    catalog = [
        {"id": "free/vision:free", "architecture": {"input_modalities": ["text", "image"]}, "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "free/text:free", "architecture": {"input_modalities": ["text"]}, "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "paid/vision", "architecture": {"input_modalities": ["text", "image"]}, "pricing": {"prompt": "0.000001", "completion": "0"}},
    ]
    visual_qa.check_openrouter_vision("free/vision:free", catalog)              # no raise
    with pytest.raises(ValueError, match="image"):
        visual_qa.check_openrouter_vision("free/text:free", catalog)
    with pytest.raises(ValueError, match="paid"):
        visual_qa.check_openrouter_vision("paid/vision", catalog)


def test_the_claude_cli_path_is_refused_with_a_clear_error(clip):
    with pytest.raises(ValueError, match="images"):
        visual_qa.review(clip["clip"], clip["direction"], clip["out"], "claude", "opus")


def test_the_cli_has_no_claude_choice(capsys):
    """G11: argparse refuses --via claude before any call is made."""
    with pytest.raises(SystemExit) as e:
        visual_qa.main(["clip.mp4", "direction.json", "out", "--via", "claude", "--model", "x"])
    assert e.value.code == 2 and "invalid choice" in capsys.readouterr().err


def test_a_model_path_needs_a_model(clip):
    with pytest.raises(ValueError, match="--model"):
        visual_qa.review(clip["clip"], clip["direction"], clip["out"], "nvidia", None)
