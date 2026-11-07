import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bible_to_sheet_jobs as b  # noqa: E402

BIBLE = {"characters": {"CHAR-SATI": {"sheet_prompt": " Sati sheet "}, "CHAR-X": {"name": "no prompt"}},
         "environments": {"ENV-HALL": {"sheet_prompt": "hall"}}, "props": {"PROP-BOW": {"sheet_prompt": "bow"}}}


def test_jobs_in_order_16x9_no_chips():
    jobs = b.sheet_jobs(BIBLE)
    assert [j["shot_id"] for j in jobs] == ["CHAR-SATI", "ENV-HALL", "PROP-BOW"]
    assert jobs[0]["prompt"] == "Sati sheet" and jobs[0]["flow_title"] == "CHAR-SATI__v01" and jobs[0]["aspect"] == "16:9"
    assert all(j["chips"] == [] and j["method"] == "generate" for j in jobs)
    assert [j["shot_id"] for j in b.sheet_jobs(BIBLE, {"ENV-HALL"})] == ["ENV-HALL"]


def test_cli_writes_once_and_refuses_overwrite(tmp_path):
    src = tmp_path / "bible.json"
    src.write_text(json.dumps(BIBLE), encoding="utf-8")
    out = tmp_path / "g" / "s_flow_jobs_sheets.json"
    assert b.main([str(src), "s", str(out)]) == 0 and len(json.loads(out.read_text(encoding="utf-8"))) == 3
    assert b.main([str(src), "s", str(out)]) == 2
