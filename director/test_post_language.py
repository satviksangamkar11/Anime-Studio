"""Owner rule 2026-11-07: English reels get English captions, Hindi reels Hindi, Marathi reels Marathi, and the caption text is
the spoken script of that language (post.py --language, spoken cues from Gate D's caption_cues)."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_post as tp  # noqa: E402

TEXT = {"en": "Krishna jumps into the river.", "hi": "कृष्ण यमुना में कूद पड़ा।", "mr": "कृष्ण यमुनेत उडी मारतो."}


def _shots_with_script():
    shots = [tp._shot("SHOT_A"), tp._shot("SHOT_B")]
    for sid_shot in shots:   # no hook caption: the spoken script is the caption
        sid_shot["metadata"]["look"]["hook"]["caption"] = "Hook line"
    shots[0]["audio_and_dialogue_track"] = {
        "narration_by_lang": {lang: {"text": text, "time_range": [0.2, 1.8]} for lang, text in TEXT.items()}}
    return shots


def _ass(build):
    return (build / "post" / "captions.ass").read_text(encoding="utf-8")


def test_each_language_burns_its_own_spoken_script(tmp_path):
    for lang in ("en", "hi", "mr"):
        build, story, styles = tp._setup(tmp_path / lang, shots=_shots_with_script())
        report = tp._run(build, story, styles, language=lang)
        ass = _ass(build)
        assert TEXT[lang].rstrip(".।") in ass, lang
        for other in set(TEXT) - {lang}:
            assert TEXT[other].rstrip(".।") not in ass, (lang, other)
        assert "Hook line" not in ass          # the spoken script replaces the hook caption
        assert report["written"] is True and report["output"].endswith(f"EP1_final_{lang}.mp4")
        sidecar = next(build.glob(f"EP1_final_{lang}.{lang}.srt"))
        assert TEXT[lang].rstrip(".।") in sidecar.read_text(encoding="utf-8")


def test_devanagari_in_an_english_reel_refuses(tmp_path):
    shots = _shots_with_script()
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"]["en"]["text"] = TEXT["hi"]
    build, story, styles = tp._setup(tmp_path, shots=shots)
    report = tp._run(build, story, styles, language="en")
    assert report["fail"] is True and report["written"] is False and not list(build.glob("EP1_final*.mp4"))
    assert any("contains Devanagari" in e["message"] for e in report["entries"] if e["level"] == "FAIL")


def test_latin_only_caption_in_a_hindi_reel_refuses(tmp_path):
    shots = _shots_with_script()
    shots[0]["audio_and_dialogue_track"]["narration_by_lang"]["hi"]["text"] = "Krishna jumps"
    build, story, styles = tp._setup(tmp_path, shots=shots)
    report = tp._run(build, story, styles, language="hi")
    assert report["fail"] is True and report["written"] is False
    assert any("has no Devanagari" in e["message"] for e in report["entries"] if e["level"] == "FAIL")


def test_no_spoken_script_falls_back_to_the_hook_caption_with_a_warning(tmp_path):
    build, story, styles = tp._setup(tmp_path)   # plain shots: no audio_and_dialogue_track
    report = tp._run(build, story, styles, language="en")
    assert "Hook line" in _ass(build) and report["written"] is True
    assert any("no spoken en script" in e["message"] for e in report["entries"] if e["level"] == "WARN")


def test_unknown_language_is_a_post_fail(tmp_path):
    build, story, styles = tp._setup(tmp_path)
    report = tp._run(build, story, styles, language="fr")
    assert report["fail"] is True and report["written"] is False
