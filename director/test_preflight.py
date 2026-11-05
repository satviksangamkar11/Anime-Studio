"""Test preflight (plan v4.3, phase 1B): frames, FL2VA/Ref2VA prompt structure, identity text, rejects, safe ids and paths, PNG."""
import base64
import io

import pytest
from PIL import Image

import run_kaggle
import shot_schema
from h3_director import check_combo, frames_for_shot, settings_for
from test_shot_schema import RICH as RICH_LIKE

BASE = {"id": "SHOT-04", "episode": 1, "mode": "fl2va", "seconds": 5, "aspect": "9:16", "start": "a.png",
        "style": "Flat 2D cel anime.", "world": "Riverbank at dawn.", "action": "0-2s he steps forward.", "camera": "slow crane down"}
BIBLE = {"characters": [{"id": "CHAR-KRISHNA", "name": "Bala Krishna", "skin": {"treatment": "warm brown; cel shade"},
                         "costume": [{"piece": "yellow dhoti", "colour_hex": "#E8B400"}], "hair": {"base_colour": "black"},
                         "silhouette_markers": ["topknot"], "proportions_heads": 6, "forbidden_drift": ["adult proportions"]}],
         "environments": [{"id": "ENV-KADAMBA-BANK", "name": "Kadamba bank", "geography": "river bend", "day_key": "morning",
                           "composition": {"fg": "leaves", "mid": "bank", "bg": "river"}}], "props": []}


def test_render_frames_is_authoritative_and_seconds_are_ignored():
    assert frames_for_shot(dict(BASE, seconds=5.2, render_frames=107)) == 107
    assert settings_for(dict(BASE, seconds=5.2, render_frames=107))["video_length"] == 107


def test_render_frames_must_be_a_legal_h3_count():
    for bad in (100, 108, 363, 124.0, True):
        with pytest.raises(ValueError, match="render_frames"):
            frames_for_shot(dict(BASE, render_frames=bad))


def test_edit_frames_is_between_one_and_render_frames():
    assert frames_for_shot(dict(BASE, render_frames=124, edit_frames=1)) == 124
    assert frames_for_shot(dict(BASE, render_frames=124, edit_frames=124)) == 124
    for bad in (0, 125, 2.5):
        with pytest.raises(ValueError, match="edit_frames"):
            frames_for_shot(dict(BASE, render_frames=124, edit_frames=bad))


def test_the_prompt_states_the_render_length_in_seconds():
    s = settings_for(dict(BASE, seconds=4.0))
    assert s["video_length"] == 107 and "A 4.46-second single take" in s["prompt"]
    assert "A 5.17-second single take" in settings_for(dict(BASE, seconds=5.2))["prompt"]


def test_frames_are_nearest_up_to_one_step_past_the_max():
    assert frames_for_shot(dict(BASE, seconds=15.15)) == 362 and frames_for_shot(dict(BASE, seconds=15.2)) == 362
    assert settings_for(dict(BASE, seconds=15.2))["video_length"] == 362
    for too_long in (15.5, 16):
        with pytest.raises(ValueError, match="longer than one H3 window"):
            settings_for(dict(BASE, seconds=too_long))
        assert any("longer than one H3 window" in p for p in shot_schema.validate_shot(dict(RICH_LIKE, seconds=too_long)))


def test_render_frames_replaces_seconds_in_validation():
    ok = dict(RICH_LIKE)
    ok.pop("seconds")
    ok["render_frames"] = 124
    assert not any("seconds" in p or "render_frames" in p for p in shot_schema.validate_shot(ok))
    neither = dict(ok)
    neither.pop("render_frames")
    assert any("missing seconds or render_frames" in p for p in shot_schema.validate_shot(neither))


