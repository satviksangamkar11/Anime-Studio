"""Tests for core/timeline.py (WP4 part 1). Synthetic shots only; no network, no model calls."""
import copy

import pytest

from core import timeline as tl
from core.timeline import build_episodes, shot_editorial_frames, shot_id, shot_look, shot_shape
from h3.tests.synth import SPEECH_UTTERANCE, STAGE_TEXT, build_story

EPISODE_KEYS = {"key", "fps", "shots", "total_frames"}
SHOT_KEYS = {"id", "shape", "index", "start_frame", "frames", "look", "cast_ids", "beats", "impacts",
             "text", "first_dialogue", "dialogue_starts", "camera_moves", "caption_changes", "purpose",
             "sound_text", "problems", "raw"}
BEAT_KEYS = {"start_s", "end_s", "hold", "primary", "bhava", "acting", "reveal", "virtual"}
IMPACT_KEYS = {"at_frame", "at_s", "type", "frames"}


def v22(sid, episode, render=124, edit=None, beats=None, **extra):
    shot = {"id": sid, "episode": episode, "mode": "fl2va", "render_frames": render,
            "beats": beats if beats is not None else [{"t": [0.0, 1.0], "acting": f"{sid} acts"}]}
    if edit is not None:
        shot["edit_frames"] = edit
    shot.update(extra)
    return shot


def legacy(sid, episode, seconds=5.0, **extra):
    shot = {"id": sid, "episode": episode, "seconds": seconds, "style": "flat colour",
            "world": "a temple", "action": "she waves", "camera": "Static, locked off.", "sound": "wind"}
    shot.update(extra)
    return shot


def assert_p0(entries):
    assert entries, "expected at least one P0 entry"
    for e in entries:
        assert e["rule"] == "P0" and e["level"] == "FAIL"
        assert set(e) == {"rule", "level", "shot", "episode", "message"}


def test_shape_and_helper_functions():
    assert shot_shape(v22("S", 1)) == "v22"
    assert shot_shape(legacy("L", 1)) == "legacy"
    assert shot_shape({"shot_id": "X", "timing_and_lattice": {}}) == "h3"
    assert shot_id({"shot_id": "X", "timing_and_lattice": {}}) == "X"
    assert shot_id(legacy("L", 1)) == "L"
    assert shot_look({"id": "L", "look": {"a": 1}}) == {"a": 1}
    assert shot_look("junk") is None
    assert shot_editorial_frames(v22("S", 1, render=124, edit=100), 24) == 100
    assert shot_editorial_frames(v22("S", 1, render=124), 24) == 124


def test_v22_grouping_order_and_lengths():
    shots = [v22("S1", 1, render=124), v22("S3", 2, render=107),
             v22("S2", 1, render=141, edit=100), v22("S4", 2, render=124, edit=60)]
    eps, problems = build_episodes(shots)
    assert problems == []
    assert [e["key"] for e in eps] == [1, 2]
    e1, e2 = eps
    assert [s["id"] for s in e1["shots"]] == ["S1", "S2"]
    assert [s["start_frame"] for s in e1["shots"]] == [0, 124]
    assert [s["frames"] for s in e1["shots"]] == [124, 100]
    assert [s["index"] for s in e1["shots"]] == [0, 1]
    assert e1["total_frames"] == 224
    assert e1["fps"] == 24
    assert [s["start_frame"] for s in e2["shots"]] == [0, 107]
    assert [s["frames"] for s in e2["shots"]] == [107, 60]
    assert e2["total_frames"] == 167
    assert all(s["shape"] == "v22" for s in e1["shots"] + e2["shots"])


def test_v22_beats_shifted_clipped_and_impacts_shifted():
    beats = [{"t": [0.0, 0.8], "acting": "lifts", "bhava": "resolve"},
             {"t": [0.8, 2.0], "acting": "holds", "hold": True, "primary": True, "reveal": True},
             {"t": [4.0, 5.0], "acting": "tail"},      # clipped at the 100-frame edit end
             {"t": [4.5, 5.5], "acting": "gone"}]      # starts after the edit end: dropped
    first = v22("S1", 1, render=124)
    second = v22("S2", 1, render=124, edit=100, beats=beats,
                 look={"impact_frames": [{"at_s": 2.1, "type": "white_out", "frames": 2}]})
    eps, problems = build_episodes([first, second])
    assert problems == []
    s2 = eps[0]["shots"][1]
    assert s2["start_frame"] == 124
    t0 = 124 / 24
    assert len(s2["beats"]) == 3
    assert s2["beats"][0]["start_s"] == pytest.approx(t0 + 0.0)
    assert s2["beats"][0]["end_s"] == pytest.approx(t0 + 0.8)
    assert s2["beats"][0]["bhava"] == "resolve"
    assert s2["beats"][1]["hold"] is True and s2["beats"][1]["primary"] is True
    assert s2["beats"][1]["reveal"] is True and s2["beats"][1]["virtual"] is False
    assert s2["beats"][2]["end_s"] == pytest.approx(t0 + 100 / 24)
    assert s2["impacts"] == [{"at_frame": 174, "at_s": pytest.approx(174 / 24), "type": "white_out", "frames": 2}]


