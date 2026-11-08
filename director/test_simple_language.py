"""Offline tests for director/simple_language.py. No network, no model call."""
import json

import pytest

import simple_language as sl

MR_LLA = "ळ"


def _write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


def test_real_word_lists_load_and_have_content():
    hi = sl.load_lists("hi")
    mr = sl.load_lists("mr")
    for lists in (hi, mr):
        assert len(lists.whitelist) >= 100
        assert len(lists.stiff) >= 100
        assert len(lists.leaks) >= 40
        assert all(v for v in lists.stiff.values())
        assert "STARTER" in lists.status


def test_whitelist_words_never_flagged():
    text = "ऋषि यज्ञ धर्म ब्रह्म गजानन महाराज देविदास वेद मुनी। ब्रह्मानंद॥"
    for lang in ("hi", "mr"):
        r = sl.check_text(text, lang)
        assert r["ok"] is True
        assert r["flags"] == []


def test_whitelist_beats_stiff_list(tmp_path):
    _write(tmp_path / sl.SACRED_FILE, {"whitelist": {"x": ["यज्ञ", "समर्थ गजानन"]}})
    _write(tmp_path / "simple_language_mr.json", {"stiff_words": {"यज्ञ": "सोपे", "गजानन": "नाव"}, "leaks": {}})
    assert sl.check_text("यज्ञ सुरू झाला", "mr", tmp_path)["ok"] is True
    # whole phrase is masked, so the stiff word inside it is not flagged...
    assert sl.check_text("समर्थ गजानन", "mr", tmp_path)["ok"] is True
    # ...but the same word on its own still is
    bare = sl.check_text("गजानन", "mr", tmp_path)
    assert [f["word"] for f in bare["flags"]] == ["गजानन"]


def test_stiff_word_flagged_with_suggestion():
    r = sl.check_text("भक्त ने अवलोकन किया।", "hi")
    assert r["ok"] is False
    assert [(f["word"], f["suggestion"], f["code"]) for f in r["flags"]] == [("अवलोकन", "देखना", "STIFF-01")]


def test_devanagari_danda_does_not_hide_a_word():
    assert [f["word"] for f in sl.check_text("अवलोकन।", "hi")["flags"]] == ["अवलोकन"]
    assert sl.check_text("ऋषि॥ यज्ञ।", "mr")["ok"] is True


def test_hindi_leak_in_marathi_flagged():
    r = sl.check_text("तो घरात है आणि खुश आहे", "mr")
    leaks = [(f["word"], f["suggestion"], f["code"]) for f in r["flags"]]
    assert leaks == [("है", "आहे", "LEAK-01")]


def test_marathi_detected_by_lla_and_postpositions():
    text = f"बा{MR_LLA} शाळेला गेले"  # no whole-word Marathi marker here: the letters decide it
    r = sl.detect_marathi(text)
    assert r["language"] == "mr"
    assert r["evidence"]["letter_lla"] == text.count(MR_LLA) == 2
    r = sl.detect_marathi("त्यांनी मला सांगितले की ते घरी आहे")
    assert r["language"] == "mr"
    assert r["score"] > 0
    assert "मला" in r["evidence"]["mr_tokens"]


def test_hindi_text_not_detected_as_marathi():
    r = sl.detect_marathi("उन्होंने मुझे बताया कि वह घर में है और खुश है")
    assert r["language"] == "hi"
    assert r["score"] < 0


def test_detection_unknown_for_latin_and_empty():
    for text in ("hello world", "", None):
        r = sl.detect_marathi(text)
        assert r["language"] == "unknown"
        assert r["score"] == 0.0


def test_language_mismatch_flagged_as_lang01():
    r = sl.check_text("उन्होंने मुझे बताया कि वह घर में है और खुश है", "mr")
    assert any(f["code"] == "LANG-01" for f in r["flags"])


