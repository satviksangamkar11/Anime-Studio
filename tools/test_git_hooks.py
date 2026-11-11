"""Tests for .githooks/pre-commit and .githooks/pre-push.

Each test builds a throwaway git repo in tmp_path, copies the hook files in,
and runs the real hook scripts with sh (Git for Windows). Skipped when sh or git is missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / ".githooks"
TOOLS = REPO / "tools"

GIT_ID = ["-c", "user.name=test", "-c", "user.email=test@example.com"]


def _need_sh() -> None:
    if shutil.which("sh") is None or shutil.which("git") is None:
        pytest.skip("sh or git not on PATH (needs Git for Windows)")


def _env() -> dict:
    env = os.environ.copy()
    env["ANIME_PY"] = Path(sys.executable).as_posix()
    return env


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    hooks = repo / ".githooks"
    hooks.mkdir()
    for name in ("pre-commit", "pre-push"):
        (hooks / name).write_bytes((HOOKS / name).read_bytes())
        os.chmod(hooks / name, 0o755)  # Git on Unix skips hooks that are not executable
    tools = repo / "tools"
    tools.mkdir()
    for name in ("precommit_check.py", "secret_scan.py", "secret_scan_allowlist.txt"):
        shutil.copy(TOOLS / name, tools / name)
    return repo


def _stub_secret_scan(repo: Path) -> None:
    # Writes a marker so the test can prove the pre-push hook reached the secret_scan stage.
    code = "import pathlib, sys\npathlib.Path('secret_scan_ran.txt').write_text('ran')\nsys.exit(0)\n"
    (repo / "tools" / "secret_scan.py").write_text(code, encoding="utf-8")


def _stage(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=repo, check=True, capture_output=True)


def _commit(repo: Path) -> subprocess.CompletedProcess:
    hooks = (repo / ".githooks").as_posix()
    return subprocess.run(
        ["git", "-c", f"core.hooksPath={hooks}", *GIT_ID, "commit", "-q", "-m", "test"],
        cwd=repo, capture_output=True, text=True, env=_env(),
    )


def _run_prepush(repo: Path, test_paths: str) -> subprocess.CompletedProcess:
    env = _env()
    env["PUSH_TEST_PATHS"] = test_paths
    return subprocess.run(
        ["sh", ".githooks/pre-push", "origin"],
        cwd=repo, capture_output=True, text=True, env=env,
    )


def test_precommit_blocks_staged_key(tmp_path):
    _need_sh()
    repo = _make_repo(tmp_path)
    fake_key = "nvapi-" + "A" * 20  # built at runtime; matches the NVIDIA key rule
    _stage(repo, "leak.txt", f"KEY = {fake_key}\n")
    result = _commit(repo)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "commit blocked" in output
    assert "leak.txt" in output  # precommit_check reported the staged file, so the scan itself fired
    assert fake_key not in output  # the secret text is never printed


def test_precommit_allows_clean(tmp_path):
    _need_sh()
    repo = _make_repo(tmp_path)
    _stage(repo, "ok.py", "x = 1\n")
    result = _commit(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_precommit_blocks_python_syntax_error(tmp_path):
    _need_sh()
    repo = _make_repo(tmp_path)
    _stage(repo, "bad.py", "def broken(:\n")
    result = _commit(repo)
    assert result.returncode != 0


def test_prepush_fails_on_failing_test(tmp_path):
    _need_sh()
    repo = _make_repo(tmp_path)
    _stub_secret_scan(repo)
    (repo / "test_fail.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    result = _run_prepush(repo, "test_fail.py")
    assert result.returncode == 1
    assert "1 failed" in result.stdout + result.stderr  # pytest ran the failing test itself
    assert "push blocked (tests exit 1)" in result.stdout + result.stderr
    assert not (repo / "secret_scan_ran.txt").exists()  # blocked before the secret scan


def test_prepush_passes_on_passing_test(tmp_path):
    _need_sh()
    repo = _make_repo(tmp_path)
    _stub_secret_scan(repo)
    (repo / "test_pass.py").write_text("def test_x():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    result = _run_prepush(repo, "test_pass.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "secret_scan_ran.txt").exists()  # the second stage ran after the tests passed
