"""Round-3 regressions (triage R3-H3, schema_and_linter.py): malformed profile and registry input is a lint error, never a crash."""
import copy

from h3.schema_and_linter import lint_profile, lint_shot, lint_story
from h3.tests.synth import codes


def _profile_with(story, **kw):
    prof = copy.deepcopy(story["registry"]["execution_profile"])
    prof.update(kw)
    return prof


def _story_with_profile(story, prof):
    st = copy.deepcopy(story)
    st["registry"]["execution_profile"] = prof
    return st


def test_base_resolution_of_wrong_shape_is_po01_not_a_crash(story):
    for bad in ([1920], "abc", [1920, 1080, 4]):
        out = lint_profile(_profile_with(story, base_resolution=bad))
        assert [m[:5] for m in out["errors"]] == ["PO-01"]


def test_aspect_ratio_with_extra_parts_is_po02_not_a_crash(story):
    out = lint_profile(_profile_with(story, aspect_ratio="16:9:extra"))
    assert [m[:5] for m in out["errors"]] == ["PO-02"]


def test_zero_fps_is_po06_and_lint_story_stops_before_dividing(story):
    out = lint_story(_story_with_profile(story, _profile_with(story, fps=0)))
    assert "PO-06" in codes(out["errors"])


def test_invalid_banned_negative_regex_is_pr08_not_a_crash(story):
    st = copy.deepcopy(story)
    st["registry"]["style_lock"]["banned_negative_words_regex"] = "["
    out = lint_story(st)
    assert "PR-08" in codes(out["errors"])


def test_malformed_mouth_block_does_not_hide_the_sound_cue_rule(story):
    """A non-object dialogue block used to abort the whole pure-Foley rule group. M-01b: SX-01 is retired
    (stage sound words are gone), so the check is that the malformed block is still reported by SC-02."""
    shot = copy.deepcopy(story["episodes"][0]["shots"][0])
    for k in list(shot["motion_7_stage"])[:7]:  # the seven action stages only
        shot["motion_7_stage"][k] = "The figure turns slowly."  # no sound word anywhere
    shot["dialogue_and_lip_lock"] = "x"
    out = lint_shot(shot, story["registry"]["execution_profile"], story["registry"],
                    story["episodes"][0]["asset_root"])
    assert "SC-02" in codes(out["errors"])
