"""Tests for score/ableton_build.py (checklist section D, triage ABR-01..11). Pure: no Ableton, no serum-mcp."""
import ast
import json
import math
import random
import sys
from pathlib import Path

import pytest

from score import ableton_build as ab

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path("D:/ableton claude final best/serum2/ableton/ableton_mcp_extended/server.py")
CUE = ROOT / "score" / "tests" / "fixtures" / "cue_sheet_reel1_v3.json"  # frozen v3 (70.0 s) test data
BIBLE = ROOT / "stories/kalika_puran_bhag1/music_bible.json"
JSON_TOOLS = {"get_session_info", "create_serum_track"}


def _server_text():
    if not SERVER.is_file():
        pytest.skip("owner server.py not found at %s" % SERVER)
    return SERVER.read_text(encoding="utf-8")


def _server_signatures():
    """{tool: (required_args, {arg: annotation_name})} from @mcp.tool functions in server.py (ast)."""
    tree = ast.parse(_server_text())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if not any(isinstance(d, (ast.Call, ast.Attribute)) and "tool" in ast.dump(d) for d in node.decorator_list):
                continue
            args = [a for a in node.args.args if a.arg != "ctx"]
            n_default = len(node.args.defaults)
            required = {a.arg for a in args[:len(args) - n_default]}
            types = {a.arg: (ast.unparse(a.annotation) if a.annotation else "") for a in args}
            out[node.name] = (required, types)
    return out


def _type_ok(value, annotation):
    if annotation == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if annotation == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if annotation == "str":
        return isinstance(value, str)
    if annotation == "bool":
        return isinstance(value, bool)
    return True  # List / Dict / Optional annotations: not type-checked here


