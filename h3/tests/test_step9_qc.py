import pytest

from h3.step9_qc import (CHECK_IDS, check_closing_payoff, check_no_storyboard_labels, check_sfx_alignment,
                         check_visual_continuity, final_qc, shot_offsets)


def _row(sid, dur=5.0, cues=(), hook="reveal", closing=False, anchors=None):
    return {
        "id": sid, "editorial_duration_sec": dur, "hook_type": hook, "is_closing_hook": closing,
        "audio_and_dialogue_track": {"sfx_cues": [{"time_range": t, "sfx_key": k, "description": "d"}
                                                  for t, k in cues]},
        "reference_anchors": anchors or {
            "fixed_landmarks": ["stone well"],
            "character_positions": [{"id": "CHAR-RAM", "screen": "left third", "depth": "mid"}],
            "exited_character_status": [{"id": "CHAR-MOTHER", "left_after_shot": "A0", "off_stage_shots": 1,
                                         "released": False}],
            "lighting_baseline": {"key": "warm lamp", "fill": "soft blue", "rim": "none", "shot_modifiers": "dusk"}},
    }


def _obs(**over):
    base = {"landmarks": ["Stone Well"], "character_positions": {"CHAR-RAM": {"screen": "Left Third", "depth": "mid"}},
            "lighting": {"key": "warm lamp", "fill": "soft blue", "rim": "none"}}
    base.update(over)
    return base


# ---- (a) sfx alignment ----

def test_sfx_cues_match_peaks_inside_tolerance():
    shots = [_row("A1", 5.0, [("1.0-1.5s", "door")]), _row("A2", 5.0, [("0.5-0.8s", "bell")])]
    ok, detail = check_sfx_alignment(shots, [1.1, 5.6], tolerance_sec=0.25)
    assert ok is True and "2 sfx cues" in detail


def test_sfx_cue_with_no_peak_fails_and_names_the_cue():
    shots = [_row("A1", 5.0, [("1.0-1.5s", "door")])]
    ok, detail = check_sfx_alignment(shots, [3.0])
    assert ok is False and "A1 door" in detail


def test_sfx_tolerance_boundary_is_inclusive():
    shots = [_row("A1", 5.0, [("1.0-1.5s", "door")])]
    assert check_sfx_alignment(shots, [1.5 + 0.25], tolerance_sec=0.25)[0] is True
    assert check_sfx_alignment(shots, [1.5 + 0.26], tolerance_sec=0.25)[0] is False


def test_sfx_peaks_use_reel_time_from_editorial_offsets():
    shots = [_row("A1", 5.0), _row("A2", 5.0, [("1.0-1.5s", "bell")])]
    assert check_sfx_alignment(shots, [6.1])[0] is True     # 5.0 + 1.0 start
    assert check_sfx_alignment(shots, [1.1])[0] is False    # shot-relative time is not enough


def test_reel_without_sfx_cues_fails():
    assert check_sfx_alignment([_row("A1")], [1.0])[0] is False


def test_shot_offsets_are_cumulative_and_validated():
    assert shot_offsets([_row("A1", 2.0), _row("A2", 3.5)]) == {"A1": 0.0, "A2": 2.0}
    with pytest.raises(ValueError):
        shot_offsets([_row("A1"), _row("A1")])
    with pytest.raises(ValueError):
        shot_offsets([_row("A1", 0)])


# ---- (b) visual continuity ----

def test_continuity_passes_when_observations_match_anchors():
    shots = [_row("A1")]
    assert check_visual_continuity(shots, {"A1": _obs()})[0] is True


def test_continuity_fails_on_missing_landmark():
    ok, detail = check_visual_continuity([_row("A1")], {"A1": _obs(landmarks=[])})
    assert ok is False and "stone well" in detail


def test_continuity_fails_on_character_position_mismatch_and_missing_character():
    ok, detail = check_visual_continuity(
        [_row("A1")], {"A1": _obs(character_positions={"CHAR-RAM": {"screen": "right", "depth": "mid"}})})
    assert ok is False and "CHAR-RAM" in detail
    ok2, detail2 = check_visual_continuity([_row("A1")], {"A1": _obs(character_positions={})})
    assert ok2 is False and "not observed" in detail2


def test_continuity_fails_when_unreleased_exited_character_is_visible():
    obs = _obs(character_positions={"CHAR-RAM": {"screen": "left third", "depth": "mid"},
                                    "CHAR-MOTHER": {"screen": "centre", "depth": "near"}})
    ok, detail = check_visual_continuity([_row("A1")], {"A1": obs})
    assert ok is False and "CHAR-MOTHER" in detail


