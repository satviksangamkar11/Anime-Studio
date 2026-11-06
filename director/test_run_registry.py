"""Run registry (director/run_registry.py): names, the append-only event log, steps, best-effort hooks, read-only summary.
Stdlib only, no network, no model call."""
import datetime as dt
import json
from pathlib import Path

import pytest

import run_registry as rr


def lines(story_dir):
    return [json.loads(x) for x in (Path(story_dir) / "RUNS.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.fixture
def story(tmp_path):
    d = tmp_path / "stories" / "kaliya_test"
    d.mkdir(parents=True)
    return d


# ---------------------------------------------------------------- pack and run names
def test_pack_name_is_pattern_day_and_version():
    name = rr.pack_name("super-vl", day=dt.date(2026, 11, 6))
    assert name == "pack_super-vl_20261106_v1"
    assert rr.PACK.fullmatch(name)


def test_pack_name_never_reuses_a_taken_folder():
    day = dt.date(2026, 11, 6)
    assert rr.pack_name("super-vl", day=day, taken={"pack_super-vl_20261106_v1"}) == "pack_super-vl_20261106_v2"
    assert rr.pack_name("super-vl", day=day, taken={"pack_super-vl_20261106_v1", "pack_super-vl_20261106_v2"}) == "pack_super-vl_20261106_v3"
    assert rr.pack_name("ultra", day=day, taken={"pack_super-vl_20261106_v1"}) == "pack_ultra_20261106_v1"


def test_run_id_gets_a_suffix_on_collision():
    when = dt.datetime(2026, 11, 6, 23, 15).astimezone()
    base = rr.run_id("writer-super-vl", when=when)
    assert base == "20261106-2315-writer-super-vl"
    assert rr.run_id("writer-super-vl", when=when, taken={base}) == base + "-2"
    assert rr.run_id("writer-super-vl", when=when, taken={base, base + "-2"}) == base + "-3"


def test_writer_tag_for_a_shortcut_and_a_plain_model():
    assert rr.writer_tag("super-vl", "openrouter", "nvidia/nemotron-3.5-super-vl:free") == "super-vl"
    assert rr.writer_tag(None, "claude", "opus") == "claude-opus"


def test_story_folder_is_only_a_slug_folder_under_stories(tmp_path):
    assert rr.story_folder(tmp_path / "stories" / "kaliya_x" / "SOURCE.md") == tmp_path / "stories" / "kaliya_x"
    assert rr.story_folder(tmp_path / "other" / "kaliya_x" / "SOURCE.md") is None
    assert rr.story_folder(tmp_path / "stories" / "Bad Slug" / "SOURCE.md") is None


# ---------------------------------------------------------------- event log
def test_append_event_adds_one_line_per_event(story):
    rr.append_event(story, "run-a", "story_saved", None, "ok", files=["SOURCE.md"])
    rr.append_event(story, "run-a", "story_saved", None, "ok")
    assert [e["run_id"] for e in lines(story)] == ["run-a", "run-a"]


def test_bad_events_are_refused_and_nothing_is_written(story):
    rr.append_event(story, "run-a", "story_saved", None, "ok")
    before = (story / "RUNS.jsonl").read_text(encoding="utf-8")
    bad_calls = [
        lambda: rr.append_event(story, "run-a", "not_a_kind", None, "ok"),
        lambda: rr.append_event(story, "run-a", "story_saved", None, "maybe"),
        lambda: rr.append_event(story, "run-a", "story_saved", None, "ok", secret_field="x"),
        lambda: rr.append_event(story, "run-a", "analysis_stage", "../1", "ok"),
        lambda: rr.append_event(story, "run-a", "story_saved", None, "ok", files=["../../etc/passwd"]),
        lambda: rr.append_event(story, "run-a", "story_saved", None, "ok", pack="../pack"),
        lambda: rr.append_event(story, "bad run id!", "story_saved", None, "ok"),
    ]
    for call in bad_calls:
        with pytest.raises(ValueError):
            call()
    assert (story / "RUNS.jsonl").read_text(encoding="utf-8") == before


def test_secrets_in_notes_are_redacted_before_they_are_written(story):
    rr.append_event(story, "run-a", "analysis_stage", "1", "failed", note="HTTP 401 Bearer abc.def.ghi nvapi-SECRETVALUE0000")
    text = (story / "RUNS.jsonl").read_text(encoding="utf-8")
    assert "abc.def.ghi" not in text and "SECRETVALUE" not in text and "[REDACTED]" in text


# ---------------------------------------------------------------- steps and status
def test_steps_keep_every_attempt_and_close_each_one(story):
    rr.append_event(story, "run-a", "analysis_stage", "2", "started", at="2026-11-06T10:00:00+05:30")
    rr.append_event(story, "run-a", "analysis_stage", "2", "failed", note="content_filter")
    rr.append_event(story, "run-a", "analysis_stage", "2", "started", at="2026-11-06T10:05:00+05:30")
    rr.append_event(story, "run-a", "analysis_stage", "2", "ok", note="")
    rows = rr.steps(lines(story))
    assert [r["status"] for r in rows] == ["failed", "ok"]
    assert rows[0]["note"] == "content_filter"


def test_run_status_is_the_run_level_row_when_there_is_one():
    rows = [{"run_id": "r", "kind": "analysis_stage", "stage": "2", "status": "failed"},
            {"run_id": "r", "kind": "analysis_stage", "stage": "2", "status": "ok"},
            {"run_id": "r", "kind": "analysis_done", "stage": None, "status": "ok"}]
    assert rr.run_status(rows) == "ok"
    assert rr.run_status([rows[0]]) == "failed"
    assert rr.run_status([{"run_id": "r", "kind": "analysis_stage", "stage": "1", "status": "started"}]) == "open"


def test_a_failed_run_level_row_makes_the_run_failed():
    rows = [{"run_id": "r", "kind": "analysis_stage", "stage": "1", "status": "ok"},
            {"run_id": "r", "kind": "analysis_done", "stage": None, "status": "failed", "note": "RuntimeError: boom"}]
    assert rr.run_status(rows) == "failed"


def test_step_block_records_ok_failed_and_stopped(story):
    rec = rr.Recorder(story, "writer-test", pack="pack_t", via="openrouter", model="nvidia/nemotron-3.5-super-vl:free")
    with rec.step("analysis_stage", "1") as st:
        st.chars = 12
    with pytest.raises(ValueError):
        with rec.step("analysis_stage", "2"):
            raise ValueError("no shots block")
    with pytest.raises(KeyboardInterrupt):
        with rec.step("analysis_stage", "3e1"):
            raise KeyboardInterrupt()
    by_stage = {r["stage"]: r for r in rr.steps(lines(story))}
    assert by_stage["1"]["status"] == "ok" and by_stage["1"]["chars"] == 12
    assert by_stage["2"]["status"] == "failed" and "ValueError" in by_stage["2"]["note"]
    assert by_stage["3e1"]["status"] == "stopped"
    assert {r["model"] for r in rr.steps(lines(story))} == {"nvidia/nemotron-3.5-super-vl:free"}


def test_close_open_steps_closes_only_the_open_ones(story):
    rr.append_event(story, "run-a", "analysis_done", None, "started")
    rr.append_event(story, "run-a", "analysis_stage", "1", "started")
    rr.append_event(story, "run-a", "analysis_stage", "1", "ok")
    closed = rr.close_open_steps(story, "stopped", "stopped from the UI")
    assert closed == 1
    rows = rr.steps(lines(story))
    assert {(r["kind"], r["status"]) for r in rows} >= {("analysis_done", "stopped"), ("analysis_stage", "ok")}
    assert rr.run_status(rows) == "stopped"
    assert rr.close_open_steps(story, "stopped", "again") == 0


# ---------------------------------------------------------------- hooks are best effort
def test_a_failing_registry_write_never_breaks_the_step(story, monkeypatch, capsys):
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(rr, "append_event", boom)
    rec = rr.Recorder(story, "writer-test")
    ran = []
    with rec.step("analysis_stage", "1"):
        ran.append(True)
    assert ran == [True]
    assert "skipped" in capsys.readouterr().err


def test_record_story_saved_on_an_unusable_folder_returns_none(tmp_path):
    blocker = tmp_path / "stories"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    assert rr.record_story_saved(blocker / "kaliya_x", "# SOURCE: x\n", False) is None


def test_record_story_saved_writes_story_json_and_one_event(story):
    text = "# SOURCE: Kaliya Katha (Dhenuk)\n\nFetched from https://www.youtube.com/watch?v=abc on the owner's link.\n\n## TRANSCRIPT (verbatim)\n\nHari om.\n"
    run = rr.record_story_saved(story, text, False)
    assert run
    story_json = json.loads((story / "story.json").read_text(encoding="utf-8"))
    assert story_json["source"]["type"] == "youtube"
    saved = [e for e in lines(story) if e["kind"] == "story_saved"]
    assert len(saved) == 1 and saved[0]["files"] == ["SOURCE.md"]
    assert (story / "RUN_REPORT.md").is_file()


def test_reading_the_registry_writes_nothing(story):
    rr.record_story_saved(story, "# SOURCE: x\n", False)
    rr.append_event(story, "run-a", "analysis_done", None, "ok", pack="pack_x", model="m", via="openrouter")
    (story / "RUN_REPORT.md").unlink()
    before = sorted((p.name, p.read_bytes()) for p in story.iterdir())
    rr.summary(story)
    rr.report_text(story)
    rr.read_events(story)
    assert sorted((p.name, p.read_bytes()) for p in story.iterdir()) == before
    assert not (story / "RUN_REPORT.md").exists()


def test_write_report_writes_the_report_next_to_the_log(story):
    rr.append_event(story, "run-a", "story_saved", None, "ok")
    text = rr.write_report(story)
    assert (story / "RUN_REPORT.md").read_text(encoding="utf-8") == text
    assert "run-a" in text or "story_saved" in text


def test_summary_reports_the_latest_pack_model_and_the_next_name(story):
    pack = story / "pack_x"
    pack.mkdir()
    (pack / "shots.json").write_text(json.dumps([{"id": "SHOT-001", "episode": 1, "seconds": 4}]), encoding="utf-8")
    (pack / "PACK.md").write_text("# Pack\n", encoding="utf-8")
    rr.append_event(story, "run-a", "analysis_done", None, "ok", pack="pack_x", model="nvidia/nemotron-3.5-super-vl:free",
                    via="openrouter")
    s = rr.summary(story)
    assert s["latest_pack"] == "pack_x"
    assert s["pack_models"] == {"pack_x": "nvidia/nemotron-3.5-super-vl:free"}
    assert s["status"] == "ok" and s["run_count"] == 1
    assert s["next_pack"].startswith("pack_super-vl_") and s["next_pack"].endswith("_v1")


def test_envelope_info_reads_the_writer_envelope():
    raw = json.dumps({"type": "result", "is_error": False, "result": "abcd", "via": "openrouter",
                      "model": "nvidia/nemotron-3.5-super-vl:free", "finish_reason": "stop"})
    info = rr.envelope_info(raw)
    assert info == {"model": "nvidia/nemotron-3.5-super-vl:free", "via": "openrouter", "failed": False, "finish": "stop", "chars": 4}
    assert rr.envelope_info("not json") == {}