def test_end_only_fl2va_gets_the_end_wording_and_the_end_image_slot():
    s = settings_for(dict(BASE, start=None, end="b.png", seconds=5.2))
    assert s["prompt"].startswith("For the target video, at 5.17 seconds into the target video, <Picture 1> (from the actual final shot)")
    assert s["image_prompt_type"] == "E" and "image_start" not in s and s["image_end"] == "b.png"
    assert not any("keyframes" in p for p in shot_schema.validate_shot(dict(RICH_LIKE, keyframes={"end": "b.png"})))


def test_ref2va_summary_names_keyframe_completion_only_when_there_are_keyframes():
    refs = dict(BASE, mode="ref2va", refs=["k.png"], subjects=["<Subject 1> is Bala Krishna in <Picture 1>."])
    assert "summary:\n[keyframe completion + reference generation] " in settings_for(refs)["prompt"]
    assert "summary:\n[keyframe completion + reference generation] " in settings_for(dict(refs, start=None, end="b.png"))["prompt"]
    bare = settings_for(dict(refs, start=None))["prompt"]
    assert "summary:\n[reference generation] " in bare and "keyframe completion" not in bare


def test_cmyk_pictures_are_converted_to_an_rgb_png(tmp_path):
    Image.new("CMYK", (64, 96), (0, 255, 255, 0)).save(tmp_path / "c.jpg")
    out = Image.open(io.BytesIO(base64.b64decode(run_kaggle.png_b64(tmp_path / "c.jpg"))))
    assert out.format == "PNG" and out.mode == "RGB" and out.size == (64, 96)


def test_a_wav_or_mp4_is_never_an_image_path():
    with pytest.raises(ValueError):
        settings_for(dict(BASE, mode="ref2va", refs=["voice.wav"], subjects=["<Subject 1> is x in <Picture 1>."]))
    with pytest.raises(ValueError):
        settings_for(dict(BASE, end="clip.mp4"))


def test_validate_reports_a_bad_render_frames():
    rich = {"id": "SHOT-07", "episode": 2, "scene": "x", "mode": "fl2va", "seconds": 5.2, "aspect": "9:16", "purpose": "p",
            "cast": [], "props": [], "set": "ENV", "beats": [{"t": [0, 5.2], "acting": "a", "primary": True}], "camera": {},
            "layers": {}, "light": {}, "compositing": {}, "keyframes": {"start": "a.png"}, "sound": "s", "render_frames": 108}
    assert any("render_frames" in p for p in shot_schema.validate_shot(rich))


def test_fl2va_alignment_for_a_start_frame():
    p = settings_for(BASE)["prompt"]
    assert p.startswith("For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.\n"
                        "integrated_multimodal_description:")


def test_fl2va_alignment_for_start_and_end_frames():
    p = settings_for(dict(BASE, end="b.png", seconds=5.2))["prompt"]
    assert "at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced." in p
    assert "at 5.17 seconds into the target video, <Picture 2> (from [Shot 1]) is fully referenced." in p


def test_ref2va_numbers_refs_after_start_and_end_and_keeps_the_sections_in_order():
    shot = dict(BASE, mode="ref2va", end="b.png", refs=["k.png"], subjects=["<Subject 1> is Bala Krishna in <Picture 1>."])
    p = settings_for(shot)["prompt"]
    assert "<Subject 1> is Bala Krishna in <Picture 3>." in p
    assert "<Picture 1> is the start frame of [Shot 1] at 0.00 seconds." in p
    assert "<Picture 2> is the end frame of [Shot 1] at 5.17 seconds." in p
    assert p.index("subject_definitions:") < p.index("summary:") < p.index("retention_analysis:") < p.index("detailed_description:") < p.index("overall_soundscape:")


def test_ref2va_retention_keeps_identity_and_lets_pose_and_camera_change():
    shot = dict(BASE, mode="ref2va", start=None, refs=["k.png"], subjects=["<Subject 1> is Bala Krishna in <Picture 1>."])
    p = settings_for(shot)["prompt"]
    assert ("<Subject 1> (appears in [Shot 1]): fully_preserved - face, eyes, age proportions, hair, costume, ornaments, "
            "line weight and cel shading. May change: pose, expression, camera framing.") in p
    assert "<Picture 1> is" not in p and "<Subject 1> is Bala Krishna in <Picture 1>." in p


