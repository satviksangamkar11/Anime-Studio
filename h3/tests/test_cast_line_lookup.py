"""Regression: the cast line of the prompt looked up registry characters by exact id and raised KeyError('shiva')
when a subject (template id 'shiva') was missing from the registry. Offline, synthetic input only."""
import copy

from core.tests.test_convert_deva_h3 import h3_shots, story_for
from h3.compile_h3_sing8 import compile_fl2va_prompt


def _shot_and_registry(characters):
    story = story_for(h3_shots(), "unused-asset-root")
    reg = copy.deepcopy(story["registry"])
    reg["characters"] = characters
    shot = copy.deepcopy(story["episodes"][0]["shots"][0])
    shot["continuity_and_seam_lock"]["subjects_present"] = ["shiva"]
    return shot, reg


def test_subject_missing_from_registry_gives_no_cast_line_instead_of_keyerror():
    shot, reg = _shot_and_registry({})
    prompt = compile_fl2va_prompt(shot, reg)["compiled_prompt"]
    assert "Only " not in prompt  # previous behaviour: no cast line


def test_subject_found_by_id_ignoring_case_names_the_character():
    shot, reg = _shot_and_registry({"SHIVA": {"short_disambiguator": "Shiva Neelkanth"}})
    prompt = compile_fl2va_prompt(shot, reg)["compiled_prompt"]
    assert "Only Shiva Neelkanth appears in this shot" in prompt
