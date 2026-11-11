"""Tests for director/script_inspect.py (spec J9c).

The hook and pacing checks are replaced by fake modules (sys.modules) in the in-process tests.
The CLI tests copy script_inspect.py into a tmp folder next to small stub script_hook.py and
script_pacing.py files written by the test, so the subprocess does not depend on the real checks.
"""
import json
import os
import shutil
import subprocess
import sys
import types

import pytest

import script_inspect

HERE = os.path.dirname(os.path.abspath(__file__))

SHOTS = [
    {"id": "s1", "seconds": 4.0, "text": "opening line"},
    {"id": "s2", "seconds": 6.0, "text": "middle line"},
]


def fake_hook_result(passed):
    # hand-set: pass -> score 90, no lists; fail -> score 40 with one hard fail
    if passed:
        return {"pass": True, "score": 90, "hard_fails": [], "reasons": [], "rewrites": []}
    return {"pass": False, "score": 40, "hard_fails": ["no ending"], "reasons": [], "rewrites": []}


def fake_pacing_result(passed):
    if passed:
        return {"pass": True, "problems": []}
    return {"pass": False, "problems": ["gap 9 s"]}


def install_fakes(monkeypatch, hook_pass=True, pacing_pass=True, record=None, hook_raises=None):
    hook_mod = types.ModuleType("script_hook")
    pacing_mod = types.ModuleType("script_pacing")

    def inspect_hook(shots, lang):
        if record is not None:
            record.append(("hook", shots, lang))
        if hook_raises is not None:
            raise hook_raises
        return fake_hook_result(hook_pass)

    def inspect_pacing(shots, lang, seconds_override=None):
        if record is not None:
            record.append(("pacing", shots, lang))
        return fake_pacing_result(pacing_pass)

    hook_mod.inspect_hook = inspect_hook
    pacing_mod.inspect_pacing = inspect_pacing
    monkeypatch.setitem(sys.modules, "script_hook", hook_mod)
    monkeypatch.setitem(sys.modules, "script_pacing", pacing_mod)


def stub_hook_text(passed):
    # a stub module file; returns a fixed dict
    score = 90 if passed else 40
    hard = "[]" if passed else '["no ending"]'
    flag = "True" if passed else "False"
    return (
        "def inspect_hook(shots, lang):\n"
        "    return {\"pass\": %s, \"score\": %d, \"hard_fails\": %s, \"reasons\": [], \"rewrites\": []}\n"
        % (flag, score, hard)
    )


def stub_pacing_text(passed):
    sig = "def inspect_pacing(shots, lang, seconds_override=None):\n"
    if passed:
        return sig + "    return {\"pass\": True, \"problems\": []}\n"
    return sig + "    return {\"pass\": False, \"problems\": [\"gap 9 s\"]}\n"


def make_run_dir(tmp_path, hook_pass, pacing_pass):
    run = tmp_path / "run"
    run.mkdir()
    shutil.copy(os.path.join(HERE, "script_inspect.py"), str(run / "script_inspect.py"))
    (run / "script_hook.py").write_text(stub_hook_text(hook_pass), encoding="utf-8")
    (run / "script_pacing.py").write_text(stub_pacing_text(pacing_pass), encoding="utf-8")
    (run / "shots.json").write_text(json.dumps(SHOTS), encoding="utf-8")
    return run


def run_cli(run, args):
    return subprocess.run(
        [sys.executable, "script_inspect.py"] + args,
        cwd=str(run),
        capture_output=True,
        text=True,
        timeout=120,
    )


# ---------- inspect_script ----------

def test_supported_langs_exact():
    assert script_inspect.SUPPORTED_LANGS == ("en", "hi", "mr")


def test_both_pass_gives_pass(monkeypatch):
    install_fakes(monkeypatch, hook_pass=True, pacing_pass=True)
    res = script_inspect.inspect_script(SHOTS, "en")
    assert res["pass"] is True
    assert res["hook"] == fake_hook_result(True)
    assert res["pacing"] == fake_pacing_result(True)
    assert set(res.keys()) == {"pass", "hook", "pacing"}


def test_hook_fail_alone_gives_fail(monkeypatch):
    install_fakes(monkeypatch, hook_pass=False, pacing_pass=True)
    res = script_inspect.inspect_script(SHOTS, "en")
    assert res["pass"] is False
    assert res["hook"]["pass"] is False
    assert res["pacing"]["pass"] is True


def test_pacing_fail_alone_gives_fail(monkeypatch):
    install_fakes(monkeypatch, hook_pass=True, pacing_pass=False)
    res = script_inspect.inspect_script(SHOTS, "en")
    assert res["pass"] is False
    assert res["hook"]["pass"] is True
    assert res["pacing"]["pass"] is False


def test_both_fail_gives_fail(monkeypatch):
    install_fakes(monkeypatch, hook_pass=False, pacing_pass=False)
    assert script_inspect.inspect_script(SHOTS, "hi")["pass"] is False


def test_shots_and_lang_passed_through(monkeypatch):
    record = []
    install_fakes(monkeypatch, record=record)
    script_inspect.inspect_script(SHOTS, "mr")
    assert ("hook", SHOTS, "mr") in record
    assert ("pacing", SHOTS, "mr") in record


