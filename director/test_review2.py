"""Second review (plan v4.3, phase 1B): duplicate ids, beats vs render length, Ref2VA subject format, identity text with props and
project rules, require_bible, Pika adapter rules, finite seconds, per-shot results on Kaggle, edit frames, T0 variants."""
import ast
import base64
import json
import math

import pytest
from PIL import Image

import dry_run
import run_kaggle
import shot_schema
import t0_variants
from check_pack import check as check_pack
from h3_director import check_combo, frames_for, settings_for
from test_shot_schema import RICH

BASE = {"id": "SHOT-04", "episode": 1, "mode": "fl2va", "seconds": 5, "aspect": "9:16", "start": "a.png",
        "style": "Flat 2D cel anime.", "world": "Riverbank at dawn.", "action": "0-2s he steps forward.", "camera": "slow crane down"}
REF_SHAPE = dict(BASE, mode="ref2va", start=None, refs=["k.png"], subjects=["<Subject 1> is Bala Krishna in <Picture 1>."])
FL_LORA = "https://huggingface.co/DeepBeepMeep/MiniMax-H3/resolve/main/loras/pika_h3_flex_fl2va_6step_v1_bf16.safetensors"
REF_LORA = FL_LORA.replace("fl2va", "ref2va")
BIBLE = {
    "palette": {"rule": "Braj daylight earth tones first."},
    "line": {"rule": "variable weight: thicker on the silhouette"},
    "shading": {"rule": "no gradient airbrush on figures"},
    "characters": [{"id": "CHAR-KRISHNA", "name": "Bala Krishna", "skin": {"treatment": "warm brown; cel shade"},
                    "costume": [{"piece": "yellow dhoti", "colour_hex": "#E8B400"}], "hair": {"base_colour": "black"},
                    "silhouette_markers": ["topknot"], "proportions_heads": 6, "forbidden_drift": ["adult proportions"]}],
    "environments": [{"id": "ENV-KADAMBA-BANK", "name": "Kadamba bank", "geography": "river bend", "day_key": "morning",
                      "composition": {"fg": "leaves", "mid": "bank", "bg": "river"}}],
    "props": [{"id": "PROP-KALI-KAMLI", "name": "Kali Kamli", "description": "black wool sash", "colour_hex": "#1C1A1E",
               "forbidden_drift": "a modern belt"}],
}


def tiny_png(path, colour="red"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 64), colour).save(path)


def blobs(script):
    out = []
    for node in ast.walk(ast.parse(script)):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "b64decode" and node.args and isinstance(node.args[0], ast.Constant):
            if not node.args[0].value.startswith("__"):
                out.append(json.loads(base64.b64decode(node.args[0].value)))
    return out


