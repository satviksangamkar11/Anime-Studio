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