def test_empty_shots_raise_value_error(monkeypatch):
    install_fakes(monkeypatch)
    with pytest.raises(ValueError):
        script_inspect.inspect_script([], "en")


def test_unsupported_lang_raises_value_error(monkeypatch):
    install_fakes(monkeypatch)
    with pytest.raises(ValueError):
        script_inspect.inspect_script(SHOTS, "fr")


def test_module_exception_propagates(monkeypatch):
    install_fakes(monkeypatch, hook_raises=RuntimeError("hook broke"))
    with pytest.raises(RuntimeError, match="hook broke"):
        script_inspect.inspect_script(SHOTS, "en")


# ---------- format_report ----------

def test_format_report_fail_exact():
    # hand-built: FAIL overall; hook score 40 FAIL with hard, reason, rewrite; pacing FAIL with one problem
    result = {
        "pass": False,
        "hook": {
            "pass": False,
            "score": 40,
            "hard_fails": ["no ending"],
            "reasons": ["too long"],
            "rewrites": ["shorten line 2"],
        },
        "pacing": {"pass": False, "problems": ["gap 9 s"]},
    }
    expected_lines = [
        "SCRIPT INSPECTION: FAIL",
        "HOOK score 40/100: FAIL",
        "  HARD: no ending",
        "  - too long",
        "  REWRITE: shorten line 2",
        "PACING: FAIL",
        "  - gap 9 s",
    ]
    assert script_inspect.format_report(result, "en") == "\n".join(expected_lines) + "\n"


def test_format_report_pass_exact():
    result = {
        "pass": True,
        "hook": {"pass": True, "score": 92, "hard_fails": [], "reasons": [], "rewrites": []},
        "pacing": {"pass": True, "problems": []},
    }
    assert script_inspect.format_report(result) == (
        "SCRIPT INSPECTION: PASS\nHOOK score 92/100: PASS\nPACING: PASS\n"
    )


def test_format_report_no_trailing_spaces_and_one_newline():
    result = {
        "pass": False,
        "hook": {"pass": False, "score": 10, "hard_fails": ["a"], "reasons": [], "rewrites": []},
        "pacing": {"pass": True, "problems": []},
    }
    text = script_inspect.format_report(result)
    assert text.endswith("\n") and not text.endswith("\n\n")
    for line in text.split("\n"):
        assert line == line.rstrip()


# ---------- main ----------

