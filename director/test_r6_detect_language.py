"""Q-R5-3 (2026-11-07): detect_language uses Marathi and Hindi function words, not only the letter u0933."""
import run_registry as rr

HINDI = "यह एक कहानी है और मुझे यह बहुत पसंद है क्योंकि इसमें बच्चा नदी में कूदता है और सब लोग उसे देखते हैं"
MARATHI_NO_LLA = "ही एक गोष्ट आहे आणि मला ती खूप आवडते कारण त्यात मुलगा नदीत उडी मारतो आणि सर्वजण त्याला पाहतात आहेत"
MARATHI_LLA = "मुलगा गोकुळात राहत होता आणि तो रोज वेळेवर नदीवर जात असे आणि गाई चारत असे"


def test_short_or_latin_text_is_english():
    assert rr.detect_language("Hello world, this is English.") == "en"
    assert rr.detect_language("नमस्ते") == "en"


def test_hindi_text_is_hindi():
    assert rr.detect_language(HINDI) == "hi"


def test_marathi_without_the_letter_lla_is_marathi():
    assert "ळ" not in MARATHI_NO_LLA
    assert rr.detect_language(MARATHI_NO_LLA) == "mr"


def test_marathi_with_the_letter_lla_is_marathi():
    assert "ळ" in MARATHI_LLA and rr.detect_language(MARATHI_LLA) == "mr"


def test_tie_is_hindi():
    assert rr.detect_language("कहानी " * 8) == "hi"
