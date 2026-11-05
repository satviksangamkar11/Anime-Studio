"""Write -> settings -> Kaggle script, without any model or network call."""
import ast
import base64
import json

import pytest
from PIL import Image

import run_kaggle
import write_pack

SHOT = {"id": "SHOT-01", "episode": 1, "mode": "fl2va", "seconds": 4, "aspect": "9:16", "start": "keyframes/SHOT-01-FRAME-A.png",
        "end": "keyframes/SHOT-01-FRAME-B.png", "refs": [], "subjects": [], "style": "Flat 2D cel anime.", "world": "River at dawn.",
        "action": "0-2s a bird falls.", "camera": "tilt down", "sound": "boiling water hiss"}


def envelope(text, is_error=False):
    return json.dumps({"type": "result", "is_error": is_error, "result": text})


def test_parse_takes_the_one_shot_block():
    text = "# Gate 1\n...\n```json shots\n" + json.dumps([SHOT]) + "\n```\n"
    pack, shots = write_pack.parse(envelope(text))
    assert pack == text and shots[0]["id"] == "SHOT-01"


@pytest.mark.parametrize("text", ["no block", "```json shots\n[]\n```\n```json shots\n[]\n```"])
def test_parse_refuses_zero_or_two_blocks(text):
    with pytest.raises(ValueError):
        write_pack.parse(envelope(text))


def test_parse_refuses_a_shot_h3_cannot_run_and_cli_errors():
    with pytest.raises(ValueError):
        write_pack.parse(envelope("```json shots\n" + json.dumps([dict(SHOT, seconds=20)]) + "\n```"))
    with pytest.raises(ValueError):
        write_pack.parse(envelope("x", is_error=True))


def test_the_prompt_is_the_brief_plus_the_story():
    p = write_pack.build_prompt("Kaliya story")
    assert p.startswith("# OPUS MASTER PROMPT v2.1") and p.endswith("Kaliya story\n")


def test_build_embeds_images_and_rewrites_paths(tmp_path):
    (tmp_path / "keyframes").mkdir()
    for name in ("SHOT-01-FRAME-A.png", "SHOT-01-FRAME-B.png"):
        Image.new("RGB", (64, 96), "red").save(tmp_path / "keyframes" / name)
    script, meta = run_kaggle.build([SHOT], tmp_path, "ep1_test")
    ast.parse(script)
    assert "__" + "IMAGES__" not in script and "__" + "SETTINGS__" not in script
    blob = script.split('json.loads(base64.b64decode("')[2].split('")')[0]
    settings = json.loads(base64.b64decode(blob))["SHOT-01"]
    assert settings["image_start"] == "/kaggle/working/Wan2GP/inputs/keyframes__SHOT-01-FRAME-A.png" and settings["video_length"] == 107
    assert meta["machine_shape"] == "NvidiaTeslaT4" and meta["is_private"] == "true" and meta["id"].endswith("/anime-ep1-test")


def test_same_named_files_from_two_folders_stay_apart(tmp_path):
    for folder, colour in (("a", "red"), ("b", "blue")):
        (tmp_path / folder).mkdir()
        Image.new("RGB", (8, 8), colour).save(tmp_path / folder / "F.png")
    shots = [dict(SHOT, id="SHOT-01", start="a/F.png", end=None), dict(SHOT, id="SHOT-02", start="b/F.png", end=None)]
    script, _ = run_kaggle.build(shots, tmp_path, "t")
    images = json.loads(base64.b64decode(script.split('json.loads(base64.b64decode("')[1].split('")')[0]))
    assert sorted(images) == ["a__F.png", "b__F.png"] and images["a__F.png"] != images["b__F.png"]


def test_parse_accepts_a_fence_on_the_json_line_and_refuses_a_bare_object():
    _, shots = write_pack.parse(envelope("```json shots\n" + json.dumps([SHOT]) + "```"))
    assert shots[0]["id"] == "SHOT-01"
    with pytest.raises(ValueError):
        write_pack.parse(envelope("```json shots\n" + json.dumps(SHOT) + "\n```"))


def test_openrouter_refuses_a_paid_model_before_any_key_is_read(monkeypatch):
    catalog = [{"id": "x/free:free", "pricing": {"prompt": "0", "completion": "0"}},
               {"id": "x/paid", "pricing": {"prompt": "0.000001", "completion": "0"}}]
    assert write_pack.openrouter_is_free("x/free:free", catalog) and not write_pack.openrouter_is_free("x/paid", catalog)
    monkeypatch.setattr(write_pack, "openrouter_is_free", lambda model: False)
    monkeypatch.setattr(write_pack, "OPENROUTER_KEY", write_pack.WORK / "no_such_key_file.txt")
    with pytest.raises(ValueError, match="paid"):
        write_pack.call_openrouter("p", "x/paid")


def test_every_path_returns_the_shape_parse_reads():
    text = "```json shots\n" + json.dumps([SHOT]) + "\n```"
    assert write_pack.parse(write_pack.envelope(text, "stop", "nvidia", "m"))[1][0]["id"] == "SHOT-01"
    with pytest.raises(ValueError, match="cut off"):
        write_pack.parse(write_pack.envelope(text, "length", "openrouter", "m"))


def test_parse_accepts_one_json_value_per_line():
    lines = "\n".join(json.dumps([dict(SHOT, id=f"SHOT-0{n}")]) for n in (1, 2)) + "\n" + json.dumps(dict(SHOT, id="SHOT-03"))
    _, shots = write_pack.parse(envelope("```json shots\n" + lines + "\n```"))
    assert [s["id"] for s in shots] == ["SHOT-01", "SHOT-02", "SHOT-03"]


def test_the_brief_example_parses():
    brief = write_pack.BRIEF.read_text(encoding="utf-8")
    example = write_pack.SHOTS_BLOCK.search(brief).group(1)
    assert json.loads(example)[0]["id"] == "SHOT-01"
