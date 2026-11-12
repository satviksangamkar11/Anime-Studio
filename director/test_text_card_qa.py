import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import text_card_qa as t  # noqa: E402

GOOD_BOX = (100, 300, 900, 1300)


def test_box_inside_text_safe_passes():
    assert t.box_problems(GOOD_BOX) == []


def test_box_left_of_margin_fails():
    assert any("x0" in p for p in t.box_problems((80, 300, 900, 1300)))


def test_box_right_of_margin_fails():
    assert any("x1" in p for p in t.box_problems((100, 300, 931, 1300)))


def test_box_above_top_margin_fails():
    assert any("y0" in p for p in t.box_problems((100, 240, 900, 1300)))


def test_box_below_bottom_line_fails():
    assert any("y1" in p for p in t.box_problems((100, 300, 900, 1421)))


def test_box_exact_edges_pass():
    assert t.box_problems((90, 250, 930, 1420)) == []


def test_no_conjunct_in_text_requires_nothing():
    assert t.required_conjuncts("कुछ नहीं") == []
    assert t.check_conjuncts("", "कुछ नहीं") == []


def test_conjunct_present_passes():
    assert t.check_conjuncts("ब्रह्मा ने कहा", "ब्रह्मा ने कहा") == []


def test_conjunct_missing_in_ocr_fails():
    assert t.check_conjuncts("ब्रह्म ने कहा", "ब्रह्मा ने कहा") == ["ब्रह्मा"]


def test_all_three_required_conjuncts_detected():
    text = "ब्रह्मा क्या दक्ष"
    assert t.required_conjuncts(text) == ["ब्रह्मा", "क्या", "दक्ष"]


def test_frame_check_ok_when_inside_box_and_text_matches():
    items = [{"text": "ब्रह्मा ने कहा", "box": GOOD_BOX}]
    res = t.check_card_frame(items, "ब्रह्मा ने कहा")
    assert res == {"ok": True, "problems": []}


def test_frame_check_fails_when_item_outside_box():
    items = [{"text": "ब्रह्मा ने कहा", "box": (50, 1300, 800, 1400)}]
    res = t.check_card_frame(items, "ब्रह्मा ने कहा")
    assert res["ok"] is False and any("x0" in p for p in res["problems"])


def test_frame_check_fails_on_conjunct_loss():
    items = [{"text": "ब्रह्म ने कहा", "box": GOOD_BOX}]
    res = t.check_card_frame(items, "ब्रह्मा ने कहा")
    assert res["ok"] is False and any("ब्रह्मा" in p for p in res["problems"])


def test_card_words_en_limit_four():
    assert t.card_word_problems("one two three four", "en") == []
    assert t.card_word_problems("one two three four five", "en") != []


def test_card_words_hindi_limit_three_and_18_chars():
    assert t.card_word_problems("क्या ब्रह्मा दक्ष", "hi") == []
    assert t.card_word_problems("क्या ब्रह्मा दक्ष अब", "hi") != []
    assert t.card_word_problems("ब्रह्मा ब्रह्मा ब्रह्मा ब्रह्मा ब्रह्मा", "mr") != []


def test_title_card_limit_six_words():
    assert t.card_word_problems("a b c d e f", "en", title=True) == []
    assert t.card_word_problems("a b c d e f g", "en", title=True) != []


# M-31: an inverted or non-finite box must not pass as "safe"
def test_inverted_box_fails():
    assert any("inverted" in p for p in t.box_problems((500, 500, 400, 600)))
    assert any("inverted" in p for p in t.box_problems((500, 500, 600, 400)))
    assert t.check_card_frame([{"box": (500, 500, 400, 600), "text": "x"}], "x")["ok"] is False


def test_non_finite_box_fails():
    assert t.box_problems((100, 300, float("nan"), 1300))
    assert t.box_problems((100, 300, float("inf"), 1300))


def test_check_cards_filters_by_lang_and_reports_problems():
    cards = [{"lang": "hi", "expected_text": "ब्रह्मा", "items": [{"text": "ब्रम्हा", "box": GOOD_BOX}]},
             {"lang": "en", "expected_text": "one two three four five", "items": [{"text": "x", "box": (0, 0, 10, 10)}]}]
    hi = t.check_cards(cards, "hi")
    assert len(hi) == 1 and "conjunct lost" in hi[0]
    en = t.check_cards(cards, "en")
    assert any("x0" in p for p in en) and any("max 4" in p for p in en)
    assert t.check_cards(cards, "mr") == []
