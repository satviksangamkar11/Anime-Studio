"""auto_log.py (PostToolUse hook): edits and commit/test/push/download commands are logged, everything else is not;
secrets are redacted; bad input is silent."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "auto_log.py"


def run(tmp_path, payload, raw=None):
    log = tmp_path / "log.md"
    log.write_text("# log\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT)], input=raw if raw is not None else json.dumps(payload), text=True,
                       env={**os.environ, "AUTO_LOG_FILE": str(log)}, capture_output=True)
    assert p.returncode == 0 and p.stderr == ""
    return log.read_text(encoding="utf-8").splitlines()[1:]


def test_edit_is_logged_with_relative_path(tmp_path):
    out = run(tmp_path, {"tool_name": "Edit", "tool_input": {"file_path": "D:\\aai work\\anime_studio\\h3\\router.py"}})
    assert len(out) == 1 and out[0].endswith("| auto | EDIT | anime_studio/h3/router.py | hook")


def test_commit_push_and_pytest_are_logged(tmp_path):
    for cmd in ("git commit -m x", "git push origin main", "cd h3 && python -m pytest -q"):
        assert len(run(tmp_path, {"tool_name": "Bash", "tool_input": {"command": cmd}})) == 1


def test_read_only_commands_and_other_tools_are_not_logged(tmp_path):
    assert run(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}) == []
    assert run(tmp_path, {"tool_name": "Read", "tool_input": {"file_path": "a.py"}}) == []
    assert run(tmp_path, {"tool_name": "Write", "tool_input": {"file_path": "C:/x/Temp/claude/a/scratchpad/s.py"}}) == []


def test_secrets_are_redacted(tmp_path):
    out = run(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "curl -H 'Authorization: Bearer abc123def456' --key=sk-abcdef1234567890 http://x"}})
    assert "abc123def456" not in out[0] and "sk-abcdef1234567890" not in out[0] and "<redacted>" in out[0]


def test_bad_input_is_silent(tmp_path):
    assert run(tmp_path, None, raw="not json") == []
    assert run(tmp_path, None, raw="") == []


def test_same_step_twice_in_a_row_is_one_line(tmp_path):
    log = tmp_path / "log.md"
    log.write_text("# log\n", encoding="utf-8")
    env = {**os.environ, "AUTO_LOG_FILE": str(log)}
    for _ in range(2):
        subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "a/b.py"}}),
                       text=True, env=env, check=True)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2