# 1. duplicate ids
def test_duplicate_shot_ids_are_refused_by_build_and_dry_run(tmp_path):
    tiny_png(tmp_path / "a.png")
    with pytest.raises(ValueError, match="duplicate"):
        run_kaggle.build([BASE, dict(BASE)], tmp_path, "t", bible=BIBLE)
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([BASE, dict(BASE, seconds=4)]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        dry_run.main(str(shots), str(tmp_path), str(tmp_path / "out"), "kaliya_mardan", require_bible=True)
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").glob("settings_*.json"))


# 2. beats fit render_frames
def test_beats_must_fit_render_frames_not_seconds():
    assert any("beats end at 5.2" in p for p in shot_schema.validate_shot(dict(RICH, render_frames=107)))
    assert not any("beats" in p for p in shot_schema.validate_shot(dict(RICH, render_frames=124)))


# 3. Ref2VA subjects
@pytest.mark.parametrize("subject", ["<Subject 1> is x in <Picture 0>.", "<Subject 1> is x in <Picture 2>.",
                                     "Bala Krishna in <Picture 1>.", "<Subject 1> is x"])
def test_malformed_or_out_of_range_subjects_are_rejected(subject):
    with pytest.raises(ValueError):
        settings_for(dict(REF_SHAPE, subjects=[subject]))
    assert any("subject" in p for p in shot_schema.validate_shot(dict(RICH, mode="ref2va", refs=["k.png"], subjects=[subject])))


def test_a_well_formed_subject_is_renumbered_after_the_keyframes():
    p = settings_for(dict(REF_SHAPE, start="a.png", end="b.png", seconds=5.2))["prompt"]
    assert "<Subject 1> is Bala Krishna in <Picture 3>." in p


# 4. identity text: props, project rules
def test_identity_text_includes_props_and_project_rules():
    shot = dict(BASE, cast=[{"id": "CHAR-KRISHNA"}], set="ENV-KADAMBA-BANK", props=[{"id": "PROP-KALI-KAMLI"}])
    p = settings_for(shot, BIBLE)["prompt"]
    assert "Kali Kamli" in p and "Bala Krishna. 6 heads." in p and "Kadamba bank" in p
    assert "Braj daylight earth tones first." in p and "variable weight" in p and "no gradient airbrush" in p


# 4b. require_bible
def test_require_bible_fails_without_a_bible(tmp_path):
    with pytest.raises(ValueError, match="style bible"):
        settings_for(BASE, None, require_bible=True)
    with pytest.raises(ValueError, match="style bible"):
        run_kaggle.build([BASE], tmp_path, "t", None, require_bible=True)
    with pytest.raises(SystemExit):
        run_kaggle.main(["shots.json", str(tmp_path), "batch"])   # --style is mandatory on the command line


# 5. Pika adapter rules
def test_pika_adapter_must_match_the_model_family():
    ok = settings_for(BASE)
    check_combo(ok)
    with pytest.raises(ValueError):
        check_combo(dict(ok, activated_loras=[REF_LORA]))                 # FL2VA model with the Ref2VA adapter
    ref = settings_for(REF_SHAPE)
    check_combo(ref)
    with pytest.raises(ValueError):
        check_combo(dict(ref, activated_loras=[FL_LORA]))                 # Ref2VA model with the FL2VA adapter
    with pytest.raises(ValueError):
        check_combo(dict(ok, activated_loras=[]))                         # Pika sampler without its adapter
    with pytest.raises(ValueError):
        check_combo(dict(ok, skip_steps_cache_type="teacache"))           # Steps Skipping must stay empty
    check_combo(dict(ok, sample_solver="euler", activated_loras=[]))      # no Pika at all: no Pika rule


# 6. finite positive seconds
@pytest.mark.parametrize("bad", [-1, 0, True, float("nan"), float("inf")])
def test_seconds_must_be_finite_and_positive_without_render_frames(bad):
    with pytest.raises(ValueError):
        frames_for(bad)
    with pytest.raises(ValueError):
        settings_for(dict(BASE, seconds=bad))
    assert any("seconds" in p for p in shot_schema.validate_shot(dict(RICH, seconds=bad)))


def test_render_frames_makes_seconds_irrelevant():
    assert settings_for(dict(BASE, seconds=-1, render_frames=107))["video_length"] == 107


# 7. per-shot results from the Kaggle runner
def test_runner_writes_result_json_and_fails_loudly(tmp_path):
    src = run_kaggle.RUNNER
    assert "finish(results)" in src and 'endswith(".mp4")' in src
    start = src.index("def finish(results):")
    end = src.index('note("ALL DONE")') + len('note("ALL DONE")')
    logs = []
    ns = {"json": json, "OUT": tmp_path, "note": logs.append}
    exec(src[start:end], ns)
    with pytest.raises(SystemExit):
        ns["finish"]({"SHOT-01": "ok", "SHOT-02": "failed"})
    assert json.loads((tmp_path / "RESULT.json").read_text(encoding="utf-8")) == {"SHOT-01": "ok", "SHOT-02": "failed"}
    assert any("FAILED: SHOT-02" in m for m in logs) and not any("ALL DONE" in m for m in logs)
    logs.clear()
    ns["finish"]({"SHOT-01": "ok"})
    assert logs == ["ALL DONE"]


# 8. edit frames
def test_dry_run_writes_edit_json_and_check_pack_counts_edit_frames(tmp_path):
    tiny_png(tmp_path / "root" / "a.png")
    shot = dict(BASE, render_frames=124, edit_frames=96)
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([shot]), encoding="utf-8")
    dry_run.main(str(shots), str(tmp_path / "root"), str(tmp_path / "out"))
    edit = json.loads((tmp_path / "out" / "SHOT-04.edit.json").read_text(encoding="utf-8"))
    assert edit["render_frames"] == 124 and edit["edit_frames"] == 96 and edit["direction"] == shot
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "shots.json").write_text(json.dumps([shot, dict(BASE, id="SHOT-05", seconds=5.2)]), encoding="utf-8")
    (pack / "PACK.md").write_text("# pack\n", encoding="utf-8")
    assert check_pack(pack)["episode_seconds"] == {1: 9.2}   # 96/24 = 4.0 plus 124/24 = 5.2 (renders without edit_frames count fully)


