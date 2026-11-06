"""dots_coder: fake model and fake tester, tmp dirs, no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dots_coder as dc  # noqa: E402

NL = "\n"
ANSWER = NL.join(["thinking...", "FINAL:", "```file ui/a.py", "x = 1", "```", "```file ui/evil.py", "y = 2", "```", "```file ../outside.py", "z = 3", "```", ""])


def block(name, body):
    return NL.join(["FINAL:", "```file " + name, body, "```", ""])


def test_parse_takes_last_final_section():
    text = NL.join(["```file a.py", "old", "```", "FINAL:", "```file b.py", "new", "```"])
    assert dc.parse_files(text) == {"b.py": "new" + NL}


def test_only_allowed_paths_are_written(tmp_path):
    res = dc.code("t", [], ["ui/a.py"], "x", tmp_path, rounds=1, caller=lambda p: ANSWER, tester=lambda c, r: (True, ""))
    assert res["ok"] and res["log"][0]["written"] == ["ui/a.py"] and set(res["log"][0]["refused"]) == {"ui/evil.py", "../outside.py"}
    assert (tmp_path / "ui" / "a.py").read_text() == "x = 1" + NL
    assert not (tmp_path / "ui" / "evil.py").exists() and not (tmp_path.parent / "outside.py").exists()


def test_failure_is_sent_back_and_second_round_passes(tmp_path):
    prompts, results = [], iter([(False, "AssertionError boom"), (True, "")])
    res = dc.code("task", [], ["ui/a.py"], "x", tmp_path, rounds=3, caller=lambda p: prompts.append(p) or ANSWER, tester=lambda c, r: next(results))
    assert res["ok"] and res["rounds"] == 2 and "AssertionError boom" in prompts[1] and "YOUR CURRENT VERSION OF ui/a.py" in prompts[1]


def test_no_usable_answer_gives_up(tmp_path):
    res = dc.code("t", [], ["ui/a.py"], "x", tmp_path, rounds=2, caller=lambda p: "no files here", tester=lambda c, r: (True, ""))
    assert not res["ok"] and all(not e["written"] for e in res["log"])


def test_missing_allowed_file_is_not_success_and_is_asked_again(tmp_path):
    answers = iter([block("ui/a.py", "x = 1"), block("ui/b.py", "y = 2")])
    prompts = []
    res = dc.code("t", [], ["ui/a.py", "ui/b.py"], "x", tmp_path, rounds=3, caller=lambda p: prompts.append(p) or next(answers), tester=lambda c, r: (True, ""))
    assert res["ok"] and res["rounds"] == 2 and "missing: ui/b.py" in res["log"][0]["tests"]
    assert (tmp_path / "ui" / "a.py").is_file() and (tmp_path / "ui" / "b.py").is_file()
    assert "did not contain these complete files: ui/b.py" in prompts[1]


def test_per_file_mode_makes_one_call_per_file(tmp_path):
    calls = []

    def caller(p):
        calls.append(p)
        return block("ui/a.py" if "complete file ui/a.py" in p else "ui/b.py", "z = 1")

    res = dc.code("t", [], ["ui/a.py", "ui/b.py"], "x", tmp_path, rounds=1, caller=caller, tester=lambda c, r: (True, ""), per_file=True)
    assert res["ok"] and len(calls) == 2
