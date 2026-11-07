"""Tests for core/retention_rules.py (R1-R10). Episodes and shots are built by hand."""
import copy
import inspect

import pytest

from core import retention_rules as rr
from core.retention_rules import RULE_IDS, check_retention_rules
from core.style_pack import load_core

CORE = load_core()
FPS = 24


def _beat(start, end, hold=False, primary=False, bhava=None, acting="", reveal=False, virtual=False):
    return {"start_s": start, "end_s": end, "hold": hold, "primary": primary, "bhava": bhava,
            "acting": acting, "reveal": reveal, "virtual": virtual}


def _look(act="HOOK", hook=None, focal="CHAR-SHIVA", **extra):
    look = {"palette_id": "shiva_neelkanth", "act": act, "phase": "PH-1", "focal": focal,
            "focal_value": "lightest", "hook": hook, "impact_frames": [], "vfx": [],
            "accent_use": False, "hold_purpose": None}
    look.update(extra)
    return look


def _shot(sid, start_frame, frames, look=None, beats=None, cast=("CHAR-SHIVA",), camera=(),
          dialogue=(), captions=(), impacts=(), purpose="", sound="ambient hum",
          first_dialogue=None, raw=None):
    return {"id": sid, "shape": "v22", "index": 0, "start_frame": start_frame, "frames": frames,
            "look": look, "cast_ids": list(cast), "beats": list(beats or []),
            "impacts": list(impacts), "text": {"prompt": "", "light_world": ""},
            "first_dialogue": first_dialogue, "dialogue_starts": list(dialogue),
            "camera_moves": list(camera), "caption_changes": list(captions),
            "purpose": purpose, "sound_text": sound, "problems": [],
            "raw": raw if raw is not None else {}}


def _episode(key, shots, total_frames):
    return {"key": key, "fps": FPS, "shots": shots, "total_frames": total_frames}


def _base():
    """Episode 1: 8 shots x 3.0 s (24 s), reveal beat at 12 s, cliffhanger ending.
    Episode 2 (final): 4 shots x 3.0 s (12 s), one act, no reveal."""
    ep1 = []
    for i in range(8):
        act = "HOOK" if i < 2 else "BUILD"
        hook = {"type": "H-03", "caption": "Why is his throat blue?"} if i == 0 else None
        extra = {"end_caption": "Will he survive?"} if i == 7 else {}
        if i == 0:
            beats = [_beat(0.0, 1.5, hold=True, acting="eyes slowly open"),
                     _beat(1.5, 3.0, acting="turns head")]
        elif i == 4:
            beats = [_beat(12.0, 13.0, primary=True, reveal=True, acting="the blade lights"),
                     _beat(13.0, 15.0, acting="steps forward")]
        else:
            beats = [_beat(3.0 * i, 3.0 * i + 3.0, acting="moves")]
        ep1.append(_shot(
            f"E1S{i + 1}", 72 * i, 72, look=_look(act, hook=hook, **extra), beats=beats,
            dialogue=[1.0] if i == 0 else [],
            purpose="cold open" if i == 0 else ("cliffhanger: the blade hums" if i == 7 else "beat"),
            first_dialogue="Who dares wake me?" if i == 0 else None,
            raw={"compositing": {"post": "grade only"}} if i == 0 else {}))
    ep2 = []
    for i in range(4):
        hook = {"type": "H-06", "caption": "Why is the lake burning?"} if i == 0 else None
        if i == 0:
            beats = [_beat(0.0, 1.5, hold=True, acting="eyes narrow"), _beat(1.5, 3.0, acting="turns")]
        else:
            beats = [_beat(3.0 * i, 3.0 * i + 3.0, acting="moves")]
        ep2.append(_shot(
            f"E2S{i + 1}", 72 * i, 72, look=_look("HOOK", hook=hook, focal="CHAR-KALIYA"),
            cast=("CHAR-KALIYA",), beats=beats, dialogue=[1.0] if i == 0 else [],
            purpose="the reed bed parts",
            first_dialogue="Hold on, I am coming" if i == 0 else None))
    return [_episode(1, ep1, 576), _episode(2, ep2, 288)]


def _long_hook_episode(beats=None, **look_extra):
    """One 20 s hook shot, one long hold beat, no dialogue or other change events."""
    frames = 20 * FPS
    look = _look("HOOK", hook={"type": "H-03", "caption": "Why is the sky red?"}, **look_extra)
    if beats is None:
        beats = [_beat(0.0, 20.0, hold=True, acting="holds")]
    shot = _shot("LONG1", 0, frames, look=look, beats=beats, first_dialogue="Who goes there?",
                 sound="wind")
    return _episode(1, [shot], frames)


