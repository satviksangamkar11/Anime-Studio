"""Tests for timeline_lock_core."""

import math

import timeline_lock_core


def test_fps_constant():
    assert timeline_lock_core.FPS == 24


def test_lattice_frames_valid():
    assert timeline_lock_core.lattice_frames(6) == 107
    assert timeline_lock_core.lattice_frames(10) == 175
    assert timeline_lock_core.lattice_frames(9) == 158
    assert timeline_lock_core.lattice_frames(12) == 209
    assert timeline_lock_core.lattice_frames(14) == 243
    assert timeline_lock_core.lattice_frames(20) == 345


def test_lattice_frames_invalid():
    for n in (0, -1, -5, 5, 21):
        try:
            timeline_lock_core.lattice_frames(n)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for n={n}")


def test_fit_lattice_values():
    assert timeline_lock_core.fit_lattice(22) == 107
    assert timeline_lock_core.fit_lattice(176) == 192
    assert timeline_lock_core.fit_lattice(175) == 175
    assert timeline_lock_core.fit_lattice(158) == 158
    assert timeline_lock_core.fit_lattice(209) == 209
    assert timeline_lock_core.fit_lattice(243) == 243
    assert timeline_lock_core.fit_lattice(1) == 107


def test_fit_lattice_clamps_107():
    assert timeline_lock_core.fit_lattice(1) == 107
    assert timeline_lock_core.fit_lattice(107) == 107
    assert timeline_lock_core.fit_lattice(108) == 124


def test_fit_lattice_raises_above_345():
    assert timeline_lock_core.fit_lattice(345) == 345
    try:
        timeline_lock_core.fit_lattice(346)
    except ValueError:
        return
    raise AssertionError("expected ValueError for 346 frames")


def test_edit_frames_no_float_overshoot():
    for n in range(1, 2001):
        assert timeline_lock_core.edit_frames_for_shot({"en": n / 24}, margin_frames=0) == n


