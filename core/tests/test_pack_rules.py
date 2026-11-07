"""Tests for core/pack_rules.py (P0-P13). Episodes and shots are hand-built dicts (INTERFACES.md contract)."""
import copy
import re
from pathlib import Path

import pytest

from core import pack_rules
from core.pack_rules import RULE_IDS, check_pack_rules
from core.style_pack import load_core, load_pack

FPS = 24
REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = {"type": "H-03", "caption": "Why is his throat blue?"}


# ---------- builders ----------
def make_pack():
    return {
        "pack_id": "test_pack", "version": "1.0", "status": "draft",
        "colour_script": {"phases": [
            {"id": "PH-A", "role": "play", "luma_mean": [0.2, 0.6], "sat_mean": [0.2, 0.6],
             "lut": "luts/test_pack/a.cube"},
            {"id": "PH-B", "role": "threat", "luma_mean": [0.1, 0.5], "sat_mean": [0.2, 0.7],
             "lut": "luts/test_pack/b.cube"},
        ]},
        "acts": {
            "HOOK": {"role": "hook", "phase": "PH-A", "lut": "luts/test_pack/hook.cube",
                     "luma_mean": [0.2, 0.6], "sat_mean": [0.2, 0.6]},
            "BUILD": {"role": "build", "phase": "PH-B", "lut": "luts/test_pack/build.cube",
                      "luma_mean": [0.1, 0.5], "sat_mean": [0.2, 0.7]},
            "PEAK": {"role": "peak", "phase": "PH-B", "lut": "luts/test_pack/peak.cube",
                     "luma_mean": [0.1, 0.5], "sat_mean": [0.2, 0.7]},
            "OUTRO": {"role": "outro", "phase": "PH-A", "lut": "luts/test_pack/outro.cube",
                      "luma_mean": [0.2, 0.6], "sat_mean": [0.2, 0.6]},
        },
        "palettes": {
            "pal_a": {
                "characters": ["CHAR-A", "CHAR-B"],
                "time_lock": {"keywords": ["dusk", "sandhya"], "note": "evening only"},
                "colors": {
                    "Gold": {"hex": "#FFD700", "role": "light", "usage_pct": 10, "neon": False},
                    "Neel Cyan": {"hex": "#00FFFF", "role": "glow", "usage_pct": 5, "neon": True},
                    "Ember": {"hex": "#FF4400", "role": "fire", "usage_pct": 5, "neon": True},
                    "Ivory": {"hex": "#FFFFF0", "role": "robe", "usage_pct": 30, "neon": False},
                },
                "special_laws": [
                    {"id": "SHIVA-EYE", "color": "Neel Cyan", "only_roles": ["third_eye"]},
                    {"id": "DURGA-TRAILS", "role": "weapon_trail", "max_vfx": 3},
                    {"id": "KARNA-TRAGIC", "tag": "tragic", "only_impact_types": ["black_out"]},
                    {"id": "NARASIMHA-TIME", "reveal_impact": {"type": "black_out", "frames": 3}},
                ],
                "accent_max_per_episode": 1,
            },
            "pal_b": {
                "characters": ["CHAR-C"],
                "time_lock": None,
                "colors": {"Saffron": {"hex": "#F4C430", "role": "robe", "usage_pct": 20, "neon": False}},
                "special_laws": [],
            },
        },
        "frame_law": {"min_dL_focal_vs_bg": None, "max_neon_hues_per_shot": 1,
                      "pure_white_area_cap_frac": 0.1},
        "impact": {"allowed_types": ["white_out", "black_out"],
                   "type_max_frames": {"white_out": 4, "black_out": 3}},
        "typography": {"display": None, "sacred": None, "subtitle_latin": "Inter",
                       "subtitle_devanagari": "Noto Sans Devanagari", "min_px_at_1080w": 22,
                       "font_dir": "styles/fonts"},
        "prompt_forbidden_words": ["halo", "dark lord"],
        "guardrails": [],
        "sound_sync": {"enabled": False},
    }


