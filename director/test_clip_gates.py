"""Tests for director/clip_gates.py (spec J13). Inputs are plain lists and tiny arrays; expectations hand-worked.

Hand arithmetic used below:
- tail_spike fixtures use 60 frames: head_skip 10, tail_frames 30. The median window is flow[10:30] (20 values)
  and the tail is indices 30..59.
- A flat flow of 1.0 gives median 1.0, so the spike threshold is ratio * 1.0 = 2.2.
"""
import numpy as np
import pytest

from clip_gates import (
    ClipGateError,
    tail_spike,
    suggest_trim_out,
    best_cut_frame,
    end_frame_pass,
    scene_cut,
    new_object_classes,
    flicker_score,
    verdict,
)


def flat_flow(n=60, value=1.0):
    return [value] * n


# ---------- tail_spike ----------

def test_flat_flow_has_no_flag():
    # median of flow[10:30] = 1.0; tail max = 1.0; ratio = 1.0 / 1.0
    res = tail_spike(flat_flow())
    assert res["flag"] is False
    assert res["first_spike_index"] is None
    assert res["median"] == pytest.approx(1.0)
    assert res["ratio"] == pytest.approx(1.0)


def test_spike_in_last_30_frames_flags_first_index():
    # flow[45] = 3.0 and flow[50] = 4.0 are in the tail (30..59); threshold 2.2 * 1.0 = 2.2
    # first index above 2.2 is 45; ratio = max(tail) / median = 4.0 / 1.0
    flow = flat_flow()
    flow[45] = 3.0
    flow[50] = 4.0
    res = tail_spike(flow)
    assert res["flag"] is True
    assert res["first_spike_index"] == 45
    assert res["ratio"] == pytest.approx(4.0)
    assert res["median"] == pytest.approx(1.0)


def test_threshold_is_strictly_greater():
    # 2.2 is not > 2.2 * 1.0, so index 40 is not a spike; 2.3 at index 41 is
    flow = flat_flow()
    flow[40] = 2.2
    flow[41] = 2.3
    res = tail_spike(flow)
    assert res["flag"] is True
    assert res["first_spike_index"] == 41
    assert res["ratio"] == pytest.approx(2.3)


def test_threshold_exact_value_alone_not_flagged():
    flow = flat_flow()
    flow[40] = 2.2
    res = tail_spike(flow)
    assert res["flag"] is False
    assert res["first_spike_index"] is None


def test_spike_in_head_is_ignored():
    # index 5 is before head_skip 10, so it is neither in the median nor in the tail
    flow = flat_flow()
    flow[5] = 10.0
    res = tail_spike(flow)
    assert res["flag"] is False
    assert res["first_spike_index"] is None
    assert res["ratio"] == pytest.approx(1.0)


def test_spike_before_tail_is_not_reported():
    # index 29 is in the median window (10..29), not in the tail (30..59).
    # median of 20 values, nineteen 1.0 and one 5.0: the 10th and 11th sorted values are both 1.0 -> median 1.0
    flow = flat_flow()
    flow[29] = 5.0
    res = tail_spike(flow)
    assert res["median"] == pytest.approx(1.0)
    assert res["flag"] is False


def test_zero_median_raises():
    with pytest.raises(ClipGateError):
        tail_spike(flat_flow(60, 0.0))


def test_too_short_raises_and_minimum_length_ok():
    # minimum N = tail_frames + head_skip + 5 = 45
    with pytest.raises(ClipGateError):
        tail_spike(flat_flow(44))
    res = tail_spike(flat_flow(45))
    assert res["flag"] is False


def test_tail_spike_does_not_mutate_input():
    flow = flat_flow()
    flow[45] = 3.0
    before = list(flow)
    tail_spike(flow)
    assert flow == before


# ---------- suggest_trim_out ----------

def test_suggest_trim_out_back_4():
    assert suggest_trim_out(45) == 41  # 45 - 4


def test_suggest_trim_out_minimum_1_floor():
    assert suggest_trim_out(5) == 1  # max(1, 5 - 4) = 1
    assert suggest_trim_out(3) == 1  # max(1, 3 - 4 = -1) = 1


def test_suggest_trim_out_custom_back_and_minimum():
    assert suggest_trim_out(10, back=2) == 8
    assert suggest_trim_out(5, minimum=3) == 3  # max(3, 1) = 3


def test_suggest_trim_out_none_raises():
    with pytest.raises(ClipGateError):
        suggest_trim_out(None)


# ---------- best_cut_frame ----------

