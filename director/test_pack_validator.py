"""Offline tests for director/pack_validator.py. Synthetic packs only; no network, no model call."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import pack_validator as pv
from pack_validator import self_check, validate_pack, validate_stage, repair_loop, duration_bucket, main

from h3.shot_table_spec import lattice, MAX_REPAIR_RETRIES, STUDIO_REEL_RANGE

ROOT = Path(__file__).resolve().parents[1]
REAL_PACKS = [ROOT / "stories" / "mahadev_katha_indresh" / "pack_opus_medium_v1",
              ROOT / "stories" / "upanishad_ganga_ep4_ashtavakra" / "pack_super-vl_20261106_v1"]

STYLE_LINE = "2D hand-drawn cel-shaded anime, organic line weight, Indian classical Puranic proportions"


def bible():
    return {
        "characters": {
            "CHAR-RAMA": {"sheet_prompt": "16:9 labeled turnaround sheet on a plain neutral backdrop, hand-drawn cel-shaded 2D anime"},
            "CHAR-SITA": {"sheet_prompt": "16:9 labeled expression sheet on a plain neutral backdrop, hand-drawn cel-shaded 2D anime"},
            "CHAR-X": {"sheet_prompt": "16:9 labeled sheet on a plain neutral backdrop, hand-drawn cel-shaded 2D anime"},
            "CHAR-Y": {"sheet_prompt": "16:9 labeled sheet on a plain neutral backdrop, hand-drawn cel-shaded 2D anime"},
        },
        "environments": {
            "ENV-CLEARING": {"card_prompt": "empty packed-earth clearing, banyan trunks, river band far off, hut at right",
                             "continuity_landmarks": ["banyan trunk left", "hut at right"]},
        },
        "props": {"PROP-BOW": {"prompt": "tall lacquered bow"}},
        "style": {"line": STYLE_LINE},
    }


def story():
    return {"story_gate_checks": {name: {"pass": True, "evidence": f"evidence for {name}"} for name in pv.STORY_GATE_CHECKS}}


HOOK_CYCLE = ("reveal", "chase", "tender")   # every 3 consecutive shots contain reveal


def shots_for_episode(ep, count=12, dur=5.5):
    rows = []
    for i in range(count):
        n = 8
        L = lattice(n)
        t, per_second = 0.0, []
        while t < dur - 1e-9:
            t1 = round(min(t + 1.0, dur), 3)
            per_second.append({"t0": round(t, 3), "t1": t1, "action_pose_expression": "Rama breathes",
                               "camera": "slow push in", "spatial_position": "centre", "audio_cue": "leaf rustle",
                               "handoff_to_next_second": "stillness holds"})
            t = t1
        rows.append({
            "id": f"S{ep}-{i:02d}", "episode": ep, "route": "FL2VA", "lattice_n": n,
            "pixel_frames": L["pixel_frames"], "latent_slots": L["latent_slots"], "editorial_duration_sec": dur,
            "continuity_handoff": {"incoming": "from prior pose", "outgoing": "into next pose",
                                   "loop_seam": None},
            "reference_anchors": {
                "fixed_landmarks": ["banyan trunk left", "hut at right"],
                "character_positions": [{"id": "CHAR-RAMA", "screen": "left", "depth": "mid", "facing": "right"},
                                        {"id": "CHAR-SITA", "screen": "right", "depth": "back"}],
                "exited_character_status": [],
                "lighting_baseline": {"key": "low sun from screen left", "fill": "cool shade",
                                      "rim": "gold rim", "shot_modifiers": []},
            },
            "hook_type": HOOK_CYCLE[i % 3],
            "is_opening_0_2s_hook": i == 0,
            "is_closing_hook": i == count - 1,
            "deliberate_flip_marker": None,
            "per_second_directives": per_second,
            "audio_and_dialogue_track": {
                "narration": None,
                "dialogue": [],
                "sfx_cues": [{"time_range": "0.2-0.6s", "sfx_key": "leaf_rustle", "description": "leaf rustle"}],
                "performance_notes": {"text": "steady breath", "narrator_mouth_closed": True,
                                      "mouth_state": {"0": "closed", "1": "open_non_verbal_breath"}},
            },
            "cast": [{"id": "CHAR-RAMA", "screen": "left", "facing": "right"},
                     {"id": "CHAR-SITA", "screen": "right", "facing": "left"}],
            "props": [{"id": "PROP-BOW", "where": "leaning on post"}],
            "set": "ENV-CLEARING",
        })
    from h3 import v4_to_h3                      # H3-01: the lattice must be one that H3 can cut (head 8..35, tail 24..47)
    fitted, _, _ = v4_to_h3.fit_lattice(rows)
    return fitted


def valid_shots():
    return shots_for_episode(1) + shots_for_episode(2)


def codes(rep):
    return {e["code"] for e in rep["errors"]}


def write_pack(d, shots, bib=None, story_data=None):
    d.mkdir(parents=True, exist_ok=True)
    (d / "shots.json").write_text(json.dumps(shots, ensure_ascii=False), encoding="utf-8")
    (d / "bible.json").write_text(json.dumps(bib if bib is not None else bible(), ensure_ascii=False), encoding="utf-8")
    if story_data is not None:
        (d / "stage_1.json").write_text(json.dumps(story_data, ensure_ascii=False), encoding="utf-8")
    return d


def episode_rows(shots, ep=1):
    return [r for r in shots if r["episode"] == ep]


# ---------- valid pack ----------

def test_valid_v4_pack_passes_everything(tmp_path):
    pack = write_pack(tmp_path / "pack", valid_shots(), story_data=story())
    before = sorted(os.listdir(pack))
    rep = validate_pack(pack)
    assert rep["ok"], rep["errors"]
    assert rep["warnings"] == []
    assert sorted(os.listdir(pack)) == before   # writes nothing
    assert validate_stage("shots", valid_shots(), bible())["ok"]
    assert self_check(valid_shots(), bible())["ok"]
    assert validate_stage("story", story())["ok"]
    assert validate_stage("bible", bible())["ok"]
    assert rep["stats"]["episodes"]["1"] == {"shots": 12, "seconds": 66.0, "bucket": "60-90"}


def test_duration_bucket_names():
    assert duration_bucket(66.0) == "60-90"
    assert duration_bucket(45.0) == "30-60"
    assert duration_bucket(200.0) == "custom"
    assert STUDIO_REEL_RANGE == (60.0, 75.0)


# ---------- story gate (stage 1) ----------

@pytest.mark.parametrize("mutate, code", [
    (lambda s: s["story_gate_checks"].pop("active_protagonist"), "STORY-01"),
    (lambda s: s["story_gate_checks"]["crisis_from_flaw"].update({"pass": False}), "STORY-02"),
    (lambda s: s["story_gate_checks"]["ending_reuses_emotional_anchor"].update({"evidence": "  "}), "STORY-03"),
])
def test_story_gate_rules(mutate, code):
    s = story()
    mutate(s)
    assert code in codes(validate_stage("story", s))


# ---------- bible (stage 2) ----------

def test_bible_list_layout_is_rejected():
    b = bible()
    b["characters"] = [{"id": "CHAR-RAMA"}]
    assert "BIBLE-01" in codes(validate_stage("bible", b))


def test_bible_id_prefix_is_checked():
    b = bible()
    b["props"]["BOW"] = b["props"].pop("PROP-BOW")
    assert "BIBLE-02" in codes(validate_stage("bible", b))


def test_env_prompt_with_people_is_rejected():
    b = bible()
    b["environments"]["ENV-CLEARING"]["card_prompt"] = "clearing with a crowd of villagers"
    assert "BIBLE-04" in codes(validate_stage("bible", b))


def test_env_hand_drawn_wording_is_not_a_hand():
    b = bible()
    b["environments"]["ENV-CLEARING"]["card_prompt"] += ", hand-drawn cel-shaded backdrop"
    assert validate_stage("bible", b)["ok"]


def test_env_without_card_prompt_or_landmarks():
    b = bible()
    b["environments"]["ENV-CLEARING"].pop("card_prompt")
    b["environments"]["ENV-CLEARING"].pop("continuity_landmarks")
    c = codes(validate_stage("bible", b))
    assert {"BIBLE-03", "BIBLE-05"} <= c


def test_char_sheet_must_be_16_9_labeled_on_neutral_backdrop():
    b = bible()
    b["characters"]["CHAR-RAMA"]["sheet_prompt"] = "4:3 sheet on a busy temple background, hand-drawn cel-shaded 2D anime"
    assert codes(validate_stage("bible", b)) == {"BIBLE-06"}


def test_style_lock_forbids_3d_wording():
    b = bible()
    b["style"]["line"] = STYLE_LINE + ", Pixar-like 3D CG render"
    c = codes(validate_stage("bible", b))
    assert "BIBLE-07" in c


def test_style_lock_needs_hand_drawn_cel_wording():
    b = bible()
    b["style"]["line"] = "smooth shading"
    for ch in b["characters"].values():
        ch["sheet_prompt"] = "16:9 labeled sheet on a plain neutral backdrop"
    assert "BIBLE-08" in codes(validate_stage("bible", b))


def test_backdrop_allows_one_colour_word():
    b = bible()
    for ch in b["characters"].values():
        ch["sheet_prompt"] = ch["sheet_prompt"].replace("plain neutral backdrop", "plain neutral grey backdrop")
    assert "BIBLE-06" not in codes(validate_stage("bible", b))
    for ch in b["characters"].values():
        ch["sheet_prompt"] = ch["sheet_prompt"].replace("plain neutral grey backdrop", "busy temple backdrop")
    assert "BIBLE-06" in codes(validate_stage("bible", b))


# ---------- structure (stage 3 columns) ----------

@pytest.mark.parametrize("mutate, code", [
    (lambda s: s[0].pop("audio_and_dialogue_track"), "ROW-02"),
    (lambda s: s[1].update({"id": s[0]["id"]}), "ROW-03"),
    (lambda s: s[2].update({"route": "XYZ"}), "ROW-04"),
    (lambda s: s[3]["continuity_handoff"].pop("incoming"), "CONT-01"),
    (lambda s: s[4]["reference_anchors"]["lighting_baseline"].pop("rim"), "ANCH-02"),
    (lambda s: s[5].update({"hook_type": "bogus"}), "HOOK-01"),
    (lambda s: s[6]["audio_and_dialogue_track"].update({"sfx_cues": []}), "AUD-04"),
    (lambda s: s[7]["audio_and_dialogue_track"]["performance_notes"].update({"narrator_mouth_closed": False}), "AUD-05"),
    (lambda s: s[8]["audio_and_dialogue_track"]["performance_notes"]["mouth_state"].update({"2": "talking"}), "AUD-05"),
    (lambda s: s[9]["audio_and_dialogue_track"].update({"narration": {"text": "x", "language": "fr", "time_range": [0, 1]}}), "AUD-02"),
    (lambda s: s[10]["reference_anchors"].pop("exited_character_status"), "ANCH-01"),
])
def test_column_completeness_rules(mutate, code):
    shots = valid_shots()
    mutate(shots)
    assert code in codes(validate_stage("shots", shots, bible()))


def test_strong_hook_flags_are_bools_only():
    shots = valid_shots()
    shots[4]["is_closing_hook"] = "yes"
    assert "HOOK-02" in codes(validate_stage("shots", shots, bible()))


# ---------- self_check: the six Step 5.5 checks ----------

def test_s55_1_density_window_broken():
    shots = valid_shots()
    for r in episode_rows(shots)[1:4]:
        r["hook_type"] = "tender" if r["hook_type"] != "tender" else "suspense"
    assert "S55-1" in codes(self_check(shots, bible()))


def test_s55_1_opening_must_be_strong():
    shots = valid_shots()
    episode_rows(shots)[0]["hook_type"] = "chase"
    assert "S55-1" in codes(self_check(shots, bible()))


def test_s55_1_closing_must_be_strong():
    shots = valid_shots()
    episode_rows(shots)[-1]["hook_type"] = "chase"
    assert "S55-1" in codes(self_check(shots, bible()))


def test_s55_1_rehook_around_30s_missing():
    shots = valid_shots()
    rows = episode_rows(shots)
    rows[5]["hook_type"] = "callback"   # starts at 27.5 s
    rows[6]["hook_type"] = "chase"      # starts at 33.0 s
    c = self_check(shots, bible())
    assert any("re-hook" in e["message"] for e in c["errors"])


def test_s55_2_duration_cap_and_lattice():
    shots = valid_shots()
    episode_rows(shots)[0]["editorial_duration_sec"] = 15.5
    assert "S55-2" in codes(self_check(shots, bible()))

    shots = valid_shots()
    episode_rows(shots)[0]["lattice_n"] = 5
    assert "S55-2" in codes(self_check(shots, bible()))

    shots = valid_shots()
    episode_rows(shots)[0]["pixel_frames"] += 1
    assert "S55-2" in codes(self_check(shots, bible()))

    shots = valid_shots()
    episode_rows(shots)[0]["latent_slots"] += 1
    assert "S55-2" in codes(self_check(shots, bible()))


def test_s55_3_at_most_three_characters():
    shots = valid_shots()
    rows = episode_rows(shots)
    rows[2]["reference_anchors"]["character_positions"] += [
        {"id": "CHAR-X", "screen": "far left", "depth": "front"},
        {"id": "CHAR-Y", "screen": "far right", "depth": "back"}]
    assert "S55-3" in codes(self_check(shots, bible()))


def test_s55_4_landmark_and_lighting_inheritance_and_release():
    shots = valid_shots()
    episode_rows(shots)[3]["reference_anchors"]["fixed_landmarks"] = ["hut at right"]
    assert "S55-4" in codes(self_check(shots, bible()))

    shots = valid_shots()
    episode_rows(shots)[3]["reference_anchors"]["lighting_baseline"]["key"] = ""
    assert "S55-4" in codes(self_check(shots, bible()))

    shots = valid_shots()
    episode_rows(shots)[3]["reference_anchors"]["exited_character_status"] = [
        {"id": "CHAR-X", "left_after_shot": "S1-02", "off_stage_shots": 1, "released": True}]
    assert "S55-4" in codes(self_check(shots, bible()))


def test_s55_5_per_second_coverage():
    shots = valid_shots()
    episode_rows(shots)[2]["per_second_directives"][1]["t0"] = 1.2     # gap after 1.0
    assert "S55-5" in codes(self_check(shots, bible()))

    shots = valid_shots()
    del episode_rows(shots)[2]["per_second_directives"][0]["camera"]   # one of the 5 elements missing
    assert "S55-5" in codes(self_check(shots, bible()))

    shots = valid_shots()
    episode_rows(shots)[2]["per_second_directives"][-1]["t1"] = 5.0    # does not reach S.SS = 5.5
    assert "S55-5" in codes(self_check(shots, bible()))


def test_s55_6_unknown_id_is_rejected():
    shots = valid_shots()
    episode_rows(shots)[1]["cast"].append({"id": "CHAR-GHOST", "screen": "centre", "facing": "left"})
    c = self_check(shots, bible())
    assert "S55-6" in codes(c)
    assert any("CHAR-GHOST" in e["message"] for e in c["errors"])


def test_s55_6_unmarked_flip_then_marked_flip_passes():
    def flip_from(shots, start, marker):
        rows = episode_rows(shots)
        for r in rows[start:]:
            for p in r["reference_anchors"]["character_positions"]:
                if p["id"] == "CHAR-RAMA":
                    p["screen"] = "right"
        rows[start]["deliberate_flip_marker"] = marker

    shots = valid_shots()
    flip_from(shots, 3, None)
    assert "S55-6" in codes(self_check(shots, bible()))

    shots = valid_shots()
    flip_from(shots, 3, "HARD CUT — time skip: 2h")
    assert self_check(shots, bible())["ok"]


def test_s55_6_lighting_flip_needs_marker():
    shots = valid_shots()
    episode_rows(shots)[5]["reference_anchors"]["lighting_baseline"]["key"] = "low sun from screen right"
    assert "S55-6" in codes(self_check(shots, bible()))


def test_reel_range_is_checked_per_episode():
    shots = [dict(r, editorial_duration_sec=4.0) for r in valid_shots()]
    rep = self_check(shots, bible())
    assert "REEL-01" in codes(rep)
    assert rep["stats"]["episodes"]["1"]["seconds"] == 48.0


# ---------- repair loop ----------

def test_repair_loop_repairs_once_then_stops():
    seen = []

    def produce():
        return {"story_gate_checks": {}}

    def repair(errors):
        seen.append(errors)
        return story()

    data, rep = repair_loop("story", produce, repair)
    assert rep["ok"] and data == story()
    assert len(seen) == 1 and all({"code", "where", "message"} <= set(e) for e in seen[0])


def test_repair_loop_never_loops_more_than_max_retries():
    calls = []

    def repair(errors):
        calls.append(1)
        return {"story_gate_checks": {}}

    _, rep = repair_loop("story", lambda: {}, repair, max_retries=3)
    assert len(calls) == 3 and not rep["ok"]

    calls.clear()
    _, rep = repair_loop("story", lambda: {}, repair)
    assert len(calls) == MAX_REPAIR_RETRIES == 1

    calls.clear()
    repair_loop("story", lambda: {}, repair, max_retries=0)
    assert calls == []


def test_repair_loop_skips_repair_when_valid():
    calls = []
    data, rep = repair_loop("story", story, lambda e: calls.append(e))
    assert rep["ok"] and calls == []


def test_unknown_stage_is_reported():
    rep = validate_stage("nope", {})
    assert codes(rep) == {"STAGE-00"}


def test_captions_stage_passes_through_with_a_warning():
    rep = validate_stage("5", {"captions": []})
    assert rep["ok"] and [w["code"] for w in rep["warnings"]] == ["STAGE-02"]


# ---------- legacy mode and the real pack folders ----------

def old_row(i, sec=5.9, cast=("CHAR-RAMA",), set_="ENV-CLEARING"):
    return {"id": f"SHOT-{i:02d}", "episode": 1, "mode": "fl2va", "seconds": sec,
            "cast": [{"id": c, "screen": "left", "facing": "right"} for c in cast],
            "props": [{"id": "PROP-BOW", "where": "post"}], "set": set_, "beats": [], "dialogue": []}


def old_bible():
    return {"characters": [{"id": "CHAR-RAMA"}, {"id": "CHAR-SITA"}],
            "environments": [{"id": "ENV-CLEARING"}], "props": [{"id": "PROP-BOW"}]}


def test_legacy_old_pack_passes_with_v4_warnings(tmp_path):
    shots = [old_row(i, sec=5.9) for i in range(12)]   # 12 x 5.9 = 70.8 s, inside the reel preset
    pack = write_pack(tmp_path / "old", shots, bib=old_bible())
    rep = validate_pack(pack, legacy=True)
    assert rep["ok"], rep["errors"]
    assert rep["warnings"] and all("legacy" in w["message"] for w in rep["warnings"])
    assert "ROW-02" in {w["code"] for w in rep["warnings"]}


def test_legacy_catches_bad_ids_lattice_and_characters(tmp_path):
    shots = [old_row(0, cast=("CHAR-GHOST",)), old_row(1, sec=5.6), old_row(2, cast=("CHAR-RAMA", "CHAR-SITA", "CHAR-X", "CHAR-Y"))]
    pack = write_pack(tmp_path / "old_bad", shots, bib=old_bible())
    rep = validate_pack(pack, legacy=True)
    assert {"S55-6", "S55-2", "S55-3"} <= codes(rep)


@pytest.mark.parametrize("pack_dir", REAL_PACKS, ids=lambda p: p.name)
def test_legacy_runs_on_real_pack_folders(pack_dir, capsys):
    if not (pack_dir / "shots.json").exists():
        pytest.skip(f"{pack_dir} not present")
    rc = main([str(pack_dir), "--legacy", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc in (0, 1)
    assert out["stats"]["mode"] == "legacy" and "episodes" in out["stats"]


# ---------- CLI ----------

def test_cli_exit_codes(tmp_path, capsys):
    with pytest.raises(SystemExit) as usage:
        main([])
    assert usage.value.code == 2
    assert main([str(tmp_path / "missing")]) == 2

    good = write_pack(tmp_path / "good", valid_shots(), story_data=story())
    assert main([str(good)]) == 0
    capsys.readouterr()
    bad_shots = valid_shots()
    bad_shots[0]["lattice_n"] = 3
    bad = write_pack(tmp_path / "bad", bad_shots)
    assert main([str(bad), "--json"]) == 1
    assert "S55-2" in {e["code"] for e in json.loads(capsys.readouterr().out)["errors"]}


def test_cli_runs_as_a_script(tmp_path):
    good = write_pack(tmp_path / "good_script", valid_shots(), story_data=story())
    proc = subprocess.run([sys.executable, str(ROOT / "director" / "pack_validator.py"), str(good), "--json"],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True


# ---------- multilingual rows (owner addendum 2026-11-07) ----------

def add_languages(shots, langs):
    """Every row gets a narration/dialogue/caption text per language, all on the same time ranges."""
    for r in shots:
        t = r["audio_and_dialogue_track"]
        t["narration"] = {"text": "shared narration", "language": langs[0], "time_range": [0.5, 3.0]}
        t["narration_by_lang"] = {lang: {"text": f"{lang} narration", "time_range": [0.5, 3.0]} for lang in langs}
        t["dialogue_by_lang"] = {lang: [] for lang in langs}
        t["captions_by_lang"] = {lang: [{"text": "two short words", "time_range": [0.5, 3.0]}] for lang in langs}
    return shots


def ml_shots(langs=("en", "hi", "mr")):
    return add_languages(valid_shots(), langs)


def test_all_three_languages_pass_with_the_selection():
    rep = validate_stage("shots", ml_shots(), bible(), output_languages=["en", "hi", "mr"])
    assert rep["ok"], rep["errors"]


def test_two_languages_pass_and_order_is_free():
    rows = ml_shots(("en", "hi"))
    assert validate_stage("shots", rows, bible(), output_languages=["hi", "en"])["ok"]


def test_single_language_rows_keep_working():
    assert validate_stage("shots", valid_shots(), bible(), output_languages=["en"])["ok"]
    assert validate_stage("shots", valid_shots(), bible(), output_languages=None)["ok"]


def test_missing_language_in_one_shot_is_reported():
    rows = ml_shots()
    del rows[3]["audio_and_dialogue_track"]["captions_by_lang"]["mr"]
    rep = validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"])
    assert "ML-03" in codes(rep)
    assert any(e["where"].startswith("shots[3]") and "mr" in e["where"] for e in rep["errors"] if e["code"] == "ML-03")


def test_single_language_row_inside_a_multi_language_story_is_reported():
    rep = validate_stage("shots", valid_shots(), bible(), output_languages=["en", "hi"])
    assert "ML-03" in codes(rep)


def test_mismatched_time_ranges_are_reported():
    rows = ml_shots()
    rows[2]["audio_and_dialogue_track"]["narration_by_lang"]["hi"]["time_range"] = [0.5, 3.5]
    assert "ML-05" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"]))

    rows = ml_shots()
    rows[2]["audio_and_dialogue_track"]["captions_by_lang"]["mr"][0]["time_range"] = [0.6, 3.0]
    assert "ML-05" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"]))

    rows = ml_shots()
    rows[2]["audio_and_dialogue_track"]["dialogue_by_lang"]["hi"] = [
        {"speaker": "CHAR-RAMA", "text": "a", "tone": "calm", "time_range": [1.0, 2.0]}]
    rows[2]["audio_and_dialogue_track"]["dialogue_by_lang"]["mr"] = [
        {"speaker": "CHAR-RAMA", "text": "b", "tone": "calm", "time_range": [1.5, 2.0]}]
    assert "ML-05" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"]))


def test_unknown_language_code_is_reported():
    rows = ml_shots()
    rows[1]["audio_and_dialogue_track"]["narration_by_lang"]["fr"] = {"text": "x", "time_range": [0.5, 3.0]}
    assert "ML-02" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"]))

    rows = ml_shots()
    rows[1]["audio_and_dialogue_track"]["captions_by_lang"]["ta"] = [{"text": "x", "time_range": [0.5, 3.0]}]
    assert "ML-02" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"]))


def test_primary_language_must_be_selected():
    rows = ml_shots()
    rows[4]["audio_and_dialogue_track"]["narration"]["language"] = "mr"
    assert "ML-04" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi"]))


def test_narration_beyond_editorial_duration_is_reported():
    rows = ml_shots()
    rows[5]["audio_and_dialogue_track"]["narration_by_lang"]["hi"]["time_range"] = [0.5, 6.0]
    rows[5]["audio_and_dialogue_track"]["narration_by_lang"]["en"]["time_range"] = [0.5, 6.0]
    rows[5]["audio_and_dialogue_track"]["narration_by_lang"]["mr"]["time_range"] = [0.5, 6.0]
    rows[5]["audio_and_dialogue_track"]["narration"]["time_range"] = [0.5, 6.0]
    assert "ML-06" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"]))


def test_caption_card_over_six_words_is_reported():
    rows = ml_shots()
    rows[6]["audio_and_dialogue_track"]["captions_by_lang"]["hi"][0]["text"] = "one two three four five six seven"
    assert "ML-07" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"]))


def test_malformed_by_lang_block_is_reported():
    rows = ml_shots()
    rows[7]["audio_and_dialogue_track"]["captions_by_lang"]["hi"] = "not a list"
    assert "ML-01" in codes(validate_stage("shots", rows, bible(), output_languages=["en", "hi", "mr"]))


def test_lang_check_hook_gets_every_text_and_its_flags_become_errors():
    seen = []

    def hook(text, lang):
        seen.append((lang, text))
        if lang == "hi" and "narration" in text:
            return {"ok": False, "flags": ["stiff literary verb"]}
        return None

    rep = validate_stage("shots", ml_shots(), bible(), output_languages=["en", "hi", "mr"], lang_check=hook)
    assert {lang for lang, _ in seen} == {"en", "hi", "mr"}
    assert "ML-08" in codes(rep) and any("stiff literary verb" in e["message"] for e in rep["errors"])


def test_lang_check_passing_adds_no_errors():
    rep = validate_stage("shots", ml_shots(), bible(), output_languages=["en", "hi", "mr"],
                         lang_check=lambda text, lang: [])
    assert rep["ok"], rep["errors"]


def test_story_output_languages_rules():
    s = story()
    s.update({"output_languages": ["hi", "en"], "output_language": "hi"})
    assert validate_stage("story", s)["ok"]
    for bad in ({"output_languages": ["en", "fr"]}, {"output_languages": ["en", "en"]},
                {"output_languages": []}, {"output_languages": ["en", "hi"], "output_language": "hi"}):
        s = {**story(), **bad}
        assert "STORY-04" in codes(validate_stage("story", s)), bad


def test_validate_pack_reads_output_languages_from_the_story(tmp_path):
    s = {**story(), "output_languages": ["en", "hi"]}
    pack = write_pack(tmp_path / "ml_pack", valid_shots(), story_data=s)
    assert "ML-03" in codes(validate_pack(pack))
    pack2 = write_pack(tmp_path / "ml_pack_ok", ml_shots(("en", "hi")), story_data=s)
    assert validate_pack(pack2)["ok"]


# --- audit gaps 3 and 5 (2026-11-08) ---
def test_speech_rate_flags_a_line_that_cannot_fit_its_window():
    shots = valid_shots()
    track = shots[0]["audio_and_dialogue_track"]
    track["narration_by_lang"] = {"en": {"text": "one two three four five six seven eight nine", "language": "en", "time_range": [0.0, 2.0]}}
    rep = pv.self_check(shots, None)
    assert any(e["code"] == "SPEECH-01" and "4.5 words/s" in e["message"] for e in rep["errors"])
    track["narration_by_lang"]["en"]["time_range"] = [0.0, 3.5]
    assert not any(e["code"] == "SPEECH-01" for e in pv.self_check(shots, None)["errors"])


def test_unfit_lattice_is_error_h3_01():
    shots = valid_shots()
    shots[3].update(lattice_n=6, pixel_frames=107, latent_slots=32)
    assert any(e["code"] == "H3-01" for e in pv.self_check(shots, None)["errors"])


def test_source_hash_must_match(tmp_path):
    import hashlib
    story = tmp_path / "s"
    (story / "pack").mkdir(parents=True)
    (story / "SOURCE.md").write_text("text", encoding="utf-8")
    (story / "story.json").write_text('{"source_sha256": "%s"}' % hashlib.sha256(b"text").hexdigest(), encoding="utf-8")
    errs, warns = [], []
    pv._source_check(story / "pack", errs, warns)
    assert errs == []
    (story / "SOURCE.md").write_text("changed", encoding="utf-8")
    pv._source_check(story / "pack", errs, warns)
    assert errs and errs[0]["code"] == "SRC-01"
