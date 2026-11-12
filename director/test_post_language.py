"""Owner rules 2026-11-07: English reels get English captions, Hindi reels Hindi, Marathi reels Marathi; the caption text is the
spoken script of that language; the hook caption stays on frame 1 (hook policy of the shared caption engine)."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_post as tp  # noqa: E402

TEXT = {"en": "Krishna jumps into the river.", "hi": "कृष्ण यमुना में कूद पड़ा।", "mr": "कृष्ण यमुनेत उडी मारतो."}
HOOK = {"en": "Why is he blue?", "hi": "उसका गला नीला क्यों?", "mr": "त्याचा गळा निळा का?"}


def _shots_with_script(first_start=1.5):
    shots = [tp._shot("SHOT_A"), tp._shot("SHOT_B")]
    shots[0]["metadata"]["look"]["hook"] = {"type": "H-01", "caption": HOOK["en"], "caption_by_lang": dict(HOOK)}
    shots[0]["audio_and_dialogue_track"] = {
        "narration_by_lang": {lang: {"text": text, "time_range": [first_start, first_start + 1.4]} for lang, text in TEXT.items()}}
    return shots


def _vo(build, lang, sid="SHOT_A", seconds=1.8):
    """A voice file for the shot: build/audio/vo/<lang>/<shot_id>.wav (a 440 Hz tone; the mix does not care what it says)."""
    import math
    import struct
    import wave
    d = build / "audio" / "vo" / lang
    d.mkdir(parents=True, exist_ok=True)
    with wave.open(str(d / f"{sid}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 48000))) for i in range(int(48000 * seconds))))


def _ass(build):
    return (build / "post" / "captions.ass").read_text(encoding="utf-8")


def test_each_language_burns_its_hook_then_its_own_spoken_script(tmp_path):
    for lang in ("en", "hi", "mr"):
        build, story, styles = tp._setup(tmp_path / lang, shots=_shots_with_script())
        _vo(build, lang)
        report = tp._run(build, story, styles, language=lang, sidecars=True)
        ass = _ass(build)
        assert HOOK[lang] in ass and TEXT[lang].rstrip(".।") in ass, lang
        assert ass.index(HOOK[lang]) < ass.index(TEXT[lang].rstrip(".।"))            # the hook is on frame 1, then the script
        for other in set(TEXT) - {lang}:
            assert TEXT[other].rstrip(".।") not in ass and HOOK[other] not in ass, (lang, other)
        assert report["written"] is True and report["output"].endswith(f"EP1_final_{lang}.mp4")
        srt = next(build.glob(f"EP1_final_{lang}.{lang}.srt")).read_text(encoding="utf-8")
        assert srt.splitlines()[2] == HOOK[lang]                                      # rule 4: the hook is the first cue


def test_hook_equal_to_the_first_spoken_line_is_burned_once(tmp_path):
    shots = _shots_with_script(first_start=0.0)
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"]["en"]["text"] = HOOK["en"]
    build, story, styles = tp._setup(tmp_path, shots=shots)
    _vo(build, "en")
    report = tp._run(build, story, styles, language="en", sidecars=True)
    assert report["written"] is True and _ass(build).count(HOOK["en"]) == 1
    assert next(build.glob("EP1_final_en.en.srt")).read_text(encoding="utf-8").count(HOOK["en"]) == 1


def test_hook_caption_in_the_wrong_script_refuses(tmp_path):
    shots = _shots_with_script()
    shots[0]["metadata"]["look"]["hook"].pop("caption_by_lang")                       # one English hook text for a Hindi reel
    build, story, styles = tp._setup(tmp_path, shots=shots)
    _vo(build, "hi")
    report = tp._run(build, story, styles, language="hi")
    assert report["fail"] is True and report["written"] is False
    assert any("has no Devanagari" in e["message"] for e in report["entries"] if e["level"] == "FAIL")


def test_devanagari_in_an_english_reel_refuses(tmp_path):
    shots = _shots_with_script()
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"]["en"]["text"] = TEXT["hi"]
    build, story, styles = tp._setup(tmp_path, shots=shots)
    _vo(build, "en")
    report = tp._run(build, story, styles, language="en")
    assert report["fail"] is True and report["written"] is False and not list(build.glob("EP1_final*.mp4"))
    assert any("contains Devanagari" in e["message"] for e in report["entries"] if e["level"] == "FAIL")


def test_latin_only_spoken_line_in_a_hindi_reel_refuses(tmp_path):
    shots = _shots_with_script()
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"]["hi"]["text"] = "Krishna jumps"
    build, story, styles = tp._setup(tmp_path, shots=shots)
    _vo(build, "hi")
    report = tp._run(build, story, styles, language="hi")
    assert report["fail"] is True and report["written"] is False


def test_no_spoken_script_burns_the_hook_alone_with_a_warning(tmp_path):
    build, story, styles = tp._setup(tmp_path)   # plain shots: no audio_and_dialogue_track
    report = tp._run(build, story, styles, language="en")
    assert "Hook line" in _ass(build) and report["written"] is True
    assert any("no spoken en script" in e["message"] for e in report["entries"] if e["level"] == "WARN")


def test_unknown_language_is_a_post_fail(tmp_path):
    build, story, styles = tp._setup(tmp_path)
    report = tp._run(build, story, styles, language="fr")
    assert report["fail"] is True and report["written"] is False
