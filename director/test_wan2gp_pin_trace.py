"""W-08: offline source trace. Does input_video_strength survive into the end-frame / soft-end handling on the pinned Wan2GP?

Reads the pinned source by path (read-only, no git, no network). Facts are checked by line text, regex and AST.
Skips with a reason when the source folder is missing. Research note: research/WAN2GP_SOFT_END_TRACE_2026-11-11.md
"""
import ast
import base64
import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

SRC = Path("D:/aai work/kaggle_h3_test/wan2gp_src")
PIN = "bd1ff5903cbc18b46c3cce3b75bd140870b536a2"
needs_src = pytest.mark.skipif(not SRC.is_dir(), reason=f"pinned Wan2GP source folder missing: {SRC}")

FL = {"id": "SHOT-04", "mode": "fl2va", "seconds": 5, "start": "a.png", "end": "b.png", "style": "Flat 2D cel anime.",
      "world": "Riverbank at dawn.", "action": "0-2s he steps forward; 2-5s he looks up.", "camera": "slow crane down"}


def _lines(rel):
    return (SRC / rel).read_text(encoding="utf-8", errors="replace").splitlines()


def _line(rel, n):
    return _lines(rel)[n - 1]


def _tree(rel):
    return ast.parse((SRC / rel).read_text(encoding="utf-8", errors="replace"))


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"def {name} not found")


def _pop_strings(node):
    """Count ui_defaults-style .pop("input_video_strength", ...) calls inside a node."""
    n = 0
    for c in ast.walk(node):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "pop" and c.args \
                and isinstance(c.args[0], ast.Constant) and c.args[0].value == "input_video_strength":
            n += 1
    return n


def _resolve_head():
    head = (SRC / ".git" / "HEAD").read_text().strip()
    if not head.startswith("ref:"):
        return head
    ref = head.split(":", 1)[1].strip()
    loose = SRC / ".git" / ref
    if loose.is_file():
        return loose.read_text().strip()
    for line in (SRC / ".git" / "packed-refs").read_text().splitlines():
        if line.endswith(" " + ref):
            return line.split(" ", 1)[0]
    raise AssertionError(f"cannot resolve {ref}")


# ---- our side ----------------------------------------------------------------------------------

def test_settings_for_drops_strength():
    from h3_director import settings_for
    s = settings_for(dict(FL, input_video_strength=0.6))
    assert "input_video_strength" not in s
    assert s["image_prompt_type"] == "SE" and s["image_end"] == "b.png"