def _find(entries, rule, level=None):
    return [e for e in entries if e["rule"] == rule and (level is None or e["level"] == level)]


# ---- base, module shape ----
def test_base_produces_no_entries():
    assert check_retention_rules(_base(), CORE) == []


def test_empty_episodes_returns_empty_list():
    assert check_retention_rules([], CORE) == []


def test_rule_ids_and_functions_present_in_module():
    assert RULE_IDS == tuple(f"R{n}" for n in range(1, 11))
    for n in range(1, 11):
        assert callable(getattr(rr, f"rule_r{n}", None)), f"rule_r{n} missing"
    src = inspect.getsource(rr)
    assert "core.timeline" not in src


# ---- R1 ----
def test_r1_fail_first_shot_without_hook():
    eps = _base()
    eps[0]["shots"][0]["look"]["hook"] = None
    assert _find(check_retention_rules(eps, CORE), "R1", "FAIL")


def test_r1_fail_focal_not_in_cast():
    eps = _base()
    eps[0]["shots"][0]["cast_ids"] = ["CHAR-OTHER"]
    assert _find(check_retention_rules(eps, CORE), "R1", "FAIL")


def test_r1_warn_fade_in_first_beat():
    eps = _base()
    eps[0]["shots"][0]["beats"][0]["acting"] = "fade in from black"
    entries = check_retention_rules(eps, CORE)
    assert _find(entries, "R1", "WARN")
    assert not _find(entries, "R1", "FAIL")


# ---- R2 ----
def test_r2_fail_first_beat_not_hold():
    eps = _base()
    eps[0]["shots"][0]["beats"][0]["hold"] = False
    assert _find(check_retention_rules(eps, CORE), "R2", "FAIL")


def test_r2_push_or_zoom_at_zero_exempts_but_offset_push_does_not():
    eps = _base()
    shot = eps[0]["shots"][0]
    shot["beats"][0]["hold"] = False
    shot["raw"] = {"compositing": {"post": "slow zoom starts at 0 s"}}
    assert not _find(check_retention_rules(eps, CORE), "R2")
    shot["raw"] = {"compositing": {"post": "push starts at 0.5 s"}}
    assert _find(check_retention_rules(eps, CORE), "R2", "FAIL")


# ---- R3 ----
def test_r3_warn_no_face_change_by_one_second():
    eps = _base()
    eps[0]["shots"][0]["beats"][0]["acting"] = "walks forward"
    assert _find(check_retention_rules(eps, CORE), "R3", "WARN")


# ---- R4 ----
def test_r4_fail_caption_equals_first_dialogue():
    eps = _base()
    eps[0]["shots"][0]["look"]["hook"]["caption"] = "  who DARES wake me? "
    eps[0]["shots"][0]["first_dialogue"] = "Who dares wake me?"
    assert _find(check_retention_rules(eps, CORE), "R4", "FAIL")


def test_r4_fail_caption_over_six_words():
    eps = _base()
    eps[0]["shots"][0]["look"]["hook"]["caption"] = "Why is his throat glowing blue in the dark?"
    assert _find(check_retention_rules(eps, CORE), "R4", "FAIL")


# ---- R5 ----
def test_r5_fail_no_hold_before_three_seconds():
    eps = _base()
    eps[0]["shots"][0]["beats"] = [_beat(0.0, 3.0, acting="walks")]
    eps[0]["shots"][1]["beats"] = [_beat(3.0, 6.0, hold=True, acting="stills")]
    assert _find(check_retention_rules(eps, CORE), "R5", "FAIL")


# ---- R6 ----
def test_r6_spec_regression_20s_single_hook_shot_fails():
    fails = _find(check_retention_rules([_long_hook_episode()], CORE), "R6", "FAIL")
    assert len(fails) == 1
    assert "20.00" in fails[0]["message"]


def test_r6_gap_between_warn_and_fail_is_warn():
    frames = 91  # 3.79 s, above static_warn_s (3.5) and below static_fail_s (4.0)
    look = _look("HOOK", hook={"type": "H-03", "caption": "Why is the sky red?"})
    shot = _shot("S1", 0, frames, look=look, beats=[_beat(0.0, frames / FPS, hold=True, acting="holds")],
                 first_dialogue="Who goes there?", sound="wind")
    entries = check_retention_rules([_episode(1, [shot], frames)], CORE)
    assert _find(entries, "R6", "WARN")
    assert not _find(entries, "R6", "FAIL")


