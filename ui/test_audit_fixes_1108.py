"""Guards for the 11-08 audit fixes: the real adhyay_01 layout, queue items without image_id, story switch resets folders."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import facts  # noqa: E402
from test_pipeline import make_images_dir, make_runs, make_story, make_pack  # noqa: E402


def test_facts_read_the_adhyay_01_layout_and_queue_items_with_only_shot_id(tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir()
    make_story(studio, "s")
    make_pack(studio, "s", "p", shots=[], bible={})
    flow = tmp_path / "anime_s"
    chapter = make_images_dir(flow, "adhyay_01", finals=2,
                              dq_lines=[{"shot_id": "SHOT-001", "version": "v01"}, {"shot_id": "SHOT-002", "version": "v01"}],
                              fl_lines=[{"image_id": "SHOT-001", "version": "v01"}])
    assert chapter.name == "adhyay_01"
    runs = make_runs(tmp_path, slug="s", pack="p", images_dir=str(flow))
    f = facts(studio, runs)
    assert f["finals"] == 2 and f["pending"] == 1   # SHOT-002 is queued and not yet filed


def test_write_pack_claude_asks_for_web_and_high_effort(tmp_path):
    import server
    studio = tmp_path / "studio"
    (studio / "stories" / "s1").mkdir(parents=True)
    (studio / "stories" / "s1" / "SOURCE.md").write_text("x", encoding="utf-8")
    cfg = server.Config(studio=studio, flow=tmp_path / "flow_outputs" / "anime_kaliya", downloads=tmp_path / "d", python=sys.executable,
                        colab=["c"], disk_paths=(str(tmp_path), str(tmp_path)), allow_claude=True)
    argv = server.b_write_pack_claude(cfg, {"slug": "s1", "pack": "p1", "out_lang": "en"})
    assert "--web" in argv and argv[argv.index("--effort") + 1] == "high" and argv[argv.index("--writer") + 1] == "opus"
