"""Dots round-2 leftovers: lint_story must report malformed input, never crash."""
import pytest

from h3.schema_and_linter import lint_story


def _sid(story):
    return story["episodes"][0]["shots"][0]["shot_id"]


@pytest.mark.parametrize("tamper", [
    lambda s: s["episodes"][0]["shots"][0].__setitem__("timing_and_lattice", "not-a-dict"),
    lambda s: s["episodes"][0]["shots"][0].__setitem__("episode_plan", "not-a-dict"),
    lambda s: s["episodes"][0].__setitem__("episode_plan", ["not", "a", "dict"]),
])
def test_non_object_fields_are_reported_not_raised(story, tamper):
    tamper(story)
    out = lint_story(story)
    assert out["errors"] or out["warnings"]


def test_non_object_compiled_entry_is_reported_not_raised(story):
    out = lint_story(story, compiled={_sid(story): "a plain string"})
    assert isinstance(out, dict)


def test_non_list_reference_value_is_reported_as_rf03(story):
    from h3.router import ref2va_limit_problems, ref_inventory
    shot = story["episodes"][0]["shots"][0]
    shot["fl2va_keyframes"] = dict(shot.get("fl2va_keyframes") or {}, reference_images="img_a.png")
    assert ref_inventory(shot)["images"] == []           # a string is not a list of refs: no per-character split
    assert any(code == "RF-03" for code, _ in ref2va_limit_problems(shot))


def test_non_dict_keyframes_do_not_crash_router(story):
    from h3.router import ref_inventory
    shot = story["episodes"][0]["shots"][0]
    shot["fl2va_keyframes"] = ["not", "a", "dict"]
    assert ref_inventory(shot) == {"images": [], "videos": [], "audio": []}