def test_h3_story_episodes_starts_lengths_and_look(tmp_path):
    story = build_story(str(tmp_path))
    shots = story["episodes"][0]["shots"]
    shots[1]["metadata"] = {"look": {"palette_id": "syn", "act": "HOOK",
                                     "impact_frames": [{"at_s": 1.0, "type": "white_out", "frames": 2}]},
                            "purpose": "Synthetic purpose."}
    # The V4 fixture is pure Foley (no speech, one character): inject the speech and the second character this test reads.
    shots[1]["dialogue_and_lip_lock"]["utterances"] = [copy.deepcopy(SPEECH_UTTERANCE)]
    shots[2]["continuity_and_seam_lock"]["subjects_present"] = ["char_alpha", "char_beta"]
    eps, problems = build_episodes(story)
    assert problems == []
    ep = eps[0]
    assert ep["key"] == "SYN_EP1"
    assert ep["total_frames"] == 453
    assert [s["start_frame"] for s in ep["shots"]] == [0, 145, 278]
    assert [s["frames"] for s in ep["shots"]] == [145, 133, 175]
    assert all(s["shape"] == "h3" for s in ep["shots"])
    b = ep["shots"][1]
    assert b["look"]["palette_id"] == "syn"
    assert b["purpose"] == "Synthetic purpose."
    assert b["sound_text"].startswith("Rain on wet stone")
    assert b["impacts"][0]["at_frame"] == 169
    assert b["cast_ids"] == ["char_alpha"]
    assert ep["shots"][2]["cast_ids"] == ["char_alpha", "char_beta"]
    assert b["camera_moves"] == [pytest.approx(145 / 24)]
    assert b["dialogue_starts"] == [pytest.approx(145 / 24)]
    assert b["first_dialogue"] == "Hold the line until the bell."
    assert ep["shots"][0]["look"] is None


def test_h3_virtual_beats_shifted_by_trim_in_and_flagged(tmp_path):
    eps, problems = build_episodes(build_story(str(tmp_path)))
    assert problems == []
    b = eps[0]["shots"][1]                       # SYN_B: trim_in 12, editorial 133, starts at frame 145
    beats = b["beats"]
    assert len(beats) == 6                       # stage 7 starts after the 133-frame editorial window
    assert all(x["virtual"] is True and x["reveal"] is False for x in beats)
    assert beats[0]["start_s"] == pytest.approx(145 / 24)
    assert beats[0]["end_s"] == pytest.approx((145 + 13) / 24)
    assert beats[1]["start_s"] == pytest.approx((145 + 13) / 24)
    assert beats[5]["end_s"] == pytest.approx((145 + 133) / 24)  # stage 6 clipped to the editorial end
    assert beats[5]["acting"] == STAGE_TEXT["6_impact_result"]
    assert [x["hold"] for x in beats] == [True, True, True, True, False, False]
    assert [x["primary"] for x in beats] == [False, False, False, False, False, True]
    assert len(eps[0]["shots"][0]["beats"]) == 6  # SYN_A: trim_in 0, stage 7 starts at 150 > 145
    assert len(eps[0]["shots"][2]["beats"]) == 7  # SYN_C: 175 editorial frames, all seven stages


def test_legacy_flat_shot_has_no_beats_and_a_problem():
    eps, problems = build_episodes([legacy("L1", 1)])
    assert problems == []
    s = eps[0]["shots"][0]
    assert s["shape"] == "legacy"
    assert s["frames"] == 124
    assert s["beats"] == []
    assert "no beats" in s["problems"]
    assert s["camera_moves"] == []
    assert "she waves" in s["text"]["prompt"]
    assert s["sound_text"] == "wind"


@pytest.mark.parametrize("bad", [None, "x", 42, {"nope": 1}])
def test_bad_container_is_one_p0(bad):
    eps, problems = build_episodes(bad)
    assert eps == []
    assert len(problems) == 1
    assert_p0(problems)


def test_list_of_junk_items_gives_one_p0_each():
    eps, problems = build_episodes([1, 2])
    assert eps == []
    assert len(problems) == 2
    assert_p0(problems)


def test_bad_seconds_skips_only_that_shot():
    bad = legacy("BAD", 1, seconds="a")
    eps, problems = build_episodes([bad, v22("S1", 1)])
    assert [s["id"] for s in eps[0]["shots"]] == ["S1"]
    assert eps[0]["shots"][0]["start_frame"] == 0
    assert [p["shot"] for p in problems] == ["BAD"]
    assert_p0(problems)


