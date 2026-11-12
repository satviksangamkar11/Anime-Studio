import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bible_to_sheet_jobs as b  # noqa: E402

BIBLE = {"characters": {"CHAR-SATI": {"sheet_prompt": "Sati sheet"}},
         "environments": {"ENV-HALL": {"sheet_prompt": "hall"}},
         "props": {"PROP-BOW": {"sheet_prompt": "bow"}}}


def test_prop_prompt_gets_grey_human_outline_for_scale():
    jobs = {j["shot_id"]: j for j in b.sheet_jobs(BIBLE)}
    assert jobs["PROP-BOW"]["prompt"] == "bow, three views, next to a plain grey human outline for scale"
    assert jobs["CHAR-SATI"]["prompt"] == "Sati sheet"
    assert jobs["ENV-HALL"]["prompt"] == "hall"


def test_prompt_sha_matches_prompt_text():
    for j in b.sheet_jobs(BIBLE):
        assert j["prompt_sha256"] == hashlib.sha256(j["prompt"].encode("utf-8")).hexdigest()


def test_extra_turnaround_and_expression_jobs_for_characters_only():
    extra = b.extra_sheet_jobs(BIBLE)
    titles = [j["flow_title"] for j in extra]
    assert titles == ["CHAR-SATI__turnaround__v01", "CHAR-SATI__expressions__v01"]
    assert "front, three-quarter, side, back" in extra[0]["prompt"] and "Sati sheet" in extra[0]["prompt"]
    assert "calm, resolve, awe, grief, anger, joy" in extra[1]["prompt"]
    assert all(j["aspect"] == "16:9" and j["chips"] == [] for j in extra)


def test_style_chip_job_only_when_bible_has_style():
    bible = dict(BIBLE, style={"sheet_prompt": "flat cel style chip, line weight, cel shadow, swatches"})
    titles = [j["flow_title"] for j in b.extra_sheet_jobs(bible)]
    assert "STYLE__chip__v01" in titles
    assert "STYLE__chip__v01" not in [j["flow_title"] for j in b.extra_sheet_jobs(BIBLE)]


def _cli(tmp_path, *flags):
    src = tmp_path / "bible.json"
    src.write_text(json.dumps(BIBLE), encoding="utf-8")
    out = tmp_path / "s_flow_jobs_sheets.json"
    assert b.main([str(src), "s", str(out), *flags]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_section_43_default_on(tmp_path):
    titles = [j["flow_title"] for j in _cli(tmp_path)]
    assert len(titles) == 5 and "CHAR-SATI__turnaround__v01" in titles and "CHAR-SATI__expressions__v01" in titles


def test_old_section_4_3_flag_still_accepted(tmp_path):
    assert len(_cli(tmp_path, "--section-4-3")) == 5


def test_no_section_4_3_gives_three_identity_jobs(tmp_path):
    assert len(_cli(tmp_path, "--no-section-4-3")) == 3
