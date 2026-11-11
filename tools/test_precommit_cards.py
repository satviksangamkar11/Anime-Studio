"""Frozen test gate for gap card X-21: precommit_check patterns, staged blob, binaries."""

import sys
from pathlib import Path

# Ensure the tools directory and project root are on sys.path so that
# precommit_check and secret_scan can be imported by bare name.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import precommit_check


def _elevenlabs_key() -> str:
    return "sk_" + "a" * 48


def _anthropic_key() -> str:
    return "sk-ant-" + "A" * 20


def _google_key() -> str:
    return "AIza" + "A" * 35


def _github_token() -> str:
    return "ghp_" + "A" * 36


def test_elevenlabs_key_found():
    secret = _elevenlabs_key()
    findings = precommit_check.check_blob("test.txt", secret.encode())
    assert any("K-ELEVEN" in f for f in findings)


def test_anthropic_key_found():
    secret = _anthropic_key()
    findings = precommit_check.check_blob("test.txt", secret.encode())
    assert any("K-OPENAI" in f for f in findings)


def test_anthropic_rule_id_found():
    # Dedicated sk-ant rule: the finding must carry K-ANTHROPIC, not only the generic K-OPENAI.
    findings = precommit_check.check_blob("test.txt", _anthropic_key().encode())
    assert any("K-ANTHROPIC" in f for f in findings)


def test_google_key_found():
    secret = _google_key()
    findings = precommit_check.check_blob("test.txt", secret.encode())
    assert any("K-GOOGLE" in f for f in findings)


def test_github_token_found():
    secret = _github_token()
    findings = precommit_check.check_blob("test.txt", secret.encode())
    assert any("K-GITHUB" in f for f in findings)


def test_nul_byte_found():
    findings = precommit_check.check_blob("test.txt", b"hello\x00world")
    assert findings
    assert any("control character" in f for f in findings)


def test_del_found():
    findings = precommit_check.check_blob("test.txt", b"hello\x7fworld")
    assert findings
    assert any("control character" in f for f in findings)


def test_staged_blob_scanned_after_worktree_cleaned(tmp_path, monkeypatch):
    import subprocess

    # Create a temporary git repository
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    # Write a file containing a secret and stage it
    secret = _elevenlabs_key()
    file_path = repo / "secret.txt"
    file_path.write_text(secret)
    subprocess.run(["git", "add", "secret.txt"], cwd=repo, check=True, capture_output=True)

    # Clean the working tree file (overwrite with harmless content)
    file_path.write_text("clean")

    # Change to the repo so that git commands run in the correct directory
    monkeypatch.chdir(repo)

    # The correct implementation should read the staged blob via git show :path
    # and still detect the secret. On the current code, check_file has no
    # 'staged' parameter, so this will raise TypeError.
    findings = precommit_check.check_file("secret.txt", staged=True)
    assert any("K-ELEVEN" in f for f in findings)


def test_png_skipped(tmp_path):
    # Write invalid UTF-8 bytes to a .png file. If the file is scanned,
    # the current code will report "not UTF-8". The correct implementation
    # skips binary extensions entirely, producing no findings.
    png_path = tmp_path / "test.png"
    png_path.write_bytes(b"\x80\x81\x82")
    findings = precommit_check.check_file(str(png_path))
    assert findings == []
