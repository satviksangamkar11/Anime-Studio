import json
import os
import re

import pytest

import h3.render_controller as rc
from h3.tests.synth import SHOT_IDS

NO_BACKEND = "no GPU backend configured (ComfyUI endpoint or Colab/Wan2GP runner not wired); nothing was started"
EXEC_FILES = ("prompt.txt", "workflow.json", "assemble.cmd", "filter.txt")
H3_DIR = os.path.dirname(os.path.abspath(rc.__file__))


def _write(tmp_path, story, name="story.json"):
    p = tmp_path / name
    p.write_text(json.dumps(story), encoding="utf-8")
    return str(p)


def _run(argv, capsys):
    code = rc.main(argv)
    return code, capsys.readouterr().out


def _argv(story_path, out, *extra, scope=("all",)):
    return ["--story-file", story_path, "--scope", *scope, "--out-dir", out, *extra]


def _readiness(out, ep="SYN_EP1"):
    with open(os.path.join(out, ep, "readiness.json"), encoding="utf-8") as f:
        return json.load(f)


def _executables(out):
    found = []
    for root, _, files in os.walk(out):
        found += [f for f in files if f in EXEC_FILES]
    return found


# ---------- scope ----------

def test_parse_scope_accepts_both_shot_forms_and_rejects_bad_ones():
    assert rc.parse_scope(["shots", "A,B"]) == ("shots", ["A", "B"], None)
    assert rc.parse_scope(["shots"], ["C, D"]) == ("shots", ["C", "D"], None)
    assert rc.parse_scope(["reel", "EP_01"]) == ("reel", [], "EP_01")
    assert rc.parse_scope(["reel"], (), "EP_02") == ("reel", [], "EP_02")
    assert rc.parse_scope(["all"]) == ("all", [], None)
    for bad in (["bogus"], ["all", "x"], ["reel", "a", "b"]):
        with pytest.raises(rc.ScopeError):
            rc.parse_scope(bad)


def test_select_scope_shots_keeps_story_order(story):
    groups = rc.select_scope(story, "shots", ["SYN_C", "SYN_A", "SYN_C"])
    assert [g["episode"]["episode_id"] for g in groups] == ["SYN_EP1"]
    assert [s["shot_id"] for s in groups[0]["shots"]] == ["SYN_A", "SYN_C"]


def test_select_scope_unknown_shot_or_episode_is_an_error(story):
    with pytest.raises(rc.ScopeError, match="unknown shot id"):
        rc.select_scope(story, "shots", ["SYN_Z"])
    with pytest.raises(rc.ScopeError, match="unknown episode"):
        rc.select_scope(story, "reel", episode_id="EP_NOPE")
    with pytest.raises(rc.ScopeError, match="needs shot ids"):
        rc.select_scope(story, "shots", [])


def test_select_scope_reel_and_all(story):
    reel = rc.select_scope(story, "reel", episode_id="SYN_EP1")
    assert [s["shot_id"] for s in reel[0]["shots"]] == list(SHOT_IDS)
    allg = rc.select_scope(story, "all")
    assert len(allg) == 1 and len(allg[0]["shots"]) == 3


# ---------- prepare-only ----------

def test_prepare_only_writes_files_and_readiness_json(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out), capsys)
    assert code == 0
    ep = os.path.join(out, "SYN_EP1")
    for sid in SHOT_IDS:
        assert os.path.isfile(os.path.join(ep, sid, "prompt.txt"))
        assert os.path.isfile(os.path.join(ep, sid, "workflow.json"))
    assert os.path.isfile(os.path.join(ep, "filter.txt")) and os.path.isfile(os.path.join(ep, "assemble.cmd"))
    doc = _readiness(out)
    assert doc["totals"]["ready"] == 3 and doc["totals"]["shots"] == 3 and doc["blocked"] is False
    assert doc["unverified_node_classes"] is True
    assert text.count(" YES") == 3 and "TOTAL shots=3 ready=3/3" in text and "RUN CLEAN" in text


def test_unverified_node_note_is_printed_once(story, tmp_path, capsys):
    path = _write(tmp_path, story)
    _, text = _run(_argv(path, str(tmp_path / "out")), capsys)
    assert text.count("UNVERIFIED") == 1


def test_shots_scope_writes_only_selected_and_their_assembly(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, _ = _run(_argv(path, out, "--ids", "SYN_B,SYN_C", scope=("shots",)), capsys)
    assert code == 0
    ep = os.path.join(out, "SYN_EP1")
    assert not os.path.exists(os.path.join(ep, "SYN_A"))
    assert os.path.isfile(os.path.join(ep, "SYN_B", "workflow.json"))
    with open(os.path.join(ep, "assemble.cmd"), encoding="utf-8") as f:
        assert f.read().count("-i ") == 2


def test_unknown_shot_id_exits_1_and_writes_nothing(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, "--ids", "SYN_Z", scope=("shots",)), capsys)
    assert code == 1 and "unknown shot id(s): SYN_Z" in text
    assert not os.path.exists(out)


def test_unknown_episode_exits_1(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, scope=("reel", "EP_NOPE")), capsys)
    assert code == 1 and "unknown episode" in text


# ---------- lint gate ----------

def test_linter_failure_exits_1_and_writes_nothing_executable(story, tmp_path, capsys):
    story["episodes"][0]["shots"][0]["timing_and_lattice"]["pixel_frames"] = 176
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out), capsys)
    assert code == 1
    assert "SYN_A: PF-02" in text and "nothing executable was written" in text
    assert _executables(out) == []
    doc = _readiness(out)
    assert doc["blocked"] is True
    assert [r["ready"] for r in doc["rows"]] == [False, True, True]