# 9. T0 variants
T0_BASE = {"episode": 1, "scene": "kadamba_leap", "aspect": "9:16", "seconds": 5.2, "render_frames": 124,
           "start": "keyframes/T0-START.png", "end": "keyframes/T0-END.png", "refs": ["refs/krishna.png"],
           "subjects": ["<Subject 1> is Bala Krishna in <Picture 1>."], "style": "Flat 2D cel anime.", "world": "River at dawn.",
           "action": "0-2s he crouches; 2-5s he leaps.", "camera": "slow crane", "sound": "river hush",
           "cast": [{"id": "CHAR-KRISHNA"}], "set": "ENV-KADAMBA-BANK", "props": [{"id": "PROP-KALI-KAMLI"}]}


def test_t0_expands_one_shot_into_four_valid_variants():
    v = t0_variants.expand(T0_BASE, BIBLE)
    assert [s["id"] for s in v] == ["SHOT-T0-FL-S42", "SHOT-T0-FL-S123", "SHOT-T0-REF-S42", "SHOT-T0-REF-S123"]
    assert [s["mode"] for s in v] == ["fl2va", "fl2va", "ref2va", "ref2va"]
    assert [s["seed"] for s in v] == [42, 123, 42, 123]
    assert all(s.get("refs") == (["refs/krishna.png"] if s["mode"] == "ref2va" else None) for s in v)
    assert len({json.dumps([s["action"], s["start"], s["end"], s["render_frames"], s["camera"], s["sound"], s["cast"], s["props"]])
                for s in v}) == 1
    assert all(settings_for(s, BIBLE)["video_length"] == 124 for s in v)
    assert all(not any("SHOT-T0" in p or "id" in p for p in shot_schema.validate_shot(dict(RICH, id=s["id"]))) for s in v)


def test_t0_variants_build_end_to_end_through_the_kaggle_script(tmp_path):
    tiny_png(tmp_path / "keyframes" / "T0-START.png")
    tiny_png(tmp_path / "keyframes" / "T0-END.png", "green")
    tiny_png(tmp_path / "refs" / "krishna.png", "yellow")
    script, meta = run_kaggle.build(t0_variants.expand(T0_BASE, BIBLE), tmp_path, "t0", bible=BIBLE, require_bible=True)
    ast.parse(script)
    decoded = blobs(script)
    images = next(b for b in decoded if "SHOT-T0-FL-S42" not in b)
    settings = next(b for b in decoded if "SHOT-T0-FL-S42" in b)
    assert set(settings) == {"SHOT-T0-FL-S42", "SHOT-T0-FL-S123", "SHOT-T0-REF-S42", "SHOT-T0-REF-S123"}
    assert {s["video_length"] for s in settings.values()} == {124} and {s["resolution"] for s in settings.values()} == {"480x832"}
    assert settings["SHOT-T0-REF-S123"]["seed"] == 123 and settings["SHOT-T0-FL-S42"]["seed"] == 42
    for s in settings.values():
        for key in ("image_start", "image_end"):
            assert s[key].endswith(".png") and s[key].rsplit("/", 1)[1] in images
    assert "<Subject 1> is Bala Krishna in <Picture 3>." in settings["SHOT-T0-REF-S42"]["prompt"]
    assert "Kali Kamli" in settings["SHOT-T0-FL-S42"]["prompt"] and "Kadamba bank" in settings["SHOT-T0-FL-S42"]["prompt"]
    assert meta["id"].endswith("/anime-t0")
