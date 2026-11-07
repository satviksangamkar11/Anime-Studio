"""
Tests for flow/scripts/pack_to_spec.py and the prop/forbidden changes in build_jobs.py.

Offline only: no network, no model call. Run with: C:/Python314/python.exe -m pytest -q -p no:cacheprovider flow/scripts
The real Kaliya pack is read-only input here; the other-story pack is written under pytest's tmp_path.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import build_jobs as bj  # noqa: E402
import pack_to_spec as p2s  # noqa: E402

FLOW_DIR = SCRIPTS_DIR.parent
REPO_DIR = FLOW_DIR.parent
REAL_PACK = REPO_DIR / "stories" / "kaliya_katha_dhenuk" / "pack_nemotron_ultra_v1"
REAL_SLUG = "kaliya_katha_dhenuk"
DEVA_IDS = ["CHAR-INDRA", "CHAR-BRAHMA", "CHAR-NARADA", "CHAR-SARASVATI"]  # in the pack, missing from its bible


def _real_pack():
    return p2s.load_pack(REAL_PACK)


def _real_pack_with_deva_fixtures():
    """Test fixture only: the real bible lacks the four deva ids. Empty entries let the rest of the real pack run.
    Nothing here is written to disk or used by the converter."""
    shots, bible = _real_pack()
    for cid in DEVA_IDS:
        bible["characters"].setdefault(cid, {})
    return shots, bible


def _lighthouse_pack():
    """A tiny synthetic pack from a different story: no Kaliya names anywhere."""
    bible = {
        "characters": {"CHAR-MIRA": {"age": "adult", "heads": 7, "attributes": ["red coat", "brass lamp"]}},
        "environments": {
            "ENV-LIGHTHOUSE-STAIR": {"layers": ["FG_iron_rail", "MID_spiral_stair", "BG_sea_window"],
                                     "light": "dusk_screen_right_35mm"},
            "ENV-LAMP-ROOM": {"layers": ["FG_brass_rail", "MID_lamp", "BG_night_sea"],
                              "light": "dusk_screen_left_24mm"},
        },
        "props": {"PROP-LAMP": {"material": "brass", "size": "small"}},
    }
    shots = [
        {"id": "SHOT-01", "scene": "climb", "mode": "fl2va", "aspect": "9:16",
         "cast": [{"id": "CHAR-MIRA", "screen": "center", "facing": "up", "start_pose": "POSE-A", "end_pose": "POSE-B"}],
         "props": [{"id": "PROP-LAMP", "where": "raised in the right hand"}],
         "set": "ENV-LIGHTHOUSE-STAIR",
         "camera": {"move": "static", "lens_mm": 35, "height": "low",
                    "start_framing": "full body", "end_framing": "medium"},
         "light": {"key": "last light through the window", "mood": "cold blue", "rim": "none"},
         "start_state": "Mira climbs the stair with the lamp raised",
         "end_state": "Mira stops on the top step with the lamp lowered",
         "keyframes": {"start": "keyframes/SHOT-01-FRAME-A.png", "end": "keyframes/SHOT-01-FRAME-B.png"}},
        {"id": "SHOT-02", "scene": "top", "mode": "fl2va", "aspect": "9:16",
         "cast": [], "props": [], "set": "ENV-LAMP-ROOM",
         "camera": {"move": "static", "lens_mm": 24, "height": "eye level",
                    "start_framing": "wide", "end_framing": "wide"},
         "light": {"key": "dusk", "mood": "cold blue", "rim": "none"},
         "start_state": "the lamp room, the lamp unlit",
         "end_state": "the lamp room lit from within",
         "keyframes": {"start": "keyframes/SHOT-02-FRAME-A.png", "end": "keyframes/SHOT-02-FRAME-B.png"}},
    ]
    return shots, bible


def _write_pack(pack_dir, shots, bible):
    pack_dir.mkdir(parents=True)
    (pack_dir / "shots.json").write_text(json.dumps(shots, ensure_ascii=False), encoding="utf-8")
    (pack_dir / "bible.json").write_text(json.dumps(bible, ensure_ascii=False), encoding="utf-8")
    return pack_dir


def _cli(pack, flow, out, *extra):
    return p2s.main(["--pack", str(pack), "--adhyay", "3", "--out-dir", str(out), *extra], flow_dir=flow)


# (a) the real Kaliya pack

def test_real_pack_is_refused_while_its_bible_lacks_its_cast(tmp_path):
    shots, bible = _real_pack()
    with pytest.raises(p2s.PackError) as err:
        p2s.convert(shots, bible, 1, REAL_SLUG)
    for cid in DEVA_IDS:
        assert cid in str(err.value)
    flow = tmp_path / "flow"
    out = flow / "generated" / REAL_SLUG
    assert _cli(REAL_PACK, flow, out) == 2
    assert not out.exists()


def test_real_pack_converts_and_build_jobs_runs_with_consistent_chips(tmp_path):
    shots, bible = _real_pack_with_deva_fixtures()
    spec, series = p2s.convert(shots, bible, 1, REAL_SLUG)
    assert len(spec["shots"]) == 2 * len(shots)  # every shot has a start and an end keyframe
    assert [s["shot_id"] for s in spec["shots"][:2]] == ["SHOT-01A", "SHOT-01B"]
    assert set(series["characters"]) == {c["id"] for s in shots for c in s["cast"]}

    jobs = bj.build_jobs(spec, series, 1)
    assert len(jobs) == len(spec["shots"])
    by_id = {j["shot_id"]: j for j in jobs}
    for s in spec["shots"]:
        job = by_id[s["shot_id"]]
        assert job["flow_title"] == f"{s['shot_id']}__v01"
        assert job["characters"] == s["characters"]
        assert job["people_count"] == len(s["characters"])
        expected = (s["characters"] + [series["places"][s["place"]]["chip"]]
                    + [series["props"][p]["chip"] for p in s["props"] if series["props"][p]["accepted"]]
                    + [series["style"]["chip"]])
        assert job["chips"] == expected
        assert all(series["characters"][c]["sheet"] in job["unaccepted_sheets"] for c in s["characters"])
        assert s["action"] in job["prompt"] and s["light"] in job["prompt"]
        assert job["method"] == "generate" and job["status"] == "TODO"
    assert by_id["SHOT-01A"]["people_count"] == 1
    assert any("END frames (B)" in w for w in spec["warnings"])
    assert any("PROP-KALI-KAMLI" in w for w in spec["warnings"])


# (b) a different story

def test_other_story_converts_and_builds_jobs_without_kaliya_terms(tmp_path):
    shots, bible = _lighthouse_pack()
    spec, series = p2s.convert(shots, bible, 3, "lighthouse_tale")
    assert [s["shot_id"] for s in spec["shots"]] == ["SHOT-01A", "SHOT-01B", "SHOT-02A", "SHOT-02B"]
    jobs = bj.build_jobs(spec, series, 3)
    by_id = {j["shot_id"]: j for j in jobs}
    assert by_id["SHOT-01A"]["chips"] == ["CHAR-MIRA", "ENV_LIGHTHOUSE_STAIR__v01", "STYLE_CHIP_SHEET__v01"]
    assert by_id["SHOT-01A"]["people_count"] == 1
    assert by_id["SHOT-02B"]["chips"] == ["ENV_LAMP_ROOM__v01", "STYLE_CHIP_SHEET__v01"]
    assert by_id["SHOT-02B"]["people_count"] == 0
    assert "No people in the picture." in by_id["SHOT-02B"]["prompt"]
    assert by_id["SHOT-01A"]["flow_title"] == "SHOT-01A__v01"
    text = json.dumps([spec, series, jobs], ensure_ascii=False).lower()
    for term in ("kaliya", "krishna", "balarama", "dhenuka", "yamuna", "kadamba"):
        assert term not in text


def test_cli_writes_both_files_inside_flow_and_build_jobs_reads_them(tmp_path):
    shots, bible = _lighthouse_pack()
    pack = _write_pack(tmp_path / "stories" / "lighthouse_tale" / "pack_v1", shots, bible)
    flow = tmp_path / "flow"
    out = flow / "generated" / "lighthouse_tale"
    assert _cli(pack, flow, out) == 0
    spec_path = out / "lighthouse_tale_image_spec.json"
    series_path = out / "lighthouse_tale_flow_series.json"
    assert spec_path.is_file() and series_path.is_file()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    series = json.loads(series_path.read_text(encoding="utf-8"))
    assert len(bj.build_jobs(spec, series, 3)) == 4
    assert _cli(pack, flow, out) == 2  # refuses to overwrite without --overwrite
    assert _cli(pack, flow, out, "--overwrite") == 0


# (c) refusals

@pytest.mark.parametrize("bad", ["SHOT 01", "../SHOT", "-SHOT", "", "SHOT\n01", "x" * 65])
def test_unsafe_shot_ids_are_refused(bad):
    shots, bible = _lighthouse_pack()
    shots[0]["id"] = bad
    with pytest.raises(p2s.PackError, match="unsafe shot id"):
        p2s.convert(shots, bible, 3, "lighthouse_tale")


def test_shot_id_at_the_limit_is_accepted_but_its_suffixed_id_is_not():
    shots, bible = _lighthouse_pack()
    shots[0]["id"] = "x" * 63  # + "A" = 64 characters: allowed
    spec, _ = p2s.convert(shots, bible, 3, "lighthouse_tale")
    assert spec["shots"][0]["shot_id"] == "x" * 63 + "A"
    shots[0]["id"] = "x" * 64  # + "A" = 65 characters: refused
    with pytest.raises(p2s.PackError, match="unsafe shot id"):
        p2s.convert(shots, bible, 3, "lighthouse_tale")


@pytest.mark.parametrize("slug", ["../evil", "bad slug", "", "a/b"])
def test_unsafe_slug_is_refused(slug):
    shots, bible = _lighthouse_pack()
    with pytest.raises(p2s.PackError, match="unsafe slug id"):
        p2s.convert(shots, bible, 3, slug)


def test_unsafe_cast_id_is_refused():
    shots, bible = _lighthouse_pack()
    shots[0]["cast"][0]["id"] = "CHAR MIRA"
    with pytest.raises(p2s.PackError, match="unsafe cast id"):
        p2s.convert(shots, bible, 3, "lighthouse_tale")


def test_cast_id_missing_from_bible_is_refused_and_named():
    shots, bible = _lighthouse_pack()
    shots[0]["cast"][0]["id"] = "CHAR-GHOST"
    with pytest.raises(p2s.PackError) as err:
        p2s.convert(shots, bible, 3, "lighthouse_tale")
    assert "CHAR-GHOST" in str(err.value)


def test_set_id_missing_from_bible_is_refused_and_named(tmp_path):
    shots, bible = _lighthouse_pack()
    shots[1]["set"] = "ENV-NOWHERE"
    with pytest.raises(p2s.PackError) as err:
        p2s.convert(shots, bible, 3, "lighthouse_tale")
    assert "ENV-NOWHERE" in str(err.value)
    pack = _write_pack(tmp_path / "stories" / "lighthouse_tale" / "pack_v1", shots, bible)
    flow = tmp_path / "flow"
    assert _cli(pack, flow, flow / "generated" / "lighthouse_tale") == 2


def test_out_dir_outside_flow_is_refused(tmp_path):
    shots, bible = _lighthouse_pack()
    pack = _write_pack(tmp_path / "stories" / "lighthouse_tale" / "pack_v1", shots, bible)
    flow = tmp_path / "flow"
    outside = tmp_path / "elsewhere"
    assert _cli(pack, flow, outside) == 2
    assert _cli(pack, flow, flow / ".." / "elsewhere") == 2
    assert _cli(pack, flow, flow) == 2  # flow/ itself is not a generated folder
    assert not outside.exists()


def test_unsafe_slug_from_pack_folder_is_refused_by_cli(tmp_path):
    shots, bible = _lighthouse_pack()
    pack = _write_pack(tmp_path / "stories" / "bad slug" / "pack_v1", shots, bible)
    flow = tmp_path / "flow"
    assert _cli(pack, flow, flow / "generated" / "x") == 2
    assert not (flow / "generated").exists()


# (d) forbidden words

def test_forbidden_word_in_action_raises_naming_the_shot():
    shots, bible = _lighthouse_pack()
    spec, series = p2s.convert(shots, bible, 3, "lighthouse_tale")
    spec["shots"][0]["action"] += " Mira is naked on the stair."
    with pytest.raises(ValueError) as err:
        bj.build_jobs(spec, series, 3)
    assert "SHOT-01A" in str(err.value) and "forbidden word" in str(err.value)


def test_kaliya_series_forbidden_words_are_enforced():
    # flow_series_kaliya.json names its list "forbidden_words"; build_jobs used to read only "forbidden".
    spec = json.loads((FLOW_DIR / "A_KM_image_spec_keyframesA.json").read_text(encoding="utf-8"))
    series = json.loads((FLOW_DIR / "flow_series_kaliya.json").read_text(encoding="utf-8"))
    spec["shots"][0]["action"] += " Krishna stands with bare shoulders on the branch."
    with pytest.raises(ValueError) as err:
        bj.build_jobs(spec, series, 1)
    assert "LEAP-01A" in str(err.value)


def test_bible_forbidden_words_are_copied_into_the_series():
    shots, bible = _lighthouse_pack()
    bible["forbidden_words"] = ["lantern-king"]
    _, series = p2s.convert(shots, bible, 3, "lighthouse_tale")
    assert series["forbidden_words"] == p2s.DEFAULT_FORBIDDEN_WORDS + ["lantern-king"]


# build_jobs prop chips

def test_build_jobs_prop_chips_follow_place_and_skip_unaccepted_props():
    shots, bible = _lighthouse_pack()
    spec, series = p2s.convert(shots, bible, 3, "lighthouse_tale")
    assert spec["shots"][0]["shot_id"] == "SHOT-01A"
    series["props"]["PROP-LAMP"].update(chip="PROP_LAMP__v01", accepted=True)
    assert bj.build_jobs(spec, series, 3)[0]["chips"] == [
        "CHAR-MIRA", "ENV_LIGHTHOUSE_STAIR__v01", "PROP_LAMP__v01", "STYLE_CHIP_SHEET__v01"]
    series["props"]["PROP-LAMP"]["accepted"] = False
    assert bj.build_jobs(spec, series, 3)[0]["chips"] == [
        "CHAR-MIRA", "ENV_LIGHTHOUSE_STAIR__v01", "STYLE_CHIP_SHEET__v01"]
    bad = copy.deepcopy(spec)
    bad["shots"][0]["props"].append("PROP-GHOST")
    with pytest.raises(ValueError, match="PROP-GHOST"):
        bj.build_jobs(bad, series, 3)


def test_bible_sections_as_lists_are_accepted():
    """Opus-written packs store characters/environments/props as [{id, ...}] lists; the converter must treat them like {id: entry}."""
    import json, pathlib
    pack = pathlib.Path(__file__).resolve().parents[2] / "stories" / "mahadev_katha_indresh" / "pack_opus_medium_v1"
    if not (pack / "shots.json").is_file():
        return
    shots = json.loads((pack / "shots.json").read_text(encoding="utf-8"))
    bible = json.loads((pack / "bible.json").read_text(encoding="utf-8"))
    spec, series = p2s.convert(shots, bible, 1, "mahadev_katha_indresh")
    assert spec["shots"]


def test_v4_bible_fields_reach_the_texts():
    import pack_to_spec as p
    bible = {"style_lock": {"prefix": "2D hand-drawn cel anime, flat colour."}}
    assert p._style_text(bible) == "2D hand-drawn cel anime, flat colour."
    sentence = p._character_sentence("CHAR-SATI", {"description": "Daksha's daughter. Adult, 7 heads tall. A third sentence that is long."}, "Sati")
    assert "Daksha's daughter" in sentence and "attached CHAR-SATI" in sentence
    place = p._place_text("Void", {"description": "A vast indigo void with a crescent moon.", "lighting_baseline": {"key": "soft gold at the horizon"}})
    assert "indigo void" in place and "soft gold at the horizon" in place
