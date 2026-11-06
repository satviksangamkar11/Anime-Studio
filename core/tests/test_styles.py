"""WP2 tests: style packs, converters, lint_pack, story.json, OPEN_QUESTIONS.md.

Tests use only committed repo files and tmp_path fixtures. They never read _inputs/.
"""
import importlib.util
import json
from pathlib import Path

from core.style_pack import load_pack, validate_pack

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- converter: braj_earth (kaliya bible) ----
EXPECTED_COLOUR_SCRIPT = {
    "phases": [
        {"id": "PH-DAWN-PLAY", "role": "play", "key": "#E9C98F", "accent": "#E8B531", "temp": "warm",
         "luma_mean": [0.45, 0.65], "sat_mean": [0.25, 0.45], "lut": "luts/ph_dawn_play.cube"},
        {"id": "PH-POISON", "role": "threat", "key": "#1F3A3E", "accent": "#5B3E6B", "temp": "cool",
         "luma_mean": [0.15, 0.35], "sat_mean": [0.10, 0.25], "lut": "luts/ph_poison.cube"},
        {"id": "PH-PURIFIED", "role": "release", "key": "#6FA7B0", "accent": "#F6D27A", "temp": "neutral-warm",
         "luma_mean": [0.45, 0.70], "sat_mean": [0.30, 0.50], "lut": "luts/ph_purified.cube"},
    ],
    "hero_contrast": {"pair": ["pitambara_gold", "violet_fume"],
                      "note": "near-complementary; reserve for hooks and climaxes"},
    "limits": {"shot_drift_de2000": 6, "cut_jump_de2000": 8, "flicker_luma_step": 0.04},
}

A9_LINE = "avoid white-dominant frames on joyful beats (white = mourning in Hindu custom)"


