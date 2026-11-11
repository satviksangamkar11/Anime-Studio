"""P2 W-12: editorial_by_lang is a deprecated shim. Nothing new may import it. Offline; no ffmpeg; no model."""
import ast
import importlib
import os
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1]
MODULE = "editorial_by_lang"
ALLOWED = {"director/editorial_by_lang.py", "director/test_editorial_by_lang.py"}


LEGACY = "editorial_legacy"
LEGACY_ALLOWED = {"director/editorial_legacy.py", "director/editorial_by_lang.py", "director/test_editorial_by_lang.py"}


def importers_of(source, module=MODULE):
    """Module names this source imports that end in `module` (import x / from x import y)."""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name.split(".")[-1] == module]
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == module:
            hits.append(node.module)
    return hits


def python_files():
    skip = {".git", "__pycache__", ".pytest_cache", "node_modules"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".edit_runner_backup")]
        for f in filenames:
            if f.endswith(".py"):
                yield Path(dirpath) / f


def test_scanner_detects_both_import_forms():
    # positive control: the scanner must see an import, otherwise the scan below proves nothing
    assert importers_of("import editorial_by_lang\n") == ["editorial_by_lang"]
    assert importers_of("from editorial_by_lang import apply_rows\n") == ["editorial_by_lang"]
    assert importers_of("import build_vo_tracks\n") == []


def test_nothing_imports_the_shim_except_its_own_tests_and_itself():
    scanned, offenders = 0, []
    for path in python_files():
        scanned += 1
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED:
            continue
        try:
            found = importers_of(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        if found:
            offenders.append((rel, found))
    assert scanned > 100, f"scan saw only {scanned} files"
    assert offenders == []


def test_legacy_module_is_marked_legacy_and_only_the_shim_and_its_old_tests_import_it():
    text = (ROOT / "director" / "editorial_legacy.py").read_text(encoding="utf-8")
    assert text.startswith('"""LEGACY'), "editorial_legacy.py must open with the LEGACY marker"
    offenders = []
    for path in python_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in LEGACY_ALLOWED:
            continue
        try:
            found = importers_of(path.read_text(encoding="utf-8"), LEGACY)
        except (SyntaxError, UnicodeDecodeError):
            continue
        if found:
            offenders.append((rel, found))
    assert offenders == []


def test_shim_warns_and_still_reexports_the_legacy_names():
    sys.modules.pop(MODULE, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        shim = importlib.import_module(MODULE)
    assert any(issubclass(w.category, DeprecationWarning) and "deprecated" in str(w.message) for w in caught)
    for name in ("load", "apply_rows", "apply_shots", "plan_shot", "needed_sec", "TAIL", "MAX_SPEEDUP", "FILE"):
        assert hasattr(shim, name), name