@pytest.fixture(scope="module")
def cue():
    return json.loads(CUE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bible():
    return json.loads(BIBLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def roles(bible):
    return [r for r in bible["presets"] if not r.startswith("_")]


@pytest.fixture(scope="module")
def plan(cue, roles):
    sections = [{"start_s": a["start_s"], "end_s": a["end_s"], "act": a["act"], "bpm": 60,
                 "feel": "normal", "genre": "ambient", "intensity": [0.4, 0.6],
                 "roles_on": roles, "why": "fixture"} for a in cue["acts"]]
    return {"schema_version": 1, "episode": 1, "sections": sections}


@pytest.fixture(scope="module")
def notes(cue, roles):
    """C1-shaped notes from the real shot list: one note per shot start per Serum role, one marker per shot."""
    shots = cue["shots"]
    tracks = {r: [{"t_s": s["start_s"] + 0.5, "dur_s": 1.0, "pitch": 50 + i % 12, "vel": 90} for s in shots]
              for i, r in enumerate(roles)}
    markers = [{"t_s": s["start_s"], "name": "%s %s" % (s["id"], s["hook_type"])} for s in shots]
    automation = [{"role": "pad", "macro": 1, "points": [[0.0, 0.2], [18.0, 0.8]]},
                  {"role": "drone", "macro": "volume", "points": [[0.0, 0.5], [70.0, 0.5]]}]
    return {"tracks": tracks, "markers": markers, "automation": automation}


@pytest.fixture(scope="module")
def recipe(notes, plan, bible):
    return ab.build_recipe(notes, plan, bible)


def _tools(recipe):
    return [s for s in recipe if "tool" in s]


def _role_index(recipe):
    """role -> 1-based track index, from create_serum_track order (what the replayer must produce)."""
    idx, n = {}, 0
    for s in recipe:
        if s.get("tool") == "create_serum_track":
            n += 1
            idx[s["args"]["name"]] = n
    return idx


def _marker_index(recipe):
    return len(_role_index(recipe)) + 1


# ---- D1 / ABR-11: tools and arguments against the real server signatures -------------------------

def test_every_tool_exists_in_server_py(recipe):
    text = _server_text()
    for s in _tools(recipe):
        assert "def %s(" % s["tool"] in text, s["tool"]


def test_required_args_and_types_match_server_signatures(recipe):
    sigs = _server_signatures()
    for s in _tools(recipe):
        assert s["tool"] in sigs, s["tool"]
        required, types = sigs[s["tool"]]
        missing = required - set(s["args"])
        assert not missing, (s["tool"], "missing required", missing)
        extra = set(s["args"]) - set(types)
        assert not extra, (s["tool"], "unknown args", extra)
        for k, v in s["args"].items():
            assert _type_ok(v, types[k]), (s["tool"], k, v, types[k])


def test_server_guards_create_serum_track_preset_path():
    assert "PRESET_FILE_INVALID" in _server_text()


# ---- ABR-05: every tool step carries an expect field of the right kind ---------------------------

def test_every_tool_step_has_expect_of_the_right_kind(recipe):
    for s in _tools(recipe):
        exp = s.get("expect")
        assert isinstance(exp, dict), s["tool"]
        if s["tool"] in JSON_TOOLS:
            assert exp.get("json_status_not") == "FAILED", s["tool"]
        else:
            assert exp.get("not_startswith") == "Error", s["tool"]


# ---- D2 order, ABR-04 integer indices, ABR-06 preset gate ----------------------------------------

def test_order_session_then_tempo_60_and_track_count_zero(recipe):
    assert recipe[0]["tool"] == "get_session_info" and recipe[0]["expect"]["track_count"] == 0
    assert recipe[1] == {"tool": "set_tempo", "args": {"tempo": 60.0}, "expect": {"not_startswith": "Error"}}
    assert [s["tool"] for s in _tools(recipe)].count("set_tempo") == 1


def test_order_tracks_then_clips_then_automation(recipe):
    names = [s.get("tool") for s in recipe]
    last_track = max(i for i, t in enumerate(names) if t in ("create_serum_track", "create_midi_track"))
    first_clip = min(i for i, t in enumerate(names) if t in ("create_clip", "create_arrangement_midi_clip"))
    first_auto = min(i for i, t in enumerate(names) if t == "manage_clip_automation")
    assert last_track < first_clip < first_auto


def test_track_indices_are_integers_in_creation_order(recipe, roles):
    idx = _role_index(recipe)
    assert list(idx) == roles and list(idx.values()) == list(range(1, len(roles) + 1))
    for s in _tools(recipe):
        for k in ("track_index",):
            if k in s["args"]:
                assert isinstance(s["args"][k], int), s["tool"]


def test_readback_after_tracks_expects_marker_count(recipe, roles):
    readbacks = [i for i, s in enumerate(recipe) if s.get("tool") == "get_session_info"]
    assert len(readbacks) == 2
    mid = recipe[readbacks[1]]
    assert mid["expect"]["track_count"] == len(roles) + 1
    assert recipe[readbacks[1] - 1].get("tool") == "create_midi_track" or any(
        s.get("tool") == "set_track_name" for s in recipe[:readbacks[1]])


def test_serum_create_step_is_gated_by_needs_and_preceded_by_manual(recipe, bible):
    for i, s in enumerate(recipe):
        if s.get("tool") != "create_serum_track":
            continue
        role = s["args"]["name"]
        assert s["needs"] == ["preset_path:" + role]
        assert "manual" in recipe[i - 1] and bible["presets"][role] in recipe[i - 1]["manual"]


def test_no_string_track_refs_anywhere(recipe):
    for s in _tools(recipe):
        for k, v in s["args"].items():
            assert not (isinstance(v, str) and v.startswith("@role:")), (s["tool"], k)


# ---- D3 seconds, clip starts, notes --------------------------------------------------------------

def test_clip_length_and_marker_start_are_seconds(recipe, notes, cue):
    total = cue["total_s"]
    creates = [s for s in recipe if s.get("tool") == "create_clip"]
    assert creates and all(s["args"]["length"] == total for s in creates)
    markers = [s for s in recipe if s.get("tool") == "create_arrangement_midi_clip"]
    times = sorted(m["t_s"] for m in notes["markers"])
    assert len(markers) == len(times)
    for s, t, nxt in zip(markers, times, times[1:] + [total]):
        assert s["args"]["start_beat"] == pytest.approx(t)
        assert s["args"]["length_beats"] == pytest.approx(nxt - t)


def test_note_times_are_seconds(recipe, notes, roles):
    idx = _role_index(recipe)
    by_idx = {v: k for k, v in idx.items()}
    for s in recipe:
        if s.get("tool") != "add_notes_to_clip":
            continue
        role_notes = notes["tracks"][by_idx[s["args"]["track_index"]]]
        assert len(s["args"]["notes"]) == len(role_notes)
        for placed, src in zip(s["args"]["notes"], role_notes):
            assert placed["start_time"] == pytest.approx(src["t_s"])
            assert placed["duration"] == pytest.approx(src["dur_s"])
            assert placed["mute"] is False


# ---- MARKERS, ABR-01 names -----------------------------------------------------------------------

def test_markers_track_has_ten_empty_named_clips_each_with_name_step(recipe, cue):
    m = _marker_index(recipe)
    creates = [s for s in recipe if s.get("tool") == "create_arrangement_midi_clip"]
    assert len(creates) == 10 == len(cue["shots"])
    assert all(s["args"]["track_index"] == m and "notes" not in s["args"] for s in creates)
    renames = [s for s in recipe if s.get("tool") == "set_arrangement_clip_property"
               and s["args"]["track_index"] == m]
    assert len(renames) == 10
    for pos, (shot, rn) in enumerate(zip(cue["shots"], renames), start=1):
        assert rn["args"]["clip_index"] == pos
        assert rn["args"]["name"].split()[0] == shot["id"]


def test_one_cue_point_per_unique_marker_no_duplicates(recipe, cue):
    cues = [s for s in recipe if s.get("tool") == "create_cue_point"]
    assert len(cues) == len(cue["shots"])
    assert len({s["args"]["beat"] for s in cues}) == len(cues)


# ---- Macros and automation (ABR-02, ABR-03) ------------------------------------------------------

def test_macros_1_to_4_steps_for_each_serum_role(recipe, roles):
    idx = _role_index(recipe)
    for role in roles:
        names = {s["args"]["parameter_name"] for s in recipe
                 if s.get("tool") == "set_device_parameter" and s["args"]["track_index"] == idx[role]}
        assert names == {"Macro 1", "Macro 2", "Macro 3", "Macro 4"}, role


def test_automation_creates_volume_and_macros_for_every_role_clip(recipe, roles):
    idx = _role_index(recipe)
    for role in roles:
        params = [s["args"]["parameter_name"] for s in recipe
                  if s.get("tool") == "manage_clip_automation" and s["args"]["track_index"] == idx[role]]
        assert params == ["volume", "Macro 1", "Macro 2", "Macro 3", "Macro 4"], role


def test_automation_points_are_one_manual_step_per_role(recipe, roles):
    per_role = [s["manual"] for s in recipe if "manual" in s and "automation points" in s["manual"]]
    assert len(per_role) == len(roles)
    pad = [m for m in per_role if "role pad" in m][0]
    assert "[[0.0, 0.2], [18.0, 0.8]]" in pad
    assert any("verify" in s["manual"].lower() and "Macro" in s["manual"] for s in recipe if "manual" in s)


def test_no_automation_for_role_without_clip(notes, plan, bible, roles):
    n = json.loads(json.dumps(notes))
    n["tracks"].pop("pad")
    rc = ab.build_recipe(n, plan, bible)
    idx = _role_index(rc)
    assert "pad" in idx
    assert not [s for s in rc if s.get("tool") == "manage_clip_automation" and s["args"]["track_index"] == idx["pad"]]
    assert any("SKIPPED automation for role pad" in s.get("manual", "") for s in rc)


# ---- ABR-09 / ABR-10 / malformed input: returned error content ----------------------------------

def test_duplicate_marker_time_is_reported_and_not_duplicated(notes, plan, bible):
    n = json.loads(json.dumps(notes))
    n["markers"].append({"t_s": n["markers"][0]["t_s"], "name": "SHOT-X dup"})
    errs = ab.check_inputs(n, plan, bible)
    assert any("duplicate marker time 0.0" in e for e in errs), errs
    rc = ab.build_recipe(n, plan, bible)
    assert any("duplicate marker time 0.0" in s.get("manual", "") for s in rc)
    assert len([s for s in rc if s.get("tool") == "create_cue_point"]) == 10


def test_points_range_checked_against_total_and_unit_value(notes, plan, bible):
    n = json.loads(json.dumps(notes))
    n["automation"].append({"role": "pad", "macro": 2, "points": [[0.0, 1.5]]})
    n["automation"].append({"role": "pad", "macro": 3, "points": [[71.0, 0.5]]})
    errs = ab.check_inputs(n, plan, bible)
    assert any("point value 1.5 outside 0..1" in e for e in errs), errs
    assert any("point time 71.0 outside 0..total_s" in e for e in errs), errs


def test_missing_plan_total_is_reported_by_name(notes, bible):
    errs = ab.check_inputs(notes, {}, bible)
    assert any(e.startswith("plan: no section with end_s > 0") for e in errs), errs


def test_note_outside_total_reported_with_location(notes, plan, bible):
    n = json.loads(json.dumps(notes))
    n["tracks"]["drone"][0]["dur_s"] = 500.0
    errs = ab.check_inputs(n, plan, bible)
    assert any(e.startswith("notes.tracks.drone[0]: note outside") for e in errs), errs


def test_malformed_input_never_raises_and_reports(plan, bible):
    rng = random.Random(7)
    junk = [None, "x", 5, [], {"tracks": 5}, {"tracks": {"drone": "no"}}, {"markers": [{"t_s": math.nan}]}]
    for _ in range(50):
        junk.append({"tracks": {"drone": [{"t_s": rng.random() * 100, "dur_s": rng.choice([0, 1, -1]),
                                           "pitch": rng.choice([60, 200, 1.5, True]), "vel": 80}]},
                     "markers": [{"t_s": "a", "name": 3}]})
    for bad in junk:
        ab.build_recipe(bad, plan, bible)
        ab.serum_briefs(bad, bad)
        assert isinstance(ab.check_inputs(bad, bad, bad), list)
    assert any("notes.tracks: not an object" in e for e in ab.check_inputs(None, plan, bible))
    assert any("not a list" in e for e in ab.check_inputs({"tracks": {"drone": "no"}}, plan, bible))


# ---- Whole-recipe properties --------------------------------------------------------------------

def test_recipe_valid_json_under_5mb_for_real_shot_list(recipe):
    text = json.dumps(recipe)
    assert len(text.encode("utf-8")) < 5 * 1024 * 1024
    assert json.loads(text) == recipe


def test_build_is_deterministic(notes, plan, bible):
    assert ab.build_recipe(notes, plan, bible) == ab.build_recipe(notes, plan, bible)


def test_no_forbidden_writes(recipe):
    for s in _tools(recipe):
        assert not s["tool"].startswith(("save", "export", "render")), s["tool"]


def test_serum_briefs_one_text_per_role(bible, plan, roles):
    briefs = ab.serum_briefs(bible, plan)
    assert set(briefs) == set(roles)
    for role, text in briefs.items():
        assert bible["presets"][role] in text
        assert "Macro 1 brightness" in text and "Macro 4 space" in text


def test_module_is_stdlib_only():
    tree = ast.parse(Path(ab.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        mods = [a.name for a in node.names] if isinstance(node, ast.Import) else (
            [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
        for m in mods:
            assert m.split(".")[0] in sys.stdlib_module_names, m
