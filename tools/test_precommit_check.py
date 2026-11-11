"""Tests for tools.precommit_check."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import precommit_check  # noqa: E402


def _key_hf() -> str:
    return "hf" + "_" + "A" * 30


def _key_openrouter() -> str:
    return "sk-or" + "-v1-" + "B" * 30


def _key_nvidia() -> str:
    return "nv" + "api-" + "C" * 30


def _key_generic() -> str:
    return "sk-" + "D" * 32


def test_scan_secrets_each_pattern_with_line_numbers() -> None:
    text = (
        "line one\n"
        f"token = {_key_hf()}\n"
        f"router = {_key_openrouter()}\n"
        f"nv = {_key_nvidia()}\n"
        f"generic = {_key_generic()}\n"
    )
    findings = precommit_check.scan_secrets(text, "example.txt")
    assert findings == [
        "example.txt:2: K-HF",
        "example.txt:3: K-OPENROUTER",
        "example.txt:3: K-OPENAI",
        "example.txt:4: K-NVIDIA",
        "example.txt:5: K-OPENAI",
    ]


def test_scan_secrets_no_secret_text_in_finding() -> None:
    text = f"key = {_key_hf()}\n"
    findings = precommit_check.scan_secrets(text, "f.txt")
    assert findings == ["f.txt:1: K-HF"]
    for finding in findings:
        assert "A" * 30 not in finding
        assert _key_hf() not in finding


def test_scan_secrets_clean_file() -> None:
    text = "x = 1\nprint('hello')\n"
    assert precommit_check.scan_secrets(text, "clean.py") == []


def test_check_python_syntax_error() -> None:
    src = "def foo(\n"  # unclosed parenthesis
    findings = precommit_check.check_python(src, "bad.py")
    assert findings == ["bad.py:1: syntax error"]


def test_check_python_clean() -> None:
    src = "x = 1 + 2\n"
    assert precommit_check.check_python(src, "good.py") == []


def test_check_control_chars_backspace_and_formfeed() -> None:
    text = "line1\x08\nline2\x0c\n"
    findings = precommit_check.check_control_chars(text, "ctrl.txt")
    assert findings == [
        "ctrl.txt:1: control character U+0008",
        "ctrl.txt:2: control character U+000C",
    ]


def test_check_control_chars_tab_newline_cr_allowed() -> None:
    text = "a\tb\nc\rd\n"
    assert precommit_check.check_control_chars(text, "ok.txt") == []


def test_check_file_over_1mb(tmp_path) -> None:
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (1024 * 1024 + 1))
    findings = precommit_check.check_file(str(big))
    assert findings == [str(big) + ": over 1 MB"]


def test_check_file_invalid_utf8(tmp_path) -> None:
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\xff\xfe\x00invalid")
    findings = precommit_check.check_file(str(bad))
    assert findings == [str(bad) + ": not UTF-8"]


def test_check_file_missing(tmp_path) -> None:
    missing = str(tmp_path / "does_not_exist.py")
    findings = precommit_check.check_file(missing)
    assert findings == [missing + ": missing file"]


def test_check_files_order_and_missing(tmp_path) -> None:
    good = tmp_path / "good.py"
    good.write_text("x = 1\n")
    missing = str(tmp_path / "nope.py")
    findings = precommit_check.check_files([str(good), missing])
    assert findings == [missing + ": missing file"]


def test_main_dirty_and_clean_via_staged(tmp_path) -> None:
    dirty = tmp_path / "dirty.py"
    dirty.write_text(f"key = {_key_hf()}\n")
    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n")

    assert precommit_check.main(staged=[str(dirty)]) == 1
    assert precommit_check.main(staged=[str(clean)]) == 0


def test_scan_secrets_no_secret_text_for_all_patterns(tmp_path) -> None:
    keys = {
        "K-HF": _key_hf(),
        "K-OPENROUTER": _key_openrouter(),
        "K-NVIDIA": _key_nvidia(),
        "K-OPENAI": _key_generic(),
    }
    name = str(tmp_path / "f.txt")
    for rule_id, key in keys.items():
        findings = precommit_check.scan_secrets(f"key = {key}\n", name)
        assert f"{name}:1: {rule_id}" in findings
        for finding in findings:
            assert key not in finding
            assert key[-30:] not in finding


def test_scan_secrets_line_numbers_with_form_feed_vt_and_u2028_u2029() -> None:
    key = _key_hf()
    for sep in ("\x0c", "\x0b", " ", " "):
        text = f"first{sep}line\n{key}\n"
        assert precommit_check.scan_secrets(text, "sep.txt") == ["sep.txt:2: K-HF"]


def test_check_control_chars_line_numbers_after_u2028_u2029() -> None:
    text = "a b c\nx\x08\n"
    assert precommit_check.check_control_chars(text, "sep.txt") == [
        "sep.txt:2: control character U+0008",
    ]


def test_scan_secrets_crlf_line_numbers() -> None:
    text = "one\r\ntwo\r\n" + _key_hf() + "\r\n"
    assert precommit_check.scan_secrets(text, "crlf.txt") == ["crlf.txt:3: K-HF"]
    assert precommit_check.check_control_chars(text, "crlf.txt") == []


def test_check_file_two_mb_flagged(tmp_path) -> None:
    big = tmp_path / "big2.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    assert precommit_check.check_file(str(big)) == [str(big) + ": over 1 MB"]


def test_check_file_python_syntax_error(tmp_path) -> None:
    bad = tmp_path / "bad_syntax.py"
    bad.write_text("def foo(\n", encoding="utf-8")
    assert precommit_check.check_file(str(bad)) == [str(bad) + ":1: syntax error"]


def test_check_file_uppercase_py_syntax_error(tmp_path) -> None:
    bad = tmp_path / "BAD.PY"
    bad.write_text("def foo(\n", encoding="utf-8")
    assert precommit_check.check_file(str(bad)) == [str(bad) + ":1: syntax error"]


def test_check_file_bom_python_valid_is_clean(tmp_path) -> None:
    bom = tmp_path / "bom.py"
    bom.write_bytes(b"\xef\xbb\xbf" + b"x = 1\n")
    assert precommit_check.check_file(str(bom)) == []


def test_check_files_exact_order_and_missing(tmp_path) -> None:
    dirty = tmp_path / "dirty_order.txt"
    dirty.write_text(f"key = {_key_hf()}\n")
    missing = str(tmp_path / "gone.py")
    clean = tmp_path / "clean_order.py"
    clean.write_text("x = 1\n")
    findings = precommit_check.check_files([str(dirty), missing, str(clean)])
    assert findings == [f"{dirty}:1: K-HF", missing + ": missing file"]


def test_main_argv_dirty_and_clean(tmp_path) -> None:
    dirty = tmp_path / "dirty_argv.py"
    dirty.write_text(f"key = {_key_hf()}\n")
    clean = tmp_path / "clean_argv.py"
    clean.write_text("x = 1\n")
    assert precommit_check.main(argv=[str(dirty)]) == 1
    assert precommit_check.main(argv=[str(clean)]) == 0


def test_main_default_git_command_uses_diff_filter(monkeypatch) -> None:
    calls = []

    class _Done:
        stdout = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _Done()

    monkeypatch.setattr(precommit_check.subprocess, "run", fake_run)
    assert precommit_check.main() == 0
    assert calls == [["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"]]


def test_eleven_key_found() -> None:
    key = "sk_" + "0" * 48
    assert precommit_check.scan_secrets(f"x = {key}\n", "k.py") == ["k.py:1: K-ELEVEN"]


def test_anthropic_key_found() -> None:
    key = "sk-ant-" + "api03-" + "Q" * 40
    assert precommit_check.scan_secrets(f"x = {key}\n", "a.py") == ["a.py:1: K-OPENAI", "a.py:1: K-ANTHROPIC"]


def test_github_token_found() -> None:
    key = "ghp_" + "A1" * 15
    assert precommit_check.scan_secrets(f"x = {key}\n", "g.py") == ["g.py:1: K-GITHUB"]


def test_png_skipped(tmp_path) -> None:
    png = tmp_path / "pic.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\xff\xfe" + ("x = " + _key_hf()).encode())
    assert precommit_check.check_file(str(png)) == []


def test_del_flagged(tmp_path) -> None:
    src = tmp_path / "del.py"
    src.write_bytes("x = 1  # a\x7fb\n".encode("utf-8"))
    assert precommit_check.check_file(str(src)) == [f"{src}:1: control character U+007F"]


def test_nul_flagged(tmp_path) -> None:
    src = tmp_path / "nul.py"
    src.write_bytes(b"x = 1\x00\n")
    findings = precommit_check.check_file(str(src))
    assert f"{src}:1: control character U+0000" in findings


def test_staged_blob_read(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "staged_clean.py").write_text("x = 1\n", encoding="utf-8")   # working file is clean
    blob = (f"key = {_key_hf()}\n").encode("utf-8")                         # staged blob has a key

    class _Out:
        def __init__(self, stdout, returncode=0):
            self.stdout = stdout
            self.returncode = returncode

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["git", "show"]:
            assert cmd == ["git", "show", ":staged_clean.py"]
            return _Out(blob)
        return _Out("staged_clean.py" + chr(0))  # the git diff --cached -z name list (NUL-separated, trailing NUL)

    monkeypatch.setattr(precommit_check.subprocess, "run", fake_run)
    assert precommit_check.check_staged("staged_clean.py") == ["staged_clean.py:1: K-HF"]
    assert precommit_check.main() == 1


def test_cli_entry_point_passes_argv(tmp_path) -> None:
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "precommit_check.py")
    dirty = tmp_path / "cli_dirty.py"
    dirty.write_text(f"key = {_key_hf()}\n")
    clean = tmp_path / "cli_clean.py"
    clean.write_text("x = 1\n")
    repo_root = os.path.dirname(os.path.dirname(script))
    dirty_run = subprocess.run([sys.executable, script, str(dirty)], capture_output=True, cwd=repo_root)
    clean_run = subprocess.run([sys.executable, script, str(clean)], capture_output=True, cwd=repo_root)
    assert dirty_run.returncode == 1
    assert clean_run.returncode == 0