def test_allow_partial_writes_passing_shots_but_no_assembly(story, tmp_path, capsys):
    story["episodes"][0]["shots"][0]["timing_and_lattice"]["pixel_frames"] = 176
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, "--allow-partial"), capsys)
    assert code == 1
    ep = os.path.join(out, "SYN_EP1")
    assert not os.path.exists(os.path.join(ep, "SYN_A", "workflow.json"))
    assert os.path.isfile(os.path.join(ep, "SYN_B", "workflow.json"))
    assert os.path.isfile(os.path.join(ep, "SYN_C", "prompt.txt"))
    assert not os.path.exists(os.path.join(ep, "assemble.cmd"))
    assert "--allow-partial wrote 2 ready shot(s)" in text


def test_stale_executables_are_removed_when_a_later_run_is_blocked(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    assert _run(_argv(path, out), capsys)[0] == 0
    assert os.path.isfile(os.path.join(out, "SYN_EP1", "SYN_A", "workflow.json"))
    story["episodes"][0]["shots"][0]["timing_and_lattice"]["pixel_frames"] = 176
    _write(tmp_path, story)
    code, text = _run(_argv(path, out), capsys)
    assert code == 1 and "removed stale executable" in text
    assert _executables(out) == []


def test_second_pass_without_upscale_resolution_is_blocked(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, "--second-pass"), capsys)
    assert code == 1 and "CLI-02" in text and _executables(out) == []


def test_profile_override_with_other_resolution_is_blocked(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    prof = os.path.join(H3_DIR, "profiles", "sing8_768x1344.json")
    code, text = _run(_argv(path, out, "--profile", prof), capsys)
    assert code == 1 and "KF-04" in text and _executables(out) == []


# ---------- dry-run and picture status ----------

def test_dry_run_writes_nothing(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, "--dry-run"), capsys)
    assert code == 0 and not os.path.exists(out)
    assert "SYN_A" in text and "DRY RUN" in text


def test_picture_1_reused_from_upstream_when_own_file_absent(story, tmp_path, capsys):
    kf = story["episodes"][0]["shots"][1]["fl2va_keyframes"]
    kf["picture_1_path"], kf["reuse_upstream_b_id"] = "missing_own.png", "SYN_A"
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out), capsys)
    assert code == 0 and "KF-W1" in text
    row = next(r for r in _readiness(out)["rows"] if r["shot_id"] == "SYN_B")
    assert row["picture_1"]["status"] == "REUSED" and row["ready"] is True


def test_missing_picture_is_reported_and_blocks(story, tmp_path, capsys):
    os.remove(os.path.join(story["episodes"][0]["asset_root"], "syn_b_end.png"))
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out), capsys)
    assert code == 1 and "KF-02" in text
    row = next(r for r in _readiness(out)["rows"] if r["shot_id"] == "SYN_B")
    assert row["picture_2"]["status"] == "MISSING" and row["ready"] is False


# ---------- execute gates and backend hook ----------

@pytest.mark.parametrize("extra", [["--mode", "execute"], ["--execute-render"]])
def test_execute_refused_without_both_flags(story, tmp_path, capsys, extra):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, *extra), capsys)
    assert code == 2 and "BOTH --mode execute AND --execute-render" in text
    assert not os.path.exists(out)


def test_execute_with_both_flags_reaches_the_none_backend(story, tmp_path, capsys):
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, "--mode", "execute", "--execute-render"), capsys)
    assert code == 3 and NO_BACKEND in text


def test_registered_backend_receives_request_and_its_code_is_returned(story, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(rc, "BACKENDS", dict(rc.BACKENDS))
    seen = []

    def fake(request):
        seen.append(request)
        return 0

    rc.register_backend("fake", fake)
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, "--mode", "execute", "--execute-render", "--backend", "fake"), capsys)
    assert code == 0 and len(seen) == 1 and NO_BACKEND not in text
    ep = seen[0]["episodes"][0]
    assert ep["episode_id"] == "SYN_EP1" and [s["shot_id"] for s in ep["shots"]] == list(SHOT_IDS)
    assert all(os.path.isfile(s["workflow"]) for s in ep["shots"])


def test_backend_not_called_when_gates_fail(story, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(rc, "BACKENDS", dict(rc.BACKENDS))
    called = []
    rc.register_backend("fake", lambda request: called.append(request))
    story["episodes"][0]["shots"][0]["timing_and_lattice"]["pixel_frames"] = 176
    path, out = _write(tmp_path, story), str(tmp_path / "out")
    code, text = _run(_argv(path, out, "--mode", "execute", "--execute-render", "--backend", "fake"), capsys)
    assert code == 1 and called == [] and "execute not started" in text


def test_none_backend_prints_message_and_returns_3(capsys):
    assert rc.run_backend("none", {"episodes": []}) == 3
    assert capsys.readouterr().out.strip() == NO_BACKEND


def test_controller_source_imports_no_network_or_ffmpeg_or_colab():
    with open(rc.__file__, encoding="utf-8") as f:
        src = f.read()
    assert not re.search(r"^\s*(import|from)\s+(requests|subprocess|colab|urllib|http)\b", src, re.M)
    assert "subprocess" not in src and "os.system" not in src
