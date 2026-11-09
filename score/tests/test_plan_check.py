"""Tests for score/plan_check.py (checklist section A). The real reel is Kalika Puran bhag 1 (70.0 s, 10 shots).

Every rule has a failing variant and a passing variant. A failing variant must produce EXACTLY its own code(s).
"""
import copy
import json
import math
import random
from pathlib import Path

import pytest

from score import plan_check as pc

ROOT = Path(__file__).resolve().parents[2]
STORY = ROOT / "stories" / "kalika_puran_bhag1"
CUE_PATH = ROOT / "score" / "tests" / "fixtures" / "cue_sheet_reel1_v3.json"  # frozen v3 (70.0 s) test data
BIBLE_PATH = STORY / "music_bible.json"

# Hand-built GOOD plan for the real reel, faithful to the style study table "Reel 1 mapped to this style"
# (bible: HOOK 60 ambient, BUILD 128 hypnotic_techno, DROP 176 drum_and_bass, OUTRO 60 unplugged; shot_genres).
# The impact hit at 43.083 is NOT under voice (bright); the one at 60.0 is inside the voice union (band "low", D5).
GOOD = {
    "schema_version": 1,
    "episode": 1,
    "style": "electronic",
    "home_key": "D minor",
    "sections": [
        {"start_s": 0.0, "end_s": 6.0, "act": "HOOK", "bpm": 60, "feel": "normal", "genre": "ambient",
         "harmony": "D minor, held chord", "density_per_beat": [1, 2], "roles_on": ["drone", "pad", "bass"],
         "intensity": [0.2, 0.4], "why": "Sonic logo, then Kali's signature held low under the narration."},
        {"start_s": 6.0, "end_s": 11.0, "act": "HOOK", "bpm": 60, "feel": "normal", "genre": "ambient",
         "harmony": "D minor, held chord with a soft kick", "density_per_beat": [1, 2],
         "roles_on": ["drone", "pad", "bass", "drums"], "voice_gated": True, "intensity": [0.3, 0.4],
         "why": "Shot 2: half-time heartbeat kick under the narration, riser ends on the 11 s cut."},
        {"start_s": 11.0, "end_s": 18.0, "act": "BUILD", "bpm": 128, "feel": "normal", "genre": "hypnotic_techno",
         "harmony": "D minor one-bar loop, filter opening slowly", "density_per_beat": [2, 4],
         "roles_on": ["drone", "bass", "drums", "ostinato"], "voice_gated": True, "intensity": [0.4, 0.5],
         "why": "Shot 3: hypnotic techno, kick filtered low under dialogue."},
        {"start_s": 18.0, "end_s": 26.0, "act": "BUILD", "bpm": 128, "feel": "normal", "genre": "melodic_techno",
         "harmony": "D minor, pad opens on Sandhya's birth", "density_per_beat": [2, 4],
         "roles_on": ["drone", "pad", "bass", "drums", "lead"], "voice_gated": True, "intensity": [0.5, 0.6],
         "why": "Shot 4: melodic techno, the pad opens on her birth."},
        {"start_s": 26.0, "end_s": 34.0, "act": "BUILD", "bpm": 128, "feel": "normal", "genre": "club_folk_groove",
         "harmony": "D Dorian golden pluck hook", "density_per_beat": [2, 4],
         "roles_on": ["bass", "drums", "folk_perc", "pluck"], "voice_gated": True, "intensity": [0.6, 0.7],
         "why": "Shot 5: club and folk groove, building to the 34 s act change."},
        {"start_s": 34.0, "end_s": 48.0, "act": "DROP", "bpm": 176, "feel": "normal", "genre": "drum_and_bass",
         "harmony": "D Phrygian, rolling reese", "density_per_beat": [2, 4],
         "roles_on": ["drone", "bass", "drums", "lead"], "voice_gated": True,
         "intensity": [0.7, 0.9], "why": "Re-hook at 34 s, then chaos until the Shiva reveal."},
        {"start_s": 48.0, "end_s": 64.0, "act": "DROP", "bpm": 176, "feel": "half", "genre": "half_time_dnb",
         "harmony": "D Phrygian, Shiva theme on brass", "density_per_beat": [1, 2],
         "roles_on": ["bass", "brass", "pad", "horn", "drums"], "voice_gated": True,
         "intensity": [0.6, 0.8], "why": "Shots 8-9: heavy half-time, Shiva's entry after a drop-out, then thinning."},
        {"start_s": 64.0, "end_s": 70.0, "act": "OUTRO", "bpm": 60, "feel": "normal", "genre": "unplugged",
         "harmony": "MAIN on piano, unresolved", "density_per_beat": [1, 1],
         "roles_on": ["piano", "pad", "drone", "drums"], "voice_gated": True, "intensity": [0.2, 0.3],
         "why": "Shot 10: the one quiet melodic moment, then the end sting."},
    ],
    "events": [
        {"at_s": 0.0, "type": "sonic_logo"},
        {"at_s": 3.5, "type": "theme_entry", "theme": "KALI", "role": "pad", "feel": "normal"},
        {"at_s": 25.36, "type": "theme_entry", "theme": "SANDHYA", "role": "lead", "feel": "quad"},
        {"at_s": 29.69, "type": "theme_entry", "theme": "KAMADEVA", "role": "pluck", "feel": "quad"},
        {"at_s": 34.0, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits", "band": "bright"},
        {"at_s": 40.25, "type": "theme_entry", "theme": "MAIN", "role": "lead", "feel": "double"},
        {"at_s": 43.2, "type": "theme_entry", "theme": "KAMADEVA", "role": "lead", "feel": "quad",
         "transform": "chaos_41s"},
        {"at_s": 43.083, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits", "band": "bright"},
        {"at_s": 48.0, "type": "theme_entry", "theme": "SHIVA", "role": "brass", "feel": "half",
         "preceded_by_dropout_s": 0.4},
        {"at_s": 60.0, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits", "band": "low"},
        {"at_s": 56.0, "type": "theme_entry", "theme": "KAMADEVA", "role": "pad", "feel": "half",
         "transform": "curse_56_64s"},
        {"at_s": 64.0, "type": "theme_entry", "theme": "MAIN", "role": "piano", "feel": "normal"},
        {"at_s": 69.85, "type": "end_sting", "tail_s": 0.15},
    ],
    "cuts": [
        {"at_s": 6.0, "transition": "theme_handover"},
        {"at_s": 11.0, "transition": "reverse_swell_to_cut"},
        {"at_s": 18.0, "transition": "swell_to_cut"},
        {"at_s": 26.0, "transition": "bed_continues"},
        {"at_s": 34.0, "transition": "act_change"},
        {"at_s": 41.0, "transition": "theme_handover"},
        {"at_s": 48.0, "transition": "bed_continues"},
        {"at_s": 56.0, "transition": "theme_handover"},
        {"at_s": 64.0, "transition": "act_change"},
    ],
    "automation": [{"role": "pad", "macro": 1, "points": [[18.0, 0.2], [20.0, 0.8]]}],
    "rehook_at_s": 40.25,
    "peak_at_s": 48.0,
}


# ---------------------------------------------------------------- fixtures and helpers

@pytest.fixture(scope="module")
def cue():
    if not CUE_PATH.exists():
        pytest.skip(f"real cue sheet missing: {CUE_PATH}")
    with open(CUE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def bible():
    if not BIBLE_PATH.exists():
        pytest.skip(f"music bible missing: {BIBLE_PATH}")
    with open(BIBLE_PATH, encoding="utf-8") as f:
        return json.load(f)


def good_plan():
    return copy.deepcopy(GOOD)


def run(cue, bible, mutate):
    plan = good_plan()
    mutate(plan)
    return pc.check_plan(plan, cue, bible)


def codes(report):
    return {e["code"] for e in report["errors"]}


def warn_codes(report):
    return {w["code"] for w in report["warnings"]}


def event_of(plan, at_s, type_=None):
    for e in plan["events"]:
        if abs(e["at_s"] - at_s) < 1e-9 and (type_ is None or e["type"] == type_):
            return e
    raise KeyError(at_s)


# ---------------------------------------------------------------- the GOOD plan and the report shape

def test_good_plan_is_ok(cue, bible):
    r = pc.check_plan(good_plan(), cue, bible)
    assert r["ok"] is True, r["errors"]
    assert r["errors"] == []
    assert set(r) == {"ok", "errors", "warnings", "stats"}
    assert r["stats"]["sections"] == 8 and r["stats"]["cue_cuts"] == 9


def test_good_plan_has_no_warnings(cue, bible):
    assert pc.check_plan(good_plan(), cue, bible)["warnings"] == []


def test_missing_why_is_only_a_warning(cue, bible):
    def m(p):
        del p["sections"][0]["why"]
    r = run(cue, bible, m)
    assert r["ok"] is True
    assert [w["code"] for w in r["warnings"]] == ["SECTION_WHY_MISSING"]


# ---------------------------------------------------------------- A1 PLAN_COVERAGE

def test_a1_coverage_passes_on_good_plan(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a1_gap_fails(cue, bible):
    def m(p):
        p["sections"][2]["start_s"] = 11.5
    assert codes(run(cue, bible, m)) == {"PLAN_COVERAGE"}


def test_a1_overlap_fails(cue, bible):
    def m(p):
        p["sections"][3]["start_s"] = 17.5  # overlap inside BUILD (no act boundary crossed)
    assert codes(run(cue, bible, m)) == {"PLAN_COVERAGE"}


def test_a1_start_not_zero_fails(cue, bible):
    def m(p):
        p["sections"][0]["start_s"] = 0.5
    assert codes(run(cue, bible, m)) == {"PLAN_COVERAGE"}


def test_a1_last_end_not_total_fails(cue, bible):
    def m(p):
        p["sections"][7]["end_s"] = 69.0
    assert codes(run(cue, bible, m)) == {"PLAN_COVERAGE"}


# ---------------------------------------------------------------- A2 TEMPO_NOT_CANDIDATE, ACT_UNKNOWN

def test_a2_candidate_tempo_passes(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a2_non_candidate_tempo_fails(cue, bible):
    def m(p):
        for k in (2, 3, 4):  # the BUILD sections: 130 is no candidate for hypnotic, melodic or club genres
            p["sections"][k]["bpm"] = 130
    assert codes(run(cue, bible, m)) == {"TEMPO_NOT_CANDIDATE"}


def test_a2_unknown_act_fails(cue, bible):
    def m(p):
        p["sections"][0]["act"] = "BRIDGE"
    assert codes(run(cue, bible, m)) == {"ACT_UNKNOWN"}


# ---------------------------------------------------------------- F5: bpm tied to genre, bible tempo_map and genre

def test_f5_drop_bpm_124_melodic_fails_bible(cue, bible):
    def m(p):
        for k in (5, 6):  # the DROP sections, 34-64: bpm 124 is a cue candidate but not the bible tempo 176
            p["sections"][k]["bpm"] = 124
        p["sections"][5]["genre"] = "melodic_techno"  # no shot_genres entry covers 34-48
    assert codes(run(cue, bible, m)) == {"TEMPO_NOT_IN_BIBLE", "GENRE_NOT_IN_BIBLE"}


def test_f5_hook_125_melodic_fails_bible(cue, bible):
    def m(p):
        for k in (0, 1):  # the whole HOOK (0-11) at 125 melodic, so no BPM change off the act
            p["sections"][k]["bpm"] = 125
            p["sections"][k]["genre"] = "melodic_techno"
    # 125 is a fast bpm, so KALI's entry at 3.5 s (in this section) now needs the drop-out and half feel (rule 8)
    assert codes(run(cue, bible, m)) == {"TEMPO_NOT_IN_BIBLE", "GENRE_NOT_IN_BIBLE", "DROPOUT_MISSING", "GOD_FEEL"}


def test_f5_genre_unknown_fails(cue, bible):
    def m(p):
        p["sections"][2]["genre"] = "polka"
    assert codes(run(cue, bible, m)) == {"GENRE_UNKNOWN"}


def test_f5_bpm_not_in_genre_list_fails(cue, bible):
    def m(p):
        p["sections"][2]["bpm"] = 176  # a DROP tempo in the BUILD act, genre hypnotic_techno
    r = run(cue, bible, m)
    assert "TEMPO_NOT_CANDIDATE" in codes(r)


def test_f5_bible_without_tempo_map_skips_bible_checks(cue, bible):
    no_map = copy.deepcopy(bible)
    del no_map["tempo_map"]
    def m(p):
        # without tempo_map nothing authorises club_folk_groove, half_time_dnb or unplugged: use genres the cue sheet lists
        p["sections"][4]["genre"] = "melodic_techno"
        p["sections"][7]["genre"] = "ambient"
        for k in (5, 6):
            p["sections"][k]["bpm"] = 124
            p["sections"][k]["genre"] = "melodic_techno"
    assert codes(run(cue, no_map, m)) == set()


# ---------------------------------------------------------------- F6: home key and episode

def test_f6_home_key_matches_bible_passes(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_f6_home_key_mismatch_fails(cue, bible):
    def m(p):
        p["home_key"] = "C major"
    assert codes(run(cue, bible, m)) == {"HOME_KEY_MISMATCH"}


def test_f6_episode_as_string_passes(cue, bible):
    def m(p):
        p["episode"] = "1"
    assert codes(run(cue, bible, m)) == set()


def test_f6_episode_mismatch_fails(cue, bible):
    def m(p):
        p["episode"] = 2
    assert codes(run(cue, bible, m)) == {"EPISODE_MISMATCH"}


# ---------------------------------------------------------------- A3 TEMPO_CHANGE_OFF_ACT

def test_a3_change_at_act_change_passes(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a3_same_tempo_split_at_plain_cut_passes(cue, bible):
    def m(p):
        first = p["sections"][3]  # 18-26 melodic, BUILD
        second = dict(first, start_s=22.0, why="Same tempo, same genre: no change at this cut.")
        first["end_s"] = 22.0
        p["sections"].insert(4, second)
    assert codes(run(cue, bible, m)) == set()


def test_a3_genre_change_same_bpm_plain_cut_passes(cue, bible):
    # inside BUILD the genre changes at 18.0 (a hard cut) and 26.0 (a plain cut) with the BPM held at 128 (rule 45)
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a3_genre_change_with_bpm_change_off_act_fails(cue, bible):
    def m(p):
        p["sections"][4]["bpm"] = 124  # 26.0 is a plain cut: the BPM may not change there
    assert codes(run(cue, bible, m)) == {"TEMPO_CHANGE_OFF_ACT"}


def test_f5_genre_not_act_or_shot_genre_fails(cue, bible):
    def m(p):
        p["sections"][4]["genre"] = "half_time_dnb"  # 26-34 overlaps SHOT-005 only, which is club_folk_groove
    assert codes(run(cue, bible, m)) == {"GENRE_NOT_IN_BIBLE"}


def test_a3_bpm_change_off_act_fails(cue, bible):
    def m(p):  # a BPM change at 22.0, inside BUILD: no act_change cut there
        p["sections"][3]["end_s"] = 22.0
        p["sections"][4]["start_s"] = 22.0
        p["sections"][4]["bpm"] = 124
    assert codes(run(cue, bible, m)) == {"TEMPO_CHANGE_OFF_ACT"}


# ---------------------------------------------------------------- A4 CUT_MISSING, CUT_OFF_FRAME, CUT_EXTRA, transitions

def test_a4_all_cuts_present_on_frame_passes(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a4_cut_within_one_frame_passes(cue, bible):
    def m(p):
        p["cuts"][3]["at_s"] = 26.0 + 1 / 24
    assert codes(run(cue, bible, m)) == set()


def test_a4_missing_cut_fails(cue, bible):
    def m(p):
        del p["cuts"][3]
    assert codes(run(cue, bible, m)) == {"CUT_MISSING"}


def test_a4_cut_two_frames_off_fails(cue, bible):
    def m(p):
        p["cuts"][3]["at_s"] = 26.0 + 2 / 24
    assert codes(run(cue, bible, m)) == {"CUT_OFF_FRAME"}


def test_a4_off_frame_cut_with_bad_transition_fails(cue, bible):
    def m(p):
        p["cuts"][3]["at_s"] = 26.0 + 2 / 24
        p["cuts"][3]["transition"] = "fade"
    assert codes(run(cue, bible, m)) == {"CUT_OFF_FRAME", "CUT_TRANSITION_BAD"}


def test_a4_unknown_transition_fails(cue, bible):
    def m(p):
        p["cuts"][3]["transition"] = "fade"
    assert codes(run(cue, bible, m)) == {"CUT_TRANSITION_BAD"}


def test_a4_hard_cut_needs_swell_fails(cue, bible):
    def m(p):
        p["cuts"][1]["transition"] = "bed_continues"  # 11.0 is a hard cut
    assert codes(run(cue, bible, m)) == {"CUT_TRANSITION_BAD"}


def test_a4_same_act_cut_with_act_change_fails(cue, bible):
    def m(p):
        p["cuts"][3]["transition"] = "act_change"  # 26.0 is same-act, not hard
    assert codes(run(cue, bible, m)) == {"CUT_TRANSITION_BAD"}


def test_a4_extra_cut_fails(cue, bible):
    def m(p):
        p["cuts"].append({"at_s": 30.0, "transition": "bed_continues"})
    assert codes(run(cue, bible, m)) == {"CUT_EXTRA"}


def test_a4_extra_cut_0_4s_after_real_cut_fails(cue, bible):
    def m(p):
        p["cuts"].append({"at_s": 11.4, "transition": "bed_continues"})
    assert codes(run(cue, bible, m)) == {"CUT_EXTRA"}


def test_a4_extra_cut_with_unknown_transition_fails(cue, bible):
    def m(p):
        p["cuts"].append({"at_s": 11.4, "transition": "fade"})
    assert codes(run(cue, bible, m)) == {"CUT_EXTRA", "CUT_TRANSITION_BAD"}


def test_a4_duplicate_cut_fails(cue, bible):
    def m(p):
        p["cuts"].append({"at_s": 11.0, "transition": "reverse_swell_to_cut"})
    assert codes(run(cue, bible, m)) == {"CUT_EXTRA"}


# ---------------------------------------------------------------- A5 IMPACT_NO_HIT, HIT_OFF_FRAME, HIT_BRIGHT_UNDER_VOICE

def test_a5_impacts_hit_on_frame_pass(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a5_missing_hit_fails(cue, bible):
    def m(p):
        p["events"].remove(event_of(p, 60.0, "hit"))
    assert codes(run(cue, bible, m)) == {"IMPACT_NO_HIT"}


def test_a5_hit_off_frame_fails(cue, bible):
    def m(p):
        event_of(p, 43.083, "hit")["at_s"] = 43.2
    assert codes(run(cue, bible, m)) == {"HIT_OFF_FRAME"}


def test_a5_bright_hit_under_voice_fails(cue, bible):
    def m(p):
        event_of(p, 60.0, "hit")["band"] = "bright"
    assert codes(run(cue, bible, m)) == {"HIT_BRIGHT_UNDER_VOICE"}


def test_a5_hit_under_voice_without_band_fails(cue, bible):
    def m(p):
        del event_of(p, 60.0, "hit")["band"]
    assert codes(run(cue, bible, m)) == {"HIT_BRIGHT_UNDER_VOICE"}


def test_a5_bright_hit_in_voice_gap_passes(cue, bible):
    def m(p):
        # 18.2 is in the gap between the voice windows [15.6, 18.0) and [18.4, 26.0)
        p["events"].append({"at_s": 18.2, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits", "band": "bright"})
    assert codes(run(cue, bible, m)) == set()


# ---------------------------------------------------------------- F8: bright hit just before speech (warning)

def test_f8_bright_hit_just_before_voice_warns(cue, bible):
    def m(p):
        # 15.55 is 0.05 s before the voice window [15.6, 18.0)
        p["events"].append({"at_s": 15.55, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits", "band": "bright"})
    r = run(cue, bible, m)
    assert codes(r) == set()
    assert warn_codes(r) == {"HIT_NEAR_VOICE"}


def test_f8_low_hit_just_before_voice_does_not_warn(cue, bible):
    def m(p):
        p["events"].append({"at_s": 15.55, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits", "band": "low"})
    r = run(cue, bible, m)
    assert codes(r) == set()
    assert "HIT_NEAR_VOICE" not in warn_codes(r)


# ---------------------------------------------------------------- A6 DROPOUT_BAD, DROPOUT_MISSING

def test_a6_dropout_in_range_passes(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a6_dropout_too_long_fails(cue, bible):
    def m(p):
        event_of(p, 43.083, "hit")["preceded_by_dropout_s"] = 0.5
    assert codes(run(cue, bible, m)) == {"DROPOUT_BAD"}


def test_a6_dropout_zero_fails(cue, bible):
    def m(p):
        event_of(p, 60.0, "hit")["preceded_by_dropout_s"] = 0.0
    assert codes(run(cue, bible, m)) == {"DROPOUT_BAD"}


def test_a6_impact_hit_without_dropout_fails(cue, bible):
    def m(p):
        del event_of(p, 43.083, "hit")["preceded_by_dropout_s"]
    assert codes(run(cue, bible, m)) == {"DROPOUT_MISSING"}


# ---------------------------------------------------------------- F2 EVENT_ROLE_MISSING, A7 BUSY_IN_VOICE, BUSY_UNGATED

def test_f2_roleless_drop_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 40.5, "type": "drop"})
    assert codes(run(cue, bible, m)) == {"EVENT_ROLE_MISSING"}


def test_f2_busy_drop_in_voice_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 20.0, "type": "drop", "role": "drums"})
    assert codes(run(cue, bible, m)) == {"DROP_IN_VOICE"}


def test_a7_busy_theme_in_voice_gap_passes(cue, bible):
    def m(p):
        p["events"].append({"at_s": 18.2, "type": "theme_entry", "theme": "MAIN", "role": "lead", "feel": "normal"})
    assert codes(run(cue, bible, m)) == set()


def test_a7_busy_theme_inside_voice_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "MAIN", "role": "lead", "feel": "normal"})
    assert codes(run(cue, bible, m)) == {"THEME_IN_VOICE"}


def test_a7_busy_role_without_gate_fails(cue, bible):
    def m(p):
        del p["sections"][1]["voice_gated"]
    assert codes(run(cue, bible, m)) == {"BUSY_UNGATED"}


def test_a7_gated_busy_roles_pass(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


# ---------------------------------------------------------------- F3 event type, A8 GOD_DROP, GOD_FEEL, god dropout

def test_f3_unknown_event_type_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 40.0, "type": "bounce", "role": "brass"})
    assert codes(run(cue, bible, m)) == {"EVENT_TYPE_UNKNOWN"}


def test_a8_drop_far_from_god_entry_passes(cue, bible):
    def m(p):
        p["events"].append({"at_s": 40.5, "type": "drop", "role": "brass"})
    assert codes(run(cue, bible, m)) == set()


def test_a8_drop_near_god_entry_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 48.5, "type": "drop", "role": "brass"})
    assert codes(run(cue, bible, m)) == {"GOD_DROP"}


def test_f3_capitalised_drop_near_god_entry_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 48.5, "type": "Drop", "role": "brass"})
    assert codes(run(cue, bible, m)) == {"GOD_DROP"}


def test_f9_bright_hit_after_god_entry_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 48.05, "type": "hit", "preceded_by_dropout_s": 0.4, "role": "hits",
                            "band": "bright"})
    assert codes(run(cue, bible, m)) == {"GOD_DROP"}


def test_a8_god_entry_not_half_feel_fails(cue, bible):
    def m(p):
        event_of(p, 48.0, "theme_entry")["feel"] = "normal"
    assert codes(run(cue, bible, m)) == {"GOD_FEEL"}


def test_a8_shiva_at_176_without_dropout_fails(cue, bible):
    def m(p):
        del event_of(p, 48.0, "theme_entry")["preceded_by_dropout_s"]
    assert codes(run(cue, bible, m)) == {"DROPOUT_MISSING"}


def test_a8_kali_at_60_bpm_without_dropout_passes(cue, bible):
    # KALI at 3.5 s is in the 60 BPM HOOK (a slow section): no drop-out and no half feel are needed
    assert event_of(good_plan(), 3.5, "theme_entry")["theme"] == "KALI"
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


# ---------------------------------------------------------------- A9 REHOOK_WINDOW

def test_a9_rehook_inside_window_passes(cue, bible):
    def m(p):
        p["rehook_at_s"] = 40.0
    assert codes(run(cue, bible, m)) == set()


def test_a9_rehook_after_window_fails(cue, bible):
    def m(p):
        p["rehook_at_s"] = 43.0
    assert codes(run(cue, bible, m)) == {"REHOOK_WINDOW"}


def test_a9_rehook_before_window_fails(cue, bible):
    def m(p):
        p["rehook_at_s"] = 31.4
    assert codes(run(cue, bible, m)) == {"REHOOK_WINDOW"}


# ---------------------------------------------------------------- A10 PEAK

def test_a10_peak_on_event_passes(cue, bible):
    def m(p):
        p["peak_at_s"] = 34.0  # a section boundary
    assert codes(run(cue, bible, m)) == set()


def test_a10_peak_off_event_fails(cue, bible):
    def m(p):
        p["peak_at_s"] = 47.0
    assert codes(run(cue, bible, m)) == {"PEAK"}


def test_a10_two_peaks_fail(cue, bible):
    def m(p):
        p["peak_at_s"] = [48.0, 34.0]
    assert codes(run(cue, bible, m)) == {"PEAK"}


# ---------------------------------------------------------------- A11 LOGO

def test_a11_logo_at_zero_passes(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a11_logo_not_at_zero_fails(cue, bible):
    def m(p):
        p["events"][0]["at_s"] = 0.5
    assert codes(run(cue, bible, m)) == {"LOGO"}


def test_a11_missing_logo_fails(cue, bible):
    def m(p):
        p["events"].pop(0)
    assert codes(run(cue, bible, m)) == {"LOGO"}


# ---------------------------------------------------------------- A12 END_STING

def test_a12_end_sting_after_last_word_passes(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_a12_end_sting_before_last_word_needs_low_band(cue, bible):
    def m(p):
        event_of(p, 69.85, "end_sting")["at_s"] = 69.0
    assert codes(run(cue, bible, m)) == {"END_STING"}


def test_a12_end_sting_at_69_80_before_last_word_needs_low_band(cue, bible):
    # the last scripted word ends at 69.846: a sting at 69.80 lands inside speech and needs band "low"
    def m(p):
        event_of(p, 69.85, "end_sting")["at_s"] = 69.80
    assert codes(run(cue, bible, m)) == {"END_STING"}


def test_a12_end_sting_before_last_word_low_band_passes(cue, bible):
    def m(p):
        ev = event_of(p, 69.85, "end_sting")
        ev["at_s"] = 69.0
        ev["band"] = "low"
    assert codes(run(cue, bible, m)) == set()


def test_a12_end_sting_outside_window_fails(cue, bible):
    def m(p):
        ev = event_of(p, 69.85, "end_sting")
        ev["at_s"] = 67.0
        ev["band"] = "low"
    assert codes(run(cue, bible, m)) == {"END_STING"}


def test_a12_long_tail_fails(cue, bible):
    def m(p):
        event_of(p, 69.85, "end_sting")["tail_s"] = 0.5
    assert codes(run(cue, bible, m)) == {"END_STING"}


def test_a12_missing_end_sting_fails(cue, bible):
    def m(p):
        p["events"].remove(event_of(p, 69.85, "end_sting"))
    assert codes(run(cue, bible, m)) == {"END_STING"}


# ---------------------------------------------------------------- A13 BIBLE_REF

def test_a13_known_refs_pass(cue, bible):
    def m(p):
        p["sections"][0]["preset"] = "KP_HITS"
    assert codes(run(cue, bible, m)) == set()


def test_a13_unknown_theme_fails(cue, bible):
    def m(p):
        event_of(p, 48.0, "theme_entry")["theme"] = "SHIVAA"
    assert codes(run(cue, bible, m)) == {"BIBLE_REF"}


def test_a13_unknown_section_role_fails(cue, bible):
    def m(p):
        p["sections"][0]["roles_on"].append("choir")
    assert codes(run(cue, bible, m)) == {"BIBLE_REF"}


def test_a13_unknown_event_role_fails(cue, bible):
    def m(p):
        event_of(p, 60.0, "hit")["role"] = "kick"
    assert codes(run(cue, bible, m)) == {"BIBLE_REF"}


def test_a13_unknown_preset_fails(cue, bible):
    def m(p):
        p["sections"][0]["preset"] = "KP_NOPE"
    assert codes(run(cue, bible, m)) == {"BIBLE_REF"}


# ---------------------------------------------------------------- A14 shape, finite numbers, fuzz

def test_a14_wrong_schema_version_fails(cue, bible):
    def m(p):
        p["schema_version"] = 2
    assert codes(run(cue, bible, m)) == {"PLAN_SCHEMA_VERSION"}


def test_a14_float_schema_version_fails(cue, bible):
    def m(p):
        p["schema_version"] = 1.0
    assert codes(run(cue, bible, m)) == {"PLAN_SCHEMA_VERSION"}


def test_a14_missing_key_fails(cue, bible):
    def m(p):
        del p["events"]
    # with no events, the peak (48.0) still sits on a section boundary, so PEAK is not raised
    assert codes(run(cue, bible, m)) == {"PLAN_SHAPE", "IMPACT_NO_HIT", "LOGO", "END_STING"}


def test_a14_nan_fails(cue, bible):
    def m(p):
        p["rehook_at_s"] = float("nan")
    assert codes(run(cue, bible, m)) == {"PLAN_NUMBER_NOT_FINITE", "REHOOK_WINDOW"}


def test_a14_non_object_plan_fails(cue, bible):
    assert codes(pc.check_plan([], cue, bible)) == {"PLAN_SHAPE"}


def test_a14_cue_sheet_shape_reported(bible):
    assert codes(pc.check_plan(good_plan(), {"total_s": 70.0}, bible)) == {"CUE_SHAPE"}


def test_a14_bible_shape_reported(cue):
    assert codes(pc.check_plan(good_plan(), cue, ["not", "a", "bible"])) == {"BIBLE_SHAPE"}


def _mutations():
    junk = [None, "x", "", [], {}, True, -1, 1e9, 0, 0.45, float("nan"), float("inf"), [1, 2], {"a": 1}]
    top = ["schema_version", "episode", "style", "home_key", "sections", "events", "cuts", "automation",
           "rehook_at_s", "peak_at_s"]
    cases = []
    for key in top:
        for value in junk:
            cases.append(("set", key, value))
        cases.append(("del", key, None))
    rng = random.Random(20261109)
    for _ in range(40):
        cases.append(("set", "sections", [rng.choice(junk) for _ in range(rng.randint(0, 3))]))
    return cases


def _apply(plan, case):
    op, key, value = case
    if op == "del":
        plan.pop(key, None)
    else:
        plan[key] = copy.deepcopy(value)


def test_a14_fuzz_never_raises(cue, bible):
    cases = _mutations()
    assert len(cases) >= 100, len(cases)
    for case in cases:
        plan = good_plan()
        _apply(plan, case)
        r = pc.check_plan(plan, cue, bible)  # must not raise
        assert set(r) == {"ok", "errors", "warnings", "stats"}
        assert r["ok"] is (len(r["errors"]) == 0)
        assert "CHECK_CRASH" not in codes(r), (case, r["errors"])


def test_a14_fuzz_nested_junk_never_raises(cue, bible):
    rng = random.Random(7)
    junk = [None, "x", [], {}, True, 3, math.nan, -2.5, [None], {"at_s": "a"}]
    paths = [("sections", 0, "bpm"), ("sections", 1, "roles_on"), ("sections", 2, "feel"),
             ("events", 1, "band"), ("events", 2, "theme"), ("events", 3, "at_s"), ("events", 4, "tail_s"),
             ("cuts", 0, "transition"), ("cuts", 1, "at_s"), ("automation", 0, "macro"), ("automation", 0, "points")]
    for _ in range(120):
        plan = good_plan()
        path = rng.choice(paths)
        target = plan[path[0]][path[1]]
        target[path[2]] = rng.choice(junk)
        r = pc.check_plan(plan, cue, bible)
        assert "CHECK_CRASH" not in codes(r), r["errors"]


def test_a14_bad_cue_and_bible_inputs_never_raise(cue, bible):
    for bad_cue in (None, [], "x", 5, {}):
        assert pc.check_plan(good_plan(), bad_cue, bible)["ok"] is False
    for bad_bible in (None, [], {"themes": 1, "track_roles": {}, "presets": {}}):
        assert pc.check_plan(good_plan(), cue, bad_bible)["ok"] is False


# ---------------------------------------------------------------- A15 expected run, CLI

def test_a15_good_plan_real_cue_ok(cue, bible):
    r = pc.check_plan(good_plan(), cue, bible)
    assert r["ok"] is True and r["errors"] == []
    assert r["stats"]["total_s"] == 70.0 and r["stats"]["hits"] == 3


def test_a15_cli_exit_codes(tmp_path, cue, bible):
    if not CUE_PATH.exists():
        pytest.skip("real cue sheet missing")
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    broken = tmp_path / "broken.json"
    good.write_text(json.dumps(GOOD), encoding="utf-8")
    worse = good_plan()
    worse["rehook_at_s"] = 43.0
    bad.write_text(json.dumps(worse), encoding="utf-8")
    broken.write_text("{ not json", encoding="utf-8")
    args = ["--cue-sheet", str(CUE_PATH), "--bible", str(BIBLE_PATH)]
    assert pc.main(["--plan", str(good)] + args) == 0
    assert pc.main(["--plan", str(bad)] + args) == 1
    assert pc.main(["--plan", str(broken)] + args) == 2
    assert pc.main(["--plan", str(tmp_path / "missing.json")] + args) == 2


def test_f7_cli_nested_json_exits_2(tmp_path, cue, bible):
    if not CUE_PATH.exists():
        pytest.skip("real cue sheet missing")
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 100000, encoding="utf-8")
    assert pc.main(["--plan", str(deep), "--cue-sheet", str(CUE_PATH), "--bible", str(BIBLE_PATH)]) == 2


# ---------------------------------------------------------------- round 2 (PCR2 review and coordinator items)

def test_pcr2_1_section_with_wrong_act_label_fails(cue, bible):
    def m(p):
        p["sections"][5]["act"] = "BUILD"  # 34-48 lies in the DROP span (34-64)
    # the relabel also makes 48.0 a BUILD-to-DROP genre/act change with no act_change cut: a second, real fault
    assert codes(run(cue, bible, m)) == {"SECTION_ACT_MISMATCH", "TEMPO_CHANGE_OFF_ACT"}


def test_pcr2_1_section_crossing_an_act_end_fails(cue, bible):
    def m(p):
        p["sections"][4]["end_s"] = 40.0  # 26-40 runs past the BUILD span end at 34
        p["sections"][5]["start_s"] = 40.0
    assert codes(run(cue, bible, m)) == {"SECTION_ACT_MISMATCH", "TEMPO_CHANGE_OFF_ACT"}


def test_pcr2_2_theme_on_brass_inside_speech_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "MAIN", "role": "brass", "feel": "normal"})
    assert codes(run(cue, bible, m)) == {"THEME_IN_VOICE"}


def test_pcr2_2_theme_on_pad_inside_speech_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 20.0, "type": "theme_entry", "theme": "MAIN", "role": "pad", "feel": "normal"})
    assert codes(run(cue, bible, m)) == {"THEME_IN_VOICE"}


def test_pcr2_2_drop_on_horn_inside_speech_fails(cue, bible):
    def m(p):
        p["events"].append({"at_s": 20.0, "type": "drop", "role": "horn"})
    assert codes(run(cue, bible, m)) == {"DROP_IN_VOICE"}


@pytest.mark.parametrize("key", ["harmony", "density_per_beat", "intensity"])
def test_pcr2_4_section_missing_field_fails(cue, bible, key):
    def m(p):
        del p["sections"][3][key]
    assert codes(run(cue, bible, m)) == {"SECTION_FIELD_MISSING"}


def test_pcr2_5_nothing_new_cut_warns(cue, bible):
    def m(p):
        p["cuts"][5]["transition"] = "bed_continues"  # 41.0: no section boundary, no event within 1.0 s after it
    r = run(cue, bible, m)
    assert codes(r) == set()
    assert warn_codes(r) == {"NOTHING_NEW_AT_CUT"}


def test_pcr2_8_act_change_cut_with_bed_continues_fails(cue, bible):
    def m(p):
        p["cuts"][4]["transition"] = "bed_continues"  # 34.0 is an act_change cut
    assert codes(run(cue, bible, m)) == {"CUT_TRANSITION_BAD"}


def test_pcr2_10_sting_running_past_total_fails(cue, bible):
    def m(p):
        ev = event_of(p, 69.85, "end_sting")
        ev["at_s"] = 69.95
        ev["tail_s"] = 0.45  # ends at 70.40, past the 70.0 s reel
    assert codes(run(cue, bible, m)) == {"END_STING"}


def test_feel_quad_passes_and_unknown_feel_fails(cue, bible):
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()  # SANDHYA lead at 25.36 is feel quad in GOOD
    assert event_of(good_plan(), 25.36, "theme_entry")["feel"] == "quad"

    def m(p):
        p["sections"][0]["feel"] = "triple"
    r = run(cue, bible, m)  # the bad section is dropped by the shape check, so later checks cascade; PLAN_SHAPE must be there
    assert r["ok"] is False
    assert "PLAN_SHAPE" in codes(r)


_JUNK = [None, "x", [], {}, True, 3, ["melodic_techno"], {"a": "b"}, float("nan"), -1.5, "", [None],
         {"melodic_techno": 1}, 0]


def _walk_set(obj, path, value, delete=False):
    for key in path[:-1]:
        obj = obj[key]
    if delete:
        if isinstance(obj, dict):
            obj.pop(path[-1], None)
        else:
            del obj[path[-1]]
    else:
        obj[path[-1]] = copy.deepcopy(value)


BIBLE_PATHS = [
    ("tempo_map",), ("tempo_map", "genre"), ("tempo_map", "genre", "HOOK"), ("tempo_map", "genre", "BUILD"),
    ("tempo_map", "shot_genres"), ("tempo_map", "shot_genres", "SHOT-003"), ("tempo_map", "shot_genres", "SHOT-004"),
    ("tempo_map", "shot_genres", "SHOT-005"), ("tempo_map", "shot_genres", "SHOT-008"),
    ("tempo_map", "alternatives"), ("tempo_map", "alternatives", "BUILD"), ("tempo_map", "HOOK"),
    ("tempo_map", "BUILD"), ("themes",), ("themes", "MAIN"), ("track_roles",), ("track_roles", "lead"),
    ("presets",), ("presets", "drums"), ("home_key",),
]

CUE_PATHS = [
    ("total_s",), ("acts",), ("acts", 0, "start_s"), ("acts", 1, "act"), ("acts", 0, "end_s"),
    ("shots",), ("shots", 2, "start_s"), ("shots", 0, "impacts"), ("cuts",), ("cuts", 0, "at_s"),
    ("cuts", 1, "act_change"), ("voice",), ("voice", "union"), ("retention",), ("retention", "rehook_window_s"),
    ("retention", "end_hook_window_s"), ("retention", "last_speech_end_s"), ("tempo_candidates",),
    ("tempo_candidates", 1, "act"), ("tempo_candidates", 1, "candidates"),
]


def test_pcr2_7_fuzz_malformed_bible_never_crashes(cue, bible):
    cases = [(path, v, False) for path in BIBLE_PATHS for v in _JUNK] + [(path, None, True) for path in BIBLE_PATHS]
    assert len(cases) >= 200, len(cases)
    for path, value, delete in cases:
        b = copy.deepcopy(bible)
        _walk_set(b, path, value, delete)
        r = pc.check_plan(good_plan(), cue, b)
        assert "CHECK_CRASH" not in codes(r), (path, value, delete, r["errors"])


def test_pcr2_7_fuzz_malformed_cue_never_crashes(cue, bible):
    cases = [(path, v, False) for path in CUE_PATHS for v in _JUNK] + [(path, None, True) for path in CUE_PATHS]
    assert len(cases) >= 200, len(cases)
    for path, value, delete in cases:
        c = copy.deepcopy(cue)
        _walk_set(c, path, value, delete)
        r = pc.check_plan(good_plan(), c, bible)
        assert "CHECK_CRASH" not in codes(r), (path, value, delete, r["errors"])


def test_pcr2_7_shot_genre_list_is_bible_shape(cue, bible):
    b = copy.deepcopy(bible)
    b["tempo_map"]["shot_genres"]["SHOT-004"] = ["melodic_techno"]
    assert codes(pc.check_plan(good_plan(), cue, b)) == {"BIBLE_SHAPE"}


def test_nwr3_6_hard_act_cut_needs_swell_key_colour_fails(cue, bible):
    def m(p):
        p["cuts"][1]["transition"] = "key_colour_on_downbeat"  # 11.0 is hard AND act_change: swell only
    assert codes(run(cue, bible, m)) == {"CUT_TRANSITION_BAD"}


def test_nwr3_6_hard_act_cut_swell_passes(cue, bible):
    def m(p):
        p["cuts"][1]["transition"] = "swell_to_cut"
    assert codes(run(cue, bible, m)) == set()


def test_transform_known_to_bible_passes(cue, bible):
    assert event_of(good_plan(), 43.2, "theme_entry")["transform"] == "chaos_41s"
    assert codes(pc.check_plan(good_plan(), cue, bible)) == set()


def test_transform_not_in_bible_theme_fails(cue, bible):
    def m(p):
        event_of(p, 43.2, "theme_entry")["transform"] = "chaos_9s"
    assert codes(run(cue, bible, m)) == {"BIBLE_REF"}


def test_transform_on_theme_without_transforms_fails(cue, bible):
    def m(p):
        event_of(p, 40.25, "theme_entry")["transform"] = "chaos_41s"  # MAIN has no transforms in the bible
    assert codes(run(cue, bible, m)) == {"BIBLE_REF"}


# ---------------------------------------------------------------- variant A (cinematic window 0 to 18.833 s)

V4_CUE_PATH = STORY / "pack_opus_high_20261108_v4_deva" / "score" / "ep1" / "cue_sheet.json"
A_PLAN_PATH = STORY / "pack_opus_high_20261108_v4_deva" / "score" / "ep1" / "score_plan_A_0_18.json"


@pytest.fixture(scope="module")
def v4_cue():
    return json.loads(V4_CUE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def a_plan():
    return json.loads(A_PLAN_PATH.read_text(encoding="utf-8"))


def test_variant_a_real_plan_passes(v4_cue, bible, a_plan):
    rep = pc.check_plan(a_plan, v4_cue, bible)
    assert rep["ok"], rep["errors"]
    assert rep["stats"]["total_s"] == pytest.approx(18.833)


def test_variant_a_build_tempo_must_be_cinematic_101(v4_cue, bible, a_plan):
    a_plan["sections"][2]["bpm"] = 128
    a_plan["sections"][2]["genre"] = "hypnotic_techno"
    rep = pc.check_plan(a_plan, v4_cue, bible)
    assert "TEMPO_NOT_IN_BIBLE" in [e["code"] for e in rep["errors"]]


def test_variant_a_event_after_window_fails(v4_cue, bible, a_plan):
    a_plan["events"].append({"at_s": 26.19, "type": "theme_entry", "theme": "SANDHYA", "role": "lead", "feel": "quad"})
    rep = pc.check_plan(a_plan, v4_cue, bible)
    assert _codes_of(rep) == ["WINDOW_OUTSIDE"]


def test_variant_a_without_window_fails(v4_cue, bible, a_plan):
    del a_plan["window_s"]
    rep = pc.check_plan(a_plan, v4_cue, bible)
    assert "PLAN_SHAPE" in _codes_of(rep)


def test_variant_a_window_past_reel_fails(v4_cue, bible, a_plan):
    a_plan["window_s"] = [0.0, 80.0]
    rep = pc.check_plan(a_plan, v4_cue, bible)
    assert "PLAN_SHAPE" in _codes_of(rep)


def test_window_s_without_variant_a_fails(v4_cue, bible, a_plan):
    a_plan["variant"] = "B"
    rep = pc.check_plan(a_plan, v4_cue, bible)
    assert "PLAN_SHAPE" in _codes_of(rep)


def test_variant_a_needs_a_tempo_map(v4_cue, bible, a_plan):
    bib = copy.deepcopy(bible)
    del bib["ab_test_m1"]["A_tempo_map"]
    rep = pc.check_plan(a_plan, v4_cue, bib)
    assert _codes_of(rep) == ["BIBLE_SHAPE"]


def test_variant_a_bad_tempo_map_shape_is_bible_shape(v4_cue, bible, a_plan):
    bib = copy.deepcopy(bible)
    bib["ab_test_m1"]["A_tempo_map"] = {"BUILD": 101}
    rep = pc.check_plan(a_plan, v4_cue, bib)
    assert "BIBLE_SHAPE" in _codes_of(rep)


def test_variant_a_plan_has_no_rehook_or_end_sting_requirement(v4_cue, bible, a_plan):
    assert "rehook_at_s" not in a_plan and "peak_at_s" not in a_plan
    assert pc.check_plan(a_plan, v4_cue, bible)["ok"]


def _codes_of(rep):
    return [e["code"] for e in rep["errors"]]