def test_margin_negative_refused():
    for bad in (-1, True):
        try:
            timeline_lock_core.edit_frames_for_shot({"en": 1.0}, margin_frames=bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for margin {bad!r}")


def test_min_seconds_silent_shot():
    assert timeline_lock_core.edit_frames_for_shot({}, min_seconds=3.0) == 72


def test_edit_frames_for_shot_basic():
    assert timeline_lock_core.edit_frames_for_shot({"en": 1.0}) == 30
    assert timeline_lock_core.edit_frames_for_shot({"en": 1.0, "fr": 2.0}) == 54


def test_edit_frames_for_shot_margin():
    assert timeline_lock_core.edit_frames_for_shot({"en": 1.0}, margin_frames=0) == 24


def test_edit_frames_for_shot_empty():
    try:
        timeline_lock_core.edit_frames_for_shot({})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty dict")


def test_edit_frames_for_shot_negative():
    try:
        timeline_lock_core.edit_frames_for_shot({"en": -1.0})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for negative seconds")


def test_edit_frames_for_shot_non_finite():
    for bad in (math.inf, -math.inf, math.nan):
        try:
            timeline_lock_core.edit_frames_for_shot({"en": bad})
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")


# bar_candidate was deleted (card S-01). The same cases now go through choose(..., snap=True), beat only.
def test_bar_candidate_128():
    c = timeline_lock_core.choose(40, 128.0, 0, True)
    assert c == {"method": "beat", "frames": 45, "beats": 4, "error_ms": 0.0, "spare": 5}


def test_bar_candidate_176():
    c = timeline_lock_core.choose(85, 176.0, 0, True)
    assert c == {"method": "beat", "frames": 90, "beats": 11, "error_ms": 0.0, "spare": 5}


def test_bar_candidate_60():
    c = timeline_lock_core.choose(25, 60.0, 0, True)
    assert c["frames"] == 48
    assert c["beats"] == 2


def test_bar_candidate_120():
    c = timeline_lock_core.choose(10, 120.0, 0, True)
    assert c["frames"] == 12
    assert c["beats"] == 1


def test_bar_candidate_none_when_no_exact():
    # no bar exists for 1000 frames at 100 BPM any more; the beat cut is the 70th beat, 1008 frames
    c = timeline_lock_core.choose(1000, 100.0, 0, True)
    assert c["beats"] == 70
    assert c["frames"] == 1008


def test_beat_candidate_60_need_25():
    c = timeline_lock_core.beat_candidate(25, 60.0, 0)
    assert c["frames"] == 48
    assert c["beats"] == 2
    assert c["error_ms"] == 0.0


def test_beat_candidate_error_bounded():
    for bpm in (128.0, 176.0):
        g = 60.0 / bpm * 24
        worst = 0.0
        for k in range(1, 201):
            need = round((k - 1) * g) + 1
            c = timeline_lock_core.beat_candidate(need, bpm, 0)
            assert c["beats"] == k
            assert c["frames"] == round(k * g)
            worst = max(worst, c["error_ms"])
        assert worst <= 20.84


def test_choose_free():
    c = timeline_lock_core.choose(100, None)
    assert c == {"method": "free", "frames": 100, "beats": None, "error_ms": 0.0, "spare": 0}


def test_choose_tie_goes_to_bar():
    # bar was the tie winner before; now a 24-frame need at 60 BPM is one beat, exactly 24 frames
    c = timeline_lock_core.choose(24, 60.0, 0, True)
    assert c["method"] == "beat"
    assert c["frames"] == 24
    assert c["spare"] == 0


def test_choose_fewer_spare():
    c = timeline_lock_core.choose(40, 128.0, 0, True)
    assert c["method"] == "beat"
    assert c["frames"] == 45
    assert c["spare"] == 5


def test_choose_snap_false_is_free():
    c = timeline_lock_core.choose(20, 128.0)
    assert c == {"method": "free", "frames": 20, "beats": None, "error_ms": 0.0, "spare": 0}


def test_plan_shots_basic():
    shots = [{"id": "a", "bpm": 128.0}, {"id": "b", "bpm": None}]
    voice = {"a": {"en": 5.75}, "b": {"en": 5.75}}
    plan = timeline_lock_core.plan_shots(shots, voice)
    assert plan[0]["id"] == "a"
    assert plan[0]["start_frame"] == 0
    assert plan[1]["id"] == "b"
    assert plan[1]["start_frame"] == plan[0]["edit_frames"]


def test_plan_shots_missing_id_keyerror():
    # card S-01: the KeyError became ValueError with the shot id and a fixed message
    shots = [{"id": "a", "bpm": None}, {"id": "missing", "bpm": None}]
    voice = {"a": {"en": 5.75}}
    try:
        timeline_lock_core.plan_shots(shots, voice)
    except ValueError as exc:
        assert str(exc) == "missing: no voice seconds and no min_seconds"
    else:
        raise AssertionError("expected ValueError")


def test_plan_shots_act_reset():
    shots = [
        {"id": "a", "bpm": 128.0},
        {"id": "b", "bpm": 176.0},
        {"id": "c", "bpm": 128.0},
    ]
    voice = {"a": {"en": 5.75}, "b": {"en": 5.75}, "c": {"en": 5.75}}
    plan = timeline_lock_core.plan_shots(shots, voice)
    assert plan[0]["start_frame"] == 0
    assert plan[1]["start_frame"] == plan[0]["edit_frames"]
    assert plan[2]["start_frame"] == plan[1]["start_frame"] + plan[1]["edit_frames"]


def test_plan_shots_inputs_not_mutated():
    shots = [{"id": "a", "bpm": 128.0}, {"id": "b", "bpm": None}]
    voice = {"a": {"en": 5.75}, "b": {"en": 5.75}}
    shots_copy = [dict(s) for s in shots]
    voice_copy = {k: dict(v) for k, v in voice.items()}
    timeline_lock_core.plan_shots(shots, voice)
    assert shots == shots_copy
    assert voice == voice_copy


def test_plan_shots_pixel_frames_lattice():
    shots = [{"id": "a", "bpm": None}, {"id": "b", "bpm": None}]
    voice = {"a": {"en": 5.75}, "b": {"en": 5.75}}
    plan = timeline_lock_core.plan_shots(shots, voice)
    for row in plan:
        pf = row["pixel_frames"]
        assert (pf - 5) % 17 == 0
        assert 107 <= pf <= 345


def test_bar_candidate_zero_need_raises():
    try:
        timeline_lock_core.choose(0, 120.0, 0, True)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for need_frames=0")


def test_beat_candidate_zero_need_raises():
    try:
        timeline_lock_core.beat_candidate(0, 120.0, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for need_frames=0")


def test_choose_zero_need_raises():
    try:
        timeline_lock_core.choose(0, 120.0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for need_frames=0")


def test_beat_candidate_successive_beats_error_bounded():
    for bpm in (128.0, 176.0):
        grid = 60.0 / bpm * timeline_lock_core.FPS
        for k in range(1, 201):
            need = round((k - 1) * grid) + 1
            c = timeline_lock_core.beat_candidate(need, bpm, 0)
            assert c["beats"] == k
            assert c["error_ms"] <= 20.84


def test_choose_act_reset_uses_zero_start_offset():
    # second act (176 BPM) starts at offset 0: need 144 -> 18 beats = 147 frames, spare 3
    shots = [{"id": "a", "bpm": 128.0, "snap": True}, {"id": "b", "bpm": 176.0, "snap": True}]
    voice = {"a": {"en": 5.75}, "b": {"en": 5.75}}
    plan = timeline_lock_core.plan_shots(shots, voice)
    assert plan[1]["edit_frames"] == 147
    assert plan[1]["beats"] == 18


def test_choose_beat_example_20_at_128():
    c = timeline_lock_core.choose(20, 128.0, 0, True)
    assert c["method"] == "beat"
    assert c["frames"] == 22
    assert c["beats"] == 2
    assert c["spare"] == 2


def test_choose_beat_example_30_at_128_offset_22():
    c = timeline_lock_core.choose(30, 128.0, 22, True)
    assert c["method"] == "beat"
    assert c["beats"] == 5
    assert c["frames"] == 34


def test_choose_picks_beat_when_fewer_spare_than_bar():
    # 20 frames at 128 BPM: snapped -> beat 2 (22 frames, spare 2); not snapped -> free 20
    c = timeline_lock_core.choose(20, 128.0, 0, True)
    assert c["method"] == "beat"
    assert c["spare"] == 2
    assert timeline_lock_core.choose(20, 128.0)["spare"] == 0


def test_beat_uses_round_not_floor():
    c = timeline_lock_core.beat_candidate(34, 128.0, 0)
    assert c["beats"] == 3
    assert c["frames"] == 34


def test_beat_respects_in_act_offset():
    c = timeline_lock_core.beat_candidate(30, 128.0, 0, start_in_act_frames=22)
    assert c["beats"] == 5
    assert c["frames"] == 34


def test_plan_shots_single_free_shot_pixel_73():
    # a one-shot list has no cut and no lattice pick: it raises (the old 30/73 result is gone)
    try:
        timeline_lock_core.plan_shots([{"id": "S", "bpm": None}], {"S": {"en": 5.75}})
    except ValueError:
        return
    raise AssertionError("expected ValueError for a one-shot list")


def test_plan_shots_tail_handle_changes_pixels():
    # tail_handle / head_handle arguments were removed; the handles come from the H3 rules now
    shots = [{"id": "a", "bpm": None}, {"id": "b", "bpm": None}]
    voice = {"a": {"en": 5.75}, "b": {"en": 5.75}}
    try:
        timeline_lock_core.plan_shots(shots, voice, tail_handle=0)
    except TypeError:
        return
    raise AssertionError("expected TypeError for tail_handle")


def test_bar_error_ms_is_real_rhythm_error_when_off_grid():
    # beat path from offset 22: need 40 -> 6 beats = 68 - 22 = 46 frames; cut sits 0.5 frame off the grid
    c = timeline_lock_core.choose(40, 128.0, 22, True)
    assert c["method"] == "beat"
    assert c["frames"] == 46
    assert abs(c["error_ms"] - 20.833) < 0.01


def test_bar_error_ms_zero_on_grid():
    c = timeline_lock_core.choose(40, 128.0, 0, True)
    assert c["error_ms"] == 0.0


def test_edit_frames_huge_seconds_refused():
    try:
        timeline_lock_core.edit_frames_for_shot({"en": 1e308})
    except ValueError:
        return
    raise AssertionError("expected ValueError for 1e308 seconds")


def test_edit_frames_huge_int_seconds_refused():
    # observer 5: a large int must raise ValueError, not OverflowError
    try:
        timeline_lock_core.edit_frames_for_shot({"en": 10**1000})
    except ValueError:
        return
    raise AssertionError("expected ValueError for 10**1000 seconds")


def test_edit_frames_fractional_seconds_ceil():
    # 1.01 s * 24 = 24.24 -> ceil 25, + 6 margin = 31
    assert timeline_lock_core.edit_frames_for_shot({"en": 1.01}) == 31


def _raises_promptly(fn, *args, timeout=5.0):
    # Runs fn in a daemon thread so a non-terminating search fails the test instead of hanging the run.
    # A thread still looping after the timeout keeps running in the background until the process exits.
    import threading

    box = {}

    def runner():
        try:
            box["result"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001
            box["exc"] = exc

    worker = threading.Thread(target=runner, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise AssertionError("call did not return or raise within %s s" % timeout)
    if "exc" in box:
        raise box["exc"]
    return box.get("result")


def test_bar_candidate_bpm_1e9_refused():
    # bound (seventh run): bpm must be finite and within 20-400 (bar_candidate removed; choose snaps via beat)
    import pytest

    with pytest.raises(ValueError):
        _raises_promptly(timeline_lock_core.choose, 20, 1e9, 0, True)


def test_bar_candidate_bpm_10_refused():
    import pytest

    with pytest.raises(ValueError):
        _raises_promptly(timeline_lock_core.choose, 20, 10.0, 0, True)


def test_bar_candidate_bpm_nan_refused():
    import pytest

    with pytest.raises(ValueError):
        _raises_promptly(timeline_lock_core.choose, 20, float("nan"), 0, True)


def test_beat_candidate_bpm_1e9_refused_promptly():
    # bound (seventh run): must raise promptly, not search forever
    import pytest

    with pytest.raises(ValueError):
        _raises_promptly(timeline_lock_core.beat_candidate, 1000, 1e9, 0)


def test_beat_candidate_bpm_10_refused():
    import pytest

    with pytest.raises(ValueError):
        _raises_promptly(timeline_lock_core.beat_candidate, 20, 10.0, 0)


def test_beat_candidate_bpm_nan_refused():
    import pytest

    with pytest.raises(ValueError):
        _raises_promptly(timeline_lock_core.beat_candidate, 20, float("nan"), 0)


# ---- card S-01 new tests: hand-checked values from the trims, beat and snap tables ----

_VOICE_5_75 = {"en": 5.75}  # 138 frames + margin 6 = 144


def test_plan_three_free_shots_trims():
    shots = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    voice = {"a": _VOICE_5_75, "b": _VOICE_5_75, "c": _VOICE_5_75}
    plan = timeline_lock_core.plan_shots(shots, voice)
    assert [r["start_frame"] for r in plan] == [0, 144, 288]
    assert [r["edit_frames"] for r in plan] == [144, 144, 144]
    # (pixel, trim_in, trim_out, head, tail) from the trims table
    expect = [(175, 0, 144, 0, 31), (192, 8, 152, 8, 40), (158, 14, 158, 14, 0)]
    for row, (pf, tin, tout, head, tail) in zip(plan, expect):
        assert (row["pixel_frames"], row["trim_in_frame"], row["trim_out_frame"]) == (pf, tin, tout)
        assert (row["head_handle"], row["tail_handle"]) == (head, tail)


def test_middle_shot_too_short_raises():
    # middle shot of 44 frames: 38/24 s + margin 6
    shots = [{"id": "a"}, {"id": "m"}, {"id": "c"}]
    voice = {"a": _VOICE_5_75, "m": {"en": 38 / 24}, "c": _VOICE_5_75}
    try:
        timeline_lock_core.plan_shots(shots, voice)
    except ValueError:
        return
    raise AssertionError("expected ValueError for a 44-frame middle shot")


def test_middle_shot_max_258():
    # 252/24 s + margin 6 = 258: pixel 311, trims 8/266. 259 frames (253/24 s) must raise.
    shots = [{"id": "a"}, {"id": "m"}, {"id": "c"}]
    voice = {"a": _VOICE_5_75, "m": {"en": 252 / 24}, "c": _VOICE_5_75}
    mid = timeline_lock_core.plan_shots(shots, voice)[1]
    assert mid["edit_frames"] == 258
    assert mid["pixel_frames"] == 311
    assert (mid["trim_in_frame"], mid["trim_out_frame"]) == (8, 266)
    voice["m"] = {"en": 253 / 24}
    try:
        timeline_lock_core.plan_shots(shots, voice)
    except ValueError:
        return
    raise AssertionError("expected ValueError for a 259-frame middle shot")


def test_beat_error_le_half_frame():
    # beat-errors table: (need, bpm, start, expected frames, expected error_ms)
    cases = [
        (144, 128.0, 0, 146, 10.4167),
        (100, 128.0, 146, 102, 20.8333),
        (90, 176.0, 0, 90, 0.0),
        (91, 176.0, 0, 98, 7.5758),
    ]
    limit = 1000 / 48 + 1e-9
    for need, bpm, start, frames, err in cases:
        c = timeline_lock_core.choose(need, bpm, start, True)
        assert c["frames"] == frames
        assert abs(c["error_ms"] - err) < 0.001
        assert c["error_ms"] <= limit
    free = timeline_lock_core.choose(100, 60.0, 0, False)
    assert free["frames"] == 100 and free["error_ms"] == 0.0


def test_snap_only_groove_shots():
    # snap table: g1 and g2 snap; the last of act 1 does not; the first of act 2 (60 BPM) resets the act
    shots = [
        {"id": "g1", "bpm": 128.0, "snap": True},
        {"id": "g2", "bpm": 128.0, "snap": True},
        {"id": "last", "bpm": 128.0, "snap": False},
        {"id": "first60", "bpm": 60.0, "snap": False},
    ]
    voice = {
        "g1": {"en": 5.75},
        "g2": {"en": 94 / 24},
        "last": {"en": 44 / 24},
        "first60": {"en": 94 / 24},
    }
    plan = timeline_lock_core.plan_shots(shots, voice)
    assert [r["edit_frames"] for r in plan] == [146, 102, 50, 100]
    assert [r["start_frame"] for r in plan] == [0, 146, 248, 298]
    assert plan[3]["act_start_frame"] == 298
    assert plan[2]["act_start_frame"] == 0


def test_cue_change_resets_act():
    shots = [{"id": "a", "bpm": 128.0, "cue": "c1"}, {"id": "b", "bpm": 128.0, "cue": "c2"}]
    voice = {"a": _VOICE_5_75, "b": _VOICE_5_75}
    plan = timeline_lock_core.plan_shots(shots, voice)
    assert plan[1]["start_frame"] == 144
    assert plan[1]["act_start_frame"] == plan[1]["start_frame"] == 144


def test_end_frame_position_is_trim_out_minus_1():
    shots = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    voice = {"a": _VOICE_5_75, "b": _VOICE_5_75, "c": _VOICE_5_75}
    for row in timeline_lock_core.plan_shots(shots, voice):
        assert row["end_frame_position"] == row["trim_out_frame"] - 1
