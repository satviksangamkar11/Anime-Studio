import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import precommit_check


class _FakeResult:
    def __init__(self, stdout: str) -> None:
        self.returncode = 0
        self.stdout = stdout


def test_staged_names_split_on_nul(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[str] = []

    def fake_check_staged(path: str) -> list[str]:
        recorded.append(path)
        return []

    monkeypatch.setattr(precommit_check, "check_staged", fake_check_staged)

    def fake_run(cmd: list[str], **kwargs: object) -> _FakeResult:
        return _FakeResult("a.py" + chr(0) + "dir/b c.py" + chr(0))

    monkeypatch.setattr(precommit_check.subprocess, "run", fake_run)

    assert precommit_check.main() == 0
    assert recorded == ["a.py", "dir/b c.py"]


def test_command_has_z_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded_argv: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> _FakeResult:
        recorded_argv.append(list(cmd))
        return _FakeResult("")

    monkeypatch.setattr(precommit_check.subprocess, "run", fake_run)

    assert precommit_check.main() == 0
    assert any("-z" in argv for argv in recorded_argv)


def test_non_ascii_path_kept_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[str] = []

    def fake_check_staged(path: str) -> list[str]:
        recorded.append(path)
        return []

    monkeypatch.setattr(precommit_check, "check_staged", fake_check_staged)

    name = "caf\xe9.py"
    stdout = name + chr(0)

    def fake_run(cmd: list[str], **kwargs: object) -> _FakeResult:
        return _FakeResult(stdout)

    monkeypatch.setattr(precommit_check.subprocess, "run", fake_run)

    assert precommit_check.main() == 0
    assert recorded == [name]
