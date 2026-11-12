import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import blocking  # noqa: E402
import blocking_lint  # noqa: E402
import write_pack  # noqa: E402

V24 = HERE / "MASTER_PROMPT_v2.4.md"
V23 = HERE / "MASTER_PROMPT_v2.3.md"
EXAMPLE = re.compile(r"```json example-blocking\s*\n(.*?)\s*```", re.DOTALL)


def _v24_text():
    return V24.read_text(encoding="utf-8")


def _example_sheet():
    import json
    found = EXAMPLE.findall(_v24_text())
    assert len(found) == 1, "v2.4 must carry exactly one ```json example-blocking fence"
    return json.loads(found[0])


def test_prompt_version_v24_is_accepted_by_the_brief_selector():
    assert write_pack.staged_brief("v2.4") == V24


def test_v24_file_exists_and_v23_stays_the_default_and_unchanged():
    assert V24.exists()
    assert V23.exists()
    assert write_pack.staged_brief().read_text(encoding="utf-8") == V23.read_text(encoding="utf-8")
    assert write_pack.staged_brief("v2.3").read_text(encoding="utf-8") == V23.read_text(encoding="utf-8")
    assert _v24_text() != V23.read_text(encoding="utf-8")


def test_prompt_version_v24_passes_argparse_choices(tmp_path):
    # without --staged the flag is refused by the staged check, not by "invalid choice"
    story = tmp_path / "story.md"
    story.write_text("A story.", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        write_pack.main([str(story), str(tmp_path / "pack"), "--prompt-version", "v2.4"])
    assert exc.value.code == 2
    result = subprocess.run([sys.executable, str(HERE / "write_pack.py"), str(story), str(tmp_path / "pack"),
                             "--prompt-version", "v2.4"], capture_output=True, text=True)
    assert "invalid choice" not in result.stderr
    assert "need --staged" in result.stderr


def test_unknown_prompt_version_still_refused():
    with pytest.raises(ValueError):
        write_pack.staged_brief("v9.9")


def test_v24_example_sheet_passes_blocking_validate():
    sheet = _example_sheet()
    assert sheet["schema"] == "blocking/1.1"
    assert blocking.validate(sheet) == []


def test_v24_example_sheet_lints_clean():
    sheet = _example_sheet()
    assert blocking_lint.lint([sheet]) == []


def test_v24_example_arms_is_an_integer_not_a_word():
    sheet = _example_sheet()
    assert all(isinstance(m["arms"], int) and m["arms"] >= 2 for m in sheet["cast"])
    assert '"arms": "down"' not in _v24_text()


def test_v24_brief_names_every_camera_move_the_code_accepts():
    text = _v24_text()
    for move in blocking._CAMERA_11_MOVES:
        if move == "locked":
            continue   # the brief says fixed mode is move null
        assert move in text, "camera move %s missing from the v2.4 vocabulary" % move


def test_v24_brief_carries_the_new_story_and_shot_fields():
    text = _v24_text()
    for name in ("premise", "reel_target_s", "arc_beat", "hook_type", "voice_rest", "composition",
                 "emotion", "chain_from", "caption_safe", "hold", "expression", "beats", "shake"):
        assert name in text, "field %s missing from v2.4" % name
    for beat in ("Hook", "Setup", "Escalation", "Payoff"):
        assert beat in text


def test_v24_brief_keeps_the_v23_retention_and_look_rules():
    text = _v24_text()
    for marker in ("RETENTION RULES", "COLOUR AND RETENTION FIELDS", "(c2) BLOCKING SHEET", "json shots",
                   "json bible", "R1 (fail)", "R10 (warning)"):
        assert marker in text, "v2.3 section %s lost in v2.4" % marker


def test_v24_brief_drops_the_fixed_reel_length():
    text = _v24_text()
    assert "reel length follows the story" in text.lower()
    assert "30-45 s" not in text or "no fixed" in text.lower()


def test_staged_run_with_v24_appends_the_style_rules(tmp_path, monkeypatch):
    seen = {}

    def fake_run_staged(story, out, via, model, effort, allow_paid, stage_via, stage_model, rec, **kw):
        seen.update(kw)

    monkeypatch.setattr(write_pack, "run_staged", fake_run_staged)
    monkeypatch.setattr(write_pack, "style_rules", lambda pack_id, **k: "## STYLE PACK RULES\nrule")
    monkeypatch.setattr(write_pack, "story_pack_id", lambda p: "demo")
    monkeypatch.setattr(write_pack, "load_style_pack", lambda pack_id: {})
    story = tmp_path / "story.md"
    story.write_text("A story.", encoding="utf-8")
    write_pack.main([str(story), str(tmp_path / "pack"), "--staged", "--prompt-version", "v2.4"])
    assert seen["prompt_version"] == "v2.4"
    assert seen["style_rules"].startswith("## STYLE PACK RULES")
