"""Owner 2026-11-08: the Flow packet must carry everything for making AND downloading, and each story has its own Flow folder.
Offline: temp folders, no model call."""
import json
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402
from server import ApiError, Config  # noqa: E402

SLUG = "kalika_puran_bhag1"


@pytest.fixture()
def api(tmp_path):
    studio = tmp_path / "anime_studio"
    (studio / "ui" / "runs").mkdir(parents=True)
    (studio / "stories" / SLUG / "pack_a").mkdir(parents=True)
    gen = studio / "flow" / "generated" / SLUG
    gen.mkdir(parents=True)
    job = {"shot_id": "SHOT-001", "flow_title": "SHOT-001__v01", "method": "edit", "base_edit_id": "e" * 36,
           "chips": ["CHAR-SATI", "STYLE_CHIP"], "previous_shot": "SHOT-000", "next_shot": "SHOT-002", "attempt_cap": 8,
           "neighbour_chips": ["SHOT-000__v01"], "neighbour_sentence": "Match the neighbour.", "edit_instruction": "Change only the hand.",
           "prompt": "a prompt", "prompt_sha256": "abc", "model": {"name": "Nano Banana 2.1", "aspect": "9:16"}}
    (gen / "jobs.json").write_text(json.dumps([job]), encoding="utf-8")
    flow = tmp_path / "flow_outputs" / "anime_kaliya"
    flow.mkdir(parents=True)
    (tmp_path / "flow_outputs" / f"anime_{SLUG}").mkdir()
    (tmp_path / "flow_outputs" / "adhyay_01").mkdir()          # a Granth folder: must stay out of reach
    cfg = Config(studio=studio, flow=flow, downloads=tmp_path / "dl", python=sys.executable,
                 colab=[str(tmp_path / "colab.exe")], disk_paths=(str(tmp_path), str(tmp_path)))
    return server.Api(cfg)


def test_packet_has_everything_for_making_and_downloading(api):
    md = api.packet({"story": SLUG, "pack": "pack_a", "jobs": f"flow/generated/{SLUG}/jobs.json", "shots": ["SHOT-001"]})["markdown"]
    root = str(server.flow_root(api.cfg, SLUG))
    for need in ("labs.google/fx/tools/flow/project/", "aspect: 9:16", "base edit id: " + "e" * 36, "previous scene: SHOT-000",
                 "next scene: SHOT-002", "Never delete", "CAPTCHA", "EDIT first", "NEEDS_REVIEW", "review_shot.py", "neighbour_sheet.py",
                 "download_queue.py add", "shots_progress.jsonl", "2K Upscaled", "save_dl.py", "download_queue.py collect",
                 "neighbour chips", "edit instruction: Change only the hand."):
        assert need in md, need
    assert root in md and "anime_kaliya" not in md


def test_each_story_has_its_own_flow_folder(api):
    cfg = api.cfg
    assert server.flow_root(cfg, None) == cfg.flow and server.flow_root(cfg, "kaliya_mardan") == cfg.flow
    assert server.flow_root(cfg, SLUG).name == f"anime_{SLUG}"
    assert server._adh(cfg, {"adhyay": 1, "story": SLUG}) == cfg.flow.parent / f"anime_{SLUG}" / "adhyay_01"
    argv = server.command_spec("queue_collect").build(cfg, {"adhyay": 1, "story": SLUG})
    assert str(server.flow_root(cfg, SLUG)) in argv
    ok = server.safe_path(cfg, str(cfg.flow.parent / f"anime_{SLUG}"), ("flow",), None, True, "dir")
    assert ok.endswith(f"anime_{SLUG}")
    with pytest.raises(ApiError):
        server.safe_path(cfg, str(cfg.flow.parent / "adhyay_01"), ("flow",), None, True, "dir")