def test_our_settings_key_set_is_fixed():
    tree = ast.parse((ROOT / "director" / "h3_director.py").read_text(encoding="utf-8"))
    fn = _func(tree, "settings_for")
    keys = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            keys |= {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert "input_video_strength" not in keys
    assert "image_end_frame_position" not in keys
    assert "image_prompt_type" in keys


def test_task_json_dry_run_has_no_strength_or_end_position(tmp_path, monkeypatch):
    """Synthetic story and keyframes, real builder path (no build_h3_batch.main, which writes into the repo)."""
    from h3.tests import synth
    import build_h3_batch as b
    import run_kaggle
    story = synth.build_story(str(tmp_path))
    pics = tmp_path / "pics"
    kf = tmp_path / "keyframes"
    kf.mkdir()
    # legacy_rows names keyframes/<id>-A.png and -B.png; SYN_C has no start picture, so its end picture serves both
    picks = {"SYN_A": (synth.A_START, synth.A_END), "SYN_B": (synth.B_START, synth.B_END), "SYN_C": (synth.C_END, synth.C_END)}
    for sid, (start, end) in picks.items():
        (kf / f"{sid}-A.png").write_bytes((pics / start).read_bytes())
        (kf / f"{sid}-B.png").write_bytes((pics / end).read_bytes())
    # the synthetic ids (SYN_A...) fail the shot-id rule, so the rows are renamed after legacy_rows has read the keyframe names
    # W-09: legacy_rows needs routes and a lock and returns (rows, post_ids); every shot gets an SE route and a lock row
    ep = story["episodes"][0]
    routes, lock = {"routes": {}}, {"shots": []}
    for sh in ep["shots"]:
        sid, pf = sh["shot_id"], sh["timing_and_lattice"]["pixel_frames"]
        routes["routes"][sid] = {"route": "SE", "image_prompt_type": "SE", "input_video_strength": None}
        lock["shots"].append({"id": sid, "pixel_frames": pf, "end_frame_position": pf - 5})
    rows, _post = b.legacy_rows(story, ep["episode_id"], routes=routes, lock=lock)
    shots = [dict(r, id=f"SHOT-{i + 1:03d}", input_video_strength=0.6) for i, r in enumerate(rows)]
    script, _meta = run_kaggle.build(shots, str(tmp_path), "t", target="colab")
    m = re.search(r"settings in json\.loads\(base64\.b64decode\(\"([A-Za-z0-9+/=]+)\"\)\)", script)
    assert m, "settings blob not found in the rendered runner"
    settings = json.loads(base64.b64decode(m.group(1)))
    assert settings, "no shots in the settings blob"
    for sid, s in settings.items():
        assert s["image_prompt_type"] in ("S", "SE", "E", "")
        assert "input_video_strength" not in s, sid
        assert "image_end_frame_position" not in s, sid


# ---- pinned source -------------------------------------------------------------------------------

def test_pin_matches():
    import run_kaggle
    assert run_kaggle.WAN2GP_COMMIT == PIN
    if (SRC / ".git").is_dir():
        assert _resolve_head() == PIN


@needs_src
def test_cli_chain_order_in_validate_task():
    """--process: _parse_settings_json (2248) -> validate_task (9662) -> clean_settings (9734, pops via fix_settings) ->
    validate_settings (forces 1.0 at 1510-1511) -> inputs.update (9744)."""
    tree = _tree("wgp.py")
    vt = _func(tree, "validate_task")
    calls = {}
    for c in ast.walk(vt):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name):
            calls.setdefault(c.func.id, c.lineno)
    assert calls["clean_settings"] == 9734
    assert calls["validate_settings"] > calls["clean_settings"]
    assert "_parse_settings_json" in {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert any(isinstance(n, ast.FunctionDef) and n.name == "_parse_settings_json" and n.lineno == 2248 for n in tree.body)
    assert _line("wgp.py", 9744).strip().startswith("override_inputs, _, _, _, validation_error = validate_settings(")
    assert _line("wgp.py", 9747).strip() == "inputs.update(override_inputs)"


@needs_src
def test_clean_settings_reaches_handler_fix_settings():
    tree = _tree("wgp.py")
    cs = _func(tree, "clean_settings")
    assert any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "fix_settings" and c.lineno == 1993
               for c in ast.walk(cs))
    fs = _func(tree, "fix_settings")
    handler_calls = [c.lineno for c in ast.walk(fs) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                     and c.func.attr == "fix_settings"]
    assert handler_calls == [3500]


@needs_src
def test_handler_fix_settings_pops_strength():
    tree = _tree("models/minimax_h3/minimax_h3_handler.py")
    fam = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "family_handler")
    methods = {n.name: n for n in fam.body if isinstance(n, ast.FunctionDef)}
    assert _pop_strings(methods["fix_settings"]) == 1
    assert _pop_strings(methods["update_default_settings"]) == 1
    assert methods["fix_settings"].lineno == 1359
    assert _line("models/minimax_h3/minimax_h3_handler.py", 1360).strip() == 'ui_defaults.pop("input_video_strength", None)'
    assert _line("models/minimax_h3/minimax_h3_handler.py", 1416).strip() == 'ui_defaults.pop("input_video_strength", None)'