def write_shots(tmp_path, data, name="shots.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_main_list_form_pass_returns_0(monkeypatch, tmp_path, capsys):
    install_fakes(monkeypatch, hook_pass=True, pacing_pass=True)
    path = write_shots(tmp_path, SHOTS)
    assert script_inspect.main([path, "en"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "SCRIPT INSPECTION: PASS"


def test_main_fail_returns_1(monkeypatch, tmp_path, capsys):
    install_fakes(monkeypatch, hook_pass=False, pacing_pass=True)
    path = write_shots(tmp_path, SHOTS)
    assert script_inspect.main([path, "en"]) == 1
    assert capsys.readouterr().out.splitlines()[0] == "SCRIPT INSPECTION: FAIL"


def test_main_dict_form_returns_0(monkeypatch, tmp_path):
    install_fakes(monkeypatch, hook_pass=True, pacing_pass=True)
    path = write_shots(tmp_path, {"shots": SHOTS})
    assert script_inspect.main([path, "hi"]) == 0


def test_main_wrong_argument_count_returns_2(monkeypatch, tmp_path):
    install_fakes(monkeypatch)
    path = write_shots(tmp_path, SHOTS)
    assert script_inspect.main([]) == 2
    assert script_inspect.main([path]) == 2
    assert script_inspect.main([path, "en", "extra"]) == 2


def test_main_missing_file_returns_2(monkeypatch, tmp_path):
    install_fakes(monkeypatch)
    assert script_inspect.main([str(tmp_path / "nope.json"), "en"]) == 2


def test_main_bad_json_returns_2(monkeypatch, tmp_path):
    install_fakes(monkeypatch)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert script_inspect.main([str(bad), "en"]) == 2


# ---------- CLI in a subprocess (stub hook and pacing files in a tmp folder) ----------

def test_cli_subprocess_pass(tmp_path):
    run = make_run_dir(tmp_path, hook_pass=True, pacing_pass=True)
    proc = run_cli(run, ["shots.json", "en"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.splitlines()[0] == "SCRIPT INSPECTION: PASS"


def test_cli_subprocess_fail(tmp_path):
    run = make_run_dir(tmp_path, hook_pass=False, pacing_pass=True)
    proc = run_cli(run, ["shots.json", "en"])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert proc.stdout.splitlines()[0] == "SCRIPT INSPECTION: FAIL"


def test_cli_subprocess_wrong_args_returns_2(tmp_path):
    run = make_run_dir(tmp_path, hook_pass=True, pacing_pass=True)
    proc = run_cli(run, ["shots.json"])
    assert proc.returncode == 2


def test_cli_subprocess_missing_file_returns_2(tmp_path):
    run = make_run_dir(tmp_path, hook_pass=True, pacing_pass=True)
    proc = run_cli(run, ["no_such_file.json", "en"])
    assert proc.returncode == 2


# ---------- S-12: from_pack, pack passthrough, --lock, ValueError exit, repo-root run ----------

ROOT = os.path.dirname(HERE)


def pack_row(row_id, ed, directives, narration, dialogue):
    return {
        "id": row_id,
        "editorial_duration_sec": ed,
        "per_second_directives": directives,
        "audio_and_dialogue_track": {
            "narration_by_lang": {"en": narration} if narration is not None else {},
            "dialogue_by_lang": {"en": dialogue},
        },
    }


ROW_A = pack_row(
    "R2-01", 5.0,
    [{"t0": 0.0, "t1": 1.0, "action_pose_expression": "Rama turns"},
     {"t0": 1.0, "t1": 2.0, "action_pose_expression": ""},
     {"t0": 2.0, "t1": 3.0, "action_pose_expression": "Sita lifts a lamp"}],
    {"text": "narration A", "time_range": "1.6-3.0s"},
    [{"text": "dialogue B", "time_range": [0.1, 0.9]}],
)
ROW_B = pack_row(
    "R2-02", 4.0,
    [{"t0": 0.0, "t1": 1.0, "action_pose_expression": "Hanuman leaps"}],
    {"text": "narration C", "time_range": [0.5, 2.0]},
    [],
)


def test_from_pack_maps_fields():
    shots = script_inspect.from_pack([ROW_A], "en")
    assert shots == [{
        "id": "R2-01",
        "seconds": 5.0,
        "action": "Rama turns",
        "events": [{"t": 0.0}, {"t": 2.0}],
        "lines": [
            {"start_s": 0.1, "end_s": 0.9, "text": "dialogue B"},
            {"start_s": 1.6, "end_s": 3.0, "text": "narration A"},
        ],
    }]


def test_from_pack_runs_inspect():
    shots = script_inspect.from_pack([ROW_A, ROW_B], "en")
    res = script_inspect.inspect_script(shots, "en")
    assert set(res.keys()) == {"pass", "hook", "pacing"}
    assert [s["id"] for s in shots] == ["R2-01", "R2-02"]


def test_pack_line_at_0_7_fails_h2():
    row = pack_row("R2-03", 5.0, [{"t0": 0.0, "t1": 1.0, "action_pose_expression": "Rama turns"}],
                   {"text": "late line", "time_range": "0.7-2.0s"}, [])
    res = script_inspect.inspect_script(script_inspect.from_pack([row], "en"), "en")
    assert res["hook"]["pass"] is False
    assert any(text.startswith("H2") for text in res["hook"]["hard_fails"])


def test_bad_schema_exit_2_no_traceback(tmp_path):
    row = pack_row("R2-04", 5.0, [], {"text": "x", "time_range": "nonsense"}, [])
    path = tmp_path / "bad_pack.json"
    path.write_text(json.dumps([row]), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "script_inspect.py"), str(path), "en"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stdout.startswith("invalid input: row R2-04")
    assert "Traceback" not in proc.stderr


def test_runs_from_repo_root(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps([ROW_A, ROW_B]), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, os.path.join("director", "script_inspect.py"), str(path), "en"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    assert proc.stdout.startswith("SCRIPT INSPECTION:")
    assert "Traceback" not in proc.stderr


def test_lock_passes_seconds_override(monkeypatch, tmp_path):
    lock_file = tmp_path / "timeline_lock.json"
    lock_file.write_text("{}", encoding="utf-8")
    lock_mod = types.ModuleType("timeline_lock_io")
    lock_mod.load_lock = lambda path: {
        "fps": 24,
        "shots": [{"id": "s1", "edit_frames": 96}, {"id": "s2", "edit_frames": 144}],
    }
    monkeypatch.setitem(sys.modules, "timeline_lock_io", lock_mod)
    seen = {}

    def fake_inspect(shots, lang, seconds_override=None):
        seen["override"] = seconds_override
        return {"pass": True, "hook": fake_hook_result(True), "pacing": fake_pacing_result(True)}

    monkeypatch.setattr(script_inspect, "inspect_script", fake_inspect)
    path = write_shots(tmp_path, SHOTS)
    assert script_inspect.main([path, "en", "--lock", str(lock_file)]) == 0
    assert seen["override"] == {"s1": 4.0, "s2": 6.0}


def test_format_report_prints_pacing_warnings_non_blocking():
    result = {
        "pass": True,
        "hook": {"pass": True, "score": 90, "hard_fails": [], "reasons": [], "rewrites": []},
        "pacing": {"pass": True, "problems": [],
                   "warnings": ["length warning: reel is 58.0 s, must be between 60 and 75 s"]},
    }
    assert script_inspect.format_report(result) == (
        "SCRIPT INSPECTION: PASS\nHOOK score 90/100: PASS\nPACING: PASS\n"
        "  WARNING: length warning: reel is 58.0 s, must be between 60 and 75 s\n"
    )