def test_continuity_allows_exited_character_once_released():
    anchors = _row("A1")["reference_anchors"]
    anchors["exited_character_status"][0]["released"] = True
    obs = _obs(character_positions={"CHAR-RAM": {"screen": "left third", "depth": "mid"},
                                    "CHAR-MOTHER": {"screen": "centre", "depth": "near"}})
    assert check_visual_continuity([_row("A1", anchors=anchors)], {"A1": obs})[0] is True


def test_continuity_fails_on_lighting_drift_and_missing_observation():
    ok, detail = check_visual_continuity([_row("A1")], {"A1": _obs(lighting={"key": "cold moon", "fill": "soft blue",
                                                                              "rim": "none"})})
    assert ok is False and "lighting key" in detail
    ok2, detail2 = check_visual_continuity([_row("A1")], {})
    assert ok2 is False and "no visual observation" in detail2


# ---- (c) closing payoff ----

def test_closing_payoff_passes_with_strong_hook_closing_flag_and_payoff():
    shots = [_row("A1"), _row("A2", hook="tender", closing=True)]
    assert check_closing_payoff(shots, True)[0] is True


@pytest.mark.parametrize("hook,closing,payoff", [("expression-beat", True, True), ("tender", False, True),
                                                 ("tender", True, False), ("tender", True, 1)])
def test_closing_payoff_fails_on_weak_hook_missing_flag_or_payoff(hook, closing, payoff):
    shots = [_row("A1", hook=hook, closing=closing)]
    assert check_closing_payoff(shots, payoff)[0] is False


# ---- (d) storyboard labels ----

@pytest.mark.parametrize("text", ["[char: Ram]", "[scene: well]", "@CHAR-RAM", "SHEET-03", "SHOT 3",
                                  "panel 2", "HOOK: tension", "0.0s-1.2s", "DUR: 5"])
def test_storyboard_labels_on_screen_fail(text):
    ok, detail = check_no_storyboard_labels([_row("A1")], {"A1": [text]})
    assert ok is False and "A1" in detail


def test_clean_on_screen_text_passes_and_missing_result_fails():
    assert check_no_storyboard_labels([_row("A1")], {"A1": ["Ram", "नमस्ते"]})[0] is True
    assert check_no_storyboard_labels([_row("A1"), _row("A2")], {"A1": []})[0] is False


# ---- final_qc: injectable measurers, fail closed ----

def _shots():
    return [_row("A1", 5.0, [("1.0-1.5s", "door")]), _row("A2", 5.0, [("0.2-0.4s", "bell")], hook="tender",
                                                          closing=True)]


def _measurers(**over):
    base = {"audio_peaks": lambda: [1.2, 5.3],
            "visual_observations": lambda: {"A1": _obs(), "A2": _obs()},
            "closing_payoff": lambda row: True,
            "frame_labels": lambda: {"A1": ["Ram"], "A2": []}}
    base.update(over)
    return base


def test_final_qc_all_pass():
    report = final_qc(_shots(), measurers=_measurers())
    assert report["ok"] is True
    assert [c["id"] for c in report["checks"]] == list(CHECK_IDS)
    assert all(c["ok"] and isinstance(c["detail"], str) for c in report["checks"])


def test_final_qc_one_failure_fails_the_gate_and_others_still_report():
    report = final_qc(_shots(), measurers=_measurers(audio_peaks=lambda: [3.0]))
    by_id = {c["id"]: c for c in report["checks"]}
    assert report["ok"] is False and by_id["sfx_alignment"]["ok"] is False
    assert by_id["visual_continuity"]["ok"] and by_id["closing_payoff"]["ok"]


def test_final_qc_missing_measurer_fails_that_check_closed():
    report = final_qc(_shots(), measurers={k: v for k, v in _measurers().items() if k != "frame_labels"})
    by_id = {c["id"]: c for c in report["checks"]}
    assert report["ok"] is False and by_id["no_storyboard_labels"]["ok"] is False
    assert "no frame_labels measurer" in by_id["no_storyboard_labels"]["detail"]


def test_final_qc_measurer_that_raises_fails_closed():
    def boom():
        raise OSError("decoder missing")
    report = final_qc(_shots(), measurers=_measurers(audio_peaks=boom))
    assert report["ok"] is False


def test_final_qc_closing_measurer_receives_the_last_row():
    seen = []
    report = final_qc(_shots(), measurers=_measurers(closing_payoff=lambda row: seen.append(row["id"]) or True))
    assert seen == ["A2"] and report["ok"] is True


def test_final_qc_rejects_empty_reel():
    with pytest.raises(ValueError):
        final_qc([], measurers=_measurers())