@needs_src
def test_h3_model_def_has_no_strength_key():
    lines = _lines("models/minimax_h3/minimax_h3_handler.py")
    hits = [(i + 1, l) for i, l in enumerate(lines) if "input_video_strength" in l]
    assert len(hits) == 2
    assert all(".pop(" in l for _, l in hits)
    assert not any(re.search(r"\"input_video_strength\"\s*:", l) for _, l in hits)


@needs_src
def test_wgp_forces_strength_1():
    tree = _tree("wgp.py")
    vs = _func(tree, "validate_settings")
    assert vs.lineno <= 1510 <= vs.end_lineno
    assert _line("wgp.py", 1510).strip() == "if not input_video_strength_visible(model_def, image_prompt_type, video_prompt_type):"
    assert _line("wgp.py", 1511).strip() == "input_video_strength = 1.0"


@needs_src
def test_strength_visible_needs_a_label():
    tree = _tree("wgp.py")
    fn = _func(tree, "input_video_strength_visible")
    assert fn.lineno == 940 and fn.end_lineno <= 946
    text = "\n".join(_lines("wgp.py")[939:946])
    assert 'input_video_strength.get("label", "").strip()' in text
    assert 'any_letters(image_prompt_type or "", "SVLE")' in text
    assert "len(input_video_strength_label) > 0" in text


@needs_src
def test_validate_settings_reads_strength_from_inputs_with_default_1():
    assert _line("wgp.py", 1297).strip() == 'input_video_strength = inputs.get("input_video_strength", 1.0)'


@needs_src
def test_generate_media_passes_strength_on():
    tree = _tree("wgp.py")
    assert _func(tree, "generate_media").lineno == 7380
    assert _line("wgp.py", 8788).strip() == "input_video_strength = input_video_strength,"


@needs_src
def test_settings_pop_is_settings_target_only():
    """wgp.py 10516-10517 pops the key only for target == "settings" (saving the UI state), not in the generation path."""
    assert _line("wgp.py", 10515).strip() == 'if target == "settings":'
    assert _line("wgp.py", 10516).strip() == 'if model_def.get("input_video_strength") is None:'
    assert _line("wgp.py", 10517).strip() == 'inputs.pop("input_video_strength", None)'


@needs_src
def test_end_position_not_read_from_inputs():
    text = "\n".join(_lines("wgp.py"))
    assert text.count('inputs.get("image_end_frame_position"') == 0
    assert text.count('inputs["image_end_frame_position"]') == 0


@needs_src
def test_end_position_is_computed_from_length_and_trim():
    assert _line("wgp.py", 8262).strip() == "tail_trim_frames = discard_last_frames + automatic_trim_last_frames"
    assert _line("wgp.py", 8317).strip().startswith("end_image_before_discard = model_def.get(\"end_image_before_discarded_frames\", False) and window_no < total_windows")
    l8318 = _line("wgp.py", 8318)
    assert l8318.strip().startswith(
        "image_end_frame_position = current_video_length - (automatic_trim_last_frames if end_image_before_discard else tail_trim_frames) - 1")
    assert '.get("image_end_frame_position", False) else None' in l8318


@needs_src
def test_h3_handler_enables_end_position_and_early_end_image():
    assert _line("models/minimax_h3/minimax_h3_handler.py", 765).strip() == '"end_image_before_discarded_frames": True,  # discarded last frames follow the end image of non-final windows'
    assert _line("models/minimax_h3/minimax_h3_handler.py", 767).strip() == '"image_end_frame_position": True,'


@needs_src
def test_pipeline_can_soften_the_end_but_defaults_to_hard():
    lines = _lines("models/minimax_h3/pipeline.py")
    assert "input_video_strength=1.0" in lines[786]   # generate() signature, line 787 (default 1.0 = hard end)
    assert lines[966].strip() == "soft_anchor_timestep = float(input_video_strength) if float(input_video_strength) < VISUAL_COND_TIMESTEP else None"
    for n in (1010, 1012, 1014, 1016):
        assert "timestep=soft_anchor_timestep" in lines[n - 1], n
