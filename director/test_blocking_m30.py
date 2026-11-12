"""M-30 tests: move+scale together, additive prop_changes, chain_state validation, B text words."""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import blocking  # noqa: E402
import keyframe_jobs  # noqa: E402


def _member(start, end):
    return {"name": "KRISHNA", "start": start, "end": end}


S0 = {"x": 0.25, "y": 0.65, "scale": 0.5, "facing": "right", "pose": "standing"}


def _sheet(end, **extra):
    sheet = {"shot": "SHOT-012", "cast": [_member(S0, dict(S0, **end))], "props": []}
    sheet.update(extra)
    return sheet


def test_move_and_scale_both_reported():
    lines = blocking.change_list(_sheet({"x": 0.6, "scale": 0.3}))
    assert "KRISHNA: move from (0.25,0.65) to (0.60,0.65)" in lines
    assert "KRISHNA: scale 0.50 to 0.30" in lines


def test_move_only_has_no_scale_line():
    lines = blocking.change_list(_sheet({"x": 0.6}))
    assert not any("scale" in line for line in lines)


def test_prop_changes_in_change_list():
    sheet = _sheet({"pose": "kneeling"}, prop_changes=[
        {"prop": "flute", "change": "lifts to chest height"}, {"prop": "reeds", "change": "bend to the right"}])
    lines = blocking.change_list(sheet)
    assert "prop flute: lifts to chest height" in lines
    assert "prop reeds: bend to the right" in lines
    assert lines[-1] == "keep everything else exactly the same"


def test_sheet_without_prop_changes_unchanged():
    sheet = _sheet({"pose": "kneeling"})
    assert blocking.change_list(sheet) == ["KRISHNA: standing -> kneeling", "keep everything else exactly the same"]


def test_b_text_prop_words_plain():
    sheet = _sheet({"pose": "kneeling"}, prop_changes=[{"prop": "flute", "change": "lifts to chest height"}])
    text = keyframe_jobs.b_instruction(sheet)
    assert text.endswith("2) The flute lifts to chest height.")
    assert "prop " not in text.split("Change only:")[1]


def test_b_text_move_and_scale_two_items():
    text = keyframe_jobs.b_instruction(_sheet({"x": 0.6, "scale": 0.3}))
    assert "1) KRISHNA moves to the" in text
    assert "2) KRISHNA now a small full figure." in text


def test_b_max_three_counts_prop_changes():
    sheet = _sheet({"x": 0.6, "scale": 0.3}, prop_changes=[{"prop": "flute", "change": "lifts"}])
    assert keyframe_jobs.b_instruction(sheet).count(") ") == 3
    sheet["prop_changes"].append({"prop": "reeds", "change": "bend"})
    with pytest.raises(keyframe_jobs.KeyframeJobError):
        keyframe_jobs.b_instruction(sheet)


def _valid_11():
    import test_blocking_11
    return copy.deepcopy(test_blocking_11.OPUS_EXAMPLE)


def test_valid_11_sheet_has_no_problems():
    assert blocking.validate(_valid_11()) == []


def test_chain_state_with_chain_from_ok():
    sheet = _valid_11()
    sheet.update(chain_from="SHOT-011", chain_state="Krishna stands, flute at his chest")
    assert blocking.validate(sheet) == []


def test_chain_state_without_chain_from_rejected():
    sheet = _valid_11()
    sheet["chain_state"] = "Krishna stands"
    assert any("chain_state" in p for p in blocking.validate(sheet))


@pytest.mark.parametrize("bad", [5, ["x"], ""])
def test_chain_state_must_be_nonempty_string(bad):
    sheet = _valid_11()
    sheet.update(chain_from="SHOT-011", chain_state=bad)
    assert any("chain_state" in p for p in blocking.validate(sheet))


BAD_PCS = ["flute", [{"prop": "flute"}], [{"prop": "", "change": "x"}], [{"prop": "a", "change": 3}]]


@pytest.mark.parametrize("bad", BAD_PCS)
def test_bad_prop_changes_rejected_in_11(bad):
    sheet = _valid_11()
    sheet["prop_changes"] = bad
    assert any("prop_changes" in p for p in blocking.validate(sheet))


def test_good_prop_changes_ok_in_11():
    sheet = _valid_11()
    sheet["prop_changes"] = [{"prop": "flute", "change": "lifts to chest height"}]
    assert blocking.validate(sheet) == []
