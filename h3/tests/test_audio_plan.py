import json

import pytest

from h3.assemble_reel import build_ffmpeg_assembly_plan, loudness_plan, write_loudness_json
from h3.compile_h3_sing8 import compile_fl2va_prompt
from h3.schema_and_linter import lint_story
from h3.tests.synth import codes

BED = "Rain on wet stone, a distant bell ringing."  # 8 words, location loc_step
EFFECTS = "Soft wind through the leaves, steps on stone."
EXPECTED_LINE = f"overall_soundscape: Sound effects only: {BED} {EFFECTS}"


def _shots(story):
    return story["episodes"][0]["shots"]


def _with_bed(story, bed=BED):
    story["registry"]["sound_beds"] = {"loc_step": bed}
    return story


def _soundscape_line(story, shot_index=0):
    text = compile_fl2va_prompt(_shots(story)[shot_index], story["registry"])["compiled_prompt"]
    return next(line for line in text.split("\n") if line.startswith("overall_soundscape: "))


@pytest.mark.parametrize("raw", [
    EFFECTS,
    f"Sound effects only: {EFFECTS}",
    f"Sound effects only: {BED} {EFFECTS}",
])
def test_bed_prefix_compiled_once(story, raw):
    _with_bed(story)
    _shots(story)[0]["sound_plan"]["overall_soundscape"] = raw
    line = _soundscape_line(story)
    assert line == EXPECTED_LINE
    assert line.count("Sound effects only:") == 1 and line.count(BED) == 1


def test_prefix_without_bed_when_none_defined(story):
    _shots(story)[0]["sound_plan"]["overall_soundscape"] = EFFECTS
    assert _soundscape_line(story) == f"overall_soundscape: Sound effects only: {EFFECTS}"


def test_bed_only_applies_to_its_own_location(story):
    _with_bed(story)
    _shots(story)[1]["continuity_and_seam_lock"]["location_id"] = "loc_other"
    assert _soundscape_line(story, 1) == ("overall_soundscape: Sound effects only: "
                                          "Rain on wet stone, a distant bell ringing, soft wind through the leaves.")


def test_sd03_passes_with_bed_and_compiled_matches(story):
    _with_bed(story)
    assert lint_story(story) == {"errors": [], "warnings": []}


@pytest.mark.parametrize("tamper", [
    lambda t: t.replace("Sound effects only: ", "", 1),
    lambda t: t.replace(f"Sound effects only: {BED} ", "Sound effects only: ", 1),
])
def test_sd03_fails_when_compiled_soundscape_loses_prefix_or_bed(story, tamper):
    _with_bed(story)
    compiled = compile_fl2va_prompt(_shots(story)[0], story["registry"])["compiled_prompt"]
    tampered = tamper(compiled)
    assert tampered != compiled
    assert "SD-03" in codes(lint_story(story, compiled={"SYN_A": tampered})["errors"])


def test_sd01_checks_raw_text_so_bed_cannot_pad_an_empty_soundscape(story):
    _with_bed(story)
    _shots(story)[0]["sound_plan"]["overall_soundscape"] = ""
    assert any("SD-01" in e and "non-empty" in e for e in lint_story(story)["errors"])


def test_sd04_bed_of_12_words_passes(story):
    _with_bed(story, " ".join(["word"] * 12))
    assert lint_story(story) == {"errors": [], "warnings": []}


def test_sd04_bed_longer_than_12_words_fails(story):
    _with_bed(story, " ".join(["word"] * 13))
    assert "SD-04" in codes(lint_story(story)["errors"])


@pytest.mark.parametrize("bad", [42, None, ["Rain"]])
def test_sd04_bed_not_a_string_fails(story, bad):
    _with_bed(story, bad)
    assert "SD-04" in codes(lint_story(story)["errors"])


def test_sd04_sound_beds_not_an_object_fails(story):
    story["registry"]["sound_beds"] = ["loc_step"]
    assert "SD-04" in codes(lint_story(story)["errors"])


MEASURED = {"a": -23.7, "b": -10.2, "c": -21.1}


def test_loudness_plan_gains_and_limit():
    plan = loudness_plan(MEASURED)
    assert {k: v["gain_db"] for k, v in plan.items()} == {"a": 7.7, "b": -5.8, "c": 5.1}
    assert all(v["limit"] == 0.8913 for v in plan.values())


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), None, "-20", True])
def test_loudness_plan_refuses_missing_or_non_finite(bad):
    with pytest.raises(ValueError):
        loudness_plan({"a": -20.0, "b": bad})


def test_filter_order_volume_limiter_then_fades(story):
    loud = loudness_plan({"SYN_A": -23.7})
    fc = build_ffmpeg_assembly_plan(_shots(story), "out.mp4", loudness=loud)["filter_complex"]
    chain = next(c for c in fc.split(";") if c.startswith("[0:a]"))
    assert chain == ("[0:a]atrim=start=0.00:end=6.04,asetpts=PTS-STARTPTS,volume=7.7dB,"
                     "alimiter=limit=0.8913:level=disabled,afade=t=in:st=0:d=0.005,"
                     "afade=t=out:st=6.035:d=0.005[a0]")


def test_shot_without_loudness_entry_keeps_old_chain(story):
    loud = loudness_plan({"SYN_A": -23.7})
    fc = build_ffmpeg_assembly_plan(_shots(story), "out.mp4", loudness=loud)["filter_complex"]
    assert "[1:a]atrim=start=0.50:end=6.04,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.005,afade=t=out:st=" in fc


def test_filter_unchanged_without_loudness(story):
    fc = build_ffmpeg_assembly_plan(_shots(story), "out.mp4")["filter_complex"]
    assert ("[0:a]atrim=start=0.00:end=6.04,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.005,"
            "afade=t=out:st=6.035:d=0.005[a0]") in fc
    assert "volume=" not in fc and "alimiter" not in fc
    assert build_ffmpeg_assembly_plan(_shots(story), "out.mp4", loudness={})["filter_complex"] == fc


def test_write_loudness_json_content(tmp_path):
    path = write_loudness_json(str(tmp_path / "loudness.json"), MEASURED, loudness_plan(MEASURED))
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    assert doc == {"target_lufs": -16.0, "true_peak_db": -1.0, "clips": {
        "a": {"measured_lufs": -23.7, "gain_db": 7.7, "limit": 0.8913},
        "b": {"measured_lufs": -10.2, "gain_db": -5.8, "limit": 0.8913},
        "c": {"measured_lufs": -21.1, "gain_db": 5.1, "limit": 0.8913}}}
