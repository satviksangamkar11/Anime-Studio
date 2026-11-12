"""Pure-Foley prompt locks: one fail and one pass per lint code (SL-01..03, AU-01, TG-01, TX-01, LEN-01, MO-01, SX-01)."""
import copy

import pytest

from h3.compile_h3_sing8 import compile_fl2va_prompt
from h3.schema_and_linter import (MOUTH_LOCK_PHRASE, MOUTH_PERSON_RE, PromptRefused, STAGES, lint_story,
                                  mouth_state_problems, prompt_lock_problems)
from h3.shot_table_spec import PROMPT_CHAR_LIMIT
from h3.tests.synth import SPEECH_UTTERANCE, build_story, codes

SOUND = "overall_soundscape: Sound effects only: Rain on wet stone, a distant bell ringing, soft wind through the leaves."


def _prompt(extra="", snd=SOUND):
    """A minimal emitted prompt: header, one description line with the mouth lock, soundscape, music N/A."""
    return ("How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the "
            "0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 7.29-second mark of the target video.\n"
            "integrated_multimodal_description: [Shot 1] Hand-drawn anime cel animation, flat colour. The figure holds "
            f"still, {MOUTH_LOCK_PHRASE}.{extra}\n{snd}\nnon_diegetic_music: N/A")


def _codes_of(text, events=0):
    return {code for code, _ in prompt_lock_problems(text, text_events=events)}


def test_clean_prompt_passes_every_text_lock():
    assert prompt_lock_problems(_prompt()) == []


# ---- one fail case per code (text level) ----

FAIL_CASES = [
    ("SL-01", " The figure says (S1) hello."),
    ("SL-01", " Two speakers (S1,S2) talk."),
    ("SL-02", " The line is [en] hello."),
    ("SL-02", " A line in [Marathi] plays."),
    ("SL-03", " He says <d>hello</d> now."),
    ("AU-01", " A voice from <Audio 1> leads."),
    ("AU-01", " A voice from <audio2> leads."),
    ("TG-01", " @CHAR-01 walks."),
    ("TG-01", " The SHEET-hero card."),
    ("TG-01", " ENV-lane is wet."),
    ("TG-01", " @STYLE-ink lines."),
    ("TG-01", " [char:hero] nods."),
    ("TG-01", " [scene:lane] opens."),
    ("TG-01", " [shot:3] cut."),
    ("TG-01", " [dur:5s] hold."),
    ("TG-01", " [hook:reveal] starts."),
    ("TG-01", " ┃ panel border."),
    ("TG-01", " The door → opens."),
    ("TG-01", " A cut at 0.0-1.0s."),
    ("TX-01", ' A sign reads "OPEN" now.'),
]


@pytest.mark.parametrize("code, extra", FAIL_CASES)
def test_lock_fails_on_its_pattern(code, extra):
    assert code in _codes_of(_prompt(extra))


def test_speaker_and_wrapper_fail_codes_are_exact():
    assert _codes_of(_prompt(" (S1)")) == {"SL-01"}
    assert _codes_of(_prompt(" [en]")) == {"SL-02"}
    assert _codes_of(_prompt(" <d>x</d>")) == {"SL-03"}


def test_shot_shot_tag_and_header_are_not_storyboard_tags():
    assert _codes_of(_prompt(" [Shot 1] beat.")) == set()


# ---- TX-01: one typography event at most, and only when requested ----

def test_tx01_quote_passes_only_when_one_event_is_requested():
    text = _prompt(' A sign reads "OPEN" now.')
    assert prompt_lock_problems(text, text_events=1) == []
    assert "TX-01" in _codes_of(text, events=0)
    assert "TX-01" in _codes_of(_prompt(' "A" and "B".'), events=1)
    assert "TX-01" in _codes_of(text, events=2)


# ---- LEN-01: the 7000-character hard limit ----

def test_len01_fails_one_over_the_limit_and_passes_at_it():
    base = _prompt()
    pad = PROMPT_CHAR_LIMIT - len(base)
    at_limit = _prompt(" " + "x" * (pad - 1))
    assert len(at_limit) == PROMPT_CHAR_LIMIT and "LEN-01" not in _codes_of(at_limit)
    assert "LEN-01" in _codes_of(_prompt(" " + "x" * pad))


# ---- MO-01: positive lock phrase ----

def test_mo01_fails_without_the_positive_lock_phrase():
    assert "MO-01" in _codes_of(_prompt().replace(MOUTH_LOCK_PHRASE, "lips move"))
    assert "MO-01" not in _codes_of(_prompt())


