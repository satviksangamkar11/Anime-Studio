"""core.retention_report: analytics dips -> shot ids (WP9, spec test: a dip at 31.0 s maps to the shot whose window covers it).
Synthetic build dirs in tmp_path; no network, no model call."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from core import retention_report as rr

REPO = Path(__file__).resolve().parents[2]


def h3_story(episodes):
    """episodes: {episode_id: [(shot_id, start_s, end_s), ...]} in the h3 shape (timing_and_lattice.master_reel_window_sec)."""
    return {"registry": {}, "episodes": [
        {"episode_id": ep, "shots": [{"shot_id": sid, "episode_id": ep,
                                      "timing_and_lattice": {"master_reel_window_sec": [a, b]}} for sid, a, b in shots]}
        for ep, shots in episodes.items()]}


H3_ONE = h3_story({"EP1": [("EP1-A", 0.0, 12.0), ("EP1-B", 12.0, 31.5), ("EP1-C", 31.5, 40.0)]})


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def analytics(dips, episode="EP1", **extra):
    data = {"episode": episode, "uploaded": "2026-11-07", "viewed_pct": 60, "swiped_pct": 40, "avg_pct_viewed": 45,
            "dips": dips}
    data.update(extra)
    return data


@pytest.fixture
def h3_dir(tmp_path):
    build = tmp_path / "build_h3"
    build.mkdir()
    write(build / "story_h3.json", H3_ONE)
    return build


def test_h3_dip_at_31_0_seconds_maps_to_the_shot_whose_window_covers_it(h3_dir, tmp_path):
    report_in = write(tmp_path / "analytics.json", analytics([{"t": 31.0, "drop_pct": 12.5}]))
    report = rr.retention_report(h3_dir, report_in)
    assert report["episode"] == "EP1" and report["source"] == "story_h3.json"
    dip = report["dips"][0]
    assert dip["shot_id"] == "EP1-B" and dip["window"] == [12.0, 31.5]
    assert dip["offset_in_shot_s"] == 19.0 and dip["drop_pct"] == 12.5 and dip["t"] == 31.0
    assert report["unmapped"] == []


def test_the_same_dip_maps_the_same_way_from_a_v22_shot_list(tmp_path):
    build = tmp_path / "build_v22"
    build.mkdir()
    # 240 + 240 + 300 edit frames at 24 fps: windows [0,10), [10,20), [20,32.5)
    write(build / "shots.json", [{"id": "S1", "episode": 3, "edit_frames": 240},
                                 {"id": "S2", "episode": 3, "edit_frames": 240},
                                 {"id": "S3", "episode": 3, "edit_frames": 300}])
    report_in = write(tmp_path / "analytics.json", analytics([{"t": 31.0, "drop_pct": 12.5}], episode=3))
    report = rr.retention_report(build, report_in)
    assert report["source"] == "shots.json" and report["episode"] == 3
    assert report["dips"][0]["shot_id"] == "S3" and report["dips"][0]["window"] == [20.0, 32.5]
    assert report["dips"][0]["offset_in_shot_s"] == 11.0


def test_v22_shot_without_edit_frames_uses_the_h3_frame_count(tmp_path):
    build = tmp_path / "build_len"
    build.mkdir()
    shot = {"id": "S1", "episode": 1, "seconds": 10}
    write(build / "shots.json", [shot])
    report_in = write(tmp_path / "analytics.json", analytics([], episode=1))
    report = rr.retention_report(build, report_in)
    assert report["dips"] == [] and report["unmapped"] == []
    written = json.loads((build / "retention_dips.json").read_text(encoding="utf-8"))
    assert written["dips"] == [] and written["episode"] == 1
    sys.path.insert(0, str(REPO / "director"))
    try:
        from h3_director import frames_for_shot
    finally:
        sys.path.remove(str(REPO / "director"))
    expected = frames_for_shot(shot) / 24
    dips_check = rr.retention_report(build, write(tmp_path / "a2.json", analytics([{"t": expected - 0.01, "drop_pct": 1}], episode=1)))
    assert dips_check["dips"][0]["shot_id"] == "S1" and dips_check["dips"][0]["window"] == [0.0, expected]


def test_a_dip_exactly_on_a_boundary_belongs_to_the_shot_that_starts_there(h3_dir, tmp_path):
    report_in = write(tmp_path / "analytics.json", analytics([{"t": 12.0, "drop_pct": 3}, {"t": 0.0, "drop_pct": 1}]))
    report = rr.retention_report(h3_dir, report_in)
    by_t = {d["t"]: d for d in report["dips"]}
    assert by_t[12.0]["shot_id"] == "EP1-B" and by_t[12.0]["offset_in_shot_s"] == 0.0
    assert by_t[0.0]["shot_id"] == "EP1-A"


def test_a_dip_outside_every_window_is_unmapped_and_a_dip_at_the_very_end_too(h3_dir, tmp_path):
    report_in = write(tmp_path / "analytics.json", analytics([{"t": 45.0, "drop_pct": 9}, {"t": 40.0, "drop_pct": 8}]))
    report = rr.retention_report(h3_dir, report_in)
    assert report["dips"] == []
    assert [u["t"] for u in report["unmapped"]] == [40.0, 45.0]
    assert report["unmapped"][0] == {"t": 40.0, "drop_pct": 8}


def test_dips_come_back_sorted_by_time(h3_dir, tmp_path):
    report_in = write(tmp_path / "analytics.json", analytics([{"t": 35.0, "drop_pct": 1}, {"t": 2.0, "drop_pct": 2}]))
    report = rr.retention_report(h3_dir, report_in)
    assert [d["t"] for d in report["dips"]] == [2.0, 35.0]
    assert [d["shot_id"] for d in report["dips"]] == ["EP1-A", "EP1-C"]


def test_two_h3_episodes_use_the_episode_named_in_the_analytics(tmp_path):
    build = tmp_path / "two_h3"
    build.mkdir()
    write(build / "story_h3.json", h3_story({"EP1": [("EP1-A", 0.0, 10.0)],
                                             "EP2": [("EP2-A", 0.0, 5.0), ("EP2-B", 5.0, 9.0)]}))
    report_in = write(tmp_path / "analytics.json", analytics([{"t": 6.0, "drop_pct": 4}], episode="EP2"))
    report = rr.retention_report(build, report_in)
    assert report["episode"] == "EP2" and report["dips"][0]["shot_id"] == "EP2-B"


def test_two_v22_episodes_keep_their_own_windows(tmp_path):
    build = tmp_path / "two_v22"
    build.mkdir()
    write(build / "shots.json", [{"id": "A1", "episode": 1, "edit_frames": 240}, {"id": "B1", "episode": 2, "edit_frames": 480},
                                 {"id": "B2", "episode": 2, "edit_frames": 240}])
    report_in = write(tmp_path / "analytics.json", analytics([{"t": 5.0, "drop_pct": 4}], episode=2))
    report = rr.retention_report(build, report_in)
    assert report["dips"][0]["shot_id"] == "B1" and report["dips"][0]["window"] == [0.0, 20.0]


def test_without_an_episode_key_one_episode_is_used_and_two_are_refused(h3_dir, tmp_path):
    no_episode = {k: v for k, v in analytics([{"t": 1.0, "drop_pct": 1}]).items() if k != "episode"}
    report = rr.retention_report(h3_dir, write(tmp_path / "a.json", no_episode))
    assert report["episode"] == "EP1" and report["dips"][0]["shot_id"] == "EP1-A"

    build = tmp_path / "two_h3_noep"
    build.mkdir()
    write(build / "story_h3.json", h3_story({"EP1": [("EP1-A", 0.0, 1.0)], "EP2": [("EP2-A", 0.0, 1.0)]}))
    with pytest.raises(ValueError, match="episode"):
        rr.retention_report(build, write(tmp_path / "b.json", no_episode))


def test_an_episode_missing_from_the_build_is_refused(h3_dir, tmp_path):
    with pytest.raises(ValueError, match="EP9"):
        rr.retention_report(h3_dir, write(tmp_path / "a.json", analytics([], episode="EP9")))


def test_the_report_is_written_into_the_build_dir(h3_dir, tmp_path):
    report = rr.retention_report(h3_dir, write(tmp_path / "a.json", analytics([{"t": 13.0, "drop_pct": 5}])))
    written = json.loads((h3_dir / "retention_dips.json").read_text(encoding="utf-8"))
    assert written == report


@pytest.mark.parametrize("bad", [
    "not json at all",
    json.dumps(["a", "list"]),
    json.dumps(analytics("nope")),
    json.dumps(analytics([{"t": 1.0}])),
    json.dumps(analytics([{"t": "31", "drop_pct": 1}])),
    json.dumps(analytics([{"t": True, "drop_pct": 1}])),
    json.dumps(analytics([{"t": -1.0, "drop_pct": 1}])),
    json.dumps({"episode": "EP1"}),                                           # no dips list
    json.dumps(analytics([{"t": 1.0, "drop_pct": 1}, "x"])),
])
def test_malformed_analytics_raises_value_error(h3_dir, tmp_path, bad):
    path = tmp_path / "bad.json"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError):
        rr.retention_report(h3_dir, path)


def test_missing_files_and_empty_build_dirs_raise_value_error(h3_dir, tmp_path):
    with pytest.raises(ValueError):
        rr.retention_report(h3_dir, tmp_path / "no_such_analytics.json")
    with pytest.raises(ValueError):
        rr.retention_report(tmp_path / "no_such_dir", write(tmp_path / "a.json", analytics([])))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        rr.retention_report(empty, write(tmp_path / "b.json", analytics([])))


def test_a_broken_story_file_raises_value_error_not_a_traceback(tmp_path):
    build = tmp_path / "broken"
    build.mkdir()
    (build / "story_h3.json").write_text("{ broken", encoding="utf-8")
    with pytest.raises(ValueError):
        rr.retention_report(build, write(tmp_path / "a.json", analytics([])))


def test_cli_exit_codes(h3_dir, tmp_path):
    good = write(tmp_path / "good.json", analytics([{"t": 31.0, "drop_pct": 2}]))
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert rr.main([str(h3_dir), str(good)]) == 0
    assert rr.main([str(h3_dir), str(bad)]) == 2
    assert rr.main([str(h3_dir), str(tmp_path / "missing.json")]) == 2
    with pytest.raises(SystemExit) as e:
        rr.main([str(h3_dir)])                                              # argparse: two arguments required
    assert e.value.code == 2


def test_cli_runs_as_a_module(h3_dir, tmp_path):
    good = write(tmp_path / "good.json", analytics([{"t": 31.0, "drop_pct": 2}]))
    done = subprocess.run([sys.executable, "-m", "core.retention_report", str(h3_dir), str(good)],
                          cwd=REPO, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert (h3_dir / "retention_dips.json").is_file()
    failed = subprocess.run([sys.executable, "-m", "core.retention_report", str(h3_dir), str(tmp_path / "nope.json")],
                            cwd=REPO, capture_output=True, text=True, timeout=120)
    assert failed.returncode == 2 and "retention_report" in failed.stderr
