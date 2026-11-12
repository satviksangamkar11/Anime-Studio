"""Text-card QA (A-04): a caption or title card frame must sit inside the text-safe box and keep every Devanagari
conjunct that the card text uses, and the card must respect the word limits of Amendment D (rule 51).

Input is what an OCR pass already read from a frame: a list of {"text": str, "box": (x0, y0, x1, y1)} in pixels of a
1080x1920 frame. No OCR runs here (no model call). The box is a parameter until core/core.json carries it (M-10).
"""
import math
import unicodedata

FRAME_W, FRAME_H = 1080, 1920
TEXT_SAFE = (90, 250, 930, 1420)   # x0, y0, x1, y1 on 1080x1920 (top 13%, bottom 26%, right 14%)
CONJUNCTS = ("ब्रह्मा", "क्या", "दक्ष")


def _nfc(text):
    return unicodedata.normalize("NFC", text or "")


def required_conjuncts(text):
    """The conjuncts of CONJUNCTS that the card text uses, in list order."""
    t = _nfc(text)
    return [c for c in CONJUNCTS if c in t]


def check_conjuncts(ocr_text, expected_text):
    """Conjuncts the card text uses that the OCR text lost."""
    ocr = _nfc(ocr_text)
    return [c for c in required_conjuncts(expected_text) if c not in ocr]


def box_problems(box, safe=TEXT_SAFE):
    x0, y0, x1, y1 = box
    sx0, sy0, sx1, sy1 = safe
    problems = []
    if not all(math.isfinite(v) for v in box):
        return ["box %r has a non-finite coordinate" % (box,)]
    if x0 > x1 or y0 > y1:
        return ["box %r is inverted (x0 > x1 or y0 > y1)" % (box,)]
    if x0 < sx0:
        problems.append("x0 %s left of text-safe %s" % (x0, sx0))
    if y0 < sy0:
        problems.append("y0 %s above text-safe %s" % (y0, sy0))
    if x1 > sx1:
        problems.append("x1 %s right of text-safe %s" % (x1, sx1))
    if y1 > sy1:
        problems.append("y1 %s below text-safe %s" % (y1, sy1))
    return problems


def check_card_frame(items, expected_text, safe=TEXT_SAFE):
    problems = []
    for item in items:
        for p in box_problems(item["box"], safe):
            problems.append("%r: %s" % (item.get("text", ""), p))
    ocr_text = " ".join(item.get("text", "") for item in items)
    for c in check_conjuncts(ocr_text, expected_text):
        problems.append("conjunct lost: %s" % c)
    return {"ok": not problems, "problems": problems}


def card_word_problems(text, lang, title=False):
    words = _nfc(text).split()
    if title:
        return [] if len(words) <= 6 else ["title card has %d words (max 6)" % len(words)]
    if lang == "en":
        return [] if len(words) <= 4 else ["en card has %d words (max 4)" % len(words)]
    if lang in ("hi", "mr"):
        problems = []
        if len(words) > 3:
            problems.append("%s card has %d words (max 3)" % (lang, len(words)))
        if len(_nfc(text)) > 18:
            problems.append("%s card has %d characters (max 18)" % (lang, len(_nfc(text))))
        return problems
    return []


def check_cards(cards, lang):
    """Problems of every OCR card of `lang` (G22). A card is {"lang", "expected_text", "title"?, "items": [{"text", "box"}]};
    each is checked for the text-safe box, lost conjuncts and the word limits. Returns a list of problem strings."""
    problems = []
    for i, card in enumerate(c for c in cards if c.get("lang") == lang):
        expected = card.get("expected_text", "")
        rep = check_card_frame(card.get("items", []), expected)
        words = card_word_problems(expected, lang, title=bool(card.get("title")))
        problems += ["card %d: %s" % (i + 1, p) for p in rep["problems"] + words]
    return problems