def test_mo01_shot_fields_narrator_flag_and_mouth_state_map():
    # pixel_frames 175 at 24 fps = 7.29 s, so the per-second map must cover seconds 0..7
    base = {"has_dialogue": False, "utterances": [], "mouth_state_rule": "Mouths stay closed."}
    ok = {"timing_and_lattice": {"pixel_frames": 175}, "dialogue_and_lip_lock": base}

    def with_lip(**extra):
        return {**ok, "dialogue_and_lip_lock": {**base, **extra}}
    full = {str(s): "closed" for s in range(8)}
    assert mouth_state_problems(ok, 24)   # both fields are required
    assert mouth_state_problems(with_lip(narrator_mouth_closed=True, mouth_state=full), 24) == []
    assert mouth_state_problems(with_lip(narrator_mouth_closed=True), 24)
    assert mouth_state_problems(with_lip(mouth_state=full), 24)
    assert mouth_state_problems(with_lip(narrator_mouth_closed=False), 24)
    assert mouth_state_problems(with_lip(mouth_state={**full, "3": "open_mumble"}), 24)
    assert mouth_state_problems(with_lip(mouth_state={str(s): "closed" for s in range(7)}), 24)
    assert mouth_state_problems(with_lip(narrator_mouth_closed=True, mouth_state={**full, "3": "open_non_verbal_breath"}), 24) == []


# ---- SX-01: 1-4 English sentences in overall_soundscape ----

@pytest.mark.parametrize("snd, ok", [
    (SOUND, True),
    ("overall_soundscape: Sound effects only: Rain. Wind. Water. Steps.", True),
    ("overall_soundscape: Sound effects only: One. Two. Three. Four. Five.", False),
    ("overall_soundscape: Sound effects only: Lluvia sobre la piedra húmeda.", False),
])
def test_sx01_soundscape_sentence_rule(snd, ok):
    assert ("SX-01" not in _codes_of(_prompt(snd=snd))) is ok


def test_sx01_missing_soundscape_line():
    assert "SX-01" in _codes_of(_prompt().replace(SOUND, "nothing here"))


# ---- lint_story on an emitted prompt: each code is reported, the clean compile is not ----

def _emit_tamper(text, extra):
    return text.replace("Picture 1 and Picture 2.", "Picture 1 and Picture 2. " + extra, 1)


TAMPERS = {
    "SL-01": lambda t: _emit_tamper(t, "He says (S1) hi."),
    "SL-02": lambda t: _emit_tamper(t, "Line [en] here."),
    "SL-03": lambda t: _emit_tamper(t, "Line <d>here</d>."),
    "AU-01": lambda t: _emit_tamper(t, "Voice <Audio 1> here."),
    "TG-01": lambda t: _emit_tamper(t, "@CHAR-01 here."),
    "TX-01": lambda t: _emit_tamper(t, 'A sign "OPEN" here.'),
    "LEN-01": lambda t: _emit_tamper(t, "x" * PROMPT_CHAR_LIMIT),
    "MO-01": lambda t: MOUTH_PERSON_RE.sub("lips move", t.replace(MOUTH_LOCK_PHRASE, "lips move")),
    "SX-01": lambda t: t.replace("Sound effects only:", "Sound effects only: One. Two. Three. Four. Five."),
}


@pytest.mark.parametrize("code", sorted(TAMPERS))
def test_lint_story_reports_each_code_on_the_emitted_prompt(tmp_path, code):
    story = build_story(str(tmp_path))
    text = compile_fl2va_prompt(story["episodes"][0]["shots"][0], story["registry"])["compiled_prompt"]
    tampered = TAMPERS[code](text)
    assert code in codes(lint_story(story, compiled={"SYN_A": tampered})["errors"])


def test_lint_story_reports_speech_and_stage_cue_codes_from_source(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["motion_7_stage"]["3_initiation"] += " He says (S2) now."
    assert "SL-01" in codes(lint_story(story)["errors"])
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][1]["dialogue_and_lip_lock"]["utterances"] = [copy.deepcopy(SPEECH_UTTERANCE)]
    assert "SL-04" in codes(lint_story(story)["errors"])


def test_compiler_refuses_speech_with_its_code(tmp_path):
    story = build_story(str(tmp_path))
    story["episodes"][0]["shots"][0]["sound_plan"]["overall_soundscape"] += " [Hindi] line."
    with pytest.raises(PromptRefused) as e:
        compile_fl2va_prompt(story["episodes"][0]["shots"][0], story["registry"])
    assert e.value.code == "SL-02"


# ---- SX-01 source rule: a sound cue in all 7 action sentences (owner 2026-11-07) ----

@pytest.mark.parametrize("cue_stages", [7, 6, 0])
def test_sx_min_zero_no_stage_error(tmp_path, cue_stages):
    """M-01 (D1 = B): sound cues left the action sentences, so no per-stage cue count is required any more."""
    story = build_story(str(tmp_path))
    story["registry"]["execution_profile"]["min_imd_body_chars"] = 50  # the short test stages are below the 600 default
    shot = story["episodes"][0]["shots"][0]
    for i, key in enumerate(STAGES):
        shot["motion_7_stage"][key] = "A sharp thud lands." if i < cue_stages else "The figure stands still."
    assert "SX-01" not in codes(lint_story(story)["errors"])


@pytest.mark.parametrize("replacement", ["Sati keeps their lips completely closed", "Sati speaks with moving lips",
                                         "Sati keeps their lips closed"])
def test_mo01_accepts_mouth_sentence(replacement):
    """M-01: the per-person mouth sentence from prompt_hygiene satisfies MO-01 without the positive lock phrase."""
    assert "MO-01" not in _codes_of(_prompt().replace(MOUTH_LOCK_PHRASE, replacement))