def test_braj_convert_is_byte_identical(tmp_path):
    conv = _load_tool("convert_bible")
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    assert conv.main(["kaliya_mardan", "--out", str(first)]) == 0
    assert conv.main(["kaliya_mardan", "--out", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()
    assert b"\r\n" not in first.read_bytes()


def test_braj_committed_file_matches_converter(tmp_path):
    conv = _load_tool("convert_bible")
    out = tmp_path / "braj.json"
    conv.main(["kaliya_mardan", "--out", str(out)])
    assert out.read_bytes() == (ROOT / "styles" / "braj_earth.json").read_bytes()


def test_committed_packs_validate():
    assert validate_pack(load_pack("braj_earth")) == []
    assert validate_pack(load_pack("deva_neon")) == []


def test_braj_palette_count_and_ids():
    pack = load_pack("braj_earth")
    chars = [p for p in pack["palettes"] if p.startswith("char_")]
    envs = [p for p in pack["palettes"] if p.startswith("env_")]
    assert len(chars) == 11
    assert len(envs) == 6
    assert len(pack["palettes"]) == 17
    assert pack["palettes"]["char_krishna"]["characters"] == ["CHAR-KRISHNA"]
    assert pack["palettes"]["env_kadamba_bank"]["characters"] == []


def test_braj_acts_derived_from_phases():
    pack = load_pack("braj_earth")
    acts = pack["acts"]
    assert set(acts) == {"HOOK", "BUILD", "DROP", "OUTRO"}
    assert (acts["HOOK"]["phase"], acts["HOOK"]["role"]) == ("PH-DAWN-PLAY", "hook")
    assert (acts["BUILD"]["phase"], acts["BUILD"]["role"]) == ("PH-DAWN-PLAY", "build")
    assert (acts["DROP"]["phase"], acts["DROP"]["role"]) == ("PH-POISON", "peak")
    assert (acts["OUTRO"]["phase"], acts["OUTRO"]["role"]) == ("PH-PURIFIED", "outro")
    phases = {p["id"]: p for p in pack["colour_script"]["phases"]}
    for act in acts.values():
        assert act["lut"] == phases[act["phase"]]["lut"]
        assert act["luma_mean"] == phases[act["phase"]]["luma_mean"]
        assert act["sat_mean"] == phases[act["phase"]]["sat_mean"]
    assert all("grade" not in act for act in acts.values())


def test_braj_colour_script_matches_spec():
    pack = load_pack("braj_earth")
    assert pack["colour_script"] == EXPECTED_COLOUR_SCRIPT


def test_braj_guardrails_and_forbidden_words():
    pack = load_pack("braj_earth")
    bible = json.loads((ROOT / "director" / "style" / "kaliya_mardan.json").read_text(encoding="utf-8"))
    for line in bible["iconography"]["restrictions"]:
        assert line in pack["guardrails"]
    assert A9_LINE in pack["guardrails"]
    assert pack["prompt_forbidden_words"] == ["neon", "glow aura", "halo"]


def test_braj_frame_and_impact_rules():
    pack = load_pack("braj_earth")
    assert pack["frame_law"]["max_neon_hues_per_shot"] == 0
    assert pack["frame_law"]["min_dL_focal_vs_bg"] is None
    assert pack["impact"]["allowed_types"] == []
    assert pack["environments"] == []
    assert pack["sound_sync"] == {"enabled": False}
    assert pack["typography"]["lockup"] == {"leader": "devanagari", "latin_size_frac": 0.4,
                                            "latin_opacity": 0.7, "gap_px_1080": 16}


def test_braj_usage_and_accent_fields():
    pack = load_pack("braj_earth")
    for pal in pack["palettes"].values():
        assert pal["accent_max_per_episode"] == 1
        assert pal["time_lock"] is None
        assert pal["special_laws"] == []
        for col in pal["colors"].values():
            assert col["usage_pct"] == 0
            assert col["neon"] is False


# ---- converter: deva_neon (DEVA art bible) ----
def _synthetic_art_bible():
    grades = {
        "HOOK": {"act": "0-3s", "exposure": 0.3, "contrast": 18, "saturation": 12, "temp": "warm+6",
                 "shadow_lift": -4, "highlight": 8, "bloom_pct": 6, "vignette_pct": 15},
        "BUILD": {"act": "3-8s", "exposure": 0.0, "contrast": 6, "saturation": -8, "temp": "cool-4",
                  "shadow_lift": 6, "highlight": 0, "bloom_pct": 0, "vignette_pct": 8},
        "DROP": {"act": "drop-24s", "exposure": 0.5, "contrast": 22, "saturation": 18, "temp": "+2",
                 "shadow_crush": -8, "highlight": 12, "bloom_pct": 12, "vignette_pct": 25},
        "OUTRO": {"act": "last 3s", "exposure": -0.3, "contrast": 8, "saturation": -20, "temp": "+4",
                  "shadow_lift": 4, "highlight": -6, "bloom_pct": 4, "vignette_pct": 30},
    }
    return {
        "art_bible": "deva-neon", "version": "1.0",
        "frame_law": {"environment_pct": 70, "character_pct": 20, "ignition_pct": 10,
                      "pure_white_area_cap_pct": 8, "neon_dominant_per_shot": 1, "min_dL_hero_vs_bg": 55},
        "palettes": {
            "test_palette": {
                "devanagari": "x", "hook_primary": "H-01", "hook_alt": "H-02",
                "colors": {
                    "Glow Test": {"hex": "#27E0FC", "role": "throat glow, energy VFX", "usage": 10},
                    "Plain": {"hex": "#8C93A6", "role": "skin shading, ash", "usage": 20},
                    "Dark": {"hex": "#0B0E1C", "role": "night sky, shadow mass", "usage": 30},
                },
                "impact": {"primary": "white_out"},
                "grades": {},
            }
        },
        "grades": grades,
        "impact": {"types": ["white_out", "black_out", "inverted", "alpha_sil", "chroma_split"]},
        "sound_sync": {"events": ["PULSE", "STROBE-LOCK"]},
    }


def test_deva_convert_synthetic_fixture(tmp_path):
    conv = _load_tool("convert_deva_bible")
    src = tmp_path / "art_bible.json"
    src.write_text(json.dumps(_synthetic_art_bible()), encoding="utf-8")
    out = tmp_path / "deva.json"
    assert conv.main([str(src), "--out", str(out)]) == 0
    pack = json.loads(out.read_text(encoding="utf-8"))
    cols = pack["palettes"]["test_palette"]["colors"]
    assert cols["Glow Test"] == {"hex": "#27E0FC", "role": "throat glow, energy VFX",
                                 "usage_pct": 10, "neon": True}
    assert cols["Plain"]["neon"] is False and cols["Plain"]["hex"] == "#8C93A6"
    assert cols["Dark"]["usage_pct"] == 30 and cols["Dark"]["neon"] is False
    assert pack["acts"]["HOOK"]["grade"]["temp"] == 6
    assert pack["acts"]["BUILD"]["grade"]["temp"] == -4
    assert pack["acts"]["DROP"]["grade"]["temp"] == 2
    assert pack["acts"]["OUTRO"]["grade"]["temp"] == 4
    assert pack["acts"]["DROP"]["grade"]["shadow_crush"] == -8
    assert pack["frame_law"]["min_dL_focal_vs_bg"] == 55
    assert pack["frame_law"]["area_split"] == [70, 20, 10]
    assert validate_pack(pack) == []
    again = tmp_path / "deva2.json"
    conv.main([str(src), "--out", str(again)])
    assert out.read_bytes() == again.read_bytes()


def test_deva_committed_shape():
    pack = load_pack("deva_neon")
    assert len(pack["palettes"]) == 5
    for name, pal in pack["palettes"].items():
        assert len(pal["colors"]) == 8, name
    cols = {n: c for pal in pack["palettes"].values() for n, c in pal["colors"].items()}
    assert cols["Neel Cyan"]["hex"] == "#27E0FC" and cols["Neel Cyan"]["neon"] is True
    assert cols["Trialokya Saffron"]["neon"] is True
    assert cols["Feral Amber"]["hex"] == "#FFA51E"
    assert cols["Rani Pink"]["hex"] == "#E93A7D"
    neon = sorted(n for n, c in cols.items() if c["neon"])
    assert neon == ["Arrow Energy", "Dusk Purple", "Feral Amber", "Neel Cyan",
                    "Rani Pink", "Tongue Red", "Trialokya Saffron"]
    law_ids = {law["id"] for pal in pack["palettes"].values() for law in pal["special_laws"]}
    assert {"SHIVA-EYE", "KARNA-TRAGIC", "DURGA-TRAILS", "NARASIMHA-TIME"} <= law_ids
    assert pack["palettes"]["narasimha_twilight"]["time_lock"]["keywords"] == ["sandhya", "twilight", "dusk"]
    assert pack["frame_law"]["min_dL_focal_vs_bg"] == 55
    assert pack["frame_law"]["area_split"] == [70, 20, 10]


# ---- lint_pack ----
def _gap_entries(entries):
    return [e for e in entries if e.get("rule") == "LINT-DL" and e.get("gap") is not None]


def test_lint_deva_reports_hanuman_karna_durga():
    lint = _load_tool("lint_pack")
    entries = _gap_entries(lint.lint_pack("deva_neon"))
    by_pal = {e["palette"]: e for e in entries}
    assert abs(by_pal["hanuman_vayu"]["gap"] - 13) <= 3
    assert abs(by_pal["karna_surya"]["gap"] - 36) <= 3
    assert abs(by_pal["durga_kali_shakti"]["gap"] - 46) <= 3
    assert all(e["level"] == "WARN" for e in entries)


def test_lint_braj_raises_no_gap():
    lint = _load_tool("lint_pack")
    entries = lint.lint_pack("braj_earth")
    assert _gap_entries(entries) == []
    assert any("no min_dL_focal_vs_bg set" in e["message"] for e in entries)


def test_lint_fixture_fail_and_pass(tmp_path):
    lint = _load_tool("lint_pack")
    base = load_pack("braj_earth")
    base["pack_id"] = "fx"
    base["frame_law"]["min_dL_focal_vs_bg"] = 55

    def colour(hex_, role):
        return {"hex": hex_, "role": role, "usage_pct": 10, "neon": False}

    base["palettes"] = {"fixture": {"characters": [], "time_lock": None, "special_laws": [],
                                    "colors": {"Hero Cloth": colour("#E8451F", "hero mass"),
                                               "Sky Fixture": colour("#2BB3C0", "sky")}}}
    (tmp_path / "fx_bad.json").write_text(json.dumps(base), encoding="utf-8")
    bad = _gap_entries(lint.lint_pack("fx_bad", styles_dir=tmp_path))
    assert len(bad) == 1 and bad[0]["gap"] < 55

    base["palettes"]["fixture"]["colors"]["Hero Cloth"] = colour("#FFFFFF", "hero mass")
    base["palettes"]["fixture"]["colors"]["Sky Fixture"] = colour("#0B0E1C", "night sky")
    (tmp_path / "fx_ok.json").write_text(json.dumps(base), encoding="utf-8")
    assert _gap_entries(lint.lint_pack("fx_ok", styles_dir=tmp_path)) == []


def test_lint_missing_pack_is_fail_not_traceback(tmp_path):
    lint = _load_tool("lint_pack")
    entries = lint.lint_pack("no_such_pack", styles_dir=tmp_path)
    assert entries and entries[0]["level"] == "FAIL"


def test_lint_cli_exit_zero_on_warn():
    lint = _load_tool("lint_pack")
    assert lint.main(["deva_neon"]) == 0


# ---- story and open questions ----
def test_story_json_loads_its_pack():
    story = json.loads((ROOT / "stories" / "kaliya_mardan" / "story.json").read_text(encoding="utf-8"))
    assert story == {"slug": "kaliya_mardan", "style_pack": "braj_earth", "platform": "shorts_9x16",
                     "language": "hi", "episode_target_s": [65, 75]}
    assert load_pack(story["style_pack"])["pack_id"] == "braj_earth"


def test_open_questions_sections():
    text = (ROOT / "OPEN_QUESTIONS.md").read_text(encoding="utf-8")
    for n in range(1, 9):
        assert f"Q{n} " in text
    for heading in ("## Owner questions", "## Auto-tagged neon colours (confirm, Q4)",
                    "## Palettes under the dL* law (Q2)", "## Decisions taken without the owner"):
        assert heading in text
