"""Round-4 regressions (triage R4-H3): a VO wav with no usable shot length is VO_UNREADABLE, not a crash;
the CLI --allow-partial path is covered by the AttributeError handler in render_controller.main."""
import json

import h3.render_controller as rc
from h3.tests.synth import build_story
from h3.voice_manifest import build_manifest, wav_rel_path


def test_vo_wav_without_editorial_length_is_vo_unreadable_not_a_crash(tmp_path):
    shot = {"id": "s1", "audio_and_dialogue_track": {"narration_by_lang": {"en": {"text": "Hello there.", "language": "en",
                                                                                "time_range": [0.0, 1.0]}}}}
    wav = tmp_path / wav_rel_path("en", "s1")
    wav.parent.mkdir(parents=True)
    wav.write_bytes(b"RIFF")   # exists; its duration is never read because the shot has no length to fit against
    m = build_manifest(str(tmp_path), [shot], ["en"])
    assert [e["code"] for e in m["fit"]["errors"]] == ["VO_UNREADABLE"]


def test_main_reports_attribute_error_from_prepare_as_exit_1(tmp_path, monkeypatch, capsys):
    story = build_story(tmp_path / "src")
    story_file = tmp_path / "story.json"
    story_file.write_text(json.dumps(story), encoding="utf-8")

    def broken_prepare(*args, **kwargs):
        raise AttributeError("a non-object block reached the writer")

    monkeypatch.setattr(rc, "prepare", broken_prepare)
    code = rc.main(["--story-file", str(story_file), "--scope", "all", "--dry-run"])
    assert code == 1
    assert "ERROR" in capsys.readouterr().out


def test_corrupt_narration_block_has_no_text_instead_of_an_attribute_error():
    from h3.voice_manifest import narration_text
    assert narration_text({"audio_and_dialogue_track": {"narration_by_lang": "corrupt"}}, "en") == ""
    assert narration_text({"audio_and_dialogue_track": {"narration": 42}}, "en") == ""


def test_infinite_bgm_level_does_not_fake_a_median_error():
    import h3.gate_d_audio as gd
    voice = [-20.0] * 100
    bgm = [float("-inf")] * 50 + [-38.0] * 50      # -inf BGM windows are not usable levels
    codes_ = [e["code"] for e in gd.check_music_presence(voice, bgm)["errors"]]
    assert "BGM_MEDIAN_OUT_OF_BAND" not in codes_


def test_gate_d_plans_a_real_shot_id_keyed_shot():
    """Real stories key shots by shot_id; planning read only 'id' and failed every language with KeyError."""
    import copy
    import pathlib
    import tempfile
    from h3.gate_d_audio import plan_language_outputs as plan
    from h3.tests import synth
    st = synth.build_story(pathlib.Path(tempfile.mkdtemp()))
    shot = copy.deepcopy(st["episodes"][0]["shots"][0])
    shot["editorial_duration_sec"] = 2.0
    res = plan("ep1", ["en"], "vo", None, shots=[shot], video_path="v.mp4", video_has_audio=True)
    assert not [e for e in res["reports"]["en"]["errors"] if "KeyError" in e["message"]], res["reports"]["en"]["errors"]
