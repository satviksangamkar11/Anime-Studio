"""M-32 part 2: 'At second N,' time points are an opt-in profile flag (default OFF); off = natural sequencing words."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from h3 import v4_to_h3  # noqa: E402
from h3.schema_and_linter import load_default_profile  # noqa: E402

PF = 107
DIRS = [{"t0": float(i), "t1": float(i + 1), "action_pose_expression": f"The monk does step {w}"}
        for i, w in enumerate("abcd")]
PROFILES = Path(__file__).resolve().parents[1] / "profiles"


def _stages(**kw):
    return v4_to_h3._stages(DIRS, PF, "SHOT-001", [], **kw)[0]


def test_off_by_default_has_no_time_number():
    for text in _stages().values():
        assert not re.search(r"\bsecond\b|\d", text), text


def test_off_uses_natural_sequencing_words():
    leads = " ".join(_stages().values()).lower()
    for word in ("as ", "while ", "toward the end"):
        assert word in leads


def test_off_stage_texts_are_distinct():
    texts = list(_stages().values())
    assert len(set(texts)) == len(texts) == 7


def test_on_keeps_time_points_and_never_a_range():
    out = _stages(time_points=True)
    assert list(out.values())[0].startswith("At second 0, ")
    joined = " ".join(out.values())
    assert "By second" in joined and "At second" in joined
    assert not re.search(r"second \d+(?:\.\d+)?\s*(?:-|to)\s*\d", joined)


def test_profiles_carry_the_flag_off():
    for name in ("sing8_768x1344", "sing8_864x1536"):
        assert load_default_profile(name)["time_points"] is False


def test_profile_files_keep_min_imd_body_chars():   # M-31 owns this key: M-32 must not change it
    for name in ("sing8_768x1344", "sing8_864x1536"):
        prof = json.loads((PROFILES / f"{name}.json").read_text(encoding="utf-8"))["registry"]["execution_profile"]
        assert prof["min_imd_body_chars"] == 450