def test_best_cut_frame_offset():
    # max similarity 0.9 is at relative index 1 -> absolute frame 30 + 1 = 31
    assert best_cut_frame([0.2, 0.9, 0.5, 0.1], 30) == 31


def test_best_cut_frame_other_offset():
    # max 0.3 at relative index 1 -> 100 + 1 = 101
    assert best_cut_frame([0.1, 0.3, 0.2], 100) == 101


def test_best_cut_frame_tie_takes_first():
    # ties at relative 0 and 2 -> first one, 0 -> absolute 7
    assert best_cut_frame([0.8, 0.1, 0.8], 7) == 7


def test_best_cut_frame_empty_raises():
    with pytest.raises(ClipGateError):
        best_cut_frame([], 5)


# ---------- end_frame_pass ----------

def test_end_frame_pass_exact_thresholds_pass():
    # ssim 0.82 >= 0.82, lpips 0.18 <= 0.18, cosine 0.88 >= 0.88
    res = end_frame_pass(0.82, 0.18, 0.88)
    assert res["pass"] is True
    assert res["failed"] == []


def test_end_frame_pass_ssim_just_below_fails():
    res = end_frame_pass(0.81, 0.18, 0.88)
    assert res["pass"] is False
    assert len(res["failed"]) == 1
    assert "ssim" in res["failed"][0]


def test_end_frame_pass_lpips_just_above_fails():
    res = end_frame_pass(0.82, 0.181, 0.88)
    assert res["pass"] is False
    assert len(res["failed"]) == 1
    assert "lpips" in res["failed"][0]


def test_end_frame_pass_cosine_just_below_fails():
    res = end_frame_pass(0.82, 0.18, 0.879)
    assert res["pass"] is False
    assert len(res["failed"]) == 1
    assert "cosine" in res["failed"][0]


def test_end_frame_pass_all_fail_lists_three():
    res = end_frame_pass(0.1, 0.5, 0.1)
    assert res["pass"] is False
    assert len(res["failed"]) == 3


def test_end_frame_pass_legal_extremes_do_not_raise():
    assert end_frame_pass(1.0, 0.0, 1.0)["pass"] is True
    assert end_frame_pass(-1.0, 0.0, -1.0)["pass"] is False


def test_end_frame_pass_out_of_range_raises():
    with pytest.raises(ClipGateError):
        end_frame_pass(1.01, 0.1, 0.9)
    with pytest.raises(ClipGateError):
        end_frame_pass(0.9, 0.1, -1.01)
    with pytest.raises(ClipGateError):
        end_frame_pass(0.9, -0.1, 0.9)


# ---------- scene_cut ----------

def test_scene_cut_ignores_index_zero_and_reports_low_samples():
    # index 0 (0.1) is the reference and is never reported; index 2 (0.5) and index 4 (0.6) are below 0.75
    # index 3 is exactly 0.75, not below -> not reported
    assert scene_cut([0.1, 0.9, 0.5, 0.75, 0.6]) == [2, 4]


def test_scene_cut_start_index_limits_range():
    assert scene_cut([0.1, 0.9, 0.5, 0.75, 0.6], start_index=3) == [4]


def test_scene_cut_all_similar_is_empty():
    assert scene_cut([1.0, 0.95, 0.9]) == []


def test_scene_cut_start_index_zero_never_reports_reference():
    # round 9 (observer 8): start_index=0 must still skip the reference sample 0
    assert scene_cut([0.1, 0.9], start_index=0) == []
    assert scene_cut([0.1, 0.5], start_index=0) == [1]


# ---------- new_object_classes ----------

def make_counts():
    # 25 frames (index 0..24). person in every frame.
    # cat from frame 5 (present before frame 12, so not new at after_frame 12)
    # zebra only at frame 12 (first frame at or after 12)
    # dog from frame 20; ant only at frame 24
    counts = []
    for i in range(25):
        frame = {"person": 1}
        if i >= 5:
            frame["cat"] = 1
        if i == 12:
            frame["zebra"] = 1
        if i >= 20:
            frame["dog"] = 1
        if i == 24:
            frame["ant"] = 1
        counts.append(frame)
    return counts


def test_new_object_classes_at_default_after_frame_12():
    # person (frame 0) and cat (frame 5, before 12) are not new.
    # zebra (frame 12), dog (frame 20), ant (frame 24) are new; sorted alphabetically
    assert new_object_classes(make_counts()) == ["ant", "dog", "zebra"]


def test_new_object_classes_after_frame_20():
    # zebra at 12 is inside frames 0..19 -> not new now; dog (20) and ant (24) are new
    assert new_object_classes(make_counts(), after_frame=20) == ["ant", "dog"]