def test_negative_edit_frames_is_p0_and_shot_skipped():
    eps, problems = build_episodes([v22("N1", 1, render=124, edit=-5), v22("OK", 1)])
    assert [s["id"] for s in eps[0]["shots"]] == ["OK"]
    assert [p["shot"] for p in problems] == ["N1"]
    assert_p0(problems)


def test_malformed_beat_time_is_p0():
    shot = v22("B1", 1, beats=[{"t": ["a", 1], "acting": "x"}])
    eps, problems = build_episodes([shot])
    assert eps == []
    assert [p["shot"] for p in problems] == ["B1"]
    assert_p0(problems)


def test_missing_id_is_p0_with_null_shot():
    eps, problems = build_episodes([{"episode": 1, "render_frames": 124, "beats": []}])
    assert eps == []
    assert problems[0]["shot"] is None
    assert_p0(problems)


def test_bare_h3_shot_list_is_p0(tmp_path):
    story = build_story(str(tmp_path))
    eps, problems = build_episodes(story["episodes"][0]["shots"])
    assert eps == []
    assert len(problems) == 3
    assert_p0(problems)


def test_h3_episode_without_shots_is_p0_and_others_built(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"].append({"episode_id": "EMPTY", "shots": []})
    eps, problems = build_episodes(story)
    assert [e["key"] for e in eps] == ["SYN_EP1"]
    assert len(eps[0]["shots"]) == 3
    assert any("EMPTY" in p["message"] for p in problems)
    assert_p0(problems)


def test_h3_story_without_episodes_list_is_p0():
    eps, problems = build_episodes({"registry": {}})
    assert eps == []
    assert_p0(problems)


def test_bad_fps_is_p0():
    eps, problems = build_episodes([v22("S1", 1)], fps=0)
    assert eps == []
    assert_p0(problems)


def test_non_dict_look_becomes_none_with_problem():
    eps, problems = build_episodes([v22("S1", 1, look="bad")])
    s = eps[0]["shots"][0]
    assert s["look"] is None
    assert any("look" in p for p in s["problems"])
    assert problems == []


def test_malformed_impact_entries_are_skipped_with_problem():
    look = {"impact_frames": [{"at_s": "x", "type": "white_out", "frames": 2},
                              {"at_s": 1.0, "type": "white_out", "frames": 2}]}
    eps, problems = build_episodes([v22("S1", 1, look=look)])
    s = eps[0]["shots"][0]
    assert len(s["impacts"]) == 1
    assert any("impact" in p for p in s["problems"])
    assert problems == []


def test_missing_director_import_is_reported_once(monkeypatch):
    monkeypatch.setattr(tl, "_h3d", None)
    monkeypatch.setattr(tl, "_H3D_ERROR", "simulated")
    no_director_needed = {"id": "E1", "episode": 1, "beats": [{"t": [0.0, 1.0], "acting": "a"}], "edit_frames": 50}
    eps, problems = build_episodes([no_director_needed, v22("S2", 1, render=124)])
    assert [s["id"] for s in eps[0]["shots"]] == ["E1"]
    assert [p["shot"] for p in problems] == [None, "S2"]          # one import P0, then the shot that needed it
    assert_p0(problems)


def test_pure_function_same_result_and_no_mutation(tmp_path):
    story = build_story(str(tmp_path))
    before = copy.deepcopy(story)
    first = build_episodes(story)
    second = build_episodes(story)
    assert first == second
    assert story == before


def test_structure_matches_contract(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][1]["metadata"] = {
        "look": {"impact_frames": [{"at_s": 1.0, "type": "white_out", "frames": 2}]}}
    eps, problems = build_episodes(story)
    assert problems == []
    eps_v, _ = build_episodes([v22("S1", 1, look={"impact_frames": [{"at_s": 0.5, "type": "black_out", "frames": 1}]})])
    for ep in eps + eps_v:
        assert set(ep) == EPISODE_KEYS
        for s in ep["shots"]:
            assert set(s) == SHOT_KEYS
            assert set(s["text"]) == {"prompt", "light_world"}
            for b in s["beats"]:
                assert set(b) == BEAT_KEYS
            for i in s["impacts"]:
                assert set(i) == IMPACT_KEYS
    assert eps[0]["shots"][1]["impacts"] and eps_v[0]["shots"][0]["impacts"]


def test_v4_row_clock_is_the_editorial_length_not_the_pixel_frames():
    from core import timeline
    row = {"lattice_n": 9, "pixel_frames": 158, "editorial_duration_sec": 6.0, "seconds": 6.0}
    assert timeline.shot_editorial_frames(row) == 144
