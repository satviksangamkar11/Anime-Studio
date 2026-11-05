"""Fourth review (plan v4.3, phase 1B): our own LoRA names only, all-or-nothing dry run, T0 base checks and no overwrite, shape checks
in validate_shot, Ref2VA subject order and one picture per subject, id syntax at the batch boundary."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

import dry_run
import run_kaggle
import shot_schema
import t0_variants
from h3_director import LORA_URL, check_combo, check_unique_ids, settings_for
from test_review2 import BASE, BIBLE, REF_SHAPE, T0_BASE, tiny_png
from test_shot_schema import RICH

DIRECTOR = Path(__file__).resolve().parent
OTHER = LORA_URL + "some_other_adapter.safetensors"


def test_an_adapter_name_we_do_not_build_is_refused():
    ok = settings_for(BASE)
    with pytest.raises(ValueError):
        check_combo(dict(ok, activated_loras=[LORA_URL + "pika_h3_flex_fl2va_6step_v2.safetensors"]))
    with pytest.raises(ValueError):
        check_combo(dict(ok, sample_solver="euler", activated_loras=[OTHER]))


def test_dry_run_is_all_or_nothing(tmp_path):
    tiny_png(tmp_path / "root" / "a.png")
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([BASE, dict(BASE, id="SHOT-05", mode="nonsense")]), encoding="utf-8")
    with pytest.raises(ValueError):
        dry_run.main(str(shots), str(tmp_path / "root"), str(tmp_path / "out"), "kaliya_mardan", require_bible=True)
    assert not (tmp_path / "out").exists()


def test_dry_run_loads_the_bible_before_writing(tmp_path):
    tiny_png(tmp_path / "root" / "a.png")
    shots = tmp_path / "shots.json"
    shots.write_text(json.dumps([BASE]), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        dry_run.main(str(shots), str(tmp_path / "root"), str(tmp_path / "out"), "no_such_style", require_bible=True)
    assert not (tmp_path / "out").exists()


def test_t0_base_must_have_both_keyframes_and_one_identity_ref():
    with pytest.raises(ValueError):
        t0_variants.expand(dict(T0_BASE, end=None), BIBLE)
    with pytest.raises(ValueError):
        t0_variants.expand(dict(T0_BASE, refs=["refs/a.png", "refs/b.png"], subjects=[
            "<Subject 1> is Bala Krishna in <Picture 1>.", "<Subject 2> is Bala Krishna in <Picture 2>."]), BIBLE)


def test_t0_variants_force_the_pika_baseline():
    variants = t0_variants.expand(dict(T0_BASE, sampler="euler"), BIBLE)
    assert all("sampler" not in v for v in variants)
    assert all(s["sample_solver"] == "pika_renoise" for s in (settings_for(v, BIBLE) for v in variants))
    assert all(v["refs"] == ["refs/krishna.png"] for v in variants if v["mode"] == "ref2va")
    assert all("refs" not in v and "subjects" not in v for v in variants if v["mode"] == "fl2va")


def test_t0_main_refuses_to_overwrite_and_refuses_out_equal_to_in(tmp_path):
    base = tmp_path / "base.json"
    base.write_text(json.dumps(T0_BASE), encoding="utf-8")
    out = tmp_path / "t0.json"
    t0_variants.main(str(base), str(out), "kaliya_mardan")
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 4
    with pytest.raises(ValueError, match="exists"):
        t0_variants.main(str(base), str(out), "kaliya_mardan")
    with pytest.raises(ValueError, match="different"):
        t0_variants.main(str(base), str(base), "kaliya_mardan")


def test_validate_shot_reports_shape_errors_instead_of_raising():
    assert shot_schema.validate_shot("SHOT-07") and "object" in shot_schema.validate_shot("SHOT-07")[0]
    assert any("cast" in p for p in shot_schema.validate_shot(dict(RICH, cast=["CHAR-KRISHNA"])))
    assert any("props" in p for p in shot_schema.validate_shot(dict(RICH, props=[{"id": 3}])))


def test_subjects_are_numbered_in_order_once_each():
    two = ["<Subject 1> is Bala Krishna in <Picture 1>.", "<Subject 2> is Balarama in <Picture 2>."]
    assert settings_for(dict(REF_SHAPE, refs=["a.png", "b.png"], subjects=two))["image_refs"] == ["a.png", "b.png"]
    with pytest.raises(ValueError, match="in order"):
        settings_for(dict(REF_SHAPE, refs=["a.png", "b.png"], subjects=[two[1], two[0]]))
    with pytest.raises(ValueError, match="in order"):
        settings_for(dict(REF_SHAPE, refs=["a.png", "b.png"], subjects=[two[0], two[0]]))
    with pytest.raises(ValueError):
        settings_for(dict(REF_SHAPE, refs=["a.png", "b.png"], subjects=["<Subject 1> is x with <Picture 2> in <Picture 1>."]))


def test_check_unique_ids_checks_every_id_syntax():
    with pytest.raises(ValueError, match="shot id"):
        check_unique_ids([{"id": "SHOT-04"}, {"id": "bad id"}])


def test_build_validates_all_ids_before_selecting(tmp_path):
    tiny_png(tmp_path / "a.png")
    with pytest.raises(ValueError, match="shot id"):
        run_kaggle.build([BASE, {"id": "bad id"}], tmp_path, "t", ids={"SHOT-04"}, bible=BIBLE)


def test_the_kaggle_docstring_says_jpeg_sources_are_re_encoded_losslessly():
    doc = run_kaggle.__doc__
    assert ".jpg" in doc and "re-encoded" in doc and "PNG" in doc


def test_the_subject_number_is_not_the_picture_number():
    from h3_director import subject_problems
    assert subject_problems(["a.png"], ["<Subject 9> is Bala Krishna in <Picture 1>."])   # 9 is not 1..1 in order
    with pytest.raises(ValueError, match="in order"):
        settings_for(dict(REF_SHAPE, subjects=["<Subject 9> is Bala Krishna in <Picture 1>."]))
    assert subject_problems(["a.png"], ["<Subject 1> is Bala Krishna in <Picture 1>."]) == []