def test_caption_word_limit_cap01():
    six = {"id": "S1", "caption": "एक दो तीन चार पाँच छह"}
    seven = {"id": "S2", "caption": "एक दो तीन चार पाँच छह सात"}
    ok_rows = sl.check_shot_texts([six])
    bad_rows = sl.check_shot_texts([seven])
    assert ok_rows[0]["ok"] is True
    assert bad_rows[0]["ok"] is False
    assert bad_rows[0]["flags"][0]["code"] == "CAP-01"
    assert bad_rows[0]["flags"][0]["where"] == "caption"


def test_caption_counts_digits_and_skips_separators():
    # "१८७८ / 1878" is two words, not three
    assert sl.word_count("१८७८ / 1878") == 2
    assert sl.word_count("।") == 0


def test_empty_and_none_text_safe():
    assert sl.check_text(None, "hi")["ok"] is True
    assert sl.check_text("", "mr")["ok"] is True
    assert sl.check_text("   ", "en")["ok"] is True
    assert sl.check_text("anything at all", "en")["flags"] == []
    assert sl.check_shot_texts([]) == []
    assert sl.check_shot_texts(None) == []
    rows = sl.check_shot_texts([{}, {"audio_and_dialogue_track": {"narration": None, "dialogue": None}},
                                {"caption": None}])
    assert [r["ok"] for r in rows] == [True, True, True]
    bad = sl.check_shot_texts(["not a row"])
    assert bad[0]["flags"][0]["code"] == "ROW-01"


def test_narration_and_dialogue_walked_with_language_inheritance():
    row = {"id": "S3", "audio_and_dialogue_track": {
        "narration": {"text": "त्यांनी मला सांगितले, ते घरी आहे", "language": "mr", "time_range": [0, 2]},
        "dialogue": [{"speaker": "x", "text": "अवलोकन करा", "tone": "calm", "time_range": [2, 3]}]}}
    r = sl.check_shot_texts([row])[0]
    assert r["ok"] is False
    assert [f["where"] for f in r["flags"]] == ["dialogue[0].text"]
    assert r["flags"][0]["suggestion"] == "पाहणे"


def test_default_lang_used_when_text_has_no_language():
    row = {"id": "S4", "audio_and_dialogue_track": {"narration": {"text": "अवलोकन करा"}}}
    assert sl.check_shot_texts([row])[0]["ok"] is True  # no language: auto-detect finds nothing, skipped
    r = sl.check_shot_texts([row], default_lang="hi")[0]
    assert [f["word"] for f in r["flags"]] == ["अवलोकन"]


def test_json_load_failure_is_clear(tmp_path):
    (tmp_path / sl.SACRED_FILE).write_text("{not json", encoding="utf-8")
    _write(tmp_path / "simple_language_hi.json", {"stiff_words": {}, "leaks": {}})
    with pytest.raises(sl.SimpleLanguageDataError, match="not valid JSON") as exc:
        sl.check_text("नमस्ते", "hi", tmp_path)
    assert str(tmp_path) in str(exc.value)


def test_missing_list_and_bad_shape_are_clear(tmp_path):
    with pytest.raises(sl.SimpleLanguageDataError, match="missing"):
        sl.load_lists("hi", tmp_path)
    _write(tmp_path / sl.SACRED_FILE, {"whitelist": {"x": ["यज्ञ"]}})
    _write(tmp_path / "simple_language_hi.json", {"stiff_words": {"two words": "x"}, "leaks": {}})
    with pytest.raises(sl.SimpleLanguageDataError, match="single words"):
        sl.load_lists("hi", tmp_path)