def make_story(**over):
    story = {"slug": "test_story", "style_pack": "test_pack", "platform": "shorts_9x16",
             "language": "hi", "episode_target_s": [65, 75]}
    story.update(over)
    return story


def look(palette="pal_a", act="BUILD", phase="PH-B", hook=None, vfx=(), accent=False,
         tags=(), focal="CHAR-A"):
    return {"palette_id": palette, "act": act, "phase": phase, "focal": focal,
            "focal_value": "lightest", "hook": hook, "impact_frames": [],
            "vfx": [dict(v) for v in vfx], "accent_use": accent, "hold_purpose": None,
            "tags": list(tags)}


def imp(at_frame, typ="white_out", frames=2):
    return {"at_frame": at_frame, "at_s": at_frame / FPS, "type": typ, "frames": frames}


def beat(start_s, end_s, reveal=False):
    return {"start_s": start_s, "end_s": end_s, "hold": False, "primary": False, "bhava": None,
            "acting": "", "reveal": reveal, "virtual": False}


def sh(sid, start, frames, lk=None, cast=(), beats=(), impacts=(), prompt="a quiet scene",
       light="dusk over hills"):
    return {"id": sid, "shape": "v22", "index": 0, "start_frame": start, "frames": frames,
            "look": lk, "cast_ids": list(cast), "beats": list(beats), "impacts": list(impacts),
            "text": {"prompt": prompt, "light_world": light}, "first_dialogue": None,
            "dialogue_starts": [], "camera_moves": [], "caption_changes": [],
            "purpose": "", "sound_text": "", "problems": [], "raw": {}}


def base_episodes():
    s1 = sh("S1", 0, 48, look(act="HOOK", phase="PH-A", hook=HOOK,
                              vfx=[{"color": "Gold", "role": "light"}]),
            cast=["CHAR-A"], prompt="A warrior stands on a cliff", light="dusk over mountains")
    s2 = sh("S2", 48, 72, look(act="BUILD", phase="PH-B",
                               vfx=[{"color": "Neel Cyan", "role": "third_eye"}]),
            cast=["CHAR-A", "CHAR-B"], prompt="Shiva walks slowly", light="soft dusk light")
    s3 = sh("S3", 120, 48, look(act="OUTRO", phase="PH-A"), cast=["CHAR-B"],
            prompt="Final frame", light="gentle dusk sky")
    return [{"key": 1, "fps": FPS, "shots": [s1, s2, s3], "total_frames": 168}]


def one_shot_episode(shot_list, key=1):
    return {"key": key, "fps": FPS, "shots": shot_list,
            "total_frames": sum(s["frames"] for s in shot_list)}


@pytest.fixture
def fonts(tmp_path):
    d = tmp_path / "fonts"
    d.mkdir()
    (d / "Inter-Regular.ttf").write_bytes(b"x")
    (d / "NotoSansDevanagari-Regular.ttf").write_bytes(b"x")
    return d


def run(fonts, episodes=None, pack="default", core=None, story="default", story_path_exists=True):
    eps = base_episodes() if episodes is None else episodes
    pk = make_pack() if pack == "default" else pack
    st = make_story() if story == "default" else story
    return check_pack_rules(eps, pk, load_core() if core is None else core, story=st,
                            story_path_exists=story_path_exists, font_dir_override=fonts)


def of(entries, rule, level=None):
    return [e for e in entries if e["rule"] == rule and (level is None or e["level"] == level)]


def assert_entry_shape(entries):
    for e in entries:
        assert set(e) == {"rule", "level", "shot", "episode", "message"}
        assert e["level"] in ("FAIL", "WARN")
        assert isinstance(e["message"], str)


# ---------- base case and P0 ----------
def test_base_case_produces_no_entries(fonts):
    assert run(fonts) == []


def test_p0_fail_junk_top_level_shapes(fonts):
    out = run(fonts, episodes="x")
    assert of(out, "P0", "FAIL")
    assert_entry_shape(out)
    out = run(fonts, pack="junk")
    assert of(out, "P0", "FAIL")
    out = run(fonts, core="junk")
    assert of(out, "P0", "FAIL")
    assert of(out, "P6") == []