def test_class_present_from_start_is_not_new():
    counts = [{"person": 1} for _ in range(15)]
    counts[13] = {"person": 1, "dog": 1}
    # dog appears at 13 (>= 12) and never in 0..11 -> new
    assert new_object_classes(counts, after_frame=12) == ["dog"]
    # person is in frame 0 -> never new
    assert "person" not in new_object_classes(counts, after_frame=12)


def test_class_present_before_after_frame_is_not_new():
    counts = [{"person": 1} for _ in range(20)]
    for i in range(3, 20):
        counts[i]["cat"] = 1
    # cat present at frame 3, which is before 12 -> not new
    assert new_object_classes(counts, after_frame=12) == []


# ---------- review findings, round 10 (observer 9) ----------

def test_zero_count_class_is_not_new():
    # observer 9 (codex r1): a class whose count is 0 is absent, so it is never reported as new.
    counts = [{"person": 1} for _ in range(15)]
    counts[13] = {"person": 1, "owl": 0}
    assert new_object_classes(counts, after_frame=12) == []


def test_end_frame_pass_nan_raises():
    # observer 9 (spec J13 round-10 item 1): NaN is outside every legal range, so it must raise, not pass.
    with pytest.raises(ClipGateError):
        end_frame_pass(float("nan"), 0.1, 0.99)
    with pytest.raises(ClipGateError):
        end_frame_pass(0.9, float("nan"), 0.99)
    with pytest.raises(ClipGateError):
        end_frame_pass(0.9, 0.1, float("nan"))


def test_tail_spike_nan_input_raises():
    # observer 9 (spec J13 round-10 item 2): a NaN flow value makes the spike test silently False; must raise.
    flow = [1.0] * 60
    flow[45] = float("nan")
    with pytest.raises(ClipGateError):
        tail_spike(flow)


def test_scene_cut_nan_similarity_raises():
    # observer 9 (spec J13 round-10 item 3): a NaN similarity is not a cut; it must raise instead.
    with pytest.raises(ClipGateError):
        scene_cut([1.0, float("nan"), 1.0])


def test_flicker_nan_frame_raises():
    # observer 9 (spec J13 round-10 item 4): a NaN luma value makes the score NaN; must raise instead.
    frames = [np.zeros((2, 2)), np.full((2, 2), np.nan), np.zeros((2, 2))]
    with pytest.raises(ClipGateError):
        flicker_score(frames)


# ---------- flicker_score ----------

def test_flicker_constant_frames_zero():
    frames = [np.full((3, 3), 0.5) for _ in range(4)]
    assert flicker_score(frames) == pytest.approx(0.0)


def test_flicker_alternating_three_frames_is_two():
    # frames 0, 1, 0 per pixel: t=1 gives |0 - 2*1 + 0| = 2 for every pixel -> mean 2.0
    frames = [np.zeros((2, 2)), np.ones((2, 2)), np.zeros((2, 2))]
    assert flicker_score(frames) == pytest.approx(2.0)


def test_flicker_alternating_five_frames_is_two():
    # values 0,1,0,1,0: each interior t gives |x[t+1] - 2 x[t] + x[t-1]| = 2 -> mean 2.0
    frames = [np.zeros((2, 2)), np.ones((2, 2)), np.zeros((2, 2)), np.ones((2, 2)), np.zeros((2, 2))]
    assert flicker_score(frames) == pytest.approx(2.0)


def test_flicker_ignores_masked_pixel():
    # only pixel (0,0) flickers: at t=1 its term is |0 - 2*1 + 0| = 2; others 0.
    # no mask: 2 / 4 pixels = 0.5. With (0,0) masked: 0 / 3 pixels = 0.0.
    f0 = np.zeros((2, 2))
    f1 = np.zeros((2, 2))
    f1[0, 0] = 1.0
    f2 = np.zeros((2, 2))
    frames = [f0, f1, f2]
    assert flicker_score(frames) == pytest.approx(0.5)
    mask = np.zeros((2, 2), dtype=bool)
    mask[0, 0] = True
    assert flicker_score(frames, mask=mask) == pytest.approx(0.0)


def test_flicker_fewer_than_three_frames_raises():
    with pytest.raises(ClipGateError):
        flicker_score([np.zeros((2, 2)), np.zeros((2, 2))])