def test_cli_exit_codes(tmp_path, capsys):
    clean = _write(tmp_path / "clean.json", [{"id": "S1", "caption": "ऋषि यज्ञ"}])
    dirty = _write(tmp_path / "dirty.json", [{"id": "S2", "caption": "एक दो तीन चार पाँच छह सात"}])
    broken = tmp_path / "broken.json"
    broken.write_text("[", encoding="utf-8")
    assert sl.main([str(clean)]) == 0
    assert sl.main([str(dirty)]) == 1
    out = capsys.readouterr().out
    assert "CAP-01" in out
    assert sl.main([str(broken)]) == 2
    assert sl.main([str(tmp_path / "nope.json")]) == 2


def test_english_word_list_loads():
    en = sl.load_lists("en")
    assert len(en.stiff) >= 200
    assert len(en.whitelist) >= 100
    assert en.leaks == {}
    assert "ashtavakra" in en.whitelist and "janaka" in en.whitelist  # stored lowercase
    assert "STARTER" in en.status


def test_english_stiff_words_flagged_with_plain_suggestion():
    r = sl.check_text("We shall endeavour to ascertain the facts.", "en")
    assert [(f["word"], f["suggestion"], f["code"]) for f in r["flags"]] == [
        ("shall", "will", "STIFF-01"), ("endeavour", "try", "STIFF-01"), ("ascertain", "find out", "STIFF-01")]
    assert sl.check_text("We will try to find out the facts.", "en")["ok"] is True


def test_english_names_never_flagged_any_case():
    text = "Sage Ashtavakra and King Janaka met Gajanan Maharaj at Kashi on the bank of the Ganga."
    assert sl.check_text(text, "en")["ok"] is True
    assert sl.check_text("ashtavakra met JANAKA", "en")["ok"] is True


def test_english_phrase_masks_stiff_word_inside_name(tmp_path):
    _write(tmp_path / sl.SACRED_FILE, {"whitelist": {"x": []}})
    _write(tmp_path / "simple_language_en.json",
           {"whitelist": {"n": ["Sage Ashtavakra"]}, "stiff_words": {"sage": "wise man"}})
    assert sl.check_text("Sage Ashtavakra spoke.", "en", tmp_path)["ok"] is True
    bare = sl.check_text("The sage spoke.", "en", tmp_path)
    assert [f["word"] for f in bare["flags"]] == ["sage"]


def test_english_sentence_over_18_words_sen01():
    nineteen = " ".join(["word"] * 19) + "."
    eighteen = " ".join(["word"] * 18) + "."
    bad = sl.check_text(nineteen, "en")
    assert [f["code"] for f in bad["flags"]] == ["SEN-01"]
    assert sl.check_text(eighteen, "en")["ok"] is True
    # splitting the long sentence clears it
    assert sl.check_text(" ".join(["word"] * 10) + ". " + " ".join(["word"] * 9) + ".", "en")["ok"] is True


def test_devanagari_in_english_text_is_wrong_script():
    r = sl.check_text("नमस्ते", "en")
    assert r["ok"] is False
    assert r["flags"][0]["code"] == "SCRIPT-01"


def test_latin_only_in_hindi_or_marathi_is_wrong_script_except_names():
    assert [f["code"] for f in sl.check_text("Hello friends", "hi")["flags"]] == ["SCRIPT-02"]
    assert [f["code"] for f in sl.check_text("Hello friends", "mr")["flags"]] == ["SCRIPT-02"]
    assert sl.check_text("Ashtavakra", "hi")["ok"] is True  # a name alone is fine
    assert sl.check_text("गजानन Maharaj", "mr")["ok"] is True  # Devanagari present: mixed text is not checked here


def test_hindi_perfective_forms_are_not_flagged():
    # होता / होती / होते are ordinary Hindi, not Marathi leaks
    assert sl.check_text("यह कैसे होता है।", "hi")["ok"] is True
    assert sl.check_text("वह ऐसा होती थी।", "hi")["ok"] is True


