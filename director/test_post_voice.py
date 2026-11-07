"""post.py voice mixing (--voice elevenlabs|h3) and the ungraded stamp: owner decision brief 2026-11-07, work items 2 and 5."""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_post as tp  # noqa: E402
from test_post_language import HOOK, TEXT, _shots_with_script, _vo  # noqa: E402


def _build(tmp_path, lang, with_vo=True, story_voice=None):
    build, story, styles = tp._setup(tmp_path, shots=_shots_with_script())
    if with_vo:
        _vo(build, lang)
    if story_voice:
        doc = json.loads(story.read_text(encoding="utf-8"))
        doc["voice_engine"] = story_voice
        story.write_text(json.dumps(doc), encoding="utf-8")
    return build, story, styles


def _graph(build):
    return (build / "post" / "graph.txt").read_text(encoding="utf-8")


def test_hindi_reel_mixes_the_elevenlabs_voice_under_the_one_graph(tmp_path):
    build, story, styles = _build(tmp_path, "hi")
    report = tp._run(build, story, styles, language="hi")
    assert report["written"] is True and report["voice"]["engine"] == "elevenlabs"
    assert [Path(p).name for p in report["voice"]["vo_files"]] == ["SHOT_A.wav"]
    g = _graph(build)
    assert "[vo_full]" in g and "sidechaincompress" in g and "loudnorm=I=-16:TP=-1.3" in g and "[aout]" in g
    argv = report["commands"][-1]
    assert argv.count("-i") == 3                                   # two clips and the one voice file
    assert any(s["codec_type"] == "audio" for s in tp._probe_streams(Path(report["output"])))


def test_english_default_is_elevenlabs_in_one_render(tmp_path):
    build, story, styles = _build(tmp_path, "en")
    report = tp._run(build, story, styles, language="en")
    assert report["written"] is True and report["voice"]["engine"] == "elevenlabs" and len(report["voice"]["vo_files"]) == 1


def test_english_with_h3_keeps_the_h3_audio_and_needs_no_voice_file(tmp_path):
    build, story, styles = _build(tmp_path, "en", with_vo=False)
    report = tp._run(build, story, styles, language="en", voice="h3")
    assert report["written"] is True and report["voice"]["engine"] == "h3" and report["voice"]["vo_files"] == []
    assert "vo_full" not in _graph(build) and "sidechaincompress" not in _graph(build)


def test_story_voice_engine_is_used_when_no_flag_is_given(tmp_path):
    build, story, styles = _build(tmp_path, "en", with_vo=False, story_voice={"en": "h3"})
    report = tp._run(build, story, styles, language="en")
    assert report["written"] is True and report["voice"]["engine"] == "h3"


def test_a_missing_voice_file_refuses_and_names_the_file_never_falls_back(tmp_path):
    build, story, styles = _build(tmp_path, "hi", with_vo=False)
    report = tp._run(build, story, styles, language="hi")
    assert report["fail"] is True and report["written"] is False and not list(build.glob("EP1_final*.mp4"))
    msgs = [e["message"] for e in report["entries"] if e["level"] == "FAIL"]
    assert any("VO_MISSING" in m and "SHOT_A.wav" in m for m in msgs)


def test_h3_voice_is_refused_for_hindi_and_marathi(tmp_path):
    for lang in ("hi", "mr"):
        build, story, styles = _build(tmp_path / lang, lang)
        report = tp._run(build, story, styles, language=lang, voice="h3")
        assert report["fail"] is True and report["written"] is False
        assert any("VE-01" in e["message"] for e in report["entries"] if e["level"] == "FAIL")


def test_a_voice_file_longer_than_its_shot_is_refused(tmp_path):
    build, story, styles = tp._setup(tmp_path, shots=_shots_with_script())
    _vo(build, "hi", seconds=2.5)                                  # the shot is 2.0 s
    report = tp._run(build, story, styles, language="hi")
    assert report["fail"] is True and report["written"] is False
    assert any("VO_OVERFLOW" in e["message"] for e in report["entries"] if e["level"] == "FAIL")


def test_the_voice_is_planned_before_the_captions_and_the_reel_meets_the_loudness_target(tmp_path):
    build, story, styles = _build(tmp_path, "hi")
    report = tp._run(build, story, styles, language="hi")
    steps = report["steps"]
    voice_at = next(i for i, s in enumerate(steps) if s.startswith("voice:"))
    caption_at = next(i for i, s in enumerate(steps) if s.startswith("captions:"))
    assert voice_at < caption_at
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", report["output"], "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lufs = float(re.findall(r"I:\s+(-?\d+\.\d+) LUFS", r.stderr)[-1])
    assert -19.0 <= lufs <= -13.0, lufs                            # delivery target -16 LUFS, short synthetic clip: +-3 LU


def test_ungraded_act_is_a_loud_warning_and_the_manifest_says_graded_false(tmp_path):
    build, story, styles = tp._setup(tmp_path)
    pack_path = styles / "test_pack.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack["acts"]["HOOK"].pop("grade", None)                        # no grade numbers ...
    pack_path.write_text(json.dumps(pack), encoding="utf-8")
    (styles / pack["acts"]["HOOK"]["lut"]).unlink()                # ... and the act's .cube file does not exist
    report = tp._run(build, story, styles)
    assert report["written"] is True and report["graded"] is False and report["graded_by_act"]["HOOK"] is False
    warn = [e for e in report["entries"] if e["rule"] == "POST-UNGRADED"]
    assert warn and warn[0]["level"] == "WARN" and "UNGRADED EXPORT" in warn[0]["message"]
    doc = json.loads((build / "colour_report.json").read_text(encoding="utf-8"))
    assert doc["graded"] is False and doc["graded_by_act"]["HOOK"] is False


def test_graded_reel_says_graded_true(tmp_path):
    build, story, styles = tp._setup(tmp_path)
    report = tp._run(build, story, styles)
    doc = json.loads((build / "colour_report.json").read_text(encoding="utf-8"))
    assert report["graded"] is True and doc["graded"] is True and not [e for e in report["entries"] if e["rule"] == "POST-UNGRADED"]