def test_p0_fail_bad_frames(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["frames"] = "5"
    eps[0]["shots"][2]["frames"] = None
    out = run(fonts, episodes=eps)
    p0 = of(out, "P0", "FAIL")
    assert len(p0) == 2
    assert all("frames" in e["message"] for e in p0)


def test_p0_fail_bad_secs(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["impacts"] = [{"at_frame": 60, "at_s": "x", "type": "white_out", "frames": 2}]
    out = run(fonts, episodes=eps)
    p0 = of(out, "P0", "FAIL")
    assert p0 and "at_s" in p0[0]["message"]


def test_p0_fail_strings_and_nulls(fonts):
    eps = [{"key": 1, "shots": [{"id": 5, "start_frame": "0", "frames": None}]}, "x"]
    out = run(fonts, episodes=eps)
    assert len(of(out, "P0", "FAIL")) >= 3
    assert_entry_shape(out)
    bad_shots = [{"key": 2, "shots": "x"}]
    assert of(run(fonts, episodes=bad_shots), "P0", "FAIL")


def test_p0_pass_valid_shapes_have_no_p0(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["impacts"] = [imp(60, "white_out", 2)]
    eps[0]["shots"][1]["beats"] = [beat(2.5, 3.5)]
    assert of(run(fonts, episodes=eps), "P0") == []


# ---------- P1 ----------
def test_p1_fail_invalid_pack_names_error(fonts):
    pk = make_pack()
    pk["status"] = "bogus"
    out = run(fonts, pack=pk)
    p1 = of(out, "P1", "FAIL")
    assert p1 and "status" in p1[0]["message"]


def test_p1_fail_style_pack_mismatch(fonts):
    out = run(fonts, story=make_story(style_pack="other_pack"))
    p1 = of(out, "P1", "FAIL")
    assert p1 and "other_pack" in p1[0]["message"]


def test_p1_fail_pack_missing_when_story_exists(fonts):
    out = run(fonts, pack=None)
    assert of(out, "P1", "FAIL")


def test_p1_fail_lists_at_most_five_errors_then_count(fonts):
    junk = {"pack_id": "", "status": "x", "colour_script": "x", "acts": "x", "palettes": "x",
            "frame_law": "x", "impact": "x", "typography": "x",
            "prompt_forbidden_words": "x", "guardrails": "x"}
    p1 = of(run(fonts, pack=junk), "P1", "FAIL")
    assert p1 and "+" in p1[0]["message"] and "more" in p1[0]["message"]


def test_p1_warn_story_json_missing(fonts):
    out = run(fonts, story=None, story_path_exists=False)
    p1 = of(out, "P1")
    assert len(p1) == 1 and p1[0]["level"] == "WARN"
    assert "stories/<slug>/story.json not found" in p1[0]["message"]


def test_p1_pass_valid_pack_and_matching_story(fonts):
    assert of(run(fonts), "P1") == []
    assert of(run(fonts, story=None, story_path_exists=None), "P1") == []


# ---------- P2 ----------
def test_p2_fail_missing_look_when_story_exists(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"] = None
    p2 = of(run(fonts, episodes=eps), "P2", "FAIL")
    assert p2 and p2[0]["shot"] == "S2"


def test_p2_fail_unknown_palette(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["palette_id"] = "pal_zz"
    p2 = of(run(fonts, episodes=eps), "P2", "FAIL")
    assert p2 and "pal_zz" in p2[0]["message"]


def test_p2_pass_palette_known_and_legacy_without_story(fonts):
    assert of(run(fonts), "P2") == []
    eps = base_episodes()
    for s in eps[0]["shots"]:
        s["look"] = None
    assert of(run(fonts, episodes=eps, story=None, story_path_exists=None), "P2") == []


# ---------- P3 ----------
def test_p3_fail_unknown_act(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["act"] = "NOPE"
    p3 = of(run(fonts, episodes=eps), "P3", "FAIL")
    assert p3 and p3[0]["shot"] == "S2"


def test_p3_pass_known_acts(fonts):
    assert of(run(fonts), "P3") == []


# ---------- P4 ----------
def test_p4_warn_cast_not_in_any_palette(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["cast_ids"] = ["CHAR-ZZZ"]
    p4 = of(run(fonts, episodes=eps), "P4", "WARN")
    assert p4 and "CHAR-ZZZ" in p4[0]["message"]


def test_p4_pass_cast_listed_in_some_palette(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["cast_ids"] = ["CHAR-C"]
    assert of(run(fonts, episodes=eps), "P4") == []


# ---------- P5 ----------
def test_p5_fail_tokens_regression_names_both_causes(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["vfx"] = [{"color": "Neel Cyan", "role": "glow"},
                                         {"color": "Ember", "role": "fire"}]
    p5 = of(run(fonts, episodes=eps), "P5", "FAIL")
    assert len(p5) == 2
    assert any("Neel Cyan" in e["message"] for e in p5)
    assert any("neon" in e["message"] for e in p5)


def test_p5_fail_colour_not_in_palette(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["vfx"] = [{"color": "Purple", "role": "glow"}]
    p5 = of(run(fonts, episodes=eps), "P5", "FAIL")
    assert p5 and "Purple" in p5[0]["message"]


def test_p5_fail_trail_law_over_max(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["vfx"] = [{"color": "Gold", "role": "weapon_trail"}] * 4
    p5 = of(run(fonts, episodes=eps), "P5", "FAIL")
    assert p5 and "weapon_trail" in p5[0]["message"]


def test_p5_pass_allowed_colour_law_role_case_insensitive(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["vfx"] = [{"color": "Neel Cyan", "role": "Third_Eye"}]
    assert of(run(fonts, episodes=eps), "P5") == []
    assert of(run(fonts), "P5") == []


# ---------- P6 ----------
def ep_with_impacts(impacts, tags=(), beats=()):
    """Episode of one hook shot followed by a shot holding the impacts (absolute frames)."""
    eps = base_episodes()
    s2 = eps[0]["shots"][1]
    s2["look"]["tags"] = list(tags)
    s2["impacts"] = list(impacts)
    s2["beats"] = list(beats)
    return eps


def test_p6_fail_type_not_allowed(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(60, "chroma_split", 2)]))
    p6 = of(out, "P6", "FAIL")
    assert p6 and "chroma_split" in p6[0]["message"]


def test_p6_fail_frames_over_type_max(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(60, "black_out", 4)]))
    p6 = of(out, "P6", "FAIL")
    assert p6 and "black_out" in p6[0]["message"]


def test_p6_fail_strobe_window_and_gap(fonts):
    """Spec regression: 4 impacts of 2 frames within 1 s in a 31 s episode."""
    hook_shot = sh("S1", 0, 744, look(act="HOOK", phase="PH-A", hook=HOOK),
                   impacts=[imp(100), imp(102), imp(104), imp(106)])
    out = run(fonts, episodes=[one_shot_episode([hook_shot])])
    p6 = of(out, "P6", "FAIL")
    msgs = " | ".join(e["message"] for e in p6)
    assert "window" in msgs
    assert "gap" in msgs


def test_p6_fail_window_sum_over_four_with_legal_gaps(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(60), imp(74), imp(88), imp(102)]))
    p6 = of(out, "P6", "FAIL")
    msgs = " | ".join(e["message"] for e in p6)
    assert "window" in msgs
    assert "gap" not in msgs


def test_p6_fail_gap_under_twelve_frames(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(60), imp(62)]))
    p6 = of(out, "P6", "FAIL")
    msgs = " | ".join(e["message"] for e in p6)
    assert "gap" in msgs
    assert "window" not in msgs


def test_p6_pass_spaced_impacts(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(60), imp(80)]))
    assert of(out, "P6") == []


def test_p6_fail_tag_law_disallowed_type(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(60, "white_out", 2)], tags=["tragic"]))
    p6 = of(out, "P6", "FAIL")
    assert p6 and "tragic" in p6[0]["message"]