def test_r6_hold_purpose_downgrades_to_warn():
    entries = check_retention_rules([_long_hook_episode(hold_purpose="ma after a divine reveal")], CORE)
    assert _find(entries, "R6", "WARN")
    assert not _find(entries, "R6", "FAIL")


def test_r6_hold_beat_with_bhava_downgrades_to_warn():
    beats = [_beat(0.0, 20.0, hold=True, bhava="ma", acting="holds")]
    entries = check_retention_rules([_long_hook_episode(beats=beats)], CORE)
    assert _find(entries, "R6", "WARN")
    assert not _find(entries, "R6", "FAIL")


# ---- R7 ----
def test_r7_warn_no_act_change_or_reveal_in_rehook_window():
    eps = _base()
    eps[0]["shots"][4]["beats"][0]["reveal"] = False
    assert _find(check_retention_rules(eps, CORE), "R7", "WARN")


def test_r7_skipped_for_single_act_without_reveal():
    entries = check_retention_rules([_base()[1]], CORE)
    assert not _find(entries, "R7")


# ---- R8 ----
def test_r8_warn_purpose_without_cliffhanger():
    eps = _base()
    eps[0]["shots"][-1]["purpose"] = "the blade hums"
    r8 = _find(check_retention_rules(eps, CORE), "R8", "WARN")
    assert len(r8) == 1
    assert "cliffhanger" in r8[0]["message"]


def test_r8_warn_missing_closing_question_reported_separately():
    eps = _base()
    del eps[0]["shots"][-1]["look"]["end_caption"]
    r8 = _find(check_retention_rules(eps, CORE), "R8", "WARN")
    assert len(r8) == 1
    assert "caption" in r8[0]["message"]


def test_r8_both_missing_gives_two_entries():
    eps = _base()
    eps[0]["shots"][-1]["purpose"] = "the blade hums"
    del eps[0]["shots"][-1]["look"]["end_caption"]
    assert len(_find(check_retention_rules(eps, CORE), "R8", "WARN")) == 2


def test_r8_final_episode_is_exempt():
    ep = copy.deepcopy(_base()[0])
    ep["shots"][-1]["purpose"] = "the blade hums"
    del ep["shots"][-1]["look"]["end_caption"]
    assert not _find(check_retention_rules([ep], CORE), "R8")


# ---- R9 ----
def test_r9_fail_empty_first_sound():
    eps = _base()
    eps[0]["shots"][0]["sound_text"] = "   "
    assert _find(check_retention_rules(eps, CORE), "R9", "FAIL")


# ---- R10 ----
def test_r10_warn_length_outside_target_plus_clip():
    entries = check_retention_rules(_base(), CORE, story={"episode_target_s": [30, 40]})
    assert len(_find(entries, "R10", "WARN")) == 2


def test_r10_pass_within_target_and_skip_without_target():
    assert not _find(check_retention_rules(_base(), CORE, story={"episode_target_s": [10, 30]}), "R10")
    assert not _find(check_retention_rules(_base(), CORE, story=None), "R10")
    assert not _find(check_retention_rules(_base(), CORE, story={}), "R10")


def test_r10_bad_target_is_p0():
    entries = check_retention_rules(_base(), CORE, story={"episode_target_s": "long"})
    assert _find(entries, "P0", "FAIL")


# ---- legacy and junk input ----
def test_legacy_shots_without_beats_give_warn_not_crash():
    shots = [_shot("L1", 0, 72, look=None, beats=[]), _shot("L2", 72, 72, look=None, beats=[])]
    entries = check_retention_rules([_episode(1, shots, 144)], CORE)
    assert entries
    assert all(e["level"] == "WARN" for e in entries)
    assert any(e["rule"] == "R2" and "no beats" in e["message"] for e in entries)


@pytest.mark.parametrize("bad", [
    None,
    "x",
    42,
    [None],
    [{"key": 1, "fps": FPS, "total_frames": 24}],
    [{"key": 1, "fps": FPS, "total_frames": 24, "shots": [None]}],
])
def test_junk_episodes_give_p0_fail(bad):
    entries = check_retention_rules(bad, CORE)
    assert entries
    assert all(e["rule"] == "P0" and e["level"] == "FAIL" for e in entries)


def test_junk_core_gives_p0_fail():
    assert _find(check_retention_rules(_base(), None), "P0", "FAIL")
    assert _find(check_retention_rules(_base(), {}), "P0", "FAIL")
