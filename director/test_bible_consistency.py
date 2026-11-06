"""WP0 / A13 / A28: the bible's skin fields must not contradict CHAR-KRISHNA's forbidden list.

Only palette.skin_range and CHAR-KRISHNA.skin.treatment are checked, never the whole file.
"""
import json
import re
from pathlib import Path

BIBLE = Path(__file__).resolve().parent / "style" / "kaliya_mardan.json"

# Old wording, kept inline as the regression subject (WP0 removed it from the bible).
OLD_SKIN_RANGE = (
    "Indian complexions varied by character (see characters). No lightened skin on any "
    "character; Krishna is cloud-dark indigo-grey."
)
OLD_TREATMENT = (
    "soft cloud-blue skin, lighter than the old indigo-grey; flat cel tones: base #AFCCEA, "
    "light #B3D1F7, core shadow #7990B9 (sampled from the approved identity master, "
    "KRISHNA_IDENTITY_MASTER__v01__edit2_candA.png, skin areas); a soft warm cheek blush kept light"
)


def _krishna():
    bible = json.loads(BIBLE.read_text(encoding="utf-8"))
    return bible, next(c for c in bible["characters"] if c["id"] == "CHAR-KRISHNA")


def _phrases(char):
    """Forbidden phrases: skin.forbidden split on ';' and ',', plus forbidden_drift entries."""
    items = re.split(r"[;,]", char["skin"]["forbidden"]) + list(char.get("forbidden_drift", []))
    phrases = []
    for item in items:
        text = re.sub(r"\([^)]*\)", "", item).strip().lower()
        if len(text) >= 8:
            phrases.append(text)
            if text.endswith(" skin") and len(text) - 5 >= 8:   # also the bare colour phrase: "dark indigo-grey"
                phrases.append(text[:-5].strip())
    return phrases


def _hits(texts, phrases):
    """Return (field, phrase) for every forbidden phrase found as a lower-case substring."""
    found = []
    for field, text in texts.items():
        low = text.lower()
        for phrase in phrases:
            if phrase in low:
                found.append((field, phrase))
    return found


def test_skin_fields_do_not_contradict_forbidden_list():
    bible, krishna = _krishna()
    texts = {
        "palette.skin_range": bible["palette"]["skin_range"],
        "CHAR-KRISHNA.skin.treatment": krishna["skin"]["treatment"],
    }
    assert _hits(texts, _phrases(krishna)) == []


def test_check_catches_the_real_old_skin_range_text():
    # Regression proof on the literal pre-WP0 sentence "Krishna is cloud-dark indigo-grey".
    _, krishna = _krishna()
    hits = _hits({"palette.skin_range": OLD_SKIN_RANGE}, _phrases(krishna))
    assert ("palette.skin_range", "dark indigo-grey") in hits


def test_current_krishna_skin_texts_never_say_indigo_grey():
    bible, krishna = _krishna()
    assert "indigo-grey" not in bible["palette"]["skin_range"].lower()
    assert "indigo-grey" not in krishna["skin"]["treatment"].lower()


def test_check_fails_on_a_contradicting_text():
    # Negative proof: the same check reports a hit when a forbidden phrase is written back in.
    # The literal OLD texts contain no phrase from the list (see report), so the old
    # "cloud-dark indigo-grey" sentence is rewritten into the forbidden form for this test.
    _, krishna = _krishna()
    regressed_range = OLD_SKIN_RANGE.replace("cloud-dark indigo-grey.", "dark indigo-grey skin.")
    regressed = {"palette.skin_range": regressed_range, "CHAR-KRISHNA.skin.treatment": OLD_TREATMENT}
    hits = _hits(regressed, _phrases(krishna))
    assert ("palette.skin_range", "dark indigo-grey skin") in hits
