import json

import pytest

from core.style_pack import (
    delta_e_2000,
    l_star,
    load_core,
    load_pack,
    srgb_to_lab,
    validate_pack,
)


# ---- CIEDE2000 (Sharma, Wu, Dalal 2005 test pairs), tolerance 1e-4 ----
SHARMA = [
    ((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
    ((50, 3.1571, -77.2803), (50, 0, -82.7485), 2.8615),
    ((50, 2.8361, -74.0200), (50, 0, -82.7485), 3.4412),
    ((50, -1.3802, -84.2814), (50, 0, -82.7485), 1.0000),
    ((50, 2.5, 0), (50, 0, -2.5), 4.3065),
]


@pytest.mark.parametrize("lab1, lab2, expected", SHARMA)
def test_delta_e_2000_matches_sharma_pairs(lab1, lab2, expected):
    assert delta_e_2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)


def test_delta_e_2000_is_zero_for_same_colour_and_symmetric():
    x = (52.3, -12.4, 30.1)
    assert delta_e_2000(x, x) == pytest.approx(0.0, abs=1e-9)
    a, b = (40.0, 20.0, -10.0), (60.0, -5.0, 25.0)
    assert delta_e_2000(a, b) == pytest.approx(delta_e_2000(b, a), abs=1e-9)


# ---- sRGB -> Lab ----
def test_l_star_white_and_black():
    assert l_star("#FFFFFF") == pytest.approx(100, abs=0.01)
    assert l_star("#000000") == pytest.approx(0, abs=0.01)


def test_srgb_to_lab_white_is_neutral():
    L, a, b = srgb_to_lab((255, 255, 255))
    assert L == pytest.approx(100, abs=0.01)
    assert a == pytest.approx(0, abs=0.01)
    assert b == pytest.approx(0, abs=0.01)


def test_srgb_to_lab_accepts_hex_without_hash_and_tuple():
    assert srgb_to_lab("FF8800") == pytest.approx(srgb_to_lab((255, 136, 0)))


@pytest.mark.parametrize("bad", ["#GGGGGG", "#12345", (256, 0, 0), (1, 2), "nope"])
def test_srgb_to_lab_rejects_invalid_input(bad):
    with pytest.raises(ValueError):
        srgb_to_lab(bad)


# ---- core.json ----
def test_core_json_has_spec_keys_and_version():
    core = load_core()
    assert core["version"] == "1.2"
    assert core["fps"] == 24
    assert set(core) == {
        "version", "_caption_note", "default_style_pack", "fps", "delivery", "safe_zone_frac", "safe_zone_templates", "captions", "retention",
        "impact", "flash", "gates", "sound_sync",
    }
    assert core["gates"]["sat_avg_ceiling"] is None
    assert core["sound_sync"] == {"enabled": False}


# ---- minimal valid pack and a broken pack ----
def minimal_pack():
    return {
        "pack_id": "test_pack",
        "version": "1.2",
        "status": "draft",
        "colour_script": {
            "phases": [
                {"id": "PH-A", "role": "play", "luma_mean": [0.2, 0.5], "sat_mean": [0.3, 0.6],
                 "lut": "luts/test_pack/a.cube"},
            ],
        },
        "acts": {
            "HOOK": {"role": "hook", "phase": "PH-A", "lut": "luts/test_pack/hook.cube",
                     "luma_mean": [0.2, 0.5], "sat_mean": [0.3, 0.6]},
        },
        "palettes": {
            "p1": {
                "characters": ["CHAR-X"],
                "time_lock": None,
                "colors": {
                    "Red": {"hex": "#FF0000", "role": "robe", "usage_pct": 10, "neon": False},
                    "Blue": {"hex": "#0000FF", "role": "sky", "usage_pct": 5, "neon": False},
                },
                "special_laws": [],
            },
        },
        "frame_law": {"min_dL_focal_vs_bg": None, "max_neon_hues_per_shot": 0,
                      "pure_white_area_cap_frac": 0.08},
        "impact": {"allowed_types": [], "type_max_frames": {}},
        "typography": {"display": None, "sacred": None, "subtitle_latin": "Inter",
                       "subtitle_devanagari": "Noto Sans Devanagari", "min_px_at_1080w": 22,
                       "font_dir": "styles/fonts"},
        "prompt_forbidden_words": [],
        "guardrails": ["no gore"],
    }


def test_minimal_valid_pack_has_no_errors():
    assert validate_pack(minimal_pack()) == []


def test_unknown_extra_keys_are_allowed():
    pack = minimal_pack()
    pack["references"] = {"note": "anything"}
    assert validate_pack(pack) == []


def broken_pack():
    pack = minimal_pack()
    pack["palettes"]["p1"]["colors"]["Red"]["hex"] = "#GG0000"                 # 1 bad hex
    pack["acts"]["BUILD"] = {"role": "chorus", "phase": "PH-A", "lut": "luts/test_pack/b.cube",
                             "luma_mean": [0.2, 0.5], "sat_mean": [0.3, 0.6]}  # 2 unknown act role
    pack["acts"]["DROP"] = {"role": "peak", "phase": "PH-MISSING", "lut": "luts/test_pack/d.cube",
                            "luma_mean": [0.2, 0.5], "sat_mean": [0.3, 0.6]}   # 3 act -> missing phase
    pack["colour_script"]["phases"].append(
        {"id": "PH-B", "role": "sleep", "luma_mean": [0.2, 0.5], "sat_mean": [0.3, 0.6],
         "lut": "luts/test_pack/../../evil.cube"})                             # 4 phase role, 6 lut ..
    pack["acts"]["HOOK"]["luma_mean"] = [0.9, 0.2]                             # 5 lo > hi
    del pack["typography"]["subtitle_devanagari"]                              # 7 missing typography key
    pack["palettes"]["p1"]["colors"]["Blue"]["usage_pct"] = "ten"              # 8 usage_pct not number
    pack["palettes"]["p1"]["special_laws"] = [{"color": "Red", "only_roles": ["robe"]}]  # 9 no id
    pack["guardrails"] = "no gore"                                             # 10 not a list
    return pack


EXPECTED_FRAGMENTS = [
    "palettes.p1.colors['Red'].hex",
    "acts.BUILD.role",
    "acts.DROP.phase",
    "colour_script.phases[1].role",
    "acts.HOOK.luma_mean",
    "colour_script.phases[1].lut",
    "typography.subtitle_devanagari",
    "palettes.p1.colors['Blue'].usage_pct",
    "palettes.p1.special_laws[0]",
    "guardrails",
]


def test_broken_pack_lists_each_error_separately():
    errors = validate_pack(broken_pack())
    assert len(errors) == len(EXPECTED_FRAGMENTS) == 10
    assert all(isinstance(e, str) for e in errors)
    for fragment in EXPECTED_FRAGMENTS:
        assert any(fragment in e for e in errors), fragment


@pytest.mark.parametrize("junk", [None, [], "x", 42])
def test_validate_pack_junk_returns_one_error_and_never_raises(junk):
    errors = validate_pack(junk)
    assert isinstance(errors, list) and len(errors) == 1


# ---- load_pack ----
def test_load_pack_missing_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        load_pack("does_not_exist", styles_dir=tmp_path)


def test_load_pack_invalid_json_raises_value_error(tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_pack("broken", styles_dir=tmp_path)


def test_load_pack_reads_valid_file(tmp_path):
    pack = minimal_pack()
    (tmp_path / "test_pack.json").write_text(json.dumps(pack), encoding="utf-8")
    assert load_pack("test_pack", styles_dir=tmp_path) == pack


# ---- the fixed default style (owner 2026-11-07: Deva Neon for every story from now) ----
def test_default_style_pack_is_deva_neon_and_a_story_can_pick_another():
    from core import style_pack as sp
    assert sp.default_pack_id() == "deva_neon"
    assert sp.pack_for_story({}) == "deva_neon"
    assert sp.pack_for_story({"style_pack": "braj_earth"}) == "braj_earth"
    assert sp.pack_for_story({"style_pack": "no_such_pack"}) == "deva_neon"   # an unknown pack never wins
    assert sp.pack_for_story({"style_pack": "../core"}) == "deva_neon"


def test_list_packs_for_the_ui_names_both_packs_and_marks_the_default():
    from core import style_pack as sp
    packs = {p["id"]: p for p in sp.list_packs()}
    assert set(packs) == {"braj_earth", "deva_neon"}
    assert [i for i, p in packs.items() if p["default"]] == ["deva_neon"]
    assert packs["deva_neon"]["has_grade_numbers"] is True and packs["braj_earth"]["has_grade_numbers"] is False
    assert packs["deva_neon"]["acts"] == ["HOOK", "BUILD", "DROP", "OUTRO"]
