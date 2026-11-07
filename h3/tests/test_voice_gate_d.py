"""Gate D with English H3 voice (en-h3): one stem from the H3 clip, per-language video choice, extra-render warning.
Pure text and dict checks, no ffmpeg, no model, no network."""
import wave

import pytest

from h3 import gate_d_audio as gd
from h3.shot_table_spec import LOUDNESS

SFX = [{"input_index": f"h3s{k}", "trim_in_sec": 0.0, "trim_out_sec": 5.0} for k in range(2)]


def test_h3_mix_is_one_stem_without_voice_stem():
    f = gd.build_mix_filter(SFX, None, None, 10.0)
    assert "[h3_sfx_full]atrim=0:10.000," in f and f.endswith(f"[{gd.MASTER_LABEL}]")
    assert "elevenlabs_vo" not in f and "vo_full" not in f and "sidechaincompress" not in f
    assert f"loudnorm=I={LOUDNESS['target_lufs']:g}:TP={LOUDNESS['loudnorm_tp']:g}" in f


def test_h3_mix_with_bgm_ducks_bgm_under_the_speech_stem():
    f = gd.build_mix_filter(SFX, None, 4, 10.0)
    assert f.count("sidechaincompress") == 1 and gd.BGM_DUCK in f
    assert "[sfx_out][bgm_ducked]amix=inputs=2:duration=longest:normalize=0,atrim=0:10.000" in f
    assert "elevenlabs_vo" not in f and f.endswith(f"[{gd.MASTER_LABEL}]")


def test_elevenlabs_mix_is_unchanged_by_the_h3_path():
    f = gd.build_mix_filter(SFX, 2, None, 10.0)
    assert "[elevenlabs_vo]" in f and "amix=inputs=2" in f and gd.SFX_DUCK in f


def test_video_choice_per_language_engine():
    shared, en_h3 = "render/shared_foley.mp4", "render/en_h3.mp4"
    variants = {"shared_foley": shared, "en_h3": en_h3}
    assert gd._video_for(variants, "h3") == en_h3
    assert gd._video_for(variants, "elevenlabs") == shared
    assert gd._video_for(shared, "h3") == shared            # one path for every language
    with pytest.raises(ValueError, match="en_h3"):
        gd._video_for({"shared_foley": shared}, "h3")


def _shot(sid, dialogue=None, editorial=6.0, opening=False, closing=False):
    return {"id": sid, "editorial_duration_sec": editorial, "is_opening_0_2s_hook": opening,
            "is_closing_hook": closing,
            "audio_and_dialogue_track": {"narration": None, "dialogue": dialogue or [], "sfx_cues": [
                {"time_range": "0.2-0.6s", "sfx_key": "bell", "description": "bell rings"}],
                "performance_notes": {"text": "calm", "narrator_mouth_closed": True, "mouth_state": {"0": "closed"}}}}


def test_en_h3_plan_needs_no_vo_files_and_warns_about_render_once(tmp_path):
    shots = [_shot("SHOT-01", [{"speaker": "S1", "text": "Hold the line.", "tone": "calm", "time_range": [0.5, 2.5]}],
                   opening=True),
             _shot("SHOT-02", closing=True)]
    res = gd.plan_language_outputs(
        "reel_a", ["en", "hi"], str(tmp_path / "vo"), None, shots=shots,
        video_path={"shared_foley": "render/shared_foley.mp4", "en_h3": "render/en_h3.mp4"}, video_has_audio=True,
        narration_driven=False, voice_engines={"en": "h3", "hi": "elevenlabs"})
    en_errs = [e["code"] for e in res["reports"]["en"]["errors"]]
    assert "VO_MISSING" not in en_errs and "NO_VO_FILES" not in en_errs
    assert any("breaks the render-once rule" in w for w in res["reports"]["en"]["warnings"])
    # hi has no speech in any shot: no VO expected, so no NO_VO_FILES; and no en warning for hi
    assert "NO_VO_FILES" not in [e["code"] for e in res["reports"]["hi"]["errors"]]
    assert not any("render-once" in w for w in res["reports"]["hi"]["warnings"])
    # the English mix is the single stem: no VO stem in its filtergraph
    en_mix = res["languages"]["en"]["mix_filter"]
    if en_mix is not None:
        assert "vo_full" not in en_mix and "elevenlabs_vo" not in en_mix


def _lines(lang_text, span):
    return [{"speaker": "CHAR-A", "text": lang_text, "tone": "calm", "time_range": list(span)}]


def _pair_shots():
    """Two shots; every language uses the SAME time ranges (cut points match)."""
    out = []
    for sid, span in (("SHOT-01", (0.5, 2.5)), ("SHOT-02", (1.0, 3.0))):
        s = _shot(sid, editorial=6.0, opening=sid == "SHOT-01", closing=sid == "SHOT-02")
        s["audio_and_dialogue_track"]["dialogue_by_lang"] = {"en": _lines("Keep going.", span),
                                                             "hi": _lines("aage badho.", span)}
        out.append(s)
    return out


def test_same_timing_passes_when_every_language_shares_the_ranges():
    assert gd.same_timing_problems(_pair_shots()) == []


def test_different_ranges_between_languages_is_time01():
    shots = _pair_shots()
    shots[1]["audio_and_dialogue_track"]["dialogue_by_lang"]["hi"][0]["time_range"] = [1.0, 3.5]
    errs = gd.same_timing_problems(shots)
    assert [e["code"] for e in errs] == ["TIME-01"] and errs[0]["where"] == "SHOT-02"


def test_non_positive_editorial_length_is_time01():
    shots = _pair_shots()
    shots[0]["editorial_duration_sec"] = 0
    assert [e["code"] for e in gd.same_timing_problems(shots)] == ["TIME-01"]


def _wav(path, seconds, rate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(2 * int(seconds * rate)))


def test_vo_fit_is_checked_per_language(tmp_path):
    """The English VO is too long for shot 1 (6.0 s editorial), Hindi fits. Only English gets VO_OVERFLOW_ERROR."""
    vo = tmp_path / "vo"
    for lang, secs in (("en", 6.5), ("hi", 3.0)):
        (vo / lang).mkdir(parents=True)
        _wav(vo / lang / "SHOT-01.wav", secs)
        _wav(vo / lang / "SHOT-02.wav", 2.0)
    res = gd.plan_language_outputs("reel_b", ["en", "hi"], str(vo), None, shots=_pair_shots(),
                                   video_path="render/shared_foley.mp4", video_has_audio=True,
                                   narration_driven=False, voice_engines={"en": "elevenlabs", "hi": "elevenlabs"})
    en_codes = [e["code"] for e in res["reports"]["en"]["errors"]]
    hi_codes = [e["code"] for e in res["reports"]["hi"]["errors"]]
    assert "VO_OVERFLOW_ERROR" in en_codes
    assert "VO_OVERFLOW_ERROR" not in hi_codes
    # the elevenlabs languages share the one Foley render
    assert res["languages"]["en"]["vo_files"] and res["languages"]["hi"]["vo_files"]