def test_flicker_non_2d_frames_raise():
    # round 9 (observer 8): frames must be 2-D arrays
    with pytest.raises(ClipGateError):
        flicker_score([np.zeros(4), np.zeros(4), np.zeros(4)])
    with pytest.raises(ClipGateError):
        flicker_score([np.zeros((2, 2, 1))] * 3)


def test_flicker_mismatched_frame_shape_raises():
    # round 9 (observer 8): every frame must have the same shape as the first
    frames = [np.zeros((2, 2)), np.zeros((2, 2)), np.zeros((2, 3))]
    with pytest.raises(ClipGateError):
        flicker_score(frames)


def test_flicker_mask_shape_mismatch_raises():
    # round 9 (observer 8): the mask must match the frame shape
    frames = [np.zeros((2, 2)), np.ones((2, 2)), np.zeros((2, 2))]
    with pytest.raises(ClipGateError):
        flicker_score(frames, mask=np.zeros((3, 3), dtype=bool))


def test_flicker_all_masked_raises():
    frames = [np.zeros((2, 2)), np.ones((2, 2)), np.zeros((2, 2))]
    mask = np.ones((2, 2), dtype=bool)
    with pytest.raises(ClipGateError):
        flicker_score(frames, mask=mask)


def test_flicker_does_not_mutate_inputs():
    f0 = np.zeros((2, 2))
    f1 = np.ones((2, 2))
    f2 = np.zeros((2, 2))
    mask = np.zeros((2, 2), dtype=bool)
    mask[1, 1] = True
    flicker_score([f0, f1, f2], mask=mask)
    assert np.array_equal(f1, np.ones((2, 2)))
    assert np.array_equal(f0, np.zeros((2, 2)))
    assert not mask[0, 0] and mask[1, 1]


def test_flicker_vector_equals_loop():
    # S-16: the vectorised flicker_score must equal a plain per-pixel loop (masked pixel excluded).
    rng = np.random.default_rng(0)
    frames = [rng.random((5, 7)) for _ in range(6)]
    mask = np.zeros((5, 7), dtype=bool)
    mask[2, 3] = True
    mask[0, 0] = True
    total = 0.0
    count = 0
    for t in range(1, 5):
        for y in range(5):
            for x in range(7):
                if not mask[y, x]:
                    total += abs(frames[t + 1][y, x] - 2.0 * frames[t][y, x] + frames[t - 1][y, x])
                    count += 1
    assert flicker_score(frames, mask=mask) == pytest.approx(total / count)


# ---------- S-16 additions ----------

def test_tail_window_ignores_handle():
    # 200 frames of 1.0 with a 5.0 handle spike at frame 180.
    # window (8, 152): analysed frames 8..151, the spike is outside -> no flag.
    # window (0, 200): the spike is inside the tail -> flagged at clip frame 180.
    flow = [1.0] * 200
    flow[180] = 5.0
    assert tail_spike(flow, window=(8, 152))["flag"] is False
    res = tail_spike(flow, window=(0, 200))
    assert res["flag"] is True
    assert res["first_spike_index"] == 180


def test_tail_window_outside_clip_raises():
    flow = [1.0] * 200
    with pytest.raises(ClipGateError):
        tail_spike(flow, window=(0, 201))
    with pytest.raises(ClipGateError):
        tail_spike(flow, window=(-1, 100))
    with pytest.raises(ClipGateError):
        tail_spike(flow, window=(100, 100))


def test_best_cut_nan_raises():
    with pytest.raises(ClipGateError):
        best_cut_frame([0.2, float("nan"), 0.5], 0)


def test_after_frame_negative_raises():
    with pytest.raises(ClipGateError):
        new_object_classes([{"person": 1}], after_frame=-1)
    with pytest.raises(ClipGateError):
        new_object_classes([{"person": 1}], after_frame=1.5)


def test_known_class_not_new():
    # "sage" is on the blocking sheet (known); it is seen at frame 20 (after 12) -> not new.
    counts = [{"person": 1} for _ in range(25)]
    counts[20] = {"person": 1, "sage": 1}
    assert new_object_classes(counts, known=["sage"]) == []
    assert new_object_classes(counts) == ["sage"]


# ---------- verdict ----------

def clean_results(**parts):
    base = {
        "tail": {"flag": False, "first_spike_index": None, "ratio": 1.0, "median": 1.0},
        "end": {"pass": True, "failed": []},
        "cuts": [],
        "new_classes": [],
        "flicker": 0.0,
        "flicker_limit": 1.0,
    }
    base.update(parts)
    return base


def test_verdict_empty_raises():
    with pytest.raises(ClipGateError, match="tail"):
        verdict({})