def test_p6_pass_tag_law_allowed_type(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(60, "black_out", 3)], tags=["tragic"]))
    assert of(out, "P6") == []


def test_p6_fail_time_law_reveal_beat_wrong_impact(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(66, "white_out", 2)],
                                              beats=[beat(2.5, 3.5, reveal=True)]))
    p6 = of(out, "P6", "FAIL")
    assert p6 and "reveal" in p6[0]["message"]


def test_p6_pass_time_law_reveal_beat_exact_impact(fonts):
    out = run(fonts, episodes=ep_with_impacts([imp(66, "black_out", 3)],
                                              beats=[beat(2.5, 3.5, reveal=True)]))
    assert of(out, "P6") == []


def test_multi_ep_two_correct_episodes_no_p6_or_p7(fonts):
    eps = base_episodes() + base_episodes()
    eps[1]["key"] = 2
    for ep in eps:
        ep["shots"][1]["impacts"] = [imp(60), imp(80)]
    out = run(fonts, episodes=eps)
    assert of(out, "P6") == []
    assert of(out, "P7") == []


# ---------- P7 ----------
def test_p7_fail_hook_on_second_shot(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["hook"] = HOOK
    p7 = of(run(fonts, episodes=eps), "P7", "FAIL")
    assert any(e["shot"] == "S2" for e in p7)


def test_p7_fail_missing_hook_on_first_shot(fonts):
    eps = base_episodes()
    eps[0]["shots"][0]["look"]["hook"] = None
    assert of(run(fonts, episodes=eps), "P7", "FAIL")


def test_p7_fail_hook_type_not_h01_to_h06(fonts):
    eps = base_episodes()
    eps[0]["shots"][0]["look"]["hook"] = {"type": "H-09", "caption": "x"}
    p7 = of(run(fonts, episodes=eps), "P7", "FAIL")
    assert p7 and "H-09" in p7[0]["message"]


def test_p7_pass_hook_only_on_first_shot(fonts):
    assert of(run(fonts), "P7") == []


# ---------- P8 ----------
def test_p8_warn_last_shot_not_outro(fonts):
    eps = base_episodes()
    eps[0]["shots"][2]["look"]["act"] = "BUILD"
    assert of(run(fonts, episodes=eps), "P8", "WARN")


def test_p8_warn_last_palette_differs_from_first(fonts):
    eps = base_episodes()
    eps[0]["shots"][2]["look"]["palette_id"] = "pal_b"
    assert of(run(fonts, episodes=eps), "P8", "WARN")


def test_p8_pass_outro_with_same_palette(fonts):
    assert of(run(fonts), "P8") == []


# ---------- P9 ----------
def test_p9_fail_forbidden_word_case_insensitive(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["text"]["prompt"] = "A Halo of golden light"
    p9 = of(run(fonts, episodes=eps), "P9", "FAIL")
    assert p9 and "halo" in p9[0]["message"].lower()


def test_p9_fail_forbidden_phrase(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["text"]["prompt"] = "The Dark Lord rises"
    assert of(run(fonts, episodes=eps), "P9", "FAIL")


def test_p9_pass_word_boundaries(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["text"]["prompt"] = "a shalow pond at dawn"
    assert of(run(fonts, episodes=eps), "P9") == []


# ---------- P10 ----------
def test_p10_fail_missing_font_file_names_family(tmp_path):
    d = tmp_path / "fonts"
    d.mkdir()
    (d / "Inter-Regular.ttf").write_bytes(b"x")
    out = check_pack_rules(base_episodes(), make_pack(), load_core(), story=make_story(),
                           story_path_exists=True, font_dir_override=d)
    p10 = of(out, "P10", "FAIL")
    assert p10 and "Noto Sans Devanagari" in p10[0]["message"]
    assert p10[0]["shot"] is None and p10[0]["episode"] is None


def test_p10_fail_missing_font_dir_once(tmp_path):
    out = check_pack_rules(base_episodes(), make_pack(), load_core(), story=make_story(),
                           story_path_exists=True, font_dir_override=tmp_path / "nope")
    p10 = of(out, "P10", "FAIL")
    assert len(p10) == 1 and "nope" in p10[0]["message"]


def test_p10_fail_devanagari_unset_for_hindi(fonts):
    pk = make_pack()
    pk["typography"]["subtitle_devanagari"] = None
    p10 = of(run(fonts, pack=pk), "P10", "FAIL")
    assert len(p10) == 1 and "devanagari" in p10[0]["message"].lower()


def test_p10_pass_normalised_file_names(tmp_path):
    d = tmp_path / "fonts"
    d.mkdir()
    (d / "inter-regular.otf").write_bytes(b"x")
    (d / "NOTO_SANS-DEVANAGARI-regular.TTF").write_bytes(b"x")
    out = check_pack_rules(base_episodes(), make_pack(), load_core(), story=make_story(),
                           story_path_exists=True, font_dir_override=d)
    assert of(out, "P10") == []


# ---------- P11 ----------
def test_p11_warn_light_world_lacks_time_lock_keyword(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["text"]["light_world"] = "noon sun"
    assert of(run(fonts, episodes=eps), "P11", "WARN")


def test_p11_pass_time_lock_keyword_present(fonts):
    assert of(run(fonts), "P11") == []


# ---------- P12 ----------
def test_p12_fail_accent_over_palette_limit(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["accent_use"] = True
    eps[0]["shots"][2]["look"]["accent_use"] = True
    p12 = of(run(fonts, episodes=eps), "P12", "FAIL")
    assert len(p12) == 1 and "pal_a" in p12[0]["message"]


def test_p12_pass_accent_at_limit_and_no_limit_without_key(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["accent_use"] = True
    assert of(run(fonts, episodes=eps), "P12") == []
    eps = base_episodes()
    for i in (1, 2):
        eps[0]["shots"][i]["look"]["palette_id"] = "pal_b"
        eps[0]["shots"][i]["look"]["accent_use"] = True
    assert of(run(fonts, episodes=eps), "P12") == []


# ---------- P13 ----------
def test_p13_fail_phase_not_in_colour_script(fonts):
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["phase"] = "PH-ZZ"
    p13 = of(run(fonts, episodes=eps), "P13", "FAIL")
    assert p13 and "PH-ZZ" in p13[0]["message"]


def test_p13_fail_phase_missing(fonts):
    eps = base_episodes()
    del eps[0]["shots"][1]["look"]["phase"]
    p13 = of(run(fonts, episodes=eps), "P13", "FAIL")
    assert p13 and "look.phase missing" in p13[0]["message"]


def test_p13_pass_phase_ids_and_no_colour_script(fonts):
    assert of(run(fonts), "P13") == []
    pk = make_pack()
    del pk["colour_script"]
    eps = base_episodes()
    eps[0]["shots"][1]["look"]["phase"] = "anything"
    assert of(run(fonts, episodes=eps, pack=pk), "P13") == []


# ---------- meta, isolation and robustness ----------
def test_every_rule_has_a_fail_or_warn_test_and_a_pass_test():
    assert RULE_IDS == tuple(f"P{i}" for i in range(14))
    names = [n for n in globals() if n.startswith("test_")]
    for rid in RULE_IDS:
        n = rid[1:]
        assert any(re.match(rf"test_p{n}_(fail|warn)", t) for t in names), rid
        assert any(re.match(rf"test_p{n}_pass", t) for t in names), rid


def test_module_source_has_no_timeline_import_or_hard_coded_paths():
    src = Path(pack_rules.__file__).read_text(encoding="utf-8")
    assert "core.timeline" not in src
    assert "import timeline" not in src
    assert "D:\\" not in src and "D:/" not in src


def test_never_raises_on_junk_inputs(fonts):
    junk_eps = [None, 5, [], {"shots": None}, {"key": 1, "shots": [None, 3, {"id": None}]}]
    for eps in junk_eps:
        out = run(fonts, episodes=eps)
        assert isinstance(out, list)
        assert_entry_shape(out)


def test_real_braj_earth_pack_does_not_raise():
    if not (REPO_ROOT / "styles" / "braj_earth.json").is_file():
        pytest.skip("styles/braj_earth.json not written yet")
    pack = load_pack("braj_earth")
    out = check_pack_rules([], pack, load_core(), story=None)
    assert isinstance(out, list)