def test_identity_text_from_the_bible_reaches_the_prompt():
    shot = dict(BASE, mode="fl2va", cast=[{"id": "CHAR-KRISHNA"}], set="ENV-KADAMBA-BANK")
    p = settings_for(shot, BIBLE)["prompt"]
    assert "Bala Krishna. 6 heads." in p and "Kadamba bank. river bend. Light: morning." in p
    assert "Bala Krishna" not in settings_for(shot)["prompt"]


def test_an_id_missing_from_the_bible_is_a_value_error():
    with pytest.raises(ValueError, match="not in the style bible"):
        settings_for(dict(BASE, cast=[{"id": "CHAR-NOBODY"}]), BIBLE)


def test_fl2va_with_refs_is_rejected():
    with pytest.raises(ValueError, match="ref2va"):
        settings_for(dict(BASE, refs=["k.png"]))


def test_a_sampler_other_than_pika_renoise_is_rejected():
    with pytest.raises(ValueError, match="pika_renoise"):
        settings_for(dict(BASE, sampler="euler"))


def test_pika_needs_an_fl2va_or_ref2va_model_and_its_sampler():
    ok = settings_for(BASE)
    check_combo(ok)
    with pytest.raises(ValueError):
        check_combo(dict(ok, model_type="minimax_h3_image"))
    with pytest.raises(ValueError):
        check_combo(dict(ok, sample_solver="euler"))
    with pytest.raises(ValueError):
        check_combo(dict(ok, activated_loras=[]))   # the Pika sampler needs its adapter


@pytest.mark.parametrize("bad", ["SHOT-1", "SHOT-1234", "shot-01", "SHOT-01AB", "../SHOT-01", "SHOT-01/x", "SHOT-01 "])
def test_shot_ids_must_match_the_pattern(bad):
    with pytest.raises(ValueError, match="id"):
        settings_for(dict(BASE, id=bad))
    assert any("id" in p for p in shot_schema.validate_shot(dict(BASE, id=bad)))


def test_suffixed_shot_ids_are_legal():
    assert settings_for(dict(BASE, id="SHOT-100A"))["video_length"] == 124


@pytest.mark.parametrize("bad", ["/abs/a.png", "C:/a.png", "C:a.png", "../a.png", "a/../b.png", "a b.png", "a.gif", "a\\b.png",
                                 "a.exe", "a/b.txt", "a.PNG"])
def test_unsafe_or_unknown_image_paths_are_rejected(bad):
    with pytest.raises(ValueError):
        settings_for(dict(BASE, start=bad))
    assert any("path" in p for p in shot_schema.validate_shot(dict(BASE, mode="ref2va", refs=[bad], subjects=["x"], start=None)))


@pytest.mark.parametrize("good", ["keyframes/SHOT-04-FRAME-A.png", "refs/krishna_v2.jpeg", "d1/d2/x.jpg"])
def test_relative_image_paths_pass(good):
    assert settings_for(dict(BASE, start=good))["image_start"] == good


def test_png_inputs_keep_their_format_and_only_large_pictures_shrink(tmp_path):
    Image.new("RGB", (2000, 3000), "red").save(tmp_path / "big.png")
    Image.new("RGB", (64, 96), "blue").save(tmp_path / "small.png")
    out_big = Image.open(io.BytesIO(base64.b64decode(run_kaggle.png_b64(tmp_path / "big.png"))))
    assert out_big.format == "PNG" and max(out_big.size) == 1376
    out_small = Image.open(io.BytesIO(base64.b64decode(run_kaggle.png_b64(tmp_path / "small.png"))))
    assert out_small.format == "PNG" and out_small.size == (64, 96)
