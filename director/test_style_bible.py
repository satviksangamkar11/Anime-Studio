import json

import pytest

import style_bible as sb

BANNED = ("ramayana", "solo leveling", "ufotable", "a-1", "pixar", "disney")
CHARS = ["CHAR-KRISHNA", "CHAR-BALARAMA", "CHAR-YASHODA", "CHAR-NANDA", "CHAR-SHRIDAMA",
         "CHAR-MADHUMANGAL", "CHAR-KALIYA", "CHAR-NAGAPATNI", "CHAR-NAGA-CHILD", "CHAR-GARUDA", "CHAR-GOPI"]
ENVS = ["ENV-KADAMBA-BANK", "ENV-KALIYA-DAH-POISONED", "ENV-KALIYA-DAH-PURIFIED",
        "ENV-CAVERN", "ENV-BRAJ-VILLAGE", "ENV-VRINDAVAN-FOREST"]
PROPS = ["PROP-KALI-KAMLI", "PROP-KANDUK", "PROP-AMRIT-KALASH", "PROP-MOR-MUKUT", "PROP-FLUTE"]
PHYSICS = ("running", "wind", "water", "turning")


@pytest.fixture(scope="module")
def bible():
    return sb.load("kaliya_mardan")


def _all_ids(bible):
    return [item["id"] for key in ("characters", "environments", "props") for item in bible[key]]


def test_loads_and_has_required_ids(bible):
    assert set(CHARS + ENVS + PROPS) <= sb.ids(bible)
    assert bible["palette"]["rule"]
    assert bible["rim_light"]["limit"]


def test_ids_unique(bible):
    ids_list = _all_ids(bible)
    assert len(ids_list) == len(set(ids_list))
    assert sb.ids(bible) == set(ids_list)


@pytest.mark.parametrize("char_id", CHARS)
def test_character_has_proportions_physics_and_drift(bible, char_id):
    char = next(c for c in bible["characters"] if c["id"] == char_id)
    assert "proportions_heads" in char
    assert char["forbidden_drift"], char_id
    assert char["costume"], char_id
    for piece in char["costume"]:
        assert set(PHYSICS) <= set(piece["physics"]), (char_id, piece["piece"])


def test_krishna_not_generic_hero(bible):
    krishna = next(c for c in bible["characters"] if c["id"] == "CHAR-KRISHNA")
    assert krishna["proportions_heads"] == 5.5
    assert any("generic" in d for d in krishna["forbidden_drift"])
    assert "cyan" not in krishna["skin"]["treatment"].split(";")[0]


def test_no_fixed_hood_count(bible):
    kaliya = next(c for c in bible["characters"] if c["id"] == "CHAR-KALIYA")
    assert kaliya["proportions_heads"] is None
    assert "7-9" in kaliya["proportion_rule"]


@pytest.mark.parametrize("entity_id", CHARS + ENVS + PROPS)
def test_prompt_block_short_and_clean(bible, entity_id):
    text = sb.prompt_block(bible, entity_id)
    assert 0 < len(text) <= 600
    low = text.lower()
    assert not any(b in low for b in BANNED), entity_id


def test_prompt_block_unknown_id_raises(bible):
    with pytest.raises(KeyError):
        sb.prompt_block(bible, "CHAR-NOPE")


@pytest.mark.parametrize("char_id", CHARS)
def test_flow_sheet_prompt(bible, char_id):
    text = sb.flow_sheet_prompt(bible, char_id)
    assert "Panel 1" in text and "Panel 2" in text and "Panel 3" in text
    assert "#808080" in text
    assert not any(b in text.lower() for b in BANNED)


def test_flow_sheet_rejects_non_character(bible):
    with pytest.raises(ValueError):
        sb.flow_sheet_prompt(bible, "ENV-CAVERN")


def test_bible_text_outside_references_is_clean(bible):
    body = {k: v for k, v in bible.items() if k != "references"}
    low = json.dumps(body, ensure_ascii=False).lower()
    assert not any(b in low for b in BANNED)


def test_references_have_status(bible):
    for ref in bible["references"]:
        assert ref["status"] in ("opened",) or ref["status"].startswith("UNVERIFIED") or ref["status"].startswith("taken")
