import sys
from pathlib import Path
import ast
import pytest

TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent.parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(PROJECT_ROOT))


def _is_negative_float_literal(node, value=14.0):
    """Check if an AST node represents the literal -value (e.g., -14.0)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, float) and node.value == -value:
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, float) and node.operand.value == value:
            return True
    return False


def _find_py_files(root):
    """Find all non-test Python files in director/, h3/, score/."""
    dirs = ["director", "h3", "score"]
    py_files = []
    for d in dirs:
        dir_path = root / d
        if dir_path.exists():
            for f in dir_path.rglob("*.py"):
                if "tests" in f.parts or "__pycache__" in f.parts:
                    continue
                py_files.append(f)
    return py_files


def test_only_audition_constant_is_minus_14():
    root = PROJECT_ROOT
    py_files = _find_py_files(root)

    occurrences = []
    for f in py_files:
        try:
            source = f.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(f))
        except Exception:
            continue
        for node in ast.walk(tree):
            if _is_negative_float_literal(node, 14.0):
                occurrences.append((f, node))

    # There must be exactly one -14.0 literal in the whole scanned codebase.
    assert len(occurrences) == 1, (
        f"Expected exactly one -14.0 literal, found {len(occurrences)}: "
        f"{[str(o[0]) for o in occurrences]}"
    )

    f, node = occurrences[0]
    expected_rel = Path("score/stem_builder.py")
    assert f.relative_to(root) == expected_rel, (
        f"Found -14.0 in {f}, expected only in {expected_rel}"
    )

    # Verify that this literal is the value of an assignment to AUDITION_NODUCK_LUFS.
    source = f.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(f))
    found_assignment = False
    for assign_node in ast.walk(tree):
        if isinstance(assign_node, ast.Assign):
            # compare by source position: the file is parsed again here, so node identity never matches
            if (getattr(assign_node.value, "lineno", None), getattr(assign_node.value, "col_offset", None)) == (
                    node.lineno, node.col_offset):
                for target in assign_node.targets:
                    if isinstance(target, ast.Name) and target.id == "AUDITION_NODUCK_LUFS":
                        found_assignment = True
                        break
    assert found_assignment, (
        "The -14.0 literal is not assigned to AUDITION_NODUCK_LUFS"
    )


def test_gate_d_target_is_read_from_core():
    """Card X-20 one-target path: h3/shot_table_spec._loudness_from_core reads lufs from load_core(), no literal."""
    tree = ast.parse((PROJECT_ROOT / "h3" / "shot_table_spec.py").read_text(encoding="utf-8"))
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_loudness_from_core"]
    assert len(fns) == 1
    fn = fns[0]
    calls_core = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "load_core"
                     for n in ast.walk(fn))
    reads_lufs = any(isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value == "lufs"
                     for n in ast.walk(fn))
    literals = [n.value for n in ast.walk(fn)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert calls_core and reads_lufs, "_loudness_from_core must read lufs from load_core()"
    assert literals == [], f"hard-coded numbers in _loudness_from_core: {literals}"


def test_write_noduck_call_passes_named_target():
    """Card X-20: the un-ducked audition write names its target (AUDITION_NODUCK_LUFS) at the call site."""
    tree = ast.parse((PROJECT_ROOT / "score" / "stem_builder.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "write_noduck"]
    assert calls, "no write_noduck call found in stem_builder.py"
    for c in calls:
        kw = {k.arg: k.value for k in c.keywords}
        assert "target_lufs" in kw, f"write_noduck call at line {c.lineno} has no explicit target_lufs"
        assert isinstance(kw["target_lufs"], ast.Name) and kw["target_lufs"].id == "AUDITION_NODUCK_LUFS", (
            f"write_noduck call at line {c.lineno} must pass AUDITION_NODUCK_LUFS")


def test_deliverables_use_core():
    """Card X-20: the deliverable loudness target (Gate D, h3.shot_table_spec.LOUDNESS) equals core/core.json delivery.audio.lufs.
    (-14 stays audition-only in stem_builder; owner confirms.)"""
    import json
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from h3.shot_table_spec import LOUDNESS
    core = json.loads((PROJECT_ROOT / "core" / "core.json").read_text(encoding="utf-8"))
    assert LOUDNESS["target_lufs"] == core["delivery"]["audio"]["lufs"]
    from score.stem_builder import AUDITION_NODUCK_LUFS
    assert AUDITION_NODUCK_LUFS == core["delivery"]["audio"]["lufs"]   # one target now: audition = delivery value