def test_verdict_tail_flagged_reason():
    res = verdict(clean_results(tail={"flag": True, "first_spike_index": 45, "ratio": 3.0, "median": 1.0}))
    assert res["pass"] is False
    assert res["reasons"] == [{"code": "TAIL_SNAP", "text": "tail snap at frame 45"}]
    assert res["accepted"] == []


def test_verdict_tail_not_flagged_passes():
    res = verdict(clean_results())
    assert res["pass"] is True
    assert res["reasons"] == []


def test_verdict_end_fail_reason_names_measure():
    res = verdict(clean_results(end={"pass": False, "failed": ["ssim"]}))
    assert res["pass"] is False
    assert len(res["reasons"]) == 1
    assert res["reasons"][0]["code"] == "END_MISMATCH"
    assert res["reasons"][0]["text"].startswith("end frame differs from keyframe B (failed:")
    assert "ssim" in res["reasons"][0]["text"]


def test_verdict_end_pass_no_reason():
    assert verdict(clean_results(end={"pass": True, "failed": []}))["pass"] is True


def test_verdict_end_pass_must_be_bool():
    with pytest.raises(ClipGateError):
        verdict(clean_results(end={"pass": "yes", "failed": []}))
    with pytest.raises(ClipGateError):
        verdict(clean_results(end={"failed": []}))


def test_verdict_scene_cut_reason_lists_samples():
    res = verdict(clean_results(cuts=[2, 4]))
    assert res["pass"] is False
    assert len(res["reasons"]) == 1
    assert res["reasons"][0]["code"] == "SCENE_CUT"
    assert "scene cut at samples" in res["reasons"][0]["text"]
    assert "2" in res["reasons"][0]["text"] and "4" in res["reasons"][0]["text"]


def test_verdict_empty_cuts_pass():
    assert verdict(clean_results(cuts=[]))["pass"] is True


def test_verdict_new_classes_reason():
    res = verdict(clean_results(new_classes=["dog"]))
    assert res["pass"] is False
    assert len(res["reasons"]) == 1
    assert res["reasons"][0]["code"] == "NEW_CLASS"
    assert "new objects appear" in res["reasons"][0]["text"]
    assert "dog" in res["reasons"][0]["text"]


def test_verdict_flicker_above_limit_fails():
    res = verdict(clean_results(flicker=2.0, flicker_limit=1.0))
    assert res["pass"] is False
    assert len(res["reasons"]) == 1
    assert res["reasons"][0]["code"] == "FLICKER"
    assert "flicker score" in res["reasons"][0]["text"]


def test_verdict_flicker_at_limit_passes():
    # "above limit" only: equal to the limit is not above
    assert verdict(clean_results(flicker=1.0, flicker_limit=1.0))["pass"] is True


def test_flicker_without_limit_raises():
    results = clean_results(flicker=2.0)
    del results["flicker_limit"]
    with pytest.raises(ClipGateError, match="flicker_limit"):
        verdict(results)


def test_verdict_all_failing_gives_five_reasons():
    results = clean_results(
        tail={"flag": True, "first_spike_index": 45, "ratio": 3.0, "median": 1.0},
        end={"pass": False, "failed": ["cosine"]},
        cuts=[3],
        new_classes=["dog"],
        flicker=2.0,
        flicker_limit=1.0,
    )
    res = verdict(results)
    assert res["pass"] is False
    assert [r["code"] for r in res["reasons"]] == ["TAIL_SNAP", "END_MISMATCH", "SCENE_CUT", "NEW_CLASS", "FLICKER"]
    assert res["reasons"][0]["text"] == "tail snap at frame 45"


def test_owner_accept_new_class():
    res = verdict(
        clean_results(new_classes=["dog"]),
        owner_accept=[{"code": "NEW_CLASS", "date": "2026-11-09", "note": "keep shot 7"}],
    )
    assert res == {"pass": True, "reasons": [], "accepted": ["NEW_CLASS"]}


def test_owner_accept_bad_entry_raises():
    with pytest.raises(ClipGateError):
        verdict(clean_results(), owner_accept=[{"code": "NEW_CLASS", "date": "2026-11-09"}])
    with pytest.raises(ClipGateError):
        verdict(clean_results(), owner_accept=[{"code": "BOGUS", "date": "2026-11-09", "note": "x"}])


def test_verdict_does_not_mutate_input():
    results = clean_results(cuts=[2, 4], new_classes=["dog"])
    before = clean_results(cuts=[2, 4], new_classes=["dog"])
    verdict(results)
    assert results == before
