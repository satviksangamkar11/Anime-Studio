import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import precommit_check


def test_git_failure_returns_1_with_message(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(128, "git")

    import subprocess

    monkeypatch.setattr(precommit_check.subprocess, "run", fake_run)

    code = precommit_check.main()
    assert code == 1
    err = capsys.readouterr().err
    assert "cannot list staged files" in err


def test_git_missing_returns_1(monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("git")

    import subprocess

    monkeypatch.setattr(precommit_check.subprocess, "run", fake_run)

    code = precommit_check.main()
    assert code == 1


def test_explicit_list_still_reads_working_files(tmp_path, monkeypatch):
    secret = "sk_" + "a" * 48
    p = tmp_path / "cfg.py"
    p.write_text(f"KEY = {secret!r}\n")

    findings = precommit_check.check_files([str(p)])
    assert findings
    for finding in findings:
        assert secret not in finding