def test_three_language_shot_checked_per_language():
    row = {"id": "S9",
           "audio_and_dialogue_track": {
               "narration": {"text": "We shall endeavour to find the sage.", "language": "en", "time_range": [0, 3]},
               "narration_by_lang": {
                   "en": {"text": "We shall endeavour to find the sage.", "time_range": [0, 3]},
                   "hi": {"text": "भक्त ने अवलोकन किया।", "time_range": [0, 3]},
                   "mr": {"text": "त्यांनी मला सांगितले, ते घरी आहे", "time_range": [0, 3]}},
               "dialogue_by_lang": {
                   "en": [{"speaker": "S1", "text": "Come home now."}],
                   "hi": [{"speaker": "S1", "text": "घर चलो।"}],
                   "mr": [{"speaker": "S1", "text": "तो घरात है"}]}},
           "captions_by_lang": {"en": "Find the sage", "hi": "संत को खोजो",
                                "mr": "एक दो तीन चार पाँच छह सात आठ"}}
    r = sl.check_shot_texts([row])[0]
    assert r["shot"] == "S9"
    assert r["ok"] is False
    assert set(r["by_language"]) == {"en", "hi", "mr"}
    codes = {lang: sorted(f["code"] for f in b["flags"]) for lang, b in r["by_language"].items()}
    assert codes == {"en": ["STIFF-01", "STIFF-01"], "hi": ["STIFF-01"], "mr": ["CAP-01", "LEAK-01"]}
    assert r["by_language"]["en"]["ok"] is False
    assert {f["where"] for f in r["flags"]} == {"narration_by_lang.en.text", "narration_by_lang.hi.text",
                                                 "dialogue_by_lang.mr[0].text", "captions_by_lang.mr"}


def test_three_language_shot_all_clean():
    row = {"id": "S10", "audio_and_dialogue_track": {
        "narration_by_lang": {"en": {"text": "The sage sat by the Ganga."},
                              "hi": {"text": "संत गंगा किनारे बैठे थे।"},
                              "mr": {"text": "संत गंगेच्या काठी बसले होते."}}}}
    r = sl.check_shot_texts([row])[0]
    assert r["ok"] is True
    assert set(r["by_language"]) == {"en", "hi", "mr"}


def test_by_lang_block_replaces_primary_copy_and_bad_key_is_flagged():
    row = {"id": "S11", "audio_and_dialogue_track": {
        "narration": {"text": "We shall endeavour.", "language": "en"},  # primary copy: not checked twice
        "narration_by_lang": {"en": {"text": "Please wait."}, "xx": {"text": "hello"}}}}
    r = sl.check_shot_texts([row])[0]
    codes = [f["code"] for f in r["flags"]]
    assert codes == ["LANG-02"]


def test_story_output_language_drives_untagged_texts():
    story = {"output_language": "en", "shots": [
        {"id": "S12", "audio_and_dialogue_track": {"narration": {"text": "We shall endeavour."}}}]}
    r = sl.check_shot_texts(story)[0]
    assert [f["word"] for f in r["flags"]] == ["shall", "endeavour"]
    assert set(r["by_language"]) == {"en"}


def test_cli_accepts_english_lang(tmp_path, capsys):
    clean = _write(tmp_path / "en.json", [{"id": "S1", "audio_and_dialogue_track": {"narration": {"text": "The sage spoke."}}}])
    assert sl.main([str(clean), "--lang", "en"]) == 0


def test_ne_alone_is_hindi_and_aai_mother_is_not_a_leak_in_marathi():
    # Kalika 3e1 (11-08): standalone "ne" is the Hindi ergative marker; "aai" is Marathi for mother
    hi = sl.check_text("कामदेव ने सोचा: ब्रह्मा जी ने कहा शिव भी। अभी आज़माता हूँ।", "hi")
    assert hi["language_detected"] != "mr" and not any(f["code"] == "LANG-01" for f in hi["flags"])
    mr = sl.check_text("आकाशाच्या आधी, काळाच्या आधी, काली आई होती.", "mr")
    assert not any(f["word"] == "आई" for f in mr["flags"])
