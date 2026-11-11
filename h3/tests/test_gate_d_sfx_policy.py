"""Offline tests for X-18: the SFX policy of rule 50(6) in Gate D. Model SFX stay at full level inside their clip_qa sfx_keep windows
and are ducked elsewhere to bed_gain_db = min(0, (voice_db - 22) - bed_db). No ffmpeg, no model call."""
import pytest

from h3 import gate_d_audio as gd


def test_bed_gain_hand():
    # voice -18 dB, bed -30 dB: target bed is -40 dB, so the gain is -10 dB and the linear gain is 0.3162
    assert gd.bed_gain_db(-18.0, -30.0) == pytest.approx(-10.0)
    assert round(10 ** (gd.bed_gain_db(-18.0, -30.0) / 20), 4) == 0.3162


def test_bed_already_quiet_gain_0():
    # bed -45 dB is already below the -40 dB target: no gain change
    assert gd.bed_gain_db(-18.0, -45.0) == 0.0


def test_keep_window_expression_text():
    expr = gd.sfx_policy_filter("sfxin", "sfxout", [(1.0, 2.0), (3.0, 4.0)], -10.0)
    assert expr == "[sfxin]volume='if(between(t,1.000,2.000)+between(t,3.000,4.000),1,0.3162)':eval=frame[sfxout]"


def test_bed_louder_than_voice_minus_22_fails():
    # voice -18 dB: the bed may be at most -39.5 dB (target -40 plus the 0.5 dB tolerance)
    loud = gd.check_sfx_beds([{"shot": "SHOT-001", "voice_db": -18.0, "bed_db": -39.0}])
    assert [e["code"] for e in loud] == ["SFX_BED_LOUD"]
    assert gd.check_sfx_beds([{"shot": "SHOT-001", "voice_db": -18.0, "bed_db": -40.0}]) == []


def test_policy_none_unchanged():
    clips = [{"input_index": "h3s0", "trim_in_sec": 0.0, "trim_out_sec": 2.0}]
    plain = gd.build_mix_filter(clips, "vo_full", None, 2.0)
    assert "volume=" not in plain and "eval=frame" not in plain   # no ducking filter when no policy is given
    assert gd.build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=[None]) == plain
    ducked = gd.build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=[{"keep": [(0.5, 1.5)], "bed_gain_db": -10.0}])
    assert "volume='if(between(t,0.500,1.500),1,0.3162)':eval=frame" in ducked
    assert ducked != plain


def test_policy_length_must_match_clips():
    clips = [{"input_index": "h3s0", "trim_in_sec": 0.0, "trim_out_sec": 2.0}]
    with pytest.raises(ValueError):
        gd.build_mix_filter(clips, "vo_full", None, 2.0, sfx_policy=[None, None])
