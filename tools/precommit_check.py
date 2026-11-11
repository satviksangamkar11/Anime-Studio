"""Pre-commit checks: secrets, Python syntax, control characters."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

import secret_scan

_BLOCKED_EXT = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".wav", ".mp3", ".mp4", ".mov", ".ttf", ".otf", ".zip", ".pdf",
}

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_MAX_FILE_SIZE = 1024 * 1024  # 1 MB


def scan_secrets(text: str, name: str = "<text>") -> list[str]:
    """Return findings for secret-like patterns in *text*, using the secret_scan rule list (one rule list for the whole repo).

    Each finding is ``"<name>:<line>: <rule id>"``.  The matched secret text is never included.
    """
    findings: list[str] = []
    for line_no, rule, _what, _line in secret_scan.content_findings(text.encode("utf-8")):
        findings.append(f"{name}:{line_no}: {rule}")
    return findings


def check_python(src: str, name: str = "<src>") -> list[str]:
    """Return ``["<name>:<line>: syntax error"]`` if *src* does not parse."""
    try:
        ast.parse(src)
    except (SyntaxError, ValueError) as exc:
        line = exc.lineno if exc.lineno is not None else 1
        return [f"{name}:{line}: syntax error"]
    return []


def check_control_chars(text: str, name: str = "<text>") -> list[str]:
    """Flag control characters other than tab, newline, carriage return."""
    findings: list[str] = []
    for line_no, line in enumerate(text.split("\n"), start=1):
        for match in _CONTROL_CHAR_RE.finditer(line):
            ch = match.group(0)
            findings.append(f"{name}:{line_no}: control character U+{ord(ch):04X}")
    return findings


def check_file(path: str, staged: bool = False) -> list[str]:
    """Run all checks on a single file path.

    When *staged* is true, the staged blob (``git show :<path>``) is read
    instead of the working copy.
    """
    if staged:
        result = subprocess.run(["git", "show", f":{path}"], capture_output=True)
        if result.returncode != 0:
            return [f"{path}: cannot read staged blob"]
        raw = result.stdout
    else:
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            return [f"{path}: missing file"]
    return check_blob(path, raw)


def check_blob(path: str, raw: bytes) -> list[str]:
    """Run all checks on the bytes of *path* (working file or staged blob)."""
    if len(raw) > _MAX_FILE_SIZE:
        return [f"{path}: over 1 MB"]

    if Path(path).suffix.lower() in _BLOCKED_EXT:
        return []  # binary media: content checks do not apply

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [f"{path}: not UTF-8"]

    findings: list[str] = []
    findings.extend(scan_secrets(text, path))
    findings.extend(check_control_chars(text, path))
    if path.lower().endswith(".py"):
        findings.extend(check_python(text, path))
    return findings


def check_staged(path: str) -> list[str]:
    """Run checks on the staged blob (``git show :<path>``), not the working file."""
    result = subprocess.run(["git", "show", f":{path}"], capture_output=True)
    if result.returncode != 0:
        return [f"{path}: cannot read staged blob"]
    return check_blob(path, result.stdout)


def check_files(paths: Sequence[str]) -> list[str]:
    """Run checks on *paths* in order, concatenating findings."""
    findings: list[str] = []
    for path in paths:
        findings.extend(check_file(path))
    return findings


def main(argv: Optional[Sequence[str]] = None,
         staged: Optional[Sequence[str]] = None) -> int:
    """Entry point used by pre-commit hooks.

    Returns 0 when no findings, 1 otherwise.

    The ``staged`` keyword argument is an explicit list of files read from the
    working tree; the no-argument path reads the staged blobs.
    """
    if argv is not None:
        findings = check_files(list(argv))
    elif staged is not None:
        findings = check_files(list(staged))
    else:
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "-z",
                 "--diff-filter=ACMR"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
            print(f"precommit_check: cannot list staged files: {exc}", file=sys.stderr)
            return 1
        paths = [item for item in result.stdout.split(chr(0)) if item]
        findings = []
        for path in paths:
            findings.extend(check_staged(path))
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
