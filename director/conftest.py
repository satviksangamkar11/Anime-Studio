"""Test-only: the stage-2 style guard (STYLE-01/02, write_pack.style_pack_errors) checks real runs against the chosen pack.
The writer tests use small fake bibles that follow no pack, so for them the guard sees no pack, unless a test is marked
real_style (those test the guard itself)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


def pytest_configure(config):
    config.addinivalue_line("markers", "real_style: run with the real style pack loader (style guard on)")


@pytest.fixture(autouse=True)
def _no_style_pack_in_fake_runs(request, monkeypatch):
    if request.node.get_closest_marker("real_style"):
        return
    try:
        import write_pack
    except ImportError:
        return
    monkeypatch.setattr(write_pack, "load_style_pack", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _writer_guard_test_env(request, monkeypatch, tmp_path):
    """Test-only (card X-06/X-07): write_pack.main() switches the claude guard on for the rest of the process.
    Keep that switch from leaking between tests, give fake claude runs a cap and a throwaway ledger folder, and make
    the real `claude --version` probe a no-op. Guard tests that need no cap delete the variable themselves."""
    if request.node.fspath.basename.startswith("test_writer_guard"):
        return
    try:
        import write_pack
        import writer_guard
    except ImportError:
        return
    monkeypatch.setattr(write_pack, "GUARD", write_pack.GUARD)
    monkeypatch.setattr(write_pack, "LEDGERS", tmp_path / "ledgers")
    monkeypatch.setattr(writer_guard, "cli_ready", lambda *a, **k: None)
    if "WRITER_CAP_CENTS" not in __import__("os").environ:
        monkeypatch.setenv("WRITER_CAP_CENTS", "100000")
