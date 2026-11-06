"""backfill_registry.py on a temp studio: idempotent, keeps what exists, reads the traceback line, never touches sources or packs."""
import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

import backfill_registry as bf
import run_registry as rr

SOURCE = ("# SOURCE: Kaliya Demo (Demo Channel)\n\nFetched from https://www.youtube.com/watch?v=abc on the owner's link (YouTube captions).\n\n"
          "## TRANSCRIPT (verbatim)\n\nHari om. Kaliya was on the river.\n")
RAW = json.dumps({"type": "result", "is_error": False, "result": "# Gate 1\nEpisode 1: river\n", "via": "nvidia",
                  "model": "nvidia/nemotron-3-ultra-550b-a55b", "finish_reason": "stop"})
TRACEBACK_LOG = ("stage 1: C:\\aai work\\anime_studio\\stories\\kaliya_demo\\pack_nemotron_v1\\stage_1_raw.json\n"
                 "Traceback (most recent call last):\n"
                 '  File "write_pack.py", line 9, in main\n'
                 "ValueError: stage 1 names no episodes (write lines 'Episode N: title')\n"
                 "exit=1\n")


def make_studio(root: Path) -> Path:
    studio = root / "studio"
    story = studio / "stories" / "kaliya_demo"
    pack = story / "pack_nemotron_v1"
    pack.mkdir(parents=True)
    (story / "SOURCE.md").write_text(SOURCE, encoding="utf-8")
    (pack / "PACK.md").write_text("# Pack\n\nEpisode 1: river\n", encoding="utf-8")
    (pack / "shots.json").write_text(json.dumps([{"id": "SHOT-001", "episode": 1, "seconds": 4}]), encoding="utf-8")
    (pack / "bible.json").write_text("{}", encoding="utf-8")
    (pack / "stage_1_raw.json").write_text(RAW, encoding="utf-8")
    (story / "writer_run.log").write_text(TRACEBACK_LOG, encoding="utf-8")
    (story / "writer_run_empty.log").write_text("", encoding="utf-8")
    return studio


def snapshot(studio: Path) -> dict:
    keep = {"RUNS.jsonl", "RUN_REPORT.md", "story.json"}
    out = {}
    for p in sorted((studio / "stories").rglob("*")):
        if p.is_file() and p.name not in keep:
            out[str(p.relative_to(studio))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def run_lines(studio: Path, slug="kaliya_demo"):
    path = studio / "stories" / slug / "RUNS.jsonl"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


@pytest.fixture
def studio(tmp_path, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("the backfill must not touch the network")
    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    return make_studio(tmp_path)


def test_backfill_writes_the_log_and_a_second_run_adds_nothing(studio, capsys):
    assert bf.main(["--studio", str(studio), "--apply"]) == 0
    first = run_lines(studio)
    assert first and (studio / "stories" / "kaliya_demo" / "story.json").is_file()
    assert (studio / "stories" / "kaliya_demo" / "RUN_REPORT.md").is_file()
    assert "+0 events" not in capsys.readouterr().out
    assert bf.main(["--studio", str(studio), "--apply"]) == 0
    assert run_lines(studio) == first
    assert "RUNS.jsonl +0 events" in capsys.readouterr().out


def test_failed_run_note_is_the_exception_line_not_the_exit_code(studio):
    bf.main(["--studio", str(studio), "--apply"])
    events = [json.loads(x) for x in run_lines(studio)]
    failed = [e for e in events if e["kind"] == "analysis_done" and e["status"] == "failed"]
    assert failed, events
    assert failed[0]["note"] == "ValueError: stage 1 names no episodes (write lines 'Episode N: title')"
    assert "exit=1" not in failed[0]["note"]


def test_an_empty_log_is_a_stopped_run(studio):
    bf.main(["--studio", str(studio), "--apply"])
    stopped = [json.loads(x) for x in run_lines(studio)
               if '"analysis_done"' in x and '"stopped"' in x]
    assert stopped and "empty log" in stopped[0]["note"]


def test_an_existing_story_json_is_kept(studio):
    bf.main(["--studio", str(studio), "--apply"])
    path = studio / "stories" / "kaliya_demo" / "story.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["title"] = "Owner's own title"
    path.write_text(json.dumps(data), encoding="utf-8")
    bf.main(["--studio", str(studio), "--apply"])
    assert json.loads(path.read_text(encoding="utf-8"))["title"] == "Owner's own title"


def test_sources_and_pack_files_are_not_changed(studio):
    before = snapshot(studio)
    bf.main(["--studio", str(studio)])
    assert snapshot(studio) == before
    assert (studio / "stories" / "kaliya_demo" / "SOURCE.md").read_text(encoding="utf-8") == SOURCE


def test_only_one_story_when_asked(studio):
    other = studio / "stories" / "kaliya_other"
    other.mkdir()
    (other / "SOURCE.md").write_text(SOURCE, encoding="utf-8")
    bf.main(["--studio", str(studio), "--only", "kaliya_demo", "--apply"])
    assert run_lines(studio, "kaliya_demo")
    assert not (other / "RUNS.jsonl").exists()


def test_the_backfilled_story_reads_back_through_the_registry(studio):
    bf.main(["--studio", str(studio), "--apply"])
    s = rr.summary(studio / "stories" / "kaliya_demo")
    assert s["title"] == "Kaliya Demo (Demo Channel)"
    assert s["source"]["type"] == "youtube"
    assert s["latest_pack"] == "pack_nemotron_v1"
    assert s["pack_models"]["pack_nemotron_v1"] == "nvidia/nemotron-3-ultra-550b-a55b"
